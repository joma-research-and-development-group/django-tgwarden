"""Tests for topic routing."""

import logging

import httpx
import pytest
import respx
from django.test import override_settings

from tgwarden.conf import clear_settings_cache
from tgwarden.handlers import TelegramHandler

SETTINGS_WITH_TOPICS = {
    "BOT_TOKEN": "123:ABC",
    "CHAT_ID": "-100123",
    "TRANSPORT": "sync",
    "TOPICS": {"DEBUG": 5, "INFO": 6, "WARNING": 7, "ERROR": 8, "CRITICAL": 9},
}


@pytest.fixture(autouse=True)
def _clear() -> None:
    clear_settings_cache()


@respx.mock
@override_settings(TGWARDEN=SETTINGS_WITH_TOPICS)
def test_each_level_routes_to_configured_topic() -> None:
    import json

    route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    handler = TelegramHandler(level=logging.DEBUG)

    levels = {"DEBUG": 5, "INFO": 6, "WARNING": 7, "ERROR": 8, "CRITICAL": 9}
    for level_name, _topic_id in levels.items():
        level = getattr(logging, level_name)
        record = logging.LogRecord(
            name="test",
            level=level,
            pathname="",
            lineno=0,
            msg="msg",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

    handler.close()
    assert route.call_count == 5
    for i, (_level_name, topic_id) in enumerate(levels.items()):
        body = json.loads(route.calls[i].request.content)
        assert body["message_thread_id"] == topic_id


@respx.mock
@override_settings(TGWARDEN={**SETTINGS_WITH_TOPICS, "TOPICS": {}})
def test_topics_empty_disables_routing() -> None:
    import json

    route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    handler = TelegramHandler(level=logging.DEBUG)
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="msg",
        args=(),
        exc_info=None,
    )
    handler.emit(record)
    handler.close()

    body = json.loads(route.calls[0].request.content)
    assert "message_thread_id" not in body
