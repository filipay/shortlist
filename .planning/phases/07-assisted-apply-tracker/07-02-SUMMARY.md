---
phase: 07-assisted-apply-tracker
plan: 02
subsystem: [api, ui]
tags: [fastapi, jinja2, htmx, alpine, apply-package, no-submit, ok-artifact-gate]

# Dependency graph
requires:
  - phase: 06-tailoring-verification
    provides: "cv_artifact_repo.latest_for_listing(ok_only=True) — the SQL-level ok-only selection the package gate consumes (D-118/D-121)"
  - phase: 07-assisted-apply-tracker
    provides: "POST /applications/record (07-01) — the record path the package's form posts to; application_repo's ok-only picker source"
provides:
  - "GET /listings/{id}/apply: ONE package_state (gated|ready) computed from stored data only, no LLM call on open (D-122)"
  - "app/web/templates/html/apply.html: the gated panel + the five ready blocks (reassurance, outbound anchor, verified PDF, gaps, record form)"
  - "the no-submit guarantee pinned by test_no_submit_surface (APPLY-02)"
affects: [07-05-drafted-answers]

# Actuals (#2632) — pairs with the plan's `estimate` (52000 chars/4 tokens; low confidence).
actuals:
  tokens: 7307
  tasks: 2
  commits: 2
  plan_head_before: a672be5499c012bc773c8635bf3c734ed833b685

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "The package page computes ONE package_state in the route and the template branches on it only (mirrors app/api/tailoring.py)"
    - "The outbound action is a plain anchor; the absence of a submit path is pinned by a test that fails if one is ever added"
    - "The ok-only picker reuses application_repo's SQL-level ok selection, so the package and tracker pickers cannot drift"

key-files:
  created:
    - app/api/apply.py
    - app/web/templates/html/apply.html
    - tests/api/test_apply_package.py
  modified:
    - app/main.py
    - app/web/templates/html/listing_detail.html
    - static/vendor/app.css
    - tests/test_auth_seam.py

key-decisions:
  - "The package gate is latest_for_listing(ok_only=True), so the verified-PDF block and the outbound apply link are unreachable while gated; a blocked artefact reads exactly like no artefact (D-118/D-121)"
  - "The gap checklist filters to verdict gap|partial: the heading promises what the CV does NOT show, so a met requirement is deliberately excluded (D-123)"
  - "The ok-only picker reuses application_repo._ok_artifacts_by_listing rather than writing a second ok-only query, so the package and tracker pickers cannot drift"
  - "A missing apply_url renders the documented fallback text as a plain paragraph, never an anchorless/dead link (D-127)"

patterns-established:
  - "The no-submit surface is a negative guarantee proven by a test (every form posts locally; no route path leaves the app), not merely a missing feature"

requirements-completed: [APPLY-01, APPLY-02]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "GET /listings/{id}/apply gates on an ok cv_artifact: gated renders the panel + /cv CTA with the ready blocks absent; ready renders the verified PDF and the outbound apply link"
    requirement: APPLY-01
    verification:
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_gated_without_an_ok_artifact"
        status: pass
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_a_blocked_artifact_is_gated_not_ready"
        status: pass
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_ready_with_an_ok_artifact"
        status: pass
    human_judgment: false
  - id: D2
    description: "The read-only gap checklist renders the stored ranking gaps (met excluded) and the documented empty copy when none are stored"
    requirement: APPLY-01
    verification:
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_gap_checklist_renders_the_stored_gaps"
        status: pass
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_gap_checklist_empty_copy_when_no_gaps_stored"
        status: pass
    human_judgment: false
  - id: D3
    description: "No submit surface: every page form posts to a local path, the outbound action is a plain rel=noopener noreferrer anchor, and no route path leaves the app"
    requirement: APPLY-02
    verification:
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_no_submit_surface"
        status: pass
    human_judgment: false
  - id: D4
    description: "Recording from the package reaches the tracker, linked to the ok artefact and stamping applied_at"
    requirement: APPLY-01
    verification:
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_record_from_the_package_links_the_ok_artifact"
        status: pass
    human_judgment: false
  - id: D5
    description: "Opening the package makes no LLM call (D-122); all three page states render while the counting backend records zero calls"
    requirement: APPLY-02
    verification:
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_package_states_and_no_llm_call_on_open"
        status: pass
    human_judgment: false
  - id: D6
    description: "The ready package reads as a designed surface — the reassurance banner, the outbound primary action and the block order"
    verification: []
    human_judgment: true
    rationale: "Whether the no-submit reassurance reads as designed rather than as a missing button is a visual judgement no automated assertion proves; the class-coverage guard only proves a rule exists, not that it reads well."

duration: ~35 min
completed: 2026-09-30
status: complete
---

# Phase 7 Plan 2: The apply package page — the ok-artefact gate, the outbound link, the gap checklist, and the no-submit guarantee Summary

