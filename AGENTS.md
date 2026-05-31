# AGENTS.md — django-tgwarden

> **For agents (and humans) building this project.**
> Read this file first. It defines roles, the phase-gated workflow, conventions, and the verification protocol. Never skip a verification gate.
>
> The detailed per-phase build plan lives in [`phases/`](./phases/) — one file per phase. Start with [`phases/README.md`](./phases/README.md) for the index.

---

## 1. Mission

Build **`django-tgwarden`** — a production-grade Django logging handler that ships log records (DEBUG / INFO / WARNING / ERROR / CRITICAL) to a Telegram supergroup, with each severity routed to its own forum topic. The handler must be **non-blocking, batched, deduplicated, rate-limited, and never crash the host app**.

Distribution target: PyPI as `django-tgwarden`, importable as `tgwarden`.

> **Current status:** ✅ All phases (0–9) complete. `v0.1.1` is released on
> [PyPI](https://pypi.org/project/django-tgwarden/). The phase-gated workflow
> below is retained as the historical build record and the process for any
> future major rework. Day-to-day changes now follow the branching model in §5
> (`dev` → version tag → `main`). Integrator/agent setup lives in
> [`INSTALL.md`](./INSTALL.md).

---

## 2. Workspace layout

The workspace contains **two sibling projects**:

```
/projects/sandbox/
├── django-tgwarden/          # The package (this repo, pushed to GitHub)
│   ├── AGENTS.md             # ← you are here
│   ├── phases/               # detailed per-phase plan
│   │   ├── README.md         # phase index + status table
│   │   ├── phase_0_bootstrap.md
│   │   ├── phase_1_mvp_handler.md
│   │   └── ...
│   ├── pyproject.toml
│   ├── src/tgwarden/
│   ├── tests/
│   ├── .github/workflows/
│   └── ...
└── tgwarden-testbed/         # Throwaway Django 5 project used to verify each phase
    ├── manage.py
    ├── testbed/              # Django project package
    │   ├── settings.py
    │   ├── urls.py
    │   └── ...
    ├── demo/                 # one app with views that emit logs
    ├── .env                  # Telegram credentials (NEVER committed)
    ├── .env.example
    └── requirements.txt
```

**Rule:** the testbed is **never** committed to the package repo. It lives outside `django-tgwarden/`. After each phase the package is reinstalled into the testbed via `pip install -e ../django-tgwarden`.

---

## 3. Agent roles

The orchestrator (Planner) spawns one or more workers per phase. Roles can be combined in a single agent for small phases.

| Role | Responsibility |
|---|---|
| **Planner** | Reads `phases/README.md` (index) then the next `phases/phase_N_*.md`, spawns workers, enforces the verification gate, opens PR. |
| **Builder** | Implements all source files listed in the phase deliverables. |
| **Tester** | Writes unit tests with `pytest` + `respx`; runs `pytest`, `ruff`, `mypy`. |
| **Verifier** | Reinstalls the package into `tgwarden-testbed/`, runs the testbed verification scenario, confirms messages arrive in Telegram. |
| **Reviewer** | Lightweight design review before PR is merged. May be skipped for trivial phases. |

Sub-agent invocation: use `general-task-execution` for Builder/Tester/Verifier; use `semantic_reviewer` for Reviewer; use `context-gatherer` if a phase requires understanding existing code.

---

## 4. Phase-gated workflow

Every phase follows the **same 10 steps**. No step may be skipped.

```
                 ┌─────────────────────────────────┐
                 │  PHASE N starts                 │
                 └────────────────┬────────────────┘
                                  ▼
 1. Branch:  git checkout -b phase/<N>-<slug>
 2. Build:   create/modify all files listed in phases/phase_<N>_*.md → "Deliverables"
 3. Test:    pytest -q   (must pass, coverage ≥ 85%)
 4. Lint:    ruff check . && ruff format --check .
 5. Types:   mypy src/tgwarden
 6. Build:   python -m build  (wheel + sdist build clean)
 7. Reinstall in testbed:
             pip install -e ../django-tgwarden  (run inside tgwarden-testbed venv)
 8. Verify:  follow the "Verification scenario" in phases/phase_<N>_*.md.
             A real message MUST appear in the Telegram supergroup.
             Capture proof: screenshot or copy/paste of Telegram message text.
 9. Commit:  conventional-commit style (see §7)
10. PR:      title "phase(N): <slug>"
             body = checklist from §6 + verification proof
             squash-merge to main, then tag `phase-N-complete`
```

**Phase gate (must all be green before merge):**
- [ ] Unit tests pass
- [ ] Coverage ≥ 85% on changed files
- [ ] `ruff check` and `ruff format --check` clean
- [ ] `mypy src/tgwarden` clean
- [ ] Package builds (`python -m build`)
- [ ] Reinstalled into testbed without error
- [ ] Testbed verification scenario passed (with Telegram proof)
- [ ] CI workflow green on the branch
- [ ] PR description includes verification proof

If any check fails, the agent must **stop and report**, not paper over it.

---

## 5. Version control (GitHub)

- **Remote:** `https://github.com/joma-research-and-development-group/django-tgwarden.git`
- **Default branch:** `main` (protected, no direct pushes; PR-only)
- **Branching model:** trunk-based. Each phase = one short-lived branch named `phase/<N>-<slug>` (e.g. `phase/1-mvp-handler`).
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/). Examples:
  - `feat(handler): add TelegramHandler with sync transport`
  - `test(client): add respx-mocked send_message tests`
  - `chore(ci): add github actions matrix for py 3.11/3.12/3.13`
