---
phase: 02-clean-filtered-queryable-queue
plan: "05"
subsystem: pipeline
tags: [hard-filter, exclusion-repo, criteria-snapshot, capacity-warnings, run-reason, sqlalchemy, alembic]

# Dependency graph
requires:
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-03's pure `app/domain/filter.evaluate` + `app/domain/criteria.rule_specs_from`/`search_query_from`"
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-04's `run_dedup_stage` insertion point and the `deduped_count` meaning"
  - phase: 02-clean-filtered-queryable-queue
    provides: "migration 0002 — `filter_rules`, `listing_exclusions.criteria_version`, and the four new `runs` columns"
provides:
  - "`app/db/repositories/search_repo.py` — the criteria/rules/listing read side under the A4 union scope"
  - "`app/db/repositories/exclusion_repo.py` — the append-only write side of `listing_exclusions`"
  - "`app/pipeline/filter_stage.py` — a total, deterministic, LLM-free hard-filter stage"
  - "`app/domain/run_reason.py` — the six-value reason enum, `RunCounts`, `compute_empty_reason`, `reason_sentence`"
  - "`runs.criteria_snapshot_json` written before the fetch; `runs.stage_log_json`, `runs.reason`, `runs.reason_counts_json` written on every run"
affects: [02-06, 02-07, 02-08, 02-10]

# Actuals (#2632) — measured, not narrated.
actuals:
  tokens: 25948        # chars/4 of `git diff 4a96591..HEAD` => 103794/4
  tasks: 3
  commits: 3           # MEASURED: git rev-list --count 4a96591..HEAD

tech-stack:
  added: []            # no new dependency — deterministic filtering cost zero new packages
  patterns:
    - "Stage-as-total-function: a stage catches per-record failures, counts them on StageCounts and continues; a malformed rule never empties the queue (PITFALLS P10)"
    - "Repository owns the SQL, the pure layer never sees an ORM row (repository -> domain, never the reverse)"
    - "Persist the decomposition, compute the aggregate: the reason is derived from `reason_counts_json`, the sentence is never the only artifact"
    - "Snapshot-before-fetch: write the immutability contract at the START of a run so a later edit cannot rewrite history"

key-files:
  created:
    - app/db/repositories/search_repo.py
    - app/db/repositories/exclusion_repo.py
    - app/pipeline/filter_stage.py
    - app/domain/run_reason.py
    - tests/pipeline/test_filter_stage.py
    - tests/pipeline/test_criteria_snapshot.py
    - tests/pipeline/test_capability_surface.py
    - tests/db/test_exclusions.py
    - tests/domain/test_run_reason.py
  modified:
    - app/pipeline/run.py

key-decisions:
  - "`all_sources_failed` requires at least one reported status: with an empty status list there is no evidence a source failed, so the reason falls through to `mixed` rather than claiming a failure (P9: zero results must never be ambiguous)."
  - "The reason is persisted on EVERY run, not only when the queue is empty — it is the run's outcome summary and plan 02-10's history page renders it unconditionally."
  - "The capability-warning sentence in `runs.errors_json` is EXTENDED with '(enforced locally as a hard filter after the fetch)' rather than replaced, so Phase-1 assertions on the existing text stay valid while the meaning becomes honest."
  - "`no_sources_enabled` recognises the existing `NO_SOURCES_REASON` condition; no second vocabulary was minted, and the Phase-1 `errors_json` record is unchanged."
  - "The stage log and the capability-warning list are bounded by two documented module constants (`STAGE_LOG_MAX_ENTRIES = 12`, `STAGE_LOG_MAX_ERRORS = 10`) rather than `Settings` knobs: a log-size guard is not a tunable operating limit."
  - "`new_since_watermark` is computed against a read-only watermark; a run never advances the boundary it is measured against (plan 02-07 owns the queue-open advance)."
  - "An unknown (`None`) watermark means every survivor counts as new, so an untouched queue cannot falsely report `nothing_new` on its first run."

patterns-established:
  - "Append-only per-run observation: `listing_exclusions` takes one INSERT per firing rule per run and is never updated, so retuning a rule brings a listing back with no deletion (D-36)."
  - "Two-place warning surfacing: a capability warning is written to `runs.errors_json` (pre-existing shape) AND to `runs.stage_log_json` as a structured `source`/`filter_name`/`reason` triple (D-37 / T-02-19)."
  - "Bounded JSON persistence: every new JSON blob written by the pipeline is capped by a named module constant and coerced to plain values (`_plain`) so it is JSON-serialisable by construction."

