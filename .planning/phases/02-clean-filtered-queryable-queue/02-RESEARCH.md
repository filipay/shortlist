# Phase 2: Clean, Filtered, Queryable Queue — Research

**Researched:** 2026-09-16
**Domain:** SQLite FTS5 search, fuzzy cross-source dedup, deterministic hard-rule filtering, reversible merge audit, run explainability, HTMX/Jinja partials
**Confidence:** HIGH on in-repo schema/code facts and FTS5 mechanics (read + executed this session); MEDIUM on the fuzzy-scoring recipe and the resume-matcher pattern reuse; LOW on θ, the merge-rate band, and run-row shape

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-25:** **High-confidence matches merge automatically during the run** — no propose-and-confirm review queue. Undoing the *user-visible* half means reworking the ingest stage and the queue/merge UI, but the triggering rationale is the daily-loop cost: "High confidence matches merge automatically." — **Reversibility:** costly — reverting to propose-and-confirm touches the dedup stage, the queue read model and the merge UI, and any listings already merged would need unpicking via the snapshot.
- **D-26:** **A full, inspectable record of the merged twin is retained and surfaced in the job's detail view.** The user's words: "Do maintain a record of what the job listing was so that the user can inspect themselves. Maybe show it in the details of the job." Implemented via `listing_dupes.snapshot_json` (column already ships in migration 0001), shown as "merged from N sources" with the twin's original fields.
- **D-27:** **First-seen listing stays canonical; blanks are filled from the twin; nothing non-null is ever overwritten.** The listing that arrived first keeps title, company and `canonical_url`; a later matching source only contributes to NULL/empty fields (salary, location, description). — **Reversibility:** costly — a later switch to source-priority or per-field precedence rewrites already-merged listings; the snapshot makes the data recoverable, but the rule change touches every merged row.
- **D-28:** **Revert = full undo + negative memory.** Reverting restores the surviving listing's snapshot fields, un-hides the twin and marks `listing_dupes.reverted_at`; the pair is recorded as deliberately-distinct so the next run does not silently re-merge it.
- **D-29:** **Dedicated Merges audit view + merge-rate stat**, with one-click revert; job detail also shows "merged from N sources" with the snapshot. Satisfies QUEUE-09 directly ("see the merge rate and the rows behind it") and gives revert a home. — **Reversibility:** reversible.
- **D-30 (agent discretion):** **Merge timing** — Tier-2 dedup runs as a **post-persist stage inside `run_pipeline()`** (after all sources' rows are persisted), not inline per source, because a cross-source candidate pair needs both rows to exist before it can be scored. Consistent with `research/ARCHITECTURE.md` §8.1 (dedup placement).
- **D-31 (agent discretion):** **Tier-2 algorithm** — `rapidfuzz` token-set ratio over the normalised `(company, title, location)` tuple already produced by `app/domain/listing.py` (`normalise_company_name`, `title_norm`, `company_norm`, `location_norm`), with `listings.blocking_key` (indexed) used to narrow candidates before scoring. **θ is a Settings value with a tuning task against the first real corpus, never a frozen constant** (ROADMAP Phase 2 Notes + STATE.md Phase-2 blocker). `rapidfuzz` is not yet declared in `pyproject.toml` — it must be added deliberately. — **Reversibility:** reversible.
- **D-32:** **One unified named search carries both the fetch query and its own exclusion rules.** A named search (e.g. "Dublin Python, remote, €70k+") holds keywords / location / remote / salary floor / seniority **and** its exclusion rules; enabling it adds it to the run, and the queue unions all enabled searches (scope-to-one supported). Reuses `searches.criteria_json` + `searches.enabled` + `searches.is_default`. — **Reversibility:** costly — splitting later into "searches fetch, one global filter set" would re-home every rule and rework the criteria + queue UI.
- **D-33:** **Past-run reproducibility = criteria snapshot stored on each run + `searches.version` bumped on edit.** No version-history table and no diff/rollback UI in v1: a run row carries the exact query+rules it used, and each `listing_exclusions`/`scores` row records `criteria_version`. — **Reversibility:** reversible — adding a `criteria_versions` history table later is additive.
- **D-34:** **Filter rules are typed rows in a new `filter_rules` table** (migration 0002): `kind` (`salary_floor` | `exclude_keyword` | `location` | `remote` | `seniority` | `company_blocklist`), `params_json`, `enabled`, ordering, and a `search_id` FK. The UI renders a purpose-built **form per kind** — no raw JSON editor, no Jinja in any logic position. Evaluators are **pure functions in `app/domain`** (the domain-import-discipline test forbids I/O there). Every rejection writes `listing_exclusions(rule_id, rule_kind, detail_json, run_id)`.
- **D-35:** **"Why was this excluded" is an inline `Show excluded` toggle on the queue** — rejected listings appear dimmed with a chip naming the firing rule and a per-rule count; excluded listings are out of the default view and out of any future LLM spend. Satisfies FILT-03 without a second browsing surface.
- **D-36:** **Rules are re-evaluated from scratch every run; exclusions are per-run observations, not permanent blacklist state.** One `listing_exclusions` row per listing+run+rule (full history, per-rule counts per run). Retuning a rule can bring a previously-excluded listing back into the queue; a listing the board no longer returns simply stops appearing.
- **D-37 (carried, pre-answered):** The **criteria compiler must consume each adapter's declared capabilities so an unsupported filter is reported, not silently ignored** (ROADMAP Phase 2 Notes; SRC-09). `compile_query_for_source()` + `CapabilityWarning` already ship in `app/sources/base.py` and are currently unconsumed — Phase 2 consumes them.
- **D-38 (carried, pre-answered):** Extend `app/domain/sanitize.py` with an **`_INJECTION_PATTERNS`-style injection rule set**, exactly as deferred from Phase 1 (ROADMAP Phase 2 Notes): pattern-copied from Resume-Matcher's `improver.py`, **attributed per Apache-2.0 §4**. The existing `looks_like_instructions` / `INSTRUCTION_MARKERS` seam is the insertion point.
- **D-39:** **"New since last visit" is a DB watermark** — `last_queue_view_at` in a small user-state row, updated when the queue is opened, plus an explicit **"Mark all as seen"** action that advances it deliberately. Cross-device, restart-safe and assertable in the DB-backed test harness (a cookie was explicitly rejected). — **Reversibility:** reversible.
- **D-40:** **Stale = `last_seen_at` older than a configurable `stale_after_days` (default ~14) OR `is_active = false`.** Robust to partial runs and board pagination (SRC-05); reuses existing columns. Stale rows get a badge but stay searchable.
- **D-41:** **Save and Hide are distinct actions**, written as **append-only `listing_events`** (event types already exist: `save`/`unsave`/`hide`/`unhide`/`shortlist`/`view`) with current state projected from the latest event. Hidden listings leave the default queue and are reachable via a `Hidden` filter with one-tap undo; saved listings get a `Saved` filter and a star. The Phase-1 append-only triggers are reused unchanged.
- **D-42:** **FTS5 MATCH over `title` + `company_norm` + `description`** (the existing `listing_fts` external-content table), ranked by **bm25 only when a query is present**; with no query the queue keeps the deterministic recent-first order the Phase-1 tests pin (`first_seen_at desc, id desc`). Pagination is HTMX "Load more"; **MATCH uses bound parameters only** (established FTS discipline). Search stays inside the active criteria scope and respects the Hide / Show-excluded toggles.
- **D-43:** **Dedicated `/runs` page** — one row per run (started/finished, trigger `manual|schedule`, per-source fetched, `deduped_count`, `filtered_count`, errors, duration) expandable to detail — plus a compact **last-run strip on the queue** linking there. Gives RUN-04 a real surface and makes the existing (partly unwritten) `runs` counters meaningful. — **Reversibility:** reversible.
- **D-44:** **A thin/empty queue is explained by a persisted structured reason + counts + a rendered sentence**, plus a **collapsible raw stage log**. Reason enum at minimum: `no_sources_enabled` | `all_sources_failed` | `zero_fetched` | `all_filtered` | `nothing_new` | `mixed`, each with the counts behind it (per-source fetched/blocked, filtered-by-rule breakdown, duplicates-already-seen). Computed **deterministically — no LLM** (Phase 3 is not available yet).
- **D-45:** **"Run search now" runs every enabled search**; the criteria page additionally offers a per-search **"Run this one"** action for iterating on a single query. No picker dialog on the main trigger (stays one tap). The planner decides the `runs`-row shape when several searches run (one run per search vs one run with per-search sections).
- **D-46:** Stack and schema are locked: Python 3.13, FastAPI 0.141.1, uvicorn `--workers 1`, SQLite WAL + SQLAlchemy 2.0 + Alembic, **FTS5 external-content (`porter unicode61`)**, Jinja2 + HTMX + Alpine + Tailwind (no CDN). Tier-1 upsert is the two-key design; `current_user` is on every route with **no `user_id` columns in v1**; `run_pipeline()` is the single pipeline callable; filtering is deterministic and precedes any LLM; `app.domain.*` imports no I/O. (Phase-1 D-17…D-24.)
- **D-47:** Migration 0001 already ships the Phase-2 scaffolding — `listing_dupes` (with `snapshot_json`/`reverted_at`), `listing_exclusions`, `listing_events` with append-only triggers, `searches` (+`version`), the `runs` counters, `listings.blocking_key`, and `listing_fts` + its triggers — but **none of the Phase-2 behaviour, repositories, routes, settings or templates exist**.

### the agent's Discretion
- Exact **θ default** and the tuning procedure (D-31); whether the fuzzy score or the normalised-tuple match is the primary gate; the **rules-in-a-blocking-window** candidate strategy.
- **Merge stage placement and ordering** within `run_pipeline()` (D-30) and how a merge interacts with the run's `deduped_count`.
- The exact **`_INJECTION_PATTERNS` catalogue** (D-38) and which identifiers are dropped vs hashed.
- The **`runs`-row shape when multiple searches run** (one run per search vs one run with per-search sections), and the "Run this one" URL/route shape (D-45).
- **Run-history retention/pruning** policy, queue **page size**, and the exact default rule vocabulary shipped on day one.
- Whether **`Show excluded`** also lists excluded-but-merged rows, and how `Load more` interacts with the excluded toggle (D-42).

### Deferred Ideas (OUT OF SCOPE)
- **Cross-source "also seen on…" links (SRC-12)** — v2, not Phase 2. The Merges audit view and the job-detail "merged from N sources" snapshot are the in-phase equivalents; they audit a merge, they are not the v2 cross-linking feature.
- **Adzuna adapter (SRC-11)** — v2; promoted from hedge to primary only if the Phase-1 survival verdict says LinkedIn/Indeed do not survive (decided at Phase 8, D-04).
- **Ranking, scoring, rationale (Phase 5)** — Phase 2 filters and cleans only; it makes no LLM call.
- **CV fact store / LaTeX compile (Phase 4, parallel) and tailoring (Phase 6)** — untouched here.
- **Application tracker (Phase 7)** — Save/Hide are queue signals, deliberately not application stages (D-41).
- **Scheduling, next-run display, UI health endpoint, phone-first pass (Phase 8)** — Phase 2 keeps the manual trigger and the desktop-first layout.
- **Criteria version-history table with diff/rollback** — consciously deferred (D-33); the snapshot-plus-version design keeps the option open.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUEUE-03 | Same job on two sources is merged, with a reversible audit record | §Q1 merge modelling; `listing_dupes` already in 0001 (`snapshot_json`, `reverted_at`, `reverted_by`); Tier-2 stage placement in `run_pipeline()` after persist (`run.py:338` before `_finish`) |
| QUEUE-04 | User can revert an incorrect merge | §Q1 revert = restore survivor fields from `snapshot_json` + set `reverted_at`/`reverted_by` + skip-pair negative memory; POST route + Merges audit view (D-29) |
| QUEUE-06 | User can full-text search the queue | §Q3 — verified MATCH/bm25/LIMIT-OFFSET mechanics against the real migrated DB; `build_match_expression()` pure sanitiser is mandatory (verified FTS5 syntax errors) |
| QUEUE-07 | Queue shows new-since-last-visit and stale | §Q2 watermark table + `stale_after_days` setting; `last_seen_at`/`is_active` already exist; per-search `searches.last_run_at` already exists |
| QUEUE-08 | Save/hide recorded as append-only events | §Q7 — event POST route + row partial; `listing_events` append-only triggers already enforced; current state projected from latest event (D-41) |
| QUEUE-09 | Merge rate and the rows behind it are visible | §Q1 merge-rate stat (`deduped_count`/`fetched_count`) + Merges audit view listing `listing_dupes` rows |
| CRIT-01 | Create/edit/delete named criteria | §Q2 `filter_rules` table; §Q4 form-per-kind (D-34); existing `searches` table reused |
| CRIT-02 | Criteria versioned so a past run is reproducible | §Q2 `runs.criteria_snapshot_json` + `listing_exclusions.criteria_version`; `searches.version` bumped on edit (D-33) |
| CRIT-03 | Enable/disable a saved search without deleting | `searches.enabled` already exists (`models.py:210`); repository + toggle route only |
| FILT-01 | Deterministic rules reject listings before any LLM call | §Q4 pure `app/domain/filter.py`; stage order dedup→filter, no LLM in Phase 2 at all |
| FILT-02 | Every rejection records which rule fired and why | §Q4 `listing_exclusions(rule_id, rule_kind, detail_json, run_id)` one row per firing rule per run (D-36) |
| FILT-03 | User can see why a listing was excluded | §Q7 `Show excluded` inline toggle + chip naming the firing rule + per-rule counts (D-35) |
| FILT-04 | Tune filter rules from the UI without a code change | §Q2 typed `filter_rules` rows + per-kind form; evaluators read `params_json`, no literals in code |
| RUN-03 | Every run records what it did / found / why the queue is empty | §Q5 `runs.reason` enum + `reason_counts_json` + collapsed `stage_log_json`; deterministic pure `compute_empty_reason()` |
| RUN-04 | User can see run history | §Q7 `/runs` page + last-run strip (D-43); `Run` model already carries every counter |
</phase_requirements>

## Summary

Phase 2 has almost no greenfield surface. Migration 0001 already ships every table
this phase needs (`listing_dupes`, `listing_exclusions`, `listing_events` with
append-only triggers, `searches` + `version`, `listing_fts` + its three triggers,
`listings.blocking_key` indexed, the `runs` counters) — so the work is *behaviour,
repositories, settings, routes and templates*, plus one small additive migration
0002 for what 0001 deliberately omitted (`filter_rules`, a last-visit watermark,
and the run-reason/criteria-snapshot columns). The single largest risk is not
capability but **guard churn**: four Phase-1 guard tests encode the *current*
schema and route surface, and every one of them must be updated **deliberately and
alongside** the change, or a correct implementation will read as a regression.

Three findings materially change how the phase should be planned, and all three
were produced by executing code this session:

1. **Safe FTS5 query construction is mandatory, not optional.** Raw user text
   handed to `MATCH` raises `sqlite3.OperationalError` on ordinary inputs —
   `-`, `OR`, `*`, `NEAR(`, `runner-up`, `it's`, an unbalanced quote. A queue
   search box wired straight to `MATCH` 500s on the first apostrophe. A pure
   `build_match_expression()` in `app/domain` (quote each token, join with `AND`,
   prefix the last) makes it total.
2. **`bm25()` alone is not a deterministic sort.** Two equal-scored rows came back
   `[1, 3]` in one query and `[3, 1]` in the next. Every FTS order must end
   `..., l.id DESC` or the "deterministic queue order" property Phase 1 pinned is lost.
3. **`fuzz.token_set_ratio` returns `100.0` when one string is a subset of the
   other** (official example: `"fuzzy was a bear but not a dog"` vs `"fuzzy was a
   bear"` → `100.0`). "Senior Software Engineer" and "Software Engineer" therefore
   score 100 — exactly PITFALLS P3's "merges two genuinely different roles at the
   same company". Token-set ratio must never be the only gate.

**Primary recommendation:** Build the phase in five seams with hard ordering:
(1) migration 0002 + guard updates together; (2) `app/domain/{filter,dedup,criteria,run_reason,search_query}.py`
as pure functions with unit tests first; (3) the five new repositories; (4) the two
pipeline stages (dedup then filter) plus capability-warning persistence; (5) the UI
partials. Do not write any HTMX partial before (2)–(4) have passing unit tests —
the first three findings above are all unit-testable in isolation and expensive to
debug through a browser.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fuzzy dedup scoring + merge decision | Domain (`app/domain/dedup.py`) | — | Pure, deterministic, unit-testable; D-24 forbids I/O in `app.domain` |
| Dedup candidate retrieval + merge write | Repository (`app/db/repositories/listing_dupe_repo.py`) | Domain (decision input) | Repositories are the only place SQL lives; the domain decides, the repo writes |
| Hard-rule evaluation | Domain (`app/domain/filter.py`) | — | D-34 mandates pure evaluators in `app.domain` |
| Rule storage / criteria CRUD | Repository + API/Web tier | — | `filter_rules` + `searches` writes; typed form per kind in Jinja |
| Criteria → per-source query compilation | Domain (`app/domain/criteria.py`) + `app/sources/base.py` compiler | Pipeline (`_fetch_one`) | `compile_query_for_source()` already ships; the compiler consumes `SourceCapabilities` (D-37) |
| Queue read model (visibility, ordering, pagination) | Repository (`app/db/repositories/queue_repo.py`) | — | One query, one place; keeps the route thin (existing `queue()` inline SQL moves here) |
| FTS5 search | Repository (`search/fts.py` port per §9.3) | Domain (`build_match_expression` is pure) | MATCH stays bound-parameter SQL; the *safety* transform is pure and testable |
| Save/hide/new-seen/stale projection | Repository (event projection + watermark) | Domain (stale predicate) | Append-only events + a watermark row; predicates are pure datetime maths |
| Empty-reason + merge-rate + stage log | Domain (`app/domain/run_reason.py`) | Pipeline (counts) + Repository (persist) | Deterministic by requirement (D-44: no LLM) |
| Queue / criteria / merges / runs UI | Web tier (Jinja + HTMX + Alpine) | API tier (fragment routes) | Phase-1 pattern: fragments rendered by `templates.TemplateResponse`, polling stopped on 286 |
| Last-visit watermark write | Web tier | Repository | Updated when the queue page is opened (D-39) |

## Key Design Answers (the phase's concrete uncertainties)

### Q1 — Tier-2 fuzzy dedup, merge modelling and revert

**Which ratio.** D-31 names token-set ratio; the *verified* behaviour of
`fuzz.token_set_ratio` is that it returns **`100.0` when one string is a subset of
the other, "regardless of extra content in the longer string"** — the official
example is `token_set_ratio("fuzzy was a bear but not a dog", "fuzzy was a bear")`
→ `100.0`. `[CITED: https://github.com/rapidfuzz/rapidfuzz/blob/main/docs/Usage/fuzz.rst]`
That makes token-set ratio alone unsafe here: `"Senior Software Engineer"` vs
`"Software Engineer"`, and `"Quantum Engineer"` vs `"Quantum Engineer - 12 month
contract"`, both score 100. This is precisely PITFALLS P3's failure mode
("merges two genuinely different roles at the same company — 'Software Engineer
II' vs 'Senior Software Engineer'"). `[CITED: .planning/research/PITFALLS.md:74-100]`

**Recommended gate (this is the agent-discretion half of D-31): make the
component-wise comparison the primary gate and the fuzzy score the tie/quality
signal — not the reverse.**

1. **Blocking.** Narrow candidates by an indexed equality, then score inside the
   block. Two usable blocking keys already exist in 0001:
   - `ix_listings_company_norm_title_norm` on `(company_norm, title_norm)`
     `[VERIFIED: alembic/versions/0001_initial_schema.py:408-410]` — its leading
     column makes a plain `company_norm = :norm` block index-usable, which is the
     realistic strategy; the same-company block is small.
   - `listings.blocking_key` (`f"{company_norm or ''}|{' '.join(title_tokens)}"[:255]`)
     `[VERIFIED: app/domain/listing.py:77-82]` is an **exact** key over the sorted
     title token set. Useful as a *fast path* for exact-tuple matches, but it does
     **not** narrow a drifted title (`"engineer software"` vs `"software engineer
     ii"` are different keys). Do not rely on it as the only blocker.
   - Add a genuine blocking-window guard: `posted_at` within ±N days (or
     `first_seen_at` in the same week bucket) — ARCHITECTURE §8.2 lists
     `posted_week` as part of the 2b key.
2. **Component gate (hard, all must pass).** `company_norm` equal, or
   `token_sort_ratio(company_norm_a, company_norm_b) >= company_threshold`;
   `location_norm` equal **or one side is `None`**; and a **seniority/grade
   conflict guard** — if exactly one title carries a grade token
   (`senior`, `sr`, `lead`, `staff`, `principal`, `head`, `chief`, `junior`,
   `intern`, `graduate`, `trainee`, `i`, `ii`, `iii`, `iv`) the pair is
   **never** merged. This guard is the cheapest defence against the P3 failure and
   belongs in `app/domain/dedup.py` as a pure predicate.
3. **Score.** Use `fuzz.token_sort_ratio` (word-order-insensitive, and *not*
   subset-forgiving — `token_sort_ratio("fuzzy was a bear", "fuzzy fuzzy was a
   bear")` → `83.87`, vs token-set's `100.0`
   `[CITED: rapidfuzz docs, same page]`) over the concatenated normalised tuple,
   and require it `>= θ` **in addition to** the component gate. Prefer the
   `min()` of the per-component scores over an average: an average lets a perfect
   company match hide a poor title match.
4. **θ** — a `Settings` value, 0–100 integer, default in the high-80s/low-90s
   (the corpus in `ARCHITECTURE.md` §8.2/STACK Q4 cites "~90"). **The default is
   `[ASSUMED]`** — STATE.md's Phase-2 blocker says it is untunable without a real
   corpus. It must be `Settings.dedup_fuzzy_threshold` (never a literal), and
   `tests/test_config.py`'s distinctive-literal scan already covers
   `app/pipeline` — so putting the default in `app/config.py` is what keeps that
   guard green.
5. **Tuning procedure (the "tuning task" D-31 requires).** A `dedup reconcile`
   operator command (script or route) that, with the threshold temporarily
   lowered to a floor (e.g. 70) and `dry_run=True`, prints **the pairs, not the
   rate** — PITFALLS P3 and ARCHITECTURE §8.4 both quote "every deduplication bug
   I've shipped looked perfectly reasonable as a percentage and obviously wrong as
   a list of titles". Record the tuned θ and the observed merge-rate band in
   `docs/` and in `STATE.md`; never bake the band into a test.

**Merge modelling.** Use the columns that already exist in 0001 — no migration
needed for the merge record itself:

| Column | Value |
|--------|-------|
| `listing_dupes.listing_id` | survivor (first-seen) |
| `listing_dupes.dup_listing_id` | absorbed twin |
| `listing_dupes.method` | `"fuzzy_tuple"` (also `"content_hash"`, `"canonical_url"` if those tiers land) |
| `listing_dupes.score` | the token_sort score (0–100) |
| `listing_dupes.snapshot_json` | **the survivor's pre-merge field values**, per ARCHITECTURE §8.3: "`snapshot_json` holds the pre-merge field values of the survivor so a revert restores them" `[CITED: .planning/research/ARCHITECTURE.md:803]` |
| `listing_dupes.merged_at` / `reverted_at` / `reverted_by` | audit trail |

`[VERIFIED: alembic/versions/0001_initial_schema.py:160-171]` confirms all six
columns exist, and `[VERIFIED: app/db/models.py:152-165]` mirrors them.

**Field union (D-27).** First-seen listing stays canonical; only fill blanks. That
is a `for field in _LISTING_FIELDS: if value is not None: setattr(...)` shape, but
with an explicit **empty-string-is-a-blank** rule (the existing Tier-1 upsert's
`_LISTING_FIELDS` loop treats `None` only — `[VERIFIED: app/db/repositories/listing_repo.py:37-60,112-126]`). Reuse that tuple; it already lists exactly the
fillable columns (`apply_url`, `location_raw`, `description`, `salary_*`,
`posted_at`, `source_extras_json`, …) and deliberately omits `title`,
`company_id`, `canonical_url`, `first_seen_at`, `content_hash`.

**Recommended: do NOT re-point `listing_sources` rows on merge.** ARCHITECTURE
§8.3 says "all `listing_sources` rows move to the surviving `listing_id`", but
moving rows makes revert a *data migration* rather than a flag flip, and it
destroys the absorber↔twin provenance the audit view wants. Leaving the rows on the
absorber and deriving "merged from N sources" via the `listing_dupes` join keeps
revert a pure `UPDATE listing_dupes SET reverted_at = ...`, which is a much safer
undo. This is a plan-level decision to surface explicitly (it amends §8.3 and
should be noted as such in the plan), not something to implement silently.

**Visibility predicate for absorbed twins.** There is **no `is_hidden` column** on
`listings` `[VERIFIED: app/db/models.py:68-112 — no such column]`, and D-41 says
hidden state comes from `listing_events`. The cleanest model: an absorbed twin is
excluded from the queue *because it has a `listing_dupes` row with
`reverted_at IS NULL`*, not because of a hide event. Revert then needs no
`unhide` event at all — the row becomes visible again the moment `reverted_at` is
set. Snap a `hide` event only if the plan wants the twin's disappearance to appear
in the event log for audit symmetry; it is not needed for correctness.

**Revert / negative memory (D-28).** Revert must:
1. restore the survivor's snapshot fields from `snapshot_json` (only those the
   merge actually changed — store both the pre-merge value and, defensively,
   which fields were written);
2. set `listing_dupes.reverted_at = now()` and `reverted_by = 'local'`;
3. make the next run skip the pair. The pair is *permanently* distinct: the dedup
   stage must filter out any candidate pair that has an existing `listing_dupes`
   row with `reverted_at IS NOT NULL` **in either orientation**
   (`(a,b)` or `(b,a)`). Since the merge fires automatically (D-25), this pre-check
   is load-bearing — without it a revert is undone by the next run.
   Recommend adding a `UNIQUE(listing_id, dup_listing_id)` index in 0002 **plus**
   the either-orientation pre-check (the unique index alone does not stop the
   reversed pair).

**`deduped_count` semantics.** `run.deduped_count` is currently mis-set to the
*created* count: `run.deduped_count = sum(int(c.get("created", 0)) for c in source_counts.values())`
`[VERIFIED: app/pipeline/run.py:248]`. It should become "rows absorbed by a
merge" (the count of `listing_dupes` rows written this run), and the merge rate
becomes `deduped_count / fetched_count`. Note `deduped_count == created` today is
asserted nowhere in the tests read this session, but the `/runs` page and the
Merges stat both read it, so the change must land with a test that pins the new
meaning.

### Q2 — Migration 0002 mechanics and the exact guard edits

**Mechanism.** A new file `alembic/versions/0002_<slug>.py` with
`revision = "0002"`, `down_revision = "0001"`. The environment already sets
`render_as_batch=True` and `compare_type=True` both online and offline
`[VERIFIED: alembic/env.py:38-71]`, so SQLite's `ALTER TABLE` limits are handled
by Alembic's batch/copy strategy where needed. Alembic runs on the **sync**
driver and the app on `aiosqlite`; migrations are therefore plain synchronous
`upgrade()` code — no `run_sync`, no async engine, no greenlet. The test harness
runs `python -m alembic upgrade head` as a subprocess with a `DATABASE_URL_SYNC`
override `[VERIFIED: tests/conftest.py:47-57]`, so 0002 is exercised automatically
by the session-scoped template fixture and needs **no** test-harness change.

SQLite specifics to respect `[CITED: https://sqlite.org/lang_altertable.html]`:
- `op.add_column` with a nullable column is a true in-place ALTER — use it for the
  new `runs` and `listing_exclusions` columns.
- Adding a `CHECK` constraint, changing `NOT NULL`, or adding a `UNIQUE` constraint
  requires the batch/table-recreation path — use `op.batch_alter_table(...)` (or a
  table create for new tables). **Name every CHECK explicitly** — the repo's own
  convention (an unnamed CHECK is silently dropped on recreation)
  `[VERIFIED: app/db/models.py:1-6]`.
- New tables go through `op.create_table`; server defaults must be `sa.text("1")`
  for booleans, matching 0001 `[VERIFIED: alembic/versions/0001_initial_schema.py:43,76,135]`.

**What 0002 must add (each is a required-by-D-item, not a nice-to-have):**

| Object | Columns | Requirement |
|--------|---------|-------------|
| `filter_rules` (new) | `id`, `search_id` FK→`searches.id`, `kind` String(32), `params_json` JSON, `enabled` Boolean NOT NULL server_default `1`, `position` Integer NOT NULL server_default `0`, `created_at`, `updated_at`; named CHECK `kind IN ('salary_floor','exclude_keyword','location','remote','seniority','company_blocklist')`; index `(search_id, position)` | CRIT-01, FILT-04, D-34 |
| `queue_state` (new, one row) | `id`, `last_queue_view_at` DateTime, `updated_at` | QUEUE-07, D-39 |
| `runs` (add) | `reason` String(32), `reason_counts_json` JSON, `stage_log_json` JSON, `criteria_snapshot_json` JSON | RUN-03, D-33, D-44 |
| `listing_exclusions` (add) | `criteria_version` Integer | CRIT-02, D-33 ("each `listing_exclusions`/`scores` row records `criteria_version`") |
| `listing_dupes` (add) | `UNIQUE(listing_id, dup_listing_id)` index; index on `dup_listing_id` | QUEUE-03/04 pre-check performance, negative memory |
| `searches` (no new column) | already has `enabled`, `is_default`, `criteria_json`, `version`, `last_run_at` | CRIT-03 free |

A named CHECK on `runs.reason` should be added (`reason IS NULL OR reason IN (...)`)
so an unknown reason cannot be persisted — matching the `ck_sources_health` /
`ck_runs_status` convention. Note this requires the batch path on an existing table;
if the plan wants to avoid a `runs` recreation, an alternative is to *not* constrain
it and assert the enum in `app/domain/run_reason.py` only. **Recommend the named
CHECK** because the enum is the product contract for "why is the queue empty".

**Guard edits — all four are mandatory and must land in the same plan task as the
migration, or the phase reads as a regression:**

1. `tests/db/test_migration_contract.py` — `test_alembic_at_revision_0001`
   asserts `versions == ["0001"]` `[VERIFIED: tests/db/test_migration_contract.py:267]`
   and `head_lines[0].startswith("0001")` `[VERIFIED: ...:278]`. Both become
   `"0002"`; the test must be renamed (e.g. `test_alembic_at_latest_revision`) and
   the module docstring's "9-item ROADMAP migration-0001 acceptance checklist"
   `[VERIFIED: ...:1-11]` reworded. Per the repo's own convention — "the migrated
   schema, not the model definitions: a model/DDL drift must fail here"
   `[VERIFIED: ...:6-9]` — **add** new items 10–13 asserting, via
   `PRAGMA table_info` / `sqlite_master`: `filter_rules` exists with its named
   CHECK; `queue_state` exists; the four new `runs` columns exist; and
   `listing_exclusions.criteria_version` exists. The Dockerfile assertion
   (`"alembic upgrade head" in dockerfile`) at `[...:280-283]` is unchanged.
2. `tests/db/test_no_pii_columns.py` — `EXPECTED_JSON_COLUMNS` is compared by
   **exact equality** against what `PRAGMA table_info` discovers
   `[VERIFIED: tests/db/test_no_pii_columns.py:93-118]`. It must gain
   `"filter_rules": frozenset({"params_json"})` and the three new `runs` JSON
   columns (`reason_counts_json`, `stage_log_json`, `criteria_snapshot_json`).
   `queue_state` has no JSON column, so it must **not** appear in the dict (the
   discovered-`==`-expected comparison drops empty entries on both sides at
   `[...:110-114]`). No new column may carry an email/phone-shaped name.
3. `tests/test_config.py` — not a schema guard, but the distinctive-literal scan
   covers `app/pipeline` `[VERIFIED: tests/test_config.py:57]`, so the new
   `dedup_fuzzy_threshold`, `dedup_posted_window_days`, `stale_after_days` and
   `queue_page_size` values must live in `Settings` and be read from there. If the
   defaults are distinctive integers `>= 3`, hard-coding any of them in
   `app/pipeline` fails the scan.
4. `app/db/models.py` — every new column/table must be mirrored. The contract test
   reads the DB, not the ORM, so ORM drift will surface as an application bug
   rather than a contract failure; mirror it in the same task to avoid that gap.

**Do NOT** touch the append-only triggers or the FTS5 objects — they are correct
and adding a fourth trigger or recreating `listing_fts` risks divergence. The
`listing_fts` extern-content index will pick up any new `listings` columns
automatically only if they are declared as FTS columns; since the searchable set is
pinned to `title, company_norm, description` by D-42, **no FTS change is needed**.

### Q3 — FTS5 external-content correctness (verified by execution)

Everything below was executed against a database produced by `alembic upgrade
head` on 0001 this session (the migration output and query results are the
evidence); the queries are the shape the plan should use verbatim.

**Verified working query shape:**

```sql
SELECT l.id, l.title, bm25(listing_fts) AS score
FROM listing_fts
JOIN listings l ON l.id = listing_fts.rowid
WHERE listing_fts MATCH :term
  AND l.is_active = 1
ORDER BY score, l.id DESC
LIMIT :limit OFFSET :offset
```

Results: a bound `:term` works; `bm25(listing_fts)` and the bare `rank` alias both
work in `ORDER BY`; the score is **negative, more-negative = more relevant**;
`bm25(listing_fts, 10.0, 5.0, 1.0)` accepts per-column weights in the FTS column
order `(title, company_norm, description)` — so title can outrank description
without a second query. `PRAGMA compile_options` reports `ENABLE_FTS5` in this
build (FTS3/4/5 all present).

**Finding 1 — `ORDER BY rank` alone is NOT deterministic.** Two rows with the
identical score `-1.375e-06` came back `[3, 1]` from the `bm25()` query and
`[1, 3]` from the `rank`-alias query. Any FTS ordering **must** append a unique
tie-break (`l.id DESC`). Without it, QUEUE-06 silently breaks the queue-ordering
determinism that Phase 1 pinned (`first_seen_at desc, id desc`).

**Finding 2 — raw user text in `MATCH` raises.** These ordinary inputs all raised
`sqlite3.OperationalError` against the real `listing_fts`:

| Input | Error |
|-------|-------|
| `-` | `fts5: syntax error near ""` |
| `a AND` | `fts5: syntax error near ""` |
| `"unbalanced` | `unterminated string` |
| `OR` | `fts5: syntax error near "OR"` |
| `*` | `unknown special query:` |
| `NEAR(` | `fts5: syntax error near ""` |
| `runner-up` | `no such column: up` |
| `it's` | `fts5: syntax error near "'"` |

Wrapping the term in double quotes fixed it (`'"runner-up"'` → clean). Therefore
QUEUE-06 **must** transform the user's text before it reaches `MATCH`, and that
transform is a **pure function** (perfect for `app/domain`, satisfying D-24):

```python
# app/domain/search_query.py  (pure: imports only re/dataclasses)
def build_match_expression(raw: str | None, *, prefix_last: bool = True) -> str | None:
    """Return a safe FTS5 MATCH expression, or None when there is no query.

    Each whitespace-separated token is double-quoted (FTS5's own escape for a
    literal term); internal quotes are doubled. Tokens are joined with AND and
    the last gets a trailing '*' for prefix matching. Total: never raises, and
    returns None for an empty/whitespace-only query so the caller can skip the
    FTS join entirely and keep the deterministic recent-first order (D-42).
    """
```

A `None` return is the D-42 "no query present → deterministic order, no `bm25`"
branch. Empty/whitespace queries must **skip the FTS join**, not `MATCH ''`.

**Pagination.** `LIMIT :limit OFFSET :offset` verified working; the phrase-stemming
behaviour (`'managing'` matched a row titled `"Quantum Manager"`) confirms
`tokenize='porter unicode61'` is live, so the plan should not add its own stemming.
For a single-user queue an offset is fine; pin `q`, `excluded`, `hidden`, `scope`
and `offset` into the Load-more fragment's `hx-get` URL so a page-2 fetch re-uses
the exact same predicate set. If the plan wants stronger paging, the keyset is
`(score, l.id)` for a query and `(first_seen_at, id)` otherwise — but that is
squarely in the agent-discretion bucket and offset is the lower-risk v1 choice.

**Port.** §9.3 wants FTS behind a `search/fts.py` port "with a documented Postgres
`tsvector`+GIN alternative". Do that: one `app/db/repositories/queue_repo.py` (or
`search_repo.py`) owning the MATCH SQL, and a module docstring stating the Postgres
substitution. Do not scatter MATCH strings across routes.

