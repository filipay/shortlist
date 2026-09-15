---
phase: 01-walking-skeleton-foundations
plan: 03
subsystem: pipeline
tags: [adapter-port, jobspy, registry, sanitise, normalisation, two-key-upsert, run-pipeline, htmx, fastapi, structlog]

# Dependency graph
requires:
  - phase: 01-walking-skeleton-foundations (plan 01)
    provides: "migration 0001 (incl. FTS5 and both dedup indexes); the async engine + PRAGMAs; the two-key repository; current_user(); the app factory; the vendored HTMX asset"
  - phase: 01-walking-skeleton-foundations (plan 02)
    provides: "the schema contract, PII-negative schema guarantee and FTS5 maintenance proof this plan's persistence relies on"
provides:
  - "app/sources/base.py — the D-18 port: SourceCapabilities (declared, with exclusive filter groups), SearchQuery, FetchBudget, RawListing (no PII field of any kind), the total FetchResult, the JobSource ABC and pure capability/error classifiers"
  - "app/sources/_jobspy_transport.py — the only jobspy importer: to_thread + wait_for boundary, the PRE-CALL budget_allows decision, and the source_request_log ledger writer"
  - "app/sources/linkedin.py — LinkedInAdapter with the real capability set, a total fetch(), a budgeted fetch_details() and a known-answer probe()"
  - "app/sources/registry.py — name-keyed registry (register/get/all_adapters/unregister/clear)"
  - "app/domain/{listing,sanitize}.py — pure canonical_url/content_hash/annualise_salary and the Phase-1 PII/HTML/truncation treatment"
  - "app/ingest/sanitize.py — the D-23 named sanitise stage (counts only, never the removed value)"
  - "app/pipeline/{stages,run}.py — normalise_listing() and run_pipeline(trigger, search_id, session_factory, run_id=…)"
  - "app/api/runs.py — POST /runs (202 + fragment, never awaits) and GET /runs/{id}/status (286 to stop)"
  - "app/api/health.py — minimal boot-tolerant /health (01-06 extends it)"
affects: ["Phase 1 plans 01-04 (Indeed), 01-05 (hardening), 01-06 (health/probe), 01-07 (probe verdict)", "Phase 2 (dedup + filter compiler consume NormalisedListing and the registry)", "Phase 8 (the scheduler reuses run_pipeline)"]

# Actuals (#2632) — pairs with the plan's estimate (62000 tokens / 3 tasks, confidence: low).
# Same estimateTokens scale: chars/4 over the realized diff (108306 chars).
actuals:
  tokens: 27077
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns: ["adapter port with declared capabilities", "total boundary (FetchResult, never raise)", "named sanitise stage at the ingest boundary", "one pipeline callable / two triggers", "HTMX poll that the server terminates (HTTP 286)", "SAVEPOINT-per-item persistence containment"]

key-files:
  created:
    - app/sources/__init__.py
    - app/sources/base.py
    - app/sources/registry.py
    - app/sources/_jobspy_transport.py
    - app/sources/linkedin.py
    - app/domain/listing.py
    - app/domain/sanitize.py
    - app/ingest/__init__.py
    - app/ingest/sanitize.py
    - app/pipeline/__init__.py
    - app/pipeline/run.py
    - app/pipeline/stages.py
    - app/api/runs.py
    - app/api/health.py
    - app/web/templates/html/_run_status.html
    - tests/sources/__init__.py
    - tests/sources/test_linkedin.py
    - tests/domain/__init__.py
    - tests/domain/test_normalize.py
    - tests/pipeline/__init__.py
    - tests/pipeline/test_ingest_e2e.py
    - tests/pipeline/test_partial_failure.py
    - tests/api/__init__.py
    - tests/api/test_run_trigger.py
    - tests/api/test_run_backgrounded.py
    - tests/fixtures/listings/linkedin_page1.json
    - tests/fixtures/listings/linkedin_missing_id.json
    - tests/fixtures/listings/linkedin_empty_description.json
  modified:
    - app/domain/models.py
    - app/db/repositories/listing_repo.py
    - app/db/session.py
    - app/main.py
    - app/web/templates/html/queue.html
    - tests/conftest.py

