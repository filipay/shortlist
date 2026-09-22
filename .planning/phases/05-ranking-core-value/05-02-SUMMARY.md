---
phase: 05-ranking-core-value
plan: 02
subsystem: ranking
tags: [ranking, spend-cap, asyncio, sqlalchemy, settings, compose, pytest]

# Dependency graph
requires:
  - phase: 05-ranking-core-value
    provides: the ranking stage, the `llm_calls` audit writer and the `scores` writer from plan 05-01
provides:
  - "Settings.ranking_max_calls_per_run / ranking_max_calls_per_day / ranking_enabled, with compose.yml and .env.example wiring"
  - "llm_call_repo.rank_calls_since and rank_cap_reason_for_run"
  - "reserve-then-call enforcement (_reserve_lock, _in_flight, _reserve, _release) in app/pipeline/rank.py"
  - "the D-94 optional posture, the _RANKING_TASK single-flight guard and the runs.ranked_count / llm_calls / llm_tokens writer"
  - "the D-102 rewrites of the two retired zero-LLM guards"
affects: [05-04, 08-scheduler]

# Actuals (#2632) — same estimateTokens scale (chars/4 over the realized diff).
actuals:
  tokens: 11127
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Reserve-then-call under an asyncio.Lock: a ceiling checked before the request, never after"
    - "Graceful cap stop: one refusal row with the cap name in the error text, run stays done"
    - "Start-or-skip single-flight detached task; no persistent job queue"
    - "Settings-driven optional feature: one off switch plus two state conditions (fact store absent/unreadable)"

key-files:
  created:
    - tests/pipeline/test_rank_caps.py
    - tests/pipeline/test_rank_optional.py
  modified:
    - app/config.py
    - app/db/repositories/llm_call_repo.py
    - app/pipeline/rank.py
    - app/api/settings.py
    - compose.yml
    - .env.example
    - tests/test_config.py
    - tests/pipeline/test_finish_llm_counters.py
    - tests/pipeline/test_filter_stage.py
    - tests/api/test_settings_reset.py

key-decisions:
  - "Every ranking call writes one `llm_calls` row, so both ceilings are measured from a single ledger; the refusal row uses `budget_exceeded: per_run|per_day` in the error text because the table has no `error_kind` column"
  - "The rolling-24h read accepts a full scan on the unindexed `llm_calls.created_at`; no index migration, recorded in the docstring so it is not 'optimised' into a second source of truth"
  - "`ranking_enabled` is checked before the filesystem or backend, so the off switch costs nothing"
  - "The in-flight counter is module-level and single-process, marked with a `ponytail:` comment naming the advisory-lock upgrade path"

patterns-established:
  - "A cap refusal is a value, not an error: the loop stops, the run stays `done`, and the cause is auditable"
  - "D-102: a retired guard is rewritten to assert the new reason, never deleted"

requirements-completed: [RANK-08]

coverage:
  - id: D1
    description: "Two ranking spend ceilings and an operator off switch as Settings fields, environment-tunable, forwarded by compose.yml and documented in .env.example, with the numeric pair covered by LIMIT_FIELDS and the literal scan"
    requirement: RANK-08
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_the_phase_five_ceilings_are_guarded"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_the_phase_five_ceilings_are_environment_tunable"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_ranking_enabled_is_environment_tunable"
        status: pass
    human_judgment: false
  - id: D2
    description: "A call is refused BEFORE the request when either the per-run or the rolling-24h ceiling would be reached, and the rolling total comes from one aggregate read over the llm_calls ledger"
    requirement: RANK-08
    verification:
      - kind: unit
        ref: "tests/pipeline/test_rank_caps.py#test_cap_refuses_before_the_call"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_rank_caps.py#test_rolling_24h_cap_is_enforced"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_rank_caps.py#test_reserve_returns_true_exactly_once_at_the_ceiling"
        status: pass
    human_judgment: false
  - id: D3
    description: "A refused call writes exactly one refusal row (purpose rank, status error, cause in the error text) rather than an error or a silent stop"
    requirement: RANK-08
    verification:
      - kind: unit
        ref: "tests/pipeline/test_rank_caps.py#test_cap_refuses_before_the_call"
        status: pass
    human_judgment: true
    rationale: "RANK-08's probe row is unclassified and unresolved: the requirement does not state whether a refused call writes an audit row. This plan chose the D-93 optional refusal row so 'enforced before the call was made' is auditable; the alternative (no row, rely on runs.ranked_count) remains a legitimate reading a human should confirm."
  - id: D4
    description: "Ranking is optional (disabled / no fact store / unreadable fact store each write nothing and leave the run done), at most one ranking task runs at a time, and the task owns runs.ranked_count / llm_calls / llm_tokens"
    requirement: RANK-08
    verification:
      - kind: unit
        ref: "tests/pipeline/test_rank_optional.py"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_finish_llm_counters.py#test_a_pipeline_run_writes_zero_llm_calls"
        status: pass
      - kind: integration
        ref: "tests/db/test_reset_coverage.py"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-09-22
