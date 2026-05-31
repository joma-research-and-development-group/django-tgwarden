"""Telegram Bot API client for tgwarden."""

from __future__ import annotations

from typing import Any

import httpx

from tgwarden.conf import TgwardenSettings
from tgwarden.exceptions import TelegramAPIError


class TelegramClient:
    """Synchronous client for the Telegram Bot API sendMessage endpoint."""

    def __init__(self, settings: TgwardenSettings) -> None:
        self._settings = settings
        self._client = httpx.Client(timeout=settings.request_timeout)

    def send_message(
        self,
        text: str,
        *,
        topic_id: int | None = None,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        """Send a message via the Telegram Bot API.

        Args:
            text: Message text.
            topic_id: Optional forum topic thread ID.
            parse_mode: Override parse mode (defaults to settings value).

        Returns:
            The 'result' dict from the Telegram API response.

        Raises:
            TelegramAPIError: On non-2xx response from Telegram.
        """
        url = f"{self._settings.api_base_url}/bot{self._settings.bot_token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": self._settings.chat_id,
            "text": text,
            "parse_mode": parse_mode or self._settings.parse_mode,
        }
        if topic_id is not None:
            payload["message_thread_id"] = topic_id

        response = self._client.post(url, json=payload)
        if response.status_code != 200:
            raise TelegramAPIError(
                status_code=response.status_code,
                body=response.text[:500],
            )
        return response.json().get("result", {})  # type: ignore[no-any-return]

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> TelegramClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
