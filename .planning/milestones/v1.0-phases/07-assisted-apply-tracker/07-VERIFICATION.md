---
phase: 07-assisted-apply-tracker
verified: 2026-10-12T15:36:07Z
status: passed
score: 18/18 must-haves verified
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
  - tests/api/test_apply_package_warnings.py
  - tests/api/test_applications_tracker.py
  - tests/api/test_apply_draft_errors.py
  - tests/api/test_cv_pdf_route.py
  - tests/db/test_application_events.py
  - tests/db/test_application_repo.py
covered_digest: "v1:sha256:90a5cc9302807b7ec304573559413cb936d64e6a2c21a84fcfe90656a3a38abf"
behavior_unverified: 0
overrides_applied: 2
overrides:
  - must_have: "G-07-7: Clicking `Draft answers` on an apply package returns usable drafted answers the user can review and copy."
    reason: "Live re-run on 2026-10-12 failed: the provider still emits a list-typed field in a shape `unwrap_single_key_mapping` does not recognise, so the response is refused (`drafting_failed`) and no answers render. The deterministic unwrap path IS tested (07-06, 07-14) but the live provider emission is not pinned. The user explicitly accepted this as a documented known limitation and directed the phase to ship (\"I think at this point I want to just move on as we've iterated so many times\"). Recorded in `07-UAT.md` (`G-07-7 status: deferred`), `deferred-items.md`, and `README.md` → Known limitations."
    accepted_by: "user"
    accepted_at: "2026-10-12T00:00:00Z"
  - must_have: "Backstop (07-05): `Copy answer` reproduces the full untruncated multi-paragraph drafted answer (clipboard fidelity)."
    reason: "Subsumed by the accepted G-07-7 deviation: the clipboard path is downstream of drafting, so while drafting returns no usable answers there is nothing to copy and the backstop is unreachable in the live environment. The handler and button markup are present and wired; the browser-only fidelity was part of UAT test 2, which was performed on 2026-10-12 and answered by the same user decision to ship."
    accepted_by: "user"
    accepted_at: "2026-10-12T00:00:00Z"
decision_coverage_override: # §13a — accepted, re-surfaced (NOT unplanned work)
  decisions: [D-120, D-126, D-128, D-129, D-130, D-131, D-133, D-134]
  kind: citation-only
  reason: "The decision-coverage gate found 8 CONTEXT decisions with no literal `D-NN:` citation on a planned surface. Each decision is implemented and verified in code; the gap is citation-only, not missing behaviour. Accepted by the user 2026-10-06 and re-confirmed 2026-10-12 (\"proceed anyway\")."
  accepted_by: "user"
  accepted_at: "2026-10-06T00:00:00Z"
  reconfirmed_at: "2026-10-12T00:00:00Z"
re_verification:
  previous_status: human_needed
  previous_score: 16/18
  gaps_closed:
    - "G-07-6 (tracker action-cell geometry): the mandated rendered-rect check was performed by the user on 2026-10-12 at 1280px and 375px — `intersects: false` for every row, no `dd/mm/yyyy` glyph band over `Update status`, note wraps. 07-UAT.md test 1: pass. G-07-5 and G-07-6 confirmed fixed in the live UI."
  gaps_remaining:
    - "G-07-7 (live drafting refusal) — NOT fixed; accepted by the user on 2026-10-12 as a documented known limitation and deferred (`07-UAT.md` `G-07-7 status: deferred`; see `overrides`). Not a blocker by explicit user decision."
  regressions: []
gaps: [] # No blocking gaps
advisory: [] # WR-02 carries deterministic evidence (reproduced hang), so it is a WARNING, not advisory
---

# Phase 07: Assisted Apply + Tracker — Re-Verification Report

**Phase Goal (ROADMAP.md, verbatim):** An apply package per listing plus an application tracker that links every outcome to the exact verified CV artefact that was sent.
**Verified:** 2026-10-12T15:36:07Z
**Status:** passed
**Re-verification:** Yes — digest refresh after the UAT results, the re-run code review and `deferred-items.md` were written (2026-10-12). No PLAN, SUMMARY or implementation file changed since the prior verification; the must-haves were re-checked against the current tree regardless.

