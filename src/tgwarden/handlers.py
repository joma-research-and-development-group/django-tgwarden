"""Logging handler that sends records to Telegram.

WARNING: The 'sync' transport blocks the calling thread until Telegram responds.
Use transport='async_worker' (Phase 2+) in production.
"""

from __future__ import annotations

import logging
import sys

from tgwarden.client import TelegramClient
from tgwarden.conf import TgwardenSettings, get_settings
from tgwarden.formatters import HTMLFormatter


class TelegramHandler(logging.Handler):
    """A logging.Handler that sends log records to a Telegram chat."""

    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self.formatter = HTMLFormatter()
        self._client: TelegramClient | None = None
        self._settings: TgwardenSettings | None = None

    def _ensure_client(self) -> TelegramClient:
        """Lazily initialize settings and client on first emit."""
        if self._client is None:
            self._settings = get_settings()
            self._client = TelegramClient(self._settings)
        return self._client

    _EXCLUDED_LOGGERS = frozenset({"httpx", "httpcore"})

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to Telegram. Never raises."""
        # Prevent recursive logging from httpx/httpcore
        if record.name.split(".")[0] in self._EXCLUDED_LOGGERS:
            return
        try:
            client = self._ensure_client()
            text = self.format(record)
            client.send_message(text)
        except Exception:
            # Never crash the host app
            try:
                print(
                    f"[tgwarden] failed to send log record: {record.getMessage()[:100]}",
                    file=sys.stderr,
                )
            except Exception:  # noqa: S110
                pass
            self.handleError(record)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None
        super().close()
