---
phase: 02-clean-filtered-queryable-queue
plan: "08"
subsystem: api
tags: [criteria, filter-rules, crud, htmx, alpine, capability-warnings, run-trigger, sqlalchemy]

# Dependency graph
requires:
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-03's `app/domain/filter.RULE_KINDS` + `app/domain/criteria.search_query_from`/`rule_specs_from`"
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-05's `search_repo` read side, `runs.criteria_snapshot_json`, `run_filter_stage`, and the criteria-before-fetch contract"
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-07's thin `app/web/routes.py`, the HTMX fragment conventions and the stable-root-id precedent"
provides:
  - "`app/db/repositories/search_repo.py` — the WRITE side: create/update/enable/delete search, create/update/delete rule, `validate_rule_params`, plus the all-searches and per-search rule reads the UI needs"
  - "`app/api/searches.py` — the criteria page, the CRUD + toggle + delete routes, the per-kind rule routes, the pre-run capability report and `POST /searches/{id}/run`"
  - "`app/web/templates/html/criteria.html` — the criteria page with a per-kind rule form and per-search/per-rule controls"
  - "single-search scoping in `run_pipeline`/`run_filter_stage` and the `resolve_enabled_adapters` seam"
  - "the version contract: a criteria change bumps `searches.version`; a scheduling toggle does not"
affects: [02-09, 02-10]

# Actuals (#2632) — measured, not narrated.
actuals:
  tokens: 30399        # chars/4 of `git diff dfad591..HEAD` => 121597/4
  tasks: 3
  commits: 3           # MEASURED: git rev-list --count dfad591..HEAD
  plan_head_before: dfad591bab6b436d868e5b6d9f26f4c023a88d66

tech-stack:
  added: []            # no new dependency — urlencoded forms parsed with the stdlib
  patterns:
    - "Repository owns the write SQL; each fallible write is a SAVEPOINT and the route owns the commit (source_repo contract)"
    - "Macro-as-fragment: the list markup lives in a Jinja macro so the page and every hx-post swap are one definition (merges.html precedent)"
    - "Decorations never 500: the capability report degrades to no warnings and a log line, like `_health_strip`"
    - "One compiler, two callers: the render-time report and the run path both go through `compile_query_for_source`; the report never duplicates the capability logic"

key-files:
  created:
    - app/api/searches.py
    - app/web/templates/html/criteria.html
    - tests/api/test_searches_crud.py
    - tests/db/test_search_repo_writes.py
    - tests/api/test_criteria_capabilities.py
    - tests/pipeline/test_single_search_run.py
  modified:
    - app/db/repositories/search_repo.py
    - app/main.py
    - app/pipeline/run.py
    - app/pipeline/filter_stage.py

key-decisions:
  - "`SearchRecord`/`RuleRecord` gained defaulted fields (`enabled`, `last_run_at`, timestamps) rather than a second record type, so the 02-05 read side is untouched and the criteria page reads the same shape."
  - "A whole-search enable/disable does NOT bump `version`; a rule toggle DOES — which rules are enabled is effective criteria, whether a search is scheduled is not. Both asserted."
  - "`delete_search` clears the nullable `runs.search_id` pointer before deleting the row: the FK has no `ON DELETE SET NULL` and `PRAGMA foreign_keys=ON` is enforced, so this is what lets the run row (and its `criteria_snapshot_json`) survive a search delete."
  - "Forms are parsed from the urlencoded body with `urllib.parse.parse_qsl` instead of adding `python-multipart`; htmx posts urlencoded by default, so this is exactly the browser's shape and keeps the dependency out."
  - "`validate_rule_params` treats an absent/empty `exclude_keyword.fields` as valid (the evaluator defaults it to `title, description`); only a populated list with bad entries is rejected."
  - "The capability report is computed over ENABLED searches only — a disabled search is not run, so warning about it would be noise; disabled searches still render (no warnings)."
  - "`resolve_enabled_adapters` is exposed as the single adapter resolution (`_resolve_adapters`' public seam) so the criteria page reuses the run path's SQL rather than a second copy."

