---
phase: 01-walking-skeleton-foundations
plan: 04
subsystem: sources
tags: [adapter-port, indeed, country-guard, registry, capabilities, import-discipline, ast, jobspy]

# Dependency graph
requires:
  - phase: 01-walking-skeleton-foundations (plan 03)
    provides: "the adapter port (JobSource, RawListing, FetchResult, SourceCapabilities), the shared JobSpy transport, the registry, the LinkedIn adapter, run_pipeline and the fixture-driven test pattern"
  - phase: 01-walking-skeleton-foundations (plan 01)
    provides: "settings (the config surface every threshold and the country guard read from)"
provides:
  - "app/sources/indeed.py — IndeedAdapter with country_indeed pinned to settings.probe_country_indeed"
  - "app/sources/_jobspy_mapping.py — one board-agnostic JobSpy row mapper, so every board produces one normalised shape"
  - "app/sources/base.py — CapabilityWarning, CompiledQuery and compile_query_for_source() (declared-and-warned filters)"
  - "app/sources/registry.py — a finalised registry whose get() fails loudly and whose all_adapters() is deterministically ordered, with the documented 'adding a source' recipe"
  - "tests/sources/test_registry.py — the SRC-04 extensibility proof (a third adapter defined in the test, persisting through the pipeline)"
  - "tests/sources/test_capabilities.py — the SRC-09 declared-and-warned path"
  - "tests/test_import_discipline.py — the D-24 AST purity guard over app/domain"
affects: ["Phase 1 plans 01-05 (hardening broadens the no-credential scan), 01-07 (the probe verdict reads the same ledger)", "Phase 2 (the criteria compiler consumes compile_query_for_source; dedup consumes the shared normalised shape)", "Any later phase adding a source"]

# Actuals (#2632) — pairs with the plan's estimate (40000 tokens / 2 tasks, confidence: low).
# Same estimateTokens scale: chars/4 over the realized diff (56599 chars).
actuals:
  tokens: 14150
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns: ["one adapter per board over a shared transport and a shared mapper", "declared capabilities compiled into a query + explicit warnings", "registry keyed by name with a loud unknown-name failure", "AST-based import discipline (not a text regex)"]

key-files:
  created:
    - app/sources/indeed.py
    - app/sources/_jobspy_mapping.py
    - tests/sources/test_indeed.py
    - tests/sources/test_registry.py
    - tests/sources/test_capabilities.py
    - tests/test_import_discipline.py
    - tests/fixtures/listings/indeed_page1.json
    - tests/fixtures/listings/indeed_missing_id.json
  modified:
    - app/sources/base.py
    - app/sources/registry.py
    - app/sources/linkedin.py
    - app/pipeline/run.py

key-decisions:
  - "The JobSpy row mapper lives in its own board-agnostic module (`_jobspy_mapping.py`). Importing the LinkedIn module from Indeed would have coupled two boards that must be independently upgradable; the LinkedIn name is now a thin board-bound wrapper that preserves its public surface."
  - "`country_indeed` is read from `settings.probe_country_indeed` on every call, never the library default. `\"usa\"` parses perfectly and would silently poison both the corpus and the probe baseline, so a test asserts the value reaches the transport on a real fetch and not merely that build_kwargs produces it."
  - "`registry.get()` raises `UnknownAdapterError` instead of returning `None`. A `sources` row with no implementation is a configuration error, and the one consumer catches it so a single bad row degrades one board rather than aborting the run."
  - "`SearchQuery` gained `easy_apply`. Without it the LinkedIn `{hours_old, easy_apply}` exclusivity is inexpressible, and the backstop truth 'at most one member of each group survives' could not have been tested."
  - "Exclusive groups keep the alphabetically-first present member and warn the rest — deterministic, documented, and the only defensible choice without a board-specific priority."
  - "`compile_query_for_source()` ships tested in Phase 1 with its consumer in Phase 2 (the criteria compiler). This is deliberate per the research: the declared-and-warned path must exist before a filter UI can be trusted."

