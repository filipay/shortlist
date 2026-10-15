---
phase: 07-assisted-apply-tracker
plan: 03
subsystem: [pipeline, verify, database]
tags: [screening, grounding, fabrication-boundary, pydantic, sqlalchemy, llm-calls, budget-ceiling]

# Dependency graph
requires:
  - phase: 07-assisted-apply-tracker
    provides: "migration 0006's screening_drafts/apply_config tables (07-01) — the store this plan writes"
  - phase: 06-tailoring-verification
    provides: "the llm_calls ledger + reserve-then-call ceiling (D-119); the CV fact-id set (app.domain.cv.iter_fact_ids); the digit-core tokeniser (app.verify.numbers.digit_cores); the advisory band (app.verify.grounding.band_for)"
provides:
  - "app/domain/schemas/screening.py: ScreeningAnswer / ScreeningDraftResponse, extra=forbid"
  - "app/verify/screening.py: ground_screening_answers — deterministic, LLM-free grounding (byte-exact evidence-id intersection + novel-digit containment), advisory band never flips the warning state"
  - "app/db/repositories/screening_draft_repo.py: the per-listing draft store (read/replace-all/delete-one/delete-all), replace atomic in one SAVEPOINT"
  - "app/pipeline/draft.py: draft_screening_answers — ONE audited structured call on the shared rolling-24h ceiling, returning grounded verdicts"
  - "app/config.py: apply_drafting_enabled — the operator off switch, read by drafting_skip_reason"
affects: [07-05-drafted-answers]

# Actuals (#2632) — pairs with the plan's estimate (70000 tokens, 3 tasks, low confidence).
actuals:
  tokens: 13770
  tasks: 3
  commits: 3
  plan_head_before: b1905c34d3a46f3ffdeb75a9a31a27acf48bafb8

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One deterministic checker, two independent findings: byte-exact id intersection (structural) plus novel-digit containment (numeric), each a warning naming its offender; the advisory fuzzy band rides along and never flips the warning state"
    - "The grounding corpus is the model-visible CV facts text (reusing rank._cv_facts_text) plus the listing text, tokenised by the SAME digit_cores the verifier uses — one tokeniser, no second implementation"
    - "An interactive drafting call shares the Phase-5 rolling-24h ceiling and reuses purpose='tailor' rather than widening ck_llm_calls_purpose (accepted A2 trade-off)"

key-files:
  created:
    - app/domain/schemas/screening.py
    - app/verify/screening.py
    - app/db/repositories/screening_draft_repo.py
    - app/pipeline/draft.py
    - tests/verify/test_screening.py
    - tests/db/test_screening_draft_repo.py
    - tests/pipeline/test_draft_stage.py
  modified:
    - app/config.py
    - tests/test_config.py

key-decisions:
  - "The grounding check is structurally anchored, never lexically: evidence ids are intersected byte-exact against iter_fact_ids, and numbers are compared as digit cores — so a valid answer that mentions another entity's id/name cannot false-fail (CONVENTIONS rule 1)"
  - "facts_present_in is deliberately NOT reused: it asks whether EVERY enumerable fact is present, the wrong direction for one short answer, and would false-fail essentially every legitimate answer"
  - "The advisory lexical band is a label only and never flips `unsupported`/warnings — a fuzzy ratio on a block decision is a false-positive machine"
  - "replace_for_listing deletes and inserts inside ONE session.begin_nested() SAVEPOINT, so an invalid insert (unknown listing FK) rolls the whole set back without poisoning the caller's transaction"
  - "The drafting call reuses purpose='tailor' on the llm_calls ledger (no stage column exists); the accepted A2 trade-off is recorded at the call site rather than widening the CHECK constraint"
  - "drafting_skip_reason() reads apply_drafting_enabled, so the operator switch has a reader now rather than being dead configuration until the 07-05 route lands"

patterns-established:
  - "A model-produced free-text answer is grounded by a pure app/verify checker BEFORE it can be stored; the finding is a value (unsupported + named warnings), never an exception"
  - "A fabricated narrative with no novel digit passes the numeric check by design — stated as runtime-visible warning policy in the module docstring, never asserted as a guarantee (CONVENTIONS rule 6)"