### Q4 — Pure filter-rule evaluation and where exclusions are written

**Module.** `app/domain/filter.py`, importing only stdlib + the existing pure
`app.domain.models` / `app.domain.listing` helpers. `app.domain` may not import
`sqlalchemy`, `httpx`, `jobspy`, `jinja2`, `subprocess` or `fastapi`
`[VERIFIED: tests/test_import_discipline.py:14-16]`, so the evaluator input must be
a **pure dataclass**, not the ORM `FilterRule` row. The repository maps ORM →
domain (the same split the codebase already uses for `NormalisedListing`).

**Shape (total functions at every boundary — Pattern 2):**

```python
# app/domain/filter.py
@dataclass(frozen=True)
class RuleSpec:            # a filter_rules row, mapped
    rule_id: str
    kind: str              # one of the six kinds
    params: Mapping[str, Any]
    position: int

@dataclass(frozen=True)
class ListingFacts:        # the subset of a listings row rules may read
    title: str
    title_norm: str
    description: str | None
    company_norm: str | None
    location_norm: str | None
    remote_flag: bool | None
    seniority: str | None
    salary_min: float | None
    salary_max: float | None
    salary_interval: str | None

@dataclass(frozen=True)
class RuleOutcome:
    excluded: bool
    rule_id: str
    rule_kind: str
    detail: dict[str, Any]   # evidence, never a description excerpt

def evaluate(rules: Sequence[RuleSpec], facts: ListingFacts) -> list[RuleOutcome]:
    """Evaluate every enabled rule; return ONLY the ones that excluded.

    Deterministic and total: ordered by (position, rule_id); a malformed
    params_json degrades to 'rule skipped' (recorded in the run's stage log)
    rather than raising, so one bad rule cannot empty the queue (P10).
    """
```

