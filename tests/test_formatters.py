"""Tests for tgwarden.formatters."""

import logging
import sys

from tgwarden.formatters import LEVEL_EMOJI, MAX_MESSAGE_LENGTH, FormattedRecord, HTMLFormatter


def _make_record(
    msg: str = "test", level: int = logging.ERROR, name: str = "test.logger"
) -> logging.LogRecord:
    return logging.LogRecord(
        name=name, level=level, pathname="", lineno=0, msg=msg, args=(), exc_info=None
    )


def test_basic_record_formatting() -> None:
    fmt = HTMLFormatter()
    fr = fmt.format_record(_make_record("hello world", logging.ERROR))
    assert isinstance(fr, FormattedRecord)
    assert "<b>ERROR</b>" in fr.message
    assert "hello world" in fr.message
    assert "<code>test.logger</code>" in fr.message
    assert fr.attachment is None


def test_html_escapes_message() -> None:
    fmt = HTMLFormatter()
    fr = fmt.format_record(_make_record("<script>alert('xss')</script>"))
    assert "<script>" not in fr.message
    assert "&lt;script&gt;" in fr.message


def test_traceback_in_pre_block() -> None:
    fmt = HTMLFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
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
    fr = fmt.format_record(record)
    assert '<pre><code class="language-python">' in fr.message
    assert "ValueError: boom" in fr.message
    assert fr.attachment is None


def test_short_message_no_attachment() -> None:
    fmt = HTMLFormatter()
    fr = fmt.format_record(_make_record("short"))
    assert fr.attachment is None
    assert fr.attachment_filename is None


def test_long_message_overflow_to_attachment() -> None:
    fmt = HTMLFormatter()
    fr = fmt.format_record(_make_record("x" * 50_000))
    assert fr.attachment is not None
    assert fr.attachment_filename is not None
    assert fr.attachment_filename.endswith(".txt")
    assert len(fr.message) <= MAX_MESSAGE_LENGTH
    assert b"x" * 1000 in fr.attachment
    assert "(see attachment for full message)" in fr.message


def test_attachment_filename_pattern() -> None:
    fmt = HTMLFormatter()
    record = _make_record("x" * 50_000, level=logging.WARNING, name="my.app")
    fr = fmt.format_record(record)
    assert fr.attachment_filename is not None
    assert fr.attachment_filename.startswith("WARNING-my.app-")
    assert fr.attachment_filename.endswith(".txt")


def test_emoji_per_level() -> None:
    fmt = HTMLFormatter()
    for level_name, emoji in LEVEL_EMOJI.items():
        level = getattr(logging, level_name)
        fr = fmt.format_record(_make_record("msg", level))
        assert emoji in fr.message


def test_backward_compat_format() -> None:
    """The .format() method still returns a string for backward compat."""
    fmt = HTMLFormatter()
    result = fmt.format(_make_record("hello"))
    assert isinstance(result, str)
    assert "hello" in result
