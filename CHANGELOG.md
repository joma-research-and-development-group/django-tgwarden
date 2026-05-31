# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-05-31

### Fixed

- `AsyncWorkerTransport` shutdown no longer hangs the process or emits
  `RuntimeError: Event loop stopped before Future completed` /
  `cannot schedule new futures after interpreter shutdown`. The final drain now
  runs via `run_coroutine_threadsafe` with the main thread blocking on the
  result, so the last network send completes while the interpreter is alive;
  the loop is then allowed to finish on its own instead of being force-stopped.
- `DedupGate` no longer spawns a `threading.Timer` per fingerprint (which
  exhausted OS threads under high-cardinality load); a single daemon sweep
  thread now expires windows.
- 429 `Retry-After` waits are capped at `retry_cap_seconds` and skipped during
  shutdown to keep teardown bounded.

## [0.1.0] - 2026-05-31

### Added

- `TelegramHandler` — logging.Handler that ships records to Telegram.
- `HTMLFormatter` with emoji per level, HTML escaping, traceback in code blocks.
- Per-severity topic routing via `TGWARDEN["TOPICS"]`.
- Long-message overflow to `.txt` file attachment.
- Non-blocking `async_worker` transport (daemon thread + asyncio + bounded queue).
- Exponential backoff retry on 429/5xx with configurable max attempts.
- Token-bucket rate limiting (global 30 msg/sec + per-chat 20 msg/min).
- Message batching (coalesce up to 20 records per Telegram message).
- Deduplication gate — repeated errors collapse to "× N more" follow-ups.
- `SamplingFilter` for probabilistic per-level sampling.
- `ScrubFilter` for PII redaction (passwords, tokens, credit cards).
- `TgwardenContextMiddleware` — injects request context (path, method, user, IP).
- `ContextFilter` — attaches request context to log records.
- Optional Celery transport (`pip install django-tgwarden[celery]`).
- `/health/` JSON endpoint for operational monitoring.
- `tgwarden_test` management command for verifying wiring.
- Full type hints (py.typed, mypy strict).
- CI matrix: Python 3.11/3.12/3.13 × Django 4.2/5.0/5.1.