**`GET /listings/{id}/apply` assembles the package from stored data only — gated on an `ok` CV artefact — showing the verified PDF, a plain outbound apply anchor, the read-only gap checklist and a record form, with no submit path anywhere pinned by a test that fails if one is added.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 2
- **Files modified:** 7 (3 created, 4 modified)

## Accomplishments
- `app/api/apply.py` computes ONE `package_state` (`gated` | `ready`) from stored rows: the page makes no LLM call on open (D-122). `gated` (no `ok` artefact) renders a `.tailoring-empty` panel with `data-state="no-ok-artifact"` and the `/cv` CTA; the ready blocks are absent entirely, never empty shells.
- The `ready` page renders the five blocks in order: the no-submit reassurance, the outbound `<a class="apply-link" rel="noopener noreferrer">` plain anchor, the verified PDF (`Preview` + `Download the exact PDF you'll send`), the read-only `.requirement-list` gap checklist, and the `Record application` form posting to `/applications/record`.
- The `ok` gate is `latest_for_listing(ok_only=True)` — the `compile_status == 'ok'` predicate applied IN SQL — so a blocked artefact is unreachable and the verified-PDF block/list cannot leak a failed CV (D-118/D-121, T-07-02-03).
- The gap checklist filters to `verdict in {gap, partial}`; a `met` requirement is excluded, and with no stored gaps the documented empty copy renders instead of an empty list (D-123).
- The no-submit surface is a proven negative: every form posts to a local path, the external action is a plain anchor, and no route path leaves the app (`test_no_submit_surface`). Opening the package is proven to make zero LLM calls via a counting `OfflineLLMBackend`.
- The detail page gains one `Apply package` link beside the tailoring link, reusing `.listing-detail-link` (no new rule); `.apply-assurance` copies `.merges-note` and `.apply-link` copies `#run-search-now`.

## Task Commits

Each task was committed atomically:

1. **Task 1: The apply package page — gate, verified PDF, apply link, gap checklist, record form** - `ac80a72` (feat)
2. **Task 2: The no-submit guarantee and the record-from-package path** - `028a7c6` (test)

**Plan metadata:** docs commit follows.

## Files Created/Modified
- `app/api/apply.py` - `GET /listings/{id}/apply`: the `package_state` gate and the stored-data assembly
- `app/web/templates/html/apply.html` - the package shell: gated panel + the five ready blocks
- `app/main.py` - registers the apply router beside `tailoring_routes`
- `app/web/templates/html/listing_detail.html` - the `Apply package` link beside the tailoring link
- `static/vendor/app.css` - `.apply-assurance` (copies `.merges-note`) and `.apply-link` (copies `#run-search-now`)
- `tests/api/test_apply_package.py` - the page-state, no-submit, no-LLM and record-from-package lanes
- `tests/test_auth_seam.py` - `/listings/{listing_id}/apply` joins `EXPECTED_SEAM_ROUTES`

## Decisions Made
- The `met` verdict is excluded from the gap checklist because the heading promises only what the CV does not show; the filter lives in the route, so the template has no verdict logic (D-123).
- The ok-only picker reuses `application_repo._ok_artifacts_by_listing` rather than writing a second ok-only SQL query — the same selection the tracker row's picker uses, so the two cannot drift and no new repository surface is added.
- The record form is a plain `method="post" action="/applications/record"` form per the plan; the picker renders always for the no-JS degrade and the server ignores it unless `status=applied` (the 07-01 route's contract).
- `.apply-link` copies `#run-search-now`'s declaration block and adds `display:inline-block; text-decoration:none` so an anchor reads as the filled accent button.

## Deviations from Plan

None - plan executed exactly as written. The two extra page-state tests (`test_a_blocked_artifact_is_gated_not_ready`, `test_gap_checklist_renders_the_stored_gaps`, `test_unknown_listing_returns_a_404_fragment`) are added coverage for the plan's own truths, not scope beyond it.

## Issues Encountered
None. The full suite was green on the first complete run after both tasks.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The package surface is live and gated; 07-05 (drafted answers) extends the ready page with the `#apply-answers` HTMX swap root without changing this plan's blocks.
- Known rough edge (by design, per the plan): the `Record application` form is a plain POST, so with no JS the browser lands on the tracker's list fragment after recording. The route and fragment are 07-01's; a redirect/swap is out of this plan's scope.
- Migration head stays `0006`; no schema or dependency change.

## Self-Check: PASSED

- All 3 created files exist on disk (`[ -f ]` verified).
- Both task commits exist (`ac80a72`, `028a7c6`); plan measured 2 commits from `a672be5`.
- Plan lane: `pytest -q tests/api/test_apply_package.py tests/test_auth_seam.py tests/test_stylesheet_coverage.py` — **20 passed**.
- Full suite: `pytest -q` — **1566 passed, 14 deselected, 2 xfailed**.
- `ruff check` on `app/api/apply.py`, `tests/api/test_apply_package.py`, `tests/test_auth_seam.py` — clean.

---
*Phase: 07-assisted-apply-tracker*
*Completed: 2026-09-30*
