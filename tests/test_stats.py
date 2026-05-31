"""Tests for tgwarden.stats."""

import threading

from tgwarden.stats import Stats


def test_increment_thread_safe() -> None:
    s = Stats()
    threads = []
    for _ in range(10):
        t = threading.Thread(target=lambda: [s.increment_sent() for _ in range(100)])
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    assert s.sent_total == 1000


def test_snapshot_immutable() -> None:
    s = Stats()
    s.increment_sent(5)
    snap = s.snapshot(queue_size=3, transport="sync")
    assert snap.sent_total == 5
    assert snap.queue_size == 3
    assert snap.transport == "sync"
    s.increment_sent(10)
    assert snap.sent_total == 5  # immutable


def test_set_last_error_clearable() -> None:
    s = Stats()
    s.set_last_error("boom")
    assert s.last_error == "boom"
    s.set_last_error(None)
    assert s.last_error is None
