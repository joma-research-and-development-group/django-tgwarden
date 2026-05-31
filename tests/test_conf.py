"""Tests for tgwarden.conf."""

import pytest
from django.test import override_settings

from tgwarden.conf import TgwardenSettings, clear_settings_cache, get_settings
from tgwarden.exceptions import ConfigurationError


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_settings_cache()


VALID_SETTINGS = {"BOT_TOKEN": "123:ABC", "CHAT_ID": "-1001234567890"}


@override_settings(TGWARDEN=VALID_SETTINGS)
def test_get_settings_happy_path() -> None:
    s = get_settings()
    assert isinstance(s, TgwardenSettings)
    assert s.bot_token == "123:ABC"
    assert s.chat_id == "-1001234567890"
    assert s.parse_mode == "HTML"
    assert s.transport == "async_worker"


@override_settings(TGWARDEN={"CHAT_ID": "-100123"})
def test_missing_token_raises() -> None:
    with pytest.raises(ConfigurationError, match="BOT_TOKEN"):
        get_settings()


@override_settings(TGWARDEN={"BOT_TOKEN": "123:ABC"})
def test_missing_chat_id_raises() -> None:
    with pytest.raises(ConfigurationError, match="CHAT_ID"):
        get_settings()


@override_settings(TGWARDEN={"BOT_TOKEN": "t", "CHAT_ID": -100123})
def test_chat_id_int_normalized_to_str() -> None:
    s = get_settings()
    assert s.chat_id == "-100123"
    assert isinstance(s.chat_id, str)


@override_settings(TGWARDEN=VALID_SETTINGS)
def test_settings_cache_clear() -> None:
    s1 = get_settings()
    clear_settings_cache()
    s2 = get_settings()
    # Both valid but re-created
    assert s1 == s2


def test_no_tgwarden_setting_raises() -> None:
    with pytest.raises(ConfigurationError, match="TGWARDEN is not defined"):
        get_settings()
