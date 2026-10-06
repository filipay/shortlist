---
phase: 07-assisted-apply-tracker
plan: 09
subsystem: api
tags: [fastapi, sqlalchemy, jinja2, cv-artifact, access-control, gap-closure]
requires:
  - phase: 06-tailoring-verification
    provides: the ok-only cv_artifact_repo.read_for_download/latest_for_listing selection and the GET /listings/{id}/cv/pdf route (D-118)
  - phase: 07-assisted-apply-tracker
    provides: the tailoring review page and its 'Previous compiles' history list (07-01 … 07-06)
provides:
  - "GET /listings/{id}/cv/pdf accepts an optional ?artifact_id= and serves that named ok artifact, with a listing-ownership check"
  - "Each 'Previous compiles' row links to its own artifact id; the persistent Latest CV control stays parameterless"
  - "The compile banner emits no download anchor, so a compile yields exactly one latest download control"
  - "Regression tests for per-artifact serving, foreign/blocked/unknown refusal, and the single-affordance contract"
affects: [07-verification, 07-uat, 07-07]
actuals:
  tokens: 920
  tasks: 2
  commits: 2
  plan_head_before: ac783e52d2580622643a2e3437da966e0a901114
tech-stack:
  added: []
  patterns:
    - "Optional query selector with a URL-scoped ownership re-check: the id only chooses a row, the listing id scopes it, and the served path is always the stored pdf_path"
key-files:
  created: []
  modified:
    - app/api/tailoring.py
    - app/web/templates/html/tailoring.html
    - tests/api/test_cv_pdf_route.py
    - tests/api/test_tailoring_review.py
    - tests/api/test_tailoring_generate.py
key-decisions:
  - "tailored_cv_pdf takes artifact_id:int|None=None; absent keeps latest_for_listing(ok_only=True), so every pre-existing caller and the persistent Latest CV control is byte-for-byte unchanged."
  - "A selected row must satisfy record.listing_id == listing_id; a foreign id is the same 404 data-error=no-ok-artifact as a missing, blocked or failed one, so this listing's URL can never serve another listing's PDF (T-07-09-01/T-07-09-03)."
  - "The ok_only=True predicate stays applied in SQL (read_for_download), preserving D-118 access control; a blocked/failed artifact is never retrievable by id."
  - "_compiled_fragment no longer emits a download anchor: the persistent 'Latest CV' section is the single affordance for the newest artifact (G-07-4)."
patterns-established:
  - "Per-affordance artifact serving: a history row's version-exact link plus a request-scoped ownership check, rather than one route that always resolves to the latest."
requirements-completed: [APPLY-01]
coverage:
  - id: D1
    description: "A request naming an artifact id serves that row's own PDF bytes, not the latest ok artifact"
    requirement: "APPLY-01"
    verification:
      - kind: integration
        ref: "tests/api/test_cv_pdf_route.py#test_a_named_artifact_serves_its_own_file_not_the_latest"
        status: pass
    human_judgment: false
  - id: D2
    description: "A blocked id, an unknown id, and an ok artifact belonging to a different listing are each refused as the same 404; no-parameter requests still serve the latest ok PDF"
    requirement: "APPLY-01"
    verification:
      - kind: integration
        ref: "tests/api/test_cv_pdf_route.py#test_a_named_blocked_artifact_is_a_404"
        status: pass
      - kind: integration
        ref: "tests/api/test_cv_pdf_route.py#test_an_artifact_belonging_to_another_listing_is_a_404"
        status: pass
      - kind: integration
        ref: "tests/api/test_cv_pdf_route.py#test_an_unknown_artifact_id_is_a_404"
        status: pass
    human_judgment: false
  - id: D3
    description: "After a compile the page offers exactly one parameterless latest download control; the compile banner carries no anchor"
    requirement: "APPLY-01"
    verification:
      - kind: integration
        ref: "tests/api/test_tailoring_review.py#test_a_compile_yields_exactly_one_latest_download_control"
        status: pass
      - kind: integration
        ref: "tests/api/test_tailoring_review.py#test_compiled_fragment_with_no_drops_is_the_compile_marker_only"
        status: pass
      - kind: integration
        ref: "tests/api/test_tailoring_generate.py#test_compile_writes_one_ok_row_and_the_page_offers_the_download"
        status: pass
    human_judgment: false
duration: 7min
completed: 2026-10-05
status: complete
---

# Phase 07 Plan 09: G-07-4 version-exact CV download affordances Summary

**Each CV download affordance now serves the artifact it labels: `?artifact_id=` selects an ok, listing-owned row while the persistent Latest CV control stays parameterless, and the compile banner no longer duplicates that control.**

## Performance

