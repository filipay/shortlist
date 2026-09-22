---
phase: 05-ranking-core-value
verified: 2026-09-22T14:05:00Z
status: gaps_found
score: 21/23 must-haves verified
covered_files:
  - .env.example
  - .planning/phases/05-ranking-core-value/05-01-PLAN.md
  - .planning/phases/05-ranking-core-value/05-01-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-02-PLAN.md
  - .planning/phases/05-ranking-core-value/05-02-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-03-PLAN.md
  - .planning/phases/05-ranking-core-value/05-03-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-04-PLAN.md
  - .planning/phases/05-ranking-core-value/05-04-SUMMARY.md
  - alembic/versions/0004_ranking_config.py
  - app/api/listings.py
  - app/api/settings.py
  - app/config.py
  - app/db/models.py
  - app/db/repositories/llm_call_repo.py
  - app/db/repositories/queue_repo.py
  - app/db/repositories/ranking_config_repo.py
  - app/db/repositories/run_repo.py
  - app/db/repositories/score_repo.py
  - app/domain/rubric.py
  - app/domain/schemas/ranking.py
  - app/main.py
  - app/pipeline/rank.py
  - app/pipeline/run.py
  - app/web/routes.py
  - app/web/templates/html/_listing_row.html
  - app/web/templates/html/listing_detail.html
  - app/web/templates/html/queue.html
  - app/web/templates/html/queue_list.html
  - app/web/templates/html/settings.html
  - compose.yml
  - static/vendor/app.css
covered_digest: "v1:sha256:5b4c1bc375fc71c60487224447bf3fa5300ff35bb82125944e4b53e7be46bda2"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "The queue page reports ranked X of Y and, when a refusal row exists for the latest run, which cap fired."
    status: failed
    reason: >-
      The strip's numerator and denominator are drawn from disjoint populations. `_ranking_strip`
      sets `ranked = latest_run.ranked_count` (COUNT(scores WHERE run_id = latest run)) and
      `candidates = page.total` (the rows surviving THIS request's filters, the min_score threshold
      and the SCORE_SORT_SCAN_LIMIT truncation). The template renders them as the ratio
      "Ranked {{ranked}} of {{candidates}}" (queue.html:135), so with a run that scored 30 listings
      and a filter that matches 5 the page literally reads "Ranked 30 of 5". Reproduced
      deterministically from the source semantics (ranked=30, candidates=5 -> "Ranked 30 of 5").
      No test covers the strip, which is why it shipped.
    artifacts:
      - path: "app/web/routes.py"
        issue: "_ranking_strip lines 291-297: candidates=int(page.total) is the current filtered page total, not the run's candidate count."
      - path: "app/web/templates/html/queue.html"
        issue: "lines 134-137 render the two values as a single ratio."
    missing:
      - "Use the run's own candidate population as the denominator (the plan's `_finish` already persists reason_counts_json['survivors']), or relabel so the two numbers are not presented as a ratio."
      - "Add a test that covers the strip (a run whose ranked_count differs from the current page total)."
  - truth: "An absent OR UNREADABLE fact store makes the detached ranking task return without raising (D-94 posture, module docstring + plan 05-02 Task 3)."
    status: partial
    reason: >-
      The guard is `except (CvFactStoreError, OSError)` (rank.py:380). `load_facts` reads with
      `path.read_text(encoding="utf-8")` (cv/factstore.py), so invalid UTF-8 raises
      `UnicodeDecodeError`, which is a `ValueError` and is neither `OSError` nor `CvFactStoreError`.
      Reproduced: a non-UTF-8 cv.yaml raises UnicodeDecodeError and `isinstance(exc, (CvFactStoreError,
      OSError))` is False. The exception escapes `run_ranking`; because the task is fire-and-forget it is
      never retrieved, `runs.ranked_count` stays NULL, and no `reason="fact_store_absent"` log is emitted.
      `test_rank_optional.py`'s "unreadable" case writes invalid YAML (valid UTF-8 -> CvFactStoreError),
      so the non-UTF-8 path is untested.
    artifacts:
      - path: "app/pipeline/rank.py"
        issue: "line 380 catches only (CvFactStoreError, OSError)."
    missing:
      - "Widen the guard (add ValueError/UnicodeError) or have load_facts wrap the read in try/except (OSError, UnicodeError) and re-raise as CvFactStoreError."
      - "Add a test writing a non-UTF-8 cv.yaml."
