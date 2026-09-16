---
phase: 02-clean-filtered-queryable-queue
verified: 2026-09-16T13:22:11Z
status: human_needed
score: 54/54 must-haves verified
re_verification: false
covered_files:
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-01-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-01-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-02-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-02-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-03-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-03-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-04-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-04-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-05-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-05-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-06-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-06-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-07-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-07-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-08-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-08-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-09-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-09-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-10-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-10-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-REVIEW.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-VALIDATION.md
  - alembic/versions/0002_queue_filter_and_run_reason.py
  - app/api/events.py
  - app/api/runs.py
  - app/api/searches.py
  - app/config.py
  - app/db/models.py
  - app/db/repositories/dupe_repo.py
  - app/db/repositories/event_repo.py
  - app/db/repositories/exclusion_repo.py
  - app/db/repositories/queue_repo.py
  - app/db/repositories/run_repo.py
  - app/db/repositories/search_repo.py
  - app/db/repositories/state_repo.py
  - app/domain/criteria.py
  - app/domain/dedup.py
  - app/domain/filter.py
  - app/domain/run_reason.py
  - app/domain/sanitize.py
  - app/domain/search_query.py
  - app/main.py
  - app/pipeline/dedup_stage.py
  - app/pipeline/filter_stage.py
  - app/pipeline/run.py
  - app/web/routes.py
  - app/web/templates/html/_listing_row.html
  - app/web/templates/html/criteria.html
  - app/web/templates/html/merges.html
  - app/web/templates/html/queue.html
  - app/web/templates/html/queue_list.html
  - app/web/templates/html/runs.html
  - pyproject.toml
  - requirements.txt
  - tests/api/test_criteria_capabilities.py
  - tests/api/test_listing_events.py
  - tests/api/test_merges_view.py
  - tests/api/test_queue_excluded.py
  - tests/api/test_queue_search.py
  - tests/api/test_queue_signals.py
  - tests/api/test_run_history.py
  - tests/api/test_run_reason.py
  - tests/api/test_searches_crud.py
  - tests/db/test_dupes.py
  - tests/db/test_exclusions.py
  - tests/db/test_listing_events.py
  - tests/db/test_migration_contract.py
  - tests/db/test_no_pii_columns.py
  - tests/db/test_orm_drift.py
  - tests/db/test_queue_state.py
  - tests/db/test_search_repo_writes.py
  - tests/db/test_skeleton_boot.py
  - tests/domain/test_criteria.py
  - tests/domain/test_dedup.py
  - tests/domain/test_filter.py
  - tests/domain/test_injection_patterns.py
  - tests/domain/test_run_reason.py
  - tests/domain/test_search_query.py
  - tests/pipeline/test_capability_surface.py
  - tests/pipeline/test_criteria_snapshot.py
  - tests/pipeline/test_dedup_merge.py
  - tests/pipeline/test_dedup_revert.py
  - tests/pipeline/test_filter_stage.py
  - tests/pipeline/test_ingest_e2e.py
  - tests/pipeline/test_single_search_run.py
  - tests/test_config.py
  - tests/test_dependency_pins.py
covered_digest: "v1:sha256:5906fc558643d77d563d28584154387fd6d3c51346a0233cca871ccdf5f48a2d"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Tune the dedup threshold θ against the first real corpus"
    expected: "Run a real pipeline run against live LinkedIn/Indeed data, inspect the listing_dupes pairs and the merge rate on /merges, and record the chosen Settings.dedup_fuzzy_threshold (currently 88) and its justification in docs/."
    why_human: "No real corpus exists pre-run; θ is deliberately shipped as a setting with a tuning procedure (02-VALIDATION.md Manual-Only; ROADMAP Phase-2 Notes; D-31). Code and tests prove θ is a settings read with no literal, not that 88 is the right value."
  - test: "Merge-rate band sanity check after a real run"
    expected: "After a real run, compare the observed merge rate on /merges against the 10–15% band from research and record why the chosen θ is or is not adjusted."
    why_human: "The band comes from a different market/query shape; QUEUE-09 asks for the rate to be visible and windowed, which is machine-verified, but whether the observed rate is sane needs real data."
  - test: "Compose smoke of the running stack"
    expected: "`docker compose up` and browse the queue; confirm the migration to 0002 applies, the queue renders, and the run trigger works end to end."
    why_human: "02-VALIDATION.md lists this as a WINDOWS.md carry-over (open item #1); it needs Docker/network and a human browsing."
  - test: "Confirm the pinned rapidfuzz dependency was human-approved"
    expected: "The approval (version 3.14.6, source repo, pre-compiled wheel, no arbitrary build step) is recorded in 02-02-SUMMARY.md 'Authentication Gates'."
    why_human: "An out-of-band human sign-off cannot be machine-verified; recorded as discharged in-phase on 2026-09-16, re-listed for the end-of-phase human checkpoint."
  - test: "Judge whether the excluded-listing chip satisfies 'which rule fired and why'"
    expected: "Under `Show excluded`, each rejected listing shows a chip `rule.kind (count)` (e.g. `exclude_keyword (2)`). Confirm this is sufficient, or require the firing rule id and the matched `detail_json` term (e.g. `crypto`) to be surfaced."
    why_human: "The rule id and the persisted `detail_json` (the matched term/field) have no UI consumer; the chip names only the rule kind plus a per-rule count. This is a product-sufficiency judgment against SC2/FILT-03 wording, not a machine-definable pass/fail."