- **Duration:** 7 min (implementation); finalized on resume 2026-10-06 after an interruption before the SUMMARY was written
- **Started:** 2026-10-05T23:13:47Z
- **Completed:** 2026-10-05T23:20:15Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `GET /listings/{id}/cv/pdf` now accepts an optional `?artifact_id=` selector: with it, the named artifact is served via `cv_artifact_repo.read_for_download(ok_only=True)`; without it, the existing `latest_for_listing(ok_only=True)` path is untouched, so every pre-existing caller and the persistent Latest CV control keep working.
- The route re-checks `record.listing_id == listing_id`, so a foreign listing's artifact is the same 404 `data-error=no-ok-artifact` as a missing, blocked or failed row — this listing's URL can never serve another listing's PDF. The `ok_only=True` SQL predicate (D-118) is preserved, so a blocked/failed artifact stays unreachable by id, and the served path remains the selected row's stored `pdf_path` under the resolved `artifacts_dir` (never built from request text).
- Every 'Previous compiles' row now links to its own artifact id (`?artifact_id={{ entry.id }}`), so clicking an older row downloads that row's PDF instead of the newest one.
- `_compiled_fragment` no longer emits a download anchor: a freshly compiled page and a reloaded page both offer exactly one latest download control (the persistent 'Latest CV' section), removing the duplicate affordance G-07-4 identified.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add an optional, listing-scoped artifact id to the PDF route and link each history row to its own artifact** - `e3ab2d1` (feat)
2. **Task 2: Remove the duplicate post-compile download control and pin the single-affordance contract** - `13b3009` (fix)

**Plan metadata:** (docs commit, follows this file)

_Note: This run resumed after the implementation commits were already made; no code was re-implemented, amended, or reverted. The SUMMARY records the two commits measured from the plan ledger (`plan_head_before ac783e5`, 2 commits)._

## Files Created/Modified

- `app/api/tailoring.py` - `tailored_cv_pdf` takes `artifact_id: int | None = None`, selects via `read_for_download(ok_only=True)` and enforces the ownership check; docstring updated. `_compiled_fragment` drops the download anchor (signature now takes only `record`).
- `app/web/templates/html/tailoring.html` - 'Previous compiles' row link carries `?artifact_id={{ entry.id }}`; the persistent Latest CV download stays parameterless.
- `tests/api/test_cv_pdf_route.py` - new coverage: named-artifact exact serving, blocked id 404, foreign-listing id 404, unknown id 404.
- `tests/api/test_tailoring_review.py` - fragment tests now assert the compile marker only (no anchor); new regression test pins exactly one parameterless latest download control after a compile.
- `tests/api/test_tailoring_generate.py` - the compile-flow test's banner assertion moved from "returns a download link" to "the page offers the download", since the banner no longer carries the anchor.

## Decisions Made

- The optional selector keeps the no-parameter behavior identical (`latest_for_listing(ok_only=True)`), so the persistent Latest CV control and all existing callers need no change.
- A selected artifact must belong to the listing (`record.listing_id == listing_id`); a foreign id collapses to the same 404 as missing/blocked/failed, so the listing id in the path genuinely scopes the selection (T-07-09-01, T-07-09-03).
- The `ok_only=True` SQL predicate is retained in both selection paths, preserving D-118 access control (T-07-09-02): the request id only chooses a row, never a filesystem path.
- The compile banner intentionally emits no download anchor; the persistent Latest CV section is the single latest-download affordance.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Updated `tests/api/test_tailoring_generate.py`, which the plan's `files_modified` did not list**

- **Found during:** Task 2 (removing the banner anchor)
- **Issue:** `test_compile_writes_one_ok_row_and_returns_a_download_link` asserted the compile response itself contained the download link. Removing the duplicate anchor per the plan made that assertion fail — the test encoded the very duplication G-07-4 removes, so it had to move with the fix.
- **Fix:** Renamed to `test_compile_writes_one_ok_row_and_the_page_offers_the_download`; it now asserts the compile flow still exposes the download on the page while the fragment banner carries no anchor.
- **Files modified:** `tests/api/test_tailoring_generate.py`
- **Verification:** `tests/api/test_tailoring_review.py` and `tests/api/test_tailoring_generate.py` pass; combined verification run is 36 passed.
- **Committed in:** `13b3009` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Necessary consequence of Task 2 — a test asserting the removed behavior had to be updated with it. No scope creep beyond the plan's intent.

## Issues Encountered

- The prior run was interrupted after both task commits landed but before the SUMMARY and tracking updates. This resume confirmed the two committed tasks against the plan's `<done>` criteria and `must_haves`, re-ran the plan's two `<verify>` blocks (green, 36 passed), and made no code changes.

## Verification Evidence

- `<verify>` Task 1 and Task 2, run together:
  `.venv/bin/python -m pytest -q tests/api/test_cv_pdf_route.py tests/api/test_tailoring_review.py` → **36 passed**.
- `must_haves` confirmed: named artifact serves its own PDF; a compile yields exactly one latest download control; foreign/blocked/failed ids are 404; no-parameter requests still serve the latest ok PDF.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None - no new security-relevant surface beyond the plan's `<threat_model>`; the change tightens access control (addresses T-07-09-01/T-07-09-02/T-07-09-03).

## Next Phase Readiness

- G-07-4 is closed: every download affordance serves the artifact it labels.
- Remaining Phase 07 gap-closure plan 07-07 (G-07-3) and the phase re-verification can proceed.

---

## Self-Check: PASSED

- `app/api/tailoring.py`, `app/web/templates/html/tailoring.html`, `tests/api/test_cv_pdf_route.py`, `tests/api/test_tailoring_review.py`, `tests/api/test_tailoring_generate.py` exist on disk.
- Task commits `e3ab2d1` and `13b3009` exist in git history; measured `git rev-list --count ac783e5..HEAD` = 2.

---
*Phase: 07-assisted-apply-tracker*
*Completed: 2026-10-05*
