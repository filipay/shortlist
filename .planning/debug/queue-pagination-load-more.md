---
slug: queue-pagination-load-more
status: root_cause_found
created: 2026-09-23
phase: 05-ranking-core-value
gap_id: G-05-3
severity: major
requirement: UI-01
updated: 2026-09-23
audit_acknowledged:
  milestone: v1.0
  at: 2026-10-15
  status: root_cause_found
---

# Symptom

User reported: "one usability issue is 'load more' loads more found jobs but then cannot go back to the previous jobs, we should have paginated responses and a ui way to show what page we're on and how many jobs per page"

# Expected Truth (G-05-3)

The queue is navigable, not one-way: the user can move back to earlier listings after loading further ones, and the UI shows which page they are on and how many listings each page holds (UI-01 browse).

## Current Focus

hypothesis: CONFIRMED — Load more is a whole-fragment `innerHTML` replacement, not an append, and no backward control / page-position indicator exists; the queue is strictly forward-only.
test: Read templates, route, repository, tests; grep for htmx history; confirm dataclass capabilities.
expecting: confirmed
next_action: none — root cause reported; fix owned by plan-phase --gaps.

## Symptoms

expected: Queue is navigable both ways; user can return to earlier listings; UI shows page position and page size.
actual: Load-more replaces the visible list with the next offset's rows; earlier jobs are gone; no back/prev control, no page indicator.
errors: none (silent UX defect)
reproduction: Open queue, click "Load more", attempt to return to the previous listings.
started: always broken (introduced with the Phase-2 Load-more paging, D-42)

## Eliminated

- hypothesis: Additional state loss via the query string (filters dropped on Load more).
  evidence: `QueueQuery.query_string(offset=...)` (queue_repo.py:171-198) carries every
  predicate plus the offset; `test_queue_excluded.py:277-278` pins that Load more carries
  the predicate set. Filters survive — not the defect.
  timestamp: 2026-09-23

- hypothesis: An offset clamp or limit bug makes earlier offsets unreachable at the SQL layer.
  evidence: `read_queue` (queue_repo.py:470-471) clamps `offset` at 0 and `limit` at >=1;
  `/queue/list` accepts any non-negative offset (`routes.py:150`). Earlier offsets are
  perfectly fetchable server-side. The defect is purely client/DOM + missing affordance.
  timestamp: 2026-09-23

## Evidence

- timestamp: 2026-09-23
  checked: app/web/templates/html/queue_list.html:76-86
  found: Load-more button issues `hx-get="/queue/list?{{ page.query.query_string(offset=page.next_offset) }}"` with `hx-target="#queue-list"` and `hx-swap="innerHTML"`. The fragment it swaps in contains ONLY that offset's rows (count + table + button), so `innerHTML` REPLACES the whole list rather than appending. Label says "Load more"; behaviour is "go to next page".
  implication: Page 1's rows are destroyed on the first click — the primary one-way defect.

- timestamp: 2026-09-23
  checked: app/web/templates/html/queue.html:39-167 and grep for `hx-push-url|hx-history|hx-boost`
  found: Only the search box and `excluded`/`hidden`/`saved`/`sort`/`min_score` controls are wired (all emit no offset → reset to 0). No previous/back control, no page indicator, no page-count display anywhere. No `hx-push-url`/`hx-history`/`hx-boost` exists in any template, so the browser URL stays `/` and browser Back cannot restore a prior offset either.
  implication: There is NO backward affordance — neither in-page nor via history. The only reset is a full navigation to `/`.

- timestamp: 2026-09-23
  checked: app/web/templates/html/queue_list.html:17 and app/web/routes.py:165-170
  found: The only position feedback is `{{ count }} listing(s)`, and `count` = `page.total` (the GRAND TOTAL matched), not the page slice. Nothing renders offset, limit, page index, page count, or "showing X–Y of N".
  implication: The user cannot tell which slice they are viewing or how many rows per page — the second half of the report.

- timestamp: 2026-09-23
  checked: app/db/repositories/queue_repo.py:262-277
  found: `QueuePage` exposes `rows, total, offset, limit, has_more, query, rule_counts` and a `next_offset` property. It has NO `has_prev` / `prev_offset` / `page_index` / `page_count`. All of the missing values are trivially derivable from the exposed fields (`offset > 0`; `max(0, offset-limit)`; `offset//limit + 1`; `ceil(total/limit)`).
  implication: The data needed for prev/next + a page indicator already exists on the page object; only rendering (and optionally small derived properties) is missing.

- timestamp: 2026-09-23
  checked: app/web/routes.py:132-154, app/config.py:127
  found: `parse_queue_query` hardcodes `limit=settings.queue_page_size` (25) and never reads `limit` from the request (deliberate, T-02-28 — client page size = self-inflicted deep scan); `offset` is clamped at zero. `queue_page_size: int = 25`.
  implication: "How many jobs per page" is fixed at 25 and not user-adjustable; displaying it is possible without touching the security constraint.

- timestamp: 2026-09-23
  checked: .planning/phases/02-clean-filtered-queryable-queue/02-RESEARCH.md:672
  found: The Phase-2 design intent for Load more is "`hx-get` → **appends** the next page's rows into `#queue-list`". The shipped template uses `hx-swap="innerHTML"` (replace). This is an intent-vs-implementation drift, not a considered design.
  implication: The append semantics were intended; the implementation regressed to replace.

- timestamp: 2026-09-23
  checked: tests/api/test_queue_excluded.py:257-278
  found: `test_a_predicate_change_resets_the_page_and_load_more_carries_it` pins the current forward-only behaviour — it asserts the Load-more link carries `offset=4` (current+limit) and that predicate changes carry no offset.
  implication: Any redesign of the paging control must update this test; it currently encodes the defect as intended behaviour.

- timestamp: 2026-09-23
  checked: app/web/templates/html/_listing_row.html:30 and app/web/routes.py:381-398
  found: Rows carry stable ids (`<tr id="listing-row-{{ row.id }}"`), and `GET /queue/list` already accepts an arbitrary `offset` and returns the fragment for any page.
  implication: Prev/next can reuse the existing endpoint with no new plumbing; stable row ids make an append-style swap dedup-safe.

## Resolution

root_cause: >
  The queue's paging affordance is forward-only and stateless in the DOM. (1) "Load more"
  performs an `hx-swap="innerHTML"` replacement of `#queue-list` with only the next
  offset's rows, destroying the rows already rendered (queue_list.html:79-85) — despite the
  Phase-2 design intending an append (02-RESEARCH.md:672). (2) There is no previous/back
  control and no `hx-push-url`/`hx-history`, so neither an in-page control nor browser
  history can return to an earlier offset; offset only ever increases from the one button.
  (3) The UI renders only the grand total (`page.total`) as "N listings" and never the
  current offset, page size, page index, or page count, so the user cannot tell which slice
  they are on or how many rows a page holds. `QueuePage` already exposes everything needed
  to derive prev/next and a position indicator; only rendering is missing.
fix:
verification:
files_changed: []
