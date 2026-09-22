---
phase: 05-ranking-core-value
plan: 03
subsystem: ui
tags: [ui, htmx, jinja2, ranking, detail-page, accessibility, escaping]

# Dependency graph
requires:
  - phase: 05-ranking-core-value
    provides: the read-time total, the per-factor sub-scores and the stored requirement breakdown from plan 05-01
provides:
  - "GET /listings/{listing_id} — the job detail page with the identity seam and a 404 fragment"
  - "the factor table with each factor's sub-score and weight, and an explicit absent marker"
  - "the requirement-by-requirement fit list with req-met / req-partial / req-gap verdicts and the evidencing CV fact id"
  - "the row's listing-detail-link and the vendored CSS for every new class"
affects: [06-cv-tailoring]

# Actuals (#2632) — same estimateTokens scale (chars/4 over the realized diff).
actuals:
  tokens: 6085
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "A full page reusing the queue read model (`read_row`) so the detail page and the row cannot drift"
    - "The read-time total is never recomputed in the route; the stored rationale and requirements are rendered verbatim"
    - "An unscored listing renders an explicit not-yet-ranked state, never a numeric zero"

key-files:
  created:
    - app/api/listings.py
    - app/web/templates/html/listing_detail.html
    - tests/api/test_listing_detail.py
  modified:
    - app/main.py
    - app/web/templates/html/_listing_row.html
    - static/vendor/app.css
    - tests/test_auth_seam.py
    - tests/api/test_queue_links.py

key-decisions:
  - "The detail page reuses `queue_repo.read_row`, so the score, flags, badges and source links come from the one queue code path"
  - "The factor table is gated on `row.total_score is not none`, so an unscored listing has no score region and no numeric zero"
  - "A CV fact id renders as `<code>` text, never as a link — it is an internal identifier, not a URL"
  - "The detail page reuses the row's exact save/hide event forms so both surfaces post one event vocabulary to the append-only endpoint (T-05-16)"

patterns-established:
  - "Detail page as a full page, not a fragment, so Phase 6's CV preview can hang off the same surface (D-96)"
  - "Vendored stylesheet coverage: every literal class token in a template has a rule, verified by tests/test_stylesheet_coverage.py"

requirements-completed: [UI-02]

coverage:
  - id: D1
    description: "GET /listings/{listing_id} returns the detail page for a known listing, a 404 fragment carrying data-error=\"unknown-listing\" for an unknown one, and declares the current_user identity seam"
    requirement: UI-02
    verification:
      - kind: unit
        ref: "tests/api/test_listing_detail.py#test_unknown_listing_returns_404_fragment"
        status: pass
      - kind: unit
        ref: "tests/test_auth_seam.py#test_every_route_with_a_dependant_declares_current_user"
        status: pass
    human_judgment: false
  - id: D2
    description: "The page renders the total, the tier, each factor's sub-score AND weight (dropped factor marked absent), the rationale, the requirement list with named gaps and evidencing fact ids, the merged-from record, and the save/hide actions; the queue row links to it with every new class styled from the vendored stylesheet"
    requirement: UI-02
    verification:
      - kind: unit
        ref: "tests/api/test_listing_detail.py#test_detail_page_renders_breakdown"
        status: pass
      - kind: unit
        ref: "tests/api/test_listing_detail.py#test_detail_shows_requirements_and_gaps"
        status: pass
      - kind: unit
        ref: "tests/test_stylesheet_coverage.py#test_every_template_class_has_a_stylesheet_rule"
        status: pass
    human_judgment: true
    rationale: "UI-02's probe row is unclassified and unresolved: the requirement does not state the layout or grouping of the fit breakdown. This plan chose a two-part layout (a factor table followed by a requirement list); whether that grouping is the right one is a presentation judgment a human should make."
  - id: D3
    description: "An unscored listing renders an explicit not-yet-ranked state and never a numeric 0.0, and untrusted listing text plus stored model prose are escaped by Jinja autoescape only"
    requirement: UI-02
    verification:
      - kind: unit
        ref: "tests/api/test_listing_detail.py#test_unscored_listing_renders_not_yet_ranked"
        status: pass
      - kind: unit
        ref: "tests/api/test_listing_detail.py#test_detail_escapes_untrusted_title_and_rationale"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-09-22
