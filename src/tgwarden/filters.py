"""Logging filters for tgwarden."""

from __future__ import annotations

import logging
import random
import re
from collections.abc import Iterable

from tgwarden.middleware import get_current_context

DEFAULT_SCRUB_KEYS = (
    "password",
    "token",
    "authorization",
    "cookie",
    "secret",
    "api_key",
    "x-api-key",
)

DEFAULT_SCRUB_PATTERNS = (
    r"\b(?:\d[ -]*?){13,16}\b",  # credit-card-ish
)


class SamplingFilter(logging.Filter):
    """Probabilistic sampling per-level.

    Example LOGGING config:
        "filters": {
            "sample": {
                "()": "tgwarden.filters.SamplingFilter",
                "rates": {"DEBUG": 0.05, "INFO": 0.1},
            },
        },
    """

    def __init__(self, *, rates: dict[str, float] | None = None) -> None:
        super().__init__()
        self.rates: dict[str, float] = rates or {}

    def filter(self, record: logging.LogRecord) -> bool:
        """Return True if the record should pass through."""
        rate = self.rates.get(record.levelname, 1.0)
        if rate >= 1.0:
            return True
        if rate <= 0.0:
            return False
        return random.random() < rate  # noqa: S311


class ContextFilter(logging.Filter):
    """Injects request context fields into the LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = get_current_context()
        if ctx is not None:
            record.request_id = ctx.request_id
            record.request_method = ctx.method
            record.request_path = ctx.path
            record.user_id = ctx.user_id
            record.client_ip = ctx.client_ip
        return True


class ScrubFilter(logging.Filter):
    """Redacts sensitive values from log messages."""

    def __init__(
        self,
        *,
        keys: Iterable[str] | None = None,
        patterns: Iterable[str] | None = None,
        replacement: str = "***",
    ) -> None:
        super().__init__()
        self._keys = tuple(k.lower() for k in (keys or DEFAULT_SCRUB_KEYS))
        self._patterns = [re.compile(p) for p in (patterns or DEFAULT_SCRUB_PATTERNS)]
        self._replacement = replacement
        # Build key regex: key=value or key:value
        escaped_keys = "|".join(re.escape(k) for k in self._keys)
        self._key_re = re.compile(
            rf"({escaped_keys})\s*[=:]\s*([^\s&,;]+(?:\s+[^\s&,;=:]+)*)",
            re.IGNORECASE,
        )

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        scrubbed = self._scrub(msg)
        record.msg = scrubbed
        record.args = ()
        return True

    def _scrub(self, text: str) -> str:
        text = self._key_re.sub(rf"\1={self._replacement}", text)
        for pattern in self._patterns:
            text = pattern.sub(self._replacement, text)
        return text