human_verification:
  - test: "RANK-05 prose quality (backstop): open several ranked listings and read each stored rationale on the job detail page."
    expected: "Each rationale reads as prose grounded in the listing's stated requirements and the CV evidence IDs actually returned — not a keyword restatement of the listing title."
    why_human: "The plan marks this truth `verification: backstop`: the mechanical half (every evidence_id is a member of iter_fact_ids) is proven, but prose quality is a non-inferable judgment the verifier cannot settle from source."
  - test: "RANK-07 live-model stability tolerance: run the same listing through a live opencode backend twice and compare the stored factor_scores_json."
    expected: "Sub-scores agree to whatever tolerance the requirement intends (the plan assumes bit-identical for a fixed stub payload; it explicitly leaves the live-model tolerance unresolved)."
    why_human: "The stub-backed test proves the call shape is absolute (one listing per prompt), but a live model is non-deterministic; the tolerance is a flagged, unclassified assumption."
  - test: "RANK-06 gap presentation: confirm a requirement the listing states but the CV has no evidence for is shown as a named gap with `evidence_id` null rather than omitted."
    expected: "The requirement appears in the detail page's Requirement fit list with the req-gap class and no evidence id."
    why_human: "Storage of every returned requirement (including gaps) is proven; the plan's flagged assumption leaves the presentation question (show vs omit) unresolved."
  - test: "UI-02 detail layout: review the two-part layout (factor table followed by requirement list) on a rendered job detail page."
    expected: "The grouping is legible and the right one for the fit breakdown."
    why_human: "UI-02's probe row is unclassified: the layout/grouping is a presentation judgment."
  - test: "RANK-04 invalid-weight rejection presentation and UI-03 editor placement: submit an invalid weight and confirm where the editor lives."
    expected: "An invalid submission re-renders the settings page with an inline error (non-200) and writes nothing; the editor lives on the settings page alongside the criteria editor."
    why_human: "Both probe rows are unclassified: rejection presentation and editor location are presentation decisions the plan chose but did not resolve."
  - test: "RANK-08 refusal-audit semantics: decide whether a refused call should write an audit row at all."
    expected: "A deterministic, documented answer; the plan chose one refusal row per refused call with status=error and the cap name in the error text."
    why_human: "RANK-08's probe row is unclassified and unresolved; the alternative (no row, rely on runs.ranked_count) remains a legitimate reading."
---

# Phase 5: One Ranked, Explained Queue — Verification Report

