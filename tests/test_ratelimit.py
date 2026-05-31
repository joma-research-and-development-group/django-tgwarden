"""Tests for tgwarden.ratelimit."""

import asyncio
import time

from tgwarden.ratelimit import TokenBucket


def test_initial_full_bucket() -> None:
    bucket = TokenBucket(capacity=10, refill_per_sec=10)

    async def _run() -> None:
        # Should not block — bucket starts full
        await bucket.acquire(5)

    asyncio.run(_run())


def test_acquire_blocks_when_empty() -> None:
    bucket = TokenBucket(capacity=1, refill_per_sec=100)

    async def _run() -> float:
        await bucket.acquire(1)  # drains bucket
        t0 = time.monotonic()
        await bucket.acquire(1)  # must wait for refill
        return time.monotonic() - t0

    elapsed = asyncio.run(_run())
    assert elapsed >= 0.005  # at least some wait


def test_refill_over_time() -> None:
    bucket = TokenBucket(capacity=10, refill_per_sec=1000)

    async def _run() -> None:
        await bucket.acquire(10)  # drain
        await asyncio.sleep(0.02)  # refill ~20 tokens (capped at 10)
        await bucket.acquire(5)  # should succeed immediately

    asyncio.run(_run())


def test_concurrent_acquires_serialize_correctly() -> None:
    bucket = TokenBucket(capacity=2, refill_per_sec=100)

    async def _run() -> None:
        results: list[float] = []

        async def _acquire() -> None:
            await bucket.acquire(1)
            results.append(time.monotonic())

        await asyncio.gather(*[_acquire() for _ in range(5)])
        assert len(results) == 5

    asyncio.run(_run())
