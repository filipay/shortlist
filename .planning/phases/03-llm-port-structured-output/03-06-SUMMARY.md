---
phase: 03-llm-port-structured-output
plan: 06
subsystem: security
tags: [trust-boundary, prompt-injection, tool-deny, permission-ruleset, import-discipline, tdd]

# Dependency graph
requires:
  - phase: 03-llm-port-structured-output
    provides: "plans 03-01/03-03's builders, complete_structured taxonomy, and the recoded Recorder fake transport"
provides:
  - "The default-deny session `permission` ruleset (DEFAULT_DENY_RULES) plus a message-level `tools` policy that sends no key by default and rejects a wildcard"
  - "`to_session_body` — the session model shape {id: modelID, providerID}, the deliberate inverse of the message shape"
  - "The trust-boundary observation: StructuredCallResult.part_types / .info_keys (TYPE and KEY names only), logged and rendered on /settings"
  - "The scoped LLM-call-path import guard (httpx) and the global subprocess guard, with an explicit app/sources exclusion"
affects: [03-07, 05-ranking, 06-tailoring]

# Actuals (#2632) — same estimateTokens scale (chars/4) as the plan's estimate.
actuals:
  tokens: 7228
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "The deny is enforced through the server's DOCUMENTED control (session permission ruleset), not an undocumented empty map"
    - "Observe, don't assert: the call records returned part TYPE names and info KEY names so a broken or over-broad deny is a finding"
    - "Untrusted content has one channel (parts); the system value is a bare parameter reference, never a computation"
    - "Import guards are scoped to where the rule is true, with a companion proving the exclusion is deliberate"

key-files:
  created:
    - tests/llm/test_trust_boundary.py
  modified:
    - app/llm/contract.py
    - app/llm/builders.py
    - app/llm/opencode_server.py
    - app/llm/base.py
    - app/api/settings.py
    - app/web/templates/html/settings.html
    - tests/llm/test_complete_structured.py
    - tests/test_import_discipline.py
    - tests/api/test_llm_selftest.py

key-decisions:
  - "The enforced deny is the session-level `permission` ruleset (DEFAULT_DENY_RULES), because the message-level `tools` map is deprecated and its wildcard semantics are undocumented (A2); the message body sends no `tools` key by default and rejects a `\"*\"` key outright."
  - "The session `model` shape is {id: modelID, providerID} — the INVERSE of the message body's {providerID, modelID}. Both key order and values are asserted together, because both objects are additionalProperties:false and a wrong placement is a silent 400."
  - "The deny is WATCHED, not assumed: part TYPE names and info KEY names are recorded and rendered, because opencode implements structured output via an internal tool and a blanket deny could break the proven path."
  - "The `app/sources` exclusion from the httpx guard is written down and proven (the transports really do import httpx and really are outside the scanned dirs), so the scoped rule cannot decay into a silent omission."

patterns-established:
  - "A guard's exclusion is itself tested: the excluded modules must still exhibit the reason for the exclusion"
  - "An observation field carries NAMES only; a sentinel test proves no text or value rides along"

requirements-completed: [PLAT-02]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "The message body sends no `tools` key by default, emits an explicit per-name allow-list when given, and raises ValueError on a wildcard `\"*\"` key naming the permission control."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_the_default_message_body_sends_no_tools_key"
        status: pass
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_an_explicit_allow_list_is_emitted_as_a_name_map"
        status: pass
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_a_wildcard_tools_key_is_rejected"
        status: pass
    human_judgment: false
  - id: D2
    description: "Tools are denied by default through the session `permission` ruleset, and _create_session actually sends it."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_the_default_deny_ruleset_is_deny_only"
        status: pass
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_the_session_request_actually_sends_the_deny_ruleset"
        status: pass
    human_judgment: false
  - id: D3
    description: "The session and message model shapes are distinct and not inverted; text parts only; the system value is a bare reference emitted verbatim."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_the_session_and_message_model_shapes_are_distinct_and_not_inverted"
        status: pass
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_the_system_value_is_a_bare_reference_never_a_computation"
        status: pass
    human_judgment: false
  - id: D4
    description: "The result observes part TYPE names and info KEY names — never part text — and logs them; the settings page renders the observation, with no payload value reaching the page or the llm_calls row."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_the_result_observes_part_types_and_info_keys_without_any_text"
        status: pass
      - kind: integration
        ref: "tests/api/test_llm_selftest.py#test_the_page_shows_the_parts_and_info_keys_for_the_current_call"
        status: pass
      - kind: integration
        ref: "tests/api/test_llm_selftest.py#test_a_payload_value_never_reaches_the_page_or_the_recorded_row"
        status: pass
    human_judgment: false
  - id: D5
    description: "Nothing on the LLM call path imports httpx outside app/llm, and nothing outside app/llm imports subprocess; the app/sources exclusion is deliberate and proven."
    requirement: PLAT-02
    verification:
      - kind: guard
        ref: "tests/test_import_discipline.py#test_the_llm_call_path_imports_no_httpx"
        status: pass
      - kind: guard
        ref: "tests/test_import_discipline.py#test_no_module_outside_app_llm_imports_subprocess"
        status: pass
      - kind: guard
        ref: "tests/test_import_discipline.py#test_the_sources_exclusion_is_deliberate_not_accidental"
        status: pass
    human_judgment: false
  - id: D6
    description: "The live observation of success criterion 4 — a real call's returned parts, system prompt and info keys."
    requirement: PLAT-02
    verification: []
    human_judgment: true
    rationale: "Needs the operator's running opencode server; the default lane proves the deny encoding and the observation plumbing with a fake transport. Recorded in 03-VALIDATION.md's Manual-Only table and appended to .planning/WINDOWS.md as an unrun-verify — the observation that closes Open Question Q1."

