"""Tests for ApolloConfigProvider facade."""

from __future__ import annotations

import pytest

from pyapollo import ApolloConfigProvider, ApolloClient, get_client, reset_apollo


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    reset_apollo()
    yield
    reset_apollo()


def test_init_is_idempotent() -> None:
    first = ApolloConfigProvider.init(
        app_id="demo",
        meta_server_address="http://meta:8080",
        autostart=False,
    )
    second = ApolloConfigProvider.init()
    assert first is second


def test_get_requires_init() -> None:
    with pytest.raises(RuntimeError, match="not initialized"):
        ApolloConfigProvider.get("k")


def test_get_delegates_to_client() -> None:
    client = ApolloClient(
        app_id="demo",
        config_server_host="http://cfg",
        autostart=False,
    )
    client._memory_cache.set("application", {"flag": "true"})
    ApolloConfigProvider.init(client=client)  # type: ignore[call-arg]
    assert ApolloConfigProvider.get_bool("flag") is True


def test_stop_clears_registry() -> None:
    ApolloConfigProvider.init(
        app_id="demo",
        meta_server_address="http://meta:8080",
        autostart=False,
    )
    ApolloConfigProvider.stop()
    assert get_client() is None


def test_is_ready_without_init() -> None:
    assert not ApolloConfigProvider.is_ready()