patterns-established:
  - "Version-is-criteria-not-clicks: `searches.version` moves on a stored criteria change and on any rule write, never on a schedule toggle; a run's snapshot references it meaningfully."
  - "Per-kind typed form: one Alpine kind selector drives server-rendered field groups; field names are namespaced per kind so a hidden group cannot bleed into the submitted one; no raw-JSON control exists."
  - "Per-search run is the same callable: `run_pipeline(trigger, search_id, ...)` scopes snapshot + fetch query + filter stage to one search; the union path is byte-for-byte the old behaviour."
  - "Degrade-don't-500 for decorative data: capability computation is wrapped, so a missing adapter or registry failure yields an empty report and a 200."

requirements-completed: [CRIT-01, CRIT-03, FILT-04]

coverage:
  - id: D1
    description: "A named search with its own typed rules can be created from the browser, validated per kind, stored with `version == 1`, and the create/rule routes answer with the `#criteria-list` fragment."
    requirement: CRIT-01
    verification:
      - kind: integration
        ref: "tests/api/test_searches_crud.py#test_post_searches_persists_a_version_one_enabled_search"
        status: pass
      - kind: integration
        ref: "tests/api/test_searches_crud.py#test_post_rule_round_trips_and_bumps_the_owning_search_version"
        status: pass
    human_judgment: false
  - id: D2
    description: "A bad rule shape is rejected before any insert: unknown kind, negative/fractional/non-numeric salary floor, and an empty name all write no row."
    requirement: CRIT-01
    verification:
      - kind: unit
        ref: "tests/db/test_search_repo_writes.py#test_create_rule_with_an_unknown_kind_writes_no_row"
        status: pass
      - kind: integration
        ref: "tests/api/test_searches_crud.py#test_a_non_integer_salary_floor_rule_is_rejected"
        status: pass
    human_judgment: false
  - id: D3
    description: "Enable/disable leaves `version` unchanged while editing a search or any rule write bumps it; editing a search with identical criteria does not churn the version."
    requirement: CRIT-03
    verification:
      - kind: unit
        ref: "tests/db/test_search_repo_writes.py#test_enable_disable_does_not_bump_the_version"
        status: pass
      - kind: unit
        ref: "tests/db/test_search_repo_writes.py#test_toggling_a_rule_bumps_the_version_unlike_toggling_a_search"
        status: pass
    human_judgment: false
  - id: D4
    description: "Deleting a search removes the search and its rules only — listings, exclusions, merges and runs are untouched, and a completed run keeps its criteria snapshot."
    requirement: CRIT-03
    verification:
      - kind: unit
        ref: "tests/db/test_search_repo_writes.py#test_delete_search_removes_it_and_all_its_rules_only"
        status: pass
      - kind: unit
        ref: "tests/db/test_search_repo_writes.py#test_a_deleted_searchs_run_keeps_its_criteria_snapshot"
        status: pass
    human_judgment: false
  - id: D5
    description: "A filter a board cannot honour is reported before any run, naming the board and the filter and stating the local-enforcement fallback; a registry failure degrades to no warnings, never a 500."
    requirement: FILT-04
    verification:
      - kind: integration
        ref: "tests/api/test_criteria_capabilities.py#test_an_unsupported_filter_is_reported_per_board"
        status: pass
      - kind: integration
        ref: "tests/api/test_criteria_capabilities.py#test_a_registry_failure_degrades_to_no_warnings_not_a_500"
        status: pass
    human_judgment: false
  - id: D6
    description: "A single search can be run on its own: it scopes the snapshot, the fetch query and the rules to that search, stamps only its `last_run_at`, and creates exactly one runs row via a 202 fragment; the one-tap union run is unchanged."
    requirement: CRIT-03
    verification:
      - kind: integration
        ref: "tests/pipeline/test_single_search_run.py#test_a_single_search_run_scopes_query_snapshot_and_rules"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_single_search_run.py#test_the_union_run_still_unions_every_enabled_search"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_single_search_run.py#test_post_search_run_returns_202_and_creates_one_run_row"
        status: pass
    human_judgment: false

# Metrics
duration: 32min
completed: 2026-09-16
status: complete
---

