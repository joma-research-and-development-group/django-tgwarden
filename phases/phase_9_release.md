# Phase 9 — Release v0.1.0 to PyPI

| | |
|---|---|
| **Slug** | `release-0.1.0` |
| **Branch** | `phase/9-release-0.1.0` |
| **Prerequisites** | Phase 8 merged |
| **Credentials needed** | PyPI Trusted Publisher configured in repo settings (no API token in code) |
| **Estimated size** | small |

---

## 1. Goal

Tag `v0.1.0` and publish the package to PyPI. Use **Trusted Publishers** so no long-lived API token is stored as a GitHub secret. After this phase, anyone can `pip install django-tgwarden`.

## 2. Why this phase

We've reserved the name and built nine phases of functionality. Time to ship.

Trusted Publishers (OIDC) is the modern, secure way to publish from GitHub Actions: PyPI verifies the workflow's identity directly with GitHub, no token storage involved.

## 3. Architecture impact

None. This phase is operational: CI workflow + release process.

## 4. Deliverables

### 4.1 `.github/workflows/release.yml`

```yaml
name: Release to PyPI

on:
  push:
    tags:
      - "v*"

permissions:
  id-token: write   # required for Trusted Publishers
  contents: read

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/django-tgwarden
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
        # No `password:` — Trusted Publisher OIDC handles auth.
```

### 4.2 `pyproject.toml` (modify)

- `version = "0.1.0"`
- Tighten classifiers and `[project.urls]`:
  ```toml
  [project.urls]
  Homepage     = "https://github.com/joma-research-and-development-group/django-tgwarden"
  Documentation = "https://github.com/joma-research-and-development-group/django-tgwarden/tree/main/docs"
  Issues       = "https://github.com/joma-research-and-development-group/django-tgwarden/issues"
  Changelog    = "https://github.com/joma-research-and-development-group/django-tgwarden/blob/main/CHANGELOG.md"
  ```

### 4.3 `CHANGELOG.md` (modify)

Promote `[Unreleased]` to `[0.1.0] - YYYY-MM-DD` with the full feature list.

### 4.4 `README.md` (modify)

- Replace the "Status: Phase 0 pending" line with a "v0.1.0 released" badge.
- Confirm install instructions point to the published package.

### 4.5 GitHub repo configuration (one-time, manual)

The user (or whoever owns the repo) must do this in the GitHub UI:

1. Go to `https://pypi.org` → log in (create account if needed).
2. Visit `https://pypi.org/manage/account/publishing/`.
3. Click "Add a new pending publisher".
4. Fill in:
   - PyPI Project Name: `django-tgwarden`
   - Owner: `joma-research-and-development-group`
   - Repository name: `django-tgwarden`
   - Workflow filename: `release.yml`
   - Environment name: `pypi`
5. In the GitHub repo Settings → Environments → New environment named `pypi`.
6. (Optional) Add a required reviewer to the environment so each release requires manual approval.

Document these steps in `docs/release.md` for future maintainers.

### 4.6 `docs/release.md`

A short doc covering:

- How to cut a release (tag `vX.Y.Z` on `main`, push, watch CI).
- How to bump the version (single source = `pyproject.toml`).
- Semver policy: BREAKING changes bump major, new features bump minor, fixes bump patch. Pre-1.0 the contract is "best effort".

## 5. Test plan

This phase has no new code paths. Tests:

- `tests/test_pyproject_metadata.py` — read `pyproject.toml`, assert `version == "0.1.0"`, classifiers present, urls present.
- `tests/test_changelog.py` — assert `0.1.0` exists, `[Unreleased]` is empty.

## 6. Acceptance criteria

- [ ] `git tag v0.1.0 && git push --tags` triggers the release workflow.
- [ ] Workflow succeeds; PyPI shows `django-tgwarden 0.1.0`.
- [ ] `pip install django-tgwarden==0.1.0` works in a fresh venv.
- [ ] All earlier gates green.

## 7. Verification scenario

### 7.1 Pre-flight

```bash
cd /projects/sandbox/django-tgwarden
git checkout main
git pull
python -m build
twine check dist/*    # must be clean
```

### 7.2 Tag + publish

```bash
git tag -a v0.1.0 -m "Release 0.1.0"
git push origin v0.1.0
# Watch the release workflow at:
#   https://github.com/joma-research-and-development-group/django-tgwarden/actions
```

### 7.3 Smoke-test the published artifact

In a brand-new venv (NOT the testbed venv):

```bash
mkdir /tmp/tgwarden-smoke && cd /tmp/tgwarden-smoke
python -m venv .venv && source .venv/bin/activate
pip install django-tgwarden==0.1.0 django>=5
django-admin startproject smoke
cd smoke
# Apply the README quickstart literally:
#  - add 'tgwarden' to INSTALLED_APPS
#  - paste TGWARDEN dict with .env values
#  - paste LOGGING dict
python manage.py migrate
python manage.py tgwarden_test --message "v0.1.0 smoke test"
```

Confirm the message arrives in Telegram.

### 7.4 Post-release

- Add a GitHub Release entry referencing `CHANGELOG.md` content.
- Tweet/post if you want.
- Open issues for known follow-ups (out-of-scope items from PHASES.md).

## 8. Risks & gotchas

- **Trusted Publisher pending vs claimed**. The "pending publisher" lets you publish *before* the project exists on PyPI. Once 0.1.0 publishes, it transitions to "claimed". You don't need to re-add it for future releases.
- **Tag immutability**. Once pushed, never delete or move a release tag. If a release is broken, ship `0.1.1` immediately.
- **PyPI 2FA on the account**. Strongly recommended. Trusted Publisher works without a password but the account must still exist and be secured.
- **First-time wheels** — `python -m build` produces a `py3-none-any.whl` (pure Python). Verify there are no inadvertent native extensions (there shouldn't be).
- **`twine check`** validates README rendering on PyPI; fix any markup issues before tagging.
- **Time zone in CHANGELOG date** — use ISO-8601 UTC: `2026-MM-DD`.

## 9. Definition of Done

All AGENTS.md §6 boxes plus:

- [ ] PyPI page live: `https://pypi.org/project/django-tgwarden/0.1.0/`.
- [ ] Smoke-test from a fresh venv succeeded (paste pip output + Telegram message in PR).
- [ ] GitHub Release created.
- [ ] `phases/README.md` flipped to ✅ for Phase 9.
- [ ] CHANGELOG `[Unreleased]` reset to empty.
- [ ] User notified: project is live.
