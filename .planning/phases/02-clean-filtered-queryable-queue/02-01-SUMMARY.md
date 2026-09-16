---
phase: 02-clean-filtered-queryable-queue
plan: "01"
subsystem: database
tags: [sqlite, alembic, sqlalchemy, pydantic-settings, migration, schema-guard]

# Dependency graph
requires:
  - phase: 01-walking-skeleton-foundations
    provides: migration 0001 (every Phase-2 table except four objects), the ORM base, the Settings class, the session-scoped migrated-DB test fixture, and the schema guard tests this plan deliberately extends
provides:
  - migration 0002 (filter_rules, queue_state, runs.reason/reason_counts_json/stage_log_json/criteria_snapshot_json, listing_exclusions.criteria_version, the listing_dupes pair indexes)
  - the ORM mirror of 0002 (FilterRule, QueueState, the new columns/constraints)
  - tests/db/test_orm_drift.py — the ORM-vs-migrated-schema drift guard
  - four new Settings knobs (dedup_fuzzy_threshold, dedup_posted_window_days, stale_after_days, queue_page_size)
affects: [02-02 rapidfuzz pin, 02-04 dedup, 02-05 run reason, 02-07 queue signals, 02-08 filter rules CRUD]

# Actuals (#2632) — same estimateTokens scale (chars/4 over the realized diff).
actuals:
  tokens: 7528
  tasks: 3
  commits: 4
  plan_head_before: 1140964793c6ea8257ba8a60c30ee217a61c0feb

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive migration + paired guard churn in one task"
    - "Explicitly named CHECK constraints (batch-recreation survival)"
    - "ORM-vs-migrated-schema drift guard"
    - "Settings-reader fields, never module constants"

key-files:
  created:
    - alembic/versions/0002_queue_filter_and_run_reason.py
    - tests/db/test_orm_drift.py
  modified:
    - app/db/models.py
    - app/config.py
    - tests/db/test_migration_contract.py
    - tests/db/test_no_pii_columns.py
    - tests/db/test_skeleton_boot.py
    - tests/test_config.py

key-decisions:
  - "θ ships as Settings.dedup_fuzzy_threshold = 88 with a tuning task (D-31): a starting value, never a frozen constant"
  - "Every new CHECK is explicitly named (ck_filter_rules_kind, ck_runs_reason) — the batch recreation preserved ck_runs_trigger/ck_runs_status, verified by assertion"
  - "runs.reason stays NULLABLE so NULL means 'this run produced a non-empty queue'"
  - "queue_state.last_queue_view_at is NULLABLE so NULL means 'never viewed' and every listing starts new"
  - "objects migration 0002 adds are listed explicitly in the drift guard and the PII allow-list so neither comparison can go vacuous"

patterns-established:
  - "Migration-and-guards-together: a schema change and the guards that encode the old schema land in one task"
  - "Drift guard in both directions: ORM table set == migrated application table set, plus per-table column-name equality"
  - "Non-vacuity guards: each new comparison asserts a positive floor (scanned > 0, table counts, named 0002 tables)"

requirements-completed: [CRIT-01, FILT-04, RUN-03, QUEUE-07]

coverage:
  - id: D1
    description: "Migration 0002 is additive and `alembic upgrade head` on a fresh database records exactly one revision, 0002, with a single Alembic head"
    requirement: CRIT-01
    verification:
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_alembic_at_latest_revision"
        status: pass
      - kind: other
        ref: "DATABASE_URL_SYNC=... python -m alembic upgrade head; python -m alembic heads -> '0002 (head)'"
        status: pass
    human_judgment: false
  - id: D2
    description: "The migrated DB contains filter_rules, queue_state, the four new runs columns, listing_exclusions.criteria_version and the listing_dupes pair indexes — proven by PRAGMA/sqlite_master, with the named CHECKs enforced"
    requirement: RUN-03
    verification:
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_filter_rules_table_and_kind_check"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_queue_state_watermark_is_nullable"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_runs_reason_columns_and_enum_check"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_criteria_version_and_dupes_unique_index"
        status: pass
      - kind: integration
        ref: "tests/db/test_skeleton_boot.py#test_migration_creates_every_table_at_latest_revision"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every new JSON column is deliberately allow-listed and no new column name is PII-shaped"
    requirement: QUEUE-07
    verification:
      - kind: integration
        ref: "tests/db/test_no_pii_columns.py#test_json_columns_are_allow_listed"
        status: pass
      - kind: integration
        ref: "tests/db/test_no_pii_columns.py#test_no_email_or_phone_columns"
        status: pass
    human_judgment: false
  - id: D4
    description: "dedup_fuzzy_threshold, dedup_posted_window_days, stale_after_days and queue_page_size are readable from Settings, environment-overridable, and covered by the surface and absence controls"
    requirement: FILT-04
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_settings_exposes_every_documented_knob"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_the_new_queue_knobs_are_environment_tunable"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_no_distinctive_threshold_literal_remains_in_probe_or_pipeline"
        status: pass
    human_judgment: false
  - id: D5
    description: "The ORM mirror of migration 0002 is machine-compared to the migrated schema, and the guard is demonstrated to fail when the mirror drifts"
    verification:
      - kind: integration
        ref: "tests/db/test_orm_drift.py#test_orm_metadata_matches_migrated_schema"
        status: pass
    human_judgment: false

