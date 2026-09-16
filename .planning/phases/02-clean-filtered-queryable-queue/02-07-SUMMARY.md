---
phase: 02-clean-filtered-queryable-queue
plan: "07"
subsystem: ui
tags: [fts5, bm25, sqlite, htmx, jinja2, queue, watermark, exclusions]

# Dependency graph
requires:
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-05's `exclusion_repo.rule_counts_for_listings` / `excluded_counts_for_run` and the un-advanced `queue_state` watermark"
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-06's `dupe_repo.merge_summary_for_listings` and `revert_merge`"
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-01's migration 0002 — `queue_state`, `filter_rules` and `listing_dupes`"
  - phase: 01-walking-skeleton
    provides: "the `listing_fts` external-content FTS5 table with its maintenance triggers and the Phase-1 queue page"
provides:
  - "`app/domain/search_query.py` — the pure FTS5 safety transform (`build_match_expression`)"
  - "`app/db/repositories/queue_repo.py` — the only queue SQL, the only `MATCH`, and the absorbed-twin/hidden/saved/scope predicates"
  - "`app/db/repositories/state_repo.py` — the last-visit watermark (`get_watermark`, `advance_watermark`, `mark_all_seen`)"
  - "`GET /` rebuilt thin over `read_queue`, plus `GET /queue/list` and `POST /queue/mark-seen`"
  - "`queue.html` (search box + toggles + `#queue-list`), `queue_list.html` (the shared fragment) and `_listing_row.html` (the row partial)"
affects: [02-08, 02-09, 02-10]

# Actuals (#2632) — measured, not narrated.
actuals:
  tokens: 22619        # chars/4 of `git diff 1f40d94..HEAD` => 90476/4
  tasks: 3
  commits: 3           # MEASURED: git rev-list --count 1f40d94..HEAD

tech-stack:
  added: []            # no new dependency — FTS5 and HTMX were already vendored/in-tree
  patterns:
    - "Transform-at-the-boundary: untrusted text is normalised by a PURE function before it reaches the database, and the SQL never sees raw input (bound parameter only)"
    - "Prove-the-escape-against-the-real-parser: the transform's test runs every hostile input through a real `MATCH`, and separately asserts the raw forms raise, so the guard cannot pass vacuously"
    - "One repository per query family: the route is thin, and enrichment is delegated to the repository that already owns each join"
    - "Watermark-after-read: the page is rendered from the pre-advance watermark and the advance is a separate, explicitly-named write"

key-files:
  created:
    - app/domain/search_query.py
    - app/db/repositories/queue_repo.py
    - app/db/repositories/state_repo.py
    - app/web/templates/html/queue_list.html
    - app/web/templates/html/_listing_row.html
    - tests/domain/test_search_query.py
    - tests/db/test_queue_state.py
    - tests/api/test_queue_search.py
    - tests/api/test_queue_signals.py
    - tests/api/test_queue_excluded.py
  modified:
    - app/web/routes.py
    - app/web/templates/html/queue.html
    - tests/pipeline/test_ingest_e2e.py

