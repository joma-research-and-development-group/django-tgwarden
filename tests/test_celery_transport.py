"""Tests for the Celery transport."""

from unittest.mock import patch

import httpx
import pytest
import respx
from django.test import override_settings

from tgwarden.conf import TgwardenSettings, clear_settings_cache
from tgwarden.transports.base import SendPayload
from tgwarden.transports.celery_ import CeleryTransport


@pytest.fixture(autouse=True)
def _clear() -> None:
    clear_settings_cache()


SETTINGS = {
    "BOT_TOKEN": "123:ABC",
    "CHAT_ID": "-100123",
    "TRANSPORT": "celery",
}


def test_submit_enqueues_task() -> None:
    s = TgwardenSettings(bot_token="123:ABC", chat_id="-100123", transport="celery")
    transport = CeleryTransport(s)
    payload = SendPayload(text="hello", topic_id=5, parse_mode="HTML")

    with patch("tgwarden.tasks.send_to_telegram.apply_async") as mock_apply:
        transport.submit(payload)
        mock_apply.assert_called_once()
        args = mock_apply.call_args[1]["args"][0]
        assert args["text"] == "hello"
        assert args["topic_id"] == 5


@respx.mock
@override_settings(
    TGWARDEN=SETTINGS,
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
def test_task_calls_send_message() -> None:
    route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    from tgwarden.tasks import send_to_telegram

    payload = SendPayload(text="test msg", parse_mode="HTML")
    send_to_telegram(payload.to_dict())
    assert route.called


@respx.mock
@override_settings(
    TGWARDEN=SETTINGS,
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
def test_task_calls_send_document_when_attachment() -> None:
    route = respx.post("https://api.telegram.org/bot123:ABC/sendDocument").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    from tgwarden.tasks import send_to_telegram

    payload = SendPayload(text="caption", attachment=b"file content", attachment_filename="log.txt")
    send_to_telegram(payload.to_dict())
    assert route.called


def test_celery_transport_raises_when_celery_missing() -> None:
    import sys

    from tgwarden.exceptions import ConfigurationError
    from tgwarden.transports import celery_ as celery_mod

    # Temporarily remove celery from sys.modules
    celery_module = sys.modules.pop("celery", None)
    sys.modules["celery"] = None  # type: ignore[assignment]
    try:
        with pytest.raises(ConfigurationError, match="celery"):
            celery_mod._ensure_celery_installed()
    finally:
        if celery_module is not None:
            sys.modules["celery"] = celery_module
        else:
            sys.modules.pop("celery", None)
