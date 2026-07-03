"""Configuration cache: thread-safe memory cache and file disaster-recovery cache."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyapollo.core.constants import ENV_CACHE_DIR

logger = logging.getLogger(__name__)


def resolve_cache_root(explicit: str | None = None) -> str:
    """
    Resolve Apollo cache root directory.

    Priority: explicit parameter > ``APOLLO_CACHE_DIR`` env > platform user cache dir.
    """
    if explicit:
        return explicit

    env_dir = os.environ.get(ENV_CACHE_DIR)
    if env_dir:
        return env_dir

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return os.path.join(base, "apollo")

    xdg_cache = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    return os.path.join(xdg_cache, "apollo")


def cache_namespace_path(root_dir: str, app_id: str, cluster: str, namespace: str) -> Path:
    """Return ``{root}/{app_id}/{cluster}/{namespace}.json``."""
    return Path(root_dir) / app_id / cluster / f"{namespace}.json"


@dataclass(frozen=True)
class FileCacheEntry:
    release_key: str | None
    configurations: dict[str, str]


class ConfigCache(ABC):
    @abstractmethod
    def get(self, namespace: str) -> dict[str, str] | None:
        raise NotImplementedError

    @abstractmethod
    def set(self, namespace: str, data: dict[str, str]) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove(self, namespace: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def snapshot(self) -> dict[str, dict[str, str]]:
        raise NotImplementedError


class MemoryCache(ConfigCache):
    """Thread-safe in-memory configuration cache."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, str]] = {}
        self._lock = threading.RLock()

    def get(self, namespace: str) -> dict[str, str] | None:
        with self._lock:
            stored = self._data.get(namespace)
            return dict(stored) if stored is not None else None

    def get_value(
        self,
        key: str,
        namespace: str = "application",
        default: str | None = None,
    ) -> str | None:
        with self._lock:
            stored = self._data.get(namespace)
            if stored is None:
                return default
            return stored.get(key, default)

    def set(self, namespace: str, data: dict[str, str]) -> None:
        with self._lock:
            self._data[namespace] = dict(data)

    def remove(self, namespace: str) -> None:
        with self._lock:
            self._data.pop(namespace, None)

    def snapshot(self) -> dict[str, dict[str, str]]:
        with self._lock:
            return {namespace: dict(data) for namespace, data in self._data.items()}


