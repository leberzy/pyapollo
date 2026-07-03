"""Concurrent memory cache read/write stress test."""

from __future__ import annotations

import threading

from pyapollo.cache import MemoryCache


def test_concurrent_read_write_no_exceptions() -> None:
    cache = MemoryCache()
    errors: list[str] = []
    stop = threading.Event()

    def writer() -> None:
        index = 0
        while not stop.is_set():
            cache.set("application", {f"k{index}": str(index)})
            index += 1

    def reader() -> None:
        try:
            while not stop.is_set():
                cache.get("application")
                cache.get_value("k1", "application")
                cache.snapshot()
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=writer) for _ in range(2)]
    threads += [threading.Thread(target=reader) for _ in range(4)]
    for thread in threads:
        thread.start()

    stop.wait(timeout=0.5)
    stop.set()
    for thread in threads:
        thread.join(timeout=2)

    assert errors == []
