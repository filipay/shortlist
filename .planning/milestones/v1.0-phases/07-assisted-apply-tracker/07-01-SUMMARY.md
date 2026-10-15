---
phase: 07-assisted-apply-tracker
plan: 01
subsystem: [api, database, ui]
tags: [fastapi, sqlalchemy, alembic, sqlite, jinja2, htmx, append-only, applications]

# Dependency graph
requires:
  - phase: 06-tailoring-verification
    provides: "cv_artifact_repo.read_for_download(ok_only=True) — the SQL-level ok-only selection the applied gate consumes (D-118)"
  - phase: 01-foundation
    provides: "the applications / application_events tables and ck_applications_status (migration 0001); the listing_events append-only trigger pattern"
provides:
  - "migration 0006: screening_drafts + apply_config tables and the two application_events append-only triggers"
  - "app/db/repositories/application_repo.py: record/transition/update writes the row and exactly one event in one SAVEPOINT; the ok-only applied gate; read_tracker/read_history"
  - "the /applications tracker page + list fragment, record route, status-transition route, history partial, and notes/next-action edit"
affects: [07-02-apply-package, 07-03-screening-drafts, 07-04-tracker-filters, 07-05-drafted-answers]

# Actuals (#2632) — pairs with the plan's `estimate`.
actuals:
  tokens: 21378
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Current state on the row, history in a trigger-enforced append-only event table; the row update and the single event append share one begin_nested() SAVEPOINT"
    - "The ok-only predicate is an attach-time access control applied IN SQL; the historical link is read back unfiltered"
    - "Route declaration order is load-bearing: static POST /applications/record precedes every dynamic POST /applications/{application_id}"

key-files:
  created:
    - alembic/versions/0006_screening_drafts.py
    - app/db/repositories/application_repo.py
    - app/api/applications.py
    - app/web/templates/html/applications.html
    - app/web/templates/html/applications_list.html
    - app/web/templates/html/_application_row.html
    - app/web/templates/html/_application_history.html
    - tests/db/test_application_repo.py
    - tests/db/test_application_events.py
    - tests/api/test_applications_tracker.py
  modified:
    - app/db/models.py
    - app/main.py
    - app/api/settings.py
    - app/web/templates/html/base.html
    - static/vendor/app.css
    - tests/db/test_migration_contract.py
    - tests/db/test_no_pii_columns.py
    - tests/db/test_skeleton_boot.py
    - tests/test_auth_seam.py
    - tests/api/test_settings_reset.py

key-decisions:
  - "The row update and the single application_events append share one session.begin_nested() SAVEPOINT, so a crash between the two writes is impossible (D-131)"
  - "The applied gate resolves the artefact through cv_artifact_repo.read_for_download(ok_only=True); a refusal returns None and writes NOTHING (D-118/D-129)"
  - "read_tracker never re-filters the linked artefact on compile_status, so the exact CV that was sent survives a later status change (APPLY-04)"
  - "POST /applications/record is declared before every dynamic POST /applications/{application_id} route, because FastAPI matches in declaration order"
  - "migration 0006 adds the two application_events triggers via raw op.execute, and deliberately adds no CHECK to to_status/from_status (batch-recreation hazard); the vocabulary is validated in the repository"

requirements-completed: [APPLY-03, APPLY-04, APPLY-05, APPLY-06]

