# django-tgwarden

> A production-grade Django logging handler that ships log records to a Telegram supergroup with per-severity topic routing, batching, deduplication, rate-limiting, and a non-blocking async worker.

## Installation

```bash
pip install django-tgwarden
```

## Quick start

```python
# settings.py
INSTALLED_APPS = [
    ...
    "tgwarden",
]
```

Full configuration docs coming after Phase 1.

## Status

🚧 **Phase 0 (bootstrap)** — package skeleton, CI, and testbed created.

## Development

```bash
git clone https://github.com/joma-research-and-development-group/django-tgwarden.git
cd django-tgwarden
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pre-commit install
```

## For agents and contributors

- 📜 [`AGENTS.md`](./AGENTS.md) — agent roles, phase-gated workflow, conventions.
- 🗺️ [`phases/`](./phases/) — detailed 10-phase build plan.

## License

MIT