# Metrics
duration: 8min
completed: 2026-09-16
status: complete
---

# Phase 2 Plan 01: Schema spine — migration 0002, the guard churn, and the settings envelope

**Additive migration 0002 (filter_rules, the last-visit watermark, the run-reason/criteria-snapshot columns and the listing_dupes pair index), its ORM mirror, a new ORM-drift guard, four Settings knobs, and five deliberately-updated Phase-1 schema guards.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-09-16T08:59:06Z
- **Completed:** 2026-09-16T09:07:51Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Migration 0002 lands additively and, on a fresh database, leaves exactly one revision (`0002`) and exactly one Alembic head. The named `ck_runs_reason` was added through SQLite's batch recreation and the pre-existing named `ck_runs_trigger`/`ck_runs_status` CHECKs survived it — verified by introspection *and* by an executable rejection test.
- The migration-contract checklist grew from 9 items to 13: `filter_rules` + `ck_filter_rules_kind`, the nullable `queue_state.last_queue_view_at`, the four new `runs` columns + `ck_runs_reason`, and `listing_exclusions.criteria_version` + the `uq_listing_dupes_pair` unique index — all read from `PRAGMA`/`sqlite_master`, never ORM metadata.
- The PII allow-list was extended deliberately (`filter_rules.params_json` and the three new `runs` JSON columns) and the one-row `queue_state` table was left out, since it has no JSON column.
- `tests/db/test_orm_drift.py` closes the gap the Phase-1 contract leaves open: `Base.metadata` is compared to the migrated schema in both directions (table-set equality excluding FTS/alembic internals, plus per-table column-name equality), with non-vacuity guards naming the 0002 objects. The guard was demonstrated to fail by temporarily renaming `QueueState.__tablename__`, then restored.
- θ, the dedup window, the staleness boundary and the page size are all `Settings` fields with an environment-override proof, and no threshold literal lives under `app/pipeline`/`app/probe`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 0002 and its paired schema-guard edits** - `26ba2a2` (feat)
2. **Task 2: Add the four new Settings knobs and extend the config guard** - `1d635a5` (feat)
3. **Task 3: ORM-vs-migrated-schema drift guard** - `7a49fae` (test)
4. **Deviation fix: fifth schema guard** - `d9bf886` (fix)

**Plan metadata:** _committed with STATE/ROADMAP/REQUIREMENTS after this file_

## Files Created/Modified

- `alembic/versions/0002_queue_filter_and_run_reason.py` — the only schema change in Phase 2: two tables, five columns, one named CHECK via the batch path, two indexes; `downgrade()` is the drop-in-reverse. Deliberately contains no FTS/trigger DDL.
- `app/db/models.py` — mirrors 0002: new `FilterRule` and `QueueState` classes, `ListingDupe` pair indexes, `ListingExclusion.criteria_version`, and the four new `Run` columns with `ck_runs_reason`.
- `tests/db/test_migration_contract.py` — renamed `test_alembic_at_latest_revision`; asserts `0002`; items 10–13 added; module docstring reworded from the 9-item 0001 checklist.
- `tests/db/test_no_pii_columns.py` — `EXPECTED_JSON_COLUMNS` extended with `filter_rules` and the five-column `runs` set.
- `tests/db/test_orm_drift.py` — new two-direction drift guard.
- `tests/db/test_skeleton_boot.py` — the fifth Phase-1 schema guard: `EXPECTED_TABLES` gains the two 0002 tables and the revision assertion becomes `0002`.
- `app/config.py` — the four new §"Phase 2 queue + dedup envelope" knobs.
- `tests/test_config.py` — required/LIMIT field lists extended, the θ default pinned, and an env-override proof for the new knobs.

