---
phase: 08-operations-polish
plan: 03
subsystem: infra
tags: [apscheduler, scheduler, sqlite, alembic, fastapi, lifespan, settings, singleton-config]

requires:
  - phase: 08-operations-polish
    provides: 08-01 (the pinned apscheduler==3.11.3 dependency and the single-worker rationale)
  - phase: 05-ranking
    provides: RankingConfig's singleton-config precedent (migration 0004) and run_repo
  - phase: 03-run-pipeline
    provides: run_pipeline (the one pipeline entry point) and TERMINAL_STATUSES

provides:
  - the singleton operations document (migration 0008, OperationsConfig) carrying schedule, retention and skip-notice JSON
  - operations_config_repo: total schedule read, validated SAVEPOINT write, skip-notice read/write
  - app/jobs/scheduler.py: AsyncIOScheduler over a sync SQLAlchemyJobStore, create-if-absent reconcile, the argument-free scheduled target, the in-flight DB guard, the two D-154 event listeners, boot-time stale-run reconciliation, a total next-run accessor
  - POST /settings/schedule and the Schedule settings card (runtime-editable, no restart)
  - run_repo.running_run_id — the ONE shared definition of "a run is in flight"
  - docs/runbook-compose-smoke.md's PLAT-06 schedule-persistence operator step

affects: [08-04 (the health page consumes next_run_at and read_skip_notice), 08-05 (owns retention_json), 09 (any surface reading the schedule)]

actuals:
  tokens: 18956
  tasks: 3
  commits: 3

tech-stack:
  added: []          # apscheduler==3.11.3 was pinned by plan 08-01; this plan only imports it
  patterns:
    - "Boot-time create-if-absent reconciliation: add a persisted job only when absent, reschedule only on trigger drift"
    - "A single shared repository predicate (run_repo.running_run_id) consumed by two guards that must agree"
    - "A durable skip notice stored as JSON on a singleton row rather than a new run status"

key-files:
  created:
    - alembic/versions/0008_operations_config.py
    - app/db/repositories/operations_config_repo.py
    - app/jobs/__init__.py
    - app/jobs/scheduler.py
    - tests/jobs/__init__.py
    - tests/jobs/test_scheduler.py
    - tests/api/test_schedule_settings.py
  modified:
    - app/db/models.py
    - app/db/repositories/run_repo.py
    - app/main.py
    - app/api/settings.py
    - app/web/templates/html/settings.html
    - tests/db/test_migration_contract.py
    - tests/db/test_no_pii_columns.py
    - tests/db/test_skeleton_boot.py
    - tests/db/test_orm_drift.py
    - tests/test_auth_seam.py
    - tests/api/test_settings_reset.py
    - docs/runbook-compose-smoke.md

key-decisions:
  - "Start the scheduler BEFORE reconciling: at STATE_STOPPED get_job only consults pending jobs, so a job persisted by a previous process looks absent and add_job would raise ConflictingIdError out of start() — the scheduler would report unavailable after every restart."
  - "The schedule route takes session_factory via Depends(get_session_factory) rather than calling the module-level factory, so the override seam reaches reconcile."
  - "A skip is recorded as JSON on the operations row, never as a runs row: runs.status is a CHECK and a fifth value would need a batch recreation of runs."
  - "Stale non-terminal runs are reconciled to the literal status 'partial' (not done/failed): the honest outcome for a run whose result is unknown."
  - "The Schedule card sits after the CV fact-store card so the page's first selected <option> remains the layout picker (test_settings_layout's assumption)."

patterns-established:
  - "Boot contract: every lifespan side effect (seeding, scheduler start, stale-run reconciliation) has its own non-fatal guard that logs the exception class name and lets the app serve (D-08)."
  - "Third-party-owned schema tables are exempted by name in the ORM drift guard rather than mirrored in our own migration."

requirements-completed: [RUN-05, PLAT-06]

