---
phase: 07-assisted-apply-tracker
verified: 2026-09-30T18:38:55Z
status: human_needed
score: 31/33 must-haves verified
covered_files:
  - .planning/phases/07-assisted-apply-tracker/07-01-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-02-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-03-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-04-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-05-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-01-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-02-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-03-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-04-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-05-SUMMARY.md
  - .planning/REQUIREMENTS.md
  - alembic/versions/0006_screening_drafts.py
  - app/api/applications.py
  - app/api/apply.py
  - app/api/settings.py
  - app/config.py
  - app/db/models.py
  - app/db/repositories/application_repo.py
  - app/db/repositories/apply_config_repo.py
  - app/db/repositories/screening_draft_repo.py
  - app/domain/schemas/screening.py
  - app/main.py
  - app/pipeline/draft.py
  - app/verify/screening.py
  - app/web/templates/html/_application_history.html
  - app/web/templates/html/_application_row.html
  - app/web/templates/html/_screening_drafts.html
  - app/web/templates/html/applications.html
  - app/web/templates/html/applications_list.html
  - app/web/templates/html/apply.html
  - app/web/templates/html/base.html
  - app/web/templates/html/listing_detail.html
  - app/web/templates/html/settings.html
  - static/vendor/app.css
  - tests/api/test_applications_tracker.py
  - tests/api/test_apply_package.py
  - tests/api/test_settings_page.py
  - tests/api/test_settings_reset.py
  - tests/db/test_application_events.py
  - tests/db/test_application_repo.py
  - tests/db/test_apply_config_repo.py
  - tests/db/test_migration_contract.py
  - tests/db/test_no_pii_columns.py
  - tests/db/test_screening_draft_repo.py
  - tests/db/test_skeleton_boot.py
  - tests/pipeline/test_draft_stage.py
  - tests/test_auth_seam.py
  - tests/test_config.py
  - tests/verify/test_screening.py
covered_digest: "v1:sha256:18688e6be410dbc745f3cb607424825fc8702b96455dcfa9431b5ee248cd46f6"
behavior_unverified: 0
overrides_applied: 0
decision_coverage:
  honored: 10
  total: 16
  not_honored: ["D-120", "D-126", "D-128", "D-132", "D-133", "D-134"]
human_verification:
  - test: "Tracker note-fidelity (backstop truth, 07-04): open `/applications` and expand a row whose note is longer than the cell; inspect the DOM to confirm the history partial / latest-note cell carries the complete untruncated note string in the truncated element's `title` attribute."
    expected: "The rendered note text is visually truncated to one line with an ellipsis, and the full untruncated string is present in `title=\"\"`. The plan declared a held-out UI-state test asserting this, which was not shipped."
    why_human: "`verification: backstop` (non-inferable). No held-out/property-based test asserts the full note string survives truncation; the `.truncate` CSS and `title=\"{{ row.notes or '' }}\"` are present and wired but the fidelity claim is only observable in a rendered DOM."
  - test: "Clipboard copy fidelity (backstop truth, 07-05): open an apply package, draft or seed a multi-paragraph answer, click `Copy answer`, and paste into a scratch field."
    expected: "The pasted text equals the full, untruncated, multi-paragraph answer; the button label flips to `Copied` for ~2s. The plan declared a held-out UI-state test asserting copy fidelity across a multi-paragraph answer, which was not shipped."
    why_human: "`verification: backstop` (non-inferable). `navigator.clipboard.writeText(...textContent)` is wired to the adjacent `.answer-text`, but clipboard behaviour and untruncated fidelity are browser-only and no held-out test exercises them."
  - test: "Tracker visual scanning + no-JS degrade (07-01 D6): load `/applications` with and without JavaScript; scan the Stage column."
    expected: "The `.badge-stage-*` column anchors the eye as the scanning element and the transition/notes forms still work (or degrade legibly) with JS off."
    why_human: "Visual scanning quality and the no-JS interaction are judgement calls; the class-coverage guard only proves a CSS rule exists."
  - test: "Apply-package ready page reads as designed (07-02 D6): open `/listings/{id}/apply` with an `ok` artefact."
    expected: "The no-submit reassurance reads as an intentional banner rather than a missing button; the outbound action is the visual primary; the block order (reassurance → link → verified PDF → gaps → answers → record) reads correctly."
    why_human: "Perceived affordance is a visual judgement no assertion proves."
  - test: "Grounding residual policy is acceptable (07-03 D4): read `app/verify/screening.py` and confirm the two stated residuals match the operator's honesty expectation."
    expected: "The operator accepts that a numberless fabrication passes the numeric check and that a computed number absent verbatim from the sources is conservatively flagged as a warning (never a block)."
    why_human: "Whether the residual policy and its runtime-visible wording are adequate honesty signalling is a product judgement, not a code fact."
  - test: "Drafted-answers region reads as designed (07-05 D6): inspect the `#apply-answers` region on the package page."
    expected: "Per-question blocks, evidence chips, the `.answer-warning` line, the neutral `Copy answer` button and the confirm-guarded delete read as a designed surface."
    why_human: "Visual/layout judgement."
  - test: "Real compiled ok PDF in the Tectonic container (07-VALIDATION Manual-Only): in the container, tailor + compile a listing, then open `/listings/{id}/apply` and confirm the verified-PDF block embeds and downloads."
    expected: "The PDF block embeds the real compiled PDF and `?download=1` attaches it."
    why_human: "No LaTeX engine in this environment (D-69); the latex lane is deselected. The `gated`/`ready` gate and the db-side attachment logic are verified, but the real Tectonic compile is container-only."
  - test: "Phone-width usability (UI-04): load `/applications` at 375px."
    expected: "`.queue-table` scrolls horizontally without clipping, the stage filter and needs-action view are reachable, and the inline history expands without horizontal scroll."
    why_human: "Responsive visual judgement."