## Decisions Made

- **θ is a setting with a tuning task, not a constant.** `dedup_fuzzy_threshold` defaults to 88 and is pinned by `test_documented_defaults`; STATE.md's Phase-2 blocker (untunable without a real corpus) is honoured by shipping a starting value, not a frozen one.
- **The `runs.reason` CHECK earned a table recreation.** The plan's recommendation was followed: the enum is the product contract for "why is the queue empty", so `ck_runs_reason` is a real named CHECK rather than a domain-module-only assertion. The batch recreation was verified to preserve the two pre-existing named CHECKs.
- **The drift guard compares names, not types.** SQLite type affinity and Alembic batch spelling legitimately differ; comparing types would produce false positives without adding real protection.
- **`queue_state` stays out of the PII JSON allow-list.** It has no JSON column, and the exact-equality comparison drops empty entries on both sides — adding it would weaken the list's meaning.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] A fifth Phase-1 schema guard also pinned revision `0001`**
- **Found during:** Plan-level verification (after Task 3), running `.venv/bin/python -m pytest -q tests/db`.
- **Issue:** The plan named four guard files that would fail when 0002 lands. `tests/db/test_skeleton_boot.py::test_migration_creates_every_table_at_revision_0001` is a fifth: it asserted `alembic_version == [("0001",)]` and a 17-table `EXPECTED_TABLES` inventory that did not include `filter_rules`/`queue_state`. The plan's own verification requires `tests/db` to pass in full and the full suite green, so leaving it red was not an option.
- **Fix:** Applied the same deliberate-guard-churn treatment as the four named guards: added the two 0002 tables to `EXPECTED_TABLES`, renamed the test to `test_migration_creates_every_table_at_latest_revision`, and changed the assertion to `[("0002",)]`. No assertion was relaxed — one table-inventory assertion was extended and one revision literal updated.
- **Files modified:** `tests/db/test_skeleton_boot.py`
- **Verification:** `.venv/bin/python -m pytest -q tests/db` → `36 passed`; full suite → `321 passed, 2 deselected in 21.62s`.
- **Committed in:** `d9bf886` (separate fix commit; Task 1 was already committed when this surfaced)

### Environment substitutions (not plan defects)

- **`.venv-host` is unusable in this sandbox**, so every `<verify>` command was run through the equivalent `.venv/bin/python -m pytest` — the same Python 3.14.7 and the same package versions. Reason: the `.venv-host` console scripts carry a stale absolute shebang (`/mnt/data/docker/apps/opencode/workspace/job-search/...`) and its compiled wheels are gnu-tagged while the sandbox interpreter is musl. Recorded in `deferred-items.md`.
- **`alembic upgrade head` was run with an explicit `DATABASE_URL_SYNC`** pointing at a workspace file, because the default `sqlite:////data/jobsearch.db` is not writable here. The test harness already sets this override itself (`tests/conftest.py:47-57`). Recorded in `deferred-items.md`.

---

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** The auto-fix is the same deliberate, paired guard churn the plan describes — it adds coverage rather than relaxing it, and it was required to satisfy the plan's own "no pre-existing test left red" criterion. The environment substitutions are sandbox-only and leave the committed artifacts unchanged.

## Issues Encountered

- None beyond the fifth guard above. `ruff` was not run (the repo has no pre-commit hook configured at commit time; no hook blocked any commit).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The schema spine for Phase 2 is in place: `filter_rules` (typed rows, ordered, per-search), `queue_state` (nullable watermark), `runs.reason`/`reason_counts_json`/`stage_log_json`/`criteria_snapshot_json`, `listing_exclusions.criteria_version`, and the `listing_dupes` pair indexes are all persisted, mirrored and guarded.
- Ready for **02-02** (the `rapidfuzz` dependency pin — still absent from `pyproject.toml`; its package-legitimacy verdict is SUS, so the install is gated by `checkpoint:human-verify`) and then 02-04/02-05/02-07/02-08, which consume θ, `stale_after_days`, `reason` and `queue_page_size`.
- No reader consumes the new knobs yet — that is by design (θ has no reader until 02-04; `filter_rules` has no writer until 02-08).

---
*Phase: 02-clean-filtered-queryable-queue*
*Completed: 2026-09-16*
