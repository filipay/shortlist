---
phase: 07-assisted-apply-tracker
plan: 12
subsystem: llm
tags: [pydantic, coercion, structured-output, screening, tailoring, gap-closure, g-07-7]

requires:
  - phase: 07-assisted-apply-tracker
    provides: the screening schemas + drafting route/stage and the G-07-2 schema-local coercion (07-03, 07-05, and the G-07-2 fix) this plan generalises
provides:
  - "one shared, pure coercion module (`app/domain/schemas/_coerce.py`) unwrapping the model's single-key `{\"item\": ...}` array wrapper on every list-typed wire field"
  - "an honest fail-loud boundary: only a single-key wrapper Mapping is unwrapped; a scalar, a multi-key mapping and an unknown/stray key still raise"
affects: [07-uat, apply-drafting, tailoring, ranking]

actuals:
  tokens: 5282
  tasks: 3
  commits: 3
plan_head_before: a1ea0333cc0c7d5f94a24584aaafac37b4f9dd01

tech-stack:
  added: []
  patterns:
    - "invalid->valid shape coercion at the schema boundary, delegating to one shared pure helper rather than per-schema duplicate logic"

key-files:
  created:
    - app/domain/schemas/_coerce.py
    - tests/domain/test_coerce.py
  modified:
    - app/domain/schemas/screening.py
    - app/domain/schemas/ranking.py
    - app/domain/cv.py
    - tests/domain/test_screening_schema.py
    - tests/llm/test_salvage.py
    - tests/api/test_apply_draft_errors.py

key-decisions:
  - "The fix lives at the coercion boundary, not in the salvager: `TOLERATED_SCHEMA_ERRORS` stays byte-unchanged `{\"missing\", \"int_parsing\"}`. Widening it to tolerate `list_type` would substitute the field default and silently discard every drafted answer (the M1 hazard)."
  - "Only a SINGLE-key wrapper Mapping is unwrapped (a loop, so `{\"item\": {\"item\": [...]}}` resolves). A scalar, a multi-key mapping, and a stray top-level key alongside `answers` still raise — `extra=\"forbid\"` (A4) is not weakened. This is a deliberate deviation from the debug report's looser 'absorb the stray top-level item' wording."
  - "One pure helper (`app/domain/schemas/_coerce.py`) is shared by `ScreeningAnswer.evidence_ids`, `ScreeningDraftResponse.answers`, `Suggestion.evidence_ids`, `GapFinding.evidence_ids` and `RankingResponse.requirements` — one behaviour, no duplicate logic."
  - "`app/domain/cv.py`'s purity docstring was amended to name the one added pure sibling import (`app.domain.schemas._coerce`, itself I/O-free) so the claim stays true (CONVENTIONS rule 6)."

patterns-established:
  - "Shared-boundary coercion: when a provider emits an invalid-but-recognisable shape for a typed field, centralise the invalid->valid unwrap in one pure helper every wire-adjacent schema delegates to; leave every other shape to pydantic's loud failure."

requirements-completed: [APPLY-01]

coverage:
  - id: D1
    description: "The literal captured payload — `answers` a 4-element array whose `evidence_ids` are `{\"item\": [17 ids]}`, `{\"item\": \"exp/self-employed-2026\"}`, `\"\"`, `{\"item\": [3 ids]}` — validates to 4 answers with 17/1/0/3 evidence ids through the production `_salvage`."
    requirement: APPLY-01
    verification:
      - kind: unit
        ref: "tests/llm/test_salvage.py#test_the_literal_captured_payload_salvages_to_four_answers"
        status: pass
    human_judgment: false
  - id: D2
    description: "POST `/listings/<id>/apply/draft` with that payload driving the production `_salvage` returns 200 and persists 4 rows — not the 502 `drafting_failed` refusal."
    requirement: APPLY-01
    verification:
      - kind: integration
        ref: "tests/api/test_apply_draft_errors.py#test_the_literal_wrapped_payload_persists_four_rows"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every other malformed shape still fails loudly: a scalar `answers`, an unknown key, `evidence_ids={\"nope\": 1}`, a two-key mapping, and a stray top-level `item` alongside `answers` all raise `ValidationError`."
    requirement: APPLY-01
    verification:
      - kind: unit
        ref: "tests/domain/test_screening_schema.py#test_an_unrecognised_mapping_evidence_ids_still_fails_loudly"
        status: pass
      - kind: unit
        ref: "tests/domain/test_screening_schema.py#test_a_multi_key_mapping_evidence_ids_still_fails_loudly"
        status: pass
      - kind: unit
        ref: "tests/domain/test_screening_schema.py#test_a_stray_top_level_key_alongside_answers_still_fails_loudly"
        status: pass
      - kind: unit
        ref: "tests/domain/test_screening_schema.py#test_a_scalar_answers_value_still_fails_loudly"
        status: pass
      - kind: unit
        ref: "tests/domain/test_screening_schema.py#test_an_unknown_key_still_fails_loudly"
        status: pass
    human_judgment: false
  - id: D4
    description: "The shared helper is wired on every named wire-adjacent list-typed field: a nested wrapper unwraps, and CV/ranking wrappers unwrap (Suggestion, GapFinding, RankingResponse.requirements)."
    requirement: APPLY-01
    verification:
      - kind: unit
        ref: "tests/domain/test_coerce.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "The pre-fix code was demonstrably RED on the new positive tests with the recorded `list_type` error at `('answers', 0, 'evidence_ids')` before any `app/` change."
    verification:
      - kind: other
        ref: "pytest run before Task 2: 5 failed (list_type) / test_the_literal_wrapped_payload_persists_four_rows errored on the same ValidationError"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-10-12
