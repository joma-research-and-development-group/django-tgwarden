# Phase 3 — Topic routing + rich HTML formatting

| | |
|---|---|
| **Slug** | `topics-and-html` |
| **Branch** | `phase/3-topics-and-html` |
| **Prerequisites** | Phase 2 merged |
| **Credentials needed** | + `TELEGRAM_TOPIC_DEBUG/INFO/WARNING/ERROR/CRITICAL` |
| **Estimated size** | medium |

---

## 1. Goal

Each severity lands in its own forum topic of the configured supergroup. Tracebacks render as syntax-highlighted HTML code blocks. Long messages overflow gracefully into a `.txt` file attachment with a short caption.

## 2. Why this phase

You picked topics specifically so a chat reader can mute INFO without missing CRITICAL. The HTML upgrade makes tracebacks readable on a phone. The file fallback fixes the 4096-character limit that would otherwise silently truncate long stack traces.

## 3. Architecture impact

- `TgwardenSettings.topics: dict[str, int]` — 5-key dict mapping levelname → `message_thread_id`.
- `TelegramClient.send_message` accepts `topic_id`; `TelegramClient.send_document` is new for overflow.
- `HTMLFormatter` becomes richer: header line, body, optional context placeholder (filled in Phase 6), traceback block, optional attachment payload.
- `SendPayload` (defined Phase 2) gains an `attachment: bytes | None` field; the worker calls `send_document` instead of `send_message` when set.

## 4. Deliverables

### 4.1 `src/tgwarden/conf.py` (modify)

Add to `TgwardenSettings`:

```python
topics: dict[str, int] = field(default_factory=dict)
"""Optional mapping like {"DEBUG": 12, "INFO": 14, ...}. Empty dict disables topic routing."""
```

`get_settings()` should:
- Accept `TGWARDEN["TOPICS"]` as `dict[str, int]`. Keys uppercased.
- Validate: if any key present, all 5 standard levels are recommended (warn to stderr if missing). Don't fail hard — partial routing is allowed.

### 4.2 `src/tgwarden/client.py` (modify + add)

- `send_message(text, *, topic_id=None, parse_mode=None) -> dict`:
  - When `topic_id` given, include `"message_thread_id": topic_id` in the payload.
- New: `send_document(file_bytes: bytes, filename: str, *, caption: str | None, topic_id: int | None) -> dict`:
  - POST `https://api.telegram.org/bot<token>/sendDocument` as `multipart/form-data`.
  - `parse_mode` for caption is `HTML`.
  - Same error handling as `send_message`.

### 4.3 `src/tgwarden/formatters.py` (rewrite)

Render in three blocks separated by `\n\n`:

1. **Header** (always):
   ```
   {emoji} <b>{level}</b> · <code>{logger_name}</code> · <i>{iso_timestamp}</i>
   ```
2. **Body** (always):
   ```
   {html_escaped(record.getMessage())}
   ```
3. **Traceback** (only if `record.exc_info`):
   ```
   <pre><code class="language-python">{html_escaped(traceback_string)}</code></pre>
   ```

Public method:

```python
def format_record(record: LogRecord) -> FormattedRecord
```

Where `FormattedRecord` is:

```python
@dataclass(frozen=True, slots=True)
class FormattedRecord:
    message: str            # always populated; ≤ 4096 chars
    attachment: bytes | None  # plain-text snapshot of the full message+traceback if overflow
    attachment_filename: str | None
```

Behavior:

- If the rendered text ≤ 4096 chars, `attachment = None`.
- If it exceeds 4096, `message` becomes a **short summary** (~1000 chars: header + first 800 chars of body + `…`), and `attachment` carries the full plain-text version (no HTML), `attachment_filename = "{level}-{logger_name}-{epoch_ms}.txt"`.

### 4.4 `src/tgwarden/handlers.py` (modify)

In `emit`:

1. Format record → `FormattedRecord`.
2. Resolve `topic_id = settings.topics.get(record.levelname)` (None if not configured).
3. Build `SendPayload(text=fr.message, topic_id=topic_id, attachment=fr.attachment, attachment_filename=fr.attachment_filename, parse_mode="HTML")`.
4. `transport.submit(payload)`.

### 4.5 `src/tgwarden/transports/async_worker.py` (modify)

- When draining the queue, if `payload.attachment is not None`, call `client.send_document(...)`; else `client.send_message(...)`.
- Same retry/backoff policy applies.

### 4.6 `src/tgwarden/transports/sync_.py` (modify)

- Same dispatch as async worker but synchronous.

### 4.7 `src/tgwarden/management/commands/tgwarden_topics.py`

- `python manage.py tgwarden_topics` — calls Telegram `getUpdates` once and prints any `message_thread_id` it sees alongside the topic name (when available). Helps the user wire `.env` topic IDs.
- Documents in stdout how to use it: "Send a message in each topic, then run this command. Copy the IDs into your .env."

## 5. Public API additions

- `tgwarden.formatters.FormattedRecord`
- `tgwarden.client.TelegramClient.send_document`

Update `__all__` in `tgwarden/__init__.py` if any of these are surfaced.

## 6. Test plan

