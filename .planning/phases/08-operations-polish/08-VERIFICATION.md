---
phase: 08-operations-polish
verified: 2026-10-14T22:25:38Z
status: human_needed
score: 40/44 must-haves verified
covered_files:
  - .planning/phases/08-operations-polish/08-01-PLAN.md
  - .planning/phases/08-operations-polish/08-02-PLAN.md
  - .planning/phases/08-operations-polish/08-03-PLAN.md
  - .planning/phases/08-operations-polish/08-04-PLAN.md
  - .planning/phases/08-operations-polish/08-05-PLAN.md
  - .planning/phases/08-operations-polish/08-01-SUMMARY.md
  - .planning/phases/08-operations-polish/08-02-SUMMARY.md
  - .planning/phases/08-operations-polish/08-03-SUMMARY.md
  - .planning/phases/08-operations-polish/08-04-SUMMARY.md
  - .planning/phases/08-operations-polish/08-05-SUMMARY.md
  - .planning/REQUIREMENTS.md
  - Dockerfile
  - alembic/versions/0008_operations_config.py
  - app/api/health.py
  - app/api/health_page.py
  - app/api/settings.py
  - app/config.py
  - app/db/models.py
  - app/db/repositories/operations_config_repo.py
  - app/db/repositories/retention_repo.py
  - app/db/repositories/run_repo.py
  - app/db/repositories/source_repo.py
  - app/jobs/__init__.py
  - app/jobs/scheduler.py
  - app/main.py
  - app/web/templates/html/_application_history.html
  - app/web/templates/html/_application_row.html
  - app/web/templates/html/_health_strip.html
  - app/web/templates/html/_listing_row.html
  - app/web/templates/html/_screening_drafts.html
  - app/web/templates/html/applications_list.html
  - app/web/templates/html/base.html
  - app/web/templates/html/health.html
  - app/web/templates/html/listing_detail.html
  - app/web/templates/html/merges.html
  - app/web/templates/html/queue_list.html
  - app/web/templates/html/runs.html
  - app/web/templates/html/settings.html
  - assets/tailwind/input.css
  - compose.yml
  - docs/runbook-compose-smoke.md
  - docs/runbook-responsive-ui.md
  - entrypoint.sh
  - pyproject.toml
  - requirements.txt
  - static/vendor/app.css
  - tests/api/test_apply_package.py
  - tests/api/test_health.py
  - tests/api/test_health_page.py
  - tests/api/test_queue_links.py
  - tests/api/test_same_origin_guard.py
  - tests/api/test_schedule_settings.py
  - tests/api/test_settings_page.py
  - tests/api/test_settings_prune.py
  - tests/api/test_settings_reset.py
  - tests/db/test_migration_contract.py
  - tests/db/test_no_pii_columns.py
  - tests/db/test_orm_drift.py
  - tests/db/test_retention_repo.py
  - tests/db/test_skeleton_boot.py
  - tests/db/test_stop_signal_parse.py
  - tests/jobs/__init__.py
  - tests/jobs/test_scheduler.py
  - tests/pipeline/test_ingest_e2e.py
  - tests/test_auth_seam.py
  - tests/test_config.py
  - tests/test_dependency_pins.py
  - tests/test_responsive_contract.py
  - tests/test_stylesheet_coverage.py
