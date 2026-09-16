---
phase: 02-clean-filtered-queryable-queue
verified: 2026-09-16T18:04:08Z
status: passed
score: 54/54 must-haves verified
re_verification: true
re_verification_details:
  delta_reverification: true
  re_verification_scope: "delta only (bcb86c2 → 1bb7332); unchanged truths were not re-derived"
  previous_status: human_needed
  previous_score: 54/54 must-haves verified
  previous_verified: 2026-09-16T17:05:21Z
  previous_commit: bcb86c2
  current_commit: 1bb7332
  gaps_closed: []
  gaps_remaining: []
  regressions: []
  verdicts_changed: 0
  uat: "02-UAT.md — 5/5 items satisfied (2026-09-16)"
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
  - .planning/seeds/SEED-001-queue-filter-by-remote-and-location.md
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
  - compose.yml
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
covered_digest: "v1:sha256:30161c0510333fc00a8ed7e26652816ac0251288c8b7ae85e9da50d59414f11d"
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
    reason: "FILT-02 ('records which rule fired and why') is satisfied — the detail is persisted and tested (tests/db/test_exclusions.py) — but FILT-03/SC2's on-screen 'why' is a product-sufficiency call. `exclusion_repo.ExclusionRecord`/`exclusions_for_run` remain uncalled. Resolved at UAT item 5: the user judged the chip sufficient for now, and the related attribute-filter ask is captured as SEED-001."
    evidence_status: "codebase observation (grep: detail_json referenced only in models/exclusion_repo); not backed by a failing test"
---

# Phase 2: Clean, Filtered, Queryable Queue — Verification Report

**Phase Goal:** A deduplicated, deterministically filtered, searchable queue the user trusts — with every rejection explained and every run observable.
**Verified:** 2026-09-16T18:04:08Z
**Status:** passed
**Re-verification:** Yes — targeted **delta** re-verification. Baseline: the previous report at `bcb86c2` (54/54, `human_needed`). This pass covers only `bcb86c2 → 1bb7332`; unchanged truths were not re-derived.
**Score:** 54/54 must-have truths verified (0 present-but-behavior-unverified). **No truth's pass/fail verdict changed** in this delta; see "Delta since the baseline report".

## Method

Independent, goal-backward verification against the codebase — not against the ten SUMMARYs:

- Full suite re-run at `1bb7332`: `.venv/bin/python -m pytest -q` → **605 passed, 2 deselected in 113.57s** (baseline: 601; +4 tests from `a51a133`).
- Targeted delta lane re-run: `tests/domain/test_dedup.py tests/db/test_dupes.py tests/pipeline/test_dedup_merge.py tests/pipeline/test_dedup_revert.py tests/api/test_merges_view.py` → **41 passed in 8.98s** (baseline lane A: 37; +4).
- The baseline's other grouped lanes (62 + 50 + 133) were **not** re-run — this is a scoped delta, and no file they cover changed in `bcb86c2 → 1bb7332`.
- Both delta commits inspected line-by-line (`a51a133` on `app/domain/dedup.py`; `30a19f0` on `dupe_repo.py`/`merges.html`/`test_merges_view.py`) and `dfb7414` on `compose.yml`.
- The location-gate-before-score ordering verified by reading the code, not assumed (see below).
- `ruff check app tests` → **All checks passed!**
- `data/` was **not opened** (live production DB). The prior report's method (migration failure reproduced fail-first) stands and is not re-run.

## Delta since the baseline report (`bcb86c2 → 1bb7332`)

| Commit | Change | Must-have impact |
| ------ | ------ | ---------------- |
| `dfb7414` | `compose.yml` forwards `DEDUP_FUZZY_THRESHOLD`/`DEDUP_POSTED_WINDOW_DAYS`/`STALE_AFTER_DAYS`/`QUEUE_PAGE_SIZE` with in-code defaults as fallbacks | **No must-have.** Fixes a deployment defect (below). Recorded as resolved. |
| `a51a133` | `app/domain/dedup.py::score_pair` no longer penalises a one-sided unknown `location_norm`; `_pair_text` gained keyword-only `include_location: bool = True`; +3 unit tests and a 3-way-duplicate pipeline test | **QUEUE-03** (via 02-04 truths 1 and 6). Re-scored below; **stays VERIFIED**. |
| `30a19f0` | `MergeRate.window` → `"this run only (#N)"` (was `"latest run (#N)"`); a scope paragraph on `/merges` reusing `.merges-note`; the copy assertion deliberately relabelled + a scope-paragraph assertion added | **QUEUE-09** (via 02-06 truth 2). Re-scored below; **stays VERIFIED**. |
| `9470d64`, `b14e1d0`, `748f2bd`, `1bb7332`, `8a92a20` | UAT record, G3 evidence, WINDOWS, gitignore | No |

