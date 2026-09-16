---
phase: 02-clean-filtered-queryable-queue
verified: 2026-09-16T17:05:21Z
status: human_needed
score: 54/54 must-haves verified
re_verification: true
re_verification_details:
  previous_status: human_needed
  previous_score: 54/54 must-haves verified
  previous_verified: 2026-09-16T13:22:11Z
  previous_commit: 52e86f3
  current_commit: bcb86c2
  gaps_closed: []
  gaps_remaining: []
  regressions: []
  verdicts_changed: 0
covered_files:
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - .planning/WINDOWS.md
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
  - .planning/phases/02-clean-filtered-queryable-queue/02-SECURITY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-UAT.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-UI-REVIEW.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-VALIDATION.md
  - alembic/env.py
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
  - app/web/filters.py
  - app/web/routes.py
  - app/web/template_env.py
  - app/web/templates/html/_listing_row.html
  - app/web/templates/html/base.html
  - app/web/templates/html/criteria.html
  - app/web/templates/html/merges.html
  - app/web/templates/html/queue.html
  - app/web/templates/html/queue_list.html
  - app/web/templates/html/runs.html
  - assets/tailwind/input.css
  - pyproject.toml
  - requirements.txt
  - static/vendor/app.css
  - tests/api/test_criteria_capabilities.py
  - tests/api/test_listing_events.py
  - tests/api/test_merges_view.py
  - tests/api/test_queue_excluded.py
  - tests/api/test_queue_search.py
  - tests/api/test_queue_signals.py
  - tests/api/test_run_history.py
  - tests/api/test_run_reason.py
  - tests/api/test_searches_crud.py
  - tests/conftest.py
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
  - tests/pipeline/test_criteria_form_to_run.py
  - tests/pipeline/test_criteria_snapshot.py
  - tests/pipeline/test_dedup_merge.py
  - tests/pipeline/test_dedup_revert.py
  - tests/pipeline/test_filter_stage.py
  - tests/pipeline/test_ingest_e2e.py
  - tests/pipeline/test_single_search_run.py
  - tests/test_config.py
  - tests/test_dependency_pins.py
  - tests/test_stylesheet_coverage.py
covered_digest: "v1:sha256:b969601f1541ba743670016fb03d41cec5489ffc7529416af6ab19a46dbd1ff7"
behavior_unverified: 0
overrides_applied: 0
gaps: []
advisory:
  - finding: "The built image is not asserted to contain rapidfuzz==3.14.6 (02-SECURITY.md W-01). Dockerfile:38-39 installs requirements.txt; the only post-install assertion (Dockerfile:49-50) checks the JobSpy VCS pin, not rapidfuzz. tests/test_dependency_pins.py imports rapidfuzz from the test env, not the image."
    category: other
    reason: "The manifest layer (pyproject.toml + requirements.txt agreement) is tested, but 'the image contains the pinned dependency' is not asserted. De-risked for the Phase-2 image by the operator compose smoke (a completed run imports app.pipeline → app.domain.dedup, which imports rapidfuzz, so the image must resolve it). Recommended follow-up, not a phase-2 gap: add a Dockerfile post-install import assertion."
    evidence_status: "README-of-record (02-SECURITY.md W-01); no failing test"
  - finding: "listing_exclusions.detail_json (the matched term/field/count behind a rejection) and the firing QueueRule.rule_id have no UI consumer; the queue chip renders only rule.kind + a per-rule count."
    category: architectural
    reason: "FILT-02 ('records which rule fired and why') is satisfied — the detail is persisted and tested (tests/db/test_exclusions.py) — but FILT-03/SC2's on-screen 'why' is a product-sufficiency call. `exclusion_repo.ExclusionsRecord`/`exclusions_for_run` remain uncalled. Surfaced as human_verification #5, not a gap."
    evidence_status: "codebase observation (grep: detail_json referenced only in models/exclusion_repo); not backed by a failing test"
human_verification:
  - test: "Tune the dedup threshold θ against the first real corpus"
    status: pending
    expected: "Run a real pipeline run against live LinkedIn/Indeed data, inspect the listing_dupes pairs and the merge rate on /merges, and record the chosen Settings.dedup_fuzzy_threshold (currently 88) and its justification in docs/."
    why_human: "No real corpus exists pre-run; θ is deliberately shipped as a setting with a tuning procedure (02-VALIDATION.md Manual-Only; ROADMAP Phase-2 Notes; D-31). Code and tests prove θ is a settings read with no literal (app/config.py:81; tests/test_config.py), not that 88 is the right value."
  - test: "Merge-rate band sanity check after a real run"
    status: pending
    expected: "After a real run, compare the observed /merges rate against the 10–15% band from research and record why the chosen θ is or is not adjusted."
    why_human: "The band comes from a different market/query shape; QUEUE-09's windowed rate is machine-verified (tests/api/test_merges_view.py:201 — 33% not 67%), but whether the observed rate is sane needs real data."
  - test: "Compose smoke of the running stack"
    status: satisfied
    expected: "`docker compose up -d --wait` healthy; `/health` db ok; a run completes; listings survive `docker compose restart`; `/`, `/merges`, `/runs`, `/searches` all 200."
    why_human: "Operator-reported PASS on the Phase-2 image (recorded as closed in .planning/WINDOWS.md item #1, resolved 2026-09-16T14:45:41Z). Docker is absent from the verifier sandbox, so this re-verification cannot independently reproduce it. Residual (not a blocker): the three later UI/test commits (566e385, 3508f05, bcb86c2) changed templates/CSS/tests but not the migration or pipeline, so the smoked contract still holds; a re-smoke on the final image is optional."
  - test: "Confirm the pinned rapidfuzz dependency was human-approved"
    status: pending
    expected: "The approval (version 3.14.6, source repo rapidfuzz/RapidFuzz, pre-compiled wheel, no arbitrary build step) is recorded in 02-02-SUMMARY.md 'Authentication Gates'."
    why_human: "An out-of-band sign-off cannot be machine-verified; recorded as discharged in-phase on 2026-09-16 (02-02-SUMMARY.md:149), re-listed for the end-of-phase human checkpoint."
  - test: "Judge whether the excluded-listing chip satisfies 'which rule fired and why'"
    status: pending
    expected: "Under `Show excluded`, each rejected listing shows a chip `rule.kind (count)` (e.g. `exclude_keyword (2)`). Confirm this is sufficient, or require the firing rule id and the matched `detail_json` term (e.g. `crypto`) to be surfaced. Note the count is deliberately run-wide — two listings rejected once each by the same rule both read `(2)`, pinned by tests/api/test_queue_excluded.py::test_the_chip_count_is_grouped_over_the_run_not_per_row."
    why_human: "The rule id and the persisted detail_json have no UI consumer (see Advisory). This is a product-sufficiency judgment against SC2/FILT-03, not a machine-definable pass/fail."
