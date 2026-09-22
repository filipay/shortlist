---
phase: 05-ranking-core-value
plan: 04
subsystem: ui
tags: [queue, ranking, htmx, jinja2, settings, weights, sqlalchemy]

# Dependency graph
requires:
  - phase: 05-ranking-core-value
    provides: the read-time total, the weights store and the rubric from plans 05-01/05-02, and the detail-page patterns from 05-03
provides:
  - "the queue's read-time-total ordering with unscored last, and the retained ?sort=recent order"
  - "the view-only ?min_score= threshold that always keeps unscored listings visible"
  - "the badge-unranked badge and the ranked X of Y (— cap reached) strip"
  - "POST /settings/weights and the Ranking weights card"
affects: [06-cv-tailoring, 08-scheduler]

# Actuals (#2632) — same estimateTokens scale (chars/4 over the realized diff).
actuals:
  tokens: 13410
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Python-side read-time sort over a bounded scan with a documented materialised-total upgrade path"
    - "A view-only threshold predicate that treats an absent total as always-kept"
    - "A zero-LLM-call settings write: weights change, totals re-derive on read"

key-files:
  created:
    - tests/api/test_queue_ranked.py
    - tests/api/test_ranking_weights.py
  modified:
    - app/db/repositories/queue_repo.py
    - app/db/repositories/run_repo.py
    - app/web/routes.py
    - app/api/settings.py
    - app/web/templates/html/queue.html
    - app/web/templates/html/queue_list.html
    - app/web/templates/html/_listing_row.html
    - app/web/templates/html/settings.html
    - static/vendor/app.css
    - tests/api/test_queue_search.py

key-decisions:
  - "The score ordering is a Python-side sort over a bounded scan (SCORE_SORT_SCAN_LIMIT = 5000) because the total's denominator is dynamic; the upgrade path is a materialised total column, marked with a ponytail comment"
  - "On the score path `page.total` is the count surviving the threshold (unscored always counted), not a SQL COUNT(*)"
  - "The minimum-score predicate keeps a row whose total is None: a listing with no score is not a listing with a low score (D-98)"
  - "The weights write makes zero model calls by construction — the totals are recomputed on read under the weights in force (D-100)"
  - "The FTS MATCH predicate is a filter and the sort is an ordering; `sort=score` wins over bm25 while `sort=recent` keeps bm25"

patterns-established:
  - "A queue ordering change keeps the previous ordering as a selectable branch rather than a deleted code path"
  - "A decorative strip (ranked X of Y) degrades to an empty mapping rather than 500-ing the product page"

requirements-completed: [RANK-04, UI-01, UI-03]

coverage:
  - id: D1
    description: "The queue defaults to the read-time total descending with unscored listings last and a deterministic tie-break; ?sort=recent retains the previous first_seen_at DESC, id DESC order; with a query set the score ordering wins over bm25 while the MATCH filter still applies"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_default_order_is_score_desc_unranked_last"
        status: pass
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_sort_recent_restores_first_seen_order"
        status: pass
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_score_sort_wins_over_bm25_when_q_is_set"
        status: pass
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_two_identical_requests_return_the_same_row_order"
        status: pass
    human_judgment: false
  - id: D2
    description: "A view-only ?min_score= threshold hides below-threshold scored listings while always keeping unscored ones visible, and stores nothing"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_min_score_keeps_unscored_visible"
        status: pass
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_junk_min_score_degrades_to_no_threshold"
        status: pass
    human_judgment: false
  - id: D3
    description: "The queue page carries the sort and threshold controls, an explicit unranked badge for a listing with no score, and the 'Ranked X of Y — cap reached' strip"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_unranked_row_renders_the_badge"
        status: pass
      - kind: unit
        ref: "tests/test_stylesheet_coverage.py#test_every_template_class_has_a_stylesheet_rule"
        status: pass
    human_judgment: false
  - id: D4
    description: "The settings weights editor saves the six weights in one ranking_config document, re-derives the queue order with zero new llm_calls rows, and refuses invalid input without writing"
    requirement: RANK-04
    verification:
      - kind: unit
        ref: "tests/api/test_ranking_weights.py#test_weights_form_saves_and_rerenders"
        status: pass
      - kind: unit
        ref: "tests/api/test_ranking_weights.py#test_weight_change_writes_zero_llm_calls"
        status: pass
      - kind: unit
        ref: "tests/api/test_ranking_weights.py#test_weight_change_reorders_the_queue"
        status: pass
      - kind: unit
        ref: "tests/api/test_ranking_weights.py#test_invalid_weight_writes_nothing"
        status: pass
      - kind: unit
        ref: "tests/api/test_ranking_weights.py#test_all_zero_weights_are_rejected"
        status: pass
    human_judgment: true
    rationale: "Two probe rows are unresolved: RANK-04 does not state the rejection presentation for an invalid weight submission (this plan chose an inline banner plus a non-200 status), and UI-03 does not state where the editor lives (this plan followed D-99 and put it on the settings page). Both are presentation decisions a human should confirm."

