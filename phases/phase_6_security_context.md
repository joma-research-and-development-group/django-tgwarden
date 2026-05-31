# Phase 6 — Security (PII scrub) + request context middleware

| | |
|---|---|
| **Slug** | `security-context` |
| **Branch** | `phase/6-security-context` |
| **Prerequisites** | Phase 5 merged |
| **Credentials needed** | same as Phase 5 |
| **Estimated size** | medium |

---

## 1. Goal

1. Sensitive values (passwords, tokens, cookies, credit-card-shaped strings) are redacted before reaching Telegram.
2. Every log record emitted during a Django request automatically carries `request.path`, `request.method`, `user_id`, and `client_ip`.
3. Unhandled exceptions in views become CRITICAL records with the full request context attached.

## 2. Why this phase

A Telegram chat is more visible than your app logs — you don't want a token leak to land there. And a traceback without `path=/api/foo, user=42` is half-useful at 3 AM. This phase makes the package safe for production by default.

## 3. Architecture impact

```
incoming request ──► TgwardenContextMiddleware (sets contextvars)
        │
        ▼
     view code calls logger.error(...)
        │
        ▼
     LogRecord ──► ContextFilter (injects request fields)
                ──► ScrubFilter (redacts PII)
                ──► DedupGate (Phase 5)
                ──► Transport (Phase 2/4)
```

## 4. Deliverables

### 4.1 `src/tgwarden/middleware.py`

```python
_request_ctx: ContextVar[RequestContext | None] = ContextVar("tgwarden_request_ctx", default=None)

@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str
    method: str
    path: str
    user_id: int | str | None
    client_ip: str | None

class TgwardenContextMiddleware:
    """
    Binds a RequestContext into a ContextVar for the lifetime of a request.

    Optionally captures unhandled exceptions and re-emits them as CRITICAL
    log records so they reach the Telegram error/critical topic with full context.
    """
    def __init__(self, get_response): ...
    def __call__(self, request): ...
    def process_exception(self, request, exception): ...

def get_current_context() -> RequestContext | None: ...
```

Behavior:

- On entry, generate a `request_id` (uuid4 short form), resolve `user_id` (anonymous → `None`), determine client IP from `X-Forwarded-For` (first hop) or `REMOTE_ADDR`, set the ContextVar.
- On exit (any path, including exceptions), reset the ContextVar.
- `process_exception` logs at CRITICAL with `exc_info=exception` and the current context. Re-raises so Django's normal 500 handling proceeds.

### 4.2 `src/tgwarden/filters.py` (extend)

Add **two** logging filters:

```python
class ContextFilter(logging.Filter):
    """Injects request fields into the LogRecord as attributes."""
    def filter(self, record): ...

class ScrubFilter(logging.Filter):
    """
    Redacts case-insensitive matches on configured keys, plus regex patterns
    (credit-card-shaped strings by default).
    """
    DEFAULT_KEYS = ("password", "token", "authorization", "cookie", "secret", "api_key", "x-api-key")
    DEFAULT_PATTERNS = (
        r"\b(?:\d[ -]*?){13,16}\b",   # credit-card-ish
    )
    def __init__(self, *, keys: Iterable[str] | None = None, patterns: Iterable[str] | None = None, replacement: str = "***") -> None: ...
    def filter(self, record): ...
```

Scrub algorithm:

- Walk `record.msg` (template) and `record.args` if it's a dict.
- For each `key` in the redaction set, replace `key=value` (case-insensitive, allow `:`, `=`, or `=>` separators) with `key=***`.
- Then apply regex patterns to the final formatted message.
- Apply to `record.exc_text` too (formatted traceback string).

Implementation note: don't mutate `record.msg` in-place if `record.args` is a tuple — operate on the result of `record.getMessage()` and store back as `record.msg = scrubbed; record.args = ()`.

### 4.3 `src/tgwarden/formatters.py` (modify)

Insert an optional **context block** between header and body when `record` carries the injected attrs:

```
🔥 CRITICAL · demo.views · 2026-…
<i>req#abc123 · GET /boom · user=42 · ip=203.0.113.5</i>

ValueError: kaboom
<pre><code class="language-python">…</code></pre>
```

### 4.4 `src/tgwarden/conf.py` (modify)

- `scrub_keys: tuple[str, ...] = DEFAULT_KEYS`
- `scrub_patterns: tuple[str, ...] = DEFAULT_PATTERNS`
- `auto_capture_exceptions: bool = True` — controls whether `TgwardenContextMiddleware` re-emits the unhandled exception as CRITICAL.

### 4.5 `src/tgwarden/__init__.py` (modify)

