---
phase: 05-ranking-core-value
reviewed: 2026-09-23T13:12:15Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - app/api/health.py
  - app/api/listings.py
  - app/api/settings.py
  - app/cv/factstore.py
  - app/db/repositories/run_repo.py
  - app/pipeline/rank.py
  - app/pipeline/run.py
  - app/web/routes.py
  - app/web/templates/html/_health_strip.html
  - app/web/templates/html/listing_detail.html
  - app/web/templates/html/queue.html
  - app/web/templates/html/settings.html
  - static/vendor/app.css
  - tests/api/test_health.py
  - tests/api/test_listing_detail.py
  - tests/api/test_queue_ranked.py
  - tests/api/test_settings_page.py
  - tests/cv/test_factstore.py
  - tests/pipeline/test_rank_optional.py
  - tests/test_cv_tex_spike_docs.py
  - docs/probes/2026-09-21-cv-tex-spike.md
  - docs/probes/README.md
findings:
  critical: 0
  warning: 2
  info: 5
  total: 7
status: issues_found
---

# Phase 5: Code Review Report (round 2 — gap-closure deltas 05-07…05-10)

**Reviewed:** 2026-09-23T13:12:15Z
**Depth:** standard
**Files Reviewed:** 22
**Status:** issues_found

## Summary

Round-2 review scoped to the gap-closure deltas (plans 05-07…05-10) that landed
after the previous report (`2026-09-22T17:36:22Z`, 46 files). Verified against the
committed tree at `0ca4308`: `.venv/bin/python -m compileall -q app` is clean and
`.venv/bin/python -m pytest -q` is `1065 passed, 14 deselected, 2 xfailed`, matching
the plans' stated baseline.

**What is sound.** The core of the delta holds up under tracing. The five-state
derivation (`RunSummary.ranking_state`) is coherent: `ranked_count` is written only
by a finished pass, skipped runs return from `run_ranking` *before* the accounting
block so they never acquire a `ranked_count`, and `not_attempted`/`skipped` are
mutually exclusive with a completed pass — so the marker and the numerator cannot
contradict each other. The `_ranking_marker` parser is total for non-mapping,
non-string and hand-edited shapes. `fact_store_report` is total, reports the
exception **class name only** (no message can carry document text into a page or the
`/health` JSON), and its `error` field is never rendered raw. The skip vocabulary has
one definition, the template branches only on precomputed state (no reason string in
markup), and no `|safe`, JS or new poll target was introduced. The `cv-status`
stylesheet rule is a clean one-line insertion into the built CSS and the coverage
guard passes; no previously-used class was dropped. The docs change is accurate
(`compose.yml` does mount `./cv:/cv`) and no step cross-reference broke.

**Two defects, both in the delta.** One is a user-visible regression on the run-detail
page caused by the new sub-key riding a generically-iterated JSON bag (WR-01); the
other is a contract violation in a new helper that claims totality it does not have
(WR-02). Neither is a crash, a data-loss path, or a security hole, so both are
WARNINGs, not BLOCKERs.

**Prior findings.** Per the scope note, the previous report's findings were not
re-litigated. They remain as filed in the prior artifact's history: CR-01
(`SCORE_SORT_SCAN_LIMIT` truncation defeats the Dismiss ceiling), WR-01
(`min_score=nan/inf`), WR-02 (dead htmx target on the detail page), WR-03 (negative
stored weights accepted on read), WR-04 (refusal row counted as spend), WR-05
(`scores.search_id` never written), WR-07 (`run_ranking`'s accounting block
unguarded), WR-08 (`_int`/`_optional_int` not total on `1e999`), and IN-01…IN-06.
**Nothing in this delta fixes or worsens any of them**, with one nuance: the new
`ranking` sub-key makes the run-detail surface (WR-01 below) the second reader that
does *not* ignore it — the same class of "unknown sub-key" assumption that the prior
WR-08 already showed `run_repo` must not make.

## Narrative Findings (AI reviewer)

### Warnings

#### WR-01: The new `reason_counts_json['ranking']` sub-key renders as a raw Python dict repr on the run-detail page

**File:** `app/pipeline/run.py:976` (writer); `app/web/templates/html/runs.html:106-112`
(reader); reached via `app/api/runs.py:113-160` (`render_run_detail` → `get_run_detail`)