gaps: []
advisory:
  - finding: "listing_exclusions.detail_json (the matched term/field/count behind a rejection) is persisted but has no UI consumer; the queue chip renders only rule.kind + a per-rule count."
    category: architectural
    reason: "FILT-02 ('records which rule fired and why') is satisfied — the detail is stored and tested — but the plan-02-07 task text asked the chip to name the 'rule kind and the rule id', and the id is not rendered. `exclusion_repo.ExclusionRecord`/`exclusions_for_run` remain uncalled (02-REVIEW.md IN-02)."
    evidence_status: "codebase observation (grep: detail_json referenced only in models/exclusion_repo); not backed by a failing test"
---

# Phase 2: Clean, Filtered, Queryable Queue — Verification Report

**Phase Goal:** A deduplicated, deterministically filtered, searchable queue the user trusts — with every rejection explained and every run observable.
**Verified:** 2026-09-16T13:22:11Z
**Status:** human_needed
**Re-verification:** No — initial verification
**Mode:** mvp (the roadmap goal is a capability statement; the five roadmap Success Criteria below are the verified contract. It is not written as a User Story.)

## Method

Independent, goal-backward verification against the codebase — not against the ten SUMMARYs.
Every claim below was re-derived from the source and re-executed:

- Full suite: `.venv/bin/python -m pytest -q` → **591 passed, 2 deselected in 96.10s**.
- Targeted phase lanes re-run and cited per truth (five grouped invocations, all green).
- Independent in-process spot checks of the pure decision layer (`build_match_expression`,
  `compute_empty_reason`, `grades_conflict`) via a throwaway `.venv/bin/python -c` check.
- All seven post-review fix commits inspected (`52e86f3`, `74bd786`, `78baf41`, `5794465`,
  `7d1b511`, `8fa4883`, `348fa69`) and their fixes confirmed present in the code.
- `ruff check app tests` → **All checks passed!**
- Decision-coverage gate: **23/23 CONTEXT.md decisions honored** (non-blocking).

## Roadmap Success Criteria

| # | Success Criterion | Status | Evidence |
| - | ----------------- | ------ | -------- |
| 1 | Deduplicated queue; same job on two sources appears once, with merge rate and rows visible, incorrect merge revertible | ✓ VERIFIED | `app/pipeline/dedup_stage.py`, `app/domain/dedup.py`, `dupe_repo.apply_merge/revert_merge/merge_rate/list_merges`, `merges.html`; `tests/pipeline/test_dedup_merge.py` (4), `tests/api/test_merges_view.py` (6), `tests/pipeline/test_dedup_revert.py`, `tests/api/test_queue_search.py::test_queue_hides_absorbed_twin_until_revert` — all pass |
| 2 | For any excluded listing, which rule fired and why is visible | ✓ VERIFIED (with advisory) | Out of default view, dimmed under `Show excluded`, chip naming the firing rule kind + per-rule count: `queue_repo._enrich` (app/db/repositories/queue_repo.py:427-435), `_listing_row.html:42-44`, `tests/api/test_queue_excluded.py` (4). "Why" is recorded in `listing_exclusions.detail_json` (FILT-02, tested) but the matched term is not rendered — see Advisory + Human Verification #5 |
| 3 | Create/edit/enable/disable/delete named criteria + tune filter rules from the UI without a code change; runs reproducible against a criteria version | ✓ VERIFIED | `app/api/searches.py` (CRUD/toggle/delete/rule routes), `app/db/repositories/search_repo.py`, `criteria.html` (per-kind forms, no raw-JSON control), `runs.criteria_snapshot_json` written before the fetch (`app/pipeline/run.py:619`); `tests/api/test_searches_crud.py` (19), `tests/db/test_search_repo_writes.py` (10), `tests/pipeline/test_criteria_snapshot.py`, `tests/api/test_criteria_capabilities.py`, `tests/pipeline/test_single_search_run.py` — all pass |
| 4 | Full-text searchable queue; save/hide as append-only events; new-since-last-visit and stale distinguishable | ✓ VERIFIED | `app/domain/search_query.py`, `queue_repo` (bound `MATCH` only), `event_repo` (append-only + projection), `state_repo` (watermark); `tests/domain/test_search_query.py` (12), `tests/api/test_queue_search.py`, `tests/api/test_queue_signals.py` (8), `tests/db/test_listing_events.py` (19), `tests/api/test_listing_events.py` (11) — all pass |
| 5 | Run history: each run records what it did, what it found, and — when the queue is empty — why | ✓ VERIFIED | `app/db/repositories/run_repo.py`, `app/domain/run_reason.py` (six-value precedence + counts), `runs.html`, queue last-run strip via `render_run_fragment`; `tests/api/test_run_history.py` (10), `tests/api/test_run_reason.py` (6), `tests/domain/test_run_reason.py` — all pass |

