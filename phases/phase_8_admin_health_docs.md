# Phase 8 — Admin, health endpoint, and docs

| | |
|---|---|
| **Slug** | `admin-health-docs` |
| **Branch** | `phase/8-admin-health-docs` |
| **Prerequisites** | Phase 7 merged |
| **Credentials needed** | same as Phase 6 |
| **Estimated size** | medium |

---

## 1. Goal

Operational visibility (admin status page + JSON health endpoint) and polished user-facing documentation. After this phase, a new user can install the package, paste from the README, and have it working in five minutes.

## 2. Why this phase

Logs go *out* of your app via this package; you also need a way to look *into* the package's own state — queue size, sent count, dropped count, last error. And no production-grade package ships without a quickstart doc.

## 3. Architecture impact

- A small singleton `tgwarden.stats.Stats` object that all transports update.
- A Django admin page that renders these stats.
- A `/health/` JSON view (mountable under any URL prefix).
- A `docs/` directory with quickstart, configuration reference, and recipes.

## 4. Deliverables

### 4.1 `src/tgwarden/stats.py`

```python
@dataclass
class Snapshot:
    queue_size: int
    sent_total: int
    dropped_total: int
    batches_sent: int
    batches_split: int
    rate_limited_seconds: float
    last_send_at: datetime | None
    last_error: str | None
    transport: str
    package_version: str

class Stats:
    """Thread-safe counters. One instance lives at module scope."""
    def increment(self, name: str, by: int = 1) -> None: ...
    def set_last_send(self, ts: datetime) -> None: ...
    def set_last_error(self, msg: str | None) -> None: ...
    def snapshot(self, transport: Transport) -> Snapshot: ...

stats: Stats = Stats()
```

All transports update `stats` via these methods.

### 4.2 `src/tgwarden/admin.py`

A custom admin view (no model). Registered via:

```python
class TgwardenStatusView:
    """Renders Stats.snapshot() in the Django admin."""
    @staticmethod
    def get_urls(): ...
    @staticmethod
    def status_view(request): ...

# In apps.py ready():
admin.site.get_urls = ... # patched to include the status view at /admin/tgwarden/status/
```

The view returns an HTML page styled with Django admin's CSS, a refresh-every-5s meta tag, and a table with the snapshot fields. Read-only.

### 4.3 `src/tgwarden/views.py`

```python
def health(request):
    """JSON snapshot. Returns 200 always; clients can decide what 'unhealthy' means."""
    return JsonResponse(stats.snapshot(...).to_dict())
```

### 4.4 `src/tgwarden/urls.py`

```python
from django.urls import path
from . import views
app_name = "tgwarden"
urlpatterns = [
    path("health/", views.health, name="health"),
]
```

User wires this into their `urls.py` with `path("tgwarden/", include("tgwarden.urls"))`.

### 4.5 `docs/`

- `docs/quickstart.md` — 5-minute install: pip install, .env, settings.py LOGGING block, test command.
- `docs/configuration.md` — every key in `TgwardenSettings` with default, type, description, and an example `TGWARDEN = {...}` block at the bottom.
- `docs/recipes.md` — multi-environment (dev/staging/prod), coexistence with Sentry, Celery setup pointer, request-context middleware.
- `docs/troubleshooting.md` — "my message didn't arrive" decision tree.
- `docs/architecture.md` — the architecture diagrams from each phase, consolidated.
- `docs/index.md` — table of contents.

### 4.6 `README.md` (rewrite)

A polished README that includes:

- Badges (PyPI, Python versions, Django versions, CI, license, codecov).
- Tagline + 3-bullet feature list.
- 30-second install snippet (`pip install django-tgwarden`, minimal `LOGGING` config).
- Link to docs.
- Status table linking to the phases (the index in `phases/README.md`).

### 4.7 `examples/`

- `examples/minimal_settings.py` — copy/paste minimum.
- `examples/production_settings.py` — recommended production config (async_worker, batching, dedup, scrub, middleware).

## 5. Public API additions

- `tgwarden.stats.stats` (singleton, intentionally lowercase)
- `tgwarden.stats.Snapshot`
- `tgwarden.views.health`
- URL include `tgwarden.urls`

## 6. Test plan

| Test file | Test functions |
|---|---|
| `tests/test_stats.py` | `test_increment_thread_safe`, `test_snapshot_immutable`, `test_set_last_error_clearable` |
| `tests/test_health_view.py` | `test_health_returns_json`, `test_health_includes_all_keys` |
| `tests/test_admin_status.py` | `test_admin_status_page_renders_for_staff`, `test_admin_status_page_403_for_non_staff` |
| `tests/test_docs_links.py` | `test_all_relative_links_in_docs_resolve` (lightweight Markdown link checker) |

Coverage: ≥ 90% on `stats.py` and `views.py`.

## 7. Acceptance criteria

- [ ] `/tgwarden/health/` returns 200 JSON with all snapshot keys.
- [ ] Admin page renders under `/admin/tgwarden/status/` for staff users only.
- [ ] All links in `docs/` resolve.
- [ ] README's quickstart snippet works **literally as pasted** in a fresh testbed-like project.

## 8. Verification scenario (testbed)

### 8.1 Wire urls

In `testbed/urls.py`:

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("tgwarden/", include("tgwarden.urls")),
    path("", include("demo.urls")),
]
```

### 8.2 Run

```bash
python manage.py createsuperuser   # interactive, one-time
python manage.py runserver 0.0.0.0:8000 &
sleep 2

# Health
curl -s http://localhost:8000/tgwarden/health/ | jq

# Admin (open in browser, log in as superuser):
#   http://localhost:8000/admin/tgwarden/status/

# Trigger some traffic
curl -s http://localhost:8000/burst/?n=200
sleep 3
curl -s http://localhost:8000/tgwarden/health/ | jq
```

### 8.3 Expected

- First `health` JSON has `sent_total: 0, queue_size: 0`.
- After the burst, `sent_total` rises (~200 records → ~10 batches), `queue_size` returns to 0.
- Admin page renders the same snapshot in HTML, refreshing every 5 seconds.

## 9. Risks & gotchas

- **Admin URL patching.** Use `admin.site.get_urls` extension carefully so we don't break other admin apps. Add a Django check (`AppConfig.ready` system check) that verifies the admin is wired correctly.
- **Stats are per-process.** With pre-fork gunicorn, each worker has its own counters. Document this; for centralized stats, point users at Prometheus exporters as a future integration.
- **Health endpoint security.** The default `health` view is **public**. Document this and recommend wrapping with `@user_passes_test(lambda u: u.is_staff)` if the JSON contains anything sensitive (it shouldn't, but counters can leak rough traffic patterns).
- **Markdown link checker** — keep it lightweight; don't fetch external links in CI.

## 10. Definition of Done

All AGENTS.md §6 boxes plus:

- [ ] Verification produced healthy JSON before and after burst (paste both in PR).
- [ ] Admin status page screenshot in PR.
- [ ] README quickstart copy-pasted into a fresh test project succeeded.
- [ ] `phases/README.md` flipped to ✅ for Phase 8.
- [ ] CHANGELOG updated.