requirements-completed: [FILT-01, FILT-02, CRIT-02, RUN-03]

coverage:
  - id: D1
    description: "A stored rule rejects a persisted listing during a run and one row per firing rule is written with its rule identity, kind, evidence, run id and criteria version."
    requirement: FILT-01
    verification:
      - kind: integration
        ref: "tests/pipeline/test_filter_stage.py#test_a_stored_rule_rejects_a_listing_and_the_run_records_why"
        status: pass
      - kind: integration
        ref: "tests/db/test_exclusions.py#test_one_row_per_outcome_with_detail_preserved_verbatim"
        status: pass
    human_judgment: false
  - id: D2
    description: "An absent or unknown value is never a rejection reason (A2/A3) — an unknown salary does not trip a salary_floor rule — and a malformed rule degrades to a recorded skip rather than emptying the queue."
    requirement: FILT-02
    verification:
      - kind: integration
        ref: "tests/pipeline/test_filter_stage.py#test_a_stored_rule_rejects_a_listing_and_the_run_records_why"
        status: pass
      - kind: unit
        ref: "tests/domain/test_filter.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "`runs.criteria_snapshot_json` holds the exact query and rule set the run used; editing the criteria afterwards leaves a completed run's snapshot unchanged."
    requirement: CRIT-02
    verification:
      - kind: integration
        ref: "tests/pipeline/test_criteria_snapshot.py#test_editing_criteria_after_a_run_leaves_that_runs_snapshot_unchanged"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_criteria_snapshot.py#test_the_snapshot_carries_every_enabled_search_and_its_rules"
        status: pass
    human_judgment: false
  - id: D4
    description: "A filter a board cannot honour is reported in two places: the pre-existing `errors_json` warning shape and a `criteria_compile` stage-log entry carrying the structured source/filter_name/reason triple."
    requirement: CRIT-02
    verification:
      - kind: integration
        ref: "tests/pipeline/test_capability_surface.py#test_an_unsupported_salary_floor_is_warned_in_both_places"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_capability_surface.py#test_an_unsupported_remote_filter_is_warned_in_both_places"
        status: pass
      - kind: unit
        ref: "tests/sources/test_capabilities.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every run persists `run.reason` from the fixed six-value precedence order plus `run.reason_counts_json` (adapters_resolved, sources, excluded_by_rule, survivors, duplicates_already_seen, new_since_watermark, watermark, capability_warnings)."
    requirement: RUN-03
    verification:
      - kind: unit
        ref: "tests/domain/test_run_reason.py"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_filter_stage.py#test_the_run_persists_a_reason_and_its_counts_on_every_run"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_filter_stage.py#test_a_run_with_zero_resolved_adapters_is_no_sources_enabled"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_filter_stage.py#test_a_run_whose_every_listing_was_filtered_is_all_filtered"
        status: pass
    human_judgment: false
  - id: D6
    description: "No LLM client is constructed, imported or called on the filter/run-reason path, and a filtered run writes no `llm_calls` row (FILT-01's 'before any LLM call')."
    requirement: FILT-01
    verification:
      - kind: integration
        ref: "tests/pipeline/test_filter_stage.py#test_a_stored_rule_rejects_a_listing_and_the_run_records_why"
        status: pass
      - kind: unit
        ref: "tests/test_import_discipline.py#test_domain_imports_no_io"
        status: pass
    human_judgment: false

# Metrics
duration: 22min
completed: 2026-09-16
status: complete
---

# Phase 02 Plan 05: Deterministic hard filtering, criteria snapshots, and the run's reason

**Deterministic rule-based rejection after dedup and before any model call, with a per-firing-rule exclusion audit row, a criteria snapshot that a later edit cannot rewrite, capability warnings surfaced in two places, and a six-value run reason persisted with the integer counts behind it.**

## Performance