## Observable Truths (plan must_haves, 54 total)

Evidence key: **lane** = the re-executed pytest invocation that contains the named test.
All lanes below passed on 2026-09-16 (see Behavioral Spot-Checks).

### 02-01 — Schema spine (4/4)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `alembic upgrade head` on a fresh DB records exactly one revision `0002` and one head | ✓ VERIFIED | `tests/db/test_migration_contract.py:270,281` (lane 5: 63 passed); migration file present, 89 files fingerprinted |
| 2 | Migrated DB has `filter_rules`, `queue_state`, four new `runs` columns, `listing_exclusions.criteria_version`, `listing_dupes` unique index (via PRAGMA/sqlite_master) | ✓ VERIFIED | `tests/db/test_migration_contract.py` items 10–13 + `tests/db/test_skeleton_boot.py` (lane 5) |
| 3 | Every new JSON column is deliberately allow-listed; no new PII-shaped column | ✓ VERIFIED | `tests/db/test_no_pii_columns.py` (lane 5) |
| 4 | `dedup_fuzzy_threshold`, `dedup_posted_window_days`, `stale_after_days`, `queue_page_size` readable from `Settings`; no distinctive literal under `app/pipeline` | ✓ VERIFIED | `app/config.py:81-89`; `tests/test_config.py` (lane 3: 48 passed) |

### 02-02 — rapidfuzz dependency (3/3)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `rapidfuzz==3.14.6` installed in `.venv-host` and importable; both fuzz functions callable | ✓ VERIFIED | Directly re-run: `.venv-host/bin/python -c "import rapidfuzz"` → `rapidfuzz 3.14.6`; `.venv` likewise; `tests/test_dependency_pins.py` |
| 2 | Exact pin declared once in `pyproject.toml` `[project].dependencies`, mirrored verbatim in `requirements.txt`; no floating range | ✓ VERIFIED | `pyproject.toml:28`, `requirements.txt:18`; `tests/test_dependency_pins.py` |
| 3 | A human explicitly confirmed the pinned version/source/build before install | ✓ VERIFIED (human-recorded) | 02-02-SUMMARY.md "Authentication Gates" records `approved`; not re-verifiable → Human Verification #4 |

### 02-03 — Pure decision layer (6/6)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `evaluate(rules, facts)` returns only firing rules ordered by `(position, rule_id)`; a malformed rule degrades to skipped | ✓ VERIFIED | `app/domain/filter.py:402`; `tests/domain/test_filter.py` (27) — lane 2 (61 passed) |
| 2 | An absent value is never a rejection reason (salary/remote/seniority pass when unknown) | ✓ VERIFIED | `tests/domain/test_filter.py::test_unknown_values_are_never_a_rejection_reason` |
| 3 | An unknown rule `kind` is skipped, not evaluated as pass-through | ✓ VERIFIED | `tests/domain/test_filter.py::test_an_unknown_kind_is_skipped` |
| 4 | Every `RuleOutcome.detail` carries terms/field names/counts only — no description excerpt/removed value | ✓ VERIFIED | `tests/domain/test_filter.py::test_detail_keys_are_exact_per_kind`, `::test_exclude_keyword_never_persists_the_field_text` |
| 5 | Criteria mapping assembles a `SearchQuery` and a rule list ordered by `(search_id, position)` | ✓ VERIFIED | `app/domain/criteria.py`; `tests/domain/test_criteria.py` (13) |
| 6 | The injection catalogue flags/counts without altering text | ✓ VERIFIED | `app/domain/sanitize.py`; `tests/domain/test_injection_patterns.py` (17) |

### 02-04 — Tier-2 dedup/merge (6/6)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Two sources → one visible listing + one absorbed twin + exactly one `listing_dupes` row (method, score, merge time) | ✓ VERIFIED | `tests/pipeline/test_dedup_merge.py::test_two_sources_one_job_merges_once_with_an_audit_row` — asserts 2 listings, 1 dupe, salary filled, `deduped_count==1` (lane 1: 37 passed) |
| 2 | A non-null survivor field is never overwritten; empty string counts as blank | ✓ VERIFIED | `tests/db/test_dupes.py::test_merge_fills_blanks_and_never_overwrites_a_non_null`, `::test_an_empty_string_counts_as_blank_but_a_real_value_does_not` |
| 3 | `snapshot_json` holds the survivor's pre-merge values for exactly the fields written | ✓ VERIFIED | `tests/db/test_dupes.py::test_snapshot_records_exactly_the_written_fields_and_their_prior_values` |
| 4 | A pair with a reverted `listing_dupes` row in either orientation is skipped before scoring | ✓ VERIFIED | `tests/db/test_dupes.py::test_reverted_pairs_is_empty_then_returns_both_orientations`; `dedup_stage.py:112-124` |
| 5 | A grade-carrying title never merges with the same title without the grade | ✓ VERIFIED | `tests/domain/test_dedup.py::test_senior_versus_ungraded_never_merges`, `::test_two_different_grades_never_merge` |
| 6 | `runs.deduped_count` equals merges written, not created count | ✓ VERIFIED | `tests/pipeline/test_dedup_merge.py` merge + zero cases |

