"""Minimal Django settings for pytest."""

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "tgwarden",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

USE_TZ = True
SECRET_KEY = "test"  # noqa: S105
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
