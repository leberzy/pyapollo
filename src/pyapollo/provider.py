"""High-level facade over the process-wide Apollo client registry."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from pyapollo.core.models import ConfigChangeEvent
from pyapollo.listeners import Subscription
from pyapollo.registry import (
    get_client,
    init_apollo,
    is_apollo_initialized,
    require_client,
    shutdown_apollo,
)
from pyapollo.sync import ApolloClient

logger = logging.getLogger(__name__)


def _resolve_meta_server_address(meta_server_address: str | None) -> str | None:
    if meta_server_address is not None:
        return meta_server_address or None
    return os.getenv("APOLLO_META_SERVER_ADDRESS") or os.getenv("APOLLO_SERVER") or None


def _parse_namespaces(namespaces: list[str] | str | None) -> list[str] | None:
    if namespaces is None:
        raw = os.getenv("APOLLO_NAMESPACES")
        if not raw:
            return None
        namespaces = raw
    if isinstance(namespaces, str):
        return [ns.strip() for ns in namespaces.split(",") if ns.strip()]
    return list(namespaces)


class ApolloConfigProvider:
    """Class-method facade for a process-wide :class:`ApolloClient`.

    Backed by :mod:`pyapollo.registry` — call :meth:`init` once at startup, then use
    :meth:`get` / :meth:`get_int` / :meth:`on_change` anywhere in the app.

    Legacy env aliases supported in :meth:`init`:

    - ``APOLLO_SERVER`` → ``meta_server_address`` (alias of ``APOLLO_META_SERVER_ADDRESS``)
    - ``APOLLO_APP_ID``, ``APOLLO_APP_SECRET``, ``APOLLO_NAMESPACES``

    Unlike the scaffold copy, convenience getters do **not** implicitly start Apollo;
    call :meth:`init` explicitly (or use :func:`pyapollo.get_client` returning ``None``).
    """

    @classmethod
    def init(
        cls,
        meta_server_address: str | None = None,
        app_id: str | None = None,
        app_secret: str | None = None,
        namespaces: list[str] | str | None = None,
        autostart: bool = True,
        *,
        client: ApolloClient | None = None,
        force: bool = False,
        **kwargs: Any,
    ) -> ApolloClient:
        """Initialize the global client. Idempotent unless *force* is ``True``."""
        if client is not None:
            return init_apollo(client, force=force)

        init_kwargs: dict[str, Any] = dict(kwargs)
        if meta_server_address is not None or "meta_server_address" not in init_kwargs:
            resolved = _resolve_meta_server_address(meta_server_address)
            if resolved is not None:
                init_kwargs["meta_server_address"] = resolved
        if app_id is not None:
            init_kwargs["app_id"] = app_id
        elif "app_id" not in init_kwargs:
            env_app_id = os.getenv("APOLLO_APP_ID")
            if env_app_id:
                init_kwargs["app_id"] = env_app_id
        if app_secret is not None:
            init_kwargs["app_secret"] = app_secret
        elif "app_secret" not in init_kwargs:
            env_secret = os.getenv("APOLLO_APP_SECRET")
            if env_secret:
                init_kwargs["app_secret"] = env_secret
        parsed_ns = _parse_namespaces(namespaces)
        if parsed_ns is not None:
            init_kwargs["namespaces"] = parsed_ns
        init_kwargs["autostart"] = autostart

        client = init_apollo(force=force, **init_kwargs)
        logger.info("Apollo client initialized: app_id=%s", client._app_id)
        return client

    @classmethod
    def client(cls) -> ApolloClient:
        """Return the initialized client or raise :class:`RuntimeError`."""
        return require_client()

    @classmethod
    def get(cls, key: str, default: Any = None) -> str | None:
        return require_client().get_value(key, default)

    @classmethod
    def get_int(cls, key: str, default: int | None = None) -> int | None:
        return require_client().get_int(key, default)

    @classmethod
    def get_bool(cls, key: str, default: bool | None = None) -> bool | None:
        return require_client().get_bool(key, default)

    @classmethod
    def get_float(cls, key: str, default: float | None = None) -> float | None:
        return require_client().get_float(key, default)

    @classmethod
    def get_list(cls, key: str, default: list[str] | None = None) -> list[str]:
        return require_client().get_list(key, default)

    @classmethod
    def get_json(cls, key: str, default: dict | None = None) -> dict:
        return require_client().get_json_value(key, default)

    @classmethod
    def is_initialized(cls) -> bool:
        return is_apollo_initialized()

    @classmethod
    def is_ready(cls) -> bool:
        client = get_client()
        return client is not None and client.is_ready()

    @classmethod
    def start(cls) -> None:
        require_client().start()

    @classmethod
    def stop(cls) -> None:
        shutdown_apollo()

    @classmethod
    def on_change(
        cls,
        callback: Callable[[ConfigChangeEvent], None],
        namespaces: list[str] | None = None,
        keys: list[str] | None = None,
    ) -> Subscription:
        return require_client().add_change_listener(
            callback,
            namespaces=namespaces,
            keys=keys,
        )
