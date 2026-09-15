---
phase: 01-walking-skeleton-foundations
reviewed: 2026-09-15T21:39:07Z
depth: standard
remediated:
  - 20235cd
  - 075e67f
  - ad6a991
  - ad62aa8
  - 510288f
files_reviewed: 79
files_reviewed_list:
  - app/__init__.py
  - app/api/__init__.py
  - app/api/deps.py
  - app/api/health.py
  - app/api/runs.py
  - app/config.py
  - app/db/__init__.py
  - app/db/base.py
  - app/db/models.py
  - app/db/repositories/__init__.py
  - app/db/repositories/listing_repo.py
  - app/db/repositories/source_repo.py
  - app/db/session.py
  - app/domain/__init__.py
  - app/domain/listing.py
  - app/domain/models.py
  - app/domain/sanitize.py
  - app/ingest/__init__.py
  - app/ingest/sanitize.py
  - app/llm/__init__.py
  - app/llm/base.py
  - app/llm/opencode_server.py
  - app/main.py
  - app/pipeline/__init__.py
  - app/pipeline/run.py
  - app/pipeline/stages.py
  - app/probe/__init__.py
  - app/probe/probe.py
  - app/probe/survival.py
  - app/sources/__init__.py
  - app/sources/_jobspy_mapping.py
  - app/sources/_jobspy_transport.py
  - app/sources/_ledger.py
  - app/sources/base.py
  - app/sources/indeed.py
  - app/sources/linkedin.py
  - app/sources/registry.py
  - app/web/__init__.py
  - app/web/routes.py
  - app/web/templates/html/_health_strip.html
  - app/web/templates/html/_run_status.html
  - app/web/templates/html/base.html
  - app/web/templates/html/queue.html
  - Dockerfile
  - compose.yml
  - entrypoint.sh
  - pyproject.toml
  - requirements.txt
  - alembic.ini
  - alembic/env.py
  - alembic/versions/0001_initial_schema.py
  - .env.example
  - .gitignore
  - scripts/compose-smoke.sh
  - scripts/run-probe.sh
  - tests/conftest.py
  - tests/test_auth_seam.py
  - tests/test_config.py
  - tests/test_deploy_manifest.py
  - tests/test_import_discipline.py
  - tests/test_no_cdn.py
  - tests/test_no_credentials.py
  - tests/api/test_health.py
  - tests/api/test_run_backgrounded.py
  - tests/api/test_run_trigger.py
  - tests/db/test_no_pii_columns.py
  - tests/db/test_source_seeding.py
  - tests/db/test_two_key_upsert.py
  - tests/domain/test_sanitize_pii.py
  - tests/live/test_probe_live.py
  - tests/pipeline/test_ingest_e2e.py
  - tests/pipeline/test_partial_failure.py
  - tests/probe/test_probe.py
  - tests/probe/test_thresholds.py
  - tests/sources/test_dataframe_conversion.py
  - tests/sources/test_indeed.py
  - tests/sources/test_jobspy_contract.py
  - tests/sources/test_registry.py
findings:
  critical: 0
  warning: 0
  info: 8
  total: 8
status: clean
---

# Phase 1: Code Review Report

**Reviewed:** 2026-09-15T21:39:07Z
**Depth:** standard
**Files Reviewed:** 79
**Status:** clean

## Summary

Re-review of the phase-1 "Walking Skeleton + Foundations" code at `510288f`, after the five
remediation commits (`20235cd`, `075e67f`, `ad6a991`, `ad62aa8`, `510288f`) that addressed the
1 Critical / 4 Warning findings from the prior review. This pass re-inspected each fix's diff
and resulting code, re-ran the full offline suite and lint, and re-hunted the defect classes
(silent-empty success, false-success statuses, ledger/status contradictions, unwired controls).

Baseline confirmed by execution at HEAD `510288f`: `.venv/bin/python -m pytest -q` → **315
passed, 2 deselected**; `.venv/bin/python -m ruff check .` → **clean**.

**All five Critical/Warning findings are RESOLVED** — verified in the code, not merely asserted
by the commit messages. No new Critical or Warning finding was introduced. The eight remaining
findings are Info-only: the six carried over from the prior review (all on files untouched by
the remediation, except `survival.py`, whose `classify_block_vs_parse` change does not affect
the unwired-signal observation) plus two new advisory notes about the capability-warning
surfacing and the per-adapter scope of the CR-01 guard.

`.planning/WINDOWS.md` #3 (deferred positive structural probe marker) and #4 (probe() is not a
proxy for fetch()) remain `open` and are deliberately deferred to the operator/human decision
at phase verification; they are **not** re-reported here.

