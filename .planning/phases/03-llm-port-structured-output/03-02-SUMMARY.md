---
phase: 03-llm-port-structured-output
plan: 02
subsystem: testing
tags: [opencode, contract-test, snapshot, live-lane, pytest, plat-05, tdd]

# Dependency graph
requires:
  - phase: 03-llm-port-structured-output
    provides: "plan 03-01's app/llm/contract.py (the pinned wire vocabulary) and app/llm/builders.py (the pure request builders the snapshot test pins)"
provides:
  - "tests/llm/fixtures/opencode-doc.json — the committed hand-projected /doc structured-output slice (D-53/D-55)"
  - "tests/llm/test_contract_snapshot.py — the default-lane builder-vs-snapshot contract, the negative control and the default-lane-cannot-run-live guard"
  - "tests/llm/test_contract_live.py — the operator live lane (spec fetch + diff only, D-57)"
  - "docs/runbook-opencode-contract.md — the four-step deliberate-refresh procedure"
affects: [03-03, 03-04, 03-05, 03-06, 03-07, 05-ranking]

# Actuals (#2632) — same estimateTokens scale (chars/4) as the plan's estimate.
actuals:
  tokens: 7252
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: []   # zero new packages this phase
  patterns:
    - "Committed snapshot slice projected to fixed list-valued facts, so unrelated OpenAPI churn cannot fail the test (D-55)"
    - "One pinned name per surface asserted against BOTH the snapshot and the builder; an adaptive client is rejected (D-54)"
    - "Guard-can-fail companion exercises the SAME pointer helper with a wrong name"
    - "The default-lane-never-runs-live guard lives in the default lane, never in the live-marked module"
    - "Live lane: spec fetch + diff only; a request event hook asserts no POST occurred (D-57)"

key-files:
  created:
    - tests/llm/fixtures/opencode-doc.json
    - tests/llm/test_contract_snapshot.py
    - tests/llm/test_contract_live.py
    - docs/runbook-opencode-contract.md
  modified: []

key-decisions:
  - "The fixture is indexed by `MESSAGE_DOC_PATH` (the OpenAPI path-template spelling) and never by `MESSAGE_PATH` (our wire spelling); the test asserts both constants exist and differ, so a future rename fails loudly rather than raising a bare KeyError."
  - "The live lane compares 22 named facts set-by-set and reports every divergent pointer (including a renamed path key) instead of raising; it also asserts the committed `_meta.server_version` matches `GET /global/health`, so a version-only upgrade still fails."
  - "The default-lane guard asserts pyproject's `addopts` still contains `-m 'not live'` and declares the `live` marker — it lives in the default-lane module because a guard inside a live-marked module never executes."

patterns-established:
  - "A committed contract artefact only ever changes through its runbook, never by a re-dump"
  - "Live-lane tests assert their own no-side-effect property (here: no POST) rather than claiming it"

requirements-completed: [PLAT-05]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "A default-lane test fails if the pinned structured-output constant or the request builder disagrees with the committed /doc slice, with no server running (builder == snapshot)."
    requirement: PLAT-05
    verification:
      - kind: unit
        ref: "tests/llm/test_contract_snapshot.py#test_the_request_side_contract_matches_the_snapshot"
        status: pass
      - kind: unit
        ref: "tests/llm/test_contract_snapshot.py#test_the_builder_emits_only_snapshot_request_properties"
        status: pass
      - kind: unit
        ref: "tests/llm/test_contract_snapshot.py#test_the_path_constants_are_real_fixture_keys"
        status: pass
    human_judgment: false
  - id: D2
    description: "The negative control blocks an adaptive client: the alternative spellings (`outputFormat`, `structured_output`, `structuredOutput`) appear nowhere in the raw fixture text (D-54)."
    requirement: PLAT-05
    verification:
      - kind: unit
        ref: "tests/llm/test_contract_snapshot.py#test_the_documented_alternative_spellings_are_absent_from_the_snapshot"
        status: pass
      - kind: unit
        ref: "tests/llm/test_contract_snapshot.py#test_the_pointer_check_can_actually_fail"
        status: pass
    human_judgment: false
  - id: D3
    description: "The default lane structurally cannot run the live lane, and the guard that proves it executes in the default lane."
    requirement: PLAT-05
    verification:
      - kind: unit
        ref: "tests/llm/test_contract_snapshot.py#test_the_default_lane_cannot_run_the_live_lane"
        status: pass
      - kind: integration
        ref: ".venv/bin/python -m pytest -q tests/llm --collect-only  (55 collected, 1 deselected)"
        status: pass
    human_judgment: false
  - id: D4
    description: "An operator-run live lane refetches /doc and diffs the live spec against the committed slice, failing loudly on drift and performing no LLM call (D-57)."
    requirement: PLAT-05
    verification:
      - kind: manual_procedural
        ref: ".venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py"
        status: unknown
    human_judgment: true
    rationale: "Deselected by addopts by design and operator-run against the user's server. The projection logic WAS validated during execution against the live 1.18.31 spec (22 facts, 0 diffs; health version matched the fixture), but the pytest live lane itself must be run by the operator — and the operator is the only one who sees a future upgrade."
  - id: D5
    description: "The refresh procedure exists as an operator runbook: four numbered steps, the host-vs-container base URL note, the --hostname 0.0.0.0 precondition, the .venv/bin/python requirement, and why the response field is `structured`."
    requirement: PLAT-05
    verification: []
    human_judgment: true
    rationale: "A documentation artefact whose adequacy (can an operator follow it and not re-dump the slice?) is a human judgement; no test asserts its prose."