---

# Phase 07: Assisted Apply + Tracker Verification Report

**Phase Goal (ROADMAP.md, verbatim):** An apply package per listing plus an application tracker that links every outcome to the exact verified CV artefact that was sent.
**Verified:** 2026-09-30T18:38:55Z
**Status:** human_needed
**Re-verification:** No — initial verification

**Roadmap Success Criteria (verbatim):**

1. User can open an apply package for a listing containing the verified PDF, the apply link, drafted screening answers, and a gap checklist.
2. The tool never submits an application on the user's behalf.
3. User can record an application with a status stage, notes, and a next-action date/deadline, and every application links to the exact verified CV artefact that was sent.
4. Application status changes are recorded as an append-only event history the user can view and manage.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | (SC1) Apply package per listing: verified PDF, apply link, drafted screening answers, gap checklist | ✓ VERIFIED | `app/api/apply.py` `GET /listings/{id}/apply` assembles stored data only; `apply.html` renders the five blocks + `#apply-answers`; tests `test_ready_with_an_ok_artifact`, `test_gap_checklist_renders_the_stored_gaps`, `test_answers_region_renders_the_defaults_not_yet_drafted` |
| 2 | (SC2) The tool never submits on the user's behalf | ✓ VERIFIED | Plain `<a class="apply-link" target="_blank" rel="noopener noreferrer">`; every form posts to a local path; `test_no_submit_surface` walks the route registry and form actions; no `submit` route exists |
| 3 | (SC3) Record application with stage/notes/next-action; link to the exact verified CV | ✓ VERIFIED | `record_application_route` + `application_repo.record_application`; `applied` requires `read_for_download(ok_only=True)`; `test_record_via_http...`, `test_applied_requires_ok_artifact`, `test_record_from_the_package_links_the_ok_artifact` |
| 4 | (SC4) Status changes recorded as append-only event history, viewable/managed | ✓ VERIFIED | migration 0006 triggers `RAISE(ABORT,'application_events is append-only')`; `read_history` + `_application_history.html`; `test_the_database_aborts_an_update_and_a_delete_of_an_event`, `test_history_partial_lists_all_events_in_order_and_count_matches` |
| 5 | (P01) Zero applications renders `#application-empty`; a recorded application shows its one `created → <stage>` transition | ✓ VERIFIED | `applications_list.html` empty branch; `_application_history.html` L13 renders NULL `from_status` as `created`; `test_empty_tracker_renders_the_empty_state`, `test_record_via_http_renders_the_row_and_its_created_event` |
| 6 | (P01) Eventless row renders `No history recorded.`; chronological order; `History (n)` matches entries | ✓ VERIFIED | `_application_history.html` L9/L19; `read_history` orders `(occurred_at, id)`; `test_history_partial_renders_no_history_recorded_for_an_eventless_row`, `test_history_partial_lists_all_events_in_order_and_count_matches` |
| 7 | (P01) Refused status transition returns a 4xx `data-error` fragment in the row slot and writes nothing | ✓ VERIFIED | `_row_error()`; `transition_application` returns `None` before any write; `test_applied_requires_ok_artifact` (HTTP + repo) asserts `(1,1)` unchanged after refusal |
| 8 | (P01) Tracker row: Stage badge, applied date, next action, latest note | ✓ VERIFIED | `_application_row.html` L13–21; `read_tracker` joins listing/company + event count; `test_read_tracker_joins_listing_and_company_and_counts_events` |
| 9 | (P02) No `ok` artefact → gated panel `data-state="no-ok-artifact"` + `/listings/{id}/cv` CTA; ready blocks absent entirely | ✓ VERIFIED | `apply_package_page` gate; `apply.html` L24–31; `test_gated_without_an_ok_artifact`, `test_a_blocked_artifact_is_gated_not_ready` |
| 10 | (P02) No stored ranking gaps → documented empty copy, not an empty list | ✓ VERIFIED | `apply.html` L66–68; `test_gap_checklist_empty_copy_when_no_gaps_stored` |
| 11 | (P02) Missing `apply_url` → documented fallback; verified PDF unreachable while `gated`; per-block degrade | ✓ VERIFIED | `apply.html` L42–44; `test_missing_apply_url_renders_the_fallback_text`; blocked/absent artefact both read `gated` |
| 12 | (P03) Grounded answer (ids resolve byte-exact, digits in corpus) passes clean | ✓ VERIFIED | `ground_screening_answers`; `test_a_grounded_answer_passes_clean` |
| 13 | (P03) Unknown evidence id flagged `unsupported`, naming the id, never silently dropped | ✓ VERIFIED | `app/verify/screening.py` L102–109; `test_an_unknown_evidence_id_is_flagged_and_named` |
| 14 | (P03) Novel digit core flagged, naming the token, via `numbers.digit_cores` | ✓ VERIFIED | L111–118; `test_a_fabricated_metric_digit_is_flagged_and_named`, `test_a_novel_digit_absent_only_from_the_listing_is_still_flagged` |
| 15 | (P03) Legitimate paraphrase reusing a known digit passes clean (false-positive direction tested) | ✓ VERIFIED | `test_a_legitimate_paraphrase_with_a_known_digit_passes_clean`; CONVENTIONS rule-4 mutation test `test_embedding_another_entitys_identifier_does_not_false_fail` (parametrized over all fact ids) |
| 16 | (P03) Exactly one `llm_calls` row per attempt; refusal at the ceiling BEFORE the call; no new numeric ceiling | ✓ VERIFIED | `draft.py` L146–207; `_reserve` runs before `complete_structured`; `test_a_successful_call_writes_one_row_with_a_null_run_id`, `test_a_cap_refusal_writes_one_budget_row_and_makes_no_call`, `test_a_raised_backend_error_writes_one_class_only_row_and_returns_none` |
| 17 | (P04) Filtered-to-nothing → `#application-empty-filtered` + `Clear filters`; zero → `#application-empty` | ✓ VERIFIED | `applications_list.html` L11–24; `test_filtered_to_nothing_renders_the_filtered_empty_state`, `test_needs_action_view_renders_the_nothing_needs_action_copy` |
| 18 | (P04) 300ms-debounced search/filter swap leaves previous rows in place; no spinner declared | ✓ VERIFIED | `applications.html` L14–60: `hx-trigger="input changed delay:300ms, search"`, `hx-swap="innerHTML"`, no `hx-indicator` on the filter controls |
| 19 | (P04) Failed fragment fetch reuses the transport convention; with JS off every control is a real form/anchor | ✓ VERIFIED | `applications_list.html` L53–72 real forms/pager; `test_filter_controls_emit_no_offset`, `test_filter_controls_reset_when_a_predicate_is_set`; `base.html` sendError/timeout handler |
| 20 | (P04) One row per application, ≤ page size, Stage badge anchor, note truncated with full string in `title=""` | ✓ VERIFIED | `_application_row.html` L18, L21; `Settings.queue_page_size` passed by `_list_context`; `test_read_tracker_paginates_two_way` |
| 21 | (P04) No `applied_at`/`next_action_at` → em-dash, not a fabricated date; empty note does not collapse the row | ✓ VERIFIED | `filters.format_datetime(None)` → `"—"` (L54–55); template renders `{{ ... \| format_datetime }}` |
| 22 | (P04) `.queue-table` ships `display:block; overflow-x:auto` | ✓ VERIFIED | `static/vendor/app.css` `.queue-table{...display:block;overflow-x:auto}` |
| 23 | (P04) `Applications` nav link + filter labels use shipped `.nav-link`/`.field`, wrap inside the header | ✓ VERIFIED | `base.html` L29; `applications.html` filter form reuses `.queue-sort`/`.queue-toggle` |
| 24 | (P04) Count copy switches on `n`; `History (1)` vs `(N)`; stage select always the fixed eight | ✓ VERIFIED | `applications_list.html` L26; `_application_history.html` L9; `applications.html` eight options from `statuses` |
| 25 | (P04) Listing/Company cell keeps `.listing-title`/`.listing-company` with no fixed width | ✓ VERIFIED | `_application_row.html` L13–15; CSS `.listing-title{white-space:normal;min-width:14rem;max-width:24rem}` (wrap-capable) |
| 26 | (P04 backstop) Titles/latest-note wrap; a held-out UI-state test asserts the history partial renders the complete untruncated note string | ⚠️ insufficient_spec | `verification: backstop`. The wrap/truncate markup and `title=""` are present and wired, but **no held-out/property-based test asserting the full untruncated note string exists** (searched `tests/`). Non-inferable — abstraction. See Human Verification #1 |
| 27 | (P05) No stored answer → `Not yet drafted.`; no questions → documented empty copy with add-question + Draft answers still present | ✓ VERIFIED | `_screening_drafts.html` L50–57; `test_answers_region_renders_the_defaults_not_yet_drafted`, `test_answers_region_renders_the_empty_copy_when_no_questions` |
| 28 | (P05) `Draft answers` uses `hx-indicator="#draft-progress"` + `hx-disabled-elt="find button"` + `role="status" aria-live="polite"` progress line | ✓ VERIFIED | `_screening_drafts.html` L75–85 |
| 29 | (P05) `Copy answer` flips its own label to `Copied` ~2s; a clipboard failure keeps `Copy answer` and selectable text | ✓ VERIFIED | `_screening_drafts.html` L34–37: `.then(() => {copied=true;...})` — a rejected `writeText` leaves `copied=false` |
| 30 | (P05) Refused drafting → `data-error` fragment into `#apply-answers`; transport failure reuses base.html copy | ✓ VERIFIED | `_answers_error()`; `base.html` `showRegionTransportError` covers `apply-answers`; `test_a_disabled_switch_refuses_before_any_call` |
| 31 | (P05) Each stored question renders one block with answer, evidence chips, `.answer-warning` when applicable; saved order | ✓ VERIFIED | `_screening_drafts.html` L22–54; `_answer_rows` merges in saved order; `test_a_stored_answer_block_renders_with_evidence_and_the_copy_control`, `test_the_unsupported_warning_renders_inside_the_block` |
| 32 | (P05) One question/one history event renders through the same per-block markup as many | ✓ VERIFIED | Single `{% for %}` loop; `History (n)` server-computed; no pluralised container label beyond the documented count |
| 33 | (P05 backstop) A long answer wraps with no truncation; a held-out UI-state test asserts copy fidelity across a multi-paragraph answer | ⚠️ insufficient_spec | `verification: backstop`. Answer renders in `<p class="answer-text">` (max-width 65ch, no truncation) and the handler reads `textContent`, but **no held-out test asserts multi-paragraph copy fidelity exists** (searched `tests/`). Non-inferable — browser-only. See Human Verification #2 |

