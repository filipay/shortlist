---
phase: 03-llm-port-structured-output
plan: 08
subsystem: llm
tags: [gap-closure, retries, plat-04, trust-boundary, tools-grant, classification, d-12, wr-01, wr-03]

# Dependency graph
requires:
  - phase: 03-llm-port-structured-output
    provides: "03-01/03-03's complete_structured port + adapter, the Recorder fake transport, and 03-06's deny ruleset and builders"
provides:
  - "complete_structured(..., retries: int | None = None) on BOTH the port and the adapter, so an omitting caller is bounded by Settings.opencode_max_retries"
  - "The port's tools: Sequence[str] grant is converted to the builder's {name: True} map and forwarded; the fail-closed default emits no message-level tools key"
  - "A non-parseable info.structured is an invalid outcome that preserves provider/model/agent and part_types/info_keys"
  - "Corrected ProbeResult salvage docstring (remove-and-revalidate, no PydanticUseDefault marker)"
affects: [05-ranking, 09-gap-closure]

# Actuals (#2632) — same estimateTokens scale (chars/4) as the plan's estimate.
actuals:
  tokens: 3269
  tasks: 3
  commits: 3
  plan_head_before: 3fa7cf741e929304cb5f7877642b7737ba97a5ff

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A configuration default belongs in Settings and the parameter default must be None, or the documented fallback is dead code"
    - "Convert at the adapter boundary: a port signature stays ergonomic (Sequence[str]) while the wire builder keeps its stricter Mapping[str, bool]"
    - "Except-clause order is load-bearing when the caught types subclass each other (ValidationError before ValueError)"
    - "A model-output defect is `invalid` with identity preserved, never an anonymous generic `error`"

key-files:
  created: []
  modified:
    - app/llm/base.py
    - app/llm/opencode_server.py
    - app/domain/schemas/probe.py
    - tests/llm/test_complete_structured.py
    - tests/llm/test_trust_boundary.py

key-decisions:
  - "Both the port and the adapter take `retries: int | None = None`; the existing `budget = retries if retries is not None else settings.opencode_max_retries` line becomes the live default path, so PLAT-04's limits-are-configuration rule holds for an omitting caller."
  - "The port keeps `tools: Sequence[str] = ()` (locked by 03-CONTEXT); the adapter converts a non-empty sequence to `{name: True}` and passes it to `to_message_body`, while an empty sequence stays None so no message-level tools key is sent (fail-closed). `to_message_body` itself is unchanged, so its wildcard guard still fires on a `\"*\"` name."
  - "The `except ValueError` clause is placed AFTER `except ValidationError` because ValidationError subclasses ValueError: a genuine schema failure keeps its 'validation failed' message and only a non-JSON payload reaches the new branch."
  - "No caller was changed. app/api/settings.py already passes `settings.opencode_max_retries` explicitly, so the default-path fix is proven by the new test rather than by altering the shipped route."

patterns-established:
  - "When a parameter documents a Settings-supplied default, the parameter default must be None — pin it with a test that patches the setting and counts POSTs"
  - "Forward an accepted parameter or delete it; an accepted-but-discarded argument is a silent no-op"

requirements-completed: [PLAT-02]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "An omitted `retries` on complete_structured is bounded by settings.opencode_max_retries, so the retry ceiling is configuration on the default path (closes Gap 1/Gap 2 / WR-02)."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_an_omitted_retries_honours_the_settings_ceiling"
        status: pass
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_the_client_loop_is_bounded_by_the_retries_argument"
        status: pass
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_a_connect_error_is_unreachable"
        status: pass
    human_judgment: false
  - id: D2
    description: "An explicit tool grant passed to the port reaches the emitted message body, while the default still emits no message-level tools key (closes WR-01)."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_an_explicit_tool_grant_reaches_the_message_body"
        status: pass
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_no_tool_grant_by_default"
        status: pass
      - kind: unit
        ref: "tests/llm/test_trust_boundary.py#test_the_session_request_actually_sends_the_deny_ruleset"
        status: pass
    human_judgment: false
  - id: D3
    description: "A non-parseable info.structured is classified `invalid` and keeps the per-call D-12 identity and trust-boundary observation; the probe salvage docstring matches the code (closes WR-03)."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_a_non_parseable_structured_payload_is_invalid_and_keeps_identity"
        status: pass
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_an_unparseable_json_200_is_an_error_with_the_parse_exception"
        status: pass
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_a_validation_error_is_invalid_with_the_validation_message"
        status: pass
    human_judgment: false

# Metrics
duration: 5min
completed: 2026-09-18
status: complete
---

# Phase 3 Plan 08: Gap Closure — Retry Ceiling, Tool Grant, Parse-Failure Identity Summary

