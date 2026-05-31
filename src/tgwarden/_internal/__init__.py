"""Internal stderr-only logger for tgwarden internals. Never recurses into Telegram."""

import logging
import sys

internal_logger = logging.getLogger("tgwarden._internal")
internal_logger.propagate = False
internal_logger.setLevel(logging.DEBUG)

if not internal_logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("[tgwarden] %(message)s"))
    internal_logger.addHandler(_handler)
