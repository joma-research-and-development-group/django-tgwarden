# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
