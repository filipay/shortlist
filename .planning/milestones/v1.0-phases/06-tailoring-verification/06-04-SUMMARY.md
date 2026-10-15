---
phase: 06-tailoring-verification
plan: 04
subsystem: ui
tags: [fastapi, sqlalchemy, jinja2, csv-artifacts, access-control, pypdf, tailwind]

requires:
  - phase: 06-tailoring-verification
    plan: 01
    provides: the cv_artifacts repository and writer, the four tailoring routes, the compile path that writes blocked/failed/ok rows
  - phase: 06-tailoring-verification
    plan: 02
    provides: the persisted merged VerificationResult (checks with id/status/detail/offending)
  - phase: 06-tailoring-verification
    plan: 03
    provides: the tailoring page states and the review fragment
provides:
  - "read_for_download(ok_only=True), the by-id access control matching latest_for_listing(ok_only=True)"
  - "the cv/pdf route: inline preview by default, attachment on ?download=1, and a 404 for any non-ok/absent artifact"
  - "the _cv_findings.html fragment and the retained-history list on the tailoring page"
  - "the P14 failure-path suite pinning that a blocked or failed CV is unreachable"
affects: [07-apply-and-track]

actuals:
  tokens: 8459
  tasks: 3
  # 3 task commits + this plan's metadata commit.
  commits: 4
  plan_head_before: 82728f606303a0ed0996207250f8b5d84aadf65c

tech-stack:
  added: []
  patterns:
    - "an ok-only selection predicate applied IN SQL as the single artifact-access control"
    - "route-level refusal as the second layer over the repository predicate"
    - "a download filename built from integer ids, never from request text"
    - "a findings fragment that renders a block as a reviewable outcome with no corrective control"

key-files:
  created:
    - app/web/templates/html/_cv_findings.html
    - tests/db/test_cv_artifact_repo.py
    - tests/api/test_cv_pdf_route.py
    - tests/api/test_cv_artifact_blocked.py
  modified:
    - app/db/repositories/cv_artifact_repo.py
    - app/api/tailoring.py
    - app/web/templates/html/tailoring.html

key-decisions:
  - "read_for_download applies the same SQL-level compile_status == ok predicate as latest_for_listing, so a blocked row is unreachable by id — the contract Phase 7's attach query will consume"
  - "The PDF route's 404 names the cause honestly (data-error=no-ok-artifact) and a missing file is a 404, never a 500"
  - "The download filename is derived from the two integer ids (listing, artifact), never from the stored or request-supplied name"
  - "The blocked page parses the persisted VerificationResult (degrading to an empty list on an odd blob), renders the findings, and offers no corrective control — recovery is the page's own fresh-tailor generate control"
  - "Retention/pruning is deliberately deferred: history_for_listing returns every row and the page lists them, but implements no cap (Phase 8)"

patterns-established:
  - "A verification failure is a block, not a dead end: the persisted findings are shown and the only recovery is a fresh tailor"
  - "Recency never beats verification: a newer blocked row does not hide an older ok artifact from the download route"

requirements-completed: [TAIL-05, UI-05]

