---
phase: 07-assisted-apply-tracker
verified: 2026-10-12T15:45:00Z
status: human_needed
score: 16/18 must-haves verified
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
  - .planning/phases/07-assisted-apply-tracker/07-13-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-13-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-14-PLAN.md
  - .planning/phases/07-assisted-apply-tracker/07-14-SUMMARY.md
  - .planning/phases/07-assisted-apply-tracker/07-CONTEXT.md
  - .planning/phases/07-assisted-apply-tracker/07-UAT.md
  - .planning/phases/07-assisted-apply-tracker/07-UI-SPEC.md
  - .planning/phases/07-assisted-apply-tracker/07-REVIEW.md
  - .planning/phases/07-assisted-apply-tracker/07-UI-REVIEW.md
  - .planning/phases/07-assisted-apply-tracker/07-SECURITY.md
  - .planning/phases/07-assisted-apply-tracker/07-VALIDATION.md
  - .planning/phases/07-assisted-apply-tracker/deferred-items.md
  - Dockerfile
  - assets/tailwind/input.css
  - static/vendor/app.css
  - app/domain/schemas/_coerce.py
  - app/domain/cv.py
  - app/domain/schemas/screening.py
  - app/domain/schemas/ranking.py
  - app/api/apply.py
  - app/api/applications.py
  - app/api/tailoring.py
  - app/db/repositories/application_repo.py
  - app/db/repositories/screening_draft_repo.py
  - app/db/repositories/apply_config_repo.py
  - app/web/templates/html/apply.html
  - app/web/templates/html/_screening_drafts.html
  - app/web/templates/html/_application_row.html
  - app/web/templates/html/applications.html
  - app/web/templates/html/applications_list.html
  - app/web/templates/html/_application_history.html
  - alembic/versions/0006_screening_drafts.py
  - alembic/versions/0007_screening_draft_warnings.py
  - tests/test_stylesheet_coverage.py
  - tests/domain/test_coerce.py
  - tests/domain/test_screening_schema.py
  - tests/llm/test_salvage.py
  - tests/api/test_apply_package.py
  - tests/api/test_applications_tracker.py
  - tests/api/test_apply_draft_errors.py
  - tests/api/test_cv_pdf_route.py
  - tests/db/test_application_events.py
covered_digest: "v3:sha256:4508b999c8057eeb44ca940e496fc22701cd85c5c4caec4129435d765068e228"
behavior_unverified: 2
overrides_applied: 0
decision_coverage_override: # §13a — accepted, re-surfaced (NOT unplanned work)
  decisions: [D-120, D-126, D-128, D-129, D-130, D-131, D-133, D-134]
  kind: citation-only
  reason: "The decision-coverage gate found 8 CONTEXT decisions with no literal `D-NN:` citation on a planned surface. Each decision is implemented and verified in code; the gap is citation-only, not missing behaviour. Accepted by the user 2026-10-06 and re-confirmed 2026-10-12 (\"proceed anyway\")."
  accepted_by: "user"
  accepted_at: "2026-10-06T00:00:00Z"
  reconfirmed_at: "2026-10-12T00:00:00Z"
re_verification:
  previous_status: gaps_found
  previous_score: 11/14
  gaps_closed:
    - "CR-01 (deployed stylesheet divergence): `static/vendor/app.css` is now the byte-identical build of `assets/tailwind/input.css` — independently re-verified here (`cmp` exit 0 on the Dockerfile:19 command with the pinned tailwindcss 4.3.3 CLI). All eight `.badge-stage-*` and three `badge-score-tier-*` selectors are present. Two Node-free source-coverage guards and a byte-identity guard were added to `tests/test_stylesheet_coverage.py`."
    - "WR-01 (arity-only wrapper unwrap): `unwrap_single_key_mapping` now recognises only the literal `WRAPPER_KEY = \"item\"`; `{\"nope\": [\"bul/x/1\"]}`, `{\"items\": …}`, `{\"value\": …}`, `{\"data\": …}` all raise; `TailoringPatch.ops/.gaps/.suggestions` route through the same helper (IN-01); the two scalar false-name tests were replaced."
  gaps_remaining: []
  regressions: []
