---
phase: 02-clean-filtered-queryable-queue
reviewed: 2026-09-16T12:50:40Z
depth: standard
files_reviewed: 66
files_reviewed_list:
  - alembic/versions/0002_queue_filter_and_run_reason.py
  - app/api/events.py
  - app/api/runs.py
  - app/api/searches.py
  - app/config.py
  - app/db/models.py
  - app/db/repositories/dupe_repo.py
  - app/db/repositories/event_repo.py
  - app/db/repositories/exclusion_repo.py
  - app/db/repositories/queue_repo.py
  - app/db/repositories/run_repo.py
  - app/db/repositories/search_repo.py
  - app/db/repositories/state_repo.py
  - app/domain/criteria.py
  - app/domain/dedup.py
  - app/domain/filter.py
  - app/domain/run_reason.py
  - app/domain/sanitize.py
  - app/domain/search_query.py
  - app/main.py
  - app/pipeline/dedup_stage.py
  - app/pipeline/filter_stage.py
  - app/pipeline/run.py
  - app/web/routes.py
  - app/web/templates/html/_listing_row.html
  - app/web/templates/html/criteria.html
  - app/web/templates/html/merges.html
  - app/web/templates/html/queue.html
  - app/web/templates/html/queue_list.html
  - app/web/templates/html/runs.html
  - pyproject.toml
  - requirements.txt
  - tests/api/test_criteria_capabilities.py
  - tests/api/test_listing_events.py
  - tests/api/test_merges_view.py
  - tests/api/test_queue_excluded.py
  - tests/api/test_queue_search.py
  - tests/api/test_queue_signals.py
  - tests/api/test_run_history.py
  - tests/api/test_run_reason.py
  - tests/api/test_searches_crud.py
  - tests/db/test_dupes.py
  - tests/db/test_exclusions.py
  - tests/db/test_listing_events.py
  - tests/db/test_migration_contract.py
  - tests/db/test_no_pii_columns.py
  - tests/db/test_orm_drift.py
  - tests/db/test_queue_state.py
  - tests/db/test_search_repo_writes.py
  - tests/db/test_skeleton_boot.py
  - tests/domain/test_criteria.py
  - tests/domain/test_dedup.py
  - tests/domain/test_filter.py
  - tests/domain/test_injection_patterns.py
  - tests/domain/test_run_reason.py
  - tests/domain/test_search_query.py
  - tests/pipeline/test_capability_surface.py
  - tests/pipeline/test_criteria_snapshot.py
  - tests/pipeline/test_dedup_merge.py
  - tests/pipeline/test_dedup_revert.py
  - tests/pipeline/test_filter_stage.py
  - tests/pipeline/test_ingest_e2e.py
  - tests/pipeline/test_single_search_run.py
  - tests/test_config.py
  - tests/test_dependency_pins.py
findings:
  critical: 1
  warning: 6
  info: 12
  total: 19
status: issues
---

# Phase 02: Code Review Report

**Reviewed:** 2026-09-16T12:50:40Z
**Depth:** standard
**Files Reviewed:** 66
**Status:** issues

## Summary

Phase 02's change set is the ten plan commits on top of the Phase-1 completion
(`f5cf20a`). Scope was taken from the ten `02-*-SUMMARY.md` `key-files` blocks and
cross-checked against `git diff --name-only f5cf20a..HEAD`: the two agree exactly
(66 non-planning files), so no changed file was omitted.

What holds up well, verified by reading the code rather than the summaries:

- **Append-and-mark is real.** `dupe_repo.py` only ever INSERTs `listing_dupes`; the
  only mutation is `revert_merge`'s UPDATE of `reverted_at`/`reverted_by`. Both the
  survivor and the twin are left in `listings`, `listing_sources` is never touched,
  and `apply_merge` writes blanks only (`_is_blank` covers `None` and `""`, so `0` and
  `False` are preserved). Snapshot-restore is symmetric with the fill map.
- **Both-orientation negative memory works.** `reverted_pairs`/`merged_pairs` add both
  directions, which the ordered `uq_listing_dupes_pair` index cannot cover by itself,
  and `dedup_stage` consults both before scoring.
- **Append-only events hold.** `event_repo` exposes no UPDATE/DELETE; the projection
  (`_fold_events`) and the SQL predicates (`latest_event_type_in`) are two expressions
  of the same event-pair grouping, which fixes the placeholder bug the summary claims.
  The route never accepts `occurred_at`.
- **FTS5 hygiene is correct.** `MATCH` is a bound parameter; the transform is
  per-token quoted and I reproduced every hostile input against the real FTS5 parser;
  both order branches carry a unique tie-break; `limit` is settings-only.
