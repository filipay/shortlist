---
phase: 07-assisted-apply-tracker
verified: 2026-10-06T19:34:39Z
status: gaps_found
score: 44/47 must-haves verified
covered_files:
  - .planning/phases/07-assisted-apply-tracker/07-01-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-02-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-03-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-04-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-05-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-06-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-07-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-08-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-09-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-01-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-02-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-03-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-04-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-05-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-06-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-07-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-08-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-09-SUMMARY.md
  - .planning/REQUIREMENTS.md
  - alembic/versions/0006_screening_drafts.py
  - alembic/versions/0007_screening_draft_warnings.py
  - app/api/applications.py
  - app/api/apply.py
  - app/api/settings.py
  - app/api/tailoring.py
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
  - app/web/templates/html/tailoring.html
  - static/vendor/app.css
  - tests/api/test_applications_tracker.py
  - tests/api/test_apply_draft_errors.py
  - tests/api/test_apply_package.py
  - tests/api/test_apply_package_warnings.py
  - tests/api/test_cv_pdf_route.py
  - tests/api/test_settings_page.py
  - tests/api/test_settings_reset.py
  - tests/api/test_tailoring_generate.py
  - tests/api/test_tailoring_review.py
  - tests/db/test_application_events.py
  - tests/db/test_application_repo.py
  - tests/db/test_apply_config_repo.py
  - tests/db/test_migration_contract.py
  - tests/db/test_no_pii_columns.py
  - tests/db/test_screening_draft_repo.py
  - tests/db/test_skeleton_boot.py
  - tests/domain/test_screening_schema.py
  - tests/llm/test_salvage.py
  - tests/pipeline/test_draft_stage.py
  - tests/test_auth_seam.py
  - tests/test_config.py
  - tests/verify/test_screening.py
covered_digest: "v1:sha256:eb571fcea48b5014a2a8668d449e190f6731ee0818ab5e53eb9652bdf566a4cf"
behavior_unverified: 2
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 31/33
  gaps_closed:
    - "G-07-1: record-submit now 303-redirects to the full styled tracker page (PRG) instead of replacing the document with a bare fragment"
    - "G-07-2: the recorded non-list screening payload shape is coerced at the schema boundary and an unusable response is reported distinctly from a valid-but-empty one"
    - "G-07-3: the checker's specific warnings (naming the offender) and the advisory band now persist (migration 0007) and render in the answers region"
    - "G-07-4: each CV download affordance serves the artifact it labels (per-row artifact_id with listing-ownership check; the compile banner no longer duplicates the Latest CV control)"
  gaps_remaining: []
  regressions: []
gaps:
  - truth: "An apply-package drafting call that returns fewer answers than were asked does not delete the user's unanswered stored drafts (including user-authored ad-hoc questions); the route's own 'Your existing drafts were kept' promise holds on every non-full-success path."
    status: failed
    reason: |
      The draft route distinguishes only "no verdicts" from "some verdicts":
      `if verdicts is None:` (drafting_failed) then `if not verdicts:` (drafting_empty),
      otherwise it calls `screening_draft_repo.replace_for_listing(...)`, which DELETES
      every `screening_drafts` row for the listing before inserting the verdicts.
      `ground_screening_answers` aligns answers positionally with
      `zip(questions, response.answers, strict=False)` and emits NO verdict for an
      unanswered question (app/verify/screening.py:108). A valid-but-PARTIAL model
      response (e.g. 1 answer for 7 asked questions) therefore passes both guards and
      the wholesale replace silently drops every row the model did not answer —
      including ad-hoc questions the user typed (the only record of that question text).
      The user sees `Not yet drafted.`, not a warning. This is the same data-loss class
      the G-07-2 gap closure addressed ("Your existing drafts were kept") but on a
      different path (partial success rather than refusal).
    artifacts:
      - path: "app/api/apply.py"
        issue: "Lines 332-361: only `None` and `[]` are refused; any non-empty partial list proceeds to `replace_for_listing`, which deletes unanswered rows. No `len(verdicts) < len(questions)` guard exists."
      - path: "app/db/repositories/screening_draft_repo.py"
        issue: "`replace_for_listing` (L109-112) unconditionally deletes the listing's whole draft set before inserting; the delete helpers also lack the SAVEPOINT the docstring promises (IN-01)."
      - path: "tests/api/test_apply_package.py"
        issue: "`test_the_draft_action_makes_one_call_and_persists_rows` (L540-542) enshrines the shallow case: a one-answer response persists exactly one row, with no assertion that seeded/unanswered rows survive."
    missing:
      - "Treat `len(verdicts) < len(questions)` as its own refused outcome (e.g. `data-error=\"drafting_partial\"`, existing drafts kept) OR implement an upsert-by-question write path that rewrites only the rows present in the verdicts and leaves every other row untouched."
      - "A regression test that seeds ad-hoc/unanswered rows, returns a partial model response, and asserts the unanswered rows (and their `question_text`) survive the POST — the test the review's reproduction used."
