---
phase: 06-tailoring-verification
verified: 2026-10-14T13:59:55Z
status: passed
score: 18/18 must-haves verified
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
covered_digest: "v1:sha256:058335ace762dfd435f7fd0a6a3543cd12d32b4178dc5677400726557d6c865d"
behavior_unverified: 0
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
  gaps_closed:
    - "Real-engine tailored compile (truth 17 / 06-UAT.md test 1) — CLOSED: the container ran `docker compose run --rm app pytest -m latex -q` → 10 passed (2026-10-13) on the real pinned Tectonic 0.17.0."
    - "Fail-vs-warn legibility and block-as-outcome (06-UAT.md test 2) — CLOSED: operator confirmed the blocked panel renders pass/warn/fail rows in green/amber/red, names offending ids, states the fresh-tailoring recovery, offers no corrective control and no download link (2026-10-14)."
  gaps_remaining: []
  regressions: []
truths:
  - id: 1
    truth: "Generate produces exactly one typed patch from exactly one structured call, one audit row, and no artifact/.tex/PDF."
    status: pass
    evidence: >-
      app/pipeline/tailor.py:196-287 (`tailor_listing`): one `backend.complete_structured`
      call (:250) and exactly one `llm_call_repo.record_llm_call(purpose="tailor", run_id=None)`
      on both the success (:260) and exception (:272) paths. Re-checked against the V2
      migration: the port signature is unchanged (app/llm/base.py:125-150) and the V2
      implementation validates client-side and returns the model in `result.data`
      (app/llm/opencode_server.py:984-1025). tests/pipeline/test_tailor_stage.py and
      tests/llm/test_v2_generate.py green.
  - id: 2
    truth: "Apply-tailoring is a typed patch over enumerated IDs, all-or-nothing, no free-text field on the PDF path, bullet text byte-immutable."
    status: pass
    evidence: >-
      app/domain/cv.py:417-462 (five typed ops, all `_Forbid`), :515-575 (TailoringPatch
      with only `listing_id`/`ops`/`gaps`/`suggestions`), :726+ (`_validate_patch`
      all-or-nothing). The V2-migration commits added only a schema-visible
      duplicate-target validator (:552-575 `_refuse_duplicate_targets`) and the
      `mode="before"` list-shape coercion validators (via app/domain/schemas/_coerce.py);
      no field was added and no text field was introduced, so the no-free-text-on-the-PDF-path
      invariant is intact. Canary tests/verify/test_no_free_text_path.py green;
      tests/domain/test_patch_ops.py green.
  - id: 3
    truth: "User can preview the tailored CV and its change log before compiling; dropped items are listed with a reason."
    status: pass
    evidence: >-
      app/web/templates/html/_tailoring_review.html:21-44 (HTML preview of the final
      order BESIDE the change log; each dropped bullet rendered `<s>` with its reason);
      app/api/tailoring.py review route; tests/api/test_tailoring_review.py green.
  - id: 4
    truth: "The verification gate implements its checks with the correct severities (metric_containment can hard-fail; page_budget/layout_ats warn-only)."
    status: pass
    evidence: "app/verify/text_checks.py:84-116 (metric_containment -> _fail/_warn), :134-143 (page_budget _warn only), :146-169 (layout_ats _warn only); `passed = all(status != 'fail')` at text_checks.py:212 and plan_checks.py:224; tests/verify/test_text_checks.py green."
  - id: 5
    truth: "Digit-bearing entry locations (Dublin 2, Eircode, Remote (GMT+1)) do not false-fail check 4."
    status: pass
    evidence: "app/verify/numbers.py:245-246 folds `entry.location` into `_allowed_for_entry` (CR-01); independent repro at HEAD: `check_metric_containment` -> `pass []`; test_a_digit_bearing_location_is_not_a_surplus_candidate green."
  - id: 6
    truth: "Check 4 does not false-fail a valid CV when an earlier entry's bullet names a later entry's org AND title (including the org-FIRST prefix-collision and extractor-merge shapes)."
    status: pass
    evidence: >-
      Separator conjunct at app/verify/numbers.py:219 (`dash_lines[index].startswith(org_dash + '-')`)
      with `_dash_fold` at :69-82. Independent repro at HEAD: shape 1 (bullet `Acme Senior
      Engineer 2019-01 -- 2019-12 cut 5 incidents`) -> `found [True, True]`, `pass []`;
      shape 2 (merge `... delivered 5 projects Acme --- Senior Engineer`) -> `warn
      ['exp/acme-2019']` with A excluded. Negative control (fabricated `99` in A's own
      region) still `fail ['exp/globex-2018:99']`. Pinned by
      test_a_bullet_opening_with_a_later_org_title_and_dates_does_not_anchor_its_region,
      test_a_merged_line_opening_with_a_later_org_title_and_dates_is_reported_not_found,
      test_the_separator_gate_does_not_weaken_a_fabricated_digit_in_the_earlier_region, and
      the parametrized prefix-collision property tests (tests/verify/test_numbers.py green).
  - id: 7
    truth: "Check 4 does not silently skip an unanchorable region (no fabricated-digit false negative)."
    status: pass
    evidence: "app/verify/text_checks.py:93-116 collects `unanchored` and returns `_warn` naming the entry with fail precedence; test_a_split_header_entry_is_reported_not_found_not_mislocated green."
  - id: 8
    truth: "A CV that fails verification is blocked (not downloadable), and no code path auto-repairs it."
    status: pass
    evidence: "app/pipeline/tailor.py:313-314 ('deliberately no repair path'), :354-366/:492-518 (blocked rows for Layer-1 and Layer-2 fails); app/api/tailoring.py:689-694 serves only `ok_only=True` (app/db/repositories/cv_artifact_repo.py:173,192) and re-checks ownership; tests/verify/test_block_no_repair.py green."
  - id: 9
    truth: "The verified CV PDF can be previewed inline and downloaded (?download=1); no served path is built from request text."
    status: pass
    evidence: >-
      app/api/tailoring.py:663-714 — without `?artifact_id=` the newest `ok` artifact is
      served; with it, the named artifact is served only when it is `ok` AND `record.listing_id
      == listing_id`. Selection is `ok_only=True` in SQL (cv_artifact_repo.py:173,192); the
      served path is the STORED `pdf_path`, never request text; the download filename is
      integer-derived. The UI download affordance exists inline on the tailoring page
      (`tailoring.html:72,93`). tests/api/test_cv_pdf_route.py green.
  - id: 10
    truth: "The four bullet ops and ReorderSection.section_id ground ids against their id sets, raising UnknownIdError on a non-family id."
    status: pass
    evidence: "app/domain/cv.py:726-756 (`_validate_patch` per-family grounding); tests/domain/test_patch_ops.py green."
  - id: 11
    truth: "Compile route honours tailoring_enabled=False with 409 tailoring_disabled before load_facts."
    status: pass
    evidence: "app/api/tailoring.py:604-605 (guard) precedes :618-623 (load_facts); tests/api/test_tailoring_review.py green."
  - id: 12
    truth: "A raised complete_structured transport error writes exactly one purpose=tailor status=error row, releases the in-flight slot, and surfaces as a typed 502."
    status: pass
    evidence: "app/pipeline/tailor.py:268-281 (audit row + class-name-only error; `finally` release :282-283); app/api/tailoring.py:507-512 returns the 502 `tailoring_failed` fragment. Pinned by test_generate_returns_a_typed_error_and_one_audit_row_when_the_backend_raises (WR-01)."
  - id: 13
    truth: "Region start is an org-first + org/title-separator structural boundary: `_entry_lines` requires `startswith(org_needle)`, title presence, the dash separator, and date adjacency."
    status: pass
    evidence: "app/verify/numbers.py:214-226 (`:217` org-first, `:219` separator conjunct, `:221-223` date adjacency); `_dash_fold` `:69-82` keeps one `-` per dash run (CR-02, tightened at da06178). Independent repro: a no-separator org-first bullet is rejected."
  - id: 14
    truth: "The region-end bound ends an anchored region by containment against a later unanchored entry's org/title/date-range, never below its own header, with the anchored entry's own date line excluded by line position."
    status: pass
    evidence: "app/verify/numbers.py:361-400. Merged / digit-bearing / identical-date shapes return `warn`; own-content shapes still `fail ['exp/globex-2018:99']`."
  - id: 15
    truth: "The numbers.py prose makes no claim the code does not deliver: the residual is stated honestly and fail-closed."
    status: pass
    evidence: >-
      numbers.py:169-183 states the full-header reproduction IS taken as the region start (a
      surplus digit there is a hard `fail`, not a warn); the gate is per-entry MONOTONE (a
      dropped/normalised separator degrades to `found=False` + visible `warn`, never a silent
      skip); and it is "not ... a global no-false-fail guarantee". Independently reproduced at
      HEAD: full-header repro -> `fail ['exp/B:99']`; grep for the old false-guarantee phrases
      -> no match. Ceiling pinned by test_a_bullet_reproducing_a_full_header_is_the_documented_hard_fail_ceiling.
  - id: 16
    truth: "VERIFIER_VERSION is a single 1.0.5 bump and phase 6's work introduces no persisted shape change."
    status: pass
    evidence: >-
      app/verify/base.py:22 `VERIFIER_VERSION = '1.0.5'`; `grep -rn '1.0.[0-4]' app/verify tests/verify`
      -> no match. No phase-6 commit touches an alembic path; the repo head is
      `0007_screening_draft_warnings.py` (added by phase 7, unrelated to this phase).
  - id: 17
    truth: "A tailored RenderPlan compiles through the real pinned Tectonic engine and its extracted pypdf text passes the real Layer-2 checks."
    status: pass
    evidence: >-
      CLOSED by 06-UAT.md test 1 (2026-10-13): in the container, `docker compose build`
      succeeded (Tectonic 0.17.0 SHA256 verified) then `docker compose run --rm app pytest -m
      latex -q` → 10 passed. The real-engine lane (tests/latex/test_fact_equivalence.py,
      tests/latex/test_compile.py; `apply_patch` → `render_plan_to_tex` → real Tectonic →
      real `extract_pdf_text`) exercises the engine and extraction on a rendered plan and
      asserts fact membership with a load-bearing floor. The tailored `compile_tailored` →
      `verify_text` orchestration is additionally pinned in the hermetic lane with a stubbed
      engine. The `-m latex` lane cannot run on this host (no LaTeX engine by design, D-69),
      so the container result is the real-engine evidence; it is committed in 06-UAT.md.
  - id: 18
    truth: "The round-5 gap-closure changed set was exactly the five declared paths (two modules, two fixtures, one test file)."
    status: pass
    evidence: "`git diff --name-status da06178~1..5a667ec` -> app/verify/base.py (M), app/verify/numbers.py (M), tests/verify/test_numbers.py (M), tests/fixtures/verify/org_first_bullet_extract.txt (A), tests/fixtures/verify/org_first_merge_extract.txt (A). Matches 06-REVIEW.md files_reviewed_list."
