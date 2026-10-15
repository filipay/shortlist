---
phase: 05-ranking-core-value
plan: 12
subsystem: ui
tags: [htmx, jinja2, fastapi, allow-list, swap-target]

# Dependency graph
requires:
  - phase: 05-ranking-core-value
    provides: the queue read model (`queue_repo.read_row`), the append-only events endpoint and the job detail page
provides:
  - "A single `_action_forms.html` Save/Hide definition shared by the queue row and the detail action section"
  - "A detail-originated action (`surface=detail`) that returns the `_detail_actions.html` section, so the detail page swaps its own markup in place"
  - "An allow-listed `surface` request field (`queue` | `detail`) with a `queue` fallback, recorded in `listing_events.context_json`"
  - "A saved/hidden state indicator and a link to the existing saved view (`GET /?saved=1`) on the detail page"
affects: [06-tailoring, future detail-page work]

# Actuals (#2632) — pairs with the plan's estimate.
actuals:
  tokens: 5901
  tasks: 3
  commits: 3
plan_head_before: 1cc617141f368eab4ff26b125a8e5a8deae849dd

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One shared partial defines a control set for every surface that renders it, so a target/field/label cannot drift between surfaces"
    - "A request-supplied value that selects a response fragment is validated against a module-level allow-list before use, with a named default fallback"

key-files:
  created:
    - app/web/templates/html/_action_forms.html
    - app/web/templates/html/_detail_actions.html
  modified:
    - app/web/templates/html/listing_detail.html
    - app/web/templates/html/_listing_row.html
    - app/api/events.py
    - app/web/routes.py
    - tests/api/test_listing_detail.py
    - tests/api/test_listing_events.py

key-decisions:
  - "The action surface is carried by an explicit, allow-listed hidden `surface` field rather than the htmx `HX-Target` header — it travels with the other form fields and is pinnable from the test client."
  - "One shared `_action_forms.html` defines the two controls for both surfaces; this makes the exact target drift that shipped G-05-8 structurally impossible."
  - "The same `POST /listings/{id}/events` endpoint returns a surface-aware fragment (row or detail section) — no second route, so the write and the re-render cannot drift."
  - "Saved discoverability is a link plus a projected state indicator, never a recomputed count — a count would have to duplicate `read_queue`'s inherent gates and could disagree with the view it advertises."

patterns-established:
  - "Shared control partial: one definition, included by every surface, with includer-set `action_url`/`target_id`/`surface` variables."
  - "Allow-listed request field: a form value that selects a response fragment is validated against `ACTION_SURFACES` and falls back to `DEFAULT_SURFACE`."

requirements-completed: [UI-02]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "One shared `_action_forms.html` is the single Save/Hide definition for both the queue row and the detail section; the queue row's rendered target is unchanged."
    requirement: "UI-02"
    verification:
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_a_detail_surface_save_is_visible_on_the_queue"
        status: pass
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_a_detail_surface_save_swaps_the_detail_actions_fragment"
        status: pass
    human_judgment: false
  - id: D2
    description: "Clicking Save/Hide on the detail page re-renders the action section in place (button flips to the inverse label, saved/hidden indicator appears) with no reload."
    requirement: "UI-02"
    verification:
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_a_detail_surface_save_swaps_the_detail_actions_fragment"
        status: pass
      - kind: integration
        ref: "tests/api/test_listing_detail.py#test_detail_action_forms_target_the_detail_section"
        status: pass
    human_judgment: true
    rationale: "The server fragment and the resolvable target are pinned by tests, but the browser-level visual swap is not covered by an automated browser test — the rendered interaction is confirmed by end-of-phase UAT."
  - id: D3
    description: "An unlisted `surface` value falls back to the queue row fragment and records `surface=queue` in the audit log."
    requirement: "UI-02"
    verification:
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_an_unknown_surface_falls_back_to_the_queue_row"
        status: pass
    human_judgment: false
  - id: D4
    description: "The detail page renders a target its own markup contains, a link to the existing saved view (`GET /?saved=1`), and a saved badge for a saved listing."
    requirement: "UI-02"
    verification:
      - kind: integration
        ref: "tests/api/test_listing_detail.py#test_detail_action_forms_target_the_detail_section"
        status: pass
      - kind: integration
        ref: "tests/api/test_listing_detail.py#test_detail_offers_the_saved_jobs_affordance"
        status: pass
      - kind: integration
        ref: "tests/api/test_listing_detail.py#test_detail_saved_listing_shows_the_saved_badge"
        status: pass
    human_judgment: false
  - id: D5
    description: "The detail-surface fragment keeps the active predicate set on its action URL, so a second click preserves `?excluded=1`."
    requirement: "UI-02"
    verification:
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_the_detail_surface_fragment_keeps_the_active_predicate_set"
        status: pass
    human_judgment: false

# Metrics
duration: 11 min
completed: 2026-09-24
status: complete
---

# Phase 5 Plan 12: Detail-page Save/Hide swap in place and point at the saved jobs Summary

**The detail page's Save/Hide controls now swap the `#detail-actions` section in place through one shared action-form partial, with an allow-listed `surface` field and a link to the existing saved view.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-09-24T10:29:01Z
- **Completed:** 2026-09-24T10:39:41Z
- **Tasks:** 3
- **Files modified:** 8 (2 created, 6 modified)

## Accomplishments