key-decisions:
  - "Every FTS token is double-quoted with internal quotes doubled, and the last token gets the prefix `*`. FTS5 parses `MATCH` as an *expression*, so quoting is the only correct escape — verified against the real parser for all eight ordinary inputs that raise when passed raw."
  - "A blank or absent query returns `None` and the caller skips the `listing_fts` join entirely: the database is never handed `MATCH ''`, and the no-query branch keeps Phase-1's `first_seen_at DESC, id DESC` order verbatim."
  - "Every order ends in a unique tie-break (`score, id DESC` for FTS, `first_seen_at DESC, id DESC` otherwise). `bm25()` alone is not deterministic — two rows with an identical score came back in different orders from two equivalent queries (RESEARCH §Q3 Finding 1)."
  - "BM25 per-column weights live in `queue_repo` as named constants, not `Settings`: they are ranking heuristics, not an operating envelope, and the module states its own choice."
  - "`limit` always comes from `Settings.queue_page_size` and never from the request — a client-supplied page size is a self-inflicted deep scan (T-02-28); `offset` is clamped at zero."
  - "A predicate change resets the page index (the toggle/`hx-get` links carry no offset) while Load more carries the current offset forward: page N of a *different* filtered set is meaningless."
  - "`#queue-list` is a wrapper inside `queue.html` and every swap targets it with `hx-swap=\"innerHTML\"`. `outerHTML` would replace the wrapper with the fragment and delete the element every later swap addresses."
  - "The watermark is written by exactly two call sites — opening the queue (after the read, so the current render keeps its badges) and `Mark all as seen` — and never moves backwards, so a clock skew cannot resurrect old listings as new."
  - "A fragment read (`GET /queue/list`) deliberately does NOT advance the watermark: a predicate swap is not a visit."
  - "`new` and `stale` are two independent flags, never a state machine: a listing just ingested and already inactive is legitimately both, and neither suppresses the other."
  - "The exclusion predicate is a correlated `NOT EXISTS` against the LATEST run only, so retuning a rule brings listings back with no deletion (D-36's per-run observations made visible), and the chip count is grouped over the run rather than summed per row."
  - "`scope_search_id` semantics (documented, not implicit): there is no listing-to-search link, so a listing is in scope when it has no exclusion at all OR at least one exclusion produced by one of the scoped search's rules; a listing excluded only by another search's rules is out of scope."
  - "Badges render in a dedicated `Signals` cell rather than inside the `listing-title` cell, because a pre-existing determinism test reads the queue back with `<td class=\"listing-title\">([^<]+)</td>` — keeping that cell pure preserved a pinned Phase-1 assertion."

patterns-established:
  - "The queue is one repository deep: every predicate, join, ordering and enrichment is in `queue_repo`, so the route cannot drift from the repository and there is one place to change."
  - "Anti-vacuity testing for a safety transform: the hostile-input lane asserts both directions (transformed parses, raw raises)."
  - "A database-backed watermark instead of a cookie, so \"what is new since I last looked\" is restart-safe, not client-controlled and auditable (T-02-29)."

requirements-completed: [QUEUE-06, QUEUE-07, FILT-03]

