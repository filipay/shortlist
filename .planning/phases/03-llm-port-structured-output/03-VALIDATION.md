---
phase: "3"
slug: "llm-port-structured-output"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-17"
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `03-RESEARCH.md` §Validation Architecture. Task IDs / Plan / Wave
> columns are filled once `03-*-PLAN.md` files exist.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest **9.1.1** + pytest-asyncio **1.4.0**, `asyncio_mode = "auto"` |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`:49-58`) — `testpaths=["tests"]`, `pythonpath=["."]`, `addopts="-m 'not live'"`, `live` marker declared |
| **Quick run command** | `.venv/bin/python -m pytest -q tests/llm tests/test_config.py tests/test_auth_seam.py tests/db/test_orm_drift.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest -q` (≈116 s) |
| **Live / operator lane** | `.venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py` — never in CI |
| **Schema gate** | `.venv/bin/python -m pytest -q tests/db/test_migration_contract.py tests/db/test_orm_drift.py tests/db/test_no_pii_columns.py -x` |
| **Import-discipline gate** | `.venv/bin/python -m pytest -q tests/test_import_discipline.py -x` |
| **Container smoke (operator-run)** | `docker compose up -d --wait && curl -fsS localhost:8000/health` |
| **Fixtures that matter** | `client` (ASGI + offline LLM stub + temp DB), `migrated_db`, `session_factory`, `db_session` — all in `tests/conftest.py` |
| **Estimated runtime** | quick lane seconds; full suite ≈116 s |

> **Runner note (verified 2026-09-17):** `.venv-host/` is **broken** in this workspace — its
> interpreter is baked to a different absolute path (`/mnt/data/docker/apps/opencode/workspace/job-search/`)
> and its `pydantic_core` fails to import. There is no `.venv/bin/pytest` either. **Always use
> `.venv/bin/python -m pytest`.** This matches `STATE.md`'s Phase-2 record and supersedes the
> `.venv-host/bin/pytest` form recorded in Phase 02's plans.

---

## Sampling Rate

- **After every task commit:** `.venv/bin/python -m pytest -q tests/llm tests/api/test_llm_selftest.py tests/test_config.py -x` (seconds)
- **After every plan wave:** `.venv/bin/python -m pytest -q` (≈116 s — exceeds a 30 s budget, so treat it as the wave gate, not the per-commit gate)
- **Before `/gsd-verify-work`:** Full suite green **and** the operator live lane run once against the real server (`pytest -q -m live tests/llm/test_contract_live.py`) **and** the selftest invoked once from the UI with the result recorded
- **Phase gate:** the three above, plus the docs gate below
- **Docs gate:** the committed fixture's `_meta.server_version` must match what the live lane observed
- **Max feedback latency:** seconds (quick lane)
- **Never in CI:** the `live`-marked lane. There is **no CI runner** in this repo (no `.github/`, `.gitlab-ci.yml`, `.circleci`) and `addopts = "-m 'not live'"` excludes it by default — by design (D-53).

---

## Per-Task Verification Map

