---
phase: 02-clean-filtered-queryable-queue
plan: "09"
subsystem: api
tags: [listing-events, append-only, projection, queue, htmx, sqlite-triggers]

# Dependency graph
requires:
  - phase: 01-walking-skeleton
    provides: "the `listing_events` table with its event-type CHECK and the two append-only triggers (migration 0001)"
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-07's `QueueQuery.hidden`/`.saved` flags, the two placeholder predicates and the `_listing_row.html` row partial"
provides:
  - "`app/db/repositories/event_repo.py` — the append-only write side (`append_event`), the projection (`ListingState`/`NO_STATE`/`_fold_events`/`state_for_listings`/`latest_state`) and the saved/hidden SQL predicates"
  - "`POST /listings/{listing_id}/events` — one click saves or hides and swaps exactly one row back"
  - "Save and Hide as distinct, separately-labelled queue actions with a `Saved` filter + star and a `Hidden` filter + one-tap undo"
affects: [02-10]

# Actuals (#2632) — measured, not narrated.
actuals:
  tokens: 14553        # chars/4 of `git diff cd23dbf..HEAD` => 58213/4
  tasks: 2
  commits: 2           # MEASURED: git rev-list --count cd23dbf..HEAD

tech-stack:
  added: []            # no new dependency — the event table, its triggers and HTMX already shipped
  patterns:
    - "Append-only + projection: current state is folded from the event log, never stored in a mutable column, so there is no state row to tamper with and an undo is always another append"
    - "One rule, two expressions: the Python fold and the SQL filter predicate are derived from the same event-pair grouping, so the queue's filtering cannot drift from the projection it claims to show"
    - "Reject-before-write: the route validates the vocabulary and the listing's existence before touching the log, so a bad request returns 422/404 rather than a half-written row or a 500"
    - "One rendering path for a swapped fragment: the POST returns the same row partial the queue renders, so escaping and badge rules cannot diverge"

key-files:
  created:
    - app/db/repositories/event_repo.py
    - app/api/events.py
    - tests/db/test_listing_events.py
    - tests/api/test_listing_events.py
  modified:
    - app/db/repositories/queue_repo.py
    - app/main.py
    - app/web/templates/html/_listing_row.html
    - app/web/templates/html/queue_list.html

key-decisions:
  - "Projection, not a column. `saved` reads the latest of `save`/`unsave`; `hidden` the latest of `hide`/`unhide`; `shortlisted` survives a `save` but is cleared by a later `unsave` (chosen semantics for the Phase-7 type); `view` sets `last_viewed_at` and **nothing else**. All four rules are stated as a table in the module docstring."
  - "Latest is `(occurred_at, id)`. The `id` tie-break is load-bearing: two clicks inside one second share a timestamp, which is the common case, and without it the projection would be non-deterministic."
  - "The saved/hidden SQL predicates live in `event_repo` beside the fold, not in `queue_repo`. The queue must filter and count BEFORE it pages, which a Python projection cannot do — and plan 02-07's `name`-less placeholder (`the latest event of any type`) was actively wrong: a `view` after a `save` would have made the `Saved` filter drop the listing."
  - "`state_for_listings` is ONE query for a whole page. A per-row query is forbidden, because the queue would become N+1 exactly where paging matters; a statement-counting test pins the contract."
  - "Every requested id appears in the returned mapping, `NO_STATE` when the listing has no events — an explicit value rather than a missing key, so a caller cannot mistake \"no events\" for \"unreadable\"."
  - "The route never accepts `occurred_at`. It is server-side, so an event's time cannot be forged (T-02-37)."
  - "Two separately-labelled controls, never one that guesses. The button text flips to the inverse action (`Save`/`Unsave`, `Hide`/`Unhide`), so an already-hidden listing reads as a one-tap undo and the user can always tell which action they performed (T-02-39)."
  - "A Hide composes with plan 02-07's absorbed-twin predicate rather than replacing it: an absorbed twin stays out of the queue whether or not anyone also hid it."
  - "The POST returns the `_listing_row.html` fragment the queue itself renders, resolved through `queue_repo.read_row` — so a swapped row cannot render differently from the row it replaces (T-02-38)."
  - "`excluded` rides on the action URL, so an action taken while looking at `?excluded=1` swaps back a row that still shows its exclusion chips; the route only READS the watermark, so the `new` badge matches the queue."