**Phase Goal:** One ranked, explained queue: every surviving listing scored against the user's CV with named factors, stored sub-scores, a grounded rationale, and named gaps.
**Verified:** 2026-09-22T14:05:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | SC1 — User can browse ranked jobs in a list where every listing is scored against their CV using named, inspectable factors, with per-factor sub-scores stored and the total computed in code | ✓ VERIFIED | Six named factors in `app/domain/rubric.py:53`; `score_repo.upsert_score` writes `factor_scores_json`; `queue_repo._enrich` computes the displayed total with `rubric.weighted_total` under current weights; total is read-time, never stored as source. `tests/api/test_queue_ranked.py`, `tests/db/test_score_repo.py`. |
| 2 | SC2 — Re-running ranking gives the same listing a stable, absolute score — never a relative ranking of a batch | ✓ VERIFIED | One `complete_structured` call per listing; prompt carries exactly one listing (`test_prompt_contains_exactly_one_listing`); `test_absolute_score_is_stable_across_runs` asserts identical `factor_scores_json` across two runs. Live-model tolerance is a human item. |
| 3 | SC3 — User can adjust factor weights from the UI and see rankings re-derive without a new LLM call | ✓ VERIFIED | `POST /settings/weights` (`app/api/settings.py:229`) calls `write_weights`; queue recomputes totals on read; `test_weight_change_reorders_the_queue` and `test_weight_change_writes_zero_llm_calls` pass. |
| 4 | SC4 — Opening a job detail shows a rationale grounded in stored evidence plus a requirement-by-requirement fit breakdown with named gaps | ✓ VERIFIED | `GET /listings/{id}` renders `score.rationale`, the factor table, and the requirement list with `req-met`/`req-partial`/`req-gap`; grounding filter drops fabricated ids. `tests/api/test_listing_detail.py`. Prose-quality half is a human item. |
| 5 | SC5 — Once the per-run or per-day LLM spend cap is reached, further calls are refused before the call is made | ✓ VERIFIED | `_reserve`/`_cap_hit` checked before `rank_listing`; `test_cap_refuses_before_the_call` asserts the stub's call count is 1 for 2 listings and one refusal row; `test_rolling_24h_cap_is_enforced`. |
| 6 | `rubric.FACTORS` is exactly the six-key tuple in D-82 order and `RUBRIC_VERSION == "v1"` | ✓ VERIFIED | `rubric.py:53-60,110`; runtime check: `FACTORS ('skills','seniority','domain','location','evidence','compensation') VER v1`. |
| 7 | `weighted_total` re-normalises over present factors, returns `None` on a zero denominator, never raises | ✓ VERIFIED | Runtime: `weighted_total({}) is None`, all-zero weights `None`, `{skills:1.0,domain:0.0}` under equal weights `0.5`. `tests/domain/test_rubric.py`. |
| 8 | `RankingResponse` exposes six top-level scalars, no `total`, bounded `-1.0..1.0`, `-1.0` = absent | ✓ VERIFIED | Runtime: `total_in_schema False`, all six present, defaults `-1.0`; `Field(ge=-1.0, le=1.0)`. |
| 9 | A `scores` row stores per-factor sub-scores; a present `0.0` is stored as `0.0` and never conflated with absent; an all-absent response stores `{}` + `NULL` total | ✓ VERIFIED | `score_repo._factor_payload`/`_factor_scores` filter `< 0.0`; `test_a_present_zero_is_stored_as_zero_and_not_conflated_with_absent`; `RankingResponse()` defaults produce `{}` + `None` through `rank_listing`. |
| 10 | Migration 0004 creates `ranking_config` pinned to id 1; head is 0004; ORM mirrors the migrated schema | ✓ VERIFIED | `alembic/versions/0004_ranking_config.py` (`revision="0004"`, `down_revision="0003"`); `test_migration_contract.py`, `test_skeleton_boot.py`, `test_orm_drift.py` pass. |
| 11 | Every non-null `evidence_id` persisted is a member of `iter_fact_ids(facts)`; a fabricated id is dropped while the listing still scores | ✓ VERIFIED | `rank.py:264-276`; `test_rationale_ids_are_cv_fact_ids` asserts `bul/does-not-exist/0` is absent and the listing still has a score row. |
| 12 | Exactly one `complete_structured` call per listing; a failed listing leaves an `llm_calls` row and no score row while the loop continues | ✓ VERIFIED | `test_failed_listing_is_isolated` asserts 2 audited calls, 1 score row (the good listing only). |
| 13 | A cap hit is a graceful stop: no exception, run not marked failed, one refusal row naming the cap | ✓ VERIFIED | `rank.py:409-434`; `test_cap_refuses_before_the_call` asserts one `purpose="rank"` `status="error"` row with `error` starting `budget_exceeded`; `rank_cap_reason_for_run` returns `per_run`. |
| 14 | D-94: ranking disabled / fact store absent → `run_pipeline` completes and writes zero `llm_calls` and zero `scores`, run `done` | ✓ VERIFIED | `test_ranking_disabled_writes_nothing_and_the_run_is_done`, `test_no_fact_store_writes_nothing_and_the_run_is_done`, `test_unreadable_fact_store...` (invalid YAML), `test_finish_llm_counters.py`. See gap 2 for the non-UTF-8 hole. |
| 15 | At most one ranking task runs at a time; a second start is skipped, not queued | ✓ VERIFIED | `_RANKING_TASK` start-or-skip; `test_a_second_start_is_skipped_while_one_is_live`. |
| 16 | The ranking task owns `runs.ranked_count`/`llm_calls`/`llm_tokens`; `_finish` does not touch `ranked_count` | ✓ VERIFIED | `rank.py:476-490`; `run.py` has no `ranked_count` assignment. |
| 17 | Queue default order is read-time total DESC with unscored last and a deterministic tie-break; `?sort=recent` retains the Phase-1 order | ✓ VERIFIED | `_score_sort_key`; `test_default_order_is_score_desc_unranked_last`, `test_sort_recent_restores_first_seen_order`, `test_two_identical_requests_return_the_same_row_order`. |
| 18 | The FTS `MATCH` predicate and the sort are independent; `sort=score` wins over bm25 while the MATCH filter still applies | ✓ VERIFIED | `test_score_sort_wins_over_bm25_when_q_is_set`. |
| 19 | An unscored listing renders a distinct unranked badge and no synthetic `0.0`; it sorts after every scored row | ✓ VERIFIED | `_listing_row.html` `badge-unranked`; `test_unranked_row_renders_the_badge`, `test_unscored_listing_renders_no_numeric_total`. |
| 20 | `?min_score=` is a view-only threshold that stores nothing and always keeps unscored listings visible | ✓ VERIFIED | `queue_repo.read_queue:533-541` (`row.total_score is None or >= threshold`); `test_min_score_keeps_unscored_visible`, `test_junk_min_score_degrades_to_no_threshold`. |
| 21 | Saving weights writes one `ranking_config` document, re-renders with a note, and rejects invalid input without writing | ✓ VERIFIED | `save_weights` + `_parse_weights`; `test_weights_form_saves_and_rerenders`, `test_invalid_weight_writes_nothing`, `test_all_zero_weights_are_rejected`. |
| 22 | `GET /listings/{listing_id}`: 200 for known, 404 fragment `data-error="unknown-listing"` for unknown, identity seam declared; renders total/tier/factors+weights/rationale/requirements/merge/actions; unscored = not-yet-ranked; untrusted text escaped | ✓ VERIFIED | `app/api/listings.py`; `listing_detail.html`; `tests/api/test_listing_detail.py` (5 tests) + `tests/test_auth_seam.py`. |
| 23 | The queue page reports ranked X of Y and, when a refusal row exists, which cap fired | ✗ FAILED | Rendered, but `ranked` and `candidates` are disjoint populations → "Ranked 30 of 5" is reproducible. See gap 1. |

