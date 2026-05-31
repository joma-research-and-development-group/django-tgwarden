"""Tests for TgwardenContextMiddleware."""

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from tgwarden.middleware import TgwardenContextMiddleware, get_current_context


@pytest.fixture()
def rf() -> RequestFactory:
    return RequestFactory()


def test_middleware_sets_and_clears_contextvar(rf: RequestFactory) -> None:
    captured = {}

    def view(request: HttpRequest) -> HttpResponse:
        ctx = get_current_context()
        captured["ctx"] = ctx
        return HttpResponse("ok")

    middleware = TgwardenContextMiddleware(view)
    request = rf.get("/test/")
    middleware(request)

    assert captured["ctx"] is not None
    assert captured["ctx"].path == "/test/"
    assert captured["ctx"].method == "GET"
    # After middleware exits, context should be cleared
    assert get_current_context() is None


def test_x_forwarded_for_first_hop(rf: RequestFactory) -> None:
    captured = {}

    def view(request: HttpRequest) -> HttpResponse:
        captured["ctx"] = get_current_context()
        return HttpResponse("ok")

    middleware = TgwardenContextMiddleware(view)
    request = rf.get("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8")
    middleware(request)
    assert captured["ctx"].client_ip == "1.2.3.4"
