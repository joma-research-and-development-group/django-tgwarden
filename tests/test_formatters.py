"""Tests for tgwarden.formatters."""

import logging

from tgwarden.formatters import LEVEL_EMOJI, MAX_MESSAGE_LENGTH, HTMLFormatter


def _make_record(
    msg: str = "test", level: int = logging.ERROR, name: str = "test.logger"
) -> logging.LogRecord:
    return logging.LogRecord(
        name=name, level=level, pathname="", lineno=0, msg=msg, args=(), exc_info=None
    )


def test_basic_record_formatting() -> None:
    fmt = HTMLFormatter()
    record = _make_record("hello world", logging.ERROR)
    result = fmt.format(record)
    assert "<b>ERROR</b>" in result
    assert "hello world" in result
    assert "<code>test.logger</code>" in result


def test_html_escapes_message() -> None:
    fmt = HTMLFormatter()
    record = _make_record("<script>alert('xss')</script>")
    result = fmt.format(record)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_traceback_in_pre_block() -> None:
    fmt = HTMLFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="t",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="err",
            args=(),
            exc_info=exc_info,
        )
    result = fmt.format(record)
    assert '<pre><code class="language-python">' in result
    assert "ValueError: boom" in result


def test_truncates_at_4096() -> None:
    fmt = HTMLFormatter()
    record = _make_record("x" * 5000)
    result = fmt.format(record)
    assert len(result) <= MAX_MESSAGE_LENGTH
    assert "…[truncated]" in result


def test_emoji_per_level() -> None:
    fmt = HTMLFormatter()
    for level_name, emoji in LEVEL_EMOJI.items():
        level = getattr(logging, level_name)
        record = _make_record("msg", level)
        result = fmt.format(record)
        assert emoji in result