human_verification:
  - test: "Tracker note-fidelity (backstop truth, 07-04): open `/applications` and inspect a row whose note is longer than the cell; read the DOM `title` attribute."
    expected: "The note truncates to one line with an ellipsis and the complete untruncated string is present in `title=\"\"`."
    why_human: "`verification: backstop` (non-inferable). `title=\"{{ row.notes or '' }}\"` is present and wired (app/web/templates/html/_application_row.html:21) but no held-out/property-based test asserting the full string survives truncation was shipped. UAT test 1 never reached the styled cell (it was blocked by G-07-1, now fixed), so this remains unobserved."
  - test: "Clipboard multi-paragraph copy fidelity (backstop truth, 07-05): open an apply package, draft or seed a multi-paragraph answer, click `Copy answer`, and paste into a scratch field."
    expected: "The paste equals the full untruncated multi-paragraph answer; the button label flips to `Copied` for ~2s (and stays `Copy answer` if the clipboard API is unavailable)."
    why_human: "`verification: backstop` (non-inferable). `navigator.clipboard.writeText(...textContent)` reads the adjacent `.answer-text` (app/web/templates/html/_screening_drafts.html:48), but clipboard behaviour and multi-paragraph fidelity are browser-only and no held-out test exercises them. UAT test 2 never reached this (it was blocked by G-07-2, now fixed)."
behavior_unverified_items:
  - truth: "A truncated tracker note exposes the complete untruncated string via `title=\"\"`."
    test: "Render a tracker row with a long note and inspect the DOM title attribute."
    expected: "The title attribute carries the full untruncated note string."
    why_human: "Non-inferable backstop; markup is present but no held-out UI-state test asserts fidelity, and truncation is only observable in a rendered DOM."
  - truth: "Copy answer reproduces the full untruncated multi-paragraph answer."
    test: "Copy a multi-paragraph drafted answer and paste into a plain-text target."
    expected: "Paragraph breaks survive; nothing is collapsed."
    why_human: "Non-inferable backstop; browser clipboard behaviour, no held-out test."
---

# Phase 07: Assisted Apply + Tracker — Re-Verification Report

**Phase Goal (ROADMAP.md, verbatim):** An apply package per listing plus an application tracker that links every outcome to the exact verified CV artefact that was sent.
**Verified:** 2026-10-06T19:34:39Z
**Status:** gaps_found
**Re-verification:** Yes — after the four gap-closure plans (07-06 … 07-09) executed against the prior `human_needed` verification.

**Roadmap Success Criteria (verbatim; `mode: mvp`, but the goal is not in User-Story form — see Note A):**

1. User can open an apply package for a listing containing the verified PDF, the apply link, drafted screening answers, and a gap checklist.
2. The tool never submits an application on the user's behalf.
3. User can record an application with a status stage, notes, and a next-action date/deadline, and every application links to the exact verified CV artefact that was sent.
4. Application status changes are recorded as an append-only event history the user can view and manage.

## Goal Achievement

### Observable Truths

