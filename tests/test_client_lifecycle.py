"""Tests for Apollo client lifecycle (no real server)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import responses
from aioresponses import aioresponses

from pyapollo import ApolloClient, AsyncApolloClient


@responses.activate
def test_autostart_false_requires_explicit_start(tmp_path: Path) -> None:
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
    assert not client.is_ready()
    assert not client._started

    client.start()
    assert client.is_ready()
    assert client.get_value("k") == "v"
    assert client.get_int("missing", 0) == 0

    client.stop()
    assert not client._started


@responses.activate
def test_context_manager_starts_and_stops(tmp_path: Path) -> None:
    homepage = "http://config:8080"
    host = "http://config"
    responses.add(
        responses.GET,
        f"{homepage}/configs/demo/default/application",
        json={"configurations": {"flag": "true"}, "releaseKey": "rk"},
        status=200,
    )
    responses.add(
        responses.GET,
        re.compile(rf"{homepage}/notifications/v2"),
        status=304,
    )

    with ApolloClient(
        app_id="demo",
        config_server_host=host,
        config_server_port=8080,
        namespaces=["application"],
        cache_file_dir_path=str(tmp_path),
        autostart=False,
    ) as client:
        assert client.is_ready()
        assert client.get_bool("flag") is True

    assert not client._started


def test_constructing_twice_creates_independent_instances(tmp_path: Path) -> None:
    a = ApolloClient(
        app_id="a",
        config_server_host="http://cfg",
        autostart=False,
        cache_file_dir_path=str(tmp_path / "a"),
    )
    b = ApolloClient(
        app_id="b",
        config_server_host="http://cfg",
        autostart=False,
        cache_file_dir_path=str(tmp_path / "b"),
    )
    assert a is not b
    assert a._app_id != b._app_id


@pytest.mark.asyncio
async def test_async_autostart_false_skips_start_on_enter(tmp_path: Path) -> None:
    async with AsyncApolloClient(
        app_id="demo",
        config_server_host="http://config",
        config_server_port=8080,
        namespaces=["application"],
        cache_file_dir_path=str(tmp_path),
        autostart=False,
    ) as client:
        assert not client._started
        assert not client.is_ready()

    assert not client._started


@pytest.mark.asyncio
async def test_async_autostart_true_starts_on_enter(tmp_path: Path) -> None:
    homepage = "http://config:8080"
    host = "http://config"
    with aioresponses() as mocked:
        mocked.get(
            re.compile(rf"{homepage}/configs/demo/default/application"),
            payload={"configurations": {"k": "v"}, "releaseKey": "rk"},
        )
        mocked.get(re.compile(rf"{homepage}/notifications/v2"), status=304, repeat=True)

        async with AsyncApolloClient(
            app_id="demo",
            config_server_host=host,
            config_server_port=8080,
            namespaces=["application"],
            cache_file_dir_path=str(tmp_path),
            autostart=True,
        ) as client:
            assert client._started
            assert client.is_ready()
            assert await client.get_value("k") == "v"
