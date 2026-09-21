---
phase: 03-llm-port-structured-output
verified: 2026-09-21T13:05:00Z
status: passed
score: 46/46 must-haves verified
covered_files:
  - .env.example
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
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
  - .planning/phases/03-llm-port-structured-output/03-08-PLAN.md
  - .planning/phases/03-llm-port-structured-output/03-08-SUMMARY.md
  - .planning/phases/03-llm-port-structured-output/03-09-PLAN.md
  - .planning/phases/03-llm-port-structured-output/03-09-SUMMARY.md
  - .planning/phases/03-llm-port-structured-output/03-10-PLAN.md
  - .planning/phases/03-llm-port-structured-output/03-10-SUMMARY.md
  - .planning/phases/03-llm-port-structured-output/03-CONTEXT.md
  - .planning/phases/03-llm-port-structured-output/03-UAT.md
  - alembic/versions/0003_llm_call_server_version.py
  - app/api/settings.py
  - app/config.py
  - app/db/models.py
  - app/db/repositories/llm_call_repo.py
  - app/db/repositories/queue_repo.py
  - app/domain/models.py
  - app/domain/schemas/__init__.py
  - app/domain/schemas/probe.py
  - app/llm/__init__.py
  - app/llm/base.py
  - app/llm/builders.py
  - app/llm/contract.py
  - app/llm/opencode_server.py
  - app/pipeline/run.py
  - app/pipeline/stages.py
  - app/web/templates/html/_listing_row.html
  - app/web/templates/html/settings.html
  - compose.yml
  - docs/runbook-opencode-contract.md
  - static/vendor/app.css
  - tests/api/test_llm_selftest.py
  - tests/conftest.py
  - tests/db/test_llm_call_repo.py
  - tests/db/test_migration_contract.py
  - tests/fixtures/opencode_providers.json
  - tests/llm/fixtures/opencode-doc.json
  - tests/llm/test_complete_structured.py
  - tests/llm/test_contract_live.py
  - tests/llm/test_contract_snapshot.py
  - tests/llm/test_discovery_redaction.py
  - tests/llm/test_live_structured_call.py
  - tests/llm/test_salvage.py
  - tests/llm/test_trust_boundary.py
  - tests/pipeline/test_finish_llm_counters.py
  - tests/pipeline/test_injection_finding.py
  - tests/test_auth_seam.py
  - tests/test_config.py
  - tests/test_import_discipline.py
covered_digest: "v1:sha256:623c882691f82560fedfa40e9c04fe2dcde57cf21b20d366cf9f4ea097510bfd"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 30/32
  gaps_closed:
    - "A schema-validated structured call completes end to end through a REAL opencode serve sibling service with the shipped default model and no second provider key (roadmap SC1 / 03-01 truth 1 / 03-10 truth 1) — verified live by the verifier."
    - "The operator live /doc drift lane refetches the installed spec and diffs it against the committed slice, failing loudly on drift (roadmap SC3 / 03-02 truth 10) — verified live by the verifier."
    - "The four 03-10 blocker causes: the StructuredOutput carve-out after the catch-all deny; a forced-tool-call-capable shipped default; the differential failure cause on llm_calls.error; and the operator live lane."
  gaps_remaining: []
  regressions: []
