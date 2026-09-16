---
phase: 02-clean-filtered-queryable-queue
plan: "04"
subsystem: pipeline
tags: [dedup, merge, rapidfuzz, fts5, sqlalchemy, audit-trail, negative-memory]

# Dependency graph
requires:
  - phase: 02-clean-filtered-queryable-queue
    provides: migration 0002's listing_dupes pair indexes and ck_filter_rules_kind (02-01), rapidfuzz==3.14.6 (02-02), and the pure decision layer's conventions (02-03)
  - phase: 01-walking-skeleton-foundations
    provides: listing_repo's _LISTING_FIELDS/_value/SAVEPOINT idiom, run_pipeline's persist loop and _finish, the FTS listings_au trigger, and the StageCounts/StageResult shapes
provides:
  - app/domain/dedup.py — the pure, safety-biased Tier-2 gate (grades_conflict, score_pair, candidate_merges)
  - app/db/repositories/dupe_repo.py — candidates_for_block, reverted_pairs, merged_pairs, apply_merge, count_merges_for_run
  - app/pipeline/dedup_stage.py — the post-persist dedup stage
  - runs.deduped_count now counts rows absorbed by a merge
affects: [02-05 filter stage insertion point, 02-06 Merges view + revert, 02-07 queue visibility predicate that hides an absorbed twin]

# Actuals (#2632) — same estimateTokens scale (chars/4 over the realized diff).
actuals:
  tokens: 15106
  tasks: 2
  commits: 3
  plan_head_before: cf1e6f7baf6bc6d0d528c8aea1c573292e61b3ed

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Component gate primary, fuzzy score secondary (token_sort_ratio, never token_set_ratio)"
    - "Fill-blanks-only field union with an empty-string-is-blank rule"
    - "Append-and-mark audit table: listing_dupes is INSERT-only on this path"
    - "Negative memory as a two-orientation pre-check, not an index"
    - "ORM-row field fills so the FTS listings_au trigger cannot drift"

key-files:
  created:
    - app/domain/dedup.py
    - app/db/repositories/dupe_repo.py
    - app/pipeline/dedup_stage.py
    - tests/domain/test_dedup.py
    - tests/db/test_dupes.py
    - tests/pipeline/test_dedup_merge.py
  modified:
    - app/pipeline/run.py

key-decisions:
  - "The grade guard decides before the score: Senior X never merges with X, whatever the fuzzy score (PITFALLS P3)"
  - "The company gate defaults its fuzzy threshold to theta rather than inventing a second constant; the candidate pool is already blocked by company equality"
  - "salary/location/company None is never a rejection reason; a pair whose posted_at is NULL on either side still passes the window"
  - "The earliest-seen listing is always the survivor and an absorbed listing leaves the pool, so a three-way duplicate yields two merges onto the first-seen listing, never a chain"
  - "listing_sources rows stay on the absorbed twin (A5, amending ARCHITECTURE 8.3) so revert stays a flag flip; 'merged from N sources' goes through the listing_dupes join"
  - "deduped_count means rows absorbed by a merge; the old sum(created) meaning is retired in a comment so it cannot be 'restored'"
  - "An already-merged pair is filtered before scoring, so a re-run neither re-merges nor records a spurious error"

patterns-established:
  - "Two pre-checks before scoring: reverted_pairs (the user's undo) and merged_pairs (an already-correct merge), both in both orientations"
  - "A total pipeline stage: one failing merge is counted and logged, the rest still apply"

requirements-completed: [QUEUE-03]