**Score:** 31/33 truths verified (0 present, behavior-unverified; 2 abstained as `insufficient_spec` non-inferable backstops)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic/versions/0006_screening_drafts.py` | `screening_drafts` + `apply_config` + 2 `application_events` triggers | ✓ EXISTS + SUBSTANTIVE | 87 lines; raw `op.execute` triggers; symmetric downgrade; pinned head `0006` |
| `app/db/repositories/application_repo.py` | record/transition/update + ok-only applied gate + reads | ✓ EXISTS + SUBSTANTIVE | 595 lines; both writes in one `begin_nested()`; only writer of `Application`/`ApplicationEvent` (grep) |
| `app/api/applications.py` | 6 tracker routes | ✓ EXISTS + SUBSTANTIVE | 320 lines; `/applications/record` declared before dynamic POST routes |
| `app/api/apply.py` | package page + draft/question/delete actions | ✓ EXISTS + SUBSTANTIVE | 400 lines; `package_state` computed in route |
| `app/verify/screening.py` | deterministic grounding check | ✓ EXISTS + SUBSTANTIVE | 138 lines; residuals stated (CONVENTIONS rule 6 satisfied) |
| `app/pipeline/draft.py` | one audited drafting call on shared ceiling | ✓ EXISTS + SUBSTANTIVE | 224 lines; frozen system prompt; `_reserve` before call |
| `app/db/repositories/screening_draft_repo.py` | per-listing draft store | ✓ EXISTS + SUBSTANTIVE | 151 lines; atomic replace-all in one SAVEPOINT |
| `app/db/repositories/apply_config_repo.py` | question singleton store | ✓ EXISTS + SUBSTANTIVE | 86 lines; `DEFAULT_QUESTIONS` fallback for absent row |
| `app/domain/schemas/screening.py` | `extra="forbid"` contract | ✓ EXISTS + SUBSTANTIVE | 43 lines |
| `app/web/templates/html/apply.html` | gated + ready package shell | ✓ EXISTS + SUBSTANTIVE | 114 lines |
| `app/web/templates/html/_screening_drafts.html` | `#apply-answers` region | ✓ EXISTS + SUBSTANTIVE | 86 lines |
| `app/web/templates/html/applications*.html`, `_application_row/history.html` | tracker page + fragment + row + timeline | ✓ EXISTS + SUBSTANTIVE | shared fragment, no drift |
| `static/vendor/app.css` | stage badges, overdue, assurance, apply-link, answer tokens | ✓ EXISTS + SUBSTANTIVE | 8 `.badge-stage-*`, `.next-overdue`, `.apply-*`, `.answer-*`, `.queue-table` scroll |
| `tests/{verify,db,pipeline,api}/test_*` phase lanes | the phase's test evidence | ✓ EXISTS + SUBSTANTIVE | 180 phase-scoped tests pass |

