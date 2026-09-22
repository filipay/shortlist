---
phase: "5"
slug: "ranking-core-value"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: false
wave_0_complete: true
created: "2026-09-22"
validated: "2026-09-22"
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Audit note:** the plan-phase seed referenced `.venv-host/bin/python`, which is
> broken in this environment (Python 3.14 with a missing `pydantic_core._pydantic_core`
> native module). Every command below uses the working `.venv/bin/python`, matching the
> harness's declared test command.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest==9.1.1` + `pytest-asyncio==1.4.0` (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`addopts = "-m 'not live and not latex'"`, `pythonpath = ["."]`, `testpaths = ["tests"]`) |
| **Quick run command** | `.venv/bin/python -m pytest -q tests/domain tests/db tests/pipeline tests/api` |
| **Full suite command** | `.venv/bin/python -m pytest -q` |
| **Estimated runtime** | ~40–60 seconds (quick) / ~370 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest -q tests/domain tests/db tests/pipeline tests/api`
- **After every plan wave:** Run `.venv/bin/python -m pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green (the `live` and `latex` lanes are collected-but-skipped by design, not failures)
- **Max feedback latency:** 60 seconds

**Last full-suite result (2026-09-22):** `1042 passed, 4 xfailed, 14 deselected`.

---

## Per-Task Verification Map

