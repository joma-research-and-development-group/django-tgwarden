"""Celery transport for tgwarden — offloads sends to Celery tasks."""

from __future__ import annotations

from tgwarden.conf import TgwardenSettings
from tgwarden.exceptions import ConfigurationError
from tgwarden.transports.base import SendPayload


def _ensure_celery_installed() -> None:
    try:
        import celery  # noqa: F401
    except ImportError as exc:
        raise ConfigurationError(
            "TRANSPORT='celery' requires the 'celery' extra: pip install django-tgwarden[celery]"
        ) from exc


class CeleryTransport:
    """Transport that offloads sends to a Celery task."""

    def __init__(self, settings: TgwardenSettings) -> None:
        _ensure_celery_installed()
        self._settings = settings

    def submit(self, payload: SendPayload) -> None:
        """Enqueue a Celery task to send the payload."""
        from tgwarden.tasks import send_to_telegram

        send_to_telegram.apply_async(args=[payload.to_dict()])

    def flush(self, timeout: float = 5.0) -> bool:
        """No-op — Celery manages its own queue."""
        return True

    def shutdown(self) -> None:
        """No-op — Celery manages its own lifecycle."""
