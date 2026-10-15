---
phase: 06-tailoring-verification
plan: 02
subsystem: llm-pipeline
tags: [verification, anti-fabrication, rapidfuzz, pypdf, pydantic, sqlalchemy, settings]

requires:
  - phase: 06-tailoring-verification
    plan: 01
    provides: app/verify Layer-1 verify_plan (5 checks), the typed TailoringPatch over enumerated ids, compile_tailored's Layer-1 short-circuit, cv_artifact_repo's ok-only selection
  - phase: 04-cv-rendering
    provides: extract_pdf_text, the escaping choke point, squash/normalise_for_compare, the RenderPlan projection
provides:
  - "the six Layer-2 checks (2b, 4, 7, 8, 9, 10) — all ten §10.3 checks now ship as eleven CheckResults"
  - "the metric tokeniser and line-based region containment with date-like/page-number exclusion"
  - "the advisory grounding band (band_for) attached to requirement_evidence without changing its fail predicate"
  - "Settings.tailoring_grounding_threshold / tailoring_grounding_review_threshold"
  - "two-layer block-don't-repair enforcement inside compile_tailored; a Layer-2 fail retains the PDF but stays unreachable"
  - "the §7.3 canary pin: no patch reason/requirement/rationale can reach the rendered .tex"
affects: [06-03, 06-04, 07-apply-and-track]

actuals:
  tokens: 17925
  tasks: 3
  # 3 task commits + this plan's metadata commit.
  commits: 4
  plan_head_before: 1484a08d5843dfd6289379ebf6ec32910e08d6df

tech-stack:
  added: []
  patterns:
    - "digit-core tokenisation with region-scoped containment, excluding date-like and page-number artefacts"
    - "a fuzzy similarity band that is ADVISORY only and can never flip passed (D-70 applied to check 6)"
    - "line-based region segmentation so date hyphens survive squash (A2/A3)"
    - "one VerificationResult merged from both layers, persisted as ids/counts/hashes only"

key-files:
  created:
    - app/verify/numbers.py
    - app/verify/text_checks.py
    - app/verify/grounding.py
    - tests/verify/test_numbers.py
    - tests/verify/test_text_checks.py
    - tests/verify/test_grounding.py
    - tests/verify/test_block_no_repair.py
    - tests/verify/test_no_free_text_path.py
    - tests/fixtures/verify/novel_metric_extract.txt
    - tests/fixtures/verify/missing_entity_extract.txt
    - tests/fixtures/verify/injection_residue_extract.txt
    - tests/fixtures/verify/reworded_verbatim_extract.txt
    - tests/fixtures/verify/three_page_extract.txt
    - tests/fixtures/verify/missing_heading_extract.txt
  modified:
    - app/verify/__init__.py
    - app/verify/plan_checks.py
    - app/pipeline/tailor.py
    - app/config.py
    - tests/verify/fixtures.py
    - tests/test_config.py
    - tests/api/test_tailoring_generate.py

key-decisions:
  - "Region segmentation is line-based (locating squash(org) per line), not squash-substring-based: squashing fuses '2021-03' into '202103' and would defeat the date-like exclusion (A3). squash remains the substrate for entity_present and verbatim_integrity only"
  - "The persisted verification_json is ONE merged VerificationResult — 11 checks, passed = both layers passed — so the UI and verify-work read the whole gate from one column"
  - "A Layer-2 fail keeps the compiled PDF (pdf_path/tex_path set) for diagnosis, but the repository's ok-only selection is what makes it unreachable (D-115/D-118); a Layer-1 fail stores NULL paths"
  - "An engine failure (or an unreadable PDF) is 'failed', never 'blocked' — Layer-2 verification never ran, so no finding explains a block"
  - "check_requirement_evidence takes optional grounded_at/review_at kwargs defaulting to Settings, so the band is testable at a pinned boundary while the production path reads config"
  - "The hermetic lane stubs extract_pdf_text, so pypdf extraction of a REAL Tectonic PDF is exercised only by the container latex lane (see coverage D8)"

patterns-established:
  - "Layer-2 post-checks consume the extracted text as a value and persist only a hash (T-06-11)"
  - "A blocked artifact is a contract, not an error: blocked row + ok-only reachability + no repair code path"
  - "A canary test pins a 'never reaches the render' guarantee by planting distinctive strings in every audit field"

