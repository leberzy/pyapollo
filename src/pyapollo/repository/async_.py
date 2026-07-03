"""Asynchronous config repository: fetch, long-poll, backoff, and change detection."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pyapollo.core.backoff import ExponentialBackoff
from pyapollo.core.constants import DEFAULT_NOTIFICATION_ID, LONG_POLL_READ_TIMEOUT
from pyapollo.core.diff import diff_config
from pyapollo.core.models import ConfigChangeEvent, ConfigResult, Notification
from pyapollo.core.urls import normalize_homepage_url
from pyapollo.repository.state import RepositoryState, export_state, restore_state
from pyapollo.transport.async_ import AsyncApolloConfigApi, AsyncConfigServiceLocator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AsyncRepositoryHooks:
    get_homepage: Callable[[], str | None]
    set_homepage: Callable[[str], None]
    get_cached_config: Callable[[str], dict[str, str]]
    apply_config: Callable[[ConfigResult, ConfigChangeEvent | None], Awaitable[None]]
    on_namespace_fetch_error: Callable[[str, Exception], Awaitable[None]]
    switch_config_server: Callable[[str | None], Awaitable[None]]


class AsyncConfigRepository:
    """Async counterpart of :class:`SyncConfigRepository`."""

    def __init__(
        self,
        api: AsyncApolloConfigApi,
        locator: AsyncConfigServiceLocator,
        namespaces: list[str],
        *,
        hooks: AsyncRepositoryHooks,
        cycle_time: int = 30,
        fetch_timeout: float = 10,
    ) -> None:
        self._api = api
        self._locator = locator
        self._hooks = hooks
        self._cycle_time = cycle_time
        self._fetch_timeout = fetch_timeout
        self._notifications: dict[str, Notification] = {
            ns: Notification(namespace_name=ns, notification_id=DEFAULT_NOTIFICATION_ID)
            for ns in namespaces
        }
        self._release_keys: dict[str, str | None] = dict.fromkeys(namespaces)
        self._remote_messages: dict[str, dict[str, object]] = {}
        self._long_poll_backoff = ExponentialBackoff(1, 120)
        self._fetch_backoff = ExponentialBackoff(1, 120)
        self._poll_homepage: str | None = None
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._last_periodic = time.monotonic()

    @property
    def notifications(self) -> dict[str, Notification]:
        return self._notifications

    @property
    def cycle_time(self) -> int:
        return self._cycle_time

    @cycle_time.setter
    def cycle_time(self, value: int) -> None:
        self._cycle_time = value

    def sync_poll_homepage(self, homepage_url: str | None) -> None:
        """Pin long-poll target to the active config server (or clear when unknown)."""
        if homepage_url is None:
            self._poll_homepage = None
        else:
            self._poll_homepage = normalize_homepage_url(homepage_url)

    def set_namespaces(self, namespaces: list[str]) -> None:
        new_set = set(namespaces)
        for ns in list(self._notifications):
            if ns not in new_set:
                self._notifications.pop(ns, None)
                self._release_keys.pop(ns, None)
                self._remote_messages.pop(ns, None)
        for ns in namespaces:
            if ns not in self._notifications:
                self._notifications[ns] = Notification(
                    namespace_name=ns,
                    notification_id=DEFAULT_NOTIFICATION_ID,
                )
                self._release_keys[ns] = None

    async def sync_namespace(self, namespace: str) -> bool:
        homepage = self._hooks.get_homepage()
        if not homepage:
            logger.warning("Config server not initialized for namespace %s", namespace)
            return False

        release_key = self._release_keys.get(namespace)
        messages = self._remote_messages.get(namespace)
        try:
            result = await self._api.fetch_config(
                homepage,
                namespace,
                release_key=release_key,
                messages=messages if messages else None,
                timeout=self._fetch_timeout,
            )
            self._fetch_backoff.success()
        except Exception as exc:
            sleep_seconds = self._fetch_backoff.fail()
            logger.warning(
                "Fetch namespace %s failed, backoff %ss: %s",
                namespace,
                sleep_seconds,
                exc,
            )
            await self._hooks.on_namespace_fetch_error(namespace, exc)
            await self._hooks.switch_config_server(homepage)
            self._poll_homepage = None
            return False

        if result is None:
            logger.debug("Namespace %s not modified (304)", namespace)
            return False

        return await self._apply_config(result)

    async def sync_all(self) -> None:
        for namespace in list(self._notifications):
            await self.sync_namespace(namespace)

    async def start_background(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._last_periodic = time.monotonic()
        self._task = asyncio.create_task(self._background_loop())
        logger.info("Apollo long-polling task started")

    async def stop_background(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Apollo long-polling task stopped")

    def export_state(self) -> RepositoryState:
        return export_state(self)

    def restore_state(self, state: RepositoryState | None) -> None:
        restore_state(self, state)

    async def _background_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                changed = await self._long_poll_once()
                self._long_poll_backoff.success()
                for namespace in changed:
                    await self.sync_namespace(namespace)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                sleep_seconds = self._long_poll_backoff.fail()
                logger.warning(
                    "Long polling failed, retry in %ss: %s",
                    sleep_seconds,
                    exc,
                )
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_seconds)
                    break
                except TimeoutError:
                    pass
                continue

            if time.monotonic() - self._last_periodic >= self._cycle_time:
                logger.debug("Periodic fallback refresh for all namespaces")
                await self.sync_all()
                self._last_periodic = time.monotonic()

    async def _long_poll_once(self) -> list[str]:
        homepage = await self._resolve_poll_homepage()
        notification_list = list(self._notifications.values())
        updated = await self._api.poll_notifications(
            homepage,
            notification_list,
            timeout=float(LONG_POLL_READ_TIMEOUT),
        )
        if not updated:
            return []

        self._poll_homepage = homepage
        return self._merge_notification_updates(updated)

    async def _resolve_poll_homepage(self) -> str:
        if self._poll_homepage:
            return self._poll_homepage
        homepage = self._hooks.get_homepage()
        if homepage:
            self._poll_homepage = homepage
            return homepage
        service = await self._locator.choose_one()
        self._hooks.set_homepage(service.home_page_url)
        self._poll_homepage = service.home_page_url
        return service.home_page_url

    def _merge_notification_updates(self, delta: list[Notification]) -> list[str]:
        changed: list[str] = []
        for item in delta:
            if not item.namespace_name:
                continue
            if item.namespace_name in self._notifications:
                self._notifications[item.namespace_name] = Notification(
                    namespace_name=item.namespace_name,
                    notification_id=item.notification_id,
                    messages=item.messages,
                )
                changed.append(item.namespace_name)
            if item.messages:
                local = dict(self._remote_messages.get(item.namespace_name, {}))
                local.update(item.messages)
                self._remote_messages[item.namespace_name] = local
        return changed

    async def _apply_config(self, result: ConfigResult) -> bool:
        old_config = self._hooks.get_cached_config(result.namespace)
        if (
            old_config == result.configurations
            and self._release_keys.get(result.namespace) == result.release_key
        ):
            return False

        event: ConfigChangeEvent | None = None
        if old_config:
            event = diff_config(result.namespace, old_config, result.configurations)
            if not event.changes:
                event = None

        self._release_keys[result.namespace] = result.release_key
        await self._hooks.apply_config(result, event)
        if event and event.changes:
            logger.info(
                "Config changed for namespace %s (%d keys)",
                result.namespace,
                len(event.changes),
            )
        return True