**Per-kind semantics** (each detail dict is the FILT-02 "why"):

| Kind | params | Excludes when | `detail_json` |
|------|--------|---------------|---------------|
| `salary_floor` | `{"amount": int, "currency": "EUR", "interval": "year"}` | **Only when a salary figure is known** and its annualised value is below the floor. **A listing with no salary is NOT excluded** — see caveat below | `{"floor": 70000, "salary_min": 52000, "salary_max": null, "interval": "year", "currency": "EUR"}` |
| `exclude_keyword` | `{"terms": ["crypto","unpaid"], "fields": ["title","description"]}` | any term (casefolded substring) is present in a listed field | `{"term": "crypto", "field": "title", "count": 1}` |
| `location` | `{"allow": ["dublin","cork"], "mode": "substring"}` | `location_norm` is non-null and matches none of the allowed terms | `{"location_norm": "galway, ireland", "allowed": ["dublin","cork"]}` |
| `remote` | `{"require": true}` | `remote_flag is False` (never excludes `None` — unknown is not "not remote") | `{"remote_flag": false, "require": true}` |
| `seniority` | `{"allow": ["senior","staff"], "deny": [], "unknown_passes": true}` | a *deny* token matches, or `seniority` is non-null and matches no *allow* token | `{"seniority": "junior", "allow": ["senior","staff"]}` |
| `company_blocklist` | `{"companies": ["acme staffing"], "match": "norm_equals"}` | `company_norm` equals (or token-matches) an entry | `{"company_norm": "acme", "matched": "acme"}` |

