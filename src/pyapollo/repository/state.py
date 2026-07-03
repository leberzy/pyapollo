"""Repository runtime state transfer for safe transport/stack rebuild."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pyapollo.core.models import Notification


class _RepositoryWithState(Protocol):
    _notifications: dict[str, Notification]
    _release_keys: dict[str, str | None]
    _remote_messages: dict[str, dict[str, object]]
    _poll_homepage: str | None


@dataclass
class RepositoryState:
    notifications: dict[str, Notification]
    release_keys: dict[str, str | None]
    remote_messages: dict[str, dict[str, object]]
    poll_homepage: str | None


def export_state(repo: _RepositoryWithState) -> RepositoryState:
    return RepositoryState(
        notifications={
            namespace: Notification(
                namespace_name=item.namespace_name,
                notification_id=item.notification_id,
                messages=dict(item.messages) if item.messages else None,
            )
            for namespace, item in repo._notifications.items()
        },
        release_keys=dict(repo._release_keys),
        remote_messages={
            namespace: dict(messages) for namespace, messages in repo._remote_messages.items()
        },
        poll_homepage=repo._poll_homepage,
    )


def restore_state(repo: _RepositoryWithState, state: RepositoryState | None) -> None:
    if state is None:
        return
    repo._notifications = {
        namespace: Notification(
            namespace_name=item.namespace_name,
            notification_id=item.notification_id,
            messages=dict(item.messages) if item.messages else None,
        )
        for namespace, item in state.notifications.items()
    }
    repo._release_keys = dict(state.release_keys)
    repo._remote_messages = {
        namespace: dict(messages) for namespace, messages in state.remote_messages.items()
    }
    repo._poll_homepage = state.poll_homepage
