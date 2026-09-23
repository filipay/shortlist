---
phase: 05-ranking-core-value
reviewed: 2026-09-23T16:21:39Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - app/db/repositories/queue_repo.py
  - app/web/templates/html/queue_list.html
  - app/web/templates/html/queue.html
  - assets/tailwind/input.css
  - static/vendor/app.css
  - tests/api/test_queue_excluded.py
findings:
  critical: 0
  warning: 1
  info: 4
  total: 5
status: issues_found
---

# Phase 5: Code Review Report (round 3 — 05-11 two-way paging delta)

**Reviewed:** 2026-09-23T16:21:39Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Round-3 review scoped to the 05-11 gap-closure delta (G-05-3, commits `71c4e3b`,
`d8e5893`, `c083082`): the four derived `QueuePage` accessors, the shared
`queue_list.html` pager, the `queue.html` comment correction, the two id-scoped
CSS rules in both the Tailwind source and the built artifact, and the paging suite.

**What is sound.** Every explicit acceptance item was traced and holds. The
`hx-get` URLs are built by `QueueQuery.query_string` (`urlencode`) and
auto-escaped; `offset=0` is omitted because `if offset:` is falsy; `limit` is
never read from the request (`parse_queue_query` fixes it from
`settings.queue_page_size`, pinned by
`test_the_page_size_is_server_fixed_and_only_surfaced`); the Phase-1 count
paragraph and `0 listings` / `No listings yet` strings are byte-identical
(`git diff` shows no change to those lines); and no route, endpoint, JavaScript,
CDN asset, `|safe` filter, or history integration was added. The four accessors
are total by inspection and by direct execution: degenerate instances
(`limit=0`, `limit=-1`, `total=-4`, `offset=99`) raise nothing, `page_count` is
never below 1, and `prev_offset` is never negative. `assets/tailwind/input.css`
and the generated `static/vendor/app.css` carry identical `#queue-pager` /
`#queue-page-position` rules and both dropped `#queue-load-more`; the built
artifact is not stale. Full suite: `1082 passed, 14 deselected, 2 xfailed`.

**One defect in the delta.** The pager (Previous, position line, Next) is gated
on the presence of *rows on this page*, not on the queue being non-empty
(`total > 0`). On an out-of-range offset the fragment renders the "No listings
yet" empty state and no Previous control, even though listings exist and
`has_prev` is true — a direct contradiction of the plan's own `must_haves`
truths 1 and 2. It is an edge case (needs a stale offset, e.g. a scheduled run
shrinking the queue between the page render and the Next click), not a crash,
data-loss path, or security hole, so it is a WARNING, not a BLOCKER. The four
Info items are nits: offset-alignment, a guard inconsistency in `prev_offset`, a
missing totality test that the plan's coverage table claims exists, and one stale
comment.

**Working-tree note.** The repository was being modified concurrently during this
review. Two test additions landed in the working tree after the 05-11 commits and
were **uncommitted** when this report was written: an untracked
`tests/db/test_queue_page.py` (a direct `QueuePage` totality suite) and three
extra paging tests appended to `tests/api/test_queue_excluded.py`
(single-page position line, predicate-set carry, sort/threshold reset). Both pass
(`25 passed` for the two files, collected in the full-suite run above), and the
untracked suite supplies the totality coverage IN-03 discusses. They are not part
of the committed 05-11 delta and are noted rather than reviewed as such; IN-03
stays open only because the coverage is not committed and the plan's D1 citation
is still wrong.

**Prior findings.** Rounds 1 and 2 (46 files, then the 05-07…05-10 delta) are
not re-litigated. Nothing in this delta fixes or worsens any of them.

## Narrative Findings (AI reviewer)

### Warnings

#### WR-01: The pager and position line are gated on rows-present, so an out-of-range offset renders the "No listings yet" empty state and strands the user

**File:** `app/web/templates/html/queue_list.html:44-104` (the `{% if is_empty %}`
branch, with the pager inside the `{% else %}`); `is_empty` is set at
`app/web/routes.py:169` as `not page.rows`

**Issue:** The plan's `must_haves` state two truths this delta does not fully
meet:

- truth 1 — "any page after the first renders a Previous control";
- truth 2 — "whenever the queue is non-empty the fragment renders
  `Page <page_index> of <page_count> (<limit> per page)`".

Both are implemented as `{% else %}` of `is_empty`, and `is_empty` is
`not page.rows` — a strictly narrower condition than "the queue is non-empty" or
"this is a page after the first". `read_queue` accepts any non-negative `offset`
and slices with it, so an offset at or beyond `total` produces zero rows while
`total > 0`, `has_prev` is `True`, and `page_count` is a real number:

```python
# app/web/routes.py:169
"is_empty": not page.rows,          # rows on THIS page, not total == 0
```

The result, proven against the code path (score and recent both slice to an
empty list, so `is_empty` is true and the empty branch wins):

