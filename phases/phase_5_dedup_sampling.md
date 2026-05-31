# Phase 5 — Deduplication + sampling

| | |
|---|---|
| **Slug** | `dedup-sampling` |
| **Branch** | `phase/5-dedup-sampling` |
| **Prerequisites** | Phase 4 merged |
| **Credentials needed** | same as Phase 4 |
| **Estimated size** | medium |

---

## 1. Goal

Identical errors collapse to "× N more in T seconds" follow-ups instead of spamming the topic. Optionally, noisy levels (DEBUG, INFO) are sampled to a configurable fraction.

## 2. Why this phase

Even with batching, a tight loop hitting the same exception 10 000 times produces unreadable noise. Sentry-style fingerprint-based dedup turns that into one detailed message + a counter follow-up. Sampling cuts INFO/DEBUG floods at the source.

## 3. Architecture impact

```
LogRecord ──► (optional SamplingFilter) ──► Handler.emit ──► DedupGate ──► Transport
```

- `DedupGate` lives **inside** the handler, before the transport. It maintains a rolling-window keyed by record fingerprint.
- `SamplingFilter` is a `logging.Filter` users opt into via the standard Django `LOGGING` config (`"filters": [...]`).
- The follow-up summary message is emitted by the gate itself when a window closes.

## 4. Deliverables

### 4.1 `src/tgwarden/dedup.py`

```python
@dataclass(frozen=True, slots=True)
class Fingerprint:
    level: str
    logger_name: str
    message_template: str
    exc_type: str | None
    exc_first_frame: str | None  # "module/file.py:lineno"

class DedupGate:
    def __init__(self, *, window_seconds: float, on_first: Callable[[LogRecord], None], on_followup: Callable[[Fingerprint, int], None]) -> None: ...
    def submit(self, record: LogRecord) -> bool:
        """
        Returns True if the record should be emitted now.
        First occurrence in window → True; subsequent → False (counter incremented).
        On window close, on_followup is called with the count.
        """
```

Algorithm:

- Compute fingerprint from `record.levelname`, `record.name`, `record.msg` (the **template**, not the formatted message), `record.exc_info[0].__name__` if any, and the first traceback frame.
- Maintain `dict[Fingerprint, _State]` where `_State = (first_seen_ts: float, count: int, last_seen_ts: float)`.
- On submit:
  - If fingerprint not in dict → add with count=1, schedule a window-close callback at `now + window_seconds`, return `True`.
  - Else → increment count, update `last_seen_ts`, return `False`.
- Window-close callback:
  - Pop the state. If `count > 1`, call `on_followup(fingerprint, count - 1)`.
- Use `loop.call_later(window_seconds, ...)` if running in a loop, else a small `threading.Timer` (handler is sync at this layer).

### 4.2 `src/tgwarden/filters.py`

```python
class SamplingFilter(logging.Filter):
    """
    Probabilistic sampling per-level. Defaults preserve everything (1.0).

    Example LOGGING config:
        "filters": {
            "sample": {"()": "tgwarden.filters.SamplingFilter", "rates": {"DEBUG": 0.05, "INFO": 0.1}},
        },
    """
    def __init__(self, *, rates: dict[str, float] | None = None) -> None: ...
    def filter(self, record: logging.LogRecord) -> bool: ...
```

Implementation: `random.random() < self.rates.get(record.levelname, 1.0)`.

### 4.3 `src/tgwarden/handlers.py` (modify)

- `__init__` constructs a `DedupGate` if `settings.dedup_window_seconds > 0`.
- In `emit`:
  - If gate present, call `gate.submit(record)`. If returns `False`, skip. If `True`, proceed normally.
- The gate's `on_first` callback is the existing emit path.
- The gate's `on_followup` callback formats a small message (`<i>… repeated × {count} more in last {N}s</i>`) and submits it through the transport with the same `topic_id` as the original.

### 4.4 `src/tgwarden/conf.py` (modify)

