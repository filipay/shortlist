---
phase: 01-walking-skeleton-foundations
fixed_at: 2026-09-15T21:35:26Z
review_path: .planning/phases/01-walking-skeleton-foundations/01-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 1: Code Review Fix Report

**Fixed at:** 2026-09-15T21:35:26Z
**Source review:** `.planning/phases/01-walking-skeleton-foundations/01-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (1 Critical, 4 Warning)
- Fixed: 5
- Skipped: 0

**Out of scope (not attempted, per instructions):** the 6 Info findings (IN-01..IN-06),
CR-01's `probe()`-vs-`fetch()` discrepancy, and the deferred positive structural marker
(`.planning/WINDOWS.md` #3/#4 — deliberate open items for a human at phase verification).

**Verification environment:** the gates ran in the **main checkout** (`/workspace/job-search`,
branch `master`), not an isolated worktree — the project's `.venv` and `.venv-host` reference
library live there, and the task pinned those paths. Every commit staged only the listed files;
`.planning/config.json` (pre-existing modification), `.gsd/`, `.planning/milestone.lock`,
`.planning/state.json`, `data/` and `.venv-host/` were never touched or staged.

## Fixed Issues

### CR-01: A board block is reported as a clean, empty `done` run

**Files modified:** `app/sources/linkedin.py`, `app/sources/indeed.py`,
`tests/sources/test_linkedin.py`, `tests/sources/test_indeed.py`,
`tests/pipeline/test_partial_failure.py`,
`tests/api/test_run_trigger.py`, `tests/api/test_run_backgrounded.py`,
`tests/db/test_source_seeding.py`
**Commit:** `20235cd`
**Status:** fixed — **requires human verification** (status-semantics change)
**Applied fix:** both adapters now classify a zero-row frame with the ledger's own
`classify_response(status_code=None, parsed_items=0)` and return
`FetchResult(status="partial", error=<same note>)` instead of `status="ok"`, so a
blocked/empty result can never produce `runs.status='done'` and the `FetchResult` no
longer contradicts the `source_request_log` verdict. A genuinely successful fetch
(rows) keeps `status="ok"` and `done`; a transport exception keeps its classified
status. The three stub adapters that returned `status="ok", items=[]` (the false
success the review named) were updated to return one real row, since they model the
corrected adapter contract.
**Tests that pin it:** `tests/pipeline/test_partial_failure.py::test_a_zero_row_frame_is_not_a_done_run`
and `::test_a_fetch_with_rows_is_still_a_done_run`;
`tests/sources/test_linkedin.py::test_an_empty_frame_is_not_reported_as_ok`;
`tests/sources/test_indeed.py::test_an_empty_frame_is_not_reported_as_ok`.
**Mutation check:** reverting `app/sources/linkedin.py` to the pre-fix unconditional
`status="ok"` makes `test_a_zero_row_frame_is_not_a_done_run` fail with
`assert 'done' != 'done'` (verified, then restored). This is a logic/status-ordering
change, so the semantic choice of `partial` (vs a distinct status) should be confirmed
by a human even though the regression is pinned.

### WR-01: `failed > 0` is excluded from the run status and never rendered

**Files modified:** `app/pipeline/run.py`, `app/web/templates/html/_run_status.html`,
`tests/pipeline/test_partial_failure.py`
**Commit:** `075e67f`
**Status:** fixed — **requires human verification** (status decision)
**Applied fix:** `run_pipeline` now sums the per-source `failed` counts and requires
`persisted_failures == 0` for `done`; a run in which every item failed to persist reports
`partial`. `_run_status.html` renders `{% if counts.failed %} — {{ counts.failed }} failed{% endif %}`
so the failure is visible rather than hidden behind a green badge.
**Test that pins it:** `tests/pipeline/test_partial_failure.py::test_a_run_whose_every_item_failed_to_persist_is_not_done`
(an `adzuna` adapter with no `sources` row → FK rejection on every item).
**Mutation check:** removing `and persisted_failures == 0` makes that test fail
(`- partial / + done`) (verified, then restored).

### WR-02: dead `DATABASE_URL` in `compose.yml`

**Files modified:** `compose.yml`, `tests/test_deploy_manifest.py`
**Commit:** `ad6a991`
**Status:** fixed
**Applied fix:** `compose.yml` now sets `DATABASE_URL_ASYNC` (the real `Settings` field
`database_url_async`) instead of the dead `DATABASE_URL`.
**Tests that pin it:** `tests/test_deploy_manifest.py::test_compose_database_url_keys_are_real_settings_fields`
(asserts every `DATABASE_URL*` key in compose maps to a real `Settings` field) and
`::test_compose_sets_the_async_database_url_key`.
**Mutation check:** restoring the bare `DATABASE_URL` makes both guards fail (verified,
then restored).

### WR-03: filters can be silently dropped on the run path

**Files modified:** `app/pipeline/run.py`, `app/sources/linkedin.py`,
`tests/pipeline/test_partial_failure.py`, `tests/sources/test_linkedin.py`
**Commit:** `ad62aa8`
**Status:** fixed
**Chosen approach — both minimal halves, and why:** the review offered "consult the
capability path" *or* "forward the declared filters". Neither alone is sufficient:
consulting capabilities records `salary_floor`/`seniority` warnings but leaves a single
`hours_old`/`easy_apply` survivor to be dropped inside `build_kwargs`; forwarding alone
leaves `salary_floor`/`seniority` silently dropped. So:
- `_fetch_one` now calls `compile_query_for_source(query, adapter.capabilities, source=...)`
  and executes the **compiled** query; the warnings are appended to `runs.errors_json`
  as recorded entries (`{"source", "status": "warning", "error": "filter not applied: ..."}`).
  When nothing must be dropped the compiled query is the caller's query unchanged, so
  `default_query()` (which sets none of these) is byte-for-byte unaffected — no warnings,
  no status change.
- `LinkedInAdapter.build_kwargs` forwards `hours_old` and `easy_apply` when set (JobSpy's
  LinkedIn scraper consumes both — verified read-only at
  `.venv-host/.../jobspy/linkedin/__init__.py`, `f_TPR`/`f_AL`).

The exclusivity arbitration the compiler already performs therefore happens end to end,
and no filter present on a query is now dropped without a recorded warning. This does
not build the Phase-2 criteria compiler.
**Tests that pin it:** `tests/pipeline/test_partial_failure.py::test_a_filter_the_board_cannot_honour_is_recorded_not_dropped`
(run path records the warning, strips the unsupported filter, stays `done`);
`tests/sources/test_linkedin.py::test_build_kwargs_forwards_the_declared_linkedin_filters`
and `::test_build_kwargs_omits_the_optional_filters_when_unset`.
**Mutation check:** bypassing the compile in `_fetch_one` makes the pipeline test fail
(`assert 'salary_floor' in ''`) (verified, then restored).

### WR-04: a transport error is logged as a parse-side failure

**Files modified:** `app/sources/base.py`, `app/sources/_ledger.py`, `app/pipeline/run.py`,
`app/probe/survival.py`, `tests/probe/test_thresholds.py`
**Commit:** `510288f`
**Status:** fixed
**Applied fix:** `classify_response` gained an optional `transport_error` (fetch-side,
takes precedence); `record_fetch_outcome` accepts the adapter's `error` string and passes
it through for `result_status == "error"`, so a connection reset/timeout is recorded as
`fetch-side: transport error: …` instead of `parse-side: no rows`. `run_pipeline` passes
`result.error` into the ledger. `classify_block_vs_parse` now classifies
`status="error"` as fetch-side too, keeping the S5 vocabulary consistent. A zero-row
`partial` with no transport error still classifies parse-side (the CR-01 case), so the
two failure kinds remain distinguishable.
**Tests that pin it:** `tests/probe/test_thresholds.py::test_a_transport_error_is_recorded_as_fetch_side`
(and `::test_a_zero_row_partial_is_still_recorded_as_parse_side`,
`::test_s5_classifies_a_transport_error_status_as_fetch_side`).
**Mutation check:** disabling the `result_status == "error"` branch makes the ledger test
fail with note `parse-side: the request returned no rows` (verified, then restored).

## Skipped Issues

None — all five in-scope findings were fixed.

---

_Fixed: 2026-09-15T21:35:26Z_
_Fixer: the agent (gsd-code-fixer)_
_Iteration: 1_