coverage:
  - id: D1
    description: "Migration 0008 and OperationsConfig: the singleton schedule/retention document, purely additive, with the named singleton CHECK"
    requirement: RUN-05
    verification:
      - kind: unit
        ref: "tests/db/test_migration_contract.py#test_operations_config_table_and_singleton_check"
        status: pass
      - kind: unit
        ref: "tests/db/test_orm_drift.py#test_orm_metadata_matches_migrated_schema"
        status: pass
      - kind: unit
        ref: "tests/db/test_no_pii_columns.py#test_json_columns_are_allow_listed"
        status: pass
    human_judgment: false
  - id: D2
    description: "The settings schedule form persists the time and timezone and leaves exactly one APScheduler job; junk input and an unknown timezone are refused with a 400 and write nothing; disabling removes the job"
    requirement: RUN-05
    verification:
      - kind: unit
        ref: "tests/api/test_schedule_settings.py#test_saving_a_time_registers_exactly_one_job"
        status: pass
      - kind: unit
        ref: "tests/api/test_schedule_settings.py#test_junk_time_returns_400_and_writes_nothing"
        status: pass
      - kind: unit
        ref: "tests/api/test_schedule_settings.py#test_unknown_timezone_returns_400_and_writes_nothing"
        status: pass
      - kind: unit
        ref: "tests/api/test_schedule_settings.py#test_disabling_the_schedule_removes_the_job"
        status: pass
      - kind: unit
        ref: "tests/test_auth_seam.py#test_every_route_with_a_dependant_declares_current_user"
        status: pass
    human_judgment: false
  - id: D3
    description: "A scheduled fire runs the existing pipeline exactly once (trigger 'schedule', null search id) and refuses to overlap a run already in flight"
    requirement: RUN-05
    verification:
      - kind: unit
        ref: "tests/jobs/test_scheduler.py#test_the_target_runs_the_pipeline"
        status: pass
      - kind: unit
        ref: "tests/jobs/test_scheduler.py#test_in_flight_run_is_skipped_not_overlapped"
        status: pass
      - kind: unit
        ref: "tests/api/test_schedule_settings.py#test_the_scheduled_path_refuses_while_a_run_is_in_flight"
        status: pass
    human_judgment: false
  - id: D4
    description: "A missed fire and an in-flight skip each leave a durable notice on the operations row, and no skip ever creates a runs row or a new status value"
    requirement: PLAT-06
    verification:
      - kind: unit
        ref: "tests/jobs/test_scheduler.py#test_a_missed_fire_is_surfaced"
        status: pass
    human_judgment: false
  - id: D5
    description: "The restart contract: reconcile creates only when absent, is idempotent, honours an enabled/disabled flip, preserves a persisted past-due fire time, and reconciles stale running rows to 'partial'"
    requirement: PLAT-06
    verification:
      - kind: unit
        ref: "tests/jobs/test_scheduler.py#test_a_past_due_fire_time_is_not_clobbered"
        status: pass
      - kind: unit
        ref: "tests/jobs/test_scheduler.py#test_reconcile_creates_the_job_when_absent"
        status: pass
      - kind: unit
        ref: "tests/jobs/test_scheduler.py#test_reconcile_is_idempotent"
        status: pass
      - kind: unit
        ref: "tests/jobs/test_scheduler.py#test_reconcile_honours_an_enabled_disabled_flip"
        status: pass
      - kind: unit
        ref: "tests/jobs/test_scheduler.py#test_next_run_at_is_total"
        status: pass
      - kind: unit
        ref: "tests/jobs/test_scheduler.py#test_stale_running_rows_are_reconciled_to_partial"
        status: pass
    human_judgment: false
  - id: D6
    description: "The operator restart check: set a daily time, docker compose restart, confirm the schedule survives and exactly one run with trigger 'schedule' fires (never two)"
    requirement: PLAT-06
    verification:
      - kind: manual_procedural
        ref: "docs/runbook-compose-smoke.md#the-schedule-persistence-step-plat-06"
        status: unknown
    human_judgment: true
    rationale: "Docker is absent from the agent sandbox, so the restart-and-fire check cannot be executed here. Recorded as unrun verify #16 in .planning/WINDOWS.md; a second concurrent schedule-triggers run is the failure only an operator on real containers can catch."

duration: 44min
completed: 2026-10-14
status: complete
---

# Phase 8 Plan 03: The schedule document, the daily job, and the no-overlap guard Summary

