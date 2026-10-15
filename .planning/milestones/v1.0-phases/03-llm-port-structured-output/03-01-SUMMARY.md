---
phase: 03-llm-port-structured-output
plan: 01
subsystem: llm-port
tags: [opencode, structured-output, pydantic, httpx, llm_calls, settings, tdd, tracer]

# Dependency graph
requires:
  - phase: 01-walking-skeleton-foundations
    provides: "the LLMBackend port (health/discovery), ProviderModel redaction, get_llm_backend DI, ConfigMap"
  - phase: 02-clean-filtered-queryable-queue
    provides: "the repository conventions, the id=merges-table render idioms, and the filter-stage LlmCall==0 guard"
provides:
  - "app/llm/contract.py — the single home of the pinned opencode wire vocabulary (D-54/D-56)"
  - "LLMBackend.complete_structured + OpenCodeServerBackend implementation (session → message → info.structured → validated typed result)"
  - "app/llm/builders.py — pure request builders; parts is the only untrusted channel"
  - "app/domain/schemas/probe.py — ProbeResult (every field defaulted for the 03-03 salvage path)"
  - "app/db/repositories/llm_call_repo.py — the llm_calls write path (never commits; run_id defaults NULL)"
  - "POST /settings/llm-test — the operator-facing selftest that records one purpose='probe' row"
  - "app/config.py — three Phase-3 ceilings (completion timeout + two retry counts)"
affects: [03-02, 03-03, 03-04, 03-05, 03-06, 03-07, 05-ranking]

# Actuals (#2632) — pairs with the plan's estimate on the same estimateTokens scale (chars/4).
actuals:
  tokens: 17056
  tasks: 3
  commits: 7

# Tech tracking
tech-stack:
  added: []   # zero new packages this phase (threat T-3-SC)
  patterns:
    - "Wire vocabulary pinned in one no-I/O module; builders/parsers read the constants, never literals"
    - "Failure as a value: complete_structured is total and returns StructuredCallResult, never raises"
    - "Validation at the llm/ boundary: schema.model_validate(...) before the caller sees anything"
    - "Redaction as a type property: StructuredCallResult carries identifiers/counts only; raw is in-memory only"
    - "Repositories own SQL, never commit; the route owns the single commit"

key-files:
  created:
    - app/llm/contract.py
    - app/llm/builders.py
    - app/domain/schemas/__init__.py
    - app/domain/schemas/probe.py
    - app/db/repositories/llm_call_repo.py
    - tests/llm/test_complete_structured.py
    - tests/api/test_llm_selftest.py
  modified:
    - app/llm/base.py
    - app/llm/opencode_server.py
    - app/llm/__init__.py
    - app/config.py
    - app/api/settings.py
    - app/web/templates/html/settings.html
    - tests/conftest.py
    - tests/test_auth_seam.py
    - tests/fixtures/opencode_providers.json
    - tests/llm/test_discovery_redaction.py
    - tests/api/test_health.py

key-decisions:
  - "Pin the request field as `format` and the response as `info.structured` (live 1.18.31), each as a single constant in app/llm/contract.py; no adaptive 'accept either name' fallback (D-54)."
  - "parse_providers accepts both the live dict shape (models keyed by model id, credential field `key`) and the legacy list shape; OPENCODE_MODEL resolves through discovery and fails loud on a miss instead of silently omitting `model`."
  - "The selftest is a plain full-page POST with no HTMX, writes exactly one llm_calls row (purpose='probe', run_id NULL) and creates no runs row (D-50); server_version travels on the returned record but is not persisted until migration 0003 (plan 03-04)."

patterns-established:
  - "contract.py is the one place a wire rename changes; a builder/parser literal is a bug"
  - "Every new ceiling is a Settings field with a comment naming why it is configuration, not a constant (PLAT-04)"
  - "A new route joins the current_user seam and tests/test_auth_seam.py's explicit expected set"

