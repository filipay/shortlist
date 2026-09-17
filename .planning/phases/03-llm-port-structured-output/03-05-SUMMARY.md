---
phase: 03-llm-port-structured-output
plan: 05
subsystem: infra
tags: [plat-04, settings, compose, env, config-guard, tdd]

# Dependency graph
requires:
  - phase: 03-llm-port-structured-output
    provides: "plans 03-01/03-03's three opencode Settings ceilings, which this plan makes real configuration"
provides:
  - "tests/test_config.py guard coverage for opencode_completion_timeout_seconds, opencode_max_retries and opencode_structured_retry_count, plus an env-tunability proof"
  - "compose.yml passthrough for the three ceilings and the previously unforwarded OPENCODE_TIMEOUT_SECONDS"
  - ".env.example documentation for all four opencode knobs"
affects: [03-06, 03-07, 05-ranking, 08-scheduling]

# Actuals (#2632) — same estimateTokens scale (chars/4) as the plan's estimate.
actuals:
  tokens: 1201
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A new ceiling is configuration only once the config guard asserts it, the environment can override it, the container forwards it, and the operator can find it"
    - "Every LIMIT_FIELDS entry must also be a REQUIRED_SETTINGS_FIELDS entry — a ceiling the surface guard omits is a knob nobody checks"

key-files:
  created: []
  modified:
    - tests/test_config.py
    - compose.yml
    - .env.example

key-decisions:
  - "The completion timeout stays a separate Settings field from `opencode_timeout_seconds` (P4): a structured completion is a different order of magnitude from a health probe. The LIMIT_FIELDS comment records this so a future reader does not merge them."
  - "The two integer ceilings are small (2) and below DISTINCTIVE_THRESHOLD_FLOOR, so they add nothing to the AST literal scan; they are listed in LIMIT_FIELDS anyway to keep the \"what counts as a ceiling\" set complete."
  - "compose.yml forwards each key with `${VAR:-default}` and a default that matches app/config.py, because the image contains no `.env` and an unforwarded key silently loses to the in-code default."
  - "OPENCODE_TIMEOUT_SECONDS is fixed alongside its three siblings even though it predates this phase: leaving one documented knob unable to reach the container while fixing the other three would be inconsistent."

patterns-established:
  - "Guard coverage is itself guarded: a test asserts each Phase-3 ceiling is named in the surface guards, so dropping one fails loudly"
  - "Every LIMIT_FIELDS name must be a numeric REQUIRED_SETTINGS_FIELDS entry"

requirements-completed: [PLAT-02]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "The three Phase-3 ceilings are asserted by the config surface guard with their documented defaults."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_the_phase_three_ceilings_are_guarded"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_settings_exposes_every_documented_knob"
        status: pass
    human_judgment: false
  - id: D2
    description: "Each of the three ceilings is env-tunable: a patched environment changes the effective value on a fresh Settings()."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_the_phase_three_ceilings_are_environment_tunable"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every LIMIT_FIELDS entry is a required numeric ceiling, and the literal-absence scan is still non-vacuous."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_every_limit_field_is_a_required_numeric_ceiling"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_the_literal_scan_can_actually_fail"
        status: pass
    human_judgment: false
  - id: D4
    description: "The container forwards all four opencode keys with ${VAR:-default} substitution whose defaults match app/config.py, and .env.example documents every new key."
    requirement: PLAT-02
    verification:
      - kind: integration
        ref: "tests/test_deploy_manifest.py (green)"
        status: pass
      - kind: integration
        ref: "tests/test_dependency_pins.py (green)"
        status: pass
      - kind: manual_procedural
        ref: "compose.yml parse + per-key ${VAR:-default} vs Settings.model_fields default comparison"
        status: pass
    human_judgment: false

# Metrics
duration: 5 min
completed: 2026-09-17
status: complete
---

# Phase 3 Plan 05: LLM Port + Structured Output Summary

