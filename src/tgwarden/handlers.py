"""Logging handler that sends records to Telegram with topic routing and dedup."""

from __future__ import annotations

import logging
import sys

from tgwarden.conf import TgwardenSettings, get_settings
from tgwarden.dedup import DedupGate, Fingerprint
from tgwarden.formatters import HTMLFormatter
from tgwarden.transports.base import SendPayload, Transport


class TelegramHandler(logging.Handler):
    """A logging.Handler that sends log records to a Telegram chat."""

    _EXCLUDED_LOGGERS = frozenset({"httpx", "httpcore"})

    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self._formatter = HTMLFormatter()
        self._transport: Transport | None = None
        self._settings: TgwardenSettings | None = None
        self._gate: DedupGate | None = None

    def _ensure_transport(self) -> Transport:
        """Lazily initialize settings, transport, and dedup gate."""
        if self._transport is None:
            from tgwarden.transports import build_transport

            self._settings = get_settings()
            self._transport = build_transport(self._settings)
            if self._settings.dedup_window_seconds > 0:
                self._gate = DedupGate(
                    window_seconds=self._settings.dedup_window_seconds,
                    on_followup=self._emit_followup,
                )
        return self._transport

    def _emit_followup(self, fp: Fingerprint, count: int, elapsed: float) -> None:
        """Emit a dedup follow-up summary message."""
        if self._transport is None or self._settings is None:
            return
        topic_id = self._settings.topics.get(fp.level)
        text = (
            f"<i>… repeated × {count} more in last {elapsed:.0f}s</i>\n"  # noqa: RUF001
            f"<code>{fp.logger_name}</code>: {fp.message_template[:200]}"
        )
        payload = SendPayload(text=text, topic_id=topic_id, parse_mode="HTML")
        self._transport.submit(payload)

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to Telegram. Never raises."""
        if record.name.split(".")[0] in self._EXCLUDED_LOGGERS:
            return
        try:
            transport = self._ensure_transport()
            # Dedup gate
            if self._gate is not None and not self._gate.submit(record):
                return
            fr = self._formatter.format_record(record)
            topic_id = (
                self._settings.topics.get(record.levelname) if self._settings else None
            )
            payload = SendPayload(
                text=fr.message,
                topic_id=topic_id,
                parse_mode="HTML",
                attachment=fr.attachment,
                attachment_filename=fr.attachment_filename,
            )
            transport.submit(payload)
        except Exception:
            try:
                print(
                    f"[tgwarden] failed to send log record: {record.getMessage()[:100]}",
                    file=sys.stderr,
                )
            except Exception:  # noqa: S110
                pass
            self.handleError(record)

    def close(self) -> None:
        """Shut down the underlying transport."""
        if self._transport is not None:
            self._transport.shutdown()
            self._transport = None
        super().close()