**Artifacts:** 13/13 verified (no missing, no stubs)

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `applications.status` | exactly one `application_events` row | `application_repo.transition_application` in one `begin_nested()` | ✓ WIRED | L536–551; only writer (grep: no other `Application.status =`/`ApplicationEvent(` in `app/`) |
| migration 0006 trigger | schema-level append-only | `CREATE TRIGGER ... RAISE(ABORT,'application_events is append-only')` | ✓ WIRED | `test_screening_drafts_apply_config_and_application_events_append_only` asserts against migrated DDL |
| `cv_artifact_repo.read_for_download(ok_only=True)` | `applied` gate → `applications.cv_artifact_id` | SQL `compile_status == "ok"` | ✓ WIRED | blocked artefact refused, writes nothing; stored link read unfiltered (`test_tracker_read_keeps_the_stored_link...`) |
| `cv_artifact_repo.latest_for_listing(ok_only=True)` | `package_state` gate → verified-PDF block | SQL ok predicate | ✓ WIRED | blocked/failed/absent all render `gated`, indistinguishable |
| `score_repo.read_score_for_listing` | read-only gap checklist | `verdict in {gap,partial}` filter | ✓ WIRED | `met` deliberately excluded (D-123) |
| package `Record application` form | `POST /applications/record` → tracker | form action | ✓ WIRED | `test_record_from_the_package_links_the_ok_artifact` |
| `apply_config.questions_json` (or defaults) | `POST .../apply/draft` → `pipeline.draft` → grounding → `screening_draft_repo.replace_for_listing` → `#apply-answers` | one call, persisted rows | ✓ WIRED | `test_the_draft_action_makes_one_call_and_persists_rows` |
| `llm_call_repo.calls_since(purpose="tailor")` | `rank._reserve(...)` → shared rolling-24h ceiling | reserve-then-call | ✓ WIRED | refusal writes one `budget_exceeded` row before any call |
| filter/search controls | `hx-get="/applications/list"` → one shared fragment | `hx-include="closest form"` | ✓ WIRED | page and swap share `applications_list.html` |
| `view=needs_action` | `(next_action_at IS NULL), next_action_at ASC`, terminal excluded | SQL over bounded scan | ✓ WIRED | `test_needs_action_ordering` |