coverage:
  - id: D1
    description: "The ok-only predicate is enforced in SQL by both latest_for_listing and read_for_download; blocked and failed rows are excluded while history still returns them"
    requirement: TAIL-05
    verification:
      - kind: unit
        ref: "tests/db/test_cv_artifact_repo.py::test_a_newer_blocked_row_is_not_returned_by_the_ok_only_read"
        status: pass
      - kind: unit
        ref: "tests/db/test_cv_artifact_repo.py::test_read_for_download_excludes_blocked_and_failed"
        status: pass
    human_judgment: false
  - id: D2
    description: "The PDF route serves an ok artifact inline by default and as an attachment with ?download=1, and returns 404 for a blocked, failed, missing-file or absent artifact without reading a path from request text"
    requirement: UI-05
    verification:
      - kind: integration
        ref: "tests/api/test_cv_pdf_route.py::test_the_default_disposition_is_inline"
        status: pass
      - kind: integration
        ref: "tests/api/test_cv_pdf_route.py::test_download_1_sets_an_attachment_disposition"
        status: pass
      - kind: integration
        ref: "tests/api/test_cv_pdf_route.py::test_a_blocked_only_listing_returns_404"
        status: pass
      - kind: integration
        ref: "tests/api/test_cv_pdf_route.py::test_the_route_ignores_a_path_like_query_param"
        status: pass
    human_judgment: false
  - id: D3
    description: "A blocked or failed artifact is unreachable by route and by accessor, and a newer blocked row never hides an older ok artifact"
    requirement: TAIL-05
    verification:
      - kind: integration
        ref: "tests/api/test_cv_artifact_blocked.py::test_a_blocked_artifact_is_never_downloadable"
        status: pass
      - kind: integration
        ref: "tests/api/test_cv_artifact_blocked.py::test_a_blocked_row_over_an_ok_row_still_serves_the_ok_pdf"
        status: pass
    human_judgment: false
  - id: D4
    description: "A warn-only artifact is ok and downloadable (D-114), and the blocked page renders the failing findings with no download or corrective control"
    requirement: TAIL-05
    verification:
      - kind: integration
        ref: "tests/api/test_cv_artifact_blocked.py::test_a_warn_only_artifact_is_downloadable"
        status: pass
    human_judgment: false
  - id: D5
    description: "The findings fragment as the human reads it — a failing check visibly distinct from a warning, and the block legible as a reviewable outcome"
    verification: []
    human_judgment: true
    rationale: "Automation asserts presence and the absence of a download/repair control; whether the fail-vs-warn distinction reads clearly and the block feels like a reviewable outcome is a human visual judgment. TAIL-05's cross-phase 'attach' claim also stays FLAGGED until Phase 7's attach query consumes the ok-only selection."

duration: 15min
completed: 2026-09-24
status: complete
---

# Phase 06 Plan 04: A blocked CV can never be downloaded or attached; the app previews and downloads the verified one

**The `ok`-only selection is enforced in SQL by both the latest and by-id accessors and again at the PDF route, the verified CV previews inline and downloads on request, and a blocked artifact is explained from its persisted findings with no corrective control.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-09-24T17:19:00Z
- **Completed:** 2026-09-24T17:33:53Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added `read_for_download(ok_only=True)` with the same SQL-level `compile_status == "ok"` predicate as `latest_for_listing`, so a blocked or failed artifact is unreachable **even by id**; the module docstring states the D-118 contract Phase 7's attach path consumes. History still returns every row, blocked and failed included.
- Completed the `GET …/cv/pdf` route: it selects through the ok-only accessor, returns a 404 fragment (`data-error="no-ok-artifact"`) for any non-ok or absent artifact, treats a missing file as a 404 rather than a 500, serves `inline` by default and `attachment` with `?download=1`, and builds the filename from the two integer ids — never from request text.
- Added `_cv_findings.html`, which renders each persisted `CheckResult` (id, status badge, detail, offending ids), makes `warn` visibly distinct from `fail`, and names a fresh tailoring as the only recovery with no corrective control.
- The tailoring page now parses the persisted verification, includes the findings for a blocked artifact, and lists the retained history with a download affordance only on `ok` entries.
- Added the PITFALLS P14 failure-path suite: blocked and failed are unreachable by route and by accessor, a newer blocked row still serves the older `ok` PDF, a warn-only artifact downloads, and the blocked page shows no download or repair control.
- 1221 tests pass in the hermetic lane; `ruff check` clean; `compileall` clean.

## Task Commits

Each task was committed atomically:

1. **Task 1: The ok-only artifact selection is the access control** — `e4b5996` (feat)
2. **Task 2: The PDF route previews inline and downloads on demand** — `2bdd746` (feat)
3. **Task 3: The P14 failure-path suite and the blocked findings the user can read** — `53f00d5` (feat)

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified

