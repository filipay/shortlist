---
phase: 03-llm-port-structured-output
plan: 10
subsystem: llm
tags: [opencode, structured-output, permission-ruleset, forced-tool-call, live-lane, pydantic, pytest]

# Dependency graph
requires:
  - phase: 03-llm-port-structured-output
    provides: 03-06 the session-level DEFAULT_DENY_RULES tool deny
  - phase: 03-llm-port-structured-output
    provides: 03-02 the committed /doc slice and the default-lane snapshot contract
  - phase: 03-llm-port-structured-output
    provides: 03-01 the /settings selftest route and the llm_calls probe write path
  - phase: 03-llm-port-structured-output
    provides: 03-09 the PermissionRule shape pinned against /doc drift
provides:
  - "An order-enforced ruleset carve-out granting only the server-internal StructuredOutput tool, with a semantic last-match-wins evaluator"
  - "A shipped opencode_model default (minimax-m3) that can honour a forced tool call, pinned across app/config.py, compose.yml and .env.example and guarded against the documented incompatible model"
  - "A differential cause clause on structured-output failures, persisted on llm_calls.error so it survives a reload"
  - "tests/llm/test_live_structured_call.py — the repeatable operator lane that performs the real /settings/llm-test call"
affects: [05-ranking, 06-tailoring, opencode-contract-refresh-runbook, phase-03-verification]

# Actuals (#2632) — pairs with the plan's estimate to calibrate future estimates.
# Same estimateTokens scale (chars/4 over the realized diff), never a harness token count.
actuals:
  tokens: 11592
  tasks: 3
  commits: 3
  plan_head_before: 7a1064e8b01ab9b5e52edc59d62340b78f2e9577

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Order-sensitive ruleset grant: the catch-all deny stays FIRST, the single carve-out follows it, and a last-match-wins evaluator makes the ordering a testable behaviour rather than a comment"
    - "Configuration-propagated fixed default: the shared fake-transport helper's stubbed discovery advertises settings.opencode_model, so moving the default leaves every implicit-resolution test green by construction"
    - "Differential failure cause on a persisted column: two otherwise byte-identical structured failures are told apart by a fixed-literal clause appended to llm_calls.error, with no new field and no new column"
    - "Operator live lane mirroring the default-lane client fixture with exactly one deliberate difference: the real backend CLASS (callable) instead of the offline stub"

key-files:
  created:
    - tests/llm/test_live_structured_call.py
  modified:
    - app/llm/contract.py
    - app/llm/opencode_server.py
    - app/config.py
    - compose.yml
    - .env.example
    - docs/runbook-opencode-contract.md
    - app/web/templates/html/settings.html
    - tests/llm/test_trust_boundary.py
    - tests/llm/test_complete_structured.py
    - tests/llm/test_discovery_redaction.py
    - tests/test_config.py

key-decisions:
  - "The carve-out is order-enforced: DEFAULT_DENY_RULES is a two-rule tuple (catch-all deny, then the StructuredOutput grant) and ruleset_allows_tool uses last-match-wins, so reordering the rule is a loud default-lane failure"
  - "opencode_model default moves to minimax-m3 with KNOWN_FORCED_TOOL_CHOICE_INCOMPATIBLE_MODELS guarding the shipped default; no pydantic validator rejects a configured model, because an operator stays free to set any model and Task 3 makes the failure legible instead"
  - "The differential travels on the persisted StructuredCallResult.error (llm_calls.error), so it survives a page reload with no new field and no migration"
  - "The default change propagates through ONE mechanism — the shared _backend helper's stubbed discovery — rather than 24 call-site model= edits, so the suite cannot depend on which path a future test takes"

patterns-established:
  - "A grants-one-name permission carve-out ships with a reordering test that proves the ordering is load-bearing"
  - "A shipped config default that is a correctness requirement ships with a declared-default guard, a known-bad set that cannot be emptied, and a cross-surface agreement test derived from the default"
  - "A live operator lane overrides get_llm_backend with the backend CLASS (a callable), never a bare instance"

requirements-completed: [PLAT-02, PLAT-05]