status: complete
---

# Phase 5 Plan 3: Job detail page — score, per-factor breakdown, rationale and named gaps Summary

**A full job detail page reusing the queue read model: the read-time total with its confidence tier, every factor's sub-score beside its weight, the grounded rationale, a requirement-by-requirement fit list with named gaps and evidencing CV fact ids, and the row's save/hide actions**

## Performance

- **Duration:** 10 min
- **Started:** 2026-09-22T12:41:18Z
- **Completed:** 2026-09-22T12:51:42Z
- **Tasks:** 3
- **Files modified:** 8 (3 created, 5 modified)

## Accomplishments

- `GET /listings/{listing_id}` renders the full detail page, resolves the listing
  through `queue_repo.read_row` (so the page and the row cannot drift) and the score
  through `score_repo.read_score_for_listing`, and returns a small HTML 404 fragment
  carrying `data-error="unknown-listing"` for an unknown id.
- The route declares the universal identity seam and joined
  `tests/test_auth_seam.py` `EXPECTED_SEAM_ROUTES`, so the flattened leaf-route walk
  proves it.
- The page renders the read-time total with its confidence-tier badge, and a factor
  table giving each factor's sub-score beside the weight currently in force — with a
  dropped factor shown as "no data", never a zero.
- The requirement list renders one entry per stored requirement with its verdict
  (`met`/`partial`/`gap` as `req-met`/`req-partial`/`req-gap`) and the evidencing CV
  fact id as `<code>` text; a gap is a named entry, not an omission.
- An unscored listing renders "Not yet ranked" and has no score region at all — the
  UI-02 transparency prohibition holds.
- The queue row gained an additive `Details` link, and every new class token has a
  vendored stylesheet rule (`tests/test_stylesheet_coverage.py` passes).
- Untrusted listing text and stored model prose are escaped by Jinja autoescape only;
  a `<script>` in both the title and the rationale renders escaped.

## Task Commits

Each task was committed atomically:

1. **Task 1: The GET /listings/{id} route and the detail page shell** - `c069070` (feat)
2. **Task 2: The full breakdown — factors with weights, requirement fits with named gaps, and the row link** - `58580ae` (feat)
3. **Task 3: The detail page's assertions, including escaping and the unscored state** - `2e6a293` (test)

**Plan metadata:** `13bb6cb` (docs: complete job detail page plan)

## Files Created/Modified

- `app/api/listings.py` - the router, the `listing_detail` route and the 404 fragment helper
- `app/web/templates/html/listing_detail.html` - the full page (score, factor table, rationale, requirement list, actions)
- `app/main.py` - the `listing_routes` import and `include_router` call
- `app/web/templates/html/_listing_row.html` - the additive `listing-detail-link`
- `static/vendor/app.css` - rules for `listing-detail-link`, `factor-table` (+ cells), `factor-absent`, `requirement-list`, `req-met`, `req-partial`, `req-gap`, `detail-rationale`, `detail-not-ranked`, `detail-empty`
- `tests/test_auth_seam.py` - `"/listings/{listing_id}"` in `EXPECTED_SEAM_ROUTES`
- `tests/api/test_listing_detail.py` - the five named assertions
- `tests/api/test_queue_links.py` - the plain-title assertion updated for the Details link

## Decisions Made

- The detail page reuses `queue_repo.read_row`, so flags, badges, source links and the
  read-time total come from the one queue code path.
- The factor table renders only for a scored listing, which is what keeps the unscored
  state free of any numeric zero.
- The save/hide forms reuse the queue row's exact block (same endpoint, same event
  types); the htmx swap target names the queue row's id, so on the detail page the POST
  still appends the event and the page reflects the change on reload — Phase 5's
  documented no-live-push posture (D-88).
- A CV fact id is rendered as `<code>` text, never a link.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The planned row Details link broke an exact-match queue test**
- **Found during:** Task 2 (the row link)
- **Issue:** `tests/api/test_queue_links.py::test_a_listing_without_a_url_renders_a_plain_title`
  asserts the literal `<td class="listing-title">Backend Engineer</td>`. Adding the
  Details link inside that cell (as the plan requires) moves the `</td>`, so the exact
  match no longer occurs. The file is not in this plan's `files_modified`.
