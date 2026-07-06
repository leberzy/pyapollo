"""Process-wide Apollo client registry (aligns with Java ``ConfigService`` usage)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from pyapollo.sync import ApolloClient

logger = logging.getLogger(__name__)

_lock = threading.RLock()
_client: ApolloClient | None = None
_factory: Callable[[], ApolloClient] | None = None


def register_apollo_factory(factory: Callable[[], ApolloClient]) -> None:
    """Register a factory used by :func:`init_apollo` when no client instance is passed.

    Must be called before the first successful initialization.
    """
    global _factory
    with _lock:
        if _client is not None:
            raise RuntimeError("Cannot register Apollo factory after client is initialized.")
        _factory = factory


def init_apollo(
    client: ApolloClient | None = None,
    *,
    force: bool = False,
    **kwargs: Any,
) -> ApolloClient:
    """Initialize the process-wide sync :class:`ApolloClient` once.

    Priority when creating a new instance:

    1. Explicit *client* argument
    2. Registered factory (see :func:`register_apollo_factory`)
    3. ``ApolloClient(**kwargs)`` when *kwargs* is non-empty
    4. ``ApolloClient()`` (env / ``.env``)

    Repeated calls return the existing instance unless *force* is ``True``.
    """
    global _client
    with _lock:
        if _client is not None and not force:
            if client is not None and client is not _client:
                logger.warning(
                    "init_apollo() called with a different client; returning existing instance"
                )
            return _client

        if force and _client is not None:
            _stop_client(_client)
            _client = None

        if client is not None:
            _client = client
        elif _factory is not None:
            _client = _factory()
        elif kwargs:
            _client = ApolloClient(**kwargs)
        else:
            _client = ApolloClient()

        return _client


def get_client() -> ApolloClient | None:
    """Return the initialized client, or ``None`` if :func:`init_apollo` was not called."""
    with _lock:
        return _client


def require_client() -> ApolloClient:
    """Return the initialized client or raise :class:`RuntimeError`."""
    client = get_client()
    if client is None:
        raise RuntimeError("Apollo client is not initialized. Call init_apollo() at startup.")
    return client


def is_apollo_initialized() -> bool:
    """Return whether a process-wide client is currently registered."""
    with _lock:
        return _client is not None


def shutdown_apollo() -> None:
    """Stop and clear the registered client. The factory (if any) is kept."""
    global _client
    with _lock:
        if _client is None:
            return
        _stop_client(_client)
        _client = None


def reset_apollo() -> None:
    """Stop the client and clear registry state (intended for tests)."""
    global _client, _factory
    with _lock:
        if _client is not None:
            _stop_client(_client)
            _client = None
        _factory = None


def _stop_client(client: ApolloClient) -> None:
    try:
        client.stop()
    except Exception:
        logger.exception("Failed to stop Apollo client during registry shutdown")
