"""Tests for Apollo core models."""

from __future__ import annotations

from pyapollo.core.constants import DEFAULT_NOTIFICATION_ID
from pyapollo.core.models import parse_notification_id


def test_parse_notification_id_accepts_int() -> None:
    assert parse_notification_id(456) == 456


def test_parse_notification_id_accepts_str() -> None:
    assert parse_notification_id("789") == 789


def test_parse_notification_id_accepts_float() -> None:
    assert parse_notification_id(123.0) == 123


def test_parse_notification_id_invalid_returns_default() -> None:
    assert parse_notification_id("not-a-number") == DEFAULT_NOTIFICATION_ID
    assert parse_notification_id(None) == DEFAULT_NOTIFICATION_ID
    assert parse_notification_id(True) == DEFAULT_NOTIFICATION_ID