requirements-completed: [PLAT-02, PLAT-05]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "complete_structured completes through the port with a fake transport: builder emits the pinned wire shape, backend creates a session, sends a text-only message, reads info.structured, and returns a validated typed ProbeResult; failure is a value."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_a_schema_constrained_call_returns_a_validated_typed_result"
        status: pass
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_the_message_protocol_makes_exactly_two_posts"
        status: pass
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_a_transport_failure_is_a_value_never_an_exception"
        status: pass
    human_judgment: false
  - id: D2
    description: "Discovery accepts the live dict shape and the legacy list shape; _resolve_model derives the provider and fails loud with the model id in the error; the sentinel credential never leaves the parser."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_discovery_redaction.py#test_discovery_returns_only_provider_and_model_identifiers"
        status: pass
      - kind: unit
        ref: "tests/llm/test_discovery_redaction.py#test_resolve_model_fails_loud_on_a_miss"
        status: pass
      - kind: unit
        ref: "tests/llm/test_discovery_redaction.py#test_the_dict_shape_branch_is_actually_exercised"
        status: pass
    human_judgment: false
  - id: D3
    description: "One POST /settings/llm-test records exactly one llm_calls row (purpose='probe', run_id IS NULL), creates no runs row, performs no call on a plain GET, and renders D-52's full detail (status, cause, attempts, latency) rather than a badge."
    requirement: PLAT-02
    verification:
      - kind: integration
        ref: "tests/api/test_llm_selftest.py#test_one_post_writes_exactly_one_probe_row_and_no_run"
        status: pass
      - kind: integration
        ref: "tests/api/test_llm_selftest.py#test_the_page_renders_every_recorded_value"
        status: pass
      - kind: integration
        ref: "tests/api/test_llm_selftest.py#test_a_plain_get_performs_no_call_and_writes_no_row"
        status: pass
    human_judgment: false
  - id: D4
    description: "The request-side structured-output vocabulary PLAT-05 pins is a single set of constants, and the builder emits exactly those names with no server running."
    requirement: PLAT-05
    verification:
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_the_structured_output_key_is_the_single_pinned_name"
        status: pass
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_every_part_is_wrapped_as_a_text_part"
        status: pass
    human_judgment: false
  - id: D5
    description: "One REAL schema-constrained call completes against the operator's own opencode server with no second provider key configured, recorded as exactly one probe row (PLAT-02 success criterion 1's live half)."
    requirement: PLAT-02
    verification: []
    human_judgment: true
    rationale: "Needs the user's live opencode server and a genuinely no-second-key environment; the default lane must never open a socket or read a provider credential. Recorded in 03-VALIDATION.md's Manual-Only table and appended to .planning/WINDOWS.md as an unrun-verify for the operator."

# Metrics
duration: 21 min
completed: 2026-09-17
status: complete
---

# Phase 3 Plan 01: LLM Port + Structured Output Summary

**One schema-constrained call now completes through the `LLMBackend` port against a fake transport and returns a validated typed `ProbeResult`, with the whole wire contract pinned in `app/llm/contract.py` and an operator button on `/settings` that records the full outcome as a single `llm_calls` row.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-09-17T19:42:58Z
- **Completed:** 2026-09-17T20:07Z
- **Tasks:** 3 (Task 1 tracer + TDD, Task 2 TDD, Task 3 auto)
- **Files modified/created:** 18 (7 created, 11 modified)
- **Full suite:** 746 passed, 2 deselected (~122 s; baseline was 712 passed)

## Accomplishments

- **The port can actually call the model.** `LLMBackend.complete_structured` + `OpenCodeServerBackend` implement session create → message send → read `info.structured` → `schema.model_validate(...)`. The tracer proves the happy path end to end with a fake transport, and the default lane opens no socket.
- **The wire contract has exactly one home.** `app/llm/contract.py` holds every pinned name (`format` not `outputFormat`; `info.structured` not `structured_output`; the message model shape `providerID`/`modelID`; `retryCount` optional). The builders read only those constants.
- **Discovery works against the server the project targets.** `parse_providers` accepts the live dict shape (verified 1.18.31) *and* the legacy list shape; the fixture was transcribed to the live shape and its sentinel now scans the real `key` field.
- **A wrong `OPENCODE_MODEL` is loud.** `_resolve_model` derives the provider from discovery, resolves ambiguity by sorted provider id, and fails loud naming the model rather than silently omitting `model`.
- **The operator can see what happened.** `POST /settings/llm-test` performs one real call, writes exactly one `llm_calls` row (`purpose='probe'`, `run_id IS NULL`, no `runs` row) and renders status, cause, attempts and latency — never a bare badge.
- **The pipeline stays LLM-free.** `run_pipeline()` still writes zero `llm_calls` rows (D-49), asserted by the existing `tests/pipeline/test_filter_stage.py` guard.

## Task Commits

Each task was committed atomically. TDD tasks produced a RED test commit and a GREEN implementation commit:

1. **Task 1: The schema-constrained call completes through the port** — `1586392` (test, RED) → `f8356ef` (feat, GREEN)
2. **Task 2: Discovery accepts the live shape and resolves the model** — `a4c4465` (test, RED) → `448adde` (test, GREEN)
3. **Task 3: The operator can run one real call from `/settings`** — `e06abe7` (feat)
4. **Follow-ups inside the plan:** `d8f460b` (fix: unstyled template class) · `2c8c609` (refactor: unused import)

**Plan metadata:** the `docs(03-01)` commit immediately following this file (SUMMARY + STATE + ROADMAP + REQUIREMENTS).

## Files Created/Modified