*Task ID / Plan / Wave columns are seeded as `—` and are filled in once `03-*-PLAN.md` files exist.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| — | — | — | PLAT-02 | T-3-01, T-3-02 | `complete_structured` returns a validated typed object from a stubbed 200 response | unit | `.venv/bin/python -m pytest -q tests/llm/test_complete_structured.py -x` | ❌ W0 | ⬜ pending |
| — | — | — | PLAT-02 | T-3-02 | A `StructuredOutputError` envelope → `ok=False`, `status="invalid"`, `attempts` from `data.retries` | unit | `.venv/bin/python -m pytest -q tests/llm/test_complete_structured.py::test_structured_output_error_is_invalid -x` | ❌ W0 | ⬜ pending |
| — | — | — | PLAT-02 | T-3-02 | Transport failure → `status="error"` / `error_kind="unreachable"`, never raises | unit | `.venv/bin/python -m pytest -q tests/llm/test_complete_structured.py::test_transport_failure_is_a_value -x` | ❌ W0 | ⬜ pending |
| — | — | — | PLAT-02 | T-3-02 | Truncated JSON salvages via `from_json(allow_partial=True)` + tolerated defaults | unit | `.venv/bin/python -m pytest -q tests/llm/test_salvage.py -x` | ❌ W0 | ⬜ pending |
| — | — | — | PLAT-02 | T-3-03 | The selftest route declares `current_user` and stays green in the seam walk | integration | `.venv/bin/python -m pytest -q tests/test_auth_seam.py -x` | ✅ guard | ⬜ pending |
| — | — | — | PLAT-02 | T-3-02, T-3-03 | One selftest writes exactly one `llm_calls` row with `run_id IS NULL`, `purpose='probe'`, and **no** `runs` row | integration | `.venv/bin/python -m pytest -q tests/api/test_llm_selftest.py -x` | ❌ W0 | ⬜ pending |
| — | — | — | PLAT-02 | T-3-03 | D-52's detail is rendered (status, attempts, latency, validation message) — not a bare badge | integration | `.venv/bin/python -m pytest -q tests/api/test_llm_selftest.py::test_the_result_shows_cause_and_attempt_count -x` | ❌ W0 | ⬜ pending |
| — | — | — | PLAT-02 | T-3-03 | `/health`'s shape is unchanged by the new work | integration | `.venv/bin/python -m pytest -q tests/api/test_health.py -x` | ✅ guard | ⬜ pending |
| — | — | — | PLAT-02 | T-3-01, T-3-04 | Untrusted text cannot reach `system`; `tools` is denied by default | unit + live | `.venv/bin/python -m pytest -q tests/llm/test_trust_boundary.py -x` + the selftest | ❌ W0 | ⬜ pending |
| — | — | — | PLAT-02 | T-3-01 | `parse_providers` accepts BOTH the list shape and the live dict shape | unit | `.venv/bin/python -m pytest -q tests/llm/test_discovery_redaction.py -x` | ✅ extend | ⬜ pending |
| — | — | — | PLAT-02 | T-3-01 | No `httpx`/`subprocess` reachable from the LLM call path outside `app/llm` | guard | `.venv/bin/python -m pytest -q tests/test_import_discipline.py -x` | ✅ extend | ⬜ pending |
| — | — | — | PLAT-05 | T-3-01 | Builder emits exactly the pinned names; snapshot contains them; negative control | unit (default lane) | `.venv/bin/python -m pytest -q tests/llm/test_contract_snapshot.py -x` | ❌ W0 | ⬜ pending |
| — | — | — | PLAT-05 | T-3-01 | Live `/doc` diffs clean against the committed slice | live (operator) | `.venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py -x` | ❌ W0 | ⬜ pending |
| — | — | — | PLAT-05 | T-3-01 | The default lane never runs the live test | guard | `.venv/bin/python -m pytest -q tests/llm --collect-only -q` asserting the live file's tests are deselected | ❌ W0 | ⬜ pending |
| — | — | — | D-12 | T-3-05 | `server_version` round-trips: migration 0003 → ORM → `record_llm_call` → read back | integration | `.venv/bin/python -m pytest -q tests/db/test_migration_contract.py tests/db/test_orm_drift.py tests/db/test_llm_call_repo.py -x` | ❌ W0 (repo test) | ⬜ pending |
| — | — | — | D-12 | T-3-05 | Both new ceilings are `Settings` fields and are env-tunable | unit | `.venv/bin/python -m pytest -q tests/test_config.py -x` | ✅ extend | ⬜ pending |
| — | — | — | §6.3 | T-3-04 | `instruction_like` / `patterns_matched` persist onto `listings.quality_signals_json` | integration | `.venv/bin/python -m pytest -q tests/pipeline/test_injection_finding.py -x` | ❌ W0 | ⬜ pending |
| — | — | — | §6.3 | T-3-04 | The PII/JSON-column allow-list is unchanged (no new blob) | guard | `.venv/bin/python -m pytest -q tests/db/test_no_pii_columns.py -x` | ✅ unchanged | ⬜ pending |
| — | — | — | D-49 | T-3-02 | `run_pipeline` still writes **zero** `llm_calls` rows | guard | `.venv/bin/python -m pytest -q tests/pipeline/test_filter_stage.py -x` | ✅ existing (`:197`) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/llm/fixtures/opencode-doc.json` — the committed structured-output slice (D-53/D-55)
- [ ] `tests/llm/test_contract_snapshot.py` — default-lane builder-vs-snapshot + negative control (PLAT-05)
- [ ] `tests/llm/test_contract_live.py` — `@pytest.mark.live` spec fetch + diff (PLAT-05)
- [ ] `tests/llm/test_complete_structured.py` — ok / invalid / timeout / unreachable, retry loop, identity recording (PLAT-02)
- [ ] `tests/llm/test_salvage.py` — `allow_partial` + `PydanticUseDefault` tolerated-types-only, including the no-default pitfall (PLAT-02, M1)
- [ ] `tests/llm/test_trust_boundary.py` — untrusted content cannot reach `system`; `tools` deny encoding; the system prompt is a constant (criterion 4)
- [ ] `tests/api/test_llm_selftest.py` — one call → one `llm_calls` row, `run_id IS NULL`, `purpose='probe'`, no `runs` row, D-52's rendered detail (D-48/D-50/D-52)
- [ ] `tests/db/test_llm_call_repo.py` — the writer's contract, `now` pinning, never-commits, `purpose`/`status` validation
- [ ] `tests/pipeline/test_injection_finding.py` — the flag lands on `listings.quality_signals_json` and a clean listing leaves it NULL
- [ ] `tests/conftest.py:33-45`'s `OfflineLLMBackend` must gain `complete_structured` in Wave 0 (Pitfall P10). No other fixture support needed — `tests/conftest.py` already builds a migrated temp DB via `alembic upgrade head`, so migration 0003 is exercised automatically.
- [ ] Existing guard edits scheduled as explicit tasks, not discovered as regressions:
      `tests/db/test_migration_contract.py:294`, `:305`, `:500` + the 0002 docstrings;
      `tests/test_config.py:28-44` (`REQUIRED_SETTINGS_FIELDS` + `LIMIT_FIELDS` for the new ceilings);
      `tests/api/test_settings_page.py:54-59` **only if** the HTMX-vs-plain-POST resolution chooses the HTMX form;
      `compose.yml:15-29` passthroughs; `.env.example`.
- [ ] Framework install: **none** — zero new packages this phase.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `/doc` contract diff against the committed slice | PLAT-05 | Requires a running `opencode serve`; the repo has no CI runner and `addopts` excludes `live` | On the **host**, export `OPENCODE_BASE_URL=http://127.0.0.1:4096` then run `.venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py`. On drift: inspect the diff, decide genuine rename vs unrelated churn, refresh the fixture **deliberately** and bump `_meta.server_version`. |
| One real schema-constrained call end to end through the app | PLAT-02 (criterion 1) | Needs the user's real opencode backend with **no second provider key**; a stub cannot prove it | Start the server (`opencode serve --hostname 0.0.0.0` if the container must reach it), open `/settings`, invoke **Test LLM backend**, confirm a validated result, then confirm exactly one new `llm_calls` row with `purpose='probe'`, `run_id IS NULL`, and **no** new `runs` row. |
| Trust boundary under real (not canned) adversarial text | PLAT-02 (criterion 4) | Observation of the live response is the only proof the deny encoding holds on the running server version | With the selftest result page open, confirm the returned `parts` carry no tool invocation and the system prompt shown is the module constant. The selftest's first live run should print `list(body["info"])` to close Open Question Q1 (`structured` vs `structured_output`). |
| Container reachability of the host opencode server | D-06/D-08 | Docker is absent in the agent sandbox; operator-only (WINDOWS #1) | `docker compose up -d --wait && curl -fsS localhost:8000/health`; confirm `/health` reports opencode reachable and **still returns HTTP 200** when it is not. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30 s (quick lane)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