requirements-completed: [APPLY-01]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "The typed screening contract (extra=forbid) and the deterministic grounding check: grounded answers pass clean; an unknown evidence id and a novel digit core each warn naming the offender; a legitimate paraphrase that reuses a known digit passes clean"
    requirement: APPLY-01
    verification:
      - kind: unit
        ref: "tests/verify/test_screening.py#test_a_grounded_answer_passes_clean"
        status: pass
      - kind: unit
        ref: "tests/verify/test_screening.py#test_an_unknown_evidence_id_is_flagged_and_named"
        status: pass
      - kind: unit
        ref: "tests/verify/test_screening.py#test_a_fabricated_metric_digit_is_flagged_and_named"
        status: pass
      - kind: unit
        ref: "tests/verify/test_screening.py#test_a_legitimate_paraphrase_with_a_known_digit_passes_clean"
        status: pass
      - kind: unit
        ref: "tests/verify/test_screening.py#test_embedding_another_entitys_identifier_does_not_false_fail"
        status: pass
    human_judgment: false
  - id: D2
    description: "The per-listing draft store: replace-all is atomic per listing, an empty set clears the rows, delete_draft removes exactly one row, and a failed insert rolls the SAVEPOINT back without poisoning the outer transaction"
    requirement: APPLY-01
    verification:
      - kind: unit
        ref: "tests/db/test_screening_draft_repo.py#test_a_second_replace_replaces_and_never_accumulates"
        status: pass
      - kind: unit
        ref: "tests/db/test_screening_draft_repo.py#test_an_empty_draft_set_clears_the_listing"
        status: pass
      - kind: unit
        ref: "tests/db/test_screening_draft_repo.py#test_delete_draft_removes_only_the_named_row"
        status: pass
      - kind: unit
        ref: "tests/db/test_screening_draft_repo.py#test_an_unknown_listing_fk_rolls_back_without_poisoning_the_outer_transaction"
        status: pass
    human_judgment: false
  - id: D3
    description: "The drafting stage and its switch: one call per request, one audit row per attempt (purpose=tailor, run_id=None), the ceiling enforced before the call, a transport error recorded as its class name only, and apply_drafting_enabled guarded as a switch not a ceiling"
    requirement: APPLY-01
    verification:
      - kind: unit
        ref: "tests/pipeline/test_draft_stage.py#test_exactly_one_call_carries_the_listing_questions_and_cv_facts"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_draft_stage.py#test_a_successful_call_writes_one_row_with_a_null_run_id"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_draft_stage.py#test_a_cap_refusal_writes_one_budget_row_and_makes_no_call"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_draft_stage.py#test_a_raised_backend_error_writes_one_class_only_row_and_returns_none"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_the_apply_switch_is_not_a_ceiling"
        status: pass
    human_judgment: false
  - id: D4
    description: "The honesty boundary itself: the two stated residuals (a numberless fabrication passes the numeric check; a computed number that never appears verbatim is conservatively flagged) are an accepted warning policy, and the drafting prompt's copy-only posture is what covers the residual"
    verification: []
    human_judgment: true
    rationale: "Whether the residual policy and its runtime-visible wording are adequate honesty signalling is a judgement call no automated assertion proves; the module docstring states both residuals explicitly (CONVENTIONS rule 6), and the human must accept the numeric check is a warning policy, not a guarantee."

# Metrics
duration: ~13 min
completed: 2026-09-30
status: complete
---

# Phase 7 Plan 3: Grounded screening-answer drafting Summary

**A typed `extra="forbid"` screening contract, a deterministic LLM-free grounding check (byte-exact evidence-id intersection + novel-digit containment) whose warnings never fire false, an atomic per-listing draft store, and one audited drafting call on the shared rolling-24h ceiling behind an operator switch.**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-09-30T16:29:50Z
- **Completed:** 2026-09-30T16:42:34Z
- **Tasks:** 3
- **Files modified:** 9 (7 created, 2 modified)

## Accomplishments
- `app/domain/schemas/screening.py` adds `ScreeningAnswer` (question, answer, `evidence_ids`) and `ScreeningDraftResponse` (answers), both `extra="forbid"` — a typo'd or extra key fails the call rather than being silently dropped.
- `app/verify/screening.py`'s `ground_screening_answers` is the phase's fabrication boundary and the only genuinely new logic: evidence ids are intersected byte-exact with `iter_fact_ids`, and answer digits are tokenised with the SAME `app.verify.numbers.digit_cores` as the sources (the model-visible CV facts text plus the listing text). An unknown id or a novel digit core produces a warning naming the offender; `unsupported` is exactly "any warning was raised". The advisory fuzzy band rides along as a label and never flips the warning state.
- `app/db/repositories/screening_draft_repo.py` gives `screening_drafts` its first writer: `read_for_listing` (ordered `(created_at, id)`), `replace_for_listing` (delete + insert in ONE `begin_nested()` SAVEPOINT), `delete_for_listing`, and `delete_draft` scoped to its listing. It never commits.
- `app/pipeline/draft.py`'s `draft_screening_answers` makes exactly ONE `complete_structured(ScreeningDraftResponse)` call: a frozen `DRAFT_SYSTEM_PROMPT`, `tools=()`, and the CV facts, listing and questions in `parts` only. It reserves on the shared rolling-24h ceiling BEFORE the call (a refusal writes one `budget_exceeded` row and returns without calling), records exactly one `llm_calls` row per attempt (`purpose="tailor"`, `run_id=None`; a transport error records the class name only), releases the slot in `finally`, and returns the grounded verdicts.
- `app/config.py` adds `apply_drafting_enabled` as the operator off switch (deliberately not a ceiling), read by `drafting_skip_reason()`; `tests/test_config.py` guards it in the surface scan and pins its absence from `LIMIT_FIELDS`.

## Task Commits

Each task was committed atomically:

1. **Task 1: The drafting contract and the deterministic grounding check** - `dbd1209` (feat)
2. **Task 2: The per-listing draft store** - `4289008` (feat)
3. **Task 3: The drafting stage and its configuration switch** - `241e234` (feat)