**Score:** 21/23 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/domain/rubric.py` | pure six-factor rubric + code-side total | ✓ VERIFIED | I/O-free, 175 lines, no forbidden imports |
| `app/domain/schemas/ranking.py` | top-level-scalar response, no total | ✓ VERIFIED | six bounded scalars + `RequirementFit` |
| `app/db/models.py` `RankingConfig` | singleton weights row | ✓ VERIFIED | `id=1` CHECK constraint, no FK |
| `alembic/versions/0004_ranking_config.py` | additive `ranking_config` table, head 0004 | ✓ VERIFIED | `upgrade`/symmetric `downgrade`; not seeded |
| `app/db/repositories/ranking_config_repo.py` | tolerant read, strict write | ✓ VERIFIED | default fallback; unknown key/negative rejected before SQL |
| `app/db/repositories/score_repo.py` | the `scores` writer | ✓ VERIFIED | one row per `(listing, run, criteria_version)`, non-null criteria_version |
| `app/pipeline/rank.py` | one listing ranked end-to-end + caps | ✓ VERIFIED | 546 lines; frozen system prompt; grounding filter; reserve-then-call |
| `app/db/repositories/queue_repo.py` | score ordering + threshold | ✓ VERIFIED | Python-side sort over bounded scan |
| `app/web/routes.py` | sort/min_score parse + ranking strip | ⚠️ PARTIAL | parse verified; `_ranking_strip` denominator wrong (gap 1) |
| `app/api/settings.py` | `POST /settings/weights` | ✓ VERIFIED | zero model calls; validation at boundary |
| `app/api/listings.py` | `GET /listings/{id}` | ✓ VERIFIED | 404 fragment + identity seam |
| templates + `static/vendor/app.css` | detail page, queue controls, badges | ✓ VERIFIED | stylesheet-coverage + no-CDN tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `app/pipeline/run.py` | `start_ranking_task` | detached call after the hard filter, backend threaded | ✓ WIRED | `llm` keyword; best-effort shape |
| `rank.py` | `score_repo.upsert_score` | grounding filter → write | ✓ WIRED | `iter_fact_ids` check before persist |
| `rank.py` | `llm_call_repo.record_llm_call` | one audit row per call | ✓ WIRED | success and failure |
| `queue_repo._enrich` | `ranking_config_repo.read_weights` + `rubric.weighted_total` | read-time total | ✓ WIRED | weights read once per page |
| `app/api/settings.py` | `ranking_config_repo.write_weights` | weights editor | ✓ WIRED | zero model calls |
| `_listing_row.html` | `/listings/{id}` | Details link | ✓ WIRED | additive |
| `listing_detail.html` | `score_repo.read_score_for_listing` | rationale + requirements | ✓ WIRED | via `read_row` + score read |
| `web/routes.py` `_ranking_strip` | `run_repo`/`llm_call_repo` | ranked + cap reason | ⚠️ PARTIAL | `candidates` wired to the page total, not the run population (gap 1) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `_listing_row.html` score badge | `row.total_score` | newest `scores.factor_scores_json` → `weighted_total` under live weights | Yes | ✓ FLOWING |
| `listing_detail.html` factor table | `row.factor_scores` / `weights` | stored score row + `ranking_config` | Yes | ✓ FLOWING |
| `listing_detail.html` requirements | `score.requirements` | stored `gaps_json`, CV-grounded | Yes | ✓ FLOWING |
| `queue.html` ranking strip | `ranking_strip.ranked`/`candidates` | `runs.ranked_count` vs `page.total` | Mismatched populations | ✗ MISWIRED (gap 1) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Factor set / version / weighted_total edges | inline python | `FACTORS` 6 in order, `VER v1`, `{} → None`, zero-weights `None`, `0.5` case | ✓ PASS |
| `RankingResponse` schema has no `total`, six top-level factors | inline python | `total_in_schema False`, all six present, defaults `-1.0` | ✓ PASS |
| Reservation primitive refuses at the ceiling | inline python | `reserve1 True`, `reserve2 False` | ✓ PASS |
| CR-01 strip population mismatch | inline python | `Ranked 30 of 5` | ✗ FAIL (gap 1) |
| WR-02 non-UTF-8 CV guard | inline python | raises `UnicodeDecodeError`; caught by `(CvFactStoreError, OSError)`: **False** | ✗ FAIL (gap 2) |
| Full hermetic suite | `.venv/bin/python -m pytest -q` | 1042 passed, 14 deselected | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` declared by this phase and no migration/tooling probe contract in the PLAN/SUMMARY files.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| RANK-01 | 05-01 | Scored against CV using named, inspectable factors | ✓ SATISFIED | `rubric.FACTORS`, `rank_listing`, queue/detail surfaces |
| RANK-02 | 05-01 | Per-factor sub-scores stored, not just a total | ✓ SATISFIED | `factor_scores_json`; `RankingResponse` has no total |
| RANK-03 | 05-01 | Total computed in code from stored sub-scores and weights | ✓ SATISFIED | `rubric.weighted_total` at read time |
| RANK-04 | 05-04 | Adjust factor weights and see rankings re-derive | ✓ SATISFIED | `/settings/weights`; zero-LLM reorder test (presentation → human) |
| RANK-05 | 05-01 | Rationale grounded in stored evidence | ✓ SATISFIED (mechanically) | Grounding filter + detail page; prose quality → human (backstop) |
| RANK-06 | 05-01 | Requirement-by-requirement fit breakdown with named gaps | ✓ SATISFIED | `gaps_json` + detail requirement list; presentation → human |
| RANK-07 | 05-01 | Absolute per-listing score, stable across runs | ✓ SATISFIED | one-listing-per-call; stub stability test; live tolerance → human |
| RANK-08 | 05-02 | LLM spend capped per run and per day, enforced before the call | ✓ SATISFIED | `_reserve`/`_cap_hit`; refusal-before-call tests |
| UI-01 | 05-04 | Browse ranked jobs in a list | ✓ SATISFIED | score-ordered queue + sort/min_score controls |
| UI-02 | 05-03 | Job detail with fit breakdown and rationale | ✓ SATISFIED | `GET /listings/{id}` + tests |
| UI-03 | 05-04 | Edit search criteria and ranking weights | ✓ SATISFIED | weights card on settings; criteria editor pre-existing |