---

# Phase 2: Clean, Filtered, Queryable Queue — Verification Report

**Phase Goal:** A deduplicated, deterministically filtered, searchable queue the user trusts — with every rejection explained and every run observable.
**Verified:** 2026-09-16T17:05:21Z
**Status:** human_needed
**Re-verification:** Yes — the prior report (2026-09-16T13:22:11Z, at `52e86f3`) predated nine commits. Re-derived from the current tree at `bcb86c2`.
**Score:** 54/54 must-have truths verified (0 present-but-behavior-unverified). **No truth's pass/fail verdict changed**; see "What changed since the prior report".

## Method

Independent, goal-backward verification against the codebase — not against the ten SUMMARYs:

- Full suite re-run: `.venv/bin/python -m pytest -q` → **601 passed, 2 deselected in 71.29s** (prior report: 591; +10 tests from this cycle).
- Four grouped phase lanes re-run and cited per truth (37 + 62 + 50 + 133 passed).
- The nine commits since the prior verification inspected individually: `7bfa417`, `3242b2d`, `566e385`, `3508f05`, `b75c79f`, `bcb86c2` (and the three docs commits).
- The migration defect **reproduced in the failure direction**: transiently forcing the migration pragma to `foreign_keys=ON` (the pre-fix behaviour) makes the new regression test fail with `sqlite3.IntegrityError: FOREIGN KEY constraint failed / [SQL: DROP TABLE runs]`. The one-word experiment was reverted in the same shell invocation; `git diff -- alembic/env.py` is clean.
- `ruff check app tests` → **All checks passed!**
- `data/` was **not opened** (live production DB). The operator-reported live-DB facts are cited as operator-confirmed, not independently re-read.

## What changed since the prior report

| Commit | Change | Effect on this verification |
| ------ | ------ | --------------------------- |
| `7bfa417` | `alembic/env.py` now runs migrations with `PRAGMA foreign_keys=OFF` (`_apply_migration_pragmas`, wired at `env.py:95`) | **Fixes a real crash-loop**: migration 0002's batch recreation of `runs` (`CREATE → COPY → DROP TABLE runs → RENAME`) aborted when a child table held rows referencing `runs.id`; `entrypoint.sh` has `set -e`, so the container crash-looped. Truths 02-01 #1/#2 now proven on the populated path. |
| `3242b2d` | `tests/db/test_migration_contract.py::test_upgrade_populated_0001_to_head` + a `populated_0001` session fixture (`tests/conftest.py`) | The regression test that catches it. **Proven fail-first** (see Method). |
| `566e385` | `static/vendor/app.css` now defines all 160 formerly-unstyled template classes; `<nav>` added; `tests/test_stylesheet_coverage.py` added | Closes UI-REVIEW blocker #1. Independent scan: **163 literal class tokens, 11 documented exemptions, 0 missing rules**. The guard has a negative control (`test_the_selection_check_flags_an_unstyled_class`). |
| `3508f05` | `human_label` / `format_datetime` filters via one `template_env` factory; `Company` outer-join for real company case; Confirm/Cancel delete pairs; `aria-expanded`/`aria-controls` | Additive UI quality; no must-have truth relies on it. Applied consistently (filters used in `runs.html`, `criteria.html`, `queue.html`, `merges.html`, `_listing_row.html`, `_run_status.html`). |
| `b75c79f` | Stylesheet-exemption reasons corrected | Cosmetic; `test_the_exemption_list_is_justified` passes. |
| `bcb86c2` | `tests/pipeline/test_criteria_form_to_run.py` + search×hidden and search×excluded tests; `02-VALIDATION.md` corrected | Fills the two Nyquist gaps G1/G2. |

## Roadmap Success Criteria

| # | Success Criterion | Status | Evidence |
| - | ----------------- | ------ | -------- |
| 1 | Deduplicated queue; same job on two sources appears once, with merge rate and rows visible, incorrect merge revertible | ✓ VERIFIED | `app/pipeline/dedup_stage.py`, `app/domain/dedup.py`, `dupe_repo.apply_merge/revert_merge/merge_rate/list_merges`, `merges.html`; `tests/pipeline/test_dedup_merge.py`, `tests/api/test_merges_view.py`, `tests/pipeline/test_dedup_revert.py`, `tests/api/test_queue_search.py::test_queue_hides_absorbed_twin_until_revert` — all pass (lane A, 37) |
| 2 | For any excluded listing, which rule fired and why is visible | ✓ VERIFIED (advisory + human call) | Out of default view, dimmed under `Show excluded`, one chip per firing rule (kind + count): `queue_repo._enrich` (`app/db/repositories/queue_repo.py:431-440`), `_listing_row.html:42-44`, `tests/api/test_queue_excluded.py` (5). "Why" is recorded in `listing_exclusions.detail_json` (FILT-02, tested) but the matched term/rule id is not rendered — Advisory + Human #5 |
| 3 | Create/edit/enable/disable/delete named criteria + tune rules from the UI without a code change; runs reproducible against a criteria version | ✓ VERIFIED | `app/api/searches.py`, `app/db/repositories/search_repo.py`, `criteria.html` (per-kind forms; 9 term textareas, no `params_json` control), `runs.criteria_snapshot_json` written before the fetch (`app/pipeline/run.py:619`); `tests/api/test_searches_crud.py`, `tests/db/test_search_repo_writes.py`, `tests/pipeline/test_criteria_snapshot.py`, `tests/api/test_criteria_capabilities.py`, `tests/pipeline/test_single_search_run.py`, and the new `tests/pipeline/test_criteria_form_to_run.py` — all pass (lane C, 50) |
| 4 | Full-text searchable queue; save/hide as append-only events; new-since-last-visit and stale distinguishable | ✓ VERIFIED | `app/domain/search_query.py`, `queue_repo` (bound `MATCH` only), `event_repo` (append-only + projection), `state_repo` (watermark); `tests/domain/test_search_query.py`, `tests/api/test_queue_search.py` (incl. search×hidden), `tests/api/test_queue_signals.py`, `tests/db/test_listing_events.py`, `tests/api/test_listing_events.py` — all pass (lane D) |
| 5 | Run history: each run records what it did, what it found, and — when the queue is empty — why | ✓ VERIFIED | `app/db/repositories/run_repo.py`, `app/domain/run_reason.py` (six-value precedence + counts), `runs.html`, queue last-run strip via `render_run_fragment`; `tests/api/test_run_history.py`, `tests/api/test_run_reason.py`, `tests/domain/test_run_reason.py` — all pass (lane D) |