**Original phase truths (07-01 … 07-05)** — carried forward from the prior verification; re-checked by the phase-scoped suite (264 tests) and by direct inspection of every file the gap-closure round touched.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | (SC1) Apply package: verified PDF, apply link, drafted screening answers, gap checklist | ✓ VERIFIED | `app/api/apply.py` + `apply.html` + `_screening_drafts.html`; `tests/api/test_apply_package.py` |
| 2 | (SC2) The tool never submits on the user's behalf | ✓ VERIFIED | plain anchor + local forms only; `test_no_submit_surface` (route-registry walk) |
| 3 | (SC3) Record application with stage/notes/next-action; link to the exact verified CV | ✓ VERIFIED | `application_repo.record_application`; ok-only `applied` gate; tracker tests |
| 4 | (SC4) Status changes recorded as append-only event history, viewable/managed | ✓ VERIFIED | migration 0006 triggers abort UPDATE/DELETE; `test_application_events.py` |
| 5 | (P01) Tracker row, badges, history count, refused transitions, empty states | ✓ VERIFIED | `_application_row.html`, `_application_history.html`, `read_tracker/read_history`; `test_applications_tracker.py` (19) |
| 6 | (P01) Refused status transition → 4xx `data-error` fragment in the row slot, writes nothing | ✓ VERIFIED | `_row_error()`; `test_applied_requires_ok_artifact` asserts `(1,1)` unchanged |
| 7 | (P02) No `ok` artefact → gated panel + `/listings/{id}/cv` CTA; ready blocks absent | ✓ VERIFIED | `apply_package_page` gate; `test_gated_without_an_ok_artifact` |
| 8 | (P02) No stored ranking gaps → documented empty copy | ✓ VERIFIED | `test_gap_checklist_empty_copy_when_no_gaps_stored` |
| 9 | (P02) Missing `apply_url` → fallback; PDF unreachable while gated; per-block degrade | ✓ VERIFIED | `http_url` gate; `test_missing_apply_url_renders_the_fallback_text` |
| 10 | (P03) Grounded answer passes clean; unknown id flagged naming the id; novel digit flagged naming the token; paraphrase false-positive direction tested | ✓ VERIFIED | `app/verify/screening.py`; `tests/verify/test_screening.py` (23, incl. parametrized mutation) |
| 11 | (P03) Exactly one `llm_calls` row per attempt; refusal at the ceiling BEFORE the call; no new ceiling | ✓ VERIFIED | `draft.py` `_reserve` before `complete_structured`; `test_draft_stage.py` |
| 12 | (P04) Filtered-to-nothing vs zero-application empty states; 300ms debounce; no-JS real forms; pagination; em-dash for absent dates; `.queue-table` scroll | ✓ VERIFIED | `applications.html`, `applications_list.html`, `static/vendor/app.css`; 07-04 tests |
| 13 | (P05) `Not yet drafted.` / no-questions empty copy; `Draft answers` indicator; `Copy answer` label flip; refused draft → `data-error`; per-question block with evidence + warning; saved order | ✓ VERIFIED | `_screening_drafts.html`; `test_apply_package.py` |
| 14 | (P05 backstop) Long answer wraps and copy reproduces the full untruncated string; a held-out UI-state test asserts multi-paragraph copy fidelity | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Non-inferable backstop. Markup + handler present, no held-out test. See Human Verification #2 |
| 15 | (P04 backstop) Titles/latest-note wrap; a held-out UI-state test asserts the complete untruncated note string in `title=\"\"` | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Non-inferable backstop. `title=""` present, no held-out test. See Human Verification #1 |