coverage:
  - id: D1
    description: "A job seen on two boards ends the run as one survivor plus one retained twin, with exactly one audited listing_dupes row"
    requirement: QUEUE-03
    verification:
      - kind: integration
        ref: "tests/pipeline/test_dedup_merge.py#test_two_sources_one_job_merges_once_with_an_audit_row"
        status: pass
    human_judgment: false
  - id: D2
    description: "Nothing non-null is ever overwritten, an empty string counts as blank, and the absorbed listing is never deleted or deactivated"
    requirement: QUEUE-03
    verification:
      - kind: integration
        ref: "tests/db/test_dupes.py#test_merge_fills_blanks_and_never_overwrites_a_non_null"
        status: pass
      - kind: integration
        ref: "tests/db/test_dupes.py#test_an_empty_string_counts_as_blank_but_a_real_value_does_not"
        status: pass
      - kind: integration
        ref: "tests/db/test_dupes.py#test_the_merge_deletes_nothing_and_re_points_no_source_rows"
        status: pass
    human_judgment: false
  - id: D3
    description: "snapshot_json holds the survivor's pre-merge values for exactly the fields the merge wrote"
    requirement: QUEUE-03
    verification:
      - kind: integration
        ref: "tests/db/test_dupes.py#test_snapshot_records_exactly_the_written_fields_and_their_prior_values"
        status: pass
    human_judgment: false
  - id: D4
    description: "A candidate pair with a reverted listing_dupes row in either orientation is skipped before scoring, and a re-run does not re-merge an already-merged pair"
    requirement: QUEUE-03
    verification:
      - kind: integration
        ref: "tests/db/test_dupes.py#test_reverted_pairs_is_empty_then_returns_both_orientations"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_dedup_merge.py#test_a_second_run_does_not_re_merge_or_record_a_spurious_error"
        status: pass
    human_judgment: false
  - id: D5
    description: "A grade-carrying title never merges with the same title without the grade, and the refusal is the guard's rather than a low score"
    requirement: QUEUE-03
    verification:
      - kind: unit
        ref: "tests/domain/test_dedup.py#test_senior_versus_ungraded_never_merges"
        status: pass
      - kind: unit
        ref: "tests/domain/test_dedup.py#test_two_different_grades_never_merge"
        status: pass
      - kind: unit
        ref: "tests/domain/test_dedup.py#test_token_set_ratio_is_subset_forgiving_and_is_never_the_gate"
        status: pass
    human_judgment: false
  - id: D6
    description: "runs.deduped_count equals the merges written by the run, not the created count"
    requirement: QUEUE-03
    verification:
      - kind: integration
        ref: "tests/pipeline/test_dedup_merge.py#test_two_sources_one_job_merges_once_with_an_audit_row"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_dedup_merge.py#test_a_run_with_no_duplicate_reports_zero_merges"
        status: pass
    human_judgment: false
  - id: D7
    description: "The stage reads theta and the posted window from Settings; no threshold literal lives under app/pipeline"
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_no_distinctive_threshold_literal_remains_in_probe_or_pipeline"
        status: pass
    human_judgment: false
  - id: D8
    description: "A merge's field fill goes through the ORM row, so the listings_au trigger keeps the FTS index in sync"
    verification:
      - kind: integration
        ref: "tests/db/test_dupes.py#test_a_filled_description_is_searchable_on_the_survivor"
        status: pass
      - kind: integration
        ref: "tests/db/test_fts_triggers.py"
        status: pass
    human_judgment: false

# Metrics
duration: 15min
completed: 2026-09-16
status: complete
---

# Phase 2 Plan 04: Tier-2 dedup and merge — the same job found twice becomes one listing

**A cross-source duplicate collapses automatically into one survivor plus a retained, inspectable twin, with exactly one audited `listing_dupes` row carrying the survivor's pre-merge snapshot; `runs.deduped_count` now reports merges rather than the created count.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-09-16T09:39:31Z
- **Completed:** 2026-09-16T09:54:49Z
- **Tasks:** 2
- **Files modified:** 7 (6 created, 1 extended)

## Accomplishments

- **The thinnest true end-to-end merge works.** Two stub boards return the same job with the same normalised `(company, title, location)`; both rows persist; the post-persist stage scores the pair; the earlier-seen listing absorbs the other and receives the twin's salary into its blank; one `listing_dupes` row records `method="fuzzy_tuple"`, the score, `merged_at` and the pre-merge snapshot; the run reports `deduped_count == 1` and `fetched_count == 2`.
- **The gate is component-based and safety-biased.** `grades_conflict` refuses `Senior X` vs `X` (and `X II` vs `Senior X`) *before* any score is computed, and the token-set pathology is captured as executable evidence: `token_set_ratio` returns `100.0` for the subset pair immediately beside the assertion that `score_pair` still refuses it. `token_sort_ratio` is the gate.
- **An absent value is never a rejection reason.** Salary, remote, seniority and location rules (from 02-03) are joined here by the dedup policy: a `None` company never merges, a `None` location passes the location gate, and a `posted_at` that is `NULL` on either side still passes the window.
- **Fill-blanks-only is machine-checked.** `apply_merge` iterates `_LISTING_FIELDS` (no second tuple), writes only when the survivor is blank and the twin is not, treats `""` as blank, and records the survivor's prior value for each field written — asserted as `set(snapshot) == {"location_raw"}` with value `None`.
- **The absorbed twin is retained and unre-pointed (A5).** `listings` stays at 2 rows, the twin stays `is_active`, and both boards' `listing_sources` rows keep pointing at their own listing — the deliberate divergence from `ARCHITECTURE.md` §8.3 that keeps a revert a flag flip.
- **FTS cannot drift.** The fill goes through the survivor's ORM row, and a merge-then-search test proves the `listings_au` trigger re-indexed the survivor with the twin's description.
- **`deduped_count` now has a real meaning** — rows absorbed by a merge — and the retired `sum(created)` line carries a comment so a future reader cannot "restore" it.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end — two sources, one duplicate, one merge with an audit row** - `1ce92ea` (feat)
2. **Task 2: The safety-biased gate in depth, and the merge repository's invariants** - `731f09d` (test)
3. **Deviation fix: filter already-merged pairs** - `49863f2` (fix)

