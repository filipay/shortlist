---
phase: 05-ranking-core-value
plan: 01
subsystem: ranking
tags: [rubric, ranking, scores, migration, sqlalchemy, pydantic, opencode, htmx]

# Dependency graph
requires:
  - phase: 04-cv-fact-store-latex-compile-spike
    provides: the CV fact store, its stable enumerated IDs and the single fail-loud reader ranking cites as evidence
  - phase: 03-llm-port-structured-output
    provides: the LLM port (`complete_structured`), the pinned wire contract and the `llm_calls` audit writer
  - phase: 02-clean-filtered-queryable-queue
    provides: the hard-filter stage, the queue read model and the `scores`/`ranking_config`-adjacent schema
provides:
  - "app/domain/rubric.py — the six-factor rubric, RUBRIC_VERSION and the code-side weighted total"
  - "app/domain/schemas/ranking.py — the top-level-scalar RankingResponse and RequirementFit"
  - "migration 0004 + ranking_config + ranking_config_repo — the live global weights store"
  - "score_repo — the `scores` writer that never existed, one row per (listing, run, criteria_version)"
  - "app/pipeline/rank.py — one listing ranked end-to-end with CV-grounded evidence ids, detached"
  - "the queue row's read-time total and confidence-tier badges"
affects: [05-02, 05-03, 05-04, 06-cv-tailoring]

# Actuals (#2632) — same estimateTokens scale (chars/4 over the realized diff).
actuals:
  tokens: 39378
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Top-level-scalar structured-output schema: a nested object would make a truncated model response unrecoverable under `_tolerant_validator`"
    - "Per-factor sub-scores only, total computed in code under the weights in force (D-78/D-100)"
    - "Never-fabricate grounding: every evidence id is checked against `iter_fact_ids` before the write"
    - "Detached best-effort pipeline stage: the run finishes first, the ranking task scores survivors one at a time"
    - "D-94 optional posture: an absent fact store makes the stage a no-op with zero `llm_calls` rows"

key-files:
  created:
    - app/domain/rubric.py
    - app/domain/schemas/ranking.py
    - alembic/versions/0004_ranking_config.py
    - app/db/repositories/ranking_config_repo.py
    - app/db/repositories/score_repo.py
    - app/pipeline/rank.py
    - tests/domain/test_rubric.py
    - tests/db/test_score_repo.py
    - tests/pipeline/test_rank_stage.py
  modified:
    - app/db/models.py
    - app/db/repositories/queue_repo.py
    - app/pipeline/run.py
    - app/web/templates/html/_listing_row.html
    - static/vendor/app.css
    - tests/db/test_migration_contract.py
    - tests/db/test_skeleton_boot.py
    - tests/db/test_no_pii_columns.py

key-decisions:
  - "The ranking call writes exactly one `llm_calls` row per call — success AND failure — because D-12/T-05-03 require the audit row and plan 05-02's spend caps count those rows"
  - "`run_ranking` skips entirely when the configured fact store is absent (D-94's second condition), which is what keeps the two existing zero-LLM guards green in the hermetic lane; plan 05-02 owns the `ranking_enabled` switch and the D-102 guard rewrites"
  - "`factor_scores_json` drops every negative sub-score (the rubric's absent convention), so an all-sentinel response stores `{}` regardless of caller"
  - "The queue's displayed total is computed on read from stored sub-scores under the CURRENT weights; `scores.total_score` stays an audit snapshot (D-100)"

patterns-established:
  - "Pure rubric in `app/domain` with a hand-bumped version string stamped onto every score row (D-80)"
  - "A single-purpose singleton table (`ranking_config`, id = 1) rather than a generic key-value store"
  - "Grounding filter before the write, not in prose: a fabricated CV fact id is dropped, the requirement survives unevidenced"

requirements-completed: [RANK-01, RANK-02, RANK-03, RANK-05, RANK-06, RANK-07]

