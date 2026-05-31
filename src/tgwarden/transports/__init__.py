"""Transport layer for tgwarden."""

from __future__ import annotations

from tgwarden.conf import TgwardenSettings
from tgwarden.exceptions import ConfigurationError
from tgwarden.transports.base import SendPayload, Transport

__all__ = ["SendPayload", "Transport", "build_transport"]


def build_transport(settings: TgwardenSettings) -> Transport:
    """Factory: return the appropriate transport based on settings.transport."""
    if settings.transport == "sync":
        from tgwarden.transports.sync_ import SyncTransport

        return SyncTransport(settings)

    if settings.transport == "async_worker":
        from tgwarden.transports.async_worker import AsyncWorkerTransport

        return AsyncWorkerTransport(settings)

    if settings.transport == "celery":
        from tgwarden.transports.celery_ import CeleryTransport

        return CeleryTransport(settings)

    raise ConfigurationError(
        f"Unknown transport: {settings.transport!r}. Choose 'sync', 'async_worker', or 'celery'."
    )