status: complete
---

# Phase 07 Plan 12: G-07-7 single-key array-wrapper unwrap Summary

**Draft answers now returns four usable rows when the provider wraps a list-typed field as `{"item": ...}` — via one shared pure coercion helper wired across the screening, cv and ranking wire schemas, with every other malformed shape still failing loudly and `TOLERATED_SCHEMA_ERRORS` byte-unchanged.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-10-12T11:21:31Z
- **Completed:** 2026-10-12T11:33:00Z
- **Tasks:** 3
- **Files modified:** 8 (2 created, 6 modified)

## Accomplishments
- The literal captured drafting payload (the `llm_calls` id-55 shape) now validates through the production `_salvage` to 4 answers with 17/1/0/3 evidence ids, and the `/apply/draft` route persists 4 rows with status 200 instead of the reported 502 `drafting_failed`.
- `app/domain/schemas/_coerce.py` is the one shared, pure coercion module: `unwrap_single_key_mapping` (looping, so nested wrappers resolve), `coerce_str_list`, `coerce_mapping_list`. The screening, cv and ranking list-typed fields now delegate to it — one behaviour, no duplicated logic.
- The fail-loud boundary is pinned: a scalar `answers`, an unknown key, `evidence_ids={"nope": 1}`, a two-key mapping and a stray top-level `item` alongside `answers` all still raise.
- `app/llm/opencode_server.py` is byte-unchanged; `TOLERATED_SCHEMA_ERRORS` remains `{"missing", "int_parsing"}` (M1 hazard avoided). No new dependency, no migration, no schema-send change.
- `app/domain/cv.py`'s purity docstring now names its one pure sibling import, so the claim stays true.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add the held-out fixture and the fail-loud cases (RED)** - `c807288` (test)
2. **Task 2: Extract the shared unwrap helper and wire the screening schema (GREEN)** - `aefd037` (feat)
3. **Task 3: Wire the cv and ranking list-typed fields** - `9523b10` (feat)

**Plan metadata:** `TBD` (docs: complete plan — see final commit)

_Note: the plan file is `type: execute`; Task 1 was `tdd="true"` and was executed RED-first (the five positive assertions fail with the recorded `list_type` error on the pre-fix tree)._

## Files Created/Modified
- `app/domain/schemas/_coerce.py` (new) - the shared pure helpers: `unwrap_single_key_mapping`, `coerce_str_list`, `coerce_mapping_list`.
- `tests/domain/test_coerce.py` (new) - nested-wrapper, multi-key / unknown-key fail-loud, `Suggestion`/`GapFinding`, and `RankingResponse.requirements` cases.
- `app/domain/schemas/screening.py` - `ScreeningAnswer.evidence_ids` and `ScreeningDraftResponse.answers` delegate to the shared helpers (no local logic).
- `app/domain/schemas/ranking.py` - `RankingResponse.requirements` delegates to `coerce_mapping_list` (`extra="ignore"` unchanged).
- `app/domain/cv.py` - `Suggestion.evidence_ids` and `GapFinding.evidence_ids` delegate to `coerce_str_list`; purity docstring amended.
- `tests/domain/test_screening_schema.py` - the `{"nope": 1}`, two-key, and stray-top-level-key fail-loud cases added.
- `tests/llm/test_salvage.py` - the literal captured payload routed through the production `_salvage`.
- `tests/api/test_apply_draft_errors.py` - the route/stage test asserting 200 + 4 persisted rows.