**Plan metadata:** _committed with STATE/ROADMAP/REQUIREMENTS after this file_

Tracer gate (task 1): its `<verify>` is automated-only and `human_verify_mode=end-of-phase`, so the verify was re-run and execution continued without a synthesized checkpoint.

## Files Created/Modified

- `app/domain/dedup.py` — `GRADE_TOKENS`, `CandidateFacts`, `MergeDecision`, `grades_conflict`, `score_pair`, `candidate_merges`. Pure; imports stdlib + `rapidfuzz` only.
- `app/db/repositories/dupe_repo.py` — `candidates_for_block`, `reverted_pairs`, `merged_pairs`, `apply_merge`, `count_merges_for_run`; the A5 divergence documented in the module docstring.
- `app/pipeline/dedup_stage.py` — `DEDUP_STAGE`, `run_dedup_stage`; θ and the window from `Settings`; bounded token-set diagnostic; total.
- `app/pipeline/run.py` — the stage runs after the persist loop and before `_finish`; `_finish` takes `merged_count`; `deduped_count` repurposed.
- `tests/domain/test_dedup.py` (15 tests), `tests/db/test_dupes.py` (7 tests), `tests/pipeline/test_dedup_merge.py` (4 tests).

## Decisions Made

- **The grade guard runs first and is decisive.** A pair refused there can never merge, whatever the fuzzy score — the cheapest defence against the P3 over-merge, and it belongs on the decision path rather than in the repository.
- **The company gate reuses θ** (`company_threshold` defaults to `threshold`) instead of inventing a second fuzzy constant. The candidate pool is already blocked by `company_norm` equality, so the fuzzy company check only matters to a direct `score_pair` caller; a second knob nobody tunes would be worse than reusing one.
- **A three-way duplicate never chains.** The absorbed listing leaves the pool, so two decisions both absorb onto the first-seen survivor — asserted as survivor ids `[1, 1]`.
- **`apply_merge` does not pre-check for an existing pair** — the unique index is the guard, the insert is wrapped in a SAVEPOINT, and the stage catches a refusal. The *stage* filters already-merged pairs so a re-run stays quiet (see the deviation below).
- **`candidates_for_block` deliberately does not apply the posted window** in SQL: the window is a per-pair property and any per-block anchor could silently drop a genuinely matchable pair. The authoritative rule is `candidate_merges`' per-pair check.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] An already-merged pair was re-proposed on every re-run and recorded a spurious error**
- **Found during:** Task 2, writing the DB lane and reasoning about D-36 ("merges are re-planned from scratch every run").
- **Issue:** The stage filtered only `reverted_pairs`. On a second run over the same listings the same pair is re-scored, the gate passes, `apply_merge` attempts the insert, and the plan-02-01 unique index refuses it — a *per-run error* recorded in `runs.errors_json` and the stage log, every day, for a merge that was already correct. `deduped_count` stayed correct (0), but a permanent misleading warning contradicts RUN-04's "every run observable" goal.
- **Fix:** Added `dupe_repo.merged_pairs` (both orientations, `reverted_at IS NULL`), symmetric to `reverted_pairs`, and filtered it alongside. A second run now proposes nothing, records no dedup error, and leaves `deduped_count == 0`.
- **Files modified:** `app/db/repositories/dupe_repo.py`, `app/pipeline/dedup_stage.py`, `tests/db/test_dupes.py`, `tests/pipeline/test_dedup_merge.py`
- **Verification:** `tests/pipeline/test_dedup_merge.py#test_a_second_run_does_not_re_merge_or_record_a_spurious_error` passes; full suite 406 passed.
- **Committed in:** `49863f2`

