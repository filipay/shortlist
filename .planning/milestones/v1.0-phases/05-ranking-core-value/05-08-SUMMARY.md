---
phase: 05-ranking-core-value
plan: 08
subsystem: ui
tags: [ranking, observability, queue-strip, jinja2, run-repo, gap-closure]

# Dependency graph
requires:
  - phase: 05-ranking-core-value
    provides: "05-02's ranked_count / candidate_count and 05-05/05-07's ratio rules (the strip's denominator semantics)"
  - phase: 05-ranking-core-value
    provides: "05-06's single `fact_store_absent` reason for the absent/unreadable/non-decodable CV store"
provides:
  - "runs.reason_counts_json['ranking'] — a persisted, machine-readable ranking outcome written by _finish"
  - "RANK_SKIP_* constants + RANK_SKIP_LABELS: the one definition of the four skip reasons and their human sentences"
  - "ranking_skip_reason() synchronous precheck and ranking_in_progress() render-time seam"
  - "RunSummary.ranking_status/ranking_reason and RunSummary.ranking_state(in_progress=...)"
  - "the queue #ranking-strip's five states (ranked / running / skipped+reason / not_attempted / unknown)"
affects: [05-09 detail-page state copy, 05-10, gsd-verify-work]

# Actuals (#2632) — pairs with the plan's estimate (42000 tokens / 3 tasks, confidence low).
# Same estimateTokens scale (chars/4 over the realized diff), never a harness token count.
actuals:
  tokens: 4541
  tasks: 3
  commits: 3
  plan_head_before: 5e345cf7631446aacdb268c8c1995c0488f1ad53

tech-stack:
  added: []
  patterns:
    - "Derived-not-persisted lifecycle state: terminal outcomes are persisted; a live/in-progress state is derived at render time from an in-process probe, so a crash degrades to an honest 'unknown' rather than a permanent claim"
    - "Single-writer JSON bag: one new sub-key rides an existing Column(JSON) and is written only by _finish, because _finish assigns the bag wholesale"
    - "Total read-model parser: the read boundary never raises on a hand-edited/older row; unknown shapes degrade to the generic truthful sentence"

key-files:
  created: []
  modified:
    - app/pipeline/rank.py
    - app/pipeline/run.py
    - app/db/repositories/run_repo.py
    - app/web/routes.py
    - app/web/templates/html/queue.html
    - tests/pipeline/test_rank_optional.py
    - tests/api/test_queue_ranked.py

key-decisions:
  - "Reuse runs.reason_counts_json for the marker instead of adding a ranking_status/ranking_reason column: no Alembic revision (head stays 0004), no migration-contract test churn, and existing readers ignore the unknown sub-key"
  - "ranking_outcome is computed synchronously in run_pipeline and written by _finish; the detached ranking task never writes it (D-88 single-writer rule), because _finish clobbers the bag wholesale"
  - "running is NOT persisted — it is derived at render time from rank.ranking_in_progress(); startup recovery is deliberately absent, so a persisted 'running' would read in-progress forever after a crash/restart"
  - "The ranking task is still STARTED on every skip path (the precheck only records the reason), preserving the test that pins the task entry point is reached with an absent fact store"
  - "A persisted skip marker is checked before the live-task probe, so a skip is authoritative over a live task"

patterns-established:
  - "Terminal-persisted / live-derived state split (see above) — reusable wherever an in-process task's liveness is shown but its liveness is not durable"
  - "Reason vocabulary as module constants + a label map, read by the writer, the precheck and the render layer from one place"

requirements-completed: [UI-01, RANK-08]

coverage:
  - id: D1
    description: "A skipped ranking pass leaves a persisted, machine-readable outcome on the run: reason_counts_json['ranking'] = {'status': 'skipped', 'reason': <constant>}, written by _finish; the no-candidates gate leaves {'status': 'not_attempted'}"
    requirement: RANK-08
    verification:
      - kind: unit
        ref: "tests/pipeline/test_rank_optional.py#test_ranking_disabled_writes_nothing_and_the_run_is_done"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_rank_optional.py#test_no_fact_store_writes_nothing_and_the_run_is_done"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_rank_optional.py#test_unreadable_fact_store_writes_nothing_and_the_run_is_done"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_rank_optional.py#test_non_utf8_fact_store_writes_nothing_and_the_run_is_done"
        status: pass
    human_judgment: false
  - id: D2
    description: "The queue strip distinguishes all five states of the latest run — ranked (Ranked N / Ranked N of M), running, skipped + human reason, not_attempted, unknown — so 'running' and 'skipped' no longer render identically"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_ranking_strip_names_the_skip_reason"
        status: pass
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_ranking_strip_shows_nothing_to_rank_for_a_not_attempted_run"
        status: pass
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_ranking_strip_shows_in_progress_while_a_pass_is_running"
        status: pass
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_ranking_strip_reports_the_runs_own_candidate_count"
        status: pass
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_ranking_strip_with_zero_candidate_count_renders_no_ratio"
        status: pass
    human_judgment: false
  - id: D3
    description: "running is derived at render time and never persisted, so an interrupted (crashed/restarted) pass reads 'has not completed', never a permanent 'in progress', and a persisted skip is authoritative over a live task"
    verification:
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_ranking_strip_says_not_completed_when_no_pass_is_running"
        status: pass
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_ranking_strip_prefers_a_persisted_skip_over_a_live_task"
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-09-23
status: complete
---

