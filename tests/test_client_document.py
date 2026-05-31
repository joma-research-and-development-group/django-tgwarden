"""Tests for TelegramClient.send_document."""

import httpx
import pytest
import respx

from tgwarden.client import TelegramClient
from tgwarden.conf import TgwardenSettings
from tgwarden.exceptions import TelegramAPIError


@pytest.fixture()
def settings() -> TgwardenSettings:
    return TgwardenSettings(bot_token="123:ABC", chat_id="-100123")


@respx.mock
def test_send_document_multipart_payload(settings: TgwardenSettings) -> None:
    route = respx.post("https://api.telegram.org/bot123:ABC/sendDocument").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
    )
    with TelegramClient(settings) as client:
        client.send_document(b"hello world", "test.txt", caption="<b>cap</b>")

    assert route.called
    req = route.calls[0].request
    assert b"test.txt" in req.content
    assert b"hello world" in req.content


@respx.mock
def test_send_document_with_topic_id(settings: TgwardenSettings) -> None:
    route = respx.post("https://api.telegram.org/bot123:ABC/sendDocument").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    with TelegramClient(settings) as client:
        client.send_document(b"data", "f.txt", topic_id=42)

    req = route.calls[0].request
    assert b"42" in req.content


@respx.mock
def test_send_document_error_path(settings: TgwardenSettings) -> None:
    respx.post("https://api.telegram.org/bot123:ABC/sendDocument").mock(
        return_value=httpx.Response(400, json={"ok": False, "description": "Bad"})
    )
    with TelegramClient(settings) as client:
        with pytest.raises(TelegramAPIError) as exc_info:
            client.send_document(b"data", "f.txt")
    assert exc_info.value.status_code == 400
