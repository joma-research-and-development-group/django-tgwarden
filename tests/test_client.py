"""Tests for tgwarden.client."""

import httpx
import pytest
import respx

from tgwarden.client import TelegramClient
from tgwarden.conf import TgwardenSettings
from tgwarden.exceptions import TelegramAPIError


@pytest.fixture()
def settings() -> TgwardenSettings:
    return TgwardenSettings(
        bot_token="123:ABC",
        chat_id="-1001234567890",
        api_base_url="https://api.telegram.org",
    )


@respx.mock
def test_send_message_payload(settings: TgwardenSettings) -> None:
    route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
    )
    with TelegramClient(settings) as client:
        result = client.send_message("hello")

    assert route.called
    payload = route.calls[0].request.content
    assert b"hello" in payload
    assert result == {"message_id": 1}


@respx.mock
def test_send_message_uses_topic_id(settings: TgwardenSettings) -> None:
    route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    with TelegramClient(settings) as client:
        client.send_message("hi", topic_id=42)

    import json

    body = json.loads(route.calls[0].request.content)
    assert body["message_thread_id"] == 42


@respx.mock
def test_non_2xx_raises_telegram_api_error(settings: TgwardenSettings) -> None:
    respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
        return_value=httpx.Response(400, json={"ok": False, "description": "Bad Request"})
    )
    with TelegramClient(settings) as client:
        with pytest.raises(TelegramAPIError) as exc_info:
            client.send_message("fail")
    assert exc_info.value.status_code == 400


@respx.mock
def test_timeout_propagates() -> None:
    s = TgwardenSettings(bot_token="t", chat_id="c", request_timeout=0.01)
    respx.post("https://api.telegram.org/bott/sendMessage").mock(
        side_effect=httpx.ReadTimeout("timeout")
    )
    with TelegramClient(s) as client:
        with pytest.raises(httpx.ReadTimeout):
            client.send_message("x")