coverage:
  - id: D1
    description: "Migration 0006: screening_drafts + apply_config tables and the two application_events BEFORE UPDATE/DELETE triggers that RAISE(ABORT, 'application_events is append-only')"
    requirement: APPLY-05
    verification:
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_screening_drafts_apply_config_and_application_events_append_only"
        status: pass
      - kind: integration
        ref: "tests/db/test_orm_drift.py#test_orm_metadata_matches_migrated_schema"
        status: pass
    human_judgment: false
  - id: D2
    description: "Record an application over HTTP; exactly one append-only 'created' event is written with it, and the tracker renders the row"
    requirement: APPLY-03
    verification:
      - kind: unit
        ref: "tests/db/test_application_repo.py#test_record_writes_one_row_and_one_created_event"
        status: pass
      - kind: integration
        ref: "tests/api/test_applications_tracker.py#test_record_via_http_renders_the_row_and_its_created_event"
        status: pass
    human_judgment: false
  - id: D3
    description: "The applied gate: a transition to applied requires an ok artefact, stores the link and stamps applied_at; a blocked/absent artefact refuses and writes nothing; the tracker reads the stored link unfiltered"
    requirement: APPLY-04
    verification:
      - kind: unit
        ref: "tests/db/test_application_repo.py#test_applied_requires_ok_artifact"
        status: pass
      - kind: unit
        ref: "tests/db/test_application_repo.py#test_tracker_read_keeps_the_stored_link_when_artifact_status_changes"
        status: pass
      - kind: integration
        ref: "tests/api/test_applications_tracker.py#test_applied_requires_ok_artifact"
        status: pass
    human_judgment: false
  - id: D4
    description: "The inline history timeline: every event renders `from -> to` + timestamp + note, a NULL from_status renders 'created', and History (n) matches the entries"
    requirement: APPLY-05
    verification:
      - kind: integration
        ref: "tests/api/test_applications_tracker.py#test_history_partial_lists_all_events_in_order_and_count_matches"
        status: pass
      - kind: integration
        ref: "tests/api/test_applications_tracker.py#test_history_partial_renders_no_history_recorded_for_an_eventless_row"
        status: pass
    human_judgment: false
  - id: D5
    description: "Notes and next-action date save in place without appending an event; an absent next-action clears the date"
    requirement: APPLY-06
    verification:
      - kind: integration
        ref: "tests/api/test_applications_tracker.py#test_notes_and_next_action_save_without_appending_an_event"
        status: pass
      - kind: integration
        ref: "tests/api/test_applications_tracker.py#test_clearing_the_next_action_field_clears_the_date"
        status: pass
    human_judgment: false
  - id: D6
    description: "The tracker's visual contract: the Stage badge is the scanning anchor, the eight .badge-stage-* variants resolve to existing tokens, and the row exposes the Move-to control and inline history"
    verification: []
    human_judgment: true
    rationale: "Visual scanning quality (does the stage column actually anchor the eye) and the no-JS degrade of the transition/notes forms are judgement calls no automated assertion proves; the class-coverage guard only proves a rule exists, not that it reads well."

duration: ~55 min
completed: 2026-09-30
status: complete
---

# Phase 7 Plan 1: Tracer — record an application and see it in the tracker Summary

**An application records through HTTP with exactly one trigger-enforced append-only event, links only to an `ok` CV artefact, and renders in the `/applications` tracker with an inline chronological history and editable notes/next-action — proven on migration 0006.**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-09-30T15:31Z (phase execution)
- **Completed:** 2026-09-30
- **Tasks:** 3
- **Files modified:** 20 (10 created, 10 modified)

## Accomplishments
- Migration 0006 creates `screening_drafts` and `apply_config`, and adds the two `application_events` BEFORE UPDATE/DELETE triggers that make the history table append-only at the schema level — mirroring the shipped `listing_events` contract.
- `application_repo` is the integrity spine: every status change updates `applications.status` and appends exactly one `application_events` row inside one `begin_nested()` SAVEPOINT, so the two writes commit or roll back together.
- The `applied` gate resolves its artefact through `cv_artifact_repo.read_for_download(ok_only=True)` (the `compile_status = 'ok'` predicate applied IN SQL); a blocked/missing artefact is a 4xx `data-error` refusal that writes nothing, while the historical link is read back unfiltered.
- The `/applications` tracker renders one row per application (Stage badge, Applied, Next action, Latest note), records over HTTP, serves an inline `<details>` history partial, and edits notes/next-action as ordinary mutable columns without appending an event.

## Task Commits

Each task was committed atomically:

1. **Task 1: Record an application and render it in the tracker — migration 0006 through the row swap** - `22193ed` (feat)
2. **Task 2: The applied gate and the status-transition refusal** - `002ec33` (feat)
3. **Task 3: The inline history timeline and notes/next-action editing** - `f411290` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `alembic/versions/0006_screening_drafts.py` - the two new tables + the two `application_events` append-only triggers
- `app/db/models.py` - `ScreeningDraft` and `ApplyConfig` ORM mirrors (migration-created, never `create_all`)
- `app/db/repositories/application_repo.py` - the applications/application_events write+read path and the ok-only applied gate
- `app/api/applications.py` - the `/applications` tracker, record/status/notes routes, and the history fragment
- `app/main.py` - registers the applications router beside `tailoring_routes`
- `app/api/settings.py` - `screening_drafts` joins `RESET_DELETE_ORDER` (before `listings`); `apply_config` joins `RESET_KEPT_TABLES`
- `app/web/templates/html/applications.html` - the tracker page shell
- `app/web/templates/html/applications_list.html` - the shared table fragment (page + swap)
- `app/web/templates/html/_application_row.html` - one row: Stage badge, dates, note, Move-to control, notes form, history `<details>`
- `app/web/templates/html/_application_history.html` - the inline timeline body (re-emits the `<summary>` on swap)
- `app/web/templates/html/base.html` - the `Applications` nav entry
- `static/vendor/app.css` - the eight `.badge-stage-*` variants and `.next-overdue`, each copying an existing declaration block
- `tests/db/test_application_repo.py`, `tests/db/test_application_events.py`, `tests/api/test_applications_tracker.py` - the repository, append-only and HTTP tracker lanes
- `tests/db/test_migration_contract.py` - head bumped to `0006` + item 17 for the new tables/triggers
- `tests/db/test_no_pii_columns.py`, `tests/db/test_skeleton_boot.py`, `tests/test_auth_seam.py`, `tests/api/test_settings_reset.py` - the guards a new table/route trips

