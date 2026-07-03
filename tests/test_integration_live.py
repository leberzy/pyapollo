"""Integration tests against a live Apollo config server."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import pytest

from pyapollo import ApolloClient
from pyapollo.cache import cache_namespace_path

pytestmark = pytest.mark.integration

DEFAULT_SERVER = "http://testapollo.shebao.net:8080"
DEFAULT_APP_ID = "arch-service-diagnose"
DEFAULT_NAMESPACES = "application,prompt"


def _integration_settings() -> tuple[str, int, str, list[str]]:
    server = os.environ.get("APOLLO_SERVER", DEFAULT_SERVER)
    app_id = os.environ.get("APOLLO_APP_ID", DEFAULT_APP_ID)
    namespaces_raw = os.environ.get("APOLLO_NAMESPACE", DEFAULT_NAMESPACES)
    namespaces = [item.strip() for item in namespaces_raw.split(",") if item.strip()]

    parsed = urlparse(server)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError(f"Invalid APOLLO_SERVER: {server}")

    host = f"{parsed.scheme}://{parsed.hostname}"
    port = parsed.port or 8080
    return host, port, app_id, namespaces


@pytest.mark.integration
def test_live_apollo_add_change_listener(tmp_path: Path) -> None:
    host, port, app_id, namespaces = _integration_settings()
    events: list[str] = []

    client = ApolloClient(
        app_id=app_id,
        config_server_host=host,
        config_server_port=port,
        namespaces=namespaces,
        cache_file_dir_path=str(tmp_path),
        cycle_time=300,
    )
    try:
        client.add_change_listener(lambda event: events.append(event.namespace))
        snapshot = client._memory_cache.snapshot()
        assert snapshot
        for namespace in namespaces:
            assert namespace in snapshot
    finally:
        client.stop()


@pytest.mark.integration
def test_live_apollo_sync_client_fetch(tmp_path: Path) -> None:
    host, port, app_id, namespaces = _integration_settings()

    client = ApolloClient(
        app_id=app_id,
        config_server_host=host,
        config_server_port=port,
        namespaces=namespaces,
        cache_file_dir_path=str(tmp_path),
        cycle_time=300,
    )
    try:
        snapshot = client._memory_cache.snapshot()
        assert snapshot, "Expected at least one namespace loaded from Apollo"

        for namespace in namespaces:
            assert namespace in snapshot, f"Namespace {namespace} not loaded"
            cache_path = cache_namespace_path(str(tmp_path), app_id, "default", namespace)
            assert cache_path.is_file(), f"File cache missing for {namespace}"

        client.fetch_configuration()
        refreshed = client._memory_cache.snapshot()
        assert refreshed
        assert client.is_ready()
    finally:
        client.stop()
