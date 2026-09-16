---
phase: 02-clean-filtered-queryable-queue
plan: "06"
subsystem: ui
tags: [merges, dedup, revert, htmx, jinja2, audit-trail, sqlalchemy]

# Dependency graph
requires:
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-04's `apply_merge` + `snapshot_json`, `reverted_pairs`/`merged_pairs` and the `listing_dupes` append-and-mark table"
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-01's `uq_listing_dupes_pair` index and the `reverted_at` / `reverted_by` columns"
provides:
  - "`dupe_repo.list_merges` / `merge_rate` / `revert_merge` / `merge_summary_for_listings` and their `MergeSide`/`MergeRecord`/`MergeRate`/`RevertResult` read models"
  - "`GET /merges` — the merge rate with its window named, and the rows behind it"
  - "`POST /merges/{dupe_id}/revert` — one-click undo returning the `#merges-table` fragment"
  - "`app/web/templates/html/merges.html` — the audit page, with the panel as a reusable Jinja macro"
affects: [02-07, 02-10]

# Actuals (#2632) — measured, not narrated.
actuals:
  tokens: 12160        # chars/4 of `git diff 5bedcfa..HEAD` => 48640/4
  tasks: 2
  commits: 2           # MEASURED: git rev-list --count 5bedcfa..HEAD

tech-stack:
  added: []            # no new dependency — the audit page and revert cost zero new packages
  patterns:
    - "Fragment-via-macro: the swapped panel is a Jinja macro inside its page template, rendered by `Template.make_module`, so one file and one definition serve both the page and the htmx swap"
    - "Rate and rows swap together: the aggregate lives inside the fragment root, so a revert cannot leave a stale number beside a fresh table"
    - "Flag-flip reversibility: a merge moves nothing, so undo is an UPDATE on the audit row plus a field restore — never a migration, never a DELETE"
    - "Negative memory as a pre-check: the revert records intent so the NEXT run declines to redo it (the control is asserted at the pipeline boundary, not at the repository)"

key-files:
  created:
    - app/web/templates/html/merges.html
    - tests/api/test_merges_view.py
    - tests/pipeline/test_dedup_revert.py
  modified:
    - app/db/repositories/dupe_repo.py
    - app/api/runs.py

key-decisions:
  - "The panel markup is a Jinja **macro** inside `merges.html`, rendered for the fragment by `Template.make_module` — one template file and one definition of the markup. `make_module` also executes the page body (the `content` block), so `render_merges_table` passes the same `merges`/`rate`/`note` the block needs; that coupling is stated in the function docstring so a later edit to the page body is visible."
  - "The rate and the reverted count live **inside** the `id=\"merges-table\"` root: reverting moves both numbers, so the swap must carry them or the page shows a stale rate beside a fresh table (T-02-25)."
  - "`MergeRate.rate` is a whole-number percentage for display only and is `None` when `fetched` is zero or null — a division by zero is a bug and a `0%` reading would be a lie. The two integers (`merged`, `fetched`) are always rendered beside it and no float is ever persisted."
  - "The rate counts **un-reverted** merges only, with the reverted count shown separately, so reverting visibly moves the number instead of silently leaving it unchanged."
  - "`revert_merge` restores snapshot fields through the survivor's **ORM row**, never raw SQL, so the `listings_au` FTS maintenance trigger fires and the search index cannot drift (reusing `apply_merge`'s reasoning)."
  - "A snapshot key that is not a column on the `Listing` mapper is counted in `RevertResult.skipped` rather than raising: a snapshot written against an older schema degrades, and the skip is visible instead of silently partial (T-02-21)."
  - "`UNRENDERED_SNAPSHOT_FIELDS` excludes `source_extras_json` / `quality_signals_json` from the audit page's snapshot list (T-02-24: expose no new free-form blob) while `revert_merge` still restores them — a display rule, not a data rule, and it lives in the repository so the template cannot disagree."
  - "No `listing_events` row is written on merge or on revert: that log records *user* actions, and writing a synthetic `hide`/`unhide` would make it claim an action that never happened and would force an un-hide step on every revert."
  - "The route owns the commit; the repository never commits (the `source_repo` contract). An unknown row answers 404 with a distinguishable body; an already-reverted row answers 200 with the current panel plus a note, so a double click is idempotent and legible."

