"""Tests for settings configuration."""

import pytest

from pyapollo.config import ApolloSettingsConfig
from pyapollo.config.settings import resolve_label


def test_from_env_file_ignores_non_apollo_keys(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APOLLO_META_SERVER_ADDRESS=http://localhost:8080\n"
        "APOLLO_APP_ID=test-app\n"
        "DATABASE_URL=postgres://localhost/db\n"
        "REDIS_HOST=127.0.0.1\n",
        encoding="utf-8",
    )

    settings = ApolloSettingsConfig.from_env_file(str(env_file))

    assert settings.meta_server_address == "http://localhost:8080"
    assert settings.app_id == "test-app"


def test_namespaces_from_comma_separated_string() -> None:
    settings = ApolloSettingsConfig(
        meta_server_address="http://localhost:8080",
        app_id="test-app",
        namespaces="app1,app2,app3",
    )
    assert settings.namespaces == ["app1", "app2", "app3"]


def test_namespaces_from_list() -> None:
    settings = ApolloSettingsConfig(
        meta_server_address="http://localhost:8080",
        app_id="test-app",
        namespaces=["app1", "app2"],
    )
    assert settings.namespaces == ["app1", "app2"]


def test_label_from_apollo_label_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APOLLO_LABEL", "apollo-gray")
    assert resolve_label() == "apollo-gray"


def test_label_from_app_label_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_LABEL", "java-gray-label")
    settings = ApolloSettingsConfig(
        meta_server_address="http://localhost:8080",
        app_id="test-app",
    )
    assert settings.label == "java-gray-label"


def test_label_apollo_label_takes_priority_over_app_label(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APOLLO_LABEL", "apollo-first")
    monkeypatch.setenv("APP_LABEL", "java-second")
    assert resolve_label() == "apollo-first"


def test_label_explicit() -> None:
    settings = ApolloSettingsConfig(
        meta_server_address="http://localhost:8080",
        app_id="test-app",
        label="explicit-label",
    )
    assert settings.label == "explicit-label"


def test_namespaces_default() -> None:
    settings = ApolloSettingsConfig(
        meta_server_address="http://localhost:8080",
        app_id="test-app",
    )
    assert settings.namespaces == ["application"]
