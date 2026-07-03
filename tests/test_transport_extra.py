"""Additional transport layer tests."""

import pytest
import responses

from pyapollo.core.exceptions import ApolloClientError
from pyapollo.core.models import ServiceInstance
from pyapollo.transport import (
    ApolloConfigApi,
    ConfigServiceLocator,
    RequestsTransport,
    parse_service_instances,
    service_to_endpoint,
)


def test_parse_service_instances_invalid() -> None:
    assert parse_service_instances({}) == []
    assert parse_service_instances([{"foo": "bar"}]) == []


def test_service_to_endpoint() -> None:
    homepage, host, port = service_to_endpoint(
        ServiceInstance(home_page_url="http://cfg.example.com:9090")
    )
    assert homepage == "http://cfg.example.com:9090"
    assert host == "http://cfg.example.com"
    assert port == 9090


@responses.activate
def test_custom_config_server_locator() -> None:
    transport = RequestsTransport()
    locator = ConfigServiceLocator(
        transport,
        custom_homepage_urls=["http://custom:8080"],
    )
    services = locator.discover()
    assert services[0].home_page_url == "http://custom:8080"


@responses.activate
def test_fetch_config_error_status() -> None:
    transport = RequestsTransport()
    responses.add(
        responses.GET,
        "http://config:8080/configs/app/default/ns",
        status=500,
    )
    api = ApolloConfigApi(
        transport,
        app_id="app",
        app_secret=None,
        cluster="default",
    )
    with pytest.raises(ApolloClientError):
        api.fetch_config("http://config:8080", "ns")


@responses.activate
def test_meta_discovery_empty_raises() -> None:
    transport = RequestsTransport()
    responses.add(
        responses.GET,
        "http://meta:8080/services/config?appId=app",
        json=[],
        status=200,
    )
    locator = ConfigServiceLocator(
        transport,
        meta_server_address="http://meta:8080",
        app_id="app",
    )
    with pytest.raises(ApolloClientError):
        locator.discover()


def test_requests_transport_close() -> None:
    transport = RequestsTransport()
    transport.close()