### 02-05 — Hard filtering, snapshot, run reason (6/6)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Every rejected listing gets one `listing_exclusions` row per firing rule with `rule_id`,`rule_kind`,`detail_json`,`run_id`,`criteria_version` | ✓ VERIFIED | `app/pipeline/filter_stage.py:119-133` (per-rule version fix `78baf41`), `exclusion_repo`; `tests/db/test_exclusions.py`, `tests/pipeline/test_filter_stage.py` (lane 2) |
| 2 | Filter stage runs after dedup, before `_finish`; no LLM client constructed/imported/called | ✓ VERIFIED | `app/pipeline/run.py:666-700`; grep confirms no `llm`/`opencode` import under `app/pipeline`; `tests/pipeline/test_filter_stage.py` asserts empty `llm_calls` |
| 3 | `runs.criteria_snapshot_json` holds the exact query/rules used; a criteria edit cannot rewrite a past run | ✓ VERIFIED | `app/pipeline/run.py:619`; `tests/pipeline/test_criteria_snapshot.py::test_editing_criteria_after_a_run_leaves_that_runs_snapshot_unchanged` |
| 4 | An unsupported filter appears in `runs.stage_log_json` (criteria_compile) **and** `runs.errors_json` | ✓ VERIFIED | `tests/pipeline/test_capability_surface.py::test_an_unsupported_salary_floor_is_warned_in_both_places` (+ remote case) |
| 5 | `runs.reason` ∈ six-value enum by documented precedence, plus `reason_counts_json` | ✓ VERIFIED | `app/domain/run_reason.py:34-41,77-125`; `tests/domain/test_run_reason.py`; independent precedence spot-check passed |
| 6 | One malformed rule is skipped and recorded; it neither empties the queue nor aborts the run | ✓ VERIFIED | `filter_stage.py:88-89`, `tests/pipeline/test_filter_stage.py` |

### 02-06 — Merge audit + revert (4/4)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Merges view lists every `listing_dupes` row with both sides' own fields, method, score, time, snapshot | ✓ VERIFIED | `dupe_repo.list_merges`; `merges.html`; `tests/api/test_merges_view.py::test_merges_page_lists_the_rate_its_window_and_the_rows_behind_it` (lane 1) |
| 2 | Merge rate visible as merges over fetched **for a stated window**, rows reachable on the same page | ✓ VERIFIED | `dupe_repo.merge_rate` (windowed; fix `348fa69`); `tests/api/test_merges_view.py::test_merge_rate_windows_both_operands_to_the_latest_run` (2-run regression, 33% not 67%) |
| 3 | Revert restores snapshot fields + marks `reverted_at`/`reverted_by`; twin reappears with no un-hide step | ✓ VERIFIED | `dupe_repo.revert_merge` (ORM row, no delete); `tests/api/test_queue_search.py::test_queue_hides_absorbed_twin_until_revert` |
| 4 | After a revert, a subsequent run does not re-merge the pair | ✓ VERIFIED | `tests/pipeline/test_dedup_revert.py::test_a_reverted_merge_is_durable_and_the_pair_stays_separate` |

### 02-07 — Searchable queue, signals, excluded toggle (7/7)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Hostile query text (apostrophe, hyphen, `OR`, `*`, `NEAR(`, trailing `AND`, unbalanced quote) does not raise/500 | ✓ VERIFIED | `app/domain/search_query.py`; `tests/domain/test_search_query.py::test_every_hostile_input_becomes_an_expression_the_real_parser_accepts` + `::test_the_raw_inputs_really_do_raise_untransformed` (anti-vacuous); `tests/api/test_queue_search.py::test_an_apostrophe_query_returns_200_not_500` (lane 4: 70 passed) |
| 2 | Every FTS order ends with a unique tie-break; identical requests return identical order | ✓ VERIFIED | `queue_repo.py:329`; `tests/api/test_queue_search.py::test_identical_search_requests_return_an_identical_row_order` |
| 3 | With no query, Phase-1 order `first_seen_at desc, id desc` and no `listing_fts` join | ✓ VERIFIED | `queue_repo.py:336-344`; `tests/api/test_queue_search.py::test_no_query_keeps_the_phase_one_order` |
| 4 | Listings after `queue_state.last_queue_view_at` (or all when NULL) marked new; `Mark all as seen` advances | ✓ VERIFIED | `state_repo`; `tests/api/test_queue_signals.py::test_listings_after_the_watermark_are_new_and_before_it_are_not`, `::test_mark_all_as_seen_clears_the_badges_and_keeps_the_rows` |
| 5 | Stale when `last_seen_at` older than `stale_after_days` or `is_active` false; new and stale can co-occur | ✓ VERIFIED | `queue_repo._row_flags`; `tests/api/test_queue_signals.py::test_the_stale_boundary_is_n_minus_one_n_and_n_plus_one`, `::test_a_listing_can_be_both_new_and_stale` |
| 6 | Excluded listings out of default view, dimmed under `Show excluded`, chip + per-rule count | ✓ VERIFIED | `queue_repo.py:427-435`, `_listing_row.html:42-44`; `tests/api/test_queue_excluded.py` (4) |
| 7 | Listing with un-reverted merges shows the merge badge; absorbed twin absent until reverted | ✓ VERIFIED | `tests/api/test_queue_search.py::test_queue_hides_absorbed_twin_until_revert` (criterion 1 machine-decided) |