### Deployment defect resolved (`dfb7414`)

**Defect:** a host-side `.env` could never reach the container. Compose reads `.env` only for `${...}` substitution, and the image contains no `.env` (the Dockerfile does not COPY it; only `./data` is mounted), so pydantic-settings' `env_file=".env"` found nothing inside the container — the in-code defaults silently won. Worse, `docker compose up -d` reported `Container ... Running 0.0s` (no recreate), so nothing applied at all. Two layers of silent no-op; this is why the UAT's attempted θ=90 override never took effect.

**Resolution:** the four Phase-2 knobs are now forwarded explicitly in `compose.yml:21-28` with the in-code defaults as `${VAR:-default}` fallbacks, fixing the whole class rather than one field. `tests/test_deploy_manifest.py` stays green. A host `.env` now takes effect (still requiring a container recreate). This is a deployment-config fix; **no must-have truth depends on it**, and it does not change any verdict.

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
| 1 | Deduplicated queue; same job on two sources appears once, with merge rate and rows visible, incorrect merge revertible | ✓ VERIFIED | `app/pipeline/dedup_stage.py`, `app/domain/dedup.py` (incl. the `a51a133` one-sided-unknown-location fix), `dupe_repo.apply_merge/revert_merge/merge_rate/list_merges`, `merges.html`; `tests/pipeline/test_dedup_merge.py` (incl. the 3-way duplicate reproduction), `tests/api/test_merges_view.py`, `tests/pipeline/test_dedup_revert.py`, `tests/api/test_queue_search.py::test_queue_hides_absorbed_twin_until_revert` — all pass (delta lane A, 41) |
| 2 | For any excluded listing, which rule fired and why is visible | ✓ VERIFIED | Out of default view, dimmed under `Show excluded`, one chip per firing rule (kind + count): `queue_repo._enrich` (`app/db/repositories/queue_repo.py:431-440`), `_listing_row.html:42-44`, `tests/api/test_queue_excluded.py` (5). "Why" is recorded in `listing_exclusions.detail_json` (FILT-02, tested); the chip's rule kind + run-scoped count was judged sufficient at UAT item 5, and the related attribute-filter ask is captured as SEED-001 |
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

Evidence key: **delta lane A** = 41 passed (baseline 37; the only lane re-run for this delta); **lane B** = 62, **lane C** = 50, **lane D** = 133 (baseline, not re-run — no file they cover changed). Full suite at HEAD = 605 passed. Truths carrying a "lane A" citation are the dedup/merge/merges truths touched by this delta; all other citations are the baseline evidence, which stands.

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
| 1 | Two sources → one visible listing + one absorbed twin + exactly one `listing_dupes` row (method, score, merge time) | ✓ VERIFIED | `tests/pipeline/test_dedup_merge.py::test_two_sources_one_job_merges_once_with_an_audit_row` **and** the new 3-way reproduction `::test_a_three_way_duplicate_merges_both_twins_onto_the_first_seen` (3 listings survive, 2 dupe rows, the NULL-location twin absorbed) (delta lane A) |
| 2 | A non-null survivor field is never overwritten; empty string counts as blank | ✓ VERIFIED | `tests/db/test_dupes.py::test_merge_fills_blanks_and_never_overwrites_a_non_null`, `::test_an_empty_string_counts_as_blank_but_a_real_value_does_not` |
| 3 | `snapshot_json` holds the survivor's pre-merge values for exactly the fields written | ✓ VERIFIED | `tests/db/test_dupes.py::test_snapshot_records_exactly_the_written_fields_and_their_prior_values`; `dupe_repo.apply_merge` sets `snapshot_json` from exactly the fields it writes (`dupe_repo.py:202-217`) |
| 4 | A pair with a reverted `listing_dupes` row in either orientation is skipped before scoring | ✓ VERIFIED | `tests/db/test_dupes.py::test_reverted_pairs_is_empty_then_returns_both_orientations`; `dedup_stage.py:112-124` |
| 5 | A grade-carrying title never merges with the same title without the grade | ✓ VERIFIED | `tests/domain/test_dedup.py::test_senior_versus_ungraded_never_merges`, `::test_two_different_grades_never_merge`; the grade gate is the **first** check in `score_pair` (`dedup.py:148-149`), so the location change cannot reach it |
| 6 | `runs.deduped_count` equals merges written, not created count | ✓ VERIFIED | `tests/pipeline/test_dedup_merge.py` merge + zero cases, and the new 3-way test asserts `deduped_count == 2` |

