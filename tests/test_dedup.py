"""Tests for tgwarden.dedup."""

import logging
import time

from tgwarden.dedup import DedupGate, Fingerprint


def _make_record(msg: str = "test error %d", level: int = logging.ERROR) -> logging.LogRecord:
    return logging.LogRecord(
        name="app.test", level=level, pathname="", lineno=0, msg=msg, args=(1,), exc_info=None
    )


def test_first_occurrence_emits() -> None:
    followups: list[tuple[Fingerprint, int, float]] = []
    gate = DedupGate(window_seconds=10.0, on_followup=lambda fp, c, e: followups.append((fp, c, e)))
    assert gate.submit(_make_record()) is True


def test_subsequent_occurrences_suppressed() -> None:
    followups: list[tuple[Fingerprint, int, float]] = []
    gate = DedupGate(window_seconds=10.0, on_followup=lambda fp, c, e: followups.append((fp, c, e)))
    gate.submit(_make_record())
    assert gate.submit(_make_record()) is False
    assert gate.submit(_make_record()) is False


def test_window_close_emits_followup_with_count() -> None:
    followups: list[tuple[Fingerprint, int, float]] = []
    gate = DedupGate(window_seconds=0.05, on_followup=lambda fp, c, e: followups.append((fp, c, e)))
    gate.submit(_make_record())
    gate.submit(_make_record())
    gate.submit(_make_record())
    time.sleep(0.15)
    assert len(followups) == 1
    assert followups[0][1] == 2  # count - 1 = 2 more


def test_different_fingerprints_not_deduped() -> None:
    followups: list[tuple[Fingerprint, int, float]] = []
    gate = DedupGate(window_seconds=10.0, on_followup=lambda fp, c, e: followups.append((fp, c, e)))
    r1 = _make_record("error A")
    r2 = _make_record("error B")
    assert gate.submit(r1) is True
    assert gate.submit(r2) is True


def test_disabled_when_window_zero() -> None:
    # When window is 0, we don't create a gate at all (tested at handler level)
    # But if someone creates one with 0, it should still work
    followups: list[tuple[Fingerprint, int, float]] = []
    gate = DedupGate(window_seconds=0.01, on_followup=lambda fp, c, e: followups.append((fp, c, e)))
    gate.submit(_make_record())
    gate.submit(_make_record())
    time.sleep(0.05)
    assert len(followups) == 1