### 02-08 — Criteria CRUD (7/7)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Create a named search (keywords/location/remote/salary/seniority + rules) persisted with `version == 1` | ✓ VERIFIED | `search_repo.create_search`; `tests/api/test_searches_crud.py::test_post_searches_persists_a_version_one_enabled_search` (lane 3) |
| 2 | Editing criteria/rules bumps `searches.version` by exactly 1; a completed run's snapshot is not rewritten | ✓ VERIFIED | `tests/db/test_search_repo_writes.py`, `tests/pipeline/test_criteria_snapshot.py` |
| 3 | A search can be disabled/re-enabled without deletion; a disabled search contributes no rules | ✓ VERIFIED | `tests/api/test_searches_crud.py::test_toggle`, `tests/db/test_search_repo_writes.py::test_enable_disable_does_not_bump_the_version` |
| 4 | Deleting a search removes its rules and leaves no orphan `filter_rules` row | ✓ VERIFIED | `tests/db/test_search_repo_writes.py::test_delete_search_removes_it_and_all_its_rules_only` |
| 5 | Every rule editor is a purpose-built per-kind form; no raw-JSON editor; no template evaluates filter semantics | ✓ VERIFIED | `criteria.html` (six typed field groups; textareas are per-kind term lists, no `params_json` control) |
| 6 | A filter a board cannot honour is reported on the criteria page before any run, naming board + filter | ✓ VERIFIED | `tests/api/test_criteria_capabilities.py::test_an_unsupported_filter_is_reported_per_board` (+ registry-failure degrade) |
| 7 | A single search can be run on its own without changing the one-tap main trigger | ✓ VERIFIED | `tests/pipeline/test_single_search_run.py` (scoping + union unchanged + 202 run row) |

### 02-09 — Save/hide append-only events (6/6)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Save appends one `save`; unsave appends `unsave`; state projected from the latest event, never a column | ✓ VERIFIED | `event_repo._fold_events`; `tests/api/test_listing_events.py::test_posting_save_appends_one_event_and_the_row_reads_saved` (lane 4) |
| 2 | UPDATE/DELETE on `listing_events` aborts with the Phase-1 append-only trigger | ✓ VERIFIED | `tests/db/test_listing_events.py::test_the_database_aborts_an_update_and_a_delete_of_an_event`, `::test_the_orm_cannot_update_or_delete_an_event_either` |
| 3 | A hidden listing leaves the default queue, reachable via `Hidden` filter with one-tap undo | ✓ VERIFIED | `tests/api/test_listing_events.py::test_hiding_removes_the_listing_from_the_queue_and_the_control_becomes_undo` |
| 4 | A saved listing appears under `Saved` and carries a star | ✓ VERIFIED | `tests/api/test_listing_events.py::test_posting_save_appends_one_event_and_the_row_reads_saved`; `_listing_row.html:30` |
| 5 | Toggling twice appends two rows and returns projected state; no event updated/deleted | ✓ VERIFIED | `tests/db/test_listing_events.py::test_save_then_unsave_projects_unsaved` |
| 6 | The page projection is one query, not one per row | ✓ VERIFIED | `tests/db/test_listing_events.py::test_state_for_a_whole_page_is_one_query` |

### 02-10 — Run history (5/5)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `GET /runs` lists one row per run, newest first, with times/trigger/duration/per-source counts/dedup/filter/errors | ✓ VERIFIED | `run_repo.list_runs`; `tests/api/test_run_history.py::test_runs_render_newest_first_and_stably` (lane 5) |
| 2 | Each run row shows the persisted reason; expansion reveals counts + bounded raw stage log | ✓ VERIFIED | `tests/api/test_run_history.py::test_the_detail_fragment_carries_the_stage_log_and_the_per_rule_counts` |
| 3 | Queue page carries a compact last-run strip linking to `/runs`, rendered through the existing run-fragment renderer | ✓ VERIFIED | `app/web/routes.py:142-174` (render inside the never-raise guard — fix `8fa4883`); `queue.html:25-37`; `tests/api/test_run_reason.py::test_the_strip_links_to_the_run_history` |
| 4 | An unfinished run renders in-flight, never as completed with empty duration | ✓ VERIFIED | `run_repo._duration` returns `None`; `tests/api/test_run_history.py::test_an_unfinished_run_renders_in_flight_with_an_em_dash` |
| 5 | The history surface is read-only — no exposed route mutates a run | ✓ VERIFIED | `app/api/runs.py` GET-only history routes; `tests/api/test_run_history.py::test_two_identical_requests_return_identical_bodies` |