**Issue:** `_finish`'s counts bag is rendered generically by `runs.html`:

```jinja
{% for key, value in detail.reason_counts.items() %}
<dt>{{ key }}</dt>
<dd>{{ value }}</dd>
{% endfor %}
```

The round-2 change merges a **nested object** into that bag
(`reason_counts = {**reason_counts, "ranking": ranking_outcome}`, where
`ranking_outcome` is `{"status": "skipped", "reason": "<constant>"}` or
`{"status": "not_attempted"}`). Every other value in the bag is a scalar, so the new
key is the only one that stringifies to a Python repr. Proven against the real
read path (`_mapping` is exactly what `get_run_detail` passes as `reason_counts`):

```
<dt>survivors</dt><dd>5</dd>
<dt>ranking</dt><dd>{&#39;status&#39;: &#39;skipped&#39;, &#39;reason&#39;: &#39;fact_store_absent&#39;}</dd>
```

i.e. `/runs/{id}` and its HTMX-expanded fragment display
`{'status': 'skipped', 'reason': 'fact_store_absent'}` in the "Counts behind the
reason" list. This is the normal path for every skipped or nothing-to-rank run.

The 05-08 plan's key decision — repeated in `05-08-SUMMARY.md` — asserts "existing
readers ignore the unknown sub-key". That premise is **false**: `runs.html` iterates
the whole bag and does not ignore it, and the existing subset-style assertions
(`tests/pipeline/test_filter_stage.py:393-403`, `tests/pipeline/test_union_fetch.py`)
cannot catch it. This is precisely the "a row written by an older build (or edited by
hand) cannot blow up the page" class of assumption `run_repo` already documents, now
made in the opposite direction: a *newer* writer changed the shape a reader depends
on.

**Fix (smallest):** render the marker explicitly in `runs.html` instead of letting the
generic loop stringify it, e.g. skip non-scalar values in the loop and add one line:

```jinja
{% for key, value in detail.reason_counts.items() %}
  {% if value is not mapping %}
  <dt>{{ key }}</dt><dd>{{ value }}</dd>
  {% endif %}
{% endfor %}
{% if detail.reason_counts.get('ranking') %}
<dt>ranking</dt>
<dd>{{ detail.reason_counts['ranking'].get('status') }}{% if detail.reason_counts['ranking'].get('reason') %} — {{ detail.reason_counts['ranking']['reason'] }}{% endif %}</dd>
{% endif %}
```

A cleaner alternative is to keep the bag scalar-only: persist the outcome as two
scalar keys (`ranking_status` / `ranking_reason`) and have `_ranking_marker` read
those, so no generic bag reader ever has to learn a nested shape. Whichever is
chosen, add a run-detail test that seeds a `{"status": "skipped", ...}` marker and
asserts the repr form is absent.

#### WR-02: `ranking_skip_reason()` is not total despite its "never raises" contract, and mislabels an unparseable fact store as `rank_start_failed`

**File:** `app/pipeline/rank.py:100-112`; consumed at `app/pipeline/run.py:921`

**Issue:** the docstring states "Read-only and total: it never raises", but the guard
catches only `(CvFactStoreError, OSError)`:

```python
try:
    load_facts(Path(settings.cv_dir) / CV_FILENAME)
except (CvFactStoreError, OSError):
    return RANK_SKIP_FACT_STORE
```

`load_facts` wraps the failures it knows about, but not every exception it can raise.
Proven with a deeply nested `cv.yaml` (a corrupt or hand-authored document is exactly
the input this probe exists for):

```
report deep: OK (total)                      # fact_store_report catches Exception
skip_reason deep RAISED: RecursionError maximum recursion depth exceeded
```

So the sibling helper `fact_store_report` (`app/cv/factstore.py:104-110`) is total
while `ranking_skip_reason` is not, even though the latter is the one whose contract
claims it. In `run_pipeline` the raise is swallowed by the ranking block's broad
handler, so the run still finishes — but it is persisted with
`{"status": "skipped", "reason": "rank_start_failed"}` and an error, and the queue
strip then tells the user "Ranking skipped — the pass could not be started" when the
real cause is an unreadable/unparseable CV fact store. It also means
`start_ranking_task` is never reached on that path. `run_ranking`'s own guard
(`rank.py:417`) has the same narrow catch, so any future caller that bypasses the
precheck lets the exception escape the detached task unretrieved.

