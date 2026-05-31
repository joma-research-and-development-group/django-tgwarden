# Phase 1 — MVP handler (sync transport)

| | |
|---|---|
| **Slug** | `mvp-handler` |
| **Branch** | `phase/1-mvp-handler` |
| **Prerequisites** | Phase 0 merged |
| **Credentials needed** | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| **Estimated size** | medium |

---

## 1. Goal

Make a single `logger.error("hi")` call in the testbed produce a real message in your Telegram chat. End-to-end wiring proven; everything else is iteration.

The transport in this phase is **synchronous** — it blocks the request until Telegram responds. That's intentional. We replace it with a non-blocking worker in Phase 2.

## 2. Why this phase

Before optimizing (async, batching, dedup), we must prove the simplest possible path works: `LogRecord` → `Formatter` → `httpx.Client.post` → Telegram displays the message. Every later phase is a strict upgrade of one of those four steps.

## 3. Architecture impact

```
LogRecord ──► HTMLFormatter ──► TelegramHandler.emit ──► TelegramClient.send_message ──► Telegram Bot API
```

New public surface:

- `tgwarden.handlers.TelegramHandler` (logging.Handler subclass)
- `tgwarden.formatters.HTMLFormatter` (logging.Formatter subclass)
- `tgwarden.client.TelegramClient`
- `tgwarden.exceptions.{TgwardenError, ConfigurationError, TelegramAPIError}`
- `tgwarden.conf.TgwardenSettings` (frozen dataclass) + `get_settings()`
- Management command: `tgwarden_test`

## 4. Deliverables

### 4.1 `src/tgwarden/exceptions.py`

```python
class TgwardenError(Exception): ...
class ConfigurationError(TgwardenError): ...
class TelegramAPIError(TgwardenError):
    def __init__(self, *, status_code: int, body: str): ...
```

### 4.2 `src/tgwarden/conf.py`

- `@dataclass(frozen=True, slots=True) class TgwardenSettings`:
  - `bot_token: str` (required)
  - `chat_id: str` (required, accepts int or str; normalized to str)
  - `parse_mode: Literal["HTML", "MarkdownV2"] = "HTML"`
  - `transport: Literal["sync", "async_worker", "celery"] = "sync"` *(default flips to `"async_worker"` in Phase 2)*
  - `request_timeout: float = 5.0`
  - `api_base_url: str = "https://api.telegram.org"`
  - Other fields reserved for later phases (`topics`, `batch_*`, `dedup_*`, `scrub_keys`, `info_sample_rate`) included with safe defaults so we don't break the dataclass shape later.
- `def get_settings() -> TgwardenSettings`:
  - Reads `getattr(django.conf.settings, "TGWARDEN", None)`.
  - Raises `ConfigurationError` with a helpful message if missing or required keys absent.
  - Returns the dataclass.
  - Memoize via `functools.lru_cache` on a settings-fingerprint helper, *but* allow `clear_settings_cache()` for tests.

### 4.3 `src/tgwarden/client.py`

- `class TelegramClient`:
  - `__init__(self, settings: TgwardenSettings)` — builds an internal `httpx.Client(timeout=settings.request_timeout)`.
  - `send_message(self, text: str, *, topic_id: int | None = None, parse_mode: str | None = None) -> dict` — POST to `<api_base_url>/bot<token>/sendMessage` with payload `{chat_id, text, parse_mode, message_thread_id?}`. Returns the parsed JSON `result` on 2xx; raises `TelegramAPIError(status_code=r.status_code, body=r.text[:500])` on non-2xx.
  - `close(self) -> None` — closes the underlying httpx client.
  - Implements `__enter__` / `__exit__` for use as a context manager.
  - `topic_id` is accepted but unused unless set; we route per-level in Phase 3.

### 4.4 `src/tgwarden/formatters.py`

- `class HTMLFormatter(logging.Formatter)`:
  - `LEVEL_EMOJI = {"DEBUG": "🔵", "INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "🐛", "CRITICAL": "🔥"}`
  - `format(record: LogRecord) -> str` returns:
    ```
    {emoji} <b>{level}</b> · <code>{logger_name}</code> · {iso_timestamp}
    {html_escaped_message}

    [if record.exc_info]
    <pre><code class="language-python">{html_escaped_traceback}</code></pre>
    ```
  - Truncate to 4096 chars; if longer, append `…\n[truncated, see attachment in Phase 3]` and stop. (Document attachment is Phase 3.)
  - All variable parts pass through `html.escape(..., quote=True)`.

### 4.5 `src/tgwarden/handlers.py`

- `class TelegramHandler(logging.Handler)`:
  - `__init__(self, level: int = logging.NOTSET)` — auto-loads `get_settings()` lazily on first emit; defers actual client construction so import-time settings missing doesn't crash startup.
  - Default formatter = `HTMLFormatter()`.
  - `emit(self, record)`:
    - Try block wraps **everything**.
    - On exception, write a one-line summary to `sys.stderr` (`"[tgwarden] failed to send: ..."`) and call `self.handleError(record)`.
    - Never re-raise.
  - `close(self)` closes the underlying client.

### 4.6 `src/tgwarden/management/commands/tgwarden_test.py`

