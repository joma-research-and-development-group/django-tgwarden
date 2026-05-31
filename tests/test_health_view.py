"""Tests for the health endpoint."""

import json

from django.test import RequestFactory

from tgwarden.views import health


def test_health_returns_json() -> None:
    rf = RequestFactory()
    request = rf.get("/tgwarden/health/")
    response = health(request)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"


def test_health_includes_all_keys() -> None:
    rf = RequestFactory()
    request = rf.get("/tgwarden/health/")
    response = health(request)
    data = json.loads(response.content)
    expected_keys = {
        "queue_size",
        "sent_total",
        "dropped_total",
        "last_send_at",
        "last_error",
        "transport",
        "package_version",
    }
    assert expected_keys <= set(data.keys())
