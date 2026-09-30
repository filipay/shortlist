---
phase: 07-assisted-apply-tracker
plan: 04
subsystem: [api, database, ui]
tags: [fastapi, sqlalchemy, jinja2, htmx, applications, tracker, pagination, search]

# Dependency graph
requires:
  - phase: 07-assisted-apply-tracker
    provides: "07-01's application_repo read_tracker/read_history, the /applications page + shared applications_list.html fragment, and the .badge-stage-* / .next-overdue CSS"
provides:
  - "read_tracker stage/q/offset/limit filters returning a frozen TrackerPage (mirrors QueuePage)"
  - "a needs-action view: (next_action_at IS NULL), next_action_at ASC, TERMINAL_STATUSES excluded, overdue derived at read time"
  - "the tracker filter form (Search / Stage / Needs action) and the two-way pager over one shared fragment"
affects: [07-05-drafted-answers]

# Actuals (#2632) — pairs with the plan's `estimate`.
actuals:
  tokens: 8780
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A filtered read returns a frozen *Page value (rows/total/offset/limit/has_more + query) mirroring QueuePage, so the fragment rebuilds its own pager URLs and the page and the swap cannot drift"
    - "Allow-listed query params validated before SQL: stage raises ValueError; view is coerced to its one literal in the route"
    - "A predicate change carries no offset; only the pager carries one — the client-side reset convention, pinned by a pure query_string test"

key-files:
  created: []
  modified:
    - app/db/repositories/application_repo.py
    - app/api/applications.py
    - app/web/templates/html/applications.html
    - app/web/templates/html/applications_list.html
    - tests/db/test_application_repo.py
    - tests/api/test_applications_tracker.py

key-decisions:
  - "read_tracker now returns a frozen TrackerPage (rows/total/offset/limit/has_more + TrackerQuery) rather than a list, so the fragment owns its pager URLs exactly as queue_list.html does"
  - "stage is validated against APPLICATION_STATUSES BEFORE SQL and raises ValueError; the route turns that into a 422 data-error refusal (T-07-04-01, fail closed)"
  - "q is a bounded Python-side casefold substring over title/company/notes; the ceiling and the FTS upgrade path are named in a ponytail comment (07-RESEARCH Q4/A4)"
  - "needs-action orders (next_action_at IS NULL), next_action_at ASC with an id DESC tie-break and excludes TERMINAL_STATUSES; overdue stays derived at read time, never stored"
  - "paging reuses Settings.queue_page_size and the queue's #queue-pager / #queue-page-position ids — no new Settings field and no new pager class"

requirements-completed: [APPLY-06, UI-04]

coverage:
  - id: D1
    description: "The tracker slices by stage, searches company/title/notes case-insensitively, and pages two-way over one shared fragment definition; an unknown stage is refused before SQL."
    requirement: UI-04
    verification:
      - kind: unit
        ref: "tests/db/test_application_repo.py#test_read_tracker_stage_filter"
        status: pass
      - kind: unit
        ref: "tests/db/test_application_repo.py#test_read_tracker_search_matches_company_title_and_notes"
        status: pass
      - kind: unit
        ref: "tests/db/test_application_repo.py#test_read_tracker_paginates_two_way"
        status: pass
      - kind: unit
        ref: "tests/db/test_application_repo.py#test_read_tracker_unknown_stage_is_a_value_error"
        status: pass
      - kind: integration
        ref: "tests/api/test_applications_tracker.py#test_stage_filter_over_http"
        status: pass
      - kind: integration
        ref: "tests/api/test_applications_tracker.py#test_search_filter_over_http"
        status: pass
    human_judgment: false
  - id: D2
    description: "The needs-action view surfaces overdue next actions first (ascending), then upcoming, nulls last, with terminal stages excluded, and renders the documented Nothing-needs-action empty copy."
    requirement: APPLY-06
    verification:
      - kind: unit
        ref: "tests/db/test_application_repo.py#test_needs_action_ordering"
        status: pass
      - kind: integration
        ref: "tests/api/test_applications_tracker.py#test_needs_action_view_over_http"
        status: pass
      - kind: integration
        ref: "tests/api/test_applications_tracker.py#test_needs_action_view_renders_the_nothing_needs_action_copy"
        status: pass
    human_judgment: false

# Metrics
duration: ~38 min
completed: 2026-09-30
status: complete
---

# Phase 7 Plan 4: Tracker slice-and-dice Summary

**The `/applications` tracker gained a stage filter, a casefold company/title/notes search, a two-way pager, and a needs-action view that surfaces overdue next actions first — all over the one shared fragment, with `stage`/`view` validated before SQL.**

## Performance

