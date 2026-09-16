---
gsd_state_version: "1.0"
current_phase: 2
current_phase_name: Clean, Filtered, Queryable Queue
status: executing
stopped_at: Completed 02-02-PLAN.md
last_updated: "2026-09-16T09:19:11.153Z"
last_activity: 2026-09-16
last_activity_desc: Phase 2 execution started
state_head: a7df39dda65193fd0affc07d41fe18a9c34caa2a
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 17
  completed_plans: 9
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-15)

**Core value:** Every morning there is one ranked, explained, apply-ready queue of jobs worth considering — so the search→judge→tailor loop costs minutes instead of hours.
**Current focus:** Phase 2 — Clean, Filtered, Queryable Queue

## Current Position

Phase: 2 (Clean, Filtered, Queryable Queue) — EXECUTING
Plan: 3 of 10
Status: Ready to execute
Last activity: 2026-09-16 — Phase 2 execution started

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 7
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 7 | - | - |

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
| Phase 01 P05 | 22 min | 2 tasks | 11 files |
| Phase 01 P06 | 22 min | 3 tasks | 20 files |
| Phase 01 P07 | 22 min | 3 tasks | 35 files |
| Phase 02 P01 | 8 min | 3 tasks | 8 files |
| Phase 02 P02 | 4 min | 2 tasks | 3 files |

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
- [Phase 01]: probe_all() resolves sources in three documented steps — an explicit names list, else the enabled sources rows when a session_factory is given (the /health path), else every registered adapter — and skips an enabled row with no adapter rather than reporting it; only a freshly probed source is written back, so last_probe_at keeps meaning 'when the probe ran' and a cache hit costs no write
- [Phase 01]: The /health body renames 01-03's 'database' key to 'db' (the plan's shape) and keeps the app's own status independent of the LLM backend (D-08: an unreachable opencode is reported inside the opencode object, not as a degraded app); one consumer assertion in tests/api/test_run_backgrounded.py was updated
- [Phase 01]: Discovery redaction is a type-level property: ProviderModel has exactly provider_id and model_id with extra='forbid' (so feeding it a raw provider entry raises rather than dropping the secret), parse_providers() is pure and copies only identifiers, and the sentinel scan covers capture_logs, a caplog bridge, stdout, vars(backend) and every table
- [Phase 01]: 01-05's no-credentials guard was refined: bare 'auth' is scoped out of the keyword-name vocabulary because httpx takes a config-supplied credential as auth= (the allowed local opencode password, D-07), while an auth-named env read, a portal kwarg (username/password/token/cookie/credentials) and a login()/sign_in() call still fail — a new control test pins that the carve-out cannot widen
- [Phase 01]: tests/conftest.py now overrides get_llm_backend() with an offline stub, so no default-lane test opens a socket; the queue route reads persisted health only and never probes a board (the live probe belongs to TTL-cached /health), and get_llm_backend() lives in app/llm/__init__.py as the overridable seam
- [Phase 01]: source_repo computes fill-rate live over the latest run's normalised records (a blank description counts as empty, 1 of 2 not 2 of 2); field_fill_baseline_json and baseline_recorded_at remain plan 01-07's record_baseline() — the key_link in the plan names that column, but the baseline is S2's signal work
- [Phase 01]: RESIDUAL for plan 01-07: the adapter probe() asserts status, minimum body length and the absence of stop signals, but not a POSITIVE structural marker (3 of the 4 RESEARCH signals). Choosing a marker needs a real page to inspect, so it is recorded as an explicit human_judgment coverage entry rather than guessed into app/sources
- [Phase 01]: app/db/repositories/source_repo.py was created in task 1 (the task's own action requires the probe write path through the source repository) and extended in task 3 with SourceHealth + get_source_health(); probe_all persists through a lazy import so the probe module imports with or without the repo
- [Phase 01]: Every S1-S6 and P-1..P-5 boundary is read from Settings via thresholds(), and there is no absolute fill-rate target anywhere: every judgement is a delta against the recorded baseline or a trailing average, because JobSpy's description-salary extraction is USA-only so an Irish search is structurally low
- [Phase 01]: The politeness ledger lives in app/sources/_ledger.py rather than inside _jobspy_transport.py, and classify_response moved to app/sources/base.py, because the transport imports jobspy (whose native TLS library cannot load in the sandbox) — a ledger there would be untestable and the survival signals could not classify a fetch outcome
- [Phase 01]: The scraper-survival verdict is PROVISIONAL at 1 run on 1 distinct day, and its first run is explicitly marked non-representative because it predates the DataFrame-row fix (created 1/updated 33 is the bug signature); a single run is never presented as a measurement and the Adzuna decision stays deferred to Phase 8
- [Phase 01]: probe() is not a reliable proxy for fetch(): in the same container session /health reported indeed unreachable and linkedin degraded at 21:02:36 while runs.id=1 had fetched 50 usable listings from EACH board at 21:02:01. The verdict is unaffected (it derives from runs + source_request_log) but the health badge can mislead and P-4 is unusable until resolved — recorded as WINDOWS #4, same family as #3
- [Phase 01]: frame_rows() + UnsupportedFrameError is now the single explicit DataFrame-to-rows conversion point with no silent-empty fallback, after list(frame) was found to iterate COLUMN LABELS (every field None, one blank listing per board); DESIRED_ORDER was completed to the full jobspy.util.desired_order and pinned by a contract test
- [Phase 01]: The pinned dependency is python-jobspy, not jobspy (the PyPI jobspy is an unrelated 2016 Redis package, and pip had been discarding the real candidate after a swallowed MetadataInconsistent), and the Dockerfile must stay classic-builder safe: no BuildKit heredocs, asserted by tests/test_deploy_manifest.py
- [Phase 01]: ensure_registered_sources() seeds the sources allow-list from the adapter registry on app startup and before a probe run: nothing in production ever inserted a sources row, so enabled_source_names() was empty and a fresh deployment silently ingested nothing
- [Phase 2]: Migration 0002 is additive and pairs with its guard churn: five Phase-1 schema guards (four named plus test_skeleton_boot.py) updated deliberately alongside it, not treated as regressions
- [Phase 2]: dedup_fuzzy_threshold is a Settings value (default 88) with a tuning task, never a frozen constant (D-31); the named ck_runs_reason CHECK survived a batch table recreation that preserved ck_runs_trigger/ck_runs_status
- [Phase 2]: rapidfuzz==3.14.6 is Phase 2 only new runtime dependency: the SUS legitimacy verdict was cleared by a blocking human checkpoint before install, and the exact pin is declared in both pyproject.toml and requirements.txt
- [Phase 2]: rapidfuzz is installed in BOTH .venv-host (the plan must-have) and .venv (the only venv the suite runs in), because .venv-host has a broken pydantic_core compiled dependency

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

Last session: 2026-09-16T09:19:11.095Z
Stopped at: Completed 02-02-PLAN.md
Resume file: None