| Test file | Test functions |
|---|---|
| `tests/test_topic_routing.py` | `test_each_level_routes_to_configured_topic`, `test_unknown_level_falls_back_to_no_topic`, `test_topics_empty_disables_routing` |
| `tests/test_html_formatter.py` (new) | `test_header_format`, `test_html_escapes_dangerous_chars` (`<script>`, `&`, `"`), `test_traceback_in_pre_block`, `test_short_message_no_attachment`, `test_long_message_overflow_to_attachment`, `test_attachment_filename_pattern` |
| `tests/test_client_document.py` (new) | `test_send_document_multipart_payload`, `test_send_document_with_topic_id`, `test_send_document_error_path` |
| `tests/test_async_worker.py` (extend) | `test_payload_with_attachment_uses_send_document` |

Coverage targets: ≥ 90% on `formatters.py`, ≥ 90% on the new `client.send_document`.

## 7. Acceptance criteria

- [ ] All Phase 0–2 gates green.
- [ ] HTML escaping verified with adversarial inputs (`<script>alert(1)</script>`, `&amp;`, embedded `"`).
- [ ] Long-message overflow path tested with a 50 KB message → produces a `.txt` attachment with the short summary as caption.
- [ ] Topic routing tested for all 5 levels.

## 8. Verification scenario (testbed)

### 8.1 Telegram setup (one-time)

1. Open the supergroup → settings → enable **Topics**.
2. Add the bot as admin with **Send Messages**, **Manage Topics**, **Pin Messages** permissions.
3. Create five topics: `Debug`, `Info`, `Warning`, `Error`, `Critical`.
4. In each topic, post a short text from your account (just to populate `getUpdates`).
5. Run `python manage.py tgwarden_topics` and copy the printed IDs into `.env`:

```dotenv
TELEGRAM_TOPIC_DEBUG=12
TELEGRAM_TOPIC_INFO=14
TELEGRAM_TOPIC_WARNING=16
TELEGRAM_TOPIC_ERROR=18
TELEGRAM_TOPIC_CRITICAL=20
```

### 8.2 Update `testbed/settings.py`

```python
TGWARDEN = {
    "BOT_TOKEN": env("TELEGRAM_BOT_TOKEN"),
    "CHAT_ID":   env("TELEGRAM_CHAT_ID"),
    "TOPICS": {
        "DEBUG":    env.int("TELEGRAM_TOPIC_DEBUG"),
        "INFO":     env.int("TELEGRAM_TOPIC_INFO"),
        "WARNING":  env.int("TELEGRAM_TOPIC_WARNING"),
        "ERROR":    env.int("TELEGRAM_TOPIC_ERROR"),
        "CRITICAL": env.int("TELEGRAM_TOPIC_CRITICAL"),
    },
}
```

### 8.3 Add a few demo views

`demo/views.py`:

```python
def levels(request):
    log = logging.getLogger("demo.levels")
    log.debug("phase 3: debug sample")
    log.info("phase 3: info sample")
    log.warning("phase 3: warning sample")
    log.error("phase 3: error sample")
    log.critical("phase 3: critical sample")
    return HttpResponse("ok")

def boom(request):
    raise ValueError("kaboom from /boom")

def big(request):
    msg = "X" * 50_000
    logging.getLogger("demo.big").error("phase 3: big message: %s", msg)
    return HttpResponse("ok")
```

### 8.4 Run the gate

```bash
pip install -e ../django-tgwarden
python manage.py runserver 0.0.0.0:8000 &
sleep 2
curl -s http://localhost:8000/levels/   # 5 messages, one per topic
curl -s http://localhost:8000/boom/ || true   # one CRITICAL with traceback in Error topic? No — error in handle_request is logged as ERROR by Django. Confirm in Error topic.
curl -s http://localhost:8000/big/      # one 50KB → arrives as .txt attachment
kill %1
```

### 8.5 Expected Telegram output

- **Debug** topic: `🔵 DEBUG · demo.levels · … phase 3: debug sample`
- **Info** topic: `ℹ️ INFO · demo.levels · …`
- **Warning** topic: `⚠️ WARNING · demo.levels · …`
- **Error** topic: ERROR sample + ERROR for the unhandled `/boom` view with full Python traceback in a code block.
- **Critical** topic: CRITICAL sample.
- One `.txt` document attachment in the Error topic with caption `🐛 ERROR · demo.big · … (truncated, see attachment)`.

## 9. Risks & gotchas

- **Topic IDs change** if a topic is recreated. Document this; users can re-run `tgwarden_topics`.
- **Bot must have Manage Topics**. Without it, sending to a thread silently 400s. Surface that error clearly via `internal_logger`.
- **`getUpdates` is one-shot** and is consumed by other webhooks if the bot uses webhook mode. Document that `tgwarden_topics` is for setup only.
- **Multipart upload for big files** — set `Content-Type: multipart/form-data` automatically via httpx `files=`. Don't try to `json=` a binary.
- **HTML in caption is limited to 1024 chars** — keep the caption short.
- **Discord-style code-fence ` ```python `** is **not** Telegram syntax. Use `<pre><code class="language-python">`. (Common copy-paste error.)

## 10. Definition of Done

All AGENTS.md §6 boxes plus:

- [ ] Five distinct topics confirmed receiving the right level (paste screenshots or message snippets in PR).
- [ ] Long-message overflow attachment confirmed in Telegram.
- [ ] `phases/README.md` flipped to ✅ for Phase 3.
- [ ] CHANGELOG updated.
