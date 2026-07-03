"""Exponential backoff schedule policy (aligned with Java ExponentialSchedulePolicy)."""

from __future__ import annotations


class ExponentialBackoff:
    """
    On ``fail()`` returns delay in seconds and doubles until upper bound.
    On ``success()`` resets to initial state.
    """

    def __init__(self, lower_bound_seconds: int = 1, upper_bound_seconds: int = 120) -> None:
        self._lower = lower_bound_seconds
        self._upper = upper_bound_seconds
        self._last_delay = 0

    def fail(self) -> int:
        delay = (
            self._lower
            if self._last_delay == 0
            else min(self._last_delay << 1, self._upper)
        )
        self._last_delay = delay
        return delay

    def success(self) -> None:
        self._last_delay = 0
