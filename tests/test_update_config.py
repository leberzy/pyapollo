"""Tests for update_config rebuild and URL normalization fixes."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest
import responses
from aioresponses import aioresponses

from pyapollo import ApolloClient, AsyncApolloClient
from pyapollo.core.models import Notification
from pyapollo.core.urls import build_custom_config_server_url


def test_build_custom_config_server_url_adds_scheme_for_bare_host() -> None:
    full, host, port = build_custom_config_server_url("localhost", 8080)
    assert full == "http://localhost:8080"
    assert host == "http://localhost"
    assert port == 8080


@responses.activate
def test_sync_update_config_preserves_repository_state(tmp_path: Path) -> None:
    homepage = "http://config:8080"
    host = "http://config"
    responses.add(
        responses.GET,
        f"{homepage}/configs/demo/default/application",
        json={"configurations": {"k": "v"}, "releaseKey": "rk-1"},
        status=200,
    )
    responses.add(
        responses.GET,
        re.compile(rf"{homepage}/notifications/v2"),
        status=304,
    )
    responses.add(
        responses.GET,
        re.compile(rf"{homepage}/notifications/v2"),
        status=304,
    )

    client = ApolloClient(
        app_id="demo",
        config_server_host=host,
        config_server_port=8080,
        namespaces=["application"],
        cache_file_dir_path=str(tmp_path),
        autostart=False,
    )
    client.start()
    client._repository._notifications["application"] = Notification(
        namespace_name="application",
        notification_id=12345,
    )
    client._repository._release_keys["application"] = "rk-1"

    client.update_config(timeout=15)

    assert client._timeout == 15
    assert client._repository._notifications["application"].notification_id == 12345
    assert client._repository._release_keys["application"] == "rk-1"
    assert client._started
    assert client._repository._thread is not None
    assert client._repository._thread.is_alive()

    client.stop()
    assert client._repository._thread is None


@responses.activate
def test_sync_update_config_custom_host_updates_homepage(tmp_path: Path) -> None:
    homepage = "http://config:8080"
    host = "http://config"
    responses.add(
        responses.GET,
        f"{homepage}/configs/demo/default/application",
        json={"configurations": {"k": "v"}, "releaseKey": "rk"},
        status=200,
    )
    responses.add(
        responses.GET,
        "http://localhost:9090/configs/demo/default/application",
        json={"configurations": {"k": "v2"}, "releaseKey": "rk2"},
        status=200,
    )
    responses.add(
        responses.GET,
        re.compile(rf"{homepage}/notifications/v2"),
        status=304,
    )
    responses.add(
        responses.GET,
        re.compile(r"http://localhost:9090/notifications/v2"),
        status=304,
    )

    client = ApolloClient(
        app_id="demo",
        config_server_host=host,
        config_server_port=8080,
        namespaces=["application"],
        cache_file_dir_path=str(tmp_path),
        autostart=False,
    )
    client.start()
    client.update_config(config_server_host="localhost", config_server_port=9090)

    assert client._config_homepage_url == "http://localhost:9090"
    assert client.get_value("k") == "v2"
    client.stop()


@pytest.mark.asyncio
async def test_async_update_config_rebuild_keeps_session_usable(tmp_path: Path) -> None:
    homepage = "http://config:8080"
    host = "http://config"
    with aioresponses() as mocked:
        mocked.get(
            re.compile(rf"{homepage}/configs/demo/default/application"),
            payload={"configurations": {"k": "v"}, "releaseKey": "rk"},
            repeat=True,
        )
        mocked.get(re.compile(rf"{homepage}/notifications/v2"), status=304, repeat=True)

        async with AsyncApolloClient(
            app_id="demo",
            config_server_host=host,
            config_server_port=8080,
            namespaces=["application"],
            cache_file_dir_path=str(tmp_path),
        ) as client:
            await client.update_cache("application", {"k": "v"})
            client._repository._notifications["application"] = Notification(
                namespace_name="application",
                notification_id=99,
            )
            await client.update_config(timeout=12)
            assert client._timeout == 12
            assert client._repository._notifications["application"].notification_id == 99
            assert client._transport.session is not None
            assert not client._transport.session.closed
            assert await client.get_value("k") == "v"


@responses.activate
def test_sync_update_config_cluster_fetches_with_new_cluster(tmp_path: Path) -> None:
    homepage = "http://config:8080"
    host = "http://config"
    responses.add(
        responses.GET,
        f"{homepage}/configs/demo/default/application",
        json={"configurations": {"k": "default"}, "releaseKey": "rk-default"},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{homepage}/configs/demo/prod/application",
        json={"configurations": {"k": "prod"}, "releaseKey": "rk-prod"},
        status=200,
    )
    responses.add(
        responses.GET,
        re.compile(rf"{homepage}/notifications/v2"),
        status=304,
    )

    client = ApolloClient(
        app_id="demo",
        config_server_host=host,
        config_server_port=8080,
        cluster="default",
        namespaces=["application"],
        cache_file_dir_path=str(tmp_path),
        autostart=False,
    )
    client.start()
    client.update_config(cluster="prod")

    assert client._cluster == "prod"
    assert client.get_value("k") == "prod"
    client.stop()


@responses.activate
def test_sync_update_config_adds_namespace_fetches_immediately(tmp_path: Path) -> None:
    homepage = "http://config:8080"
    host = "http://config"
    responses.add(
        responses.GET,
        f"{homepage}/configs/demo/default/application",
        json={"configurations": {"k": "v"}, "releaseKey": "rk-app"},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{homepage}/configs/demo/default/redis",
        json={"configurations": {"host": "127.0.0.1"}, "releaseKey": "rk-redis"},
        status=200,
    )
    responses.add(
        responses.GET,
        re.compile(rf"{homepage}/notifications/v2"),
        status=304,
    )

    client = ApolloClient(
        app_id="demo",
        config_server_host=host,
        config_server_port=8080,
        namespaces=["application"],
        cache_file_dir_path=str(tmp_path),
        autostart=False,
    )
    client.start()
    client.update_config(namespaces=["application", "redis"])

    assert client.get_value("host", namespace="redis") == "127.0.0.1"
    client.stop()


@responses.activate
def test_update_config_custom_host_long_poll_targets_new_server(tmp_path: Path) -> None:
    old_homepage = "http://config:8080"
    new_homepage = "http://localhost:9090"
    host = "http://config"
    responses.add(
        responses.GET,
        f"{old_homepage}/configs/demo/default/application",
        json={"configurations": {"k": "v"}, "releaseKey": "rk"},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{new_homepage}/configs/demo/default/application",
        json={"configurations": {"k": "v2"}, "releaseKey": "rk2"},
        status=200,
    )
    responses.add(
        responses.GET,
        re.compile(rf"{re.escape(old_homepage)}/notifications/v2"),
        status=304,
    )
    responses.add(
        responses.GET,
        re.compile(rf"{re.escape(new_homepage)}/notifications/v2"),
        status=304,
    )

    client = ApolloClient(
        app_id="demo",
        config_server_host=host,
        config_server_port=8080,
        namespaces=["application"],
        cache_file_dir_path=str(tmp_path),
        autostart=False,
    )
    client.start()
    client.update_config(config_server_host="localhost", config_server_port=9090)

    assert client._repository._poll_homepage == new_homepage
    client._repository._long_poll_once()
    assert client.get_value("k") == "v2"
    client.stop()


@responses.activate
def test_sync_update_config_restarts_background_after_fetch(tmp_path: Path) -> None:
    homepage = "http://config:8080"
    host = "http://config"
    config_body = {"configurations": {"k": "v"}, "releaseKey": "rk"}
    responses.add(
        responses.GET,
        f"{homepage}/configs/demo/default/application",
        json=config_body,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{homepage}/configs/demo/default/application",
        json=config_body,
        status=200,
    )
    responses.add(
        responses.GET,
        re.compile(rf"{homepage}/notifications/v2"),
        status=304,
    )
    responses.add(
        responses.GET,
        re.compile(rf"{homepage}/notifications/v2"),
        status=304,
    )

    client = ApolloClient(
        app_id="demo",
        config_server_host=host,
        config_server_port=8080,
        namespaces=["application"],
        cache_file_dir_path=str(tmp_path),
        autostart=False,
    )
    client.start()
    assert client._repository._thread is not None
    assert client._repository._thread.is_alive()

    client.update_config(timeout=20)

    assert client._started
    assert client._repository._thread is not None
    assert client._repository._thread.is_alive()
    client.stop()


@patch("pyapollo.sync.get_local_ip", return_value="10.1.2.3")
def test_sync_update_config_ip_uses_hint_host(
    mock_get_local_ip: object, tmp_path: Path
) -> None:
    client = ApolloClient(
        app_id="demo",
        meta_server_address="http://old-meta:8080",
        namespaces=["application"],
        cache_file_dir_path=str(tmp_path),
        autostart=False,
    )
    with patch.object(client, "update_config_server"), patch.object(
        client, "fetch_configuration"
    ):
        client.update_config(meta_server_address="http://new-meta:9090", ip=None)

    mock_get_local_ip.assert_called_with(  # type: ignore[attr-defined]
        None,
        hint_host="http://new-meta:9090",
    )


@pytest.mark.asyncio
@patch("pyapollo.async_.get_local_ip", return_value="10.1.2.3")
async def test_async_update_config_ip_uses_hint_host(
    mock_get_local_ip: object, tmp_path: Path
) -> None:
    client = AsyncApolloClient(
        app_id="demo",
        meta_server_address="http://old-meta:8080",
        config_server_host="http://config",
        config_server_port=8080,
        namespaces=["application"],
        cache_file_dir_path=str(tmp_path),
        autostart=False,
    )
    try:
        await client.update_config(config_server_host="http://new-config:9090", ip=None)

        mock_get_local_ip.assert_called_with(  # type: ignore[attr-defined]
            None,
            hint_host="http://new-config:9090",
        )
    finally:
        await client.stop()