- **Fix:** The assertion now keeps the test's intent — the title stays a plain title
  with no external `listing-title-link` anchor — and additionally asserts the internal
  `listing-detail-link` to `/listings/{id}`.
- **Files modified:** `tests/api/test_queue_links.py`
- **Verification:** `tests/api/test_queue_links.py` passes (19 tests in the Task 2 verify).
- **Committed in:** `58580ae`

**2. [Rule 3 - Blocking] The `grep -c "|safe"` acceptance grep**
- **Found during:** Task 1 (acceptance check)
- **Issue:** `grep -c "|safe" app/web/templates/html/listing_detail.html` returned 1
  because a Jinja comment described the rule using the literal token. No `|safe` filter
  existed.
- **Fix:** Reworded the comment to "no value here is ever marked as safe for the
  browser", preserving the meaning without the token.
- **Files modified:** `app/web/templates/html/listing_detail.html`
- **Verification:** `grep -c "|safe"` returns 0.
- **Committed in:** `c069070`

**3. [Rule 3 - Blocking] The plan's `.venv-host/bin/python` is unusable**
- **Found during:** Task 1 (first verify run)
- **Issue:** `.venv-host/bin/python` is Python 3.14 with a missing
  `pydantic_core._pydantic_core`; importing `pydantic` aborts during conftest load.
  Carried from 05-01/05-02.
- **Fix:** Ran every `<verify>` under `.venv/bin/python`.
- **Files modified:** none
- **Verification:** all listed verify commands pass under `.venv/bin/python`.

**4. [Rule 1 - Bug] Test assertions adjusted for Jinja autoescape and the code element**
- **Found during:** Task 3 (first test run)
- **Issue:** The rationale contains an apostrophe, which autoescape renders as `&#39;`,
  so the literal rationale substring never matched; and the evidence-id assertion was a
  fragile "40 chars before the id" check.
- **Fix:** Assert an apostrophe-free rationale substring, and assert
  `<code>skill.python</code>` — which also proves the id is text, not a link.
- **Files modified:** `tests/api/test_listing_detail.py`
- **Verification:** all five named tests pass.
- **Committed in:** `2e6a293`

---

**Total deviations:** 4 auto-fixed (2 bugs, 2 blockers)
**Impact on plan:** No scope creep. Only `tests/api/test_queue_links.py` is outside the
plan's `files_modified`, and it is a direct consequence of the required row link.

## Issues Encountered

- The reused save/hide block's `hx-target` names the queue row's id, which does not
  exist on the detail page. The POST is still issued and the event appended (the
  append-only log stays consistent); the page shows the new state on reload. This is
  the plan's specified "exact two-form block" and matches Phase 5's no-live-push
  posture, but a future plan may want a detail-page-specific swap target.

## Known Stubs

None. An unscored listing renders its explicit not-yet-ranked paragraph rather than a
placeholder value.

## Threat Flags

None beyond the plan's threat model. T-05-12 is verified by
`test_detail_escapes_untrusted_title_and_rationale`; T-05-13 by the `int` path
parameter (FastAPI 422 before SQL); T-05-15 by the reused `read_row` scheme gate and
the anchored external links; T-05-16 by the shared event vocabulary.

## Next Phase Readiness

- Phase 6 can read `score_repo.read_score_for_listing` (or reuse this page) for the
  stored requirement breakdown it patches the CV against.
- The detail page is the natural host for Phase 6's CV preview (D-96).
- Open (the plan's flagged assumption): the layout/grouping of the fit breakdown — a
  factor table followed by a requirement list — is a presentation choice a human should
  confirm.

## Self-Check: PASSED

- All three created files exist on disk.
- All three commits (`c069070`, `58580ae`, `2e6a293`) exist in the history.
- `commits: 3` was measured from the plan ledger
  (`plan_head_before = 1330a67e88ad6abaa8fc812e18c5abb8a235cb98`).

---
*Phase: 05-ranking-core-value*
*Completed: 2026-09-22*
