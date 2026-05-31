# Phase 7 — Celery transport (optional, opt-in)

| | |
|---|---|
| **Slug** | `celery-transport` |
| **Branch** | `phase/7-celery-transport` |
| **Prerequisites** | Phase 6 merged |
| **Credentials needed** | + `REDIS_URL` (or any Celery broker) |
| **Estimated size** | small–medium |

---

## 1. Goal

For users who already run Celery, offload sends to a Celery task instead of the in-process worker. This phase is **strictly opt-in**: existing setups keep using `async_worker`. Activated only when `TGWARDEN["TRANSPORT"] = "celery"`.

## 2. Why this phase

Two reasons:

1. Some teams centralize all background work in Celery and want tgwarden to participate in their existing observability (Flower dashboards, Celery routing, retry policies).
2. Pre-fork servers (gunicorn) duplicate the in-process worker thread per process. With Celery, sends happen in a single dedicated worker process, simpler to reason about at very large scale.

## 3. Architecture impact

```
LogRecord ──► Handler.emit ──► CeleryTransport.submit
                                       │
                                       ▼
                            tgwarden.tasks.send_to_telegram.delay(payload_dict)
                                       │
                                       ▼
                              Celery worker picks up
                                       │
                                       ▼
                              TelegramClient.send_message / send_document
```

Celery brings its own retry mechanism, so the transport hands off retry to Celery rather than implementing it locally.

## 4. Deliverables

### 4.1 `src/tgwarden/transports/celery_.py`

```python
def _ensure_celery_installed() -> None:
    try:
        import celery  # noqa: F401
    except ImportError as exc:
        raise ConfigurationError(
            "TRANSPORT=celery requires the 'celery' extra: pip install django-tgwarden[celery]"
        ) from exc

class CeleryTransport(Transport):
    def __init__(self, settings: TgwardenSettings) -> None:
        _ensure_celery_installed()
        ...
    def submit(self, payload: SendPayload) -> None:
        from tgwarden.tasks import send_to_telegram
        send_to_telegram.apply_async(args=[payload.to_dict()], retry=True)
    def flush(self, timeout: float = 5.0) -> bool: return True   # delegated to Celery
    def shutdown(self) -> None: ...                              # no-op
```

### 4.2 `src/tgwarden/tasks.py`

```python
from celery import shared_task
from tgwarden.client import TelegramClient
from tgwarden.conf import get_settings

@shared_task(
    bind=True,
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_backoff_max=30,
    retry_jitter=True,
    max_retries=5,
    name="tgwarden.send_to_telegram",
)
def send_to_telegram(self, payload_dict: dict) -> None:
    settings = get_settings()
    client = TelegramClient(settings)
    payload = SendPayload.from_dict(payload_dict)
    if payload.attachment:
        client.send_document(...)
    else:
        client.send_message(...)
```

### 4.3 `src/tgwarden/transports/__init__.py` (modify)

```python
def build_transport(settings: TgwardenSettings) -> Transport:
    match settings.transport:
        case "sync":         return SyncTransport(settings)
        case "async_worker": return AsyncWorkerTransport(settings)
        case "celery":       return CeleryTransport(settings)
        case other:          raise ConfigurationError(f"unknown TRANSPORT: {other!r}")
```

### 4.4 `pyproject.toml` (modify)

```toml
[project.optional-dependencies]
celery = ["celery>=5.3"]
dev    = [..., "celery>=5.3"]   # so tests can import celery
```

### 4.5 `examples/celery_setup.md`

A short recipe document with copy-pasteable code:

- How to add tgwarden's task to Celery's `imports`.
- A reminder to restart the Celery worker after each `pip install -e ../django-tgwarden`.
- Recommended Celery routing (`task_routes = {"tgwarden.send_to_telegram": {"queue": "tgwarden"}}`) so the load is isolated.
- Note that batching/dedup (Phases 4–5) **do not apply** in Celery mode — each record becomes its own task.