- `app/llm/contract.py` — **created**; the single home of the pinned wire vocabulary (D-54/D-56)
- `app/llm/builders.py` — **created**; pure `to_message_parts` / `to_message_body`; port strings → `TextPartInput` on the wire
- `app/domain/schemas/__init__.py` — **created**; package marker naming §6.2's schemas-in-domain / validation-in-llm split
- `app/domain/schemas/probe.py` — **created**; `ProbeResult`, every field defaulted (P11)
- `app/db/repositories/llm_call_repo.py` — **created**; `PURPOSES`/`STATUSES`, `LlmCallRecord`, `record_llm_call` (validates before SQL, SAVEPOINT, never commits, `run_id` defaults NULL)
- `tests/llm/test_complete_structured.py` — **created**; the tracer test (14 cases)
- `tests/api/test_llm_selftest.py` — **created**; route + repository contract (13 cases)
- `app/llm/base.py` — `StructuredCallResult` + the `complete_structured` Protocol method; `health()` unchanged
- `app/llm/opencode_server.py` — both-shape `parse_providers`, completion client, `_resolve_model`, `_create_session`, total `complete_structured`
- `app/llm/__init__.py` — re-exports `StructuredCallResult`; `get_llm_backend()` shape unchanged
- `app/config.py` — `opencode_completion_timeout_seconds`, `opencode_max_retries`, `opencode_structured_retry_count`
- `app/api/settings.py` — `LLM_TEST_PATH`, `SELFTEST_SYSTEM_PROMPT`, `SELFTEST_USER_PART`, `_latest_probe_row`, extended `_settings_context`, `POST /settings/llm-test`
- `app/web/templates/html/settings.html` — the "LLM backend" card: plain POST form + D-52 result block
- `tests/conftest.py` — `OfflineLLMBackend.complete_structured` (P10)
- `tests/test_auth_seam.py` — `EXPECTED_SEAM_ROUTES` gains `/settings/llm-test`
- `tests/fixtures/opencode_providers.json` — transcribed to the live 1.18.31 shape
- `tests/llm/test_discovery_redaction.py` — live-shape + legacy-shape + guard-can-fail + `_resolve_model` cases
- `tests/api/test_health.py` — fixture sentinel read updated (`key`, deviation 1)

## Decisions Made

- **`format` + `info.structured`, pinned once.** The live `/doc` and a live discovery fetch settled the roadmap's `format` vs `outputFormat` flag. The response field is `info.structured` — the docs' `structured_output` occurs zero times in the live spec. No fallback lookup.
- **Model resolution derives the provider.** `OPENCODE_MODEL` is a bare id; the provider comes from the server's own discovery, so the dead config becomes live (D-10) without changing the documented setting's meaning.
- **The selftest is a plain POST with one persisted row.** No HTMX (an `hx-post` on `/settings` fails an existing guard), no synthetic run (D-50), and the full cause is rendered (D-52).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `tests/api/test_health.py` read the fixture's old `api_key` field**
- **Found during:** Task 3 (verify command `tests/api/test_health.py`)
- **Issue:** Task 2 renamed the fixture's credential-adjacent field from `api_key` to the live 1.18.31 name `key`. `test_health.py` builds its sentinel with `["providers"][0]["api_key"]` and failed at **collection** (`KeyError`), which would have failed the whole default lane.
- **Fix:** read `["providers"][0]["key"]` (still the sentinel value, so the redaction guard is unchanged and non-vacuous).
- **Files modified:** `tests/api/test_health.py`
- **Verification:** `tests/api/test_health.py` 11 tests pass; full suite green.
- **Committed in:** `e06abe7` (Task 3 commit)

