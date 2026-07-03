"""Tests for transport layer (aligned with Java Apollo client HTTP API)."""

import re

import pytest
import responses

from pyapollo.core.constants import DEFAULT_NOTIFICATION_ID
from pyapollo.core.models import Notification
from pyapollo.core.urls import build_meta_service_url
from pyapollo.transport import (
    ApolloConfigApi,
    ConfigServiceLocator,
    RequestsTransport,
    parse_service_instances,
)


@pytest.fixture
def transport() -> RequestsTransport:
    return RequestsTransport(default_timeout=5)


def test_parse_service_instances() -> None:
    payload = [{"homepageUrl": "http://config:8080", "instanceId": "i1"}]
    services = parse_service_instances(payload)
    assert len(services) == 1
    assert services[0].home_page_url == "http://config:8080"


@responses.activate
def test_meta_discovery_includes_app_id_and_ip(transport: RequestsTransport) -> None:
    meta = "http://meta:8080"
    app_id = "my-app"
    ip = "10.0.0.1"
    url = build_meta_service_url(meta, app_id, ip)
    responses.add(
        responses.GET,
        url,
        json=[{"homepageUrl": "http://config:8080", "instanceId": "cfg-1"}],
        status=200,
    )

    locator = ConfigServiceLocator(
        transport,
        meta_server_address=meta,
        app_id=app_id,
        local_ip=ip,
    )
    services = locator.discover()
    assert services[0].home_page_url == "http://config:8080"


@responses.activate
def test_fetch_config_with_release_key_and_ip(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    responses.add(
        responses.GET,
        f"{homepage}/configs/my-app/default/application",
        json={
            "configurations": {"k": "v"},
            "releaseKey": "rk-1",
        },
        status=200,
        match=[
            responses.matchers.query_param_matcher(
                {"releaseKey": "old-rk", "ip": "10.0.0.2"},
            )
        ],
    )

    api = ApolloConfigApi(
        transport,
        app_id="my-app",
        app_secret=None,
        cluster="default",
        local_ip="10.0.0.2",
    )
    result = api.fetch_config(
        homepage,
        "application",
        release_key="old-rk",
    )
    assert result is not None
    assert result.configurations == {"k": "v"}
    assert result.release_key == "rk-1"


@responses.activate
def test_fetch_config_with_label(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    responses.add(
        responses.GET,
        f"{homepage}/configs/my-app/default/application",
        json={
            "configurations": {"k": "gray-v"},
            "releaseKey": "rk-gray",
        },
        status=200,
        match=[
            responses.matchers.query_param_matcher(
                {"label": "gray-label-1", "ip": "10.0.0.2"},
            )
        ],
    )

    api = ApolloConfigApi(
        transport,
        app_id="my-app",
        app_secret=None,
        cluster="default",
        local_ip="10.0.0.2",
        label="gray-label-1",
    )
    result = api.fetch_config(homepage, "application")
    assert result is not None
    assert result.configurations == {"k": "gray-v"}


@responses.activate
def test_poll_notifications_includes_label(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    responses.add(
        responses.GET,
        re.compile(re.escape(homepage) + r"/notifications/v2\?"),
        json=[{"namespaceName": "application", "notificationId": 456}],
        status=200,
    )
    api = ApolloConfigApi(
        transport,
        app_id="my-app",
        app_secret=None,
        cluster="default",
        label="gray-label-1",
    )
    updates = api.poll_notifications(
        homepage,
        [Notification(namespace_name="application", notification_id=-1)],
        timeout=90,
    )
    assert updates[0].notification_id == 456
    assert "label=gray-label-1" in responses.calls[0].request.url


@responses.activate
def test_fetch_config_304_returns_none(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    responses.add(
        responses.GET,
        f"{homepage}/configs/my-app/default/application",
        status=304,
    )
    api = ApolloConfigApi(
        transport,
        app_id="my-app",
        app_secret=None,
        cluster="default",
    )
    assert api.fetch_config(homepage, "application", release_key="rk") is None


@responses.activate
def test_poll_notifications_long_poll(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    responses.add(
        responses.GET,
        re.compile(re.escape(homepage) + r"/notifications/v2\?"),
        json=[{"namespaceName": "application", "notificationId": 123}],
        status=200,
    )
    api = ApolloConfigApi(
        transport,
        app_id="my-app",
        app_secret=None,
        cluster="default",
        local_ip="10.0.0.3",
    )
    updates = api.poll_notifications(
        homepage,
        [Notification(namespace_name="application", notification_id=DEFAULT_NOTIFICATION_ID)],
        timeout=90,
    )
    assert len(updates) == 1
    assert updates[0].notification_id == 123


@responses.activate
def test_poll_notifications_304(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    responses.add(
        responses.GET,
        re.compile(re.escape(homepage) + r"/notifications/v2\?"),
        status=304,
    )
    api = ApolloConfigApi(
        transport,
        app_id="my-app",
        app_secret=None,
        cluster="default",
    )
    updates = api.poll_notifications(
        homepage,
        [Notification(namespace_name="application", notification_id=-1)],
        timeout=90,
    )
    assert updates == []


@responses.activate
def test_locator_exclude_failed_server(transport: RequestsTransport) -> None:
    meta = "http://meta:8080"
    url = build_meta_service_url(meta, "app", None)
    responses.add(
        responses.GET,
        url,
        json=[
            {"homepageUrl": "http://bad:8080"},
            {"homepageUrl": "http://good:8080"},
        ],
        status=200,
    )
    locator = ConfigServiceLocator(transport, meta_server_address=meta, app_id="app")
    service = locator.choose_one(exclude_homepage="http://bad:8080")
    assert service.home_page_url == "http://good:8080"


@responses.activate
def test_locator_exclude_normalizes_trailing_slash(transport: RequestsTransport) -> None:
    meta = "http://meta:8080"
    url = build_meta_service_url(meta, "app", None)
    responses.add(
        responses.GET,
        url,
        json=[
            {"homepageUrl": "http://bad:8080/"},
            {"homepageUrl": "http://good:8080"},
        ],
        status=200,
    )
    locator = ConfigServiceLocator(transport, meta_server_address=meta, app_id="app")
    service = locator.choose_one(exclude_homepage="http://bad:8080")
    assert service.home_page_url == "http://good:8080"


@responses.activate
def test_poll_notifications_parses_string_notification_id(transport: RequestsTransport) -> None:
    homepage = "http://config:8080"
    responses.add(
        responses.GET,
        re.compile(re.escape(homepage) + r"/notifications/v2\?"),
        json=[{"namespaceName": "application", "notificationId": "456"}],
        status=200,
    )
    api = ApolloConfigApi(
        transport,
        app_id="my-app",
        app_secret=None,
        cluster="default",
    )
    updates = api.poll_notifications(
        homepage,
        [Notification(namespace_name="application", notification_id=-1)],
        timeout=90,
    )
    assert updates[0].notification_id == 456