# Phase 05 Plan 08: The ranking outcome is persisted and rendered Summary

**The ranking pass's outcome now survives the run — `_finish` writes a named skip/not-attempted marker into the existing counts JSON, and the queue strip renders five distinct states instead of one blank, so "ranking is running" and "ranking was skipped, because X" are finally different screens.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-09-23T10:09:35Z
- **Completed:** 2026-09-23T10:22:10Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- **Gap G-05-1 closed.** A run whose ranking pass did not complete now carries a persisted, machine-readable outcome: `runs.reason_counts_json['ranking']` is `{"status": "skipped", "reason": "<ranking_disabled|fact_store_absent|ranking_in_flight|rank_start_failed>"}` or `{"status": "not_attempted"}`. It is computed synchronously in `run_pipeline` and written by `_finish` in its single commit — never by the detached task, whose earlier write `_finish` would clobber wholesale (D-88).
- **The queue strip is now a truthful progress statement.** `#ranking-strip` renders `Ranked N` / `Ranked N of M`, `Ranking in progress. …`, `Ranking skipped — <human reason>.`, `Nothing to rank on the last run.` and `Ranking has not completed for the last run.` — the five states 05-UAT.md reported as conflated into one blank strip.
- **The staleness hazard is designed out.** `running` is never persisted; it is derived at render time from the live single-flight task (`rank.ranking_in_progress()`). A crash or restart leaves no marker and degrades to the honest `unknown`, so a pass can never read "in progress" forever.
- **The reason vocabulary has exactly one definition** (`RANK_SKIP_*` + `RANK_SKIP_LABELS` in `app/pipeline/rank.py`), read by both `run_ranking`'s own guards, the precheck and the render layer, so the strings cannot drift.
- **05-05/05-07's ratio rules are untouched:** `Ranked 5 of 30` still renders, an absent/non-positive candidate count still renders the numerator alone, and no ratio is ever printed against the request's page total.

## Task Commits

Each task was committed atomically:

1. **Task 1: A skipped pass leaves a durable, machine-readable reason written by `_finish`** - `453cef4` (feat)
2. **Task 2: The run read model derives the five ranking states and the strip renders each one** - `41ffcb0` (feat)
3. **Task 3: Pin the persisted marker and every strip state with first-class tests** - `09598ce` (test)

**Plan metadata:** committed separately after this SUMMARY (docs).

## Files Created/Modified

- `app/pipeline/rank.py` — `RANK_SKIP_DISABLED` / `RANK_SKIP_FACT_STORE` / `RANK_SKIP_IN_FLIGHT` / `RANK_SKIP_START_FAILED` + `RANK_SKIP_LABELS`; `ranking_skip_reason()`; `ranking_in_progress()`; `start_ranking_task` now returns `str | None`; the two `run_ranking` skip branches log the constants; `__all__` extended.
- `app/pipeline/run.py` — `ranking_outcome` initialised before the outer `try`; the ranking block computes the skipped reason (in-flight wins over precheck), the not-attempted marker and the start-failed marker; the marker is merged into `reason_counts` before `_finish`. `_finish` itself unchanged.
- `app/db/repositories/run_repo.py` — the total `_ranking_marker` parser; `RunSummary.ranking_status` / `ranking_reason`; the pure `RunSummary.ranking_state(in_progress=...)`.
- `app/web/routes.py` — module-level by-name import of `RANK_SKIP_LABELS` and `ranking_in_progress`; `_ranking_strip` returns `state` / `reason` / `reason_label` alongside the unchanged `ranked` / `candidates` / `cap_reason`.
- `app/web/templates/html/queue.html` — the five-branch `#ranking-strip` gated on `state`; no `|safe`, no new class, no JS, no poll target.
- `tests/pipeline/test_rank_optional.py` — `_assert_skipped(reason=...)` now asserts the persisted marker; four call sites pass the module constants.
- `tests/api/test_queue_ranked.py` — `_seed_run_with_ranking` helper and five strip-state regression tests over the `routes_module.ranking_in_progress` monkeypatch seam.