## Decisions Made
- **Fix at the coercion boundary, never the salvager.** `TOLERATED_SCHEMA_ERRORS` is untouched; adding `list_type` would substitute the field default and silently discard every drafted answer (M1).
- **Only a single-key wrapper Mapping is unwrapped.** A stray top-level key (`{"answers": [...], "item": ...}`, the id-51 shape) still raises, deliberately refusing to weaken `extra="forbid"` (A4). This is a conscious narrowing of the debug report's looser "absorb the top-level `item`" wording.
- **One shared pure helper.** All five named list-typed fields delegate to `app/domain/schemas/_coerce.py` rather than re-implementing the branches.

## Deviations from Plan

None in the code — the plan was executed exactly as written (TDD RED-first, three atomic commits).

### Environment repair (blocking, non-code)

- **Found during:** Task 1 verification.
- **Issue:** the project `.venv` is a Python **3.14** venv (`pyvenv.cfg` pins `/usr/bin/python3.14`), but this sandbox has no `python3.14`; `.venv/bin/python` resolves to system Python 3.11 with none of the app's packages, so `.venv/bin/python -m pytest` fails with `No module named pytest`. The plan's `<verify>` blocks and `config.test_command` both name `.venv/bin/python`.
- **Fix:** created an equivalent Python 3.11 virtualenv at `/tmp/gsdvenv` and installed the pinned runtime set (fastapi / sqlalchemy / alembic / pydantic 2.13.5 / jinja2 / httpx / structlog / rapidfuzz / pypdf / pyyaml) plus dev tools (pytest 9.1.1, pytest-asyncio, ruff 0.16.7) and pandas/numpy (so the full default lane's dataframe-conversion tests collect). No repo file, dependency manifest or lockfile was changed.
- **Verification:** all four touched files green, `ruff check app/domain` clean, and the full default lane green (below).
- **Risk:** the test evidence was produced on CPython 3.11 rather than the pinned 3.13/3.14. The repo's own `ruff target-version = "py313"` and Python 3.13/3.14-targeted wheels still gate the shipped container; this was a local execution substitute only.

## Issues Encountered
- The pre-fix RED run printed the exact recorded error: `answers.0.evidence_ids / Input should be a valid list [type=list_type, input_value={'item': [...]}]` at `('answers', 0, 'evidence_ids')` — matching the stored `llm_calls.error` byte-for-byte, confirming the fixture exercises the real defect.
- No code-facing problems; the pre-fix `test_a_multi_key_mapping...` and `test_an_unknown_single_key_wrapper...` cases passed before the fix (they are fail-loud, so they must), and their sibling positives were red.

## Verification

Command (environment substituted per the deviation above):
`.venv/bin/python -m pytest -q tests/domain/test_coerce.py tests/domain/test_screening_schema.py tests/llm/test_salvage.py tests/api/test_apply_draft_errors.py tests/api/test_apply_package.py tests/test_import_discipline.py -x && .venv/bin/python -m ruff check app/domain`

- Combined gate: **69 passed**, ruff **All checks passed**.
- Four touched files alone: **33 passed**.
- Full default lane (`-m 'not live and not latex'`): **1692 passed, 14 deselected, 2 xfailed** in 303s.
- `tests/test_import_discipline.py::test_domain_imports_no_io` green (the new `app/domain/schemas/_coerce.py` imports only stdlib).
- `git diff app/llm/opencode_server.py` empty — the salvager and its allow-list are byte-unchanged.

## Known Residual (recorded, no further plan change)

The other captured occurrence (id 51) carries `{"answers": ..., "item": ...}` — a **stray top-level `item` alongside `answers`**. Under `extra="forbid"` that shape still raises and would emit `drafting_failed` again if the provider re-emits it. This plan does **not** absorb it (doing so would weaken `extra="forbid"`, A4). The UAT re-run must watch for a second `drafting_failed` on a package whose model output carries that stray key; if it recurs, the recorded next step is a fresh diagnosis of the provider's emission (or a separately-reviewed decision about the top-level `extra` policy) — never a silent loosening inside this plan.

## Known Stubs

None — no stub, placeholder or unwired data source was introduced.

## Next Phase Readiness
- G-07-7 is closed for the `{"item": ...}`/`""` shapes; the UAT re-run of the `Draft answers` action should now produce a reviewable queue of answers.
- The residual above is the only open item for the re-run; no code, schema or dependency follow-up is planned.

---
*Phase: 07-assisted-apply-tracker*
*Completed: 2026-10-12*

## Self-Check: PASSED

- SUMMARY.md: FOUND
- Commit `c807288` (Task 1, RED): FOUND
- Commit `aefd037` (Task 2, GREEN): FOUND
- Commit `9523b10` (Task 3): FOUND
- Created files `app/domain/schemas/_coerce.py`, `tests/domain/test_coerce.py`: FOUND
- Modified files `screening.py`, `ranking.py`, `cv.py`, `test_screening_schema.py`, `test_salvage.py`, `test_apply_draft_errors.py`: FOUND