**2. [Rule 1 - Bug] An unstyled template class broke the stylesheet-coverage guard**
- **Found during:** the full-suite wave gate
- **Issue:** the new result block used `class="settings-result"`, which has no rule in `static/vendor/app.css`; `tests/test_stylesheet_coverage.py` requires every template class to have a rule.
- **Fix:** dropped the class (the block's `id="llm-test-result"` is sufficient).
- **Files modified:** `app/web/templates/html/settings.html`
- **Verification:** `tests/test_stylesheet_coverage.py` plus the selftest/settings page tests pass; full suite green.
- **Committed in:** `d8f460b`

**3. [Rule 1 - Bug] An unused import failed `ruff check`**
- **Found during:** lint pass after Task 3
- **Issue:** `STRUCTURED_RESPONSE_PATH` was imported but not referenced in `tests/llm/test_complete_structured.py`.
- **Fix:** removed the import.
- **Files modified:** `tests/llm/test_complete_structured.py`
- **Verification:** `ruff check` clean across every touched file.
- **Committed in:** `2c8c609`

---

**Total deviations:** 3 auto-fixed (1 blocking, 2 bugs)
**Impact on plan:** All three were necessary for the default lane and lint to stay green; none changed scope or design. Note: an intermediate `ruff format` pass was reverted because the project's committed style wraps near 88 columns while `pyproject.toml` declares `line-length = 100`; only the intended edits were kept.

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Notes |
|------|-----|-------|----------|-------|
| 1 | `1586392` (test) | `f8356ef` (feat) | — | RED was a **collection/import failure** (`app.llm.contract` and the port extension did not exist). `workflow.tdd_mode` is `false`, so the enforced `check tdd-red-evidence` gate is inactive; the strict #3770 classifier would call a load failure INVALID_RED. Recorded rather than papered over. |
| 2 | `a4c4465` (test) | `448adde` (test) | — | RED was a **genuine assertion failure**: the target test asserted the live-shape pairs against the committed legacy-list fixture (1 failed, 29 passed). The GREEN commit is a `test(...)` commit because the production parser fix shipped in Task 1; Task 2's artefact is the fixture + guard alignment, so `feat` would be a mislabel. |

## Issues Encountered

- **Task 1's RED is an import failure, not an assertion failure.** The plan collects the new modules and the test in a single task, so the test cannot import them before they exist. The honest options were a load-failure RED or authoring throwaway interface stubs; the load-failure RED was chosen and documented. The enforced TDD gate is off (`tdd_mode: false`), so nothing downstream blocks on it.
- **Task 2's RED is a test-vs-fixture failure.** Because Task 1's acceptance criteria require the both-shape parser, Task 2's production change had already shipped; its RED is the target assertion failing against the not-yet-updated fixture. Documented above.

## Known Stubs

These are **planned deferrals** owned by later plans in this phase, not unplanned gaps. They do not prevent this plan's goal (a completing, recorded structured call) from being achieved.

| Stub | File | Reason / owner |
|------|------|----------------|
| `server_version` is returned on `LlmCallRecord` but not persisted (no column) | `app/db/repositories/llm_call_repo.py` | Migration 0003 adds `LlmCall.server_version` (plan 03-04). Until then the immediate render shows it and a reload shows "not reported". |
| `error_kind` renders on the immediate POST only (no column) | `app/api/settings.py`, `settings.html` | The `unreachable`/`timeout`/`http_…` taxonomy and its persistence arrive with plans 03-03/03-04. |
| `complete_structured` does not send a `tools` deny map | `app/llm/opencode_server.py` | The documented deny encoding is plan 03-06 (Pitfall P5); a blanket early deny risks suppressing the server's internal structured-output tool. |
| No `StructuredOutputError` classification, client retry loop, or salvage path | `app/llm/opencode_server.py` | Plans 03-03 (taxonomy + salvage) and 03-06 (trust boundary). A missing payload is classified `invalid` today, never a crash. |

## Threat Flags

None — the new surface (`POST /settings/llm-test`, the completion timeout ceiling, the completion client) is already enumerated in the plan's threat register (T-3-06, T-3-07). No new network endpoint, auth path, file-access pattern or schema change was introduced.

## User Setup Required

None — no external service configuration required. (The operator-run live lane is a verification activity, not setup; see below.)

## Next Phase Readiness

- **Ready for the rest of Phase 3.** `app/llm/contract.py` is the seam 03-02 needs for the `/doc` snapshot test; `complete_structured`'s happy path is the seam 03-03 extends with the failure taxonomy and salvage; `record_llm_call` is the writer 03-04 adds `latest_probe`/`llm_totals_for_run` and the `server_version` column to; the three `Settings` ceilings are what 03-05 forwards through `compose.yml`.
- **Operators still to do (deliberately, at end-of-phase):** run the live lane and invoke "Test LLM backend" against the real opencode server with no second provider key configured, then confirm exactly one new `llm_calls` row (`purpose='probe'`, `run_id IS NULL`) and no new `runs` row. Recorded in `03-VALIDATION.md`'s Manual-Only table and appended to `.planning/WINDOWS.md` as an `unrun-verify`.
- **Open Question Q1 is materially closed for this plan:** the live spec and the research both say `info.structured`; the operator's first live call should print `list(body["info"])` once to confirm on the running server.

---
*Phase: 03-llm-port-structured-output*
*Completed: 2026-09-17*

## Self-Check: PASSED

- All six created files exist on disk (`app/llm/contract.py`, `app/llm/builders.py`, `app/domain/schemas/probe.py`, `app/db/repositories/llm_call_repo.py`, `tests/llm/test_complete_structured.py`, `tests/api/test_llm_selftest.py`).
- All seven plan commits are present (`1586392`, `f8356ef`, `a4c4465`, `448adde`, `e06abe7`, `d8f460b`, `2c8c609`).
- Measured commit count from the plan ledger: 7 (`git rev-list --count 638d600..HEAD`).
