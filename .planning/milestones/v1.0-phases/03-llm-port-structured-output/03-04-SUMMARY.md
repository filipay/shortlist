---
phase: 03-llm-port-structured-output
plan: 04
subsystem: database
tags: [alembic, migration, llm_calls, telemetry, repository, tdd, d-12]

# Dependency graph
requires:
  - phase: 03-llm-port-structured-output
    provides: "plan 03-01's LlmCallRecord / record_llm_call and the /settings probe read it replaces"
provides:
  - "Migration 0003: llm_calls.server_version VARCHAR(32), nullable and additive with a symmetric downgrade"
  - "LlmCall.server_version, so the ORM drift guard enforces that model and migration move together"
  - "llm_call_repo.latest_probe and llm_call_repo.llm_totals_for_run — the shared reads the selftest and Phase 5 consume"
  - "record_llm_call persists server_version; _settings_context reads the probe through the repository contract"
affects: [03-05, 03-06, 03-07, 05-ranking]

# Actuals (#2632) — same estimateTokens scale (chars/4) as the plan's estimate.
actuals:
  tokens: 4069
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Schema change lands as a paired migration + ORM mirror, with the drift guard as the enforcement mechanism (T-3-15)"
    - "One _to_record mapping shared by the write and the reads, so they cannot disagree about a field"
    - "Reads are total: a half-written row totals as 0 rather than raising"
    - "Repositories own SQL, never commit; `_settings_context` reads through the repository, not ad-hoc SQL"

key-files:
  created:
    - alembic/versions/0003_llm_call_server_version.py
    - tests/db/test_llm_call_repo.py
  modified:
    - app/db/models.py
    - app/db/repositories/llm_call_repo.py
    - app/api/settings.py
    - tests/db/test_migration_contract.py
    - tests/db/test_skeleton_boot.py

key-decisions:
  - "Task 1's decision gate: the user selected `migration-0003` (add migration 0003 with the nullable column). Rationale: every existing text column has a distinct meaning another surface relies on — `backend` is the transport, `provider` is the provider id, and `error` is NULL on the successful rows where the version is most needed — so overloading one would corrupt the field the Phase-5 operator reads. The column is additive, queryable, backfill-free and symmetrically reversible."
  - "The version column is `VARCHAR(32)`, never a JSON column, so test_no_pii_columns' exact-equality `llm_calls: frozenset()` allow-list needs no edit and a future free-form blob would fail the guard."
  - "`llm_totals_for_run` is the READ only; no `runs.llm_calls`/`runs.llm_tokens` writer ships here — `_finish` is Phase 5's caller through the seam, keeping D-49's pipeline-LLM-free rule intact."

patterns-established:
  - "A one-way schema change is preceded by a blocking decision checkpoint and lands with its ORM mirror in the same task"
  - "The read shape D-52 renders and Phase 5 consumes is one repository function, not two divergent queries"

requirements-completed: [PLAT-02]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "Migration 0003 adds a nullable llm_calls.server_version VARCHAR(32) and its downgrade drops exactly that column; alembic reports one head starting 0003."
    requirement: PLAT-02
    verification:
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_llm_calls_server_version_column_is_nullable"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_alembic_at_latest_revision"
        status: pass
      - kind: manual_procedural
        ref: ".venv/bin/python -m alembic upgrade head / downgrade 0002 / heads against a temp DATABASE_URL_SYNC"
        status: pass
    human_judgment: false
  - id: D2
    description: "The ORM mirrors the migrated schema, and llm_calls still has zero JSON columns."
    requirement: PLAT-02
    verification:
      - kind: integration
        ref: "tests/db/test_orm_drift.py#test_orm_matches_the_migrated_schema (no edit)"
        status: pass
      - kind: integration
        ref: "tests/db/test_no_pii_columns.py (no edit)"
        status: pass
    human_judgment: false
  - id: D3
    description: "server_version round-trips: record_llm_call persists it and latest_probe reads it back unchanged."
    requirement: PLAT-02
    verification:
      - kind: integration
        ref: "tests/db/test_llm_call_repo.py#test_server_version_round_trips_through_latest_probe"
        status: pass
    human_judgment: false
  - id: D4
    description: "The audit writer's shared reads are total and correct: latest_probe picks the most recent probe only (None on empty, id tie-break), and llm_totals_for_run sums only that run's rows with NULL tokens as 0 and run_id-NULL probes excluded."
    requirement: PLAT-02
    verification:
      - kind: integration
        ref: "tests/db/test_llm_call_repo.py#test_latest_probe_returns_the_most_recent_probe_row_only"
        status: pass
      - kind: integration
        ref: "tests/db/test_llm_call_repo.py#test_llm_totals_for_run_sums_only_that_runs_rows"
        status: pass
      - kind: integration
        ref: "tests/db/test_llm_call_repo.py#test_a_null_run_probe_never_appears_in_run_totals"
        status: pass
    human_judgment: false
  - id: D5
    description: "The /settings page reads its probe detail through llm_call_repo.latest_probe, and the rendered page is unchanged."
    requirement: PLAT-02
    verification:
      - kind: integration
        ref: "tests/api/test_llm_selftest.py (unchanged, green)"
        status: pass
      - kind: integration
        ref: "tests/api/test_settings_page.py (unchanged, green)"
        status: pass
    human_judgment: false