gaps: []
advisory: []
behavior_unverified_items: []
coincidental_reliance_items: []
---

# Phase 6: Tailoring + Verification — Verification Report

**Phase Goal:** A tailored, verified CV PDF the user can preview and download — shipped with its verification gate, never before it.
**Verified:** 2026-10-14T13:59:55Z
**Status:** passed
**Re-verification:** Yes — digest refresh + gap closure after Phase 7 (`assisted-apply-tracker`) and Phase 7.1 (`opencode-v2-migration`) touched shared files on Phase 6's surface, plus completion of the two outstanding human/UAT items.

**MVP-mode note:** ROADMAP.md marks Phase 6 `mode: mvp`, but the ROADMAP goal text is not in
user-story form. A valid story was obtained from the plan objective: *"As a job seeker working a
ranked queue, I want to turn one listing into a CV tailored to it, so that I can apply with a CV
shaped to that job without risking a claim I cannot stand behind."* User Flow Coverage uses that
outcome clause.

## Scope of this re-verification

The prior report (`2026-10-12T22:45:22Z`, `status: human_needed`, `17/18`) was stale: its
`covered_files` digest no longer matched the tree, and its one outstanding human item (the UAT)
has since been answered. `06-UAT.md` is now `status: complete` with **2/2 tests passing**.