# Phase 2 Plan 08: Criteria you can tune from the UI Summary

**Named searches with per-kind rule forms, version-stamped edits, a pre-run capability report, and a per-search "Run this one" — wired into one shared pipeline callable.**

## Performance

- **Duration:** 32 min
- **Started:** 2026-09-16T11:17:18Z
- **Completed:** 2026-09-16T11:49:35Z
- **Tasks:** 3
- **Files modified:** 10 (6 created, 4 modified)

## Accomplishments
- The write half of `search_repo`: create/edit/enable/disable/delete a search and create/edit/toggle/delete its rules, with `validate_rule_params` rejecting a bad shape before any insert and the version contract asserted in the DB lane.
- `app/api/searches.py` and `criteria.html`: the criteria page, the CRUD routes, a per-kind Alpine-driven rule form (six kinds, each with its unknown-passes help text), per-search/per-rule controls, and the `#criteria-list` fragment shared by the page and every swap.
- The pre-run capability report: every enabled search compiled against every enabled adapter's `SourceCapabilities` through the existing `compile_query_for_source`, rendered as `board`/`filter`/`reason` with the local-enforcement sentence, degrading to no warnings on a registry failure.
- D-45's per-search run: `run_pipeline(..., search_id=...)` scopes the snapshot, fetch query and filter rules to one search and stamps only its `last_run_at`; `POST /searches/{id}/run` answers 202 with the `hx-get="/runs/{id}/status"` fragment. The union path is unchanged.

## Task Commits

Each task was committed atomically:

1. **Task 1: create a named search with a typed rule in the browser** - `a1cb4f7` (feat)
2. **Task 2: enable, disable, edit and delete without losing history** - `2e4b47b` (feat)
3. **Task 3: report what a board cannot honour, and run a single search** - `5f0c869` (feat)

**Plan metadata:** _committed with STATE/ROADMAP/REQUIREMENTS after this file_

## Files Created/Modified
- `app/db/repositories/search_repo.py` - extended with the write half (`create_search`, `update_search`, `set_search_enabled`, `delete_search`, `create_rule`, `update_rule`, `delete_rule`, `validate_rule_params`) and the UI reads (`all_searches`, `search_by_id`, `rules_for_search`, `rule_by_id`).
- `app/api/searches.py` - the criteria router: page, create/edit/toggle/delete search, create/edit/toggle/delete rule, capability report, `POST /searches/{id}/run`.
- `app/web/templates/html/criteria.html` - the page + `criteria_list`/`rule_form`/`rule_edit_form` macros.
- `app/main.py` - registers the searches router.
- `app/pipeline/run.py` - `resolve_enabled_adapters`, `_resolve_fetch_query`, `_stamp_last_run`, snapshot/query/`filter_stage` scoping.
- `app/pipeline/filter_stage.py` - keyword-only `search_id` so a rule set can be scoped to one search.
- `tests/api/test_searches_crud.py` - the CRUD/version/escaping/flagged-assumption lane (19 tests).
- `tests/db/test_search_repo_writes.py` - the manual-session DB lane (10 tests).
- `tests/api/test_criteria_capabilities.py` - the capability report lane (3 tests).
- `tests/pipeline/test_single_search_run.py` - the single-search scoping lane (3 tests).

## Decisions Made
- Extended `SearchRecord`/`RuleRecord` with defaulted fields instead of a second record type; the 02-05 read side is untouched.
- A whole-search toggle does not bump `version`; a rule toggle does. Both asserted, both documented in the docstrings.
- `delete_search` clears the nullable `runs.search_id` before deleting (FK integrity with `foreign_keys=ON`); the run row and its snapshot survive.
- Forms parsed with the stdlib rather than adding `python-multipart`.
- Empty `exclude_keyword.fields` is valid (evaluator default), not an error.
- The capability report covers enabled searches only; the registry walk is wrapped so it cannot 500 the page.

## Deviations from Plan

### Environment

