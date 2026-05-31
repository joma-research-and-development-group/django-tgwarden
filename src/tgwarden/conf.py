"""Configuration for tgwarden — single source of truth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tgwarden.exceptions import ConfigurationError

_cached_settings: TgwardenSettings | None = None


@dataclass(frozen=True, slots=True)
class TgwardenSettings:
    """Validated, immutable settings for tgwarden."""

    bot_token: str
    chat_id: str
    parse_mode: Literal["HTML", "MarkdownV2"] = "HTML"
    transport: Literal["sync", "async_worker", "celery"] = "sync"
    request_timeout: float = 5.0
    api_base_url: str = "https://api.telegram.org"


def get_settings() -> TgwardenSettings:
    """Load and cache TgwardenSettings from Django settings.TGWARDEN.

    Raises:
        ConfigurationError: If TGWARDEN is missing or required keys are absent.
    """
    global _cached_settings
    if _cached_settings is not None:
        return _cached_settings

    from django.conf import settings

    raw = getattr(settings, "TGWARDEN", None)
    if raw is None:
        raise ConfigurationError(
            "settings.TGWARDEN is not defined. "
            "Add a TGWARDEN dict with at least 'BOT_TOKEN' and 'CHAT_ID'."
        )

    bot_token = raw.get("BOT_TOKEN")
    if not bot_token:
        raise ConfigurationError("TGWARDEN['BOT_TOKEN'] is required.")

    chat_id = raw.get("CHAT_ID")
    if not chat_id:
        raise ConfigurationError("TGWARDEN['CHAT_ID'] is required.")

    _cached_settings = TgwardenSettings(
        bot_token=bot_token,
        chat_id=str(chat_id),
        parse_mode=raw.get("PARSE_MODE", "HTML"),
        transport=raw.get("TRANSPORT", "sync"),
        request_timeout=float(raw.get("REQUEST_TIMEOUT", 5.0)),
        api_base_url=raw.get("API_BASE_URL", "https://api.telegram.org"),
    )
    return _cached_settings


def clear_settings_cache() -> None:
    """Clear the cached settings. Used in tests."""
    global _cached_settings
    _cached_settings = None
