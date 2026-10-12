---
phase: 06-tailoring-verification
verified: 2026-10-12T22:45:22Z
status: human_needed
score: 17/18 must-haves verified
covered_files:
  - .planning/REQUIREMENTS.md
  - .planning/phases/06-tailoring-verification/06-01-PLAN.md
  - .planning/phases/06-tailoring-verification/06-01-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-02-PLAN.md
  - .planning/phases/06-tailoring-verification/06-02-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-03-PLAN.md
  - .planning/phases/06-tailoring-verification/06-03-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-04-PLAN.md
  - .planning/phases/06-tailoring-verification/06-04-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-05-PLAN.md
  - .planning/phases/06-tailoring-verification/06-05-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-06-PLAN.md
  - .planning/phases/06-tailoring-verification/06-06-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-07-PLAN.md
  - .planning/phases/06-tailoring-verification/06-07-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-08-PLAN.md
  - .planning/phases/06-tailoring-verification/06-08-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-09-PLAN.md
  - .planning/phases/06-tailoring-verification/06-09-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-10-PLAN.md
  - .planning/phases/06-tailoring-verification/06-10-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-11-PLAN.md
  - .planning/phases/06-tailoring-verification/06-11-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-CONTEXT.md
  - .planning/phases/06-tailoring-verification/06-DISCUSSION-LOG.md
  - .planning/phases/06-tailoring-verification/06-PATTERNS.md
  - .planning/phases/06-tailoring-verification/06-RESEARCH.md
  - .planning/phases/06-tailoring-verification/06-REVIEW.md
  - .planning/phases/06-tailoring-verification/06-SECURITY.md
  - .planning/phases/06-tailoring-verification/06-UAT.md
  - .planning/phases/06-tailoring-verification/06-UI-REVIEW.md
  - .planning/phases/06-tailoring-verification/06-VALIDATION.md
  - app/api/tailoring.py
  - app/db/repositories/cv_artifact_repo.py
  - app/domain/cv.py
  - app/domain/schemas/_coerce.py
  - app/pipeline/tailor.py
  - app/verify/__init__.py
  - app/verify/base.py
  - app/verify/grounding.py
  - app/verify/numbers.py
  - app/verify/plan_checks.py
  - app/verify/text_checks.py
  - app/web/templates/html/_cv_findings.html
  - app/web/templates/html/_tailoring_review.html
  - app/web/templates/html/tailoring.html
  - tests/api/test_cv_pdf_route.py
  - tests/api/test_tailoring_generate.py
  - tests/api/test_tailoring_review.py
  - tests/domain/test_coerce.py
  - tests/domain/test_patch_ops.py
  - tests/fixtures/verify/digit_bearing_header_extract.txt
  - tests/fixtures/verify/identical_dates_extract.txt
  - tests/fixtures/verify/org_first_bullet_extract.txt
  - tests/fixtures/verify/org_first_merge_extract.txt
  - tests/fixtures/verify/org_title_collision_extract.txt
  - tests/fixtures/verify/org_title_dates_collision_extract.txt
  - tests/fixtures/verify/org_title_dates_merge_extract.txt
  - tests/pipeline/test_tailor_stage.py
  - tests/verify/fixtures.py
  - tests/verify/test_block_no_repair.py
  - tests/verify/test_grounding.py
  - tests/verify/test_no_free_text_path.py
  - tests/verify/test_numbers.py
  - tests/verify/test_plan_checks.py
  - tests/verify/test_text_checks.py
covered_digest: "v1:sha256:603eb1b7ec9cfd6669ed562cad227f53148c732e3d58bc97da2ff8cb98ae8f79"
behavior_unverified: 1
overrides_applied: 0
requirements_verified:
  - TAIL-01
  - TAIL-02
  - TAIL-03
  - TAIL-04
  - TAIL-05
  - TAIL-06
  - TAIL-07
  - TAIL-08
  - UI-05
re_verification:
  previous_status: human_needed
  previous_score: 17/18
  gaps_closed: []
  gaps_remaining:
    - "Real-engine tailored compile (truth 17 / 06-UAT.md test 1) — still pending; Tectonic is absent on this host by design (D-69)."
    - "Fail-vs-warn legibility and block-as-outcome (06-UAT.md test 2) — still pending; visual/UX, not settlable by grep or the hermetic suite."
  regressions: []