# Metrics
duration: 13 min
completed: 2026-09-17
status: complete
---

# Phase 3 Plan 06: LLM Port + Structured Output Summary

**Success criterion 4 is now structural: untrusted content has no channel into `system`, tools are denied by default through the server's documented `permission` ruleset, the deny is observed on every call rather than assumed, and no LLM HTTP or process path exists outside `app/llm/`.**

## Performance

- **Duration:** 13 min
- **Tasks:** 3 (Task 1 TDD; Tasks 2 and 3 auto)
- **Files created/modified:** 10 (1 created, 9 modified)
- **Full suite:** 811 passed, 3 deselected (~118 s; plan 03-05 baseline was 792 passed, 3 deselected)

## Accomplishments

- **No message-level grant by default.** `to_message_body` sends no `tools` key for `None` or `{}` — an undocumented empty map is not a deny — emits an explicit per-name allow-list when given, and raises `ValueError` on a `"*"` key naming the `permission` control.
- **The deny lives where the server documents it.** `DEFAULT_DENY_RULES` is a deny-only `permission` ruleset encoded in one module constant; `_create_session` now builds its body with `to_session_body` and actually sends it (asserted from the captured request).
- **The two model shapes cannot be confused.** `to_session_body` places the model id under `id` and the provider id under `providerID` — the inverse of the message body — and both key order and values are asserted together, because a wrong placement is a silent 400.
- **The deny is observed, not asserted.** `StructuredCallResult` gains `part_types`/`info_keys`, populated from the response (TYPE and KEY names only) and logged as `llm.structured_response`; the `/settings` result block renders them beside D-52's detail, so an over-broad deny or a broken structured path is a visible finding.
- **The import rule is enforced where it is true.** A scoped guard fails if `httpx` appears under `app/pipeline`, `app/api`, `app/web`, `app/domain` or `app/probe`; `subprocess` is asserted absent everywhere outside `app/llm`; and a companion proves the `app/sources` exclusion is deliberate.
- **Nothing leaks.** A sentinel in a returned part / payload value appears in no observation field, no log line, no rendered page, and no `llm_calls` row.

## Task Commits

1. **Task 1: The default-deny encoding** — `31de1b1` (test, RED) → `3acff0d` (feat, GREEN)
2. **Task 2: The scoped import guard** — `98d80c5` (feat)
3. **Task 3: Surface the observation** — `f0df570` (feat)

**Plan metadata:** the `docs(03-06)` commit immediately following this file (SUMMARY + STATE + ROADMAP + REQUIREMENTS).

## Files Created/Modified

- `tests/llm/test_trust_boundary.py` — **created**; the untrusted-content and default-deny guard (12 tests)
- `app/llm/contract.py` — the permission/tools/part-type vocabulary, `TEXT_PART_FIELDS` now derives from `PART_TYPE_FIELD`
- `app/llm/builders.py` — `to_session_body`; `to_message_body`'s tools policy and wildcard guard
- `app/llm/opencode_server.py` — `DEFAULT_DENY_RULES`, the session body, `_part_types`, the observation on every classified result, the `llm.structured_response` log
- `app/llm/base.py` — `StructuredCallResult.part_types` / `.info_keys`
- `app/api/settings.py` — transient observation context + the route-populated values
- `app/web/templates/html/settings.html` — the observation block
- `tests/llm/test_complete_structured.py` — the session-body assertion updated to the new shape
- `tests/test_import_discipline.py` — the scoped httpx guard, the global subprocess guard, the exclusion companions
- `tests/api/test_llm_selftest.py` — the observation render, the rich-observation test, the leak sentinel

## Decisions Made

- **Deny via `permission`, not `tools`.** `tools` is deprecated with undocumented wildcard semantics (A2), so the enforced control is the session ruleset; the message body sends no ambiguous empty map.
- **Watch the deny.** Because structured output is implemented via an internal tool, the plan records the returned part types and `info` keys rather than assuming a blanket deny is harmless (P5 step 4).
- **The observation is names-only and transient.** It is request-scoped context (never a column, never a JSON blob), and `latest_probe` continues to render D-52's persisted detail on reload.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `app/llm/base.py` had to carry the observation fields**
- **Found during:** Task 1 GREEN
- **Issue:** the plan requires `part_types`/`info_keys` "on `StructuredCallResult`", but `StructuredCallResult` lives in `app/llm/base.py`, which Task 1's `<files>` did not list.
- **Fix:** added the two optional fields (with a names-only comment) to `base.py`.
- **Files modified:** `app/llm/base.py`
- **Verification:** `tests/llm` 87 passed; the observation tests assert the fields.
- **Committed in:** `3acff0d` (Task 1 GREEN)

