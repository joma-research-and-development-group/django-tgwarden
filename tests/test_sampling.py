"""Tests for tgwarden.filters.SamplingFilter."""

import logging

from tgwarden.filters import SamplingFilter


def _make_record(level: int = logging.INFO) -> logging.LogRecord:
    return logging.LogRecord(
        name="test", level=level, pathname="", lineno=0, msg="msg", args=(), exc_info=None
    )


def test_default_rates_pass_all() -> None:
    f = SamplingFilter()
    for _ in range(100):
        assert f.filter(_make_record()) is True


def test_per_level_rate_zero_blocks_all() -> None:
    f = SamplingFilter(rates={"INFO": 0.0})
    for _ in range(100):
        assert f.filter(_make_record(logging.INFO)) is False


def test_unknown_level_passes() -> None:
    f = SamplingFilter(rates={"DEBUG": 0.0})
    # INFO not in rates → passes
    assert f.filter(_make_record(logging.INFO)) is True


def test_statistical_distribution_within_tolerance() -> None:
    f = SamplingFilter(rates={"INFO": 0.1})
    passed = sum(1 for _ in range(10000) if f.filter(_make_record(logging.INFO)))
    # Expect ~1000 ± 200
    assert 600 < passed < 1400
