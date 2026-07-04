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

logging.getLogger("pyapollo").addHandler(logging.NullHandler())

__all__ = [
    "ApolloClient",
    "ApolloSettingsConfig",
    "AsyncApolloClient",
    "ChangeType",
    "ConfigChange",
    "ConfigChangeEvent",
    "Subscription",
]
