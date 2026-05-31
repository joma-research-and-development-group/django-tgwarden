"""Management command to send a test message via tgwarden."""

from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand

from tgwarden.handlers import TelegramHandler


class Command(BaseCommand):
    """Send a test message via the configured TelegramHandler to verify wiring."""

    help = "Send a test message via the configured TelegramHandler to verify wiring."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--level", default="INFO", help="Log level (default: INFO)")
        parser.add_argument("--message", default="tgwarden test message", help="Message text")

    def handle(self, *args: Any, **opts: Any) -> None:
        level_name = opts["level"].upper()
        level = getattr(logging, level_name, logging.INFO)
        message = opts["message"]

        logger = logging.getLogger("tgwarden.test")
        handler = TelegramHandler(level=level)
        logger.addHandler(handler)
        logger.setLevel(level)

        try:
            logger.log(level, message)
            self.stdout.write(
                self.style.SUCCESS(f"Sent test message at {level_name} via tgwarden.")
            )
        finally:
            handler.close()
            logger.removeHandler(handler)
