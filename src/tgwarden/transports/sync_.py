"""Synchronous (blocking) transport for tgwarden."""

from __future__ import annotations

from tgwarden.client import TelegramClient
from tgwarden.conf import TgwardenSettings
from tgwarden.transports.base import SendPayload


class SyncTransport:
    """Blocking transport that sends immediately via httpx.Client."""

    def __init__(self, settings: TgwardenSettings) -> None:
        self._client = TelegramClient(settings)

    def submit(self, payload: SendPayload) -> None:
        """Send the payload synchronously (blocks until Telegram responds)."""
        self._client.send_message(
            payload.text,
            topic_id=payload.topic_id,
            parse_mode=payload.parse_mode,
        )

    def flush(self, timeout: float = 5.0) -> bool:
        """No-op for sync transport."""
        return True

    def shutdown(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