```
GET /queue/list?offset=99   (total=5, limit=2)
  page.total=5, page.offset=99, page.has_prev=True, page.page_index=50, page.page_count=3
  rendered: "No listings yet. Once a search runs, its normalised results appear here."
  rendered: no #queue-pager, no #queue-page-prev, no position line
```

So the user is told there are no listings while listings exist, and the one
control that would return them to a real page (Previous) is exactly the one
suppressed. This is reachable without hand-editing the URL: a scheduled run that
excludes/hides listings between a fragment render and the Next click can leave
the offset beyond the new total. The requirement-6 "no 500" property holds — this
is a wrong render, not a crash.

**Fix (smallest):** make the empty state mean "the queue is empty", not "this
slice is empty", so the table (possibly empty) and the pager render whenever
`total > 0`. In `_queue_context`:

```python
"is_empty": page.total == 0,
```

At `offset == 0` this is equivalent to the current `not page.rows` (and the
Phase-1 pins are unchanged), while at an out-of-range offset it keeps the pager
and the Previous control on screen. Optionally also clamp the request offset to
the last page in `parse_queue_query`/`read_queue` so a stale offset never lands
past the end. Add a test that requests an out-of-range offset and asserts the
position line and `#queue-page-prev` are present.

### Info

#### IN-01: `page_index`/`prev_offset` assume `offset` is a multiple of `limit`, but the request offset is never snapped

**File:** `app/db/repositories/queue_repo.py:294-301`; accepted unvalidated at
`app/web/routes.py:150`

**Issue:** `page_index = offset // limit + 1` and `prev_offset = offset - limit`
are only a coherent page model when `offset` is a multiple of `limit`.
`parse_queue_query` clamps `offset` at zero but does not snap it, so a
hand-crafted `GET /queue/list?offset=3` with `limit=2` renders "Page 2 of 3" over
the rows `[3:5]`, overlapping the real page 2 (`[2:4]`); its Previous goes to
offset 1 and its Next to offset 5, neither of which is a page boundary. No UI
path produces this (only the pager emits offsets, always `next_offset`/
`prev_offset` from aligned values), so it is an integrity nit, not a live bug.

**Fix:** snap in `parse_queue_query` — `offset = (offset // limit) * limit` — or
document that only pager-generated offsets are supported.

#### IN-02: `prev_offset` omits the `max(1, limit)` guard the other three accessors use

**File:** `app/db/repositories/queue_repo.py:289-291`

**Issue:** The comment above the accessors claims "The `max(1, ...)` guards
exist only so a hand-constructed instance cannot raise `ZeroDivisionError` or
report a 0-page queue", but `prev_offset` uses `self.limit` directly while
`page_index`/`page_count` use `max(1, self.limit)`. On a degenerate
`QueuePage(limit=0, offset=3)` (verified by direct execution),
`prev_offset == 3 == offset`: `has_prev` is true and the rendered Previous
re-requests the same page, a dead control. Harmless and unreachable from
`read_queue` (which clamps `limit >= 1`), but it contradicts the stated guard
rationale.

**Fix:** `return max(0, self.offset - max(1, self.limit))` for consistency.

#### IN-03: The committed 05-11 delta ships no totality test, and the plan's coverage row cites a file that does not exercise it

**File:** `tests/api/test_queue_excluded.py:255-347` (all committed paging tests
use the live route, never a hand-constructed `QueuePage`); cited by
`.planning/phases/05-ranking-core-value/05-11-SUMMARY.md:59`

**Issue:** `05-11-SUMMARY.md`'s D1 coverage row claims
`tests/db/test_queue_state.py` verifies "all total (no ZeroDivisionError, no
0-page queue)". That file contains no `QueuePage` reference at all
(`grep -n "QueuePage\|page_count\|prev_offset" tests/db/test_queue_state.py`
returns nothing), and the committed 05-11 tests never construct a degenerate
page. An **untracked** working-tree file `tests/db/test_queue_page.py` now
supplies exactly that coverage (and its own docstring notes the SUMMARY's
mis-citation), but it is uncommitted, unnamed in the plan/SUMMARY, and would be
lost by a clean checkout. The accessors are correct by inspection today, but on
the committed delta nothing fails if a later edit drops a `max(1, ...)` guard.

**Fix:** commit `tests/db/test_queue_page.py` (or fold it into
`tests/api/test_queue_excluded.py`) and correct the D1 coverage row to name it;
add a route test for WR-01's out-of-range offset, which neither suite covers.

#### IN-04: Stale "Load more" comment left in `app/config.py` (outside the scoped files)

**File:** `app/config.py:126` — `# The queue read model's page size (D-42 "Load more" paging).`

**Issue:** The 05-11 delta renamed the control to a pager and updated every
comment in the scoped templates, but the settings comment still names the deleted
"Load more" affordance. Outside the `--files` scope; noted because it is a direct
consequence of this delta and one line to fix.

**Fix:** reword to `# The queue read model's page size (D-42 paging).`

---

_Reviewed: 2026-09-23T16:21:39Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