### Interface refinements (documented, not silent)

- **`app/domain/dedup.py` does not import `app.domain.listing`.** The plan allowed "the standard library, `rapidfuzz`, and `app.domain.listing`"; nothing from `listing.py` is needed, because normalisation happens upstream in `normalise_listing` and `CandidateFacts` already carries the normalised fields. The module imports stdlib + `rapidfuzz` only — a strict subset, and the import-discipline guard passes.
- **`apply_merge` drops the plan's vestigial `survivor_fields_on_twin` parameter.** The fill values are read from the twin's own `listings` ORM row, which is the only correct source: the stage's `CandidateFacts` deliberately carries only the decision fields (no salary/location/description), so the caller could not supply a fill map. `now` and `run_id` are kept as specified.
- **`from rapidfuzz import fuzz` (module import) rather than `from rapidfuzz.fuzz import token_sort_ratio`.** Task 1's acceptance greps for the literal `fuzz.token_sort_ratio` and requires `fuzz.token_set_ratio` to be absent from `app/domain/dedup.py`, so the module-qualified call is the correct spelling. The docstring describes token-set ratio in prose, never as the forbidden literal.
- **`candidates_for_block` accepts `posted_window_days` per the plan's signature but does not apply it in SQL** (see Decisions).
- **`_finish` gained a `merged_count: int = 0` keyword.** Keeping a default preserves the existing call shape for anything else that finishes a run.

### Environment substitution (not a plan defect)

- **`<verify>` commands ran through `.venv/bin/python -m pytest`**, not `.venv-host/bin/pytest`: that console script's shebang is stale and `.venv-host`'s `pydantic_core` wheel is broken (gnu/musl mismatch). Same Python 3.14.7 and package versions. Recorded in `deferred-items.md` by plan 02-01.

**Total deviations:** 1 auto-fixed (Rule 1).
**Impact on plan:** The auto-fix removes a daily misleading warning introduced by this plan's own stage; it adds one repository function and one regression test and relaxes nothing. The interface refinements are simplifications of unspecified or vestigial parameters.

## Issues Encountered

- One unit-test assumption needed correcting: the location-gate test asserted a whole-pair pass for a `None`-location side, but the score gate legitimately lowers the score when the tuple text loses a location. The test now uses a permissive θ to isolate the location gate (and still asserts a real mismatch is refused at any θ).
- Two `ruff` findings (line length, import order) were fixed with `ruff format` / `--fix`; all changed files are `ruff check` clean.
- Full-suite wall-clock varied 26–32s across runs versus a ~17s earlier baseline, with individual lanes equally variable (7s → 21s on identical input). Machine contention from parallel work, not a regression.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-05 inserts the hard-filter stage between the dedup stage and `_finish`; the comment in `run_pipeline` names that insertion point and `filtered_count` was deliberately left untouched.
- Plan 02-06's Merges view and revert have what they need: the audit row, the pre-merge snapshot, the A5 provenance, and `reverted_pairs`/`merged_pairs` as the negative-memory primitives. A revert must set `reverted_at`, and the next run will then skip the pair.
- Plan 02-07 owns the queue-visibility predicate that hides an absorbed twin (a `listing_dupes` row with `reverted_at IS NULL`); this plan deliberately did not add an `is_hidden` column or a delete.
- Known residual: a merge that is *wrong but plausible* (two different roles at one company with near-identical ungraded titles) is still possible. It is fully reversible with a retained snapshot, and the product decision D-25 accepts that residual because a confirmation queue re-introduces the daily-loop cost the project exists to remove.
- Requirement **QUEUE-03** was marked complete — the shared-ID gate reported `1/1 ready`.

---
*Phase: 02-clean-filtered-queryable-queue*
*Completed: 2026-09-16*

## Self-Check: PASSED

- All seven plan files exist on disk (4 modules/edited files + 3 test modules).
- All three commits exist: `1ce92ea`, `731f09d`, `49863f2`; measured count `3` over `plan_head_before=cf1e6f7baf6bc6d0d528c8aea1c573292e61b3ed`.
- Plan-level verification re-run: dedup trio → `25 passed`; `tests/pipeline tests/db` → `58 passed`; `tests/test_config.py` → `8 passed`; full suite → `406 passed, 2 deselected`.
- `ruff check app/ tests/` → `All checks passed!`
- No θ literal under `app/pipeline`; `token_set_ratio` absent from `app/domain/dedup.py`; `ListingDupe(...)` constructed only in `dupe_repo.py`.