The phase executed as four wave-ordered plans (waves 1–4). Task IDs below are
`{plan}-T{n}` (the plans carry no explicit task IDs). The requirement→evidence binding
is the contract; the `Wave 0` column records whether the named file had to be created
before the task could run.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-T1 | 01 | 1 | RANK-01 | — | Factor set is exactly the six named keys; module is I/O-free | unit (pure) | `.venv/bin/python -m pytest -q tests/domain/test_rubric.py::test_the_factor_set_is_exactly_the_six_in_order tests/domain/test_rubric.py::test_the_module_imports_no_io_module_and_not_settings -x` | ✅ | ✅ green |
| 05-01-T1 | 01 | 1 | RANK-03 | — | Total computed in code from stored sub-scores × weights; schema exposes no total | unit (pure) | `.venv/bin/python -m pytest -q tests/domain/test_rubric.py -k weighted_total -x` | ✅ | ✅ green |
| 05-01-T2 | 01 | 1 | RANK-02 | — | Per-factor sub-scores persisted, never a bare total; `0.0` ≠ absent | integration (DB) | `.venv/bin/python -m pytest -q tests/db/test_score_repo.py::test_one_upsert_stores_the_per_factor_entries_and_never_a_bare_total -x` | ✅ | ✅ green |
| 05-01-T2 | 01 | 1 | D-12/M9 | — | Every score row records provider/model; every call records server_version | integration (DB) | `.venv/bin/python -m pytest -q tests/db/test_score_repo.py::test_the_row_records_provider_and_model_identity -x` | ✅ | ✅ green |
| 05-01-T3 | 01 | 1 | RANK-05 | T-05-01 | Rationale/evidence ids grounded in stored CV fact IDs; fabricated id dropped | unit + integration | `.venv/bin/python -m pytest -q tests/pipeline/test_rank_stage.py::test_rationale_ids_are_cv_fact_ids -x` | ✅ | ✅ green |
| 05-01-T3 | 01 | 1 | RANK-07 | — | Re-scoring the same fixture twice yields identical sub-scores (stubbed backend); one listing per prompt | unit | `.venv/bin/python -m pytest -q tests/pipeline/test_rank_stage.py::test_absolute_score_is_stable_across_runs tests/pipeline/test_rank_stage.py::test_prompt_contains_exactly_one_listing -x` | ✅ | ✅ green |
| 05-01-T3 | 01 | 1 | RANK-06 | — | Requirement-by-requirement breakdown with named gaps rendered | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_listing_detail.py::test_detail_shows_requirements_and_gaps -x` | ✅ | ✅ green |
| 05-01-T3 | 01 | 1 | D-95 | — | Per-listing failure isolated; loop continues; audit row written | integration | `.venv/bin/python -m pytest -q tests/pipeline/test_rank_stage.py::test_failed_listing_is_isolated -x` | ✅ | ✅ green |
| 05-02-T1 | 02 | 2 | PLAT-04 | — | New cap fields are `Settings` fields; literals absent from `app/pipeline` | guard | `.venv/bin/python -m pytest -q tests/test_config.py -q` | ✅ | ✅ green |
| 05-02-T2 | 02 | 2 | RANK-08 | V11/L10 | Cap refuses **before** the call; refusal writes one audit row, no score row | unit + integration | `.venv/bin/python -m pytest -q tests/pipeline/test_rank_caps.py::test_cap_refuses_before_the_call -x` | ✅ | ✅ green |
| 05-02-T2 | 02 | 2 | RANK-08 | V11/L10 | Rolling-24h ceiling enforced from the `llm_calls` ledger | unit | `.venv/bin/python -m pytest -q tests/pipeline/test_rank_caps.py::test_rolling_24h_cap_is_enforced -x` | ✅ | ✅ green |
| 05-02-T3 | 02 | 2 | D-94 | — | Disabled / no fact store / unreadable fact store ⇒ zero LLM calls, run `done` | integration | `.venv/bin/python -m pytest -q tests/pipeline/test_rank_optional.py -x` | ✅ | ⚠️ partial (see E-01) |
| 05-02-T3 | 02 | 2 | D-102 | — | Retired zero-LLM guards assert the D-94 posture and the entry point was reached | regression | `.venv/bin/python -m pytest -q tests/pipeline/test_finish_llm_counters.py tests/pipeline/test_filter_stage.py -q` | ✅ | ✅ green |
| 05-03-T1 | 03 | 3 | PLAT-03 | V4 (auth seam) | New `GET /listings/{id}` declares `current_user` | guard | `.venv/bin/python -m pytest -q tests/test_auth_seam.py -q` | ✅ | ✅ green |
| 05-03-T2 | 03 | 3 | UI-02 | — | Detail page renders breakdown + rationale; unscored = not-yet-ranked, never `0.0` | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_listing_detail.py::test_detail_page_renders_breakdown tests/api/test_listing_detail.py::test_unscored_listing_renders_not_yet_ranked -x` | ✅ | ✅ green |
| 05-03-T3 | 03 | 3 | UI-02 | T-05-12 | Untrusted title + stored model prose escaped by autoescape only | guard | `.venv/bin/python -m pytest -q tests/api/test_listing_detail.py::test_detail_escapes_untrusted_title_and_rationale -x` | ✅ | ✅ green |
| 05-04-T1 | 04 | 4 | UI-01 | — | Queue defaults to score DESC, unranked last; deterministic tie-break | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_queue_ranked.py::test_default_order_is_score_desc_unranked_last -x` | ✅ | ✅ green |
| 05-04-T1 | 04 | 4 | UI-01/D-98 | T-05-19 | `?min_score=` keeps unscored visible; junk degrades to no threshold | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_queue_ranked.py -k "min_score" -x` | ✅ | ⚠️ partial (see E-03) |
| 05-04-T2 | 04 | 4 | UI-01 | — | Unranked badge; "Ranked X of Y" strip degrades rather than 500-ing | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_queue_ranked.py::test_unranked_row_renders_the_badge -x` | ✅ | ⚠️ partial (see E-04) |
| 05-04-T3 | 04 | 4 | RANK-04 | — | Weight change re-derives with zero new LLM calls | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_ranking_weights.py::test_weight_change_writes_zero_llm_calls -x` | ✅ | ✅ green |
| 05-04-T3 | 04 | 4 | UI-03 | — | Weights editor saves and re-renders; criteria editor untouched | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_ranking_weights.py::test_weights_form_saves_and_rerenders tests/api/test_ranking_weights.py::test_settings_page_still_renders_existing_cards -x` | ✅ | ✅ green |
| — | — | — | UI-07 | — | New templates' classes all have CSS rules; no CDN | guard | `.venv/bin/python -m pytest -q tests/test_stylesheet_coverage.py tests/test_no_cdn.py -q` | ✅ | ✅ green |
| — | — | — | D-24 | — | `app/domain/rubric.py` imports no I/O | guard | `.venv/bin/python -m pytest -q tests/test_import_discipline.py -q` | ✅ | ✅ green |
| — | — | — | §6.5 | — | Nothing outside `app/llm` imports `httpx` | guard | `.venv/bin/python -m pytest -q tests/test_import_discipline.py::test_the_llm_call_path_imports_no_httpx -q` | ✅ | ✅ green |
| — | — | — | — | — | Schema-violation fixture degrades/classifies without crashing | unit | `.venv/bin/python -m pytest -q tests/llm/test_salvage.py -q` | ✅ | ✅ green |
| — | — | — | — | — | No new migration beyond head `0004`; ORM matches migrated schema | guard | `.venv/bin/python -m pytest -q tests/db/test_migration_contract.py tests/db/test_orm_drift.py -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky/partial*

