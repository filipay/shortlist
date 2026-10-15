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

*Filled 2026-09-17 from `03-01-PLAN.md` … `03-07-PLAN.md`.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-T1 (tracer) | 03-01 | 1 | PLAT-02 | T-3-01, T-3-05 | `complete_structured` returns a validated typed object from a stubbed 200 response; builder emits the pinned wire shape | unit + tracer | `.venv/bin/python -m pytest -q tests/llm/test_complete_structured.py -x` | ❌ W0 | ⬜ pending |
| 01-T2 | 03-01 | 1 | PLAT-02 | T-3-04 | `parse_providers` accepts BOTH the list shape and the live dict shape; the live `key` field is the scanned sentinel | unit | `.venv/bin/python -m pytest -q tests/llm/test_discovery_redaction.py -x` | ✅ extend | ⬜ pending |
| 01-T3 | 03-01 | 1 | PLAT-02 | T-3-01, T-3-06 | One selftest writes exactly one `llm_calls` row with `run_id IS NULL`, `purpose='probe'`, and **no** `runs` row; D-52's detail is rendered | integration | `.venv/bin/python -m pytest -q tests/api/test_llm_selftest.py -x` | ❌ W0 | ⬜ pending |
| 01-T3 | 03-01 | 1 | PLAT-02 | T-3-03 | The selftest route declares `current_user` and stays green in the seam walk | integration | `.venv/bin/python -m pytest -q tests/test_auth_seam.py -x` | ✅ guard | ⬜ pending |
| 01-T3 | 03-01 | 1 | PLAT-02 | T-3-07 | `/health`'s shape is unchanged by the new work | integration | `.venv/bin/python -m pytest -q tests/api/test_health.py -x` | ✅ guard | ⬜ pending |
| 01-T3 | 03-01 | 1 | D-49 | T-3-22 | `run_pipeline` still writes **zero** `llm_calls` rows | guard | `.venv/bin/python -m pytest -q tests/pipeline/test_filter_stage.py -x` | ✅ existing (`:197`) | ⬜ pending |
| 02-T1 | 03-02 | 2 | PLAT-05 | T-3-09, T-3-10 | Builder emits exactly the pinned names; snapshot contains them; negative control over raw fixture text; guard-can-fail companion; default lane cannot run the live file | unit (default lane) | `.venv/bin/python -m pytest -q tests/llm/test_contract_snapshot.py -x` | ❌ W0 | ⬜ pending |
| 02-T2 | 03-02 | 2 | PLAT-05 | T-3-11, T-3-12 | Live `/doc` diffs clean against the committed slice; deselectable in the default lane, collectable under `-m live` | live (operator) | `.venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py -x` | ❌ W0 | ⬜ pending |
| 03-T1 | 03-03 | 2 | PLAT-02 | T-3-14, T-3-05 | A `StructuredOutputError` envelope → `ok=False`, `status="invalid"`, `attempts` from `data.retries`; transport failure → `status="error"` / `error_kind="unreachable"`, never raises | unit | `.venv/bin/python -m pytest -q tests/llm/test_complete_structured.py -x` | ❌ W0 | ⬜ pending |
| 03-T2 | 03-03 | 2 | PLAT-02 | T-3-01 | Truncated JSON salvages via `from_json(allow_partial=True)` + tolerated defaults; an untolerated mismatch still fails loudly | unit | `.venv/bin/python -m pytest -q tests/llm/test_salvage.py -x` | ❌ W0 | ⬜ pending |
| 04-T1 | 03-04 | 2 | PLAT-02 | T-3-09 | One-way-door decision gate before the schema change (checkpoint, not a test) | checkpoint | operator decision — no command | n/a | ⬜ pending |
| 04-T2 | 03-04 | 2 | D-12 | T-3-05, T-3-15 | Migration 0003 → ORM → migrated DDL agree; `llm_calls` keeps zero JSON columns; guards updated deliberately | integration | `.venv/bin/python -m pytest -q tests/db/test_migration_contract.py tests/db/test_orm_drift.py tests/db/test_no_pii_columns.py -x` | ✅ guards | ⬜ pending |
| 04-T3 | 03-04 | 2 | D-12, PLAT-02 | T-3-16 | `server_version` round-trips: `record_llm_call` → `latest_probe`; `purpose`/`status` validated pre-SQL; never commits | integration | `.venv/bin/python -m pytest -q tests/db/test_llm_call_repo.py -x` | ❌ W0 | ⬜ pending |
| 05-T1 | 03-05 | 2 | PLAT-02 | T-3-06 | All three new ceilings are `Settings` fields, are in both guard tuples, and are env-tunable | unit | `.venv/bin/python -m pytest -q tests/test_config.py -x` | ✅ extend | ⬜ pending |
| 05-T2 | 03-05 | 2 | PLAT-02 | T-3-06, T-3-17 | Every new `opencode_*` key is forwarded by `compose.yml` and documented in `.env.example` | manifest | `.venv/bin/python -m pytest -q tests/test_deploy_manifest.py -x` | ✅ extend | ⬜ pending |
| 06-T1 | 03-06 | 3 | PLAT-02 (criterion 4) | T-3-01, T-3-03 | Untrusted text cannot reach `system`; a default session carries a deny-only `permission` ruleset; a wildcard `tools` key is rejected; text-only parts | unit + guard | `.venv/bin/python -m pytest -q tests/llm/test_trust_boundary.py -x` | ❌ W0 | ⬜ pending |
| 06-T2 | 03-06 | 3 | PLAT-02 | T-3-18 | No `httpx` reachable from the LLM call path outside `app/llm`; `subprocess` absent outside `app/llm`; `app/sources` excluded by construction | guard | `.venv/bin/python -m pytest -q tests/test_import_discipline.py -x` | ✅ extend | ⬜ pending |
| 06-T3 | 03-06 | 3 | PLAT-02 | T-3-19 | The returned `part_types` / `info_keys` are rendered (type names only) — the observation that closes Open Question Q1 | integration | `.venv/bin/python -m pytest -q tests/api/test_llm_selftest.py -x` | ❌ W0 | ⬜ pending |
| 07-T1 | 03-07 | 3 | PLAT-02 | T-3-21 | `quality_signals` is a typed, counts-only field; an absent signal is `None`, never `{}`; `normalise_listing` stays pure | unit | `.venv/bin/python -m pytest -q tests/pipeline/test_injection_finding.py -x` | ❌ W0 | ⬜ pending |
| 07-T2 | 03-07 | 3 | §6.3 | T-3-01, T-3-05 | `instruction_like` / `patterns_matched` persist onto `listings.quality_signals_json`; a clean listing leaves it NULL; the payload carries no matched text | integration | `.venv/bin/python -m pytest -q tests/pipeline/test_injection_finding.py -x` | ❌ W0 | ⬜ pending |
| 07-T2 | 03-07 | 3 | §6.3 | T-3-23 | The PII/JSON-column allow-list is unchanged (no new blob); the queue assertions are unchanged | guard | `.venv/bin/python -m pytest -q tests/db/test_no_pii_columns.py tests/api/test_queue_links.py -x` | ✅ unchanged | ⬜ pending |
| 07-T3 | 03-07 | 3 | D-49 | T-3-22 | `_finish` persists `llm_calls`/`llm_tokens` only when supplied; `ranked_count` untouched; the pipeline still writes zero `llm_calls` rows | unit | `.venv/bin/python -m pytest -q tests/pipeline/test_finish_llm_counters.py tests/pipeline/test_filter_stage.py -x` | ❌ W0 (new) | ⬜ pending |


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