advisory:
  - finding: "Failures outside the per-attempt loop (session-create transport failure, non-200 session) report attempts=0 and drop the resolved provider/model identity, even though both were resolved moments earlier."
    category: other
    reason: "Pre-existing attribution gap on an edge path; no must-have truth requires session-handshake identity. Raised by 03-REVIEW.md WR-01; not a Step-7 anti-pattern match."
    evidence_status: "Reproduced in-process by the reviewer against a stubbed transport; no standing test added."
  - finding: "The generic exception handler and the 'other provider error envelope' branch write a raw class/provider name into error_kind, outside the documented D-52 namespace."
    category: architectural
    reason: "Pre-existing taxonomy leak; status still stays within the four legal llm_calls.status values, and the 03-03 truth explicitly allows 'other' in error_kind, so no must-have fails. 03-REVIEW.md WR-02."
    evidence_status: "Reproduced in-process (tools=(\"*\",) -> error_kind 'ValueError'); no standing test."
  - finding: "The differential structured-failure cause can name the model/provider side when the response only proves no tool part was observed (e.g. a schema-retry exhaustion with an empty parts list)."
    category: other
    reason: "Diagnostic-accuracy nuance in the new 03-10 clause. The must-have truth (distinguish ruleset-stripped vs grant-survived-no-tool-part) holds under its own wording; the reviewer explicitly flags this as unconfirmed without a live failure capture, so it is not deterministic evidence. 03-REVIEW.md WR-03."
    evidence_status: "none provided — reviewer states it cannot be confirmed without a live StructuredOutputError capture."
---

# Phase 3: LLM Port + Structured Output Verification Report

**Phase Goal:** Any schema-constrained LLM call works end to end through `opencode serve` as a sibling service, with the structured-output contract pinned by a failing test.
**Verified:** 2026-09-21T13:05:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (plans 03-08, 03-09 and 03-10). The prior `03-VERIFICATION.md` (2026-09-18, `human_needed`, 30/32) was stale: it predated plan 03-10, which closed the blocker that the app could not complete a real schema-constrained call against the sibling `opencode serve` with the shipped default configuration.

## Goal Achievement

### Roadmap Success Criteria

| # | Success Criterion | Status | Evidence |
| --- | ----------------- | ------ | -------- |
| 1 | App completes a schema-validated structured call through the opencode backend with no second provider key configured | ✓ VERIFIED (live) | **Independently executed by the verifier** against a reachable `opencode serve` 1.18.31: `.venv/bin/python -m pytest -q -m live tests/llm/test_live_structured_call.py` → `1 passed in 12.92s`. The lane drives the real `POST /settings/llm-test` route with `get_llm_backend` overridden by the callable `OpenCodeServerBackend` class, asserts 200 + `status ok` + `Structured payload: present` + `Model: minimax-m3` + a rendered `tool` part + exactly one `probe` row (`run_id IS NULL`, `server_version` set) + zero `runs` rows. No second provider key exists: `Settings` (all 36 fields) carries only `opencode_base_url`/`opencode_model`/`opencode_server_password` + ceilings (`app/config.py:45-73`). |
| 2 | A schema violation is recorded as an explicit, retried run outcome rather than a silent failure | ✓ VERIFIED | `_classify_message_response` maps `StructuredOutputError` → `invalid` with the server's own `data.retries`, `ValidationError` → `invalid`, non-parseable `info.structured` → `invalid` preserving identity/observation, connect → `error`/`unreachable`, timeout → `timeout`, non-200 → `error`/`http_<code>` with a bounded excerpt. `complete_structured` is total (`except Exception` at `opencode_server.py:580`); the route writes exactly one row. Full default lane green. |
| 3 | A CI contract test reads the installed server's `GET /doc` and fails loudly if the structured-output field name changes — resolving the `format` vs `outputFormat` ambiguity | ✓ VERIFIED (live) | Default-lane pin: `FORMAT_FIELD="format"`, `STRUCTURED_RESPONSE_PATH=("info","structured")` (`app/llm/contract.py:35,50`) asserted against the committed slice with a negative control and a guard-can-fail companion (`test_contract_snapshot.py`). **Live half independently executed by the verifier**: `.venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py` → `1 passed in 0.35s` (0 divergent pointers across the projected facts incl. the deny-rule shape, no LLM call). |
| 4 | Untrusted listing text reaches the model only as user content (never the system prompt) and tools are disabled by default | ✓ VERIFIED | `SELFTEST_SYSTEM_PROMPT` is a module constant with an AST-verified single `Constant` and no interpolation (`tests/api/test_llm_selftest.py`); the builder assigns `system` a bare `Name` and `parts` is the only content channel; the message body sends no `tools` key by default and rejects `"*"` (`builders.py`). The session carries `DEFAULT_DENY_RULES`, evaluated by the verifier: shipped ruleset grants only `StructuredOutput`; `bash`/`read`/`write`/`webfetch`/`*` all denied. The live success response carries the internal tool part and nothing else. |