**QUEUE-03 / `a51a133` re-score — the fix does not weaken any dedup prohibition.** The change is confined to the *score* construction: `_pair_text` gained a keyword-only `include_location: bool = True` (`dedup.py:108-119`), and `score_pair` passes `include_location = a.location_norm is not None and b.location_norm is not None` (`dedup.py:172-176`). Consequences, each checked against current code:

- **Known-incompatible locations still refuse, and the gate runs BEFORE the score.** The location gate is `dedup.py:158-163` (refuse when both locations are known and unequal); the score is computed afterwards at `dedup.py:172-176`. Reading the ordering directly (not assuming it): grade gate `:148` → company gate `:151-156` → location gate `:158-163` → score `:172-179`. So omitting the location *from the score* cannot merge a pair whose *known* locations are incompatible — that pair never reaches the score. Pinned by `tests/domain/test_dedup.py::test_the_location_gate_still_refuses_two_known_incompatible_locations` (a permissive θ=50 isolates the gate; both orientations return `None`).
- **Both-present scores are byte-identical.** When both locations are known, `include_location=True`, so the tuple is the full `(company, title, location)` — no existing score or boundary assertion changes. Guarded by `tests/domain/test_dedup.py::test_two_known_compatible_locations_still_score_with_location_included`, which first asserts the two computations genuinely differ (so the guard is not vacuous).
- **One-sided-unknown no longer penalised.** `tests/domain/test_dedup.py::test_a_one_sided_unknown_location_is_not_penalised_in_the_score` asserts the old computation was `< THETA` and the new is `100.0`, symmetrically.
- **Prohibitions unchanged:** a merge still never deletes the absorbed listing (the 3-way test asserts `len(listings) == 3`; `dupe_repo.py:185` — "the twin is never deleted and never deactivated"; a grep of `dedup_stage.py`/`dupe_repo.py` finds no `DELETE`), never overwrites a non-null survivor field (row 2), and always writes the snapshot for the fields it wrote (row 3).
- **Scope note:** `dedup_stage.py:151` still uses the full-tuple `_pair_text` default for its `token_set_ratio` **diagnostic**, which remains non-deciding (the gate is `token_sort_ratio`).

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
| 1 | Merges view lists every `listing_dupes` row with both sides, method, score, time, snapshot | ✓ VERIFIED | `dupe_repo.list_merges`; `merges.html`; `tests/api/test_merges_view.py::test_merges_page_lists_the_rate_its_window_and_the_rows_behind_it` (delta lane A) |
| 2 | Merge rate visible as merges over fetched for a stated window; rows reachable on the same page | ✓ VERIFIED | **Windowing NOT reverted** — `dupe_repo.merge_rate` still selects the latest run (`dupe_repo.py:470-473`, `select(Run).order_by(Run.started_at.desc(), Run.id.desc()).limit(1)`) and windows both operands to it (`count_merges_for_run(run_id)`); `tests/api/test_merges_view.py::test_merge_rate_windows_both_operands_to_the_latest_run` still asserts **33% not 67%** (2-run regression). `30a19f0` changed only the *label* (`MergeRate.window` → `"this run only (#N)"`, `dupe_repo.py:320-329`) and added a scope paragraph; the relabelled assertion is a deliberate relabel, not a weakened check — the window is still named, the rate/rows assertions are untouched, and a **new, stronger** assertion was added (`assert 'id="merge-rate-scope"' in text` and `assert "not an all-time rate" in text`) |
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
| 6 | Excluded listings out of default view, dimmed under `Show excluded`, one chip per firing rule with a per-rule count | ✓ VERIFIED | `queue_repo.py:431-440`, `_listing_row.html:42-44`; `tests/api/test_queue_excluded.py` (5, incl. the search×excluded composition and the run-wide count semantics). The count is run-wide by design (`_page_rule_counts` docstring); the chip's rule id/detail is unrendered — judged sufficient at UAT item 5 (SEED-001) |
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
| Full suite at HEAD `1bb7332` | `.venv/bin/python -m pytest -q` | 605 passed, 2 deselected in 113.57s | ✓ PASS |
| Migration regression (fixed) | `pytest -q tests/db/test_migration_contract.py::test_upgrade_populated_0001_to_head` | 1 passed | ✓ PASS |
| Migration regression (fail-first proof) | same test with pragma transiently set to `foreign_keys=ON` | 1 failed — `FOREIGN KEY constraint failed / [SQL: DROP TABLE runs]` | ✓ PROVEN |
| **Delta lane A** (dedup/merge/revert/merges) | `pytest -q tests/domain/test_dedup.py tests/db/test_dupes.py tests/pipeline/test_dedup_merge.py tests/pipeline/test_dedup_revert.py tests/api/test_merges_view.py` | **41 passed in 8.98s** (baseline 37; +4) | ✓ PASS |
| Filter/exclusions/capability lanes (B) — *baseline, not re-run* | `pytest -q tests/domain/test_filter.py tests/domain/test_criteria.py tests/db/test_exclusions.py tests/pipeline/test_filter_stage.py tests/pipeline/test_capability_surface.py tests/api/test_queue_excluded.py` | 62 passed in 42.51s | ✓ PASS (baseline) |
| Criteria/snapshot/form-to-run lanes (C) — *baseline, not re-run* | `pytest -q tests/db/test_search_repo_writes.py tests/api/test_searches_crud.py tests/pipeline/test_criteria_snapshot.py tests/api/test_criteria_capabilities.py tests/pipeline/test_single_search_run.py tests/test_config.py tests/pipeline/test_criteria_form_to_run.py` | 50 passed in 55.50s | ✓ PASS (baseline) |
| Search/signals/events/migration/UI/run lanes (D) — *baseline, not re-run* | `pytest -q tests/domain/test_search_query.py tests/db/test_queue_state.py tests/api/test_queue_search.py tests/api/test_queue_signals.py tests/db/test_listing_events.py tests/api/test_listing_events.py tests/test_stylesheet_coverage.py tests/db/test_migration_contract.py tests/api/test_run_history.py tests/api/test_run_reason.py tests/domain/test_run_reason.py` | 133 passed in 88.06s | ✓ PASS (baseline) |
| Stylesheet coverage (independent scan) | throwaway scan of `class="..."` tokens vs `app.css` | 163 tokens, 11 exempt, **0 missing**; negative-control test present | ✓ PASS |
| Lint | `.venv/bin/python -m ruff check app tests` | All checks passed! | ✓ PASS |

