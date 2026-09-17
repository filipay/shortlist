---
phase: 03-llm-port-structured-output
verified: 2026-09-17T23:50:27Z
status: gaps_found
score: 29/32 must-haves verified
covered_files:
  - .env.example
  - .planning/REQUIREMENTS.md
  - .planning/phases/03-llm-port-structured-output/03-01-PLAN.md
  - .planning/phases/03-llm-port-structured-output/03-01-SUMMARY.md
  - .planning/phases/03-llm-port-structured-output/03-02-PLAN.md
  - .planning/phases/03-llm-port-structured-output/03-02-SUMMARY.md
  - .planning/phases/03-llm-port-structured-output/03-03-PLAN.md
  - .planning/phases/03-llm-port-structured-output/03-03-SUMMARY.md
  - .planning/phases/03-llm-port-structured-output/03-04-PLAN.md
  - .planning/phases/03-llm-port-structured-output/03-04-SUMMARY.md
  - .planning/phases/03-llm-port-structured-output/03-05-PLAN.md
  - .planning/phases/03-llm-port-structured-output/03-05-SUMMARY.md
  - .planning/phases/03-llm-port-structured-output/03-06-PLAN.md
  - .planning/phases/03-llm-port-structured-output/03-06-SUMMARY.md
  - .planning/phases/03-llm-port-structured-output/03-07-PLAN.md
  - .planning/phases/03-llm-port-structured-output/03-07-SUMMARY.md
  - alembic/versions/0003_llm_call_server_version.py
  - app/api/settings.py
  - app/config.py
  - app/db/models.py
  - app/db/repositories/llm_call_repo.py
  - app/db/repositories/queue_repo.py
  - app/domain/models.py
  - app/domain/schemas/probe.py
  - app/llm/base.py
  - app/llm/builders.py
  - app/llm/contract.py
  - app/llm/opencode_server.py
  - app/pipeline/run.py
  - app/pipeline/stages.py
  - app/web/templates/html/_listing_row.html
  - app/web/templates/html/settings.html
  - compose.yml
  - tests/llm/test_complete_structured.py
  - tests/llm/test_contract_live.py
  - tests/llm/test_contract_snapshot.py
  - tests/llm/test_salvage.py
  - tests/llm/test_trust_boundary.py
  - tests/test_config.py
  - tests/test_import_discipline.py
covered_digest: "v1:sha256:c49f16de28cd0b7e3292f10ee6f7ad0c9190794d67723a301b1588f4aa54d69b"
behavior_unverified: 2
overrides_applied: 0
gaps:
  - truth: "Every Phase-3 ceiling is a Settings field with a documented default and is asserted by the config guard, so no completion timeout or retry count is a literal (PLAT-04)."
    status: failed
    reason: >-
      WR-02 confirmed against the code. `OpenCodeServerBackend.complete_structured`
      declares `retries: int = 2` (app/llm/opencode_server.py:356; the port at
      app/llm/base.py:122 declares the same literal), so the documented fallback
      `budget = retries if retries is not None else settings.opencode_max_retries`
      (app/llm/opencode_server.py:402) is unreachable for any caller that omits the
      argument. Reproduced in-process: with `settings.opencode_max_retries = 7` and
      `retries` omitted, exactly 2 message POSTs were issued and `attempts == 2`.
      The shipped selftest route passes `settings.opencode_max_retries` explicitly
      (app/api/settings.py:412), which masks the defect for the app's only current
      caller, but a literal retry count now governs the default and PLAT-04's
      "limits are configuration, not constants" is violated for the next caller.
    artifacts:
      - path: "app/llm/opencode_server.py"
        issue: "line 356 `retries: int = 2`; line 402 Settings fallback is dead code"
      - path: "app/llm/base.py"
        issue: "line 122 protocol declares `retries: int = 2` and the docstring promises `Settings` supplies the default"
    missing:
      - "Change the parameter to `retries: int | None = None` in both app/llm/base.py and app/llm/opencode_server.py (keep the existing `retries if retries is not None else settings.opencode_max_retries` line)."
      - "Add a default-lane test asserting an omitted `retries` honours a patched `settings.opencode_max_retries` (e.g. 7 → 7 POSTs)."
  - truth: "Both retry ceilings are configuration (03-03 success criterion); 'Settings.opencode_max_retries still supplies the default ceiling' (03-03 acceptance criterion)."
    status: failed
    reason: >-
      Same root cause as the first gap (WR-02). The caller-supplied bound itself is
      honoured — a schema failure is never retried client-side and `retries=3` issues
      exactly 3 POSTs (tests/llm/test_complete_structured.py:593-622, green) — so
      03-03's stated retry-BOUND truth ("the parameter governs the loop, not a
      direct read of Settings") still holds. What is falsified is 03-03's companion
      claim that Settings supplies the DEFAULT: whenever `retries` is omitted the
      literal 2 governs, not `settings.opencode_max_retries`.
    artifacts:
      - path: "app/llm/opencode_server.py"
        issue: "line 402 documented fallback unreachable"
    missing:
      - "Same one-line fix as the first gap; no separate change."
