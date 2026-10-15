---
phase: 05-ranking-core-value
plan: 11
subsystem: ui
tags: [queue, paging, htmx, jinja2, tailwind, css, gap-closure, g-05-3]

# Dependency graph
requires:
  - phase: 05-ranking-core-value
    provides: the ranked queue read model (05-01/05-04) and the shared queue_list.html fragment the queue page and GET /queue/list both render
provides:
  - "QueuePage.has_prev / prev_offset / page_index / page_count — total derived page navigation on the existing dataclass"
  - "the two-way #queue-pager (Previous / 'Page X of Y (N per page)' / Next) in the shared queue fragment"
affects: [06-cv-tailoring, 08-scheduler]

# Actuals (#2632) — same estimateTokens scale (chars/4 over the realized diff).
actuals:
  tokens: 19314
  tasks: 3
  commits: 3
  plan_head_before: f81b2b3768b0ec68815cb33dfc658aed834cbee3

tech-stack:
  added: []
  patterns:
    - "A pager renders a discrete PAGE, so an innerHTML swap of #queue-list is correct; only the pager carries an offset"
    - "Derived page accessors guard with max(1, limit) so a degenerate hand-constructed dataclass cannot raise ZeroDivisionError or report 0 pages"

key-files:
  created: []
  modified:
    - app/db/repositories/queue_repo.py
    - app/web/templates/html/queue_list.html
    - app/web/templates/html/queue.html
    - static/vendor/app.css
    - assets/tailwind/input.css
    - tests/api/test_queue_excluded.py

key-decisions:
  - "The pager renders on EVERY non-empty page, not gated on has_more: the position line is the point, so a single-page queue still reports its page size"
  - "No htmx history/URL-push: a fragment request URL pushed into history reloads as a bare fragment with no page shell, so the in-page Previous control is the backward affordance"
  - "The four accessors are pure derivations of offset/limit/total already set by read_queue; max(1, ...) guards exist only for a hand-constructed instance"
  - "assets/tailwind/input.css was updated alongside the built static/vendor/app.css — the artifact is generated from the source in Docker, so editing only the artifact would silently revert the fix on the next image build"

patterns-established:
  - "A derived page model on an existing frozen dataclass (no schema, no route, no new state) replaces a mislabelled forward-only control"

requirements-completed: [UI-01]

coverage:
  - id: D1
    description: "QueuePage derives backward navigation and its own position — has_prev, prev_offset, page_index, page_count — all total (no ZeroDivisionError, no 0-page queue)"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "tests/api/test_queue_excluded.py#test_the_first_page_has_no_previous_and_the_last_has_no_next"
        status: pass
      - kind: unit
        ref: "tests/db/test_queue_state.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "The shared queue fragment renders Previous / position line / Next: Previous only after page 1, Next only while has_more, and 'Page X of Y (N per page)' on every non-empty page with N the server-fixed page size"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "tests/api/test_queue_excluded.py#test_a_predicate_change_resets_the_page_and_the_pager_carries_it"
        status: pass
      - kind: unit
        ref: "tests/api/test_queue_excluded.py#test_the_first_page_has_no_previous_and_the_last_has_no_next"
        status: pass
      - kind: unit
        ref: "tests/api/test_queue_excluded.py#test_the_page_size_is_server_fixed_and_only_surfaced"
        status: pass
      - kind: unit
        ref: "tests/api/test_queue_excluded.py#test_the_full_page_renders_the_pager_and_the_position_line"
        status: pass
      - kind: unit
        ref: "tests/test_stylesheet_coverage.py#test_every_template_class_has_a_stylesheet_rule"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-09-23
status: complete
---

# Phase 5 Plan 11: Two-way queue paging with a position line Summary

**The queue is now browsable both ways: `QueuePage` derives prev/next/page index/page count, and the shared fragment renders `Page 2 of 3 (25 per page)` between a Previous and a Next control — all through the existing `GET /queue/list` swap, with no new route, state, history integration or page-size negotiation**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-09-23T15:44:00Z
- **Completed:** 2026-09-23T15:53:37Z
- **Tasks:** 3
- **Files modified:** 6 (0 created, 6 modified)