patterns-established:
  - "Append-only log beside projected state, with the enforcement at the database (triggers) and the repository exposing no mutating call at all — both halves asserted."
  - "A route that validates before it writes, so a rejection is a 422/404 with nothing appended rather than a raised FK error surfacing as a 500."

requirements-completed: [QUEUE-08]

coverage:
  - id: D1
    description: "Saving a listing appends exactly one `save` event, unsaving appends `unsave`, and the current saved state is projected from the latest event (never stored in a column); toggling twice appends two rows and returns the projected state to its original value."
    requirement: QUEUE-08
    verification:
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_posting_save_appends_one_event_and_the_row_reads_saved"
        status: pass
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_save_twice_appends_two_events_and_still_reads_saved"
        status: pass
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_save_then_unsave_appends_two_events_and_reads_unsaved"
        status: pass
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_save_then_unsave_projects_unsaved"
        status: pass
    human_judgment: false
  - id: D2
    description: "A hidden listing leaves the default queue, is reachable through the `Hidden` filter, and its control reads as a one-tap undo."
    requirement: QUEUE-08
    verification:
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_hiding_removes_the_listing_from_the_queue_and_the_control_becomes_undo"
        status: pass
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_hide_then_unhide_projects_visible"
        status: pass
    human_judgment: false
  - id: D3
    description: "A saved listing carries a star on its row and appears under the `Saved` filter, and the filter is unaffected by a later `view`."
    requirement: QUEUE-08
    verification:
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_posting_save_appends_one_event_and_the_row_reads_saved"
        status: pass
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_a_view_after_a_save_leaves_the_listing_saved"
        status: pass
    human_judgment: false
  - id: D4
    description: "Save and Hide are distinct actions in the data, the projection and the UI: one never implies the other, and each has its own labelled control."
    requirement: QUEUE-08
    verification:
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_hiding_leaves_the_saved_flag_untouched_and_vice_versa"
        status: pass
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_only_save_projects_saved_and_not_hidden"
        status: pass
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_only_hide_projects_hidden_and_not_saved"
        status: pass
    human_judgment: false
  - id: D5
    description: "Events are append-only: no repository path issues an UPDATE or DELETE, the database triggers abort both with 'append-only', and the 0001 triggers are neither dropped nor bypassed."
    requirement: QUEUE-08
    verification:
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_append_event_issues_no_update_or_delete"
        status: pass
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_the_database_aborts_an_update_and_a_delete_of_an_event"
        status: pass
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_the_orm_cannot_update_or_delete_an_event_either"
        status: pass
    human_judgment: false
  - id: D6
    description: "The page projection is one query regardless of page size, with a deterministic `(occurred_at, id)` tie-break proved in both insertion orders."
    requirement: QUEUE-08
    verification:
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_state_for_a_whole_page_is_one_query"
        status: pass
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_an_identical_occurred_at_is_broken_by_the_higher_id"
        status: pass
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_an_empty_id_list_returns_empty_without_a_query"
        status: pass
    human_judgment: false
  - id: D7
    description: "A `view` after a `hide` leaves the listing hidden while recording that it was viewed, and a listing with no events projects to a present `NO_STATE` entry."
    requirement: QUEUE-08
    verification:
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_a_view_after_a_hide_leaves_the_listing_hidden_but_records_the_view"
        status: pass
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_a_view_after_a_hide_leaves_the_listing_hidden"
        status: pass
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_a_listing_with_no_events_has_a_present_no_state_entry"
        status: pass
    human_judgment: false
  - id: D8
    description: "An event type outside the vocabulary is 422 and an unknown listing is 404, both before any write; a caller-supplied `occurred_at` is ignored."
    requirement: QUEUE-08
    verification:
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_an_event_type_outside_the_vocabulary_is_422_and_writes_nothing"
        status: pass
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_an_unknown_listing_is_404_and_writes_nothing"
        status: pass
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_a_caller_supplied_timestamp_is_ignored"
        status: pass
      - kind: unit
        ref: "tests/db/test_listing_events.py#test_an_unknown_event_type_is_rejected_by_the_repository"
        status: pass
    human_judgment: false
  - id: D9
    description: "The swapped row fragment is the same rendering path as the queue: listing text is escaped and no safe-marking filter is used; every new route carries the auth seam and no CDN is referenced."
    verification:
      - kind: integration
        ref: "tests/api/test_listing_events.py#test_the_swapped_fragment_escapes_listing_text"
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
  - id: D10
    description: "No behaviour plan 02-07 pinned changed: the queue search, signal and exclusion lanes, the migration contract (including the pre-existing append-only guard) and the run trigger all still pass."
    verification:
      - kind: integration
        ref: "tests/api/test_queue_search.py"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_signals.py"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py"
        status: pass
    human_judgment: false

