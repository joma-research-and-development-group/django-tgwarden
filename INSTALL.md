# Installing django-tgwarden in a Django Project

> For AI agents and developers adding tgwarden to an existing Django project.

## 1. Install

```bash
pip install django-tgwarden
# Or with Celery support:
pip install django-tgwarden[celery]
```

## 2. Telegram Setup

1. Message `@BotFather` on Telegram → `/newbot` → copy the **bot token**.
2. Create a **supergroup** with **Topics** enabled.
3. Add the bot to the group as **admin** (needs Send Messages + Manage Topics).
4. Create 5 topics: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
5. Get the **chat ID** (starts with `-100`) and each **topic thread ID**.

> Tip: Add `@raw_data_bot` to the group temporarily to see IDs, or use `python manage.py tgwarden_test` after setup.

## 3. Environment Variables

```dotenv
TELEGRAM_BOT_TOKEN=123456:ABC-your-token
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_TOPIC_DEBUG=5
TELEGRAM_TOPIC_INFO=6
TELEGRAM_TOPIC_WARNING=7
TELEGRAM_TOPIC_ERROR=8
TELEGRAM_TOPIC_CRITICAL=9
```

## 4. Django Settings

```python
# settings.py

INSTALLED_APPS = [
    ...,
    "tgwarden",
]

MIDDLEWARE = [
    ...,
    "tgwarden.middleware.TgwardenContextMiddleware",  # after AuthenticationMiddleware
]

TGWARDEN = {
    "BOT_TOKEN": env("TELEGRAM_BOT_TOKEN"),
    "CHAT_ID": env("TELEGRAM_CHAT_ID"),
    "TOPICS": {
        "DEBUG": env.int("TELEGRAM_TOPIC_DEBUG"),
        "INFO": env.int("TELEGRAM_TOPIC_INFO"),
        "WARNING": env.int("TELEGRAM_TOPIC_WARNING"),
        "ERROR": env.int("TELEGRAM_TOPIC_ERROR"),
        "CRITICAL": env.int("TELEGRAM_TOPIC_CRITICAL"),
    },
    # Defaults (override as needed):
    # "TRANSPORT": "async_worker",       # "sync" | "async_worker" | "celery"
    # "DEDUP_WINDOW_SECONDS": 60.0,      # 0 to disable
    # "BATCH_MAX_RECORDS": 20,
    # "BATCH_FLUSH_SECONDS": 2.0,
    # "QUEUE_MAX_SIZE": 10000,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "ctx": {"()": "tgwarden.filters.ContextFilter"},
        "scrub": {"()": "tgwarden.filters.ScrubFilter"},
        # Optional: sample noisy levels
        # "sample": {"()": "tgwarden.filters.SamplingFilter", "rates": {"DEBUG": 0.0, "INFO": 0.1}},
    },
    "handlers": {
        "telegram": {
            "class": "tgwarden.handlers.TelegramHandler",
            "level": "WARNING",  # adjust: DEBUG/INFO/WARNING/ERROR
            "filters": ["ctx", "scrub"],
        },
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
        },
    },
    "root": {
        "handlers": ["console", "telegram"],
        "level": "INFO",
    },
}
```

## 5. URLs (optional health endpoint)

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    ...,
    path("tgwarden/", include("tgwarden.urls")),
]
```

This exposes `GET /tgwarden/health/` returning JSON stats.

## 6. Verify

```bash
python manage.py tgwarden_test --message "Hello from tgwarden!" --level ERROR
```

You should see the message in your Telegram ERROR topic within seconds.

## 7. Production Recommendations

| Setting | Dev | Production |
|---|---|---|
| `TRANSPORT` | `"sync"` | `"async_worker"` |
| `LOGGING.handlers.telegram.level` | `"DEBUG"` | `"WARNING"` |
| `DEDUP_WINDOW_SECONDS` | `10` | `60` |
| Sampling (INFO) | `1.0` | `0.1` |
| Sampling (DEBUG) | `1.0` | `0.0` |

## Quick Copy-Paste (Minimal)

If you just want errors in Telegram with zero config overhead:

```python
# settings.py
INSTALLED_APPS = [..., "tgwarden"]

TGWARDEN = {
    "BOT_TOKEN": "your-token",
    "CHAT_ID": "-100your-group-id",
}

LOGGING = {
    "version": 1,
    "handlers": {
        "telegram": {"class": "tgwarden.handlers.TelegramHandler", "level": "ERROR"},
    },
    "root": {"handlers": ["telegram"], "level": "ERROR"},
}
```

That's it. Errors and critical logs go to Telegram. No topics, no batching config needed — defaults handle everything.