**Wiring:** 10/10 connections verified

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `applications_list.html` | `rows`, `count`, `page` | `application_repo.read_tracker` (SQL join + event count) | Yes | ✓ FLOWING |
| `_application_row.html` | `row.*`, `row.ok_artifacts` | `ApplicationRecord` + `_ok_artifacts_by_listing` (SQL ok filter) | Yes | ✓ FLOWING |
| `_application_history.html` | `events`, `count` | `read_history` (SQL) | Yes | ✓ FLOWING |
| `apply.html` (gaps) | `gaps` | `score_repo.read_score_for_listing(...).requirements` | Yes | ✓ FLOWING |
| `apply.html` (PDF/link) | `latest_artifact_id`, `apply_url` | `latest_for_listing` / `listing.apply_url` | Yes | ✓ FLOWING |
| `_screening_drafts.html` | `answer_rows` | `screening_draft_repo.read_for_listing` + `apply_config_repo.read_questions` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase-scoped suite (repo, events, draft store, config, grounding, draft stage, tracker, apply package, settings, seam, stylesheet, migration/ORM/PII/reset/boot guards) | `.venv/bin/python -m pytest -q <17 files>` | `180 passed in 56.86s` | ✓ PASS |
| Full default lane (confirms the claimed last-known result) | `.venv/bin/python -m pytest -q` | `1639 passed, 14 deselected, 2 xfailed in 333.72s` | ✓ PASS |
| Append-only trigger raises on UPDATE/DELETE | `test_the_database_aborts_an_update_and_a_delete_of_an_event` | `IntegrityError('application_events is append-only')` | ✓ PASS |
| No submit surface | `test_no_submit_surface` | all forms local, anchor carries `rel="noopener noreferrer"`, no portal route | ✓ PASS |
| Zero LLM calls on package GET | `test_package_states_and_no_llm_call_on_open` | counting backend recorded `[]` | ✓ PASS |
| One drafting call, one audit row, refusal before call | `test_the_draft_action_makes_one_call_and_persists_rows`, `test_a_cap_refusal_writes_one_budget_row_and_makes_no_call` | 1 call / 1 row; refusal → no call | ✓ PASS |

