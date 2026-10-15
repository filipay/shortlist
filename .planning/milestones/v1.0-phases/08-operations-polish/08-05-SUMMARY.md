---
phase: 08-operations-polish
plan: 05
subsystem: database
tags: [retention, prune, sqlite, triggers, sqlalchemy, fastapi, jinja2, htmx-free, audit]

requires:
  - phase: 08-operations-polish
    provides: the `operations_config` singleton (08-03) whose retention payload this plan owns, the scheduler module, and the run/operations repositories
  - phase: 08-operations-polish
    provides: the health page's run-derived badge and Adzuna verdict (08-04), the readers the runs floor and the ledger guard exist to protect
  - phase: 06-tailoring-verification
    provides: `cv_artifact_repo.latest_for_listing(ok_only=True)` — the read the newest-artifact guard is the exact SQL complement of
provides:
  - a manual, per-category, per-threshold prune over four categories, behind a dry-run preview, a separate confirm, an audit line and four hard guards
  - `app/db/repositories/retention_repo.py` — the category allow-list, the run floor, the shared selection for preview and delete, and the per-category deletes
  - the D-164 amendment (the audit logs are never pruned except by the deletion of their parent listing) recorded in code, not implied
  - `POST /settings/prune/preview` and `POST /settings/prune` with the post-commit, artifacts-dir-scoped unlink
  - `read_retention` / `write_retention` completing the `operations_config` payload pair
affects: [08-operations-polish, verify-phase-08, runbook operators, any future relaxation of the artifact guard on the listings category]

actuals:
  tokens: 20937
  tasks: 3
  commits: 3
  plan_head_before: dbf06ec89de41bf42fb5858e9666781434b34cf2

tech-stack:
  added: []
  patterns:
    - "Guards as WHERE clauses: every D-165 invariant is a condition in the selection, so it cannot be forgotten at the confirm step"
    - "One predicate, two statements: preview and delete run the same select, so the count before destruction cannot disagree with the number removed"
    - "Commit then unlink: rows commit first, files are unlinked strictly after, contained to the artifacts directory"
    - "Create-if-absent writers that satisfy the other NOT NULL column: each upsert's `set_` carries only its own payload"

key-files:
  created:
    - app/db/repositories/retention_repo.py
    - tests/db/test_retention_repo.py
    - tests/api/test_settings_prune.py
  modified:
    - app/api/settings.py
    - app/db/repositories/operations_config_repo.py
    - app/web/templates/html/settings.html
    - tests/test_auth_seam.py

key-decisions:
  - "`delete` (the repository's public name, per the plan) shadows SQLAlchemy's `delete` at module scope, so the construct is imported as `sa_delete` — the public name stays the plan's."
  - "`retention_repo` re-exports `APPEND_ONLY_TRIGGER` and `TRIGGER_CARVE_OUT_CATEGORIES`, and `app/api/settings.py`'s `_APPEND_ONLY_TRIGGER` now points at that one name — the repository never re-implements the drop/re-arm pair (which would have been an `api` <-> `repositories` import cycle)."
  - "The listings selection's artifact guard makes `_paths_for_listings` empty by construction today; it is kept (not deleted) so relaxing that guard still hands the child files to the unlink instead of orphaning them."
  - "`read_retention` parses per entry rather than whole-document: a half-written threshold is simply absent and each category has a form default, so no state is lost (unlike the schedule, where a half-written document is not a schedule)."
  - "Both test modules seed `NOW = datetime.now(UTC)` rather than a fixed calendar date, so a row meant to be 'recent' stays recent against the running clock; a fixed 2026-10-01 landed inside a 30-day window only by coincidence of the run date."
  - "The prune card's age field defaults to 30 days and the stored thresholds are rendered as a read-back line, rather than pretending a no-JavaScript select can reflect the stored value of whichever category the user later picks."

patterns-established:
  - "A destructive two-step surface: a POST preview that deletes nothing and persists only the threshold, then a POST confirm that re-derives the count rather than trusting the form"
  - "A carve-out that is transaction-local: the append-only trigger is suspended and re-armed inside the same transaction, and the database's own catalog is read afterwards to prove the re-arm"

requirements-completed: [RUN-07]

