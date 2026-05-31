"""Transport protocol and payload dataclass for tgwarden."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class SendPayload:
    """Immutable payload submitted to a transport."""

    text: str
    topic_id: int | None = None
    parse_mode: str | None = None
    attachment: bytes | None = None
    attachment_filename: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for Celery task args."""
        import base64

        d: dict[str, Any] = {"text": self.text}
        if self.topic_id is not None:
            d["topic_id"] = self.topic_id
        if self.parse_mode:
            d["parse_mode"] = self.parse_mode
        if self.attachment is not None:
            d["attachment_b64"] = base64.b64encode(self.attachment).decode()
            d["attachment_filename"] = self.attachment_filename
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SendPayload:
        """Deserialize from Celery task args."""
        import base64

        attachment = None
        if "attachment_b64" in d:
            attachment = base64.b64decode(d["attachment_b64"])
        return cls(
            text=d["text"],
            topic_id=d.get("topic_id"),
            parse_mode=d.get("parse_mode"),
            attachment=attachment,
            attachment_filename=d.get("attachment_filename"),
        )


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
