"""Non-blocking async worker transport for tgwarden with batching and rate limiting."""

from __future__ import annotations

import asyncio
import atexit
import random
import threading
from datetime import UTC, datetime
from typing import Any

import httpx

from tgwarden._internal import internal_logger
from tgwarden.batcher import BatchEntry, Batcher
from tgwarden.conf import TgwardenSettings
from tgwarden.ratelimit import TokenBucket
from tgwarden.transports.base import SendPayload


class AsyncWorkerTransport:
    """Non-blocking transport: daemon thread + asyncio loop + batching + rate limiting."""

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
        self._loop.run_until_complete(self._main())

    async def _main(self) -> None:
        async with httpx.AsyncClient(timeout=self._settings.request_timeout) as client:
            self._client = client
            self._global_bucket = TokenBucket(
                capacity=self._settings.rate_limit_global_per_sec,
                refill_per_sec=self._settings.rate_limit_global_per_sec,
            )
            self._chat_bucket = TokenBucket(
                capacity=self._settings.rate_limit_per_chat_per_min,
                refill_per_sec=self._settings.rate_limit_per_chat_per_min / 60.0,
            )
            self._batchers: dict[int | None, Batcher] = {}

            ticker = asyncio.ensure_future(self._ticker())
            try:
                await self._consumer()
            finally:
                ticker.cancel()
                for b in self._batchers.values():
                    await b.force_flush()

    async def _ticker(self) -> None:
        """Periodic flush for time-based batching."""
        while not self._shutdown_requested:
            await asyncio.sleep(0.5)
            for b in self._batchers.values():
                await b.maybe_flush()

    def _get_batcher(self, topic_id: int | None) -> Batcher:
        if topic_id not in self._batchers:

            async def on_flush(text: str) -> None:
                await self._rate_limited_send(text, topic_id=topic_id)

            self._batchers[topic_id] = Batcher(
                max_records=self._settings.batch_max_records,
                max_bytes=self._settings.batch_max_bytes,
                max_seconds=self._settings.batch_flush_seconds,
                on_flush=on_flush,
            )
        return self._batchers[topic_id]

    async def _consumer(self) -> None:
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

            if payload.attachment is not None:
                # Documents skip batching
                await self._rate_limited_send_document(payload)
            else:
                batcher = self._get_batcher(payload.topic_id)
                batcher.add(BatchEntry(text=payload.text))
                await batcher.maybe_flush()

            self._queue.task_done()  # type: ignore[union-attr]

            if self._shutdown_requested and self._queue.empty():  # type: ignore[union-attr]
                break

    async def _rate_limited_send(self, text: str, *, topic_id: int | None) -> None:
        await self._global_bucket.acquire()
        await self._chat_bucket.acquire()
        await self._send_message_with_retry(text, topic_id=topic_id)

    async def _rate_limited_send_document(self, payload: SendPayload) -> None:
        await self._global_bucket.acquire()
        await self._chat_bucket.acquire()
        await self._send_document_with_retry(payload)

    async def _send_message_with_retry(self, text: str, *, topic_id: int | None) -> None:
        base_url = f"{self._settings.api_base_url}/bot{self._settings.bot_token}"
        body: dict[str, Any] = {
            "chat_id": self._settings.chat_id,
            "text": text,
            "parse_mode": self._settings.parse_mode,
        }
        if topic_id is not None:
            body["message_thread_id"] = topic_id

        await self._retry_loop(f"{base_url}/sendMessage", json_body=body)

    async def _send_document_with_retry(self, payload: SendPayload) -> None:
        base_url = f"{self._settings.api_base_url}/bot{self._settings.bot_token}"
        data: dict[str, Any] = {"chat_id": self._settings.chat_id, "parse_mode": "HTML"}
        if payload.text:
            data["caption"] = payload.text[:1024]
        if payload.topic_id is not None:
            data["message_thread_id"] = payload.topic_id

        files = {
            "document": (
                payload.attachment_filename or "log.txt",
                payload.attachment or b"",
                "text/plain",
            )
        }
        await self._retry_loop(f"{base_url}/sendDocument", data=data, files=files)

    async def _retry_loop(
        self,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> None:
        max_attempts = self._settings.retry_max_attempts
        base = self._settings.retry_base_seconds
        cap = self._settings.retry_cap_seconds

        for attempt in range(max_attempts):
            try:
                if json_body is not None:
                    resp = await self._client.post(url, json=json_body)
                else:
                    resp = await self._client.post(url, data=data, files=files)
            except httpx.RequestError as e:
                self.last_error = str(e)
                if attempt == max_attempts - 1:
                    self.dropped_count += 1
                    return
                await self._backoff(attempt, base, cap)
                continue

            if resp.status_code == 200:
                self.sent_count += 1
                self.last_send_at = datetime.now(UTC)
                return

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else None
                if wait:
                    await asyncio.sleep(wait)
                else:
                    await self._backoff(attempt, base, cap)
                continue

            if 500 <= resp.status_code < 600:
                self.last_error = f"HTTP {resp.status_code}"
                if attempt == max_attempts - 1:
                    self.dropped_count += 1
                    return
                await self._backoff(attempt, base, cap)
                continue

            # 4xx (not 429)
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
        """Wait for the queue to drain and batchers to flush."""
        if self._loop is None or self._queue is None:
            return True

        async def _drain() -> None:
            await self._queue.join()  # type: ignore[union-attr]
            for b in self._batchers.values():
                await b.force_flush()

        future = asyncio.run_coroutine_threadsafe(_drain(), self._loop)
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
        self.flush(timeout=3.0)
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