# Metrics
duration: 20min
completed: 2026-09-16
status: complete
---

# Phase 02 Plan 09: Save and hide, recorded as append-only events

**Save and Hide as two distinct queue actions, each appending one `listing_events` row that the database refuses to update or delete, with the current state folded from the log in one query per page and surfaced as a `Saved` filter with a star and a `Hidden` filter with a one-tap undo.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-09-16T11:52:12Z
- **Completed:** 2026-09-16T12:12:08Z
- **Tasks:** 2
- **Files modified:** 8 (`git diff --numstat cd23dbf..HEAD`: 8 files, +1280 / −30)

## Accomplishments

- **The event log finally has a writer, and only ever an appender.** `append_event` is the single write path in `event_repo`, it validates against `EVENT_TYPES` (the six values the `ck_listing_events_event_type` CHECK already allows), wraps the insert in a SAVEPOINT, and issues nothing but an `INSERT`. A statement listener proves no `UPDATE`/`DELETE` is ever attempted, with a positive control that the listener really saw the insert; the Phase-1 triggers are re-asserted from raw `sqlite3` *and* through the ORM, so a future migration that dropped them fails in this lane.
- **State is projected, not stored.** `_fold_events` is the one shared fold behind both `state_for_listings` (a page) and `latest_state` (one listing), with the projection table — which event pair each flag reads, what `view` does and does not affect, and that an absent flag is false — written out in the module docstring. A listing with no events projects to a **present** `NO_STATE` entry, never a missing key.
- **One query for the whole page.** `state_for_listings` costs exactly one `listing_events` statement for five listings with three events each, pinned by a statement-counting test; an empty id list issues no query at all. The ordering is `(occurred_at, id)` and the tie-break is load-bearing — two clicks inside one second share a timestamp, and both insertion orders are asserted.
- **Plan 02-07's placeholder predicate was wrong, and is fixed.** The old filter asked whether *the* latest event (of any type) was `hide`/`save`, so a `view` after a `save` would have made the `Saved` filter drop the listing. The predicates now come from `event_repo` and are restricted to the `save`/`unsave` and `hide`/`unhide` pairs, so the SQL filter and the Python fold state the same rule.
- **The two actions stay distinct end to end.** Hiding a saved listing leaves `saved` true and vice versa; the row renders two separately-labelled controls; and the button text flips to the inverse action so an already-hidden listing reads as a one-tap undo. D-41 is asserted in the projection, the HTTP surface and the markup.
- **Rejections write nothing.** 422 for an unknown event type and 404 for an unknown listing, both decided *before* the insert — and `occurred_at` is server-side, so a caller cannot forge an event's time.
- **No 02-07 behaviour regressed.** The search, signal, exclusion, migration-contract and run-trigger lanes are all green, and every new route carries the auth seam.

## Task Commits

Each task was committed atomically:

1. **Task 1 (tracer): one click saves a listing and the queue row shows it** - `bb8881d` (feat)
2. **Task 2: the projection contract and the append-only enforcement in depth** - `ca90ad4` (test)

**Plan metadata:** _committed with STATE/ROADMAP/REQUIREMENTS after this file_