**Score:** 54/54 truths verified (0 present-but-behavior-unverified).

## Required Artifacts (Level 1–2: exist + substantive)

All 66 changed non-planning files exist and are substantive (no stubs). Grouped:

| Artifact group | Status | Details |
| -------------- | ------ | ------- |
| Migration + ORM + config | ✓ VERIFIED | `alembic/versions/0002_queue_filter_and_run_reason.py`, `app/db/models.py`, `app/config.py` |
| Pure domain layer | ✓ VERIFIED | `app/domain/{filter,criteria,sanitize,dedup,run_reason,search_query}.py` — real logic, no placeholders; `tests/test_import_discipline.py` keeps them I/O-free |
| Repositories | ✓ VERIFIED | `dupe_repo`, `event_repo`, `exclusion_repo`, `queue_repo`, `run_repo`, `search_repo`, `state_repo` — all real SQL; `queue_repo` holds the only `MATCH` (bound parameter) |
| Pipeline stages | ✓ VERIFIED | `dedup_stage.py`, `filter_stage.py`, `run.py` (snapshot → dedup → filter → reason → finish) |
| API routes | ✓ VERIFIED | `app/api/{searches,events,runs}.py`, `app/web/routes.py` — all registered in `app/main.py:56-60` |
| Templates | ✓ VERIFIED | `queue.html`, `queue_list.html`, `_listing_row.html`, `criteria.html` (364 lines), `merges.html`, `runs.html` — all substantive and escaping-safe (`tests/test_no_cdn.py`, no `\|safe`) |
| Tests | ✓ VERIFIED | 65 test modules included in the fingerprint; every phase lane green |

## Key Link Verification (Level 3: wired)

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `app/main.py` | searches/events/runs/web routers | `include_router` | ✓ WIRED | `app/main.py:56-60` |
| `run_pipeline` | `run_dedup_stage` → `run_filter_stage` → `_finish` | sequential calls | ✓ WIRED | `app/pipeline/run.py:666-740` |
| `filter_stage` | `criteria.rule_specs_from` → `filter.evaluate` → `exclusion_repo.record_exclusions` | repository→domain→repository | ✓ WIRED | `filter_stage.py:82,100,126` |
| `queue_repo.read_queue` | `event_repo.hidden_predicate` / `saved_predicate` | derived predicates | ✓ WIRED | `queue_repo.py:311-314`; one rule, two expressions (`event_repo.py:236-272`) |
| `queue_repo.read_queue` | `dupe_repo.merge_summary_for_listings`, `exclusion_repo.rule_counts_for_listings` | enrichment | ✓ WIRED | `queue_repo.py:403,414` — no re-implementation |
| `revert_merge` route | `dupe_repo.revert_merge` → queue visibility predicate | `reverted_at` flag | ✓ WIRED | `app/api/runs.py:241`; `queue_repo._not_absorbed_twin` |
| `queue` route | `render_run_fragment` (one run renderer) | `_last_run_strip` | ✓ WIRED | `app/web/routes.py:170`; `RunFragmentSource` Protocol (`app/api/runs.py:68-77`) |
| `POST /listings/{id}/events` | `event_repo.append_event` → `queue_repo.read_row` | same row partial | ✓ WIRED | `app/api/events.py:114,127-155` |
| `state_repo` watermark | `GET /` (after read) + `POST /queue/mark-seen` | only two writers | ✓ WIRED | `app/web/routes.py:198,253` |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| Queue rows | `QueuePage.rows` | `read_queue` → `listings` (+ `listing_fts` when querying) | Yes — real FTS/listings SQL, no static fallback | ✓ FLOWING |
| Merge rate | `MergeRate.merged/fetched` | `count_merges_for_run` (windowed) / latest `runs.fetched_count` | Yes — real aggregate; `None` at zero denominator (not a fake `0%`) | ✓ FLOWING |
| Exclusion chips | `QueueRule.kind/count` | `rule_counts_for_listings` + `FilterRule` kind lookup | Yes — per latest run | ✓ FLOWING |
| Save/hidden flags | `ListingState.saved/hidden` | `state_for_listings` (one query over `listing_events`) | Yes — real projection | ✓ FLOWING |
| Last-run strip | `RunSummary` → `render_run_fragment` | `run_repo.list_runs` | Yes — persisted run row | ✓ FLOWING |
| New/stale badges | `_row_flags` | `first_seen_at`/`last_seen_at`/`is_active` + watermark | Yes — real columns | ✓ FLOWING |
| Run reason | `RunSummary.sentence` | `reason_sentence` over persisted `reason_counts_json` + `fetched_count` | Yes — derived from persisted counts | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full suite | `.venv/bin/python -m pytest -q` | 591 passed, 2 deselected in 96.10s | ✓ PASS |
| Dedup/merge/revert/merges lanes | `pytest -q tests/domain/test_dedup.py tests/db/test_dupes.py tests/pipeline/test_dedup_merge.py tests/pipeline/test_dedup_revert.py tests/api/test_merges_view.py` | 37 passed in 21.15s | ✓ PASS |
| Filter/exclusions/capability lanes | `pytest -q tests/domain/test_filter.py tests/domain/test_criteria.py tests/db/test_exclusions.py tests/pipeline/test_filter_stage.py tests/pipeline/test_capability_surface.py tests/api/test_queue_excluded.py` | 61 passed in 21.15s | ✓ PASS |
| Criteria CRUD/snapshot/config lanes | `pytest -q tests/db/test_search_repo_writes.py tests/api/test_searches_crud.py tests/pipeline/test_criteria_snapshot.py tests/api/test_criteria_capabilities.py tests/pipeline/test_single_search_run.py tests/test_config.py` | 48 passed in 31.47s | ✓ PASS |
| Search/signals/events lanes | `pytest -q tests/domain/test_search_query.py tests/db/test_queue_state.py tests/api/test_queue_search.py tests/api/test_queue_signals.py tests/db/test_listing_events.py tests/api/test_listing_events.py` | 70 passed in 36.76s | ✓ PASS |
| Run reason/history/migration guards | `pytest -q tests/domain/test_run_reason.py tests/api/test_run_history.py tests/api/test_run_reason.py tests/db/test_migration_contract.py tests/db/test_orm_drift.py tests/db/test_no_pii_columns.py tests/db/test_skeleton_boot.py` | 63 passed in 29.01s | ✓ PASS |
| Pure domain (independent, throwaway) | `.venv/bin/python -c "build_match_expression/compute_empty_reason/grades_conflict checks"` | all assertions passed | ✓ PASS |
| rapidfuzz pinned + importable | `.venv-host/bin/python -c "import rapidfuzz"` | `rapidfuzz 3.14.6` | ✓ PASS |
| Lint | `.venv/bin/python -m ruff check app tests` | All checks passed! | ✓ PASS |