Export `TgwardenContextMiddleware`, `get_current_context`, `ContextFilter`, `ScrubFilter` for users to wire up.

## 5. Public API additions

- `tgwarden.middleware.TgwardenContextMiddleware`
- `tgwarden.middleware.RequestContext` (read-only dataclass)
- `tgwarden.middleware.get_current_context`
- `tgwarden.filters.ContextFilter`
- `tgwarden.filters.ScrubFilter`

## 6. Test plan

| Test file | Test functions |
|---|---|
| `tests/test_scrub_filter.py` | `test_scrubs_password_query_string`, `test_scrubs_authorization_header_log`, `test_scrubs_credit_card_in_message`, `test_custom_keys_and_replacement`, `test_does_not_scrub_unrelated_text`, `test_idempotent_when_called_twice` |
| `tests/test_context_filter.py` | `test_filter_injects_when_context_present`, `test_filter_no_op_when_context_absent` |
| `tests/test_middleware.py` | `test_middleware_sets_and_clears_contextvar`, `test_user_id_resolution_anonymous`, `test_user_id_resolution_authenticated`, `test_x_forwarded_for_first_hop`, `test_unhandled_exception_logged_critical_with_context` |
| `tests/test_formatter_context_block.py` | `test_context_block_rendered_when_record_has_attrs`, `test_context_block_omitted_otherwise` |

Coverage: ≥ 90% on `middleware.py` and `filters.py`.

## 7. Acceptance criteria

- [ ] All earlier gates green.
- [ ] No log line in any test fixture leaks the literal string `password=hunter2` after scrubbing.
- [ ] Middleware resets ContextVar even on exception paths.

## 8. Verification scenario (testbed)

### 8.1 Wire middleware

In `testbed/settings.py`:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "tgwarden.middleware.TgwardenContextMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    ...,
]

LOGGING = {
    "version": 1,
    "filters": {
        "ctx":    {"()": "tgwarden.filters.ContextFilter"},
        "scrub":  {"()": "tgwarden.filters.ScrubFilter"},
    },
    "handlers": {
        "telegram": {
            "class": "tgwarden.handlers.TelegramHandler",
            "level": "DEBUG",
            "filters": ["ctx", "scrub"],
        },
    },
    "root": {"handlers": ["telegram"], "level": "INFO"},
}
```

### 8.2 Add demo views

```python
def login_demo(request):
    # logs the GET querystring including password
    logging.getLogger("demo.login").info("login attempt: %s", request.GET.urlencode())
    return HttpResponse("ok")

def boom_user(request):
    raise ValueError("kaboom for user")
```

### 8.3 Run and observe

```bash
curl -s "http://localhost:8000/login_demo/?username=alice&password=hunter2"
# Telegram Info topic should show: "login attempt: username=alice&password=***"

# Authenticate as user "alice" first (admin or test fixture), then:
curl -s -b cookies.txt http://localhost:8000/boom_user/ || true
# Telegram Critical topic shows ValueError traceback PLUS context block:
#    "req#... · GET /boom_user/ · user=alice · ip=127.0.0.1"
```

### 8.4 Expected Telegram output

- Info topic: a record with `password=***` (never `hunter2`).
- Critical topic: a record with full context block + traceback when `/boom_user/` 500s.

## 9. Risks & gotchas

- **Middleware order matters**. `TgwardenContextMiddleware` must run **after** `AuthenticationMiddleware` so `request.user` is populated; but it must **wrap** the view (`__call__`) so context is set before the view runs. The Django middleware factory pattern handles this correctly if registered after auth.
- **`X-Forwarded-For` parsing** must be done carefully — if the user is behind a load balancer, take the first hop; if they aren't, the header is attacker-controllable. Document this and let users opt out via `auto_capture_exceptions=False`.
- **Scrub false negatives** are inevitable; document that this is best-effort, not a guarantee. Recommend Sentry-style data-scrubbing for high-stakes apps.
- **Async views (Django 4.1+)**. ContextVar works correctly across `asgiref.sync.sync_to_async` and `async def` views. Test both.
- **`auto_capture_exceptions` double-logging**: Django's own `django.request` logger logs 500s by default. Make sure we don't duplicate. Use a flag on the record (`record.tgwarden_emitted = True`) to break recursion.

## 10. Definition of Done

All AGENTS.md §6 boxes plus:

- [ ] Verification confirmed scrubbing of `password=...` in Telegram (paste in PR).
- [ ] Verification confirmed context block on `/boom_user/` traceback (paste in PR).
- [ ] `phases/README.md` flipped to ✅ for Phase 6.
- [ ] CHANGELOG updated.
