---
phase: 03-llm-port-structured-output
verified: 2026-09-18T11:06:23Z
status: human_needed
score: 30/32 must-haves verified
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
  - .planning/phases/03-llm-port-structured-output/03-CONTEXT.md
  - .planning/phases/03-llm-port-structured-output/03-PATTERNS.md
  - .planning/phases/03-llm-port-structured-output/03-RESEARCH.md
  - .planning/phases/03-llm-port-structured-output/03-REVIEW.md
  - .planning/phases/03-llm-port-structured-output/03-VALIDATION.md
  - .planning/phases/03-llm-port-structured-output/COVERAGE.md
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
  - tests/db/test_skeleton_boot.py
  - tests/fixtures/opencode_providers.json
  - tests/llm/fixtures/opencode-doc.json
  - tests/llm/test_complete_structured.py
  - tests/llm/test_contract_live.py
  - tests/llm/test_contract_snapshot.py
  - tests/llm/test_discovery_redaction.py
  - tests/llm/test_salvage.py
  - tests/llm/test_trust_boundary.py
  - tests/pipeline/test_finish_llm_counters.py
  - tests/pipeline/test_injection_finding.py
  - tests/test_auth_seam.py
  - tests/test_config.py
  - tests/test_import_discipline.py
covered_digest: "v1:sha256:146803990977db22358ba1ae6a201b2e8f483aee5e66f5a97d05ea6436dfd4e8"
behavior_unverified: 2
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 29/32
  gaps_closed:
    - "Every Phase-3 ceiling is a Settings field with a documented default and is asserted by the config guard, so no completion timeout or retry count is a literal (PLAT-04)."
    - "Both retry ceilings are configuration (03-03 success criterion); 'Settings.opencode_max_retries still supplies the default ceiling' (03-03 acceptance criterion)."
  gaps_remaining: []
  regressions: []
advisory: []
behavior_unverified_items:
  - truth: "The app completes a schema-validated structured call through the opencode backend with no second provider key configured (roadmap SC1 / 03-01 truth 1)."
    test: "Start the user's own `opencode serve` (no second provider key configured), open /settings, press 'Test LLM backend'."
    expected: "A validated ProbeResult is returned and rendered, and exactly one llm_calls row is written (purpose='probe', run_id IS NULL) with no new runs row."
    why_human: >-
      The default lane proves the full HTTP-shaped path against a fake transport
      (session -> message -> info.structured -> typed ProbeResult), but the claim is
      that it completes through a REAL `opencode serve` sibling service with a real
      model; that requires the operator's server. Recorded as WINDOWS #5 /
      03-VALIDATION.md Manual-Only.
  - truth: "An operator-run @pytest.mark.live test refetches /doc and diffs the live spec against the committed slice, failing loudly on drift (roadmap SC3 / 03-02 truth 4)."
    test: "On the host: OPENCODE_BASE_URL=http://127.0.0.1:4096 .venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py"
    expected: "0 divergent pointers (26 fact keys) and GET /global/health version == the fixture's _meta.server_version (1.18.31)."
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
  - test: "Confirm on the first live server call that the message body's pinned `format` field and the response `info.structured` field are accepted (Open Question Q1)."
    expected: "The call reaches a validated result rather than 400/None."
    why_human: "The pinned names were resolved from the 1.18.31 spec; a real acceptance cannot be observed in the sandbox."
---

# Phase 3: LLM Port + Structured Output Verification Report

**Phase Goal:** Any schema-constrained LLM call works end to end through `opencode serve` as a sibling service, with the structured-output contract pinned by a failing test.
**Verified:** 2026-09-18T11:06:23Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (plans 03-08 and 03-09)
**Baseline checked:** `.venv/bin/python -m pytest -q` → **834 passed, 3 deselected** (126.6 s); `.venv/bin/python -m ruff check .` → **All checks passed**. Targeted named gap-closure tests → 9 passed; guard cluster (orm-drift, no-pii-columns, migration-contract, import-discipline, config, contract-snapshot, trust-boundary, llm-selftest, injection-finding) → 92 passed; `alembic heads` → single head `0003`.

## Goal Achievement