**Orphaned requirements:** None. All 11 IDs mapped to Phase 5 appear in a PLAN's `requirements_addressed` (05-01: RANK-01/02/03/05/06/07; 05-02: RANK-08; 05-03: UI-02; 05-04: RANK-04, UI-01, UI-03).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/web/routes.py` | 291-297 | Strip denominator from a different population than the numerator | 🛑 Blocker | Gap 1 — user-visible false "Ranked X of Y" |
| `app/pipeline/rank.py` | 380 | `except (CvFactStoreError, OSError)` misses non-UTF-8 `UnicodeDecodeError` | ⚠️ Warning | Gap 2 — detached task raises, no skip log, NULL `ranked_count` |
| `app/db/repositories/queue_repo.py` | 111,430-454,543 | Score-path scan truncates at 5000; default read silently drops older listings and under-reports `total` | ⚠️ Warning | WR-01 — accepted at personal scale (ponytail comment) but the default queue is the truncated one; also caps `_queued_listing_ids` below `_DISMISS_LIMIT` |
| `app/web/routes.py` | 109-116,140 | `_float_or_none` accepts `nan`/`inf`; `?min_score=nan` hides every scored listing | ⚠️ Warning | WR-03 — contradicts the "junk degrades to None" docstring/T-05-19 |
| `app/web/templates/html/listing_detail.html` | 96-117 | Save/Hide forms target `#listing-row-{id}`, which does not exist on the detail page | ⚠️ Warning | WR-04 — htmx targetError; the control appears inert |
| `app/db/repositories/ranking_config_repo.py` | 48-64 | `read_weights` accepts a negative stored weight; only the write path validates | ⚠️ Warning | WR-05 — a hand-written doc can produce `None` totals or out-of-range order |
| `app/pipeline/rank.py` | 417-424,486-489 | The cap-refusal row is counted as spend by `rank_calls_since` and `llm_totals_for_run` | ⚠️ Warning | WR-06 — refusals inflate the rolling cap and `runs.llm_calls` |
| `app/pipeline/rank.py` | 278-294 | `scores.search_id` is never written (column dead) | ℹ️ Info | WR-07 — audit field dropped even though `search_id` is in scope |
| `app/web/templates/html/queue.html` | 30 | `{{ last_run.reason or 'unknown' | human_label }}` — filter precedence | ℹ️ Info | IN-01 — pre-existing; label never humanises a truthy reason |
| `app/pipeline/rank.py` | 369,407 | One frozen `moment` reused for the whole pass | ℹ️ Info | IN-04 — every row shares one `created_at`; window does not advance |
| `app/pipeline/rank.py` | 476-490 | Final accounting block is not exception-guarded | ℹ️ Info | IN-05 — a DB error there is the same silent NULL-`ranked_count` state as WR-02 |

