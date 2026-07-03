"""Change listener registry: registration, filtering, and isolated dispatch."""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from pyapollo.core.models import ConfigChangeEvent

logger = logging.getLogger(__name__)

ChangeCallback = Callable[[ConfigChangeEvent], None]
AsyncChangeCallback = Callable[[ConfigChangeEvent], Awaitable[None]]


@dataclass(frozen=True)
class _ListenerEntry:
    subscription_id: int
    callback: Callable[[ConfigChangeEvent], Any]
    namespaces: set[str] | None
    keys: set[str] | None
    is_async: bool


class Subscription:
    """Handle returned by ``add``; call ``cancel()`` to unregister."""

    def __init__(
        self,
        registry: ListenerRegistry | AsyncListenerRegistry,
        subscription_id: int,
    ) -> None:
        self._registry = registry
        self._subscription_id = subscription_id
        self._cancelled = False

    def cancel(self) -> None:
        if self._cancelled:
            return
        self._registry.remove(self._subscription_id)
        self._cancelled = True


def _filter_event(
    event: ConfigChangeEvent,
    namespaces: set[str] | None,
    keys: set[str] | None,
) -> ConfigChangeEvent | None:
    if namespaces is not None and event.namespace not in namespaces:
        return None
    if keys is not None:
        filtered = {key: change for key, change in event.changes.items() if key in keys}
        if not filtered:
            return None
        return ConfigChangeEvent(namespace=event.namespace, changes=filtered)
    return event


class ListenerRegistry:
    """Synchronous listener registry; callbacks run on a background thread pool."""

    def __init__(self, *, max_workers: int = 4) -> None:
        self._entries: dict[int, _ListenerEntry] = {}
        self._next_id = 0
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="apollo-listener",
        )

    def add(
        self,
        callback: ChangeCallback,
        *,
        namespaces: set[str] | None = None,
        keys: set[str] | None = None,
    ) -> Subscription:
        with self._lock:
            subscription_id = self._next_id
            self._next_id += 1
            self._entries[subscription_id] = _ListenerEntry(
                subscription_id=subscription_id,
                callback=callback,
                namespaces=namespaces,
                keys=keys,
                is_async=False,
            )
        return Subscription(self, subscription_id)

    def remove(self, subscription_id: int) -> None:
        with self._lock:
            self._entries.pop(subscription_id, None)

    def dispatch(self, event: ConfigChangeEvent) -> None:
        with self._lock:
            entries = list(self._entries.values())

        for entry in entries:
            filtered = _filter_event(event, entry.namespaces, entry.keys)
            if filtered is None:
                continue
            self._executor.submit(self._invoke_sync, entry.callback, filtered)

    def shutdown(self, *, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)

    @staticmethod
    def _invoke_sync(callback: ChangeCallback, event: ConfigChangeEvent) -> None:
        try:
            callback(event)
        except Exception:
            logger.exception("Apollo change listener failed for namespace %s", event.namespace)


class AsyncListenerRegistry:
    """Async listener registry; coroutine callbacks are awaited, sync ones run in a thread."""

    def __init__(self) -> None:
        self._entries: dict[int, _ListenerEntry] = {}
        self._next_id = 0
        self._lock = threading.RLock()

    def add(
        self,
        callback: ChangeCallback | AsyncChangeCallback,
        *,
        namespaces: set[str] | None = None,
        keys: set[str] | None = None,
    ) -> Subscription:
        with self._lock:
            subscription_id = self._next_id
            self._next_id += 1
            self._entries[subscription_id] = _ListenerEntry(
                subscription_id=subscription_id,
                callback=callback,
                namespaces=namespaces,
                keys=keys,
                is_async=inspect.iscoroutinefunction(callback),
            )
        return Subscription(self, subscription_id)

    def remove(self, subscription_id: int) -> None:
        with self._lock:
            self._entries.pop(subscription_id, None)

    async def dispatch(self, event: ConfigChangeEvent) -> None:
        with self._lock:
            entries = list(self._entries.values())

        for entry in entries:
            filtered = _filter_event(event, entry.namespaces, entry.keys)
            if filtered is None:
                continue
            await self._invoke(entry, filtered)

    async def _invoke(self, entry: _ListenerEntry, event: ConfigChangeEvent) -> None:
        try:
            if entry.is_async:
                await entry.callback(event)
            else:
                await asyncio.to_thread(entry.callback, event)
        except Exception:
            logger.exception("Apollo change listener failed for namespace %s", event.namespace)
