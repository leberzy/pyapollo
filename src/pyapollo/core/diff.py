"""Configuration change diff utilities."""

from __future__ import annotations

from .models import ChangeType, ConfigChange, ConfigChangeEvent


def diff_config(
    namespace: str,
    old: dict[str, str],
    new: dict[str, str],
) -> ConfigChangeEvent:
    """Compute ADDED / MODIFIED / DELETED changes between two config snapshots."""
    changes: dict[str, ConfigChange] = {}
    all_keys = set(old) | set(new)

    for key in all_keys:
        old_val = old.get(key)
        new_val = new.get(key)
        if key not in old:
            changes[key] = ConfigChange(
                namespace=namespace,
                key=key,
                old_value=None,
                new_value=new_val,
                change_type=ChangeType.ADDED,
            )
        elif key not in new:
            changes[key] = ConfigChange(
                namespace=namespace,
                key=key,
                old_value=old_val,
                new_value=None,
                change_type=ChangeType.DELETED,
            )
        elif old_val != new_val:
            changes[key] = ConfigChange(
                namespace=namespace,
                key=key,
                old_value=old_val,
                new_value=new_val,
                change_type=ChangeType.MODIFIED,
            )

    return ConfigChangeEvent(namespace=namespace, changes=changes)