coverage:
  - id: D1
    description: "A pure six-factor rubric module (RUBRIC_VERSION 'v1', normalised weighted mean with a zero-denominator guard, confidence tiers) and a top-level-scalar RankingResponse with no total field"
    requirement: RANK-01
    verification:
      - kind: unit
        ref: "tests/domain/test_rubric.py"
        status: pass
      - kind: unit
        ref: "tests/test_import_discipline.py#test_domain_imports_no_io"
        status: pass
    human_judgment: false
  - id: D2
    description: "Migration 0004 creating the `ranking_config` singleton weights store, its tolerant/strict repository, and the `scores` writer (one row per listing/run/criteria, non-NULL criteria_version, per-factor sub-scores)"
    requirement: RANK-02
    verification:
      - kind: unit
        ref: "tests/db/test_score_repo.py"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_ranking_config_table_and_singleton_check"
        status: pass
      - kind: integration
        ref: "tests/db/test_orm_drift.py#test_orm_metadata_matches_migrated_schema"
        status: pass
    human_judgment: false
  - id: D3
    description: "One listing ranked end-to-end: one complete_structured call per listing, exactly one listing per prompt, CV-grounded evidence ids, per-listing failure isolation, the detached rank stage wired into run_pipeline, and the read-time total + confidence-tier badge on the queue row"
    requirement: RANK-05
    verification:
      - kind: unit
        ref: "tests/pipeline/test_rank_stage.py"
        status: pass
      - kind: unit
        ref: "tests/test_stylesheet_coverage.py"
        status: pass
    human_judgment: true
    rationale: "RANK-05's prose-quality half is a backstop the verifier cannot settle mechanically: whether each stored rationale actually reads as prose grounded in the listing's requirements and the cited CV facts (rather than a keyword restatement) is a judgment call. RANK-06's gap-presentation and RANK-07's live-model tolerance are also flagged assumptions this plan deliberately leaves unresolved."

duration: 28min
completed: 2026-09-22
status: complete
---

# Phase 5 Plan 1: Tracer — one listing scored end-to-end and visible on the queue row Summary

**A pure six-factor rubric, the live weights store (migration 0004), the `scores` writer that never existed, one detached `complete_structured` call per listing with CV-grounded evidence IDs, and a read-time total badge on the queue row**

## Performance

- **Duration:** 28 min
- **Started:** 2026-09-22T11:41:47Z
- **Completed:** 2026-09-22T12:09:27Z
- **Tasks:** 3
- **Files modified:** 17 (9 created, 8 modified)

## Accomplishments

- `app/domain/rubric.py` is pure and I/O-free: the six-factor tuple in D-82 order,
  `RUBRIC_VERSION = "v1"`, the normalised weighted mean that re-normalises over
  present factors and returns `None` on a zero denominator, and confidence tiers
  derived from the factor count rather than hard-coded thresholds.
- `RankingResponse` uses six top-level scalars with `-1.0` as the absent sentinel
  and no `total` field — the shape that keeps a truncated response salvageable and
  keeps the total in code (D-78).
- Migration 0004 creates `ranking_config` as a single row pinned to `id = 1`; the
  repository falls back to the rubric defaults when the row is absent and rejects
  an unknown key or a negative weight before any SQL.
- `score_repo` writes exactly one row per `(listing, run, criteria_version)` with
  the per-factor decomposition, a non-NULL `criteria_version`, and the provider and
  model identity — and never an `agent` column.
- One listing travels prompt assembly → `complete_structured` → CV grounding → a
  `scores` row → a read-time total on the queue row. A fabricated evidence id is
  dropped before the write while the listing still scores.
- The rank stage is detached and best-effort: the run completes normally, a ranking
  start failure is recorded, and an absent fact store makes the whole stage a no-op
  with zero `llm_calls` rows.

## Task Commits

Each task was committed atomically:

1. **Task 1: Pure rubric and the top-level-scalar ranking schema** - `3807511` (feat)
2. **Task 2: The live weights store (migration 0004) and the scores writer** - `46a436f` (feat)
3. **Task 3: One listing ranked end-to-end, wired into run_pipeline and visible on the queue row** - `443eddd` (feat)
4. **Formatting normalisation of the phase-5 modules** - `c7b8b9c` (style)

**Plan metadata:** `PENDING` (docs: complete plan)

## Files Created/Modified