## Probe Execution

Step 7c: **SKIPPED** — no `scripts/*/tests/probe-*.sh` exist and Phase 2 declares no probe. (The scraper-survival probe is a Phase-1 deliverable; `docs/probes/2026-09-15-scraper-survival.md` is Phase-1 evidence.)

## Requirements Coverage

All 15 Phase-2 requirement IDs are claimed by the ten PLAN frontmatters and marked Complete in `REQUIREMENTS.md`. **No orphaned IDs and no unclaimed Phase-2 IDs. This delta changed no requirement accounting** — `bcb86c2 → 1bb7332` added no requirement, removed none, and re-mapped none.

| Requirement | Source Plan(s) | Description | Status | Evidence |
| ----------- | -------------- | ----------- | ------ | -------- |
| QUEUE-03 | 02-02, 02-04 | Same job on two sources merged, reversible audit | ✓ SATISFIED | `dedup_stage`, `dupe_repo.apply_merge`, `listing_dupes`; delta lane A (41), incl. the 3-way duplicate reproduction |
| QUEUE-04 | 02-06 | Revert an incorrect merge | ✓ SATISFIED | `revert_merge` + revert route; delta lane A |
| QUEUE-06 | 02-07 | Full-text search the queue | ✓ SATISFIED | `search_query`, `queue_repo` FTS branch; lane D |
| QUEUE-07 | 02-01, 02-07 | New-since-last-visit + stale | ✓ SATISFIED | `state_repo`, `_row_flags`; lane D |
| QUEUE-08 | 02-09 | Save/hide as append-only events | ✓ SATISFIED | `event_repo`, events route; lane D |
| QUEUE-09 | 02-06 | Merge rate + rows behind it | ✓ SATISFIED | latest-run window intact (not reverted); 33%/67% regression still asserts the window; label/scope clarified; delta lane A |
| CRIT-01 | 02-01, 02-03, 02-08 | Create/edit/delete named criteria | ✓ SATISFIED | `search_repo` write side, `searches.py`, `criteria.html`; lanes B/C |
| CRIT-02 | 02-05 | Criteria versioned for reproducibility | ✓ SATISFIED | `criteria_snapshot_json` before fetch; lane C |
| CRIT-03 | 02-08 | Enable/disable without delete | ✓ SATISFIED | toggle route, version semantics; lane C |
| FILT-01 | 02-02, 02-03, 02-05 | Deterministic reject before any LLM call | ✓ SATISFIED | `filter.evaluate`; no LLM import under `app/pipeline`; empty `llm_calls` |
| FILT-02 | 02-03, 02-05 | Every rejection records rule + why | ✓ SATISFIED | `listing_exclusions(rule_id, rule_kind, detail_json)`; lane B |
| FILT-03 | 02-07 | See why a specific listing was excluded | ✓ SATISFIED (chip judged sufficient at UAT item 5) | excluded toggle + chips; `detail_json` recorded, matched term not rendered; follow-on SEED-001 |
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
| `app/db/repositories/queue_repo.py` | 519-523 | `_page_rule_counts` count is run-wide (documented in the docstring), so a listing excluded once by a rule that fired N times run-wide shows `(N)`; pinned by `tests/api/test_queue_excluded.py::test_the_chip_count_is_grouped_over_the_run_not_per_row` | ℹ️ Info (product call) | Deliberate, pre-dates the UI review (introduced `32994d0`, pinned `01862d4`). UI-REVIEW blocker #2's premise ("per-row count") was consciously not adopted; judged sufficient at UAT item 5 |
| `Dockerfile` | 38-50 | No post-install assertion that `rapidfuzz` is present in the built image (02-SECURITY.md W-01) | ℹ️ Info (follow-up) | Manifest-level agreement is tested; image-level presence is not. De-risked by the operator smoke (a completed run imports the dedup module). See Advisory |
| `app/domain/dedup.py` | 151 | `fuzz.token_set_ratio` used as a diagnostic only | ℹ️ Info | Not a defect: explicitly non-deciding; the gate is `token_sort_ratio` (asserted) |
| `app/pipeline/run.py` | 708-716,737 | `criteria_compile` prepended then `stage_log[-12:]` truncates from the same end | ℹ️ Info | 02-REVIEW.md IN-04; latent only with >9 sources; not reachable with today's 2 adapters |
| `app/db/repositories/exclusion_repo.py` | 30-40,144-177 | `ExclusionRecord`/`exclusions_for_run` uncalled | ℹ️ Info | 02-REVIEW.md IN-02; `detail_json` has no UI consumer (see Advisory; closed as sufficient at UAT item 5) |
| `app/api/searches.py` etc. | — | No CSRF token on POSTs | ℹ️ Info | Accepted risk under the project's "Auth: none in v1" decision; every route carries the `current_user` seam |