**Gap-closure truths (07-06 … 07-09)** — all re-verified at the full three levels plus the named tests.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 16 | (G-07-2) A recorded malformed payload (`answers` as one object, `evidence_ids` as a bare string) validates with every answer preserved; unknown keys and scalar `answers` still raise; `TOLERATED_SCHEMA_ERRORS` untouched | ✓ VERIFIED | `app/domain/schemas/screening.py:38-72`; `tests/domain/test_screening_schema.py`; `tests/llm/test_salvage.py` golden payload |
| 17 | (G-07-2) The route distinguishes an unusable response (`drafting_failed`) from a valid-but-empty one (`drafting_empty`); different reasons/copy; neither refusal deletes stored drafts | ✓ VERIFIED | `app/api/apply.py:332-344`; `tests/api/test_apply_draft_errors.py` (both directions, seeded draft survives) |
| 18 | (G-07-2) `DRAFT_SYSTEM_PROMPT` requires the answers/evidence collections as JSON arrays and stays interpolation-free | ✓ VERIFIED | `app/pipeline/draft.py:99-100`; `test_the_draft_system_prompt_is_a_frozen_constant_with_no_interpolation` |
| 19 | (G-07-3) A flagged answer's rendered warning names the specific offender (evidence id / novel number token) | ✓ VERIFIED | `_screening_drafts.html:38-40`; `tests/api/test_apply_package_warnings.py::test_a_flagged_answer_names_each_specific_offender` |
| 20 | (G-07-3) A non-default advisory band renders as explicitly advisory ("not a guarantee"); `grounded`/NULL render nothing | ✓ VERIFIED | `_screening_drafts.html:42-44`; same test + `test_a_grounded_answer_renders_neither_warning_nor_band` |
| 21 | (G-07-3) Migration 0007 adds nullable `warnings_json`/`band`; repo round-trips and degrades NULL to `[]`/`None`; a NULL-specifics unsupported row still renders the generic caution | ✓ VERIFIED | `alembic/versions/0007_screening_draft_warnings.py`; `test_migration_contract.py` item 18; `test_screening_draft_repo.py`; `test_a_null_specifics_flagged_row_still_renders_the_generic_caution` |
| 22 | (G-07-1) A successful plain-form record submit returns 303 to `/applications` | ✓ VERIFIED | `app/api/applications.py:205`; `test_record_route_is_not_shadowed_by_the_dynamic_route`, `test_record_from_the_package_links_the_ok_artifact` |
| 23 | (G-07-1) Refusal paths unchanged: `data-error` fragments, no writes, status codes unchanged | ✓ VERIFIED | `test_record_refuses_an_applied_stage_without_an_ok_artifact` (409, counts unchanged) |
| 24 | (G-07-1) The landing page is a full base-layout document carrying `/static/vendor/app.css` and the new row | ✓ VERIFIED | `test_record_submit_lands_on_the_full_styled_tracker_page` |
| 25 | (G-07-4) A `?artifact_id=` request serves that row's own PDF, not the latest | ✓ VERIFIED | `app/api/tailoring.py:673-676`; `test_a_named_artifact_serves_its_own_file_not_the_latest` |
| 26 | (G-07-4) A foreign-listing, blocked, unknown or missing artifact id is a 404; no-parameter requests still serve the latest `ok` PDF | ✓ VERIFIED | `test_an_artifact_belonging_to_another_listing_is_a_404`, `test_a_named_blocked_artifact_is_a_404`, `test_an_unknown_artifact_id_is_a_404` |
| 27 | (G-07-4) Each `Previous compiles` row links to its own artifact id; the persistent Latest CV control stays parameterless | ✓ VERIFIED | `tailoring.html:93` vs `:72` |
| 28 | (G-07-4) After a compile the page offers exactly one latest download control; the banner emits no anchor | ✓ VERIFIED | `_compiled_fragment` (no anchor); `test_a_compile_yields_exactly_one_latest_download_control`, `test_compiled_fragment_with_no_drops_is_the_compile_marker_only` |
| 29 | **CR-01 (derived data-integrity truth): a partial drafting response does not delete the user's unanswered stored drafts** | ✗ **FAILED** | Reproduced: 3 seeded ad-hoc rows → 1 row remained after a one-answer POST. See gap + Reproduced Evidence |