duration: 26min
completed: 2026-09-22
status: complete
---

# Phase 5 Plan 4: Weighted queue ordering, the minimum-score view filter, and the weights editor Summary

**The queue now defaults to the read-time total descending with unscored listings last, a view-only minimum-score threshold keeps unscored listings visible, the weights editor re-derives the order with zero model calls, and the page reports ranked X of Y with the cap reason**

## Performance

- **Duration:** 26 min
- **Started:** 2026-09-22T12:59:35Z
- **Completed:** 2026-09-22T13:25:06Z
- **Tasks:** 3
- **Files modified:** 12 (2 created, 10 modified)

## Accomplishments

- The queue's default order is the read-time total descending, computed in Python
  under the weights currently in force (D-100), with unscored listings last and a
  deterministic `(confidence tier, id DESC)` tie-break. The Phase-1
  `first_seen_at DESC, id DESC` order remains selectable via `?sort=recent`.
- The score path scans at most `SCORE_SORT_SCAN_LIMIT` (5000) matching ids and sorts
  in Python; `total` on that path is the count surviving the threshold, and the
  upgrade path (a materialised total) is documented with a `ponytail:` comment.
- The MATCH predicate and the ordering are independent: `sort=score` orders the
  matched set by total (winning over `bm25`) while `sort=recent` keeps relevance.
- `?min_score=` is a view-only threshold: nothing is stored, no `listing_exclusions`
  row is written, and an unscored listing is always kept (D-98).
- The queue page gained a sort select and a minimum-score input inside
  `#queue-filters`, an explicit `badge-unranked` badge instead of any numeric
  fallback, and a `#ranking-strip` paragraph reading "Ranked X of Y" with
  "— cap reached (…)" when a refusal row exists.
- The settings page gained a "Ranking weights" card: saving six numbers writes one
  `ranking_config` document and re-renders with a note; the queue re-derives with
  **zero** new `llm_calls` rows (success criterion 3). Invalid input (non-numeric,
  non-finite, negative, or an all-zero set) writes nothing and re-renders with an
  inline error and a 400.
- The filtered-empty state recognises the threshold but not the sort, so a sort
  change cannot misreport a genuinely empty queue.

## Task Commits

Each task was committed atomically:

1. **Task 1: The ranked queue read model — read-time sort, unscored last, threshold predicate** - `6e3986f` (feat)
2. **Task 2: The queue controls, the unranked badge, and the ranked X of Y strip** - `278c41c` (feat)
3. **Task 3: The weights editor — save six numbers, re-derive with zero LLM calls** - `e514083` (feat)

**Plan metadata:** `PENDING` (docs: complete plan)

## Files Created/Modified