behavior_unverified_items:
  - truth: "The app completes a schema-validated structured call through the opencode backend with no second provider key configured (roadmap SC1 / 03-01 truth 1)."
    test: "Start the user's own `opencode serve` (no second provider key configured), open /settings, press 'Test LLM backend'."
    expected: "A validated ProbeResult is returned and rendered, and exactly one llm_calls row is written (purpose='probe', run_id IS NULL) with no new runs row."
    why_human: >-
      The default lane proves the full HTTP-shaped path against a fake transport, but
      the claim is that it completes through a REAL `opencode serve` sibling service
      with a real model; that requires the operator's server. Recorded as
      WINDOWS #5 / 03-VALIDATION.md Manual-Only.
  - truth: "An operator-run @pytest.mark.live test refetches /doc and diffs the live spec against the committed slice, failing loudly on drift (roadmap SC3 / 03-02 truth 4)."
    test: "On the host: OPENCODE_BASE_URL=http://127.0.0.1:4096 .venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py"
    expected: "0 divergent pointers and GET /global/health version == the fixture's _meta.server_version (1.18.31)."
    why_human: >-
      The lane is deselected by design (`addopts = \"-m 'not live'\"`) and the repo has
      no CI runner, so the default suite cannot exercise a live server. Recorded as
      WINDOWS #6 / 03-VALIDATION.md Manual-Only.
human_verification:
  - test: "Live real schema-constrained call from /settings against the user's opencode server with no second provider key configured."
    expected: "A validated result is shown; exactly one llm_calls row (purpose='probe', run_id IS NULL) and no new runs row."
    why_human: "Needs the operator's real server; the default lane's transport is a fake. (WINDOWS #5, SC1 / 03-01 truth 1.)"
  - test: "Operator live /doc drift lane (pytest -m live tests/llm/test_contract_live.py)."
    expected: "0 diffs against tests/llm/fixtures/opencode-doc.json; health version equals the committed _meta.server_version."
    why_human: "No CI runner and the lane is excluded by addopts by design. (WINDOWS #6, SC3 / 03-02 truth 4.)"
  - test: "Live trust-boundary observation: with the selftest result page open on a real call, confirm the returned parts carry no tool invocation, the rendered system prompt is the module constant, and info_keys contains the structured payload key."
    expected: "part_types shows only the text/structured mechanism; info_keys contains 'structured'; the system prompt equals SELFTEST_SYSTEM_PROMPT."
    why_human: "The default lane proves the deny ENCODING with a fake transport; only a live response shows the running server honoured it (and closes Open Question Q1). (WINDOWS #7, SC4.)"
  - test: "Confirm on the first live server call that the message body's `format` field and the response `info.structured` field are accepted (Open Question Q1)."
    expected: "The call reaches a validated result rather than 400/None."
    why_human: "The pinned names were resolved from the 1.18.31 spec; a real acceptance cannot be observed in the sandbox."
---

# Phase 3: LLM Port + Structured Output Verification Report