**Debt markers:** None. No `TBD`/`FIXME`/`XXX` in any phase-modified file.

### Human Verification Required

1. **RANK-05 rationale prose quality (backstop)** — read several stored rationales on the detail page; confirm each is grounded prose, not a keyword restatement.
   - Expected: grounded in the listing's stated requirements and the cited CV fact IDs.
2. **RANK-07 live-model stability tolerance** — run one listing twice against a live backend and compare `factor_scores_json`.
   - Expected: agreement to the tolerance the requirement intends (unresolved flagged assumption).
3. **RANK-06 gap presentation** — confirm an unevidenced requirement is shown as a named gap, not omitted.
   - Expected: present with the `req-gap` class and `evidence_id` null.
4. **UI-02 detail layout** — review the factor-table-then-requirement-list grouping.
   - Expected: legible and the right grouping.
5. **RANK-04 / UI-03 weights editor presentation and placement** — submit an invalid weight; confirm the inline error and the settings-page location.
   - Expected: non-200 re-render with an inline error, nothing written; editor on the settings page.
6. **RANK-08 refusal-audit semantics** — decide whether a refused call should write an audit row at all.
   - Expected: a deliberate, documented decision (the plan chose one refusal row with the cap name in the error text).

### Gaps Summary

The architectural core of the phase is real and largely proven: the rubric is pure and correctly ordered, `weighted_total` re-normalises and never fabricates a `0.0`, the response schema is top-level-scalar with no model-supplied total, the `scores` writer stores per-factor sub-scores with a non-null `criteria_version`, the CV-grounding filter drops fabricated evidence IDs before the write, one `complete_structured` call per listing is detached and threaded correctly, both spend ceilings refuse before the request, the job detail page renders the rationale/factor-weight table/requirement list with named gaps and escaping, and the queue defaults to the read-time total with unscored listings last and a weights editor that re-derives order with zero LLM calls. All 5 roadmap success criteria are met at the code level and 1042 tests pass.