patterns-established:
  - "A board's difference is data (a `SourceCapabilities` value), not a branch in the core."
  - "A filter the board cannot honour is never silently dropped: it is removed from the compiled query AND recorded as a warning naming source and filter."
  - "Purity is enforced structurally — an AST walk over the package, with self-tests proving the walker can fail."

# Declared by this plan: SRC-02, SRC-03, SRC-04, SRC-09 — all four are ready.
requirements-completed: [SRC-02, SRC-03, SRC-04, SRC-09]

coverage:
  - id: D1
    description: "An Indeed search returns normalised listings in the same shape LinkedIn produces (same type, same field set, same canonical values for the fields both boards supply)"
    requirement: "SRC-02"
    verification:
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_indeed_maps_into_the_same_normalised_shape_as_linkedin"
        status: pass
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_indeed_adapter_maps_fixture_items"
        status: pass
    human_judgment: false
  - id: D2
    description: "The Indeed adapter passes country_indeed=\"ireland\" on every search, sourced from settings and never the library default"
    requirement: "SRC-02"
    verification:
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_country_indeed_is_pinned_to_ireland"
        status: pass
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_country_indeed_guard_rejects_the_library_default"
        status: pass
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_country_indeed_is_sourced_from_settings"
        status: pass
      - kind: integration
        ref: "tests/sources/test_indeed.py#test_country_indeed_is_passed_on_every_fetch_call"
        status: pass
    human_judgment: false
  - id: D3
    description: "A third source is added by writing one adapter and registering it — no edit to app/pipeline/ or app/db/ and no schema change"
    requirement: "SRC-04"
    verification:
      - kind: integration
        ref: "tests/sources/test_registry.py#test_a_third_adapter_registers_and_runs_through_the_pipeline"
        status: pass
      - kind: other
        ref: "tests/sources/test_registry.py#test_adding_a_source_required_no_core_edit (scans every module under app/pipeline/ and app/db/ for the third adapter's name)"
        status: pass
    human_judgment: false
  - id: D4
    description: "An unsupported or mutually exclusive requested filter is reported as a recorded warning rather than silently dropped"
    requirement: "SRC-09"
    verification:
      - kind: unit
        ref: "tests/sources/test_capabilities.py#test_unsupported_salary_floor_is_dropped_and_warned"
        status: pass
      - kind: unit
        ref: "tests/sources/test_capabilities.py#test_exclusive_group_keeps_at_most_one_member_and_warns_the_other"
        status: pass
      - kind: unit
        ref: "tests/sources/test_capabilities.py#test_two_sources_compile_against_their_own_capabilities"
        status: pass
      - kind: unit
        ref: "tests/sources/test_capabilities.py#test_warnings_are_deterministically_ordered"
        status: pass
    human_judgment: false
  - id: D5
    description: "app.domain imports none of httpx, sqlalchemy, jobspy, jinja2, subprocess or fastapi"
    requirement: null
    verification:
      - kind: unit
        ref: "tests/test_import_discipline.py#test_domain_imports_no_io"
        status: pass
      - kind: unit
        ref: "tests/test_import_discipline.py#test_the_walker_actually_detects_a_forbidden_import"
        status: pass
    human_judgment: false
  - id: D6
    description: "No adapter — the second one or any registered later — carries a credentialed or session-bearing acquisition path"
    requirement: null
    verification:
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_both_adapters_build_no_credential_bearing_kwargs"
        status: pass
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_no_credential_material_anywhere_in_the_sources_package"
        status: pass
    human_judgment: false
  - id: D7
    description: "The Indeed probe asserts a known answer and returns one of the three liveness literals"
    requirement: null
    verification:
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_probe_returns_ok_on_a_healthy_known_answer"
        status: pass
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_probe_returns_degraded_on_a_block_page"
        status: pass
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_probe_returns_unreachable_on_a_transport_error"
        status: pass
    human_judgment: false
  - id: D8
    description: "`jobspy` is still imported by exactly one module after the second adapter and the shared mapper were added"
    requirement: null
    verification:
      - kind: other
        ref: "grep -rl '^import jobspy|^from jobspy' app/ -> app/sources/_jobspy_transport.py only"
        status: pass
    human_judgment: false
  - id: D9
    description: "A real (un-stubbed) Indeed or LinkedIn request behaves as designed — no credential escalation, and the survival verdict on live boards"
    requirement: "SRC-02"
    verification: []
    human_judgment: true
    rationale: "Live board contact is deliberately operator-only (plan 01-07's probe run) and must never happen in CI. Everything in this plan is fixture-driven by design."