## Accomplishments

- Closed gap **G-05-3**: the forward-only "Load more" control — which promised an append while its `innerHTML` swap destroyed the rows already on screen — is replaced by an explicit page pager. Each slice IS a page now, so replacing the page is the correct behaviour rather than a mislabelled one.
- `QueuePage` gained four pure derived accessors: `has_prev` (`offset > 0`), `prev_offset` (`max(0, offset - limit)`), `page_index` (`offset // limit + 1`) and `page_count` (`ceil(total / limit)`, never below 1). All are derived from fields `read_queue` already sets; no SQL, no column, no migration (Alembic head stays `0004`).
- The shared `queue_list.html` fragment renders `<nav id="queue-pager">` on **every non-empty page**: `#queue-page-prev` only when `page.has_prev`, `#queue-page-position` reading `Page {{ page.page_index }} of {{ page.page_count }} ({{ page.limit }} per page)`, and `#queue-page-next` only while `page.has_more`. The position line renders even for a single-page queue, because the page size is itself the answer to "how many jobs per page".
- The predicate-reset rule is unchanged: only the pager carries an offset; a filter/sort/threshold change still emits no offset and restarts at page 1. The count paragraph and the `0 listings` / `No listings yet` strings are byte-identical (Phase-1 pins still pass).
- The page size stays server-fixed (T-02-28): the pager only **displays** `page.limit`; a new test pins that `GET /queue/list?limit=1` still returns `settings.queue_page_size` rows.

## Task Commits

Each task was committed atomically:

1. **Task 1: `QueuePage` derives backward navigation and its own position** - `71c4e3b` (feat)
2. **Task 2: The shared fragment renders a Previous / position / Next pager** - `d8e5893` (feat)
3. **Task 3: The paging tests encode the two-way page model** - `c083082` (test)

**Plan metadata:** (this SUMMARY commit) (docs: complete two-way queue paging plan)

_Note: `commits: 3` is measured from the plan ledger, not narrated._

## Files Created/Modified

- `app/db/repositories/queue_repo.py` — `QueuePage.has_prev`, `prev_offset`, `page_index`, `page_count` (pure derivations, with the guard rationale in a comment)
- `app/web/templates/html/queue_list.html` — the `#queue-pager` nav (`#queue-page-prev`, `#queue-page-position`, `#queue-page-next`) replacing the forward-only control; the block comment rewritten to state a discrete page is swapped and that no history integration is added on purpose
- `app/web/templates/html/queue.html` — the filter comment corrected: the pager carries the offset forward and back, and a predicate change still resets it (no markup change)
- `static/vendor/app.css` — the dead `#queue-load-more` rules dropped; `#queue-pager` and `#queue-page-position` rules added
- `assets/tailwind/input.css` — the same rule change in the Tailwind source the built stylesheet is generated from
- `tests/api/test_queue_excluded.py` — `LOAD_MORE_RE` replaced by `PAGER_PREV_RE` / `PAGER_NEXT_RE`; the paging test rewritten; first/last-page, server-fixed-limit and full-page tests added

## Decisions Made