### Probe Execution

N/A — phase 07 declares no probes, is not a migration/tooling phase, and its success criteria do not mention probes. (No `scripts/*/tests/probe-*.sh` relevant to this phase.)

### Requirements Coverage

Every requirement ID from the phase's PLAN frontmatter accounted for; REQUIREMENTS.md maps all seven to Phase 7. No orphaned IDs (no REQUIREMENTS.md Phase-7 row absent from a plan).

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| APPLY-01 | 07-02, 07-03, 07-05 | Apply package: verified PDF, apply link, drafted answers, gap checklist | ✓ SATISFIED | `apply.py`, `apply.html`, `_screening_drafts.html`, `screening.py`, `draft.py`; package/page/draft tests |
| APPLY-02 | 07-02 | The tool never submits on the user's behalf | ✓ SATISFIED | `test_no_submit_surface`; no submit route; plain anchor |
| APPLY-03 | 07-01 | Record an application with a status stage and notes | ✓ SATISFIED | `record_application` + `/applications/record`; `test_record_writes_one_row_and_one_created_event` |
| APPLY-04 | 07-01 | Every recorded application links to the exact CV version sent | ✓ SATISFIED | ok-only applied gate (`read_for_download(ok_only=True)`); link survives later artefact status change; D-129 interpretation: the link is enforced at the `applied` transition |
| APPLY-05 | 07-01 | Status changes recorded as append-only events | ✓ SATISFIED | migration 0006 triggers; one-event-in-same-transaction; `test_application_events.py` |
| APPLY-06 | 07-01, 07-04 | Next action date/deadline | ✓ SATISFIED | `parse_next_action`, `next_action_at`, needs-action ordering; `test_needs_action_ordering` |
| UI-04 | 07-04, 07-05 | User can view and manage the application tracker | ✓ SATISFIED | tracker page, stage filter, search, needs-action view, two-way pager, transitions, notes, `#apply-answers` region |