Two must-have defects remain, both independently reproduced:

1. **The ranking strip reports a false ratio (gap 1).** `ranked` (score rows for the latest run) and `candidates` (the current filtered page total) are disjoint populations, so the phase's own "ranked X of Y" surface can read "Ranked 30 of 5". This is the one must-have truth that is FAILED; it is user-visible and untested.
2. **The "unreadable CV" skip is incomplete (gap 2).** A non-UTF-8 `cv.yaml` raises `UnicodeDecodeError` past the `(CvFactStoreError, OSError)` guard, so the detached task fails without the documented skip log and leaves `ranked_count` NULL.

The accompanying `05-REVIEW.md` (1 critical + 7 warnings + 5 info) independently corroborates gap 1 and adds edge-case warnings (scan truncation, `nan` threshold, detail-page htmx target, `read_weights` validation, refusal-row double-count, dead `search_id`) that the phase's tests do not cover. Scope is otherwise clean: no dependency additions, no CDN assets, repositories still never commit, and no debt markers.

### Deferred Items

None. The gaps above are Phase-5 surfaces (queue read, ranking lifecycle, ranking strip); no later milestone phase's goal or success criteria covers them.

---

_Verified: 2026-09-22T14:05:00Z_
_Verifier: the agent (gsd-verifier)_