**A singleton schedule row plus an in-process `AsyncIOScheduler` that registers the daily job at boot without ever clobbering a persisted fire time, runs the existing pipeline exactly once, skips (and records) any fire that would overlap a run already in flight, and degrades to "unavailable" instead of breaking boot.**

## Performance

- **Duration:** 44 min
- **Started:** 2026-10-14T18:13:09Z
- **Completed:** 2026-10-14T18:57:09Z
- **Tasks:** 3
- **Files modified:** 20 (7 created, 13 modified)

## Accomplishments

- Migration 0008 creates exactly one table, `operations_config` (`id` pinned to 1 by the named `ck_operations_config_singleton`), and the revision is purely additive — it does not touch `runs`, so the status vocabulary is unchanged and `test_upgrade_populated_0001_to_head` cannot be forced into a batch recreation.
- `operations_config_repo` is the only place the row's SQL lives: a total `read_schedule` (absent row or malformed payload → the code-level disabled default), a strictly validated `write_schedule`, and the D-154 skip-notice pair.
- `app/jobs/scheduler.py` ships the whole scheduler slice: `AsyncIOScheduler` over a sync `SQLAlchemyJobStore` carrying the same four SQLite PRAGMAs, an argument-free module-level coroutine target, create-if-absent reconciliation, the database in-flight guard, the missed/max-instances listeners, boot-time stale-run reconciliation, and a total `next_run_at()`.
- The lifespan starts and stops the scheduler inside its own non-fatal guard, so a scheduler that cannot start leaves the app serving.
- `POST /settings/schedule` validates the time and timezone at the boundary, commits the row first, and only then re-configures the live scheduler — a scheduler failure is reported in the banner and never rolls the save back.
- `run_repo.running_run_id` is now the single definition of "a run is in flight"; the reset guard's private helper delegates to it and the scheduler consumes the same coroutine.
- The compose-smoke runbook carries the PLAT-06 operator step, and the step is recorded as unrun verify #16 in the broken-windows ledger.

## Task Commits

Each task was committed atomically:

1. **Task 1: Save a daily time on Settings and see exactly one job registered** - `76c706f` (feat)
2. **Task 2: The scheduled fire runs the pipeline once, never overlapping a run already in flight** - `666078c` (feat)
3. **Task 3: The schedule survives a restart, and its past-due fire time is not clobbered** - `a0cf772` (test)

**Plan metadata:** (SUMMARY commit, below)

## Files Created/Modified

- `alembic/versions/0008_operations_config.py` - the one migration; creates `operations_config`, drops it symmetrically, seeds nothing
- `app/db/models.py` - new `OperationsConfig` class beside `ApplyConfig`, with the named singleton `CheckConstraint`
- `app/db/repositories/operations_config_repo.py` - the row's only SQL: `ScheduleConfig`, `DEFAULT_SCHEDULE`, `ALLOWED_TIMEZONES`, `read_schedule`, `write_schedule`, `read_skip_notice`, `write_skip_notice`
- `app/db/repositories/run_repo.py` - `running_run_id`, the shared in-flight predicate
- `app/jobs/__init__.py` - package marker
- `app/jobs/scheduler.py` - the scheduler, its jobstore engine, `get_scheduler`, `reconcile`, `run_scheduled_pipeline`, `reconcile_stale_runs`, `start_scheduler`, `stop_scheduler`, `next_run_at`, the event listener and its durable-write task set
- `app/main.py` - the lifespan starts/stops the scheduler in its own guard
- `app/api/settings.py` - `SCHEDULE_PATH`, `_parse_schedule_form`, the `save_schedule` route, the `schedule` context key, `operations_config` in `RESET_KEPT_TABLES`, `_running_run_id` delegating, the extended CSRF caveat
- `app/web/templates/html/settings.html` - the `#schedule-card` section (enable checkbox, time input, timezone select, helper copy, save button)
- `tests/jobs/test_scheduler.py` - the scheduler contract lane on a real temp-file job store
- `tests/api/test_schedule_settings.py` - the form round-trip, its two refusal paths, register/reschedule/remove, and the scheduled-path refusal
- `tests/db/test_migration_contract.py`, `tests/db/test_no_pii_columns.py`, `tests/db/test_skeleton_boot.py`, `tests/db/test_orm_drift.py`, `tests/test_auth_seam.py` - the guards updated for 0008, the three JSON columns, the jobstore exemption and the new route
- `tests/api/test_settings_reset.py` - the seeded corpus gained an `operations_config` row (a kept table must hold one)
- `docs/runbook-compose-smoke.md` - the schedule-persistence step plus the "never two concurrent runs" failure statement