- **The filter path is genuinely LLM-free and pure**, and the migration is additive.

The defects below cluster in the *read/report* surfaces rather than the write path:
the merge-rate statistic mixes two different windows, one UIs the swapped-row path
wrongly, one singleton table has no uniqueness to back its race handling, and one
route lets a database FK violation escape as a 500.

Evidence run: `ruff check app tests` → clean; full suite → **584 passed, 2 deselected**
(102.7 s). Both checks are green, which is precisely why the window-mixing bug in
CR-01 is worth flagging: the tests only ever seed a single run.

## Critical Issues

### CR-01: Merge rate divides an all-time merge count by the *latest run's* fetched count

**File:** `app/db/repositories/dupe_repo.py:456-488` (rendered at `app/web/templates/html/merges.html:19-23`)
**Issue:** `merge_rate()` computes

```python
merged = count(listing_dupes where reverted_at IS NULL)      # no run window at all
...
latest = select(Run).order_by(Run.started_at.desc(), Run.id.desc()).limit(1)
fetched = latest.fetched_count
```

so the numerator is every un-reverted merge ever recorded while the denominator is the
single latest run's `fetched_count`. The page labels the result as the **latest run's**
rate (`MergeRate.window` → `"latest run (#{id})"`, template line 19) and QUEUE-09 asks
for "the merge rate … with the window named". After a second run the number is
arithmetically wrong and can exceed 100%. Reproduced directly against the shipped
class:

```
MergeRate(merged=5, reverted=0, fetched=3, run_id=2).rate  ->  167
                           window -> "latest run (#2)"
```

The proof that this is a bug and not the intended all-time aggregate: the repository
already ships `count_merges_for_run(session, run_id=...)` — a windowed count written
for exactly this purpose — and `merge_rate` does not call it (see IN-01).
`tests/api/test_merges_view.py` never catches it because `_seed_run` creates exactly
one run, so numerator and denominator always share a window.

**Fix:** window the numerator to the latest run (and reuse the existing helper):

```python
if latest is not None:
    run_id = int(latest.id)
    if latest.fetched_count is not None:
        fetched = int(latest.fetched_count)
    merged = await count_merges_for_run(session, run_id=run_id)
    reverted = int(await session.scalar(
        select(func.count()).select_from(ListingDupe)
        .where(ListingDupe.reverted_at.is_not(None), ListingDupe.merged_at >= latest.started_at)
    ) or 0)
```

Alternatively keep the all-time numerator but compute `fetched` over the same all-time
window and drop the "latest run" label — do not ship a rate whose window label and
operands disagree. Add a two-run test so the mixed window cannot regress.

## Warnings

### WR-01: The last-run strip's `try` does not cover the render, so a decorative strip can still 500 the queue

**File:** `app/web/routes.py:162-171`
**Issue:** The docstring promises "never raises. A decorative strip must not 500 the
product page", but only the `run_repo.list_runs` call is inside the `try`. The
`render_run_fragment(...)` call is the line *after* the `except` block, so any template
rendering failure (a hand-edited/older `stage_log_json`, a `source_counts_json` shape
the partial cannot traverse) escapes as a 500 on `GET /` — the product page — which is
exactly the failure mode the guard exists to prevent. `_health_strip` (lines 61-73)
correctly wraps both of its fallible calls; this one does not.
**Fix:**

```python
    try:
        runs = await run_repo.list_runs(session, limit=1)
        latest = runs[0] if runs else None
        if latest is None:
            return None, None
        fragment = Markup(render_run_fragment(request, latest, latest.sources))
    except Exception as exc:  # noqa: BLE001 — decorative data must not 500 the queue
        log.warning("queue.last_run_read_failed", error=type(exc).__name__)
        return None, None
    return latest, fragment
```

### WR-02: The swapped row's action URL drops the active filter set, so a second click desynchronises the Excluded column

**File:** `app/api/events.py:144-146` and `app/web/templates/html/_listing_row.html:51`
**Issue:** The standalone row render passes only `row` and `show_excluded`:

```python
return templates.TemplateResponse(
    request, ROW_TEMPLATE, {"row": row, "show_excluded": query.excluded}
)
```

but the partial derives the action URL from `queue_query`:

```jinja
{% set action_url = "/listings/" ~ row.id ~ "/events" ~ ("?" ~ queue_query if queue_query else "") %}
```