Since the prior verification (HEAD `1cf8d8b`), the changes that touch Phase 6's own surface are:

| File | Change | Phase-6 must-have it touches | Re-check |
| ---- | ------ | ---------------------------- | -------- |
| `app/domain/cv.py` | `+25`: a `TailoringPatch` schema validator `_refuse_duplicate_targets` mirroring `_validate_patch` rule 2, so a duplicate-target reply is a retriable `ValidationError` (D-140) | truths 2, 10 | No field added; no free-text path introduced; `next_page_trim` excludes already-targeted bullets (`cv.py:713-722`) so the page-trim path cannot build a duplicate patch; patch-op tests green |
| `app/pipeline/tailor.py` | `+6`: three sentences stating the per-id exclusivity rule in `TAILOR_SYSTEM_PROMPT` | truth 1 | Constant-only prompt, no interpolation; one-call/one-row shape unchanged |
| `app/api/tailoring.py` | `+16`: `structlog` warning `tailoring.patch_refused` on the invalid-patch branch (observability only; response status/body byte-identical) | truths 3, 8, 11, 12 | `ok_only` selection, typed 409/502 fragments and no-repair branch unchanged |

Phase 7.1's migration to the opencode **V2** HTTP API (`app/llm/*`, `app/config.py`,
`app/db/models.py`) was re-checked against the LLM/tailoring call path. The `LLMBackend`
port signature is unchanged (`app/llm/base.py:125-150`), the V2 arm validates client-side and
returns the model in `result.data` (`app/llm/opencode_server.py:984-1025`), and `tailor_listing`
still makes one `complete_structured` call and writes exactly one `llm_calls` row per attempt.
`settings.opencode_model` (`app/config.py:59`) and `settings.tailoring_enabled` (:228) still
exist. `app/verify/*` is byte-identical to the prior verification — truths 4-7 and 13-16 are
re-confirmed against unchanged code.