> **Design decision:** Celery mode skips batching and dedup intentionally; if you need those, use `async_worker`. Celery is for users who prefer simplicity over throughput optimization.

### 4.6 `src/tgwarden/conf.py` (modify)

- Already accepts `transport = "celery"`. Add a runtime hint when this transport is selected, suggesting `auto_capture_exceptions=True` works the same way.

## 5. Public API additions

- `tgwarden.transports.CeleryTransport`
- `tgwarden.tasks.send_to_telegram`

## 6. Test plan

| Test file | Test functions |
|---|---|
| `tests/test_celery_transport.py` | `test_submit_enqueues_task` (with `CELERY_TASK_ALWAYS_EAGER=True` + respx), `test_task_calls_send_message`, `test_task_calls_send_document_when_attachment`, `test_task_retries_on_httpx_error` |
| `tests/test_celery_optional_dep.py` | `test_celery_transport_raises_helpful_error_when_celery_missing` (use `unittest.mock.patch` to simulate ImportError) |

Coverage targets: ≥ 90% on `transports/celery_.py` and `tasks.py`.

## 7. Acceptance criteria

- [ ] Without `[celery]` extra installed, importing `tgwarden` still works; selecting `TRANSPORT=celery` raises a clear `ConfigurationError`.
- [ ] With `[celery]` and `CELERY_TASK_ALWAYS_EAGER=True`, tests run end-to-end.
- [ ] No regression on Phases 0–6.

## 8. Verification scenario (testbed)

### 8.1 Install extras

```bash
cd /projects/sandbox/tgwarden-testbed
source .venv/bin/activate
pip install -e ../django-tgwarden[celery]
pip install redis
```

### 8.2 Add Celery to testbed

`testbed/celery.py`:

```python
import os
from celery import Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testbed.settings")
app = Celery("testbed")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

`testbed/__init__.py`:

```python
from .celery import app as celery_app
__all__ = ("celery_app",)
```

`testbed/settings.py`:

```python
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_TASK_ALWAYS_EAGER = False
CELERY_IMPORTS = ("tgwarden.tasks",)
TGWARDEN["TRANSPORT"] = "celery"
```

### 8.3 Run

In one terminal:

```bash
docker run -p 6379:6379 redis:7-alpine    # or use any redis you have
```

In another:

```bash
celery -A testbed worker -l info
```

In a third:

```bash
python manage.py runserver 0.0.0.0:8000 &
sleep 2
curl -s http://localhost:8000/levels/        # Phase 3 view
```

### 8.4 Expected

- Celery worker logs `Received task: tgwarden.send_to_telegram(...)` for each level.
- Telegram receives one message per level in the right topic (no batching, by design).
- Killing the Celery worker mid-burst causes pending tasks to remain in Redis; restart and they deliver — proving durability.

## 9. Risks & gotchas

- **Pickling `SendPayload`** — convert to a plain dict before passing to `apply_async`. Don't pickle the dataclass.
- **Settings access in the task** — the task runs in a different process. `get_settings()` must work there too. Make sure `DJANGO_SETTINGS_MODULE` is configured for the Celery worker.
- **No batching, no dedup** in Celery mode. Document loudly.
- **Auto-discover** — recommend `app.autodiscover_tasks()` plus including `"tgwarden.tasks"` in `CELERY_IMPORTS` for explicitness.
- **Eager mode in tests** — set `CELERY_TASK_ALWAYS_EAGER=True` only inside `tests/conftest.py` for the celery test module; don't pollute other tests.
- **Test DB vs Celery worker DB** — out of scope; tgwarden tasks are stateless.

## 10. Definition of Done

All AGENTS.md §6 boxes plus:

- [ ] Verification confirmed task ran in Celery worker logs (paste task log line in PR).
- [ ] Verification confirmed Telegram received messages (paste sample).
- [ ] `phases/README.md` flipped to ✅ for Phase 7.
- [ ] CHANGELOG updated.