## Decisions Made

- **Reuse `runs.reason_counts_json`, not a new column.** A dedicated `ranking_status`/`ranking_reason` column would cost an Alembic revision (`0005`) plus the two pinned migration-contract tests, and would only be needed if the detached task wrote directly — which this design does not require, because the reason is knowable synchronously before `_finish`. Head stays `0004`; no existing reader changes meaning (`run_counts_for` reads named keys).
- **`_finish` is the sole writer; the detached task writes nothing.** `_finish` assigns `reason_counts_json = reason_counts or None` wholesale, so any task-side write is clobbered. The marker therefore rides the payload handed to `_finish`.
- **`running` is derived, never persisted.** `rank.py:31-34` documents that startup recovery is deliberately absent; a persisted "running" would read in-progress forever after a crash. Only terminal outcomes are persisted; the live state is a render-time snapshot (D-88 refresh-only — no polling, no SSE, no new poll target).
- **The task is still started on a skip.** `tests/pipeline/test_finish_llm_counters.py:145-175` exists to prove the ranking entry point is reached with an absent fact store. The precheck RECORDS the reason without preventing the start; `run_ranking` returns immediately on its own guard.
- **No logging from the precheck.** `run_ranking` keeps emitting the one `pipeline.rank_skipped` line so `tests/pipeline/test_rank_optional.py`'s capture-span assertion still passes and the log is not duplicated.

## Deviations from Plan

### Auto-fixed Issues

None — no Rule 1/2/3 fix was needed; the implementation ran on the existing stdlib + installed stack, with no package install and no migration.

### Plan acceptance-criteria inaccuracies (documented, not "fixed" by contorting the code)

The plan's Task 1 and Task 3 acceptance-criteria greps contain two counts that are internally inconsistent with the plan's own prescribed actions. The actions were followed exactly; the greps below are the inaccurate ones:

1. **Task 1, `grep -n "ranking_skip_reason" app/pipeline/run.py` "reports one match" — actual: 2.**
   - **Cause:** Step 7 explicitly requires importing `ranking_skip_reason` into `run.py`, and step 9 explicitly requires calling it. That is necessarily two lines (import at `run.py:45`, call at `run.py:921`).
   - **Impact:** None on behaviour. Every other Task 1 grep and the three Python assertions pass as written.

2. **Task 3, `grep -c "routes_module.ranking_in_progress" tests/api/test_queue_ranked.py` "returns at least 3" — actual: 0.**
   - **Cause:** The plan's own prescribed mechanism is `monkeypatch.setattr(routes_module, "ranking_in_progress", ...)` — the probe name is a string argument, so the literal text `routes_module.ranking_in_progress` never appears. The intent (three tests patch the probe) is met: the seam is patched in the in-progress, not-completed and authoritative-skip tests.
   - **Impact:** None on behaviour; the five named strip-state tests — the substantive acceptance criterion — all pass.

## Issues Encountered

- One self-inflicted edit slip during Task 2 (a trailing-newline mismatch briefly merged `_duration`'s signature with its docstring) was caught immediately by the editor's diagnostics and corrected before any test run. No effect on the committed result.

## User Setup Required

None - no external service configuration required. No package installed, no migration, no schema change, no CDN asset, no polling.

## Next Phase Readiness

- The observability half of RANK-08 and the state-rendering half of UI-01 are now shipped. The refusal-audit semantics of RANK-08 remain flagged (this plan touched no refusal decision), and UI-02's detail-page state copy is plan 05-09's.
- Plan 05-09 can consume `RunSummary.ranking_state` / `ranking_status` / `ranking_reason` and `RANK_SKIP_LABELS` directly to render the same five states on the run-detail page without re-deriving them.
- Full suite green: `1053 passed, 14 deselected, 2 xfailed`. Build (`compileall -q app`) green.

---
*Phase: 05-ranking-core-value*
*Completed: 2026-09-23*

## Self-Check: PASSED

- FOUND: `.planning/phases/05-ranking-core-value/05-08-SUMMARY.md`
- FOUND commit: `453cef4` (Task 1)
- FOUND commit: `41ffcb0` (Task 2)
- FOUND commit: `09598ce` (Task 3)
- Full suite: `1053 passed, 14 deselected, 2 xfailed`; build `compileall -q app` clean.