- `app/db/repositories/queue_repo.py` - `QueueQuery.sort` / `min_score`, `SCORE_SORT_SCAN_LIMIT`, `_score_sort_key`, `_sql_page_ids`, `_score_candidate_ids`, the branch in `read_queue`
- `app/db/repositories/run_repo.py` - `RunSummary.ranked_count`
- `app/web/routes.py` - `parse_queue_query` for the two new predicates, `_ranking_strip`, the strip in the queue context
- `app/api/settings.py` - `POST /settings/weights`, `_parse_weights`, `weights`/`factors` in `_settings_context`
- `app/web/templates/html/queue.html` - the sort select, the min-score input, `#ranking-strip`
- `app/web/templates/html/queue_list.html` - the extended filtered-empty predicate
- `app/web/templates/html/_listing_row.html` - `badge-unranked`
- `app/web/templates/html/settings.html` - the Ranking weights card
- `static/vendor/app.css` - rules for `queue-sort`, `queue-threshold`, `badge-unranked`, `ranking-strip`, `weights-form`, `weight-grid`, `weight-field`, `weights-note`
- `tests/api/test_queue_ranked.py`, `tests/api/test_ranking_weights.py` - new coverage
- `tests/api/test_queue_search.py` - the phase-one order test retargeted to `?sort=recent`

## Decisions Made

- The score ordering is a Python-side sort over a bounded scan because the total's
  denominator is dynamic; the ceiling and its upgrade path are documented in the
  module docstring and with a `ponytail:` comment.
- On the score path `page.total` is the threshold-surviving count (unscored always
  counted), which is what the count paragraph and `has_more` must reflect.
- The weights editor is a plain full-page POST (no htmx), matching the reset card and
  keeping the page's `hx-post`-free settings assertion true.
- The `runs.ranked_count` read needed by the strip was exposed on `RunSummary` rather
  than queried ad hoc in the route, keeping SQL in the repository.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `parse_queue_query` was extended in Task 1, not Task 2**
- **Found during:** Task 1 (writing the ranked-queue tests)
- **Issue:** Task 1's tests exercise `?sort=recent` and `?min_score=` through the
  `client` fixture, but the plan defers the parser change to Task 2 ("Extend
  `parse_queue_query` in `app/web/routes.py` in the next task, not here"). Without the
  parser change, Task 1's own verify cannot pass.
- **Fix:** The tolerant `sort`/`min_score` parsing landed in Task 1. Task 2 still
  added the controls, the badge, the empty-state predicate and the strip.
- **Files modified:** `app/web/routes.py`
- **Verification:** `tests/api/test_queue_ranked.py` passes; Task 2 re-verified the same parser acceptance one-liner.
- **Committed in:** `6e3986f`

**2. [Rule 1 - Bug] The pinned Phase-1 queue-order test was retargeted**
- **Found during:** Task 1 (first run of `tests/api/test_queue_search.py`)
- **Issue:** `test_no_query_keeps_the_phase_one_order` seeds listings whose `id DESC`
  order is the reverse of their `first_seen_at DESC` order and asserts the default
  queue returns the `first_seen_at` order. This plan deliberately changes the default
  to the score order, so the assertion is superseded by design. The file is not in
  this plan's `files_modified`.
- **Fix:** Renamed the test to `test_sort_recent_keeps_the_phase_one_order` and pointed
  it at `?sort=recent` — which is exactly the must-have "the previous ordering remains
  selectable", and it still fails if the `recent` branch loses its `first_seen_at`
  ordering.
- **Files modified:** `tests/api/test_queue_search.py`
- **Verification:** the retargeted test passes; the score path's own order is pinned by `tests/api/test_queue_ranked.py`.
- **Committed in:** `6e3986f`

**3. [Rule 1 - Bug] The unranked-badge assertion moved to Task 2**
- **Found during:** Task 1 (the badge does not exist until Task 2)
- **Issue:** Task 1's action lists "does render the unranked badge" among its test
  file's coverage, but the badge is an explicit Task 2 deliverable (markup + CSS).
- **Fix:** Task 1's test asserts the read-model invariant (an unscored row renders no
  score badge and no numeric zero); the badge assertion
  (`test_unranked_row_renders_the_badge`) landed with the badge in Task 2.