## Decisions Made

- **Start, then reconcile** (deviates from the research shape) — see Deviations, Rule 3.
- **The route injects the session factory** via `Depends(get_session_factory)` instead of calling the module-level factory, so the test lane's override reaches `reconcile`. The target still resolves `get_session_factory()` itself, because APScheduler pickles the target's arguments.
- **The skip lives on the operations row** (`last_schedule_skip_json`), not as a new `runs` row or a fifth status; `retention_json` is created by this migration but is written as `{}` and never read here (plan 08-05 owns it).
- **`partial` is the reconciliation status** for a stale non-terminal run: the pipeline's own handlers catch `Exception` only, so a shutdown cancellation leaves the row `running` forever and would block both the reset guard and every future scheduled run.
- **The Schedule card is placed after the CV fact-store card** so the layout picker remains the page's first `<option ... selected>`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reconciled AFTER starting the scheduler, not before**
- **Found during:** Task 1 (the scheduler module)
- **Issue:** The research shape called `reconcile` before `scheduler.start()`. Reading the pinned 3.11.3 source, `BaseScheduler._lookup_job` consults only `_pending_jobs` while the state is `STOPPED`, so a job persisted by a previous process is invisible; `reconcile` would then `add_job` a duplicate, and `start()` would flush it into `_real_add_job` with `replace_existing=False`, raising `ConflictingIdError`. Under the boot contract that becomes `"unavailable"` — the scheduler would never start after the first restart, and Task 3's restart contract would be unachievable.
- **Fix:** `start_scheduler` starts the scheduler first, then reconciles, so `get_job`/`add_job`/`remove_job`/`reschedule_job` all operate on the real job store. The stale-run reconciliation runs before `start()` so no scheduled trigger can observe a stale row.
- **Files modified:** `app/jobs/scheduler.py`
- **Verification:** `tests/jobs/test_scheduler.py` (register/reschedule/remove/idempotent/past-due/next-run) and the API lane all pass.
- **Committed in:** `76c706f` (Task 1 commit)

**2. [Rule 3 - Blocking] The route injects the session factory instead of calling the module function**
- **Found during:** Task 1 (`save_schedule`)
- **Issue:** The plan text called `reconcile(get_scheduler(), get_session_factory())` directly, but the module-level factory points at the configured `/data` database, so in the API test lane the override would not reach `reconcile` and no job would be registered.
- **Fix:** The route declares `session_factory: async_sessionmaker = Depends(get_session_factory)` and passes it to `reconcile`.
- **Files modified:** `app/api/settings.py`
- **Verification:** `tests/api/test_schedule_settings.py` registers exactly one job through the overridden factory.
- **Committed in:** `76c706f` (Task 1 commit)

**3. [Rule 1 - Bug] The reset test's seeded corpus now seeds the operations row**
- **Found during:** Task 1 (full-suite run)
- **Issue:** `tests/api/test_settings_reset.py` asserts that every `RESET_KEPT_TABLES` entry holds a row after a reset; adding `operations_config` to that tuple made the assertion fail because the seed did not populate it.
- **Fix:** `_seed_corpus` now adds an `OperationsConfig` row (schedule enabled, `retention_json={}`), and the model is imported.
- **Files modified:** `tests/api/test_settings_reset.py`
- **Verification:** `tests/api/test_settings_reset.py` passes.
- **Committed in:** `76c706f` (Task 1 commit)

**4. [Rule 3 - Blocking] Moved the Schedule card after the CV fact-store card**
- **Found during:** Task 1 (full-suite run)
- **Issue:** `tests/api/test_settings_layout.py` matches the page's first `<option ... selected>`; the schedule card's timezone select, placed before the CV card, became that first option and broke the layout assertion.
- **Fix:** The `#schedule-card` section was placed after the CV fact-store card and before the danger zone — still among the settings cards, as the spec requires.
- **Files modified:** `app/web/templates/html/settings.html`
- **Verification:** `tests/api/test_settings_layout.py` and `tests/test_stylesheet_coverage.py` pass (no new CSS class was introduced, so no rebuild was needed).
- **Committed in:** `76c706f` (Task 1 commit)

