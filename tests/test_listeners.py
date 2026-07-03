"""Tests for change listener registry."""

from __future__ import annotations

import pytest

from pyapollo.core.diff import diff_config
from pyapollo.core.models import ChangeType, ConfigChange, ConfigChangeEvent
from pyapollo.listeners import AsyncListenerRegistry, ListenerRegistry


def _event(namespace: str = "application", keys: tuple[str, ...] = ("k1",)) -> ConfigChangeEvent:
    changes = {
        key: ConfigChange(
            namespace=namespace,
            key=key,
            old_value="old",
            new_value="new",
            change_type=ChangeType.MODIFIED,
        )
        for key in keys
    }
    return ConfigChangeEvent(namespace=namespace, changes=changes)


def test_sync_listener_receives_matching_event() -> None:
    received: list[ConfigChangeEvent] = []
    registry = ListenerRegistry(max_workers=1)
    registry.add(lambda event: received.append(event))

    registry.dispatch(_event())
    registry.shutdown(wait=True)

    assert len(received) == 1
    assert received[0].namespace == "application"
    assert "k1" in received[0].changes


def test_sync_listener_namespace_filter() -> None:
    received: list[str] = []
    registry = ListenerRegistry(max_workers=1)
    registry.add(lambda event: received.append(event.namespace), namespaces={"prompt"})

    registry.dispatch(_event(namespace="application"))
    registry.dispatch(_event(namespace="prompt"))
    registry.shutdown(wait=True)

    assert received == ["prompt"]


def test_sync_listener_key_filter() -> None:
    received: list[set[str]] = []
    registry = ListenerRegistry(max_workers=1)
    registry.add(
        lambda event: received.append(set(event.changes)),
        keys={"k2"},
    )

    registry.dispatch(_event(keys=("k1", "k2")))
    registry.shutdown(wait=True)

    assert received == [{"k2"}]


def test_sync_listener_exception_isolation() -> None:
    calls: list[str] = []

    def bad_listener(_event: ConfigChangeEvent) -> None:
        raise RuntimeError("boom")

    def good_listener(_event: ConfigChangeEvent) -> None:
        calls.append("ok")

    registry = ListenerRegistry(max_workers=2)
    registry.add(bad_listener)
    registry.add(good_listener)
    registry.dispatch(_event())
    registry.shutdown(wait=True)

    assert calls == ["ok"]


def test_subscription_cancel() -> None:
    received: list[str] = []
    registry = ListenerRegistry(max_workers=1)
    sub = registry.add(lambda event: received.append(event.namespace))
    sub.cancel()
    registry.dispatch(_event())
    registry.shutdown(wait=True)
    assert received == []


def test_filter_event_from_diff() -> None:
    event = diff_config("application", {"a": "1"}, {"a": "2", "b": "3"})
    assert len(event.changes) == 2
    assert event.changes["a"].change_type == ChangeType.MODIFIED
    assert event.changes["b"].change_type == ChangeType.ADDED


@pytest.mark.asyncio
async def test_async_listener_dispatch() -> None:
    received: list[str] = []

    async def on_change(event: ConfigChangeEvent) -> None:
        received.append(event.namespace)

    registry = AsyncListenerRegistry()
    registry.add(on_change)
    await registry.dispatch(_event(namespace="prompt"))
    assert received == ["prompt"]


@pytest.mark.asyncio
async def test_async_listener_sync_callback_via_thread() -> None:
    received: list[str] = []
    registry = AsyncListenerRegistry()
    registry.add(lambda event: received.append(event.namespace))
    await registry.dispatch(_event())
    assert received == ["application"]