patterns-established:
  - "Aggregate-and-rows on one page: the merge rate and the `listing_dupes` rows behind it render from the same request, so an incorrect merge can never hide behind a number (T-02-25)."
  - "Both endpoints described by their own fields: the twin is shown by its own title/company/location/sources rather than by an id, which is what makes an automatic merge judgeable (D-26)."
  - "Total boundary functions: `revert_merge` returns a `RevertResult` for every outcome (reverted / already-reverted / not-found) and never raises on a stale snapshot."

requirements-completed: [QUEUE-04, QUEUE-09]

coverage:
  - id: D1
    description: "The Merges page lists every `listing_dupes` row newest-first with the survivor and the twin both identified by their own titles, companies, locations and source names, plus the method, the score, the merge time and the survivor's pre-merge snapshot values."
    requirement: QUEUE-04
    verification:
      - kind: integration
        ref: "tests/api/test_merges_view.py#test_merges_page_lists_the_rate_its_window_and_the_rows_behind_it"
        status: pass
    human_judgment: false
  - id: D2
    description: "The merge rate renders as a percentage with both integers beside it over a named window (the latest run), or an em dash when the denominator is zero, with the reverted count shown separately."
    requirement: QUEUE-09
    verification:
      - kind: integration
        ref: "tests/api/test_merges_view.py#test_merges_page_lists_the_rate_its_window_and_the_rows_behind_it"
        status: pass
      - kind: integration
        ref: "tests/api/test_merges_view.py#test_reverting_a_merge_restores_the_survivor_and_marks_the_audit_row"
        status: pass
    human_judgment: false
  - id: D3
    description: "One-click revert restores the survivor's snapshot fields through the ORM row, sets `reverted_at`/`reverted_by`, keeps the audit row, and never deletes or touches `listing_sources`."
    requirement: QUEUE-04
    verification:
      - kind: integration
        ref: "tests/api/test_merges_view.py#test_reverting_a_merge_restores_the_survivor_and_marks_the_audit_row"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_dedup_revert.py#test_a_reverted_merge_is_durable_and_the_pair_stays_separate"
        status: pass
    human_judgment: false
  - id: D4
    description: "A reverted merge is durable: the next run creates zero new `listing_dupes` rows and reports `deduped_count == 0`, and the pair is separated in both orientations."
    requirement: QUEUE-04
    verification:
      - kind: integration
        ref: "tests/pipeline/test_dedup_revert.py#test_a_reverted_merge_is_durable_and_the_pair_stays_separate"
        status: pass
    human_judgment: false
  - id: D5
    description: "`merge_summary_for_listings` returns the un-reverted merge count per survivor, non-zero while a merge is in force and empty after a revert, for plan 02-07's queue-row indicator."
    requirement: QUEUE-04
    verification:
      - kind: integration
        ref: "tests/pipeline/test_dedup_revert.py#test_a_reverted_merge_is_durable_and_the_pair_stays_separate"
        status: pass
    human_judgment: false
  - id: D6
    description: "Untrusted listing text is escaped on the audit page: the escaped form is rendered and the raw tag never reaches the response, wrapped in a source guard that fails if a safe-marking filter is ever added."
    requirement: QUEUE-04
    verification:
      - kind: integration
        ref: "tests/api/test_merges_view.py#test_merges_page_escapes_listing_text"
        status: pass
      - kind: unit
        ref: "tests/api/test_merges_view.py#test_the_page_has_no_unsafe_filter_on_listing_text"
        status: pass
      - kind: unit
        ref: "tests/test_no_cdn.py"
        status: pass
    human_judgment: false
  - id: D7
    description: "The revert path is total against a stale snapshot: a null snapshot is a no-op restore that still separates the pair, and an unknown snapshot key is skipped and counted rather than raising."
    requirement: QUEUE-04
    verification:
      - kind: integration
        ref: "tests/pipeline/test_dedup_revert.py#test_reverting_a_null_snapshot_still_separates_the_pair"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_dedup_revert.py#test_a_snapshot_key_that_is_not_a_column_is_skipped_and_counted"
        status: pass
    human_judgment: false
  - id: D8
    description: "A merge chain (three boards, two merges onto the earliest-seen survivor) reverts newest-first with each merge restoring only its own snapshot, and a third run re-merges neither pair."
    requirement: QUEUE-04
    verification:
      - kind: integration
        ref: "tests/pipeline/test_dedup_revert.py#test_a_merge_chain_reverts_newest_first_and_survives_a_third_run"
        status: pass
    human_judgment: false

