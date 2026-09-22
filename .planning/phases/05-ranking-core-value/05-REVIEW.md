---
phase: 05-ranking-core-value
reviewed: 2026-09-22T13:47:40Z
depth: standard
files_reviewed: 42
files_reviewed_list:
  - .env.example
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
  - tests/api/test_listing_detail.py
  - tests/api/test_queue_links.py
  - tests/api/test_queue_ranked.py
  - tests/api/test_queue_search.py
  - tests/api/test_ranking_weights.py
  - tests/api/test_settings_reset.py
  - tests/db/test_migration_contract.py
  - tests/db/test_no_pii_columns.py
  - tests/db/test_score_repo.py
  - tests/db/test_skeleton_boot.py
  - tests/domain/test_rubric.py
  - tests/pipeline/test_filter_stage.py
  - tests/pipeline/test_finish_llm_counters.py
  - tests/pipeline/test_rank_caps.py
  - tests/pipeline/test_rank_optional.py
  - tests/pipeline/test_rank_stage.py
  - tests/test_auth_seam.py
  - tests/test_config.py
findings:
  critical: 1
  warning: 7
  info: 5
  total: 13
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-09-22T13:47:40Z
**Depth:** standard
**Files Reviewed:** 42
**Status:** issues_found

## Summary

Phase 5 delivers the core value: a pure six-factor rubric (`app/domain/rubric.py`),
a structured `RankingResponse` schema, a `scores` writer, a live `ranking_config`
weights document (migration 0004), one `complete_structured` call per listing wired
into a detached ranking task, two reserve-then-call spend ceilings, a job detail
page, and a score-ordered queue with a weights editor.

The architectural core is sound. The rubric is genuinely pure and I/O-free; the
factor set is pinned and free of protected attributes; `weighted_total` re-normalises
over present factors and returns `None` (never a fabricated `0.0`) for a zero
denominator; the `-1.0` absent sentinel is handled consistently across
`present_factors`, `_factor_payload`, `_factor_scores` and `rank_listing`; the total
is computed in code and never requested from the model; the RANK-05 grounding
(`iter_fact_ids` check before persistence) is real and correctly placed; and the
`system` prompt is a frozen literal with untrusted text confined to `parts`. The
repository/route/template layering holds, repositories still never commit, and the
reset route correctly treats `ranking_config` as kept configuration.

The defects found are concentrated in the surfaces added last: the queue's
read-time scoring path, the new ranking strip, and the detached task's failure
handling. One is user-visible incorrect information on the phase's headline surface;
the rest are robustness/edge-case gaps and one dead column. Verified: the phase's
test suites pass (`tests/db/test_score_repo.py`, `tests/domain/test_rubric.py`,
`tests/pipeline/test_rank_stage.py`, `tests/pipeline/test_rank_caps.py`,
`tests/api/test_queue_ranked.py`, `tests/api/test_listing_detail.py`,
`tests/api/test_ranking_weights.py`, `tests/test_config.py` — 84 passed), but the
failures below are not covered by them.

## Narrative Findings (AI reviewer)

### Critical Issues

#### CR-01: The ranking strip's "of N" denominator is an unrelated population, so the strip routinely reports "Ranked 30 of 5"

**File:** `app/web/routes.py:276-301` and `app/web/templates/html/queue.html:133-137`

**Issue:** `_ranking_strip` builds `candidates` from the *current queue page's*
`page.total`:

```python
return {
    "ranked": latest_run.ranked_count,      # score rows written for that run
    "candidates": int(page.total),          # rows surviving THIS request's filters/threshold
    "cap_reason": ...,
}
```

and `queue.html` renders `Ranked {{ ranking_strip.get('ranked') }} of
{{ ranking_strip.get('candidates') }}`.

`ranked_count` is written by `run_ranking` as `COUNT(scores WHERE run_id = ?)`
(`app/pipeline/rank.py:480-487`), while `page.total` is the queue total *after* the
user's `q`/`excluded`/`hidden`/`saved`/`scope` predicates, the `min_score`
threshold, and the `SCORE_SORT_SCAN_LIMIT` truncation
(`app/db/repositories/queue_repo.py:533-553`). The two numbers are drawn from
different populations, so the strip is not a ratio at all:

* with a search that matches 5 listings after a run that scored 30, the page reads
  **"Ranked 30 of 5"**;
* unfiltered, `ranked_count` (score rows for one run) and `page.total`
  (queue-visible listings, which exclude hidden/absorbed/excluded rows) still
  disagree routinely.

This is incorrect, user-visible information on the ranking surface this phase
exists to build — the surface whose whole purpose is to make ranking coverage
legible (D-89/D-93). No test covers the strip, which is why it passed.

**Fix:** use the run's own candidate count as the denominator. `_finish` already
persists `reason_counts_json["survivors"]` (the run's survivor count), so:

```python
counts = latest_run.reason_counts or {}
return {
    "ranked": latest_run.ranked_count,
    "candidates": int(counts.get("survivors", 0)),
    "cap_reason": await llm_call_repo.rank_cap_reason_for_run(session, run_id=latest_run.id),
}
```

(`RunSummary` does not currently expose `reason_counts`; either add it to the
summary or read the column in `_ranking_strip`.) If the intended meaning really is
"how many of the currently-shown queue are ranked", then rename the labels
(e.g. "N of these M are ranked") and compute `ranked` from the page, not the run —
but do not render a numerator and denominator from two different sets.

### Warnings

#### WR-01: The default (score) queue sort silently drops every listing beyond the 5 000-row scan

**File:** `app/db/repositories/queue_repo.py:111`, `424-454`, `520-553`;
`app/web/routes.py:195-238`

**Issue:** `SCORE_SORT_SCAN_LIMIT = 5000` bounds `_score_candidate_ids` with
`ORDER BY first_seen_at DESC, id DESC LIMIT 5000`. Because `sort="score"` is the
default, this is not a performance guard on a secondary view — it is the *primary
queue read*. With more than 5 000 matching listings, the oldest ones are not
"unranked last", they are **absent from the queue entirely**, and `page.total`
(computed as `len(enriched)`) under-reports so paging stops early. The queue is the
product; a listing that exists and is not filtered out but never appears is the
worst failure mode for a job-search tool.

The same truncation also defeats the Dismiss guard it appears to protect:
`_queued_listing_ids` (`app/web/routes.py:195-238`) pages through `read_queue`,
which always uses the bounded scan, so its `page.total > _DISMISS_LIMIT` check can
never see more than 5 000 rows. `_DISMISS_LIMIT = 10_000` therefore never trips, and
"Dismiss all" silently hides only the first 5 000 — precisely the "a 'Dismiss all'
that silently stopped at the cap would be a lie" case the docstring forbids.

**Fix:** at minimum, surface the truncation (e.g. return a `truncated: bool` on
`QueuePage` and render "showing the 5 000 newest — narrow the search"); better, make
the score sort SQL-expressible (materialise the read-time total, or sort on a fixed
denominator) as the `ponytail:` comment already names, and make `_queued_listing_ids`
count against the true predicate rather than the truncated scan.

#### WR-02: A non-UTF-8 `cv.yaml` crashes the detached ranking task instead of taking the documented clean-skip path

**File:** `app/pipeline/rank.py:377-387`

**Issue:** the D-94 skip guard is

```python
except (CvFactStoreError, OSError) as exc:
```

`load_facts` reads with `path.read_text(encoding="utf-8")`
(`app/cv/factstore.py:56`). Invalid UTF-8 raises `UnicodeDecodeError`, which is a
`ValueError` — **not** `OSError` and **not** `CvFactStoreError` (verified:
`isinstance(exc, OSError) == False`). It therefore escapes `run_ranking`. Because
the task is fire-and-forget, the exception is never retrieved: the run still
completes, but `runs.ranked_count` stays NULL and the operator gets an asyncio
"exception was never retrieved" rather than the documented
`reason="fact_store_absent"` log. The module docstring explicitly claims "an absent
**or unreadable** fact store" is handled.

**Fix:** widen the guard to the actual contract, e.g.
`except (CvFactStoreError, OSError, ValueError) as exc:` — or, cleaner, have
`load_facts` wrap the read in `try/except (OSError, UnicodeError)` and re-raise as
`CvFactStoreError` so the trust boundary reports one failure type.

#### WR-03: `?min_score=nan` (or `inf`) passes validation and silently hides every scored listing

**File:** `app/web/routes.py:109-116`, `140`

**Issue:** `_float_or_none` accepts anything `float()` parses:

```python
try:
    return float(value)
except (TypeError, ValueError):
    return None
```

`float("nan")` and `float("inf")` succeed, so `?min_score=nan` produces
`min_score = nan`. In `read_queue` (`queue_repo.py:533-541`) the predicate
`row.total_score >= nan` is `False` for every scored row, so **all scored listings
disappear** while unscored rows are kept. The nan then round-trips into
`QueueQuery.query_string()` and onto the Load-more / Mark-seen / Dismiss URLs. The
docstring for `parse_queue_query` and T-05-19 promise that junk degrades to `None`;
nan/inf is not junk-handled.

**Fix:** add the same finiteness gate the weights parser already uses:

```python
import math
...
try:
    parsed = float(value)
except (TypeError, ValueError):
    return None
return parsed if math.isfinite(parsed) else None
```

#### WR-04: The detail page's Save/Hide forms target an element that does not exist on that page

**File:** `app/web/templates/html/listing_detail.html:96-117`

**Issue:** both forms use `hx-target="#listing-row-{{ row.id }}"`. `#listing-row-*`
is emitted only by `_listing_row.html` on the queue; the detail page renders no such
element. htmx cannot resolve the target on the response, raises `htmx:targetError`
and performs no swap, so clicking Save/Hide on the detail page appends the event
server-side but gives the user **no feedback whatsoever** — not even the button
flip. The template comment acknowledges "the page reflects the new state on reload",
but a control that appears inert is a defect, and a 404/422 response is equally
invisible.

**Fix:** either target something that exists on the detail page (e.g. wrap the
actions section in `id="detail-actions-{{ row.id }}"` and swap it), or drop the
`hx-*` attributes and use a plain `method="post"` full-page form, which matches the
documented "reflects the new state on reload" posture without a dead htmx target.

#### WR-05: `read_weights` accepts negative stored weights; only the write path validates

**File:** `app/db/repositories/ranking_config_repo.py:48-64`

**Issue:** `write_weights` rejects negative/non-finite values (good), but
`read_weights` only checks `_as_float` and then `weights[factor] = value`. A
`ranking_config.weights_json` written by hand, by an older build, or by any future
path that bypasses `write_weights` with e.g. `{"skills": -5}` is returned verbatim.
`rubric.weighted_total` then divides by a weight sum that can be `<= 0` (returning
`None`, silently un-ranking everything) or produces a total outside the documented
`-1.0..1.0` range and a nonsensical queue order. The module docstring promises the
read is "tolerant by construction".

**Fix:** clamp or drop non-finite/negative values on read, mirroring
`write_weights`:

```python
value = _as_float(document.get(factor))
if value is None or value < 0.0:
    value = float(rubric.DEFAULT_WEIGHTS[factor])
weights[factor] = value
```

#### WR-06: The cap-refusal audit row is counted as a spend by both the ceiling and `runs.llm_calls`

**File:** `app/pipeline/rank.py:417-424`, `486-489`;
`app/db/repositories/llm_call_repo.py:193-213`, `221-241`

**Issue:** a refusal writes a `purpose="rank"`, `status="error"` row
(`app/pipeline/rank.py:417-424`). Two consequences:

1. `rank_calls_since` counts `purpose="rank"` rows with no status filter, so each
   refused run's *non-spending* refusal row consumes one slot of the rolling-24h
   ceiling. Repeated runs at the cap inflate `day_total` with rows that never made a
   request.
2. `run_ranking`'s final accounting calls `llm_totals_for_run`, which counts every
   row for the run including the refusal row, so `runs.llm_calls` over-reports the
   run's real call count by one per refusal. `runs.llm_tokens` is unaffected only
   because the refusal row has NULL tokens.

The audit row itself is right (D-93); counting it as a call is not.

**Fix:** exclude refusals from the counts — e.g. filter
`LlmCall.error.is_(None) | ~LlmCall.error.startswith(BUDGET_EXCEEDED_MARKER)`, or
filter on `status != "error"` where the intent is "attempts that reached the
backend". Keep the refusal row for the UI.

#### WR-07: `scores.search_id` is never written — the column is dead

**File:** `app/pipeline/rank.py:278-294`; `app/db/repositories/score_repo.py:175-194`

**Issue:** `upsert_score` accepts `search_id` and the `scores` table has carried the
column (with an FK) since migration 0001, but the only production call site
(`app/pipeline/rank.py:278`) never passes it, so `scores.search_id` is always NULL —
including for a per-search run where `run_ranking` knows the id (`search_id` is in
scope at `app/pipeline/rank.py:390`). `criteria_version` is derived from that search,
so the association is available and simply dropped. Any future per-search ranking
view or audit query over `scores.search_id` will find nothing.

**Fix:** thread `search_id` through `rank_listing` into `upsert_score` (add the
parameter, default `None`, and pass `run_ranking`'s `search_id`). Do not add it to
`uq_scores_listing_run_criteria` without a migration; it is an audit field only.

### Info

#### IN-01: `human_label` never applies to a truthy reason because of filter precedence

**File:** `app/web/templates/html/queue.html:30`, `app/web/templates/html/runs.html:66`

**Issue:** `{{ last_run.reason or 'unknown' | human_label }}` parses as
`reason or ('unknown' | human_label)` — filters bind tighter than `or` (verified:
renders `all_filtered`, not the humanised form). The filter only ever runs on the
`'unknown'` fallback. Pre-existing, but `queue.html` is in this phase's change set.

**Fix:** parenthesise: `{{ (last_run.reason or 'unknown') | human_label }}`.

#### IN-02: `_flag` is copy-pasted into three modules, and per-page rule counts are computed twice

**File:** `app/api/events.py:57`, `app/api/listings.py:49`, `app/web/routes.py:90`;
`app/db/repositories/queue_repo.py:492` and `667`

**Issue:** the identical `_flag` helper exists in three modules; and
`read_queue` calls `_page_rule_counts` at line 492 while `_enrich` calls it again at
line 667 for the same page (two identical aggregate queries per render).

**Fix:** move `_flag` to `app/web/` (or `app/api/deps.py`) and import it; pass the
already-computed `rule_counts` into `_enrich` instead of recomputing.

#### IN-03: `jobsearch.db` sits at the repo root, untracked and not gitignored

**File:** `.gitignore` (repo root `jobsearch.db`)

**Issue:** `git status` reports `?? jobsearch.db`; `git check-ignore` exits 1. The
file is a local SQLite database that can contain CV-derived scores, rationales and
listing history — the same class of personal data `.gitignore` already protects with
`cv/`, `artifacts/` and `.env`. A broad `git add -A` would commit it.

**Fix:** add `*.db`, `*.db-wal`, `*.db-shm` (or at least `jobsearch.db*`) to
`.gitignore`. Outside the phase file list, but worth fixing before the next commit.

#### IN-04: One frozen `moment` is used for the whole ranking pass

**File:** `app/pipeline/rank.py:369`, `407`

**Issue:** `moment = now or datetime.now(UTC)` is captured once and reused for every
listing's `now` and for every `rank_calls_since(now=moment)`. Every `llm_calls` row
in a pass shares one `created_at`, and the rolling-24h window does not advance while
a long pass runs.

**Fix:** either document this explicitly (it is deterministic and convenient for
tests) or re-read `datetime.now(UTC)` per iteration for the cap read.

#### IN-05: `run_ranking`'s final accounting block is not exception-guarded

**File:** `app/pipeline/rank.py:476-490`

**Issue:** the per-listing loop is carefully isolated, but the final
`session.get(Run)` / commit is not. A DB error there raises out of the detached
task and is never retrieved, leaving the same silent NULL-`ranked_count` state as
WR-02. Wrapping it in the module's usual best-effort shape would make the failure
legible.

**Fix:** wrap the block in `try/except Exception` with a
`log.warning("pipeline.rank_accounting_failed", ...)`, matching the rest of the
stage.

---

_Reviewed: 2026-09-22T13:47:40Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