coverage:
  - id: D1
    description: "The queue is full-text searchable through FTS5/BM25, and untrusted query text can no longer 500 the page: `it's`, `runner-up`, a lone hyphen, `OR`, `*`, `NEAR(`, a trailing `AND` and an unbalanced quote all return 200."
    requirement: QUEUE-06
    verification:
      - kind: unit
        ref: "tests/domain/test_search_query.py#test_every_hostile_input_becomes_an_expression_the_real_parser_accepts"
        status: pass
      - kind: unit
        ref: "tests/domain/test_search_query.py#test_the_raw_inputs_really_do_raise_untransformed"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_search.py#test_an_apostrophe_query_returns_200_not_500"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_search.py#test_a_hyphenated_query_returns_200_not_500"
        status: pass
    human_judgment: false
  - id: D2
    description: "Search results are deterministic: two identical requests return an identical row order, the unique tie-break is load-bearing, and a request with no query keeps Phase-1's `first_seen_at DESC, id DESC` order without joining the FTS table."
    requirement: QUEUE-06
    verification:
      - kind: integration
        ref: "tests/api/test_queue_search.py#test_identical_search_requests_return_an_identical_row_order"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_search.py#test_no_query_keeps_the_phase_one_order"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_search.py#test_search_returns_the_matching_row_and_not_the_other"
        status: pass
    human_judgment: false
  - id: D3
    description: "Listings newer than `queue_state.last_queue_view_at` are badged `new` (and every listing is new when the watermark is NULL); opening the queue advances the watermark, `Mark all as seen` clears the badges explicitly, and a fragment read advances nothing."
    requirement: QUEUE-07
    verification:
      - kind: unit
        ref: "tests/db/test_queue_state.py"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_signals.py#test_listings_after_the_watermark_are_new_and_before_it_are_not"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_signals.py#test_mark_all_as_seen_clears_the_badges_and_keeps_the_rows"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_signals.py#test_opening_the_queue_advances_the_watermark_every_time"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_signals.py#test_a_fragment_read_does_not_advance_the_watermark"
        status: pass
    human_judgment: false
  - id: D4
    description: "A listing is badged `stale` when `last_seen_at` is at or older than `Settings.stale_after_days` or when it is inactive, and new/stale can both apply to one listing."
    requirement: QUEUE-07
    verification:
      - kind: integration
        ref: "tests/api/test_queue_signals.py#test_the_stale_boundary_is_n_minus_one_n_and_n_plus_one"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_signals.py#test_an_inactive_listing_is_stale_regardless_of_last_seen"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_signals.py#test_a_listing_can_be_both_new_and_stale"
        status: pass
    human_judgment: false
  - id: D5
    description: "An absorbed twin is absent from the queue while its `listing_dupes` row is un-reverted, and reappears the moment `dupe_repo.revert_merge` clears it — with no separate un-hide step."
    verification:
      - kind: integration
        ref: "tests/api/test_queue_search.py#test_queue_hides_absorbed_twin_until_revert"
        status: pass
    human_judgment: false
  - id: D6
    description: "A listing with un-reverted merges renders `merged from N sources` linking to `/merges`, and the indicator disappears once the merge is reverted."
    verification:
      - kind: integration
        ref: "tests/api/test_queue_search.py#test_queue_hides_absorbed_twin_until_revert"
        status: pass
    human_judgment: false
  - id: D7
    description: "Excluded listings are out of the default view and appear dimmed under `Show excluded`, each carrying a chip naming the firing rule kind with a count grouped over the latest run; a listing excluded only by an older run returns to the default view."
    requirement: FILT-03
    verification:
      - kind: integration
        ref: "tests/api/test_queue_excluded.py#test_the_default_view_hides_excluded_listings_and_the_toggle_reveals_them"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_excluded.py#test_a_listing_excluded_only_by_an_older_run_returns_to_the_default_view"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_excluded.py#test_the_chip_count_is_grouped_over_the_run_not_per_row"
        status: pass
    human_judgment: false
  - id: D8
    description: "Paging: Load more carries the current offset plus the current predicate set, while a predicate change carries no offset so the page index restarts."
    requirement: QUEUE-06
    verification:
      - kind: integration
        ref: "tests/api/test_queue_excluded.py#test_a_predicate_change_resets_the_page_and_load_more_carries_it"
        status: pass
    human_judgment: false
  - id: D9
    description: "No behaviour the Phase-1 tests pinned changed: the trigger control, the status slot, the `0 listings`/`No listings yet` empty state and the FTS round-trip all still pass, and every new route carries the auth seam."
    verification:
      - kind: integration
        ref: "tests/api/test_run_trigger.py"
        status: pass
      - kind: integration
        ref: "tests/db/test_fts_triggers.py"
        status: pass
      - kind: unit
        ref: "tests/test_auth_seam.py"
        status: pass
      - kind: unit
        ref: "tests/test_no_cdn.py"
        status: pass
      - kind: unit
        ref: "tests/test_import_discipline.py"
        status: pass
    human_judgment: false

# Metrics
duration: 22min
completed: 2026-09-16
status: complete
---

# Phase 02 Plan 07: The queue you can actually search — full-text, new, stale, excluded

**An FTS5/BM25-searchable queue whose query text is normalised by a pure transform proven against the real parser, with database-backed new/stale badges, an absorbed twin hidden until its merge is reverted, and a `Show excluded` toggle that names the rule that fired and how many it caught.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-09-16T10:46:42Z
- **Completed:** 2026-09-16T11:09:07Z
- **Tasks:** 3
- **Files modified:** 13 (`git diff --numstat 1f40d94..HEAD`: 13 files, +2180 / −71)

## Accomplishments

