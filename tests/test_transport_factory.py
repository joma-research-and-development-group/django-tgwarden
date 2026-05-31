"""Tests for the transport factory."""

import pytest

from tgwarden.conf import TgwardenSettings, clear_settings_cache
from tgwarden.exceptions import ConfigurationError
from tgwarden.transports import build_transport
from tgwarden.transports.async_worker import AsyncWorkerTransport
from tgwarden.transports.sync_ import SyncTransport


@pytest.fixture(autouse=True)
def _clear() -> None:
    clear_settings_cache()


def test_build_transport_sync() -> None:
    s = TgwardenSettings(bot_token="t", chat_id="c", transport="sync")
    t = build_transport(s)
    assert isinstance(t, SyncTransport)
    t.shutdown()


def test_build_transport_async_worker() -> None:
    s = TgwardenSettings(bot_token="t", chat_id="c", transport="async_worker")
    t = build_transport(s)
    assert isinstance(t, AsyncWorkerTransport)
    t.shutdown()


def test_unknown_transport_raises() -> None:
    s = TgwardenSettings(bot_token="t", chat_id="c", transport="celery")  # type: ignore[arg-type]
    with pytest.raises(ConfigurationError, match="Unknown transport"):
        build_transport(s)