# Metrics
duration: 15min
completed: 2026-09-16
status: complete
---

# Phase 02 Plan 06: The merge audit trail — see the rate, inspect the rows, undo a bad merge

**A `/merges` page showing the merge rate over a named window with every `listing_dupes` row behind it — survivor and twin described by their own fields plus the survivor's pre-merge snapshot — and a one-click revert that restores the snapshot, marks the audit row, deletes nothing, and survives the next run.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-09-16T10:28:09Z
- **Completed:** 2026-09-16T10:42:41Z
- **Tasks:** 2
- **Files modified:** 5 (`git diff --numstat 5bedcfa..HEAD`: 5 files, +1209 / -3)

## Accomplishments

- **The rate and the rows behind it are one page, never a second query.** `GET /merges` renders `merge_rate` (un-reverted merges over the latest run's `fetched_count`) with the window named in the heading, both integers beside the percentage, the reverted count shown separately, and every `listing_dupes` row newest-first underneath — so an incorrect automatic merge can never hide behind an aggregate (D-29 / T-02-25).
- **The twin is inspectable, not just an id.** Each row shows the survivor and the twin side by side with their own titles, companies, locations and source names, the method and score, the merge time, and the survivor's pre-merge `snapshot_json` as a definition list — which is what makes the merge judgeable by a human (D-26).
- **Revert is a flag flip, not a migration.** `revert_merge` restores every field named in that row's snapshot **through the survivor's ORM row** (so the `listings_au` FTS trigger fires), sets `reverted_at` and `reverted_by`, and never deletes: no `DELETE` exists on `listing_dupes`, and `listing_sources` is never touched (the A5 divergence). The twin reappears in the queue automatically because the visibility predicate is the un-reverted dupe row — no un-hide step, and no `listing_events` row is written for either direction.
- **The revert is durable, proven at the pipeline boundary.** A second real run with the same adapters creates **zero** new `listing_dupes` rows and reports `deduped_count == 0`: plan 02-04's negative-memory pre-check does the filtering, and the test drives the whole pipeline rather than the repository in isolation (D-28 / T-02-22).
- **The revert path is total.** A null snapshot is a no-op restore that still separates the pair; an unknown snapshot key is skipped and counted (`RevertResult.skipped`) instead of raising; an already-reverted row writes nothing; an unknown row is a 404 with a distinguishable body.
- **The per-listing merge indicator is ready for the queue.** `merge_summary_for_listings` returns `{listing_id: un-reverted merge count}` in one query — non-zero while the merge is in force and empty once reverted — so plan 02-07's queue row needs no join of its own.
- **Untrusted listing text stays text.** Jinja autoescape is the only escaping in play (no safe-marking filter anywhere in the template, guarded by a source test), and the page carries no remote asset (`tests/test_no_cdn.py` still green).

## Task Commits

Each task was committed atomically:

1. **Task 1 (tracer): End-to-end — the Merges page lists a merge, shows the twin, and reverts it** - `a1d44bb` (feat)
2. **Task 2: Revert is durable — the pair is never silently re-merged** - `99f0f74` (test)

**Plan metadata:** `_pending_` (docs: complete 02-06 plan)

_Note: `commits: 2` and `plan_head_before: 5bedcfa76df04bdebab70f5404bf64841cff1e62` are measured from the on-disk per-plan ledger at `.git/gsd-plan-head-before-02-06`, not narrated (#3968)._

## Files Created/Modified

- `app/db/repositories/dupe_repo.py` — extended with `MergeSide`, `MergeRecord`, `MergeRate`, `RevertResult`, `list_merges` (newest-first `(merged_at DESC, id DESC)`, bounded by `MERGE_LIST_LIMIT`, both endpoints described from their own `listings` rows plus their `listing_sources`), `merge_rate`, `revert_merge` (UPDATE-only, ORM field restore, total against stale snapshots), `merge_summary_for_listings`, and `UNRENDERED_SNAPSHOT_FIELDS`.
- `app/api/runs.py` — `GET /merges` (full page) and `POST /merges/{dupe_id}/revert` (the `#merges-table` fragment), both behind `Depends(current_user)`; `render_merges_table` renders the panel macro without rendering the page.
- `app/web/templates/html/merges.html` — extends `html/base.html`; the panel is a macro containing the `id="merges-table"` root, the rate/reverted summary, the newest-first table with stable `id="merge-row-{{ row.id }}"` ids, the twin/survivor columns, the snapshot definition list, and the per-row `hx-post` revert button (disabled and labelled differently once reverted).
- `tests/api/test_merges_view.py` — the rate/rows/window contract, HTML escaping, the template-source guard, the restore-and-mark revert, the 404 branch, and the idempotent second revert.
- `tests/pipeline/test_dedup_revert.py` — durability across a second run, the two-orientation negative memory, the before/after `merge_summary_for_listings` pair, the merge chain reverted newest-first then a third run, and the null/unknown-key snapshot totality cases.

## Decisions Made

- **The page body and the swapped fragment share one definition.** The panel is a Jinja macro inside `merges.html`; the fragment is rendered through Jinja's `Template.make_module`. Because `make_module` also executes the page's `content` block, `render_merges_table` passes the same `merges`/`rate`/`note` the block needs — documented in the function docstring so the coupling is discoverable. A separate partial template would have kept two files but broken the plan's single-`merges.html` surface and its literal `id="merges-table"` requirement.
- **The rate moved into the fragment root.** Reverting changes both the rate and the reverted count; keeping them inside the swapped element is what makes the number honest after a revert.
- **`rate` is an integer percentage for display; the integers are the record.** `None` at a zero or null denominator, never `0.0`; `merged`/`fetched` are always rendered so no precision is lost to rounding, and no float is persisted.
- **Un-reverted merges only.** Both `merge_rate` and `merge_summary_for_listings` count un-reverted rows, so a revert visibly moves the rate and removes the queue-row indicator; the reverted count is displayed beside the rate rather than folded into it.
- **Snapshot JSON blobs are excluded from the page but not from the restore.** `UNRENDERED_SNAPSHOT_FIELDS` keeps `source_extras_json`/`quality_signals_json` off the audit page (T-02-24) while `revert_merge` still restores them, so the display rule cannot silently weaken the undo.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The fragment had to be renderable from the single `merges.html`, so the panel became a macro**
- **Found during:** Task 1 (the Merges page)
- **Issue:** The plan requires `merges.html` to extend `html/base.html` **and** to contain the literal `id="merges-table"` root **and** requires `POST /merges/{dupe_id}/revert` to return that table fragment — while listing only `merges.html` as the template surface. A separate `_merges_table.html` partial would satisfy the fragment requirement but would move the literal id out of `merges.html`; duplicating the markup would create two definitions to drift.
- **Fix:** The panel is a Jinja **macro** declared in `merges.html` and called both by the page's `content` block and by `render_merges_table` (via `Template.make_module`). One file, one definition, both literal criteria satisfied. The make-module context coupling is documented in the docstring and exercised by every revert-path test.
- **Files modified:** `app/web/templates/html/merges.html`, `app/api/runs.py`
- **Verification:** `.venv/bin/python -m pytest -q tests/api/test_merges_view.py` → 6 passed.
- **Committed in:** `a1d44bb` (part of task 1)

### Deviations of record (no code change)

**2. Task 2's repository deliverable was already satisfied by task 1, so it was verified rather than edited**
- **Found during:** Task 2 (revert durability)
- **Issue:** Task 2 lists `app/db/repositories/dupe_repo.py` as modified and asks to "tighten `merge_summary_for_listings` so plan 02-07 gets exactly what it needs without a second query", with the docstring stating un-reverted-only. Task 1 had already implemented it that way: a single `GROUP BY listing_id` over `ListingDupe.reverted_at.is_(None)`, ordered by `listing_id`, with the contract stated in the docstring.
- **Fix:** none — no edit was made. Editing the function would have been churn with no behavioural change, so the existing implementation was verified against the task-2 acceptance criterion instead.
- **Verification:** `tests/pipeline/test_dedup_revert.py#test_a_reverted_merge_is_durable_and_the_pair_stays_separate` asserts the non-zero-before / empty-after pair.
- **Committed in:** task-2 commit `99f0f74` (test only)

**3. [Environment] Every plan `<verify>` / `<verification>` command was run as `.venv/bin/python -m pytest …` instead of `.venv-host/bin/pytest …`**
- **Found during:** all tasks (plan-level verification)
- **Issue:** `.venv-host/bin/pytest` is unusable in this sandbox — its shebang is a build-time absolute path that does not exist here, and its compiled wheels are `x86_64-linux-gnu` while the interpreter expects a musl `EXT_SUFFIX`, so `import pydantic_core` fails.
- **Fix:** none — the sibling `.venv/` (same Python 3.14.7, same package versions) was used; every asserted command has an exact equivalent.
- **Verification:** the full suite is green under `.venv`.
- **Recorded in:** `.planning/phases/02-clean-filtered-queryable-queue/deferred-items.md` (from plan 02-01) and repeated here for this plan.

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking), 1 verified-not-edited deliverable and 1 environment substitution of record.
**Impact on plan:** No scope creep. The macro approach is confined to the two files the plan already lists; no production file outside the plan's surface was touched.

## Issues Encountered

- **`Template.make_module({})` on an extending template raises.** The page's `content` block executes during module construction, so an empty context failed with `'rate' is undefined`. Resolved by passing the three variables the block references; the constraint is now documented in `render_merges_table` and covered by the fragment-path tests (which is why the failure surfaced immediately as a test failure rather than only at runtime in a browser).
- **The template's own comment tripped the safe-marking guard.** The first draft of `merges.html` mentioned the forbidden filter name in a comment, and the acceptance guard greps the source. Reworded to describe the rule without naming the filter. `ruff check app tests` reports **All checks passed!**
- No stubs, no skipped tests, and no unrun `<verify>` blocks: no new entries were added to `.planning/WINDOWS.md`.
- The untracked `.gsd/` and `.planning/milestone.lock` paths pre-date this plan and are outside its scope; they were left untouched.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Ready for plan 02-07 (queue visibility).** `merge_summary_for_listings` is exported and counts un-reverted merges only, so the queue row's `merged from N sources` indicator needs no join of its own. The queue-level half of the revert contract — the twin reappearing in `GET /` once the un-reverted row is cleared — is plan 02-07's `tests/api/test_queue_search.py::test_queue_hides_absorbed_twin_until_revert`, deliberately not duplicated here; it is executed by the full-suite run.
- **Ready for plan 02-10 (`/runs` history).** The runs page and its last-run strip are untouched by this plan (D-43).
- **Carry-forward for the verifier:** `deduped_count`, `filtered_count`, `fetched_count` and the terminal-status logic are unchanged; the merge decision and the negative-memory pre-check are plan 02-04's and were not modified.
- **Known residual risk (accepted, unchanged):** a revert applied out of order in a merge chain can drop a later merge's fill. It is documented in `revert_merge`'s docstring, the UI presents merges newest-first so the natural order is the correct one, the chain test pins that order, and the later merge stays revertible so nothing is lost.

---
*Phase: 02-clean-filtered-queryable-queue*
*Completed: 2026-09-16*

## Self-Check: PASSED

- All 5 created/modified artifacts and `02-06-SUMMARY.md` verified present on disk.
- Both plan commits verified in `git log --all`: `a1d44bb`, `99f0f74`.
- Full suite green: `460 passed, 2 deselected`.
- No missing items.
