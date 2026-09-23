---
phase: "5"
slug: "ranking-core-value"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-09-22"
validated: "2026-09-23"
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

**Last full-suite result (2026-09-22, post gap-closure):** `1046 passed, 14 deselected, 2 xfailed`.

**Last full-suite result (2026-09-23, after the round-2 gap-closure plans 05-07…05-10):** `1065 passed, 14 deselected, 2 xfailed`.

**Last full-suite result (2026-09-23, after the round-3 gap-closure plan 05-11 + this re-audit):** `1085 passed, 14 deselected, 2 xfailed`.

---

## Per-Task Verification Map

The phase executed as eleven plans: the four wave-ordered delivery plans (waves 1–4), the
first gap-closure pair (05-05, 05-06, wave 5), the round-2 gap-closure plans
(05-07 and 05-08 in wave 1; 05-09 and 05-10 in wave 2), and the round-3 gap-closure plan
05-11 (wave 1). Task IDs below are `{plan}-T{n}`
(the plans carry no explicit task IDs). The requirement→evidence binding is the contract;
the `Wave 0` column records whether the named file had to be created before the task could
run. Rows for 05-05/05-06 were added by the first re-audit; rows for 05-07…05-10 by the
2026-09-23 round-2 re-audit; rows for 05-11 by the 2026-09-23 round-3 re-audit.

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
| 05-02-T3 | 02 | 2 | D-94 / RANK-08 | — | Disabled / no fact store / unreadable (invalid-YAML) / non-UTF-8 fact store ⇒ zero LLM calls, run `done` | integration | `.venv/bin/python -m pytest -q tests/pipeline/test_rank_optional.py -x` | ✅ | ✅ green (E-01 closed by 05-06) |
| 05-02-T3 | 02 | 2 | D-102 | — | Retired zero-LLM guards assert the D-94 posture and the entry point was reached | regression | `.venv/bin/python -m pytest -q tests/pipeline/test_finish_llm_counters.py tests/pipeline/test_filter_stage.py -q` | ✅ | ✅ green |
| 05-03-T1 | 03 | 3 | PLAT-03 | V4 (auth seam) | New `GET /listings/{id}` declares `current_user` | guard | `.venv/bin/python -m pytest -q tests/test_auth_seam.py -q` | ✅ | ✅ green |
| 05-03-T2 | 03 | 3 | UI-02 | — | Detail page renders breakdown + rationale; unscored = not-yet-ranked, never `0.0` | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_listing_detail.py::test_detail_page_renders_breakdown tests/api/test_listing_detail.py::test_unscored_listing_renders_not_yet_ranked -x` | ✅ | ✅ green |
| 05-03-T3 | 03 | 3 | UI-02 | T-05-12 | Untrusted title + stored model prose escaped by autoescape only | guard | `.venv/bin/python -m pytest -q tests/api/test_listing_detail.py::test_detail_escapes_untrusted_title_and_rationale -x` | ✅ | ✅ green |
| 05-04-T1 | 04 | 4 | UI-01 | — | Queue defaults to score DESC, unranked last; deterministic tie-break | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_queue_ranked.py::test_default_order_is_score_desc_unranked_last -x` | ✅ | ✅ green |
| 05-04-T1 | 04 | 4 | UI-01/D-98 | T-05-19 | `?min_score=` keeps unscored visible; junk degrades to no threshold | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_queue_ranked.py -k "min_score" -x` | ✅ | ✅ green (core); non-finite edge WR-03 accepted |
| 05-04-T2 | 04 | 4 | UI-01 | — | Unranked badge; "Ranked X of Y" strip degrades rather than 500-ing | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_queue_ranked.py::test_unranked_row_renders_the_badge -x` | ✅ | ✅ green |
| 05-05-T1/T2 | 05 | 5 | UI-01 | — | Both strip numbers come from the run's own population; an absent candidate count renders the numerator alone, never a fabricated denominator | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_queue_ranked.py::test_ranking_strip_reports_the_runs_own_candidate_count tests/api/test_queue_ranked.py::test_ranking_strip_without_candidate_count_renders_no_ratio -x` | ✅ | ✅ green (E-04 closed by 05-05) |
| 05-06-T1 | 06 | 5 | RANK-08 | — | A non-UTF-8 file is one path-qualified `CvFactStoreError` at the fact-store boundary, decode failure preserved as cause | unit | `.venv/bin/python -m pytest -q tests/cv/test_factstore.py::test_non_utf8_bytes_raise_the_path_qualified_fact_store_error -x` | ✅ | ✅ green (E-01 closed by 05-06) |
| 05-06-T2 | 06 | 5 | RANK-08 | — | Non-UTF-8 fact store ⇒ detached task returns cleanly: zero `llm_calls`, zero `scores`, run `done`, `pipeline.rank_skipped` with `reason=fact_store_absent` | integration | `.venv/bin/python -m pytest -q tests/pipeline/test_rank_optional.py::test_non_utf8_fact_store_writes_nothing_and_the_run_is_done -x` | ✅ | ✅ green (E-01 closed by 05-06) |
| 05-07-T1 | 07 | 1 | UI-01 | T-05-30 | A non-positive candidate count is not a denominator: the strip degrades to the numerator alone, and the read model returns no count | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_queue_ranked.py::test_ranking_strip_with_zero_candidate_count_renders_no_ratio tests/api/test_queue_ranked.py::test_run_summary_has_no_candidate_count_for_a_non_positive_survivors -x` | ✅ | ✅ green |
| 05-08-T1/T2 | 08 | 1 | UI-01 / RANK-08 | T-05-34 | The ranking outcome is persisted on the run (`reason_counts_json['ranking']`) and rendered: running / skipped + reason / nothing-to-rank / not-completed, with a persisted skip winning over a live task | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_queue_ranked.py -k "ranking_strip" -x` | ✅ | ✅ green |
| 05-09-T1 | 09 | 2 | UI-02 | T-05-39 | The unscored detail page names the last run's real ranking state (skipped + reason / running / not-completed) and the CV fact-store path, never a hedge | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_listing_detail.py -k "unscored" -x` | ✅ | ✅ green |
| 05-10-T1/T2/T3 | 10 | 2 | RANK-08 / UI-01 | T-05-43 | The CV fact-store prerequisite is disclosed on `/settings`, the queue status line and the `/health` `cv` object; only the exception class name crosses the boundary | unit + integration | `.venv/bin/python -m pytest -q tests/api/test_settings_page.py tests/api/test_health.py tests/cv/test_factstore.py -q` | ✅ | ✅ green |
| 05-11-T1 | 11 | 1 | UI-01 | — | The four derived page accessors are total: a degenerate `QueuePage` (limit 0/negative, total 0, in-page offset) never raises `ZeroDivisionError`, `page_count ≥ 1`, `page_index ≥ 1`, `prev_offset ≥ 0` | unit (pure) | `.venv/bin/python -m pytest -q tests/db/test_queue_page.py -q` | ✅ | ✅ green |
| 05-11-T2 | 11 | 1 | UI-01 | T-05-40 | The shared fragment renders `Page X of Y (N per page)` on a **single-page** non-empty queue (the plan's explicit "even when there is only one page" case) with no Previous and no Next | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_queue_excluded.py::test_the_position_line_renders_on_a_single_page_queue -x` | ✅ | ✅ green |
| 05-11-T2 | 11 | 1 | UI-01 | T-05-40 | Both pager controls carry the CURRENT predicate set (a non-default `sort` and a `q` ride along on Previous and Next, not just the `excluded` toggle) | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_queue_excluded.py::test_the_pager_carries_the_current_predicate_set -x` | ✅ | ✅ green |
| 05-11-T2 | 11 | 1 | UI-01 | T-05-39 | The predicate-reset rule covers every control in the filter form: no `offset` appears in `#queue-filters`, so a filter/sort/threshold change restarts at page 1 | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_queue_excluded.py::test_a_sort_or_threshold_change_emits_no_offset -x` | ✅ | ✅ green |
| 05-11-T3 | 11 | 1 | UI-01 | T-05-39 | First page has no Previous, last page has no Next; `?limit=1` is ignored and the position line shows the server-fixed page size; the full page renders the same pager | integration (API) | `.venv/bin/python -m pytest -q tests/api/test_queue_excluded.py -q` | ✅ | ✅ green |
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

## Adversarial Probes (updated 2026-09-22, re-audit)

The original audit ran four adversarial behavioural probes against requirement-level
behaviours the phase's own tests did **not** cover. They were committed as
`xfail(strict=True)` sentinels so the default lane stayed green while the gap was open.
Two were closed by the gap-closure plans and their sentinels retired; two remain open and
are accepted by design (see Known Accepted Limitations below). Run uncensored with
`--runxfail` to see the raw failure.

| Probe file | Test | Requirement | Status |
|------------|------|-------------|--------|
| `tests/pipeline/test_rank_adversarial.py` | `test_unreadable_non_utf8_fact_store_is_a_clean_skip` | RANK-08 / D-94 | ✅ **retired by 05-06** — coverage re-homed as `tests/cv/test_factstore.py::test_non_utf8_bytes_raise_the_path_qualified_fact_store_error` + `tests/pipeline/test_rank_optional.py::test_non_utf8_fact_store_writes_nothing_and_the_run_is_done` |
| `tests/api/test_queue_ranking_adversarial.py` | `test_ranking_strip_denominator_is_the_runs_own_candidates` | UI-01 / CR-01 | ✅ **retired by 05-05** — coverage re-homed as `tests/api/test_queue_ranked.py::test_ranking_strip_reports_the_runs_own_candidate_count` + `...::test_ranking_strip_without_candidate_count_renders_no_ratio` |
| `tests/pipeline/test_rank_adversarial.py` | `test_read_weights_rejects_a_negative_stored_weight` | RANK-03 / WR-05 | ⚠️ **open, accepted by design** — strict-xfail sentinel retained (not a coverage gap) |
| `tests/api/test_queue_ranking_adversarial.py` | `test_nan_min_score_degrades_to_no_threshold` | UI-01 / T-05-19 | ⚠️ **open, accepted by design** — strict-xfail sentinel retained (not a coverage gap) |

---

## Gap-Closure Outcomes

| ID | Requirement | Source | Gap | Outcome |
|----|-------------|--------|-----|---------|
| E-01 | RANK-08 / D-94 | 05-REVIEW WR-02 | A non-UTF-8 `cv.yaml` ("unreadable") raised `UnicodeDecodeError` out of the detached ranking task instead of the documented clean skip | ✅ **Resolved** by plan 05-06 (`8c6754c`, `60e7f19`): `load_facts` catches `(OSError, UnicodeError)` and re-raises a path-qualified `CvFactStoreError`; a unit test pins the boundary contract and an end-to-end test pins the detached task's clean skip (`done`, zero `llm_calls`, zero `scores`, `pipeline.rank_skipped` reason `fact_store_absent`). |
| E-04 | UI-01 / RANK-08 | 05-REVIEW CR-01 | The "Ranked X of Y" strip drew its numerator from `runs.ranked_count` and its denominator from the current page total — two different populations — so it read "Ranked 30 of 5" | ✅ **Resolved** by plan 05-05 (`d5ac5c2`, `f894b4c`): `RunSummary.candidate_count` reads the run's own `reason_counts_json['survivors']`; `_ranking_strip` no longer takes a request-derived denominator and the template degrades to `Ranked N` alone. Two first-class regression tests pin both branches. |
| E-02 | RANK-03 | 05-REVIEW WR-05 | `read_weights` returns a negative stored weight verbatim (`_as_float` rejects only non-finite values) | ⚠️ **Open — accepted by design.** Strict-xfail sentinel retained; RANK-03's requirement-level behaviour is green. |
| E-03 | UI-01 / T-05-19 | 05-REVIEW WR-03 | `?min_score=nan` passes `float()` and `total >= nan` is False, so a junk threshold silently hides every scored row | ⚠️ **Open — accepted by design.** Strict-xfail sentinel retained; UI-01/T-05-19's requirement-level behaviour is green. |
| G-05-3 | UI-01 | UAT ad-hoc finding | The queue's paging was forward-only and stateless: "Load more" did an `innerHTML` replace (destroying on-screen rows), no back control existed, and the UI showed only the grand total — never the page index, page count or page size | ✅ **Resolved** by plan 05-11 (`71c4e3b`, `d8e5893`, `c083082`): `QueuePage` derives `has_prev`/`prev_offset`/`page_index`/`page_count`; the shared fragment renders Previous / `Page X of Y (N per page)` / Next through the existing `GET /queue/list` swap; no new route, state, history integration or JS. |

### Known Accepted Limitations (tracked by strict-xfail sentinels — NOT coverage gaps)

| ID | Requirement | Sentinel | Effect while open |
|----|-------------|----------|-------------------|
| WR-05 | RANK-03 | `tests/pipeline/test_rank_adversarial.py::test_read_weights_rejects_a_negative_stored_weight` | A hand-edited/legacy `ranking_config` row carrying a finite negative weight is returned verbatim; the read-time total can fall out of range. `write_weights` still rejects negative input at the storage boundary. |
| WR-03 | UI-01 / T-05-19 | `tests/api/test_queue_ranking_adversarial.py::test_nan_min_score_degrades_to_no_threshold` | `?min_score=nan` (or `inf`) passes `float()` and hides every scored listing. Ordinary junk (`abc`) degrades correctly. |

Both are deliberate and separately tracked. Each turns into an XPASS (suite failure) the
moment the underlying behaviour is fixed, forcing the sentinel's removal. Neither leaves
a requirement without green automated verification.

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
- [x] `nyquist_compliant: true` set in frontmatter — all 11 in-scope requirements have green automated verification

**Approval:** validated 2026-09-22 — COMPLIANT. All 11 requirements green; the two
former BLOCKER gaps E-01 and E-04 are closed by plans 05-06 and 05-05; WR-03/WR-05 are
accepted-by-design limitations tracked by strict-xfail sentinels, not coverage gaps.
Re-verified 2026-09-23 after the round-2 gap-closure plans 05-07…05-10 — still COMPLIANT,
still 0 coverage gaps.
Re-verified 2026-09-23 after the round-3 gap-closure plan 05-11 (G-05-3) — still
COMPLIANT. Four coverage gaps in the 05-11 delta were found and filled with 17 new tests
(including the accessor-totality suite the 05-11 SUMMARY had wrongly attributed to
`tests/db/test_queue_state.py`); 0 BLOCKERs, 0 escalations.

---

## Validation Audit 2026-09-22

| Metric | Count |
|--------|-------|
| Requirements audited | 11 (RANK-01..08, UI-01..03) |
| Requirements covered by green automated tests | 11 |
| Map rows audited | 24 (23 ✅ green, 1 ✅ green core with accepted WR-03 edge) |
| Named/adjacent guard suites green | 15 files / 142 tests |
| Adversarial gap tests written | 4 |
| Gaps found (adversarial) | 4 |
| Resolved by gap-closure plans | 2 (E-01 by 05-06, E-04 by 05-05) |
| Accepted by design (strict-xfail, not coverage gaps) | 2 (WR-05/RANK-03, WR-03/UI-01) |
| Manual-only | 5 |
| Full suite (post gap-closure) | `1046 passed, 14 deselected, 2 xfailed` |

### Re-Audit 2026-09-22 (after plans 05-05 and 05-06)

| Metric | Count |
|--------|-------|
| New first-class tests verified green | 4 |
| Retired strict-xfail sentinels | 2 (WR-02 → 05-06; CR-01 → 05-05) |
| Remaining strict-xfail sentinels | 2 (WR-05, WR-03 — accepted by design) |
| XPASS observed | 0 |
| Coverage gaps remaining | 0 |
| Nyquist verdict | ✅ compliant (`nyquist_compliant: true`) |

**Evidence verified on HEAD** (`8f82b5b`): `.venv/bin/python -m pytest -q` → `1046 passed,
14 deselected, 2 xfailed`. Targeted re-run of the four new tests plus both sentinel files
→ `4 passed, 2 xfailed`.

**Full-suite command:** `.venv/bin/python -m pytest -q`

---

## Round-2 Validation Audit 2026-09-23 (after plans 05-07…05-10)

| Metric | Count |
|--------|-------|
| Requirements audited | 11 (RANK-01..08, UI-01..03) — unchanged |
| New map rows added | 4 (05-07, 05-08, 05-09, 05-10) |
| New first-class tests verified green | 18 (05-07: 2, 05-08: 5, 05-09: 3, 05-10: 8) |
| Coverage gaps found | 0 |
| Retired strict-xfail sentinels | 0 |
| Remaining strict-xfail sentinels | 2 (WR-05, WR-03 — accepted by design) |
| Nyquist verdict | ✅ compliant (`nyquist_compliant: true`) |

**Evidence verified on HEAD** (after `7df8af4`): `.venv/bin/python -m pytest -q` → `1065 passed,
14 deselected, 2 xfailed`. The four round-2 plans added 18 first-class tests across
`tests/api/test_queue_ranked.py`, `tests/api/test_listing_detail.py`,
`tests/api/test_settings_page.py`, `tests/api/test_health.py` and `tests/cv/test_factstore.py`;
no requirement was left without green automated verification, and no new requirement ID was
introduced (the plans address existing UI-01/UI-02/RANK-08 gaps).

---

## Round-3 Validation Audit 2026-09-23 (after plan 05-11, G-05-3)

The delta under audit: `QueuePage` gained four derived accessors
(`has_prev`/`prev_offset`/`page_index`/`page_count`), the shared fragment
`queue_list.html` replaced the forward-only control with a
`#queue-pager` (Previous / position line / Next), and `static/vendor/app.css` +
`assets/tailwind/input.css` swapped the dead control rules for `#queue-pager` /
`#queue-page-position`. No route, no state, no migration (head stays `0004`), no JS,
no CDN asset.

The 05-11 SUMMARY cites `tests/db/test_queue_state.py` as the D1 (accessor totality)
evidence. **That file is the watermark suite and contains no `QueuePage` assertion** —
the claimed coverage did not exist. This audit found and closed that and three other
coverage gaps against the plan's `must_haves.truths`:

| Gap | Truth | Gap type | Resolution |
|-----|-------|----------|------------|
| G-05-3-a | "The four derived accessors are total: `page_count` never returns 0 and never divides by zero, and `prev_offset` never goes negative" | MISSING (SUMMARY cited a file that does not test it) | New `tests/db/test_queue_page.py` — 14 tests over first/middle/last/empty/non-divisible/zero-size/negative-size/degenerate shapes |
| G-05-3-b | "whenever the queue is non-empty the fragment renders `Page <page_index> of <page_count> (<limit> per page)` … even when there is only one page" | MISSING (only 3-page queues were tested) | `test_the_position_line_renders_on_a_single_page_queue` |
| G-05-3-c | "Previous … with the CURRENT predicate set" / Next likewise | PARTIAL (only the `excluded` toggle was exercised) | `test_the_pager_carries_the_current_predicate_set` — a `q` and a non-default `sort` must ride both controls |
| G-05-3-d | "a filter, sort or threshold change still emits no offset" | PARTIAL (only the toggle was pinned) | `test_a_sort_or_threshold_change_emits_no_offset` — no `offset` anywhere in `#queue-filters` |

All four were verified non-vacuous by a runtime mutation probe (no implementation file
was modified): breaking `page_count`'s `max(1, limit)` guard and making
`QueueQuery.query_string` return `""` turned the three probe-run tests red. The probe
was then deleted. No implementation bug was found — the accessors, the pager markup and
the server-fixed `limit` all behave as the plan's truths state.

| Metric | Count |
|--------|-------|
| Requirements audited | 11 (RANK-01..08, UI-01..03) — unchanged |
| New map rows added | 5 (05-11-T1, T2 ×3, T3) |
| Coverage gaps found against the 05-11 delta | 4 |
| Gaps resolved by new tests | 4 (all FILLED) |
| Gaps escalated / BLOCKER | 0 |
| New first-class tests added | 17 (14 unit in `tests/db/test_queue_page.py`, 3 API in `tests/api/test_queue_excluded.py`) |
| Tests modified | `tests/api/test_queue_excluded.py` (added `FORM_RE` + 3 tests; existing 8 unchanged and still green) |
| Non-vacuous probe | 3/3 mutated tests failed as expected, probe removed |
| Remaining strict-xfail sentinels | 2 (WR-05, WR-03 — accepted by design, unchanged) |
| Nyquist verdict | ✅ compliant (`nyquist_compliant: true`) |

**Evidence verified on HEAD** (`6062f77` + this audit's working tree): targeted guard run
`tests/db/test_queue_page.py tests/api/test_queue_excluded.py tests/api/test_queue_search.py
tests/api/test_run_trigger.py tests/api/test_queue_links.py tests/test_stylesheet_coverage.py
tests/test_no_cdn.py` → `57 passed`. Full suite `.venv/bin/python -m pytest -q` →
`1085 passed, 14 deselected, 2 xfailed` (was `1068 passed` at the 05-11 SUMMARY; +17 new).

**Files added/updated by this audit:**

- `tests/db/test_queue_page.py` (new, 14 tests) — accessor totality.
- `tests/api/test_queue_excluded.py` (updated, +3 tests) — single-page position line,
  predicate-set carry, form-wide predicate reset.
- `.planning/phases/05-ranking-core-value/05-VALIDATION.md` (this file).