- **Duration:** ~38 min
- **Started:** 2026-09-30T16:28Z
- **Completed:** 2026-09-30T17:06Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- `application_repo.read_tracker` grew `stage`/`q`/`view`/`offset`/`limit` and now returns a frozen `TrackerPage` (with `TrackerQuery`) mirroring `QueuePage` — `has_prev`/`prev_offset`/`page_index`/`page_count`/`next_offset` — so the fragment rebuilds its own pager URLs.
- The stage filter validates against `APPLICATION_STATUSES` before any SQL (a `ValueError` the route renders as a 422 `data-error` refusal); the search is a bounded Python casefold substring over `listings.title`, `companies.name` and `applications.notes`, with the ceiling and FTS upgrade path named in a `ponytail:` comment.
- The needs-action view orders `(next_action_at IS NULL), next_action_at ASC` with an `id DESC` tie-break and excludes `TERMINAL_STATUSES`; `overdue` remains a read-time derivation, never a stored column.
- The page's filter form (Search / Stage / Needs action) and the two-way pager reuse the queue's markup, `Settings.queue_page_size`, and the existing `#queue-pager` / `#queue-page-position` ids — no new Settings field, no new class.

## Task Commits

Each task was committed atomically:

1. **Task 1: Stage filter, free-text search, and the two-way pager** - `3d1f01a` (feat)
2. **Task 2: The needs-action view** - `d006dc7` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `app/db/repositories/application_repo.py` - `TrackerQuery`/`TrackerPage`, the extended `read_tracker` (stage/q/view/offset/limit), and `_row_matches`
- `app/api/applications.py` - `_parse_tracker_query`, the widened `_list_context`, and the page/list routes passing query params
- `app/web/templates/html/applications.html` - the filter form (`Search` / `Stage` / `Needs action`)
- `app/web/templates/html/applications_list.html` - filtered-/needs-action empty states and the two-way pager
- `tests/db/test_application_repo.py` - stage/search/paging/needs-action tests, plus the existing `read_tracker` callers updated to `.rows`
- `tests/api/test_applications_tracker.py` - the HTTP stage/search/view/filtered-empty tests

## Decisions Made
- **`read_tracker` returns a page value, not a list** — the fragment needs `page.query.query_string(offset=...)` to emit pager URLs without re-deriving them; the change mirrors `QueuePage` exactly and the two existing callers were updated to `.rows`.
- **Fail closed on an unknown stage** — validated in the repository before SQL (`ValueError`), rendered as a 422 `data-error` fragment by the route, never a silently-empty table (T-07-04-01).
- **`view` coerced, not trusted** — the route maps only the literal `needs_action` into the repo; any other value degrades to no view (the queue's `sort` convention).
- **`q` is a bounded Python scan** — accepted at 1–5 users per 07-RESEARCH Q4/A4; the FTS index over `listings(title, company)` + `applications(notes)` is the named upgrade path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added an "All stages" empty option to the Stage select**
- **Found during:** Task 1 (filter form)
- **Issue:** A `<select name="stage">` whose only options are the eight frozen stages has no way to represent "no filter": the browser would select the first option (`discovered`) by default, and because the controls `hx-include="closest form"`, every subsequent search or toggle would silently filter the tracker to `discovered`.
- **Fix:** A leading `<option value="">All stages</option>` selected when `page.query.stage` is `None`; the route already maps a blank/absent `stage` to `None`.
- **Files modified:** `app/web/templates/html/applications.html`
- **Verification:** `tests/api/test_applications_tracker.py` (search/stage tests and the unfiltered page render pass)
- **Committed in:** `3d1f01a` (Task 1)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** The empty option is the correctness precondition for the stage filter; without it the filter would be permanently on. No scope creep.

## Issues Encountered
- The needs-action SQL landed in the Task 1 repository delta (inert until the route passed `view`) and was wired end-to-end in Task 2. The behaviour and its test (`test_needs_action_ordering`) ship in Task 2 as the plan specifies; the sequencing only means Task 2's diff is the route coercion, the empty copy, and the tests.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The tracker is sliceable by stage, searchable, two-way pageable, and has a needs-action view — UI-04's "view and manage" slice is complete.
- Ready for 07-05 (drafted answers), the last phase plan; it does not depend on this plan's repository changes.
- Full suite was not re-run for this plan (the two target files + ruff + the stylesheet/auth-seam guards are green); the phase gate runs the full hermetic lane before `/gsd-verify-work`.

---
*Phase: 07-assisted-apply-tracker*
*Completed: 2026-09-30*

## Self-Check: PASSED

- All 6 modified files and this SUMMARY exist on disk (`[ -f ]` verified).
- Both task commits exist: `3d1f01a` and `d006dc7`.
- `pytest -q tests/db/test_application_repo.py tests/api/test_applications_tracker.py`: **30 passed**.
- `ruff check app/db/repositories/application_repo.py app/api/applications.py`: clean.
- `pytest -q tests/test_stylesheet_coverage.py tests/test_auth_seam.py`: **10 passed**.