status: complete
---

# Phase 5 Plan 2: Spend caps enforced before the call, and the detached ranking lifecycle Summary

**Two spend ceilings refused before the request under an `asyncio.Lock`, a rolling-24h ledger read, the D-94 optional posture, a start-or-skip single-flight ranking task, and the D-102 rewrites of the two retired zero-LLM guards**

## Performance

- **Duration:** 20 min
- **Started:** 2026-09-22T12:17:32Z
- **Completed:** 2026-09-22T12:37:45Z
- **Tasks:** 3
- **Files modified:** 12 (2 created, 10 modified)

## Accomplishments

- `Settings` gained `ranking_max_calls_per_run` (40), `ranking_max_calls_per_day`
  (400) and `ranking_enabled` (True), each forwarded by `compose.yml` and
  documented in `.env.example`; the numeric pair joined `LIMIT_FIELDS` and the
  distinctive-literal scan, the switch deliberately did not.
- `llm_call_repo.rank_calls_since` is the per-day cap's single aggregate read over
  the unindexed `llm_calls` ledger (full scan accepted, recorded in the docstring);
  `rank_cap_reason_for_run` is the cap-reason surface read for plan 05-04.
- `app/pipeline/rank.py` now enforces both ceilings **before** each call via
  `_reserve`/`_release` under a module-level lock. A refusal ends the pass
  gracefully: no exception, the run is not marked failed, and one refusal row
  records which cap fired in the `error` text.
- The D-94 posture is complete: `ranking_enabled` is checked first (before the
  filesystem or backend), then the fact store's absence or unreadability. All three
  paths write zero `llm_calls` and zero `scores` rows and leave `runs.status` at
  `"done"`.
- `start_ranking_task` is start-or-skip: a run whose ranking would overlap an
  in-flight task is skipped, not queued, and the in-flight task continues.
- The ranking task now owns the run's LLM accounting: `runs.ranked_count` is the
  number of listings with a score row at write time (D-89), plus `llm_calls` and
  `llm_tokens` from the ledger. `_finish` still never touches `ranked_count`.
- The two retired zero-LLM guards now assert the D-94 posture explicitly, with the
  ranking task entry point proven to have been reached and returned early.

## Task Commits

Each task was committed atomically:

1. **Task 1: The two spend ceilings as Settings fields, with their three operator surfaces** - `d59f9e8` (feat)
2. **Task 2: The rolling-24h ledger read, the cap-reason read, and reserve-then-call** - `bad11c9` (feat)
3. **Task 3: The optional posture, the single-flight lifecycle, and the D-102 guard rewrites** - `22948ac` (feat)

**Plan metadata:** `PENDING` (docs: complete plan)

## Files Created/Modified

- `app/config.py` - the Phase-5 block: two ceilings and `ranking_enabled`, with the D-91 token-cap rejection documented
- `app/db/repositories/llm_call_repo.py` - `rank_calls_since`, `rank_cap_reason_for_run`, `BUDGET_EXCEEDED_MARKER`, `RANK_CALL_WINDOW`
- `app/pipeline/rank.py` - `_reserve_lock`/`_in_flight`/`_cap_hit`/`_reserve`/`_release`, the capped loop with the graceful-stop refusal row, the `ranking_enabled` skip, the `_RANKING_TASK` single-flight guard, and the run-accounting writer
- `app/api/settings.py` - `"ranking_config"` added to `RESET_KEPT_TABLES`
- `compose.yml`, `.env.example` - all three keys forwarded and documented with the refusal semantics
- `tests/test_config.py` - `PHASE_FIVE_CEILINGS`, the guarded/environment-tunable tests
- `tests/pipeline/test_rank_caps.py` - refuse-before-the-call, the rolling window, the reservation primitive
- `tests/pipeline/test_rank_optional.py` - the three skip paths and the start-or-skip case
- `tests/pipeline/test_finish_llm_counters.py`, `tests/pipeline/test_filter_stage.py` - the D-102 guard rewrites
- `tests/api/test_settings_reset.py` - seeds the kept weights row (see Deviations)

## Decisions Made

- Both ceilings are measured from the single `llm_calls` ledger: every ranking call
  (success or failure, per 05-01) writes one row, and a refusal writes one more.
- The refusal cause is `budget_exceeded: per_run|per_day` in the `error` text — the
  table has no `error_kind` column, and one marker vocabulary (`BUDGET_EXCEEDED_MARKER`)
  is minted in the repository.
- The per-run ceiling is named first when both would fire, so the operator gets a
  deterministic cause.
- The in-flight counter is module-level and single-process; the `ponytail:` comment
  names the advisory-lock upgrade path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The reset-coverage test broke when `ranking_config` joined the kept list**