# Metrics
duration: 8 min
completed: 2026-09-17
status: complete
---

# Phase 3 Plan 04: LLM Port + Structured Output Summary

**`llm_calls.server_version` is now a real, nullable, queryable column that the ORM mirrors, the audit writer round-trips, and the `/settings` probe read renders — so a future model/version regression is traceable to the opencode server that produced it (D-12 / M9).**

## Performance

- **Duration:** 8 min
- **Started:** 2026-09-17T22:31:02Z
- **Completed:** 2026-09-17T22:39Z
- **Tasks:** 3 (Task 1 a decision gate resolved by the user; Tasks 2 and 3 executed, Task 3 TDD)
- **Files created/modified:** 7 (2 created, 5 modified)
- **Full suite:** 789 passed, 3 deselected (~105 s; plan 03-03 baseline was 777 passed, 3 deselected)

## Accomplishments

- **Migration 0003 shipped cleanly.** `upgrade()` adds one nullable `VARCHAR(32)`; `downgrade()` drops exactly that column; `alembic heads` reports a single head `0003`. Verified by applying, downgrading to 0002 and re-applying against a temp database.
- **The ORM move is enforced, not assumed.** `LlmCall.server_version` lands in the same task, so `test_orm_drift.py`'s per-table column-name equality is the mechanism that would have failed a "migration only" change (T-3-15).
- **`llm_calls` still has zero JSON columns.** `test_no_pii_columns.py` is green with **no edit** — the bounded `VARCHAR(32)` cannot become a payload sink.
- **The audit reader surface is complete and total.** `record_llm_call` persists `server_version` through one `_to_record` mapping; `latest_probe` returns the most recent probe row (or `None`) with an `(created_at, id)` tie-break; `llm_totals_for_run` returns `(call_count, total_tokens)` for one run, treating NULL tokens as 0 and structurally excluding `run_id IS NULL` probes.
- **One read shape for D-52.** `_settings_context` now calls `llm_call_repo.latest_probe` instead of owning a second query, and the rendered page is unchanged — and, as a side effect, the server version now survives a reload because it is a persisted column.

## Task Commits

1. **Task 1: Confirm the one-way schema change (checkpoint:decision)** — no commit; resolved by the user (see Decisions Made).
2. **Task 2: Migration 0003, the ORM mirror and the guard churn** — `d03edef` (feat)
3. **Task 3: The read helpers and the repository contract test** — `98b3d53` (test, RED) → `006b318` (feat, GREEN)

**Plan metadata:** the `docs(03-04)` commit immediately following this file (SUMMARY + STATE + ROADMAP + REQUIREMENTS).

## Files Created/Modified

- `alembic/versions/0003_llm_call_server_version.py` — **created**; the additive nullable column with a symmetric downgrade
- `tests/db/test_llm_call_repo.py` — **created**; the writer/read contract (11 tests)
- `app/db/models.py` — **modified**; `LlmCall.server_version = Column(String(32))`
- `app/db/repositories/llm_call_repo.py` — **modified**; `_to_record`, `_tolerant_int`, `latest_probe`, `llm_totals_for_run`; `record_llm_call` now persists `server_version`
- `app/api/settings.py` — **modified**; `_settings_context` reads through `llm_call_repo.latest_probe`, and the ad-hoc query is deleted
- `tests/db/test_migration_contract.py` — **modified**; the three revision assertions become `0003`, and item 14 pins the new column by name
- `tests/db/test_skeleton_boot.py` — **modified** (deviation); the revision assertion becomes `0003`

## Decisions Made

- **Task 1's gate: `migration-0003` was selected.** The one-way-door decision was presented to the human and answered before execution. The plan's stated rationale stands: `backend` means "which transport", `provider` is the provider id, and `error` is NULL on the successful rows where the version matters most, so overloading any of them would corrupt the field the Phase-5 operator reads. A dedicated nullable column is additive, queryable (`GROUP BY server_version`), backfill-free and symmetrically reversible.
- **Reads are shared, not duplicated.** `latest_probe`/`llm_totals_for_run` live in the repository so the selftest, `/settings` and Phase 5 all read the same shape; the plan ships the read seam, not a writer for `runs.llm_calls`/`runs.llm_tokens` (D-49 keeps the pipeline LLM-free).
- **`server_version` is the only new column, and it is bounded.** No JSON blob, no backfill, no CHECK change.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `tests/db/test_skeleton_boot.py` pinned the migration revision**
- **Found during:** Task 3 verify (`pytest -q tests/db tests/api/test_settings_page.py -x`)
- **Issue:** `test_migration_creates_every_table_at_latest_revision` asserts `version == [("0002",)]`. The plan's guard-churn table (and the research table it came from) listed `test_skeleton_boot.py` as needing **no** edit, but that referred to its table list; its revision assertion is a second, separate guard that the migration trips.
- **Fix:** bumped the assertion to `[("0003",)]`.
- **Files modified:** `tests/db/test_skeleton_boot.py`
- **Verification:** `tests/db` + `tests/api/test_settings_page.py` 125 passed; full suite green.
- **Committed in:** `006b318` (Task 3 GREEN)