Git state: branch `master`, tree clean, HEAD `9cca641`. All 11 plans (`06-01`..`06-11`) still
have PLAN+SUMMARY pairs and are byte-identical to the prior verification.

## User Flow Coverage

| Step | Expected | Evidence in codebase | Status |
| ---- | -------- | -------------------- | ------ |
| Outcome clause: apply without risking an unsupported claim | Gate blocks fabrication; valid CVs verify and are previewable/downloadable | Canary `tests/verify/test_no_free_text_path.py`; ok-only download predicate `app/db/repositories/cv_artifact_repo.py:173,192`; `check_metric_containment` with the org-first + separator anchor (numbers.py:214-226) | ✓ VERIFIED |
| Open page → generate → review → compile → download | Each step reachable with the tailoring gate | app/api/tailoring.py routes; `_tailoring_review.html`; `tailoring.html`; tests/api/test_tailoring_review.py, test_cv_pdf_route.py green | ✓ VERIFIED |
| Blocked CV reads as a reviewable outcome | Blocked panel names the failing checks, offers no corrective control and no download | `app/web/templates/html/_cv_findings.html`; `tailoring.html:77-79`; UAT test 2 (operator-confirmed, 2026-10-14) | ✓ VERIFIED |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | One typed patch from one structured call, one audit row, no artifact | ✓ VERIFIED | `app/pipeline/tailor.py:196-287`; V2 port unchanged; `tests/pipeline/test_tailor_stage.py`, `tests/llm/test_v2_generate.py` green |
| 2 | Typed patch over enumerated IDs, no free-text on PDF path, bullets immutable | ✓ VERIFIED | `app/domain/cv.py:417-575`; new duplicate-target validator adds no text field; canary green |
| 3 | Preview + change log before compiling; drops listed with a reason | ✓ VERIFIED | `_tailoring_review.html:21-44`; `tests/api/test_tailoring_review.py` |
| 4 | Gate checks with correct severities (metric_containment can fail; 8/9 warn-only) | ✓ VERIFIED | `app/verify/text_checks.py:84-169,212` |
| 5 | Digit-bearing locations do not false-fail check 4 | ✓ VERIFIED | `app/verify/numbers.py:245-246`; independent repro `pass []`; test green |
| 6 | Check 4 does not false-fail a valid CV when an earlier bullet names a later entry's org + title (incl. org-first + merge shapes) | ✓ VERIFIED | Separator conjunct `numbers.py:219`; repro shape 1 `pass`, shape 2 `warn ['exp/acme-2019']`; control `fail ['exp/globex-2018:99']` |
| 7 | Check 4 does not silently skip an unanchorable region | ✓ VERIFIED | `app/verify/text_checks.py:93-116` |
| 8 | Failing CV blocked (not downloadable); no auto-repair | ✓ VERIFIED | `app/pipeline/tailor.py:313-314,492-518`; `ok_only=True` at `cv_artifact_repo.py:173,192` |
| 9 | Preview inline + `?download=1`; path never built from request text | ✓ VERIFIED | `app/api/tailoring.py:663-714`; `tests/api/test_cv_pdf_route.py` |
| 10 | Four bullet ops + `ReorderSection.section_id` grounded → `UnknownIdError` | ✓ VERIFIED | `app/domain/cv.py:417-462,726-756`; `tests/domain/test_patch_ops.py` |
| 11 | Compile route honours `tailoring_enabled=False` with 409 before `load_facts` | ✓ VERIFIED | `app/api/tailoring.py:604-605` vs `:618-623`; review tests |
| 12 | Transport error → one `purpose=tailor`,`status=error` row, slot released, typed 502 | ✓ VERIFIED | `app/pipeline/tailor.py:268-283`; `app/api/tailoring.py:507-512`; WR-01 test |
| 13 | Org-first + separator + title + date-adjacency region start (`_dash_fold`) | ✓ VERIFIED | `app/verify/numbers.py:69-82,214-226` |
| 14 | Region-end containment bound, never below header, own date line positional | ✓ VERIFIED | `app/verify/numbers.py:361-400`; merged/digit-header/identical-date → `warn`; own-content → `fail` |
| 15 | No false guarantee in prose; residual honest and fail-closed | ✓ VERIFIED | `numbers.py:169-183`; repro full-header `fail ['exp/B:99']`; no false-guarantee phrase remains |
| 16 | `VERIFIER_VERSION` single `1.0.5` bump; phase 6 adds no migration | ✓ VERIFIED | `app/verify/base.py:22`; `grep` clean; head `0007` is phase 7's |
| 17 | Real Tectonic engine compiles a rendered/tailored plan; extracted text is verified | ✓ VERIFIED | 06-UAT.md test 1 (2026-10-13): container `pytest -m latex -q` → 10 passed; real lane = `tests/latex/*` |
| 18 | Round-5 gap-closure changed set is exactly the five declared paths | ✓ VERIFIED | `git diff --name-status da06178~1..5a667ec` → 5 paths; matches `06-REVIEW.md` |

