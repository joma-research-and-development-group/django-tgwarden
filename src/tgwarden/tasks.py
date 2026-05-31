"""Celery tasks for tgwarden."""

from __future__ import annotations

from typing import Any

import httpx
from celery import shared_task

from tgwarden.client import TelegramClient
from tgwarden.conf import get_settings
from tgwarden.transports.base import SendPayload


@shared_task(  # type: ignore[untyped-decorator]
    bind=True,
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_backoff_max=30,
    retry_jitter=True,
    max_retries=5,
    name="tgwarden.send_to_telegram",
)
def send_to_telegram(self: Any, payload_dict: dict[str, Any]) -> None:
    """Send a log record to Telegram via the Bot API."""
    settings = get_settings()
    payload = SendPayload.from_dict(payload_dict)
    with TelegramClient(settings) as client:
        if payload.attachment is not None and payload.attachment_filename is not None:
            client.send_document(
                payload.attachment,
                payload.attachment_filename,
                caption=payload.text[:1024] if payload.text else None,
                topic_id=payload.topic_id,
            )
        else:
            client.send_message(
                payload.text,
                topic_id=payload.topic_id,
                parse_mode=payload.parse_mode,
            )