## Migration defect — independently verified, not merely tested

The migration defect is **genuinely fixed in the code path**, not only covered by a new test:

- **The code path now guarantees it:** `alembic/env.py:37-67` defines `_apply_migration_pragmas` which executes `PRAGMA foreign_keys=OFF` (`env.py:63`) and is attached to the migration engine's `connect` event (`env.py:95`). The runtime engine is unchanged and still enforces `PRAGMA foreign_keys=ON` (`app/db/session.py:38`) — so the fix is scoped to migrations only.
- **The new test fails without the fix:** reverting only the pragma to `ON` (pre-fix behaviour) makes `tests/db/test_migration_contract.py::test_upgrade_populated_0001_to_head` fail at `tests/db/test_migration_contract.py:99` with:

  ```
  sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) FOREIGN KEY constraint failed
  [SQL: DROP TABLE runs]
  ```

  With the fix in place the test passes (`1 passed`); the whole `tests/db/test_migration_contract.py` file passes.
- **The test is not vacuous:** the fixture seeds one non-NULL `run_id` row in each of `listing_events`, `listing_exclusions`, `scores`, `llm_calls`, `source_request_log` (`tests/conftest.py` `RUN_REFERENCING_TABLES`) — the exact condition fresh-DB tests and the Docker build never exercised — then asserts revision `0002`, no seeded row loss, both new tables, the four new `runs` columns, `listing_events.criteria_version`, `ck_runs_reason` **and** the surviving `ck_runs_trigger`/`ck_runs_status` CHECKs, and both `listing_dupes` indexes.
- **Live database:** operator-confirmed at revision `0002` with 104 listings preserved, `ck_runs_reason` present and both `listing_dupes` indexes present. Not independently re-read here (`data/` is out of scope).

## Observable Truths (plan must_haves, 54 total)

Evidence key: **lane A** = 37 passed; **lane B** = 62 passed; **lane C** = 50 passed; **lane D** = 133 passed. Full suite = 601 passed.

### 02-01 — Schema spine (4/4)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `alembic upgrade head` on a fresh database leaves exactly one revision `0002` and one Alembic head | ✓ VERIFIED | `tests/db/test_migration_contract.py:270,281` (fresh) **plus** the new populated-upgrade case `:496-500`; migration engine `alembic/env.py:63,95` |
| 2 | Migrated DB has `filter_rules`, `queue_state`, four new `runs` columns, `listing_exclusions.criteria_version`, `listing_dupes` unique index (PRAGMA/sqlite_master) | ✓ VERIFIED | `tests/db/test_migration_contract.py` items 10–13 **and** the populated-path assertions `:511-549`; `tests/db/test_skeleton_boot.py` (lane D) |
| 3 | Every new JSON column is allow-listed; no new PII-shaped column | ✓ VERIFIED | `tests/db/test_no_pii_columns.py` (lane D) |
| 4 | `dedup_fuzzy_threshold`, `dedup_posted_window_days`, `stale_after_days`, `queue_page_size` readable from `Settings`; no literal under `app/pipeline` | ✓ VERIFIED | `app/config.py:81,84,87,89`; `tests/test_config.py` (lane C) |

### 02-02 — rapidfuzz dependency (3/3)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `rapidfuzz==3.14.6` installed and importable; both fuzz functions callable | ✓ VERIFIED | `tests/test_dependency_pins.py::test_rapidfuzz_imports_at_the_pinned_version` (asserts version + both callables) |
| 2 | Exact pin declared once in `pyproject.toml` `[project].dependencies`, mirrored verbatim in `requirements.txt`; no floating range | ✓ VERIFIED | `tests/test_dependency_pins.py::test_rapidfuzz_pin_is_declared_exactly`; `pyproject.toml`, `requirements.txt:18` |
| 3 | A human confirmed the pinned version/source/build before install | ✓ VERIFIED (human-recorded) | `02-02-SUMMARY.md:149` records `user_response = "approved"`; not re-verifiable → Human #4 (Advisory W-01 for the image assertion) |

### 02-03 — Pure decision layer (6/6)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `evaluate(rules, facts)` returns only firing rules ordered by `(position, rule_id)`; a malformed rule degrades to skipped | ✓ VERIFIED | `app/domain/filter.py:402`; `tests/domain/test_filter.py` (lane B) |
| 2 | An absent value is never a rejection reason | ✓ VERIFIED | `tests/domain/test_filter.py::test_unknown_values_are_never_a_rejection_reason` |
| 3 | An unknown rule `kind` is skipped, not pass-through | ✓ VERIFIED | `tests/domain/test_filter.py::test_an_unknown_kind_is_skipped` |
| 4 | Every `RuleOutcome.detail` carries terms/field names/counts only — no description excerpt/removed value | ✓ VERIFIED | `tests/domain/test_filter.py::test_detail_keys_are_exact_per_kind`, `::test_exclude_keyword_never_persists_the_field_text` |
| 5 | Criteria mapping assembles a `SearchQuery` and a rule list ordered by `(search_id, position)` | ✓ VERIFIED | `app/domain/criteria.py`; `tests/domain/test_criteria.py` |
| 6 | The injection catalogue flags/counts without altering text | ✓ VERIFIED | `app/domain/sanitize.py`; `tests/domain/test_injection_patterns.py` |