**An omitted retry argument now honours `OPENCODE_MAX_RETRIES`, an explicit tool grant reaches the message body, and a broken model payload is an attributable `invalid` outcome — closing the phase BLOCKER plus two adapter warnings on the trust-boundary path.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-09-18T10:16:34Z
- **Completed:** 2026-09-18T10:21:49Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- **Gap 1/Gap 2 (WR-02) closed.** `complete_structured` declares `retries: int | None = None` on both the port (`app/llm/base.py`) and the adapter (`app/llm/opencode_server.py`), so the documented `settings.opencode_max_retries` fallback is the live default path. New test patches the setting to 7 and observes exactly 7 completion POSTs and `attempts == 7`; the existing explicit-bound and unpatched-default tests stay green unchanged.
- **WR-01 closed.** The port's `tools: Sequence[str]` is converted to the builder's `{name: True}` grant map and forwarded. An explicit `tools=("read", "bash")` now produces `tools == {"read": True, "bash": True}` in the emitted completion body; an omitted `tools` still emits no message-level `tools` key, so the fail-closed default and the session `permission` deny are untouched.
- **WR-03 closed.** `_classify_message_response` gained an `except ValueError` clause ordered after `except ValidationError`. A non-JSON `info.structured` is now `status == "invalid"` / `error_kind == "invalid"` with `attempts` equal to the issued POST count and `provider`/`model`/`agent`/`part_types`/`info_keys` preserved, instead of escaping to the generic handler as `error`/`ValueError` with `attempts=0` and no identity.
- **Docstring corrected.** `app/domain/schemas/probe.py` no longer claims the salvage uses a `PydanticUseDefault` marker; it now describes remove-and-revalidate and keeps the point that every `ProbeResult` field declares a default.

## Task Commits

Each task was committed atomically:

1. **Task 1: The client retry ceiling defaults to Settings, not a literal** - `fdde3fa` (fix)
2. **Task 2: An explicit tool grant reaches the message body** - `ee66d0a` (fix)
3. **Task 3: A non-parseable structured payload keeps its identity and observation** - `2b0c137` (fix)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified

- `app/llm/base.py` — port `complete_structured` `retries: int | None = None`; docstring names `Settings.opencode_max_retries` as the adapter-applied default
- `app/llm/opencode_server.py` — concrete `retries: int | None = None`; tool-name sequence converted and forwarded to `to_message_body`; `except ValueError` parse-failure branch preserving identity and observation
- `app/domain/schemas/probe.py` — corrected salvage docstring
- `tests/llm/test_complete_structured.py` — `test_an_omitted_retries_honours_the_settings_ceiling`, `test_a_non_parseable_structured_payload_is_invalid_and_keeps_identity`
- `tests/llm/test_trust_boundary.py` — `test_an_explicit_tool_grant_reaches_the_message_body`, `test_no_tool_grant_by_default`

## Decisions Made

- **Settings supplies the default, the parameter default is None.** The plan's key_link held: without the nullable signature on both the port and the adapter, an omitting caller passes an int and the fallback stays unreachable.
- **Convert at the adapter, keep both signatures as documented.** The port keeps `Sequence[str]` (locked by 03-CONTEXT) and the builder keeps `Mapping[str, bool]`; the conversion is the only place that reconciles them, and the wildcard guard continues to apply to a port-level grant.
- **Except-clause order is load-bearing.** `ValidationError` subclasses `ValueError`, so the validation branch must remain first; the existing validation-error test proves a genuine schema failure still reports "validation failed".
- **No caller touched.** `app/api/settings.py` already passes the setting explicitly, so the default-path fix is proven by the new test rather than by modifying the shipped route.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The retry ceiling on the default path is configuration, so Phase 5 can size its ranking-call spend via `OPENCODE_MAX_RETRIES` without touching code.
- A future caller passing an explicit tool grant now gets a real grant rather than a silent no-op; the enforced deny remains the session `permission` ruleset.
- A model-output parse defect is attributable in `llm_calls` telemetry (identity + observation preserved), so a broken model response is a recorded finding rather than a mystery.
- The phase's two human-verification items (live `opencode serve` call; live `/doc` drift lane) are unchanged and remain operator-run (WINDOWS #5/#6).

## Self-Check: PASSED

- `app/llm/base.py` and `app/llm/opencode_server.py` both declare `retries: int | None = None` (no `retries: int = 2` remains).
- All four new test functions exist and pass; full suite: **830 passed, 3 deselected** (baseline 826 + 4 new).
- Commits `fdde3fa`, `ee66d0a`, `2b0c137` present in history; no file deletions in any task commit.

---

*Phase: 03-llm-port-structured-output*
*Completed: 2026-09-18*