class AsyncMemoryCache:
    """Asyncio-safe in-memory configuration cache."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, str]] = {}
        self._lock = asyncio.Lock()

    async def get(self, namespace: str) -> dict[str, str] | None:
        async with self._lock:
            stored = self._data.get(namespace)
            return dict(stored) if stored is not None else None

    async def get_value(
        self,
        key: str,
        namespace: str = "application",
        default: str | None = None,
    ) -> str | None:
        async with self._lock:
            stored = self._data.get(namespace)
            if stored is None:
                return default
            return stored.get(key, default)

    async def set(self, namespace: str, data: dict[str, str]) -> None:
        async with self._lock:
            self._data[namespace] = dict(data)

    async def remove(self, namespace: str) -> None:
        async with self._lock:
            self._data.pop(namespace, None)

    async def snapshot(self) -> dict[str, dict[str, str]]:
        async with self._lock:
            return {namespace: dict(data) for namespace, data in self._data.items()}


def _parse_cache_file(raw: str, path: Path) -> FileCacheEntry | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Invalid cache JSON at %s", path)
        return None

    if not isinstance(payload, dict):
        logger.error("Cache file %s must contain a JSON object", path)
        return None

    configurations = payload.get("configurations", payload)
    if not isinstance(configurations, dict):
        logger.error("Cache file %s has invalid configurations", path)
        return None

    str_config = {str(k): str(v) for k, v in configurations.items()}
    release_key = payload.get("release_key")
    return FileCacheEntry(
        release_key=str(release_key) if release_key is not None else None,
        configurations=str_config,
    )


class FileCache:
    """
    Synchronous file disaster-recovery cache.

    Layout: ``{root_dir}/{app_id}/{cluster}/{namespace}.json``
    """

    def __init__(self, root_dir: str, app_id: str, cluster: str) -> None:
        self._root_dir = root_dir
        self._app_id = app_id
        self._cluster = cluster
        self._release_keys: dict[str, str | None] = {}
        self._write_lock = threading.Lock()

    @property
    def base_dir(self) -> Path:
        return Path(self._root_dir) / self._app_id / self._cluster

    def get_release_key(self, namespace: str) -> str | None:
        return self._release_keys.get(namespace)

    def load(self, namespace: str) -> dict[str, str] | None:
        path = cache_namespace_path(self._root_dir, self._app_id, self._cluster, namespace)
        if not path.is_file():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("Failed to read cache file %s: %s", path, exc)
            return None

        entry = _parse_cache_file(raw, path)
        if entry is None:
            return None
        self._release_keys[namespace] = entry.release_key
        return dict(entry.configurations)

    def save(
        self,
        namespace: str,
        data: dict[str, str],
        release_key: str | None,
    ) -> None:
        if self._release_keys.get(namespace) == release_key:
            return

        path = cache_namespace_path(self._root_dir, self._app_id, self._cluster, namespace)
        payload = {
            "release_key": release_key,
            "configurations": data,
        }
        with self._write_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self._release_keys[namespace] = release_key

    def load_all(self) -> dict[str, dict[str, str]]:
        loaded: dict[str, dict[str, str]] = {}
        base = self.base_dir
        if not base.is_dir():
            return loaded

        for path in base.glob("*.json"):
            namespace = path.stem
            data = self.load(namespace)
            if data is not None:
                loaded[namespace] = data
        return loaded

    def remove(self, namespace: str) -> None:
        path = cache_namespace_path(self._root_dir, self._app_id, self._cluster, namespace)
        self._release_keys.pop(namespace, None)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to remove cache file %s: %s", path, exc)


class AsyncFileCache:
    """Async file disaster-recovery cache (``aiofiles`` loaded lazily)."""

    def __init__(self, root_dir: str, app_id: str, cluster: str) -> None:
        self._root_dir = root_dir
        self._app_id = app_id
        self._cluster = cluster
        self._release_keys: dict[str, str | None] = {}
        self._write_lock = asyncio.Lock()

    @property
    def base_dir(self) -> Path:
        return Path(self._root_dir) / self._app_id / self._cluster

    def get_release_key(self, namespace: str) -> str | None:
        return self._release_keys.get(namespace)

    async def load(self, namespace: str) -> dict[str, str] | None:
        path = cache_namespace_path(self._root_dir, self._app_id, self._cluster, namespace)
        if not path.is_file():
            return None
        try:
            aiofiles = _import_aiofiles()
            async with aiofiles.open(path, encoding="utf-8") as handle:
                raw = await handle.read()
        except OSError as exc:
            logger.error("Failed to read cache file %s: %s", path, exc)
            return None

        entry = _parse_cache_file(raw, path)
        if entry is None:
            return None
        self._release_keys[namespace] = entry.release_key
        return dict(entry.configurations)

    async def save(
        self,
        namespace: str,
        data: dict[str, str],
        release_key: str | None,
    ) -> None:
        if self._release_keys.get(namespace) == release_key:
            return

        path = cache_namespace_path(self._root_dir, self._app_id, self._cluster, namespace)
        payload = json.dumps(
            {"release_key": release_key, "configurations": data},
            ensure_ascii=False,
        )
        async with self._write_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            aiofiles = _import_aiofiles()
            async with aiofiles.open(path, "w", encoding="utf-8") as handle:
                await handle.write(payload)
            self._release_keys[namespace] = release_key

    async def load_all(self) -> dict[str, dict[str, str]]:
        loaded: dict[str, dict[str, str]] = {}
        base = self.base_dir
        if not base.is_dir():
            return loaded

        for path in base.glob("*.json"):
            namespace = path.stem
            data = await self.load(namespace)
            if data is not None:
                loaded[namespace] = data
        return loaded

    async def remove(self, namespace: str) -> None:
        path = cache_namespace_path(self._root_dir, self._app_id, self._cluster, namespace)
        self._release_keys.pop(namespace, None)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to remove cache file %s: %s", path, exc)


def _import_aiofiles() -> Any:
    import aiofiles as module

    return module
