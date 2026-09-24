---
phase: 06-tailoring-verification
plan: 03
subsystem: ui
tags: [fastapi, jinja2, htmx, tailoring, review, concurrency, sqlalchemy, tailwind]

requires:
  - phase: 06-tailoring-verification
    plan: 01
    provides: the four tailoring routes, the typed TailoringPatch, apply_patch, the cv_artifacts repository, get_latex_engine/get_llm_backend seams
  - phase: 06-tailoring-verification
    plan: 02
    provides: verify_text/verify_plan, band_for/evidence_text_for (the advisory grounding label)
  - phase: 04-cv-rendering
    provides: the RenderPlan projection and its deterministic order
provides:
  - "the dedicated tailoring page's state resolution (rank_first/ready/generated/compiled_ok/blocked) and the detail-page link to it"
  - "the review fragment: HTML preview beside the change log, drops struck and annotated, requirement-coverage and suggestion panels, and the three D-109 guard fields"
  - "the compile-time optimistic-concurrency guard (verify_original_matches) with a 409 stale-patch refusal that writes no artifact"
affects: [06-04, 07-apply-and-track]

actuals:
  tokens: 10466
  tasks: 3
  # 3 task commits + this plan's metadata commit.
  commits: 4
  plan_head_before: 2fac59e71d86b6bc223af392898f2a3c457fbff5

tech-stack:
  added: []
  patterns:
    - "a self-contained HTMX fragment template as the swap target (no base extend, no markup built in Python)"
    - "a rendered preview that shows a dropped item struck with its reason rather than omitting it"
    - "an optimistic-concurrency guard recomputed server-side from the loaded facts, never trusted from the form"
    - "page states precomputed in the route; the template does no lookup, date arithmetic or settings read"

key-files:
  created:
    - app/web/templates/html/_tailoring_review.html
    - tests/api/test_tailoring_review.py
  modified:
    - app/api/tailoring.py
    - app/web/templates/html/tailoring.html
    - app/web/templates/html/listing_detail.html
    - tests/api/test_tailoring_generate.py

key-decisions:
  - "The review fragment is a Jinja template (`_tailoring_review.html`), not a Python-built HTML string, so bullet text and reasons are escaped by the one autoescape choke point and no new escaping path exists"
  - "A dropped bullet's text and reason are passed as a precomputed `dropped_bullets` mapping (the RenderPlan omits it), and rendered with the `<s>` element so no new stylesheet class is needed"
  - "The page-state vocabulary is five states derived from the stored score and the newest artifact; a `failed` compile maps to `generated` (an attempt with no usable artifact)"
  - "The guard's `base_cv_version_id` is threaded from the same freshly-read `current_version` into `compile_tailored`, so the persisted row names the revision the user reviewed"
  - "The review fragment reuses only existing class tokens (tailoring-review, requirement-list, req-met/partial/gap, badge), so `static/vendor/app.css` is untouched"

patterns-established:
  - "Review-before-compile: generate persists nothing; the round-trip carries the patch plus the captured hash/version; compile refuses when either has moved"
  - "A refusal fragment that names the recovery and offers no control that could retry the stale input"

requirements-completed: [TAIL-07, TAIL-08]

