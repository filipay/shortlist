---
phase: 07-assisted-apply-tracker
plan: 06
subsystem: api
tags: [pydantic, schema-coercion, screening, llm, gap-closure, apply]

# Dependency graph
requires:
  - phase: 07-assisted-apply-tracker
    provides: screening drafting stage (07-03) and the apply answers region (07-05)
provides:
  - Schema-local coercion of the recorded non-list screening payload shapes
  - A draft route that distinguishes an unusable model response from a valid-but-empty one
  - A drafting prompt that asks for JSON arrays, still interpolation-free
affects: [07-assisted-apply-tracker, apply, screening, llm]

# Actuals (#2632)
actuals:
  tokens: 4333
  tasks: 2
  commits: 2
  plan_head_before: 3127ce6834e2cc7a9ab26ae36267cf86238a3ed8

tech-stack:
  added: []
  patterns:
    - "Schema-local before-validators tolerate only the recorded shapes and let every other shape fail loudly"
    - "A stage's None and [] are two different user-facing states with distinct reasons and copy"

key-files:
  created:
    - tests/domain/test_screening_schema.py
    - tests/api/test_apply_draft_errors.py
  modified:
    - app/domain/schemas/screening.py
    - app/pipeline/draft.py
    - app/api/apply.py
    - tests/llm/test_salvage.py

key-decisions:
  - "G-07-2: coercion lives at the schema boundary, not in the global salvage allow-list — widening TOLERATED_SCHEMA_ERRORS would drop the whole answers field to its default and silently discard every drafted answer (the M1 hazard)"
  - "G-07-2: only the recorded shapes are coerced (a single answer-shaped mapping; a bare evidence-id string); a scalar answers value and an unknown key still fail loudly, so extra=\"forbid\" survives"
  - "G-07-2: the unusable-response copy is cause-neutral — it neither claims the model returned nothing nor that the backend was unreachable"

patterns-established:
  - "Before-validators that coerce by exact isinstance checks and return the value untouched otherwise"

requirements-completed: [APPLY-01]

coverage:
  - id: D1
    description: "A recorded non-list screening payload (answers as one object, evidence_ids as a bare string) validates with its answer intact; valid arrays validate unchanged; unknown keys and scalar answers still raise."
    requirement: APPLY-01
    verification:
      - kind: unit
        ref: "tests/domain/test_screening_schema.py"
        status: pass
      - kind: unit
        ref: "tests/llm/test_salvage.py#test_the_recorded_non_list_screening_payload_salvages_with_its_answer"
        status: pass
    human_judgment: false
  - id: D2
    description: "The draft route reports a schema-invalid/unusable response as drafting_failed and a valid-but-empty response as drafting_empty; the two carry different reasons and copy and neither deletes stored drafts."
    requirement: APPLY-01
    verification:
      - kind: integration
        ref: "tests/api/test_apply_draft_errors.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "DRAFT_SYSTEM_PROMPT requires the answers collection and evidence_ids to be JSON arrays, remaining a plain interpolation-free literal."
    requirement: APPLY-01
    verification:
      - kind: unit
        ref: "tests/pipeline/test_draft_stage.py#test_the_draft_system_prompt_is_a_frozen_constant_with_no_interpolation"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-10-05
status: complete
---

# Phase 07 Plan 06: G-07-2 gap closure Summary

**The screening schema now coerces the recorded non-list payload shapes without dropping answers, and the draft route reports an unusable model response distinctly from a genuinely empty one**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-10-05T22:38:18Z
- **Completed:** 2026-10-05T22:45:27Z
- **Tasks:** 2
- **Files modified:** 6 (4 modified, 2 created)

## Accomplishments

- A `ScreeningDraftResponse.answers` before-validator wraps a single answer-shaped mapping into a one-element list and a `ScreeningAnswer.evidence_ids` before-validator turns a bare comma-separated id string into a one-element list — so the exact `validation failed: Input should be a valid list` payload the UAT recorded now validates with every answer preserved.
- The coercion is deliberately narrow: only `None`, a mapping and a list/tuple are reshaped; a scalar `answers` value and an unknown key still raise. `extra="forbid"` and `TOLERATED_SCHEMA_ERRORS = frozenset({"missing", "int_parsing"})` are untouched.
- `draft_screening_answers` returning `None` (schema-invalid, transport error or cap refusal) is now a 502 `data-error="drafting_failed"` with cause-neutral copy; a valid empty list stays `data-error="drafting_empty"`. Neither branch calls `replace_for_listing`, so stored drafts survive both.
- `DRAFT_SYSTEM_PROMPT` instructs the model to return the answers collection and each `evidence_ids` as JSON arrays, and remains a plain literal with no interpolation.

## Task Commits

Each task was committed atomically:

1. **Task 1: Coerce the recorded non-list screening shapes at the schema boundary** - `9521696` (fix)
2. **Task 2: Harden the prompt and split the unusable/empty refusals** - `c993c7a` (fix)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified

- `app/domain/schemas/screening.py` - before-validators coercing the recorded answer/evidence-id shapes
- `tests/domain/test_screening_schema.py` - new: both directions (coerced golden payload, valid array, unknown key, scalar)
- `tests/llm/test_salvage.py` - golden recorded payload routed through production `_salvage`
- `app/pipeline/draft.py` - `DRAFT_SYSTEM_PROMPT` now asks for JSON arrays
- `app/api/apply.py` - two distinct 502 refusals (`drafting_failed` vs `drafting_empty`) and an updated route docstring
- `tests/api/test_apply_draft_errors.py` - new: both refusals driven through the real route with an overridden backend

## Decisions Made

- **Coerce at the schema boundary, never by widening the global salvage allow-list.** Adding `list_type` to `TOLERATED_SCHEMA_ERRORS` would substitute the `answers` field default (`[]`) for the entire field, silently erasing every drafted answer — the M1 hazard the exact allow-list exists to prevent. The exact-set test `test_the_tolerated_error_allow_list_is_exact` still passes.
- **Only the recorded shapes are tolerated.** A scalar `answers` value is left untouched so pydantic still fails loudly; the coercion cannot be mistaken for a general "fix any shape" pass.
- **Cause-neutral unusable copy.** The `drafting_failed` message names no cause (not "returned nothing", not "unreachable") because `None` conflates a schema mismatch, a transport error and a cap refusal.

## Deviations from Plan

None - plan executed exactly as written.

`tests/pipeline/test_draft_stage.py` is listed in the plan's `files_modified`, but the plan's Task 2 action only required that its prompt-interpolation test keep passing — it did (no edit needed).

## Issues Encountered

None.

## Threat Flags

None — no new network endpoints, auth paths, file-access patterns or schema changes at a trust boundary. T-07-06-01 (keep the allow-list exact), T-07-06-02 (coercion stops the repeat-failure loop) and T-07-06-03 (prompt stays a literal) are all satisfied; no packages installed (T-07-06-SC accepted).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- G-07-2's two `missing` nodes are addressed: the common non-list shape is coercively salvaged, and the schema-invalid case is told apart from the empty one in the user-facing copy.
- The live-model leg remains inherently uncovered by the default (backend-stubbed) lane; the recorded golden payload is the hermetic stand-in, per the gap's own note.
- Ready for the remaining gap-closure plans (G-07-1, G-07-3, G-07-4).

---

*Phase: 07-assisted-apply-tracker*
*Completed: 2026-10-05*

## Self-Check: PASSED