coverage:
  - id: D1
    description: "A manual, per-category, per-threshold prune control with a dry-run preview (count + on-disk size), a separate confirm, an empty-preview state and an audit line"
    requirement: RUN-07
    verification:
      - kind: unit
        ref: "tests/api/test_settings_prune.py#test_the_preview_round_trips_and_offers_the_confirm"
        status: pass
      - kind: unit
        ref: "tests/api/test_settings_prune.py#test_a_zero_count_preview_renders_the_empty_copy_and_no_confirm"
        status: pass
      - kind: unit
        ref: "tests/api/test_settings_prune.py#test_a_bad_category_returns_400_and_deletes_nothing"
        status: pass
      - kind: unit
        ref: "tests/api/test_settings_prune.py#test_a_non_positive_or_non_numeric_age_returns_400_and_deletes_nothing"
        status: pass
    human_judgment: false
  - id: D2
    description: "The artifact category deletes rows and their `.tex`/`.pdf` files, with the application-link and newest-successful-artifact guards holding"
    requirement: RUN-07
    verification:
      - kind: unit
        ref: "tests/db/test_retention_repo.py#test_an_old_unreferenced_non_newest_artifact_is_previewed_and_deleted"
        status: pass
      - kind: unit
        ref: "tests/db/test_retention_repo.py#test_the_newest_successful_artifact_is_never_selected"
        status: pass
      - kind: unit
        ref: "tests/db/test_retention_repo.py#test_an_artifact_referenced_by_an_application_is_never_selected"
        status: pass
      - kind: unit
        ref: "tests/api/test_settings_prune.py#test_the_confirm_deletes_the_rows_and_the_files_and_renders_the_audit"
        status: pass
      - kind: unit
        ref: "tests/api/test_settings_prune.py#test_a_path_outside_the_artifacts_directory_is_skipped_and_reported"
        status: pass
    human_judgment: false
  - id: D3
    description: "Run history and the source request log prune at a chosen age while the retained-run floor, the LLM call ledger and the verdict's log inputs survive, with no foreign-key failure"
    requirement: RUN-07
    verification:
      - kind: unit
        ref: "tests/db/test_retention_repo.py#test_the_floor_protects_inside_runs_while_an_outer_run_is_selected"
        status: pass
      - kind: unit
        ref: "tests/db/test_retention_repo.py#test_the_ledger_rows_survive_with_a_nulled_run_reference"
        status: pass
      - kind: unit
        ref: "tests/db/test_retention_repo.py#test_a_source_log_row_of_a_retained_run_survives_and_an_orphan_row_is_selected"
        status: pass
      - kind: unit
        ref: "tests/db/test_retention_repo.py#test_the_runs_ordering_deletes_children_before_parents"
        status: pass
    human_judgment: false
  - id: D4
    description: "The stale-listing hard delete: foreign-key safe, snapshotted first, with the append-only delete trigger re-armed after the commit"
    requirement: RUN-07
    verification:
      - kind: unit
        ref: "tests/db/test_retention_repo.py#test_the_listing_prune_leaves_the_append_only_trigger_armed_with_its_negative_control"
        status: pass
      - kind: unit
        ref: "tests/db/test_retention_repo.py#test_the_listing_selection_excludes_applications_artifacts_and_both_dupe_sides"
        status: pass
      - kind: unit
        ref: "tests/api/test_settings_prune.py#test_a_snapshot_destination_collision_refuses_and_deletes_nothing"
        status: pass
    human_judgment: false
  - id: D5
    description: "The operator walk of the prune control — one pass per category in a browser, reading the preview panel and the audit banner"
    verification: []
    human_judgment: true
    rationale: "Docker and a browser are absent from the agent sandbox; the automated suites prove the data behaviour and the rendered markup, but only a person can confirm the surface reads honestly end to end. Recorded as an unrun-verify item in .planning/WINDOWS.md."

duration: 37min
completed: 2026-10-14
status: complete
---

# Phase 08 Plan 05: Payments on the retention debts, with nothing destroyed silently

**A manual four-category prune behind a dry-run preview and a separate confirm, with the run floor, the LLM call ledger, application-linked CVs and each listing's newest verified CV guarded as conditions in the queries themselves — and the stale-listing carve-out suspending and re-arming the append-only trigger inside one transaction.**

## Performance

- **Duration:** 37 min
- **Started:** 2026-10-14T19:54:25Z
- **Completed:** 2026-10-14T20:31:10Z
- **Tasks:** 3
- **Files modified:** 7 (2,156 insertions)

## Accomplishments

