# Phase 0 — Bootstrap

| | |
|---|---|
| **Slug** | `bootstrap` |
| **Branch** | `phase/0-bootstrap` |
| **Prerequisites** | none |
| **Credentials needed** | none |
| **Estimated size** | small–medium (mostly config files) |

---

## 1. Goal

Stand up the **package skeleton**, the **testbed Django project**, and **green CI** on GitHub. No `tgwarden` functionality yet — but at the end of this phase the package builds, the testbed boots, and every subsequent phase has a stable foundation to build on.

## 2. Why this phase

Without bootstrap, every later phase pays a tax of "but the test runner isn't configured" or "but CI isn't green". One careful phase up front pays for itself ten times over.

## 3. Architecture impact

Establishes:
- The src-layout package (`src/tgwarden/`) under `hatchling`.
- The Django app config so the package can be added to `INSTALLED_APPS`.
- The `tgwarden-testbed/` sibling project that will verify every later phase against a real Telegram bot.
- CI matrix Python 3.11/3.12/3.13 × Django 4.2/5.0/5.1.

## 4. Deliverables — package (`/projects/sandbox/django-tgwarden/`)

### 4.1 Build & metadata

- 📁 **`pyproject.toml`** — single source of project config:
  - `[build-system]`: `hatchling` backend.
  - `[project]`: `name = "django-tgwarden"`, `version = "0.0.0"`, dynamic-free, `requires-python = ">=3.11"`, classifiers (Framework :: Django, Programming Language :: Python :: 3.11/3.12/3.13).
  - `[project.dependencies]`: `["django>=4.2", "httpx>=0.27"]`.
  - `[project.optional-dependencies]`: `dev = [pytest, pytest-django, pytest-cov, respx, ruff, mypy, build, pre-commit]`.
  - `[tool.hatch.build.targets.wheel]`: `packages = ["src/tgwarden"]`.
  - `[tool.ruff]`: `line-length = 100`, target Python 3.11.
  - `[tool.ruff.lint]`: enable `E, F, I, B, UP, RUF, S, ASYNC` rule families.
  - `[tool.mypy]`: `strict = true`, `files = ["src/tgwarden"]`, `exclude = ["tests"]`.
  - `[tool.pytest.ini_options]`: `DJANGO_SETTINGS_MODULE = "tests.settings"`, `addopts = "-ra -q --cov=tgwarden --cov-report=term-missing"`.
- 📁 **`LICENSE`** — MIT. Copyright holder: `joma-research-and-development-group` (or as you specify).
- 📁 **`CHANGELOG.md`** — Keep-a-Changelog format with `## [Unreleased]` section.
- ✏️ **`README.md`** — already exists; expand with a "Status" section and a one-line install hint.

### 4.2 Package source

- 📁 **`src/tgwarden/__init__.py`** — exports `__version__ = "0.0.0"` and `default_app_config = "tgwarden.apps.TgwardenConfig"`.
- 📁 **`src/tgwarden/py.typed`** — empty marker (PEP 561).
- 📁 **`src/tgwarden/apps.py`** — `class TgwardenConfig(AppConfig)` with `name = "tgwarden"`, `label = "tgwarden"`, `verbose_name = "Tgwarden"`.

### 4.3 Tests

- 📁 **`tests/__init__.py`** — empty.
- 📁 **`tests/settings.py`** — minimal Django settings used by pytest:
  - `INSTALLED_APPS = ["django.contrib.contenttypes", "django.contrib.auth", "tgwarden"]`
  - `DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}`
  - `USE_TZ = True`, `SECRET_KEY = "test"`, `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`
- 📁 **`tests/conftest.py`** — minimal pytest config; placeholder for shared fixtures introduced in later phases.
- 📁 **`tests/test_smoke.py`** — single test asserting `import tgwarden; assert tgwarden.__version__`.

### 4.4 Tooling & CI

- 📁 **`.gitignore`** — Python + Django + venv + `.env` + `dist/` + `build/` + `*.egg-info` + `.coverage` + `.mypy_cache` + `.ruff_cache` + `.pytest_cache`.
- 📁 **`.pre-commit-config.yaml`** — hooks: `ruff` (with `--fix`), `ruff-format`, `mypy` (manual stage), trailing-whitespace, end-of-file-fixer.
- 📁 **`.github/workflows/ci.yml`** — on push & pull_request:
  - `lint` job: ruff check + ruff format check + mypy.
  - `test` job: matrix `python: [3.11, 3.12, 3.13]` × `django: [4.2, 5.0, 5.1]`; runs `pytest`.
  - `build` job: `python -m build`; uploads wheel as artifact.
