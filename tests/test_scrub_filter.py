"""Tests for ScrubFilter."""

import logging

from tgwarden.filters import ScrubFilter


def _make_record(msg: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0, msg=msg, args=(), exc_info=None
    )


def test_scrubs_password_query_string() -> None:
    f = ScrubFilter()
    record = _make_record("login: username=alice&password=hunter2")
    f.filter(record)
    assert "hunter2" not in record.getMessage()
    assert "password=***" in record.getMessage()


def test_scrubs_authorization_header_log() -> None:
    f = ScrubFilter()
    record = _make_record("headers: authorization=Bearer abc123xyz")
    f.filter(record)
    assert "abc123xyz" not in record.getMessage()
    assert "authorization=***" in record.getMessage()


def test_scrubs_credit_card_in_message() -> None:
    f = ScrubFilter()
    record = _make_record("payment with 4111 1111 1111 1111 processed")
    f.filter(record)
    assert "4111 1111 1111 1111" not in record.getMessage()
    assert "***" in record.getMessage()


def test_custom_keys_and_replacement() -> None:
    f = ScrubFilter(keys=["ssn"], replacement="[REDACTED]")
    record = _make_record("user ssn=123-45-6789")
    f.filter(record)
    assert "123-45-6789" not in record.getMessage()
    assert "ssn=[REDACTED]" in record.getMessage()


def test_does_not_scrub_unrelated_text() -> None:
    f = ScrubFilter()
    record = _make_record("hello world, nothing sensitive here")
    f.filter(record)
    assert record.getMessage() == "hello world, nothing sensitive here"