- **Files modified:** `tests/api/test_queue_ranked.py`
- **Verification:** both tests pass.
- **Committed in:** `6e3986f`, `278c41c`

**4. [Rule 3 - Blocking] `RunSummary` had no `ranked_count`**
- **Found during:** Task 2 (the ranked X of Y strip)
- **Issue:** `_ranking_strip` needs the latest run's `runs.ranked_count`, but
  `RunSummary` (the read model the queue already holds) did not expose it, and
  querying `runs` directly in the route would put SQL outside the repositories.
- **Fix:** Added `ranked_count: int | None` to `RunSummary` and populated it in
  `_summary`. `run_repo.py` is not in this plan's `files_modified`.
- **Files modified:** `app/db/repositories/run_repo.py`
- **Verification:** the run-history and queue suites pass; the full gate is green.
- **Committed in:** `278c41c`

**5. [Rule 3 - Blocking] The `grep -c "0.0"` acceptance grep**
- **Found during:** Task 1 (acceptance check)
- **Issue:** `grep -c "0.0" app/web/templates/html/_listing_row.html` returned 1
  because a Jinja comment said "a real 0.0 must never be implied". No numeric
  fallback was rendered.
- **Fix:** Reworded the comment to "a real zero must never be implied".
- **Files modified:** `app/web/templates/html/_listing_row.html`
- **Verification:** `grep -c "0.0"` returns 0.
- **Committed in:** `6e3986f`

**6. [Rule 3 - Blocking] The plan's `.venv-host/bin/python` is unusable**
- **Found during:** Task 1 (first verify run)
- **Issue:** `.venv-host/bin/python` is Python 3.14 with a missing
  `pydantic_core._pydantic_core` (carried from 05-01/02/03).
- **Fix:** Ran every `<verify>` under `.venv/bin/python`.
- **Files modified:** none
- **Verification:** all listed verify commands pass under `.venv/bin/python`.

---

**Total deviations:** 6 auto-fixed (2 bugs, 4 blockers)
**Impact on plan:** No scope creep. Beyond `files_modified`, only
`tests/api/test_queue_search.py` and `app/db/repositories/run_repo.py` were touched —
both direct consequences of a required change.

## Issues Encountered

- The full-suite wall time in this environment varied widely (479 s for one gate run,
  then ~70 s for `tests/api` and ~64 s for `tests/db + tests/pipeline` on re-run with
  no pathological durations), so it is host load, not a scan/sort regression.

## Known Stubs

None. Every predicate is wired, and an unscored listing renders the explicit unranked
state rather than a placeholder value.

## Threat Flags

None beyond the plan's threat model. T-05-17/T-05-18 are covered by
`test_invalid_weight_writes_nothing` and `test_all_zero_weights_are_rejected`; T-05-19
by `test_junk_min_score_degrades_to_no_threshold`; T-05-20's accepted scan bound is
documented in the module docstring and the `ponytail:` comment; T-05-21 by
`ranking_config.updated_at` plus the per-score `weights_json` snapshot.

## Next Phase Readiness

- The queue is genuinely ranked and the ordering is weight-driven, so Phase 6's
  tailoring can rely on the queue's order matching the stored scores.
- Phase 8's scheduler inherits the same read path; nothing here is run-triggered.
- Open (the plan's flagged assumptions): where the weights editor lives (UI-03) and how
  an invalid weight submission is presented (RANK-04) remain presentation judgments.

## Self-Check: PASSED

- Both created files exist on disk.
- All three work commits (`6e3986f`, `278c41c`, `e514083`) exist in the history.
- `commits: 3` was measured from the plan ledger
  (`plan_head_before = b50794934d4afbcad9f68d3198b248a3f6d7d5f3`).

---
*Phase: 05-ranking-core-value*
*Completed: 2026-09-22*