- **Search cannot 500 the page, and that is proven, not asserted.** `build_match_expression` quotes every whitespace token (FTS5's only correct escape) and returns `None` for a blank query so the FTS join is skipped entirely. The lane runs all eight researched hostile inputs through a **real `MATCH`**, and separately asserts the raw forms raise — a guard that cannot pass vacuously.
- **Ordering is deterministic with and without a query.** Every FTS order ends `score, id DESC`; the no-query branch keeps Phase-1's `first_seen_at DESC, id DESC` and never joins `listing_fts` at all. A test seeds three rows with an identical `bm25` score and pins the exact `id DESC` order across two identical requests.
- **The route is thin over one repository.** `queue_repo` owns every predicate, join, ordering and enrichment; the route parses the query string and renders. `MATCH` appears once in `app/`, taking a bound `:match_expression` — the module docstring records the Postgres `tsvector`/`@@`/`ts_rank_cd` substitution.
- **"New since I last looked" is a database row, not a cookie.** `state_repo` reads without writing, creates the single row once, and refuses to move the boundary backwards. Opening the queue advances it **after** the read (so the render keeps its badges); `Mark all as seen` clears them explicitly; a fragment swap advances nothing.
- **Stale is independent of new.** The N−1/N/N+1 boundary uses `Settings.stale_after_days` (`<= now − N` is stale), `is_active = false` is stale regardless of `last_seen_at`, and a listing can carry both badges at once.
- **The merge contract is decided, not described.** `test_queue_hides_absorbed_twin_until_revert` seeds a merge through `dupe_repo.apply_merge`, asserts the twin is absent and the survivor renders `merged from 1 sources`, reverts through `revert_merge`, and asserts the twin reappears — the machine-decided form of the phase's first success criterion.
- **The excluded toggle is a view, not a second page.** Excluded listings are out of the default view; `Show excluded` brings them back dimmed with one chip per firing rule and a count grouped over the latest run, so two listings rejected by one rule read `(2)`.
- **Nothing Phase 1 pinned regressed.** The trigger control, the status slot, `0 listings`, `No listings yet`, the FTS round-trip, the auth seam and the CDN/import guards are all green.

## Task Commits

Each task was committed atomically:

1. **Task 1 (tracer): typed search text reaches the queue as bound FTS and renders rows** - `32994d0` (feat)
2. **Task 2: new-since-last-visit, stale, and the explicit watermark action** - `b8e0fba` (feat)
3. **Task 3: the excluded toggle — rejected listings, dimmed, with the rule that fired** - `01862d4` (test)

**Plan metadata:** _committed with STATE/ROADMAP/REQUIREMENTS after this file_

_Note: `commits: 3` and `plan_head_before: 1f40d94ab81bfdbe4d9cbe5a7230c1c78b9840f5` are measured from the on-disk per-plan ledger at `.git/gsd-plan-head-before-02-07`, not narrated (#3968)._

## Files Created/Modified

- `app/domain/search_query.py` — the pure `build_match_expression`; imports only `re`.
- `app/db/repositories/queue_repo.py` — `QueueQuery`/`QueueRule`/`QueueRow`/`QueuePage` and `read_queue`; the only `MATCH` in `app/` (bound parameter); the absorbed-twin, hidden, saved, scope and latest-run-exclusion predicates; the FTS and no-query branches; merge/exclusion enrichment delegated to plans 02-06 and 02-05.
- `app/db/repositories/state_repo.py` — `get_watermark` (a read that never writes), `advance_watermark` (idempotent row creation, no backwards move) and `mark_all_seen`.
- `app/web/routes.py` — `queue()` rewritten thin (no inline `select`), the new `GET /queue/list` fragment route and `POST /queue/mark-seen`; `parse_queue_query` reads `limit` from settings and clamps `offset`.
- `app/web/templates/html/queue.html` — the search box (`hx-trigger="input changed delay:300ms"`), the three toggles, and the `#queue-list` wrapper; the Phase-1 trigger control and status slot untouched.
- `app/web/templates/html/queue_list.html` — the shared fragment: the verbatim Phase-1 count paragraph, the empty state, the rows, `Mark all as seen` and Load more.
- `app/web/templates/html/_listing_row.html` — the row partial with `id="listing-row-{{ row.id }}"`, the `new`/`stale` badges, the `merged from N sources` link, the exclusion chips and the `dimmed` class.
- `tests/domain/test_search_query.py`, `tests/db/test_queue_state.py`, `tests/api/test_queue_search.py`, `tests/api/test_queue_signals.py`, `tests/api/test_queue_excluded.py` — the five lanes.
- `tests/pipeline/test_ingest_e2e.py` — the two-identical-requests byte comparison narrowed to the row-order contract (see deviations).

## Decisions Made

- **Quoting is the only correct escape.** FTS5 parses `MATCH` as an expression, so the transform treats every token as a literal string rather than trying to sanitise operators. No stemming, no normalisation is added — `porter unicode61` owns that.
- **`None` is a first-class result.** A blank query is not `MATCH ''`; it is "do not touch the FTS table", which is also what keeps the no-query order identical to Phase 1.
- **The tie-break is part of the contract.** Both branches end in a unique column, and the test asserts it by construction rather than by inspection.
- **BM25 weights are code, not settings.** They are a ranking heuristic; making them an environment knob would invite tuning that changes result ordering without a migration.
- **The watermark has exactly two writers and cannot move backwards.** The advance happens after the read, so the page the user is looking at keeps the badges it was rendered with.
- **`innerHTML` swaps, not `outerHTML`.** `#queue-list` is a wrapper in `queue.html`; an `outerHTML` swap would replace it with the fragment and delete the element every later swap targets.
- **Badges live in their own `Signals` cell.** A pre-existing determinism test reads `<td class="listing-title">([^<]+)</td>`, so that cell stays pure — the alternative silently broke a pinned Phase-1 assertion.
- **The latest run decides exclusion, and chips are grouped over that run.** A listing excluded by an older run is back in the default view; the chip count states how many listings the run rejected, not how many are on the page.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] A pinned Phase-1 test's whole-body byte comparison had to be narrowed**
- **Found during:** Task 2 (the watermark)
- **Issue:** `tests/pipeline/test_ingest_e2e.py::test_queue_order_is_deterministic_when_first_seen_at_is_equal` asserted `first.text == second.text` for two consecutive `GET /`s. D-39 (and this plan's explicit task-2 action) makes opening the queue advance the watermark, so the second render legitimately drops the `new` badge the first showed — the two bodies cannot be byte-identical any more. The test's own docstring states its purpose as the id-descending tie-break, so the byte comparison was a proxy that the new feature invalidates by design.
- **Fix:** the determinism contract is now asserted directly — the row order is compared across BOTH responses as well as to the expected `["Platform Engineer", "Senior Python Engineer"]` — and the two bodies are asserted byte-identical **after normalising out the single deliberate difference** (`data-new` and the `new` badge), so any other divergence between two identical requests is still caught.
- **Files modified:** `tests/pipeline/test_ingest_e2e.py`
- **Verification:** `.venv/bin/python -m pytest -q tests/pipeline/test_ingest_e2e.py` passes; the full suite is green.
- **Committed in:** `b8e0fba` (part of task 2)

**2. [Rule 3 - Blocking] The pinned `listing-title` cell regex forced a separate badges column**
- **Found during:** Task 1 (the row partial)
- **Issue:** `tests/pipeline/test_ingest_e2e.py` reads rows with `<td class="listing-title">([^<]+)</td>`, which requires the title cell to contain the title and nothing else. Rendering badges inside it (the natural layout) broke a pinned Phase-1 assertion.
- **Fix:** badges, the `merged from` link and the exclusion chips render in a dedicated `Signals` cell; the title cell stays exactly `<td class="listing-title">{{ row.title }}</td>`.
- **Files modified:** `app/web/templates/html/_listing_row.html`, `app/web/templates/html/queue_list.html`
- **Verification:** `tests/pipeline/test_ingest_e2e.py` and `tests/api/test_run_trigger.py` pass.
- **Committed in:** `32994d0` (part of task 1)

### Deviations of record (no code change)

**3. Task 3's production work landed with task 1's queue rewrite, so its commit is test-only**
- **Found during:** Task 3 (the excluded toggle)
- **Issue:** Task 3 lists `app/db/repositories/queue_repo.py`, `app/web/routes.py`, `_listing_row.html` and `queue.html` as modified. The queue is one coherent surface — the route, the fragment, the row partial and the repository were written together in the tracer — so the exclusion predicate, the chips, the `dimmed` class and the toggle wiring were already in place and verified by the time task 3 started.
- **Fix:** none — no production edit was needed. Task 3's commit is the required `tests/api/test_queue_excluded.py` lane, which is where its acceptance criteria are asserted.
- **Verification:** `tests/api/test_queue_excluded.py` (4 passed) plus the acceptance greps (no `LIKE` anywhere; one bound `MATCH`).
- **Committed in:** `01862d4` (task-3 commit, test only)

**4. `hx-swap="innerHTML"` rather than the plan's `outerHTML`**
- **Found during:** Task 1 (the fragment structure)
- **Issue:** The plan describes `hx-target="#queue-list"` with `hx-swap="outerHTML"`. With `#queue-list` as a wrapper inside `queue.html` (which the plan's acceptance criteria require, since `queue.html` must contain `id="queue-list"`), an outerHTML swap replaces that wrapper with the fragment's own content and removes the element every later swap targets — the second interaction would silently stop working.
- **Fix:** every swap targeting `#queue-list` uses `hx-swap="innerHTML"`, so the wrapper survives and the swaps are idempotent. The URLs, targets and predicate-reset behaviour are as specified.
- **Files modified:** `app/web/templates/html/queue.html`, `app/web/templates/html/queue_list.html`
- **Verification:** `tests/api/test_queue_excluded.py#test_a_predicate_change_resets_the_page_and_load_more_carries_it` and the signals lane drive repeated swaps.
- **Committed in:** `32994d0` / `b8e0fba`

**5. [Environment] Every plan `<verify>` / `<verification>` command was run as `.venv/bin/python -m pytest …` instead of `.venv-host/bin/pytest …`**
- **Found during:** all three tasks (plan-level verification)
- **Issue:** `.venv-host/bin/pytest` is unusable in this sandbox — its shebang is a build-time absolute path that does not exist here, and its compiled wheels are `x86_64-linux-gnu` while the interpreter expects a musl `EXT_SUFFIX`, so `import pydantic_core` fails.
- **Fix:** none — the sibling `.venv/` (same Python 3.14.7, same package versions) was used; every asserted command has an exact equivalent.
- **Verification:** the full suite is green under `.venv`.
- **Recorded in:** `.planning/phases/02-clean-filtered-queryable-queue/deferred-items.md` (from plan 02-01) and repeated here for this plan.

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking), 1 already-satisfied deliverable and 1 swap-mode correction and 1 environment substitution of record.
**Impact on plan:** No scope creep. The narrowed assertion still protects exactly the contract it was written for, and no production file outside the plan's declared surface was touched.

## Issues Encountered

- **`func.bm25(<table>)` is rejected by SQLAlchemy.** Passing the `table()` clause as `bm25`'s first argument raises `ArgumentError`; `literal_column("listing_fts")` renders the bare table name FTS5 requires. Verified against a migrated database before the repository was written, which is why the FTS branch uses a Core `table()` clause with a `text(... MATCH :match_expression)` fragment rather than string SQL.
- **A real keying bug caught by the type checker.** `_rule_kinds` initially keyed its mapping by `int` while `listing_exclusions.rule_id` and `rule_counts_for_listings` are strings — every chip would have silently read "unknown". Fixed before the first test run.
- **The first staleness/watermark test compared a tz-aware expectation to a naive stored value.** SQLite stores naive datetimes; the repository normalises both sides (as plan 02-05 did) and the tests now compare on the instant.
- **`ruff` E501 on four long lines** in the new modules — wrapped. `ruff check app tests` reports **All checks passed!**
- No stubs, no skipped tests, and no unrun `<verify>` blocks: no new entries were added to `.planning/WINDOWS.md`.
- The untracked `.gsd/` and `.planning/milestone.lock` paths pre-date this plan and are outside its scope; they were left untouched.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Ready for plan 02-08 (criteria CRUD).** `queue_repo` documents the `scope_search_id` semantics it can rely on, and the criteria read/write surface is unchanged by this plan.
- **Ready for plan 02-09 (save/hide events).** The `Hidden` and `Saved` toggles are already wired as read-side predicates over the latest `listing_events` row (`hide` / `save`), so those events need only be written for the filters to work — no queue change.
- **Ready for plan 02-10 (run history).** Untouched: the runs page and its last-run strip remain that plan's (D-43).
- **Carry-forward for the verifier:** `deduped_count`, `filtered_count`, `fetched_count` and the terminal-status logic are unchanged; the merge decision, the negative-memory pre-check and the exclusion write path were not modified.
- **Known residual risk (accepted, from the plan):** `OFFSET` paging degrades on a very large corpus. Keyset paging on `(score, id)` / `(first_seen_at, id)` is the documented upgrade path in the repository docstring, not needed for one person's queue.

---
*Phase: 02-clean-filtered-queryable-queue*
*Completed: 2026-09-16*

## Self-Check: PASSED

- All 12 created/modified artifacts and `02-07-SUMMARY.md` verified present on disk.
- All 3 plan commits verified in `git log --all`: `32994d0`, `b8e0fba`, `01862d4`.
- Full suite green: `502 passed, 2 deselected`.
- No missing items.
