---
phase: "1"
slug: "walking-skeleton-foundations"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-15"
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `01-RESEARCH.md` §Validation Architecture. Task IDs / Plan / Wave
> columns are filled once `01-*-PLAN.md` files exist.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| **Config file** | none — Wave 0 adds `[tool.pytest.ini_options]` to `pyproject.toml` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`, `live` marker) |
| **Quick run command** | `pytest -q tests/domain tests/db tests/sources tests/test_import_discipline.py` |
| **Full suite command** | `pytest -q` |
| **Live / operator lane** | `pytest -q -m live` — never in CI (P13) |
| **Schema gate** | `pytest -q tests/db/test_migration_contract.py` |
| **Container smoke (operator-run)** | `docker compose up -d --wait && curl -fsS localhost:8000/health` |
| **Estimated runtime** | quick lane ~15 s; full suite ~60–90 s |

---

## Sampling Rate

- **After every task commit:** Run `pytest -q tests/domain tests/db tests/sources tests/test_import_discipline.py` (offline, no network, < 30 s)
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green **plus** the two non-test gates: (a) the 9-item migration checklist asserted in `tests/db/test_migration_contract.py`, and (b) the dated probe verdict document committed to the repo
- **Max feedback latency:** 30 seconds (quick lane)
- **Never in CI:** any test that contacts LinkedIn or Indeed (`-m live` is operator-run only)

---

## Per-Task Verification Map

> Task IDs, Plan and Wave are resolved by `validate-phase` once plans exist. Until
> then, each row is keyed by its requirement so coverage is auditable now.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | 01 | 1 | SRC-01 | — | Fixture-driven; no network in tests | unit | `pytest tests/sources/test_linkedin.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | SRC-02 | — | Fixture-driven; no network in tests | unit | `pytest tests/sources/test_indeed.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | SRC-03 | — | One normalised shape across sources | unit | `pytest tests/domain/test_normalize.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | SRC-04 | — | Registry extensibility; no core change | unit + introspection | `pytest tests/sources/test_registry.py tests/test_import_discipline.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | SRC-05 | — | Partial result, never abort the run | integration | `pytest tests/pipeline/test_partial_failure.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | SRC-06 | T-01-01 | No credential path anywhere | static scan | `pytest tests/test_no_credentials.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | SRC-07 | — | Health strip + probe detectable | unit + api | `pytest tests/probe/test_signals.py tests/api/test_health.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | SRC-08 | T-01-02 | Untrusted text sanitised at one boundary | unit | `pytest tests/domain/test_sanitize.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | SRC-09 | — | Capabilities declared; unsupported filter warned | unit | `pytest tests/sources/test_capabilities.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | SRC-10 | T-01-03 | PII stripped; never stored (unrepresentable) | unit + negative schema | `pytest tests/domain/test_sanitize_pii.py tests/db/test_no_pii_columns.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | QUEUE-01 | — | Queue persists across restart | integration | `pytest tests/db/test_persistence.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | QUEUE-02 | — | Two-key upsert; `id=None` case is mandatory | integration | `pytest tests/db/test_two_key_upsert.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | QUEUE-05 | — | `first_seen_at`/`last_seen_at`/`content_hash` NOT NULL | schema contract | `pytest tests/db/test_migration_contract.py::test_listings_timestamps_not_null -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 2 | RUN-01 | — | Manual trigger from the UI | api integration | `pytest tests/api/test_run_trigger.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 2 | RUN-02 | — | Response returns before pipeline finishes; `/health` stays responsive | api integration | `pytest tests/api/test_run_backgrounded.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 2 | PLAT-01 | — | App not exposed beyond host; opencode port unpublished | operator smoke | `docker compose up -d --wait && curl -fsS localhost:8000/health` | ❌ W0 | ⬜ pending |
| TBD | 01 | 2 | PLAT-03 | T-01-04 | Every route carries the auth seam | route introspection | `pytest tests/test_auth_seam.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 2 | PLAT-04 | — | Limits/thresholds/engine are config | unit + grep assertion | `pytest tests/test_config.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 2 | UI-07 | — | Assets vendored; no CDN | static scan | `pytest tests/test_no_cdn.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | D-20 item 6 | — | Both dedup indexes exist (partial + unconditional) | schema contract | `pytest tests/db/test_migration_contract.py::test_dedup_indexes -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | D-20 items 2,3,4,5,7,8 | — | Append-only events, score decomposition, artifact link, source metadata, indexed `blocking_key` | schema contract | `pytest tests/db/test_migration_contract.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 2 | D-11 | T-01-05 | Raw `/config/providers` response never logged/persisted | unit + log scan + DB scan | `pytest tests/llm/test_discovery_redaction.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | P8 / M8 | — | PRAGMAs applied on every connection (WAL, FK ON, busy_timeout) | unit (live temp DB) | `pytest tests/db/test_pragmas.py -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | Probe | — | Each WARN/FAIL boundary fires at the right value | unit (fixture-driven) | `pytest tests/probe/test_thresholds.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — exact pins for the Standard Stack; `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`, `live` marker); `[tool.ruff]`
- [ ] `tests/conftest.py` — async-Engine fixture backed by a **temp file** (not `:memory:`), PRAGMAs applied, schema created via **`alembic upgrade head`** (never `create_all`)
- [ ] `tests/db/test_migration_contract.py` — the 9-item checklist as assertions (highest-value test in the phase)
- [ ] `tests/fixtures/listings/*.json` — captured/hand-built raw payloads per source, `emails` stripped, committed; never fetched in CI
- [ ] `tests/sources/test_linkedin.py`, `tests/sources/test_indeed.py` — fixture-driven; include `id=None`, empty description, `country_indeed` regression guard
- [ ] `tests/test_import_discipline.py` — AST walk asserting `app.domain.*` imports none of `httpx | sqlalchemy | jobspy | jinja2 | subprocess` (D-24)
- [ ] `tests/test_no_credentials.py`, `tests/test_no_cdn.py`, `tests/test_auth_seam.py` — the three static/introspection guards
- [ ] `tests/probe/test_thresholds.py` — one test per WARN/FAIL boundary
- [ ] `static/vendor/` — vendored `htmx.min.js` / `alpine.min.js` + built `app.css`
- [ ] `scripts/compose-smoke.sh` + runbook note — operator-run PLAT-01 check
- [ ] Framework install (`pytest`, `pytest-asyncio`, `ruff`) before any of the above

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Whole stack starts with one `docker compose up` and `/health` answers | PLAT-01 | Docker unavailable in the agent sandbox | Run `scripts/compose-smoke.sh` (or `docker compose up -d --wait && curl -fsS localhost:8000/health`); confirm HTTP 200 + healthy JSON, then `docker compose restart` and confirm listings persist |
| Scraper-survival verdict on LinkedIn/Indeed | SRC-07 (probe) | A live measurement against hostile third-party sites; must never be a CI test (P13) | Operator runs `pytest -q -m live` (or the probe task) on ≥3 distinct days; record raw evidence in `runs`/`source_request_log` + `probe()` status; write the dated verdict document with the Adzuna promotion condition |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