key-decisions:
  - "One `runs` row per trigger. `POST /runs` creates and commits the row so it can answer with a run id immediately; `run_pipeline` takes an optional `run_id` and updates THAT row. Without this the handler and the pipeline each created a row and the polled run never terminated."
  - "The JobSpy transport keeps its top-level `import jobspy` (so 'exactly one importer' stays greppable) but is imported lazily by the adapter, because JobSpy cannot be imported in this sandbox at all (`tls_client` needs `libresolv.so.2`). Production imports it normally; unit tests never need the scraper toolchain."
  - "Persistence is SAVEPOINT-per-item. `listing_sources.source` is a live FK, so a missing `sources` row made the insert fail AFTER the `listings` row was written, committing an orphan. The savepoint makes a bad item atomic."
  - "A run is `done` only when every board returned `ok`; any other outcome is `partial`. A `partial` that looks like a clean success is a trust failure, not a cosmetic one (Pitfall 10)."
  - "`get_session_factory()` is a FastAPI dependency, not a module global read, because a background task cannot use the request-scoped session and tests must be able to point the pipeline at the temp DB."
  - "`fetch_details()` is implemented but returns `{}` unless the budget allows it; `linkedin_fetch_description` is pinned False so the survival measurement is not confounded by the O(n) pass."

patterns-established:
  - "Adapters are total: every transport outcome (timeout, 429, 403, error) maps to a `FetchResult.status` and never propagates."
  - "`RawListing` structurally cannot carry PII; a fixture canary proves the library's `emails` column is never read."
  - "The sanitiser drops PII and logs only counts; the removed value is never returned, logged or hashed."
  - "Registry-keyed adapters resolved from the `sources` table, so a new board is a class plus a row — no pipeline edit."

# Declared by this plan: SRC-01, SRC-03, SRC-05, SRC-08, QUEUE-02, RUN-01, RUN-02, PLAT-03
# `requirements.ready-ids` marks only the five no sibling still blocks.
requirements-completed: [SRC-01, SRC-05, QUEUE-02, RUN-01, RUN-02]

