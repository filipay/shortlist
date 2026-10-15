---
phase: 07-assisted-apply-tracker
plan: 08
subsystem: api
tags: [fastapi, httpx, post-redirect-get, gap-closure, tracker, jinja2]
requires:
  - phase: 07-assisted-apply-tracker
    provides: the /applications tracker, the apply package record form (07-01 … 07-06)
provides:
  - "POST /applications/record returns a 303 to /applications after commit (Post/Redirect/Get)"
  - "Regression tests pinning the 303 and the full stylesheet-bearing tracker landing page"
affects: [07-09, 07-verification, 07-uat]
actuals:
  tokens: 2425
  tasks: 2
  commits: 2
plan_head_before: f88e805e851f783b6cba142a2b710e17824e402d
tech-stack:
  added: []
  patterns:
    - "Post/Redirect/Get for a plain (non-HTMX) form write: redirect to a fixed server-authored location"
key-files:
  created: []
  modified:
    - app/api/applications.py
    - tests/api/test_applications_tracker.py
    - tests/api/test_apply_package.py
key-decisions:
  - "The record route's success path is a 303 to the fixed literal /applications, mirroring tailoring.py's delete route; no request-derived value enters the location (T-07-08-01)."
  - "The record route is annotated `-> Any` (not `HTMLResponse | RedirectResponse`), because FastAPI infers a response model from a union annotation and fails at import; `Any` mirrors tailoring.py's delete route."
  - "No HTMX branch was added: the plain form's full navigation is the correct no-JavaScript behavior."
requirements-completed: [APPLY-03, APPLY-06, UI-04]
coverage:
  - id: D1
    description: "A successful plain-form submit of the record route returns 303 to /applications instead of the bare applications_list.html fragment"
    requirement: "APPLY-03"
    verification:
      - kind: integration
        ref: "tests/api/test_applications_tracker.py#test_record_route_is_not_shadowed_by_the_dynamic_route"
        status: pass
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_record_from_the_package_links_the_ok_artifact"
        status: pass
    human_judgment: false
  - id: D2
    description: "The followed landing page is a full document extending base.html, carrying /static/vendor/app.css and the new row"
    requirement: "UI-04"
    verification:
      - kind: integration
        ref: "tests/api/test_applications_tracker.py#test_record_submit_lands_on_the_full_styled_tracker_page"
        status: pass
    human_judgment: false
  - id: D3
    description: "Refusal branches (unknown listing/stage, applied without an ok artefact) keep their fragments, status codes and no-write behavior"
    requirement: "APPLY-06"
    verification:
      - kind: integration
        ref: "tests/api/test_applications_tracker.py#test_record_refuses_an_applied_stage_without_an_ok_artifact"
        status: pass
    human_judgment: false
duration: 7min
completed: 2026-10-05
status: complete
---

# Phase 07 Plan 08: G-07-1 record-submit lands on the styled tracker Summary

**Record-submit now Post/Redirect/Gets to the styled `/applications` tracker, with regression tests pinning the 303 and a full stylesheet-bearing landing page**

## Performance

- **Duration:** 7 min
- **Started:** 2026-10-05T22:53:04Z
- **Completed:** 2026-10-05T22:59:51Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `POST /applications/record` returns `RedirectResponse(url="/applications", status_code=303)` after the single `session.commit()`, replacing the bare `applications_list.html` fragment response that stranded the user on an unstyled page (G-07-1).
- Every refusal branch is byte-for-byte unchanged: the unknown-listing 422/404 fragments, the unknown-stage 422 fragment and the `applied-needs-ok-artifact` 409 fragment still return their `data-error` bodies, still write nothing, and their status codes did not move.
- All record-submit tests moved onto the redirect (assert 303 + `location`, then read the tracker via a follow-up GET); a new regression test pins the actual gap — the followed page is a full document with `<!doctype html>`, `href="/static/vendor/app.css"`, `#application-list` and the new row.

## Task Commits

Each task was committed atomically:

1. **Task 1: Return a 303 to /applications and move the shadow test's assertion with it** - `35b5179` (fix)
2. **Task 2: Get every record-submit test onto the redirect and assert the styled landing page** - `977f0aa` (test)

**Plan metadata:** (docs commit, follows this file)

## Files Created/Modified

- `app/api/applications.py` - `record_application_route` now returns a 303 redirect on success; module + route docstrings updated; `RedirectResponse` imported.
- `tests/api/test_applications_tracker.py` - record-submit tests assert the 303 and read the tracker via follow-up GET; new `test_record_submit_lands_on_the_full_styled_tracker_page`.
- `tests/api/test_apply_package.py` - `test_record_from_the_package_links_the_ok_artifact` asserts the 303 then confirms the linked row on the tracker.

## Decisions Made

- The redirect target is the fixed literal `/applications`; no request-derived value enters the location (open-redirect mitigation T-07-08-01).
- The route is annotated `-> Any` rather than `HTMLResponse | RedirectResponse`: FastAPI attempts to build a response model from a union return annotation and raises `FastAPIError` at import. `Any` mirrors `tailoring.py`'s delete route and disables response-model inference.
- No HTMX branch: `apply.html`'s record form is plain (`method="post"`, no `hx-post`), so the redirect is the correct full-navigation and no-JavaScript behavior.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Return annotation broke FastAPI import**

- **Found during:** Task 1 (record route change)
- **Issue:** Annotating the route `-> HTMLResponse | RedirectResponse` made FastAPI try to derive a response model from the union and raise `fastapi.exceptions.FastAPIError: Invalid args for response field!` at import, failing the whole test lane.
- **Fix:** Changed the annotation to `-> Any` (the same shape `app/api/tailoring.py`'s redirect route already uses). The route still declares `response_class=HTMLResponse` and returns either an `HTMLResponse` refusal or the `RedirectResponse`.
- **Files modified:** `app/api/applications.py`
- **Verification:** Task 1 verify (2 tests) and Task 2 verify (50 tests) both pass.
- **Committed in:** `35b5179` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The annotation change is mechanical and mirrors the established `tailoring.py` precedent; no behavior or scope change.

## Issues Encountered

None beyond the annotation fix above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- G-07-1 is closed: the record→review flow lands on the full styled tracker page.
- The remaining Phase 07 gap-closure plans (07-07, 07-09) and the phase re-verification can proceed.
- The phase-scoped suite (`tests/api/test_applications_tracker.py`, `tests/api/test_apply_package.py`, `tests/test_auth_seam.py`) is green at 50 passed.

---
*Phase: 07-assisted-apply-tracker*
*Completed: 2026-10-05*

## Self-Check: PASSED

- All modified files exist on disk.
- Task commits `35b5179` and `977f0aa` exist in git history.