Debt-marker gate: **no `TBD`/`FIXME`/`XXX`/`TODO`/`PLACEHOLDER` markers** anywhere under `app/`.
No stub/hollow implementations found: every rendered value traces to a real query (Level 4 above).

## Manual Verification — closed (UAT)

`02-UAT.md` records **5/5 items satisfied** (`passed: 5, pending: 0`), so there is **no outstanding human-verification item** and the automated `status` is `passed`. Phase completion itself comes from `/gsd-verify-work`, not from this report.

| # | Item | Result | Evidence |
| - | ---- | ------ | -------- |
| 1 | Tune θ against the first real corpus | **satisfied** — θ=88 retained | 2 real runs; latest run #6 fetched=100 with 6 live merges at scores `89.1 / 90.6 / 92.0 / 95.2 / 100.0 / 100.0`. True duplicates span 89.1–100 while unmerged near-misses span 70–97.9, so the distributions **overlap and no θ separates them**; the dangerous `Senior X ↔ X` pair is stopped by the grade guard, not by θ. Conclusion: θ=88 is approximately correct and not the discriminating lever. |
| 2 | Merge-rate band sanity check | **satisfied** — band does not transfer | Per-run figures are 6/100=6.0% (run #5, the run that merged) and 0/100=0.0% (run #6, steady state); the defensible figure is distinct un-reverted merges / distinct corpus = **6/104 ≈ 5.8%**, below the 10–15% research band — which the band's own "different market and query shape" caveat allows. G2 decision (a) implemented by `30a19f0`: keep the latest-run window, label its scope unmistakably. |
| 3 | Compose smoke | **satisfied** — operator-confirmed | `bash scripts/compose-smoke.sh` PASS on the Phase-2 image (`up -d --wait` healthy, `/health` db ok, a run completed, listings survived `restart`; revision `0002`, 104 listings, `ck_runs_reason`, `rapidfuzz 3.14.6`, `/`, `/merges`, `/runs`, `/searches` all 200). `.planning/WINDOWS.md` item #1 closed. **The operator is re-running it on the current build now** (`dfb7414` touched deploy config; `a51a133` touched `dedup.py`), so it remains operator-confirmed rather than machine-verifiable from the verifier sandbox — a watch item, not an open gap. |
| 4 | `rapidfuzz` pin sign-off | **satisfied** | Human answered the `blocking-human` checkpoint "approved" after seeing version 3.14.6, repo `rapidfuzz/RapidFuzz`, and a pre-compiled musllinux wheel; recorded in `02-02-SUMMARY.md`. |
| 5 | Excluded-listing chip vs SC2 | **satisfied** — judged sufficient for now | User decision recorded verbatim at UAT: *"I think it's enough for now, we can add more."* The capability is present (`detail_json` persisted; `rule_id` on `QueueRule`), so enriching the chip later is a template + one repository read. The distinct ask (browse-time `remote`/`location` filters) is captured as **SEED-001**. |

**UAT-surfaced defects and disposition:** G1 (host `.env` could never reach the container) → **FIXED** by `dfb7414` (recorded above). G2 (merge rate reads 0% in steady state) → **decision (a) implemented** by `30a19f0`: keep the latest-run window and label it unmistakably; the trailing-window option is a recorded alternative, not this phase's scope. G3 (a one-sided NULL location depressed the Tier-2 score, so a real cross-source duplicate was never merged) → **root cause confirmed and FIXED** by `a51a133`, re-verified in §02-04 above.

**Watch item (non-blocking):** the compose re-smoke on the current build is in flight. If it failed, that would be new information — but nothing in `dfb7414`/`a51a133`/`30a19f0` touches the migration or boot path, and the full suite is green at HEAD.

## Gaps Summary

**No must-have gap was found.** All 54 plan `must_haves.truths`, all five roadmap Success Criteria, all required artifacts (Levels 1–2), all key links (Level 3) and the dynamic data flows (Level 4) hold at HEAD `1bb7332`. All 15 Phase-2 requirement IDs are accounted for and satisfied. The migration defect remains genuinely fixed in the code path (`alembic/env.py`), proven fail-first. The `a51a133` dedup fix removes a real contradiction between the score and the location gate without weakening any dedup prohibition. The new stylesheet guard is non-vacuous. `ruff` is clean; no debt markers exist. **No truth's verdict changed in this delta.**

Observations that do **not** block the phase:

- **Advisory (02-SECURITY W-01):** the built image is not asserted to contain `rapidfuzz`; manifest agreement is tested. De-risked by the operator smoke; recommended follow-up is a Dockerfile import assertion. Not a phase-2 gap.
- **Advisory (FILT-03/SC2, closed at UAT item 5):** the persisted `listing_exclusions.detail_json` and the firing rule id are not rendered; the chip shows the rule kind and a run-wide per-rule count. FILT-02's recording requirement is fully met and tested; the product judgment is recorded as satisfied-for-now, with the follow-on captured as SEED-001.
- **Known deliberate residual (not re-reported):** `run.trigger` still renders as a raw enum on `/runs` (the status and reason now have `human_label`; the raw enum also survives in `data-*` attributes and row classes). Rendered-markup tests pin the raw strings; a product decision.
- **Info:** `02-VALIDATION.md`'s intro says "four genuine gaps were found" while the audit table lists two distinct gaps (G1/G2) spanning four requirement rows — a wording inconsistency, not a coverage defect.

Status is **passed**: automated verification is complete and green at HEAD, the 5/5 UAT items are satisfied, and no outstanding human-verification item remains. The phase's completion is still gated on `/gsd-verify-work`.

---

_Verified: 2026-09-16T18:04:08Z_
_Verifier: the agent (gsd-verifier)_
