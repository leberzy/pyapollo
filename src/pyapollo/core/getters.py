"""Shared typed configuration value accessors (no IO)."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any

from pyapollo.cache import MemoryCache

from .constants import DEFAULT_NAMESPACE

logger = logging.getLogger(__name__)

_TRUE_VALUES = frozenset({"true", "1", "yes", "on"})
_FALSE_VALUES = frozenset({"false", "0", "no", "off"})


def _resolve_raw_value(
    cache: MemoryCache,
    key: str,
    *,
    namespace: str | None,
    namespaces: Sequence[str] | None,
) -> tuple[str | None, str | None]:
    """Look up a raw string value and the namespace it came from.

    When ``namespace`` is set, only that namespace is searched.
    Otherwise namespaces are tried in list order; the first hit wins.
    """
    if namespace is not None:
        stored = cache.get(namespace)
        if stored is None:
            return None, None
        if key not in stored:
            return None, None
        return stored[key], namespace

    search_order = list(namespaces) if namespaces else [DEFAULT_NAMESPACE]
    for ns in search_order:
        stored = cache.get(ns)
        if stored is not None and key in stored:
            return stored[key], ns
    return None, None


def get_value(
    cache: MemoryCache,
    key: str,
    default: str | None = None,
    *,
    namespace: str | None = None,
    namespaces: Sequence[str] | None = None,
) -> str | None:
    raw, _ = _resolve_raw_value(
        cache,
        key,
        namespace=namespace,
        namespaces=namespaces,
    )
    return raw if raw is not None else default


def get_json_value(
    cache: MemoryCache,
    key: str,
    default: dict[str, Any] | None = None,
    *,
    namespace: str | None = None,
    namespaces: Sequence[str] | None = None,
) -> dict[str, Any]:
    raw, resolved_ns = _resolve_raw_value(
        cache,
        key,
        namespace=namespace,
        namespaces=namespaces,
    )
    if raw is None:
        return default or {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.error(
            "Value for key %s in namespace %s is not valid JSON",
            key,
            resolved_ns,
        )
        return default or {}
    return parsed if isinstance(parsed, dict) else (default or {})


def get_int(
    cache: MemoryCache,
    key: str,
    default: int | None = None,
    *,
    namespace: str | None = None,
    namespaces: Sequence[str] | None = None,
) -> int | None:
    raw, resolved_ns = _resolve_raw_value(
        cache,
        key,
        namespace=namespace,
        namespaces=namespaces,
    )
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (ValueError, AttributeError):
        logger.error("Value for key %s in namespace %s is not an int", key, resolved_ns)
        return default


def get_bool(
    cache: MemoryCache,
    key: str,
    default: bool | None = None,
    *,
    namespace: str | None = None,
    namespaces: Sequence[str] | None = None,
) -> bool | None:
    raw, resolved_ns = _resolve_raw_value(
        cache,
        key,
        namespace=namespace,
        namespaces=namespaces,
    )
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    logger.error("Value for key %s in namespace %s is not a bool", key, resolved_ns)
    return default


def get_float(
    cache: MemoryCache,
    key: str,
    default: float | None = None,
    *,
    namespace: str | None = None,
    namespaces: Sequence[str] | None = None,
) -> float | None:
    raw, resolved_ns = _resolve_raw_value(
        cache,
        key,
        namespace=namespace,
        namespaces=namespaces,
    )
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except (ValueError, AttributeError):
        logger.error("Value for key %s in namespace %s is not a float", key, resolved_ns)
        return default


def get_list(
    cache: MemoryCache,
    key: str,
    default: list[str] | None = None,
    *,
    namespace: str | None = None,
    namespaces: Sequence[str] | None = None,
    separator: str = ",",
) -> list[str]:
    raw, _ = _resolve_raw_value(
        cache,
        key,
        namespace=namespace,
        namespaces=namespaces,
    )
    if raw is None:
        return list(default) if default is not None else []
    return [item.strip() for item in raw.split(separator) if item.strip()]
