"""Token bucket rate limiter for tgwarden."""

from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """Async-aware token bucket rate limiter."""

    def __init__(self, *, capacity: float, refill_per_sec: float) -> None:
        self._capacity = capacity
        self._refill_per_sec = refill_per_sec
        self._tokens = capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        self.total_wait_seconds: float = 0.0

    async def acquire(self, tokens: float = 1.0) -> None:
        """Acquire tokens, sleeping if necessary until available."""
        async with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return
            needed = tokens - self._tokens
            wait = needed / self._refill_per_sec
            self.total_wait_seconds += wait
            await asyncio.sleep(wait)
            self._refill()
            self._tokens -= tokens

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_per_sec)
        self._last_refill = now