- `dedup_window_seconds: float = 60.0` — set to 0 to disable.
- `sampling_rates: dict[str, float] = field(default_factory=dict)` — used by users wiring `SamplingFilter` programmatically (optional).

## 5. Test plan

| Test file | Test functions |
|---|---|
| `tests/test_dedup.py` | `test_first_occurrence_emits`, `test_subsequent_occurrences_suppressed`, `test_window_close_emits_followup_with_count`, `test_different_fingerprints_not_deduped`, `test_different_exc_frames_not_deduped`, `test_disabled_when_window_zero` |
| `tests/test_sampling.py` | `test_default_rates_pass_all`, `test_per_level_rate`, `test_unknown_level_passes`, `test_statistical_distribution_within_tolerance` (10000 records → expected count ± 10%) |
| `tests/test_handler_with_dedup.py` | `test_handler_collapses_burst_into_one_send_plus_followup` |

Coverage: ≥ 90% on `dedup.py` and `filters.py`.

## 6. Acceptance criteria

- [ ] All earlier gates green.
- [ ] Burst of 1000 identical errors produces exactly **1** primary message + **1** follow-up summary in respx-mocked tests.
- [ ] Sampling test produces ~100 keeps from 1000 records at rate 0.1 (within ±20%).

## 7. Verification scenario (testbed)

### 7.1 Add demo views

`demo/views.py`:

```python
def repeat(request):
    log = logging.getLogger("demo.repeat")
    for i in range(500):
        try:
            raise ValueError("oops")
        except ValueError:
            log.exception("repeated failure %d", i)
    return HttpResponse("ok")

def info_flood(request):
    log = logging.getLogger("demo.info")
    for _ in range(1000):
        log.info("noisy info")
    return HttpResponse("ok")
```

### 7.2 Configure sampling for INFO

In `testbed/settings.py`:

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "sample": {"()": "tgwarden.filters.SamplingFilter", "rates": {"INFO": 0.1, "DEBUG": 0.0}},
    },
    "handlers": {
        "telegram": {
            "class": "tgwarden.handlers.TelegramHandler",
            "level": "DEBUG",
            "filters": ["sample"],
        },
    },
    "root": {"handlers": ["telegram"], "level": "DEBUG"},
}

TGWARDEN = {
    ...,
    "DEDUP_WINDOW_SECONDS": 60.0,
}
```

### 7.3 Run and observe

```bash
curl -s http://localhost:8000/repeat/    # 500 identical errors
curl -s http://localhost:8000/info_flood/   # 1000 INFOs at 10% sample
```

### 7.4 Expected Telegram output

- **Error** topic: ONE primary message with the traceback for `ValueError("oops")`. After ~60 seconds, ONE follow-up: `… repeated × 499 more in last 60s`.
- **Info** topic: ~100 (±30) records arrive (10% sample). They batch normally.
- **Debug** topic: nothing (rate 0).

## 8. Risks & gotchas

- **Fingerprint must use the message template, not the formatted message** — otherwise `"failed user 1"`, `"failed user 2"`, … all look different. Read `record.msg` (template) and ignore `record.args` for fingerprinting.
- **Memory leak risk**: stale entries in the dedup map. Always schedule a window-close callback that removes the entry.
- **Threading vs asyncio**: the handler runs in the calling thread, but the worker is in another. Be explicit about which side schedules the close timer; safest is a `threading.Timer` keyed on a `Lock`. The follow-up payload then enters the worker queue normally.
- **Sampling and dedup interact**: the user might dedup on an already-sampled stream. Document order: SamplingFilter applies first (Python logging filter chain), then the handler's DedupGate.
- **Statistical tests are flaky** if tolerance is too tight. Use ±20% bounds or seed `random` in tests.

## 9. Definition of Done

All AGENTS.md §6 boxes plus:

- [ ] Verification produced 1 primary + 1 follow-up for `/repeat/` (paste both in PR).
- [ ] `/info_flood/` produced ~100 INFOs (paste a sample window from Telegram).
- [ ] `phases/README.md` flipped to ✅ for Phase 5.
- [ ] CHANGELOG updated.
