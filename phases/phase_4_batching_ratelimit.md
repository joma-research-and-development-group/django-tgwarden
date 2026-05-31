# Phase 4 — Batching + rate limiting

| | |
|---|---|
| **Slug** | `batching-ratelimit` |
| **Branch** | `phase/4-batching-ratelimit` |
| **Prerequisites** | Phase 3 merged |
| **Credentials needed** | same as Phase 3 |
| **Estimated size** | medium–large |

---

## 1. Goal

Coalesce many `LogRecord`s per topic into one Telegram message, and respect Telegram's API rate limits via a token-bucket scheduler. After this phase the package can sustain thousands of logs/minute without 429 floods.

## 2. Why this phase

Telegram limits per-bot to ~30 messages/sec globally and ~20 messages/min/group. At your peak target (50 logs/sec) a 1:1 record→message mapping is impossible. The fix is to combine many records into one message at flush time, and to gate sends through a token bucket so the bot never spikes above the allowed rate.

## 3. Architecture impact

```
worker queue ─► Demultiplexer ─► per-topic Batcher ─► flush trigger ─┐
                                                                     ▼
                                                       global TokenBucket (30 msg/sec)
                                                                     │
                                                                     ▼
                                                       per-chat TokenBucket (20 msg/min)
                                                                     │
                                                                     ▼
                                                              client.send_message
```

New abstractions:

- `Batcher` (per topic_id) with three flush triggers: count, bytes, time.
- `TokenBucket` (asyncio-aware).
- A `Scheduler` inside the worker that wires demux → batchers → buckets → client.

## 4. Deliverables

### 4.1 `src/tgwarden/batcher.py`

```python
@dataclass
class BatchEntry:
    text: str          # already HTML-formatted single record
    bytes_len: int

class Batcher:
    def __init__(self, *, max_records: int, max_bytes: int, max_seconds: float, on_flush: Callable[[str], Awaitable[None]]) -> None: ...
    def add(self, entry: BatchEntry) -> None: ...
    async def maybe_flush(self) -> None: ...
    async def force_flush(self) -> None: ...
```

Behavior:

- Maintains a buffer of `BatchEntry`s.
- Flush trigger: any of (`len(buffer) >= max_records`, sum of bytes_len ≥ `max_bytes`, oldest entry age ≥ `max_seconds`).
- Render: join entries with a separator `\n\n———\n\n`. Cap final text at 4096 chars; if overflow, split across multiple flush messages (must NOT silently truncate).
- `on_flush` is the awaitable that actually sends the rendered text.
- Time-based flush is driven by the loop's periodic tick (every 0.5s).

Defaults:

- `max_records = 20`
- `max_bytes = 3500`
- `max_seconds = 2.0`

### 4.2 `src/tgwarden/ratelimit.py`

```python
class TokenBucket:
    def __init__(self, *, capacity: float, refill_per_sec: float) -> None: ...
    async def acquire(self, tokens: float = 1.0) -> None: ...
```

- Standard token-bucket algorithm: `tokens = min(capacity, tokens + elapsed * refill_per_sec)`; if insufficient, async sleep `(needed - tokens) / refill_per_sec`.
- `asyncio.Lock` to keep `acquire` correct under concurrency.

Two buckets in the worker:

- `global_bucket = TokenBucket(capacity=30, refill_per_sec=30)` — 30 msg/sec across the whole bot.
- `per_chat_bucket = TokenBucket(capacity=20, refill_per_sec=20/60)` — 20 msg/min per supergroup.

Both must be acquired before each `send_message` / `send_document` call.

### 4.3 `src/tgwarden/transports/async_worker.py` (modify)

- The consumer loop changes shape:
  - Pull a `SendPayload` from queue.
  - **If `payload.attachment is not None`**: skip batching, send as a document (after acquiring tokens). Documents are not batched.
  - **Else**: route to `batchers[payload.topic_id]` (lazy-created). Call `batcher.add(...)` then `await batcher.maybe_flush()`.
- Add a periodic ticker coroutine: every 0.5s, `for b in batchers.values(): await b.maybe_flush()` — guarantees time-based flush even when traffic stops.
- On `shutdown`, force-flush all batchers before stopping the loop.

