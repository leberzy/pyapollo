"""
PyApollo - Python client for Ctrip's Apollo configuration service.

This package provides both synchronous and asynchronous clients for Apollo.
"""

import logging

from pyapollo.sync import ApolloClient
from pyapollo.async_ import AsyncApolloClient
from pyapollo.config import ApolloSettingsConfig
from pyapollo.core.models import ChangeType, ConfigChange, ConfigChangeEvent
from pyapollo.listeners import Subscription
from pyapollo.provider import ApolloConfigProvider
from pyapollo.registry import (
    get_client,
    init_apollo,
    is_apollo_initialized,
    register_apollo_factory,
    require_client,
    reset_apollo,
    shutdown_apollo,
)

logging.getLogger("pyapollo").addHandler(logging.NullHandler())

__all__ = [
    "ApolloClient",
    "ApolloConfigProvider",
    "ApolloSettingsConfig",
    "AsyncApolloClient",
    "ChangeType",
    "ConfigChange",
    "ConfigChangeEvent",
    "Subscription",
    "get_client",
    "init_apollo",
    "is_apollo_initialized",
    "register_apollo_factory",
    "require_client",
    "reset_apollo",
    "shutdown_apollo",
]