covered_digest: "v3:sha256:66527a90ea1dff7978ef793ffb5bcabf453c88e97799391966fe3eae3e0a27a7"
behavior_unverified: 4
overrides_applied: 0
behavior_unverified_items:
  - truth: "SC4 — The UI is usable from both a laptop and a phone browser (the rendered phone/laptop walk)."
    test: "Open /, a listing detail, /status, the run control and /applications at 320, 375 and 768 px in a browser (docs/runbook-responsive-ui.md)."
    expected: "Journey tables reflow to label:value cards below the breakpoint with no horizontal scroll; admin tables sit inside a keyboard-reachable labelled scroll region at/above it; every compact control is >=44x44px."
    why_human: "The reflow, per-cell labels, scroll regions and tap floor are pinned by static + byte-identity tests, but 'usable' is a rendered-pixel claim no test exercises; no browser or Docker exists in this sandbox (WINDOWS #15)."
  - truth: "08-01 — The runtime image proves ZoneInfo('Europe/Dublin') resolves at image build time."
    test: "docker compose build (or `docker build .`) — the Dockerfile RUN asserts ZoneInfo resolves."
    expected: "The image build succeeds; a missing tz database fails the build rather than the morning run."
    why_human: "The Dockerfile assertion is present and correct, but Docker is absent from the sandbox, so the build has never executed (WINDOWS #14)."
  - truth: "08-02 — A long unbroken source name, absolute CV path or long fill-rate chip list wraps inside its card instead of widening the phone page (backstop)."
    test: "Inject a long unbroken token into a source name / CV path / fill-rate chip list and view at 320 px."
    expected: "The value wraps inside its card; the page gains no horizontal scroll."
    why_human: "Declared verification: backstop — a rendered-pixel claim; presence of `overflow-wrap: anywhere` is necessary but not sufficient."
  - truth: "08-02 — An operator-run checklist at 320/375/768 px across the journey pages confirms the reflow and scroll regions (backstop)."
    test: "Run docs/runbook-responsive-ui.md end to end."
    expected: "Card reflow below the breakpoint and desktop table inside its scroll region at/above it, on every listed page."
    why_human: "Declared verification: backstop — the operator checklist itself; duplicates SC4's rendered walk (WINDOWS #15)."
human_verification:
  - test: "Run the full operator responsive walk (docs/runbook-responsive-ui.md) at 320/375/768 px across queue, listing detail, /status, run control and /applications."
    expected: "Card reflow below the breakpoint; admin tables inside labelled keyboard-reachable scroll regions at/above it; 44px tap floor holds; no horizontal scroll."
    why_human: "Rendered-pixel claim; no browser/Docker in sandbox (WINDOWS #15)."
  - test: "docker compose build — confirm the Dockerfile's build-time ZoneInfo('Europe/Dublin') assertion runs and passes."
    expected: "Build succeeds (tzdata is the documented remedy if it fails)."
    why_human: "Docker absent from sandbox (WINDOWS #14)."
  - test: "PLAT-06 operator half: set a daily time, `docker compose restart`, confirm the schedule survives and exactly one run with trigger='schedule' fires (never two)."
    expected: "Schedule persists across the restart; one scheduled run, no duplicate, no overlap."
    why_human: "Docker absent; the hermetic test proves the persisted job survives a fresh scheduler with a past-due fire time, but the compose restart path is operator-only (WINDOWS #16)."
  - test: "Walk the Prune history control once per category: pick a category and age, read the preview counts + protected line, confirm, verify the audit banner."
    expected: "Preview matches the delete; audit line names the category/age/count; no protected row is removed."
    why_human: "Docker/browser absent; automated coverage exists (test_retention_repo.py, test_settings_prune.py) but the rendered walk is unrun (WINDOWS #17)."
  - test: "Resolve the 13 judgment-tier prohibitions (see Prohibitions) — confirm none is violated."
    expected: "Each MUST-NOT statement holds in the shipped code."
    why_human: "Judgment-tier prohibitions: an LLM-judge verdict is recorded below as NON-AUTHORITATIVE; interactive verification requires explicit human resolution per item."
---

# Phase 8: Operations + Polish Verification Report

**Phase Goal:** A scheduled, self-reporting, responsive tool — once the pipeline is trustworthy enough that a cron job will not simply hide failures.
**Verified:** 2026-10-14T22:25:38Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Verification mode note

