"""Non-blocking async worker transport for tgwarden."""

from __future__ import annotations

import asyncio
import atexit
import random
import threading
from datetime import UTC, datetime
from typing import Any

import httpx

from tgwarden._internal import internal_logger
from tgwarden.conf import TgwardenSettings
from tgwarden.transports.base import SendPayload


class AsyncWorkerTransport:
    """Non-blocking transport: daemon thread + asyncio event loop + bounded queue."""

    def __init__(self, settings: TgwardenSettings) -> None:
        self._settings = settings
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[SendPayload] | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._shutdown_requested = False

        # Stats
        self.sent_count = 0
        self.dropped_count = 0
        self.last_send_at: datetime | None = None
        self.last_error: str | None = None

        self._start_worker()
        atexit.register(self.shutdown)

    @property
    def queue_size(self) -> int:
        """Current number of items in the queue."""
        if self._queue is None:
            return 0
        return self._queue.qsize()

    def _start_worker(self) -> None:
        self._thread = threading.Thread(target=self._run_loop, name="tgwarden-worker", daemon=True)
        self._thread.start()
        self._started.wait(timeout=5.0)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._queue = asyncio.Queue(maxsize=self._settings.queue_max_size)
        self._started.set()
        self._loop.run_until_complete(self._consumer())

    async def _consumer(self) -> None:
        async with httpx.AsyncClient(timeout=self._settings.request_timeout) as client:
            while True:
                try:
                    payload = await asyncio.wait_for(
                        self._queue.get(),  # type: ignore[union-attr]
                        timeout=0.5,
                    )
                except TimeoutError:
                    if self._shutdown_requested:
                        break
                    continue

                await self._send_with_retry(client, payload)
                self._queue.task_done()  # type: ignore[union-attr]

                if self._shutdown_requested and self._queue.empty():  # type: ignore[union-attr]
                    break

    async def _send_with_retry(self, client: httpx.AsyncClient, payload: SendPayload) -> None:
        is_doc = payload.attachment is not None and payload.attachment_filename is not None
        base_url = f"{self._settings.api_base_url}/bot{self._settings.bot_token}"

        max_attempts = self._settings.retry_max_attempts
        base = self._settings.retry_base_seconds
        cap = self._settings.retry_cap_seconds

        for attempt in range(max_attempts):
            try:
                if is_doc:
                    data: dict[str, Any] = {
                        "chat_id": self._settings.chat_id,
                        "parse_mode": "HTML",
                    }
                    if payload.text:
                        data["caption"] = payload.text[:1024]
                    if payload.topic_id is not None:
                        data["message_thread_id"] = payload.topic_id
                    resp = await client.post(
                        f"{base_url}/sendDocument",
                        data=data,
                        files={
                            "document": (
                                payload.attachment_filename or "log.txt",
                                payload.attachment or b"",
                                "text/plain",
                            )
                        },
                    )
                else:
                    body: dict[str, Any] = {
                        "chat_id": self._settings.chat_id,
                        "text": payload.text,
                        "parse_mode": payload.parse_mode or self._settings.parse_mode,
                    }
                    if payload.topic_id is not None:
                        body["message_thread_id"] = payload.topic_id
                    resp = await client.post(f"{base_url}/sendMessage", json=body)
            except httpx.RequestError as e:
                self.last_error = str(e)
                if attempt == max_attempts - 1:
                    self.dropped_count += 1
                    internal_logger.warning("dropped after %d attempts: %s", max_attempts, e)
                    return
                await self._backoff(attempt, base, cap)
                continue

            if resp.status_code == 200:
                self.sent_count += 1
                self.last_send_at = datetime.now(UTC)
                return

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    await asyncio.sleep(float(retry_after))
                else:
                    await self._backoff(attempt, base, cap)
                continue

            if 500 <= resp.status_code < 600:
                self.last_error = f"HTTP {resp.status_code}"
                if attempt == max_attempts - 1:
                    self.dropped_count += 1
                    internal_logger.warning(
                        "dropped after %d attempts: HTTP %d", max_attempts, resp.status_code
                    )
                    return
                await self._backoff(attempt, base, cap)
                continue

            # 4xx (not 429) — don't retry
            self.dropped_count += 1
            self.last_error = f"HTTP {resp.status_code}: {resp.text[:100]}"
            internal_logger.warning("dropped (no retry): HTTP %d", resp.status_code)
            return

        self.dropped_count += 1

    @staticmethod
    async def _backoff(attempt: int, base: float, cap: float) -> None:
        delay = min(base * (2**attempt), cap)
        jitter = delay * 0.2 * (random.random() * 2 - 1)  # noqa: S311
        await asyncio.sleep(delay + jitter)

    def submit(self, payload: SendPayload) -> None:
        """Submit a payload for async delivery. Non-blocking."""
        if self._loop is None or self._queue is None:
            return

        def _enqueue() -> None:
            try:
                self._queue.put_nowait(payload)  # type: ignore[union-attr]
            except asyncio.QueueFull:
                # Drop oldest
                try:
                    self._queue.get_nowait()  # type: ignore[union-attr]
                    self._queue.task_done()  # type: ignore[union-attr]
                except asyncio.QueueEmpty:
                    pass
                self.dropped_count += 1
                try:
                    self._queue.put_nowait(payload)  # type: ignore[union-attr]
                except asyncio.QueueFull:
                    pass

        self._loop.call_soon_threadsafe(_enqueue)

    def flush(self, timeout: float = 5.0) -> bool:
        """Wait for the queue to drain."""
        if self._loop is None or self._queue is None:
            return True
        future = asyncio.run_coroutine_threadsafe(self._queue.join(), self._loop)
        try:
            future.result(timeout=timeout)
            return True
        except (TimeoutError, Exception):
            return False

    def shutdown(self) -> None:
        """Flush remaining items and stop the worker loop."""
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self.flush(timeout=2.0)
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