**Score:** 44/47 truths verified (2 present, behavior-unverified; 1 failed)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic/versions/0006_screening_drafts.py` | drafts + config + append-only triggers | ✓ VERIFIED | 87 lines; raw `op.execute` triggers; symmetric downgrade |
| `alembic/versions/0007_screening_draft_warnings.py` | nullable `warnings_json` + `band` | ✓ VERIFIED | `op.add_column` ×2; symmetric downgrade; head pins moved 0006→0007 |
| `app/api/applications.py` | 6 tracker routes; record success = 303 PRG | ✓ VERIFIED | 325 lines; `RedirectResponse(url="/applications", status_code=303)` at L205 |
| `app/api/apply.py` | package page + draft/question/delete actions | ⚠️ PRESENT/WIRED but data-loss path | All actions present; the draft action's partial-response path deletes stored rows (CR-01) |
| `app/domain/schemas/screening.py` | `extra="forbid"` contract + recorded-shape coercion | ✓ VERIFIED | Coercion only for `None`/mapping/`str`/list/tuple; scalar still raises |
| `app/db/repositories/screening_draft_repo.py` | draft store, warnings/band round-trip | ⚠️ VERIFIED (with IN-01) | Round-trips correctly; `replace_for_listing` is delete-then-insert (CR-01); deletes lack the docstring's SAVEPOINT |
| `app/api/tailoring.py` | optional listing-scoped `artifact_id`; single latest control | ✓ VERIFIED | `read_for_download(ok_only=True)` + `record.listing_id == listing_id`; banner anchor removed |
| `app/verify/screening.py` | deterministic grounding check | ✓ VERIFIED | 148 lines; warnings + advisory band; residuals stated (no false guarantee) |
| `app/pipeline/draft.py` | one audited drafting call on the shared ceiling | ✓ VERIFIED | `_reserve` before call; frozen prompt now requests arrays |
| `app/db/repositories/application_repo.py`, `apply_config_repo.py` | record/transition/read; question singleton | ✓ VERIFIED | unchanged by the gap round |
| `app/web/templates/html/apply.html`, `_screening_drafts.html`, `applications*.html`, `_application_row/history.html`, `tailoring.html` | package + tracker + answers + download surfaces | ✓ VERIFIED | warning/band lines render; per-row artifact links |
| `static/vendor/app.css` | stage badges, `.queue-table` scroll, answer tokens | ✓ VERIFIED | unchanged by the gap round |
| phase test lanes | evidence | ✓ VERIFIED | 264 phase-scoped tests pass; full default lane 1674 passed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `applications.status` | exactly one `application_events` row | one `begin_nested()` | ✓ WIRED | only writer (grep); `test_application_events.py` |
| migration 0006 trigger | schema-level append-only | `RAISE(ABORT,'application_events is append-only')` | ✓ WIRED | asserted against migrated DDL |
| `read_for_download(ok_only=True)` | `applied` gate → `cv_artifact_id` | SQL `compile_status == "ok"` | ✓ WIRED | blocked refused, writes nothing |
| `read_for_download(ok_only=True, artifact_id)` | `/cv/pdf?artifact_id=` | listing-ownership re-check | ✓ WIRED | foreign/blocked/unknown all 404 |
| `latest_for_listing(ok_only=True)` | `package_state` gate → verified-PDF block | SQL ok predicate | ✓ WIRED | blocked/failed/absent all `gated` |
| `score_repo.read_score_for_listing` | read-only gap checklist | `verdict in {gap,partial}` | ✓ WIRED | `met` deliberately excluded (D-123) |
| record form (plain POST) | 303 → `GET /applications` | Post/Redirect/Get | ✓ WIRED | full styled document landing |
| `apply_config.questions_json` (or defaults) | `POST .../apply/draft` → draft stage → grounding → `replace_for_listing` → `#apply-answers` | one call, persisted rows | ✓ WIRED | `test_the_draft_action_makes_one_call_and_persists_rows` |
| `ScreeningVerdict.warnings`/`.band` | `screening_drafts.warnings_json`/`.band` → `_one_row` → rendered lines | migration 0007 | ✓ WIRED | persisted, never re-derived |
| filter/search controls | `hx-get="/applications/list"` → shared fragment | `hx-include="closest form"` | ✓ WIRED | page and swap share one template |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `applications_list.html` | `rows`, `count`, `page` | `application_repo.read_tracker` (SQL join + event count) | Yes | ✓ FLOWING |
| `_application_row.html` | `row.*`, `row.notes` | `ApplicationRecord` + SQL ok filter | Yes | ✓ FLOWING |
| `_application_history.html` | `events`, `count` | `read_history` (SQL) | Yes | ✓ FLOWING |
| `apply.html` (gaps) | `gaps` | `score_repo.read_score_for_listing` | Yes | ✓ FLOWING |
| `apply.html` (PDF/link) | `latest_artifact_id`, `apply_url` | `latest_for_listing` / `listing.apply_url` | Yes | ✓ FLOWING |
| `_screening_drafts.html` | `answer_rows` (answer/evidence/warnings/band) | `screening_draft_repo.read_for_listing` + `apply_config_repo.read_questions` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase-scoped suite (all 4 gap closures + original lanes) | `.venv/bin/python -m pytest -q <27 files>` | `264 passed in 92.81s` | ✓ PASS |
| Full default lane | `.venv/bin/python -m pytest -q` | `1674 passed, 14 deselected, 2 xfailed in 330.71s` | ✓ PASS |
| Record submit redirects to a styled page | `test_record_submit_lands_on_the_full_styled_tracker_page` | full doc + `/static/vendor/app.css` + new row | ✓ PASS |
| Named artifact serves its own bytes / foreign+blocked ids 404 | `tests/api/test_cv_pdf_route.py` | 4 cases pass | ✓ PASS |
| Specific warning names the offender + advisory band renders | `tests/api/test_apply_package_warnings.py` | pass | ✓ PASS |
| Two distinct refusal reasons; stored draft survives both | `tests/api/test_apply_draft_errors.py` | pass | ✓ PASS |
| **CR-01 reproduction** (temporary probe, since removed) | partial 1-answer response against 3 seeded ad-hoc rows | **`1 failed`** — only `['Why are you interested in this role?']` remained; all 3 ad-hoc rows deleted | ✗ **FAIL** |

