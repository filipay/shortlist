---
id: SEED-001
status: dormant
planted: 2026-09-16
planted_during: Phase 2 — Clean, Filtered, Queryable Queue
trigger_when: when planning queue/UI polish, or any phase about filtering or browsing the queue
scope: small-to-medium
audit_acknowledged:
  milestone: v1.0
  at: 2026-10-15
  status: dormant
---

# SEED-001: Ad-hoc queue filters over listing attributes (remote: no, location: Galway)

## Why This Matters

Recorded verbatim at Phase 2 UAT: *"I would like to be able to filter out specific things like
`remote: no` or `location: galway` but that can be a future feature."*

Phase 2 shipped two different things, and neither answers this:

- **Criteria rules** (`filter_rules`, plan 02-03/02-05) — evaluated at RUN time, scoped to a
  saved search, and they change the queue for every future run. `location` and `remote` already
  exist as rule kinds, but a rule is a durable decision, not a browse-time question.
- **Queue toggles** (plan 02-07/02-09) — only `q` (FTS search), `excluded`, `hidden`, `saved`,
  and `scope_search_id`. There is no predicate over `remote_flag`, `location_norm` or any other
  listing attribute.

So "show me only the Galway roles, right now" is currently unexpressible. The distinction that
matters: a **rule** changes what the pipeline keeps; a **filter** is a transient view over what was
kept. This seed is about the latter.

## When to Surface

**Trigger:** when planning queue/UI polish, or any phase about filtering or browsing the queue.

Likely belongs with the Phase 8 "Operations + Polish" work, or as its own small slice. It is a pure
read-path + UI feature — no ingest, schema or pipeline change is required.

## Scope Estimate

**Small-to-medium.** The data is already captured: `Listing.remote_flag`, `location_norm`, `city`,
`region_country_code` all exist in the migrated schema (Phase 1 / migration 0001). The work is a
predicate extension plus UI, not a data-model change.

The non-obvious cost is **parameter hygiene**, not the feature: `queue_repo.QueueQuery` deliberately
refuses a client-supplied page size (`limit` comes from `Settings.queue_page_size`) because a
client-chosen page size is a self-inflicted deep scan (threat T-02-28). Any new filter parameter
must follow that same discipline. Nullable attributes also need care — Phase 2 established that an
*unknown* value must never be treated as a rejection reason (D-31/A2/A3, and the G3 dedup defect
fixed in `a51a133` was exactly this class of bug), so "remote: no" must decide explicitly how a NULL
`remote_flag` behaves.

## Breadcrumbs

- `app/db/repositories/queue_repo.py` — `QueueQuery` (`q`, `excluded`, `hidden`, `saved`,
  `scope_search_id`, `offset`, `limit`) and `read_queue` are the extension point. Note the
  server-owned `limit` precedent.
- `app/web/routes.py` — `parse_queue_query()` is where query-string parameters are parsed and
  clamped; add new predicates there, not in the repository.
- `app/web/templates/html/queue.html` — the existing toggle row is the UI precedent
  (HTMX fragment swaps against `#queue-list`).
- `app/domain/filter.py` — the existing rule-kind vocabulary (`location`, `remote`, `seniority`,
  `salary_floor`, …) to mirror so filter and rule wording stay consistent.
- `tests/api/test_queue_search.py`, `tests/api/test_queue_signals.py` — the predicate-composition
  test lane; note the Nyquist gap filled in `bcb86c2` (a search × hidden/excluded composition test)
  exists precisely because these predicates interact.
- `app/web/templates/html/_listing_row.html` — where a filter's effect becomes visible.

## Notes

Captured during the Phase 2 end-of-phase UAT, at the user's request, as a future feature. It was
explicitly NOT implemented in Phase 2. The Phase 2 excluded-listing chip (`rule.kind (count)`) was
judged sufficient for now, so this is separate from any chip-enrichment work.
