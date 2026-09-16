---
phase: "2"
slug: "clean-filtered-queryable-queue"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-16"
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `addopts="-m 'not live'"`) |
| **Quick run command** | `.venv-host/bin/pytest -q tests/domain tests/db tests/pipeline` |
| **Full suite command** | `.venv-host/bin/pytest -q` |
| **Estimated runtime** | ~30 s (quick) / ~90 s (full, offline lanes only) |

---

## Sampling Rate

- **After every task commit:** Run `.venv-host/bin/pytest -q tests/domain tests/db tests/pipeline`
- **After every plan wave:** Run `.venv-host/bin/pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green, plus the schema gate
  `.venv-host/bin/pytest -q tests/db/test_migration_contract.py tests/db/test_no_pii_columns.py`
- **Max feedback latency:** 120 seconds
- **Live/operator lane:** `.venv-host/bin/pytest -q -m live` — never in CI (P13)

---

## Per-Task Verification Map

> Seeded by plan-phase; populated with concrete `{N}-{plan}-{task}` IDs by
> `/gsd-validate-phase`. Requirement → command mapping is authoritative here.

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| QUEUE-03 | Cross-source duplicate merges once; twin retained | integration | `pytest tests/pipeline/test_dedup_merge.py -x` | ❌ W0 | ⬜ pending |
| QUEUE-03 | Fuzzy gate: seniority-conflict guard, component gate, subset pathology | unit | `pytest tests/domain/test_dedup.py -x` | ❌ W0 | ⬜ pending |
| QUEUE-04 | Revert restores fields, unhides twin, survives the next run | integration | `pytest tests/pipeline/test_dedup_revert.py -x` | ❌ W0 | ⬜ pending |
| QUEUE-06 | FTS search finds a listing; hostile query does not 500; order stable | unit + api | `pytest tests/domain/test_search_query.py tests/api/test_queue_search.py -x` | ❌ W0 | ⬜ pending |
| QUEUE-07 | New-since-watermark and stale badges | db + api | `pytest tests/db/test_queue_state.py tests/api/test_queue_signals.py -x` | ❌ W0 | ⬜ pending |
| QUEUE-08 | save/hide append events; projection shows current state; UPDATE/DELETE abort | db + api | `pytest tests/db/test_listing_events.py tests/api/test_listing_events.py -x` | ⚠️ append-only half exists in `tests/db/test_migration_contract.py::test_listing_events_append_only`; projection is new | ⬜ pending |
| QUEUE-09 | Merge rate + rows behind it | db + api | `pytest tests/api/test_merges_view.py -x` | ❌ W0 | ⬜ pending |
| CRIT-01 | Create/edit/delete a named search + rules | api | `pytest tests/api/test_searches_crud.py -x` | ❌ W0 | ⬜ pending |
| CRIT-02 | Run stores criteria snapshot; exclusion rows carry `criteria_version` | integration + schema | `pytest tests/pipeline/test_criteria_snapshot.py tests/db/test_migration_contract.py -x` | ❌ W0 | ⬜ pending |
| CRIT-03 | Enable/disable without delete | api | `pytest tests/api/test_searches_crud.py::test_toggle -x` | ❌ W0 | ⬜ pending |
| FILT-01 | Rules reject post-merge, pre-LLM; no LLM call in phase | unit + integration | `pytest tests/domain/test_filter.py tests/pipeline/test_filter_stage.py -x` | ❌ W0 | ⬜ pending |
| FILT-02 | One `listing_exclusions` row per firing rule with detail | db | `pytest tests/db/test_exclusions.py -x` | ❌ W0 | ⬜ pending |
| FILT-03 | Show-excluded toggle names the rule + per-rule counts | api | `pytest tests/api/test_queue_excluded.py -x` | ❌ W0 | ⬜ pending |
| FILT-04 | Rule params read from DB, not code; no distinctive literal in `app/pipeline` | unit + static | `pytest tests/test_config.py tests/domain/test_filter.py -x` | ✅ `test_config.py` exists — extend settings | ⬜ pending |
| RUN-03 | Reason enum + counts persisted and rendered | unit + api | `pytest tests/domain/test_run_reason.py tests/api/test_run_reason.py -x` | ❌ W0 | ⬜ pending |
| RUN-04 | `/runs` history page + last-run strip | api | `pytest tests/api/test_run_history.py -x` | ❌ W0 | ⬜ pending |
| SRC-09 (D-37) | Capability warning surfaced, not silently dropped | unit + integration | `pytest tests/sources/test_capabilities.py tests/pipeline/test_capability_surface.py -x` | ⚠️ `compile_query_for_source` unit-tested; *consumption* is new | ⬜ pending |
| SRC-08 (D-38) | Injection rule set flags without mutating | unit | `pytest tests/domain/test_sanitize.py tests/domain/test_injection_patterns.py -x` | ⚠️ `test_sanitize.py` exists; add pattern-catalogue cases | ⬜ pending |
| Guards | Migration 0002 contract, PII allow-list, import purity, auth seam, no-CDN | schema/static | `pytest tests/db/test_migration_contract.py tests/db/test_no_pii_columns.py tests/test_import_discipline.py tests/test_auth_seam.py tests/test_no_credentials.py tests/test_no_cdn.py -x` | ✅ all exist — **must be updated alongside 0002** | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/domain/test_search_query.py` — the 8 verified-hostile inputs + the `None` branch (QUEUE-06)
- [ ] `tests/domain/test_dedup.py` — seniority-conflict guard, component gate, subset pathology (QUEUE-03)
- [ ] `tests/domain/test_filter.py` — six rule kinds, unknown-value policy, malformed `params_json` (FILT-01/02)
- [ ] `tests/domain/test_run_reason.py` — every enum branch + precedence (RUN-03)
- [ ] `tests/domain/test_injection_patterns.py` — the 8 upstream regexes, flag-not-mutate (SRC-08/D-38)
- [ ] `tests/db/test_migration_contract.py` — **edit** item 9 + new items 10–13 (Q2 guard churn)
- [ ] `tests/db/test_no_pii_columns.py` — **edit** `EXPECTED_JSON_COLUMNS` (Q2 guard churn)
- [ ] `tests/db/test_queue_state.py`, `tests/db/test_exclusions.py`, `tests/db/test_listing_events.py`, `tests/db/test_dupes.py` — repository lanes
- [ ] `tests/pipeline/test_dedup_merge.py`, `test_dedup_revert.py`, `test_filter_stage.py`, `test_criteria_snapshot.py`, `test_capability_surface.py` — stage lanes (reuse `session_factory` + `registry_snapshot`)
- [ ] `tests/api/` — `test_queue_search.py`, `test_queue_signals.py`, `test_queue_excluded.py`, `test_listing_events.py`, `test_searches_crud.py`, `test_run_history.py`, `test_run_reason.py`, `test_merges_view.py` (reuse `client`)
- [ ] `tests/test_config.py` — **edit**: add the new required settings fields to `REQUIRED_SETTINGS_FIELDS` / `LIMIT_FIELDS`
- [ ] Framework install: `.venv-host/bin/python -m pip install 'rapidfuzz==3.14.6'` (gated by `checkpoint:human-verify` — package-legitimacy verdict `SUS`)

*(No shared-fixture work is needed: `migrated_db`, `session_factory`, `db_session`, `client`, `registry_snapshot` and the offline LLM stub already cover every lane.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dedup threshold θ tuned against the first real corpus | QUEUE-03 | No real corpus exists pre-run; θ must be a setting with a recorded tuning procedure, not a frozen constant (STATE.md Phase-2 blocker) | Run a real pipeline run, inspect `listing_dupes` pairs + merge rate, record chosen θ and band in `docs/` |
| Merge-rate band sanity check | QUEUE-09 | The 10–15% band in research comes from a different market/query shape | After a real run, compare observed merge rate against the recorded θ; adjust or record why not |
| dependency-legitimacy human check for `rapidfuzz` | Tier-2 dedup | Package-legitimacy gate returned `SUS` (`too-new`, `unknown-downloads`) | Confirm the pin `rapidfuzz==3.14.6` and licence (MIT) before install; `checkpoint:human-verify` |
| Compose smoke of the running stack | PLAT-01 carry-over | WINDOWS.md open item #1 — the compose smoke is still unrun | `docker compose up` and browse the queue; record the result |

*If a row above is discharged in-phase, record the evidence path in the plan's SUMMARY.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