- **Duration:** 22 min (resumed session span; task 1 was committed in a prior session that was aborted)
- **Started:** 2026-09-16T10:02:25Z (task-1 commit; this session resumed on top of it)
- **Completed:** 2026-09-16T10:23:57Z (task-3 commit)
- **Tasks:** 3
- **Files modified:** 10 (`git diff --numstat 4a96591..HEAD`: 10 files, +2518 / -33)

## Accomplishments

- **The filter is real and total.** `run_filter_stage` loads the **union of every enabled search's** rules (A4), maps ORM rows through plan 02-03's pure `rule_specs_from`, calls `evaluate` once per persisted listing, and writes through `exclusion_repo`. It runs after dedup and before `_finish` (`ARCHITECTURE.md` §8.1) and it is best-effort: one bad listing or malformed `params_json` is counted on `StageCounts`, logged, and the run continues — a broken rule can never empty the queue (P10).
- **Every rejection is auditable.** One `listing_exclusions` row per **firing rule** per listing per run, carrying `rule_id`, `rule_kind`, `detail_json`, `run_id` and the owning search's `criteria_version`. Append-only: re-running writes a second row, never an update (D-36). `detail_json` carries terms, field names and counts only — a test asserts neither the description nor any distinctive phrase from it reaches the stored evidence (T-02-17).
- **A completed run cannot be rewritten.** `runs.criteria_snapshot_json` is written **before the fetch** and is never touched by `_finish`. A test edits a search's rules, drives a second run, and asserts the **first** run's snapshot is byte-identical on re-read (CRIT-02 / D-33 / T-02-20).
- **A board's inability to honour a filter is reported twice.** The pre-existing `errors_json` warning survives with its `"status": "warning"` shape and its sentence **extended** (`… (enforced locally as a hard filter after the fetch)`), and the same warning additionally lands in `runs.stage_log_json` under `criteria_compile` as a structured `source`/`filter_name`/`reason` triple (D-37 / SRC-09 / T-02-19).
- **The queue's emptiness is never ambiguous.** `compute_empty_reason` picks the first matching cause from a fixed six-value precedence order; `runs.reason_counts_json` carries the decomposition (`adapters_resolved`, `sources`, `excluded_by_rule`, `survivors`, `duplicates_already_seen`, `new_since_watermark`, `watermark`, `capability_warnings`) and `reason_sentence` renders from it. Persisted on **every** run, not only an empty one.
- **No model call.** No LLM module is imported under `app/pipeline`, and a filtered end-to-end run asserts `llm_calls` stays empty — the cost-control claim is structural and observational.

## Task Commits

Each task was committed atomically:

1. **Task 1 (tracer): End-to-end — a stored rule rejects a listing and the run records why** - `c6bff50` (feat) — *completed and committed in the prior (aborted) session; verified present and not redone.*
2. **Task 2: Reproducibility — the criteria snapshot and the capability-warning surface** - `bd90e4d` (feat)
3. **Task 3: The run's reason — a deterministic enum with the counts behind it** - `6b9e56b` (feat)

**Plan metadata:** `_pending_` (docs: complete 02-05 plan)