- `app/db/repositories/cv_artifact_repo.py` — `read_for_download`, the SQL-level `ok` predicate on both accessors, the D-118 contract in the docstring
- `app/api/tailoring.py` — the inline/attachment PDF response with the integer-id filename, the `no-ok-artifact` 404, and `_parse_findings` + the blocked findings/history page context
- `app/web/templates/html/_cv_findings.html` — the per-check findings fragment, warn visibly non-blocking
- `app/web/templates/html/tailoring.html` — the findings include for the blocked state and the retained-history list
- `tests/db/test_cv_artifact_repo.py` — the ok-only latest/by-id predicates, history, no-commit writer, status guard
- `tests/api/test_cv_pdf_route.py` — dispositions, the 404s, the missing-file case, the ignored path-like param
- `tests/api/test_cv_artifact_blocked.py` — the P14 failure-path suite

## Decisions Made

- **One predicate, two accessors, in SQL.** `read_for_download` mirrors `latest_for_listing`; no accessor bypasses the predicate and there is no Python post-filter.
- **The route refuses a non-`ok` selection with a 404 that names the cause** (`no-ok-artifact`), and a missing file is a 404, not a 500.
- **The download filename is built from the two integer ids** — the stored path is never renamed for a response, and no request text contributes to a path (T-06-19).
- **A block is explainable.** The page parses the persisted `VerificationResult` (degrading to `[]` on an odd blob) and renders the findings; the only recovery is the page's own fresh-tailor generate control.
- **Retention is Phase 8.** `history_for_listing` returns every row and the page lists them with status and timestamp; no cap is implemented (D-117).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The blocked-page tests needed a SCORED listing**
- **Found during:** Task 3 (the first page assertion failed: no findings rendered)
- **Issue:** the page's `blocked` state is only reachable when the listing has a stored score (D-110); the initially used `_seed_listing` helper seeds an UNSCORED listing, so the page rendered `rank_first` and skipped the findings include.
- **Fix:** the blocked suite seeds through `_seed_scored_listing`, so the page resolves to `blocked` and renders `_cv_findings.html`.
- **Files modified:** `tests/api/test_cv_artifact_blocked.py`
- **Verification:** all four P14 tests pass.
- **Committed in:** `53f00d5` (Task 3 commit)

**2. [Rule 1 - Bug] The recency test overwrote the ok PDF on disk**
- **Found during:** Task 3 (the ok-vs-blocked recency test served the blocked bytes)
- **Issue:** both seeded artifacts shared one `cv.pdf` path, so writing the blocked file overwrote the ok file the ok row pointed at, and the route correctly served the overwritten content.
- **Fix:** the two artifacts write to distinct filenames (`ok.pdf`, `blocked.pdf`), so the test proves the ok-only selection rather than a filename collision.
- **Files modified:** `tests/api/test_cv_artifact_blocked.py`
- **Verification:** `test_a_blocked_row_over_an_ok_row_still_serves_the_ok_pdf` passes and asserts byte equality with the ok content.
- **Committed in:** `53f00d5` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug), both in the new test suite.
**Impact on plan:** No product-code change beyond the plan; both fixes are test-correctness.

## Issues Encountered

- **Two block-explaining surfaces now coexist, deliberately.** The compile action's immediate response still uses the Python-built `_findings_fragment`, while the page's blocked state uses `_cv_findings.html`. Both name the failing checks; unifying them is a later polish item, not this plan's concern.
- **The history download link points at `/cv/pdf`** (the latest `ok` artifact), since this plan adds no per-artifact PDF route. The plan only required a download affordance on `ok` entries, which this satisfies.

## Known Stubs

None.

## Next Phase Readiness

- Phase 7's attach path must consume `read_for_download(ok_only=True)` / `latest_for_listing(ok_only=True)`; the contract is pinned and FLAGGED as a cross-phase claim until that query exists.
- Retention/pruning of `cv_artifacts` rows is Phase 8 (D-117); the history view is unbounded by design here.

---
*Phase: 06-tailoring-verification*
*Completed: 2026-09-24*

## Self-Check: PASSED

- All 4 created files exist; `06-04-SUMMARY.md` exists.
- All 3 task commits exist: `e4b5996`, `2bdd746`, `53f00d5`.
- `git rev-list --count 82728f6..HEAD` = 4 (3 task commits + this metadata commit), matching `actuals.commits`.
