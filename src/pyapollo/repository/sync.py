"""Synchronous config repository: fetch, long-poll, backoff, and change detection."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from pyapollo.core.backoff import ExponentialBackoff
from pyapollo.core.constants import DEFAULT_NOTIFICATION_ID, LONG_POLL_READ_TIMEOUT
from pyapollo.core.diff import diff_config
from pyapollo.core.models import ConfigChangeEvent, ConfigResult, Notification
from pyapollo.core.urls import normalize_homepage_url
from pyapollo.repository.state import RepositoryState, export_state, restore_state
from pyapollo.transport import ApolloConfigApi, ConfigServiceLocator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncRepositoryHooks:
    """Callbacks wired by ``ApolloClient`` for cache and server lifecycle."""

    get_homepage: Callable[[], str | None]
    set_homepage: Callable[[str], None]
    get_cached_config: Callable[[str], dict[str, str]]
    apply_config: Callable[[ConfigResult, ConfigChangeEvent | None], None]
    on_namespace_fetch_error: Callable[[str, Exception], None]
    switch_config_server: Callable[[str | None], None]


class SyncConfigRepository:
    """
    Orchestrates config sync and long-polling.

    Mirrors Java ``RemoteConfigRepository`` + ``RemoteConfigLongPollService``:
    - long-poll ``/notifications/v2`` (90s read timeout)
    - fetch changed namespaces with ``releaseKey`` / ``messages``
    - exponential backoff on failures
    - periodic full refresh as fallback (``cycle_time``)
    """

    def __init__(
        self,
        api: ApolloConfigApi,
        locator: ConfigServiceLocator,
        namespaces: list[str],
        *,
        hooks: SyncRepositoryHooks,
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
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
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
        """Replace tracked namespaces (e.g. after client ``update_config``)."""
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

    def sync_namespace(self, namespace: str) -> bool:
        """
        Fetch one namespace from config server.

        Returns ``True`` when new configuration was applied (HTTP 200 with changes).
        """
        homepage = self._hooks.get_homepage()
        if not homepage:
            logger.warning("Config server not initialized for namespace %s", namespace)
            return False

        release_key = self._release_keys.get(namespace)
        messages = self._remote_messages.get(namespace)
        try:
            result = self._api.fetch_config(
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
            self._hooks.on_namespace_fetch_error(namespace, exc)
            self._hooks.switch_config_server(homepage)
            self._poll_homepage = None
            return False

        if result is None:
            logger.debug("Namespace %s not modified (304)", namespace)
            return False

        return self._apply_config(result)

    def sync_all(self) -> None:
        """Fetch all tracked namespaces."""
        for namespace in list(self._notifications):
            self.sync_namespace(namespace)

    def start_background(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._last_periodic = time.monotonic()
        self._thread = threading.Thread(target=self._background_loop, daemon=True)
        self._thread.start()
        logger.info("Apollo long-polling thread started")

    def stop_background(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=float(LONG_POLL_READ_TIMEOUT) + 5.0)
        self._thread = None
        logger.info("Apollo long-polling thread stopped")

    def export_state(self) -> RepositoryState:
        return export_state(self)

    def restore_state(self, state: RepositoryState | None) -> None:
        restore_state(self, state)

    def _background_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                changed = self._long_poll_once()
                self._long_poll_backoff.success()
                for namespace in changed:
                    self.sync_namespace(namespace)
            except Exception as exc:
                sleep_seconds = self._long_poll_backoff.fail()
                logger.warning(
                    "Long polling failed, retry in %ss: %s",
                    sleep_seconds,
                    exc,
                )
                if self._stop_event.wait(sleep_seconds):
                    break
                continue

            if time.monotonic() - self._last_periodic >= self._cycle_time:
                logger.debug("Periodic fallback refresh for all namespaces")
                self.sync_all()
                self._last_periodic = time.monotonic()

    def _long_poll_once(self) -> list[str]:
        homepage = self._resolve_poll_homepage()
        notification_list = list(self._notifications.values())
        updated = self._api.poll_notifications(
            homepage,
            notification_list,
            timeout=float(LONG_POLL_READ_TIMEOUT),
        )
        if not updated:
            return []

        self._poll_homepage = homepage
        return self._merge_notification_updates(updated)

    def _resolve_poll_homepage(self) -> str:
        if self._poll_homepage:
            return self._poll_homepage
        homepage = self._hooks.get_homepage()
        if homepage:
            self._poll_homepage = homepage
            return homepage
        service = self._locator.choose_one()
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

    def _apply_config(self, result: ConfigResult) -> bool:
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
        self._hooks.apply_config(result, event)
        if event and event.changes:
            logger.info(
                "Config changed for namespace %s (%d keys)",
                result.namespace,
                len(event.changes),
            )
        return True