# Metrics
duration: 8min
completed: 2026-09-15
status: complete
---

# Phase 01 Plan 04: Indeed adapter, capability warnings, extensibility proof, domain purity

**A second board lands in the same normalised shape with its `country_indeed` pinned to Ireland, a filter a board cannot honour is warned about instead of silently dropped, a third adapter runs with zero core edits, and `app.domain` is provably free of I/O.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-09-15T17:49:40Z
- **Completed:** 2026-09-15T17:57:55Z
- **Tasks:** 2 of 2
- **Files modified:** 12 (8 created, 4 modified)
- **Tests added:** 37 (suite 73 → 110)

## Accomplishments

- **Two boards, one shape.** `IndeedAdapter` returns the same `RawListing` shape as LinkedIn, including the nullable-`id` case, because both now share a single board-agnostic JobSpy row mapper. The mapper still never reads the library's `emails` column, and a fixture canary proves it.
- **The Ireland guard is pinned and load-bearing.** `country_indeed=settings.probe_country_indeed` is set on every search, and a test asserts the value reaches the transport on a real `fetch()` — not merely that `build_kwargs` produces it. A second test fails if the value is ever the library default `"usa"`, and a third proves it is read from settings rather than hard-coded.
- **Extensibility is proven, not asserted.** `tests/sources/test_registry.py` defines a third adapter entirely inside the test file, registers it, runs it through `run_pipeline()` and sees its items persisted — and separately scans every module under `app/pipeline/` and `app/db/` to prove no core file names it.
- **A filter is never silently dropped.** `compile_query_for_source()` removes an unsupported filter from the compiled query *and* records a `CapabilityWarning` naming the source and the filter; `exclusive_filter_groups` keep at most one member and warn the rest; warnings are ordered by `(source, filter_name)` so identical inputs produce identical run records.
- **Purity is enforced structurally.** The D-24 guard AST-walks `app/domain`, and two self-tests prove the walker actually detects a forbidden import and ignores relative/harmless ones — a guard that cannot fail is not a guard.

## Task Commits

1. **Task 1: Indeed adapter with the explicit Ireland country guard** - `6ade850` (feat)
2. **Task 2: Extensibility proof, capability warnings, and domain purity** - `2a79763` (feat)
3. **Verification: country guard at the fetch boundary + the no-credential prohibition** - `c0145ee` (test)

**Plan metadata:** `docs(01-04): complete indeed-adapter plan` (SUMMARY + STATE + ROADMAP + REQUIREMENTS)

## Files Created/Modified

- `app/sources/indeed.py` - `IndeedAdapter`: its own capabilities, the Ireland guard, a total `fetch()`, an inert `fetch_details()` and a known-answer `probe()`
- `app/sources/_jobspy_mapping.py` - the shared, dependency-free row mapper (`DESIRED_ORDER`, `EXTRA_FIELDS`, `DROP_FIELDS`)
- `app/sources/linkedin.py` - now a thin board-bound view over the shared mapper; public surface unchanged
- `app/sources/base.py` - `CapabilityWarning`, `CompiledQuery`, `compile_query_for_source()`, `SearchQuery.easy_apply`
- `app/sources/registry.py` - loud `get()`, deterministic `all_adapters()`, the recipe comment, Indeed registered
- `app/pipeline/run.py` - catches `UnknownAdapterError` so a bad `sources` row degrades one board only
- `tests/sources/test_indeed.py`, `test_registry.py`, `test_capabilities.py`, `tests/test_import_discipline.py` - 37 tests
- `tests/fixtures/listings/indeed_page1.json`, `indeed_missing_id.json` - raw Indeed payloads with a PII canary and a null id