**Phase Goal:** Any schema-constrained LLM call works end to end through `opencode serve` as a sibling service, with the structured-output contract pinned by a failing test.
**Verified:** 2026-09-17T23:50:27Z
**Status:** gaps_found
**Re-verification:** No — initial verification
**Baseline checked:** `.venv/bin/python -m pytest -q` → **826 passed, 3 deselected** (142.3 s), matching STATE.md's recorded baseline. Targeted guard suite (orm-drift, no-pii-columns, migration-contract, import-discipline, contract-snapshot, trust-boundary) → 49 passed.

## Goal Achievement

### Roadmap Success Criteria

| # | Success Criterion | Status | Evidence |
| --- | ----------------- | ------ | -------- |
| 1 | App completes a schema-validated structured call through the opencode backend with no second provider key configured | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Port path present + wired: `LLMBackend.complete_structured` (`app/llm/base.py:113-132`), `OpenCodeServerBackend.complete_structured` (`app/llm/opencode_server.py:347-526`), selftest route (`app/api/settings.py:389-461`). No second provider key exists in `Settings` (`app/config.py:30-49`; only the optional `opencode_server_password`) and the request body carries no credential. Proven end-to-end against a fake transport (`tests/llm/test_complete_structured.py:321-349`); the REAL `opencode serve` call is operator-run (WINDOWS #5). |
| 2 | A schema violation is recorded as an explicit, retried run outcome rather than a silent failure | ✓ VERIFIED | Classification matrix green: `StructuredOutputError` → `invalid` + server `data.retries` (`test_complete_structured.py:473-490`), `ValidationError` → `invalid` (`:493-515`), connect → `error`/`unreachable`, read timeout → `timeout`, non-200 → `error`/`http_<code>` with bounded excerpt (`:563-575`), unparseable JSON 200 → `error` naming the parse exception (`:578-590`). `complete_structured` is total (`except Exception` at `opencode_server.py:519`); the selftest writes exactly one row (`tests/api/test_llm_selftest.py:55-72`). WR-03 caveat below. |
| 3 | A CI contract test reads the installed server's `GET /doc` and fails loudly if the structured-output field name changes — resolving the `format` vs `outputFormat` ambiguity | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED (default-lane pin ✓; live lane operator-run) | The ambiguity IS resolved and pinned: `FORMAT_FIELD = "format"` and `STRUCTURED_RESPONSE_PATH = ("info","structured")` (`app/llm/contract.py:35,50`), asserted against the committed slice with a negative control over raw fixture text (`tests/llm/test_contract_snapshot.py:113-184`) and a guard-can-fail companion (`:211-227`). The spec-reading half is `tests/llm/test_contract_live.py`, which is `@pytest.mark.live` and deselected (`pyproject.toml:55`; `--collect-only` confirms 87/88, 1 deselected). The repo has **no CI runner** (D-53); the live lane is operator-run (WINDOWS #6). |
| 4 | Untrusted listing text reaches the model only as user content (never the system prompt) and tools are disabled by default | ✓ VERIFIED (structural); live observation is a human item | `SELFTEST_SYSTEM_PROMPT` is a module constant with an AST-verified single `Constant` and no `%`/`.format` (`tests/api/test_llm_selftest.py:223-240`); the builder assigns `system` a bare `Name` (`tests/llm/test_trust_boundary.py:193-207`); `parts` is the only channel and emits text parts only (`:161-174`); the message body sends no `tools` key by default and rejects `"*"` (`:53-78`); the session carries the deny-only `permission` ruleset which `_create_session` actually sends (`app/llm/opencode_server.py:104-110, 319-326`; `tests/llm/test_trust_boundary.py:137-155`). The returned parts/info keys are observed and rendered (`:213-247`, `app/web/templates/html/settings.html:58-73`). Live confirmation = WINDOWS #7. |

### Observable Truths (plan `must_haves.truths`)

| # | Plan | Truth | Status | Evidence |
| --- | ---- | ----- | ------ | -------- |
| 1 | 03-01 | Schema-validated call completes through the opencode backend with no second provider key | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | See SC1; live call operator-run |
| 2 | 03-01 | Schema violation → explicit retried outcome; exactly one `llm_calls` row; no failure path raises | ✓ VERIFIED | `opencode_server.py:519-526`; `test_complete_structured.py:473-590`; `test_llm_selftest.py:55-72` |
| 3 | 03-01 | Untrusted content only as `parts`; port tools default empty; no param reaches `system` | ✓ VERIFIED | `builders.py:55-108`; `base.py:113-132`; `test_trust_boundary.py:180-207` |
| 4 | 03-01 | Default-lane test pins the request vocabulary; importing constants needs no network | ✓ VERIFIED | `test_contract_snapshot.py`; `contract.py` imports only `__future__` |
| 5 | 03-01 | Operator can trigger one call from `/settings`; exactly one probe row, `run_id IS NULL`, no `runs` row | ✓ VERIFIED | `settings.py:389-461`; `test_llm_selftest.py:55-104` (real-server execution = human item) |
| 6 | 03-01 | `run_pipeline()` writes zero `llm_calls` rows (D-49) | ✓ VERIFIED | `run.py:865-866` comment + no LLM import; `tests/pipeline/test_finish_llm_counters.py:135-162`; `tests/pipeline/test_filter_stage.py:197` |
| 7 | 03-02 | Default-lane test fails if the structured-output field name is absent from the snapshot | ✓ VERIFIED | `test_contract_snapshot.py:113-119`; fixture `opencode-doc.json` |
| 8 | 03-02 | Same test asserts the builder emits exactly the pinned names | ✓ VERIFIED | `test_contract_snapshot.py:190-205` |
| 9 | 03-02 | Negative control blocks `outputFormat`/`structured_output` | ✓ VERIFIED | `test_contract_snapshot.py:172-184` |
| 10 | 03-02 | Operator `@pytest.mark.live` test refetches `/doc`, diffs, makes no LLM call | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `test_contract_live.py:229-272` complete + collectable under `-m live`; not run in sandbox (WINDOWS #6) |
| 11 | 03-02 | Default lane structurally cannot run the live test; cheap guard makes it explicit | ✓ VERIFIED | `pyproject.toml:55-58`; `test_contract_snapshot.py:233-240`; collect-only 87/88, 1 deselected |
| 12 | 03-03 | `StructuredOutputError` and `ValidationError` → `ok=False`, `status='invalid'`, attempt count from server `data.retries` | ✓ VERIFIED | `opencode_server.py:734-763, 792-810`; `test_complete_structured.py:473-515` |
| 13 | 03-03 | Every observed condition maps onto the four legal statuses; cause in `error_kind`, never a fifth status | ✓ VERIFIED | `opencode_server.py:68-83, 650-826`; full matrix green. WR-03 caveat: a non-parseable `info.structured` string lands as `error`/`ValueError` (legal status, cause carried) but loses identity/attempts |
| 14 | 03-03 | A transport failure is a value, never an exception | ✓ VERIFIED | `opencode_server.py:429-471, 499-518`; `test_complete_structured.py:404-415, 518-560` |
| 15 | 03-03 | Truncated JSON salvaged only via an explicit allow-list; an unexpected mismatch never laundered | ✓ VERIFIED | `TOLERATED_SCHEMA_ERRORS` (`opencode_server.py:90`), `_salvage` (`:629-647`), `_tolerant_validator` (`:598-626`); `tests/llm/test_salvage.py:70-103, 141-177` |
| 16 | 03-04 | Every recorded call carries the opencode server version, queryable per row | ✓ VERIFIED | migration 0003 adds `server_version VARCHAR(32)` (`alembic/versions/0003_llm_call_server_version.py:37-44`); ORM mirror `app/db/models.py:455`; `alembic heads` → single head `0003` |
| 17 | 03-04 | `server_version` round-trips end-to-end with the drift guard green | ✓ VERIFIED | `llm_call_repo.py:100-133, 165-182`; `tests/db/test_llm_call_repo.py`; `tests/db/test_orm_drift.py` green unedited |
| 18 | 03-04 | `llm_calls` still has zero JSON columns | ✓ VERIFIED | `tests/db/test_no_pii_columns.py` green with no edit (targeted run) |
| 19 | 03-04 | `record_llm_call` never commits, validates before SQL, reads default rather than raise | ✓ VERIFIED | `llm_call_repo.py:95-98, 129-133, 157-205`; `test_llm_selftest.py:246-269` |
| 20 | 03-05 | Every Phase-3 ceiling is a Settings field with documented default asserted by the config guard, so no completion timeout or retry count is a literal | ✗ FAILED | Fields exist/guarded/tunable (`app/config.py:43-49`; `tests/test_config.py:118-189`), BUT the client retry count IS a literal (`app/llm/opencode_server.py:356`, `app/llm/base.py:122`) and the Settings default is unreachable when `retries` is omitted. Repro: `opencode_max_retries=7`, omitted `retries` → 2 POSTs. See gap 1 |
| 21 | 03-05 | Each new `opencode_*` setting reaches the container via `compose.yml` | ✓ VERIFIED | `compose.yml:34-37` (`${VAR:-default}` matching `config.py`) |
| 22 | 03-05 | `.env.example` documents every new key | ✓ VERIFIED | `.env.example:13-26` |
| 23 | 03-05 | The literal-absence scan still reports no distinctive threshold literal in `app/pipeline`/`app/probe` | ✓ VERIFIED | `tests/test_config.py:233-280` green |
| 24 | 03-06 | Untrusted content never reaches `system`; the only app `system` value is a non-interpolated constant | ✓ VERIFIED | `settings.py:63-67`; `test_llm_selftest.py:223-240`; `test_trust_boundary.py:180-207` |
| 25 | 03-06 | Tools denied by default via the session `permission` ruleset | ✓ VERIFIED | `opencode_server.py:104-110, 319-326`; `test_trust_boundary.py:114-155` (server-honoured deny = human item) |
| 26 | 03-06 | The deny is observed: returned `parts` types and `info` keys recorded | ✓ VERIFIED | `base.py:93-98`; `opencode_server.py:577-595, 716-724`; `settings.html:58-73`; `test_trust_boundary.py:213-247` |
| 27 | 03-06 | Nothing outside `app/llm/` imports `httpx` on the LLM call path or `subprocess` anywhere | ✓ VERIFIED | `tests/test_import_discipline.py:117-179` green |
| 28 | 03-07 | Instruction-like text is recorded on the listing, never executed or stripped | ✓ VERIFIED | `run.py:267-285`; `tests/pipeline/test_injection_finding.py:157-178` |
| 29 | 03-07 | A clean listing leaves `quality_signals_json` NULL | ✓ VERIFIED | `stages.py:124`; `tests/pipeline/test_injection_finding.py:181-189` |
| 30 | 03-07 | The finding is counts-only (no matched text); the PII/JSON allow-list unchanged | ✓ VERIFIED | payload built at `run.py:276-279`; sentinel assertion `test_injection_finding.py:174-178`; `tests/db/test_no_pii_columns.py` green unedited |
| 31 | 03-07 | `run_pipeline()` still writes zero `llm_calls` while the `_finish` seam exists and is proven | ✓ VERIFIED | `run.py:566-622`; `tests/pipeline/test_finish_llm_counters.py` |
| 32 | 03-07 | The queue badge does not break existing queue assertions (or is dropped) | ✓ VERIFIED | badge + `.badge-flagged` CSS rule shipped (`_listing_row.html:44`, `static/vendor/app.css`); queue tests, stylesheet-coverage and PII guard green |

**Score:** 29/32 truths verified (2 present, behavior-unverified; 1 failed)

### Deferred Items

None. Every outstanding item is either a real gap or a human-verification item; nothing is deferred to a later milestone phase (Phase 5 consumes the seams this phase ships but does not close any Phase-3 truth).

### Advisory (New Scope, Unevidenced)

None. This is an initial verification; the #3304 evidence gate applies only in re-verification mode. The non-must-have findings below are WARNING-level observations, each with deterministic evidence, recorded in the Anti-Patterns section.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/llm/contract.py` | Single home of pinned wire vocabulary | ✓ VERIFIED | 123 lines; imports only `__future__`; `__all__`; `FORMAT_FIELD="format"`, `STRUCTURED_RESPONSE_PATH=("info","structured")`, permission constants |
| `app/llm/builders.py` | Pure request builders | ✓ VERIFIED | `to_message_parts`, `to_message_body` (wildcard guard), `to_session_body` (inverse model shape) |
| `app/llm/base.py` | `StructuredCallResult` + port method | ✓ VERIFIED | `extra="forbid"`, identifiers/counts only; `part_types`/`info_keys` names-only. **Defect:** `retries: int = 2` literal (:122) |
| `app/llm/opencode_server.py` | Total adapter + taxonomy + salvage | ✓ VERIFIED | both-shape `parse_providers`, `_resolve_model` fail-loud, deny ruleset, observation, 4-value taxonomy, `_salvage`. **Defects:** dead `tools` param, literal retries, salvage `ValueError` misclassification |
| `app/domain/schemas/probe.py` | `ProbeResult`, every field defaulted | ✓ VERIFIED | `extra="ignore"`; salvage works |
| `app/db/repositories/llm_call_repo.py` | `record_llm_call` + reads | ✓ VERIFIED | validates pre-SQL, never commits, `latest_probe`, `llm_totals_for_run` |
| `app/api/settings.py` | Selftest route + constant prompt | ✓ VERIFIED | `POST /settings/llm-test`, plain POST, one row, no run |
| `app/web/templates/html/settings.html` | Plain-POST selftest + full D-52 detail + observation | ✓ VERIFIED | no `hx-`; status/cause/attempts/latency/provider/model/version; system prompt rendered |
| `alembic/versions/0003_llm_call_server_version.py` | `server_version` column | ✓ VERIFIED | nullable `String(32)`, symmetric downgrade |
| `tests/llm/fixtures/opencode-doc.json` | Committed projection | ✓ VERIFIED | 113 lines; 2,992 bytes (vs ~479 KB live spec); no wrong spellings |
| `tests/llm/test_contract_snapshot.py` | Default-lane contract + negative control + guard-can-fail | ✓ VERIFIED | has teeth |
| `tests/llm/test_contract_live.py` | Operator live lane | ✓ VERIFIED (code) / ⚠️ unrun | deselected by default; collects 1 under `-m live` |
| `docs/runbook-opencode-contract.md` | Refresh procedure | ✓ VERIFIED | 4 numbered steps, host-vs-container note, `--hostname 0.0.0.0`, `.venv/bin/python`, "why `structured`" |
| `app/pipeline/run.py`, `stages.py`, `app/domain/models.py`, `queue_repo.py`, `_listing_row.html` | Finding + counter seam | ✓ VERIFIED | quality_signals plumbing; `_finish` seam |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `builders.py` | `contract.py` | all wire names imported | ✓ WIRED | no wire literal authored in the builder |
| `complete_structured` | `discover_models` | `_resolve_model` derives `{providerID,modelID}` | ✓ WIRED | fails loud on miss (`opencode_server.py:294-305`; test `:433-445`) |
| `settings.py` route | `llm_call_repo` | `record_llm_call` + route-owned `commit()` | ✓ WIRED | repo never commits; route commits once (`settings.py:426-435`) |
| `tests/conftest.py` `OfflineLLMBackend` | `complete_structured` | stub method present | ✓ WIRED | returns honest offline error; no socket (`conftest.py:46-54`) |
| `_create_session` | session `permission` deny | `to_session_body(permission=DEFAULT_DENY_RULES)` | ✓ WIRED | sent from captured request (`test_trust_boundary.py:137-155`) |
| `_persist_result` | `listings.quality_signals_json` | `normalise_listing(quality_signals=…)` | ✓ WIRED | None for clean listings |
| `_finish` | `runs.llm_calls`/`llm_tokens` | keyword seam, no caller (D-49) | ✓ WIRED | proven by direct unit test |
| `complete_structured` | `tools` allow-list | `to_message_body(tools=…)` | ✗ NOT_WIRED | WR-01: the parameter is accepted but never forwarded; a message body built from `tools=("read","bash")` has no `tools` key. Fails closed (session deny is the control) → WARNING, not a truth failure |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `/settings` result block | `probe` | `llm_call_repo.latest_probe` → persisted `llm_calls` row | Yes (real DB read) | ✓ FLOWING |
| `/settings` observation | `probe_part_types` / `probe_info_keys` | transient from the current `complete_structured` result | Yes (per current call) | ✓ FLOWING |
| Queue row badge | `QueueRow.instruction_like` | `listings.quality_signals_json` read via tolerant accessor | Yes | ✓ FLOWING |
| `server_version` | `result.server_version` | `health().version` → `llm_calls.server_version` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full suite at the claimed baseline | `.venv/bin/python -m pytest -q` | `826 passed, 3 deselected in 142.30s` | ✓ PASS |
| Live lane excluded by default / selectable | `pytest -q tests/llm --collect-only` / `pytest -q -m live tests/llm/test_contract_live.py --collect-only` | `87/88 (1 deselected)` / `1` | ✓ PASS |
| Guard cluster | `pytest -q tests/db/test_orm_drift.py tests/db/test_no_pii_columns.py tests/db/test_migration_contract.py tests/test_import_discipline.py tests/llm/test_contract_snapshot.py tests/llm/test_trust_boundary.py` | `49 passed` | ✓ PASS |
| Migration head | `.venv/bin/python -m alembic heads` | `0003 (head)` | ✓ PASS |
| WR-01 `tools` discarded | in-process: `complete_structured(..., tools=("read","bash"))` | emitted message keys `['format','model','parts','system']`; no `tools` | ✗ found (WARNING) |
| WR-02 retries literal | `opencode_max_retries=7`, omit `retries` | 2 POSTs issued, `attempts == 2` | ✗ found (BLOCKER for 03-05 truth 1) |
| WR-03 non-parseable structured | `info.structured = "not json at all"` | `status=error`, `error_kind=ValueError`, `attempts=0`, provider/model/part_types/info_keys null | ✗ found (WARNING) |
| Debt-marker gate | `grep -rE "TBD|FIXME|XXX"` over phase-touched files | none | ✓ PASS |

### Probe Execution

N/A — no probe scripts are declared or implied by this phase. The "live" pytest lane is a test lane, not a `scripts/*/tests/probe-*.sh`; its operator-run status is captured in Human Verification Required.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
| ----------- | ------------ | ----------- | ------ | -------- |
| PLAT-02 | 03-01, 03-03, 03-04, 03-05, 03-06, 03-07 | The LLM is reached through opencode as a sibling service with no second provider key required | ✓ SATISFIED (code) / ⚠️ live half human | Port + adapter + selftest + config exist; `Settings` has no second provider key and the request carries no credential. Live real call = WINDOWS #5. |
| PLAT-05 | 03-01, 03-02 | The opencode structured-output contract is covered by a test that fails loudly on an upgrade | ✓ SATISFIED (code) / ⚠️ live lane human | `format`/`structured` pinned once with a negative control (default lane) and a live `/doc` diff lane; the live lane is operator-run (no CI runner). |

**Accounted-for requirement IDs:** PLAT-02, PLAT-05 (the only IDs mapped to Phase 3 in REQUIREMENTS.md; both appear in plan frontmatter). **Orphaned requirements:** none — no other REQUIREMENTS.md ID maps to Phase 3.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/llm/opencode_server.py` | 356, 402 | Literal retry default makes the `settings.opencode_max_retries` fallback dead code | 🛑 Blocker (03-05 truth 1) | A caller omitting `retries` ignores the configured ceiling (PLAT-04). Confirmed by repro. |
| `app/llm/base.py` | 122 | Same literal default on the port | ⚠️ Warning | Duplicates the defect; the docstring promises the opposite |
| `app/llm/opencode_server.py` | 355, 413-423 | `tools` parameter accepted but never forwarded to `to_message_body`; type mismatch (`Sequence[str]` vs `Mapping[str,bool]`) | ⚠️ Warning | A future explicit grant is a silent no-op (fails closed today). Only builder-level tests exist |
| `app/llm/opencode_server.py` | 639-643, 792-810 | `from_json(allow_partial=True)` raises `ValueError` (not `ValidationError`) for non-JSON; escapes `_collect`, caught by the generic handler | ⚠️ Warning | Model-output defect mislabelled `error`/`ValueError`; `attempts=0` and D-12 identity + observation discarded. No test covers it |
| `tests/llm/fixtures/opencode-doc.json`, `tests/llm/test_contract_snapshot.py` | — | The tool-deny rule shape (`{permission,pattern,action}`, action `deny`) is not in the `/doc` slice, the snapshot test, or the live projection | ⚠️ Warning | A server-side rename of the rule fields would silently turn the enforced deny into a no-op while all default-lane tests stay green |
| `tests/pipeline/test_injection_finding.py` | 157-189 | No update-path test: a clean re-ingest of an already-flagged listing is never asserted to preserve the signal | ⚠️ Warning | The T-3-21 nullable-guard design is only proven on insert |
| `app/api/settings.py` | 414-424 | A raising backend returns HTTP 200 and writes no `llm_calls` row | ⚠️ Warning | A token-spending attempt leaves no audit trace; inconsistent with the reset route's 400/409/500 convention |
| `app/domain/schemas/probe.py` | 11-13 | Docstring says the salvage uses `PydanticUseDefault`; the code removes-and-revalidates | ℹ️ Info | Misleading comment only |

**Debt markers:** none (`TBD`/`FIXME`/`XXX` absent from every phase-touched file).

### Human Verification Required

1. **Live real schema-constrained call from /settings (SC1 / PLAT-02).** Start the user's `opencode serve` with no second provider key configured, open `/settings`, press **Test LLM backend**, confirm a validated result and exactly one new `llm_calls` row (`purpose='probe'`, `run_id IS NULL`) and no new `runs` row.
2. **Operator live `/doc` drift lane (SC3 / PLAT-05).** On the host: `OPENCODE_BASE_URL=http://127.0.0.1:4096 .venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py`; expect 0 divergent pointers and the committed `_meta.server_version` to match `GET /global/health`.
3. **Live trust-boundary observation (SC4).** With the selftest result page open on a real call, confirm the returned parts carry no tool invocation, the rendered system prompt is the module constant, and `info_keys` contains the structured payload key.
4. **Close Open Question Q1 live.** On the first real call, confirm the pinned `format` request field and `info.structured` response field are accepted by the running server.

### Gaps Summary

The phase's four roadmap criteria are substantially implemented and well-tested in the default lane: the port, the pinned wire vocabulary, the failure taxonomy, the salvage path, the migration/ORM pair, the trust-boundary encoding, and the injection finding all exist, are wired, and are proven by tests that can fail. The structured-output contract is pinned in one place (`app/llm/contract.py`) with a negative control, and the `format`-vs-`outputFormat` ambiguity is resolved.

Two items block a clean pass:

- **Gap 1 (must-have truth 03-05 #1, failed):** `complete_structured` declares `retries: int = 2` (both `app/llm/opencode_server.py:356` and `app/llm/base.py:122`), making the documented `settings.opencode_max_retries` fallback unreachable. Reproduced: with `opencode_max_retries=7` and `retries` omitted, exactly 2 POSTs are issued. **Closes with:** change the parameter to `retries: int | None = None` in both files (keeping the existing fallback line) and add a test that an omitted `retries` honours a patched `settings.opencode_max_retries`.
- **Gap 2 (03-03 acceptance criterion, same root cause):** "`Settings.opencode_max_retries` still supplies the default ceiling" is false for an omitting caller. 03-03's stated retry-**bound** truth does still hold (an explicit `retries=3` issues 3 POSTs and a schema failure is never retried client-side), but its default-ceiling claim does not. **Closes with:** the same one-line fix; no separate change.

The WARNING-level defects (WR-01 dead `tools` channel, WR-03 salvage `ValueError` misclassification losing identity/attempts, WR-04 unguarded deny rule shape, the missing clean-re-ingest test, and the 200-on-raise route) do not by themselves block the phase goal, but they should be swept in the same closure round because three of them sit on the trust-boundary/audit path this phase exists to make trustworthy.

---

_Verified: 2026-09-17T23:50:27Z_
_Verifier: the agent (gsd-verifier)_
