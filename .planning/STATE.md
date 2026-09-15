---
gsd_state_version: "1.0"
current_phase: 01
current_phase_name: Walking Skeleton + Foundations
status: executing
stopped_at: Completed 01-03-PLAN.md
last_updated: "2026-09-15T17:48:23.081Z"
last_activity: 2026-09-15
last_activity_desc: Phase 01 execution started
state_head: 3af6467b1fd2e21212f0a925ab25e6040b1c221c
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 7
  completed_plans: 3
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-15)

**Core value:** Every morning there is one ranked, explained, apply-ready queue of jobs worth considering — so the search→judge→tailor loop costs minutes instead of hours.
**Current focus:** Phase 01 — Walking Skeleton + Foundations

## Current Position

Phase: 01 (Walking Skeleton + Foundations) — EXECUTING
Plan: 4 of 7
Status: Ready to execute
Last activity: 2026-09-15 — Phase 01 execution started

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 23 min | 3 tasks | 40 files |
| Phase 01 P02 | 5 min | 2 tasks | 3 files |
| Phase 01 P03 | 15 min | 3 tasks | 34 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Ranking (Phase 5) precedes tailoring (Phase 6) — tailoring consumes the requirement gaps ranking produces.
- [Roadmap]: Phase 4 (CV fact store + LaTeX spike) runs **in parallel** with Phases 2–3; it is a shared prerequisite and the largest unquantified cost.
- [Roadmap]: Scheduling is late (Phase 8) on purpose — a cron job over an unstable pipeline hides failures.
- [Phase 01]: Alembic's sync engine now applies the app's PRAGMAs (WAL + synchronous=NORMAL), so the first migration lands in the D-17 configuration; this also cut migration wall-clock from ~16s to ~5s
- [Phase 01]: The PRAGMA autocommit toggle is getattr-guarded: pysqlite needs it for foreign_keys=ON, but SQLAlchemy's aiosqlite adapter exposes no autocommit attribute
- [Phase 01]: conftest uses a session-scoped migrated template DB plus a per-test file copy, so each test gets an empty migrated database without re-running alembic (full suite stays inside the 30s lane)
- [Phase 01]: listing_sources.source keeps its FK to sources.name, so ingestion must register the source row first; foreign_keys=ON is genuinely enforced
- [Phase 01]: Migration-contract tests introspect the migrated temp DB (PRAGMA/sqlite_master) and never the ORM metadata, so model/DDL drift fails the contract
- [Phase 01]: The JSON-column set is asserted by exact equality against a per-table allow-list, so a new free-form blob (the realistic PII vector) fails the PII-negative test until added deliberately
- [Phase 01]: Queue-ordering tie-break and content_hash stability/difference are delegated to plan 01-03 (queue read + app/domain/listing.py); tracked as human_judgment coverage here, schema half asserted
- [Phase 01]: One runs row per trigger: POST /runs commits the row and passes run_id to run_pipeline, which updates it; without this both created a row and the polled run never terminated
- [Phase 01]: The JobSpy transport keeps its top-level import (one-importer grep holds) but is loaded lazily via an injectable factory, because tls_client cannot load libresolv.so.2 in the sandbox; production behaviour is unchanged
- [Phase 01]: Persistence is SAVEPOINT-per-item: listing_sources.source is a live FK, so a failed insert could otherwise commit an orphan listings row
- [Phase 01]: FINDING for plan 01-05: FastAPI 0.141.1 include_router yields _IncludedRouter objects with no .dependant, so a naive app.routes walk finds zero APIRoutes and a test_auth_seam.py written that way passes vacuously; recurse via original_router.routes

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1] Blocking unknown #2 — scrape survival at personal scale is unmeasured; the Phase 1 probe answers it and re-ranks Adzuna from hedge to primary if LinkedIn/Indeed fail.
- [Phase 4] Blocking unknown #1 — the real `.tex` is **not in this repo**; `.tex → cv.yaml` import cost and Tectonic bundle coverage are unmeasured. Spike on one section is a hard gate before Phase 6 is estimated.
- [Phase 3] `format` vs `outputFormat` in the opencode structured-output contract is unresolved; resolve against the running server and pin with a `/doc` contract test.
- [Phase 5] Ranking batching (one call per listing vs per K) and budget-cap semantics are unresolved; decide in the plan.
- [Phase 2] Dedup threshold θ and the merge-rate band are untunable without a real corpus; leave as a setting + tuning task.

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-09-15T17:48:23.040Z
Stopped at: Completed 01-03-PLAN.md
Resume file: None
