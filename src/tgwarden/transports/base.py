"""Transport protocol and payload dataclass for tgwarden."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SendPayload:
    """Immutable payload submitted to a transport."""

    text: str
    topic_id: int | None = None
    parse_mode: str | None = None
    as_document: bool = False


class Transport(Protocol):
    """Protocol that all tgwarden transports must implement."""

    def submit(self, payload: SendPayload) -> None:
        """Submit a payload for delivery. May or may not block."""
        ...

    def flush(self, timeout: float = 5.0) -> bool:
        """Wait for pending payloads to drain. Returns True if drained."""
        ...

    def shutdown(self) -> None:
        """Gracefully shut down the transport."""
        ...