**Roadmap Success Criteria (verbatim; `mode: mvp`, but the goal is not in User-Story form — confirmed intentional at UAT test 3, 2026-10-12):**

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
| 4 | (SC4) Status changes recorded as append-only event history, viewable/managed | ✓ VERIFIED | migration 0006 `application_events_no_update/no_delete` `RAISE(ABORT,…)`; row update + one event in one `begin_nested()` (`application_repo.py`); `read_history`; `tests/db/test_application_events.py` |
| 5 | (G-07-1) Record submit returns 303 to the full styled tracker page | ✓ VERIFIED | `applications.py:205` `RedirectResponse(url="/applications", status_code=303)`; refusal paths unchanged |
| 6 | (G-07-2) Recorded malformed screening payloads coerce without dropping answers | ✓ VERIFIED | `screening.py` before-validators delegate to `_coerce`; `test_screening_schema.py`, `test_salvage.py` |
| 7 | (G-07-3) Flagged answers name the offender; advisory band renders as advisory | ✓ VERIFIED | `_screening_drafts.html:37-43` per-finding `.answer-warning` + advisory `.field-note` band; migration 0007 (`warnings_json`, `band`); `tests/api/test_apply_package_warnings.py` |
| 8 | (G-07-4) A `?artifact_id=` request serves that row's own PDF; foreign/blocked/unknown → 404 | ✓ VERIFIED | `tailoring.py:673-676` `read_for_download(ok_only=True, artifact_id)` + listing-ownership; `tests/api/test_cv_pdf_route.py` |
| 9 | (CR-01 prior) A valid-but-partial drafting response is refused before `replace_for_listing` | ✓ VERIFIED | `apply.py` `len(verdicts) < len(questions)` → `drafting_partial` guard precedes the delete; `tests/api/test_apply_draft_errors.py` |
| 10 | (G-07-5) The tracker note cell wraps and keeps the full untruncated string in `title=""` | ✓ VERIFIED | `_application_row.html:21` `class="tracker-note" title="{{ row.notes or '' }}"`; `.tracker-note{white-space:normal;overflow-wrap:anywhere;max-width:24rem}` |
| 11 | (G-07-6) The tracker Actions cell is scoped and its controls cannot share a line box (declaration contract + rendered geometry) | ✓ VERIFIED | `tracker-actions`/`tracker-action` present; `test_the_tracker_action_cell_cannot_overlap_its_controls` asserts `white-space:normal`/`display:block`; **the mandated rendered-rect check was performed by the user 2026-10-12** — `intersects: false` for every row at 1280px and 375px (`07-UAT.md` test 1: pass) |
| 12 | (G-07-7) A `{"item": …}`-wrapped list-typed field yields usable drafted answers, not 502 | ✓ PASSED (override) | Deterministic half verified (`_coerce.unwrap_single_key_mapping`; `test_the_literal_captured_payload_salvages_to_four_answers`; `test_the_literal_wrapped_payload_persists_four_rows`). **Live half FAILED 2026-10-12** — the provider still emits an unrecognised list-typed shape → `drafting_failed`. Accepted by the user as a documented known limitation and deferred; see `overrides` and `07-UAT.md` `G-07-7 status: deferred` |
| 13 | (07-13/CR-01) The stylesheet the Docker image ships IS the build of its source | ✓ VERIFIED | Fresh build of `assets/tailwind/input.css` with the pinned CLI (`./node_modules/.bin/tailwindcss` v4.3.3, the `Dockerfile:19` command) → byte-identical to the committed `static/vendor/app.css`; the byte-identity guard ran (did not skip) and passed; `Dockerfile:19` → ships at `:116` |
| 14 | (07-13) No template class can be dropped by a rebuild; dynamic-suffix values pinned | ✓ VERIFIED | `badge-stage-*` = 8 distinct selectors, `badge-score-tier-*` = 3 in the committed build; `test_every_template_class_has_a_rule_in_the_source_stylesheet`, `test_every_dynamic_suffix_class_is_defined_in_the_source_stylesheet` (+ not-vacuous siblings), `test_the_committed_stylesheet_is_the_build_of_its_source` (10 tests pass) |
| 15 | (07-14/WR-01) The unwrap recognises only the literal `"item"` key; unknown keys fail loudly | ✓ VERIFIED | `_coerce.py` `WRAPPER_KEY = "item"` + key check; `test_an_unknown_wrapper_key_with_a_list_value_still_fails_loudly`, `test_a_non_item_single_key_still_fails_loudly` |
| 16 | (07-14) The unwrap terminates on a directly self-referential single-key Mapping | ✓ VERIFIED | `if inner is value: break`; `test_a_self_referential_single_key_mapping_terminates` passes. **Caveat:** a two-node mutual cycle still loops — see WR-02 (non-blocking) |
| 17 | (07-14/IN-01) `TailoringPatch.ops/.gaps/.suggestions` share the helper | ✓ VERIFIED | `app/domain/cv.py:531-550` before-validators route through `coerce_mapping_list`; `test_a_tailoring_patch_list_field_unwraps_the_wrapper_and_wraps_the_bare_object`, `test_a_tailoring_patch_non_item_single_key_mapping_is_refused` |
| 18 | (Backstop) `Copy answer` reproduces the full untruncated multi-paragraph answer | ✓ PASSED (override) | Handler + markup present and wired; the browser-only fidelity was part of UAT test 2 (performed 2026-10-12). Unreachable while the accepted G-07-7 limitation means no answers render; subsumed by the same user decision — see `overrides` |