`queue_query` is undefined in the standalone context (Jinja's default `Undefined` is
falsy, so no error is raised and the query string is silently dropped). Concrete
failure mode: with `?excluded=1`, the page renders
`/listings/5/events?excluded=1`; the first click's response (rendered standalone)
contains a row whose form posts to `/listings/5/events` with no query string; the
second click therefore reaches the route with `excluded` absent, `show_excluded` is
`False`, and the response omits `<td class="listing-exclusion">`. With `?excluded=1`
the table header still has the "Excluded by" column, so the swapped row now has one
fewer cell than its header. `tests/api/test_listing_events.py` never posts with
`?excluded=1` and never asserts the action URL, so this is untested.
**Fix:** pass the query string through, and build the URL from the same `QueueQuery`
the route already constructs:

```python
# app/api/events.py
return templates.TemplateResponse(
    request,
    ROW_TEMPLATE,
    {"row": row, "show_excluded": query.excluded, "queue_query": query.query_string()},
)
```

### WR-03: `queue_state` has no uniqueness constraint, so the "racing insert" handling can never fire — and a race creates a second, ignored watermark row

**File:** `app/db/repositories/state_repo.py:68-78`; schema at `alembic/versions/0002_queue_filter_and_run_reason.py:82-87` and `app/db/models.py:97-108`
**Issue:** `advance_watermark` creates the singleton row inside a SAVEPOINT and catches
`IntegrityError` with the comment "a concurrent writer won the race; re-read instead".
The `queue_state` table has **no unique/CHECK constraint on anything but the primary
key**, so two concurrent first-inserts both succeed with `id=1` and `id=2`; no
`IntegrityError` is ever raised, and the `except` branch is dead. `_load` then orders
by `QueueState.id` and takes the first, so the second row (and any later write routed
to it) is silently ignored — "new since last visit" can freeze at the older watermark
until the process restarts. Two writers are improbable at `--workers 1`, but the code's
stated protection does not exist, which is worse than not claiming it.
**Fix:** make the singleton real — e.g. add a `CHECK (id = 1)` (or a dedicated
`singleton INTEGER NOT NULL DEFAULT 1 UNIQUE`) in a follow-up migration and insert with
`id=1`, so the `IntegrityError` path becomes reachable; otherwise delete the
`try/except IntegrityError` and document the single-writer assumption honestly.

### WR-04: The salary-floor error is rendered with the field name duplicated

**File:** `app/api/searches.py:184-186`
**Issue:** `_int_field` already returns a full sentence (`"salary floor must be a whole
number."`, from line 156) and `criteria_from_form` prefixes it again while *lowercasing*
the first character:

```python
errors.append("Salary floor " + salary_error[0].lower() + salary_error[1:])
```

which renders **"Salary floor salary floor must be a whole number."** — malformed
user-facing output from an operator/typo bug (`[0].lower()` was presumably meant to
capitalise a bare field name, not a complete sentence).
**Fix:** append the message as returned, or strip the duplicated prefix:

```python
errors.append(salary_error[0].upper() + salary_error[1:])
# -> "Salary floor must be a whole number."
```

### WR-05: One `criteria_version` is stamped onto every exclusion row for a listing, so another search's rule records the wrong version

**File:** `app/pipeline/filter_stage.py:117-131`
**Issue:** `criteria_version` is resolved from `outcomes[0]` (the first firing rule's
owning search) and then passed once to `record_exclusions`, which writes that single
value onto **every** row in the batch (one row per firing rule). When a listing is
rejected by two enabled searches' rules — the normal case under the documented A4 union
scope — the exclusion row belonging to search B's rule is persisted with search A's
`version`. That contradicts D-33's contract ("each `listing_exclusions` row records
`criteria_version`") and makes the stored per-row evidence wrong for exactly the
multi-search union this phase produces.
**Fix:** pass the version per outcome, e.g. give `RuleOutcome` an owning-search/version
lookup at write time:

```python
# filter_stage: build version per outcome, not once per listing
versions = {o.rule_id: version_by_search.get(search_id_by_rule.get(o.rule_id)) for o in outcomes}
# record_exclusions: accept a mapping and stamp row-by-row
```

At minimum, document that `criteria_version` is "the first firing rule's owning search"
rather than "this row's search", if the single value is intentional.

### WR-06: Posting a rule to a non-existent search escapes as a 500 instead of a 404

