"""Message batcher for tgwarden — coalesces multiple records into one Telegram message."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

MAX_TELEGRAM_LENGTH = 4096
SEPARATOR = "\n\n———\n\n"


@dataclass
class BatchEntry:
    """A single formatted record waiting to be batched."""

    text: str
    bytes_len: int = field(init=False)

    def __post_init__(self) -> None:
        self.bytes_len = len(self.text.encode("utf-8"))


class Batcher:
    """Accumulates log entries and flushes them as combined messages."""

    def __init__(
        self,
        *,
        max_records: int = 20,
        max_bytes: int = 3500,
        max_seconds: float = 2.0,
        on_flush: Callable[[str], Awaitable[None]],
    ) -> None:
        self._max_records = max_records
        self._max_bytes = max_bytes
        self._max_seconds = max_seconds
        self._on_flush = on_flush
        self._buffer: list[BatchEntry] = []
        self._total_bytes = 0
        self._oldest_time: float | None = None
        self.batch_count = 0
        self.split_count = 0

    def add(self, entry: BatchEntry) -> None:
        """Add an entry to the buffer."""
        if not self._buffer:
            self._oldest_time = time.monotonic()
        self._buffer.append(entry)
        self._total_bytes += entry.bytes_len

    async def maybe_flush(self) -> None:
        """Flush if any trigger condition is met."""
        if not self._buffer:
            return
        if (
            len(self._buffer) >= self._max_records
            or self._total_bytes >= self._max_bytes
            or (
                self._oldest_time is not None
                and (time.monotonic() - self._oldest_time) >= self._max_seconds
            )
        ):
            await self.force_flush()

    async def force_flush(self) -> None:
        """Flush all buffered entries, splitting if needed."""
        if not self._buffer:
            return

        entries = self._buffer
        self._buffer = []
        self._total_bytes = 0
        self._oldest_time = None

        # Build messages respecting 4096 char limit
        messages: list[str] = []
        current_parts: list[str] = []
        current_len = 0

        for entry in entries:
            sep_len = len(SEPARATOR) if current_parts else 0
            if current_len + sep_len + len(entry.text) > MAX_TELEGRAM_LENGTH and current_parts:
                messages.append(SEPARATOR.join(current_parts))
                current_parts = []
                current_len = 0
                sep_len = 0

            current_parts.append(entry.text)
            current_len += sep_len + len(entry.text)

        if current_parts:
            messages.append(SEPARATOR.join(current_parts))

        if len(messages) > 1:
            self.split_count += len(messages) - 1

        for msg in messages:
            self.batch_count += 1
            await self._on_flush(msg)