**Score:** 18/18 truths verified (2 PASSED by accepted override; 0 failed; 0 present-behavior-unverified)

### Deferred Items

None. `deferred-items.md`'s `input.css` drift entry is **closed** by plan 07-13, not deferred; its remaining entry (G-07-7) is recorded as an accepted known limitation under `overrides`, not as a milestone-deferred item.

### Advisory (New Scope, Unevidenced)

None. The residual WR-02 finding carries deterministic, reproducible evidence (a reproduced hang, exit 124), so it is a WARNING anti-pattern, not an advisory.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `assets/tailwind/input.css` | reconciled source of truth (all template rules) | ✓ VERIFIED | Appended `@layer components` block carries the 30 previously hand-appended rules + 8 `.badge-stage-*` + 3 `badge-score-tier-*`; additive only |
| `static/vendor/app.css` | the byte-identical build of its source | ✓ VERIFIED | `cmp` against a fresh pinned-CLI build exits 0; guard green (not skipped) in this environment |
| `app/domain/schemas/_coerce.py` | shared pure unwrap, key-restricted + bounded | ✓ VERIFIED | `WRAPPER_KEY`; literal-key check; `inner is value` bound; docstrings match code (direct case) |
| `app/domain/cv.py` | `TailoringPatch` list fields share the helper | ✓ VERIFIED | `_coerce_ops`/`_coerce_gaps`/`_coerce_suggestions` before-validators |
| `app/domain/schemas/screening.py`, `ranking.py` | wire list fields coerce before validation | ✓ VERIFIED | `_coerce_evidence_ids`/`_coerce_answers` (screening), `_coerce_requirements` (ranking) delegate to `_coerce` |
| `app/api/apply.py`, `app/api/applications.py`, `app/api/tailoring.py` | package + tracker + scoped-PDF routes | ✓ VERIFIED | package/draft/question/delete; 6 tracker routes; 303 PRG; `drafting_partial` guard; `?artifact_id=` ok-only |
| `application_repo.py`, `screening_draft_repo.py`, `apply_config_repo.py` | record/transition/history/store | ✓ VERIFIED | ok-only gate; single-transaction event; warnings/band round-trip; `read_tracker`/`read_history` |
| `alembic/versions/0006/0007` | append-only triggers; nullable warnings | ✓ VERIFIED | raw `op.execute` `RAISE(ABORT,…)` triggers; symmetric downgrade; nullable `warnings_json`/`band` |
| `tests/test_stylesheet_coverage.py` | source-coverage + byte-identity guards | ✓ VERIFIED | 10 tests pass; byte-identity guard ran (did not skip) in this environment |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `input.css` (source) | `static/vendor/app.css` (deployed) | Tailwind CLI build | ✓ WIRED | Byte-identical fresh build; `Dockerfile:19` → `:116` |
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
| Phase functional/support lanes (coerce, screening, salvage, package, warnings, tracker, draft-errors, cv route, events, screening-draft repo, stylesheet) | `/tmp/opencode/gsdvenv13/bin/python -m pytest -q <11 files>` | `135 passed in 34.87s` | ✓ PASS |
| Full default lane | `/tmp/opencode/gsdvenv13/bin/python -m pytest -q` | `1708 passed, 14 deselected, 2 xfailed in 366.85s` | ✓ PASS |
| Deployed-stylesheet reproducibility (`Dockerfile:19` command) | `tests/test_stylesheet_coverage.py -v` (byte-identity guard ran) | `10 passed` | ✓ PASS |
| `.badge-stage-*` / `badge-score-tier-*` in the shipped build | `grep -oE … \| sort -u \| wc -l` | `8` and `3` | ✓ PASS |
| Named phase tests exist | `grep -rln "def <test>" tests/` | all 11 named tests located | ✓ PASS |
| WR-02 residual: mutual-cycle termination | `timeout 15 python -c "…a['item']=b; b['item']=a; u(a)"` | hang, `RAW_EXIT=124` | ✗ FAIL (WR-02, non-blocking) |

