# django-tgwarden

[![PyPI](https://img.shields.io/pypi/v/django-tgwarden)](https://pypi.org/project/django-tgwarden/)
[![Python](https://img.shields.io/pypi/pyversions/django-tgwarden)](https://pypi.org/project/django-tgwarden/)
[![Django](https://img.shields.io/badge/django-4.2%20%7C%205.0%20%7C%205.1-green)](https://pypi.org/project/django-tgwarden/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> A production-grade Django logging handler that ships log records to a Telegram supergroup with per-severity topic routing, batching, deduplication, rate-limiting, and a non-blocking async worker.

**Status:** ✅ `v0.1.1` released on [PyPI](https://pypi.org/project/django-tgwarden/).

## Features

- 🚀 **Non-blocking** — daemon thread + asyncio worker; submitting 10,000 records takes ~100ms and never slows your request cycle
- 📋 **Per-level topic routing** — DEBUG/INFO/WARNING/ERROR/CRITICAL each land in their own forum topic
- 🎨 **Rich HTML** — emoji headers, syntax-highlighted tracebacks; long messages overflow to a `.txt` attachment
- 📦 **Batching + rate limiting** — coalesces records and respects Telegram's limits via a token bucket
- 🔁 **Deduplication** — repeated errors collapse to a "× N more" follow-up instead of spamming
- 🎚️ **Sampling** — probabilistically thin out noisy DEBUG/INFO levels
- 🔒 **PII scrubbing** — passwords, tokens, credit-card numbers redacted before reaching Telegram
- 🧭 **Request context** — middleware injects path, method, user, and IP into every record
- ⚙️ **Pluggable transport** — `async_worker` (default), `sync`, or optional `celery`
- 🩺 **Health endpoint** — `/tgwarden/health/` JSON stats for monitoring

## Installation

```bash
pip install django-tgwarden
# optional Celery transport:
pip install "django-tgwarden[celery]"
```

## Quick start

```python
# settings.py
INSTALLED_APPS = [..., "tgwarden"]

TGWARDEN = {
    "BOT_TOKEN": "your-bot-token",
    "CHAT_ID": "-100your-supergroup-id",
    "TOPICS": {
        "DEBUG": 5, "INFO": 6, "WARNING": 7, "ERROR": 8, "CRITICAL": 9,
    },
}

LOGGING = {
    "version": 1,
    "handlers": {
        "telegram": {"class": "tgwarden.handlers.TelegramHandler", "level": "WARNING"},
    },
    "root": {"handlers": ["telegram"], "level": "WARNING"},
}
```

Then verify:

```bash
python manage.py tgwarden_test --message "Hello from tgwarden!"
```

## For agents & integrators

📘 **[INSTALL.md](./INSTALL.md)** — a step-by-step guide for AI agents and developers
adding `django-tgwarden` to a new or existing Django project: Telegram bot setup,
environment variables, full + minimal settings blocks, the health endpoint, and
production tuning recommendations.

## Development

```bash
git clone https://github.com/joma-research-and-development-group/django-tgwarden.git
cd django-tgwarden
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pre-commit install
pytest
```

See [`CHANGELOG.md`](./CHANGELOG.md) for release history and [`AGENTS.md`](./AGENTS.md)
for the build workflow and conventions.

## License

MIT
