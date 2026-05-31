"""django-tgwarden — Django logging handler for Telegram."""

from tgwarden.exceptions import ConfigurationError, TelegramAPIError, TgwardenError
from tgwarden.formatters import HTMLFormatter
from tgwarden.handlers import TelegramHandler

__version__ = "0.1.0"
default_app_config = "tgwarden.apps.TgwardenConfig"

__all__ = [
    "ConfigurationError",
    "HTMLFormatter",
    "TelegramAPIError",
    "TelegramHandler",
    "TgwardenError",
    "__version__",
]