`ROADMAP.md` marks this phase `Mode: mvp`, but the phase goal is **not** in the
User Story form (`As a … I want … so that …`), so MVP-mode narrowing (the
`[outcome]` clause check) cannot be applied. Standard goal-backward verification
was used against the roadmap's four explicit **Success Criteria**, which are the
binding contract. This is a process note, not a defect in the phase.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | **SC1 (RUN-05/RUN-06)** User can schedule recurring runs and see when the next run will happen. | ✓ VERIFIED | `POST /settings/schedule` + `Schedule` card (`settings.html:235-270`); `operations_config_repo.write_schedule`/`read_schedule`; `scheduler.reconcile` registers/removes the one job; `next_run_at()`; `/status` next-run line. Tests: `test_saving_a_time_registers_exactly_one_job`, `test_resaving_a_new_time_reschedules_the_same_single_job`, `test_disabling_the_schedule_removes_the_job`, `test_the_next_run_line_renders_a_countdown_for_a_registered_job` — all green. |
| 2 | **SC2 (PLAT-06)** Scheduled runs persist across restarts and execute only once with a single worker. | ✓ VERIFIED | Persistent `SQLAlchemyJobStore(engine=_jobstore_engine())`; `entrypoint.sh` pins `--workers 1` (comment names the scheduler); overlap guard is `run_repo.running_run_id` (one predicate shared with the reset guard). Tests: `test_a_past_due_fire_time_is_not_clobbered`, `test_reconcile_creates_the_job_when_absent`, `test_reconcile_is_idempotent`, `test_in_flight_run_is_skipped_not_overlapped` — green. |
| 3 | **SC3 (RUN-07)** User can check system and source health from a health endpoint surfaced in the UI, with source status from recorded stop signals rather than auto-escalation. | ✓ VERIFIED | `GET /status` (`health_page.py`) reached from the `Health` nav entry (`base.html:34`); JSON `/health` untouched; both call one `dependency_report`; per-source table from `get_source_health_with_signals` (DB-only); Adzuna verdict from `board_evidence` + pure `adzuna_promotion_condition`, read-only. Tests: `test_the_health_page_is_surfaced_in_the_nav`, `test_the_page_and_the_json_cannot_disagree`, `test_the_page_issues_no_board_request`, `test_the_verdict_region_offers_no_control` — green. |
| 4 | **SC4 (UI-06)** The UI is usable from both a laptop and a phone browser, with all assets vendored locally and no CDN dependency. | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Vendoring + no-CDN ✓ (`tests/test_no_cdn.py` 7 passed; `base.html` links only `/static/vendor/*`). Reflow/labels/scroll-regions/tap-floor ✓ (`test_responsive_contract.py`, byte-identity guard ran). But "usable from a phone browser" is a rendered claim no test exercises → human walk (WINDOWS #15). |
| 5 | 08-01: `apscheduler` at exactly `3.11.3` importable and declared in BOTH manifests, bound by `tests/test_dependency_pins.py`. | ✓ VERIFIED | `requirements.txt:31` and `pyproject.toml:38` both `apscheduler==3.11.3`; `PINNED_PACKAGES` row present; `test_dependency_pins.py` green. |
| 6 | 08-01: A human confirmed the distribution/version/source before install, behind a blocking-human gate. | ✓ VERIFIED | Recorded checkpoint resolved `approved: apscheduler=3.11.3` before any install/manifest edit (08-01-SUMMARY); code-side fact (exact pin) independently verified. The approval itself is a self-reported process record. |
| 7 | 08-01: Two `Settings` fields with shipped defaults, covered by the config surface + ceiling guards. | ✓ VERIFIED | `app/config.py:253,258`; `test_config.py` `REQUIRED_SETTINGS_FIELDS`, `LIMIT_FIELDS`, `SCANNED_DIRS` includes `app/jobs`; green. |
| 8 | 08-01: Both knobs forwarded through `compose.yml`. | ✓ VERIFIED | `compose.yml:72-73` `SCHEDULE_TIMEZONE`, `SCHEDULE_MISFIRE_GRACE_SECONDS`. |
| 9 | 08-01: The runtime image proves `ZoneInfo('Europe/Dublin')` at build time. | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `Dockerfile:58-59` present and correct; build never executed (Docker absent) → human (WINDOWS #14). |
| 10 | 08-01: `entrypoint.sh` still pins `--workers 1` and names the scheduler as a second reason. | ✓ VERIFIED | `entrypoint.sh:7-10`. |
| 11 | 08-02: Below the phone breakpoint each journey table renders label:value cards from `data-label`; desktop unchanged. | ✓ VERIFIED | `input.css` phone media block with `td[data-label]::before { content: attr(data-label) }`; `_listing_row.html` (8), `_application_row.html` (6), `_health_strip.html` (5) labels; `test_responsive_contract.py` row-restack tests green. |
| 12 | 08-02: Every journey row restacks ALL its desktop columns. | ✓ VERIFIED | `test_the_queue_row_restacks_every_desktop_column`, `…health_row…`, `…tracker_row…`, `test_the_conditional_exclusion_column_has_a_matching_label_pair` — green. |
| 13 | 08-02: Non-journey tables wrapped in an accessible, keyboard-reachable, named scroll region. | ✓ VERIFIED | `merges.html:43`, `runs.html:27`, `listing_detail.html:63` `class="table-scroll" role="region" tabindex="0" aria-label=…`; `test_every_admin_table_keeps_a_labelled_keyboard_scroll_region` green. |
| 14 | 08-02: Every compact/icon control clears the 44x44px minimum. | ✓ VERIFIED | `.touch-target` on nav links, queue/tracker actions, history summaries, copy-answer, and the three settings submits; `test_every_nav_link_carries_the_tap_floor`, `test_the_compact_journey_controls_carry_the_tap_floor`, `test_the_prune_and_schedule_submits_carry_the_tap_floor` green. |
| 15 | 08-02: Reflow authored in the Tailwind input, CSS-only, committed stylesheet byte-identical. | ✓ VERIFIED | `assets/tailwind/input.css` rules + media block; `static/vendor/app.css` byte-identity test **ran** the pinned CLI and passed; no JS added. |
| 16 | 08-02: A long unbroken value wraps inside its card (backstop). | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `overflow-wrap: anywhere` present; declared `verification: backstop` → rendered claim → human. |
| 17 | 08-02: Operator checklist at 320/375/768 px confirms the reflow (backstop). | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `docs/runbook-responsive-ui.md` exists; checklist unrun → human (WINDOWS #15). |
| 18 | 08-03: The schedule persists time-of-day + timezone; exactly one job registered matching that time; unchecking removes it. | ✓ VERIFIED | `operations_config_repo`; `scheduler.reconcile`; tests `test_saving_a_time_registers_exactly_one_job`, `test_disabling_the_schedule_removes_the_job` green. |
| 19 | 08-03: Runtime-editable with no restart; commit first, then reconfigure; unavailable scheduler reports in banner. | ✓ VERIFIED | `save_schedule` commits then `reconcile` inside try/except with banner (`settings.py:509-528`). |
| 20 | 08-03: A restart leaves exactly one job; an in-flight trigger creates no second Run row and records a skip reason. | ✓ VERIFIED | `reconcile` create-if-absent + `test_reconcile_is_idempotent`; `_record_skip`/`write_skip_notice`; `test_in_flight_run_is_skipped_not_overlapped`. |
| 21 | 08-03: Concurrent triggers yield at most one in-flight run — a second is skipped, never overlapped. | ✓ VERIFIED | DB-read guard `run_repo.running_run_id` in `run_scheduled_pipeline`; test green. |
| 22 | 08-03: A past-due fire time is preserved at boot; create-if-absent / reschedule only on drift. | ✓ VERIFIED | `reconcile` leaves a matching job alone; `test_a_past_due_fire_time_is_not_clobbered`, `test_a_timezone_change_is_detected_with_identical_cron_fields` green. |
| 23 | 08-03: Non-terminal leftover runs reconciled to literal `partial` at boot with the failure recorded. | ✓ VERIFIED | `reconcile_stale_runs`; `test_stale_running_rows_are_reconciled_to_partial`, `test_reconcile_stale_runs_preserves_existing_errors` green. |
| 24 | 08-03: `start_scheduler`/`stop_scheduler` idempotent, never raise; a broken jobstore degrades and the app boots. | ✓ VERIFIED | Both wrapped in try/except returning `unavailable`/no-op; `test_a_broken_jobstore_degrades_to_unavailable`, `test_start_stop_are_total` green. |
| 25 | 08-04: `/status` reachable from `Health` nav; `/health` stays JSON; both read one `auth_configured` helper. | ✓ VERIFIED | `HEALTH_PAGE_PATH="/status"`; `base.html:34`; shared `dependency_report`; `test_the_page_declares_status_and_not_health`, `test_the_page_and_the_json_cannot_disagree` green. |
| 26 | 08-04: A view of `/status` issues ZERO outbound job-board requests. | ✓ VERIFIED | `source_repo` imports no probe orchestration; `health_page` imports no adapter; `test_the_page_issues_no_board_request`, `test_the_verdict_read_issues_no_board_request` green. |
| 27 | 08-04: The system section assembles DB/opencode/LaTeX/CV reports; each failure is data. | ✓ VERIFIED | `_dependency_rows`; `test_the_page_renders_the_four_dependency_rows`, `test_the_page_answers_when_a_dependency_probe_raises` green. |
| 28 | 08-04: The page and the queue strip render the same per-source table from the same partial. | ✓ VERIFIED | `health.html` `{% include "html/_health_strip.html" %}` verbatim. |
| 29 | 08-04: Next-run line renders a real next fire time or an honest off/unscheduled state; never fabricated. | ✓ VERIFIED | `_schedule_line`; tests `test_a_disabled_schedule_reads_scheduling_off`, `test_an_enabled_schedule_with_no_job_never_fabricates_a_time` green. |
| 30 | 08-04: A skipped run is surfaced from the durable skip record (missed + in-flight wording). | ✓ VERIFIED | `_skip_notice`; `test_the_missed_run_notice_renders_from_a_recorded_skip`, `test_the_in_flight_skip_renders_its_own_wording`, `test_no_notice_renders_without_a_recorded_skip` green. |
| 31 | 08-04: The page renders the last run's status + one-line reason, linking to run history. | ✓ VERIFIED | `_last_run`; `test_the_last_run_line_names_the_status_and_reason` green. |
| 32 | 08-04: The Adzuna promotion verdict is shown read-only with its number and a probe-document link; no enabling control. | ✓ VERIFIED | `_verdict_view`; `test_the_verdict_line_carries_the_recorded_fraction`, `test_the_verdict_region_offers_no_control` green. |
| 33 | 08-04: Every failure path degrades to data (degraded dep, broken DB read, missing scheduler, absent verdict). | ✓ VERIFIED | try/except around every read in `page_context`; `test_the_page_answers_when_the_database_read_fails`, `…when_the_scheduler_raises` green. |
| 34 | 08-05: Per-category, per-threshold prune control (never one global switch). | ✓ VERIFIED | `PRUNE_CATEGORY_LABELS` select + `age_days`; `test_the_prune_card_offers_every_prune_category` green. |
| 35 | 08-05: Preview returns count + on-disk size; confirm is a separate submit; an audit line records category/threshold/time. | ✓ VERIFIED | `preview`/`confirm_prune`; `test_the_preview_round_trips_and_offers_the_confirm`, `test_the_confirm_deletes_the_rows_and_the_files_and_renders_the_audit` green. |
| 36 | 08-05: Preview count and delete count come from one predicate. | ✓ VERIFIED | Shared `_prune_preview_or_error` + `retention_repo.delete`; `test_preview_and_delete_agree_for_runs_and_the_request_log` green. |
| 37 | 08-05: Four guards (run floor, LLM ledger, app-linked artifact, newest successful artifact) are the queries' own conditions. | ✓ VERIFIED | `_select_runs`/`_select_artifacts` WHERE clauses; `test_the_floor_guard_holds_for_every_category`, `…ledger_guard…`, `…application_link_guard…`, `…newest_successful_artifact_guard…` green. |
| 38 | 08-05: Runs prune is FK-safe — children first, ledger nulled, undeletable excluded. | ✓ VERIFIED | `_delete_runs`; `test_the_runs_ordering_deletes_children_before_parents`, `test_the_ledger_rows_survive_with_a_nulled_run_reference`, `test_a_run_with_undeletable_listing_events_is_excluded_from_the_selection` green. |
| 39 | 08-05: `source_request_log` prune keeps every row of a retained run. | ✓ VERIFIED | `_select_source_request_log`; `test_a_source_log_row_of_a_retained_run_survives_and_an_orphan_row_is_selected` green. |
| 40 | 08-05: Stale-listing prune is a hard delete of the listing + children + events, suspending/re-arming the append-only trigger, with the D-164 amendment recorded. | ✓ VERIFIED | `confirm_prune` carve-out path; `retention_repo` docstring records the amendment; `test_a_stale_listing_prune_deletes_its_children_and_its_events` green. |
| 41 | 08-05: The append-only trigger is re-armed after a listing prune, asserted from the DB catalog. | ✓ VERIFIED | `test_the_listing_prune_leaves_the_append_only_trigger_armed_with_its_negative_control` green. |
| 42 | 08-05: A stale-listing prune is preceded by a DB snapshot; regenerable categories are not snapshotted. | ✓ VERIFIED | `carve_out` snapshot branch in `confirm_prune`; `test_a_snapshot_destination_collision_refuses_and_deletes_nothing` green. |
| 43 | 08-05: Artifact rows and their files go together — rows commit first, files unlinked after, each path contained in `artifacts_dir`. | ✓ VERIFIED | `_unlink_artifacts` containment; `test_a_path_outside_the_artifacts_directory_is_skipped_and_reported`, `test_a_missing_file_contributes_zero_and_is_reported` green. |
| 44 | 08-05: Every prune route carries the identity seam and is a POST. | ✓ VERIFIED | Both routes `Depends(current_user)`, declared `@router.post`; `tests/test_auth_seam.py` inventory lists `/settings/prune/preview`, `/settings/prune` and passes. |

**Score:** 40/44 truths verified (4 present, behavior-unverified)

### Deferred Items

None. Phase 8 is the last phase in the milestone; no unmet truth is addressed by a
later phase.

### Advisory (New Scope, Unevidenced)

| # | Finding | Category | Why Advisory |
| --- | --- | --- | --- |
| 1 | MVP-mode user-story narrowing could not be applied (the phase goal is not a User Story). Verification used the roadmap's four explicit Success Criteria instead. | other | Process note; no deterministic evidence either way. Not a defect in the shipped code. |

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `requirements.txt` / `pyproject.toml` | `apscheduler==3.11.3` in both | ✓ VERIFIED | Lines 31 / 38; bound by `test_dependency_pins.py`. |
| `app/config.py` | `schedule_timezone`, `schedule_misfire_grace_seconds` | ✓ VERIFIED | Lines 253, 258. |
| `Dockerfile` | `ENV TZ` + build-time ZoneInfo proof | ✓ PRESENT (build unrun) | Lines 58-59; operator build pending. |
| `entrypoint.sh` | `--workers 1` + scheduler comment | ✓ VERIFIED | Lines 7-10. |
| `alembic/versions/0008_operations_config.py` | singleton table migration | ✓ VERIFIED | Purely additive; `ck_operations_config_singleton`; downgrade drops the table. |
| `app/db/models.py` | `OperationsConfig` | ✓ VERIFIED | `id` pinned to 1; 3 JSON columns; no FK/identity. |
| `app/db/repositories/operations_config_repo.py` | total schedule read, strict write, skip notice | ✓ VERIFIED | Full module read. |
| `app/jobs/scheduler.py` | scheduler, jobstore, reconcile, target, next-run, listeners, stale-run reconcile | ✓ VERIFIED | 342 lines; substantive; wired into lifespan. |
| `app/main.py` | scheduler start/stop in lifespan; `_same_origin_guard`; health page router | ✓ VERIFIED | Lines 54-68, 100-118, 131. |
| `app/api/settings.py` | schedule + prune routes | ✓ VERIFIED | `POST /settings/schedule`, `/settings/prune/preview`, `/settings/prune`. |
| `app/web/templates/html/settings.html` | Schedule card + Prune history card | ✓ VERIFIED | Lines 235-270, 300-365. |
| `app/api/health.py` | shared `dependency_report` (key names unchanged) | ✓ VERIFIED | Lines 100-131; `/health` JSON route unchanged. |
| `app/api/health_page.py` | `GET /status` route | ✓ VERIFIED | Full module; total; DB-only. |
| `app/db/repositories/source_repo.py` | run-derived signal read + board-evidence builder | ✓ VERIFIED | `get_source_health_with_signals`, `board_evidence`; no probe import. |
| `app/db/repositories/retention_repo.py` | prune SQL: allow-list, per-category select + guards, preview, delete, unlink list | ✓ VERIFIED | 530 lines; guards are query conditions. |
| `app/web/templates/html/health.html` | system grid, schedule/last-run/skip lines, read-only verdict, included source table | ✓ VERIFIED | Includes `_health_strip.html` verbatim. |
| `app/web/templates/html/base.html` | `Health` nav → `/status` | ✓ VERIFIED | Line 34. |
| `assets/tailwind/input.css` / `static/vendor/app.css` | new component rules + media block; byte-identical build | ✓ VERIFIED | Byte-identity test ran and passed. |
| `docs/runbook-responsive-ui.md`, `docs/runbook-compose-smoke.md` | operator checklists | ✓ VERIFIED (unrun) | Exist; operator walk pending. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `app/jobs/scheduler.py` | `apscheduler.schedulers.asyncio` / `jobstores.sqlalchemy` | module-scope import | ✓ WIRED | Imported; app boots. |
| `app/main.py` lifespan | `scheduler.start_scheduler`/`stop_scheduler` | `await` in non-fatal guard | ✓ WIRED | Lines 54-68. |
| `settings.html` schedule form | `POST /settings/schedule` → `reconcile` | form action | ✓ WIRED | Commits then reconfigures. |
| `run_scheduled_pipeline` | `run_pipeline("schedule", None, factory)` | direct call | ✓ WIRED | Only pipeline entry point. |
| `run_scheduled_pipeline` overlap guard | `run_repo.running_run_id` | DB read | ✓ WIRED | Same predicate as the reset guard. |
| `/status` page | `dependency_report` (shared with `/health`) | direct call | ✓ WIRED | One definition. |
| `health.html` | `_health_strip.html` | `{% include %}` verbatim | ✓ WIRED | Same partial as the queue. |
| `/status` verdict | `board_evidence` → `adzuna_promotion_condition` | repository builder + pure fn | ✓ WIRED | Read-only; no control. |
| prune preview | `retention_repo.delete` | same category/age predicate | ✓ WIRED | Preview count == delete count. |
| `confirm_prune` listing carve-out | `_suspend_append_only_trigger` / `_restore_append_only_trigger` | reused reset helpers | ✓ WIRED | Trigger re-armed inside the transaction. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `/status` per-source table | `source_health` | `get_source_health_with_signals` (runs + `source_request_log` reads) | Yes | ✓ FLOWING |
| `/status` next-run line | `schedule_line` | stored schedule row + live `next_run_at()` | Yes | ✓ FLOWING |
| `/status` verdict | `board_verdicts` | `board_evidence` from persisted rows | Yes | ✓ FLOWING |
| settings schedule card | `schedule` | `operations_config_repo.read_schedule` | Yes | ✓ FLOWING |
| settings prune card | `retention`, `prune_preview` | `read_retention` + `retention_repo.preview` | Yes | ✓ FLOWING |

No value traces to a static return, hardcoded literal, or mock.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Phase-specific lane (scheduler, schedule settings, health page, retention, prune, pins) | `pytest tests/jobs tests/api/test_schedule_settings.py tests/api/test_health_page.py tests/db/test_retention_repo.py tests/api/test_settings_prune.py tests/test_dependency_pins.py -q` | 111 passed | ✓ PASS |
| Stylesheet byte-identity + no-CDN + responsive contract + same-origin guard | `pytest tests/test_stylesheet_coverage.py tests/test_no_cdn.py tests/test_responsive_contract.py tests/api/test_same_origin_guard.py -q` | 56 passed (byte-identity guard **ran**, not skipped) | ✓ PASS |
| Full hermetic suite (regression gate) | `pytest -q` (run twice) | 1955 passed, 15 deselected, 2 xfailed, 0 failed | ✓ PASS |

### Probe Execution

N/A — this phase declares no `scripts/*/tests/probe-*.sh` and mentions no probes.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| RUN-05 | 08-01, 08-03 | User can schedule recurring runs | ✓ SATISFIED | Settings form + singleton row + one APScheduler job; tests green. |
| RUN-06 | 08-04 | User can see when the next scheduled run will happen | ✓ SATISFIED | `/status` next-run line from `next_run_at()`; tests green. |
| RUN-07 | 08-04, 08-05 | User can check system and source health from a health endpoint surfaced in the UI | ✓ SATISFIED | `/status` + `Health` nav + per-source table + read-only verdict + manual prune; tests green. |
| PLAT-06 | 08-03 | Scheduled runs are single-worker safe and persist across restarts | ✓ SATISFIED | `--workers 1`, persistent job store, overlap guard; hermetic persistence test green. Compose-restart half is operator (WINDOWS #16). |
| UI-06 | 08-02 | The UI is usable from both a laptop and a phone browser | ✓ SATISFIED (static) / ⚠️ rendered walk | Reflow + labels + scroll regions + tap floor + no-CDN verified; rendered walk is human (WINDOWS #15). |

All five phase requirement IDs (RUN-05, RUN-06, RUN-07, PLAT-06, UI-06) are claimed
by a plan and accounted for. No orphaned requirements: `REQUIREMENTS.md` maps
exactly these five IDs to Phase 8, and no plan claims an ID outside this set.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| — | — | — | — | None. No `TBD`/`FIXME`/`XXX` in any phase-modified file; no placeholder/stub markers; no `return {}`/empty-handler stubs; no hardcoded-empty data on a rendered path. |

### Prohibitions (judgment-tier — LLM-judge verdicts, NON-AUTHORITATIVE)

Autonomous verification recorded the following verdicts. None is a silent pass:
each is flagged **`unverified-prohibition — human review recommended`** and appears
in Human Verification. All are advisory here and do not by themselves fail the phase.

| # | Prohibition | LLM-judge verdict | Flag |
| --- | --- | --- | --- |
| 1 | 08-01 MUST NOT add a third-party package not human-approved at an exact pin | Not violated — only `apscheduler==3.11.3` added, exact pin in both manifests | unverified-prohibition — human review recommended |
| 2 | 08-01 MUST NOT add a dependency from a floating range/branch/unshown source | Not violated — exact `==3.11.3` | unverified-prohibition — human review recommended |
| 3 | 08-02 MUST NOT add JS for the reflow or introduce a CDN | Not violated — no JS; `test_no_cdn.py` green | unverified-prohibition — human review recommended |
| 4 | 08-02 MUST NOT hand-edit the committed stylesheet | Not violated — byte-identity guard passes | unverified-prohibition — human review recommended |
| 5 | 08-03 MUST NOT start a second concurrent pipeline | Not violated — DB overlap guard + test | unverified-prohibition — human review recommended |
| 6 | 08-03 MUST NOT back-fill/catch up a missed run | Not violated — no catch-up code; skip notice | unverified-prohibition — human review recommended |
| 7 | 08-03 MUST NOT fabricate a next-run time | Not violated — total `next_run_at()`; honest states; tests | unverified-prohibition — human review recommended |
| 8 | 08-04 MUST NOT put a request on a job board from a page view | Not violated — DB-only; `test_the_page_issues_no_board_request` | unverified-prohibition — human review recommended |
| 9 | 08-04 MUST NOT escalate/switch adapters automatically | Not violated — read-only verdict; no control | unverified-prohibition — human review recommended |
| 10 | 08-04 MUST NOT echo raw upstream/DB content | Not violated — exception class name only; tests | unverified-prohibition — human review recommended |
| 11 | 08-05 MUST NOT prune automatically or on the scheduled run | Not violated — manual POSTs only | unverified-prohibition — human review recommended |
| 12 | 08-05 MUST NOT prune the ledger/app-linked/newest artifact or below the floor | Not violated — guards are query conditions; guard tests | unverified-prohibition — human review recommended |
| 13 | 08-05 MUST NOT delete/unlink outside the artifacts dir, or leave rows pointing at missing files | Not violated — containment + post-commit unlink | unverified-prohibition — human review recommended |

### Human Verification Required

1. **Operator responsive walk (SC4 / UI-06 / WINDOWS #15)** — run `docs/runbook-responsive-ui.md` at 320/375/768 px across queue, listing detail, `/status`, run control and `/applications`. Expected: card reflow below the breakpoint, admin tables inside labelled keyboard-reachable scroll regions at/above it, 44px tap floor holds, no horizontal scroll.
2. **Docker build tz proof (08-01 / WINDOWS #14)** — `docker compose build`; the Dockerfile asserts `ZoneInfo('Europe/Dublin')` resolves at build time.
3. **PLAT-06 compose-restart persistence (WINDOWS #16)** — set a daily time, `docker compose restart`, confirm the schedule survives and exactly one `trigger='schedule'` run fires (never two).
4. **Prune history browser walk (08-05 / WINDOWS #17)** — one pass per category: preview counts + protected line, confirm, audit banner.
5. **Prohibitions review** — resolve the 13 judgment-tier prohibitions above (all currently "not violated", non-authoritative).

### Gaps Summary

**No gaps.** Every must-have artifact exists, is substantive (not a stub), is wired
into the app, and traces to a real data source. Every key link is connected. The
full hermetic suite is green (1955 passed, 0 failed), including the byte-identity
stylesheet guard, the no-CDN guard, the migration-contract/ORM-drift/no-PII guards
updated for migration 0008, and the auth-seam route inventory.

Four truths remain **present-but-behavior-unverified** because they assert rendered
or build-time behavior no automated test in this sandbox can exercise (no browser,
no Docker): SC4's phone usability, the Dockerfile tz build proof, the long-value
wrap backstop, and the operator checklist. They are routed to human verification,
not counted as verified, and they do not fail the phase (the code is present and
correct). No BLOCKER was found.

---

_Verified: 2026-10-14T22:25:38Z_
_Verifier: the agent (gsd-verifier)_