**The three Phase-3 opencode ceilings are now real configuration: the config guard asserts them, a patched environment overrides them, the container forwards them (plus the previously unforwarded `OPENCODE_TIMEOUT_SECONDS`), and `.env.example` documents them.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-09-17T22:43:51Z
- **Completed:** 2026-09-17T22:49Z
- **Tasks:** 2 (Task 1 TDD)
- **Files modified:** 3 (all modified; no files created)
- **Full suite:** 792 passed, 3 deselected (~119 s; plan 03-04 baseline was 789 passed, 3 deselected)

## Accomplishments

- **The surface guard covers every Phase-3 ceiling.** `REQUIRED_SETTINGS_FIELDS` gains `opencode_completion_timeout_seconds`, `opencode_max_retries` and `opencode_structured_retry_count`; `LIMIT_FIELDS` gains the two integer ceilings.
- **The guard's own coverage is guarded.** `test_the_phase_three_ceilings_are_guarded` names the three explicitly, so a future edit that drops one from either tuple fails loudly instead of silently un-covering it.
- **Env-tunability is proven, not assumed.** `OPENCODE_COMPLETION_TIMEOUT_SECONDS=7.5`, `OPENCODE_MAX_RETRIES=5` and `OPENCODE_STRUCTURED_RETRY_COUNT=4` all take effect on a fresh `Settings()` — a config field no test can override is only half a config field.
- **A pre-existing guard gap was closed.** `test_every_limit_field_is_a_required_numeric_ceiling` exposed that `probe_cache_ttl_seconds` was listed as a ceiling but omitted from the surface guard; it is now required.
- **A host `.env` override now reaches the container.** `compose.yml` forwards the three new keys and the previously unforwarded `OPENCODE_TIMEOUT_SECONDS`, each with `${VAR:-default}` and a default that matches `app/config.py` exactly (`5`/`120`/`2`/`2`).
- **The operator can discover every knob.** `.env.example` documents all four with a one-line purpose and the safe default; no credential value was added.

## Task Commits

Each task was committed atomically; Task 1 (TDD) produced a RED test commit and a GREEN implementation commit:

1. **Task 1: The config guard covers the new ceilings** — `f9264dd` (test, RED) → `7885e9e` (feat, GREEN)
2. **Task 2: The container forwards the keys and the operator can discover them** — `c887c31` (feat)

**Plan metadata:** the `docs(03-05)` commit immediately following this file (SUMMARY + STATE + ROADMAP + REQUIREMENTS).

## Files Created/Modified

- `tests/test_config.py` — **modified**; the Phase-3 guard coverage, the env-tunability test, the LIMIT⊆REQUIRED completeness test, and the `probe_cache_ttl_seconds` fix
- `compose.yml` — **modified**; four `${VAR:-default}` passthrough entries under a Phase-3 comment
- `.env.example` — **modified**; four documented keys with purpose comments

## Decisions Made

- **The completion timeout remains a distinct field.** `opencode_timeout_seconds` stays scoped to health/discovery (P4); the LIMIT_FIELDS comment records why, so the two are not "simplified" back into one.
- **Small integer ceilings are still listed.** `2` is below `DISTINCTIVE_THRESHOLD_FLOOR`, so the AST scan is unaffected; listing them keeps the ceiling set complete rather than leaving them discoverable only by reading `app/config.py`.
- **Fix the timeout passthrough too.** `OPENCODE_TIMEOUT_SECONDS` was never forwarded — the identical defect class — so it is corrected alongside its three siblings.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] `probe_cache_ttl_seconds` was a ceiling the surface guard omitted**
- **Found during:** Task 1 RED (the new "every LIMIT_FIELDS name is a required ceiling" test failed on it)
- **Issue:** `probe_cache_ttl_seconds` was listed in `LIMIT_FIELDS` (so the absence scan covers its value 300) but was absent from `REQUIRED_SETTINGS_FIELDS`, so nothing asserted the field itself exists with its documented default. The plan's behaviour Test 2 requires every `LIMIT_FIELDS` name to be a required field, which cannot hold while that gap exists.
- **Fix:** added `probe_cache_ttl_seconds` to `REQUIRED_SETTINGS_FIELDS` with a comment naming it as a pre-existing omission.
- **Files modified:** `tests/test_config.py`
- **Verification:** `tests/test_config.py` 11 passed; full suite green.
- **Committed in:** `7885e9e` (Task 1 GREEN)

