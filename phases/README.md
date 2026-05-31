# phases/ — django-tgwarden build plan

Each file in this folder is a self-contained spec for **one phase** of the build.
The orchestrator reads these in order. After a phase merges to `main`, tag `phase-N-complete` and move on to the next.

> Read [`../AGENTS.md`](../AGENTS.md) **first** for the workflow, conventions, version-control rules, and verification protocol that apply to every phase.

## Phase index

| # | File | Slug | Branch | Goal (one line) | Status |
|---|---|---|---|---|---|
| 0 | [`phase_0_bootstrap.md`](./phase_0_bootstrap.md) | bootstrap | `phase/0-bootstrap` | Buildable empty package + runnable testbed + green CI | ⏳ pending |
| 1 | [`phase_1_mvp_handler.md`](./phase_1_mvp_handler.md) | mvp-handler | `phase/1-mvp-handler` | `logger.error()` → real Telegram message (sync) | ⏳ pending |
| 2 | [`phase_2_async_worker.md`](./phase_2_async_worker.md) | async-worker | `phase/2-async-worker` | Non-blocking; daemon-thread + asyncio + retries | ⏳ pending |
| 3 | [`phase_3_topics_html.md`](./phase_3_topics_html.md) | topics-and-html | `phase/3-topics-and-html` | Per-level topic routing + rich HTML + long-msg attachments | ⏳ pending |
| 4 | [`phase_4_batching_ratelimit.md`](./phase_4_batching_ratelimit.md) | batching-ratelimit | `phase/4-batching-ratelimit` | Coalesce + token-bucket; survive thousands/min | ⏳ pending |
| 5 | [`phase_5_dedup_sampling.md`](./phase_5_dedup_sampling.md) | dedup-sampling | `phase/5-dedup-sampling` | Repeated errors → "× N more"; sample noisy levels | ⏳ pending |
| 6 | [`phase_6_security_context.md`](./phase_6_security_context.md) | security-context | `phase/6-security-context` | PII scrubbing + request-context middleware | ⏳ pending |
| 7 | [`phase_7_celery_transport.md`](./phase_7_celery_transport.md) | celery-transport | `phase/7-celery-transport` | Optional Celery transport for users with brokers | ⏳ pending |
| 8 | [`phase_8_admin_health_docs.md`](./phase_8_admin_health_docs.md) | admin-health-docs | `phase/8-admin-health-docs` | Admin stats page + `/health/` JSON + docs site | ⏳ pending |
| 9 | [`phase_9_release.md`](./phase_9_release.md) | release-0.1.0 | `phase/9-release-0.1.0` | PyPI v0.1.0 via Trusted Publisher | ⏳ pending |

Status legend: ⏳ pending · 🚧 in progress · ✅ done

## Per-phase file template

Every phase file follows the same structure:

1. **Header** — phase number, slug, branch name, prerequisites, credentials needed.
2. **Goal** — one paragraph, sharp.
3. **Why this phase** — what problem it solves, what it depends on.
4. **Architecture impact** — what modules change, what the new public API looks like.
5. **Deliverables** — every file to create/modify with a description of its contents.
6. **Public API surface** — exact class signatures and function names.
7. **Test plan** — specific test functions to write.
8. **Acceptance criteria** — the checklist that must pass.
9. **Verification scenario (testbed)** — exact commands to run, expected Telegram output.
10. **Risks & gotchas** — known traps for this phase.
11. **Definition of Done** — final gate from AGENTS.md §6.

## Update rules

- These files are immutable mid-build. If a phase reveals a flaw, **stop and report** to the user — do not silently rewrite earlier phases.
- The user is the only one who can edit phase specs. Agents read-only.
- After a phase merges, edit only this `README.md` (the table) to flip the status to ✅.