### Probe Execution

N/A — phase 07 declares no probes and is not a migration/tooling phase. No `scripts/*/tests/probe-*.sh` apply.

### Requirements Coverage

All 7 phase requirement IDs are declared in PLAN frontmatter and mapped to Phase 7 in REQUIREMENTS.md. No orphaned IDs.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| APPLY-01 | 07-02,03,05,06,07,09,10,12,13,14 | Apply package: verified PDF, apply link, drafted answers, gap checklist | ✓ SATISFIED | Package/page/grounding/coercion/warnings/download verified; deployed styling reproducible. Live drafting emission deferred as an accepted known limitation (G-07-7 override) |
| APPLY-02 | 07-02 | The tool never submits on the user's behalf | ✓ SATISFIED | `test_no_submit_surface`; plain anchor + local record form only |
| APPLY-03 | 07-01, 07-08 | Record an application with a status stage and notes | ✓ SATISFIED | record route 303s to the tracker; refusal unchanged |
| APPLY-04 | 07-01 | Every recorded application links to the exact CV version sent | ✓ SATISFIED | ok-only `applied` gate; `cv_artifact_id` survives later transitions (commit 6740f3a) |
| APPLY-05 | 07-01 | Status changes recorded as append-only events | ✓ SATISFIED | migration 0006 triggers; same-transaction event |
| APPLY-06 | 07-01, 07-04, 07-08 | Next action date/deadline | ✓ SATISFIED | `parse_next_action`, needs-action ordering |
| UI-04 | 07-04, 07-05, 07-08, 07-11, 07-13 | User can view and manage the application tracker | ✓ SATISFIED | Tracker page/filters/search/needs-action/pager/transitions/notes/answers region; G-07-5/6 fixed and confirmed in the live UI (UAT test 1); deployed styling reproducible |