**Coverage:** 7/7 requirements satisfied

### Test Quality Audit

| Test File | Linked Req | Active | Skipped | Circular | Assertion Level | Verdict |
|-----------|-----------|--------|---------|----------|-----------------|---------|
| `tests/db/test_application_repo.py` | APPLY-03/04/05/06 | 12 | 0 | no | Value + Behavioral | ✓ adequate |
| `tests/db/test_application_events.py` | APPLY-05 | 6 | 0 | no | Behavioral (trigger abort, counts) | ✓ adequate |
| `tests/db/test_screening_draft_repo.py` | APPLY-01 | 8 | 0 | no | Value + rollback | ✓ adequate |
| `tests/db/test_apply_config_repo.py` | APPLY-01 | 3 | 0 | no | Value | ✓ adequate |
| `tests/verify/test_screening.py` | D-125/APPLY-01 | 23 | 0 | no | Value + parametrized property | ✓ adequate |
| `tests/pipeline/test_draft_stage.py` | D-119 | 11 | 0 | no | Behavioral (call shape, audit rows) | ✓ adequate |
| `tests/api/test_applications_tracker.py` | UI-04/APPLY-03..06 | 19 | 0 | no | Behavioral (HTTP + DB state) | ✓ adequate |
| `tests/api/test_apply_package.py` | APPLY-01/02 | 21 | 0 | no | Behavioral (page states, no-submit, persistence) | ✓ adequate |

**Disabled tests on requirements:** 0 → no blocker.
**Circular patterns detected:** 0. The one `write_text` (`test_apply_package.py:472`) writes a committed stand-in CV fixture used as input, not an expected value derived from the SUT.
**Insufficient assertions:** 0 — every requirement has value- or behavioral-level assertions, not existence/type only.

### Decision Coverage

`check.decision-coverage-verify` reports 10/16 CONTEXT.md decisions matched by the substring heuristic; the six it lists as `not_honored` (D-120, D-126, D-128, D-132, D-133, D-134) are **all demonstrably implemented** in the code (verified by direct inspection):

- **D-120** — `GET /listings/{id}/apply` dedicated page + `listing_detail.html` link + `Depends(current_user)` on every route. ✓
- **D-126** — `screening_drafts` table created by migration 0006, one row per question per listing. ✓
- **D-128** — guided transitions over the eight frozen `ck_applications_status` values (`APPLICATION_STATUSES`). ✓
- **D-132** — tracker table at `/applications` reusing `.queue-table` + HTMX fragment. ✓
- **D-133** — stage filter, needs-action view, free-text search. ✓
- **D-134** — append-only history rendered as an expandable inline timeline per row. ✓

Non-blocking (the gate does not influence the status decision tree); recorded here to document that the `not_honored` list is a heuristic false positive, not drift.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No `TBD`/`FIXME`/`XXX`/`HACK`/`PLACEHOLDER` markers in any phase-modified file | — | Clean (debt-marker gate satisfied) |
| — | — | No `return null`/empty-handler/console-log-only stubs in phase files | — | Clean |