# Coverage metadata (#1602) — one entry per shipped deliverable.
coverage:
  - id: D1
    description: "The session ruleset denies every user-facing tool and grants only the server-internal structured-output tool by an order-enforced carve-out"
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_the_default_deny_ruleset_stays_fail_closed_with_one_carve_out"
        status: pass
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_the_carve_out_must_follow_the_catch_all_deny"
        status: pass
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_the_evaluator_denies_an_unmentioned_tool_name"
        status: pass
    human_judgment: false
  - id: D2
    description: "The shipped default model can honour a forced tool call, pinned on app/config.py, compose.yml and .env.example and guarded against the documented incompatible model"
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_the_default_model_is_not_a_known_forced_tool_call_incompatible_model"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_the_compose_model_default_agrees_with_the_declared_one"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_the_shipped_model_default_is_environment_tunable"
        status: pass
    human_judgment: false
  - id: D3
    description: "A structured-output failure names which side is at fault via a differential cause on the persisted error, surviving a reload"
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_a_structured_error_without_a_tool_part_carries_the_model_cause"
        status: pass
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_a_reordered_ruleset_carries_the_ruleset_cause_instead"
        status: pass
    human_judgment: false
  - id: D4
    description: "A real schema-constrained call through POST /settings/llm-test returns a validated payload, a rendered tool part, exactly one probe row (run_id NULL) and no runs row, with no second provider key"
    requirement: PLAT-02
    verification:
      - kind: e2e
        ref: ".venv/bin/python -m pytest -q -m live tests/llm/test_live_structured_call.py"
        status: pass
    human_judgment: true
    rationale: "The live lane needs a running opencode serve and spends tokens against the operator's own server; it is deselected from the default lane (D-53), so a human must run it in the target environment. It passed here (1 passed, 20.48s) but is not part of the automated default-lane gate."
  - id: D5
    description: "The structured-output / permission contract stays pinned by the unedited /doc slice and snapshot test (PLAT-05 half)"
    requirement: PLAT-05
    verification:
      - kind: unit
        ref: "tests/llm/test_contract_snapshot.py#test_the_permission_deny_rule_contract_matches_the_snapshot"
        status: pass
      - kind: e2e
        ref: ".venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py"
        status: pass
    human_judgment: false

# Metrics
duration: 13min
completed: 2026-09-21
status: complete
---

# Phase 3 Plan 10: Structured-output blocker closure Summary

**Restored the internal `StructuredOutput` tool the session deny was stripping, moved the shipped default model to one that honours a forced tool call, made a structured failure name its cause, and proved the fixed path with a real end-to-end live call.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-09-21T10:25:47Z
- **Completed:** 2026-09-21T10:38:19Z
- **Tasks:** 3
- **Files modified:** 12 (one new)

## Accomplishments

- **The blocker is fixed at the ruleset.** `DEFAULT_DENY_RULES` is now a two-rule tuple — the wildcard catch-all deny FIRST, then a single carve-out granting exactly the server-internal `StructuredOutput` tool — and the new `ruleset_allows_tool` evaluator uses last-match-wins, so `test_the_carve_out_must_follow_the_catch_all_deny` fails loudly if the rule is reordered. The catch-all staying first keeps success criterion 4's fail-closed default for every user-facing tool.
- **The shipped default can now make the call this phase exists to make.** `opencode_model` moved to `minimax-m3` (the live-evidenced capable model) with the forced-tool-call constraint documented, `KNOWN_FORCED_TOOL_CHOICE_INCOMPATIBLE_MODELS` naming the previously shipped `deepseek-v4.1-flash`, and consistency asserted across `app/config.py`, `compose.yml` and `.env.example` by tests that derive the expected spelling from the declared default.
- **The residual failure is legible.** `_structured_tool_note` tells a ruleset that stripped the internal tool apart from a model that declined the forced call; the clause is appended to `error` on both structured-failure branches, persists on `llm_calls.error`, and survives a reload with no new field and no migration.
- **Success criterion 1 has repeatable executable evidence.** `tests/llm/test_live_structured_call.py` performs one real schema-constrained call through `POST /settings/llm-test` against the running `opencode serve` 1.18.31 and passed: 200, `status ok`, `Structured payload: present`, a rendered `tool` part, `Model: minimax-m3`, exactly one `probe` row with `run_id IS NULL`, and zero `runs` rows.
- **The propagation is complete and verified by an untouched canary.** All 24 `_backend`-driven `complete_structured` calls now resolve `settings.opencode_model` through the shared helper's stubbed discovery; `tests/llm/test_salvage.py`, which this plan deliberately did not edit, stayed green.

## Task Commits

Each task was committed atomically:

1. **Task 1: Carve the server-internal structured-output tool out of the session deny ruleset** - `e3cb23a` (fix)
2. **Task 2: Ship a default model that can honour a forced tool call** - `ca72fbe` (fix)
3. **Task 3: Make a structured-output failure legible and prove the fixed path end to end** - `a307296` (fix)

_No TDD plan (phase.tdd-applicable = false); no RED/GREEN commits._

## Files Created/Modified

