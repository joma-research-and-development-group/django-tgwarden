"""Stats tracking for tgwarden."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Snapshot:
    """Immutable point-in-time snapshot of tgwarden stats."""

    queue_size: int
    sent_total: int
    dropped_total: int
    last_send_at: str | None
    last_error: str | None
    transport: str
    package_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Stats:
    """Thread-safe counters for tgwarden operational metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.sent_total = 0
        self.dropped_total = 0
        self.last_send_at: datetime | None = None
        self.last_error: str | None = None

    def increment_sent(self, by: int = 1) -> None:
        with self._lock:
            self.sent_total += by

    def increment_dropped(self, by: int = 1) -> None:
        with self._lock:
            self.dropped_total += by

    def set_last_send(self, ts: datetime) -> None:
        with self._lock:
            self.last_send_at = ts

    def set_last_error(self, msg: str | None) -> None:
        with self._lock:
            self.last_error = msg

    def snapshot(self, *, queue_size: int = 0, transport: str = "unknown") -> Snapshot:
        import tgwarden

        with self._lock:
            return Snapshot(
                queue_size=queue_size,
                sent_total=self.sent_total,
                dropped_total=self.dropped_total,
                last_send_at=self.last_send_at.isoformat() if self.last_send_at else None,
                last_error=self.last_error,
                transport=transport,
                package_version=tgwarden.__version__,
            )


stats = Stats()
