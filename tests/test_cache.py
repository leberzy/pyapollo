"""Tests for cache layer."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from pyapollo.cache import (
    AsyncFileCache,
    FileCache,
    MemoryCache,
    cache_namespace_path,
    resolve_cache_root,
)


def test_resolve_cache_root_explicit() -> None:
    assert resolve_cache_root("/tmp/apollo-cache") == "/tmp/apollo-cache"


def test_file_cache_invalid_json_returns_none(tmp_path: Path) -> None:
    cache = FileCache(str(tmp_path), "app-1", "default")
    path = cache_namespace_path(str(tmp_path), "app-1", "default", "application")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json", encoding="utf-8")
    assert cache.load("application") is None


def test_resolve_cache_root_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APOLLO_CACHE_DIR", str(tmp_path))
    assert resolve_cache_root() == str(tmp_path)


def test_resolve_cache_root_platform_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APOLLO_CACHE_DIR", raising=False)
    root = resolve_cache_root()
    assert root.endswith("apollo")


def test_cache_namespace_path_supports_underscore_namespace() -> None:
    path = cache_namespace_path("/cache", "my-app", "default", "my_custom_ns")
    assert path == Path("/cache/my-app/default/my_custom_ns.json")
    assert path.stem == "my_custom_ns"


def test_memory_cache_thread_safe_reads_and_writes() -> None:
    cache = MemoryCache()
    errors: list[str] = []

    def writer() -> None:
        for index in range(100):
            cache.set("application", {f"k{index}": str(index)})

    def reader() -> None:
        try:
            for _ in range(100):
                cache.get("application")
                cache.get_value("k1", "application", "default")
                cache.snapshot()
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert cache.get("application") is not None


def test_file_cache_save_load_and_release_key_dedup(tmp_path: Path) -> None:
    cache = FileCache(str(tmp_path), "app-1", "default")
    cache.save("application", {"k": "v"}, "rk-1")

    path = cache_namespace_path(str(tmp_path), "app-1", "default", "application")
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["release_key"] == "rk-1"
    assert payload["configurations"] == {"k": "v"}

    assert cache.load("application") == {"k": "v"}
    cache.save("application", {"k": "v"}, "rk-1")
    mtime_first = path.stat().st_mtime
    cache.save("application", {"k": "v2"}, "rk-2")
    assert path.stat().st_mtime >= mtime_first
    assert cache.load("application") == {"k": "v2"}


def test_file_cache_load_all_and_remove(tmp_path: Path) -> None:
    cache = FileCache(str(tmp_path), "app-1", "default")
    cache.save("application", {"a": "1"}, "rk-a")
    cache.save("my_custom_ns", {"b": "2"}, "rk-b")

    loaded = cache.load_all()
    assert loaded == {"application": {"a": "1"}, "my_custom_ns": {"b": "2"}}

    cache.remove("my_custom_ns")
    assert cache.load("my_custom_ns") is None
    assert cache.load_all() == {"application": {"a": "1"}}


@pytest.mark.asyncio
async def test_async_file_cache_roundtrip(tmp_path: Path) -> None:
    cache = AsyncFileCache(str(tmp_path), "app-1", "default")
    await cache.save("prompt", {"p": "x"}, "rk-p")
    assert await cache.load("prompt") == {"p": "x"}
    assert (await cache.load_all()) == {"prompt": {"p": "x"}}
    await cache.remove("prompt")
    assert await cache.load("prompt") is None