### Observable Truths (plan `must_haves.truths`)

Original plans 03-01…03-07 (`03-0X-PLAN.md` frontmatter), plus the gap-closure plans 03-08/03-09/03-10.

| # | Plan | Truth | Status | Evidence |
| --- | ---- | ----- | ------ | -------- |
| 1 | 03-01 | Schema-validated call completes through the opencode backend with no second provider key | ✓ VERIFIED | Live lane passed (SC1). Was ⚠️ in the prior pass. |
| 2 | 03-01 | Schema violation → explicit retried outcome; exactly one `llm_calls` row; no failure path raises | ✓ VERIFIED | `opencode_server.py:580-587`; `test_complete_structured.py`; `test_llm_selftest.py`. |
| 3 | 03-01 | Untrusted content only as `parts`; port tools default empty; no param reaches `system` | ✓ VERIFIED | `builders.py`; `base.py`; `test_trust_boundary.py`. |
| 4 | 03-01 | Default-lane test pins the request vocabulary; importing constants needs no network | ✓ VERIFIED | `test_contract_snapshot.py`; `contract.py` imports only `__future__`. |
| 5 | 03-01 | Operator can trigger one call from `/settings`; exactly one probe row, `run_id IS NULL`, no `runs` row | ✓ VERIFIED | `settings.py:389-490`; `test_llm_selftest.py`; live lane asserts the row shape. |
| 6 | 03-01 | `run_pipeline()` writes zero `llm_calls` rows (D-49) | ✓ VERIFIED | `run.py`; `tests/pipeline/test_filter_stage.py`; `test_finish_llm_counters.py`. |
| 7 | 03-02 | Default-lane test fails if the structured-output field name is absent from the snapshot | ✓ VERIFIED | `test_contract_snapshot.py`; fixture `opencode-doc.json`. |
| 8 | 03-02 | Same test asserts the builder emits exactly the pinned names | ✓ VERIFIED | `test_contract_snapshot.py`. |
| 9 | 03-02 | Negative control blocks `outputFormat`/`structured_output` | ✓ VERIFIED | `test_contract_snapshot.py:223-235`. |
| 10 | 03-02 | Operator `@pytest.mark.live` test refetches `/doc`, diffs, makes no LLM call | ✓ VERIFIED | **Executed live by the verifier**: 1 passed in 0.35s (SC3). Was ⚠️ in the prior pass. |
| 11 | 03-02 | Default lane structurally cannot run the live test; cheap guard makes it explicit | ✓ VERIFIED | `pyproject.toml` `addopts = "-m 'not live'"`; collect-only 843/847, 4 deselected. |
| 12 | 03-03 | `StructuredOutputError` and `ValidationError` → `ok=False`, `status='invalid'`, attempt count from server `data.retries` | ✓ VERIFIED | `opencode_server.py`; `test_complete_structured.py`. |
| 13 | 03-03 | Every observed condition maps onto the four legal statuses; cause in `error_kind`, never a fifth status | ✓ VERIFIED | `opencode_server.py:760-953`; full matrix green. |
| 14 | 03-03 | A transport failure is a value, never an exception | ✓ VERIFIED | `complete_structured` total; outer handlers return `_failure(...)`. |
| 15 | 03-03 | Truncated JSON salvaged only via an explicit allow-list; an unexpected mismatch never laundered | ✓ VERIFIED | `TOLERATED_SCHEMA_ERRORS`; `_salvage`; `_tolerant_validator`; `test_salvage.py`. |
| 16 | 03-04 | Every recorded call carries the opencode server version, queryable per row | ✓ VERIFIED | Migration 0003 adds `server_version VARCHAR(32)`; ORM mirror; `alembic heads` → single `0003`; live row has `server_version` set. |
| 17 | 03-04 | `server_version` round-trips end-to-end with the drift guard green | ✓ VERIFIED | `llm_call_repo.py`; `test_llm_call_repo.py`; `test_orm_drift.py` green. |
| 18 | 03-04 | `llm_calls` still has zero JSON columns | ✓ VERIFIED | ORM inspection: no JSON/raw column; `test_no_pii_columns.py` green unedited. |
| 19 | 03-04 | `record_llm_call` never commits, validates before SQL, reads default rather than raise | ✓ VERIFIED | `llm_call_repo.py:69-130`; `test_llm_selftest.py`; `test_llm_call_repo.py`. |
| 20 | 03-05 | Every Phase-3 ceiling is a Settings field with documented default asserted by the config guard, so no completion timeout or retry count is a literal | ✓ VERIFIED | `app/config.py:63-73`; `tests/test_config.py`; `retries: int | None = None` on both port and adapter makes the `settings.opencode_max_retries` fallback live (`test_an_omitted_retries_honours_the_settings_ceiling`). |
| 21 | 03-05 | Each new `opencode_*` setting reaches the container via `compose.yml` | ✓ VERIFIED | `compose.yml` `${VAR:-default}` matches `config.py`. |
| 22 | 03-05 | `.env.example` documents every new key | ✓ VERIFIED | `.env.example`. |
| 23 | 03-05 | The literal-absence scan still reports no distinctive threshold literal in `app/pipeline`/`app/probe` | ✓ VERIFIED | `tests/test_config.py` green. |
| 24 | 03-06 | Untrusted content never reaches `system`; the only app `system` value is a non-interpolated constant | ✓ VERIFIED | `settings.py`; `test_llm_selftest.py`; `test_trust_boundary.py`. |
| 25 | 03-06 | Tools denied by default via the session `permission` ruleset | ✓ VERIFIED | `DEFAULT_DENY_RULES`; evaluator check by the verifier; `test_trust_boundary.py`. |
| 26 | 03-06 | The deny is observed: returned `parts` types and `info` keys recorded | ✓ VERIFIED | `base.py`; `opencode_server.py`; `settings.html`; `test_trust_boundary.py`; live render. |
| 27 | 03-06 | Nothing outside `app/llm/` imports `httpx` on the LLM call path or `subprocess` anywhere | ✓ VERIFIED | `tests/test_import_discipline.py` green; grep confirms `httpx` only in `app/sources` (excluded) and no `subprocess`. |
| 28 | 03-07 | Instruction-like text is recorded on the listing, never executed or stripped | ✓ VERIFIED | `run.py` `_persist_result`; `test_injection_finding.py`. |
| 29 | 03-07 | A clean listing leaves `quality_signals_json` NULL | ✓ VERIFIED | `stages.py`; `test_injection_finding.py`. |
| 30 | 03-07 | The finding is counts-only (no matched text); the PII/JSON allow-list unchanged | ✓ VERIFIED | sentinel assertion; `test_no_pii_columns.py` green. |
| 31 | 03-07 | `run_pipeline()` still writes zero `llm_calls` while the `_finish` seam exists and is proven | ✓ VERIFIED | `run.py`; `test_finish_llm_counters.py`. |
| 32 | 03-07 | The queue badge does not break existing queue assertions (or is dropped) | ✓ VERIFIED | badge + CSS shipped; queue/stylesheet/PII guards green. |
| 33 | 03-08 | An omitted `retries` honours `settings.opencode_max_retries` | ✓ VERIFIED | `base.py` / `opencode_server.py` nullable signatures; `test_an_omitted_retries_honours_the_settings_ceiling`. |
| 34 | 03-08 | An explicit tool grant reaches the message body; the default still emits no message-level `tools` key | ✓ VERIFIED | `opencode_server.py:472-480`; `test_an_explicit_tool_grant_reaches_the_message_body`; `test_no_tool_grant_by_default`. |
| 35 | 03-08 | A non-parseable `info.structured` is `invalid` preserving identity and observation | ✓ VERIFIED | `opencode_server.py:931-953`; `test_a_non_parseable_structured_payload_is_invalid_and_keeps_identity`. |
| 36 | 03-09 | The default-lane contract test fails on a `permission` rule-field rename or a dropped `deny` action | ✓ VERIFIED | `test_contract_snapshot.py#test_the_permission_deny_rule_contract_matches_the_snapshot`; guard-can-fail companion. |
| 37 | 03-09 | A raising backend writes the token-spending attempt and returns an honest non-2xx | ✓ VERIFIED | `settings.py:420-453`; `test_a_raising_backend_returns_500_and_writes_one_audit_row`. |
| 38 | 03-09 | A clean re-ingest preserves the recorded instruction-like signal on the update path | ✓ VERIFIED | `test_a_clean_reingest_preserves_the_recorded_signal`. |
| 39 | 03-10 | A real schema-constrained call completes `ok` with the shipped default model and the server-internal `StructuredOutput` tool part | ✓ VERIFIED | Live lane passed; settings default `minimax-m3`. |
| 40 | 03-10 | The session ruleset denies every user-facing tool via a catch-all and grants only `StructuredOutput` by an order-enforced carve-out | ✓ VERIFIED | Source tuple + verifier evaluator run (`bash`/`read`/`write`/`*` → False). |
| 41 | 03-10 | Reordering the carve-out before the catch-all flips the grant and a default-lane test fails on the flip | ✓ VERIFIED | `ruleset_allows_tool` last-match-wins; `test_the_carve_out_must_follow_the_catch_all_deny` (reordered → False). |
| 42 | 03-10 | The shipped default honours a forced tool call; guarded against the known-incompatible model | ✓ VERIFIED | `minimax-m3` + `KNOWN_FORCED_TOOL_CHOICE_INCOMPATIBLE_MODELS`; live call succeeded; `test_the_default_model_is_not_a_known_forced_tool_call_incompatible_model`. |
| 43 | 03-10 | The default model is pinned on all three operator surfaces and guarded against revert | ✓ VERIFIED | `app/config.py:57`, `compose.yml:19`, `.env.example:15`; `test_the_compose_model_default_agrees_with_the_declared_one`. |
| 44 | 03-10 | Default-lane tests resolving the model implicitly are independent of the shipped default's value | ✓ VERIFIED | `_backend` helper advertises `settings.opencode_model`; full suite green after the default move; `test_salvage.py` unedited and green. |
| 45 | 03-10 | A `StructuredOutputError` carries a differential cause persisted on `llm_calls.error`, surviving reload | ✓ VERIFIED | `_structured_tool_note` / `_with_note` on both structured-failure branches; `record_llm_call` maps `result.error` to `LlmCall.error`; `test_a_structured_error_without_a_tool_part_carries_the_model_cause` + reordered companion. |
| 46 | 03-10 | An operator-run `@pytest.mark.live` lane performs the real call and proves the one-row/no-run audit shape | ✓ VERIFIED | `tests/llm/test_live_structured_call.py`; **executed by the verifier** → 1 passed in 12.92s. |

