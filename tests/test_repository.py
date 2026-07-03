"""Tests for repository layer (long-poll orchestration, aligned with Java client)."""

from __future__ import annotations

import re
import threading
import time

import pytest
import responses

from pyapollo.core.models import ConfigResult
from pyapollo.repository import SyncConfigRepository, SyncRepositoryHooks
from pyapollo.transport import ApolloConfigApi, ConfigServiceLocator, RequestsTransport


@pytest.fixture
def transport() -> RequestsTransport:
    return RequestsTransport(default_timeout=5)


def _make_repository(
    transport: RequestsTransport,
    homepage: str = "http://config:8080",
) -> tuple[SyncConfigRepository, dict[str, object]]:
    state: dict[str, object] = {
        "homepage": homepage,
        "cache": {},
        "applied": [],
    }

    def get_homepage() -> str | None:
        return state["homepage"]  # type: ignore[return-value]

    def set_homepage(url: str) -> None:
        state["homepage"] = url

    def get_cached(ns: str) -> dict[str, str]:
        cache = state["cache"]
        assert isinstance(cache, dict)
        value = cache.get(ns, {})
        return dict(value) if isinstance(value, dict) else {}

    def apply_config(result: ConfigResult, event: object) -> None:
        applied = state["applied"]
        assert isinstance(applied, list)
        cache = state["cache"]
        assert isinstance(cache, dict)
        cache[result.namespace] = dict(result.configurations)
        applied.append((result.namespace, result.release_key, event))

    locator = ConfigServiceLocator(
        transport,
        meta_server_address="http://meta:8080",
        app_id="my-app",
        local_ip="10.0.0.1",
        custom_homepage_urls=[homepage],
    )
    api = ApolloConfigApi(
        transport,
        app_id="my-app",
        app_secret=None,
        cluster="default",
        local_ip="10.0.0.1",
    )
    repo = SyncConfigRepository(
        api,
        locator,
        ["application"],
        hooks=SyncRepositoryHooks(
            get_homepage=get_homepage,
            set_homepage=set_homepage,
            get_cached_config=get_cached,
            apply_config=apply_config,
            on_namespace_fetch_error=lambda ns, exc: None,
            switch_config_server=lambda exclude: None,
        ),
        cycle_time=60,
        fetch_timeout=5,
    )
    return repo, state