## Probe Execution

Step 7c: **SKIPPED** — no `scripts/*/tests/probe-*.sh` exist and Phase 2 declares no probe. (The
scraper-survival probe is a Phase-1 deliverable.)

## Requirements Coverage

All 15 Phase-2 requirement IDs appear in the ten PLAN frontmatters and are marked Complete in
REQUIREMENTS.md. No orphaned and no unclaimed IDs.

| Requirement | Source Plan(s) | Description | Status | Evidence |
| ----------- | -------------- | ----------- | ------ | -------- |
| QUEUE-03 | 02-02, 02-04 | Same job on two sources merged, reversible audit | ✓ SATISFIED | `dedup_stage`, `dupe_repo.apply_merge`, `listing_dupes`; tests above |
| QUEUE-04 | 02-06 | Revert an incorrect merge | ✓ SATISFIED | `revert_merge` + revert route; tests |
| QUEUE-06 | 02-07 | Full-text search the queue | ✓ SATISFIED | `search_query`, `queue_repo` FTS branch; tests |
| QUEUE-07 | 02-01, 02-07 | New-since-last-visit + stale | ✓ SATISFIED | `state_repo`, `_row_flags`; tests |
| QUEUE-08 | 02-09 | Save/hide as append-only events | ✓ SATISFIED | `event_repo`, events route; tests |
| QUEUE-09 | 02-06 | Merge rate + rows behind it | ✓ SATISFIED | windowed `merge_rate` + `list_merges`; 2-run regression test |
| CRIT-01 | 02-01, 02-03, 02-08 | Create/edit/delete named criteria | ✓ SATISFIED | `search_repo` write side, `searches.py`, `criteria.html`; tests |
| CRIT-02 | 02-05 | Criteria versioned for reproducibility | ✓ SATISFIED | `criteria_snapshot_json` before fetch; tests |
| CRIT-03 | 02-08 | Enable/disable without delete | ✓ SATISFIED | toggle route, version semantics; tests |
| FILT-01 | 02-02, 02-03, 02-05 | Deterministic reject before any LLM call | ✓ SATISFIED | `filter.evaluate`; no LLM import under `app/pipeline`; empty `llm_calls` |
| FILT-02 | 02-03, 02-05 | Every rejection records rule + why | ✓ SATISFIED | `listing_exclusions(rule_id, rule_kind, detail_json)`; tests |
| FILT-03 | 02-07 | See why a specific listing was excluded | ✓ SATISFIED (advisory) | excluded toggle + chips; `detail_json` recorded, matched term not rendered (see Advisory) |
| FILT-04 | 02-01, 02-08 | Tune rules from UI without a code change | ✓ SATISFIED | DB-backed `filter_rules`, per-kind forms, no raw JSON; tests |
| RUN-03 | 02-01, 02-05, 02-10 | Run records what it did/found/why | ✓ SATISFIED | `run_reason`, stage log, `/runs` + last-run strip; tests |
| RUN-04 | 02-10 | Run history | ✓ SATISFIED | `run_repo.list_runs`, `runs.html`; tests |

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/domain/dedup.py` | 151 | `fuzz.token_set_ratio` used as a diagnostic | ℹ️ Info | Not a defect: it is explicitly non-deciding; the gate is `token_sort_ratio` (asserted) |
| `app/pipeline/run.py` | 708-716,737 | `criteria_compile` prepended then `stage_log[-12:]` truncates from the same end | ℹ️ Info | 02-REVIEW.md IN-04; latent only with >9 sources; not reachable with today's 2 adapters |
| `app/db/repositories/exclusion_repo.py` | 30-40,122-156 | `ExclusionRecord`/`exclusions_for_run` uncalled | ℹ️ Info | 02-REVIEW.md IN-02; `detail_json` has no UI consumer (see Advisory) |
| `app/db/repositories/queue_repo.py` | 365,416 | `_page_rule_counts` queried twice per page | ℹ️ Info | 02-REVIEW.md IN-03; redundant query, no behaviour impact |
| `app/api/searches.py` etc. | — | No CSRF token on POSTs | ℹ️ Info | Accepted risk under the project's "Auth: none in v1" decision; every route carries the `current_user` seam |

Debt-marker gate: **no `TBD`/`FIXME`/`XXX`/`TODO`/`PLACEHOLDER` markers** anywhere under `app/`.
No stub/hollow implementations found: every rendered value traces to a real query (Level 4 above).

## Decision Coverage

`check.decision-coverage-verify` → `{ total: 23, honored: 23, not_honored: [] }` —
"All trackable CONTEXT.md decisions are honored by shipped artifacts." (non-blocking gate.)

## Human Verification Required

1. **Tune θ against the first real corpus**

   **Test:** Run a real pipeline run against live sources; inspect `listing_dupes` pairs and the
   `/merges` rate; choose and record `Settings.dedup_fuzzy_threshold` (default 88) and its band.
   **Expected:** A recorded θ with justification in `docs/`; the merge rate within/explained against
   the 10–15% research band.
   **Why human:** No real corpus exists pre-run (02-VALIDATION.md Manual-Only; ROADMAP Phase-2 Notes;
   D-31). Code proves θ is a settings read with no literal — not that 88 is correct.

2. **Merge-rate band sanity check**

   **Test:** After a real run, compare the observed `/merges` rate to the 10–15% research band.
   **Expected:** Either an accepted rate or a recorded decision to adjust θ.
   **Why human:** The band is from a different market/query shape (02-VALIDATION.md).

3. **Compose smoke of the running stack**

   **Test:** `docker compose up`, browse the queue, trigger a run, confirm migration 0002 applies.
   **Expected:** App boots, queue renders, run completes; result recorded.
   **Why human:** 02-VALIDATION.md carry-over (WINDOWS.md open item #1); needs Docker + a browser.

4. **Confirm the human approval of the `rapidfuzz` pin**

   **Test:** Confirm the recorded approval in 02-02-SUMMARY.md "Authentication Gates".
   **Expected:** Approval of version 3.14.6, source repo, pre-compiled wheel, no arbitrary build step.
   **Why human:** An out-of-band sign-off cannot be machine-verified (discharged in-phase; re-listed
   for the end-of-phase checkpoint).

5. **Judge whether the excluded-listing chip satisfies SC2's "which rule fired and why"**

   **Test:** Under `Show excluded`, inspect a rejected listing's chip (`exclude_keyword (2)`).
   **Expected:** Decide whether rule-kind + per-rule count is sufficient, or whether the firing rule
   id and the matched `detail_json` term must be surfaced.
   **Why human:** The rule id and matched term have no UI consumer; the chip names only the kind.
   This is a product-sufficiency judgment, not a machine-definable pass/fail.

## Gaps Summary

**No must-have gap was found.** All 54 plan `must_haves.truths`, all five roadmap Success
Criteria, all required artifacts (Levels 1–2), all key links (Level 3) and the dynamic
data flows (Level 4) verified against the codebase and re-executed tests. All 15 Phase-2
requirement IDs are accounted for and satisfied. The post-review fixes (CR-01 and WR-01…WR-06)
are present in the code and covered by regression tests. `ruff` is clean; no debt markers exist.

Two observations are recorded but do **not** block the phase:

- **Advisory (FILT-03/SC2):** the persisted `listing_exclusions.detail_json` ("why" — the matched
  term/field/count) and the firing rule id are not rendered anywhere; the queue chip shows only
  the rule kind and a per-rule count. FILT-02's recording requirement is fully met and tested.
  This is surfaced to the human at the end-of-phase checkpoint (Human Verification #5).
- **Info:** the remaining 02-REVIEW.md Info items (IN-03 double count query, IN-04 stage-log
  truncation ordering, IN-13 no CSRF under the accepted "auth: none" decision) are latent,
  non-goal-blocking observations.

Status is **human_needed**: automated verification is complete and green; the manual-only items
(θ tuning, merge-rate band, compose smoke) and the SC2-sufficiency judgment require a human.

---

_Verified: 2026-09-16T13:22:11Z_
_Verifier: the agent (gsd-verifier)_