- `app/db/repositories/retention_repo.py` owns every prune statement: the `PRUNE_CATEGORIES` allow-list, the `RUN_FLOOR` reuse of `RUN_HISTORY_LIMIT`, `_validate`'s positive-integer threshold refusal, a frozen category-to-statement mapping, and a `preview`/`delete` pair that run one predicate per category. It contains no f-string, so no request-derived text can reach a statement (T-08-24).
- All four D-163 categories are implemented. The artifacts category mirrors `latest_for_listing(ok_only=True)`'s `ORDER BY created_at DESC, id DESC` as a `NOT EXISTS` complement, so the prune can never delete the CV the listing page is showing. The runs category deletes children before parents and **nulls** the `llm_calls.run_id` rather than deleting ledger rows, so the spend ceilings keep their inputs. The source request log keeps every row belonging to a retained run because the survival verdict reads it. The listings category hard-deletes with the D-164 carve-out.
- The two routes are separate POSTs (D-166): the preview deletes nothing and only persists the chosen threshold (D-168); the confirm **re-derives** the count and refuses with the empty copy when it is zero. Files are unlinked strictly after the commit, each path resolved and asserted inside `artifacts_dir` (T-08-23, T-08-30), with skips and misses reported in the audit line (T-08-27).
- The stale-listing delete takes a snapshot first (the category's only recovery), then inside one transaction suspends the append-only trigger via the reset's shipped pair, deletes the per-listing children in foreign-key order, the events, then the listing, and re-arms the trigger before the commit (T-08-28). An automated assertion reads `sqlite_master` after the commit — the assertion the reset itself lacks — with a negative control proving it can fail.
- The four guards are parametrized across all four categories as a failure class, and the full hermetic suite is green: **1903 passed, 15 deselected, 2 xfailed**.

## Task Commits

1. **Task 1: Preview and then delete old tailored CV artifacts — rows and files** — `9d4b74b` (feat)
2. **Task 2: Prune run history and the source request log without breaking a foreign key or starving the verdict** — `9b7ef8a` (feat)
3. **Task 3: The stale-listing hard delete, its snapshot, and the re-armed trigger** — `7b93a7e` (feat)

**Plan metadata:** see the orchestrator's metadata commit (this executor does not write STATE.md/ROADMAP.md).

## Files Created/Modified

- `app/db/repositories/retention_repo.py` (new, 515 lines) — `PRUNE_CATEGORIES`, `RUN_FLOOR`, `APPEND_ONLY_TRIGGER`, `TRIGGER_CARVE_OUT_CATEGORIES`, `PrunePreview`, `_validate`, the frozen `_CATEGORIES` mapping, and the four selections/deletes.
- `app/db/repositories/operations_config_repo.py` — `read_retention`/`write_retention` (per-category age thresholds), a shared `_schedule_payload` builder, and the create-if-absent `schedule_json` supply in `write_retention`.
- `app/api/settings.py` — `PRUNE_PREVIEW_PATH`/`PRUNE_PATH`, `PRUNE_CATEGORY_LABELS`, the three refusal strings, `_prune_root`, `_unlink_artifacts`, `_prune_preview_or_error`, `preview_prune`, `confirm_prune`, the `retention`/`prune_preview`/`prune_categories`/`prune_run_floor` context keys, the extended CSRF caveat, and `_APPEND_ONLY_TRIGGER` re-pointed at the repository's single name.
- `app/web/templates/html/settings.html` — the `Prune history` block inside the danger zone: category select, `Older than` field, the stored-threshold read-back, the `.capability-warnings` preview panel with its counts/size and protected line, the empty state, and the separate confirm with the "This cannot be undone." note. No new CSS, no JavaScript.
- `tests/db/test_retention_repo.py` (new, 817 lines) — the per-category guard tests, the artifact size/containment tests, the runs floor/ledger/events/ordering tests, the listings carve-out tests, the trigger re-arm assertion with its negative control, and the parametrized four-category guard suite.
- `tests/api/test_settings_prune.py` (new, 360 lines) — the form round-trip, the refusals, the preview-equals-delete behaviour, the post-commit unlink and its containment skip, the audit line, the threshold persistence and NOT NULL create path, the category-option coverage, and the snapshot-collision refusal.
- `tests/test_auth_seam.py` — the two prune paths added to `EXPECTED_SEAM_ROUTES`.

## Decisions Made

- `delete` is the repository's public name (as the plan specifies), which shadows SQLAlchemy's `delete` at module scope; the construct is imported as `sa_delete`. Without the alias, `_delete_artifacts` called the repository's own `delete` and raised `TypeError` — caught by the first test run.
- The append-only trigger name and the carve-out category set live in `retention_repo` and are referenced by `app/api/settings.py`; the suspend/restore functions stay in `settings.py` and the route orchestrates. Importing the private helpers into the repository would have created an `api` ↔ `repositories` cycle, and re-implementing the pair was explicitly forbidden.
- The listings selection excludes any listing that owns an artifact row, so `_paths_for_listings` is empty by construction today. It is kept rather than replaced with `_no_paths` so that relaxing that guard hands the child files to the unlink instead of silently orphaning them; a test asserts the present, empty behaviour and documents the coupling.
- `read_retention` parses per entry (a malformed threshold is simply absent) rather than falling back for the whole document like `_parse_schedule`: a category with no stored age has its own form default, so there is no usable state a partial document could lose.
- Both new test modules seed `NOW = datetime.now(UTC)` instead of a fixed calendar date. A fixed `2026-10-01` read as "recent" only because the run date happened to be 2026-10-14; against the running clock it was already 13 days old, which made a 30-day threshold wrongly eligible and surfaced as a listing-prune count of 2 instead of 1.
- The prune card's age field defaults to 30 and the stored thresholds are rendered as a read-back line (`artifacts 45 days`). A no-JavaScript `<select>` cannot reflect the stored value of whichever category the user later picks, so the control does not pretend it can.

## Deviations from Plan

**1. Task 3 lists `app/api/settings.py` in its `files`, but no edit was needed there.**
- **Found during:** Task 3.
- **Detail:** the plan's Task 3 action is "add the one-way category with its carve-out", and the confirm route's carve-out branch (snapshot, suspend, delete, restore, commit, then unlink) plus the D-164 amendment comment at the suspension call were built in Task 1 because the route is category-generic. Task 3 therefore changed only the repository and its tests. The `files` entry is satisfied by Task 1's commit (`9d4b74b`) rather than Task 3's (`7b93a7e`).
- **Impact:** none on behaviour; the plan's own "the allow-list, the validation and the preview/delete shape are built now so those tasks change one mapping entry each" anticipates exactly this.

**2. The literal token `queue_state` was removed from the repository's prose.**
- **Found during:** Task 1 verification.
- **Detail:** the plan's verify step asserts `'queue_state' not in app/db/repositories/retention_repo.py`. The module docstring originally explained D-167's wording slip by quoting it; the explanation is kept but reworded ("its queue watermark"), so the guard passes without losing the rationale.
- **Impact:** none; the assertion is a crude guard against implementing a per-listing watermark delete, and the reasoning still ships in the docstring.

---

**Total deviations:** 0 auto-fixed issues (no Rule 1/2/3 fixes were required; the two entries above are plan-faithful adaptations and a file-list note).
**Impact on plan:** No scope creep. Every acceptance criterion in the plan is covered by the committed code and its tests.

## Issues Encountered

- **`delete` name collision.** `_delete_artifacts` called the module's own `delete` instead of SQLAlchemy's, raising `TypeError: delete() missing 2 required keyword-only arguments`. Resolved by importing the construct as `sa_delete`.
- **The no-f-string assertion caught `%.1f`.** `_human_size` used `("%.1f" % value)`, whose literal contains the substring `f"`. Replaced with `"{:.1f}".format(value)`, which does not.
- **Test clock drift.** Fixed-date seeds made a "recent" row old against the running clock; both modules now derive `NOW` from `datetime.now(UTC)`.
- **`_human_size`'s trailing `return`** is unreachable (the loop always returns at its last unit); it carries a `# pragma: no cover` rather than a false claim.

## User Setup Required

None — no external service configuration required. The prune control adds no dependency, no environment variable and no migration (the `retention_json` column shipped in 08-03's migration 0008).

## Threat Flags

None — every file changed sits inside the plan's `<threat_model>`, and all nine threats (T-08-23 … T-08-31) are mitigated by code committed here or by the repository/route shapes this plan reuses.

## Known Stubs

None. `_paths_for_listings` returns an empty list by construction because of the listings artifact guard — that is a documented consequence of a guard, not a stub, and it is asserted by `test_a_listing_with_an_artifact_is_never_selected_and_yields_no_paths`.

## Next Phase Readiness

- RUN-07's reader-protecting invariants now hold in code: the health page's run-derived badge and the Adzuna verdict keep their inputs, and the spend ceilings keep their ledger.
- The operator walk of the prune control (one pass per category, in a browser with the stack up) is **UNRUN** — Docker and a browser are absent from this sandbox. It is recorded as an `unrun-verify` item in `.planning/WINDOWS.md` and must be executed before `/gsd-ship`.
- The `latex` lane remains operator-run and UNRUN, as recorded in the phase's other plans; nothing in this plan depends on it.

---
*Phase: 08-operations-polish*
*Completed: 2026-10-14*

## Self-Check: PASSED

- `app/db/repositories/retention_repo.py` — FOUND
- `tests/db/test_retention_repo.py` — FOUND
- `tests/api/test_settings_prune.py` — FOUND
- `.planning/phases/08-operations-polish/08-05-SUMMARY.md` — FOUND
- Commit `9d4b74b` (Task 1) — FOUND
- Commit `9b7ef8a` (Task 2) — FOUND
- Commit `7b93a7e` (Task 3) — FOUND
- Full hermetic suite (`pytest -q -m 'not live and not latex'`) — 1903 passed, 15 deselected, 2 xfailed
- Measured commits since the plan ledger base `dbf06ec`: 3 (measured via `git rev-list --count`, not narrated)

