"""Shared typed configuration value accessors (no IO)."""

from __future__ import annotations

import json
import logging
from typing import Any

from pyapollo.cache import MemoryCache

from .constants import DEFAULT_NAMESPACE

logger = logging.getLogger(__name__)

_TRUE_VALUES = frozenset({"true", "1", "yes", "on"})
_FALSE_VALUES = frozenset({"false", "0", "no", "off"})


def get_value(
    cache: MemoryCache,
    key: str,
    default: str | None = None,
    *,
    namespace: str = DEFAULT_NAMESPACE,
) -> str | None:
    return cache.get_value(key, namespace, default)


def get_json_value(
    cache: MemoryCache,
    key: str,
    default: dict[str, Any] | None = None,
    *,
    namespace: str = DEFAULT_NAMESPACE,
) -> dict[str, Any]:
    raw = cache.get_value(key, namespace)
    if raw is None:
        return default or {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.error("Value for key %s in namespace %s is not valid JSON", key, namespace)
        return default or {}
    return parsed if isinstance(parsed, dict) else (default or {})


def get_int(
    cache: MemoryCache,
    key: str,
    default: int | None = None,
    *,
    namespace: str = DEFAULT_NAMESPACE,
) -> int | None:
    raw = cache.get_value(key, namespace)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (ValueError, AttributeError):
        logger.error("Value for key %s in namespace %s is not an int", key, namespace)
        return default


def get_bool(
    cache: MemoryCache,
    key: str,
    default: bool | None = None,
    *,
    namespace: str = DEFAULT_NAMESPACE,
) -> bool | None:
    raw = cache.get_value(key, namespace)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    logger.error("Value for key %s in namespace %s is not a bool", key, namespace)
    return default


def get_float(
    cache: MemoryCache,
    key: str,
    default: float | None = None,
    *,
    namespace: str = DEFAULT_NAMESPACE,
) -> float | None:
    raw = cache.get_value(key, namespace)
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except (ValueError, AttributeError):
        logger.error("Value for key %s in namespace %s is not a float", key, namespace)
        return default


def get_list(
    cache: MemoryCache,
    key: str,
    default: list[str] | None = None,
    *,
    namespace: str = DEFAULT_NAMESPACE,
    separator: str = ",",
) -> list[str]:
    raw = cache.get_value(key, namespace)
    if raw is None:
        return list(default) if default is not None else []
    return [item.strip() for item in raw.split(separator) if item.strip()]