_Note: `commits: 2` and `plan_head_before: cd23dbff436dbb8fadb974fe61d7c2d53177127a` are measured from the on-disk per-plan ledger at `.git/gsd-plan-head-before-02-09`, not narrated (#3968)._

## Files Created/Modified

- `app/db/repositories/event_repo.py` — `EVENT_TYPES`, `SAVE_EVENTS`/`HIDE_EVENTS`, `ListingState`, `NO_STATE`, `_fold_events`, `append_event`, `state_for_listings`, `latest_state`, and the `latest_event_type_in`/`saved_predicate`/`hidden_predicate` SQL builders the queue's filters use.
- `app/api/events.py` — `POST /listings/{listing_id}/events`: validate, reject unknown listing, append, commit, re-render the row fragment.
- `app/db/repositories/queue_repo.py` — the placeholder event predicate is gone; the saved/hidden filters now come from `event_repo`; `QueueRow` gained `saved`/`hidden`; `read_row` is the single-row seam the swap uses.
- `app/main.py` — the events router is registered.
- `app/web/templates/html/_listing_row.html` — the `Save`/`Unsave` and `Hide`/`Unhide` forms, the saved star, the hidden badge, `data-saved`/`data-hidden`, and the `show_excluded`/`queue_query` context the standalone fragment needs.
- `app/web/templates/html/queue_list.html` — sets `show_excluded` and `queue_query` once for the row include, and adds the `Actions` column header.
- `tests/api/test_listing_events.py` (11 cases) and `tests/db/test_listing_events.py` (19 cases) — the two lanes.

## Decisions Made

- **The projection rule is expressed twice from one source.** `_fold_events` (Python) and `latest_event_type_in` (SQL) both read the `SAVE_EVENTS`/`HIDE_EVENTS` grouping defined once in `event_repo`. The queue must filter and count *before* paging, which a Python fold cannot do, so the SQL predicate has to exist — but it is derived, not restated.
- **`shortlisted` semantics chosen and documented:** a `shortlist` is set by `shortlist`, survives a `save`, and is cleared by a later `unsave` (a shortlist is the stronger form of the same intent). The type stays unwired in the UI because Phase 7 owns application stages.
- **`view` is recorded and inert.** It sets `last_viewed_at`/`viewed` and touches no flag — the least obvious rule in the projection and the easiest to get silently wrong, so it is pinned from both the DB lane and the HTTP lane.
- **Reject before write.** The route checks the vocabulary and the listing's existence ahead of the insert so the user gets a 422/404 rather than a 500 from a raised foreign key.
- **The action URL carries `excluded`.** An action taken while looking at `?excluded=1` swaps back a row that still shows its exclusion chips; the route only *reads* the watermark, so the `new` badge matches the queue and no visit is recorded by a click.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The saved/hidden SQL predicates had to live in `event_repo` beside the fold**
- **Found during:** Task 1 (wiring the row data)
- **Issue:** The plan says `read_queue` "consumes `event_repo.state_for_listings` for its `Hidden` and `Saved` predicates". Taken literally that is not implementable: the queue filters, counts and pages in SQL, and a Python projection cannot decide which rows are on page 3. Worse, the existing placeholder was a real bug — it compared the latest event *of any type* to `hide`/`save`, so a `view` after a `save` would have made the `Saved` filter drop the listing.
- **Fix:** `event_repo` exports `latest_event_type_in`, `saved_predicate` and `hidden_predicate`, built from the same `SAVE_EVENTS`/`HIDE_EVENTS` grouping the fold uses; `queue_repo` consumes them and keeps only the queue's own SQL. `state_for_listings` still supplies the per-row flags, exactly as the plan's row-wiring sentence asks.
- **Files modified:** `app/db/repositories/event_repo.py`, `app/db/repositories/queue_repo.py`
- **Verification:** `tests/api/test_listing_events.py` (saved and hidden filters), `tests/db/test_listing_events.py`, and the 02-07 queue lanes.
- **Committed in:** `bb8881d` (part of task 1)

**2. [Rule 3 - Blocking] `request.form()` is unusable in this project, so the existing `read_form` helper was reused**
- **Found during:** Task 1 (the POST route)
- **Issue:** Starlette's `request.form()` asserts that `python-multipart` is installed for *any* form parsing, and this project deliberately does not depend on it — so the first run of the new lane failed with `AssertionError: The python-multipart library must be installed to use form parsing`.
- **Fix:** reused `app.api.searches.read_form`, the standard-library urlencoded parser plan 02-08 already added for exactly this reason, rather than duplicating it or adding a dependency.
- **Files modified:** `app/api/events.py`
- **Verification:** `tests/api/test_listing_events.py` — 11 passed.
- **Committed in:** `bb8881d` (part of task 1)

### Deviations of record (no code change)

**3. Task 2's repository tightening already landed with task 1's module**
- **Found during:** Task 2 (the projection contract)
- **Issue:** Task 2 lists `app/db/repositories/event_repo.py` as modified and asks for a shared fold helper, explicit ordering and the projection table in the docstring. The module was written that way in task 1, so the requirements were already met and verified.
- **Fix:** none — no production edit was made. Task 2's commit is its required lane, `tests/db/test_listing_events.py`, which is where the acceptance criteria are asserted.
- **Verification:** 19 passed, including the one-query, tie-break and append-only assertions.
- **Committed in:** `ca90ad4` (task-2 commit, test only)

**4. `queue_list.html` was edited although the plan lists only `_listing_row.html`**
- **Found during:** Task 1 (the standalone fragment)
- **Issue:** The row partial is now rendered two ways — inside the queue, and standalone by the events route. Its previous `page.query.excluded` lookup would have forced the route to fabricate a whole `QueuePage` just to hide one column.
- **Fix:** `queue_list.html` sets `show_excluded` and `queue_query` once, which the row include inherits; the events route passes the same two variables explicitly. One row definition, two callers, no fake page object.
- **Files modified:** `app/web/templates/html/queue_list.html`, `app/web/templates/html/_listing_row.html`
- **Verification:** both the queue lanes and the events lane render the row; `tests/api/test_queue_excluded.py` still passes.
- **Committed in:** `bb8881d`

**5. [Environment] Every plan `<verify>` / `<verification>` command was run as `.venv/bin/python -m pytest …` instead of `.venv-host/bin/pytest …`**
- **Found during:** all tasks (plan-level verification)
- **Issue:** `.venv-host/bin/pytest` is unusable in this sandbox — its shebang is a build-time absolute path that does not exist here, and its compiled wheels are `x86_64-linux-gnu` while the interpreter expects a musl `EXT_SUFFIX`, so `import pydantic_core` fails.
- **Fix:** none — the sibling `.venv/` (same Python 3.14.7, same package versions) was used; every asserted command has an exact equivalent.
- **Verification:** the full suite is green under `.venv`.
- **Recorded in:** `.planning/phases/02-clean-filtered-queryable-queue/deferred-items.md` (from plan 02-01) and repeated here for this plan.

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking), 1 already-satisfied deliverable and 1 necessary file addition and 1 environment substitution of record.
**Impact on plan:** No scope creep. The added file is the sibling template of the one the plan names, and no production file outside the queue/event surface was touched.

