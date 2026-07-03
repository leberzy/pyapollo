"""Apollo client data models."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from .constants import DEFAULT_NOTIFICATION_ID


@dataclass(frozen=True)
class ConfigResult:
    app_id: str
    cluster: str
    namespace: str
    configurations: dict[str, str]
    release_key: str | None


@dataclass(frozen=True)
class ServiceInstance:
    home_page_url: str
    instance_id: str | None = None


@dataclass
class Notification:
    namespace_name: str
    notification_id: int = -1
    messages: dict[str, object] | None = None


def parse_notification_id(value: object) -> int:
    """Parse notificationId from Apollo JSON (int, str, or float)."""
    if isinstance(value, bool):
        return DEFAULT_NOTIFICATION_ID
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return DEFAULT_NOTIFICATION_ID
    return DEFAULT_NOTIFICATION_ID


class ChangeType(enum.Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"


@dataclass(frozen=True)
class ConfigChange:
    namespace: str
    key: str
    old_value: str | None
    new_value: str | None
    change_type: ChangeType


@dataclass(frozen=True)
class ConfigChangeEvent:
    namespace: str
    changes: dict[str, ConfigChange] = field(default_factory=dict)
