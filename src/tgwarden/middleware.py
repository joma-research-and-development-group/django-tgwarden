"""Request context middleware for tgwarden."""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from django.http import HttpRequest, HttpResponse

_request_ctx: ContextVar[RequestContext | None] = ContextVar("tgwarden_request_ctx", default=None)


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Immutable request context attached to log records."""

    request_id: str
    method: str
    path: str
    user_id: int | str | None
    client_ip: str | None


def get_current_context() -> RequestContext | None:
    """Get the current request context, if any."""
    return _request_ctx.get()


class TgwardenContextMiddleware:
    """Binds a RequestContext into a ContextVar for the lifetime of a request."""

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        ctx = self._build_context(request)
        token = _request_ctx.set(ctx)
        try:
            response: HttpResponse = self.get_response(request)
        finally:
            _request_ctx.reset(token)
        return response

    def process_exception(self, request: HttpRequest, exception: Exception) -> None:
        """Log unhandled exceptions as CRITICAL with context."""
        logger = logging.getLogger("tgwarden.unhandled")
        logger.critical(
            "Unhandled %s at %s %s",
            type(exception).__name__,
            request.method,
            request.path,
            exc_info=True,
        )

    @staticmethod
    def _build_context(request: HttpRequest) -> RequestContext:
        user_id: int | str | None = None
        if hasattr(request, "user") and request.user.is_authenticated:
            user_id = request.user.pk

        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.META.get("REMOTE_ADDR")

        return RequestContext(
            request_id=uuid.uuid4().hex[:8],
            method=request.method or "GET",
            path=request.path,
            user_id=user_id,
            client_ip=client_ip,
        )