**Caveat that must be decided explicitly (currently `[ASSUMED]`):** "a listing with
no salary is not excluded by `salary_floor`". The alternative (exclude unknowns)
would silently drop a large share of an Irish corpus, because JobSpy's
description-derived salary extraction is USA-only and `$`-anchored — a documented
Phase-1 finding recorded in `app/domain/listing.py`'s own docstring
`[VERIFIED: app/domain/listing.py:233-236]` and in `source_repo.py:41-44`. "Unknown
passes" is the recommendation; it must be stated in the rule's UI help text.

**`detail_json` must never carry a description excerpt.** The kind is user-supplied
and safe, but a description snippet could contain a recruiter's name — the same
class of data Phase 1 drops at ingest. Store the term, the field, and a count.

**Where rows are written.** `listing_exclusions(listing_id, run_id, rule_id,
rule_kind, detail_json, created_at)` already exists in 0001
`[VERIFIED: alembic/versions/0001_initial_schema.py:187-196]`, plus
`criteria_version` added by 0002. Write **one row per firing rule per listing per
run** (D-36: "One `listing_exclusions` row per listing+run+rule (full history,
per-rule counts per run)"), append-only, never updated — retuning a rule
re-evaluates from scratch and can bring a listing back with no deletion needed.

**Precedence with multiple enabled searches (D-32) — the one genuinely ambiguous
part.** `filter_rules` belongs to a `search`, and the queue is the **union** of all
enabled searches, but the schema has no "which search retrieved this listing" link.
Two deterministic options:
- **(recommended) Union-of-rules:** evaluate the deduplicated union of every enabled
  in-scope search's rules as one rule set, ordered by `(search_id, position)`.
  Simple, deterministic, and matches "the queue unions all enabled searches". A
  listing is excluded if any rule fires; all firing rules get a row.
- Per-search scoping: requires a new `listings.retrieved_by_search_id` column and
  a new concept in the run row. Larger and not required by any requirement.

Record whichever is chosen in the plan and in the `filter.py` docstring; the
planner should not leave it implicit. (Flagged in Open Questions.)

**Stage order.** ARCHITECTURE §8.1 is emphatic: fetch fully → sanitise → normalise →
**dedup/merge** → **hard-rule filter** → cap
`[CITED: .planning/research/ARCHITECTURE.md:754-777]`. In `run_pipeline()` the
filter stage therefore lands after the Tier-2 merge stage, both after the existing
per-source `_persist_result` loop and before `_finish`. The existing
`Stage`/`StageCounts`/`StageResult` shapes in `app/pipeline/stages.py:30-57` are the
instrumentation to reuse — do not invent a second counter type.

### Q5 — Queue empty-reason enum, computed deterministically

**Module.** `app/domain/run_reason.py`, pure. Input is a counts dataclass the
pipeline assembles; output is `(reason: str, counts: dict)`.

```python
REASONS = ("no_sources_enabled","all_sources_failed","zero_fetched",
           "all_filtered","nothing_new","mixed")

def compute_empty_reason(counts: RunCounts) -> str:
    """A fixed, documented priority order; the first matching cause wins.

    1 no_sources_enabled : counts.adapters_resolved == 0
    2 all_sources_failed : adapters resolved > 0 and every source status != 'ok'
    3 zero_fetched       : every source 'ok' and total fetched == 0
    4 all_filtered       : fetched > 0 and excluded_by_rule > 0 and survivors == 0
    5 nothing_new        : survivors > 0 but every survivor predates the watermark
    6 mixed              : anything else (≥2 causes co-occur)
    """
```

**Counts to persist** (`runs.reason_counts_json`), all machine-readable and all
already derivable:

| Key | Source |
|-----|--------|
| `adapters_resolved` | `len(selected)` in `run_pipeline` |
| `sources: {name: {status, fetched, created, updated, failed, requests_used}}` | already built by `_persist_result` and returned as the per-source dict `[VERIFIED: app/pipeline/run.py:221-228]` |
| `excluded_by_rule: {rule_id: n}` | `GROUP BY rule_id` over this run's `listing_exclusions` |
| `survivors` | listings visible in the queue after dedup + filter |
| `duplicates_already_seen` | the `updated` count (Tier-1 key hits) |
| `watermark` | `queue_state.last_queue_view_at` |
| `capability_warnings: [...]` | the `_fetch_one` warning dicts (Q8) |

**The "collapsed raw stage log"** goes in `runs.stage_log_json` as a bounded list of
`{"stage": name, "counts": {...}, "errors": [...]}` — i.e. the serialised
`StageCounts`/`StageResult` objects the stages already produce
`[VERIFIED: app/pipeline/stages.py:44-57]`. Cap it (last N stages / N errors) so a
pathological run cannot write an unbounded blob; the UI renders it inside a
collapsed `<details>` (D-44's "collapsible raw stage log").

**Existing precedent to extend rather than duplicate:** `run_pipeline` already
records a machine-readable no-sources error as
`{"source": "*", "status": "partial", "error": NO_SOURCES_REASON}` with
`NO_SOURCES_REASON = "no enabled sources resolved from the adapter registry"`
`[VERIFIED: app/pipeline/run.py:47-51,297-299]`. `no_sources_enabled` should
recognise the same condition; do not create a second vocabulary for it.

**Why this matters product-wise:** PITFALLS P9 lists "the queue is empty and `runs`
shows a successful run — with no per-source counts or exclusion reasons to explain
it" as the top warning sign, and states "Zero results must never be ambiguous"
`[CITED: .planning/research/PITFALLS.md:264-290]`.

### Q6 — The `_INJECTION_PATTERNS` catalogue and Apache-2.0 §4 attribution

**What Resume-Matcher actually contains.** Fetched from the upstream raw file this
session (`app/services/improver.py`, `srbhr/resume-matcher`, Apache-2.0). The list is
eight **regex** strings:

```python
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?above",
    r"forget\s+(everything|all)",
    r"new\s+instructions?:",
    r"system\s*:",
    r"<\s*/?\s*system\s*>",
    r"\[\s*INST\s*\]",
    r"\[\s*/\s*INST\s*\]",
]
```
`[CITED: https://raw.githubusercontent.com/srbhr/resume-matcher/main/apps/backend/app/services/improver.py]`

and the consumer applies them with `re.sub(pattern, "[REDACTED]", text,
flags=re.IGNORECASE)` — i.e. it **mutates** the text.

**What to copy, and what not to.** D-38 says "pattern-copied … attributed per
Apache-2.0 §4", and the existing seam (`INSTRUCTION_MARKERS` +
`looks_like_instructions`, `[VERIFIED: app/domain/sanitize.py:38-51,121-125]`) is
**flag-only**: it returns a boolean and `SanitizeReport.instruction_like`
`[VERIFIED: app/domain/sanitize.py:54-71]`. **Keep the flag semantics; do not copy
the redaction.** Two reasons:
- Redaction would change `description` between runs for the same listing, and
  `content_hash` is computed over the sanised `description`
  `[VERIFIED: app/domain/listing.py:169-182]` — a redacted description would
  produce a spurious content change and break repost detection.
- Phase 1's contract is "the removed value is never returned or logged — only a
  count" `[VERIFIED: app/domain/sanitize.py:8-10,74-85]`; a redaction that rewrites
  the stored description is a different and larger behaviour change than Phase 2's
  scope allows.

Recommended extension of `app/domain/sanitize.py`:
- add a module-level `INJECTION_PATTERNS: tuple[re.Pattern[str], ...]` compiled from
  the eight strings (case-insensitive), with a comment naming the upstream file,
  repo, licence and the exact commit/tag inspected;
- add `patterns_matched: int` to `SanitizeReport` (keep `instruction_like` as the
  boolean, so the Phase-1 tests and callers are unaffected), and a
  `matched_pattern_names()`-style helper is *not* needed — a count plus a log line
  is enough and avoids leaking attacker text into logs;
- keep `INSTRUCTION_MARKERS` as the fast literal-substring pre-check (it is already
  public API and unit-tested `[VERIFIED: app/domain/sanitize.py:40-51]`);
- make `looks_like_instructions` consult both.

**Precision caution:** `r"system\s*:"` is low-precision — it matches ordinary prose
like `"System: Windows 11 required"`. Because the result is only a flag (no
mutation, no exclusion), a false positive costs a log line and a flag, not a
dropped listing. Record the count, not the match, so a false positive remains
diagnosable without persisting listing text.

**Identifiers dropped vs hashed.** Nothing in this rule set drops or hashes an
identifier — the catalogue only sets a flag/count. The only drop-not-hash rule in
the module is PII (emails/phones), already implemented by `strip_pii`
`[VERIFIED: app/domain/sanitize.py:104-112]`; that behaviour is unchanged. So the
answer to the discretion question "which identifiers are dropped vs hashed" is:
**none are hashed anywhere in this phase; PII is dropped, injection markers are
counted.**

**Apache-2.0 §4 obligations** `[CITED: https://www.apache.org/licenses/LICENSE-2.0]`:
- §4(a)/(b) — give recipients a copy of the licence if you distribute the work;
- §4(c) — retain all copyright/attribution notices present in the source form and
  **state significant changes** in modified files — so the copied file must carry a
  comment block naming the origin (`srbhr/resume-matcher`,
  `apps/backend/app/services/improver.py`), the licence, and the fact that the
  patterns were re-expressed as flags rather than redactions;
- §4(d) — add a `NOTICE` file (or extend an existing one) if the upstream
  distribution contains a NOTICE; the target file itself has **no licence header**
  (verified by the fetch), so §4(c) is discharged by an origin comment, but the plan
  should still check the upstream repo root for `LICENSE`/`NOTICE` and record the
  commit SHA it read.