- `app/domain/rubric.py` - the six-factor rubric, labels, prose definitions, `RUBRIC_VERSION`, `DEFAULT_WEIGHTS`, `weighted_total`, `confidence_tier`, `present_factors`
- `app/domain/schemas/ranking.py` - `RankingResponse` (six bounded top-level scalars, no total) and `RequirementFit`
- `alembic/versions/0004_ranking_config.py` - the additive `ranking_config` table, head becomes `0004`
- `app/db/repositories/ranking_config_repo.py` - `read_weights` (rubric-default fallback) and `write_weights` (validated singleton upsert)
- `app/db/repositories/score_repo.py` - `ScoreRecord`, `upsert_score`, `latest_for_listings`, `read_score_for_listing`
- `app/pipeline/rank.py` - `RANK_SYSTEM_PROMPT`, `build_ranking_parts`, `criteria_version_for_run`, `rank_listing`, `run_ranking`, `start_ranking_task`, `_BACKGROUND_TASKS`
- `app/db/models.py` - the `RankingConfig` ORM model and `ck_ranking_config_singleton`
- `app/pipeline/run.py` - the `llm` keyword and the detached rank-stage call site after the hard filter
- `app/db/repositories/queue_repo.py` - `QueueRow.total_score` / `confidence_tier` / `factor_scores` and the read-time total under current weights
- `app/web/templates/html/_listing_row.html` - the score and confidence-tier badges (nothing rendered when unscored)
- `static/vendor/app.css` - rules for `badge-score` and the three tier classes
- `tests/domain/test_rubric.py`, `tests/db/test_score_repo.py`, `tests/pipeline/test_rank_stage.py` - new coverage
- `tests/db/test_migration_contract.py`, `tests/db/test_skeleton_boot.py`, `tests/db/test_no_pii_columns.py` - the three pinned-revision guards agree on head `0004`

## Decisions Made

- The ranking call writes exactly one `llm_calls` row per call, success and failure
  alike: D-12/T-05-03 require the audit row, and plan 05-02's spend caps count those
  rows, so a success-only-missing row would make a ceiling invisible.
- `run_ranking` implements D-94's "fact store absent" skip; this is the mechanism
  that keeps the two existing zero-LLM guards green without editing them. Plan 05-02
  adds `ranking_enabled` and owns the D-102 guard rewrites.
- `score_repo` drops every negative sub-score (the rubric treats every negative as
  absent), so `factor_scores_json` is `{}` for an all-sentinel response regardless
  of caller — RANK-02's empty case is enforced at the storage layer too.
- The queue's displayed total is computed on read from stored sub-scores under the
  current weights; `scores.total_score` remains an audit snapshot (D-100).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Successful ranking calls also write an `llm_calls` row**
