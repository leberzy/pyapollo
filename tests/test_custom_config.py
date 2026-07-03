"""Tests for custom config server URL building."""

from pyapollo.core.urls import build_custom_config_server_url


def test_custom_config_server_defaults() -> None:
    full, host, port = build_custom_config_server_url("http://test.example.com", None)
    assert host == "http://test.example.com"
    assert port == 8080
    assert full == "http://test.example.com:8080"


def test_custom_config_server_bare_hostname() -> None:
    full, host, port = build_custom_config_server_url("localhost", 9090)
    assert full == "http://localhost:9090"
    assert host == "http://localhost"
    assert port == 9090