gaps: [] # No blocking gaps — the prior CR-01 blocker is closed
behavior_unverified_items:
  - truth: "G-07-6: the tracker `Update status` button rect does not intersect the `Next action` date-input rect at 1280px and 375px (the plan's mandated rendered-rect check)."
    test: "Load `/applications` with a row carrying both a status and a Next-action date; run 07-11-PLAN Task 2's `getBoundingClientRect()` snippet per row at 1280px and 375px, JS on, the `Move to` select untouched."
    expected: "`intersects: false` for every row; no `dd/mm/yyyy` glyph band over the button; no horizontal scrollbar for a long note."
    why_human: "No layout/browser engine ships in the repo (dev deps are pytest/pytest-asyncio/ruff). The CSS declaration contract IS asserted and green, but the measured-rect verdict is unrun — `WINDOWS.md` #9 remains an open `unrun-verify`."
  - truth: "Backstop (07-05): `Copy answer` reproduces the full untruncated multi-paragraph drafted answer (clipboard fidelity)."
    test: "Draft or seed a multi-paragraph answer, click `Copy answer`, paste into a scratch field."
    expected: "The paste equals the full untruncated answer; the label flips to `Copied` for ~2s."
    why_human: "Non-inferable backstop; browser clipboard behaviour has no held-out test (the suite only asserts the button markup). UAT test 2 was never re-run after G-07-7."
human_verification:
  - test: "Tracker layout re-run (G-07-5 + G-07-6): record an application with a ~300-character note and a next-action date; open `/applications` at 1280px and 375px; confirm the note wraps (no horizontal scroll), the `Update status` button has no date field painted over it, and run the rendered-rect snippet from 07-11-PLAN Task 2."
    expected: "Note wraps; `intersects: false` for every row at both widths; button legible and clickable."
    why_human: "Runtime layout; the automated lane only asserts the CSS declaration contract. Not re-run since the fix."
  - test: "Drafting round-trip + clipboard re-run (G-07-7, backstop): click `Draft answers` on a package whose provider wraps a list-typed field as `{\"item\": …}`; confirm four reviewable answers appear and `Copy answer` pastes the full untruncated answer."
    expected: "Four answers render (not the 502 `drafting_failed` message); copy/paste reproduces the full answer."
    why_human: "Depends on the live provider emission and browser clipboard; the deterministic half is covered by tests but the live round-trip was not re-run."
  - test: "MVP-mode / goal-format discrepancy (developer decision)."
    expected: "Confirm the `mode: mvp` annotation on Phase 7 is intentional; the goal is not in User-Story form (`user-story.validate` → `valid: false`). Standard goal-backward verification (as here) is sufficient, or run `/gsd mvp-phase 7` to convert the goal."
    why_human: "Developer decision, not a code defect. Carried forward from the prior verification (UAT test 3 passed 2026-10-06)."
advisory: [] # WR-02 carries deterministic evidence (reproduced hang), so it is a WARNING, not advisory
---

# Phase 07: Assisted Apply + Tracker — Re-Verification Report

**Phase Goal (ROADMAP.md, verbatim):** An apply package per listing plus an application tracker that links every outcome to the exact verified CV artefact that was sent.
**Verified:** 2026-10-12T15:45:00Z
**Status:** human_needed
**Re-verification:** Yes — after re-verification gap-closure plans 07-13 (CR-01) and 07-14 (WR-01).

