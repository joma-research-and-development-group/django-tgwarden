"""Tests for the tgwarden_test management command."""

import httpx
import respx
from django.core.management import call_command
from django.test import override_settings

from tgwarden.conf import clear_settings_cache

SETTINGS = {
    "BOT_TOKEN": "123:ABC",
    "CHAT_ID": "-100123",
    "API_BASE_URL": "https://api.telegram.org",
    "TRANSPORT": "sync",
}


@respx.mock
@override_settings(TGWARDEN=SETTINGS)
def test_tgwarden_test_command_emits_message() -> None:
    clear_settings_cache()
    route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    call_command("tgwarden_test", "--message", "hello from test")
    assert route.called