requirements-completed: [TAIL-04, TAIL-06]

coverage:
  - id: D1
    description: "All ten §10.3 checks ship as eleven CheckResults (check 2 split across layers); 1-7 and 10 are fail, 8 and 9 are warn-only and never block"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "tests/verify/test_text_checks.py::test_a_valid_extraction_passes_every_layer_two_check"
        status: pass
      - kind: unit
        ref: "tests/verify/test_plan_checks.py::test_a_valid_plan_passes_every_layer_one_check"
        status: pass
    human_judgment: false
  - id: D2
    description: "The metric tokeniser handles affix/range/percent/thousands/decimal/magnitude edge cases and region containment excludes date-like and page-number artefacts"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "tests/verify/test_numbers.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "The grounding band is advisory, reads its thresholds as arguments/Settings, and never flips VerificationResult.passed (A1)"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "tests/verify/test_grounding.py::test_an_ungrounded_band_does_not_block"
        status: pass
    human_judgment: false
  - id: D4
    description: "Both grounding thresholds are Settings fields guarded by the Phase-6 ceilings, environment-tunable, and app/verify is in SCANNED_DIRS so a hard-coded threshold there fails the absence scan (A7)"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "tests/test_config.py::test_the_phase_six_ceilings_are_guarded"
        status: pass
      - kind: unit
        ref: "tests/test_config.py::test_no_distinctive_threshold_literal_remains_in_probe_or_pipeline"
        status: pass
    human_judgment: false
  - id: D5
    description: "A Layer-1 fail never reaches the engine; a Layer-2 fail writes a blocked row that retains the PDF but is excluded by the ok-only selection; an engine failure is 'failed'; no repair path exists"
    requirement: TAIL-06
    verification:
      - kind: unit
        ref: "tests/verify/test_block_no_repair.py::test_a_layer_one_fail_never_reaches_the_engine"
        status: pass
      - kind: unit
        ref: "tests/verify/test_block_no_repair.py::test_a_layer_two_fail_retains_the_pdf_but_is_not_downloadable"
        status: pass
      - kind: unit
        ref: "tests/verify/test_block_no_repair.py::test_a_blocked_artifact_is_never_regenerated"
        status: pass
    human_judgment: false
  - id: D6
    description: "The §7.3 guarantee is pinned: a canary in a drop/demote reason, a GapFinding.requirement and a Suggestion.rationale never reaches the rendered .tex or any render-plan field, while the change log still carries it"
    requirement: TAIL-06
    verification:
      - kind: unit
        ref: "tests/verify/test_no_free_text_path.py::test_a_reason_canary_never_reaches_the_rendered_tex"
        status: pass
    human_judgment: false
  - id: D7
    description: "compile_tailored runs verify_text over the extracted text and an ok row persists page_count plus the merged 11-check VerificationResult and check 9's findings"
    requirement: TAIL-04
    verification:
      - kind: integration
        ref: "tests/api/test_tailoring_generate.py::test_compile_writes_one_ok_row_and_returns_a_download_link"
        status: pass
    human_judgment: false
  - id: D8
    description: "Layer-2 checks over a REAL pypdf extraction of a Tectonic-compiled tailored CV"
    verification:
      - kind: other
        ref: "docker compose run --rm app pytest -m latex"
        status: unknown
    human_judgment: true
    rationale: "The hermetic default lane stubs extract_pdf_text (D-69): the stub engine in tests writes a canned PDF, not a Tectonic one. Only the container latex lane can confirm check 14-7/10 behaviour against a real extraction (page-count and ligature artefacts)."

duration: 19min
completed: 2026-09-24
status: complete
---

# Phase 06 Plan 02: The verification gate, complete: all ten checks, warn-not-block, block-don't-repair

**The remaining six §10.3 checks ship with a digit-core metric tokeniser, an advisory rapidfuzz grounding band that can never block, and two-layer enforcement inside `compile_tailored` where a fail always writes a non-downloadable blocked row and never repairs.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-09-24T16:35:01Z
- **Completed:** 2026-09-24T16:54:12Z
- **Tasks:** 3
- **Files modified:** 21

