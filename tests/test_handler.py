"""Tests for tgwarden.handlers."""

import logging
from unittest.mock import patch

import httpx
import pytest
import respx
from django.test import override_settings

from tgwarden.conf import clear_settings_cache
from tgwarden.handlers import TelegramHandler

SETTINGS = {
    "BOT_TOKEN": "123:ABC",
    "CHAT_ID": "-100123",
    "API_BASE_URL": "https://api.telegram.org",
    "TRANSPORT": "sync",
}


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_settings_cache()


@respx.mock
@override_settings(TGWARDEN=SETTINGS)
def test_emit_calls_client_with_formatted_text() -> None:
    route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    handler = TelegramHandler(level=logging.DEBUG)
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="hello",
        args=(),
        exc_info=None,
    )
    handler.emit(record)
    handler.close()
    assert route.called


@override_settings(TGWARDEN=SETTINGS)
def test_emit_swallows_exceptions() -> None:
    handler = TelegramHandler(level=logging.DEBUG)
    with patch("tgwarden.client.TelegramClient.send_message", side_effect=RuntimeError("boom")):
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        # Should not raise
        handler.emit(record)
    handler.close()


@override_settings(TGWARDEN=SETTINGS)
def test_emit_writes_to_stderr_on_failure(capsys: pytest.CaptureFixture[str]) -> None:
    handler = TelegramHandler(level=logging.DEBUG)
    handler.raiseExceptions = False
    with patch("tgwarden.client.TelegramClient.send_message", side_effect=RuntimeError("boom")):
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
    captured = capsys.readouterr()
    assert "[tgwarden] failed to send" in captured.err
    handler.close()


def test_handler_lazy_settings_load() -> None:
    # Should not raise at construction time even without settings
    handler = TelegramHandler()
    assert handler._transport is None
    handler.close()
