"""Tests for typed configuration getters."""

from pyapollo.cache import MemoryCache
from pyapollo.core.getters import get_bool, get_float, get_int, get_json_value, get_list, get_value


def test_get_value_and_typed_accessors() -> None:
    cache = MemoryCache()
    cache.set(
        "application",
        {
            "count": "42",
            "enabled": "true",
            "ratio": "3.14",
            "tags": "a, b,c",
            "meta": '{"x": 1}',
        },
    )

    assert get_value(cache, "count") == "42"
    assert get_int(cache, "count") == 42
    assert get_bool(cache, "enabled") is True
    assert get_float(cache, "ratio") == 3.14
    assert get_list(cache, "tags") == ["a", "b", "c"]
    assert get_json_value(cache, "meta") == {"x": 1}


def test_get_typed_defaults_on_missing_or_invalid() -> None:
    cache = MemoryCache()
    cache.set("application", {"bad_int": "x", "bad_bool": "maybe"})

    assert get_value(cache, "missing", "d") == "d"
    assert get_int(cache, "missing", 1) == 1
    assert get_int(cache, "bad_int", 9) == 9
    assert get_bool(cache, "bad_bool", False) is False
    assert get_list(cache, "missing") == []


def test_get_value_searches_namespaces_in_order() -> None:
    cache = MemoryCache()
    cache.set("application", {"timeout": "from-app"})
    cache.set("db", {"timeout": "from-db", "host": "127.0.0.1"})
    cache.set("system", {"timeout": "from-system"})

    assert get_value(cache, "timeout", namespaces=["application", "db", "system"]) == "from-app"
    assert get_value(cache, "host", namespaces=["application", "db", "system"]) == "127.0.0.1"
    assert get_value(cache, "missing", "default", namespaces=["application", "db"]) == "default"


def test_get_value_explicit_namespace_skips_chain() -> None:
    cache = MemoryCache()
    cache.set("application", {"timeout": "from-app"})
    cache.set("db", {"timeout": "from-db"})

    assert get_value(cache, "timeout", namespaces=["application", "db"]) == "from-app"
    assert get_value(cache, "timeout", namespace="db", namespaces=["application", "db"]) == "from-db"


def test_get_value_later_namespace_wins_when_earlier_missing_key() -> None:
    cache = MemoryCache()
    cache.set("application", {})
    cache.set("db", {"only-in-db": "yes"})

    assert get_value(cache, "only-in-db", namespaces=["application", "db"]) == "yes"
