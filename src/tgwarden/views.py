"""Views for tgwarden."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse

from tgwarden.stats import stats


def health(request: HttpRequest) -> JsonResponse:
    """JSON health endpoint returning current tgwarden stats."""
    snapshot = stats.snapshot(transport="async_worker")
    return JsonResponse(snapshot.to_dict())
