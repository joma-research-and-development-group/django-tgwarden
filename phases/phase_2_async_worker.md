# Phase 2 — Async worker (non-blocking transport)

| | |
|---|---|
| **Slug** | `async-worker` |
| **Branch** | `phase/2-async-worker` |
| **Prerequisites** | Phase 1 merged |
| **Credentials needed** | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| **Estimated size** | medium |

---

## 1. Goal

Logging never blocks the request cycle. A daemon thread runs an asyncio event loop that drains a bounded queue, sends via `httpx.AsyncClient`, retries on 429/5xx with exponential backoff, and flushes pending records on process exit.

## 2. Why this phase

Phase 1's sync transport blocks every `logger.error()` call for as long as Telegram takes (~200 ms on a good day, **forever** if Telegram is down). At your target volume of thousands of logs per minute, sync is a denial-of-service against your own app.

## 3. Architecture impact

```
LogRecord ──► Handler.emit ──► [non-blocking submit] ──► Queue ──► Worker thread
                                                                     │
                                                          asyncio loop drains
                                                                     │
                                                                     ▼
                                                            httpx.AsyncClient (with retry)
                                                                     │
                                                                     ▼
                                                              Telegram Bot API
```

New abstractions:

- A `Transport` protocol so handlers don't care which transport is wired up.
- Three transports: `sync` (Phase 1, kept as dev fallback), `async_worker` (this phase, default), `celery` (Phase 7).
- An internal stderr-only logger (`tgwarden._internal.log`) used by the worker so its own diagnostics never recurse back into Telegram.

## 4. Deliverables

### 4.1 `src/tgwarden/transports/__init__.py`

- `def build_transport(settings) -> Transport` — factory that returns the right transport based on `settings.transport`.
- Exports `Transport` protocol.

### 4.2 `src/tgwarden/transports/base.py`

```python
class Transport(Protocol):
    def submit(self, payload: SendPayload) -> None: ...
    def flush(self, timeout: float = 5.0) -> bool: ...
    def shutdown(self) -> None: ...
```

`SendPayload` is a small frozen dataclass: `text`, `topic_id`, `parse_mode`, `as_document` (bool, set by Phase 3 long-message overflow).

### 4.3 `src/tgwarden/transports/sync_.py`

- `class SyncTransport(Transport)` — straight wrapper around `TelegramClient.send_message`.
- `submit` is blocking. `flush` and `shutdown` are no-ops returning `True`.

### 4.4 `src/tgwarden/transports/async_worker.py`

The heart of this phase.

- `class AsyncWorkerTransport(Transport)`:
  - On `__init__`, spawns a single daemon `threading.Thread` named `tgwarden-worker`.
  - The thread creates a fresh `asyncio.new_event_loop()` and runs forever.
  - The loop hosts:
    - `asyncio.Queue(maxsize=settings.queue_max_size)` (default 10_000).
    - One persistent `httpx.AsyncClient` (timeout from settings).
    - A long-running consumer coroutine.
  - `submit(payload)` is called from any thread; it does `loop.call_soon_threadsafe(queue.put_nowait, payload)`.
  - **Queue overflow policy:** if `put_nowait` raises `QueueFull`, drop the **oldest** record (`queue.get_nowait()`) then retry. Increment `dropped_count`. Once per second, write `f"[tgwarden] dropped N records due to queue overflow"` to stderr.
  - `flush(timeout)` — waits up to `timeout` seconds for the queue to drain (`asyncio.run_coroutine_threadsafe(queue.join(), loop)`).
  - `shutdown()` — best-effort: `flush(2.0)`, then `loop.call_soon_threadsafe(loop.stop)`.
  - Registered with `atexit.register(self.shutdown)`.

- **Retry policy** (inside the consumer coroutine):
  - HTTP 429 → read `Retry-After` header if present, else exponential backoff base 0.5s, cap 30s, jitter ±20%.
  - HTTP 5xx → exponential backoff base 0.5s, cap 30s, jitter ±20%.
  - HTTP 4xx (other than 429) → log to stderr once, drop record (no retry).
  - Network errors (`httpx.RequestError`) → exponential backoff like 5xx, max 5 attempts.
  - After max attempts → drop, increment `dropped_count`.

- **Stats** (exposed for Phase 8):
  - `sent_count: int`
  - `dropped_count: int`
  - `last_send_at: datetime | None`
  - `last_error: str | None`
  - `queue_size: int` (read live from the queue)

### 4.5 `src/tgwarden/_internal/log.py`

- `internal_logger`: a `logging.Logger` named `tgwarden._internal` configured to write **only to `sys.stderr`** with `propagate=False` and `handlers=[StreamHandler(sys.stderr)]`. Used everywhere inside tgwarden's own code paths so we never recurse.

### 4.6 Modified files

