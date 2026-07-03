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