## Decisions Made
- The row update and its single `application_events` append are one `begin_nested()` block, so an impossible-to-recover half-state cannot exist (D-131).
- The `applied` gate lives in the repository, not a DB trigger (D-118): `read_for_download(ok_only=True)` makes a blocked artefact unreachable even by id, and a refusal writes nothing.
- The tracker read deliberately does not re-filter the linked artefact, so the "exact CV sent" link is an immutable historical fact (APPLY-04).
- `screening_drafts` and `apply_config` are built now (the phase's one migration) but their writers arrive in later plans; they are declared in the reset guards in this plan so no guard fails later.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added a dedicated `_application_row.html` partial**
- **Found during:** Task 1 (tracker templates)
- **Issue:** The plan's `files_modified` lists `applications_list.html` but Task 3 requires the status/notes routes to re-render "the whole row" into `#application-row-{id}` with an `outerHTML` swap. A single `<tr>` cannot be returned from the shared table fragment.
- **Fix:** Factored the row markup into `_application_row.html`, included by `applications_list.html` and returned standalone by the status/notes routes — the same split the queue uses (`queue_list.html` includes `_listing_row.html`).
- **Files modified:** `app/web/templates/html/_application_row.html` (created), `applications_list.html`
- **Verification:** `tests/api/test_applications_tracker.py` (row swap + history controls) pass
- **Committed in:** `22193ed` (Task 1)

**2. [Rule 1 - Bug] Reused existing CSS classes instead of four unscoped new ones**
- **Found during:** Task 3 (full-suite run)
- **Issue:** `test_stylesheet_coverage.py` requires every literal template class to have a rule in `app.css`; `stage-note`, `stage-empty`, `application-transition`, `application-notes` had none, and the UI-SPEC did not sanction them.
- **Fix:** The history note renders as plain text, the empty timeline uses the existing `.detail-empty`, and both row forms use the existing `.listing-action` wrapper.
- **Files modified:** `app/web/templates/html/_application_history.html`, `app/web/templates/html/_application_row.html`
- **Verification:** `tests/test_stylesheet_coverage.py` passes
- **Committed in:** `f411290` (Task 3)

**3. [Rule 1 - Bug] Seeded `apply_config` in the reset-corpus test**
- **Found during:** Task 3 (full-suite run)
- **Issue:** `test_a_correct_token_empties_the_corpus_and_keeps_configuration` asserts every `RESET_KEPT_TABLES` member holds a row after a reset; `apply_config` was newly added to that list but the seed left it empty.
- **Fix:** `_seed_corpus` now seeds one `apply_config` row, so the "configuration is kept" assertion is real.
- **Files modified:** `tests/api/test_settings_reset.py`
- **Verification:** `tests/api/test_settings_reset.py` passes
- **Committed in:** `f411290` (Task 3)

---

**Total deviations:** 3 auto-fixed (1 blocking, 2 bug)
**Impact on plan:** All three keep the plan's behaviour intact; the row partial is the structural precondition for the documented `outerHTML` row swap, and the two bug fixes repair guards the plan's own new tables/classes trip.

## Issues Encountered
None beyond the deviations above — all three were caught by the full suite, fixed, and re-verified before the final run (1556 passed).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Wave 1's integrity spine is proven: migration head is `0006`, the append-only triggers abort UPDATE/DELETE, and the applied gate refuses a non-`ok` artefact.
- Ready for 07-02 (the apply package page), 07-03 (grounded screening drafting, which writes `screening_drafts`), and 07-04 (tracker filters, which the `/applications/list` fragment is structured to grow into).
- `screening_drafts` and `apply_config` currently have no writer; their routes land in 07-03/07-05.

## Self-Check: PASSED

- All 10 created files exist on disk (`[ -f ]` verified).
- All three task commits exist (`22193ed`, `002ec33`, `f411290`).
- `pytest -q` (full suite): **1556 passed, 14 deselected, 2 xfailed**.
- `ruff check` on both new modules, the migration, and the three test files: clean.

---
*Phase: 07-assisted-apply-tracker*
*Completed: 2026-09-30*

