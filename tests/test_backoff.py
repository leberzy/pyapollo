"""Tests for ExponentialBackoff."""

from pyapollo.core.backoff import ExponentialBackoff


def test_backoff_reset_on_success() -> None:
    backoff = ExponentialBackoff(1, 120)
    assert backoff.fail() == 1
    assert backoff.fail() == 2
    backoff.success()
    assert backoff.fail() == 1