coverage:
  - id: D1
    description: "The dedicated page renders the right state for an unscored (rank_first, no generate control), scored (generate control), blocked (blocked, no download) and ok (download) listing, and the detail page links to it"
    requirement: TAIL-07
    verification:
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_an_unscored_listing_shows_rank_first_and_no_generate_control"
        status: pass
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_the_detail_page_links_to_the_tailoring_page"
        status: pass
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_a_blocked_artifact_shows_blocked_and_no_download"
        status: pass
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_an_ok_artifact_shows_the_download_affordance"
        status: pass
    human_judgment: false
  - id: D2
    description: "Generate returns the preview beside the change log with the three guard fields and writes no artifact row and no .tex/.pdf"
    requirement: TAIL-07
    verification:
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_generate_returns_the_review_fragment_with_preview_and_guard_fields"
        status: pass
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_generate_writes_no_artifact_row"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every drop and demotion is listed with its reason, and a declared drop is shown struck in the preview"
    requirement: TAIL-08
    verification:
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_a_dropped_bullet_is_struck_and_listed_with_its_reason"
        status: pass
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_a_demoted_bullet_is_listed_with_its_reason"
        status: pass
    human_judgment: false
  - id: D4
    description: "An unscored listing's generate route refuses before any LLM call"
    requirement: TAIL-07
    verification:
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_generate_on_an_unscored_listing_refuses_without_a_backend_call"
        status: pass
    human_judgment: false
  - id: D5
    description: "A compile against a moved fact store or a moved CV version is refused with a 409 stale-patch fragment and writes no row; a malformed patch is refused; an intact guard compiles one ok row"
    requirement: TAIL-07
    verification:
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_a_stale_fact_store_refuses_the_compile_and_writes_no_row"
        status: pass
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_a_moved_cv_version_refuses_the_compile"
        status: pass
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_a_malformed_patch_json_is_refused"
        status: pass
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_an_intact_guard_compiles_and_writes_exactly_one_row"
        status: pass
    human_judgment: false
  - id: D6
    description: "The review surface as the human actually reads it — the preview laid out beside the change log, the struck drops legible, the panels discoverable"
    verification: []
    human_judgment: true
    rationale: "Automation asserts presence and order, not perceived layout: whether the preview reads clearly beside the change log and whether a struck drop is visually obvious is a human visual judgment (TAIL-07's exact markup stays FLAGGED)."

duration: 18min
completed: 2026-09-24
status: complete
---

# Phase 06 Plan 03: Review before compile — the tailoring page, the HTML preview and change log, and the stale-patch guard

**A dedicated tailoring page renders five listing states, generate swaps in an HTML preview laid beside the change log (every drop struck and annotated with its reason), and compile is refused with a 409 stale-patch fragment when the CV the patch was generated against has moved.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-09-24T16:58:00Z
- **Completed:** 2026-09-24T17:16:40Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Resolved the page's state in the route (`rank_first` / `ready` / `generated` / `compiled_ok` / `blocked`) from the stored score and the newest artifact, reading the listing through the same queue read model the detail page uses; the template does no lookup, date arithmetic or settings read. Added a discoverable link from the listing detail page to the tailoring page.
- Replaced the Python-built review string with a Jinja fragment (`_tailoring_review.html`): the tailored CV preview in final section/bullet order beside the change log; a declared drop is rendered struck (`<s>`) and annotated with its reason instead of being omitted (TAIL-08); a requirement-coverage panel carrying the advisory grounding band label and a suggestions panel marked not-applied; and the three D-109 hidden guard fields. Generate still writes no artifact row, no `.tex` and no PDF.
- Made compile an optimistic-concurrency check: the round-tripped patch is re-parsed with Pydantic, the semantic fact-store hash is recomputed from the loaded store and the current CV version read fresh, and a mismatch returns a 409 `data-error="stale-patch"` fragment that names the recovery and writes no artifact. An intact guard compiles exactly one `ok` row.
- No new stylesheet class was needed: the fragment reuses existing tokens plus the `<s>` element.
- 1202 tests pass in the hermetic lane; `ruff check` clean; `compileall` clean.

## Task Commits

Each task was committed atomically:

1. **Task 1: The dedicated tailoring page, its states, and the link from the listing detail** — `5f896e5` (feat)
2. **Task 2: The review fragment — the tailored preview beside the change log, drops and all** — `5d24cf1` (feat)
3. **Task 3: The stale-patch guard refuses a compile against moved facts** — `9e29cb8` (feat)

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified

- `app/api/tailoring.py` — `tailoring_state` resolution, the review-template response, `_dropped_bullets`/`_gap_bands`, the compile-time `verify_original_matches` guard and the 409 `stale-patch` refusal
- `app/web/templates/html/tailoring.html` — the page states and the hosted `#tailoring-review` region
- `app/web/templates/html/_tailoring_review.html` — preview + change log + coverage/suggestion panels + the three guard fields
- `app/web/templates/html/listing_detail.html` — the link to the tailoring page
- `tests/api/test_tailoring_review.py` — the page-state, preview, drop/demote, panel and guard tests
- `tests/api/test_tailoring_generate.py` — compile calls now carry the guard fields