### 4.4 `src/tgwarden/conf.py` (modify)

Add fields with defaults:

- `batch_max_records: int = 20`
- `batch_max_bytes: int = 3500`
- `batch_flush_seconds: float = 2.0`
- `rate_limit_global_per_sec: float = 30.0`
- `rate_limit_per_chat_per_min: float = 20.0`

These are user-tunable; the defaults are conservative for Telegram's published limits.

### 4.5 Stats (extend)

- `batch_count_sent: int`
- `batch_count_split: int` (when a single batch had to be split because the rendered text exceeded 4096)
- `rate_limited_total_seconds: float` (cumulative time spent waiting on tokens)

## 5. Test plan

| Test file | Test functions |
|---|---|
| `tests/test_batcher.py` | `test_flush_on_count`, `test_flush_on_bytes`, `test_flush_on_time`, `test_force_flush_partial`, `test_split_when_render_exceeds_4096`, `test_separator_format` |
| `tests/test_ratelimit.py` | `test_initial_full_bucket`, `test_acquire_blocks_when_empty`, `test_refill_over_time`, `test_concurrent_acquires_serialize_correctly` |
| `tests/test_async_worker_batched.py` | `test_burst_of_500_uses_batching` (count batches sent vs records submitted), `test_documents_are_not_batched`, `test_429_does_not_double_count_tokens`, `test_periodic_ticker_flushes_idle_batches` |

Coverage: ≥ 90% on `batcher.py` and `ratelimit.py`.

## 6. Acceptance criteria

- [ ] All earlier gates green.
- [ ] Test: 5000 records submitted in 10 seconds → at the configured rate, ≥ 95% delivered without HTTP 429s in the respx mock (which simulates Telegram's limits).
- [ ] No record loss except on user-configured queue overflow.

## 7. Verification scenario (testbed)

### 7.1 Run a real burst

```bash
cd /projects/sandbox/tgwarden-testbed
source .venv/bin/activate
pip install -e ../django-tgwarden
python manage.py runserver 0.0.0.0:8000 &
sleep 2

# Submit 2000 records — should arrive batched, paced
curl -s "http://localhost:8000/burst/?n=2000"
echo "submitted; watch Telegram"
```

### 7.2 Expected behavior

- Telegram's **Error** topic receives **batched** messages, each containing up to ~20 records separated by a horizontal rule (`———`).
- Send pace is roughly one batch per ~2 seconds (the time-based flush) or one batch per 20 records, whichever first.
- No 429s in stderr (or only transient ones with successful retries).
- Final batch flushes within ~3 seconds of the last submission.

### 7.3 Stats sanity check

After the burst, in `python manage.py shell`:

```python
from tgwarden.transports import current_stats
print(current_stats())
# Expect approximately:
# {"sent": ~100, "batches": ~100, "dropped": 0, "queue": 0, "rate_limited_seconds": small}
```

(`current_stats()` is exposed in Phase 8 via the admin/health view; in Phase 4 it can live as an internal function used by tests.)

## 8. Risks & gotchas

- **Documents are not batched** — they are larger and Telegram requires separate multipart uploads. Don't try to merge them.
- **Token bucket math under jitter** — your refill_per_sec must equal capacity / period. For 20 msg/min, that's 0.333 msg/sec — very slow. Document this clearly so users understand why batching matters.
- **Splitting a batch** when rendered HTML exceeds 4096 chars: you must not split a single record across messages — split between records. If a single record's formatted text alone exceeds 4096, fall back to attachment (as in Phase 3).
- **Batch ordering across topics** — within a topic, FIFO is preserved. Across topics, no global ordering guarantee — that's intentional and matches user expectation (each topic has its own narrative).
- **Time-based flush during quiet periods** — the periodic ticker must not busy-spin; use `asyncio.sleep(0.5)`.
- **`Retry-After`** values on 429 should be respected even if they exceed the bucket's refill estimate.

## 9. Definition of Done

All AGENTS.md §6 boxes plus:

- [ ] Verification confirmed batched delivery in Telegram (paste sample batch in PR).
- [ ] Stats output captured in PR body.
- [ ] `phases/README.md` flipped to ✅ for Phase 4.
- [ ] CHANGELOG updated.