- 📁 **`.github/pull_request_template.md`** — PR template matching AGENTS.md §5.
- 📁 **`.github/ISSUE_TEMPLATE/bug_report.md`** — minimal bug template.
- 📁 **`.github/dependabot.yml`** — weekly updates for `pip` and `github-actions`.

## 5. Deliverables — testbed (`/projects/sandbox/tgwarden-testbed/`)

> The testbed is a **separate Git-untracked Django project** sitting beside the package. It is created once (here in Phase 0) and reused by every later verification.

- 📁 **`manage.py`** — standard Django manage.py.
- 📁 **`testbed/__init__.py`**, **`testbed/settings.py`**, **`testbed/urls.py`**, **`testbed/wsgi.py`**, **`testbed/asgi.py`**.
  - `settings.py` reads `.env` via `django-environ`.
  - `INSTALLED_APPS` includes `"demo"`. `tgwarden` will be added in Phase 1.
- 📁 **`demo/__init__.py`**, **`demo/apps.py`**, **`demo/urls.py`**, **`demo/views.py`**.
  - `demo/views.py:home(request)` returns `HttpResponse("tgwarden testbed")`.
- 📁 **`.env.example`** — every key from AGENTS.md §8 with placeholder values.
- 📁 **`.env`** — created locally by the user with real values; **gitignored**.
- 📁 **`.gitignore`** — `.env`, `.venv/`, `__pycache__/`, `db.sqlite3`.
- 📁 **`requirements.txt`**:
  ```
  django>=5.0
  django-environ>=0.11
  -e ../django-tgwarden
  ```
- 📁 **`README.md`** — short note: "Verification harness for django-tgwarden. Do not commit."

## 6. Public API surface

None yet. `tgwarden.__version__` is the only public symbol exported in this phase.

## 7. Test plan

- `tests/test_smoke.py::test_import_version` — `tgwarden.__version__ == "0.0.0"`.
- `tests/test_smoke.py::test_app_config` — `apps.get_app_config("tgwarden").name == "tgwarden"`.

## 8. Acceptance criteria

- [ ] `pip install -e .[dev]` succeeds in a fresh venv.
- [ ] `pytest -q` shows 2 passed, 0 failed.
- [ ] `ruff check .` and `ruff format --check .` clean.
- [ ] `mypy src/tgwarden` clean.
- [ ] `python -m build` produces both `dist/django_tgwarden-0.0.0-py3-none-any.whl` and `.tar.gz`.
- [ ] Testbed `python manage.py runserver 0.0.0.0:8000` returns 200 on `/`.
- [ ] First push to `phase/0-bootstrap` is green in GitHub Actions on every matrix cell.
- [ ] PR opened, reviewed, squash-merged to `main`, tagged `phase-0-complete`.

## 9. Verification scenario

```bash
# --- package ---
cd /projects/sandbox/django-tgwarden
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
ruff check . && ruff format --check .
mypy src/tgwarden
pytest -q
python -m build
ls dist/

# --- testbed ---
deactivate
cd /projects/sandbox/tgwarden-testbed
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000 &
sleep 2
curl -s http://localhost:8000/ | grep "tgwarden testbed"
kill %1
```

Expected:
- All commands exit 0.
- `dist/` contains a wheel and an sdist.
- `curl` prints `tgwarden testbed`.
- Telegram is **not** used in this phase.

## 10. Risks & gotchas

- **Hatchling + src layout** — easy to misconfigure. Verify the wheel contains `tgwarden/__init__.py` (`unzip -l dist/*.whl`).
- **Editable install of `..` in testbed `requirements.txt`** — pip resolves paths relative to the `requirements.txt` file location; keep the testbed at `/projects/sandbox/tgwarden-testbed/` so `../django-tgwarden` resolves correctly.
- **Matrix CI** — Django 5.1 requires Python ≥ 3.10; Django 4.2 supports 3.8+. Our floor is 3.11, which works for both. Don't add Python 3.10 just because Django 4.2 allows it.
- **Pre-commit** — install with `pre-commit install` once per clone; mention this in `README.md`.

## 11. Definition of Done

All boxes from `AGENTS.md` §6:

- [ ] All deliverable files exist and are committed.
- [ ] Public API (just `__version__` here) has type hints (string is fine) and is documented in `README.md`.
- [ ] Tests added; `pytest` shows green.
- [ ] Coverage ≥ 85% on changed code (trivially true since only `__init__.py` and `apps.py`).
- [ ] `ruff` + `mypy` clean.
- [ ] `python -m build` succeeds.
- [ ] Testbed installs the package editable and `runserver` returns 200.
- [ ] CI green on `phase/0-bootstrap`.
- [ ] PR merged into `main`; tag `phase-0-complete` pushed.
- [ ] `phases/README.md` status flipped to ✅ for Phase 0.