---

**Total deviations:** 4 auto-fixed (1 bug, 3 blocking)
**Impact on plan:** All four were necessary for the plan's own success criteria; deviations 1 and 2 make the difference between a scheduler that works after a restart and one that reports "unavailable" forever. No scope creep — no health page, no pruning, no new CSS, no route beyond the schedule form.

### Environment deviation (not a code change)

- The plan's `<verify>` commands invoke `.venv/bin/python`, which resolves to the sandbox's Python 3.11.2 with no pytest. All verification ran through the documented working lane: `PYTHONPATH=/workspace/job-search:/workspace/job-search/.venv/lib/python3.11/site-packages /tmp/opencode/gsdvenv13/bin/python -m pytest` (Python 3.13.16, pytest 9.1.1). Every command in the plan's `<verify>` blocks was executed this way; only the interpreter path differs.

## Known Stubs

- `operations_config.retention_json` is created by migration 0008 and written as `{}` by both writers; it is deliberately neither read nor interpreted in this plan. Plan 08-05 is its reader and writer (D-168). It reaches no render path, so it cannot present an empty state to a user.

No other stubs: every new field, route and helper is wired to a real read, a real write or a real test.

## Issues Encountered

- **`BackgroundScheduler` and `batch_alter_table` appear in the plan's source assertions as forbidden substrings.** The first drafts of the scheduler docstring and the migration docstring named both literally (the scheduler's "never `BackgroundScheduler`" mechanic, the migration's "a later `batch_alter_table`"). Reworded to state the same mechanics without the literal tokens, so the plan's own guard assertions hold. Resolved within Task 1, no behaviour change.
- **`start_scheduler`'s error path leaves the module singleton set** when `scheduler.start()` fails part-way (e.g. the jobstore engine cannot open the configured database). The scheduler's state stays `STOPPED` and `stop_scheduler` early-returns, so nothing further fails; a later call retries and reports "unavailable" again. Acceptable for the boot contract; noted rather than "fixed" so a later reader does not add redundant teardown.

## User Setup Required

None - no external service configuration required. The scheduler reuses `DATABASE_URL_SYNC`, `SCHEDULE_TIMEZONE` and `SCHEDULE_MISFIRE_GRACE_SECONDS`, all already forwarded/configurable.

## Next Phase Readiness

- `next_run_at()` and `operations_config_repo.read_skip_notice()` are the two read seams plan 08-04's health page consumes; `next_run_at()` is total for the unavailable, disabled and paused states, so the page can render "no run scheduled" without inventing a time.
- `retention_json` and the operations row are ready for plan 08-05.
- Verifier note: the operator restart check is unrun (`.planning/WINDOWS.md` entry #16). `.develop`-time test lane deviation is recorded above.
- No blockers.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: new-scheduled-execution-path | `app/jobs/scheduler.py` | A new unattended execution path: a trigger now calls `run_pipeline` with no user in the loop. Mitigated as planned — the database in-flight guard (T-08-13), the non-fatal boot guard (T-08-16) and the allow-listed schedule inputs (T-08-10) — and no new network endpoint or credential was added. |

## Self-Check: PASSED

- Created files exist: `alembic/versions/0008_operations_config.py`, `app/db/repositories/operations_config_repo.py`, `app/jobs/__init__.py`, `app/jobs/scheduler.py`, `tests/jobs/__init__.py`, `tests/jobs/test_scheduler.py`, `tests/api/test_schedule_settings.py` — all FOUND.
- Commits exist: `76c706f`, `666078c`, `a0cf772` — all FOUND (`git log --oneline`).
- `commits` measured, not narrated: `git rev-list --count 5ed72a6..HEAD` = 3 before this SUMMARY commit; `plan_head_before` = `5ed72a6`.
- Full hermetic suite green: `1823 passed, 15 deselected, 2 xfailed`.
- No modification to `.planning/STATE.md` or `.planning/ROADMAP.md` (the orchestrator owns those writes).