- **Do not put the attribution URL in a Jinja template.** `tests/test_no_cdn.py`'s
  `REMOTE_SCHEME_RE = re.compile(r"https?://", re.IGNORECASE)` is documented as
  catching "Any bare remote scheme anywhere in a template"
  `[VERIFIED: tests/test_no_cdn.py:24-27]`, so a documentation URL in an HTML
  comment would fail the no-CDN guard. Attribution lives in `.py` files and
  `NOTICE` only.

### Q7 — HTMX/Alpine patterns for the new partials

**The Phase-1 conventions that are locked in code** (copy these; do not invent):

| Convention | Existing evidence |
|------------|-------------------|
| `hx-post` + `hx-target` + `hx-swap="innerHTML"` for actions | `app/web/templates/html/queue.html` run button |
| Poll fragment self-replaces: `hx-get="/runs/{{ run.id }}/status" hx-trigger="every 2s" hx-swap="outerHTML"` | `app/web/templates/html/_run_status.html` |
| Stop polling with **HTTP 286** + `HX-Reswap: outerHTML` | `app/api/runs.py:89-92` `[VERIFIED]` |
| Vendored assets only, no CDN; `htmx.min.js` + `alpine.min.js` + `app.css` | `app/web/templates/html/base.html`; `tests/test_no_cdn.py` |
| Jinja autoescape on; `|safe` never applied to listing text | default `Jinja2Templates` behaviour; no `|safe` in any template |
| Templates live in `app/web/templates/html/*.html`; routes build a `Jinja2Templates` per module | `app/web/routes.py:30-33`, `app/api/runs.py:32-33` |

**Recommended fragment set** (path, trigger, target):

| Partial | Method + URL | HTMX |
|---------|--------------|------|
| Queue list + load-more | `GET /queue/list?q=&excluded=&hidden=&scope=&offset=` | search box `hx-get hx-trigger="input changed delay:300ms" hx-target="#queue-list"`; load-more button `hx-get` → appends the next page's rows into `#queue-list` |
| Excluded toggle | `GET /queue/list?excluded=1&…` | checkbox `hx-get hx-include="closest form" hx-target="#queue-list"` |
| Save / Hide / Unsave / Unhide | `POST /listings/{id}/events` with `event_type` in the body | `hx-post hx-target="#listing-row-{id}" hx-swap="outerHTML"`, returns the row partial |
| Criteria list + form | `GET /searches`, `POST /searches`, `POST /searches/{id}/toggle`, `POST /searches/{id}/delete` | form `hx-post hx-target="#search-list"`; per-kind field groups switched with Alpine `x-data`/`x-show` (no extra round trip) |
| Rule editor per kind | inside the criteria form | Alpine locally; server renders the persisted rules on reload |
| Runs page + detail | `GET /runs`, `GET /runs/{id}` (expand) | plain links + Alpine `x-show` for the collapsed stage log; reuse `_run_status.html` as the polled fragment |
| Merges audit view | `GET /merges` with revert `POST /merges/{id}/revert` | `hx-post` returning the merges table partial |

**Notes that will bite otherwise:**
- The queue page currently renders one `<table>` with all rows and no ids. The
  load-more and per-row event targets require a stable per-row id — use
  `id="listing-row-{{ listing.id }}"`.
- "No Jinja in any logic position" (D-34) means `{% if %}` for *rendering* is fine;
  what is banned is computing filter semantics in a template. The rule-kind field
  visibility must come from an Alpine `x-data` object or from server-rendered
  blocks per kind, not from `{{ ... }}` evaluating anything.
- The run-history strip on the queue (D-43) should reuse `render_run_fragment`
  `[VERIFIED: app/api/runs.py:40-42]` rather than a parallel renderer.
- `queue()` currently does the query inline in the route
  `[VERIFIED: app/web/routes.py:67-73]`; Phase 2 moves it to a repository and the
  route becomes thin. The Phase-1 e2e assertion `"0 listings"` /
  `'hx-post="/runs"'` / `'id="run-status-slot"'` must keep passing
  `[VERIFIED: tests/api/test_run_trigger.py:test_queue_page_shows_the_trigger_control_and_the_count]`,
  so keep the count element and the run-control markup ids.

### Q8 — Capability-warning surfacing

**What already ships and is unconsumed.** `compile_query_for_source(query,
capabilities, source=…)` returns `CompiledQuery(query, warnings)` where each
`CapabilityWarning` is `(source, filter_name, reason)`
`[VERIFIED: app/sources/base.py:211-226,236-296]`, and `SourceCapabilities`
declares `supports_salary_min_filter`, `supports_remote_flag`, `supports_seniority`,
`exclusive_filter_groups`
`[VERIFIED: app/sources/base.py:44-61]`. `_fetch_one` already converts those
warnings into the run's error-record shape with `"status": "warning"` and the text
`f"filter not applied: {warning.filter_name} — {warning.reason}"`
`[VERIFIED: app/pipeline/run.py:118-132]`, and `run_pipeline` extends `errors` with
them so they land in `runs.errors_json` `[VERIFIED: app/pipeline/run.py:301-306]`.

**The Phase-2 improvement that makes this honest.** Because Phase 2 also evaluates
every rule *locally as a hard filter on the persisted listing* (Q4), an
unsupported **fetch-side** filter is no longer "not applied" — it is applied
post-fetch. The warning text should therefore be produced by the criteria compiler
and rendered on the criteria page as, e.g., "LinkedIn has no salary-minimum filter;
this rule will be enforced locally after the fetch." That is materially stronger
than SRC-09's minimum ("reported rather than silently ignored") and costs nothing
because the local evaluator exists anyway.

**Where it surfaces:**
1. as today, into `runs.errors_json` (status `warning`) — keep this, it is already
   tested;
2. **additionally** into the new `runs.stage_log_json` under a
   `{"stage": "criteria_compile", "warnings": [...]}` entry, so the run detail page
   shows it without parsing the error list;
3. **on the criteria page**, derived by compiling each enabled search against each
   enabled adapter's `capabilities` at render time (no run needed) — this is what
   makes FILT-04/Critera honest *before* a run.