**Coverage:** 7/7 satisfied.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/domain/schemas/_coerce.py` | docstring 35-36; loop 38-45 | WR-02: the bound covers only the direct instance (`inner is value`); a two-node mutual `{"item": …}` cycle loops (reproduced: 15s timeout, exit 124), while the docstring claims self-reference "cannot hang" | ⚠️ WARNING | CONVENTIONS rule 6 false guarantee in an exported helper. Non-wire-reachable (`json.loads`-derived payloads cannot be cyclic), so not a blocker; the review's visited-identity fix is the recommended follow-up |
| `app/domain/cv.py` | `_coerce_ops` docstring | IN-03: names `extra="forbid"` as the refusal route for `ops`, where the discriminator (missing `op` tag) is what fires | ℹ️ INFO | Prose only; both refuse |
| `tests/test_stylesheet_coverage.py` | `test_the_committed_stylesheet_is_the_build_of_its_source` | IN-04: the byte-identity guard visibly `pytest.skip`s where the CLI is absent (ran here, so armed); it would not catch a byte-diff that drops no class in a Node-less lane | ℹ️ INFO | Documented trade-off; the deployed image rebuilds from source, so no runtime impact |
| — | — | No `TBD`/`FIXME`/`XXX`/`HACK`/`PLACEHOLDER` markers in any phase-modified file | — | Debt-marker gate satisfied |

### Accepted Deviation — Known Limitation (G-07-7)

The user ran the three human-verification items on **2026-10-12** (recorded in `07-UAT.md`, `status: diagnosed`; summary `passed: 2 / issues: 1`):

1. **Tracker layout re-run (G-07-5 + G-07-6) — pass.** The rendered-rect check at 1280px and 375px passed; G-07-5 and G-07-6 are closed. Truth #11 is therefore **VERIFIED**.
2. **Drafting round-trip + clipboard re-run (G-07-7) — fail, then accepted.** Clicking `Draft answers` still returns *"The drafting call did not return a usable response. Your existing drafts were kept."* — the live provider emits a list-typed field in a shape `unwrap_single_key_mapping` does not recognise, so `drafting_failed` is returned and no answers render. The user **explicitly decided to accept this as a documented known limitation and ship** ("I think at this point I want to just move on as we've iterated so many times"), recorded as `G-07-7 status: deferred` in `07-UAT.md`, in `deferred-items.md` (section "07-UAT re-run (2026-10-12) — accepted known limitation") and in `README.md` → Known limitations. This is recorded above as an **accepted override** (truth #12), and the downstream clipboard backstop (truth #18) is subsumed by it. The deterministic unwrap is fully tested (07-06, 07-14); the fix path is to capture the raw failing payload, widen the key-restricted unwrap to the observed shape, and add the literal payload as a held-out fixture.
3. **MVP mode / goal-format — pass.** The `mode: mvp` annotation is intentional; standard goal-backward verification (as performed here) is sufficient. No goal rewrite needed.

### Accepted Override — Decision Coverage (§13a)

The decision-coverage gate found **8 CONTEXT decisions without literal `D-NN:` citations on a planned surface**: `D-120`, `D-126`, `D-128`, `D-129`, `D-130`, `D-131`, `D-133`, `D-134`. Each is **implemented and verified in code** (e.g. D-120 `/listings/{id}/apply` dedicated page; D-126 per-listing draft persistence; D-128 eight-value guided transitions; D-129 ok-artefact picker on `applied`; D-130 `applied_at` stamped by the transition; D-131 same-transaction event append; D-133 stage/needs-action/search slice; D-134 inline expandable history timeline). The gap is **citation-only, not missing behaviour**. The user accepted this override on **2026-10-06** and re-confirmed it on **2026-10-12** ("proceed anyway"). Recorded here so it is **not** re-treated as unplanned work. (Note: `D-130` does appear cited in `07-01-PLAN.md`; it is retained in the override list as given.)

## Gaps Summary

**No blocking gaps.** The prior verification's two human-verification truths are now resolved: **G-07-6** (the tracker rendered-rect geometry) was performed by the user on 2026-10-12 and **passed**, and **G-07-7** (live drafting) was performed, **failed**, and was **explicitly accepted by the user as a documented known limitation** and deferred. Both are recorded above — G-07-6 as VERIFIED, G-07-7 (and the downstream clipboard backstop) as **PASSED (override)** with the user's decision and its provenance.

This was a digest refresh: no PLAN, SUMMARY or implementation file changed since the prior verification (only `07-UAT.md`, `07-REVIEW.md` and `deferred-items.md` were written). Every must-have was re-checked against the current tree: the code claims hold, the 11 phase lanes pass (135 tests), the full default lane is green (1708 passed, 14 deselected, 2 xfailed), and the stylesheet byte-identity guard runs and passes. All 7 requirement IDs are satisfied. The phase's functional goal is achieved.

One **non-blocking WARNING (WR-02)** survives from the 07-14 fix: `unwrap_single_key_mapping` bounds only the direct self-reference, so a two-node mutual `{"item": …}` cycle loops (reproduced, exit 124) while its docstring claims self-reference "cannot hang". It is not wire-reachable (JSON-derived payloads cannot be cyclic) and therefore does not gate this phase, but the review's visited-identity fix is recommended as a follow-up to make the prose honest (CONVENTIONS rule 6).

---

_Verified: 2026-10-12T15:36:07Z_
_Verifier: the agent (gsd-verifier)_