---

## Wave 0 Requirements

All Wave 0 artifacts landed during execution — every referenced file exists and runs.

- [x] `tests/domain/test_rubric.py` — factor set, purity, `weighted_total` re-normalisation + empty-denominator guard, tier boundaries
- [x] `tests/db/test_score_repo.py` — upsert idempotency (including the NULL `criteria_version` trap), latest-per-listing selection, model identity recorded
- [x] `tests/pipeline/test_rank_stage.py` — one-listing prompt, `parts` only, stubbed backend, per-listing isolation, stability across runs
- [x] `tests/pipeline/test_rank_caps.py` — per-run and rolling-24h refusal *before* the call; graceful stop; `ranked_count`
- [x] `tests/pipeline/test_rank_optional.py` — D-94 skip paths write zero `llm_calls`
- [x] `tests/api/test_queue_ranked.py`, `tests/api/test_listing_detail.py`, `tests/api/test_ranking_weights.py` — UI-01/02/03
- [x] **Edited** `tests/pipeline/test_finish_llm_counters.py` and `tests/pipeline/test_filter_stage.py` (D-102)
- [x] **Edited** `tests/test_config.py` (`REQUIRED_SETTINGS_FIELDS`, `LIMIT_FIELDS`) and added the new keys to `compose.yml` / `.env.example`
- [x] **Edited** `tests/test_auth_seam.py` `EXPECTED_SEAM_ROUTES` and `static/vendor/app.css` for the new route/templates

*Existing infrastructure covers the shared fixtures: `session_factory`, `client`, `migrated_db` and `OfflineLLMBackend` all exist.*

---

## Adversarial Probes (added 2026-09-22)

The audit ran four adversarial behavioural probes against requirement-level behaviours
that the phase's own tests do **not** cover. All four reproduce real gaps; they are
committed as `xfail(strict=True)` sentinels so the default lane stays green while the
gap is open, and a fix turns the expected failure into an XPASS that fails the suite and
forces the sentinel's removal. Run uncensored with `--runxfail` to see the raw failure.

| Probe file | Test | Requirement | Observed (actual) | Expected |
|------------|------|-------------|-------------------|----------|
| `tests/pipeline/test_rank_adversarial.py` | `test_unreadable_non_utf8_fact_store_is_a_clean_skip` | RANK-08 / D-94 | `UnicodeDecodeError` escapes `run_ranking` (guard catches only `CvFactStoreError`/`OSError`) | clean skip: zero `llm_calls`, zero `scores`, no raise |
| `tests/pipeline/test_rank_adversarial.py` | `test_read_weights_rejects_a_negative_stored_weight` | RANK-03 / WR-05 | `read_weights` returns `skills = -5.0` verbatim | degrade to `DEFAULT_WEIGHTS` (finite, `>= 0`) |
| `tests/api/test_queue_ranking_adversarial.py` | `test_nan_min_score_degrades_to_no_threshold` | UI-01 / T-05-19 | `?min_score=nan` hides the scored listing | nan is junk → degrade to `None` |
| `tests/api/test_queue_ranking_adversarial.py` | `test_ranking_strip_denominator_is_the_runs_own_candidates` | UI-01 / CR-01 | strip renders `Ranked 5 of 2` (numerator from the run, denominator from the page) | both from the run's own candidate population (`Ranked 5 of 30`) |