**Roadmap Success Criteria (verbatim; `mode: mvp`, but the goal is not in User-Story form — see Human Verification #3):**

1. User can open an apply package for a listing containing the verified PDF, the apply link, drafted screening answers, and a gap checklist.
2. The tool never submits an application on the user's behalf.
3. User can record an application with a status stage, notes, and a next-action date/deadline, and every application links to the exact verified CV artefact that was sent.
4. Application status changes are recorded as an append-only event history the user can view and manage.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | (SC1) Apply package: verified PDF, apply link, drafted answers, gap checklist | ✓ VERIFIED | `app/api/apply.py::apply_package_page` computes ONE `package_state` (gated/ready) from `latest_for_listing(ok_only=True)` + `read_score_for_listing`; `apply.html` blocks 1–4; `_screening_drafts.html`; `tests/api/test_apply_package.py` |
| 2 | (SC2) The tool never submits on the user's behalf | ✓ VERIFIED | Only local-path forms (`/applications/record`, `/listings/{id}/apply/draft[/delete]`, `/listings/{id}/apply/question`); the outbound action is a plain `<a class="apply-link" target="_blank" rel="noopener noreferrer">`; `test_no_submit_surface` |
| 3 | (SC3) Record with stage/notes/next-action; link to the exact verified CV | ✓ VERIFIED | `applications.py` record → 303; `application_repo.record_application` ok-only gate via `cv_artifact_repo.read_for_download(ok_only=True)`; `applications.cv_artifact_id` is the historical link; `test_a_later_stage_move_keeps_the_exact_cv_link_over_http`, `test_the_exact_cv_link_survives_every_later_transition` (commit 6740f3a) |
| 4 | (SC4) Status changes recorded as append-only event history, viewable/managed | ✓ VERIFIED | migration 0006 `application_events_no_update/no_delete` `RAISE(ABORT,…)`; row update + one event in one `begin_nested()` (`application_repo.py:486/542`); `read_history`; `tests/db/test_application_events.py` |
| 5 | (G-07-1) Record submit returns 303 to the full styled tracker page | ✓ VERIFIED | `applications.py` `RedirectResponse(url="/applications", status_code=303)`; refusal paths unchanged |
| 6 | (G-07-2) Recorded malformed screening payloads coerce without dropping answers | ✓ VERIFIED | `screening.py` before-validators delegate to `_coerce`; `test_screening_schema.py`, `test_salvage.py` |
| 7 | (G-07-3) Flagged answers name the offender; advisory band renders as advisory | ✓ VERIFIED | `_screening_drafts.html:37-43` per-finding `.answer-warning` + advisory `.field-note` band; migration 0007; `tests/api/test_apply_package_warnings.py` |
| 8 | (G-07-4) A `?artifact_id=` request serves that row's own PDF; foreign/blocked/unknown → 404 | ✓ VERIFIED | `tailoring.py` `read_for_download(ok_only=True, artifact_id)` + listing-ownership; `tests/api/test_cv_pdf_route.py` |
| 9 | (CR-01 prior) A valid-but-partial drafting response is refused before `replace_for_listing` | ✓ VERIFIED | `apply.py` `len(verdicts) < len(questions)` → `drafting_partial` guard precedes the delete; `tests/api/test_apply_draft_errors.py` (6 pass) |
| 10 | (G-07-5) The tracker note cell wraps and keeps the full untruncated string in `title=""` | ✓ VERIFIED | `_application_row.html` `class="tracker-note" title="{{ row.notes or '' }}"`; `.tracker-note{white-space:normal;overflow-wrap:anywhere;max-width:24rem}` |
| 11 | (G-07-6) The tracker Actions cell is scoped and its controls cannot share a line box (declaration contract) | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `tracker-actions`/`tracker-action` present; `test_the_tracker_action_cell_cannot_overlap_its_controls` asserts `white-space:normal`/`display:block`. The MANDATED rendered-rect measurement was NOT performed → see Human Verification |
| 12 | (G-07-7) A `{"item": …}`-wrapped list-typed field yields usable drafted answers, not 502 | ✓ VERIFIED | `_coerce.unwrap_single_key_mapping`; `test_the_literal_captured_payload_salvages_to_four_answers`; `test_the_literal_wrapped_payload_persists_four_rows` |
| 13 | (07-13/CR-01) The stylesheet the Docker image ships IS the build of its source | ✓ VERIFIED | Fresh build of `assets/tailwind/input.css` with the pinned CLI (`./node_modules/.bin/tailwindcss` v4.3.3, the `Dockerfile:19` command) → `cmp static/vendor/app.css /tmp/opencode/verify-rebuilt.css` **exit 0**; `Dockerfile:116` ships it |
| 14 | (07-13) No template class can be dropped by a rebuild; dynamic-suffix values pinned | ✓ VERIFIED | `badge-stage-*` = 8 distinct selectors, `badge-score-tier-*` = 3 in the committed build; `test_every_template_class_has_a_rule_in_the_source_stylesheet`, `test_every_dynamic_suffix_class_is_defined_in_the_source_stylesheet` (+ not-vacuous siblings), `test_the_committed_stylesheet_is_the_build_of_its_source` |
| 15 | (07-14/WR-01) The unwrap recognises only the literal `"item"` key; unknown keys fail loudly | ✓ VERIFIED | `_coerce.py` `WRAPPER_KEY = "item"` + key check; `test_an_unknown_wrapper_key_with_a_list_value_still_fails_loudly`, `test_a_non_item_single_key_still_fails_loudly`; `TOLERATED_SCHEMA_ERRORS` byte-unchanged |
| 16 | (07-14) The unwrap terminates on a directly self-referential single-key Mapping | ✓ VERIFIED | `if inner is value: break`; `test_a_self_referential_single_key_mapping_terminates` passes. **Caveat:** a two-node mutual cycle still loops — see WR-02 (non-blocking) |
| 17 | (07-14/IN-01) `TailoringPatch.ops/.gaps/.suggestions` share the helper | ✓ VERIFIED | `app/domain/cv.py` before-validators route through `coerce_mapping_list`; `test_a_tailoring_patch_list_field_unwraps_the_wrapper_and_wraps_the_bare_object`, `test_a_tailoring_patch_non_item_single_key_mapping_is_refused` |
| 18 | (Backstop) `Copy answer` reproduces the full untruncated multi-paragraph answer | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Handler + markup present; browser-only, no held-out test exercises the clipboard → see Human Verification |

**Score:** 16/18 truths verified (2 present, behavior-unverified; 0 failed)

### Deferred Items

None. `deferred-items.md`'s single entry (the `input.css` drift) is now **closed** by plan 07-13, not deferred.

### Advisory (New Scope, Unevidenced)

None. The residual WR-02 finding carries deterministic, reproducible evidence (a reproduced hang, exit 124), so it is a WARNING anti-pattern, not an advisory.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `assets/tailwind/input.css` | reconciled source of truth (all template rules) | ✓ VERIFIED | Appended `@layer components` block carries the 30 previously hand-appended rules + 8 `.badge-stage-*` + 3 `badge-score-tier-*`; additive only |
| `static/vendor/app.css` | the byte-identical build of its source | ✓ VERIFIED | 38,842 B; `cmp` against a fresh pinned-CLI build exits 0 (was ✗ STUB) |
| `app/domain/schemas/_coerce.py` | shared pure unwrap, key-restricted + bounded | ✓ VERIFIED | `WRAPPER_KEY`; literal-key check; `inner is value` bound; docstrings match code (direct case) |
| `app/domain/cv.py` | `TailoringPatch` list fields share the helper | ✓ VERIFIED | `_coerce_ops`/`_coerce_gaps`/`_coerce_suggestions` before-validators |
| `app/api/apply.py`, `app/api/applications.py` | package + tracker routes | ✓ VERIFIED | 6 tracker routes; package/draft/question/delete; 303 PRG; `drafting_partial` guard |
| `application_repo.py`, `screening_draft_repo.py`, `apply_config_repo.py` | record/transition/history/store | ✓ VERIFIED | ok-only gate; single-transaction event; warnings/band round-trip |
| `alembic/versions/0006/0007` | append-only triggers; nullable warnings | ✓ VERIFIED | raw `op.execute` triggers; symmetric downgrade |
| `tests/test_stylesheet_coverage.py` | source-coverage + byte-identity guards | ✓ VERIFIED | 10 tests; byte-identity guard ran (did not skip) in this environment |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `input.css` (source) | `static/vendor/app.css` (deployed) | Tailwind CLI build | ✓ WIRED | Byte-identical fresh build; `Dockerfile:19` → `:116` (was ✗ NOT_WIRED) |
| `applications.status` | exactly one `application_events` row | one `begin_nested()` | ✓ WIRED | only writer; `test_application_events.py` |
| migration 0006 trigger | schema-level append-only | `RAISE(ABORT,…)` | ✓ WIRED | asserted against migrated DDL |
| `read_for_download(ok_only=True)` | `applied` gate → `cv_artifact_id` | SQL `compile_status == "ok"` | ✓ WIRED | blocked refused, writes nothing; link survives later transitions |
| `_coerce_evidence_ids` | `_salvage` → route persistence | before-validator | ✓ WIRED | 4 rows persist for the literal payload |
| filter/search controls | `hx-get="/applications/list"` fragment | one shared template | ✓ WIRED | page and swap share `applications_list.html` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `applications_list.html` | `rows`, `count`, `page` | `application_repo.read_tracker` (SQL join + event count) | Yes | ✓ FLOWING |
| `_screening_drafts.html` | `answer_rows`, `warnings`, `band` | `screening_draft_repo.read_for_listing` + `apply_config_repo.read_questions` | Yes | ✓ FLOWING |
| `apply.html` (gaps/PDF/link) | `gaps`, `latest_artifact_id`, `apply_url` | `score_repo.read_score_for_listing` / `latest_for_listing` / `listing.apply_url` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase functional/support lanes (coerce, screening, salvage, draft-errors, tracker, package, warnings, events, cv route, stylesheet) | `/tmp/opencode/gsdvenv13/bin/python -m pytest -q <10 files>` | `122 passed in 45.98s` | ✓ PASS |
| Full default lane | `/tmp/opencode/gsdvenv13/bin/python -m pytest -q` | `1708 passed, 14 deselected, 2 xfailed in 306.60s` | ✓ PASS |
| Deployed-stylesheet reproducibility (Dockerfile:19 command) | `./node_modules/.bin/tailwindcss -i ./assets/tailwind/input.css -o /tmp/opencode/verify-rebuilt.css --minify && cmp static/vendor/app.css …` | `cmp` exit **0** (byte-identical) | ✓ PASS |
| `.badge-stage-*` / `badge-score-tier-*` in the shipped build | `grep -o … \| sort -u \| wc -l` | `8` and `3` | ✓ PASS |
| WR-02 residual: mutual-cycle termination | `timeout 15 python -c "…a['item']=b; b['item']=a; u(a)"` | hang, `RAW_EXIT=124` | ✗ FAIL (WR-02, non-blocking) |

### Probe Execution

N/A — phase 07 declares no probes and is not a migration/tooling phase. No `scripts/*/tests/probe-*.sh` apply.

### Requirements Coverage

All 7 phase requirement IDs are declared in PLAN frontmatter and mapped to Phase 7 in REQUIREMENTS.md. No orphaned IDs.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| APPLY-01 | 07-02,03,05,06,07,09,10,12,13,14 | Apply package: verified PDF, apply link, drafted answers, gap checklist | ✓ SATISFIED | Package/page/grounding/coercion/warnings/download verified; deployed styling now reproducible |
| APPLY-02 | 07-02 | The tool never submits on the user's behalf | ✓ SATISFIED | `test_no_submit_surface`; plain anchor + local record form only |
| APPLY-03 | 07-01, 07-08 | Record an application with a status stage and notes | ✓ SATISFIED | record route 303s to the tracker; refusal unchanged |
| APPLY-04 | 07-01 | Every recorded application links to the exact CV version sent | ✓ SATISFIED | ok-only `applied` gate; `cv_artifact_id` survives later transitions (commit 6740f3a) |
| APPLY-05 | 07-01 | Status changes recorded as append-only events | ✓ SATISFIED | migration 0006 triggers; same-transaction event |
| APPLY-06 | 07-01, 07-04, 07-08 | Next action date/deadline | ✓ SATISFIED | `parse_next_action`, needs-action ordering |
| UI-04 | 07-04, 07-05, 07-08, 07-11, 07-13 | User can view and manage the application tracker | ✓ SATISFIED | Tracker page/filters/search/needs-action/pager/transitions/notes/answers region; G-07-5/6 fixed; deployed styling reproducible |

**Coverage:** 7/7 satisfied.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/domain/schemas/_coerce.py` | docstring 35-36; loop 38-45 | WR-02: the bound covers only the direct instance (`inner is value`); a two-node mutual `{"item": …}` cycle loops (reproduced: 20s timeout, exit 124), while the docstring claims self-reference "cannot hang" | ⚠️ WARNING | CONVENTIONS rule 6 false guarantee in an exported helper. Non-wire-reachable (`json.loads`-derived payloads cannot be cyclic), so not a blocker; the review's visited-identity fix is the recommended follow-up |
| `app/domain/cv.py` | `_coerce_ops` docstring | IN-03: names `extra="forbid"` as the refusal route for `ops`, where the discriminator (missing `op` tag) is what fires | ℹ️ INFO | Prose only; both refuse |
| `tests/test_stylesheet_coverage.py` | `test_the_committed_stylesheet_is_the_build_of_its_source` | IN-04: the byte-identity guard visibly `pytest.skip`s where the CLI is absent (ran here, so armed); it would not catch a byte-diff that drops no class in a Node-less lane | ℹ️ INFO | Documented trade-off; the deployed image rebuilds from source, so no runtime impact |
| — | — | No `TBD`/`FIXME`/`XXX`/`HACK`/`PLACEHOLDER` markers in any phase-modified file | — | Debt-marker gate satisfied |

### Accepted Override — Decision Coverage (§13a)

The decision-coverage gate found **8 CONTEXT decisions without literal `D-NN:` citations on a planned surface**: `D-120`, `D-126`, `D-128`, `D-129`, `D-130`, `D-131`, `D-133`, `D-134`. Each is **implemented and verified in code** (e.g. D-120 `/listings/{id}/apply` dedicated page; D-126 per-listing draft persistence; D-128 eight-value guided transitions; D-129 ok-artefact picker on `applied`; D-130 `applied_at` stamped by the transition; D-131 same-transaction event append; D-133 stage/needs-action/search slice; D-134 inline expandable history timeline). The gap is **citation-only, not missing behaviour**. The user accepted this override on **2026-10-06** and re-confirmed it on **2026-10-12** ("proceed anyway"). Recorded here so it is **not** re-treated as unplanned work. (Note: `D-130` does appear cited in `07-01-PLAN.md`; it is retained in the override list as given.)

## Human Verification Required

### 1. Tracker layout re-run (G-07-5 + G-07-6)
**Test:** Record an application with a ~300-character note and a next-action date; open `/applications` at 1280px and 375px; run the rendered-rect snippet from 07-11-PLAN Task 2 per row.
**Expected:** Note wraps (no horizontal scrollbar); `intersects: false` for every row; `Update status` legible with no `dd/mm/yyyy` glyph band.
**Why human:** Runtime layout — no layout engine in the repo. The mandated rendered-rect check was not performed (WINDOWS #9 open).

### 2. Drafting round-trip + clipboard re-run (G-07-7, backstop)
**Test:** Click `Draft answers` on a package whose provider wraps a list-typed field as `{"item": …}`; confirm four reviewable answers and test `Copy answer`.
**Expected:** Four answers render; paste reproduces the full untruncated answer.
**Why human:** Depends on the live provider emission and browser clipboard; the deterministic half is tested but not re-run live.

### 3. MVP mode / goal-format (developer decision)
**Observation:** Phase 7 is marked `mode: mvp` but the goal is not in User-Story form (`user-story.validate` → `valid: false`). Confirmed intentional at UAT test 3 (2026-10-06); standard goal-backward verification used.

## Gaps Summary

**No blocking gaps remain.** The prior verification's single blocker — **CR-01** (the deployed stylesheet diverged from its Tailwind source) — is **closed and independently re-verified here**: a fresh build of `assets/tailwind/input.css` with the pinned 4.3.3 CLI (the exact `Dockerfile:19` command) is byte-identical to the committed `static/vendor/app.css` (`cmp` exit 0), all eight `.badge-stage-*` and three `badge-score-tier-*` selectors are present, and two Node-free source-coverage guards plus a byte-identity guard now make a divergence a test failure. **WR-01** (the arity-only wrapper unwrap) is also closed: the unwrap recognises only the literal `"item"` key and unknown keys fail loudly.

All 7 requirement IDs are satisfied; the full default lane is green (1708 passed, 14 deselected, 2 xfailed), and the phase lanes pass 122 tests. The phase's functional goal is achieved.

Two truths remain **PRESENT_BEHAVIOR_UNVERIFIED** (recorded in `behavior_unverified_items`, surfaced under Human Verification): the G-07-6 rendered-rect geometry (no layout engine in the repo) and the clipboard multi-paragraph copy fidelity (browser-only backstop, no held-out test). Because human-verification items exist, the status is **`human_needed`** rather than `passed`.

One **non-blocking WARNING (WR-02)** survives from the 07-14 fix: `unwrap_single_key_mapping` bounds only the direct self-reference, so a two-node mutual `{"item": …}` cycle loops (reproduced, exit 124) while its docstring claims self-reference "cannot hang". It is not wire-reachable (JSON-derived payloads cannot be cyclic) and therefore does not gate this phase, but the review's visited-identity fix is recommended as a follow-up to make the prose honest (CONVENTIONS rule 6).

---

_Verified: 2026-10-12T15:45:00Z_
_Verifier: the agent (gsd-verifier)_