@responses.activate
def test_sync_namespace_applies_config(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    responses.add(
        responses.GET,
        f"{homepage}/configs/my-app/default/application",
        json={"configurations": {"k": "v"}, "releaseKey": "rk-1"},
        status=200,
    )
    repo, state = _make_repository(transport, homepage)
    assert repo.sync_namespace("application") is True
    cache = state["cache"]
    assert isinstance(cache, dict)
    assert cache["application"] == {"k": "v"}
    assert repo._release_keys["application"] == "rk-1"


@responses.activate
def test_sync_namespace_304_no_apply(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    responses.add(
        responses.GET,
        f"{homepage}/configs/my-app/default/application",
        status=304,
        match=[responses.matchers.query_param_matcher({"releaseKey": "rk-1"})],
    )
    repo, state = _make_repository(transport, homepage)
    repo._release_keys["application"] = "rk-1"
    state["cache"] = {"application": {"k": "v"}}
    assert repo.sync_namespace("application") is False


@responses.activate
def test_long_poll_triggers_namespace_refresh(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    responses.add(
        responses.GET,
        re.compile(rf"{homepage}/notifications/v2"),
        json=[{"namespaceName": "application", "notificationId": 42}],
        status=200,
    )
    responses.add(
        responses.GET,
        f"{homepage}/configs/my-app/default/application",
        json={"configurations": {"k": "new"}, "releaseKey": "rk-2"},
        status=200,
    )

    repo, state = _make_repository(transport, homepage)
    repo._stop_event.set()
    changed = repo._long_poll_once()
    assert changed == ["application"]
    assert repo.notifications["application"].notification_id == 42
    assert repo.sync_namespace("application") is True
    cache = state["cache"]
    assert isinstance(cache, dict)
    assert cache["application"] == {"k": "new"}


@responses.activate
def test_long_poll_304_returns_empty(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    responses.add(
        responses.GET,
        re.compile(rf"{homepage}/notifications/v2"),
        status=304,
    )
    repo, _ = _make_repository(transport, homepage)
    assert repo._long_poll_once() == []


@responses.activate
def test_sync_namespace_fetch_error_invokes_hooks(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    responses.add(
        responses.GET,
        f"{homepage}/configs/my-app/default/application",
        status=500,
    )
    errors: list[str] = []
    repo, _ = _make_repository(transport, homepage)
    repo = SyncConfigRepository(
        repo._api,
        repo._locator,
        ["application"],
        hooks=SyncRepositoryHooks(
            get_homepage=lambda: homepage,
            set_homepage=lambda url: None,
            get_cached_config=lambda ns: {},
            apply_config=lambda result, event: None,
            on_namespace_fetch_error=lambda ns, exc: errors.append(ns),
            switch_config_server=lambda exclude: None,
        ),
        cycle_time=60,
    )
    assert repo.sync_namespace("application") is False
    assert errors == ["application"]


def test_set_namespaces_adds_and_removes(transport: RequestsTransport) -> None:
    repo, _ = _make_repository(transport)
    repo.set_namespaces(["application", "redis"])
    assert set(repo.notifications) == {"application", "redis"}
    repo.set_namespaces(["application"])
    assert set(repo.notifications) == {"application"}


def test_sync_poll_homepage_pins_long_poll_target(transport: RequestsTransport) -> None:
    repo, _ = _make_repository(transport)
    repo.sync_poll_homepage("http://config:8080/")
    assert repo._poll_homepage == "http://config:8080"
    repo.sync_poll_homepage(None)
    assert repo._poll_homepage is None


@responses.activate
def test_resolve_poll_homepage_via_locator(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    state: dict[str, str | None] = {"homepage": None}

    locator = ConfigServiceLocator(
        transport,
        meta_server_address="http://meta:8080",
        app_id="my-app",
        custom_homepage_urls=[homepage],
    )
    api = ApolloConfigApi(
        transport,
        app_id="my-app",
        app_secret=None,
        cluster="default",
    )
    repo = SyncConfigRepository(
        api,
        locator,
        ["application"],
        hooks=SyncRepositoryHooks(
            get_homepage=lambda: state["homepage"],
            set_homepage=lambda url: state.update(homepage=url),
            get_cached_config=lambda ns: {},
            apply_config=lambda result, event: None,
            on_namespace_fetch_error=lambda ns, exc: None,
            switch_config_server=lambda exclude: None,
        ),
    )
    resolved = repo._resolve_poll_homepage()
    assert resolved == homepage
    assert state["homepage"] == homepage


def test_exponential_backoff_doubles_until_cap() -> None:
    from pyapollo.core.backoff import ExponentialBackoff

    backoff = ExponentialBackoff(1, 8)
    assert backoff.fail() == 1
    assert backoff.fail() == 2
    assert backoff.fail() == 4
    assert backoff.fail() == 8
    assert backoff.fail() == 8
    backoff.success()
    assert backoff.fail() == 1


@responses.activate
def test_background_loop_periodic_refresh(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    responses.add(
        responses.GET,
        re.compile(rf"{homepage}/notifications/v2"),
        status=304,
    )
    responses.add(
        responses.GET,
        f"{homepage}/configs/my-app/default/application",
        json={"configurations": {"x": "1"}, "releaseKey": "rk"},
        status=200,
    )

    repo, state = _make_repository(transport, homepage)
    repo._cycle_time = 0
    repo._last_periodic = time.monotonic() - 1
    repo._stop_event.clear()
    done = threading.Event()

    def run_once() -> None:
        try:
            repo._long_poll_once()
            if time.monotonic() - repo._last_periodic >= repo._cycle_time:
                repo.sync_all()
                repo._last_periodic = time.monotonic()
        finally:
            repo._stop_event.set()
            done.set()

    threading.Thread(target=run_once, daemon=True).start()
    assert done.wait(timeout=5)
    cache = state["cache"]
    assert isinstance(cache, dict)
    assert cache.get("application") == {"x": "1"}
