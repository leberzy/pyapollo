"""Tests for process-wide Apollo client registry."""

from __future__ import annotations

import pytest

from pyapollo import ApolloClient, get_client, init_apollo, register_apollo_factory, require_client, reset_apollo, shutdown_apollo
from pyapollo.registry import is_apollo_initialized


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    reset_apollo()
    yield
    reset_apollo()


def _client(app_id: str = "demo") -> ApolloClient:
    return ApolloClient(
        app_id=app_id,
        config_server_host="http://cfg",
        autostart=False,
    )


def test_init_returns_same_instance() -> None:
    first = init_apollo(_client())
    second = init_apollo()
    assert first is second
    assert get_client() is first


def test_get_client_before_init_returns_none() -> None:
    assert get_client() is None
    assert not is_apollo_initialized()


def test_require_client_raises_when_not_initialized() -> None:
    with pytest.raises(RuntimeError, match="not initialized"):
        require_client()


def test_shutdown_clears_client() -> None:
    init_apollo(_client())
    shutdown_apollo()
    assert get_client() is None
    assert not is_apollo_initialized()


def test_register_factory_used_by_init() -> None:
    created: list[ApolloClient] = []

    def factory() -> ApolloClient:
        client = _client("from-factory")
        created.append(client)
        return client

    register_apollo_factory(factory)
    client = init_apollo()
    assert len(created) == 1
    assert client is created[0]
    assert client._app_id == "from-factory"


def test_cannot_register_factory_after_init() -> None:
    init_apollo(_client())
    with pytest.raises(RuntimeError, match="after client is initialized"):
        register_apollo_factory(_client)


def test_init_with_different_client_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    existing = _client("existing")
    other = _client("other")
    init_apollo(existing)

    with caplog.at_level("WARNING"):
        returned = init_apollo(other)

    assert returned is existing
    assert "different client" in caplog.text


def test_force_replaces_client() -> None:
    first = init_apollo(_client("first"))
    second = _client("second")
    replaced = init_apollo(second, force=True)
    assert replaced is second
    assert get_client() is second
    assert first is not second


def test_reset_clears_factory() -> None:
    register_apollo_factory(lambda: _client("factory"))
    init_apollo()
    reset_apollo()
    assert get_client() is None

    register_apollo_factory(lambda: _client("factory-2"))
    client = init_apollo()
    assert client._app_id == "factory-2"