- **Found during:** Task 3 (the full hermetic suite)
- **Issue:** `tests/api/test_settings_reset.py::test_a_correct_token_empties_the_corpus_and_keeps_configuration`
  asserts every `RESET_KEPT_TABLES` entry has rows after a reset. The seed created
  none for the newly-kept `ranking_config`, so the assertion failed. The plan lists
  `tests/api/test_settings_reset.py` nowhere in `files_modified`.
- **Fix:** `_seed_corpus` now seeds one `RankingConfig` row, which is also the
  stronger assertion — it proves the user's weights survive a reset (D-99).
- **Files modified:** `tests/api/test_settings_reset.py`
- **Verification:** `tests/api/test_settings_reset.py` and `tests/db/test_reset_coverage.py` pass; the full hermetic suite is green.
- **Committed in:** `22948ac`

**2. [Rule 3 - Blocking] The plan's `.venv-host/bin/python` is unusable**
- **Found during:** Task 1 (first verify run)
- **Issue:** `.venv-host/bin/python` is Python 3.14 with a missing
  `pydantic_core._pydantic_core`; the import of `pydantic` aborts during conftest
  load. Same defect 05-01 hit.
- **Fix:** Ran every `<verify>` under `.venv/bin/python`, matching the harness's
  declared test command.
- **Files modified:** none
- **Verification:** all listed verify commands pass under `.venv/bin/python`.

**3. [Rule 3 - Blocking] The `error_kind=` acceptance grep**
- **Found during:** Task 2 (acceptance check)
- **Issue:** The acceptance requires `grep -c "error_kind=" app/pipeline/rank.py`
  to return 0, but the module docstring contained a prose sentence with the literal
  `error_kind=`.
- **Fix:** Reworded the docstring to "there is no such keyword to pass to
  `record_llm_call`", preserving the meaning without the token.
- **Files modified:** `app/pipeline/rank.py`
- **Verification:** `grep -c "error_kind=" app/pipeline/rank.py` returns 0.
- **Committed in:** `bad11c9`

**4. [Rule 2 - Missing Critical] Proving the ranking task entry point was reached**
- **Found during:** Task 3 (writing the D-102 guard rewrite)
- **Issue:** The plan asks the rewritten guard to assert the task "was reached and
  returned early" but gives only an example. Asserting zero rows alone cannot
  distinguish "reached and skipped" from "never launched".
- **Fix:** Added `drain_ranking_tasks()` to `tests/pipeline/test_rank_optional.py`
  (used by both new and rewritten tests) and a spy around `run_ranking` in
  `test_a_pipeline_run_writes_zero_llm_calls` that records the call. The test now
  asserts no `purpose="rank"` row AND that the entry point was reached.
- **Files modified:** `tests/pipeline/test_rank_optional.py`, `tests/pipeline/test_finish_llm_counters.py`
- **Verification:** both tests pass.
- **Committed in:** `22948ac`

---

**Total deviations:** 4 auto-fixed (1 bug, 1 missing-critical, 2 blocking)
**Impact on plan:** No scope creep. The reset-coverage fix is the only edit outside
the plan's `files_modified`, and it is a direct consequence of the required
`RESET_KEPT_TABLES` change.

## Issues Encountered

- A module-level `asyncio.Lock` is reused across pytest-asyncio's per-function event
  loops. It works because CPython's `Lock.acquire` only calls `_get_loop()` on the
  contended path; the ranking task is single sequential, so there is never
  contention. The full suite (multiple tests across loops) proves this empirically.

## Known Stubs

None. Every skip path returns before any write, and the refusal path writes an
honest row rather than a placeholder.

## Threat Flags

None beyond the plan's threat model. T-05-07 is verified by
`test_cap_refuses_before_the_call` (zero further requests after the cap fires);
T-05-08's full-scan acceptance is recorded in the `rank_calls_since` docstring;
T-05-09's lock + `finally` release are exercised by the reservation tests; T-05-10's
refusal audit is asserted; T-05-11's single-flight guard is asserted.

## Next Phase Readiness

- Plan 05-04 can render "ranked X of Y — cap reached" from
  `rank_cap_reason_for_run` and `runs.ranked_count`, both now written.
- Plan 08's scheduler can call `run_pipeline` unchanged: ranking remains optional and
  the caps bound a scheduled run exactly as they bound a manual one.
- Open (the plan's flagged assumption): whether a refused call should write an audit
  row at all remains a human decision; this plan chose the D-93 refusal row.

## Self-Check: PASSED

- Both created files exist on disk.
- All three commits (`d59f9e8`, `bad11c9`, `22948ac`) exist in the history.
- `commits: 3` was measured from the plan ledger
  (`plan_head_before = 450acd3a0016b2016bb70209420124058dc01444`).

---
*Phase: 05-ranking-core-value*
*Completed: 2026-09-22*