_Note: `commits: 3` and `plan_head_before: 4a965917d6adbc4cc500514e6adda4ba9f76d8b4` are measured from the on-disk per-plan ledger at `.git/gsd-plan-head-before-02-05`, not narrated (#3968)._

## Files Created/Modified

- `app/db/repositories/search_repo.py` — the criteria/rules/listing read side. `enabled_searches`, `rules_for_searches` (ordered `(search_id, position, id)`), `active_listings` (the `last_seen_at >= run.started_at` Phase-1 window, skipping absorbed twins), plus frozen `SearchRecord`/`RuleRecord`/`ListingRecord`; the A4 union semantics are stated in the module docstring.
- `app/db/repositories/exclusion_repo.py` — `record_exclusions` (one row per outcome, wrapped in a SAVEPOINT, never updates), `excluded_counts_for_run` (deterministic `GROUP BY rule_id`), `rule_counts_for_listings` (for plan 02-07's excluded toggle), `exclusions_for_run`. Contains the only `ListingExclusion(` constructor in `app/`.
- `app/pipeline/filter_stage.py` — the total hard-filter stage; `bump("candidates"/"survivors"/"excluded_listings"/"exclusions")`, `rules_skipped` so a dropped rule is visible rather than assumed applied.
- `app/domain/run_reason.py` — pure, stdlib-only. `REASONS` (six values in precedence order), frozen `RunCounts`, `compute_empty_reason`, `reason_sentence`; all four in `__all__`.
- `app/pipeline/run.py` — the filter-stage invocation after dedup and before `_finish`; `criteria_snapshot_json`; the bounded `stage_log_json` (`STAGE_LOG_MAX_ENTRIES`/`STAGE_LOG_MAX_ERRORS`); the `criteria_compile` entry; `filtered_count`; and `reason`/`reason_counts_json`. `_fetch_one` now returns a 3-tuple `(FetchResult, error-shaped warnings, structured warning triples)`.
- `tests/pipeline/test_filter_stage.py` — the tracer's end-to-end lane (exclusion row fields, unknown-salary pass, `filtered_count == 1`, empty `llm_calls`, two-runs-two-rows) plus three run-boundary reason tests.
- `tests/pipeline/test_criteria_snapshot.py` — snapshot keyed by search id with versions and rule kinds; JSON round-trip; and the post-edit immutability property.
- `tests/pipeline/test_capability_surface.py` — registered fake adapters with `supports_salary_min_filter=False` / `supports_remote_flag=False`; both warning surfaces asserted, plus the empty-warning-list case.
- `tests/db/test_exclusions.py` — the exclusion table's DB invariants: verbatim `detail_json`, exact deterministic per-rule counts, caller-supplied `criteria_version`, append-only per run, and the no-prose boundary.
- `tests/domain/test_run_reason.py` — one test per branch, five precedence/adjacency tests, the two empty-corpus boundaries, stability, the no-float precision contract, and the derived-sentence properties.

## Decisions Made

- **`all_sources_failed` requires evidence.** The plan's precedence line 2 ("every source status != 'ok'") is vacuously true over an empty status list. I require at least one reported status and otherwise fall through, so a run with no status information reports `mixed` rather than claiming a failure it cannot support. Documented in the `compute_empty_reason` docstring and pinned by `test_an_empty_status_list_with_resolved_adapters_does_not_raise_or_claim_failure`. (In production this case is unreachable: `_fetch_one` is total, so every resolved adapter contributes exactly one status.)
- **The reason is unconditional.** Written on every run, not only a thin one, because it is the run's outcome summary and plan 02-10's history page renders it for every run.
- **The warning sentence was extended, not replaced.** `"filter not applied: X — Y"` keeps its prefix and gains `" (enforced locally as a hard filter after the fetch)"`, so the Phase-1 assertions that match the existing text stay valid while the meaning becomes honest (the local hard filter now enforces the same rule).
- **Bounds are module constants, not `Settings`.** `STAGE_LOG_MAX_ENTRIES = 12` / `STAGE_LOG_MAX_ERRORS = 10` are documented as a log-size guard. They are deliberately *not* `Settings` knobs (the settings absence-scan in `tests/test_config.py` continues to pass), and they collide with no distinctive threshold value.
- **The watermark is read-only and `None` means "never viewed".** A run never advances the boundary it is measured against (plan 02-07 owns that), and an absent watermark makes every survivor count as new — otherwise the first run of an untouched queue would report `nothing_new` and hide the listings it exists to show.
- **`no_sources_enabled` recognises `NO_SOURCES_REASON`.** Same condition, one vocabulary: the Phase-1 `errors_json` record is unchanged and a test asserts both it and the enum value are produced by the same zero-adapter run.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The task-3 run-boundary assertion had no designated file, so it landed in the planned pipeline lane**
- **Found during:** Task 3 (the run's reason)
- **Issue:** The acceptance criteria require "`run.reason` and `run.reason_counts_json` on every run, and `no_sources_enabled` … (asserted by a test that drives that case)". Task 3's `<files>` names only `tests/domain/test_run_reason.py`, which the plan explicitly designs as a **pure unit lane, no DB** — it cannot drive `run_pipeline`. The plan's `files_modified` frontmatter already declares `tests/pipeline/test_filter_stage.py`, and the phase `<verification>` runs `tests/pipeline`.
- **Fix:** Added three run-boundary tests to the declared pipeline lane (the same fixtures `run_pipeline` is already driven with there): a zero-adapter run is `no_sources_enabled` with `adapters_resolved == 0` and the Phase-1 `NO_SOURCES_REASON` record still present; a healthy run carries a reason in `REASONS` and all required count keys, JSON round-trip included; and a run whose every listing was filtered is `all_filtered`. The domain lane stayed pure.
- **Files modified:** `tests/pipeline/test_filter_stage.py`, `app/pipeline/run.py`, `app/domain/run_reason.py`
- **Verification:** `.venv/bin/python -m pytest -q tests/pipeline/test_filter_stage.py` → 6 passed; full suite 450 passed.
- **Committed in:** `6b9e56b` (part of task 3)

### Deviations of record (no code change)

**2. [Environment] Every plan `<verify>` / `<verification>` command was run as `.venv/bin/python -m pytest …` instead of `.venv-host/bin/pytest …`**
- **Found during:** all three tasks (plan-level verification)
- **Issue:** `.venv-host/bin/pytest` is unusable in this sandbox — its shebang is a build-time absolute path that does not exist here, and its compiled wheels are `x86_64-linux-gnu` while the interpreter expects a musl `EXT_SUFFIX`, so `import pydantic_core` fails.
- **Fix:** none — the sibling `.venv/` (same Python 3.14.7, same package versions) was used; every asserted command has an exact equivalent.
- **Verification:** the full suite is green under `.venv`.
- **Recorded in:** `.planning/phases/02-clean-filtered-queryable-queue/deferred-items.md` (from plan 02-01) and repeated here for this plan.

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking), 1 environment substitution of record.
**Impact on plan:** No scope creep. The added tests are test-only and exercise behaviour the plan's acceptance criteria already required. No production file outside the plan's declared surface was touched.

## Issues Encountered

- **The plan was resumed after an aborted session.** Task 1 (`c6bff50`) was already committed; its files were verified present and its lane re-run, and it was **not** redone. Task 2's `app/pipeline/run.py` changes were found uncommitted in the tree; they were reviewed against task 2's `<action>`, found correct (snapshot before the fetch, not rewritten in `_finish`; bounded stage log; extended warning sentence), and the two missing test modules were created before committing.
- **`ruff` E501 on three long lines** in the two new test modules — fixed by wrapping (no pre-commit hooks are installed in this repo, so this was a manual check). `ruff check app tests` now reports **All checks passed!**.
- No stubs, no skipped tests, and no unrun `<verify>` blocks: no new entries were added to `.planning/WINDOWS.md`.
- The untracked `.gsd/` and `.planning/milestone.lock` paths present in the tree pre-date this plan and are outside its scope; they were left untouched.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Ready for plan 02-06 (Merges view) and 02-07 (queue visibility).** `rule_counts_for_listings` and `exclusions_for_run` already expose the per-listing firing rules that 02-07's `Show excluded` toggle renders, and `queue_state.last_queue_view_at` is read but never advanced, exactly as 02-07 expects to take over.
- **Ready for plan 02-08 (criteria CRUD).** The read side (`search_repo`) and the `criteria_snapshot_json` shape are in place; this plan only *reads* criteria and rules, and deliberately does not bump `searches.version`.
- **Ready for plan 02-10 (`/runs` history).** `runs.reason` and `runs.reason_counts_json` are written on every run and `reason_sentence` renders a sentence from the counts; the page that displays them is separate.
- **Carry-forward for the verifier:** `deduped_count`, `filtered_count`, `fetched_count` and the terminal-status logic are unchanged from 02-04 / task 1 — `deduped_count` still counts rows absorbed by a merge, and `filtered_count` now has its writer.
- **Known residual risk (accepted, unchanged):** the filter is only as good as the user's rules; a mis-typed `exclude_keyword` term can remove a whole class of listings. Mitigated by append-only per-run observations (retuning brings listings back), the per-rule counts, and `all_filtered` being distinguishable from every other empty-queue cause.

---
*Phase: 02-clean-filtered-queryable-queue*
*Completed: 2026-09-16*

## Self-Check: PASSED

- All 9 created/modified artifacts and `02-05-SUMMARY.md` verified present on disk.
- All 3 plan commits verified in `git log --all`: `c6bff50`, `bd90e4d`, `6b9e56b`.
- Full suite green: `450 passed, 2 deselected`.
- No missing items.