## Remediation verified

### CR-01 — a board block reported as a clean, empty `done` run → **RESOLVED**

`app/sources/linkedin.py:145-157` and `app/sources/indeed.py:140-152` now classify a zero-row
frame instead of returning `ok`:

```python
rows = frame_rows(frame)
if not rows:
    _, note = classify_response(status_code=None, parsed_items=0)
    return FetchResult(source=NAME, status="partial", requests_used=1, error=note)
```

End-to-end trace with the exact `JobResponse(jobs=[])` path: JobSpy catches its own 429/403 and
returns `JobResponse(jobs=[])` (`.venv-host/.../jobspy/linkedin/__init__.py:134-139`) →
`scrape_jobs` returns `pd.DataFrame()` (`jobspy/__init__.py:221`) → `frame_rows` yields `[]` →
`partial` + note → `run_pipeline` appends a `{source, status, error}` entry to `errors_json`
(`app/pipeline/run.py:310-317`) and computes `status = "partial"` (`run.py:326-332`). The run is
no longer `done`, `errors_json` is no longer empty, and the fragment renders the degraded
paragraph. The ledger verdict is now identical to `FetchResult.error` (both
`parse-side: the request returned no rows`), so the prior contradiction is gone. Regression
pinned by `tests/sources/test_linkedin.py`, `tests/sources/test_indeed.py`,
`tests/pipeline/test_partial_failure.py::test_a_zero_row_frame_is_not_a_done_run`, and
`tests/probe/test_thresholds.py::test_a_zero_row_partial_is_still_recorded_as_parse_side`.
I re-checked the remaining paths that could produce a green `done`: an empty frame → `partial`;
a raised `UnsupportedFrameError` from `frame_rows` (outside `fetch`'s try) is caught by
`_fetch_one`'s belt-and-braces handler → `error` → `partial`; zero adapters → `NO_SOURCES_REASON`
→ `partial`; all-items-failed-to-persist → `partial` (WR-01). No path to a fully green `done`
with an empty `errors_json` remains for the shipped adapters.

### WR-01 — persist failures invisible, run still `done` → **RESOLVED**

`app/pipeline/run.py:323-332` sums the per-source `failed` counts and requires it to be zero for
`done`; `app/web/templates/html/_run_status.html:13` renders `— {{ counts.failed }} failed`.
Verified by
`tests/pipeline/test_partial_failure.py::test_a_run_whose_every_item_failed_to_persist_is_not_done`,
which drives a real adapter with no `sources` FK row, asserts `status == "partial"`,
`failed == 1`, and that the fragment contains `1 failed`. The `created + updated + failed ==
len(items)` invariant in `_persist_result` means a non-empty `ok` fetch with zero failures
always persisted at least one row, so `done` is now sound.

### WR-02 — dead `DATABASE_URL` in compose.yml → **RESOLVED**

`compose.yml:19` now sets `DATABASE_URL_ASYNC=sqlite+aiosqlite:////data/jobsearch.db` — the
actual `Settings` field (`app/config.py:27`); `DATABASE_URL_SYNC` was already correct. Guarded
by two non-vacuous tests in `tests/test_deploy_manifest.py`
(`test_compose_database_url_keys_are_real_settings_fields`,
`test_compose_sets_the_async_database_url_key`): the parser asserts at least one key was found,
maps each `DATABASE_URL*` key against `Settings.model_fields`, and explicitly rejects the bare
dead key. I confirmed the parser handles both the list and dict `environment:` forms.

### WR-03 — R3 capability warnings never fired on the run path → **RESOLVED**

`app/pipeline/run.py:107-132` compiles each query against the adapter's declared capabilities
before fetching (`compile_query_for_source`) and records every dropped-filter warning as an
`errors_json` entry; `_fetch_all` now carries the warnings through as tuples.
`app/sources/linkedin.py:116-121` forwards `hours_old`/`easy_apply` when set, and both are
omitted when unset. I verified the real default path is unaffected: `default_query()` sets only
keywords/location/results_wanted, so `compile_query_for_source` produces no warnings and the
compiled query is identical. Pinned non-vacuously by
`tests/pipeline/test_partial_failure.py::test_a_filter_the_board_cannot_honour_is_recorded_not_dropped`
(asserts `salary_floor`/`seniority` warnings recorded, both stripped from the query the adapter
received) and `tests/sources/test_linkedin.py` (forwards-when-set / omits-when-unset). The
exclusive `{hours_old, easy_apply}` group is now arbitrated by the compiler before `build_kwargs`,
so at most one survives.

### WR-04 — a transport error recorded as parse-side → **RESOLVED**

`app/sources/base.py:148-169` gained a `transport_error` argument whose branch takes precedence;
`app/sources/_ledger.py:91-99` sets it only for `result_status == "error"`, and
`app/pipeline/run.py:200` passes `result.error` through. `classify_block_vs_parse`
(`app/probe/survival.py:434-439`) now also maps `status == "error"` to fetch-side. Confirmed a
zero-row `partial` (CR-01's new status) is still parse-side, keeping the ledger consistent with
the adapter. Pinned by
`tests/probe/test_thresholds.py::test_a_transport_error_is_recorded_as_fetch_side` (asserts the
message is carried and the note starts `fetch-side`),
`test_s5_classifies_a_transport_error_status_as_fetch_side`, and
`test_a_zero_row_partial_is_still_recorded_as_parse_side`.

## Critical Issues

None.

## Warnings

None.

## Info

The following are unchanged from the prior review (none touches a remediated code path — the
remediation changed only `run.py`, `survival.py`'s `classify_block_vs_parse`, `_ledger.py`,
`base.py`, both adapters, `_run_status.html` and `compose.yml`) unless marked **(new)**.

### IN-01: `_as_tuple("")` yields `("",)` rather than `()`

**File:** `app/sources/_jobspy_mapping.py:200-203` — unchanged. Latent (JobSpy emits `None` for
an empty list); fix: `if not text: return ()` before the split.

### IN-02: `source_extras` bypasses the sanitise stage and is persisted raw

**File:** `app/ingest/sanitize.py:47-53`, `app/pipeline/stages.py:114` — unchanged. The control
holds today only because `EXTRA_FIELDS` is four non-PII columns; harden if a future adapter can
populate it.

### IN-03: The probe/fetch discrepancy is correctly deferred

**File:** `app/sources/indeed.py:42-49`, `app/sources/linkedin.py:50-52` — the `PROBE_*`
constants are untouched and the deferral stands (WINDOWS #3/#4). If the probe is re-pointed,
route `PROBE_MIN_BODY_BYTES` through `Settings`; no code change warranted now.

### IN-04: A failure in `_finish` leaves the run `running` forever

**File:** `app/pipeline/run.py:338-344`, `app/api/runs.py:65-67` — unchanged: `_finish` is still
outside the `try`, and the task done-callback does not retrieve `task.exception()`. Fix: wrap
`_finish` (or move it inside the `try`) and log the task exception.

### IN-05: S5/S6 have no producer, so they cannot fire on real data

**File:** `app/probe/survival.py:417-478` — still true (WR-04 extended `classify_block_vs_parse`
but it remains uncalled in production; nothing captures the returned frame columns for S6).
`raw_hash` (`app/db/repositories/listing_repo.py:198-211`) is still write-once/never-read. Phase-8
item.

### IN-06: Duplicated `_populated` / `is_populated`

**File:** `app/db/repositories/source_repo.py:71`, `app/probe/survival.py:167` — unchanged;
reuse one predicate.

### IN-07 (new): A `done` run can carry capability warnings that the fragment never renders

**File:** `app/web/templates/html/_run_status.html:20-34`, `app/pipeline/run.py:305`

The WR-03 fix appends `{"source": <name>, "status": "warning", ...}` entries to `errors_json`
while leaving `status == "done"` (correctly — the fetch succeeded). The fragment only surfaces
`errors_json` when `run.status == "partial"`/`"failed"`, so a `done` run can now have a
non-empty `errors_json` that the UI hides; previously `done` implied `errors_json is None`. This
is unreachable today (no Phase-1 UI sets a capability-filtered field — `default_query()` sets
none), and R3's stated requirement is only "recorded". Recommendation, not a defect: either
render warning-severity entries for a `done` run, or document the new `done ⇒ errors_json may be
non-empty` invariant for downstream consumers.

### IN-08 (new): The CR-01 zero-row guard is per-adapter, not central

**File:** `app/pipeline/run.py:326-332`

`done` requires `results` non-empty and every `result.status == "ok"`, but not `fetched > 0`.
Both shipped adapters now classify an empty frame as `partial`, so no current path produces the
false success. Because "adding a source is a one-module change" is an explicit phase goal
(SRC-04), a future third adapter that returns `ok` with `[]` on a block would reintroduce CR-01
silently. Recommendation: add `sum(int(c.get("fetched", 0)) for c in source_counts.values()) > 0`
to the `done` condition as defence-in-depth, and/or a registry-contract test. Advisory only — I
did not treat this as a Warning because no shipped code path reaches it.

---

_Reviewed: 2026-09-15T21:39:07Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