- **Found during:** Task 3 (the ranking stage)
- **Issue:** The plan's Task 3 action spelled out the failure-path audit row but not
  the success path. Without a success row, plan 05-02's per-run and rolling-24h caps
  (`llm_totals_for_run` / `rank_calls_since`, which count `llm_calls` rows) could
  never fire, and D-12/T-05-03 ("every ranking call writes exactly one `llm_calls`
  row") would be violated.
- **Fix:** `rank_listing` records exactly one `purpose="rank"` row on every call via
  `record_llm_call`, with `status` from the result (`ok` on success).
- **Files modified:** `app/pipeline/rank.py`
- **Verification:** `tests/pipeline/test_rank_stage.py::test_failed_listing_is_isolated`
  asserts two audited calls for two listings.
- **Committed in:** `443eddd`

**2. [Rule 2 - Missing Critical] The D-94 fact-store-absent skip**
- **Found during:** Task 3 (wiring the stage into `run_pipeline`)
- **Issue:** Launching the stage unconditionally would make the default hermetic lane
  attempt ranking (the default backend is a real `OpenCodeServerBackend` when a test
  does not thread one), breaking the two D-102 guards — which are not in this plan's
  `files_modified`.
- **Fix:** `run_ranking` returns immediately, writing nothing, when the configured
  fact store is missing or unreadable (`settings.cv_dir / "cv.yaml"`). This is
  D-94's own second condition; plan 05-02 adds the `ranking_enabled` first check.
- **Files modified:** `app/pipeline/rank.py`
- **Verification:** full hermetic suite green, including
  `tests/pipeline/test_finish_llm_counters.py::test_a_pipeline_run_writes_zero_llm_calls`
  and `tests/pipeline/test_filter_stage.py` line 197.
- **Committed in:** `443eddd`

**3. [Rule 2 - Missing Critical] `factor_scores_json` drops negative sub-scores at the storage boundary**
- **Found during:** Task 2 (the scores writer)
- **Issue:** The plan's RANK-02 "empty" truth requires `{}` when no factor is present,
  but the writer originally stored whatever mapping it was handed, so a `-1.0`
  sentinel passed by a careless caller would have been persisted.
- **Fix:** `_factor_payload` (and the read-side `_factor_scores`) accept only values
  `>= 0.0`, matching `rubric.present_factors`.
- **Files modified:** `app/db/repositories/score_repo.py`
- **Verification:** `tests/db/test_score_repo.py::test_a_present_zero_is_stored_as_zero_and_not_conflated_with_absent`
- **Committed in:** `46a436f` (initial), `c7b8b9c` (format)

**4. [Rule 3 - Blocking] Test/assembly seams beyond the plan's literal signatures**
- **Found during:** Task 3 (writing the stage tests)
- **Issue:** The stage could not be exercised without a real `cv.yaml`, and
  `upsert_score`'s declared write surface (`search_id`, `backend`, `strengths_json`)
  exceeded its literal parameter list.
- **Fix:** `run_ranking` gained optional `facts` and `now` injection parameters;
  `upsert_score` gained optional `search_id`, `backend` and `strengths` keywords.
  Both are additive and production defaults are unchanged.
- **Files modified:** `app/pipeline/rank.py`, `app/db/repositories/score_repo.py`
- **Verification:** `tests/pipeline/test_rank_stage.py` passes.
- **Committed in:** `46a436f`, `443eddd`

**5. [Rule 3 - Blocking] Separate ruff-format commit; `f"` acceptance grep interpreted**
- **Found during:** Task 3 (linting)
- **Issue:** The repo's ruff config selects `UP032`, which *prefers* f-strings, so the
  `.format()` rewrite that would satisfy the Task 3 acceptance grep literally is
  auto-reverted by the project's own lint rule. The `.venv-host/bin/python` the plan's
  `<verify>` commands name is broken (missing `pydantic_core._pydantic_core`), so the
  harness's `.venv/bin/python` was used.
- **Fix:** Kept f-strings (repo idiom) and added
  `test_the_system_prompt_is_a_frozen_constant_with_no_interpolation`, which proves
  `RANK_SYSTEM_PROMPT` is a plain literal with no `{`, no `%s` and no `f`-prefix —
  the substantive property the acceptance criterion names. Formatting-only changes to
  Task 1/2 files were isolated in `style(05-01)`.
- **Files modified:** `app/pipeline/rank.py`, `tests/pipeline/test_rank_stage.py`
- **Verification:** `ruff check` clean on all touched files; the new test passes.
- **Committed in:** `c7b8b9c`, `443eddd`

---

**Total deviations:** 5 auto-fixed (4 missing-critical/blocking, 1 formatting)
**Impact on plan:** No scope creep. Every deviation is either a correctness requirement
the plan implied (D-12 audit rows, RANK-02 empty, D-94 posture) or a testability seam.

## Issues Encountered

- The plan's `<verify>` interpreter `.venv-host/bin/python` is unusable (its
  `pydantic_core` native module is absent). All verification ran under
  `.venv/bin/python`, matching the harness's declared `test` command.
- `app/domain/schemas/ranking.py` was unchanged by `ruff format`, so it does not
  appear in the style commit.

## Known Stubs

None. The ranking stage is fully wired: no hardcoded empty values flow to the UI, no
placeholder text, and no component receives mock data. `QueueRow.total_score` is
`None` for an unscored listing by design and the template renders nothing for it.

## Threat Flags

None beyond the plan's threat model. `RANK_SYSTEM_PROMPT` is a frozen constant with a
dedicated interpolation-free test (T-05-01); `tools=()` is asserted on every call
(T-05-02); every call writes one `llm_calls` row with the D-52 status and the
provider/model/agent identity (T-05-03); the badge carries only a rounded float and a
CHECK-validated tier string, escaped by Jinja autoescape with no `|safe` (T-05-04).

## Next Phase Readiness

- Plan 05-02 can build on `run_ranking` directly: the reserve-then-call accounting,
  the `ranking_enabled` switch and the D-102 guard rewrites all have their seams in
  place, and the `llm_calls` row per call is what its cap reads depend on.
- Plan 05-03's detail page can read `score_repo.read_score_for_listing`, which already
  returns the rationale, the per-factor sub-scores and the grounded requirement list.
- Plan 05-04's ranked queue ordering can use `QueueRow.factor_scores` plus
  `ranking_config_repo.read_weights` to compute the read-time total for sorting.
- Open (carried from the plan's flagged assumptions): RANK-06's gap-presentation
  question and RANK-07's live-model score-stability tolerance remain unresolved by
  design.

## Self-Check: PASSED

- All nine created files exist on disk.
- All four commits (`3807511`, `46a436f`, `c7b8b9c`, `443eddd`) exist in the history.
- `commits: 4` was measured from the plan ledger
  (`plan_head_before = 4f21af83f8ec666a623843812e2d126a14afd20f`).

---
*Phase: 05-ranking-core-value*
*Completed: 2026-09-22*