- `app/llm/contract.py` — exported `PERMISSION_ALLOW_ACTION`, `STRUCTURED_OUTPUT_TOOL_NAME`, `PART_TYPE_TOOL`; amended the deny-action comment to record the single carve-out exception
- `app/llm/opencode_server.py` — two-rule `DEFAULT_DENY_RULES`, the `ruleset_allows_tool` evaluator, `_structured_tool_note`/`_with_note`, and the differential wired into both structured-failure branches
- `app/config.py` — `opencode_model` default `minimax-m3` with the constraint docstring and the `KNOWN_FORCED_TOOL_CHOICE_INCOMPATIBLE_MODELS` frozenset
- `compose.yml` — `OPENCODE_MODEL` passthrough default matched to the code default
- `.env.example` — `OPENCODE_MODEL` value and the operator-selection requirement comment
- `docs/runbook-opencode-contract.md` — a "Choosing a model that can satisfy a forced tool call" section (requirement, observed 400, retryCount cannot rescue it); existing sections intact
- `app/web/templates/html/settings.html` — corrected observation copy (a healthy call DOES return a tool part); marker ids unchanged
- `tests/llm/test_trust_boundary.py` — re-expressed ruleset assertions, the reordering guard, the evaluator companion, the `settings` import and the resolved-model assertion
- `tests/llm/test_complete_structured.py` — `_backend` now advertises `settings.opencode_model`, the resolved-model assertions read it, the four `_structured_tool_note` branches and both classification causes
- `tests/llm/test_discovery_redaction.py` — the four `_resolve_model()` calls script their fake discovery from `settings.opencode_model` and stay argument-less
- `tests/test_config.py` — `opencode_model` in `REQUIRED_SETTINGS_FIELDS`, the declared-default pin, the incompatible-model guard, the env-tunable test and the compose/.env agreement test
- `tests/llm/test_live_structured_call.py` — NEW: the operator lane over the real route, overriding `get_llm_backend` with the callable `OpenCodeServerBackend` class

## Decisions Made

- **Order is behaviour, not a comment.** `ruleset_allows_tool` deliberately avoids `any()`, first-match and presence checks, so the shipped ruleset and a reordered one are distinguishable; that is what `test_the_carve_out_must_follow_the_catch_all_deny` asserts.
- **No validator rejects a configured model.** An operator stays free to set any `opencode_model`; the guard is on the SHIPPED default only, and Task 3's differential makes the resulting failure legible instead of gating the setting.
- **The differential lives on the existing `error` column.** No new `StructuredCallResult` field and no migration — the clause travels `_classify_message_response` → `StructuredCallResult.error` → `llm_calls.error` → the `/settings` Cause line.
- **One propagation mechanism.** The shared `_backend` helper's default, not 24 `model=` call-site edits, so the suite cannot depend on which resolution path a future test happens to take.

## Deviations from Plan

None - plan executed exactly as written.

---

**Total deviations:** 0 auto-fixed
**Impact on plan:** No deviation. One additional default-lane test (`test_the_missing_structured_payload_branch_also_carries_the_note`) covers the second structured-failure branch, which the task's action explicitly required the note to reach.

## Issues Encountered

None. The full suite grew from the 834-passed / 3-deselected baseline to **843 passed, 4 deselected** (the +1 deselected is the new live module; the +9 passing tests are this plan's new/completed default-lane tests), with no failures. `ruff check .` is clean, the four contract/ORM/PII/import guards pass unedited, `alembic heads` is still a single head `0003`, and the operator live `/doc` lane still passes.

## User Setup Required

None - no external service configuration required. The live lane is operator-run and needs a running `opencode serve` reachable at `OPENCODE_BASE_URL` (the default `http://host.docker.internal:4096` resolved from this environment).

## Next Phase Readiness

- Success criterion 1 now holds on shipped code: with no second provider key configured and the shipped default model, `POST /settings/llm-test` returns a validated structured result, recorded as exactly one probe row with `run_id IS NULL` and no `runs` row.
- UAT item 1 ("Live schema-constrained call from /settings") and item 4 (`format` vs `outputFormat`, satisfied by the same successful call) now have the repeatable live evidence `/gsd-verify-work` should re-run. UAT item 3's expectation must be re-read, not re-asserted: a healthy live response DOES carry a tool invocation — the server-internal structured-output tool — and no other tool part.
- `tests/llm/fixtures/opencode-doc.json`, `tests/llm/test_contract_live.py`, `tests/llm/test_contract_snapshot.py` and `tests/llm/test_salvage.py` are byte-identical to their committed state.
- This plan did not mark the phase complete and did not edit `ROADMAP.md`; re-verification and phase completion remain the orchestrator's act.

---

*Phase: 03-llm-port-structured-output*
*Completed: 2026-09-21*

## Self-Check: PASSED

- FOUND: app/llm/contract.py (modified, committed in e3cb23a)
- FOUND: app/llm/opencode_server.py (modified, committed in e3cb23a, a307296)
- FOUND: tests/llm/test_live_structured_call.py (created, committed in a307296)
- FOUND: e3cb23a
- FOUND: ca72fbe
- FOUND: a307296