coverage:
  - id: D1
    description: "A LinkedIn fixture run ingests end to end — adapter -> sanitise -> normalise -> two-key upsert — and GET / renders the listings with a count"
    requirement: "SRC-01"
    verification:
      - kind: integration
        ref: "tests/pipeline/test_ingest_e2e.py#test_ingest_e2e_persists_dedups_and_renders"
        status: pass
    human_judgment: false
  - id: D2
    description: "The LinkedIn adapter is total: a failing/blocked/rate-limited/timed-out transport yields a FetchResult and never raises; the missing-id and empty-description fixtures map deterministically"
    requirement: "SRC-01"
    verification:
      - kind: unit
        ref: "tests/sources/test_linkedin.py (14 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "RawListing has no email field and the library's emails column never reaches the domain object"
    requirement: null
    verification:
      - kind: unit
        ref: "tests/sources/test_linkedin.py#test_email_column_is_never_mapped"
        status: pass
      - kind: db
        ref: "tests/db/test_no_pii_columns.py#test_no_email_or_phone_columns"
        status: pass
    human_judgment: false
  - id: D4
    description: "One board blocked while another is ok leaves the run `partial`, persists the healthy board's listings and never aborts"
    requirement: "SRC-05"
    verification:
      - kind: integration
        ref: "tests/pipeline/test_partial_failure.py#test_a_blocked_board_degrades_the_run_but_keeps_the_healthy_queue"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_partial_failure.py#test_no_exception_propagates_when_a_board_is_blocked"
        status: pass
    human_judgment: false
  - id: D5
    description: "POST /runs returns 202 with a status fragment before the pipeline completes, and GET /health answers while the run is in flight"
    requirement: "RUN-01"
    verification:
      - kind: integration
        ref: "tests/api/test_run_backgrounded.py#test_handler_returns_before_the_pipeline_finishes"
        status: pass
      - kind: integration
        ref: "tests/api/test_run_trigger.py#test_post_runs_returns_202_and_creates_a_running_row"
        status: pass
    human_judgment: false
  - id: D6
    description: "GET /runs/{id}/status returns 200 while the run is in flight and 286 (HX-Reswap: outerHTML) once it is terminal"
    requirement: "RUN-02"
    verification:
      - kind: integration
        ref: "tests/api/test_run_backgrounded.py#test_handler_returns_before_the_pipeline_finishes"
        status: pass
    human_judgment: false
  - id: D7
    description: "Re-ingesting an identical payload creates no second listing_sources row for the same source"
    requirement: "QUEUE-02"
    verification:
      - kind: integration
        ref: "tests/pipeline/test_ingest_e2e.py#test_reingesting_the_identical_payload_does_not_duplicate"
        status: pass
    human_judgment: false
  - id: D8
    description: "Queue output is deterministic: identical requests render identically, ordered by first_seen_at desc then id desc"
    requirement: "SRC-01"
    verification:
      - kind: integration
        ref: "tests/pipeline/test_ingest_e2e.py#test_queue_order_is_deterministic_when_first_seen_at_is_equal"
        status: pass
    human_judgment: false
  - id: D9
    description: "Every adapter class lives under app/sources/ and jobspy is imported by exactly one module"
    requirement: null
    verification:
      - kind: other
        ref: "grep -rl '^import jobspy|^from jobspy' app/ -> app/sources/_jobspy_transport.py only"
        status: pass
      - kind: unit
        ref: "tests/sources/test_linkedin.py#test_registry_resolves_linkedin_by_name"
        status: pass
    human_judgment: false
  - id: D10
    description: "The auth seam is on every application route"
    requirement: "PLAT-03"
    verification:
      - kind: integration
        ref: "route-dependant walk over app.routes (recursing _IncludedRouter.original_router.routes) -> /, /runs, /runs/{run_id}/status, /health all depend on current_user"
        status: pass
    human_judgment: true
    rationale: "The universal route-introspection test is plan 01-05's deliverable and it CANNOT be written naively on FastAPI 0.141.1: `include_router` now yields `_IncludedRouter` objects with no `.dependant`, so `for route in app.routes` finds zero APIRoutes and a naive test passes vacuously. Verified manually here; 01-05 must recurse."
  - id: D11
    description: "A genuinely slow real scrape never freezes the single worker in production"
    requirement: "RUN-02"
    verification: []
    human_judgment: true
    rationale: "The in-flight responsiveness is proven with a stub adapter. The real-scrape residual is the operator probe run in plan 01-07 (a live board must never be contacted in CI)."
---

# Phase 01 Plan 03: LinkedIn ingest slice — port, sanitise, normalise, two-key upsert, run trigger

**A LinkedIn search ingested from a fixture lands as normalised, deduplicated rows that `GET /` renders, an operator can trigger it without the page freezing, the poll terminates itself with HTTP 286, and one blocked board degrades the run to `partial` without emptying the queue.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-09-15T17:31:22Z
- **Completed:** 2026-09-15T17:46:00Z
- **Tasks:** 3 of 3
- **Files modified:** 34 (28 created, 6 modified)
- **Tests added:** 39 (suite 34 → 73)

## Accomplishments

- **The vertical slice works end to end.** `run_pipeline()` resolves an enabled board through the registry, the LinkedIn adapter fetches (fixture-stubbed in tests), the named sanitise stage strips PII/HTML and truncates, `normalise_listing()` derives both dedup keys, and the two-key upsert persists. `GET /` then renders the listing with a count.
- **The boundary is total.** Every transport outcome — timeout, 429, 403/captcha, generic error, or an exhausted pre-call budget — returns a `FetchResult` with the right status and never raises. `RawListing` has no `emails`/phone/credential field at all, and a fixture canary proves the library's `emails` column is never read.
- **One failure degrades, never aborts.** A blocked board leaves `runs.status = "partial"`, records the per-source status and a structured error, and the healthy board's listings stay in the queue.
- **The trigger is backgrounded and the poll stops itself.** `POST /runs` returns 202 with the fragment while the pipeline is still running; `/health` answers mid-run; `GET /runs/{id}/status` returns 286 once the run is terminal.
- **The extensibility seam is real.** Adding a board is: implement `JobSource`, register it, insert a `sources` row. No pipeline edit, no schema change.

## Task Commits