# Metrics
duration: 8 min
completed: 2026-09-17
status: complete
---

# Phase 3 Plan 02: LLM Port + Structured Output Summary

**The opencode structured-output wire vocabulary is now pinned by a committed `/doc` slice and a default-lane test that fails on any code-side rename with no server running, with a negative control against adaptive clients and an operator live lane that reports server drift by pointer.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-09-17T21:10:23Z
- **Completed:** 2026-09-17T21:18Z
- **Tasks:** 2 (Task 1 TDD, Task 2 auto)
- **Files created:** 4 (all new)
- **Full suite:** 757 passed, 3 deselected (~148 s; plan 03-01 baseline was 746 passed, 2 deselected)

## Accomplishments

- **The snapshot exists and is a projection, not a dump.** `tests/llm/fixtures/opencode-doc.json` is 2,992 bytes versus the live spec's 478,968 — it keeps only the session/message endpoints and the four structured-output schemas as fixed list-valued facts, so unrelated OpenAPI churn cannot fail the contract (D-55).
- **The default lane proves builder == snapshot with no server.** Eleven tests pin every wire constant to a fixture pointer and assert the builder emits only properties the server accepts.
- **An adaptive client is structurally impossible to add.** The negative control scans the raw fixture text for `outputFormat` / `structured_output` / `structuredOutput`, and a guard-can-fail companion exercises the same pointer helper with those wrong names.
- **The live lane is real and honest.** `tests/llm/test_contract_live.py` fetches `/doc`, compares 22 facts set-by-set, reports every divergent pointer including a renamed path key, asserts the committed `_meta.server_version` equals `GET /global/health`, and uses a request event hook to assert no `POST`/`/session` call occurred (D-57).
- **The refresh path is documented.** `docs/runbook-opencode-contract.md` carries the four-step procedure, the container-vs-host base-URL trap, the `--hostname 0.0.0.0` precondition, the `.venv/bin/python` requirement, and a "why the response field is `structured`" section.

## Task Commits

Each task was committed atomically. Task 1 (TDD) produced a RED test commit and a GREEN implementation commit:

1. **Task 1: The committed snapshot slice and the default-lane contract** — `c5a2e2b` (test, RED) → `6c77c96` (feat, GREEN)
2. **Task 2: The operator live lane and the refresh runbook** — `19f9535` (feat)

**Plan metadata:** the `docs(03-02)` commit immediately following this file (SUMMARY + STATE + ROADMAP + REQUIREMENTS).

## Files Created/Modified

- `tests/llm/fixtures/opencode-doc.json` — **created**; the committed hand-projected slice, recording the observed 1.18.31 health version and explicitly that `/doc`'s `info.version` is a static spec version (P12)
- `tests/llm/test_contract_snapshot.py` — **created**; 11 default-lane tests: path-constant presence, request/response contract, negative control, builder-subset check, guard-can-fail, addopts guard
- `tests/llm/test_contract_live.py` — **created**; the `live`-marked operator lane with the test-local projection helpers
- `docs/runbook-opencode-contract.md` — **created**; the deliberate-refresh procedure

## Decisions Made