**Anti-patterns:** 0 found (0 blockers, 0 warnings)

**False-guarantee prose (CONVENTIONS rule 6):** `app/verify/screening.py` explicitly states its two residuals and makes **no** absolute guarantee — compliant. `app/pipeline/draft.py` frames grounding as "a value, not a gate" — accurate. `application_repo.py`'s "a crash between the two writes is impossible" is a reasonable claim under one caller-owned commit (no committed half-state can exist), though strictly a crash can occur between the flushes; the persisted invariant it describes holds. No false guarantee that suppresses scrutiny was found.

## Human Verification Required

### 1. Tracker note-fidelity (backstop truth, 07-04)
**Test:** Open `/applications`; inspect a row whose note is longer than the cell; read the DOM `title` attribute.
**Expected:** Note truncates to one line; the full untruncated string is in `title=""`.
**Why human:** `verification: backstop` (insufficient_spec) — no held-out/property-based test asserting the full note string was shipped, so presence+wiring cannot carry the truth.

### 2. Clipboard multi-paragraph copy fidelity (backstop truth, 07-05)
**Test:** On an apply package, copy a multi-paragraph answer and paste it into a scratch field.
**Expected:** The paste equals the full untruncated answer; the button flips to `Copied` for ~2s.
**Why human:** `verification: backstop` (insufficient_spec) — clipboard behaviour is browser-only and no held-out test exercises multi-paragraph fidelity.

### 3–8. Design / environment / product judgements
The remaining items (tracker visual scanning + no-JS degrade; ready-package perceived affordance; grounding residual policy adequacy; `#apply-answers` region reads as designed; real compiled PDF in the Tectonic container; 375px phone-width usability) are recorded in the frontmatter `human_verification` list with test/expected/why-human. They are legitimate visual, product-judgement and container-only checks that no server-side assertion covers.

## Gaps Summary

**No gaps found.** All 7 requirement IDs are satisfied, all artefacts exist and are substantive and wired, all key links are connected, data flows from real queries, and no blocker anti-patterns or debt markers exist. The phase-scoped suite (180 tests) and the full default lane (`1639 passed, 14 deselected, 2 xfailed`) are green, confirming the SUMMARYs' claimed result.

Three advisory observations, **none of which block**:

1. **Advisory (documentation lag):** `07-VALIDATION.md` remains `status: draft` / `nyquist_compliant: false` with its Wave-0 checkboxes unticked, even though every Wave-0 test file it names exists and passes. Bookkeeping only — no deliverable is missing.
2. **Advisory (design interpretation):** APPLY-04's "every application links to the exact CV sent" is enforced at the `applied` transition (D-129); an application recorded at `discovered`/`queued`/`shortlisted` carries no link, which is correct because no CV has been sent yet. The roadmap's SC3 wording is satisfied for any application that has been applied to.
3. **Advisory (honesty residual):** the grounding check is deliberately a warning policy, not a guarantee — a fabricated narrative with no novel digit passes, and a computed number absent verbatim from the sources is conservatively flagged. Both are stated in the module docstring and the module makes no false guarantee.

Because genuine human-verification items remain (two non-inferable backstop abstentions plus visual/container judgements), the status is `human_needed`, not `passed`.

## Verification Metadata

**Verification approach:** Goal-backward (ROADMAP success criteria + PLAN frontmatter `must_haves` + CONTEXT decisions), verified against the live codebase and by running the tests.
**Must-haves source:** `07-01..05-PLAN.md` frontmatter (complemented by ROADMAP §Phase 7 success criteria).
**Automated checks:** 180 phase-scoped passed / 0 failed; full lane 1639 passed / 0 failed / 2 xfailed.
**Human checks required:** 8 (2 abstained non-inferable backstops + 6 visual/container/product judgements).
**Total verification time:** ~20 min.

---

*Verified: 2026-09-30T18:38:55Z*
*Verifier: the agent (gsd-verifier)*