## Accomplishments

- Shipped the six Layer-2 checks (`entity_present`, `metric_containment`, `injection_residue`, `page_budget`, `layout_ats`, `verbatim_integrity`) so the ten §10.3 checks now exist as eleven `CheckResult`s — check 2's resolvability on Layer 1 and its presence on Layer 2.
- Built the pure metric tokeniser (`digit_cores`) and line-based region containment (`region_token_report`): every surviving digit core in a region must be one of that region's source tokens, with date-like cores and lone-integer page-number lines excluded (D-113, A2/A3).
- Added the advisory grounding band (`band_for` over `fuzz.token_set_ratio` + `normalise_for_compare`) attached to `requirement_evidence`'s passing `detail`; the structural fail predicate is untouched and the band can never flip `passed` (A1, D-70). Both thresholds are Settings fields (80/55, uncalibrated) guarded by the Phase-6 ceilings, with `app/verify` added to `SCANNED_DIRS` (A7).
- Wired Layer 2 into `compile_tailored`: the PDF text is read through `asyncio.to_thread(extract_pdf_text)`, then `verify_text` runs; a fail writes a `blocked` row (retaining the PDF for a Layer-2 fail), an engine failure is `failed`, and no branch repairs anything.
- Pinned the §7.3 guarantee with a canary test: distinctive strings in a drop reason, a demote reason, a `GapFinding.requirement` and a `Suggestion.rationale` never reach the rendered `.tex` or any render-plan field, while the change log still carries the reasons.
- 1187 tests pass in the hermetic lane; `ruff check` clean; `compileall` clean.

## Task Commits

Each task was committed atomically:

1. **Task 1: The metric tokeniser and the Layer-2 checks** — `d62b657` (feat)
2. **Task 2: The advisory grounding band and its Settings surface** — `3696f9b` (feat)
3. **Task 3: Block-don't-repair wired end-to-end, and the canary that pins §7.3** — `89b2515` (feat)

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified

- `app/verify/numbers.py` — `digit_cores`, `date_like_cores_for_entry`, `is_page_number_line`, `region_token_report`, `RegionReport`
- `app/verify/text_checks.py` — `verify_text` and the six Layer-2 checks
- `app/verify/grounding.py` — `GroundingBand`, `band_for`, `evidence_text_for`
- `app/verify/plan_checks.py` — `requirement_evidence` attaches the advisory band to a passing `detail`; the structural fail predicate is unchanged
- `app/verify/__init__.py` — exports the Layer-2 and grounding names
- `app/pipeline/tailor.py` — the Layer-2 call site, the two-layer blocked-row contract, the `failed`-on-engine-failure branch
- `app/config.py` — `tailoring_grounding_threshold` (80), `tailoring_grounding_review_threshold` (55)
- `tests/verify/fixtures.py` — per-requirement grounding expectations on the builder
- `tests/test_config.py` — `PHASE_SIX_CEILINGS` guards, the env-tunability test, `app/verify` in `SCANNED_DIRS`
- `tests/api/test_tailoring_generate.py` — the hermetic lane stubs `extract_pdf_text`
- Six committed `tests/fixtures/verify/*.txt` extracts (novel metric, missing entity, injection residue, reworded verbatim, three page, missing heading)
- Tests — `tests/verify/{test_numbers,test_text_checks,test_grounding,test_block_no_repair,test_no_free_text_path}.py`

## Decisions Made