## Decisions Made

- **The mapper is board-agnostic and lives on its own.** SharePoint reuse without coupling: Indeed importing `app.sources.linkedin` would have made two independently upgradable boards depend on each other.
- **The country guard is asserted at the boundary.** `build_kwargs` producing the right value is necessary but not sufficient; the assertion that it reaches `run_scrape` is what would catch a regression where the kwargs are rebuilt or filtered downstream.
- **`get()` fails loudly.** Silently returning `None` turns a typo into an unexplained empty queue; the one consumer catches the error so the run still degrades gracefully.
- **Exclusive-group resolution is alphabetical and documented** rather than board-specific — deterministic beats clever, and the warning is the real product value.
- **The capability helper ships now, is consumed in Phase 2.** The research is explicit that the declared-and-warned path must exist before a filter UI can be trusted, and that consumption belongs to the Phase-2 criteria compiler.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] The shared mapper had no home in the plan's file list**
- **Found during:** Task 1
- **Issue:** The plan says Indeed must "reuse the same normalisation function as LinkedIn", but neither `files_modified` nor the artifacts list names a shared module. Importing `app.sources.linkedin` from `app.sources.indeed` would have created a cross-board dependency on a board that is explicitly meant to be independently upgradable.
- **Fix:** extracted the mapper, its constants and its NaN/NaT coercion helpers into `app/sources/_jobspy_mapping.py`; `linkedin.py` now re-exports a thin board-bound wrapper so every existing caller (including plan 01-03's tests) is unchanged.
- **Files modified:** `app/sources/_jobspy_mapping.py` (new), `app/sources/linkedin.py`
- **Verification:** `tests/sources/test_linkedin.py`, `test_indeed.py` and `tests/pipeline/test_ingest_e2e.py` all pass; `grep -rl '^import jobspy' app/` still returns exactly one file.
- **Committed in:** `6ade850`

**2. [Rule 3 - Blocking] Making `registry.get()` raise broke its only consumer**
- **Found during:** Task 2
- **Issue:** The plan requires `get(name)` to raise for an unknown name, but `app/pipeline/run.py` (absent from `files_modified`) relied on the old `None` return to skip an unimplemented board.
- **Fix:** `_resolve_adapters` now catches `registry.UnknownAdapterError`, logs the board and continues — an unimplemented `sources` row still degrades one board rather than aborting the run.
- **Files modified:** `app/pipeline/run.py`
- **Verification:** the full suite passes, including `tests/pipeline/test_partial_failure.py`.
- **Committed in:** `2a79763`

**3. [Rule 2 - Missing Critical] The LinkedIn exclusivity was inexpressible**
- **Found during:** Task 2
- **Issue:** `SearchQuery` had no `easy_apply` field, so the `{hours_old, easy_apply}` exclusivity — the very example the research uses — could not be requested, and the backstop truth "at most one member of each group survives" would have been untestable.
- **Fix:** added `easy_apply: bool | None = None` to `SearchQuery` with a comment explaining why it exists.
- **Files modified:** `app/sources/base.py`
- **Verification:** `tests/sources/test_capabilities.py#test_exclusive_group_keeps_at_most_one_member_and_warns_the_other`.
- **Committed in:** `2a79763`

**4. [Rule 2 - Missing Critical] `capability_warnings` returned un-nameable strings**
- **Found during:** Task 2
- **Issue:** the plan requires warnings that "carry the source name and the filter name"; the Phase-1 stub returned bare prose, so a consumer could not attribute or de-duplicate them.
- **Fix:** introduced `CapabilityWarning(source, filter_name, reason)` and `CompiledQuery`, and kept `capability_warnings()` as a backwards-compatible plain-text view.
- **Files modified:** `app/sources/base.py`
- **Verification:** `tests/sources/test_capabilities.py` plus `test_backwards_compatible_text_view_still_works`.
- **Committed in:** `2a79763`

**5. [Rule 2 - Missing Critical] Two `must_haves` obligations had no assertion**
- **Found during:** final verification pass
- **Issue:** the truth "passes `country_indeed="ireland"` on every search call" was only asserted at `build_kwargs`, not at the transport boundary; and the plan's `must_haves.prohibitions` entry ("no adapter may carry a credentialed or session-bearing path", `verification: test`) had no test at all.
- **Fix:** added a fetch-boundary country assertion and two credential tests — no credential-shaped kwarg from either adapter, and no `JOBSPY_CREDS`/`LINKEDIN_*`/`INDEED_*`/`cookies=` token anywhere under `app/sources/`.
- **Files modified:** `tests/sources/test_indeed.py`
- **Verification:** the three new tests pass; suite 107 → 110.
- **Committed in:** `c0145ee`

---

**Total deviations:** 5 auto-fixed (4 missing critical, 1 blocking)
**Impact on plan:** No scope creep. Deviation 1 prevented a cross-board coupling that would have undermined the plan's own extensibility goal; 2 was required for the plan's test suite to keep passing; 3 and 4 made stated truths testable/attributable; 5 closed the last two unproven obligations.

## Issues Encountered

- **The two fixtures legitimately disagree on the raw location string** ("Dublin, County Dublin, Ireland" vs "Dublin, County Dublin") and Indeed carries structured salary where LinkedIn does not. The "same shape" test therefore asserts the field *set* plus value equality only for the fields both boards supply, and documents the differences in the test — asserting value equality on every field would have been a false test of a real board difference.
- **BusyBox `grep` in this shell** rejects `--include`; the repository search tools were used instead. No impact.

## User Setup Required

None — no external service configuration required. No new dependency; this plan consumes the plan 01-01 lock only. Live board contact remains deferred to plan 01-07.

## Next Phase Readiness

- **Ready for plan 01-05 (hardening).** `app/sources/` now holds the credentialed-path surface to scan; the token list in `test_no_credential_material_anywhere_in_the_sources_package` is a starting point the static scan should broaden.
- **Carry the 01-03 finding forward:** FastAPI 0.141.1's `include_router` produces `_IncludedRouter` objects with no `.dependant`, so `tests/test_auth_seam.py` must recurse via `original_router.routes` or it will pass vacuously.
- **Ready for Phase 2.** `compile_query_for_source()` is the criteria compiler's input contract, and the shared mapper means Tier-1/Tier-2 dedup sees one shape regardless of board.
- **Blockers:** none. Full suite 110 passed, `ruff check .` clean, `alembic heads` still `0001`, and no test contacts a live board.

---

*Phase: 01-walking-skeleton-foundations*
*Completed: 2026-09-15*

## Self-Check: PASSED

- Task commits `6ade850` (Indeed adapter + Ireland guard), `2a79763` (registry extensibility, capability warnings, domain purity guard) and `c0145ee` (country guard at the fetch boundary + no-credential prohibition) are present in `git log --oneline --all`.
- Spot-checked files in `key-files.created` exist on disk: `app/sources/indeed.py`, `tests/sources/test_indeed.py`, `tests/sources/test_registry.py`, `tests/sources/test_capabilities.py`, `tests/test_import_discipline.py`, both Indeed fixtures.
- Plan verification re-run: `.venv/bin/python -m pytest -q` → **110 passed**; `ruff check .` → **All checks passed**; `alembic heads` → **0001 (head)**.
- No test contacts a live board (`pytest -q -m live --collect-only` collects zero).
- The `must_haves` truths are backed: the concrete truths by assertions (`country_indeed` read from settings, pinned at the transport boundary, never the library default `"usa"`; third-adapter registration with zero core edits; deterministic `(source, filter_name)` warning order; AST purity guard with self-tests that prove the walker can fail) and the plan's `backstop` truths by the capability/registry tests; no truth was left unbacked.
- Recovery note: this plan's dispatch was cancelled after the three task commits but before the metadata commit; the tracking close-out (STATE.md, ROADMAP.md, REQUIREMENTS.md) and this Self-Check block were completed by the orchestrator. No source-code change was made during recovery.