### Probe Execution

N/A — phase 07 declares no probes and is not a migration/tooling phase. No `scripts/*/tests/probe-*.sh` apply.

### Requirements Coverage

All 7 phase requirement IDs are declared in PLAN frontmatter and mapped to Phase 7 in REQUIREMENTS.md. No orphaned IDs.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| APPLY-01 | 07-02, 07-03, 07-05, 07-06, 07-07, 07-09 | Apply package: verified PDF, apply link, drafted answers, gap checklist | ⚠️ PARTIAL | Package/page/grounding/coercion/warnings/download all verified, but the drafting write path can silently delete unanswered stored drafts (CR-01) — a gap in the package's answer-persistence integrity |
| APPLY-02 | 07-02 | The tool never submits on the user's behalf | ✓ SATISFIED | `test_no_submit_surface`; no submit route; plain anchor |
| APPLY-03 | 07-01, 07-08 | Record an application with a status stage and notes | ✓ SATISFIED | record route now 303s to the styled tracker; refusal unchanged |
| APPLY-04 | 07-01 | Every recorded application links to the exact CV version sent | ✓ SATISFIED | ok-only `applied` gate; link survives later status change |
| APPLY-05 | 07-01 | Status changes recorded as append-only events | ✓ SATISFIED | migration 0006 triggers; same-transaction event |
| APPLY-06 | 07-01, 07-04, 07-08 | Next action date/deadline | ✓ SATISFIED | `parse_next_action`, needs-action ordering |
| UI-04 | 07-04, 07-05, 07-08 | User can view and manage the application tracker | ✓ SATISFIED | tracker page/filters/search/needs-action/pager/transitions/notes/answers region |

**Coverage:** 6/7 satisfied; APPLY-01 partial due to CR-01.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No `TBD`/`FIXME`/`XXX`/`HACK`/`PLACEHOLDER` markers in any phase-modified file | — | Clean (debt-marker gate satisfied) |
| `app/api/apply.py` | 339-346 | partial-response path falls through to a wholesale replace (silent data loss) | 🛑 BLOCKER | CR-01 |
| `app/api/tailoring.py` | 377 | `record.verification_json or {}` assumes a mapping (WR-02; pre-existing, not introduced by 07-09) | ⚠️ WARNING | A non-dict JSON row 500s a findings fragment; sibling `_parse_findings` already guards |
| `app/web/templates/html/_screening_drafts.html` | 54-59 | delete form has no `hx-post`; a full-page submit lands on the bare region fragment (WR-01; same class as G-07-1) | ⚠️ WARNING | No-JS/JS-on stranding on the delete action; UAT test 6 accepted this leg |
| `app/db/repositories/screening_draft_repo.py` | 8-9, 163-184 | docstring claims every write uses a SAVEPOINT; the two deletes do not (IN-01) | ℹ️ INFO | Prose overclaim (CONVENTIONS rule 6) |
| `app/web/templates/html/_screening_drafts.html` | 48 | clipboard handler dereferences `navigator.clipboard` unguarded (IN-04) | ℹ️ INFO | Throws on non-secure context; user-visible outcome matches the comment (label stays) |

### Advisory (New Scope, Unevidenced)

The advisory code review (`07-REVIEW.md`, 2026-10-06) raised 1 Critical + 2 Warnings + 4 Info. The Critical (CR-01) was **independently reproduced** by this verifier and is therefore promoted from advisory to a blocking gap above. The remainder are recorded as warnings/info, not phase must-haves:

| # | Finding | Category | Why Not a Gap |
|---|---------|----------|----------------|
| 1 | WR-01: apply-region forms return a bare fragment on a full-page submit | ux/correctness | The `POST .../draft/delete` fragment response is by design (`delete_answer` docstring); UAT test 6 accepted the leg. Not covered by a must-have truth. |
| 2 | WR-02: `_findings_fragment` can 500 on a non-dict `verification_json` | robustness | Pre-existing tailoring code, not introduced by 07-09's change; no phase must-have asserts it. |
| 3 | IN-01…IN-04 | hygiene | Documentation/comments, duplicate-question edge, unguarded clipboard property. |

## Human Verification Required

### 1. Tracker note-fidelity
**Test:** Open `/applications` and inspect a row whose note is longer than the cell; read the DOM `title` attribute.
**Expected:** Note truncates to one line; the full untruncated string is present in `title=""`.
**Why human:** Non-inferable backstop — no held-out test asserts fidelity, and UAT test 1 never reached the styled cell (blocked by G-07-1, now fixed).

### 2. Clipboard multi-paragraph copy fidelity
**Test:** On an apply package, copy a multi-paragraph answer and paste into a scratch field.
**Expected:** The paste equals the full untruncated answer; the label flips to `Copied` for ~2s.
**Why human:** Non-inferable backstop — browser-only behaviour, no held-out test. UAT test 2 never reached this (blocked by G-07-2, now fixed).

### 3. Note A — MVP mode / goal-format discrepancy (developer decision)
**Observation:** ROADMAP marks Phase 7 `mode: mvp`, but the phase goal ("An apply package per listing plus an application tracker that links every outcome to the exact verified CV artefact that was sent.") is **not** in User-Story form — `user-story.validate` returns `valid: false`. Under strict MVP-mode verification this would require `/gsd mvp-phase 7` before a User-Flow-Coverage report could be produced. This verifier proceeded with standard goal-backward verification (the roadmap Success Criteria are the contract, and the prior verification did the same). **Developer decision:** confirm the `mvp` annotation is intentional, or run `/gsd mvp-phase 7` to convert the goal.

## Gaps Summary

**One blocking gap: CR-01 — a partial drafting response silently deletes the user's unanswered stored drafts.**

The four UAT gaps are genuinely closed and their gap-closure truths verified:
- **G-07-1** — `POST /applications/record` now 303-redirects to the full styled tracker page (PRG); refusals unchanged.
- **G-07-2** — the recorded non-list payload shape is coerced at the schema boundary and an unusable response is reported distinctly (`drafting_failed`) from a valid-but-empty one (`drafting_empty`); both refusals keep stored drafts.
- **G-07-3** — migration 0007 persists the checker's warnings + advisory band; the answers region names the specific offender and marks the band advisory-only.
- **G-07-4** — `?artifact_id=` serves a named, listing-owned, `ok` artifact; the compile banner no longer duplicates the Latest CV control.

**But the G-07-2 data-loss class survives on the partial-response path.** `ground_screening_answers` emits no verdict for an unanswered question, and `draft_answers` refuses only `None` and `[]` before calling `replace_for_listing`, which deletes the listing's entire draft set. A valid response covering a subset of questions therefore deletes every unanswered row — including ad-hoc questions whose text exists nowhere else. The user sees `Not yet drafted.` rather than a warning, and the route's own copy ("Your existing drafts were kept") is false on this path. Reproduced deterministically (temporary probe: 3 seeded ad-hoc rows → 1 row remained after a one-answer POST; probe since removed).

This is a must-have failure for the phase's drafting feature: APPLY-01's "drafted screening answers" cannot be called trustworthy while a realistic model response destroys stored user input. Fail-closed: status `gaps_found`.

The two non-inferable backstop truths (note fidelity, clipboard fidelity) remain `PRESENT_BEHAVIOR_UNVERIFIED` and are preserved in `behavior_unverified_items` so they survive this `gaps_found` verdict; they would route to `human_needed` once the gap is closed.

---

_Verified: 2026-10-06T19:34:39Z_
_Verifier: the agent (gsd-verifier)_