- **Index by the OpenAPI spelling, never the wire spelling.** The fixture key is `MESSAGE_DOC_PATH` (`/session/{sessionID}/message`); the test proves both path constants exist and differ. Indexing by `MESSAGE_PATH` would raise a bare `KeyError` on both the fixture and the live spec.
- **Compare facts, not documents.** Both the snapshot test and the live diff operate on fixed lists of property names, required lists, enums and refs, so an unrelated endpoint or a new optional property elsewhere in the 479 KB spec cannot fail the contract.
- **Validate the projection against the real spec while authoring.** The executor fetched `/doc` and `/global/health` once (read-only) to build an accurate projection, then ran the live module's own `_committed_facts` / `_live_facts` / `_diff_facts` helpers against it: 22 facts, **0 diffs**, health version `1.18.31` matching the fixture. This is what makes the operator lane trustworthy on its first real run; the `pytest -m live` lane itself remains operator-run.
- **The default-lane guard cannot live in the live module.** `test_the_default_lane_cannot_run_the_live_lane` reads `pyproject.toml` and asserts `addopts` still deselects `live`; placing it in the live-marked module would mean it never executes in the default lane.

## Deviations from Plan

None - plan executed exactly as written.

Two in-task self-corrections were made before either commit and are not deviations:

- The snapshot test initially restated the message path as a string literal; it was removed so every wire name comes from `app/llm/contract.py` (the plan's own acceptance criterion: no hard-coded wire literal).
- The live projection's first draft read the structured-error data object from the wrong key; caught by validating the projection against the live spec before committing.

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Notes |
|------|-----|-------|----------|-------|
| 1 | `c5a2e2b` (test) | `6c77c96` (feat) | — | RED was a **genuine assertion failure**: 10 tests failed on `_load_fixture`'s existence assertion because the committed slice did not exist yet; the 11th (the addopts guard) is fixture-independent and passed. No load/collection error. |
| 2 | n/a (not TDD) | `19f9535` (feat) | — | Task 2 is `type="auto"`: two files, one commit. |

## Issues Encountered

- **The live lane must never run in the default lane.** `pytest -q tests/llm --collect-only` now reports `55/56 tests collected (1 deselected)`, and `pytest -q -m live tests/llm/test_contract_live.py --collect-only` collects 1 — both asserted by the plan's verify commands.
- **No production code changed.** This plan is test + documentation only; the contract it pins lives in plan 03-01's `app/llm/contract.py`.
- **The `/doc` read during authoring is not the live lane.** It was a single read-only spec fetch to build and validate the projection; the operator lane remains the operator's check and is recorded in `.planning/WINDOWS.md` as an `unrun-verify`.

## Known Stubs

None. The live lane is not a stub: it is complete, collectable under `-m live`, and its projection was validated against the running server; it is simply operator-run by design (D-53/D-57).

## Threat Flags

None — this plan adds no network endpoint, auth path, or production code. It mitigates T-3-09 (silent rename), T-3-10 (a guard that cannot fail), T-3-11 (fixture content: property-name lists only, no credential/body), T-3-12 (no live model call) and T-3-13 (deliberate refresh runbook), all already in the plan's threat register.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **PLAT-05's chain of proof is now installed:** builder == snapshot (default lane, passing) → snapshot == live spec (operator lane, projection validated) → the real call works (03-01's `/settings` selftest).
- **Operators still to do (deliberately, at end-of-phase):** run `OPENCODE_BASE_URL=http://127.0.0.1:4096 .venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py` on the host and confirm the committed `_meta.server_version` matches the observed health version. Recorded in `03-VALIDATION.md`'s Manual-Only table and appended to `.planning/WINDOWS.md` as an `unrun-verify`.
- **Ready for 03-03..03-07.** The snapshot test's constants and the builders are the surfaces those plans extend; the negative control means any future rename must go through `app/llm/contract.py` plus a deliberate fixture refresh.

---
*Phase: 03-llm-port-structured-output*
*Completed: 2026-09-17*

## Self-Check: PASSED

- All four created files exist on disk (`tests/llm/fixtures/opencode-doc.json`, `tests/llm/test_contract_snapshot.py`, `tests/llm/test_contract_live.py`, `docs/runbook-opencode-contract.md`).
- All three plan commits are present (`c5a2e2b`, `6c77c96`, `19f9535`).
- Measured commit count from the plan ledger: 3 (`git rev-list --count c21f775..HEAD`).