### 02-04 — Tier-2 dedup/merge (6/6)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Two sources → one visible listing + one absorbed twin + exactly one `listing_dupes` row (method, score, merge time) | ✓ VERIFIED | `tests/pipeline/test_dedup_merge.py::test_two_sources_one_job_merges_once_with_an_audit_row` (lane A) |
| 2 | A non-null survivor field is never overwritten; empty string counts as blank | ✓ VERIFIED | `tests/db/test_dupes.py::test_merge_fills_blanks_and_never_overwrites_a_non_null`, `::test_an_empty_string_counts_as_blank_but_a_real_value_does_not` |
| 3 | `snapshot_json` holds the survivor's pre-merge values for exactly the fields written | ✓ VERIFIED | `tests/db/test_dupes.py::test_snapshot_records_exactly_the_written_fields_and_their_prior_values` |
| 4 | A pair with a reverted `listing_dupes` row in either orientation is skipped before scoring | ✓ VERIFIED | `tests/db/test_dupes.py::test_reverted_pairs_is_empty_then_returns_both_orientations`; `dedup_stage.py:112-124` |
| 5 | A grade-carrying title never merges with the same title without the grade | ✓ VERIFIED | `tests/domain/test_dedup.py::test_senior_versus_ungraded_never_merges`, `::test_two_different_grades_never_merge` |
| 6 | `runs.deduped_count` equals merges written, not created count | ✓ VERIFIED | `tests/pipeline/test_dedup_merge.py` merge + zero cases |

### 02-05 — Hard filtering, snapshot, run reason (6/6)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Every rejected listing gets one `listing_exclusions` row per firing rule with `rule_id`,`rule_kind`,`detail_json`,`run_id`,`criteria_version` | ✓ VERIFIED | `app/pipeline/filter_stage.py:119-133`; `exclusion_repo`; `tests/db/test_exclusions.py`, `tests/pipeline/test_filter_stage.py` (lane B) |
| 2 | Filter stage runs after dedup, before `_finish`; no LLM client constructed/imported/called | ✓ VERIFIED | `app/pipeline/run.py:666-700`; grep finds **no** `llm`/`opencode` import under `app/pipeline/`; `tests/pipeline/test_filter_stage.py` asserts empty `llm_calls` |
| 3 | `runs.criteria_snapshot_json` holds the exact query/rules used; a criteria edit cannot rewrite a past run | ✓ VERIFIED | `app/pipeline/run.py:619`; `tests/pipeline/test_criteria_snapshot.py::test_editing_criteria_after_a_run_leaves_that_runs_snapshot_unchanged` |
| 4 | An unsupported filter appears in `runs.stage_log_json` (criteria_compile) **and** `runs.errors_json` | ✓ VERIFIED | `tests/pipeline/test_capability_surface.py::test_an_unsupported_salary_floor_is_warned_in_both_places` |
| 5 | `runs.reason` ∈ six-value enum by documented precedence, plus `reason_counts_json` | ✓ VERIFIED | `app/domain/run_reason.py:34-41,77-125`; `tests/domain/test_run_reason.py` |
| 6 | One malformed rule is skipped and recorded; neither empties the queue nor aborts the run | ✓ VERIFIED | `filter_stage.py:88-89`; `tests/pipeline/test_filter_stage.py` |

### 02-06 — Merge audit + revert (4/4)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Merges view lists every `listing_dupes` row with both sides, method, score, time, snapshot | ✓ VERIFIED | `dupe_repo.list_merges`; `merges.html`; `tests/api/test_merges_view.py::test_merges_page_lists_the_rate_its_window_and_the_rows_behind_it` (lane A) |
| 2 | Merge rate visible as merges over fetched for a stated window; rows reachable on the same page | ✓ VERIFIED | windowed `dupe_repo.merge_rate`; `tests/api/test_merges_view.py::test_merge_rate_windows_both_operands_to_the_latest_run` (33% not 67%) |
| 3 | Revert restores snapshot fields + marks `reverted_at`/`reverted_by`; twin reappears with no un-hide step | ✓ VERIFIED | `dupe_repo.revert_merge` (UPDATE-only, no delete); `tests/api/test_queue_search.py::test_queue_hides_absorbed_twin_until_revert` |
| 4 | After a revert, a subsequent run does not re-merge the pair | ✓ VERIFIED | `tests/pipeline/test_dedup_revert.py::test_a_reverted_merge_is_durable_and_the_pair_stays_separate` |

### 02-07 — Searchable queue, signals, excluded toggle (7/7)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Hostile query text does not raise/500 | ✓ VERIFIED | `tests/domain/test_search_query.py::test_every_hostile_input_becomes_an_expression_the_real_parser_accepts` + `::test_the_raw_inputs_really_do_raise_untransformed` (anti-vacuous); `tests/api/test_queue_search.py::test_an_apostrophe_query_returns_200_not_500` (lane D) |
| 2 | Every FTS order ends with a unique tie-break; identical requests return identical order | ✓ VERIFIED | `queue_repo.py:329`; `tests/api/test_queue_search.py::test_identical_search_requests_return_an_identical_row_order` |
| 3 | With no query, Phase-1 order `first_seen_at desc, id desc` and no `listing_fts` join | ✓ VERIFIED | `queue_repo.py:336-344`; `tests/api/test_queue_search.py::test_no_query_keeps_the_phase_one_order` |
| 4 | Listings after `queue_state.last_queue_view_at` (or all when NULL) marked new; `Mark all as seen` advances | ✓ VERIFIED | `state_repo`; `tests/api/test_queue_signals.py::test_listings_after_the_watermark_are_new_and_before_it_are_not`, `::test_mark_all_as_seen_clears_the_badges_and_keeps_the_rows` |
| 5 | Stale when `last_seen_at` older than `stale_after_days` or `is_active` false; new and stale can co-occur | ✓ VERIFIED | `queue_repo._row_flags`; `tests/api/test_queue_signals.py::test_the_stale_boundary_is_n_minus_one_n_and_n_plus_one`, `::test_a_listing_can_be_both_new_and_stale` |
| 6 | Excluded listings out of default view, dimmed under `Show excluded`, one chip per firing rule with a per-rule count | ✓ VERIFIED | `queue_repo.py:431-440`, `_listing_row.html:42-44`; `tests/api/test_queue_excluded.py` (5, incl. the new search×excluded composition and the run-wide count semantics). The count is run-wide by design (`_page_rule_counts` docstring); the chip's rule id/detail is unrendered → Advisory + Human #5 |
| 7 | Listing with un-reverted merges shows `merged from N sources`; absorbed twin absent until reverted | ✓ VERIFIED | `tests/api/test_queue_search.py::test_queue_hides_absorbed_twin_until_revert`; `merge_summary_for_listings` |