**Fix:** add a catch-all, mirroring `fact_store_report`:

```python
    try:
        load_facts(Path(settings.cv_dir) / CV_FILENAME)
    except (CvFactStoreError, OSError):
        return RANK_SKIP_FACT_STORE
    except Exception:  # noqa: BLE001 — the probe is total; a broken store is a skip
        return RANK_SKIP_FACT_STORE
    return None
```

### Info

#### IN-01: The fact-store path expression is duplicated in five places, defeating the "surfaces cannot disagree" claim

**File:** `app/pipeline/rank.py:109`, `app/pipeline/rank.py:416`,
`app/web/routes.py:100`, `app/api/listings.py:122`, `app/api/settings.py:170`,
`app/api/health.py:85`

**Issue:** `Path(settings.cv_dir) / CV_FILENAME` is rebuilt independently at each
surface. The 05-10 write-up says the path "is computed once … shared by the Settings
card, the queue line and `/health`, so no surface can disagree" — what is shared is the
*probe function*, not the path construction. A future change to the filename or its
resolution must be made in five places or the surfaces drift, which is the exact
failure the design claims to prevent.

**Fix:** add one `def fact_store_path() -> Path` (in `app/cv/factstore.py` or
`app/pipeline/rank.py`) returning `Path(settings.cv_dir) / CV_FILENAME` and import it
at all five sites.

#### IN-02: `fact_store_report`'s first `except` clause is redundant

**File:** `app/cv/factstore.py:104-110`

**Issue:** `except (CvFactStoreError, OSError)` and the following `except Exception`
have byte-identical bodies; the first only narrows which exceptions are *named*, since
the second would catch the same ones anyway. It reads as if the two branches differ.

**Fix:** collapse to a single `except Exception as exc:  # noqa: BLE001 — a report must never raise`.

#### IN-03: The queue's CV status line asserts "ranking is skipped" even when ranking is switched off or already ranked

**File:** `app/web/templates/html/_health_strip.html:21-30`

**Issue:** the line is unconditional and states "No readable CV fact store at … —
ranking is skipped until one is supplied." When `Settings.ranking_enabled` is false,
ranking is off rather than blocked on the CV, and when a prior run already scored the
queue it is not unranked. The sentence is honest for the common fresh-checkout case
but overstates for those two.

**Fix:** pass `ranking_enabled` into the strip context and either omit or soften the
sentence when ranking is disabled (e.g. "ranking is turned off in Settings").
Low priority; the wording is not load-bearing.

#### IN-04: A cap-read failure discards the entire ranking strip, including the persisted marker

**File:** `app/web/routes.py:319-332`

**Issue:** `_ranking_strip` builds `ranked`/`candidates`/`state`/`reason` and
`cap_reason` in one dict inside a single `try`; any failure — including one in the
unrelated `llm_call_repo.rank_cap_reason_for_run` read — returns `{}`, so the strip
vanishes even though the marker and numerator were available. The convention is to
degrade the strip, not to drop the disclosure it exists to provide.

**Fix:** compute `cap_reason` in its own guarded read (falling back to `None`) so a
cap-read failure only drops the `— cap reached (…)` suffix.

#### IN-05: `/health` and the HTML surfaces disclose the absolute fact-store path

**File:** `app/api/health.py:85`; `app/api/settings.py:170`; `app/web/routes.py:100`;
`app/api/listings.py:122`

**Issue:** `cv.path` (e.g. `/cv/cv.yaml`) is returned from the unauthenticated (v1 has
no auth, D-21) `/health` JSON and rendered on the queue, settings and detail pages.
The path is server-derived and low-sensitivity, and disclosing it is the point of the
G-05-2 disclosure work — so this is accepted by design, not a vulnerability. Noted
only so it is a conscious decision when the Authentik step lands and `/health` stops
being local-only.

**Fix:** none required now; revisit at the auth milestone (keep `/health` behind the
same seam as the other routes, or report only the basename).

---

_Reviewed: 2026-09-23T13:12:15Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
