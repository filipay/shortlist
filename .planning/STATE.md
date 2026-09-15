---
gsd_state_version: "1.0"
current_phase: 01
current_phase_name: Walking Skeleton + Foundations
status: executing
stopped_at: Completed 01-05-PLAN.md
last_updated: "2026-09-15T18:27:14.950Z"
last_activity: 2026-09-15
last_activity_desc: Phase 01 execution started
state_head: 3b9948b309028e07fc162d8fc652b43514d2061f
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 7
  completed_plans: 4
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-15)

**Core value:** Every morning there is one ranked, explained, apply-ready queue of jobs worth considering — so the search→judge→tailor loop costs minutes instead of hours.
**Current focus:** Phase 01 — Walking Skeleton + Foundations

## Current Position

Phase: 01 (Walking Skeleton + Foundations) — EXECUTING
Plan: 6 of 7
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
| Phase 01 P04 | 8min | 2 tasks | 12 files |
| Phase 01 P05 | 20 min | 2 tasks | 11 files |

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
- [Phase 01]: The JobSpy row mapper is board-agnostic and lives on its own (app/sources/_jobspy_mapping.py): Indeed importing app.sources.linkedin would have coupled two boards that are meant to be independently upgradable
- [Phase 01]: The Indeed country guard is asserted at the transport boundary — that country_indeed reaches run_scrape — not merely that build_kwargs produces it
- [Phase 01]: registry.get() fails loudly on an unknown source; the single consumer catches UnknownAdapterError so one bad sources row degrades one board only
- [Phase 01]: Exclusive-filter-group resolution is alphabetical and documented rather than board-specific; the CapabilityWarning is the product value, not the drop
- [Phase 01]: compile_query_for_source() + CapabilityWarning ship in Phase 1 and are consumed by the Phase-2 criteria compiler
- [Phase 01]: Truncation is defined over Python characters (code points), not bytes and not grapheme clusters: sanitize_text slices to exactly max_chars and reports truncated=True; the contract is stated in the module and function docstrings and pinned by a multi-byte test (SRC-08)
- [Phase 01]: The sanitise stage emits an aggregate pii_removed count and never the removed value; the PII tests assert against structlog capture_logs (the real event payload), a stdlib-backed caplog bridge and capsys, because structlog has no explicit configuration and its PrintLogger bypasses caplog by default
- [Phase 01]: FastAPI 0.141.1 include_router appends _IncludedRouter wrappers with no .dependant and no .path; tests/test_auth_seam.py recurses through original_router.routes and proves it reached the four leaf routes before asserting Depends(current_user) — confirming the plan-01-04 finding and closing the vacuous-pass hazard
- [Phase 01]: PLAT-04 fix (Rule 2): DEFAULT_QUERY, which hard-coded results_wanted=50 and location='Ireland' in app/pipeline, became default_query() reading settings.probe_results_wanted and the new settings.probe_query_location; no distinctive threshold literal remains in app/pipeline, which the literal-absence scan now enforces
- [Phase 01]: SanitizeResult was renamed to SanitisedText (the plan's contract name) with SanitizeResult kept as an import-compatible alias; the stage keeps the name sanitize_listing rather than gaining a British-spelling duplicate, and a new test asserts no adapter imports the sanitiser so the single named stage cannot silently diverge
- [Phase 01]: No credential path exists under app/: the only AsyncClient call sites pass headers only, and app/config.py's opencode_server_password is the LLM-backend secret rather than a portal credential — so the raw-token scan stays narrow (LINKEDIN_PASSWORD, INDEED_EMAIL, cookies=, CookieJar, ...) instead of flagging bare PASSWORD

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

Last session: 2026-09-15T18:27:14.914Z
Stopped at: Completed 01-05-PLAN.md
Resume file: None