### 02-08 — Criteria CRUD (7/7)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Create a named search (keywords/location/remote/salary/seniority + rules) persisted with `version == 1` | ✓ VERIFIED | `search_repo.create_search`; `tests/api/test_searches_crud.py::test_post_searches_persists_a_version_one_enabled_search` (lane C) |
| 2 | Editing criteria/rules bumps `searches.version` by exactly 1; a completed run's snapshot is not rewritten | ✓ VERIFIED | `tests/db/test_search_repo_writes.py`, `tests/pipeline/test_criteria_snapshot.py` |
| 3 | A search can be disabled/re-enabled without deletion; a disabled search contributes no rules | ✓ VERIFIED | `tests/api/test_searches_crud.py::test_toggle`, `tests/db/test_search_repo_writes.py::test_enable_disable_does_not_bump_the_version` |
| 4 | Deleting a search removes its rules and leaves no orphan `filter_rules` row | ✓ VERIFIED | `tests/db/test_search_repo_writes.py::test_delete_search_removes_it_and_all_its_rules_only` |
| 5 | Every rule editor is a purpose-built per-kind form; no raw-JSON editor; no template evaluates filter semantics | ✓ VERIFIED | `criteria.html` (per-kind blocks; 9 term textareas; **no** `params_json` control; no `\|safe`) |
| 6 | A filter a board cannot honour is reported on the criteria page before any run, naming board + filter | ✓ VERIFIED | `tests/api/test_criteria_capabilities.py::test_an_unsupported_filter_is_reported_per_board` |
| 7 | A single search can be run on its own without changing the one-tap main trigger | ✓ VERIFIED | `tests/pipeline/test_single_search_run.py` (scoping + union unchanged + 202 run row) |

### 02-09 — Save/hide append-only events (6/6)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Save appends one `save`; unsave appends `unsave`; state projected from the latest event, never a column | ✓ VERIFIED | `event_repo._fold_events`; `tests/api/test_listing_events.py::test_posting_save_appends_one_event_and_the_row_reads_saved` (lane D) |
| 2 | UPDATE/DELETE on `listing_events` aborts with the Phase-1 append-only trigger | ✓ VERIFIED | `tests/db/test_listing_events.py::test_the_database_aborts_an_update_and_a_delete_of_an_event`, `::test_the_orm_cannot_update_or_delete_an_event_either` |
| 3 | A hidden listing leaves the default queue, reachable via `Hidden` with one-tap undo | ✓ VERIFIED | `tests/api/test_listing_events.py::test_hiding_removes_the_listing_from_the_queue_and_the_control_becomes_undo` |
| 4 | A saved listing appears under `Saved` and carries a star | ✓ VERIFIED | `tests/api/test_listing_events.py::test_posting_save_appends_one_event_and_the_row_reads_saved`; `_listing_row.html:30` |
| 5 | Toggling twice appends two rows and returns projected state; no event updated/deleted | ✓ VERIFIED | `tests/db/test_listing_events.py::test_save_then_unsave_projects_unsaved` |
| 6 | The page projection is one query, not one per row | ✓ VERIFIED | `tests/db/test_listing_events.py::test_state_for_a_whole_page_is_one_query` |