---

## Escalated Gaps (BLOCKER — implementation unmet, owner: developer)

| ID | Requirement | Source | Gap | Suggested fix (no implementation changed here) |
|----|-------------|--------|-----|-------------------------------------------------|
| E-01 | RANK-08 / D-94 | 05-REVIEW WR-02 | A non-UTF-8 `cv.yaml` ("unreadable") raises `UnicodeDecodeError` out of the detached ranking task instead of the documented clean skip; `runs.ranked_count` stays NULL and asyncio logs an unretrieved exception | Widen the guard to `except (CvFactStoreError, OSError, ValueError)` or have `load_facts` wrap the read and re-raise as `CvFactStoreError` |
| E-02 | RANK-03 | 05-REVIEW WR-05 | `read_weights` returns a negative stored weight verbatim; a hand-edited/legacy document can drive the read-time total out of range or to `None` and silently un-rank everything | Clamp/drop non-finite or negative values on read, mirroring `write_weights` |
| E-03 | UI-01 / T-05-19 | 05-REVIEW WR-03 | `?min_score=nan` (or `inf`) passes `float()` and `total >= nan` is False for every scored row, so a junk threshold silently hides every scored listing and round-trips into paging URLs | Add the `math.isfinite` gate already used by the weights parser |
| E-04 | UI-01 / RANK-08 | 05-REVIEW CR-01 | The "Ranked X of Y" strip draws its numerator from `runs.ranked_count` and its denominator from the current page total — two different populations — so it routinely reads "Ranked 30 of 5" | Use the run's own `reason_counts_json["survivors"]` as the denominator (expose it on `RunSummary` or read the column in `_ranking_strip`) |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A real `opencode serve` round-trip returns a schema-valid ranking for a real listing | RANK-01 | Requires the live opencode server and a real model; excluded from the default lane by `-m 'not live'` | `.venv/bin/python -m pytest -q -m live tests/llm -x` with `opencode serve` running, then confirm one `scores` row landed |
| Rationale reads as genuinely grounded prose rather than a keyword restatement | RANK-05 | Quality judgment, not a predicate | Open `GET /listings/{id}` for 3 scored listings and confirm each rationale cites stored evidence, not listing boilerplate |
| Fit-breakdown layout/grouping (factor table then requirement list) is the right presentation | RANK-06 | Presentation judgment; the requirement does not state grouping | Open a scored listing and confirm the factor table + requirement list read coherently |
| Where the weights editor lives (settings page) and how invalid input presents (inline banner + 400) | RANK-04 / UI-03 | Presentation judgment; the requirement does not state placement | Open `/settings`, change a weight, submit; confirm re-derivation and the error presentation |
| Live-model score stability tolerance across repeated runs | RANK-07 | The stubbed lane proves determinism; real models are not bit-stable | Run the live lane twice against the same listing and compare `factor_scores_json` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter — **not set: 4 escalated gaps E-01..E-04**

**Approval:** validated 2026-09-22 — PARTIAL (all 11 requirements green; 4 adversarial
gaps escalated to the developer)

---

## Validation Audit 2026-09-22

| Metric | Count |
|--------|-------|
| Requirements audited | 11 (RANK-01..08, UI-01..03) |
| Requirements covered by green automated tests | 11 |
| Seeded map rows audited | 21 (18 ✅ green, 3 ⚠️ partial — E-01, E-03, E-04) |
| Named/adjacent guard suites green | 15 files / 142 tests |
| Adversarial gap tests written | 4 |
| Gaps found (adversarial) | 4 |
| Resolved | 0 (all 4 are implementation defects; tests kept as `xfail(strict=True)` sentinels) |
| Escalated (BLOCKER) | 4 (E-01..E-04) |
| Manual-only | 5 |
| Full suite | `1042 passed, 4 xfailed, 14 deselected` |

**Full-suite command:** `.venv/bin/python -m pytest -q`
