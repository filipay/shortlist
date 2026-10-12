---
phase: 07-assisted-apply-tracker
verified: 2026-10-12T12:15:00Z
status: gaps_found
score: 11/14 must-haves verified
covered_files:
  - .planning/REQUIREMENTS.md
  - .planning/phases/07-assisted-apply-tracker/07-01-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-01-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-02-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-02-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-03-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-03-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-04-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-04-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-05-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-05-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-06-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-06-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-07-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-07-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-08-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-08-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-09-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-09-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-10-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-10-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-11-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-11-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-12-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-12-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-REVIEW.md
  - .planning/phases/07-assisted-apply-tracker/07-UAT.md
  - .planning/phases/07-assisted-apply-tracker/07-UI-SPEC.md
  - .planning/phases/07-assisted-apply-tracker/deferred-items.md
  - Dockerfile
  - app/domain/cv.py
  - app/domain/schemas/_coerce.py
  - app/domain/schemas/ranking.py
  - app/domain/schemas/screening.py
  - app/web/templates/html/_application_row.html
  - assets/tailwind/input.css
  - static/vendor/app.css
  - tests/api/test_applications_tracker.py
  - tests/api/test_apply_draft_errors.py
  - tests/domain/test_coerce.py
  - tests/domain/test_screening_schema.py
  - tests/llm/test_salvage.py
covered_digest: "v1:sha256:bbc0c2a5bd2ccdfb1e20c1f958d730bf3241adc26900bfe75716dfd73b923756"
behavior_unverified: 2
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 45/47
  gaps_closed:
    - "G-07-5: the tracker note cell no longer carries `.truncate`; it is `class=\"tracker-note\"` with `white-space:normal; overflow-wrap:anywhere; max-width:24rem` and the full string kept in `title=\"\"`."
    - "G-07-6: the tracker Actions cell is phase-scoped `tracker-actions` / `tracker-action` with `white-space:normal` and `display:block` forms, so the `Update status` button and the `Next action` date input cannot share a line box (declaration contract asserted in `tests/api/test_applications_tracker.py`)."
    - "G-07-7: the model's single-key array wrapper `{\"item\": ...}` is unwrapped on every list-typed wire field via `app/domain/schemas/_coerce.py`; the literal captured payload now salvages to 4 answers (17/1/0/3 evidence ids) and the `/apply/draft` route persists 4 rows instead of 502 `drafting_failed`."
  gaps_remaining: []
  regressions:
    - "CR-01 (new, blocker): the committed `static/vendor/app.css` is not reproducible from `assets/tailwind/input.css`; a fresh Tailwind build — exactly what the Dockerfile's asset stage produces and ships — drops 30 template classes, including the phase-7 `.answer-text`/`.answer-warning`/`.apply-link`/`.apply-assurance`/`.next-overdue`/`.requirement-list` rules and all eight `.badge-stage-*` tracker badge colours."
gaps:
  - truth: "The phase's UI deliverables (apply package, tracker) are actually delivered by the supported deployment (Docker): the stylesheet the image ships must carry the component rules the phase templates use."
    status: failed
    reason: "`static/vendor/app.css` (committed) diverges from its Tailwind source `assets/tailwind/input.css`. Running the Dockerfile's exact build command produces a different, smaller file that is MISSING 30 classes the templates reference. The Dockerfile ships the rebuilt file (`COPY --from=assets /app/static/vendor ./static/vendor`, line 116) and compose mounts only `./data`/`./cv`/`./artifacts`, never the repo tree, so the deployed image loses the phase-7 styling. The repo's own `tests/test_stylesheet_coverage.py` cannot see this because it reads the committed artifact; it would FAIL in the image."
    artifacts:
      - path: "assets/tailwind/input.css"
        issue: "Source of truth is missing every phase 6/7 component rule (`.badge-stage-*`, `.badge-score*`, `.apply-*`, `.answer-*`, `.next-overdue`, `.requirement-list`, `.req-*`, `.listing-detail-link`, `.cv-*`, `.weights-*`, `.factor-table*`, …); last content change was phase 5."
      - path: "static/vendor/app.css"
        issue: "The committed build carries those rules only because they were hand-appended; a real rebuild (Dockerfile assets stage, line 19) drops them."
      - path: "Dockerfile"
        issue: "Line 116 ships the rebuilt stylesheet; compose does not mount the repo, so the deployed UI is unstyled."
    missing:
      - "Move every component class the templates depend on from the hand-appended block of `static/vendor/app.css` into the `@layer components` blocks of `assets/tailwind/input.css`."
      - "Then regenerate `static/vendor/app.css` with the pinned CLI (`./node_modules/.bin/tailwindcss -i ./assets/tailwind/input.css -o ./static/vendor/app.css --minify`) and commit the result — do NOT rebuild before backfilling, or the 30 rules are deleted."
      - "Add a guard that runs the CLI over `input.css` and asserts the committed `app.css` is identical (or extend `tests/test_stylesheet_coverage.py` to fail when a template class is absent from a *freshly built* file), so the divergence cannot recur. Note `.badge-stage-{{ row.status }}` is dynamic and invisible to the current coverage scan, so add an explicit rule for the eight stage classes."