---

**Total deviations:** 1 auto-fixed (1 missing-critical)
**Impact on plan:** Strengthened the existing guard rather than changing scope; no `app/` source was touched, as the plan requires.

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Notes |
|------|-----|-------|----------|-------|
| 1 | `f9264dd` (test) | `7885e9e` (feat) | — | RED was a **genuine assertion failure**: 2 target tests failed — the Phase-3 ceilings were absent from the guards, and the LIMIT⊆REQUIRED check exposed the `probe_cache_ttl_seconds` gap. |
| 2 | n/a (not TDD) | `c887c31` (feat) | — | Two config files; the guards (`test_deploy_manifest`, `test_dependency_pins`) were run inside the task. |

**Unexpected-green note (tdd.md fail-fast rule 1).** The env-tunability test (`test_the_phase_three_ceilings_are_environment_tunable`) passed at RED time, because the three `Settings` fields shipped in plan 03-01. Investigated and expected: this task adds guard *coverage* for behaviour that already exists, not new behaviour. The RED for the task is therefore the guard-coverage test, which did fail for the right reason.

## Issues Encountered

- **The RED commit's message needed amending.** The first `git commit` for `f9264dd` accidentally included a bogus `(cherry picked from commit 0000…)` trailer from a malformed shell command. The message was corrected with `git commit --amend` (the commit was local and unpushed, and the trailer was false attribution), so the RED commit hash is `f9264dd` rather than the initial `a438aaa`. No content changed.
- **compose defaults are written as `5`/`120`, not `5.0`/`120.0`.** The plan specifies the integer form; the values match the float `Settings` defaults numerically, which is what the passthrough needs. The verification compares them numerically rather than as strings.
- **No live/openode or container action was required.** This plan is config-and-guard only; the container smoke remains an operator-run check recorded elsewhere.

## Known Stubs

None. Every deliverable is implemented and asserted by a test in the default lane.

## Threat Flags

None — no new surface. This plan mitigates T-3-06 (ceilings now genuinely reach the container, so an operator can bound spend), T-3-17 (compose defaults asserted to match the code defaults via key-presence plus a value comparison) and T-3-SC (zero new packages; two config files and one test file), all already in the plan's threat register.

## User Setup Required

None - the new keys are optional and default to the current behaviour. An operator who wants to tune them copies `.env.example` to `.env` and edits; the container now forwards each value.

## Next Phase Readiness

- **PLAT-04's constraint on Phase 3 is satisfied.** Every new ceiling is a `Settings` field with a documented default, asserted by the config guard, overridable from the environment, forwarded to the container, and documented for the operator.
- **`OPENCODE_TIMEOUT_SECONDS` is no longer a dead knob**, so the health/discovery timeout is tunable through the same path as everything else.
- **`PLAT-02` stays open by design.** It is declared by six plans; the shared-ID gate keeps it incomplete until the last declaring sibling (03-06/03-07) has a SUMMARY.md.

---
*Phase: 03-llm-port-structured-output*
*Completed: 2026-09-17*

## Self-Check: PASSED

- All three plan files exist on disk (`tests/test_config.py`, `compose.yml`, `.env.example`).
- All three plan commits are present (`f9264dd`, `7885e9e`, `c887c31`).
- Measured commit count from the plan ledger: 3 (`git rev-list --count 3934d8c..HEAD`).