- `class Command(BaseCommand)`:
  - `help = "Send a test message via the configured TelegramHandler to verify wiring."`
  - `add_arguments(parser)` accepts `--level` (default `INFO`) and `--message` (default `"tgwarden test message"`).
  - `handle(*args, **opts)`:
    1. Loads settings via `get_settings()`.
    2. Builds a transient `TelegramHandler`, attaches to a child logger, emits the message at the requested level.
    3. Echoes a confirmation to stdout: `"Sent test message at INFO via tgwarden."`.

## 5. Public API surface (this phase)

```python
# tgwarden/__init__.py exports
from tgwarden.handlers import TelegramHandler
from tgwarden.formatters import HTMLFormatter
from tgwarden.exceptions import TgwardenError, ConfigurationError, TelegramAPIError
__all__ = ["TelegramHandler", "HTMLFormatter", "TgwardenError", "ConfigurationError", "TelegramAPIError", "__version__"]
```

## 6. Test plan

All HTTP calls mocked via `respx`. The Telegram API base URL is configurable in `TgwardenSettings.api_base_url`, which makes mocking trivial.

| Test file | Test functions |
|---|---|
| `tests/test_conf.py` | `test_get_settings_happy_path`, `test_missing_token_raises`, `test_missing_chat_id_raises`, `test_chat_id_int_normalized_to_str`, `test_settings_cache_clear` |
| `tests/test_formatters.py` | `test_basic_record_formatting`, `test_html_escapes_message`, `test_traceback_in_pre_block`, `test_truncates_at_4096`, `test_emoji_per_level` |
| `tests/test_client.py` | `test_send_message_payload`, `test_send_message_uses_topic_id`, `test_non_2xx_raises_telegram_api_error`, `test_timeout_propagates` |
| `tests/test_handler.py` | `test_emit_calls_client_with_formatted_text`, `test_emit_swallows_exceptions`, `test_emit_writes_to_stderr_on_failure`, `test_handler_lazy_settings_load` |
| `tests/test_management_command.py` | `test_tgwarden_test_command_emits_message` |

Coverage target: ≥ 85% per file in this phase, ≥ 90% on `client.py` and `handlers.py` (the critical paths).

## 7. Acceptance criteria

- [ ] All Phase 0 gates still green.
- [ ] `from tgwarden.handlers import TelegramHandler` works.
- [ ] `python manage.py tgwarden_test` exits 0 in the testbed.
- [ ] `respx`-mocked tests cover happy path + error path for every public method.
- [ ] No `time.sleep`, no global state, no `print` calls in production code.

## 8. Verification scenario (testbed)

### 8.1 Configure credentials

In `tgwarden-testbed/.env`:

```dotenv
TELEGRAM_BOT_TOKEN=123456:AAH...your-real-token...
TELEGRAM_CHAT_ID=-1001234567890
```

### 8.2 Update `tgwarden-testbed/testbed/settings.py`

```python
import environ
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

INSTALLED_APPS = [
    *DEFAULT_APPS,
    "tgwarden",
    "demo",
]

TGWARDEN = {
    "BOT_TOKEN": env("TELEGRAM_BOT_TOKEN"),
    "CHAT_ID":   env("TELEGRAM_CHAT_ID"),
    "TRANSPORT": "sync",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "telegram": {"class": "tgwarden.handlers.TelegramHandler", "level": "DEBUG"},
        "console":  {"class": "logging.StreamHandler",            "level": "DEBUG"},
    },
    "root": {"handlers": ["console", "telegram"], "level": "INFO"},
}
```

### 8.3 Run the gate

```bash
cd /projects/sandbox/tgwarden-testbed
source .venv/bin/activate
pip install -e ../django-tgwarden            # rebuild from current branch
python -c "import tgwarden; print(tgwarden.__version__)"

# Test 1 — management command
python manage.py tgwarden_test --message "phase 1: hello via management command"

# Test 2 — direct logger call from a Django shell
python manage.py shell <<'PY'
import logging
logging.getLogger("phase1.test").error("hello from phase 1 root logger")
PY

# Test 3 — server boots clean
python manage.py runserver 0.0.0.0:8000 &
sleep 2
curl -s http://localhost:8000/ | grep "tgwarden testbed"
kill %1
```

### 8.4 Expected Telegram output

In the configured chat, two messages should appear within seconds:

> 🐛 **INFO** · `tgwarden` · 2026-…
> phase 1: hello via management command

> 🐛 **ERROR** · `phase1.test` · 2026-…
> hello from phase 1 root logger

Copy/paste both into the PR body as proof.

## 9. Risks & gotchas

- **Sync transport blocks the request thread.** Acceptable for Phase 1 because we're proving wiring. Document loudly in the docstring of `TelegramHandler` that `"sync"` is for **dev only**; the default flips to `"async_worker"` in Phase 2.
- **Bot must already be a member of the chat.** Common first-time failure: 400 `chat not found`. Guidance in the management command's error path.
- **Topic IDs not honored yet.** Phase 3 wires them. If user already set `TOPICS`, ignore them this phase (no warning).
- **httpx import-time cost.** Lazy-construct the client inside `emit` only if not yet created.
- **Test isolation.** `respx.mock` decorator on every test that hits the API.

## 10. Definition of Done

Same as AGENTS.md §6, plus:

- [ ] User confirms two messages received in Telegram (paste in PR).
- [ ] `phases/README.md` status flipped to ✅ for Phase 1.
- [ ] `CHANGELOG.md` updated under `[Unreleased]` with the new public API.