behavior_unverified_items:
  - truth: "G-07-6: the tracker `Update status` button rect does not intersect the `Next action` date-input rect at 1280px and 375px (the mandated rendered-rect check)."
    test: "Load `/applications` with a row that has both a status and a Next-action date, and run the plan's `getBoundingClientRect()` snippet per row at 1280px and 375px, JS on and the `Move to` select untouched."
    expected: "`intersects: false` for every row; no `dd/mm/yyyy` glyph band over the button; no horizontal scrollbar for a long note."
    why_human: "No layout engine ships in the repo (dev deps are pytest/pytest-asyncio/ruff). The declaration contract is asserted and green, but the measured rect verdict is unrun — 07-11-SUMMARY records no rect pairs and `WINDOWS.md` #9 is an open `unrun-verify`."
  - truth: "Backstop: `Copy answer` reproduces the full untruncated multi-paragraph drafted answer (clipboard fidelity)."
    test: "Draft or seed a multi-paragraph answer, click `Copy answer`, paste into a scratch field."
    expected: "The paste equals the full untruncated answer; the label flips to `Copied` for ~2s."
    why_human: "Non-inferable backstop; browser clipboard behaviour, no held-out test exercises it. UAT test 2 never reached this (blocked by G-07-7, now fixed) and has not been re-run."
human_verification:
  - test: "Re-run UAT test 1 (tracker layout, G-07-5/G-07-6): record an application with a ~300-character note and a next-action date; open `/applications` at 1280px and 375px; confirm the note wraps (no horizontal scroll), the `Update status` button has no date field painted over it, and run the rect snippet above."
    expected: "Note wraps; `intersects: false` for every row at both widths; button legible and clickable."
    why_human: "Runtime layout; the automated lane only asserts the CSS declaration contract. Not re-run since the fix."
  - test: "Re-run UAT test 2 (drafting, G-07-7): click `Draft answers` on a package whose provider wraps a list-typed field as `{\"item\": ...}`; confirm four reviewable answers appear and `Copy answer` works end-to-end."
    expected: "Four answers render (not the 502 `drafting_failed` message); copy/paste reproduces the full answer."
    why_human: "Depends on the live provider's emission; the deterministic half is covered by tests but the live round-trip was not re-run."
  - test: "MVP-mode / goal-format discrepancy (developer decision)."
    expected: "Confirm the `mvp` annotation on Phase 7 is intentional; the goal is not in User-Story form (`user-story.validate` → `valid: false`). Standard goal-backward verification (as here) is sufficient, or run `/gsd mvp-phase 7` to convert the goal."
    why_human: "Developer decision, not a code defect. Recorded since the prior verification (UAT test 3 passed 2026-10-06)."
---

# Phase 07: Assisted Apply + Tracker — Re-Verification Report

**Phase Goal (ROADMAP.md, verbatim):** An apply package per listing plus an application tracker that links every outcome to the exact verified CV artefact that was sent.
**Verified:** 2026-10-12T12:15:00Z
**Status:** gaps_found
**Re-verification:** Yes — after gap-closure plans 07-11 (G-07-5/G-07-6) and 07-12 (G-07-7).

