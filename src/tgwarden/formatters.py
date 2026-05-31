"""Log formatters for tgwarden."""

from __future__ import annotations

import html
import logging
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime

MAX_MESSAGE_LENGTH = 4096
SUMMARY_LENGTH = 1000

LEVEL_EMOJI: dict[str, str] = {
    "DEBUG": "🔵",
    "INFO": "ℹ️",  # noqa: RUF001
    "WARNING": "⚠️",
    "ERROR": "🐛",
    "CRITICAL": "🔥",
}


@dataclass(frozen=True, slots=True)
class FormattedRecord:
    """Result of formatting a log record for Telegram."""

    message: str
    attachment: bytes | None = None
    attachment_filename: str | None = None


class HTMLFormatter(logging.Formatter):
    """Format log records as Telegram-compatible HTML with overflow support."""

    def format(self, record: logging.LogRecord) -> str:
        """Format for backward compat — returns just the message text."""
        return self.format_record(record).message

    def format_record(self, record: logging.LogRecord) -> FormattedRecord:
        """Format a LogRecord into a FormattedRecord with optional attachment."""
        emoji = LEVEL_EMOJI.get(record.levelname, "📝")
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        msg_text = record.getMessage()
        logger_name = html.escape(record.name, quote=True)

        header = (
            f"{emoji} <b>{record.levelname}</b> · <code>{logger_name}</code> · <i>{timestamp}</i>"
        )
        body = html.escape(msg_text, quote=True)

        tb_text = ""
        if record.exc_info and record.exc_info[0] is not None:
            tb_text = "".join(traceback.format_exception(*record.exc_info))

        tb_html = ""
        if tb_text:
            escaped_tb = html.escape(tb_text, quote=True)
            tb_html = f'<pre><code class="language-python">{escaped_tb}</code></pre>'

        full_html = header + "\n" + body
        if tb_html:
            full_html += "\n\n" + tb_html

        if len(full_html) <= MAX_MESSAGE_LENGTH:
            return FormattedRecord(message=full_html)

        # Overflow: create attachment with full plain text
        plain = f"{record.levelname} · {record.name} · {timestamp}\n{msg_text}"
        if tb_text:
            plain += "\n\n" + tb_text
        attachment = plain.encode("utf-8")

        # Short summary for the message
        summary_body = body[:800] + "…" if len(body) > 800 else body
        summary = header + "\n" + summary_body + "\n\n<i>(see attachment for full message)</i>"
        if len(summary) > MAX_MESSAGE_LENGTH:
            summary = summary[: MAX_MESSAGE_LENGTH - 20] + "\n…[truncated]"

        epoch_ms = int(record.created * 1000)
        filename = f"{record.levelname}-{record.name}-{epoch_ms}.txt"

        return FormattedRecord(
            message=summary,
            attachment=attachment,
            attachment_filename=filename,
        )
