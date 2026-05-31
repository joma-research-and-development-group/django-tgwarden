"""Log formatters for tgwarden."""

from __future__ import annotations

import html
import logging
import traceback
from datetime import UTC, datetime

MAX_MESSAGE_LENGTH = 4096

LEVEL_EMOJI: dict[str, str] = {
    "DEBUG": "🔵",
    "INFO": "ℹ️",  # noqa: RUF001
    "WARNING": "⚠️",
    "ERROR": "🐛",
    "CRITICAL": "🔥",
}


class HTMLFormatter(logging.Formatter):
    """Format log records as Telegram-compatible HTML."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a LogRecord into HTML suitable for Telegram's sendMessage API."""
        emoji = LEVEL_EMOJI.get(record.levelname, "📝")
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        message = html.escape(record.getMessage(), quote=True)
        logger_name = html.escape(record.name, quote=True)

        text = (
            f"{emoji} <b>{record.levelname}</b> · "
            f"<code>{logger_name}</code> · {timestamp}\n"
            f"{message}"
        )

        if record.exc_info and record.exc_info[0] is not None:
            tb = "".join(traceback.format_exception(*record.exc_info))
            tb_escaped = html.escape(tb, quote=True)
            text += f'\n\n<pre><code class="language-python">{tb_escaped}</code></pre>'

        if len(text) > MAX_MESSAGE_LENGTH:
            suffix = "\n…[truncated]"
            text = text[: MAX_MESSAGE_LENGTH - len(suffix)] + suffix

        return text
