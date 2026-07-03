"""Tests for urls module."""

import pytest

from pyapollo.core.models import Notification
from pyapollo.core.urls import (
    build_config_url,
    build_custom_config_server_url,
    build_meta_service_url,
    build_notifications_url,
    parse_homepage_url,
)


def test_parse_homepage_url_http() -> None:
    base, port = parse_homepage_url("http://config.example.com:8080")
    assert base == "http://config.example.com"
    assert port == 8080


def test_parse_homepage_url_https_default_port() -> None:
    base, port = parse_homepage_url("https://config.example.com")
    assert base == "https://config.example.com"
    assert port == 443


def test_parse_homepage_url_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid homepage URL"):
        parse_homepage_url("not-a-url")


def test_build_meta_service_url() -> None:
    url = build_meta_service_url("http://meta:8080", "my-app", "10.0.0.1")
    assert url == "http://meta:8080/services/config?appId=my-app&ip=10.0.0.1"


def test_build_notifications_url_with_ip_and_datacenter() -> None:
    url = build_notifications_url(
        "http://host:8080",
        "app",
        "default",
        [Notification(namespace_name="application", notification_id=-1)],
        ip="10.0.0.1",
        data_center="dc1",
    )
    assert "ip=10.0.0.1" in url
    assert "dataCenter=dc1" in url


def test_build_config_url_basic() -> None:
    url = build_config_url(
        "http://host:8080",
        "app",
        "default",
        "application",
    )
    assert url == "http://host:8080/configs/app/default/application"


def test_build_config_url_with_query_params() -> None:
    url = build_config_url(
        "http://host:8080",
        "app",
        "default",
        "application",
        release_key="rk1",
        ip="10.0.0.1",
        label="gray",
    )
    assert "releaseKey=rk1" in url
    assert "ip=10.0.0.1" in url
    assert "label=gray" in url


def test_build_notifications_url_with_label() -> None:
    url = build_notifications_url(
        "http://host:8080",
        "app",
        "default",
        [Notification(namespace_name="application", notification_id=-1)],
        ip="10.0.0.1",
        label="gray-label",
    )
    assert "label=gray-label" in url
    assert "ip=10.0.0.1" in url


def test_build_notifications_url() -> None:
    url = build_notifications_url(
        "http://host:8080",
        "app",
        "default",
        [Notification(namespace_name="application", notification_id=-1)],
    )
    assert url.startswith("http://host:8080/notifications/v2?")
    assert "appId=app" in url
    assert "cluster=default" in url


def test_build_custom_config_server_url() -> None:
    full, host, port = build_custom_config_server_url("http://custom", 9090)
    assert full == "http://custom:9090"
    assert host == "http://custom"
    assert port == 9090