**Score:** 18/18 truths verified (0 failed; 0 present, behavior-unverified).

### Cross-Phase Note (was a deferred item)

The attach half of TAIL-05 — "a failed CV cannot be **attached** to an application" — was deferred
to Phase 7 at the prior verification. Phase 7 shipped and closed it:
`application_repo.record_application` resolves the CV link through
`cv_artifact_repo.read_for_download(ok_only=True)` (`app/db/repositories/application_repo.py:465-466,532-533`),
verified in `.planning/phases/07-assisted-apply-tracker/07-VERIFICATION.md` (SC3). TAIL-05 is fully
satisfied across the milestone.

### Advisory (New Scope, Unevidenced)

None. This pass surfaced no new-scope finding: the phase-7.1 shared-file edits were already
reviewed and accepted, and this pass confirmed they add no field and no free-text path to Phase 6's
surface.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/verify/numbers.py` | Org-first + separator region start; region-end bound; honest residual | ✓ VERIFIED | `_dash_fold` `:69-82`; separator conjunct `:219`; bound `:361-400`; residual `:169-183` |
| `app/verify/base.py` | `VERIFIER_VERSION == "1.0.5"` | ✓ VERIFIED | `:22`; no `1.0.[0-4]` in app/verify or tests/verify |
| `app/verify/text_checks.py` | Fail-closed visible `warn` for unanchorable region; fail precedence | ✓ VERIFIED | `:93-116` |
| `app/api/tailoring.py` | Four routes; ok-only selection; typed refusals; no request-text path | ✓ VERIFIED | generate/review/compile/pdf routes; `?artifact_id=` with ownership recheck |
| `app/db/repositories/cv_artifact_repo.py` | SQL-level `ok` predicate on both selectors | ✓ VERIFIED | `latest_for_listing` `:173`; `read_for_download` `:192` |
| `app/domain/cv.py` | Typed patch ops; bullet-immutable `apply_patch`; duplicate-target schema guard | ✓ VERIFIED | Ops union + `apply_patch` + `_refuse_duplicate_targets`; no text field |
| `app/domain/schemas/_coerce.py` | Shared list-shape helper; bounded, literal-key unwrap | ✓ VERIFIED | `WRAPPER_KEY = "item"`; loop bounded |
| `app/web/templates/html/_cv_findings.html` | Blocked panel: pass/warn/fail rows, offending ids, recovery, no control/download | ✓ VERIFIED | `:12-27`; UAT test 2 |
| `app/web/templates/html/_tailoring_review.html` | Preview + change log + drop reasons + guard fields | ✓ VERIFIED | `:21-44`, `:78-80` |
| `tests/fixtures/verify/org_first_bullet_extract.txt` | Shape-1 literal repro string | ✓ VERIFIED | committed (tracked) |
| `tests/fixtures/verify/org_first_merge_extract.txt` | Shape-2 merged repro string | ✓ VERIFIED | committed (tracked) |
| `tests/verify/test_numbers.py` | Literal, merge, negative-control, prefix-collision property, ceiling tests | ✓ VERIFIED | T1-T4 + ceiling tests; `tests/verify` green |
| Migration | none from phase-6 work | ✓ VERIFIED | No phase-6 commit touches an alembic path; head `0007` is phase 7's |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `cv.tex.jinja:61` (ORG --- TITLE) | `_entry_lines` separator conjunct | `dash_lines[index].startswith(org_dash + '-')` | WIRED | `app/verify/numbers.py:219` |
| later unanchored entry org/title/date-range | region-end bound | containment `any(needle in line ...)` | WIRED | `app/verify/numbers.py:361-400` |
| `region_token_report` `found=False` | `check_metric_containment` warn | explicit `unanchored` collection | WIRED | `app/verify/text_checks.py:93-116` |
| `GET /listings/{id}/cv/pdf?artifact_id=` | `read_for_download(ok_only=True)` + ownership check | SQL predicate + `record.listing_id == listing_id` | WIRED | `app/api/tailoring.py:689-694`; `cv_artifact_repo.py:192` |
| `latest_for_listing(ok_only=True)` | download route (no selector) | SQL `compile_status == "ok"` | WIRED | `cv_artifact_repo.py:173`; `app/api/tailoring.py:690` |
| `application_repo.record_application` | exact-CV link | `read_for_download(ok_only=True)` | WIRED | `app/db/repositories/application_repo.py:465-466` (phase-7 cross-phase contract) |
| `tailor_listing` | `LLMBackend.complete_structured` | port call with frozen `system` + untrusted `parts` | WIRED | `app/pipeline/tailor.py:249-257`; V2 impl `app/llm/opencode_server.py:606-1041` |
| `VERIFIER_VERSION` | `VerificationResult.verifier_version` → persisted `verification_json` | `base.py:22,50` | WIRED | 1.0.5 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| check-4 region report | `RegionReport.candidates` / `.allowed` | `region_token_report(plan, extracted_text)` | Yes — real extraction (fixture in hermetic lane; real engine in `-m latex`) | ✓ FLOWING |
| `check_metric_containment` outcome | `CheckResult.status` / `.offending` | region reports + allowed sets | Yes | ✓ FLOWING |
| download | `record.pdf_path` | `ok_only=True` SQL selection | Yes | ✓ FLOWING |
| generate | `StructuredCallResult.data` | V2 `generate` response, pydantic-validated client-side | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Phase-6 core lanes | `/tmp/gsdvenv/bin/python -m pytest -q tests/verify tests/domain/test_patch_ops.py tests/domain/test_coerce.py tests/api/test_tailoring_review.py tests/api/test_tailoring_generate.py tests/api/test_cv_pdf_route.py` | `209 passed in 50.12s` | ✓ PASS |
| Tailor stage + Layer-1/grounding + stylesheet + V2 generate | `/tmp/gsdvenv/bin/python -m pytest -q tests/pipeline/test_tailor_stage.py tests/verify/test_grounding.py tests/verify/test_plan_checks.py tests/test_stylesheet_coverage.py tests/llm/test_v2_generate.py` | `72 passed in 57.46s` | ✓ PASS |
| Full hermetic suite | `/tmp/gsdvenv/bin/python -m pytest -q` | `1805 passed, 15 deselected, 2 xfailed in 493.66s` | ✓ PASS |
| Build gate | `.venv/bin/python -m compileall -q app` | exit 0 | ✓ PASS |
| Truth 5 — digit-bearing location | independent repro | `pass []` | ✓ PASS |
| Truth 6 shape 1 — org-first bullet, no separator | independent repro | `found [True, True]`, `pass []` | ✓ PASS |
| Truth 15 ceiling — full-header reproduction | independent repro | `fail ['exp/B:99']` (documented hard fail) | ✓ PASS |
| Real-engine latex lane | `pytest -m latex` | cannot run on host — Tectonic absent (D-69); container run recorded in 06-UAT.md (10 passed) | ? SKIP (host) |

`tests/verify` alone plus the tailored API/pipeline lanes total **281 passed** on this tree.

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes and no PLAN-declared probes exist for this phase. Step 7c: NOT APPLICABLE.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| TAIL-01 | 06-01, 06-07 | Generate a CV tailored to a specific listing | ✓ SATISFIED | one call → one patch; generate route; off-switch guard; typed 502 |
| TAIL-02 | 06-01, 06-09 | Typed patch over enumerated IDs, no free-text on the PDF path | ✓ SATISFIED | schema + canary + raised-error audit row; V2/coercion add no text field |
| TAIL-03 | 06-01 | Never rewrites/invents claims; bullet text immutable | ✓ SATISFIED | carried-through `Bullet` objects; canary test |
| TAIL-04 | 06-02, 06-05, 06-08, 06-10, 06-11 | Verification gate checks the compiled PDF for unsupported content | ✓ SATISFIED | org-first + separator anchor (truths 6/13), region-end bound (truth 14), fail-closed warn (truth 7), honest residual (truth 15) |
| TAIL-05 | 06-04 (+ Phase 7 for attach) | Failed CV blocked; cannot be downloaded or attached | ✓ SATISFIED | download: `ok_only=True` SQL + route; attach: `application_repo.record_application` ok-only gate |
| TAIL-06 | 06-02 | Verification never auto-repairs — it blocks | ✓ SATISFIED | no repair branch (`tailor.py:313-314`); tests |
| TAIL-07 | 06-03 | Review the tailored CV and change log before compiling | ✓ SATISFIED | review route/template; guard; tests |
| TAIL-08 | 06-03, 06-06 | Anything dropped is listed explicitly with a reason | ✓ SATISFIED | `dropped_bullets` struck + reason; phantom-change path closed |
| UI-05 | 06-04, 06-07 | Preview and download the tailored CV PDF | ✓ SATISFIED | inline preview + `?download=1` route; download links on `tailoring.html`; tests |

All 9 phase requirement IDs appear in at least one plan's `requirements:` field. No ORPHANED
requirements. `REQUIREMENTS.md`'s `TAIL-*`/`UI-05` traceability marks still read "Gaps Found" on
disk; with verification now `passed` they may be set to Complete, but that edit is out of scope for
this report.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/verify/numbers.py` | 169-183 | Documented hard-fail ceiling: a bullet reproducing the FULL header still anchors and hard-fails (structurally irreducible at line granularity) | ℹ️ Info (scoped, fail-closed) | A contrived bullet that literally opens `<org> --- <title> <dates>` can block a valid CV; documented and fail-closed, not a false pass |
| `tests/verify/test_numbers.py` | 10,524,578,686 | Pre-existing `ruff` I001/E501 style errors on lines untouched by this work | ℹ️ Info | Cosmetic; not introduced by the gap closure |
| `app/web/templates/html/tailoring.html` | 43 | Nested duplicate `id="tailoring-review"` when a persisted draft is present (outer div + `_tailoring_review.html:17`) | ⚠️ Warning (pre-existing, UI-REVIEW) | htmx resolves the first match so swaps still land; a markup-hygiene defect, not a truth failure. Carried by `06-UI-REVIEW.md`; the UAT's fail-vs-warn legibility check passed regardless |

