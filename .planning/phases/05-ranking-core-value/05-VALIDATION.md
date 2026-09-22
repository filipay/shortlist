---
phase: "5"
slug: "ranking-core-value"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-22"
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest==9.1.1` + `pytest-asyncio==1.4.0` (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`addopts = "-m 'not live and not latex'"`, `pythonpath = ["."]`, `testpaths = ["tests"]`) |
| **Quick run command** | `.venv-host/bin/python -m pytest -q tests/domain tests/db tests/pipeline tests/api` |
| **Full suite command** | `.venv-host/bin/python -m pytest -q` |
| **Estimated runtime** | ~60 seconds (quick) / ~240 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `.venv-host/bin/python -m pytest -q tests/domain tests/db tests/pipeline tests/api`
- **After every plan wave:** Run `.venv-host/bin/python -m pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green (the `live` and `latex` lanes are collected-but-skipped by design, not failures)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Task IDs are assigned when the plans land; the requirement→evidence binding below is the contract.
The `Wave 0` column marks whether the named test file must be created before the task can run.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| — | — | — | RANK-01 | — | Factor set is exactly the six named keys; module is I/O-free | unit (pure) | `.venv-host/bin/python -m pytest -q tests/domain/test_rubric.py::test_factor_keys_are_the_six_named -x` | ❌ W0 | ⬜ pending |
| — | — | — | RANK-02 | — | Per-factor sub-scores persisted, never a bare total | integration (DB) | `.venv-host/bin/python -m pytest -q tests/db/test_score_repo.py::test_upsert_stores_factor_scores_json -x` | ❌ W0 | ⬜ pending |
| — | — | — | RANK-03 | — | Total computed in code from stored sub-scores × weights | unit (pure) | `.venv-host/bin/python -m pytest -q tests/domain/test_rubric.py::test_weighted_total_renormalises_present_factors -x` | ❌ W0 | ⬜ pending |
| — | — | — | RANK-04 | V11/L10 (cap correctness) | Weight change re-derives with zero new LLM calls | integration (API) | `.venv-host/bin/python -m pytest -q tests/api/test_ranking_weights.py::test_weight_change_writes_zero_llm_calls -x` | ❌ W0 | ⬜ pending |
| — | — | — | RANK-05 | — | Rationale grounded in stored evidence (CV fact IDs) | unit + integration | `.venv-host/bin/python -m pytest -q tests/pipeline/test_rank_stage.py::test_rationale_ids_are_cv_fact_ids -x` | ❌ W0 | ⬜ pending |
| — | — | — | RANK-06 | — | Requirement-by-requirement breakdown with named gaps rendered | integration (API) | `.venv-host/bin/python -m pytest -q tests/api/test_listing_detail.py::test_detail_shows_requirements_and_gaps -x` | ❌ W0 | ⬜ pending |
| — | — | — | RANK-07 | — | Re-scoring the same fixture twice yields identical sub-scores (stubbed backend) | unit | `.venv-host/bin/python -m pytest -q tests/pipeline/test_rank_stage.py::test_absolute_score_is_stable_across_runs -x` | ❌ W0 | ⬜ pending |
| — | — | — | RANK-08 | V11/L10 (unbounded spend) | Cap refuses **before** the call; refusal writes no score row | unit + integration | `.venv-host/bin/python -m pytest -q tests/pipeline/test_rank_caps.py::test_cap_refuses_before_the_call -x` | ❌ W0 | ⬜ pending |
| — | — | — | UI-01 | — | Queue defaults to score DESC, unranked last | integration (API) | `.venv-host/bin/python -m pytest -q tests/api/test_queue_ranked.py::test_default_order_is_score_desc_unranked_last -x` | ❌ W0 | ⬜ pending |
| — | — | — | UI-02 | — | Detail page renders breakdown + rationale | integration (API) | `.venv-host/bin/python -m pytest -q tests/api/test_listing_detail.py::test_detail_page_renders_breakdown -x` | ❌ W0 | ⬜ pending |
| — | — | — | UI-03 | — | Weights editor saves and re-renders; criteria editor untouched | integration (API) | `.venv-host/bin/python -m pytest -q tests/api/test_ranking_weights.py::test_weights_form_saves_and_rerenders -x` | ❌ W0 | ⬜ pending |
| — | — | — | SC-2 | — | One call per listing (no sibling listings in any prompt) | unit | `.venv-host/bin/python -m pytest -q tests/pipeline/test_rank_stage.py::test_prompt_contains_exactly_one_listing -x` | ❌ W0 | ⬜ pending |
| — | — | — | SC-5 | V11/L10 | Cap enforced before the call, traced from the task | integration | `.venv-host/bin/python -m pytest -q tests/pipeline/test_rank_caps.py -x` | ❌ W0 | ⬜ pending |
| — | — | — | D-94 | — | No `cv.yaml` / disabled / unreachable ⇒ zero LLM calls, run completes | integration | `.venv-host/bin/python -m pytest -q tests/pipeline/test_rank_optional.py -x` | ❌ W0 | ⬜ pending |
| — | — | — | D-95 | — | Per-listing failure writes an `llm_calls` row, no `scores` row, loop continues | integration | `.venv-host/bin/python -m pytest -q tests/pipeline/test_rank_stage.py::test_failed_listing_is_isolated -x` | ❌ W0 | ⬜ pending |
| — | — | — | D-102 | — | Updated zero-LLM guards reflect the D-94 posture | regression | `.venv-host/bin/python -m pytest -q tests/pipeline/test_finish_llm_counters.py tests/pipeline/test_filter_stage.py -q` | ✅ (must be edited) | ⬜ pending |
| — | — | — | PLAT-03 | V4 (auth seam) | New `GET /listings/{id}` declares `current_user` | guard | `.venv-host/bin/python -m pytest -q tests/test_auth_seam.py -q` | ✅ (add path to `EXPECTED_SEAM_ROUTES`) | ⬜ pending |
| — | — | — | UI-07 | — | New templates' classes all have CSS rules; no CDN | guard | `.venv-host/bin/python -m pytest -q tests/test_stylesheet_coverage.py tests/test_no_cdn.py -q` | ✅ (add rules / exemptions) | ⬜ pending |
| — | — | — | D-24 | — | `app/domain/rubric.py` imports no I/O | guard | `.venv-host/bin/python -m pytest -q tests/test_import_discipline.py -q` | ✅ | ⬜ pending |
| — | — | — | §6.5 | — | Nothing outside `app/llm` imports `httpx` | guard | `.venv-host/bin/python -m pytest -q tests/test_import_discipline.py::test_the_llm_call_path_imports_no_httpx -q` | ✅ | ⬜ pending |
| — | — | — | PLAT-04 | — | New cap fields are `Settings` fields; literals absent from `app/pipeline` | guard | `.venv-host/bin/python -m pytest -q tests/test_config.py -q` | ✅ (edit the two tuples) | ⬜ pending |
| — | — | — | D-12/M9 | — | Every score row records provider/model/agent; every call records server_version | integration | `.venv-host/bin/python -m pytest -q tests/db/test_score_repo.py::test_score_records_model_identity -x` | ❌ W0 | ⬜ pending |
| — | — | — | — | — | Schema-violation fixture degrades/classifies without crashing | unit | `.venv-host/bin/python -m pytest -q tests/llm/ -q` (existing salvage lane) | ✅ | ⬜ pending |
| — | — | — | — | — | No new migration, or the migration contract updated | guard | `.venv-host/bin/python -m pytest -q tests/db/test_migration_contract.py -q` | ✅ (edit if a migration lands) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/domain/test_rubric.py` — factor set, purity, `weighted_total` re-normalisation + empty-denominator guard, tier boundaries
- [ ] `tests/db/test_score_repo.py` — upsert idempotency (including the NULL `criteria_version` trap), latest-per-listing selection, model identity recorded
- [ ] `tests/pipeline/test_rank_stage.py` — one-listing prompt, `parts` only, stubbed backend, per-listing isolation, stability across runs
- [ ] `tests/pipeline/test_rank_caps.py` — per-run and rolling-24h refusal *before* the call; graceful stop; `ranked_count`
- [ ] `tests/pipeline/test_rank_optional.py` — D-94 skip paths write zero `llm_calls`
- [ ] `tests/api/test_queue_ranked.py`, `tests/api/test_listing_detail.py`, `tests/api/test_ranking_weights.py` — UI-01/02/03
- [ ] **Edit** `tests/pipeline/test_finish_llm_counters.py` and `tests/pipeline/test_filter_stage.py:197` (D-102)
- [ ] **Edit** `tests/test_config.py` (`REQUIRED_SETTINGS_FIELDS`, `LIMIT_FIELDS`) and add the new keys to `compose.yml` / `.env.example`
- [ ] **Edit** `tests/test_auth_seam.py` `EXPECTED_SEAM_ROUTES` and `static/vendor/app.css` for the new route/templates

*Existing infrastructure covers the shared fixtures: `session_factory`, `client`, `migrated_db` and `OfflineLLMBackend` all exist.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A real `opencode serve` round-trip returns a schema-valid ranking for a real listing | RANK-01 | Requires the live opencode server and a real model; excluded from the default lane by `-m 'not live'` | `.venv-host/bin/python -m pytest -q -m live tests/llm -x` with `opencode serve` running, then confirm one `scores` row landed |
| Rationale reads as genuinely grounded prose rather than a keyword restatement | RANK-05 | Quality judgment, not a predicate | Open `GET /listings/{id}` for 3 scored listings and confirm each rationale cites stored evidence, not listing boilerplate |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
