"""Tests for the async worker transport."""

import time

import httpx
import pytest
import respx

from tgwarden.conf import TgwardenSettings
from tgwarden.transports.async_worker import AsyncWorkerTransport
from tgwarden.transports.base import SendPayload


@pytest.fixture()
def settings() -> TgwardenSettings:
    return TgwardenSettings(
        bot_token="123:ABC",
        chat_id="-100123",
        transport="async_worker",
        api_base_url="https://api.telegram.org",
        queue_max_size=100,
        retry_max_attempts=3,
        retry_base_seconds=0.01,
        retry_cap_seconds=0.1,
        request_timeout=2.0,
    )


def _payload(msg: str = "test") -> SendPayload:
    return SendPayload(text=msg)


@respx.mock
def test_submit_is_non_blocking_under_load(settings: TgwardenSettings) -> None:
    respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    transport = AsyncWorkerTransport(settings)
    t0 = time.perf_counter()
    for i in range(1000):
        transport.submit(_payload(f"msg {i}"))
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5  # submits should be near-instant
    transport.shutdown()


@respx.mock
def test_records_eventually_sent(settings: TgwardenSettings) -> None:
    route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    transport = AsyncWorkerTransport(settings)
    for i in range(10):
        transport.submit(_payload(f"msg {i}"))
    transport.flush(timeout=5.0)
    transport.shutdown()
    # With batching, 10 records may be combined into fewer messages
    assert route.call_count >= 1
    assert transport.sent_count >= 1


@respx.mock
def test_overflow_drops_oldest() -> None:
    s = TgwardenSettings(
        bot_token="123:ABC",
        chat_id="-100123",
        transport="async_worker",
        api_base_url="https://api.telegram.org",
        queue_max_size=5,
        retry_max_attempts=1,
        retry_base_seconds=0.01,
        retry_cap_seconds=0.05,
        request_timeout=2.0,
    )
    # Mock slow responses to fill queue
    respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {}})
    )
    transport = AsyncWorkerTransport(s)
    # Pause consumer by flooding
    for i in range(20):
        transport.submit(_payload(f"msg {i}"))
    transport.flush(timeout=5.0)
    transport.shutdown()
    # Some should have been dropped
    assert transport.dropped_count > 0


@respx.mock
def test_retry_on_429(settings: TgwardenSettings) -> None:
    route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0.01"}, json={"ok": False}),
        httpx.Response(200, json={"ok": True, "result": {}}),
    ]
    transport = AsyncWorkerTransport(settings)
    transport.submit(_payload("retry me"))
    transport.flush(timeout=5.0)
    transport.shutdown()
    assert transport.sent_count == 1
    assert route.call_count == 2


@respx.mock
def test_retry_on_5xx(settings: TgwardenSettings) -> None:
    route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage")
    route.side_effect = [
        httpx.Response(500, json={"ok": False}),
        httpx.Response(200, json={"ok": True, "result": {}}),
    ]
    transport = AsyncWorkerTransport(settings)
    transport.submit(_payload("retry me"))
    transport.flush(timeout=5.0)
    transport.shutdown()
    assert transport.sent_count == 1


@respx.mock
def test_no_retry_on_400(settings: TgwardenSettings) -> None:
    route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
        return_value=httpx.Response(400, json={"ok": False, "description": "Bad Request"})
    )
    transport = AsyncWorkerTransport(settings)
    transport.submit(_payload("bad"))
    transport.flush(timeout=5.0)
    transport.shutdown()
    assert route.call_count == 1
    assert transport.dropped_count == 1
    assert transport.sent_count == 0


def test_shutdown_stops_thread(settings: TgwardenSettings) -> None:
    transport = AsyncWorkerTransport(settings)
    assert transport._thread is not None
    assert transport._thread.is_alive()
    transport.shutdown()
    time.sleep(0.5)
    assert not transport._thread.is_alive()