- **PR titles:** `phase(N): <slug>` — e.g. `phase(2): async worker`
- **PR body template** (also in `.github/pull_request_template.md`):
  ```markdown
  ## Phase N: <slug>

  ### What
  <one-paragraph summary>

  ### Verification
  - [ ] Unit tests pass
  - [ ] Coverage ≥ 85%
  - [ ] ruff + mypy clean
  - [ ] Reinstalled into tgwarden-testbed
  - [ ] Telegram message received (proof below)

  <screenshot or pasted message text>

  ### Files
  <bulleted list of new/changed files>
  ```
- **Tags:** after each phase merge, tag `phase-N-complete`. Real releases use semver tags (`v0.1.0`, `v0.2.0`, …) on Phase 9.
- **CI:** GitHub Actions runs on every push and PR — matrix of Python `3.11 / 3.12 / 3.13` × Django `4.2 / 5.0 / 5.1`.

---

## 6. Definition of Done (per phase)

A phase is **only** done when **every** box is checked:

- [ ] All files in the phase's "Deliverables" list exist and are reachable from `__init__` exports where appropriate.
- [ ] Public API listed in the phase has type hints and docstrings.
- [ ] Unit tests added; full suite passes.
- [ ] Coverage ≥ 85% on the phase's new code.
- [ ] `ruff` + `mypy` are clean.
- [ ] Package builds and installs editable into the testbed.
- [ ] Testbed verification scenario executed; Telegram message proof attached to PR.
- [ ] CI green on the phase branch.
- [ ] PR merged into `main` and tagged `phase-N-complete`.

---

## 7. Coding conventions

| Concern | Choice |
|---|---|
| Python | 3.11+ (target 3.12) |
| Layout | `src/` layout, package name `tgwarden` |
| Build backend | `hatchling` |
| Linter / formatter | `ruff` + `ruff format` (no black, no isort) |
| Type checker | `mypy` strict on `src/tgwarden` |
| Test runner | `pytest` + `pytest-django` + `respx` (httpx mocking) |
| HTTP client | `httpx` (sync + async) |
| Logging discipline | Never log inside the handler; use `sys.stderr` or the handler's own internal error reporting. |
| Imports | Absolute. No `from .x import *`. |
| Docstrings | Google style. |
| Errors | Custom exceptions in `tgwarden/exceptions.py`, never raise from `Handler.emit`. |
| Settings | Single source of truth in `tgwarden/conf.py`, validated via dataclass. |

---

## 8. Credentials & secrets

- All secrets live in `tgwarden-testbed/.env`.
- `.env` is **gitignored** in both repos.
- `.env.example` (committed) lists required keys with placeholder values.
- The package itself **never** reads env vars directly; it reads from Django settings (`settings.TGWARDEN`). The testbed's `settings.py` reads `.env` via `django-environ` and populates `TGWARDEN`.
- The PR/issue templates remind reviewers to redact tokens from any pasted log output.

Required keys (full list — staged per phase, see §9):

| Key | Required from phase | How to obtain |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | 1 | `@BotFather` → `/newbot` |
| `TELEGRAM_CHAT_ID`   | 1 | Supergroup ID with `-100` prefix |
| `TELEGRAM_TOPIC_DEBUG` | 3 | Topic ID inside the supergroup |
| `TELEGRAM_TOPIC_INFO` | 3 | Topic ID |
| `TELEGRAM_TOPIC_WARNING` | 3 | Topic ID |
| `TELEGRAM_TOPIC_ERROR` | 3 | Topic ID |
| `TELEGRAM_TOPIC_CRITICAL` | 3 | Topic ID |
| `REDIS_URL` | 7 (optional) | For Celery transport |
| `PYPI_TRUSTED_PUBLISHER` config | 9 | GitHub Actions OIDC |

---

## 9. Credential staging by phase

To avoid blocking on credentials before they're needed:

- **Phase 0** — none
- **Phase 1–2** — `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (one chat is fine; topics not yet)
- **Phase 3+** — add the 5 topic IDs
- **Phase 7** — add `REDIS_URL` (optional, only if testing Celery transport)
- **Phase 9** — configure PyPI Trusted Publisher in GitHub repo settings (no token in code)

---

## 10. Verification protocol

Each phase has a numbered scenario in its `phases/phase_N_*.md` file. The Verifier role must:

1. Activate the testbed venv: `source tgwarden-testbed/.venv/bin/activate`
2. Reinstall the package: `pip install -e /projects/sandbox/django-tgwarden`
3. Confirm install: `python -c "import tgwarden; print(tgwarden.__version__)"`
4. Run the phase's scenario commands exactly as listed.
5. Confirm the expected Telegram message(s) arrived. Copy the message text (or take a screenshot) for the PR body.
6. If the scenario fails, **do not modify the testbed** — go back to the package, fix the issue, re-run from step 1.

---

## 11. Quick reference commands

```bash
# Package (run inside django-tgwarden/)
ruff check . && ruff format --check .
mypy src/tgwarden
pytest -q --cov=tgwarden --cov-report=term-missing
python -m build

# Testbed (run inside tgwarden-testbed/)
source .venv/bin/activate
pip install -e ../django-tgwarden
python manage.py migrate
python manage.py tgwarden_test           # phase 1+
python manage.py runserver
```

---

## 12. Safety rules for agents

- Never commit `.env`, `*.token`, or any file matching `*secret*`.
- Never push directly to `main`. Always go through a PR.
- Never weaken a phase gate to make CI pass. Fix the root cause.
- Never modify `AGENTS.md` or any file under `phases/` without an explicit instruction from the user. (Exception: after merging a phase, the Planner flips that phase's status row in `phases/README.md` to ✅.)
- If a phase reveals a design flaw in an earlier phase, stop and report — do not silently refactor across phases.

---

*Last updated: v0.1.1 — all phases complete, released to PyPI.*
