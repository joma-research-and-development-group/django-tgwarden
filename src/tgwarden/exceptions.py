"""Custom exceptions for tgwarden."""


class TgwardenError(Exception):
    """Base exception for all tgwarden errors."""


class ConfigurationError(TgwardenError):
    """Raised when tgwarden settings are missing or invalid."""


class TelegramAPIError(TgwardenError):
    """Raised when the Telegram Bot API returns a non-2xx response."""

    def __init__(self, *, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Telegram API error {status_code}: {body[:200]}")