**1. [Environment] `.venv-host/bin/pytest` → `.venv/bin/python -m pytest`**
- **Found during:** all tasks
- **Issue:** the plan's `<verify>` blocks name `.venv-host/bin/pytest`, which has a stale absolute shebang and a broken `pydantic_core` build in this sandbox (per the carry-over context).
- **Fix:** ran every verification with `cd /workspace/job-search && .venv/bin/python -m pytest -q <paths>`.
- **Impact:** none on behaviour; the same tests ran.

### Auto-fixed Issues

**2. [Rule 3 - Blocking] Forms parsed without `python-multipart`**
- **Found during:** Task 1
- **Issue:** `request.form()` raises unless `python-multipart` is installed, and it is not a declared dependency (no code used `Form(...)` before). Package installs are explicitly excluded from auto-fix.
- **Fix:** added a small `_UrlForm` view fed by `urllib.parse.parse_qsl` over the urlencoded body. htmx posts urlencoded by default, so this is exactly the browser's shape.
- **Files modified:** `app/api/searches.py`
- **Verification:** all CRUD form tests pass; no new dependency added.
- **Committed in:** `a1cb4f7` (Task 1)

**3. [Rule 3 - Blocking] `delete_search` clears the nullable `runs.search_id`**
- **Found during:** Task 2
- **Issue:** the plan said delete must not touch any `Run`, but `runs.search_id` is a plain FK with no `ON DELETE SET NULL` and `PRAGMA foreign_keys=ON` is enforced by the engine — so deleting a referenced search raised `IntegrityError`.
- **Fix:** clear the nullable pointer in the same transaction, then delete the rules and the search. The run row and its `criteria_snapshot_json` are preserved (asserted by count and by value); only the dangling id is released. Documented in the docstring.
- **Files modified:** `app/db/repositories/search_repo.py`
- **Verification:** `tests/db/test_search_repo_writes.py#test_a_deleted_searchs_run_keeps_its_criteria_snapshot` and the protected-row count test.
- **Committed in:** `2e4b47b` (Task 2)

**4. [Rule 2 - Missing critical] `app/pipeline/filter_stage.py` scoped by `search_id`**
- **Found during:** Task 3
- **Issue:** the plan's task-3 text requires a per-search run to apply only that search's rules, but `run_filter_stage` loaded the union of enabled searches; scoping could not be done from `run.py` alone.
- **Fix:** added a keyword-only `search_id` to `run_filter_stage` (default `None` keeps the union behaviour and all existing callers/tests green) and passed it from `run_pipeline`.
- **Files modified:** `app/pipeline/filter_stage.py`, `app/pipeline/run.py`
- **Verification:** `tests/pipeline/test_single_search_run.py` asserts the other search's rule is not applied in a single run, and `tests/pipeline/test_filter_stage.py` (union) still passes.
- **Committed in:** `5f0c869` (Task 3)

---

**Total deviations:** 1 environment substitution + 3 auto-fixed (2 blocking, 1 missing critical, plus one extra file beyond the plan's list).
**Impact on plan:** the fix in (3) is the one concession the schema forces; it preserves the plan's actual intent (the run keeps its snapshot). (4) adds one file to the plan's `files_modified` but is required by the plan's own task-3 behaviour. No scope creep.

## Issues Encountered
- The first Task-1 test run rejected a valid `exclude_keyword` rule because an omitted `fields` list was treated as invalid. Fixed the validator to accept an empty/absent list (the evaluator's documented default) while still rejecting a populated list with unknown entries — committed as part of Task 1's follow-up before the commit.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The criteria surface is complete for the six `RULE_KINDS`; adding a new kind remains a coordinated migration + `RULE_KINDS` + evaluator + form change (documented in the repository docstring as a decision, not a gap).
- `searches.version` is meaningful for the run snapshot, so plan 02-10's run-history page can render a snapshot's version directly.
- Residual (accepted, per the plan): a double-submitted create produces two identically named searches — no unique constraint exists; the test records this honestly. Optimistic concurrency is the upgrade path and is out of scope.
- Full suite: **538 passed, 2 deselected** (~64s); ruff clean.

---
*Phase: 02-clean-filtered-queryable-queue*
*Completed: 2026-09-16*

## Self-Check: PASSED

All six created source/test files and the SUMMARY exist; commits a1cb4f7, 2e4b47b and 5f0c869 are present.