1. **Task 1: Source-adapter port, shared transport, LinkedIn adapter, registry** - `b1cf75d` (feat)
2. **Task 2: Sanitise + normalise + two-key ingest + run_pipeline** - `7e733b9` (feat)
3. **Task 3: Manual run trigger, background execution, HTMX status polling** - `1a4a708` (feat)
4. **Verification: deterministic queue ordering** - `3af6467` (test)

**Plan metadata:** `docs(01-03): complete linkedin-ingest plan` (SUMMARY + STATE + ROADMAP + REQUIREMENTS)

## Files Created/Modified

- `app/sources/base.py` - the port, the total `FetchResult`, and the pure capability/error classifiers
- `app/sources/_jobspy_transport.py` - the only jobspy importer: `to_thread`/`wait_for`, `budget_allows`, `remaining_seconds`, `record_source_request`
- `app/sources/linkedin.py` - `LinkedInAdapter`, the row mapper, capabilities with the exclusive `{hours_old, easy_apply}` group
- `app/sources/registry.py` - name-keyed registry, populated by importing adapter modules
- `app/domain/listing.py`, `app/domain/sanitize.py` - pure derivation and the Phase-1 PII/HTML/truncation treatment
- `app/ingest/sanitize.py` - the named stage (structlog counts only)
- `app/pipeline/stages.py`, `app/pipeline/run.py` - `normalise_listing()` and `run_pipeline()`
- `app/api/runs.py`, `app/api/health.py` - the trigger/poll routes and a minimal boot-tolerant `/health`
- `app/web/templates/html/_run_status.html`, `queue.html` - the polling fragment and the run control
- `app/db/repositories/listing_repo.py` - `companies` anchor maintenance
- `app/db/session.py` - `get_session_factory()` dependency
- `app/main.py` - runs + health routers wired
- `tests/fixtures/listings/*.json`, `tests/{sources,domain,pipeline,api}/*` - 39 new tests, no network

## Decisions Made

- **One `runs` row per trigger.** The handler creates and commits the row (so it can return a run id immediately) and passes `run_id=` to the pipeline, which updates that same row. The Phase 8 scheduler will omit the argument and let the pipeline create its own.
- **Lazy transport import.** Production-identical, but the adapter obtains the transport through an injectable factory so the unit suite never needs JobSpy's native toolchain (see Deviation 1).
- **SAVEPOINT-per-item persistence.** A row that fails to persist rolls back alone; it can never leave an orphan `listings` row (see Deviation 4).
- **`done` only when every board is `ok`.** Anything else is `partial`.
- **`get_session_factory()` as a dependency.** A request-scoped session cannot outlive its response, and tests must be able to point the background pipeline at the temp DB.
- **`fetch_details()` is implemented but inert** while `probe_max_detail_fetches = 0`, so the Phase-1 survival measurement is not confounded by the O(n) description pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] JobSpy cannot be imported in this environment at all**
- **Found during:** Task 1 (adapter port)
- **Issue:** Installing JobSpy from its pinned git SHA succeeded, but `import jobspy` fails: `tls_client` loads a native library and raises `OSError: libresolv.so.2: No such file or directory`. A plain top-level import in `linkedin.py` would therefore make the adapter (and the whole suite) unimportable here. Its `regex` dependency also has no cp314 wheel and the host has no C compiler.
- **Fix:** `app/sources/_jobspy_transport.py` keeps its top-level `import jobspy` (so `grep -rl '^import jobspy' app/` still returns exactly one file), but the adapter imports it lazily through an injectable factory and tests inject a fake transport. Production (python:3.13-slim, where the dependency installs cleanly) is unaffected.
- **Files modified:** `app/sources/linkedin.py`, `app/sources/_jobspy_transport.py`
- **Verification:** `tests/sources/test_linkedin.py` (14 tests) passes with no network and no jobspy; `grep -rl '^import jobspy|^from jobspy' app/` returns exactly `app/sources/_jobspy_transport.py`.
- **Committed in:** `b1cf75d`