**Roadmap Success Criteria (verbatim; `mode: mvp`, but the goal is not in User-Story form — see Human Verification #3):**

1. User can open an apply package for a listing containing the verified PDF, the apply link, drafted screening answers, and a gap checklist.
2. The tool never submits an application on the user's behalf.
3. User can record an application with a status stage, notes, and a next-action date/deadline, and every application links to the exact verified CV artefact that was sent.
4. Application status changes are recorded as an append-only event history the user can view and manage.

## Goal Achievement

### Observable Truths

**Functional truths** — verified by the phase suite (85 + 172 tests green) and by direct inspection.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | (SC1) Apply package: verified PDF, apply link, drafted answers, gap checklist | ✓ VERIFIED | `app/api/apply.py` `apply_package_page` gate; `apply.html`; `_screening_drafts.html`; `tests/api/test_apply_package.py` |
| 2 | (SC2) The tool never submits on the user's behalf | ✓ VERIFIED | `apply.html` has one local form (`action="/applications/record"`) and a plain outbound `<a>`; no portal-submit route. `tests/api/test_apply_package.py::test_no_submit_surface` |
| 3 | (SC3) Record an application with stage/notes/next-action; link to the exact verified CV | ✓ VERIFIED | `applications.py:189-205` record → 303; `application_repo.record_application` ok-only gate (`cv_artifact_repo.read_for_download(ok_only=True)`); `applications.cv_artifact_id` is the historical link |
| 4 | (SC4) Status changes recorded as append-only event history, viewable/managed | ✓ VERIFIED | migration 0006 triggers `application_events_no_update/no_delete` `RAISE(ABORT,…)`; row update + one event in one `begin_nested()`; `read_history`; `tests/db/test_application_events.py` |
| 5 | (G-07-1) Record submit returns 303 to the full styled tracker page; refusal paths unchanged | ✓ VERIFIED | `applications.py:205` `RedirectResponse(url="/applications", status_code=303)`; `test_record_submit_lands_on_the_full_styled_tracker_page` |
| 6 | (G-07-2) Recorded malformed screening payloads coerce without dropping answers; other shapes still raise | ✓ VERIFIED | `screening.py` delegates to `_coerce`; `test_screening_schema.py`, `test_salvage.py` |
| 7 | (G-07-3) Flagged answers name the specific offender; advisory band renders as advisory; grounded/NULL render nothing | ✓ VERIFIED | `_screening_drafts.html`; migration 0007; `tests/api/test_apply_package_warnings.py` |
| 8 | (G-07-4) A `?artifact_id=` request serves that row's own PDF; foreign/blocked/unknown → 404; no-parameter serves latest ok | ✓ VERIFIED | `tailoring.py` `read_for_download(ok_only=True, artifact_id)` + ownership; `tests/api/test_cv_pdf_route.py` |
| 9 | (CR-01 prior) A valid-but-partial drafting response is refused (`drafting_partial`, 502) BEFORE `replace_for_listing`; stored rows survive | ✓ VERIFIED | `apply.py:356-364` guard textually precedes `replace_for_listing`; `test_a_partial_response_keeps_unanswered_ad_hoc_rows` etc. — 6 pass |
| 10 | (G-07-5) The tracker note cell wraps and keeps the full untruncated string in `title=""` | ✓ VERIFIED | `_application_row.html:21` `class="tracker-note" title="{{ row.notes or '' }}"`; `input.css` `.tracker-note{white-space:normal;overflow-wrap:anywhere;max-width:24rem}`; `test_a_long_note_wraps_and_keeps_its_full_string_in_the_title` |
| 11 | (G-07-6) The tracker Actions cell is scoped and its controls cannot share a line box (declaration contract) | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `tracker-actions`/`tracker-action` present; `test_the_tracker_action_cell_cannot_overlap_its_controls` asserts `white-space:normal`/`display:block`. The MANDATED rendered-rect measurement was NOT performed → see Human Verification |
| 12 | (G-07-7) A `{"item": ...}`-wrapped list-typed field yields usable drafted answers, not 502 `drafting_failed` | ✓ VERIFIED | `_coerce.unwrap_single_key_mapping`; `test_the_literal_captured_payload_salvages_to_four_answers`; `test_the_literal_wrapped_payload_persists_four_rows` |
| 13 | (SC1/UI-04 deploy) The stylesheet the Docker image ships carries the component rules the phase templates use | ✗ FAILED | Fresh Tailwind build (Dockerfile command) is missing 30 classes incl. `.answer-text`, `.answer-warning`, `.apply-link`, `.apply-assurance`, `.next-overdue`, `.requirement-list`, `.listing-detail-link` and all `.badge-stage-*`; Dockerfile line 116 ships it → **CR-01 blocker** |
| 14 | (Backstop) `Copy answer` reproduces the full untruncated multi-paragraph answer | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Handler + markup present; browser-only, no held-out test; UAT test 2 not re-run → see Human Verification |

**Score:** 11/14 truths verified (2 present, behavior-unverified; 1 failed)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/domain/schemas/_coerce.py` | shared pure unwrap helpers | ✓ VERIFIED | 68 lines, stdlib only; import-discipline test green |
| `app/domain/schemas/screening.py`, `ranking.py`, `app/domain/cv.py` | delegate list-typed fields to the helper | ✓ VERIFIED | validators present; `extra="forbid"` and `TOLERATED_SCHEMA_ERRORS` untouched |
| `app/web/templates/html/_application_row.html` | `tracker-note`/`tracker-actions`/`tracker-action`; wrap; full `title` | ✓ VERIFIED | classes swapped; no `.truncate` / `listing-*` in the row |
| `assets/tailwind/input.css` | `tracker-*` rules | ✓ VERIFIED | 3 rules beside `.listing-*` (which are byte-unchanged) |
| `static/vendor/app.css` | regenerated build carrying the rules | ✗ STUB (not reproducible) | The 3 `tracker-*` rules ARE present (hand-appended), but the file is not the build of `input.css`; a real rebuild drops 30 classes (CR-01) |
| `app/api/applications.py`, `apply.py` | tracker + package routes | ✓ VERIFIED | 6 tracker routes + package/draft/question/delete; 303 PRG; `drafting_partial` guard |
| `application_repo.py`, `screening_draft_repo.py`, `apply_config_repo.py` | record/transition/history/store | ✓ VERIFIED | ok-only gate; single-transaction event; warnings/band round-trip |
| `alembic/versions/0006/0007` | append-only triggers; nullable warnings | ✓ VERIFIED | raw `op.execute` triggers; symmetric downgrade |
| `tests/…` (coerce, salvage, draft-errors, tracker) | held-out fixture + regressions | ✓ VERIFIED | all green |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `input.css` (source) | `static/vendor/app.css` (deployed) | Tailwind CLI build | ✗ NOT_WIRED | The build drops 30 template classes; the committed file is only correct by hand-append (CR-01) |
| `applications.status` | exactly one `application_events` row | one `begin_nested()` | ✓ WIRED | only writer; `test_application_events.py` |
| migration 0006 trigger | schema-level append-only | `RAISE(ABORT,…)` | ✓ WIRED | asserted against migrated DDL |
| `read_for_download(ok_only=True)` | `applied` gate → `cv_artifact_id` | SQL `compile_status == "ok"` | ✓ WIRED | blocked refused, writes nothing |
| `_coerce_evidence_ids` | `_salvage` → route persistence | before-validator | ✓ WIRED | 4 rows persist for the literal payload |
| filter/search controls | `hx-get="/applications/list"` fragment | one shared template | ✓ WIRED | page and swap share `applications_list.html` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `applications_list.html` | `rows`, `count`, `page` | `application_repo.read_tracker` (SQL join + event count) | Yes | ✓ FLOWING |
| `_screening_drafts.html` | `answer_rows` | `screening_draft_repo.read_for_listing` + `apply_config_repo.read_questions` | Yes | ✓ FLOWING |
| `apply.html` (gaps/PDF/link) | `gaps`, `latest_artifact_id`, `apply_url` | `score_repo.read_score_for_listing` / `latest_for_listing` / `listing.apply_url` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase functional lane (coerce, screening, salvage, draft-errors, tracker, package, warnings) | `/tmp/opencode/gsdvenv13/bin/python -m pytest -q <7 files>` | `85 passed in 42.66s` | ✓ PASS |
| Phase-support lane (events, repos, migrations, CV route, settings, tailoring, grounding, draft stage, coverage, import discipline) | `/tmp/opencode/gsdvenv13/bin/python -m pytest -q <14 files>` | `172 passed in 42.81s` | ✓ PASS |
| Docker stylesheet build (exact Dockerfile command) | `./node_modules/.bin/tailwindcss -i ./assets/tailwind/input.css -o /tmp/opencode/built-app.css --minify` | built 34561 B vs committed 39308 B | ✓ PASS (build runs) |
| Template-class coverage of the FRESH build | `_stylesheet_has_class` over `/tmp/opencode/built-app.css` | **30 classes missing** (incl. phase-7 `.answer-text`, `.answer-warning`, `.apply-link`, `.apply-assurance`, `.next-overdue`, `.requirement-list`, `.listing-detail-link`) | ✗ FAIL |
| `.badge-stage-*` presence in the fresh build | `grep -c badge-stage /tmp/opencode/built-app.css` | `0` (committed file: 8) | ✗ FAIL |

### Probe Execution

N/A — phase 07 declares no probes and is not a migration/tooling phase. No `scripts/*/tests/probe-*.sh` apply.

### Requirements Coverage

All 7 phase requirement IDs are declared in PLAN frontmatter and mapped to Phase 7 in REQUIREMENTS.md. No orphaned IDs.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| APPLY-01 | 07-02,03,05,06,07,09,10,12 | Apply package: verified PDF, apply link, drafted answers, gap checklist | ✓ SATISFIED (functionally) | Package/page/grounding/coercion/warnings/download verified; drafting returns 4 rows for the wrapped payload. Styling degraded in Docker by CR-01 |
| APPLY-02 | 07-02 | The tool never submits on the user's behalf | ✓ SATISFIED | `test_no_submit_surface`; plain anchor + local record form only |
| APPLY-03 | 07-01, 07-08 | Record an application with a status stage and notes | ✓ SATISFIED | record route 303s to the tracker; refusal unchanged |
| APPLY-04 | 07-01 | Every recorded application links to the exact CV version sent | ✓ SATISFIED | ok-only `applied` gate; `cv_artifact_id` survives later status changes |
| APPLY-05 | 07-01 | Status changes recorded as append-only events | ✓ SATISFIED | migration 0006 triggers; same-transaction event |
| APPLY-06 | 07-01, 07-04, 07-08 | Next action date/deadline | ✓ SATISFIED | `parse_next_action`, needs-action ordering |
| UI-04 | 07-04, 07-05, 07-08, 07-11 | User can view and manage the application tracker | ✓ SATISFIED (functionally) | Tracker page/filters/search/needs-action/pager/transitions/notes/answers region; G-07-5/6 fixed. Styling degraded in Docker by CR-01 |

**Coverage:** 7/7 functionally satisfied; the deployed-UI caveat (CR-01) applies to APPLY-01/UI-04 presentation.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `assets/tailwind/input.css` / `static/vendor/app.css` / `Dockerfile` | — | Committed build not reproducible from source; docker ships an unstyled UI | 🛑 BLOCKER | CR-01 — 30 template classes absent from the deployed stylesheet |
| `app/domain/schemas/_coerce.py` | 1-8 | Docstring claims "an unknown key … fails loudly", but the unwrap is arity-only: `{"anything": ["bul/x/1"]}` unwraps and validates | ⚠️ WARNING | WR-01 — fail-open-ish in untrusted-input handling; the two apparent fail-loud tests pass a *scalar* value |
| `app/domain/cv.py` | — | `TailoringPatch.ops/gaps/suggestions` are list-typed on the same salvage path but not wrapped | ℹ️ INFO | IN-01 — residual exposure to the same provider class (out of the plan's stated scope) |
| `app/domain/schemas/_coerce.py` | 27-29 | `while` loop unbounded for a self-referential Mapping | ℹ️ INFO | IN-02 — unreachable from `json.loads`-derived wire payloads |
| — | — | No `TBD`/`FIXME`/`XXX`/`HACK`/`PLACEHOLDER` markers in any phase-modified file | — | Debt-marker gate satisfied |

### Advisory (New Scope, Unevidenced)

None. The CR-01 and WR-01 findings carry deterministic, reproducible evidence (a ran build; a ran validation), so neither is advisory.

## Human Verification Required

### 1. Tracker layout re-run (G-07-5 + G-07-6)
**Test:** Record an application with a ~300-character note and a next-action date; open `/applications` at 1280px and 375px; run the rect snippet from 07-11-PLAN Task 2 per row.
**Expected:** Note wraps (no horizontal scrollbar); `intersects: false` for every row; `Update status` legible with no `dd/mm/yyyy` glyph band.
**Why human:** Runtime layout — no layout engine in the repo. The mandated rendered-rect check was not performed (WINDOWS #9 open).

### 2. Drafting round-trip re-run (G-07-7)
**Test:** Click `Draft answers` on a package whose provider wraps a list-typed field as `{"item": ...}`; confirm four reviewable answers and test `Copy answer`.
**Expected:** Four answers render; paste reproduces the full untruncated answer.
**Why human:** Depends on the live provider emission; the deterministic half is tested but not re-run live.

### 3. MVP mode / goal-format (developer decision)
**Observation:** Phase 7 is marked `mode: mvp` but the goal is not in User-Story form (`user-story.validate` → `valid: false`). Confirmed intentional at UAT test 3 (2026-10-06); standard goal-backward verification used.

## Gaps Summary

The phase's **functional** goal is achieved: the apply package, the tracker, the exact-CV linkage, the append-only event history, and both gap-closure fixes (G-07-5/6/7) are implemented and pass 257 tests across the phase lanes. All 7 requirement IDs are functionally satisfied.

**One blocker prevents a clean pass — CR-01 (deployment stylesheet divergence):**

- I ran the Dockerfile's exact build command. The result (34,561 B) differs from the committed `static/vendor/app.css` (39,308 B) and is **missing 30 classes** the templates use, including the phase-7 surfaces `.answer-text`, `.answer-warning`, `.apply-link`, `.apply-assurance`, `.next-overdue`, `.requirement-list`, `.listing-detail-link` — and **all eight `.badge-stage-*` tracker badge colours** (which the existing coverage guard cannot see, because `badge-stage-{{ row.status }}` is a dynamic class).
- `Dockerfile` line 116 ships that rebuilt file, and `compose.yml` mounts only `./data`/`./cv`/`./artifacts` — never the repo tree — so the supported deployment renders the tracker and apply package unstyled. The repo's own `tests/test_stylesheet_coverage.py` reads the committed artifact and cannot detect this.
- Root cause is pre-existing (the `input.css` drift dates to phase 5) but phase 7 both adds to the hand-appended block and, in 07-11, hand-appended rather than regenerating. `deferred-items.md` logged it as out-of-scope; the review (`07-REVIEW.md` CR-01) and this verification treat the deployed consequence as blocking, in files modified this gap round (evidence gate → fail closed).

Because the defect touches the phase's own required UI artifacts and its only deployment target, this is recorded as a blocker: **status `gaps_found`**. If the developer judges that shipping unstyled UI is acceptable for v1, this can be waived with an override; otherwise the fix is to reconcile `assets/tailwind/input.css` with the built output, regenerate `static/vendor/app.css`, and add a build-reproducibility guard.

The two non-inferable backstop truths (tracker note `title` fidelity at render, clipboard multi-paragraph copy fidelity) and the G-07-6 rendered-rect check remain `PRESENT_BEHAVIOR_UNVERIFIED`; they are preserved in `behavior_unverified_items` and surfaced under Human Verification.

---

_Verified: 2026-10-12T12:15:00Z_
_Verifier: the agent (gsd-verifier)_