`exclusive_filter_groups` (LinkedIn's `{hours_old, easy_apply}`) stays a
compile-time warning plus a deterministic alphabetical drop; Phase 1 already
documented that choice as "the `CapabilityWarning` is the product value, not the
drop" `[VERIFIED: docs/STATE.md:93]`.

### Q9 — Validation Architecture (see the full section below)

The five success criteria map onto four test lanes: pure-domain unit tests
(`tests/domain/`), DB-backed repository/integration tests (`tests/db/`,
`tests/pipeline/`), API/HTMX fragment tests (`tests/api/`, `tests/web/`), and the
schema-contract guards. All of them reuse `migrated_db`, `session_factory`,
`db_session`, `client` and `registry_snapshot` from `tests/conftest.py` — the
Phase-1 harness needs **no** change beyond the guard updates in Q2, because the
session-scoped template DB now migrates to 0002 automatically.

## Standard Stack

### Core (no new runtime dependencies except one)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `rapidfuzz` | `3.14.6` (pip latest, verified) | Tier-2 fuzzy dedup scoring | MIT; the `STACK.md` Q4 pick; ships abi3 wheels so it works on the pinned 3.13 **and** the local 3.14 dev venv. `[VERIFIED: pip index versions rapidfuzz → 3.14.6]` |
| SQLAlchemy + Alembic | `2.0.53` / `1.20.0` (already pinned) | Migration 0002, repositories | Already in `pyproject.toml` `[VERIFIED]` |
| FastAPI + Jinja2 | `0.141.1` / `3.1.6` (already pinned) | Fragment routes + templates | Already in use |
| SQLite FTS5 | stdlib-bundled | Queue full-text search | `ENABLE_FTS5` verified present in this build |

### Supporting (already present, reused)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `structlog` | `26.1.0` | Stage-named events for the new stages | Every new stage/route logs an event; the existing pipeline uses `log.warning/info` |
| `pytest` + `pytest-asyncio` | `9.1.1` / `1.4.0` | All phase tests | `asyncio_mode = "auto"` is already configured |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `rapidfuzz` | stdlib `difflib.SequenceMatcher` | No wheels supply chain, but no `token_sort_ratio`/`score_cutoff` and far slower; the research explicitly chose rapidfuzz |
| `rapidfuzz.fuzz.token_set_ratio` | `fuzz.token_sort_ratio` | token_set is subset-forgiving (returns 100 for `"Software Engineer"` vs `"Senior Software Engineer"`); token_sort is the safer primary. **Use token_sort for the gate and treat token_set only as diagnostic.** |
| `rapidfuzz.process.cdist` | a hand-rolled loop | `cdist` is faster on large blocks but returns a matrix that is harder to attach per-pair evidence to; at a same-company block size the loop is clearer. `[CITED: rapidfuzz process docs]` |
| Offset pagination | Keyset `(score, id)` | Offset is simpler and correct for a single-user queue; keyset is the upgrade if the corpus grows |

**Installation:**
```bash
# NOTE: the repo venv has no pip module and no rapidfuzz. The working env is .venv-host.
.venv-host/bin/python -m pip install 'rapidfuzz==3.14.6'
# then add the exact pin to pyproject.toml dependencies (D-31: "added deliberately",
# and the file's own convention is exact pins only)
```

**Version verification (as required before writing the table):**
```
$ pip index versions rapidfuzz
rapidfuzz (3.14.6)          # latest, published 2026-08-30 per the legitimacy seam
$ .venv-host/bin/python -c "import sys; print(sys.version.split()[0])"
3.14.x                       # local dev env; Docker stays pinned to 3.13 (D-46)
```

### Package Legitimacy Audit

> Ran the Package Legitimacy Gate for the one package this phase adds.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `rapidfuzz` | PyPI | newest release 2026-08-30 | unknown (seam returned `weeklyDownloads: null`) | `https://github.com/rapidfuzz/RapidFuzz` | **SUS** (`too-new`, `unknown-downloads`) | **Flagged — planner must add `checkpoint:human-verify` before install** |

**Packages removed due to [SLOP] verdict:** none.

**Packages flagged as suspicious [SUS]:** `rapidfuzz`
`` `rapidfuzz` [WARNING: flagged as suspicious — verify before using.] ``

**Honest reading of the SUS verdict.** The two signals are both artefacts of the
gate's metadata, not evidence of a slopsquat: `publishedAt` is the *latest release*
date (2026-08-30), not the package's age, and `weeklyDownloads` is `null` because
the PyPI JSON API does not expose download counts (that lives on pypistats). The
package is a well-known MIT library with a public, active repo
(`rapidfuzz/RapidFuzz`), it is the library `STACK.md` Q4 already selected, and it
supplies abi3 wheels. Per the protocol, however, the verdict stands as recorded:
the planner **must** gate the install behind a `checkpoint:human-verify` task. The
checkpoint should confirm three things: (1) the pinned version, (2) the source repo
matches the distribution's `Project-URL`, (3) no `postinstall`-equivalent hook
(PyPI metadata showed `postinstall: null`, which is an npm field and simply not
applicable — the real check is that rapidfuzz is a compiled-extension wheel, not a
build-from-source with arbitrary setup code).

*No other package is added or changed this phase. `python-jobspy` and every other
dependency stays exactly as pinned in Phase 1.*

## Architecture Patterns

### System Architecture Diagram

```
                        ┌──────────────────────── run_pipeline() ────────────────────────┐
                        │                                                                │
  enabled searches ─────►│  criteria compiler                                             │
  (searches +            │    • SearchQuery per search                                    │
   filter_rules)         │    • compile_query_for_source(query, caps, source)  D-37        │
                        │    • CapabilityWarning ──► runs.stage_log_json / errors_json    │
                        └───────────────┬────────────────────────────────────────────────┘
                                        ▼
                     _resolve_adapters()  (enabled `sources` rows → registry)
                                        ▼
                     _fetch_all()  asyncio.gather, one FetchBudget per board   (unchanged)
                                        ▼
                     _persist_result()  sanitise → normalise → Tier-1 two-key upsert
                                        │   (unchanged; writes listings + listing_sources)
                                        ▼
    ┌──────────── STAGE: Tier-2 dedup (D-30, NEW) ─────────────┐
    │  candidate block: company_norm equality (indexed) +       │
    │  posted window; score token_sort_ratio over the tuple;    │
    │  component gate + seniority-conflict guard; θ from Settings│
    │  → merge: fill survivor blanks, write listing_dupes row   │
    │    (snapshot_json, merged_at); skip reverted pairs (D-28)  │
    │  → counters: deduped_count, stage_log_json                │
    └──────────────────────────┬───────────────────────────────┘
                               ▼
    ┌──────────── STAGE: hard filter (D-34, NEW) ──────────────┐
    │  union of enabled searches' rules, ordered (search,pos)   │
    │  pure app/domain/filter.py evaluate() → RuleOutcome list   │
    │  → append one listing_exclusions row per firing rule       │
    │  → counters: filtered_count, excluded_by_rule{}            │
    └──────────────────────────┬───────────────────────────────┘
                               ▼
                compute_empty_reason() (pure, deterministic)
                → runs.reason + runs.reason_counts_json
                               ▼
                        _finish()  (persists counters; existing)

  ── Read paths (separate from the pipeline) ───────────────────────────────
  GET /            → queue()  → queue_repo: visibility + FTS MATCH + order + paging
                                 + watermark read/advance (D-39)
                                 + merge-rate stat + last-run strip
  GET /searches    → criteria CRUD + per-kind rule forms + capability warnings
  GET /merges      → listing_dupes rows + one-click revert (QUEUE-09, D-29)
  GET /runs        → run history + reason sentence + collapsed stage log (RUN-04)
  POST /listings/{id}/events → append-only save/hide/unsave/unhide (QUEUE-08)
```

A reader can trace the primary use case left-to-right: criteria in → fetch →
persist → merge → filter → reason, and separately queue-read → visibility → FTS →
order → page.

### Recommended Project Structure (additions only)

```
app/
├── domain/
│   ├── dedup.py         # NEW: pure candidate scoring, seniority guard, merge plan
│   ├── filter.py        # NEW: six pure rule evaluators, RuleOutcome
│   ├── criteria.py      # NEW: search criteria ↔ SearchQuery, rule specs
│   ├── search_query.py  # NEW: build_match_expression() — the FTS5 safety transform
│   └── run_reason.py    # NEW: compute_empty_reason() + RunCounts
├── db/repositories/
│   ├── search_repo.py   # NEW: searches + filter_rules CRUD + version bump
│   ├── run_repo.py      # NEW: run history read model, reason writes
│   ├── event_repo.py    # NEW: append-only listing_events + state projection
│   ├── exclusion_repo.py# NEW: listing_exclusions writes + per-rule counts
│   ├── dupe_repo.py     # NEW: listing_dupes write/read/revert + negative memory
│   ├── queue_repo.py    # NEW: the queue read model (visibility, FTS, order, paging)
│   └── state_repo.py    # NEW: the queue_state watermark row
├── pipeline/
│   ├── dedup_stage.py   # NEW: the post-persist Tier-2 stage
│   ├── filter_stage.py  # NEW: the post-dedup hard-filter stage
│   └── run.py           # EXTEND: insert both stages, fix deduped_count, persist reason
├── web/templates/html/
│   ├── queue_list.html  # NEW: rows + load-more fragment
│   ├── _listing_row.html# NEW: row incl. save/hide + exclusion chip
│   ├── criteria.html    # NEW: searches + per-kind rule forms
│   └── runs.html        # NEW: run history
└── api/
    ├── events.py        # NEW: POST /listings/{id}/events
    ├── searches.py      # NEW: criteria CRUD + toggle + run-one
    └── runs.py          # EXTEND: /runs history page, /merges revert
```

### Pattern 1 — Pure decision / impure write split (existing codebase convention)

**What:** the domain decides, the repository writes. `app.domain.*` may import no
I/O (`tests/test_import_discipline.py`), so a rule/merge decision is a pure value
object and only the repository touches the session.
**When:** every new dedup, filter, criteria and reason computation.
**Example:**
```python
# app/pipeline/dedup_stage.py — the stage owns ORM + session; the decision is pure
outcomes = merge_plan(candidates, threshold=settings.dedup_fuzzy_threshold)
for plan in outcomes:
    await apply_merge(session, plan=plan, now=now, run_id=run_id)
```

### Pattern 2 — Total functions at the boundary

**What:** a rule with malformed `params_json`, a candidate block of one, an FTS
query with an apostrophe, or a run with zero sources all degrade to a recorded
outcome, never an exception. `[CITED: .planning/research/ARCHITECTURE.md:1146-1150]`
**When:** every new evaluator, the FTS query builder, and `compute_empty_reason`.
**Why it is load-bearing here:** PITFALLS P10 — "every run tries to do everything,
so one failure produces nothing". A single bad rule must not empty the queue.

### Pattern 3 — Append-only event log beside mutable state

**What:** `listing_events` is INSERT-only, enforced by DB triggers
`[VERIFIED: alembic/versions/0001_initial_schema.py:343-350]`; current state is
projected from the latest event. `[CITED: ARCHITECTURE.md:1158-1162]`
**When:** save/hide/unsave/unhide (QUEUE-08) and the merge's presence in the audit
trail.

### Pattern 4 — Persist the decomposition, compute the aggregate

**What:** store the raw counts and the firing rule; render the sentence from them.
**When:** `runs.reason_counts_json` + `listing_exclusions.detail_json` +
`deduped_count`. Never store a rendered sentence as the only artifact. The ranking
phase later reuses the identical shape for `factor_scores_json`/`weights_json`.
`[CITED: ARCHITECTURE.md:1152-1156]`

### Pattern 5 — Migration is the schema test

**What:** migration 0002's acceptance items are asserted by introspecting the
*migrated* DB (`PRAGMA table_info` / `sqlite_master`), never the ORM metadata.
`[VERIFIED: tests/db/test_migration_contract.py:1-11]`

### Anti-Patterns to Avoid

- **Filtering or capping before merging** (AP4) — you discard the copy that carried
  the salary. Stage order is fixed by §8.1.
- **Deleting the absorbed listing** (AP5) — mark it, keep the snapshot, make revert
  a flag flip.
- **Trusting an exact key alone to dedup cross-source** (AP7) — `blocking_key` misses
  drifted titles; it is a fast path, not the strategy.
- **Raw user text into `MATCH`** — verified to raise; always `build_match_expression`.
- **`ORDER BY rank` without a tie-break** — verified non-deterministic.
- **A global "last run"** (m10) — the watermark is a queue-state row; per-search
  freshness uses `searches.last_run_at`, which already exists.
- **Threading board-specific filter logic into the core** (AP10) — capabilities are
  declared per adapter and the compiler warns; the core never branches on a board name.
- **A redaction sanitiser that rewrites listing text** — breaks `content_hash`
  stability (Q6).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string scoring | Levenshtein/trigram in Python | `rapidfuzz.fuzz.token_sort_ratio` | C++/SIMD, well-tested, has `score_cutoff` which short-circuits |
| Full-text search over the queue | `LIKE '%term%'` | the existing `listing_fts` FTS5 table + `bm25()` | Indexed, ranked, and the research explicitly bans `LIKE` (M4) |
| FTS5 query escaping | a regex that "cleans" the query | `build_match_expression()` (quote-per-token) | FTS5's own quoting is the only correct escape; verified against 8 failing inputs |
| HTTP-dataset migrations | editing 0001 or `create_all()` | a new Alembic revision + the contract test | The repo's one-way-door convention: "a model/DDL drift must fail here" |
| Event state projection | a mutable `is_hidden` column | `listing_events` + latest-event projection | D-41 and the append-only triggers; a column would need a second source of truth |
| A per-run listing link | a new `listings.run_id` | `last_seen_at >= run.started_at` (Phase-1 pattern) and `listing_exclusions.run_id` | Already established and documented in `source_repo.py:14-18` |
| HTMX polling stop condition | `hx-trigger="every 2s"` forever | HTTP **286** + `HX-Reswap: outerHTML` | The Phase-1 documented stop signal; an unbounded poll is a battery/latency leak |

**Key insight:** every "deceptively complex" problem here already has an in-repo or
research-supplied answer. The phase's real work is wiring, not algorithms.

## Common Pitfalls

### Pitfall 1: Aggressive fuzzy merge deletes a real job
**What goes wrong:** `token_set_ratio` scores `"Software Engineer"` and `"Senior
Software Engineer"` at 100, the merge fires, and a genuine role disappears.
**Why it happens:** token-set ratio is *subset-forgiving by design* (verified in the
official docs example). Using it as the only gate reproduces PITFALLS P3 exactly.
**How to avoid:** component gate (company + location) **plus** a seniority/grade
conflict guard **plus** `token_sort_ratio >= θ`; never a bare title score.
**Warning signs:** a merge rate far above the 10–15% reference band; a Merges view
whose titles are obviously different roles ("every dedup bug looks reasonable as a
percentage and obviously wrong as a list of titles").
**Verification:** a unit test asserting `"Senior X"` / `"X"` never merges, and a
`dedup reconcile` dry-run that prints pairs.

### Pitfall 2: Revert that is undone by the next run
**What goes wrong:** the user reverts a merge; the next run re-merges the pair
because dedup is automatic (D-25) and stateless.
**Why it happens:** "negative memory" (D-28) is a *pre-check*, and the pre-check is
easy to forget when the merge path is the interesting code.
**How to avoid:** before scoring a candidate pair, query
`listing_dupes WHERE (listing_id=a AND dup_listing_id=b) OR (listing_id=b AND
dup_listing_id=a) AND reverted_at IS NOT NULL` and skip. Add the
`UNIQUE(listing_id, dup_listing_id)` index in 0002 **as well** — it stops the
same-orientation re-insert but not the reversed one.
**Verification:** an integration test: merge → revert → run again → still two rows.

### Pitfall 3: The queue search box 500s on an apostrophe
**What goes wrong:** `GET /?q=it's` raises `sqlite3.OperationalError: fts5: syntax
error near "'"` and the queue page 500s.
**Why it happens:** FTS5 `MATCH` takes a *query expression*, not a literal string.
**How to avoid:** `build_match_expression()` (pure, in `app/domain`), and skip the
FTS join entirely when it returns `None`.
**Warning signs:** any user-visible search field; any `MATCH f"..."` string build.
**Verification:** a unit test over the eight verified-failing inputs plus a route
test with `q="it's"`.

### Pitfall 4: Silent reordering of the queue
**What goes wrong:** a search result set is ordered differently between two
identical requests, breaking the Phase-1 determinism guarantee.
**Why it happens:** equal `bm25` scores have no defined order (verified).
**How to avoid:** always `ORDER BY <score>, l.id DESC`; the no-query path keeps
`first_seen_at DESC, id DESC`.
**Verification:** a test that fetches the same page twice and compares ids.

### Pitfall 5: The four guard tests read as regressions
**What goes wrong:** migration 0002 lands, `test_alembic_at_revision_0001` fails
(`versions == ["0001"]`), someone "fixes" it by reverting the migration or by
loosening the assertion, and the schema contract stops protecting anything.
**Why it happens:** the guards pin the *current* state by design.
**How to avoid:** the plan must pair the migration with the guard edits in one task
and state explicitly that the failing assertion is the expected, deliberate signal.
**Warning signs:** an `assert ... == ["0001"]` edited without adding the new
acceptance items.

### Pitfall 6: `deduped_count` still means "created"
**What goes wrong:** the merge-rate stat renders as "0% merged / 100% new" because
`run.deduped_count` is set from the created count (verified at `run.py:248`).
**How to avoid:** repurpose it to "rows absorbed by a merge" and add a test pinning
the new meaning; update `_run_status.html`'s existing `counts.created` label if it
depends on it.

### Pitfall 7: A rule that excludes on missing data empties a low-fill-rate corpus
**What goes wrong:** `salary_floor` excludes every listing whose salary is unknown;
on an Irish corpus that is a large majority (JobSpy's salary extraction is
USA-only), so the queue is silently empty and the reason reads `all_filtered`.
**How to avoid:** "unknown passes" for `salary_floor`/`remote`/`seniority`; the
`location` rule only excludes a *known* non-matching location. State it in the rule
help text.

### Pitfall 8: PII leaking through `detail_json` or the injection log
**What goes wrong:** a rule's `detail_json` stores a description snippet that
contains a recruiter's name/phone.
**How to avoid:** `detail_json` carries terms, field names and counts only; the
injection rule records a count, never the matched text. The schema PII guard
(`test_no_pii_columns.py`) only checks *column names* — it will not catch a
PII-bearing JSON value, so this is a code-review obligation, not a test.

### Pitfall 9: Criteria/UI identifiers tripping the credential scan
**What goes wrong:** a variable named `email_rule` or a function named
`send_login_notice` fails `tests/test_no_credentials.py`, whose
`CREDENTIAL_PATTERNS` include `email`, `phone`, `token`, `secret`, `cookie`,
`login`, `session_id` and are applied to collected **identifiers** — and whose
`CREDENTIAL_TOKENS` include `cookies=`, `CookieJar`, `http.cookiejar`
`[VERIFIED: tests/test_no_credentials.py:38-94]`.
**How to avoid:** name things `company_blocklist`, `exclude_keyword`,
`notification_*` (not `email_notification`); never write `cookies=` or
`requests.Session` anywhere under `app/`. The scan is on `.py` text + AST, not
templates, so Jinja field labels are safe.

### Pitfall 10: FTS index drift after a data change
**What goes wrong:** a merged listing's fields are updated, and either the index
diverges or the search misses the new title.
**Why it happens:** the `listings_au` trigger exists and works (Phase-1 verified),
but only if the update goes through `listings`.
**How to avoid:** perform all merge field-fills on the `listings` ORM row (not raw
SQL that bypasses triggers) and re-run the existing round-trip test as a regression
check. `tests/db/test_fts_triggers.py` already proves update/delete sync; extend it
with a merge-then-search case.

## Code Examples

### Verified FTS5 queue query (executed against the real migrated DB)

```sql
-- Source: executed this session against `alembic upgrade head` output on 0001
SELECT l.id, l.title, bm25(listing_fts, 10.0, 5.0, 1.0) AS score
FROM listing_fts
JOIN listings l ON l.id = listing_fts.rowid
WHERE listing_fts MATCH :match_expression        -- BOUND, never interpolated
  AND l.is_active = 1                            -- + visibility predicates
ORDER BY score, l.id DESC                        -- tie-break is mandatory (verified)
LIMIT :limit OFFSET :offset
```

The no-query branch is the Phase-1 pinned order and must **not** join `listing_fts`:

```sql
SELECT ... FROM listings l WHERE ... ORDER BY l.first_seen_at DESC, l.id DESC
LIMIT :limit OFFSET :offset
```

### Pure FTS5 query builder (the safety transform)

```python
# app/domain/search_query.py — pure; imports only `re`
def build_match_expression(raw: str | None, *, prefix_last: bool = True) -> str | None:
    """Safe FTS5 MATCH expression, or None when there is nothing to search.

    FTS5 treats `-`, `*`, `OR`, `NEAR(`, an unbalanced `"` and a bare `'` as
    query syntax, so raw user text raises OperationalError (verified: 8 inputs).
    Each token is therefore quoted (FTS5's own term-literal escape) and joined
    with AND; the last token gets '*' for a prefix match.
    """
    if not raw or not raw.strip():
        return None
    tokens = [t for t in re.split(r"\s+", raw.strip()) if t]
    if not tokens:
        return None
    quoted = ['"' + t.replace('"', '""') + '"' for t in tokens]
    if prefix_last:
        quoted[-1] = quoted[-1] + "*"
    return " AND ".join(quoted)
```

### Pure seniority-conflict guard (the P3 defence)

```python
# app/domain/dedup.py — pure
GRADE_TOKENS = frozenset({
    "senior", "sr", "lead", "staff", "principal", "head", "chief",
    "junior", "jr", "intern", "internship", "graduate", "trainee",
    "i", "ii", "iii", "iv",
})

def grades_conflict(title_norm_a: str, title_norm_b: str) -> bool:
    """True when exactly one title carries a grade token → never merge."""
    a = set(title_norm_a.split()) & GRADE_TOKENS
    b = set(title_norm_b.split()) & GRADE_TOKENS
    return bool(a) != bool(b) or (a and b and a != b)
```

### Merge decision sketch (pure input, impure write elsewhere)

```python
@dataclass(frozen=True)
class MergePlan:
    survivor_id: int
    absorbed_id: int
    score: float
    method: str                      # "fuzzy_tuple" | "content_hash" | "canonical_url"
    fill_fields: Mapping[str, Any]   # the blanks the twin contributes (D-27)
    snapshot: Mapping[str, Any]      # the survivor's pre-merge values (revert)

# app/pipeline/dedup_stage.py
plans = candidate_merges(listings_in_run, threshold=settings.dedup_fuzzy_threshold)
for plan in plans:
    await apply_merge(session, plan=plan, run_id=run_id, now=now)
```

### Revert (QUEUE-04) — a flag flip plus a field restore

```python
async def revert_merge(session, *, dupe_id: int, now: datetime) -> None:
    row = await session.get(ListingDupe, dupe_id)
    row.reverted_at = now
    row.reverted_by = "local"
    survivor = await session.get(Listing, row.listing_id)
    for field, value in (row.snapshot_json or {}).items():
        setattr(survivor, field, value)   # restores only what the merge changed
    await session.flush()
    # the absorbed twin reappears automatically: the queue hides rows that have
    # an un-reverted listing_dupes row, so no unhide event is required.
```

### Empty-reason precedence (deterministic, documented order)

```python
# app/domain/run_reason.py
def compute_empty_reason(c: RunCounts) -> str:
    if c.adapters_resolved == 0:                       return "no_sources_enabled"
    if c.adapters_resolved and all(s != "ok" for s in c.statuses):
                                                       return "all_sources_failed"
    if all(s == "ok" for s in c.statuses) and c.fetched == 0:
                                                       return "zero_fetched"
    if c.fetched and c.excluded_by_rule and c.survivors == 0:
                                                       return "all_filtered"
    if c.survivors and not c.new_since_watermark:      return "nothing_new"
    return "mixed"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `LIKE '%term%'` for listing search | FTS5 external-content + `bm25()` | v1 design (STACK Q4) | Indexed + ranked; the `rank` alias is stable in SQLite ≥ 3.9 |
| `token_set_ratio` as a general dedup gate | component gate + `token_sort_ratio` + grade guard | this research | token-set is subset-forgiving by design (verified) and unsafe as a sole gate |
| Delete-the-loser dedup | mark + `snapshot_json` + flag-flip revert | P3 / §8.3 | A false merge becomes undoable |
| A global "last run" timestamp | per-search `last_run_at` + a queue watermark row | m10 / D-39 | "New since" survives multiple searches |
| Redact-and-continue prompt-injection handling (Resume-Matcher) | flag-and-count, never mutate | this research | Keeps `content_hash` stable; no listing text rewritten |

**Deprecated/outdated:**
- `capability_warnings()` (the plain-text back-compat wrapper in
  `app/sources/base.py:299-308`) should not gain new consumers; Phase 2 should call
  `compile_query_for_source()` and read the structured `CapabilityWarning` objects.
- `evaluate`-in-template (any rule logic expressed in Jinja) — banned by D-34.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `dedup_fuzzy_threshold` default in the high-80s/low-90s is usable on this corpus | Q1 | Over-merging (data loss) or near-zero merging (duplicate queue). STATE.md already flags this as untunable pre-corpus; keep it a setting + tuning task |
| A2 | `salary_floor` should **not** exclude listings with no salary | Q4 | Excluding unknowns would empty an Irish corpus (JobSpy salary extraction is USA-only). Needs user confirmation because it is a product policy, not a technical default |
| A3 | `remote`/`seniority` rules should not exclude on an unknown (`None`) value | Q4 | Same class of risk; a stricter rule would drop silent-majority rows |
| A4 | Multi-search rule precedence = union of all enabled searches' rules | Q4, Open Q2 | If per-search scoping is actually wanted, it needs a new column and a plan change |
| A5 | `listing_sources` rows stay on the absorbed twin (do not move to the survivor) | Q1 | Amends ARCHITECTURE §8.3; if the plan wants §8.3 verbatim, revert becomes a data migration and needs its own design |
| A6 | Run-row shape: **one `runs` row per trigger**, with per-search sections inside `stage_log_json`/`reason_counts_json` | Q2, Q5 | D-45 explicitly leaves this to the planner; one-row-per-search would change the "one trigger = one runs row" test at `tests/api/test_run_trigger.py` |
| A7 | Queue visibility excludes absorbed, un-reverted twins via the `listing_dupes` join (no `is_hidden` column, no hide event) | Q1 | If D-41's hide event is expected on merge, an extra event write is needed |
| A8 | `rapidfuzz` 3.14.6 has wheels for the pinned 3.13 and the local 3.14 dev env | Standard Stack | Install fails; fall back to `difflib` only as a last resort (worse but stdlib) |
| A9 | Queue page size and the Load-more/offset interaction | Open Q3 | Purely a UX default; cheap to change |
| A10 | Run-history retention/pruning policy | Open Q4 | Unbounded growth is slow at this scale; deferring is low risk |

**If this table is non-empty, the planner and `/gsd-discuss-phase` should confirm
A1, A2, A4 and A6 before locking the corresponding tasks** — A2/A3 are product
policy, A4/A6 are structural.

## Open Questions (RESOLVED)

1. **[RESOLVED]** **Which ranking function is the primary gate?**
   - What we know: D-31 names token-set ratio; verified subset-forgiving behaviour
     makes it unsafe alone.
   - What's unclear: whether the user wants token-set *specifically* or the outcome
     (safe cross-source merges).
   - Recommendation: implement the component gate as primary with
     `token_sort_ratio` and log the token-set score as diagnostic; this satisfies
     D-31's intent (rapidfuzz over the normalised tuple, θ as a setting) without
     reproducing P3.

2. **[RESOLVED]** **Multi-search rule scope (union vs per-search).**
   - What we know: `filter_rules` FKs to `searches`; the queue unions enabled searches.
   - What's unclear: whether an exclusion from search A should remove a listing that
     search B retrieved.
   - Recommendation: union-of-rules (deterministic, no schema change) and document
     it in `filter.py` + the criteria UI copy.

3. **[RESOLVED]** **Load-more vs the excluded toggle.**
   - What we know: both change the row set; offset pagination is page-local.
   - What's unclear: whether toggling `Show excluded` resets the page or preserves offset.
   - Recommendation: any predicate change resets `offset=0` (the `hx-get` URL carries
     the offset, so resetting is a one-line template change) — otherwise page N of
     the filtered set is meaningless.

4. **[RESOLVED]** **Run retention/pruning.**
   - What we know: `runs` grows once per manual trigger (and later, per day).
   - Recommendation: no pruning in Phase 2; add a bounded `GET /runs?limit=` and a
     note that pruning is a Phase-8 ops item.

5. **[RESOLVED]** **Does "Show excluded" also list excluded-but-merged rows?** (CONTEXT discretion)
   - Recommendation: no — a merged twin is not "excluded by a rule"; the Merges view
     is its home. Show it dimmed under the excluded toggle only if it also has an
     exclusion row, which the union-of-rules model permits naturally.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | everything | ✓ | 3.14.x in `.venv-host` (Docker pins 3.13 per D-46) | — |
| SQLite with FTS5 | QUEUE-06 | ✓ | `ENABLE_FTS5` present (verified via `PRAGMA compile_options`) | — |
| Alembic | migration 0002 | ✓ | `1.20.0` (runnable only via `.venv-host/bin/python -m alembic`; no `alembic` on `PATH`, and `.venv/bin/python` raises `No module named alembic.__main__`) | — |
| `rapidfuzz` | Tier-2 dedup | ✗ **not installed in either venv** | — | none acceptable; must install (SUS verdict → `checkpoint:human-verify`) |
| pip | installing rapidfuzz | ✓ only in `.venv-host` (`.venv` has **no pip module**) | — | — |
| `pytest` | the test lane | ✓ in `.venv-host` | `9.1.1` | — |
| Knowledge graph (`.planning/graphs/graph.json`) | graph-context step | ✗ | — | skipped; no graph context injected |

**Missing dependencies with no fallback:**
- `rapidfuzz` — the Tier-2 stage cannot land without it. Install command:
  `.venv-host/bin/python -m pip install 'rapidfuzz==3.14.6'`, then add the exact pin
  to `pyproject.toml`, behind the required `checkpoint:human-verify`.

**Missing dependencies with fallback:**
- None blocking. (No knowledge graph exists, so Step 1.3 graph queries were skipped
  — not a blocker.)

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json`, so this
> section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest `9.1.1` + pytest-asyncio `1.4.0`, `asyncio_mode = "auto"` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (exists: `testpaths=["tests"]`, `addopts="-m 'not live'"`) `[VERIFIED: pyproject.toml]` |
| Quick run command | `.venv-host/bin/pytest -q tests/domain tests/db tests/pipeline` |
| Full suite command | `.venv-host/bin/pytest -q` |
| Schema gate | `.venv-host/bin/pytest -q tests/db/test_migration_contract.py tests/db/test_no_pii_columns.py` |
| Live/operator lane | `.venv-host/bin/pytest -q -m live` — never in CI (P13) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| QUEUE-03 | Cross-source duplicate merges once; twin retained | integration | `pytest tests/pipeline/test_dedup_merge.py -x` | ❌ Wave 0 |
| QUEUE-04 | Revert restores fields, unhides twin, survives the next run | integration | `pytest tests/pipeline/test_dedup_revert.py -x` | ❌ Wave 0 |
| QUEUE-06 | FTS search finds a listing; hostile query does not 500; order stable | api + unit | `pytest tests/domain/test_search_query.py tests/api/test_queue_search.py -x` | ❌ Wave 0 |
| QUEUE-07 | New-since-watermark and stale badges | db + api | `pytest tests/db/test_queue_state.py tests/api/test_queue_signals.py -x` | ❌ Wave 0 |
| QUEUE-08 | save/hide append events; projection shows current state; UPDATE/DELETE abort | db + api | `pytest tests/db/test_listing_events.py tests/api/test_listing_events.py -x` | ⚠️ append-only half exists in `tests/db/test_migration_contract.py::test_listing_events_append_only`; projection is new |
| QUEUE-09 | Merge rate + rows behind it | db + api | `pytest tests/api/test_merges_view.py -x` | ❌ Wave 0 |
| CRIT-01 | Create/edit/delete a named search + rules | api | `pytest tests/api/test_searches_crud.py -x` | ❌ Wave 0 |
| CRIT-02 | Run stores criteria snapshot; exclusion rows carry `criteria_version` | integration + schema | `pytest tests/pipeline/test_criteria_snapshot.py tests/db/test_migration_contract.py -x` | ❌ Wave 0 |
| CRIT-03 | Enable/disable without delete | api | `pytest tests/api/test_searches_crud.py::test_toggle -x` | ❌ Wave 0 |
| FILT-01 | Rules reject post-merge, pre-LLM; no LLM call in phase | unit + integration | `pytest tests/domain/test_filter.py tests/pipeline/test_filter_stage.py -x` | ❌ Wave 0 |
| FILT-02 | One `listing_exclusions` row per firing rule with detail | db | `pytest tests/db/test_exclusions.py -x` | ❌ Wave 0 |
| FILT-03 | Show-excluded toggle names the rule + per-rule counts | api | `pytest tests/api/test_queue_excluded.py -x` | ❌ Wave 0 |
| FILT-04 | Rule params read from DB, not code; no literal in `app/pipeline` | unit + static | `pytest tests/test_config.py tests/domain/test_filter.py -x` | ✅ `test_config.py` exists; extend the new settings |
| RUN-03 | Reason enum + counts persisted and rendered | unit + api | `pytest tests/domain/test_run_reason.py tests/api/test_run_reason.py -x` | ❌ Wave 0 |
| RUN-04 | `/runs` history page + last-run strip | api | `pytest tests/api/test_run_history.py -x` | ❌ Wave 0 |
| SRC-09 (D-37) | Capability warning surfaced, not dropped | unit + integration | `pytest tests/sources/test_capabilities.py tests/pipeline/test_capability_surface.py -x` | ⚠️ `compile_query_for_source` is unit-tested; the *consumption* is new |
| SRC-08 (D-38) | Injection rule set flags without mutating | unit | `pytest tests/domain/test_sanitize.py tests/domain/test_injection_patterns.py -x` | ⚠️ `test_sanitize.py` exists; add the pattern catalogue cases |
| Guards | Migration 0002 contract, PII allow-list, import purity, auth seam | schema/static | `pytest tests/db/test_migration_contract.py tests/db/test_no_pii_columns.py tests/test_import_discipline.py tests/test_auth_seam.py tests/test_no_credentials.py tests/test_no_cdn.py -x` | ✅ all exist — **must be updated** (Q2) |

### Sampling Rate

- **Per task commit:** `.venv-host/bin/pytest -q tests/domain tests/db tests/pipeline` (offline, < 30 s)
- **Per wave merge:** `.venv-host/bin/pytest -q`
- **Phase gate:** full suite green, plus the updated migration-contract checklist and
  the two non-test gates the phase owes: the tuned-θ record and the merge-rate band
  noted in `docs/` (STATE.md's Phase-2 blocker).

### Wave 0 Gaps

- [ ] `tests/domain/test_search_query.py` — the 8 verified-hostile inputs + the `None` branch (QUEUE-06)
- [ ] `tests/domain/test_dedup.py` — seniority-conflict guard, component gate, subset pathology (QUEUE-03)
- [ ] `tests/domain/test_filter.py` — six kinds, unknown-value policy, malformed `params_json` (FILT-01/02)
- [ ] `tests/domain/test_run_reason.py` — every enum branch + precedence (RUN-03)
- [ ] `tests/domain/test_injection_patterns.py` — the 8 upstream regexes, flag-not-mutate (SRC-08/D-38)
- [ ] `tests/db/test_migration_contract.py` — **edit** items 9 + new 10–13 (Q2)
- [ ] `tests/db/test_no_pii_columns.py` — **edit** `EXPECTED_JSON_COLUMNS` (Q2)
- [ ] `tests/db/test_queue_state.py`, `test_exclusions.py`, `test_listing_events.py`, `test_dupes.py` — repository lanes
- [ ] `tests/pipeline/test_dedup_merge.py`, `test_dedup_revert.py`, `test_filter_stage.py`, `test_criteria_snapshot.py`, `test_capability_surface.py` — stage lanes (reuse `session_factory` + `registry_snapshot`)
- [ ] `tests/api/` — `test_queue_search.py`, `test_queue_signals.py`, `test_queue_excluded.py`, `test_listing_events.py`, `test_searches_crud.py`, `test_run_history.py`, `test_run_reason.py`, `test_merges_view.py` (reuse `client`)
- [ ] `tests/test_config.py` — **edit**: add the new required settings fields to `REQUIRED_SETTINGS_FIELDS` / `LIMIT_FIELDS`
- [ ] Framework install: `.venv-host/bin/python -m pip install 'rapidfuzz==3.14.6'` (gated by `checkpoint:human-verify`)

*(No shared-fixture work is needed: `migrated_db`, `session_factory`, `db_session`,
`client`, `registry_snapshot` and the offline LLM stub already cover every lane.)*

## Security Domain

> `security_enforcement` is `true`, `security_asvs_level` is `1`,
> `security_block_on` is `high` in `.planning/config.json`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth in v1 (D-21); the seam is `Depends(current_user)`; adding Authentik must not change route signatures |
| V3 Session Management | no | No sessions, no cookies (explicitly rejected for the watermark, D-39) |
| V4 Access Control | no | Single local user; no `user_id`/`owner_id`/`tenant_id` columns (asserted by `tests/test_auth_seam.py`) |
| V5 Input Validation | **yes** | Search text → `build_match_expression()` (pure) before FTS5; rule `params_json` validated per kind on write; all SQL bound-parameter; Jinja autoescape on; **no raw HTML from listing text** |
| V6 Cryptography | no | Nothing new; the only secret remains the opencode password (Phase 3) |
| V7 Error Handling & Logging | **yes** | Total functions at boundaries; a malformed rule/query degrades with a recorded reason; PII is never logged (only counts) |
| V12 Files & Resources | no | No file I/O this phase |
| V13 API & Web Service | **yes** | All new routes declare `Depends(current_user)`; MATCH bound; no response echoes untrusted input unescaped |

### Known Threat Patterns for SQLite FTS5 + FastAPI/Jinja2/HTMX

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via a listing description (D-38) | Tampering | Flag-and-count on ingest; **listing text never enters a logic position**; Phase 3 restricts `tools` and keeps untrusted text out of `system` (AP9) |
| FTS5 query-injection / DoS via `MATCH` | Tampering / DoS | `build_match_expression()` quotes every token; verified that raw input otherwise raises |
| SQL injection via the search/rule path | Tampering | Bound parameters only, including `MATCH :expr` (existing discipline, `tests/db/test_fts_triggers.py:39-45`) |
| Stored XSS via listing title/company/description | Tampering/XSS | Jinja autoescape; **never `\|safe`** on listing text; no CDN (so no third-party script surface) |
| PII persistence via `detail_json` / logs | Information Disclosure | Terms/counts only in `detail_json`; the sanitiser drops PII and reports counts; the schema guard keeps PII-shaped *columns* impossible |
| Silent capability drop (a filter the board cannot honour) | Repudiation | `CapabilityWarning` persisted per run + rendered on the criteria page (D-37) and enforced locally post-fetch |
| Destructive revert / merge tampering | Tampering | `listing_dupes` is append-and-mark (never DELETE); revert restores from `snapshot_json`; merge/revert write an audit row with actor + timestamp |
| Unbounded poll / battery drain | DoS (self) | HTTP 286 + `HX-Reswap: outerHTML` stop condition (Phase-1 convention) |

## Sources

### Primary (HIGH confidence)
- In-repo code read this session (verbatim values quoted in-line with path:line):
  `alembic/versions/0001_initial_schema.py`, `app/db/models.py`,
  `app/domain/{listing,sanitize,models}.py`, `app/pipeline/{run,stages}.py`,
  `app/db/repositories/{listing_repo,source_repo}.py`, `app/sources/base.py`,
  `app/api/{runs,deps}.py`, `app/web/routes.py`, `app/config.py`, `app/main.py`,
  `alembic/env.py`, `app/db/session.py`, `tests/conftest.py`,
  `tests/db/{test_migration_contract,test_no_pii_columns,test_fts_triggers}.py`,
  `tests/{test_import_discipline,test_config,test_no_credentials,test_no_cdn}.py`,
  `app/web/templates/html/*`, `pyproject.toml`
- **Live execution this session** against a DB created by `alembic upgrade head`
  (0001): FTS5 `MATCH`/`bm25()`/`rank`/per-column weights/`LIMIT-OFFSET`/porter
  stemming behaviour, the non-deterministic tie order, and 8 `OperationalError`
  inputs from raw user text
- `.planning/phases/02-clean-filtered-queryable-queue/02-CONTEXT.md` (D-25…D-47, verbatim above)
- `.planning/research/ARCHITECTURE.md` §8.1–8.4, §9.1–9.4, §12, §13, §14.3
- `.planning/research/PITFALLS.md` P3, P8, P9, P10, M4, m10
- `gsd-tools query package-legitimacy check --ecosystem pypi rapidfuzz` → `SUS`
  (`too-new`, `unknown-downloads`)
- `gsd-tools query classify-confidence --provider context7 --verified` → `MEDIUM`

### Secondary (MEDIUM confidence)
- `[CITED: https://raw.githubusercontent.com/srbhr/resume-matcher/main/apps/backend/app/services/improver.py]` — the verbatim `_INJECTION_PATTERNS` list and `_sanitize_user_input`; fetched this session; Apache-2.0; no licence header in the file
- `[CITED: https://github.com/rapidfuzz/rapidfuzz/blob/main/docs/Usage/fuzz.rst]` — `token_set_ratio` / `token_sort_ratio` / `ratio` / `WRatio` semantics and the subset-returns-100 example
- `[CITED: https://github.com/rapidfuzz/rapidfuzz/blob/main/docs/Usage/process.rst]` — `process.cdist` / `extract` / `extractOne`
- `[CITED: https://sqlite.org/fts5.html]` — FTS5 external-content, `bm25()`, `rank`, tokenizers, `MATCH` query syntax
- `[CITED: https://sqlite.org/lang_altertable.html]` — SQLite `ALTER TABLE` limits and the table-recreation strategy Alembic batches
- `[CITED: https://www.apache.org/licenses/LICENSE-2.0]` — §4 attribution/NOTICE obligations
- `.planning/research/{SUMMARY,STACK,RESUME-MATCHER-SPIKE}.md`

### Tertiary (LOW confidence)
- The θ default and the 10–15% merge-rate band (carried from research; explicitly
  flagged as untunable without a real corpus in STATE.md)
- `rapidfuzz` download volume (the seam returned `null`)

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** on versions and install mechanics (pip index + two venv
  probes); **MEDIUM** on the fuzzy-scoring *recipe* (Context7 official docs, seam
  tier MEDIUM) and **LOW** on θ
- Architecture: **HIGH** — every schema/code claim is a verbatim read this session
  with a path:line citation, and the FTS5 claim is a live execution result
- Pitfalls: **HIGH** for the execution-verified ones (FTS5 syntax errors,
  non-deterministic ties, token-set subset behaviour, guard assertions); **MEDIUM**
  for the merge/negative-memory and rule-scope pitfalls (derived from the research
  docs plus schema reading)

**Research date:** 2026-09-16
**Valid until:** 2026-10-16 (30 days — schema and code facts are stable; re-check
`rapidfuzz` wheel availability for the pinned Python if the environment changes)