**2. [Rule 1 - Bug] Duplicate `site_name` keyword would have crashed the first real scrape**
- **Found during:** Task 1 (acceptance grep)
- **Issue:** `build_kwargs()` returned a `site_name` key while `run_scrape(site=...)` also passed `site_name=site` to `scrape_jobs` → `TypeError: got multiple values for keyword argument 'site_name'` on the first production fetch. No test could catch it because tests stub the transport.
- **Fix:** `run_scrape` now merges `{**kwargs, "site_name": site}` (site wins), and the adapter passes `site_name="linkedin"` explicitly in its kwargs.
- **Files modified:** `app/sources/_jobspy_transport.py`, `app/sources/linkedin.py`
- **Verification:** `test_build_kwargs_targets_linkedin_and_respects_the_budget` asserts `site_name == "linkedin"`; the merge is exercised by the real transport's contract.
- **Committed in:** `b1cf75d`

**3. [Rule 2 - Missing Critical] Two `runs` rows were created per trigger**
- **Found during:** Task 3 (run trigger test)
- **Issue:** `POST /runs` created and committed a `runs` row for the response, and `run_pipeline()` created ANOTHER. The handler's row (the one whose id the UI polls) was never updated, so the poll never terminated — the exact never-terminating-poll failure the plan warns about.
- **Fix:** `run_pipeline(..., run_id=…)` accepts a pre-created row; the handler passes the row it just committed. The scheduler omits it and the pipeline creates its own.
- **Files modified:** `app/pipeline/run.py`, `app/api/runs.py`
- **Verification:** `tests/api/test_run_trigger.py` and `test_run_backgrounded.py` assert the polled run reaches `done` and then returns 286.
- **Committed in:** `1a4a708`

**4. [Rule 2 - Missing Critical] A failed `listing_sources` insert left an orphan `listings` row**
- **Found during:** Task 2 (partial-failure test)
- **Issue:** `listing_sources.source` is a live FK to `sources.name`. Persisting an item whose board had no `sources` row raised `IntegrityError` AFTER the `listings` row was flushed; the per-item `except` swallowed it and the transaction committed the orphan listing.
- **Fix:** each item is wrapped in `session.begin_nested()` (SAVEPOINT) so a failure rolls that item back atomically, and the partial-failure test now registers its `sources` rows.
- **Files modified:** `app/pipeline/run.py`, `tests/pipeline/test_partial_failure.py`
- **Verification:** `tests/pipeline/test_partial_failure.py` passes and asserts the healthy board's rows survive a failing one with no orphans.
- **Committed in:** `7e733b9`

**5. [Rule 3 - Blocking] `/health` did not exist, and `app/main.py` was not in the plan's file list**
- **Found during:** Task 3
- **Issue:** The plan's own `test_run_backgrounded.py` requires `GET /health` to answer while a run is in flight, but no task in this plan creates the route (`app/api/health.py` belongs to plan 01-06). `app/main.py` was also absent from `files_modified` even though the new routers must be mounted.
- **Fix:** added a minimal boot-tolerant `app/api/health.py` (db reachability, never raises) and wired the runs + health routers in `app/main.py`. Plan 01-06 extends both.
- **Files modified:** `app/api/health.py`, `app/main.py`
- **Verification:** `tests/api/test_run_backgrounded.py` asserts `/health` returns 200 and `{"status": "ok"}` mid-run; 4 application routes are registered.
- **Committed in:** `1a4a708`

**6. [Rule 3 - Blocking] The shared `client` fixture could not route the background pipeline to the temp DB**
- **Found during:** Task 3
- **Issue:** The background task cannot use the request-scoped session, so the pipeline read `async_session_maker` (pointing at `/data/jobsearch.db`) even though `get_session` was overridden. Any DB assertion after `POST /runs` would have hit the wrong database.
- **Fix:** added `get_session_factory()` as a dependency and made the `client` fixture override it too; added a `registry_snapshot` fixture for adapter injection.
- **Files modified:** `app/db/session.py`, `tests/conftest.py`
- **Verification:** the api tests assert `runs` rows in the temp DB.
- **Committed in:** `1a4a708`

**7. [Rule 2 - Missing Critical] A `must_haves` truth had no assertion**
- **Found during:** final verification pass
- **Issue:** the backstop truth "queue output order is stable across identical requests — ordered by first_seen_at descending, then id descending" was implemented but unasserted.
- **Fix:** added `test_queue_order_is_deterministic_when_first_seen_at_is_equal`, which persists both fixture items with the same `first_seen_at` (so only the id tie-break can order them) and asserts two identical requests render byte-identically.
- **Files modified:** `tests/pipeline/test_ingest_e2e.py`
- **Verification:** the new test passes; suite 72 → 73.
- **Committed in:** `3af6467`