- **Line-based regions, not squash-substring regions.** `squash("2021-03")` is `"202103"`, which would defeat the date-like exclusion the check exists for. Regions are located by matching `squash(org)` against each line's squash and then read from the ORIGINAL lines, preserving the date hyphen. `squash` stays the substrate for `entity_present`/`verbatim_integrity`, where whitespace-insensitivity is the point.
- **One merged `VerificationResult` for the persisted column.** On an ok or Layer-2-fail row the `verification_json` carries all eleven checks and `passed = layer1.passed and layer2.passed`, so the UI fragment and verify-work read the whole gate from one place. A Layer-1 fail (which short-circuits before Layer 2) stores the five Layer-1 checks.
- **A Layer-2 fail retains the PDF but remains unreachable.** `pdf_path`/`tex_path` are set for diagnosis (D-115); the repository's `ok`-only selection is the access control (D-118).
- **Engine failure (and an unreadable PDF) → `failed`, never `blocked`.** Layer-2 verification never ran, so there is no finding to explain a block.
- **`check_requirement_evidence` accepts optional `grounded_at`/`review_at`** defaulting to `Settings`, so the band boundary is testable exactly while production reads config.
- **`app/verify` honours the absence scan.** The two thresholds are arguments/Settings, never literals in the package (A7).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Stubbed `extract_pdf_text` in the existing tailoring API test**
- **Found during:** Task 3 (wiring the real Layer-2 call)
- **Issue:** `tests/api/test_tailoring_generate.py`'s `StubEngine` writes `b"%PDF-1.4 stub\n"`. Once `compile_tailored` reads the PDF through `pypdf`, that canned file makes `PdfReader` raise, so the existing ok-row test would fail.
- **Fix:** The `tailoring_client` fixture monkeypatches `tailor_module.extract_pdf_text` to the committed `base_extract.txt` (which passes all Layer-2 checks). This is a hermetic-lane substitution, not a product change; the real extraction is the container `latex` lane's job (coverage D8).
- **Files modified:** `tests/api/test_tailoring_generate.py`
- **Verification:** `tests/api/test_tailoring_generate.py` (14 tests across it and the stage test) passes; full suite green.
- **Committed in:** `89b2515` (Task 3 commit)

### Plan-text reconciliation (no code impact)

**2. [Rule 1 - Bug] Region segmentation substrate**
- **Found during:** Task 1
- **Issue:** The plan's `must_haves` truth says the region is the span "in `squash(text)`". Squashing removes the hyphen in `2021-03`, fusing it into `202103`, so the required date-core exclusion (`2021`, `03`) can never match — the two requirements are mutually exclusive.
- **Fix:** region segmentation uses line-located `squash(org)` matches and reads candidates from the original lines (documented in the `app/verify/numbers.py` module docstring). The date-exclusion requirement is satisfied; the `squash` wording is not, deliberately.
- **Files modified:** `app/verify/numbers.py`
- **Verification:** `tests/verify/test_numbers.py::test_a_date_core_is_never_a_candidate` passes.
- **Committed in:** `d62b657` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking) + 1 plan-text reconciliation
**Impact on plan:** Both are direct consequences of this plan's own files. No scope creep, no behavioural change beyond the mandated Layer-2 gate.

## Issues Encountered

- **`missing_heading_extract.txt` is not purely a `layout_ats` warn.** Because `entity_present` (check 2b) deliberately includes `SECTION_TITLES.values()`, removing the `Skills` heading also fails check 2b; only `layout_ats` warns. The test asserts the `layout_ats` warn specifically, and this overlap is recorded here so it is not mistaken for a defect. It is a consequence of the locked truth that entity_present scans structured fields including section titles.
- **`ruff format --check` reports three pre-existing unformatted files** (`app/verify/plan_checks.py`, `tests/verify/test_plan_checks.py`, and the pre-existing wrap in others). They were already non-format-clean before this plan; only `ruff check` is clean. No pre-existing file was reformatted.

## Known Stubs

None. The only intentional thin seam is the test-only `extract_pdf_text` substitution described above, which is a hermetic-lane fixture (D-69), not a product stub: the production path calls the real `extract_pdf_text`.

## Next Phase Readiness

- 06-03 (stale-patch 409 guard and the full review change log) and 06-04 (history, the `_cv_findings.html` fragment) can read the combined `verification_json` and `ats_checks_json` directly.
- **UNRUN:** Layer-2 checks against a real `pypdf` extraction of a Tectonic-compiled tailored CV are exercised only by the container `latex` lane (coverage D8). The hermetic lane stubs the extraction.

---
*Phase: 06-tailoring-verification*
*Completed: 2026-09-24*

## Self-Check: PASSED

- All 14 created files exist; `06-02-SUMMARY.md` exists.
- All 3 task commits exist: `d62b657`, `3696f9b`, `89b2515`.
- `git rev-list --count 1484a08..HEAD` = 4 (3 task commits + this metadata commit), matching `actuals.commits`.