truths:
  - id: 1
    truth: "Generate produces exactly one typed patch from exactly one structured call, one audit row, and no artifact/.tex/PDF."
    status: pass
    evidence: "app/pipeline/tailor.py:217-256 (unchanged since the prior verification); tests/pipeline/test_tailor_stage.py green on this tree."
  - id: 2
    truth: "Apply-tailoring is a typed patch over enumerated IDs, all-or-nothing, no free-text field on the PDF path, bullet text byte-immutable."
    status: pass
    evidence: >-
      app/domain/cv.py:401-441 (typed Literal ops) and apply_patch's Bullet-carrying path
      (:578,691-713,758-786) are unchanged in substance. Phase 7 added `mode="before"`
      coercion validators to `TailoringPatch.ops`/`.gaps`/`.suggestions` and to
      `Suggestion.evidence_ids`/`GapFinding.evidence_ids` (all list-shape normalisation via
      app/domain/schemas/_coerce.py); no field was added and no text field was introduced, so
      the no-free-text-on-the-PDF-path invariant is intact. Canary
      tests/verify/test_no_free_text_path.py green; tests/domain/test_patch_ops.py green.
  - id: 3
    truth: "User can preview the tailored CV and its change log before compiling; dropped items are listed with a reason."
    status: pass
    evidence: >-
      app/web/templates/html/_tailoring_review.html:21-44 (HTML preview of the final order
      BESIDE the change log; each dropped bullet rendered `<s>` with its reason);
      app/api/tailoring.py review route; tests/api/test_tailoring_review.py green.
  - id: 4
    truth: "The verification gate implements its checks with the correct severities (metric_containment can hard-fail; page_budget/layout_ats warn-only)."
    status: pass
    evidence: "app/verify/text_checks.py:84-116 (metric_containment -> _fail/_warn), :134-143 (page_budget _warn only), :146-169 (layout_ats _warn only); tests/verify/test_text_checks.py green."
  - id: 5
    truth: "Digit-bearing entry locations (Dublin 2, Eircode, Remote (GMT+1)) do not false-fail check 4."
    status: pass
    evidence: "app/verify/numbers.py:199-200 folds location into allowed (file byte-identical to the prior verification); test_a_digit_bearing_location_is_not_a_surplus_candidate green."
  - id: 6
    truth: "Check 4 does not false-fail a valid CV when an earlier entry's bullet names a later entry's org AND title (including the org-FIRST prefix-collision and extractor-merge shapes)."
    status: pass
    evidence: >-
      Separator conjunct at app/verify/numbers.py:219 (`dash_lines[index].startswith(org_dash + '-')`)
      with `_dash_fold` at :69-82. Independent repro at HEAD: shape 1 (bullet `Acme Senior Engineer
      2019-01 -- 2019-12 cut 5 incidents`) -> `pass`; shape 2 (merge `Acme Senior Engineer contract --
      delivered 5 projects Acme --- Senior Engineer`) -> `warn ['exp/acme-2019']` with A excluded.
      Negative control (fabricated `99` in A's own region) still `fail ['exp/globex-2018:99']`. Pinned by
      test_a_bullet_opening_with_a_later_org_title_and_dates_does_not_anchor_its_region,
      test_a_merged_line_opening_with_a_later_org_title_and_dates_is_reported_not_found,
      test_the_separator_gate_does_not_weaken_a_fabricated_digit_in_the_earlier_region, and the
      parametrized prefix-collision property test (tests/verify/test_numbers.py green).
  - id: 7
    truth: "Check 4 does not silently skip an unanchorable region (no fabricated-digit false negative)."
    status: pass
    evidence: "app/verify/text_checks.py:93-116 collects `unanchored` and returns `_warn` naming the entry with fail precedence; independent repro (empty title + fabricated 99) returns `warn offending=['exp/acme-2019']`."
  - id: 8
    truth: "A CV that fails verification is blocked (not downloadable), and no code path auto-repairs it."
    status: pass
    evidence: "app/pipeline/tailor.py:308 ('deliberately no repair path'); app/api/tailoring.py serves only `ok_only=True` (app/db/repositories/cv_artifact_repo.py:173,191); tests/verify/test_block_no_repair.py green."
  - id: 9
    truth: "The verified CV PDF can be previewed inline and downloaded (?download=1); no served path is built from request text."
    status: pass
    evidence: >-
      app/api/tailoring.py:648-690 — without `?artifact_id=` the newest `ok` artifact is served;
      with it, the named artifact is served only when it is `ok` AND `record.listing_id == listing_id`
      (ownership recheck added by phase 7). Selection is `ok_only=True` in SQL
      (cv_artifact_repo.py:173,191); the served path is the STORED `pdf_path`, never request text; the
      download filename is integer-derived. The UI download affordance now exists on the apply page
      (`app/web/templates/html/apply.html:51`, `?download=1`) as well as inline on the tailoring page
      (`tailoring.html:72,93`). tests/api/test_cv_pdf_route.py green.
  - id: 10
    truth: "The four bullet ops and ReorderSection.section_id ground ids against their id sets, raising UnknownIdError on a non-family id."
    status: pass
    evidence: "app/domain/cv.py; tests/domain/test_patch_ops.py green."
  - id: 11
    truth: "Compile route honours tailoring_enabled=False with 409 tailoring_disabled before load_facts."
    status: pass
    evidence: "app/api/tailoring.py:588-589 (guard) precedes :602-607 (load_facts); tests/api/test_tailoring_review.py green."
  - id: 12
    truth: "A raised complete_structured transport error writes exactly one purpose=tailor status=error row, releases the in-flight slot, and surfaces as a typed 502."
    status: pass
    evidence: "app/pipeline/tailor.py:225,244-277 (audit row + `finally` release; returns None); app/api/tailoring.py:504-509 returns the 502 `tailoring_failed` fragment; tests green."
  - id: 13
    truth: "Region start is an org-first + org/title-separator structural boundary: `_entry_lines` requires `startswith(org_needle)`, title presence, the dash separator, and date adjacency."
    status: pass
    evidence: "app/verify/numbers.py:214-226 (`:217` org-first, `:219` separator conjunct, `:221-223` date adjacency); `_dash_fold` `:69-82` keeps one `-` per dash run. Independent repro: a no-separator org-first bullet is rejected."
  - id: 14
    truth: "The region-end bound ends an anchored region by containment against a later unanchored entry's org/title/date-range, never below its own header, with the anchored entry's own date line excluded by line position."
    status: pass
    evidence: "app/verify/numbers.py:361-400. Merged / digit-bearing / identical-date shapes return `warn`; own-content shapes still `fail ['exp/acme-2018:99']`."
  - id: 15
    truth: "The numbers.py prose makes no claim the code does not deliver: the residual is stated honestly and fail-closed."
    status: pass
    evidence: >-
      numbers.py:169-183 states the full-header reproduction IS taken as the region start (a surplus
      digit there is a hard `fail`, not a warn); the gate is per-entry MONOTONE (a dropped/normalised
      separator degrades to `found=False` + visible `warn`, never a silent skip); and it is "not ... a
      global no-false-fail guarantee". Independently reproduced: full-header bullet ->
      `fail ['exp/acme-2019:99']`; real header without separator -> `warn ['exp/acme-2018']`; grep for the
      old false-guarantee phrases ('warn instead', 'limits a neighbour', 'cannot carry', 'impossible') ->
      no match. Ceiling pinned by test_a_bullet_reproducing_a_full_header_is_the_documented_hard_fail_ceiling.
  - id: 16
    truth: "VERIFIER_VERSION is a single 1.0.5 bump and phase 6's work introduces no persisted shape change."
    status: pass
    evidence: >-
      app/verify/base.py:22 `VERIFIER_VERSION = '1.0.5'`; `grep -rn '1.0.[0-4]' app tests` against
      verifier source -> no match (only stale `.pyc` binaries). No phase-6 commit touches an alembic
      path; the repo head is now `0007_screening_draft_warnings.py` (added by phase 7, unrelated to
      this phase). The prior report's "head is 0005" was a snapshot of that moment, not a phase-6
      claim — restated here against the current head.
  - id: 17
    truth: "A tailored RenderPlan compiles through the real pinned Tectonic engine and its extracted pypdf text passes the real Layer-2 checks."
    status: present_behavior_unverified
    evidence: "Real path present and wired (app/pipeline/tailor.py); no test in this environment exercises the real engine/extraction (Tectonic absent by design D-69). See behavior_unverified_items."
  - id: 18
    truth: "The round-5 gap-closure changed set was exactly the five declared paths (two modules, two fixtures, one test file)."
    status: pass
    evidence: "`git diff --name-status da06178~1..5a667ec` -> app/verify/base.py (M), app/verify/numbers.py (M), tests/verify/test_numbers.py (M), tests/fixtures/verify/org_first_bullet_extract.txt (A), tests/fixtures/verify/org_first_merge_extract.txt (A). Matches 06-REVIEW.md files_reviewed_list."
gaps: []
advisory: []
behavior_unverified_items:
  - truth: "A tailored RenderPlan compiles through the real pinned Tectonic engine and its extracted pypdf text passes the real Layer-2 checks."
    test: "In the container (`docker compose run --rm app pytest -m latex`, or generate + compile a scored listing), compile a tailored plan with the real engine and confirm a PDF plus a passing merged verification_json."
    expected: "A real PDF is produced and the merged VerificationResult passes (or reports only warn-tier checks)."
    why_human: >-
      Tectonic is absent from this host by design (D-69); the hermetic lane overrides the engine with a
      stub writing a canned PDF and monkeypatches `extract_pdf_text` to a committed fixture. Presence and
      wiring of the real path are verified by code reading (app/pipeline/tailor.py), but no test in this
      environment exercises the real engine/extraction behaviour on a tailored plan.
coincidental_reliance_items: []
human_verification:
  - test: "Real-engine tailored compile"
    expected: "In the container (`docker compose run --rm app pytest -m latex`, or generate + compile a scored listing), a real PDF is produced and the persisted merged `verification_json` passes (or reports only warn-tier checks)."
    why_human: "Tectonic is absent on this host by design (D-69); the hermetic lane stubs the engine and extraction."
  - test: "Fail-vs-warn legibility and block-as-outcome"
    expected: "Open the tailoring review and a blocked state; a failing check is visually distinct from a warning, and the block reads as a reviewable outcome with a clear recovery."
    why_human: "Visual/UX behaviour cannot be settled by grep or the hermetic suite."
---

# Phase 6: Tailoring + Verification — Verification Report

**Phase Goal:** A tailored, verified CV PDF the user can preview and download — shipped with its verification gate, never before it.
**Verified:** 2026-10-12T22:45:22Z
**Status:** human_needed
**Re-verification:** Yes — digest refresh after Phase 7 (`assisted-apply-tracker`) closed and touched shared files on Phase 6's surface

**MVP-mode note:** ROADMAP.md marks Phase 6 `mode: mvp`, but the ROADMAP goal text is not in
user-story form. A valid story was obtained from the plan objective: *"As a job seeker working a
ranked queue, I want to turn one listing into a CV tailored to it, so that I can apply with a CV
shaped to that job without risking a claim I cannot stand behind."* User Flow Coverage uses that
outcome clause.

## Scope of this re-verification

`verification.status` reported this phase `stale`: the prior report's `covered_files` digest no
longer matched the tree. **No phase-6 PLAN or SUMMARY changed** — the drift came entirely from
Phase 7 work that landed afterwards and touched files Phase 6's report had covered. The drift-
exposed files on Phase 6's own surface are:

| File | Phase 7 change | Phase-6 must-have it touches | Re-check |
| ---- | -------------- | ---------------------------- | -------- |
| `app/domain/cv.py` | `mode="before"` list coercion validators on `TailoringPatch.ops`/`.gaps`/`.suggestions` and the two `evidence_ids` fields | truths 2, 10 | No field added; no free-text path introduced; canary + patch-op tests green |
| `app/domain/schemas/_coerce.py` | new shared helper; `unwrap_single_key_mapping` restricted to the literal `WRAPPER_KEY = "item"` and bounded | truth 2 | Pure stdlib, `app/domain` import-discipline test green; `coerce_mapping_list` returns an unrecognised single-key mapping as ONE item, refused by the discriminated union's `extra="forbid"` |
| `app/api/tailoring.py` | PDF route gained `?artifact_id=` selection with an ownership recheck; the compile fragment no longer emits its own download anchor | truths 3, 8, 9, 11, 12 | `ok_only=True` retained in SQL; stored `pdf_path` still the served path; ownership recheck added; 409/502 fragments unchanged |
| `app/web/templates/html/tailoring.html` | persistent "Latest CV" section + per-history `?artifact_id=` links | truths 3, 9 | Single download affordance per artifact; review fragment unchanged |

All 11 plans (`06-01`..`06-11`) still have PLAN+SUMMARY pairs and are byte-identical to the prior
verification. Git state: HEAD `1cf8d8b`; the prior verification was at `5a667ec`. The four shared
files above are the only Phase 6 covered files Phase 7 changed (plus `.planning/REQUIREMENTS.md`
and the phase-6 `06-REVIEW.md`/`06-UAT.md` artifacts, both re-read here).

**Phase 7 items noted but out of scope** (per instruction): the accepted `Draft answers` known
limitation (`G-07-7`, a screening-draft path, not tailoring) and the non-blocking WR-02 two-node
`{"item": …}` cycle in `unwrap_single_key_mapping`. WR-02 is unreachable from Phase 6's path — the
patch arrives as JSON (which cannot express a reference cycle) or is constructed in Python by the
pipeline — so it does not affect any Phase 6 must-have.

## User Flow Coverage

| Step | Expected | Evidence in codebase | Status |
| ---- | -------- | -------------------- | ------ |
| Outcome clause: apply without risking an unsupported claim | Gate blocks fabrication; valid CVs verify and are previewable/downloadable | Canary `tests/verify/test_no_free_text_path.py`; ok-only download predicate `app/db/repositories/cv_artifact_repo.py:173,191`; `check_metric_containment` with the org-first + separator anchor (numbers.py:214-226) | ✓ VERIFIED |
| Open page → generate → review → compile → download | Each step reachable with the tailoring gate | app/api/tailoring.py routes; `_tailoring_review.html`; `tailoring.html`; tests/api/test_tailoring_review.py, test_cv_pdf_route.py green | ✓ VERIFIED |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | One typed patch from one structured call, one audit row, no artifact | ✓ VERIFIED | `app/pipeline/tailor.py:217-256`; `tests/pipeline/test_tailor_stage.py` green |
| 2 | Typed patch over enumerated IDs, no free-text on PDF path, bullets immutable | ✓ VERIFIED | `app/domain/cv.py:401-441,578,691-713`; phase-7 coercion adds no text field; canary green |
| 3 | Preview + change log before compiling; drops listed with a reason | ✓ VERIFIED | `_tailoring_review.html:21-44`; `tests/api/test_tailoring_review.py` |
| 4 | Gate checks with correct severities (metric_containment can fail; 8/9 warn-only) | ✓ VERIFIED | `app/verify/text_checks.py:84-169` |
| 5 | Digit-bearing locations do not false-fail check 4 | ✓ VERIFIED | `app/verify/numbers.py:199-200`; test green |
| 6 | Check 4 does not false-fail a valid CV when an earlier bullet names a later entry's org + title (incl. org-first + merge shapes) | ✓ VERIFIED | Separator conjunct `numbers.py:219`; repro shape 1 `pass`, shape 2 `warn ['exp/acme-2019']`; control `fail ['exp/globex-2018:99']` |
| 7 | Check 4 does not silently skip an unanchorable region | ✓ VERIFIED | `app/verify/text_checks.py:93-116`; repro `warn ['exp/acme-2019']` |
| 8 | Failing CV blocked (not downloadable); no auto-repair | ✓ VERIFIED | `app/pipeline/tailor.py:308`; `ok_only=True` at `app/api/tailoring.py` + `cv_artifact_repo.py:173,191` |
| 9 | Preview inline + `?download=1`; path never built from request text | ✓ VERIFIED | `app/api/tailoring.py:648-690`; `tests/api/test_cv_pdf_route.py` |
| 10 | Four bullet ops + `ReorderSection.section_id` grounded → `UnknownIdError` | ✓ VERIFIED | `app/domain/cv.py`; `tests/domain/test_patch_ops.py` |
| 11 | Compile route honours `tailoring_enabled=False` with 409 before `load_facts` | ✓ VERIFIED | `app/api/tailoring.py:588-589` vs `:602-607`; review tests |
| 12 | Transport error → one `purpose=tailor`,`status=error` row, slot released, typed 502 | ✓ VERIFIED | `app/pipeline/tailor.py:225,244-277`; `app/api/tailoring.py:504-509` |
| 13 | Org-first + separator + title + date-adjacency region start (`_dash_fold`) | ✓ VERIFIED | `app/verify/numbers.py:69-82,214-226`; no-separator bullet rejected |
| 14 | Region-end containment bound, never below header, own date line positional | ✓ VERIFIED | `app/verify/numbers.py:361-400`; merged/digit-header/identical-date → `warn`; own-content → `fail` |
| 15 | No false guarantee in prose; residual honest and fail-closed | ✓ VERIFIED | `numbers.py:169-183`; repro full-header `fail`, dropped-separator header `warn`; no false-guarantee phrase remains |
| 16 | `VERIFIER_VERSION` single `1.0.5` bump; phase 6 adds no migration | ✓ VERIFIED | `app/verify/base.py:22`; `grep` clean; repo head `0007` is phase 7's, no phase-6 alembic path |
| 17 | Real Tectonic engine compiles a tailored plan; extracted text passes real Layer-2 | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Path wired; Tectonic absent by design (D-69) — `behavior_unverified_items` |
| 18 | Round-5 gap-closure changed set is exactly the five declared paths | ✓ VERIFIED | `git diff --name-status da06178~1..5a667ec` → 5 paths; matches `06-REVIEW.md` |

**Score:** 17/18 truths verified (0 failed; 1 present, behavior-unverified: truth 17).

### Cross-Phase Note (was a deferred item)

The attach half of TAIL-05 — "a failed CV cannot be **attached** to an application" — was deferred
to Phase 7 at the prior verification. Phase 7 has since shipped and closed it: `application_repo.
record_application` resolves the CV link through `cv_artifact_repo.read_for_download(ok_only=True)`
(`app/db/repositories/application_repo.py:19-22,463-479`), verified in
`.planning/phases/07-assisted-apply-tracker/07-VERIFICATION.md` (SC3). The item is therefore no
longer deferred — TAIL-05 is fully satisfied across the milestone.

### Advisory (New Scope, Unevidenced)

None. This re-verification surfaced no new-scope finding: the phase-7 shared-file edits were
already reviewed and accepted, and this pass confirmed they add no field and no free-text path to
Phase 6's surface.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/verify/numbers.py` | Org-first + separator region start; region-end bound; honest residual | ✓ VERIFIED | `_dash_fold` `:69-82`; separator conjunct `:219`; bound `:361-400`; residual `:169-183` |
| `app/verify/base.py` | `VERIFIER_VERSION == "1.0.5"` | ✓ VERIFIED | `:22`; no `1.0.[0-4]` in app/tests |
| `app/verify/text_checks.py` | Fail-closed visible `warn` for unanchorable region; fail precedence | ✓ VERIFIED | `:93-116` |
| `app/api/tailoring.py` | Four routes; ok-only selection; typed refusals; no request-text path | ✓ VERIFIED | generate/review/compile/pdf routes; `?artifact_id=` with ownership recheck |
| `app/db/repositories/cv_artifact_repo.py` | SQL-level `ok` predicate on both selectors | ✓ VERIFIED | `latest_for_listing` `:173`; `read_for_download` `:191` |
| `app/domain/cv.py` | Typed patch ops; bullet-immutable `apply_patch` | ✓ VERIFIED | Ops union + `apply_patch`; phase-7 coercion adds no text field |
| `app/domain/schemas/_coerce.py` | Shared list-shape helper; bounded, literal-key unwrap | ✓ VERIFIED | `WRAPPER_KEY = "item"` `:25`; loop bounded `:38-45` |
| `app/web/templates/html/_tailoring_review.html` | Preview + change log + drop reasons + guard fields | ✓ VERIFIED | `:21-44`, `:78-80` |
| `tests/fixtures/verify/org_first_bullet_extract.txt` | Shape-1 literal repro string | ✓ VERIFIED | committed (tracked) |
| `tests/fixtures/verify/org_first_merge_extract.txt` | Shape-2 merged repro string | ✓ VERIFIED | committed (tracked) |
| `tests/verify/test_numbers.py` | Literal, merge, negative-control, prefix-collision property, ceiling tests | ✓ VERIFIED | T1–T4 + ceiling tests; `tests/verify` 97 passed |
| Migration | none from phase-6 work | ✓ VERIFIED | No phase-6 commit touches an alembic path; head `0007` is phase 7's |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `cv.tex.jinja:61` (ORG --- TITLE) | `_entry_lines` separator conjunct | `dash_lines[index].startswith(org_dash + '-')` | WIRED | `app/verify/numbers.py:219`; org-first bullet rejected, real header accepted |
| later unanchored entry org/title/date-range | region-end bound | containment `any(needle in line ...)` | WIRED | `app/verify/numbers.py:361-400`; merged/digit-header/identical-date → `warn` |
| `region_token_report` `found=False` | `check_metric_containment` warn | explicit `unanchored` collection | WIRED | `app/verify/text_checks.py:93-116` |
| `GET /listings/{id}/cv/pdf?artifact_id=` | `read_for_download(ok_only=True)` + ownership check | SQL predicate + `record.listing_id == listing_id` | WIRED | `app/api/tailoring.py:648-690`; `cv_artifact_repo.py:191` |
| `latest_for_listing(ok_only=True)` | download route (no selector) | SQL `compile_status == "ok"` | WIRED | `cv_artifact_repo.py:173`; `app/api/tailoring.py:673-676` |
| `application_repo.record_application` | exact-CV link | `read_for_download(ok_only=True)` | WIRED | `app/db/repositories/application_repo.py:463-479` (phase-7 cross-phase contract) |
| `VERIFIER_VERSION` | `VerificationResult.verifier_version` → persisted `verification_json` | `base.py:22,50` | WIRED | 1.0.5 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| check-4 region report | `RegionReport.candidates` / `.allowed` | `region_token_report(plan, extracted_text)` | Yes — real extraction (fixture in hermetic lane) | ✓ FLOWING |
| `check_metric_containment` outcome | `CheckResult.status` / `.offending` | region reports + allowed sets | Yes | ✓ FLOWING |
| download | `record.pdf_path` | `ok_only=True` SQL selection | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Phase-6 core lanes | `/tmp/opencode/gsdvenv13/bin/python -m pytest -q tests/verify tests/domain/test_patch_ops.py tests/domain/test_coerce.py tests/api/test_tailoring_review.py tests/api/test_tailoring_generate.py tests/api/test_cv_pdf_route.py` | `204 passed in 62.61s` | ✓ PASS |
| Tailor stage + Layer-1/grounding + stylesheet | `/tmp/opencode/gsdvenv13/bin/python -m pytest -q tests/pipeline/test_tailor_stage.py tests/verify/test_grounding.py tests/verify/test_plan_checks.py tests/test_stylesheet_coverage.py` | `38 passed in 20.02s` | ✓ PASS |
| Full hermetic suite | `/tmp/opencode/gsdvenv13/bin/python -m pytest -q` | see note below | ✓ PASS |
| Truth 6 shape 1 — org-first bullet, no separator | independent repro | `found [True, True]`, `pass` | ✓ PASS |
| Truth 6 shape 2 — merge beginning with later org | independent repro | `found [True, False]`, `warn ['exp/acme-2019']` | ✓ PASS |
| Truth 6 negative control — fabricated `99` in A's own region | independent repro | `fail ['exp/globex-2018:99']` | ✓ PASS |
| Truth 15 ceiling — full-header reproduction | independent repro | `fail ['exp/acme-2019:99']` (documented hard fail) | ✓ PASS |
| Truth 15 — real header loses separator | independent repro | `found=False`, `warn ['exp/acme-2018']` | ✓ PASS |
| Real-engine latex lane | `pytest -m latex` | cannot run on host — Tectonic absent (D-69) | ? SKIP |

`tests/verify` alone: **97 passed**. Targeted Phase-6 lanes total **242 passed** on this tree.

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes and no PLAN-declared probes exist for this phase. Step 7c: NOT APPLICABLE.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| TAIL-01 | 06-01, 06-07, 06-09 | Generate a CV tailored to a specific listing | ✓ SATISFIED | one call → one patch; generate route; off-switch guard; typed 502 |
| TAIL-02 | 06-01, 06-09 | Typed patch over enumerated IDs, no free-text on the PDF path | ✓ SATISFIED | schema + canary + raised-error audit row; phase-7 coercion adds no text field |
| TAIL-03 | 06-01 | Never rewrites/invents claims; bullet text immutable | ✓ SATISFIED | carried-through `Bullet` objects; canary test |
| TAIL-04 | 06-02, 06-05, 06-08, 06-10, 06-11 | Verification gate checks the compiled PDF for unsupported content | ✓ SATISFIED | org-first + separator anchor (truths 6/13), region-end bound (truth 14), fail-closed warn (truth 7), honest residual (truth 15); `tests/verify` 97 passed |
| TAIL-05 | 06-04 (+ Phase 7 for attach) | Failed CV blocked; cannot be downloaded or attached | ✓ SATISFIED | download: `ok_only=True` SQL + route (phase 6); attach: `application_repo.record_application` ok-only gate (phase 7, verified in 07-VERIFICATION.md) |
| TAIL-06 | 06-02, 06-03 | Verification never auto-repairs — it blocks | ✓ SATISFIED | no repair branch (`tailor.py:308`); tests |
| TAIL-07 | 06-03 | Review the tailored CV and change log before compiling | ✓ SATISFIED | review route/template; guard; tests |
| TAIL-08 | 06-03, 06-06 | Anything dropped is listed explicitly with a reason | ✓ SATISFIED | `dropped_bullets` struck + reason; phantom-change path closed |
| UI-05 | 06-04, 06-07 | Preview and download the tailored CV PDF | ✓ SATISFIED | inline preview + `?download=1` route; UI download affordance on the apply page (`apply.html:51`) and inline links on `tailoring.html`; tests |

All 9 phase requirement IDs appear in at least one plan's `requirements:` field. No ORPHANED
requirements. `REQUIREMENTS.md`'s `TAIL-*` traceability marks may now be set to Complete; the
attach half of TAIL-05 shipped in Phase 7.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/verify/numbers.py` | 169-183 | Documented hard-fail ceiling: a bullet reproducing the FULL header still anchors and hard-fails (structurally irreducible at line granularity) | ℹ️ Info (scoped, fail-closed) | A contrived bullet that literally opens `<org> --- <title> <dates>` can block a valid CV; documented and fail-closed, not a false pass |
| `tests/verify/test_numbers.py` | 10,524,578,686 | Pre-existing `ruff` I001/E501 style errors on lines untouched by this work | ℹ️ Info | Cosmetic; not introduced by the gap closure |
| `app/web/templates/html/tailoring.html` | 43 | Nested duplicate `id="tailoring-review"` when a persisted draft is present (outer div + `_tailoring_review.html:17`) | ⚠️ Warning (pre-existing, UI-REVIEW) | htmx resolves the first match (the outer div) so swaps still land; a markup-hygiene defect, not a truth failure. Carried by `06-UI-REVIEW.md` and human-verification item 2 |

No `TBD`/`FIXME`/`XXX` debt markers were found in the phase's covered files. **No blocking check was
weakened** — `metric_containment` still hard-fails an anchored surplus; `page_budget`/`layout_ats`
remain the only warn-only checks; a warn never blocks. **No new dependency added.** **No phase-6
commit touches an Alembic path.**

### Human Verification Required

1. **Real-engine tailored compile** — In the container (`docker compose run --rm app pytest -m latex`,
   or generate + compile a scored listing), compile a tailored plan with the real pinned Tectonic
   engine; confirm a real PDF and the persisted merged `verification_json`. The hermetic lane stubs the
   engine and extraction (D-69).
2. **Fail-vs-warn legibility and block-as-outcome** — Open the tailoring review and the blocked state;
   confirm a failing check is visually distinct from a warning and that the block reads as a reviewable
   outcome with a clear recovery. (`06-UI-REVIEW.md` also flags that htmx does not swap non-2xx
   responses, so typed refusals may be invisible in the browser — worth confirming here.)

### Gaps Summary

No gaps. This pass is a digest refresh plus a genuine re-check of the must-haves on today's tree,
prompted by Phase 7's edits to shared files on Phase 6's surface. The two previously-failing truths
(6 and 15) remain closed — `app/verify/numbers.py` and `tests/verify/test_numbers.py` are
byte-identical to the prior verification, and their independent repros still hold. Truth 16 is
restated honestly: `VERIFIER_VERSION` is `1.0.5` and phase 6 adds no migration, but the repo's
Alembic head is now `0007` (phase 7's, unrelated) rather than the `0005` snapshot the prior report
recorded. Truth 18's round-5 diff range is re-confirmed as exactly the five declared paths.

The only open items are the two container-only checks above — the real Tectonic compile (truth 17,
present-and-wired but behavior-unexercised here) and fail-vs-warn legibility — which is why the
status is `human_needed`, not `passed`.

---

_Verified: 2026-10-12T22:45:22Z_
_Verifier: the agent (gsd-verifier)_