- Extracted the queue row's Save/Hide forms into one shared `_action_forms.html`, included by both the queue row (`target listing-row-{id}`, surface `queue`) and the new `_detail_actions.html` section (`target detail-actions`, surface `detail`) — the target drift that shipped G-05-8 is now structurally impossible.
- Taught `POST /listings/{id}/events` to return the detail action section for a `surface=detail` action, guarded by an `ACTION_SURFACES` (`queue`, `detail`) allow-list with a `DEFAULT_SURFACE` fallback, so an unlisted value can select only one of two known templates and write only one of two known strings into `context_json`.
- Gave the detail action section a visible saved/hidden state (existing badge classes) and a link to the existing saved view (`GET /?saved=1`), so a user who just clicked Save has both feedback and a path to follow.
- Added six regression tests (three per suite) pinning the detail target resolution, the allow-list fallback, the predicate-set preservation, and the queue path's invariance.

## Task Commits

Each task was committed atomically:

1. **Task 1: One shared action-form partial, and a detail-surface fragment the swap can target** - `38d7610` (feat)
2. **Task 2: The detail action section shows its state and points at the saved jobs** - `9b47b14` (feat)
3. **Task 3: The regression gates for the surface split and the queue path's invariance** - `d971a71` (test)

**Plan metadata:** (pending — this SUMMARY commit)

## Files Created/Modified

- `app/web/templates/html/_action_forms.html` (created) — the single Save/Hide form definition, included by both surfaces.
- `app/web/templates/html/_detail_actions.html` (created) — the `#detail-actions` swap root with the projected badges and the saved-view link.
- `app/web/templates/html/listing_detail.html` — includes `_detail_actions.html`; the two inline form blocks removed; header notes the inline-swap posture.
- `app/web/templates/html/_listing_row.html` — includes `_action_forms.html` with the queue target and surface; rendered queue markup unchanged.
- `app/api/events.py` — `ACTION_SURFACES`/`DEFAULT_SURFACE`, `DETAIL_ACTIONS_TEMPLATE`, the allow-listed `surface` read, the `context={"surface": surface}` write, the detail-fragment return and the surface-aware error fragment.
- `app/web/routes.py` — the comment that named the replaced `ACTION_CONTEXT` constant corrected.
- `tests/api/test_listing_detail.py` — target-resolution, affordance and saved-badge tests.
- `tests/api/test_listing_events.py` — detail-surface swap, allow-list fallback, predicate-set and queue-invariance tests.

## Decisions Made

- **Allow-listed hidden `surface` field over the `HX-Target` header.** The header-driven choice is implicit and awkward to pin from the test client; a hidden field is explicit, travels with `event_type`, and can be allow-listed so no unlisted value selects an unknown template.
- **Same endpoint, surface-aware fragment.** `POST /listings/{id}/events` stays the single writer; a second route would duplicate the write and the `read_row` re-render, the same drift class being fixed.
- **Link + projected indicator, not a saved count.** A correct count would have to reproduce `read_queue`'s inherent gates (hidden, absorbed-twin, latest-run) or disagree with the view it advertises; the link goes to the existing filtered view whose own count line is the count.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task 3 acceptance criterion `grep -c "|safe" tests/api/test_listing_events.py` returns 0 is unsatisfiable**

- **Found during:** Task 3 (regression gates)
- **Issue:** The criterion assumed the file contains no `|safe` literal, but line 276 already carries `assert "|safe" not in response.text` in `test_the_swapped_fragment_escapes_listing_text` — a pre-existing negative assertion present before this plan (verified in `HEAD~2`). The task explicitly forbids altering existing tests, so the criterion cannot be met without deleting an existing escaping guard.
- **Fix:** Left the existing assertion intact. Confirmed by inspection that no line added by this plan contains a safe-marking filter — the intent of the criterion ("no safe-marking filter added") holds.
- **Files modified:** tests/api/test_listing_events.py (added tests only)
- **Verification:** `grep -n "|safe" tests/api/test_listing_events.py` returns only the pre-existing line 276; the plan's automated verify (`39 passed`) and the full default-lane suite (`1093 passed`) both pass.
- **Committed in:** d971a71 (Task 3 commit)

**2. [Rule 1 - Bug] Task 1 step 3 named a file-header sentence that does not exist**

- **Found during:** Task 1 (shared partial)
- **Issue:** The plan asked to "rewrite the file-header sentence that describes the reused two-form block" in `listing_detail.html`, but the header carried no such sentence — the only description of the reused block was the comment inside the `#detail-actions` section being replaced.
- **Fix:** Added one header paragraph stating the deliberate inline-swap posture (controls target `#detail-actions`, re-render in place through the queue's endpoint, controls shared with the queue row) so the file header now carries the posture the plan asked for.
- **Files modified:** app/web/templates/html/listing_detail.html
- **Verification:** Header now states the inline-swap posture; rendered output is unchanged by a comment.
- **Committed in:** 38d7610 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 plan-specification defects; no production behaviour affected)
**Impact on plan:** Neither deviation changes shipped behaviour. Deviation 1 is a mis-specified acceptance grep; deviation 2 supplied the header sentence the plan intended to exist. No scope creep.

## Issues Encountered

None. The queue-path event tests, the stylesheet-coverage guard and the vendored-asset guard all remained green through the shared-partial refactor.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Gap G-05-8 is closed: the detail page's Save/Hide controls resolve a target the page renders, and the saved view is discoverable from where Save is clicked.
- No route, endpoint, JavaScript, polling/SSE, CDN asset, history integration, safe-marking filter, schema, migration or setting was added; the Alembic head stays `0004`.
- `static/vendor/app.css` and `app/db/repositories/*` are deliberately unmodified (existing class tokens reused; no read-model change).
- The one judgment-dependent item (the browser-level visual swap, D2) is routed to end-of-phase UAT.

## Self-Check: PASSED

- FOUND: app/web/templates/html/_action_forms.html
- FOUND: app/web/templates/html/_detail_actions.html
- FOUND: 38d7610
- FOUND: 9b47b14
- FOUND: d971a71
- Full default-lane suite: 1093 passed, 14 deselected, 2 xfailed