**2. [Rule 3 - Blocking] `alembic upgrade head` targets an absent database path in the sandbox**
- **Found during:** Task 2 verify
- **Issue:** the plan's literal command uses the configured `sqlite:////data/jobsearch.db`, and `/data` does not exist in this sandbox (`OperationalError: unable to open database file`). `alembic heads` is unaffected.
- **Fix:** ran the same migration against a temp file via `DATABASE_URL_SYNC` — the exact mechanism `tests/conftest.py` uses — and additionally proved the downgrade is symmetric (`upgrade head` → `0003`, `downgrade 0002` removes the column, re-`upgrade head` restores it).
- **Files modified:** none (environment adaptation, no code change)
- **Verification:** the pytest lane already exercises `alembic upgrade head` against temp databases via the session-scoped fixture.
- **Committed in:** n/a

**3. [Rule 2 - Missing critical] The plan's guard table under-counted the deliberate churn**
- **Found during:** Task 2 (reading the guard suite) and Task 3 (discovery of the skeleton-boot assertion)
- **Issue:** the plan listed three `test_migration_contract.py` assertions; the actual deliberate churn is four assertions across two files plus a new item-14 test.
- **Fix:** updated all of them explicitly, and left `test_orm_drift.py` / `test_no_pii_columns.py` untouched so their greenness remains the proof of a correctly paired change.
- **Files modified:** `tests/db/test_migration_contract.py`, `tests/db/test_skeleton_boot.py`
- **Verification:** full guard suite green.
- **Committed in:** `d03edef`, `006b318`

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 missing-critical)
**Impact on plan:** None changed the schema design. Items 1 and 3 are the same deliberate guard churn the plan anticipated, just one guard larger; item 2 is a sandbox path limitation with the migration proven by the pytest lane and a temp-file run.

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Notes |
|------|-----|-------|----------|-------|
| 2 | n/a (not TDD) | `d03edef` (feat) | — | A schema change has no behavioural RED; its proof is the guard suite, which was updated and run inside the task. |
| 3 | `98b3d53` (test) | `006b318` (feat) | — | RED was a **genuine assertion failure**: 7 target tests failed because `latest_probe`/`llm_totals_for_run` did not exist; the 4 already-implemented write-contract tests passed. |

## Issues Encountered

- **`error_kind` is still not persisted.** The `/settings` page shows the operator-facing cause only on the immediate POST response, because `llm_calls` has no `error_kind` column and no plan in this phase adds one. This plan closes the `server_version` half of D-52's reload story; the `error_kind` half remains an in-memory-only detail carried from plan 03-01.
- **The `/data` path is unavailable in the sandbox**, so the plan's literal `alembic upgrade head` cannot be run as written. The migration is nevertheless exercised end to end by the pytest lane (which runs the real `alembic upgrade head` against a temp database) and by the temp-file upgrade/downgrade/re-upgrade check.

## Known Stubs

None. Every deliverable in this plan is implemented, migrated and tested; `llm_totals_for_run` is a shipped read whose caller (`_finish`) is deliberately Phase 5's, per the plan.

## Threat Flags

None — no new surface. This plan mitigates T-3-09 (decision gate + additive nullable column + symmetric downgrade), T-3-05 (no JSON column; allow-list untouched), T-3-15 (ORM drift guard) and T-3-16 (`server_version` plus the existing identity columns make a call attributable), all already in the plan's threat register.

## User Setup Required

None - no external service configuration required. The operator does **not** need to run the migration manually: the app's container entrypoint runs `alembic upgrade head`.

## Next Phase Readiness

- **D-12's telemetry gap is closed.** A recorded call now carries the server version it was made against, and the value survives a page reload because it is a persisted column rather than a transient field.
- **The read seam Phase 5 needs exists.** `llm_totals_for_run` is ready for `_finish` to call; `latest_probe` is the single read shape `/settings` and any future operator surface can share.
- **`PLAT-02` stays open by design.** It is declared by six plans; the shared-ID gate keeps it incomplete until the last declaring sibling (03-05..03-07) has a SUMMARY.md.

---
*Phase: 03-llm-port-structured-output*
*Completed: 2026-09-17*

## Self-Check: PASSED

- All seven plan files exist on disk (`alembic/versions/0003_llm_call_server_version.py`, `tests/db/test_llm_call_repo.py`, `app/db/models.py`, `app/db/repositories/llm_call_repo.py`, `app/api/settings.py`, `tests/db/test_migration_contract.py`, `tests/db/test_skeleton_boot.py`).
- All three plan commits are present (`d03edef`, `98b3d53`, `006b318`).
- Measured commit count from the plan ledger: 3 (`git rev-list --count 6b6313f..HEAD`).
