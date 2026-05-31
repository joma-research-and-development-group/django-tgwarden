"""Smoke tests for the tgwarden package."""

import django
from django.apps import apps


def test_import_version() -> None:
    """Package exposes __version__."""
    import tgwarden

    assert tgwarden.__version__ == "0.0.0"


def test_app_config() -> None:
    """Django app config is registered correctly."""
    django.setup()
    config = apps.get_app_config("tgwarden")
    assert config.name == "tgwarden"
