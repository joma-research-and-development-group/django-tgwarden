"""Tests for tgwarden.batcher."""

import asyncio

import pytest

from tgwarden.batcher import SEPARATOR, BatchEntry, Batcher


@pytest.fixture()
def flushed() -> list[str]:
    return []


def _make_batcher(
    flushed: list[str],
    *,
    max_records: int = 20,
    max_bytes: int = 3500,
    max_seconds: float = 2.0,
) -> Batcher:
    async def on_flush(text: str) -> None:
        flushed.append(text)

    return Batcher(
        max_records=max_records,
        max_bytes=max_bytes,
        max_seconds=max_seconds,
        on_flush=on_flush,
    )


def test_flush_on_count(flushed: list[str]) -> None:
    batcher = _make_batcher(flushed, max_records=5)
    for i in range(5):
        batcher.add(BatchEntry(text=f"msg {i}"))
    asyncio.run(batcher.maybe_flush())
    assert len(flushed) == 1
    assert "msg 0" in flushed[0]
    assert "msg 4" in flushed[0]


def test_flush_on_bytes(flushed: list[str]) -> None:
    batcher = _make_batcher(flushed, max_bytes=50)
    batcher.add(BatchEntry(text="x" * 60))
    asyncio.run(batcher.maybe_flush())
    assert len(flushed) == 1


def test_flush_on_time(flushed: list[str]) -> None:
    import time

    batcher = _make_batcher(flushed, max_seconds=0.01)
    batcher.add(BatchEntry(text="hello"))
    time.sleep(0.02)
    asyncio.run(batcher.maybe_flush())
    assert len(flushed) == 1


def test_force_flush_partial(flushed: list[str]) -> None:
    batcher = _make_batcher(flushed, max_records=100)
    batcher.add(BatchEntry(text="partial"))
    asyncio.run(batcher.force_flush())
    assert len(flushed) == 1
    assert flushed[0] == "partial"


def test_split_when_render_exceeds_4096(flushed: list[str]) -> None:
    batcher = _make_batcher(flushed, max_records=100, max_bytes=100000)
    # Each entry ~500 chars, 10 entries = ~5000 + separators > 4096
    for _i in range(10):
        batcher.add(BatchEntry(text="A" * 500))
    asyncio.run(batcher.force_flush())
    assert len(flushed) >= 2
    for msg in flushed:
        assert len(msg) <= 4096


def test_separator_format(flushed: list[str]) -> None:
    batcher = _make_batcher(flushed, max_records=3)
    batcher.add(BatchEntry(text="one"))
    batcher.add(BatchEntry(text="two"))
    batcher.add(BatchEntry(text="three"))
    asyncio.run(batcher.maybe_flush())
    assert SEPARATOR in flushed[0]
    assert "one" in flushed[0]
    assert "three" in flushed[0]