- The pager renders unconditionally on a non-empty page rather than inside `{% if page.has_more %}` — the position line is the requested feature, and gating it on a next page would hide it on exactly the single-page and last-page cases.
- No `hx-push-url` / `hx-history` / `hx-boost`: a fragment URL pushed into browser history reloads as a bare fragment with no page shell, a worse defect than the one fixed. The in-page Previous control is the backward affordance the gap's `missing` list allows.
- `prev_offset` uses `max(0, ...)` and the other accessors use `max(1, limit)` guards so a hand-constructed or degenerate `QueuePage` cannot 500 the queue — the guards never change a value `read_queue` produces (it already clamps `limit >= 1`).
- The page size is surfaced from `page.limit`, so neither `app/web/routes.py` nor `app/config.py` needed a change — the route already passes the whole `page` object and already fixes `limit` from settings.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `assets/tailwind/input.css` updated alongside the built `static/vendor/app.css`**
- **Found during:** Task 2 (the CSS rule edit)
- **Issue:** `static/vendor/app.css` is **generated** from `assets/tailwind/input.css` by the Tailwind CLI in `Dockerfile:19`. The plan named only the built artifact. Editing just the artifact would leave the source still defining `#queue-load-more` and still missing `#queue-pager`/`#queue-page-position`, so the next image build would silently revert the whole fix.
- **Fix:** Made the same rule change in `assets/tailwind/input.css` (drop the `#queue-load-more` group member and its `margin-top` rule; add the `#queue-pager` and `#queue-page-position` rules). The generated `app.css` was edited to match the minified output the plan specified.
- **Files modified:** `assets/tailwind/input.css` (the plan's `static/vendor/app.css` edit is unchanged)
- **Verification:** `grep -c "queue-load-more" static/vendor/app.css` returns 0; `grep -c "queue-load-more" assets/tailwind/input.css` returns 0; `tests/test_stylesheet_coverage.py` passes; the full suite is green.
- **Committed in:** `d8e5893`

**2. [Rule 1 - Bug] Stale comment naming the deleted control**
- **Found during:** Task 2
- **Issue:** `queue_list.html`'s header comment and `queue.html`'s filter comment both still named the "Load-more control". The plan asked only for the block comment above the pager and the queue.html filter comment to be rewritten; leaving the header comment naming a control that no longer exists is exactly the kind of drift G-05-3 is about.
- **Fix:** `queue_list.html`'s header comment now says "the pager"; `queue.html`'s filter comment (the plan's named edit) says the pager carries the offset forward and back.
- **Files modified:** `app/web/templates/html/queue_list.html`, `app/web/templates/html/queue.html`
- **Verification:** `grep -c "queue-load-more" app/web/templates/html/queue_list.html` returns 0; all template/queue tests pass.
- **Committed in:** `d8e5893`

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** No scope creep. `assets/tailwind/input.css` is the only file touched beyond `files_modified`, and it is the source of a file the plan does name — the fix would otherwise revert on the next build.

## Issues Encountered

- The plan's Task 1 verify names `.venv-host/bin/python`; as in plans 05-01…05-10 that interpreter is unusable here. Every `<verify>` and the full suite ran under `.venv/bin/python` (Python 3.14.7), which is what the project's configured test command uses.
- Task 2 leaves `tests/api/test_queue_excluded.py` transiently red (it still referenced the removed `queue-load-more` id) until Task 3 rewrites it. The plan's Task 2 verify deliberately excludes that file, and no git hook runs the suite, so the atomic Task 2 commit is not blocked. The file is green again after `c083082`.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. Every pager value is derived from a field `read_queue` already sets; there is no placeholder, no hardcoded empty value and no unwired data source.

## Threat Flags

None beyond the plan's threat model. T-05-39 (Tampering — `limit` from the request) is mitigated by the unchanged `parse_queue_query` and pinned by `test_the_page_size_is_server_fixed_and_only_surfaced`; T-05-40 (Tampering — pager `hx-get` URLs) holds because every value is an integer and the URL is built by `QueueQuery.query_string` (`urlencode`) and auto-escaped; T-05-41/T-05-42 are accepted at personal scale as documented. T-05-SC holds — no package was installed.

## Next Phase Readiness

- The queue is fully browsable and self-describing, which is the Core Value screen's last UI gap. Phase 6's tailoring and Phase 8's scheduler inherit the same read path unchanged.
- The Alembic head is still `0004`; no persisted shape, route or setting was added, so nothing downstream needs migrating.
- No blockers. The `05-VERIFICATION.md` and UAT artifacts for G-05-3 can be closed by the verifier.

## Self-Check: PASSED

- All six modified files exist on disk.
- All three work commits (`71c4e3b`, `d8e5893`, `c083082`) exist in the history.
- `commits: 3` was measured from the plan ledger
  (`plan_head_before = f81b2b3768b0ec68815cb33dfc658aed834cbee3`).
- Full suite: `1068 passed, 14 deselected, 2 xfailed`. Build: `compileall` clean.

---
*Phase: 05-ranking-core-value*
*Completed: 2026-09-23*