**Score:** 46/46 truths verified (0 present-but-behavior-unverified). Roadmap SCs 4/4.

> Count note: the prior report scored 32 original truths; the gap-closure plans add truths that are separately enumerated here (03-08: 3, 03-09: 3, 03-10: 8 → the 03-10 live-lane truth is listed as #46 in addition to the seven `.planning`-recorded truths). All 46 resolve VERIFIED.

### Deferred Items

None. Phase 5 consumes the seams this phase ships (`runs.llm_calls`/`llm_tokens`, the port) but closes no Phase-3 truth.

### Advisory (New Scope, Unevidenced)

| # | Finding | Category | Why Advisory |
|---|---------|----------|--------------|
| 1 | Session-handshake transport failures report `attempts=0` and drop the resolved provider/model identity (03-REVIEW WR-01). | other | Pre-existing; no must-have truth covers it; not a Step-7 anti-pattern. |
| 2 | Generic handler / provider-envelope branch write a raw name into `error_kind`, outside the documented D-52 namespace (03-REVIEW WR-02). | architectural | Pre-existing; `status` stays legal and the 03-03 truth explicitly allows "other" in `error_kind`; no must-have fails. |
| 3 | The differential cause may name the model/provider side when the observed parts list is empty but the failure was schema-retry exhaustion (03-REVIEW WR-03). | other | The reviewer flags it as unconfirmed without a live failure capture — no deterministic evidence. |

None of these is a must-have failure, an artifact stub, a broken key link, or a debt marker, and none prevents the phase goal.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/llm/contract.py` | Single home of pinned wire vocabulary | ✓ VERIFIED | imports only `__future__`; `FORMAT_FIELD="format"`, `STRUCTURED_RESPONSE_PATH=("info","structured")`, permission + `STRUCTURED_OUTPUT_TOOL_NAME`/`PART_TYPE_TOOL` constants. |
| `app/llm/builders.py` | Pure request builders | ✓ VERIFIED | `to_message_parts`, `to_message_body` (wildcard guard), `to_session_body` (rules copied verbatim, order preserved). |
| `app/llm/base.py` | `StructuredCallResult` + port method | ✓ VERIFIED | `extra="forbid"`; `retries: int | None = None`; docstring names the adapter-applied default. |
| `app/llm/opencode_server.py` | Total adapter + taxonomy + salvage + ruleset | ✓ VERIFIED | both-shape `parse_providers`, `_resolve_model` fail-loud, two-rule `DEFAULT_DENY_RULES`, `ruleset_allows_tool`, observation, four-value taxonomy, `_salvage`, tool-grant forwarding, differential note. |
| `app/domain/schemas/probe.py` | `ProbeResult`, every field defaulted | ✓ VERIFIED | `extra="ignore"`; salvage works. |
| `app/db/repositories/llm_call_repo.py` | `record_llm_call` + reads | ✓ VERIFIED | validates pre-SQL, never commits, `latest_probe`, `llm_totals_for_run`. |
| `app/api/settings.py` | Selftest route + constant prompt | ✓ VERIFIED | `POST /settings/llm-test` writes one probe row (value and raise paths), returns 500 on a raise. |
| `app/web/templates/html/settings.html` | Plain-POST selftest + D-52 detail + observation | ✓ VERIFIED | no `hx-`; status/cause/attempts/latency/provider/model/version; observation rendered; healthy-call copy corrected. |
| `alembic/versions/0003_llm_call_server_version.py` | `server_version` column | ✓ VERIFIED | nullable `String(32)`, symmetric downgrade; single head `0003`. |
| `app/config.py` | `minimax-m3` default + incompatibility guard + ceilings | ✓ VERIFIED | `app/config.py:23-25,57,63-73`. |
| `compose.yml` / `.env.example` | Model + ceiling passthrough | ✓ VERIFIED | `OPENCODE_MODEL=${OPENCODE_MODEL:-minimax-m3}`; matching `.env.example`. |
| `tests/llm/fixtures/opencode-doc.json` | Committed projection | ✓ VERIFIED | includes `PermissionRule`; `_meta.note` records the D-55 widening. |
| `tests/llm/test_contract_snapshot.py` / `test_contract_live.py` | Default-lane pin + operator live lane | ✓ VERIFIED | 13 default-lane passes; live lane independently run → 1 passed. |
| `tests/llm/test_live_structured_call.py` | Real end-to-end operator lane | ✓ VERIFIED | independently run → 1 passed in 12.92s. |
| `docs/runbook-opencode-contract.md` | Refresh procedure + model-selection section | ✓ VERIFIED | present. |
| `app/pipeline/run.py`, `stages.py`, `app/domain/models.py`, `queue_repo.py`, `_listing_row.html` | Finding + counter seam | ✓ VERIFIED | quality_signals plumbing; `_finish` keyword seam. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `builders.py` | `contract.py` | all wire names imported | ✓ WIRED | no wire literal authored in the builder. |
| `complete_structured` | `discover_models` | `_resolve_model` derives `{providerID,modelID}` | ✓ WIRED | fails loud on a miss. |
| `settings.py` route | `llm_call_repo` | `record_llm_call` + route-owned `commit()` | ✓ WIRED | repo never commits; route commits once on both paths. |
| `conftest.OfflineLLMBackend` | `complete_structured` | stub method present | ✓ WIRED | no socket in the default lane. |
| `_create_session` | session `permission` deny | `to_session_body(permission=DEFAULT_DENY_RULES)` | ✓ WIRED | rules copied verbatim in order. |
| `_structured_tool_note` | `llm_calls.error` | `_with_note` → `StructuredCallResult.error` → `record_llm_call` → `LlmCall.error` | ✓ WIRED | fixed literals only; persisted, so a reload shows the cause. |
| `ruleset_allows_tool` | `DEFAULT_DENY_RULES` | last-match-wins evaluator | ✓ WIRED | shipped → True; reordered → False (test + verifier run). |
| `Settings.opencode_model` | `compose.yml` / `.env.example` | derived-spelling agreement test | ✓ WIRED | three surfaces, one value. |
| `_finish` | `runs.llm_calls`/`llm_tokens` | keyword seam, no caller (D-49) | ✓ WIRED | proven by direct unit test. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `/settings` result block | `probe` | `llm_call_repo.latest_probe` → persisted `llm_calls` row | Yes (real DB read) | ✓ FLOWING |
| `/settings` observation | `probe_part_types` / `probe_info_keys` | current `complete_structured` result | Yes (live run rendered a `tool` part) | ✓ FLOWING |
| `llm_calls.error` differential | `result.error` | `_structured_tool_note` → `_with_note` | Yes (fixed literals; persisted) | ✓ FLOWING |
| Queue row badge | `QueueRow.instruction_like` | `listings.quality_signals_json` | Yes | ✓ FLOWING |
| `server_version` | `result.server_version` | `health().version` → `llm_calls.server_version` | Yes (live row set) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full default suite | `.venv/bin/python -m pytest -x -q --tb=short` | `843 passed, 4 deselected in 119.59s` | ✓ PASS |
| Lint | `.venv/bin/python -m ruff check .` | `All checks passed!` | ✓ PASS |
| Guard cluster (llm boundary, config, import, injection) | targeted pytest (8 files) | `119 passed in 13.86s` | ✓ PASS |
| Real schema-constrained call (SC1) | `.venv/bin/python -m pytest -q -m live tests/llm/test_live_structured_call.py` | `1 passed in 12.92s` | ✓ PASS |
| Live `/doc` contract diff (SC3) | `.venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py` | `1 passed in 0.35s` | ✓ PASS |
| Live server version | `curl -s http://host.docker.internal:4096/global/health` | `{"healthy":true,"version":"1.18.31"}` | ✓ PASS |
| Ruleset evaluator (user-facing tools denied) | in-process `ruleset_allows_tool` | shipped→True; `bash`/`read`/`write`/`webfetch`/`*`→False | ✓ PASS |
| Migration head | `.venv/bin/python -m alembic heads` | `0003 (head)` | ✓ PASS |
| Debt-marker gate | `grep -rE "TBD|FIXME|XXX" app/ tests/` | none | ✓ PASS |
| Live lanes deselected by default | `pytest -q --collect-only` | 843 collected / 4 deselected (2 live modules) | ✓ PASS |

### Probe Execution

N/A — no `scripts/*/tests/probe-*.sh` probes are declared or implied. The `live` pytest lane is a test lane, run directly in this pass (see above), not a probe script.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
| ----------- | ------------ | ----------- | ------ | -------- |
| PLAT-02 | 03-01, 03-03, 03-04, 03-05, 03-06, 03-07, 03-08, 03-09, 03-10 | The LLM is reached through opencode as a sibling service with no second provider key required | ✓ SATISFIED | Port + adapter + selftest + config; no second provider key in `Settings`; request carries no credential; real live call passed. |
| PLAT-05 | 03-01, 03-02, 03-09, 03-10 | The opencode structured-output contract is covered by a test that fails loudly on an upgrade | ✓ SATISFIED | `format`/`structured` + deny-rule shape pinned with negative controls; live `/doc` diff lane executed and passed. |

**Accounted-for requirement IDs:** PLAT-02, PLAT-05 — the only IDs mapped to Phase 3 in `REQUIREMENTS.md`, both marked `[x]` and both declared in plan frontmatter. **Orphaned requirements:** none. No other REQUIREMENTS.md ID maps to Phase 3.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | No debt markers (`TBD`/`FIXME`/`XXX`) in any phase-touched file | — | none |
| `app/llm/opencode_server.py` | 560-587 | Edge-path identity/attempts attribution gap (advisory WR-01) | ℹ️ Info | Not a must-have; see Advisory. |
| `app/llm/opencode_server.py` | 580-587, 886-896 | Raw name in `error_kind` (advisory WR-02) | ℹ️ Info | Not a must-have; see Advisory. |
| `app/llm/opencode_server.py` | 727-752 | Differential-cause accuracy nuance (advisory WR-03) | ℹ️ Info | Not a must-have; unevidenced; see Advisory. |

No 🛑 Blocker, no ⚠️ Warning against a must-have. `.planning/state.json` shows the phase still marked In Progress and the ROADMAP plan list still shows "9/9 … 2 gap-closure pending" without 03-10 — a bookkeeping staleness the orchestrator owns; not a phase-goal gap (ROADMAP/STATE were left untouched per instruction).

### Human Verification Required

None. The two items that were operator-only in the prior pass (SC1's real call, SC3's live `/doc` diff) were **executed by this verifier** against a reachable `opencode serve` 1.18.31 and passed, so no must-have truth remains present-but-behavior-unverified. The live trust-boundary observation (SC4) is covered by the live lane's assertion that a healthy response carries the internal `tool` part plus the structural default-lane guards.

### Gaps Summary

None. The phase goal is achieved on shipped code: a real schema-constrained call completes `status ok` end to end through `opencode serve` 1.18.31 with the shipped default model (`minimax-m3`) and no second provider key; the structured-output contract (`format` request field, `info.structured` response path, and the session deny-rule shape) is pinned by a default-lane test with negative controls and an operator live `/doc` diff lane that passes; a schema violation is an explicit, counted, retried outcome; and untrusted text reaches the model only as user content with tools denied by default (a single order-enforced carve-out for the server-internal `StructuredOutput` tool).

All four 03-10 blocker causes are genuinely addressed in the shipped code, not just in prose:
1. `DEFAULT_DENY_RULES` is a two-rule tuple — catch-all deny first, `StructuredOutput` carve-out second (`opencode_server.py:117-128`) — with `ruleset_allows_tool` last-match-wins and a reordering test that fails on the flip.
2. `opencode_model` defaults to `minimax-m3` (`app/config.py:57`) with `KNOWN_FORCED_TOOL_CHOICE_INCOMPATIBLE_MODELS` guarding the shipped default, pinned across all three operator surfaces.
3. Structured-output failures carry a differential cause persisted on `llm_calls.error` (`_with_note` on both structured-failure branches; `record_llm_call` maps `result.error` to the column), so it survives a reload.
4. `tests/llm/test_live_structured_call.py` exists and was run in this pass → `1 passed in 12.92s`.

The three open code-review warnings (WR-01, WR-02, WR-03) are recorded as advisory — pre-existing quality gaps and one flagged, unevidenced diagnostic nuance. None is a must-have failure, a stub/artifact gap, a broken key link, or a debt marker.

---

_Verified: 2026-09-21T13:05:00Z_
_Verifier: the agent (gsd-verifier)_