- ✏️ **`src/tgwarden/handlers.py`**:
  - In `__init__`, call `build_transport(get_settings())` and hold a reference.
  - `emit` builds a `SendPayload` from the formatted record and calls `self.transport.submit(payload)`.
  - `close` calls `self.transport.shutdown()`.
- ✏️ **`src/tgwarden/conf.py`** — flip the default `transport` from `"sync"` to `"async_worker"`. Add fields:
  - `queue_max_size: int = 10_000`
  - `retry_max_attempts: int = 5`
  - `retry_base_seconds: float = 0.5`
  - `retry_cap_seconds: float = 30.0`

## 5. Test plan

| Test file | Test functions |
|---|---|
| `tests/test_async_worker.py` | `test_submit_is_non_blocking_under_load` (1000 submits in <100ms wall time), `test_records_eventually_sent` (with respx, count = submitted), `test_overflow_drops_oldest` (capacity=10, push=100 → 90 drops, last 10 sent), `test_retry_on_429`, `test_retry_on_5xx`, `test_no_retry_on_400`, `test_atexit_flushes_pending`, `test_shutdown_stops_thread` |
| `tests/test_transport_factory.py` | `test_build_transport_sync`, `test_build_transport_async_worker`, `test_unknown_transport_raises` |
| `tests/test_handler_async.py` | `test_handler_uses_async_transport_by_default`, `test_emit_does_not_block` |

Coverage targets: ≥ 90% on `transports/async_worker.py` and `transports/base.py`.

Test discipline: **no `time.sleep` in production code**. Tests may use `time.sleep` for ergonomics, but prefer `wait_for(predicate, timeout=...)` helpers so flaky CI doesn't bite.

## 6. Acceptance criteria

- [ ] `time` measurement: 1000 records submitted in < 100 ms wall time on CI runners.
- [ ] All retry paths covered with `respx` simulating sequenced responses.
- [ ] No regression on Phase 1 tests.
- [ ] `mypy --strict` clean (Protocol with `...` bodies type-checks correctly under mypy 1.x).

## 7. Verification scenario (testbed)

### 7.1 Add a burst view to `demo/views.py`

```python
import logging, time
from django.http import HttpResponse
logger = logging.getLogger("demo")

def burst(request):
    n = int(request.GET.get("n", 1000))
    t0 = time.perf_counter()
    for i in range(n):
        logger.error("burst message %d", i)
    return HttpResponse(f"submitted {n} in {(time.perf_counter()-t0)*1000:.1f}ms")
```

Wire `path("burst/", views.burst)` in `demo/urls.py`.

### 7.2 Run

```bash
cd /projects/sandbox/tgwarden-testbed
source .venv/bin/activate
pip install -e ../django-tgwarden
python manage.py runserver 0.0.0.0:8000 &
sleep 2

# Submit 1000 logs and time the response
curl -w "\nHTTP_TIME=%{time_total}s\n" "http://localhost:8000/burst/?n=1000"
# Expect: HTTP_TIME < 0.5s. The page body reports the submit-side time which should be < 100ms.

# Watch Telegram fill up over the next ~30s
# (Phase 4 will pace these properly; here some 429s/retries are expected.)

# Stress test — 5000 records
curl -w "\nHTTP_TIME=%{time_total}s\n" "http://localhost:8000/burst/?n=5000"

kill %1
```

### 7.3 Expected

- `HTTP_TIME` for `n=1000` is sub-second.
- Telegram receives "many" messages (exact count varies; some may be dropped due to 429s — that's OK, Phase 4 fixes that).
- The Django process never raises.
- Stderr shows occasional `[tgwarden] dropped N records due to queue overflow` only if the worker can't keep up — this is informational, not an error.
- After `Ctrl+C`, the server shuts down cleanly within a couple seconds (atexit flush succeeds or times out).

## 8. Risks & gotchas

- **Forking servers (gunicorn pre-fork).** Each worker process gets its own thread + queue. That's fine and intended. Document it.
- **`asyncio.run_coroutine_threadsafe`** must be used to cross the thread boundary safely — never directly await across threads.
- **Daemon thread + atexit** — the thread is a daemon so it doesn't block interpreter shutdown, but `atexit` runs before daemon-thread termination, giving us one chance to flush.
- **`httpx.AsyncClient` lifecycle** — created inside the loop, closed in shutdown. Don't construct it outside the loop.
- **Logging recursion.** Any error in the worker that goes through normal Python `logging` could route back into the same handler. Use `tgwarden._internal.log` only inside the worker.
- **gevent / eventlet monkey-patching** — out of scope. Document that users running gevent should choose the Celery transport.

## 9. Definition of Done

All AGENTS.md §6 boxes plus:

- [ ] Verification produced sub-100 ms response time for `n=1000`.
- [ ] Telegram received the expected (best-effort) messages — paste sample in PR.
- [ ] `phases/README.md` status flipped to ✅ for Phase 2.
- [ ] CHANGELOG updated under `[Unreleased]`.