No `TBD`/`FIXME`/`XXX` debt markers were found in the phase's covered impl/template files. **No
blocking check was weakened** — `metric_containment` still hard-fails an anchored surplus;
`page_budget`/`layout_ats` remain the only warn-only checks; a warn never blocks. **No new
dependency added.** **No phase-6 commit touches an Alembic path.**

### Human Verification Required

None. The two container/visual items the prior report listed are both answered in `06-UAT.md`
(status `complete`, 2/2 passing):

1. **Real-engine tailored compile** — container `docker compose run --rm app pytest -m latex -q`
   → 10 passed (2026-10-13).
2. **Fail-vs-warn legibility and block-as-outcome** — operator-confirmed 2026-10-14: pass/warn/fail
   rows render green/amber/red (`.req-met/.req-partial/.req-gap` → `--color-success/--color-warning/--color-danger`
   in `static/vendor/app.css`), offending ids named, fresh-tailoring recovery stated, no corrective
   control and no download link.

### Gaps Summary

No gaps. This pass is a digest refresh plus a genuine re-check of the must-haves on today's tree,
prompted by Phase 7.1's V2 migration and two phase-7.1 commits touching Phase 6's surface, and by
completion of the UAT. All 18 truths are VERIFIED:

- Truths 1/12 (the LLM/tailoring call path) are re-confirmed against the CURRENT V2 code: the port
  signature is unchanged, the V2 arm returns a validated model in `result.data`, and the
  one-call/one-audit-row/typed-502 shape is intact.
- Truths 2/10 are re-confirmed: the new `_refuse_duplicate_targets` schema validator adds no field
  and no free-text path; `next_page_trim` cannot build a duplicate patch.
- Truths 4-7 and 13-16 rest on `app/verify/*`, which is byte-identical to the prior verification and
  independently reproduced here (truth 5 `pass`, truth 6 shape-1 `pass`, truth 15 ceiling `fail`).
- Truth 17 is upgraded from PRESENT_BEHAVIOR_UNVERIFIED to VERIFIED on the committed container
  `-m latex` result (10 passed); the host cannot run that lane (D-69), and this report does not
  claim it ran it.

The only residual is the pre-existing `id="tailoring-review"` markup-hygiene warning and the
documented `numbers.py` full-header hard-fail ceiling — both scoped, non-blocking, and carried from
the prior reports.

---

_Verified: 2026-10-14T13:59:55Z_
_Verifier: the agent (gsd-verifier)_