### 02-10 — Run history (5/5)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `GET /runs` lists one row per run, newest first, with times/trigger/duration/per-source counts/dedup/filter/errors | ✓ VERIFIED | `run_repo.list_runs`; `tests/api/test_run_history.py::test_runs_render_newest_first_and_stably` (lane D) |
| 2 | Each run row shows the persisted reason; expansion reveals counts + bounded raw stage log | ✓ VERIFIED | `tests/api/test_run_history.py::test_the_detail_fragment_carries_the_stage_log_and_the_per_rule_counts`; `runs.html:65-67` (reason rendered via `human_label`, with the raw value retained in `data-reason` and row classes) |
| 3 | Queue page carries a compact last-run strip linking to `/runs`, through the existing run-fragment renderer | ✓ VERIFIED | `app/web/routes.py` last-run strip; `queue.html`; `tests/api/test_run_reason.py::test_the_strip_links_to_the_run_history` |
| 4 | An unfinished run renders in-flight, never as completed with empty duration | ✓ VERIFIED | `run_repo._duration` returns `None`; `tests/api/test_run_history.py::test_an_unfinished_run_renders_in_flight_with_an_em_dash` |
| 5 | The history surface is read-only — no exposed route mutates a run | ✓ VERIFIED | `app/api/runs.py` history routes are `GET` only (`:125,:142,:163`; the module's only POSTs are `/runs` — create — and `/merges/{id}/revert` — dupe row); `tests/api/test_run_history.py::test_two_identical_requests_return_identical_bodies` |

**Score:** 54/54 truths verified (0 present-but-behavior-unverified). **Verdicts changed from the prior report: none.** Two truths (02-01 #1, #2) have stronger evidence via the populated-upgrade regression test.

## Required Artifacts (Level 1–2: exist + substantive)

All 102 fingerprinted files exist and are substantive; the newly-added ones:

| Artifact group | Status | Details |
| -------------- | ------ | ------- |
| Migration engine | ✓ VERIFIED | `alembic/env.py` (110 lines) — `_apply_migration_pragmas` with `foreign_keys=OFF`, scoped to migrations |
| Stylesheet layer | ✓ VERIFIED | `static/vendor/app.css` (31,233 bytes, minified single line); source `assets/tailwind/input.css` (+~1565 lines) |
| Shared UI filters | ✓ VERIFIED | `app/web/filters.py` (68 lines, real `human_label`/`format_datetime`), `app/web/template_env.py` (22 lines, single factory) |
| New guards/tests | ✓ VERIFIED | `tests/test_stylesheet_coverage.py` (158 lines, negative control present), `tests/pipeline/test_criteria_form_to_run.py` (162 lines) |
| Existing migration/ORM/config | ✓ VERIFIED | `alembic/versions/0002_queue_filter_and_run_reason.py`, `app/db/models.py`, `app/config.py` |
| Pure domain layer | ✓ VERIFIED | `app/domain/{filter,criteria,sanitize,dedup,run_reason,search_query}.py` — real logic, no placeholders |
| Repositories | ✓ VERIFIED | `dupe_repo`, `event_repo`, `exclusion_repo`, `queue_repo`, `run_repo`, `search_repo`, `state_repo` — real SQL; `queue_repo` holds the only bound `MATCH` |
| Pipeline stages | ✓ VERIFIED | `dedup_stage.py`, `filter_stage.py`, `run.py` (snapshot → dedup → filter → reason → finish) |
| API routes | ✓ VERIFIED | `app/api/{searches,events,runs}.py`, `app/web/routes.py` — registered in `app/main.py:56-60` |
| Templates | ✓ VERIFIED | `base.html` (nav), `queue.html`, `queue_list.html`, `_listing_row.html`, `criteria.html`, `merges.html`, `runs.html`, `_run_status.html` — substantive, escaping-safe (no `\|safe`) |
| Tests | ✓ VERIFIED | 65 test modules in the fingerprint; every phase lane green |

## Key Link Verification (Level 3: wired)

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `app/main.py` | searches/events/runs/web routers | `include_router` | ✓ WIRED | `app/main.py:56-60` |
| `run_pipeline` | `run_dedup_stage` → `run_filter_stage` → `_finish` | sequential calls | ✓ WIRED | `app/pipeline/run.py:666-740` |
| `filter_stage` | `criteria.rule_specs_from` → `filter.evaluate` → `exclusion_repo.record_exclusions` | repository→domain→repository | ✓ WIRED | `filter_stage.py:82,100,126` |
| `queue_repo.read_queue` | `event_repo.hidden_predicate` / `saved_predicate` | derived predicates | ✓ WIRED | `queue_repo.py:311-314`; one rule, two expressions |
| `queue_repo.read_queue` | `dupe_repo.merge_summary_for_listings`, `exclusion_repo.rule_counts_for_listings` | enrichment | ✓ WIRED | `queue_repo.py:403,414` — no re-implementation |
| `revert_merge` route | `dupe_repo.revert_merge` → queue visibility predicate | `reverted_at` flag | ✓ WIRED | `app/api/runs.py:241`; `queue_repo._not_absorbed_twin` |
| `queue` route | `render_run_fragment` (one run renderer) | `_last_run_strip` | ✓ WIRED | `app/web/routes.py`; `RunFragmentSource` Protocol |
| `POST /listings/{id}/events` | `event_repo.append_event` → `queue_repo.read_row` | same row partial | ✓ WIRED | `app/api/events.py:114,127-155` |
| `state_repo` watermark | `GET /` (after read) + `POST /queue/mark-seen` | only two writers | ✓ WIRED | `app/web/routes.py` |
| **NEW:** every page + HTMX fragment | `app/web/filters.py` (`human_label`, `format_datetime`) | `make_templates` factory | ✓ WIRED | `app/api/{events,runs,searches}.py` and `app/web/routes.py` all build via `app/web/template_env.py:17-21`; filters used in 6 templates |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| Queue rows | `QueuePage.rows` | `read_queue` → `listings` (+ `listing_fts` when querying) | Yes — real FTS/listings SQL, no static fallback | ✓ FLOWING |
| Queue company | `QueueRow.company` | `Listing` ⋈ `Company` outer-join (`queue_repo.py:385-386,447`), falling back to `company_norm` | Yes — real join (was `company_norm` only) | ✓ FLOWING |
| Merge rate | `MergeRate.merged/fetched` | `count_merges_for_run` (windowed) / latest `runs.fetched_count` | Yes — real aggregate; `None` at zero denominator | ✓ FLOWING |
| Exclusion chips | `QueueRule.kind/count` | `rule_counts_for_listings` + `_page_rule_counts` + `FilterRule` kind lookup | Yes — per latest run | ✓ FLOWING |
| Save/hidden flags | `ListingState.saved/hidden` | `state_for_listings` (one query over `listing_events`) | Yes — real projection | ✓ FLOWING |
| Last-run strip | `RunSummary` → `render_run_fragment` | `run_repo.list_runs` | Yes — persisted run row | ✓ FLOWING |
| Run reason/status labels | `human_label` filter | `_LABELS` dict over persisted enum | Yes — deterministic mapping, unknown values title-cased | ✓ FLOWING |
| New/stale badges | `_row_flags` | `first_seen_at`/`last_seen_at`/`is_active` + watermark | Yes — real columns | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full suite | `.venv/bin/python -m pytest -q` | 601 passed, 2 deselected in 71.29s | ✓ PASS |
| Migration regression (fixed) | `pytest -q tests/db/test_migration_contract.py::test_upgrade_populated_0001_to_head` | 1 passed | ✓ PASS |
| Migration regression (fail-first proof) | same test with pragma transiently set to `foreign_keys=ON` | 1 failed — `FOREIGN KEY constraint failed / [SQL: DROP TABLE runs]` | ✓ PROVEN |
| Dedup/merge/revert/merges lanes (A) | `pytest -q tests/domain/test_dedup.py tests/db/test_dupes.py tests/pipeline/test_dedup_merge.py tests/pipeline/test_dedup_revert.py tests/api/test_merges_view.py` | 37 passed in 42.17s | ✓ PASS |
| Filter/exclusions/capability lanes (B) | `pytest -q tests/domain/test_filter.py tests/domain/test_criteria.py tests/db/test_exclusions.py tests/pipeline/test_filter_stage.py tests/pipeline/test_capability_surface.py tests/api/test_queue_excluded.py` | 62 passed in 42.51s | ✓ PASS |
| Criteria/snapshot/form-to-run lanes (C) | `pytest -q tests/db/test_search_repo_writes.py tests/api/test_searches_crud.py tests/pipeline/test_criteria_snapshot.py tests/api/test_criteria_capabilities.py tests/pipeline/test_single_search_run.py tests/test_config.py tests/pipeline/test_criteria_form_to_run.py` | 50 passed in 55.50s | ✓ PASS |
| Search/signals/events/migration/UI/run lanes (D) | `pytest -q tests/domain/test_search_query.py tests/db/test_queue_state.py tests/api/test_queue_search.py tests/api/test_queue_signals.py tests/db/test_listing_events.py tests/api/test_listing_events.py tests/test_stylesheet_coverage.py tests/db/test_migration_contract.py tests/api/test_run_history.py tests/api/test_run_reason.py tests/domain/test_run_reason.py` | 133 passed in 88.06s | ✓ PASS |
| Stylesheet coverage (independent scan) | throwaway scan of `class="..."` tokens vs `app.css` | 163 tokens, 11 exempt, **0 missing**; negative-control test present | ✓ PASS |
| Lint | `.venv/bin/python -m ruff check app tests` | All checks passed! | ✓ PASS |

## Probe Execution

Step 7c: **SKIPPED** — no `scripts/*/tests/probe-*.sh` exist and Phase 2 declares no probe. (The scraper-survival probe is a Phase-1 deliverable; `docs/probes/2026-09-15-scraper-survival.md` is Phase-1 evidence.)

## Requirements Coverage

All 15 Phase-2 requirement IDs are claimed by the ten PLAN frontmatters and marked Complete in `REQUIREMENTS.md`. **No orphaned IDs and no unclaimed Phase-2 IDs.**

| Requirement | Source Plan(s) | Description | Status | Evidence |
| ----------- | -------------- | ----------- | ------ | -------- |
| QUEUE-03 | 02-02, 02-04 | Same job on two sources merged, reversible audit | ✓ SATISFIED | `dedup_stage`, `dupe_repo.apply_merge`, `listing_dupes`; lane A |
| QUEUE-04 | 02-06 | Revert an incorrect merge | ✓ SATISFIED | `revert_merge` + revert route; lane A |
| QUEUE-06 | 02-07 | Full-text search the queue | ✓ SATISFIED | `search_query`, `queue_repo` FTS branch; lane D |
| QUEUE-07 | 02-01, 02-07 | New-since-last-visit + stale | ✓ SATISFIED | `state_repo`, `_row_flags`; lane D |
| QUEUE-08 | 02-09 | Save/hide as append-only events | ✓ SATISFIED | `event_repo`, events route; lane D |
| QUEUE-09 | 02-06 | Merge rate + rows behind it | ✓ SATISFIED | windowed `merge_rate` + `list_merges`; 33%/67% regression |
| CRIT-01 | 02-01, 02-03, 02-08 | Create/edit/delete named criteria | ✓ SATISFIED | `search_repo` write side, `searches.py`, `criteria.html`; lanes B/C |
| CRIT-02 | 02-05 | Criteria versioned for reproducibility | ✓ SATISFIED | `criteria_snapshot_json` before fetch; lane C |
| CRIT-03 | 02-08 | Enable/disable without delete | ✓ SATISFIED | toggle route, version semantics; lane C |
| FILT-01 | 02-02, 02-03, 02-05 | Deterministic reject before any LLM call | ✓ SATISFIED | `filter.evaluate`; no LLM import under `app/pipeline`; empty `llm_calls` |
| FILT-02 | 02-03, 02-05 | Every rejection records rule + why | ✓ SATISFIED | `listing_exclusions(rule_id, rule_kind, detail_json)`; lane B |
| FILT-03 | 02-07 | See why a specific listing was excluded | ✓ SATISFIED (advisory) | excluded toggle + chips; `detail_json` recorded, matched term not rendered → Advisory + Human #5 |
| FILT-04 | 02-01, 02-08 | Tune rules from UI without a code change | ✓ SATISFIED | DB-backed `filter_rules`, per-kind forms, no raw JSON; lane C |
| RUN-03 | 02-01, 02-05, 02-10 | Run records what it did/found/why | ✓ SATISFIED | `run_reason`, stage log, `/runs` + last-run strip; lane D |
| RUN-04 | 02-10 | Run history | ✓ SATISFIED | `run_repo.list_runs`, `runs.html`, GET-only history; lane D |

## Nyquist Residual Skips — disposition

The Nyquist audit (`02-VALIDATION.md`) holds `nyquist_compliant: false` and names two residual skips. **Both are accepted; neither is escalated.**

| # | Residual | Disposition | Rationale |
| - | -------- | ----------- | --------- |
| R1 | No `alembic downgrade 0001 → upgrade head` round-trip test (empty or populated). `0001` is the one-way door. | **ACCEPTED** | `0001` is the one-way door; `downgrade()` exists only for Alembic tooling coherence. It was manually probed on 2026-09-16 (both empty and populated DBs complete `head → 0001 → head` with row counts preserved). The populated **upgrade** direction — the defect that actually occurred — now has a fail-first regression test. Adding a downgrade round-trip is worthwhile only if downgrade becomes user-facing. |
| R2 | "No route mutates a run" proven structurally (`app/api/runs.py` exposes GET for history) rather than by a route-method inventory. | **ACCEPTED** | Independently confirmed: history routes are `GET /runs`, `GET /runs/{run_id}`, `GET /runs/{run_id}/status` (`app/api/runs.py:125,142,163`); the module's only POSTs are `POST /runs` (create a run) and `POST /merges/{id}/revert` (mutate a dupe row). A regression requires adding a new mutating *history* route — a feature decision, not silent drift. |

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/db/repositories/queue_repo.py` | 519-523 | `_page_rule_counts` count is run-wide (documented in the docstring), so a listing excluded once by a rule that fired N times run-wide shows `(N)`; pinned by `tests/api/test_queue_excluded.py::test_the_chip_count_is_grouped_over_the_run_not_per_row` | ℹ️ Info (product call) | Deliberate, pre-dates the UI review (introduced `32994d0`, pinned `01862d4`). UI-REVIEW blocker #2's premise ("per-row count") was consciously not adopted; the on-screen sufficiency is Human #5, not a concealed defect |
| `Dockerfile` | 38-50 | No post-install assertion that `rapidfuzz` is present in the built image (02-SECURITY.md W-01) | ℹ️ Info (follow-up) | Manifest-level agreement is tested; image-level presence is not. De-risked by the operator smoke (a completed run imports the dedup module). See Advisory |
| `app/domain/dedup.py` | 151 | `fuzz.token_set_ratio` used as a diagnostic only | ℹ️ Info | Not a defect: explicitly non-deciding; the gate is `token_sort_ratio` (asserted) |
| `app/pipeline/run.py` | 708-716,737 | `criteria_compile` prepended then `stage_log[-12:]` truncates from the same end | ℹ️ Info | 02-REVIEW.md IN-04; latent only with >9 sources; not reachable with today's 2 adapters |
| `app/db/repositories/exclusion_repo.py` | 30-40,144-177 | `ExclusionRecord`/`exclusions_for_run` uncalled | ℹ️ Info | 02-REVIEW.md IN-02; `detail_json` has no UI consumer (see Advisory / Human #5) |
| `app/api/searches.py` etc. | — | No CSRF token on POSTs | ℹ️ Info | Accepted risk under the project's "Auth: none in v1" decision; every route carries the `current_user` seam |

Debt-marker gate: **no `TBD`/`FIXME`/`XXX`/`TODO`/`PLACEHOLDER` markers** anywhere under `app/`.
No stub/hollow implementations found: every rendered value traces to a real query (Level 4 above).

## Human Verification Required

Status is **human_needed**. Automated verification is complete and green; the manual-only items and the one product-sufficiency judgment require a human. (These are persisted in `02-UAT.md` for the end-of-phase checkpoint.)

### 1. Tune θ against the first real corpus — PENDING

**Test:** Run a real pipeline run against live sources; inspect `listing_dupes` pairs and the `/merges` rate; choose and record `Settings.dedup_fuzzy_threshold` (default 88).
**Expected:** A recorded θ with justification in `docs/`; the merge rate within/explained against the research band.
**Why human:** No real corpus exists pre-run (02-VALIDATION.md Manual-Only; ROADMAP Phase-2 Notes; D-31). Code proves θ is a settings read with no literal (`app/config.py:81`), not that 88 is correct.

### 2. Merge-rate band sanity check — PENDING

**Test:** After a real run, compare the observed `/merges` rate to the 10–15% research band.
**Expected:** Either an accepted rate or a recorded decision to adjust θ.
**Why human:** The band is from a different market/query shape (02-VALIDATION.md).

### 3. Compose smoke of the running stack — SATISFIED (operator-reported)

**Test:** `docker compose up -d --wait`, browse the queue, trigger a run, confirm migration 0002 applies; restart and confirm listings survive; check `/`, `/merges`, `/runs`, `/searches` return 200.
**Expected:** App boots healthy, `/health` db ok, a run completes, listings persist across restart, all four pages 200.
**Status:** **PASS on the Phase-2 image**, recorded as closed in `.planning/WINDOWS.md` item #1 (resolved 2026-09-16T14:45:41Z, after the migration fix `7bfa417`). Docker is absent from the verifier sandbox, so this re-verification cannot independently reproduce it. Residual, non-blocking: the three later commits (`566e385`, `3508f05`, `bcb86c2`) changed templates/CSS/tests only, not the migration or pipeline, so the smoked contract still holds; a re-smoke on the final image is optional.

### 4. Confirm the human approval of the `rapidfuzz` pin — PENDING

**Test:** Confirm the recorded approval in `02-02-SUMMARY.md:149` "Authentication Gates".
**Expected:** Approval of version 3.14.6, source repo `rapidfuzz/RapidFuzz`, pre-compiled wheel, no arbitrary build step.
**Why human:** An out-of-band sign-off cannot be machine-verified (discharged in-phase; re-listed for the end-of-phase checkpoint).

### 5. Judge whether the excluded-listing chip satisfies SC2's "which rule fired and why" — PENDING

**Test:** Under `Show excluded`, inspect a rejected listing's chip (`exclude_keyword (2)`).
**Expected:** Decide whether rule kind + per-rule count is sufficient, or whether the firing rule id and the matched `detail_json` term (e.g. `crypto`) must be surfaced. Note the count is run-wide by design.
**Why human:** The rule id and matched term have no UI consumer; this is a product-sufficiency judgment against SC2/FILT-03.

## Gaps Summary

**No must-have gap was found.** All 54 plan `must_haves.truths`, all five roadmap Success Criteria, all required artifacts (Levels 1–2), all key links (Level 3) and the dynamic data flows (Level 4) were re-derived against the codebase at `bcb86c2` and re-executed. All 15 Phase-2 requirement IDs are accounted for and satisfied. The migration defect is genuinely fixed in the code path (`alembic/env.py`), proven fail-first. The new stylesheet guard is non-vacuous (0 missing classes, with a negative control). `ruff` is clean; no debt markers exist.

Observations that do **not** block the phase:

- **Advisory (02-SECURITY W-01):** the built image is not asserted to contain `rapidfuzz`; manifest agreement is tested. De-risked by the operator smoke; recommended follow-up is a Dockerfile import assertion. Not a phase-2 gap.
- **Advisory / Human #5 (FILT-03/SC2):** the persisted `listing_exclusions.detail_json` and the firing rule id are not rendered; the chip shows the rule kind and a run-wide per-rule count. FILT-02's recording requirement is fully met and tested.
- **Known deliberate residual (not re-reported):** `run.trigger` still renders as a raw enum on `/runs` (the status and reason now have `human_label`; the raw enum also survives in `data-*` attributes and row classes). Rendered-markup tests pin the raw strings; a product decision.
- **Info:** `02-VALIDATION.md`'s intro says "four genuine gaps were found" while the audit table lists two distinct gaps (G1/G2) spanning four requirement rows — a wording inconsistency, not a coverage defect.

Status is **human_needed**: automated verification is complete and green; θ tuning, the merge-rate band, the rapidfuzz sign-off, the SC2 chip-sufficiency judgment, and an optional final-image re-smoke require a human.

---

_Verified: 2026-09-16T17:05:21Z_
_Verifier: the agent (gsd-verifier)_