**Plan metadata:** docs commit follows.

## Files Created/Modified
- `app/domain/schemas/screening.py` - `ScreeningAnswer` / `ScreeningDraftResponse`, both `extra="forbid"`
- `app/verify/screening.py` - `ground_screening_answers` and `ScreeningVerdict`; deterministic, LLM-free; residuals stated in the docstring
- `app/db/repositories/screening_draft_repo.py` - `ScreeningDraftInput`, `ScreeningDraftRecord`, `read_for_listing`, `replace_for_listing`, `delete_for_listing`, `delete_draft`
- `app/pipeline/draft.py` - `draft_screening_answers`, `build_screening_parts`, `DRAFT_SYSTEM_PROMPT`, `drafting_skip_reason`
- `app/config.py` - `apply_drafting_enabled: bool = True`
- `tests/verify/test_screening.py` - both directions + the CONVENTIONS rule-4 mutation test (23 tests)
- `tests/db/test_screening_draft_repo.py` - the store contract (8 tests)
- `tests/pipeline/test_draft_stage.py` - the call shape, audit trail, ceiling, switch (11 tests)
- `tests/test_config.py` - the Phase-7 switch surface + absence guards

## Decisions Made
- **Structural anchoring, not lexical** (CONVENTIONS rule 1): the checker intersects ids byte-exact and compares digit cores, so mentioning another entity's id/name in a valid answer cannot false-fail it. `facts_present_in` is deliberately not reused — it answers "are ALL the facts present?", the wrong direction for one short answer.
- **The advisory band is a label only**: it reuses `band_for` with the existing uncalibrated `tailoring_grounding_*` thresholds and never touches `unsupported` or the warnings.
- **The grounding corpus is the model-visible facts text**: `app/verify/screening.py` reuses `rank._cv_facts_text` via a documented cross-module private import (the same pattern `app.pipeline.tailor` already uses). A duplicated renderer would drift from the prompt silently; the two residuals are stated in prose instead of hidden.
- **One rolling-24h ceiling, no new numeric knob** (D-119): drafting shares `ranking_max_calls_per_day` and reuses `purpose="tailor"` because `llm_calls` has no stage column. The accepted A2 trade-off (drafting spend is indistinguishable from tailoring spend) is recorded at the call site.
- **Atomic replace per listing**: delete + insert share one SAVEPOINT, so a bad insert cannot leave a half-written set or poison the caller's transaction.

## Deviations from Plan

### Auto-added Issues

**1. [Rule 2 - Missing Critical] Added `drafting_skip_reason()` so the switch has a reader**
- **Found during:** Task 3 (the config switch)
- **Issue:** The plan adds `apply_drafting_enabled` as "the operator off switch" but its Task-3 `draft.py` spec lists only `draft_screening_answers`. An operator switch that no code reads is dead configuration, and the plan explicitly says to mirror `tailoring_enabled` — which is read by `tailoring_skip_reason`.
- **Fix:** Added `drafting_skip_reason()` (the exact counterpart of `tailoring_skip_reason`: switch first, then fact store) so the switch is load-bearing now; the 07-05 route consumes it.
- **Files modified:** `app/pipeline/draft.py`
- **Verification:** `tests/pipeline/test_draft_stage.py::test_drafting_disabled_skips_before_any_filesystem_read` passes
- **Committed in:** `241e234` (Task 3)

---

**Total deviations:** 1 auto-added (1 missing critical).
**Impact on plan:** The addition completes the switch the plan introduced; no scope creep, no behavioural change to the three named deliverables.

## Issues Encountered
None. The plan verification lane and the full suite were green on the first complete run (initial ruff `I001`/`F401` on the new verifier module were trivially fixed before the Task-1 commit).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 07-05 (drafted answers) can now wire the package page: load `CvFacts`, call `draft_screening_answers`, persist the verdicts via `replace_for_listing` (mapping `grounded_evidence_ids` → `evidence_json` and `unsupported` → the column), and render `warnings` per answer. `delete_draft` is the per-answer delete.
- The stage deliberately returns verdicts (not persisted rows); persistence and the UI are the route's job, so no write happens without an explicit user action.
- Migration head stays `0006`; no schema change. Opening a stored draft makes zero LLM calls — only `draft_screening_answers` does.

## Self-Check: PASSED

- All 7 created files exist on disk (`[ -f ]` verified).
- All three task commits exist (`dbd1209`, `4289008`, `241e234`); measured 3 commits from `b1905c3`.
- Plan verification lane: `pytest -q tests/verify/test_screening.py tests/db/test_screening_draft_repo.py tests/pipeline/test_draft_stage.py tests/test_config.py tests/test_import_discipline.py` — **76 passed**.
- Full suite: `pytest -q` — **1608 passed, 14 deselected, 2 xfailed**.
- `ruff check` on all five source modules and all four touched test files — clean.
- `.venv/bin/python -m compileall -q app` — clean.

---
*Phase: 07-assisted-apply-tracker*
*Completed: 2026-09-30*
