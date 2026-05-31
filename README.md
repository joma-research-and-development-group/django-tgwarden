# django-tgwarden

[![PyPI](https://img.shields.io/pypi/v/django-tgwarden)](https://pypi.org/project/django-tgwarden/)
[![Python](https://img.shields.io/pypi/pyversions/django-tgwarden)](https://pypi.org/project/django-tgwarden/)
[![Django](https://img.shields.io/badge/django-4.2%20%7C%205.0%20%7C%205.1-green)](https://pypi.org/project/django-tgwarden/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> A production-grade Django logging handler that ships log records to a Telegram supergroup with per-severity topic routing, batching, deduplication, rate-limiting, and a non-blocking async worker.

**Features:**
- 🚀 Non-blocking — daemon thread + asyncio, never slows your app
- 📋 Per-level topic routing — DEBUG/INFO/WARNING/ERROR/CRITICAL each in their own forum topic
- 🔒 PII scrubbing — passwords, tokens, credit cards redacted before reaching Telegram

## Installation

```bash
pip install django-tgwarden
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

## Development

```bash
git clone https://github.com/joma-research-and-development-group/django-tgwarden.git
cd django-tgwarden
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest
```

## License

MIT