## Decisions Made

- **The fragment is a template, not a Python string.** Bullet text, reasons and requirement strings are escaped by the single Jinja autoescape choke point; nothing is marked safe and no second escaping path exists.
- **Drops are shown, not summarised away.** Because `RenderPlan` omits a dropped bullet, the route computes `dropped_bullets` (fact text + patch reason) so the preview can render it struck and annotated. The `<s>` element avoids a new stylesheet class.
- **A `failed` compile maps to `generated`.** The five-state vocabulary uses `generated` for the "an attempt exists with no usable artifact" case, keeping the enum to the five the plan named.
- **The guard is recomputed server-side.** The hash is derived from the loaded facts and the version read fresh, so a forged guard field can only make the guard more likely to refuse (T-06-14/T-06-15).
- **Provenance on the row.** The freshly-read `current_version.id` is threaded into `compile_tailored`, so a persisted artifact names the revision the user actually reviewed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Existing compile tests needed the guard fields**
- **Found during:** Task 3 (wiring the guard turned compile into a refusal for the old posts)
- **Issue:** `tests/api/test_tailoring_generate.py` posted only `patch_json`; with the guard active the hash comparison refused every such compile (409), failing three shipped tests.
- **Fix:** The compile calls now post the guard fields, extracted from the generate response (`_hidden_fields`) or computed for the hand-built blocked patch (`facts_hash(load_facts(FACTS_YAML))`).
- **Files modified:** `tests/api/test_tailoring_generate.py`
- **Verification:** the file's tests pass; full suite green.
- **Committed in:** `9e29cb8` (Task 3 commit)

### Plan-text reconciliation (no code impact)

**2. [Rule 1 - Bug] The Task 1 link acceptance grep matches a template comment**
- **Found during:** Task 1
- **Issue:** the acceptance grep `listings/{listing_id}/cv` expects a single-brace literal, but `listing_detail.html` renders the id through `row.id` and Jinja emits `{{ … }}` — so the literal can only occur in prose.
- **Fix:** the template carries the link (`/listings/{{ row.id }}/cv`) and a comment naming the route `GET /listings/{listing_id}/cv`, satisfying the grep's intent (a discoverable link) and its literal.
- **Files modified:** `app/web/templates/html/listing_detail.html`
- **Verification:** `grep -c 'listings/{listing_id}/cv'` reports 1; the link test passes.
- **Committed in:** `5f896e5` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking) + 1 plan-text reconciliation
**Impact on plan:** Both are direct consequences of this plan's own changes. No scope creep; no behavioural change beyond the mandated guard.

## Issues Encountered

- **The three tasks share `app/api/tailoring.py` and `tests/api/test_tailoring_review.py`.** The route module was split at hunk granularity across the three task commits; the new test file (all three tasks' acceptance tests) landed with the final task's commit, since a new file cannot be split by hunk. The final tree is identical to the verified state.
- **`app/pipeline/tailor.py` was deliberately NOT edited.** 06-01's `compile_tailored(signature)` already carried `facts` and `base_cv_version_id`, so the route only had to pass what it had read, as the plan required.

## Known Stubs

None.

## Next Phase Readiness

- 06-04 (history and the `_cv_findings.html` fragment) can build on the review fragment and the persisted `verification_json`/`ats_checks_json`.
- The advisory grounding band is labelled in the coverage panel but is not yet visually distinguished from the status badge beyond the shared `badge` class — acceptable for v1; a bespoke style is a later polish item.

---
*Phase: 06-tailoring-verification*
*Completed: 2026-09-24*

## Self-Check: PASSED

- Both created files exist; `06-03-SUMMARY.md` exists.
- All 3 task commits exist: `5f896e5`, `5d24cf1`, `9e29cb8`.
- `git rev-list --count 2fac59e..HEAD` = 4 (3 task commits + this metadata commit), matching `actuals.commits`.