## Issues Encountered

- **`HTMLResponse.status_code` is read-only** in Starlette, so the 422/404 fragments are constructed with `status_code=` rather than assigned afterwards. Caught on the first import.
- **`sources.name` is UNIQUE but not the primary key**, so `session.get(Source, "linkedin")` never matched and the seed tried to re-insert the row. The DB lane now looks the source up by `name`.
- **A whitespace-fragile assertion** (`">Save<"`) failed against the real indented markup; replaced with the decisive one — the hidden input's `value="save"` vs `value="unsave"`, which is what the control actually submits.
- **`ruff` F401/E501** on the new lane — one unused import removed and two long lines wrapped. `ruff check app tests` reports **All checks passed!**
- No stubs, no skipped tests, and no unrun `<verify>` blocks: no new entries were added to `.planning/WINDOWS.md`.
- The untracked `.gsd/` and `.planning/milestone.lock` paths pre-date this plan and are outside its scope; they were left untouched.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Ready for plan 02-10 (run history).** Untouched: the runs page and its last-run strip remain that plan's (D-43). The events router is registered alongside the others and adds no boot-time dependency.
- **Carry-forward for the verifier:** `deduped_count`, `filtered_count`, `fetched_count`, the terminal-status logic, the merge/exclusion write paths and the queue's search/signal semantics are unchanged. The only behavioural change to an existing surface is the corrected saved/hidden filter predicate, which is a fix rather than a regression.
- **Known residual risk (accepted, from the plan):** a double-clicked save appends two identical events. The projected state is unchanged and the log honestly records two clicks; application-level de-duplication would require deciding which real events to suppress. Event retention/pruning is recorded as a Phase-8 operations item.

---
*Phase: 02-clean-filtered-queryable-queue*
*Completed: 2026-09-16*

## Self-Check: PASSED

- All 8 created/modified artifacts and `02-09-SUMMARY.md` verified present on disk.
- Both plan commits verified in `git log --all`: `bb8881d`, `ca90ad4`.
- Full suite green: `568 passed, 2 deselected`.
- No missing items.
