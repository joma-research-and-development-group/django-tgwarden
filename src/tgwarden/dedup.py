"""Deduplication gate for tgwarden — collapses repeated errors."""

from __future__ import annotations

import logging
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Fingerprint:
    """Unique identity of a log record for dedup purposes."""

    level: str
    logger_name: str
    message_template: str
    exc_type: str | None
    exc_first_frame: str | None


def _compute_fingerprint(record: logging.LogRecord) -> Fingerprint:
    exc_type: str | None = None
    exc_first_frame: str | None = None
    if record.exc_info and record.exc_info[0] is not None:
        exc_type = record.exc_info[0].__name__
        tb = record.exc_info[2]
        if tb is not None:
            frames = traceback.extract_tb(tb)
            if frames:
                f = frames[-1]
                exc_first_frame = f"{f.filename}:{f.lineno}"
    return Fingerprint(
        level=record.levelname,
        logger_name=record.name,
        message_template=record.msg if isinstance(record.msg, str) else str(record.msg),
        exc_type=exc_type,
        exc_first_frame=exc_first_frame,
    )


@dataclass
class _State:
    first_seen: float
    count: int
    last_seen: float


class DedupGate:
    """Suppresses repeated log records within a time window."""

    def __init__(
        self,
        *,
        window_seconds: float,
        on_followup: Callable[[Fingerprint, int, float], None],
    ) -> None:
        self._window = window_seconds
        self._on_followup = on_followup
        self._states: dict[Fingerprint, _State] = {}
        self._lock = threading.Lock()
        self._timers: dict[Fingerprint, threading.Timer] = {}

    def submit(self, record: logging.LogRecord) -> bool:
        """Return True if this record should be emitted (first in window)."""
        fp = _compute_fingerprint(record)
        now = time.monotonic()

        with self._lock:
            if fp in self._states:
                self._states[fp].count += 1
                self._states[fp].last_seen = now
                return False

            self._states[fp] = _State(first_seen=now, count=1, last_seen=now)

        # Schedule window close
        timer = threading.Timer(self._window, self._close_window, args=(fp,))
        timer.daemon = True
        timer.start()
        with self._lock:
            self._timers[fp] = timer

        return True

    def _close_window(self, fp: Fingerprint) -> None:
        with self._lock:
            state = self._states.pop(fp, None)
            self._timers.pop(fp, None)

        if state and state.count > 1:
            elapsed = state.last_seen - state.first_seen
            self._on_followup(fp, state.count - 1, elapsed)
