"""Logging filters for tgwarden."""

from __future__ import annotations

import logging
import random


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