---

**Total deviations:** 7 auto-fixed (1 bug, 3 missing critical, 3 blocking)
**Impact on plan:** No scope creep. Deviations 2 and 3 were latent production crashes the fixture-stubbed tests could not have caught; 4 protected queue integrity; 1 is an environment adaptation with production behaviour unchanged; 5 and 6 were required for the plan's own tests to be meaningful; 7 closed a coverage gap.

## Issues Encountered

- **⚠️ Finding for plan 01-05 (important).** FastAPI 0.141.1 restructures routing: `include_router` appends opaque `_IncludedRouter` objects with **no `.dependant` and no visible `.routes`**, and the built-in `/docs`-family `Route`s have no `dependant` either. A `for route in app.routes` walk — exactly the shape the PATTERNS/RESEARCH example gives for `tests/test_auth_seam.py` — finds **zero** APIRoutes and passes vacuously. The leaf routes are reachable by recursing into `_IncludedRouter.original_router.routes`. Verified manually here: `/`, `/runs`, `/runs/{run_id}/status` and `/health` all resolve `current_user`. 01-05 must recurse or its PLAT-03 gate is worthless.
- **JobSpy in the sandbox.** `python-jobspy` and its dependency set were installed, but `import jobspy` still fails on the host shared-library gap (Deviation 1). The suite is designed to pass without it.
- **`pytest --collect-only -q`** prints a count, not test names, on pytest 9.1.1 (same observation as plan 01-02).
- **Ruff's `--target` install fragility.** A later `pip install --target … --upgrade` of numpy/pandas recreated `site-packages/bin/` and removed the `ruff` launcher; reinstalling `ruff` restored it. Environment-only, recorded so the next executor does not lose 10 minutes to it.

## User Setup Required

None — no external service configuration required. This plan installs nothing new at runtime and makes no LLM call; the JobSpy pin and lock were established in plan 01-01. The live board contact is deliberately deferred to the operator probe in plan 01-07.

## Next Phase Readiness

- **Ready for plan 01-04 (Indeed adapter).** The port, registry, shared transport and pipeline are in place. Adding Indeed is: `app/sources/indeed.py`, register it, insert a `sources` row — and, per Pitfall 6, set `country_indeed="ireland"` explicitly (the library default is `"usa"` and silently returns US listings).
- **Ready for plan 01-05 (hardening).** `app/sources/` is the place to point the no-credential static scan. The auth-seam test must handle the nested-router structure above.
- **Ready for plan 01-06 (health/probe).** `app/api/health.py` is a working base to extend with the opencode report, the per-source `probe()` and the TTL cache; `LinkedInAdapter.probe()` already asserts a known answer.
- **Ready for plan 01-07.** `source_request_log`, the `runs` row counters and `_run_status.html`'s per-source line are the surfaces the survival verdict will read.
- **Blockers:** none. Full suite 73 passed, `ruff check .` clean, and no test contacts a live board (the `live` lane collects zero tests here).

---

*Phase: 01-walking-skeleton-foundations*
*Completed: 2026-09-15*

## Self-Check: PASSED

- All 21 spot-checked files in `key-files.created` exist on disk.
- Task commits `b1cf75d`, `7e733b9`, `1a4a708` and the verification commit `3af6467` are present in `git log --oneline --all`.
- Plan verification re-run: `python -m pytest -q tests/sources tests/domain tests/pipeline tests/api -x` → **39 passed**; `python -m pytest -q -x` → **73 passed**; `ruff check .` → **All checks passed**.
- `grep -rl '^import jobspy|^from jobspy' app/` returns exactly `app/sources/_jobspy_transport.py`.
- All 13 `must_haves` truths are backed: 11 by an assertion in this plan (or plan 01-01's `test_concurrent_insert_race_is_caught_and_resolved` for the concurrent-upsert truth), and 2 recorded as `human_judgment: true` coverage entries — the universal auth-seam test (plan 01-05, with the FastAPI nested-router caveat spelled out) and the live-scrape responsiveness residual (plan 01-07's operator probe).
- No unrun `<verify>`: every `<automated>` command in all three tasks was executed and passed. No stubs, no skipped tests.