**File:** `app/api/searches.py:482-511` (write at `app/db/repositories/search_repo.py:621-656`)
**Issue:** Every other criteria route resolves the parent before writing
(`toggle_search_route`, `edit_search_route`, and `_owned_rule` for all rule
sub-routes), but `create_rule_route` never checks that `search_id` exists and only
catches `ValueError`. `create_rule` inserts a `FilterRule(search_id=...)` and flushes;
`PRAGMA foreign_keys=ON` is enforced (`app/db/session.py:38`, asserted by
`tests/db/test_pragmas.py`), so a crafted `POST /searches/9999/rules` raises
`sqlalchemy.exc.IntegrityError`, which is not caught and surfaces as a 500. The
`_not_found` helper already exists but is not used here, and no test covers the case.
**Fix:** resolve the parent first and reuse the existing 404 path:

```python
record = await search_repo.search_by_id(session, search_id)
if record is None:
    return await _not_found(session, "Unknown search.")
```

and/or catch `IntegrityError` alongside `ValueError`.

## Info

### IN-01: `count_merges_for_run` is dead code — and it is the windowed count `merge_rate` needed

**File:** `app/db/repositories/dupe_repo.py:227-249, 594`
**Issue:** Defined and exported, never called anywhere in `app/` or `tests/`
(`rg` finds only the definition and `__all__`). Its own query is also under-bounded:
`merged_at >= run.started_at` with no upper bound would count a later run's merges for
an earlier run if it were ever recomputed.
**Fix:** either call it from `merge_rate` (see CR-01) and add an upper bound
(`merged_at < run.finished_at` or the next run's `started_at`), or delete it.

### IN-02: `ExclusionRecord` and `exclusions_for_run` are dead code

**File:** `app/db/repositories/exclusion_repo.py:30-40, 122-147, 150-156`
**Issue:** Both are defined and exported but have no caller (`rg` finds only the
definition, the internal construction, and `__all__`). The exclusion detail surface
actually renders through `excluded_counts_for_run`/`rule_counts_for_listings`.
**Fix:** remove them, or wire `exclusions_for_run` into the run-detail page (the
`detail_json` surface currently has no consumer, which is itself worth a decision).

### IN-03: The per-rule counts query runs twice per queue page, and `_page_rule_counts` ignores its `query` argument

**File:** `app/db/repositories/queue_repo.py:365, 416, 512-521`
**Issue:** `read_queue` calls `_page_rule_counts(...)` at line 365, and `_enrich` (which
`read_queue` just called) already called it at line 416 — two identical
`excluded_counts_for_run` queries per request, each preceded by its own
`_latest_run_id_value` query. The `query` parameter of `_page_rule_counts` is never
read (the counts are run-scoped, not query-scoped).
**Fix:** compute the counts once in `read_queue` and pass them into `_enrich`; drop the
unused parameter or use it to decide whether counts are needed at all.

### IN-04: The stage log slices from the wrong end, so `criteria_compile` is the first entry dropped

**File:** `app/pipeline/run.py:708-716, 737`
**Issue:** `criteria_compile` is `insert(0, ...)`-ed with the comment "prepended because
it is chronologically first", then `_finish(..., stage_log=stage_log[-STAGE_LOG_MAX_ENTRIES:])`
keeps the **last** 12 entries. A run with more than nine sources (entries = one
`persist:<source>` each + `dedup` + `filter` + `criteria_compile`) loses the compile
entry — the one the prepend was designed to protect. Unreachable with today's two
adapters, but it is a latent ordering/logic defect.
**Fix:** prepend the compile entry *after* truncation, or reserve a slot for it:

```python
stage_log = [compile_entry, *stage_log[-(STAGE_LOG_MAX_ENTRIES - 1):]]
```

### IN-05: `filter.py`'s "never an excerpt of the listing's own text" contract is stronger than the code

**File:** `app/domain/filter.py:28-34` vs `261` (`location_norm`), `303/312/319` (`seniority`), `358` (`company_norm`)
**Issue:** The module docstring says every `detail` mapping carries "terms, field names,
counts and numbers only — never an excerpt of the listing's own text and never a
removed value". Three evaluators copy the listing's own field value into
`detail_json`. The review's specific privacy bar (no **description prose**) is met —
none of these is description text and none is PII — but the docstring overstates the
guarantee and T-02-02/T-02-07's mitigation claim leans on it.
**Fix:** either drop those values (the `matched`/`term`/count is enough evidence) or
narrow the docstring to "never description text, never a removed PII value".

### IN-06: `_in_scope` casts a text column to INTEGER, breaking the module's own Postgres substitution story

**File:** `app/db/repositories/queue_repo.py:237-250`
**Issue:** `cast(ListingExclusion.rule_id, Integer) == scoped.id` joins a `String(64)`
column to an integer PK. On SQLite a non-numeric `rule_id` silently casts to `0` and
simply never matches (`_rule_kinds` guards against this by `.isdigit()`-filtering, so
the two disagree about what is a valid id); on Postgres — which the module docstring
explicitly designs for — `CAST(text AS integer)` raises on non-numeric input.
**Fix:** store/join the rule id as an integer (`listing_exclusions.rule_id` values are
always `str(FilterRule.id)` today, so an `Integer` column with a text column kept for
display would be cleaner), or guard the cast with a numeric test.

### IN-07: `_UrlForm.__len__` returns the number of pairs, not the number of keys

**File:** `app/api/searches.py:107-108`
**Issue:** The class subclasses `Mapping[str, str]` and `__iter__` deduplicates names,
but `__len__` returns `len(self._pairs)`, so `len(form)` can exceed the number of keys
`iter(form)` yields — a `Mapping` contract violation for repeated keys
(`keyword_fields`). No current caller uses `len()`, so the impact is latent.
**Fix:** `return len(set(name for name, _ in self._pairs))`.

### IN-08: `delete_rule` ignores its caller's clock

**File:** `app/db/repositories/search_repo.py:706-719`
**Issue:** Every other Phase-2 write takes `now: datetime` so a test can pin it;
`delete_rule` has no `now` parameter and internally calls `datetime.now(UTC)` at line
713 before bumping the version. This is the one non-deterministic write in a module
whose docstring is built on determinism.
**Fix:** add `now: datetime` and pass `search_id_by_rule`-style context through, as
`update_rule`/`create_rule` do.

### IN-09: `include_reverted` is a dead option on `list_merges`

**File:** `app/db/repositories/dupe_repo.py:372-395`
**Issue:** The parameter defaults to `True` and no caller ever passes `False`
(`rg` finds only the definition and the docstring). The page always lists reverted rows
(which is the intended audit behaviour), so the branch is untested dead code.
**Fix:** remove the parameter, or add the "merges currently in force" filter as a real
page control and test it.

### IN-10: The queue and merges pages display the *normalised* company string, not the human company name

**File:** `app/db/repositories/queue_repo.py:440`, `app/db/repositories/dupe_repo.py:365`
**Issue:** Both read models surface `Listing.company_norm` for display.
`normalise_company_name` casefolds and strips punctuation and legal suffixes
(`app/domain/listing.py:67-74`), so the UI shows `acme` / `acme holdings` rather than
the board's `Acme` / `Acme Holdings Ltd`. The human-readable name is available via the
existing `Listing.company_id → companies.name` join; nothing on the read path uses it.
**Fix:** join `Company.name` (falling back to `company_norm`) in `_enrich`/`list_merges`
and render that.

### IN-11: "merged from N sources" counts absorbed listings, not sources

**File:** `app/web/templates/html/_listing_row.html:34` with `app/db/repositories/dupe_repo.py:556-582`
**Issue:** `merge_summary_for_listings` returns a count of un-reverted absorbed
**listings**, but the badge text says "merged from {{ row.merged_from }} sources". A
twin seen on two boards still counts as 1; a survivor plus one twin from one board
reads as "merged from 1 sources". D-26/D-29's whole point is an honest merge story.
**Fix:** rename the badge to "merged with N listing(s)" or compute a distinct-source
count by joining `listing_sources` through the absorbed ids.

### IN-12: `events.py` reaches into `app.api.searches` for the form parser

**File:** `app/api/events.py:34`
**Issue:** `from app.api.searches import read_form` couples the listing-event router to
the criteria router, which in turn imports `run_pipeline`/`resolve_enabled_adapters`
and therefore the whole pipeline + source registry. Importing the small events router
now pulls in the pipeline entrypoints.
**Fix:** move `read_form`/`_UrlForm` into a shared `app/api/forms.py` (or
`app/web/forms.py`) so both routers depend on the helper rather than on each other.

### IN-13: No CSRF token on state-changing POSTs

**File:** `app/api/searches.py` (`/searches/*`), `app/api/events.py` (`/listings/{id}/events`), `app/api/runs.py` (`/runs`, `/merges/{id}/revert`)
**Issue:** All mutating routes are cookie-less but also token-less, so a page the user
visits could POST to `http://localhost:<port>/...` and save/hide listings, delete
searches, or start runs. This is consistent with the project's explicit "Auth: none in
v1" decision and every route does carry the required `current_user` seam (verified by
`tests/test_auth_seam.py`), so it is recorded as an accepted-risk observation rather
than a phase defect.
**Fix (when auth lands):** require an `Origin`/`Referer` check or a double-submit token
on the POST surface; the HTMX forms make a single shared `hx-headers` token cheap to add.

---

_Reviewed: 2026-09-16T12:50:40Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