### Roadmap Success Criteria

| # | Success Criterion | Status | Evidence |
| --- | ----------------- | ------ | -------- |
| 1 | App completes a schema-validated structured call through the opencode backend with no second provider key configured | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Port path present + wired: `LLMBackend.complete_structured` (`app/llm/base.py:113-138`), `OpenCodeServerBackend.complete_structured` (`app/llm/opencode_server.py:347-535`), selftest route (`app/api/settings.py:390-465`). No second provider key exists in `Settings` (`app/config.py:32-49`: only `opencode_base_url`/`opencode_model`/`opencode_server_password` + ceilings; grep for `api_key`/`openai`/`anthropic`/`gemini` → none) and the request body carries no credential. Proven end-to-end against a fake transport (`tests/llm/test_complete_structured.py`); the REAL `opencode serve` call is operator-run (WINDOWS #5). |
| 2 | A schema violation is recorded as an explicit, retried run outcome rather than a silent failure | ✓ VERIFIED | Classification matrix green: `StructuredOutputError` → `invalid` + server `data.retries`; `ValidationError` → `invalid`; a non-parseable `info.structured` → `invalid` preserving identity/observation (new in 03-08, `opencode_server.py:820-842`); connect → `error`/`unreachable`; read timeout → `timeout`; non-200 → `error`/`http_<code>` with bounded excerpt; unparseable HTTP JSON → `error` naming the parse exception. `complete_structured` is total (`except Exception` at `opencode_server.py:528`); the selftest writes exactly one row. |
| 3 | A CI contract test reads the installed server's `GET /doc` and fails loudly if the structured-output field name changes — resolving the `format` vs `outputFormat` ambiguity | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED (default-lane pin ✓; live lane operator-run) | The ambiguity IS resolved and pinned: `FORMAT_FIELD = "format"` and `STRUCTURED_RESPONSE_PATH = ("info","structured")` (`app/llm/contract.py:35,50`), asserted against the committed slice with a negative control over raw fixture text (`test_contract_snapshot.py:223-235`) and a guard-can-fail companion (`:262-301`). The deny-rule shape is now pinned too (03-09: `PermissionRule` + `test_the_permission_deny_rule_contract_matches_the_snapshot`). The spec-reading half is `tests/llm/test_contract_live.py`, `@pytest.mark.live` and deselected (`pyproject.toml:55`; `--collect-only` → 93/94, 1 deselected). No CI runner by design (D-53); the live lane is operator-run (WINDOWS #6). |
| 4 | Untrusted listing text reaches the model only as user content (never the system prompt) and tools are disabled by default | ✓ VERIFIED (structural); live observation is a human item | `SELFTEST_SYSTEM_PROMPT` is a module constant with an AST-verified single `Constant` and no `%`/`.format` (`tests/api/test_llm_selftest.py`); the builder assigns `system` a bare `Name` (`test_trust_boundary.py:221-248`); `parts` is the only channel and emits text parts only; the message body sends no `tools` key by default and rejects `"*"` (`builders.py:98-107`); an explicit port grant is now forwarded as `{name: True}` (`opencode_server.py:420-428`, `test_trust_boundary.py:82-119`); the session carries the deny-only `permission` ruleset `DEFAULT_DENY_RULES` which `_create_session` actually sends (`opencode_server.py:104-110`, `test_trust_boundary.py:178-197`). Live confirmation = WINDOWS #7. |

### Observable Truths (plan `must_haves.truths`)

| # | Plan | Truth | Status | Evidence |
| --- | ---- | ----- | ------ | -------- |
| 1 | 03-01 | Schema-validated call completes through the opencode backend with no second provider key | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | See SC1; live call operator-run |
| 2 | 03-01 | Schema violation → explicit retried outcome; exactly one `llm_calls` row; no failure path raises | ✓ VERIFIED | `opencode_server.py:528-535`; `test_complete_structured.py`; `test_llm_selftest.py` |
| 3 | 03-01 | Untrusted content only as `parts`; port tools default empty; no param reaches `system` | ✓ VERIFIED | `builders.py:55-108`; `base.py:113-138`; `test_trust_boundary.py` |
| 4 | 03-01 | Default-lane test pins the request vocabulary; importing constants needs no network | ✓ VERIFIED | `test_contract_snapshot.py`; `contract.py` imports only `__future__` |
| 5 | 03-01 | Operator can trigger one call from `/settings`; exactly one probe row, `run_id IS NULL`, no `runs` row | ✓ VERIFIED | `settings.py:390-465`; `test_llm_selftest.py` (real-server execution = human item) |
| 6 | 03-01 | `run_pipeline()` writes zero `llm_calls` rows (D-49) | ✓ VERIFIED | `run.py` no LLM import; `tests/pipeline/test_filter_stage.py`; `test_finish_llm_counters.py` |
| 7 | 03-02 | Default-lane test fails if the structured-output field name is absent from the snapshot | ✓ VERIFIED | `test_contract_snapshot.py:139-146`; fixture `opencode-doc.json` |
| 8 | 03-02 | Same test asserts the builder emits exactly the pinned names | ✓ VERIFIED | `test_contract_snapshot.py:241-256` |
| 9 | 03-02 | Negative control blocks `outputFormat`/`structured_output` | ✓ VERIFIED | `test_contract_snapshot.py:223-235` |
| 10 | 03-02 | Operator `@pytest.mark.live` test refetches `/doc`, diffs, makes no LLM call | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `test_contract_live.py:264-307` complete (26 fact keys incl. deny-rule) + collectable under `-m live`; not run in sandbox (WINDOWS #6) |
| 11 | 03-02 | Default lane structurally cannot run the live test; cheap guard makes it explicit | ✓ VERIFIED | `pyproject.toml:55-58`; `test_contract_snapshot.py:307-314`; collect-only 93/94, 1 deselected |
| 12 | 03-03 | `StructuredOutputError` and `ValidationError` → `ok=False`, `status='invalid'`, attempt count from server `data.retries` | ✓ VERIFIED | `opencode_server.py:743-819`; `test_complete_structured.py` |
| 13 | 03-03 | Every observed condition maps onto the four legal statuses; cause in `error_kind`, never a fifth status | ✓ VERIFIED | `opencode_server.py:68-83, 659-858`; full matrix green. A non-parseable `info.structured` now maps to `invalid` with identity preserved (03-08) |
| 14 | 03-03 | A transport failure is a value, never an exception | ✓ VERIFIED | `opencode_server.py:433-493, 508-535`; `test_complete_structured.py` |
| 15 | 03-03 | Truncated JSON salvaged only via an explicit allow-list; an unexpected mismatch never laundered | ✓ VERIFIED | `TOLERATED_SCHEMA_ERRORS` (`opencode_server.py:90`), `_salvage` (`:638-656`), `_tolerant_validator` (`:607-635`); `tests/llm/test_salvage.py` |
| 16 | 03-04 | Every recorded call carries the opencode server version, queryable per row | ✓ VERIFIED | migration 0003 adds `server_version VARCHAR(32)` (`alembic/versions/0003_llm_call_server_version.py`); ORM mirror `app/db/models.py`; `alembic heads` → single `0003` |
| 17 | 03-04 | `server_version` round-trips end-to-end with the drift guard green | ✓ VERIFIED | `llm_call_repo.py`; `tests/db/test_llm_call_repo.py`; `tests/db/test_orm_drift.py` green unedited |
| 18 | 03-04 | `llm_calls` still has zero JSON columns | ✓ VERIFIED | `tests/db/test_no_pii_columns.py` green with no edit (targeted run) |
| 19 | 03-04 | `record_llm_call` never commits, validates before SQL, reads default rather than raise | ✓ VERIFIED | `llm_call_repo.py:150-215`; `test_llm_selftest.py`; `test_llm_call_repo.py` |
| 20 | 03-05 | Every Phase-3 ceiling is a Settings field with documented default asserted by the config guard, so no completion timeout or retry count is a literal | ✓ VERIFIED (was ✗ FAILED) | `app/config.py:43-49`; `tests/test_config.py` guard + env-tunability; **Gap 1 fixed** — `retries: int | None = None` on both port (`base.py:122`) and adapter (`opencode_server.py:356`), making `budget = retries if retries is not None else settings.opencode_max_retries` (`:405`) the live default path. `test_an_omitted_retries_honours_the_settings_ceiling` patches the setting to 7 and observes exactly 7 POSTs / `attempts == 7` (green) |
| 21 | 03-05 | Each new `opencode_*` setting reaches the container via `compose.yml` | ✓ VERIFIED | `compose.yml` (`${VAR:-default}` matching `config.py`) |
| 22 | 03-05 | `.env.example` documents every new key | ✓ VERIFIED | `.env.example` |
| 23 | 03-05 | The literal-absence scan still reports no distinctive threshold literal in `app/pipeline`/`app/probe` | ✓ VERIFIED | `tests/test_config.py` green |
| 24 | 03-06 | Untrusted content never reaches `system`; the only app `system` value is a non-interpolated constant | ✓ VERIFIED | `settings.py`; `test_llm_selftest.py`; `test_trust_boundary.py:221-248` |
| 25 | 03-06 | Tools denied by default via the session `permission` ruleset | ✓ VERIFIED | `opencode_server.py:104-110, 309-345`; `test_trust_boundary.py:178-197` (server-honoured deny = human item) |
| 26 | 03-06 | The deny is observed: returned `parts` types and `info` keys recorded | ✓ VERIFIED | `base.py:93-98`; `opencode_server.py:586-604, 725-733`; `settings.html`; `test_trust_boundary.py` |
| 27 | 03-06 | Nothing outside `app/llm/` imports `httpx` on the LLM call path or `subprocess` anywhere | ✓ VERIFIED | `tests/test_import_discipline.py` green |
| 28 | 03-07 | Instruction-like text is recorded on the listing, never executed or stripped | ✓ VERIFIED | `run.py` `_persist_result`; `tests/pipeline/test_injection_finding.py:157-178` |
| 29 | 03-07 | A clean listing leaves `quality_signals_json` NULL | ✓ VERIFIED | `stages.py`; `test_injection_finding.py:181-189` |
| 30 | 03-07 | The finding is counts-only (no matched text); the PII/JSON allow-list unchanged | ✓ VERIFIED | payload built in `run.py`; sentinel assertion `test_injection_finding.py:174-178`; `tests/db/test_no_pii_columns.py` green unedited |
| 31 | 03-07 | `run_pipeline()` still writes zero `llm_calls` while the `_finish` seam exists and is proven | ✓ VERIFIED | `run.py:578-579`; `tests/pipeline/test_finish_llm_counters.py` |
| 32 | 03-07 | The queue badge does not break existing queue assertions (or is dropped) | ✓ VERIFIED | badge + `.badge-flagged` CSS rule shipped (`_listing_row.html`, `static/vendor/app.css`); queue tests, stylesheet-coverage and PII guard green |

**Score:** 30/32 truths verified (2 present, behavior-unverified; the previously FAILED truth 20 is now VERIFIED)

### Deferred Items

None. Every outstanding item is either a real human-verification item or closed; nothing is deferred to a later milestone phase (Phase 5 consumes the seams this phase ships but does not close any Phase-3 truth).

### Advisory (New Scope, Unevidenced)

None. This re-verification round surfaced no new-scope Step-7 blocker requiring deterministic evidence; the five warning-level defects the prior pass raised (WR-01 dead `tools` channel, WR-03 salvage `ValueError` misclassification, WR-04 unguarded deny-rule shape, the missing clean-re-ingest test, and the 200-on-raise route) were all closed by plans 03-08/03-09 and each closure is pinned by a named, passing test.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/llm/contract.py` | Single home of pinned wire vocabulary | ✓ VERIFIED | 123 lines; imports only `__future__`; `__all__`; `FORMAT_FIELD="format"`, `STRUCTURED_RESPONSE_PATH=("info","structured")`, permission constants |
| `app/llm/builders.py` | Pure request builders | ✓ VERIFIED | `to_message_parts`, `to_message_body` (wildcard guard), `to_session_body` (inverse model shape) |
| `app/llm/base.py` | `StructuredCallResult` + port method | ✓ VERIFIED | `extra="forbid"`; `retries: int | None = None` (:122) — Gap 1 fixed; docstring names `Settings.opencode_max_retries` as the adapter-applied default |
| `app/llm/opencode_server.py` | Total adapter + taxonomy + salvage | ✓ VERIFIED | both-shape `parse_providers`, `_resolve_model` fail-loud, deny ruleset, observation, 4-value taxonomy, `_salvage`, forwarded tool grant, `except ValueError` branch |
| `app/domain/schemas/probe.py` | `ProbeResult`, every field defaulted | ✓ VERIFIED | `extra="ignore"`; salvage works; docstring describes remove-and-revalidate (WR-03 doc fix) |
| `app/db/repositories/llm_call_repo.py` | `record_llm_call` + reads | ✓ VERIFIED | validates pre-SQL, never commits, `latest_probe`, `llm_totals_for_run` |
| `app/api/settings.py` | Selftest route + constant prompt | ✓ VERIFIED | `POST /settings/llm-test`, plain POST, one row, no run; raise branch records then returns 500 |
| `app/web/templates/html/settings.html` | Plain-POST selftest + full D-52 detail + observation | ✓ VERIFIED | no `hx-`; status/cause/attempts/latency/provider/model/version; system prompt + `part_types`/`info_keys` rendered |
| `alembic/versions/0003_llm_call_server_version.py` | `server_version` column | ✓ VERIFIED | nullable `String(32)`, symmetric downgrade; single head `0003` |
| `tests/llm/fixtures/opencode-doc.json` | Committed projection | ✓ VERIFIED | includes `PermissionRule` (`properties`/`required`/`action_enum`); `_meta.note` records the deliberate D-55 widening; no wrong spellings |
| `tests/llm/test_contract_snapshot.py` | Default-lane contract + negative control + guard-can-fail + deny-rule pin | ✓ VERIFIED | has teeth |
| `tests/llm/test_contract_live.py` | Operator live lane (26 fact keys) | ✓ VERIFIED (code) / ⚠️ unrun | deselected by default; collects 1 under `-m live` |
| `docs/runbook-opencode-contract.md` | Refresh procedure | ✓ VERIFIED | numbered steps, host-vs-container note, `.venv/bin/python`, "why `structured`" |
| `app/pipeline/run.py`, `stages.py`, `app/domain/models.py`, `queue_repo.py`, `_listing_row.html` | Finding + counter seam | ✓ VERIFIED | quality_signals plumbing; `_finish` keyword seam |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `builders.py` | `contract.py` | all wire names imported | ✓ WIRED | no wire literal authored in the builder |
| `complete_structured` | `discover_models` | `_resolve_model` derives `{providerID,modelID}` | ✓ WIRED | fails loud on miss (`opencode_server.py:269-307`) |
| `settings.py` route | `llm_call_repo` | `record_llm_call` + route-owned `commit()` | ✓ WIRED | repo never commits; route commits once (both value and raise paths) |
| `tests/conftest.py` `OfflineLLMBackend` | `complete_structured` | stub method present | ✓ WIRED | returns honest offline error; no socket |
| `_create_session` | session `permission` deny | `to_session_body(permission=DEFAULT_DENY_RULES)` | ✓ WIRED | sent from captured request (`test_trust_boundary.py:178-197`) |
| `_persist_result` | `listings.quality_signals_json` | `normalise_listing(quality_signals=…)` | ✓ WIRED | None for clean listings; update-path proof added (03-09) |
| `_finish` | `runs.llm_calls`/`llm_tokens` | keyword seam, no caller (D-49) | ✓ WIRED | proven by direct unit test |
| `complete_structured` | `tools` allow-list | `to_message_body(tools=tool_grant)` | ✓ WIRED (was ✗ NOT_WIRED) | WR-01 fixed: `{name: True}` conversion forwarded; default still emits no key (`test_trust_boundary.py:82-119`) |

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
| Full suite at the claimed baseline | `.venv/bin/python -m pytest -q` | `834 passed, 3 deselected in 126.60s` | ✓ PASS |
| Lint | `.venv/bin/python -m ruff check .` | `All checks passed!` | ✓ PASS |
| Live lane excluded by default / selectable | `pytest -q tests/llm --collect-only` / `pytest -q -m live tests/llm/test_contract_live.py --collect-only` | `93/94 (1 deselected)` / `1` | ✓ PASS |
| Guard cluster | `pytest -q tests/db/test_orm_drift.py tests/db/test_no_pii_columns.py tests/db/test_migration_contract.py tests/test_import_discipline.py tests/test_config.py tests/llm/test_contract_snapshot.py tests/llm/test_trust_boundary.py tests/api/test_llm_selftest.py tests/pipeline/test_injection_finding.py` | `92 passed` | ✓ PASS |
| Named gap-closure tests (9) | `pytest -q <9 named tests>` | `9 passed in 20.42s` | ✓ PASS |
| **Gap 1 repro (independent)** | patched `settings.opencode_max_retries = 7`, omitted `retries` | exactly 7 completion POSTs, `attempts == 7` (via `test_an_omitted_retries_honours_the_settings_ceiling`) | ✓ PASS |
| Migration head | `.venv/bin/python -m alembic heads` | `0003 (head)` | ✓ PASS |
| Debt-marker gate | `grep -rE "TBD|FIXME|XXX" app/ tests/` | none | ✓ PASS |

### Probe Execution

N/A — no `scripts/*/tests/probe-*.sh` probes are declared or implied by this phase. The "live" pytest lane is a test lane (operator-run), not a probe script; its status is captured in Human Verification Required.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
| ----------- | ------------ | ----------- | ------ | -------- |
| PLAT-02 | 03-01, 03-03, 03-04, 03-05, 03-06, 03-07, 03-08, 03-09 | The LLM is reached through opencode as a sibling service with no second provider key required | ✓ SATISFIED (code) / ⚠️ live half human | Port + adapter + selftest + config exist; `Settings` has no second provider key and the request carries no credential. Live real call = WINDOWS #5. |
| PLAT-05 | 03-01, 03-02, 03-09 | The opencode structured-output contract is covered by a test that fails loudly on an upgrade | ✓ SATISFIED (code) / ⚠️ live lane human | `format`/`structured` + the deny-rule shape pinned once with a negative control (default lane) and a live `/doc` diff lane; the live lane is operator-run (no CI runner). |

**Accounted-for requirement IDs:** PLAT-02, PLAT-05 (the only IDs mapped to Phase 3 in REQUIREMENTS.md; both appear in plan frontmatter). **Orphaned requirements:** none — no other REQUIREMENTS.md ID maps to Phase 3.

### Test Quality Audit

| Test File | Linked Req | Active | Skipped | Circular | Assertion Level | Verdict |
|-----------|-----------|--------|---------|----------|-----------------|---------|
| `tests/llm/test_complete_structured.py` | PLAT-02 | 27 | 0 | No | Behavioral (POST count, status/error_kind/attempts, identity) | ✓ PASS |
| `tests/llm/test_trust_boundary.py` | PLAT-02 | 14 | 0 | No | Behavioral (captured body/keys, sentinel leak) | ✓ PASS |
| `tests/llm/test_contract_snapshot.py` | PLAT-05 | 13 | 0 | No (fixture projected from live spec; external oracle = live `/doc`) | Value + guard-can-fail | ✓ PASS |
| `tests/llm/test_salvage.py` | PLAT-02 | 9 | 0 | No | Behavioral (allow-list load-bearing) | ✓ PASS |
| `tests/api/test_llm_selftest.py` | PLAT-02 | 14 | 0 | No | Integration (row count, status 500, rendered values) | ✓ PASS |
| `tests/pipeline/test_injection_finding.py` | PLAT-02 | 10 | 0 | No | Integration (stored JSON, update path) | ✓ PASS |
| `tests/db/test_llm_call_repo.py` | PLAT-02 | 11 | 0 | No | Integration (round-trip, NULL totals, never-commits) | ✓ PASS |
| `tests/test_config.py` | PLAT-04 (constrains PLAT-02) | 11 | 0 | No | AST + env-tunability + guard-can-fail | ✓ PASS |

**Disabled tests on requirements:** 0 → no BLOCKER.
**Circular patterns detected:** 0 → no BLOCKER. The contract fixture is a hand-projection validated against the live spec, and the default-lane test asserts builder == snapshot; the live lane is the external-oracle half of the chain.
**Insufficient assertions:** 0 → no WARNING.

### Decision Coverage

All 10 trackable CONTEXT.md decisions (D-48..D-57) are honored by shipped artifacts. Gate result: `{honored: 10, total: 10, not_honored: []}` — non-blocking.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/db/models.py` / `llm_call_repo.py` | — | `error_kind` (D-52's operator label) has no column; only the immediate POST render shows the label, a reload shows the persisted `error`/`status`/`attempts` | ℹ️ Info | Pre-existing design limitation, documented in 03-04-SUMMARY; the cause string and attempt count ARE persisted in `error`/`attempts`, so D-52's audit intent holds. Not a must-have. |

**Debt markers:** none (`TBD`/`FIXME`/`XXX` absent from every phase-touched file). No 🛑 Blocker, no ⚠️ Warning remain — all eight anti-patterns the prior pass raised are closed.

### Human Verification Required

1. **Live real schema-constrained call from /settings (SC1 / PLAT-02).** Start the user's `opencode serve` with no second provider key configured, open `/settings`, press **Test LLM backend**, confirm a validated result and exactly one new `llm_calls` row (`purpose='probe'`, `run_id IS NULL`) and no new `runs` row.
2. **Operator live `/doc` drift lane (SC3 / PLAT-05).** On the host: `OPENCODE_BASE_URL=http://127.0.0.1:4096 .venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py`; expect 0 divergent pointers across the 26 fact keys (including the deny-rule properties/action enum) and the committed `_meta.server_version` (1.18.31) to match `GET /global/health`.
3. **Live trust-boundary observation (SC4).** With the selftest result page open on a real call, confirm the returned parts carry no tool invocation, the rendered system prompt is the module constant, and `info_keys` contains the structured payload key.
4. **Close Open Question Q1 live.** On the first real call, confirm the pinned `format` request field and `info.structured` response field are accepted by the running server.

### Gaps Summary

The phase's four roadmap criteria are implemented, wired, and proven in the default lane, and the prior verification's blocking gap is closed.

**Gap closure (re-verification):**
- **Gap 1 (truth 03-05 #20, was failed):** `complete_structured` declared `retries: int = 2` on both the port and the adapter, making the documented `settings.opencode_max_retries` fallback dead code. **Closed** by plan 03-08: both signatures are now `retries: int | None = None` (`app/llm/base.py:122`, `app/llm/opencode_server.py:356`) and the existing `budget = retries if retries is not None else settings.opencode_max_retries` line (`:405`) is the live default path. Independently reproduced by the named test: patched ceiling 7 + omitted `retries` → exactly 7 POSTs, `attempts == 7`.
- **Gap 2 (03-03 default-ceiling claim, same root cause):** **Closed** by the same signature change; 03-03's retry-BOUND truth (an explicit `retries=3` issues 3 POSTs; a schema failure is never retried client-side) still holds and is green.
- **All five prior warnings closed by 03-08/03-09:** the dead `tools` channel now forwards an explicit grant (`{name: True}`, default still emits no key); the salvage `ValueError` is now an `invalid` outcome preserving provider/model/agent/part_types/info_keys; the `PermissionRule` deny-rule shape is pinned in the fixture, the default-lane snapshot test (with decoy guard-can-fail), and the live projection; the clean re-ingest update path preserves a recorded finding; and a raising backend writes one `error` probe row and returns 500.

**Remaining (not gaps):** the two behavior-unverified truths (the real `opencode serve` call = SC1, and the operator live `/doc` diff = SC3) and the live trust-boundary observation (SC4). These are operator-run by design because the default lane must never open a socket, the repo has no CI runner (D-53), and a real call needs the operator's server. They route to the end-of-phase human checkpoint; the phase is otherwise complete and ready for Phase 5.

---

_Verified: 2026-09-18T11:06:23Z_
_Verifier: the agent (gsd-verifier)_
