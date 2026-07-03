"""Tests for diff module."""

from pyapollo.core.diff import diff_config
from pyapollo.core.models import ChangeType


def test_diff_config_added_modified_deleted() -> None:
    old = {"a": "1", "b": "2"}
    new = {"a": "1", "b": "3", "c": "4"}
    event = diff_config("application", old, new)

    assert event.namespace == "application"
    assert len(event.changes) == 2
    assert event.changes["b"].change_type == ChangeType.MODIFIED
    assert event.changes["c"].change_type == ChangeType.ADDED


def test_diff_config_deleted() -> None:
    old = {"a": "1", "b": "2"}
    new = {"a": "1"}
    event = diff_config("ns", old, new)
    assert event.changes["b"].change_type == ChangeType.DELETED


def test_diff_config_no_changes() -> None:
    data = {"k": "v"}
    event = diff_config("ns", data, dict(data))
    assert event.changes == {}