**2. [Rule 3 - Blocking] The stale "session body is an empty object" assertion**
- **Found during:** Task 1 GREEN
- **Issue:** `tests/llm/test_complete_structured.py::test_the_session_body_is_an_empty_object` asserted the session POST body was `{}`. The session body now legitimately carries the model and the deny ruleset, so the assertion was stale, not a regression.
- **Fix:** renamed and rewrote it to assert the session model shape and the presence of `permission`.
- **Files modified:** `tests/llm/test_complete_structured.py`
- **Verification:** `tests/llm` 87 passed.
- **Committed in:** `3acff0d` (Task 1 GREEN)

**3. [Rule 1 - Bug] The leak assertion is scoped to the observation, not the whole result**
- **Found during:** Task 1 RED design
- **Issue:** the plan asks to "assert the sentinel appears nowhere on the result", but `StructuredCallResult.raw` deliberately holds the parsed body in memory for the current call (P9) — a literal "nowhere on the result" assertion cannot hold without removing a documented field.
- **Fix:** the tests assert the sentinel is absent from `part_types`, `info_keys`, the `llm.structured_response` log line, the rendered page and the `llm_calls` row, with a comment recording that `raw` is the one in-memory holder by design and is never persisted or logged.
- **Files modified:** `tests/llm/test_trust_boundary.py`, `tests/api/test_llm_selftest.py`
- **Verification:** both tests pass; the observation surfaces carry no text.
- **Committed in:** `31de1b1`, `f0df570`

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug)
**Impact on plan:** None changed the security design. Item 1 is a file the plan's list omitted; item 2 is expected churn from the session-body change; item 3 keeps the leak proof honest against a documented in-memory field.

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Notes |
|------|-----|-------|----------|-------|
| 1 | `31de1b1` (test) | `3acff0d` (feat) | — | RED was a **genuine assertion failure** for the tools policy (a `"*"` key did not raise; an empty map was emitted) alongside missing-attribute failures for the not-yet-written permission names, `to_session_body`, `DEFAULT_DENY_RULES` and the observation fields; 3 tests passed because their behaviour already held. |
| 2 | n/a (not TDD) | `98d80c5` (feat) | — | A guard extension; its proof is the guard suite plus the guard-can-fail companion. |
| 3 | n/a (not TDD) | `f0df570` (feat) | — | A route/template extension; the Leak sentinel is its proof. |

## Issues Encountered

- **The plan ledger file for this dispatch was not created before the first commit** (an omission in the executor's own setup): `plan_head_before` was reconstructed from the documented pre-plan HEAD (`f0911be`) and the measured count is 4. Recorded rather than back-dated silently.
- **The observation is only meaningful on a live call.** With the offline stub it renders "not reported"/"absent", which is honest: the stub is not a server response. The live observation is the operator's `unrun-verify`.
- **`/doc`'s tool semantics remain experimental.** `GET /experimental/tool/ids` is deliberately not pinned or called; the deny uses the documented `permission` ruleset instead of a discovered tool-name list (T-3-20).

## Known Stubs

None. Every deliverable is implemented and asserted in the default lane; the only deferred item is the operator's live observation, recorded as an `unrun-verify` because the sandbox must not exercise the live server.

## Threat Flags

None — no new surface. This plan mitigates T-3-01 (no `system`-from-data path; the value is a bare reference), T-3-03 (documented default-deny ruleset plus the observation), T-3-18 (scoped import guard), T-3-19 (names-only observation with a sentinel proof) and T-3-20 (no experimental surface pinned), all already in the plan's threat register.

## User Setup Required

None - no external service configuration required. The default tool posture needs no operator action; if a future opencode server reshapes the ruleset, `DEFAULT_DENY_RULES` is the one place to change.

## Next Phase Readiness

- **Success criterion 4 is satisfied structurally.** Untrusted content has exactly one channel; the deny is enforced in the documented place and observed on every call; and no LLM HTTP/process path exists outside `app/llm/`.
- **Phase 5 gets a safer backend.** Ranking will feed real listing text as `parts`; the port's default-deny posture and the observation travel with it unchanged.
- **Operator still to do (end-of-phase):** with the selftest result page open on a real call, confirm the returned parts carry no tool invocation, the rendered system prompt is the module constant, and `info_keys` contains the structured key — appended to `.planning/WINDOWS.md`.
- **`PLAT-02` stays open by design**; only 03-07 remains before the shared-ID gate can release it.

---
*Phase: 03-llm-port-structured-output*
*Completed: 2026-09-17*

## Self-Check: PASSED

- All ten plan files exist on disk (`tests/llm/test_trust_boundary.py` plus the nine modified files).
- All four plan commits are present (`31de1b1`, `3acff0d`, `98d80c5`, `f0df570`).
- Measured commit count from the plan ledger: 4 (`git rev-list --count f0911be..HEAD`).
