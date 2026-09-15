# Phase 2: Clean, Filtered, Queryable Queue - Context

**Gathered:** 2026-09-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Turn the Phase-1 walking skeleton into a queue the user trusts: **cross-source dedup/merge with a reversible audit trail and a visible merge rate**, **deterministic hard-rule filtering that rejects listings before any LLM call and records exactly which rule fired**, **named/versioned search criteria editable from the UI**, **full-text search over the queue**, **new-since-last-visit and stale signals**, **save/hide recorded as append-only events**, and **run history that explains what a run did and why the queue is empty**.

**Requirement scope:** QUEUE-03, QUEUE-04, QUEUE-06, QUEUE-07, QUEUE-08, QUEUE-09, CRIT-01, CRIT-02, CRIT-03, FILT-01, FILT-02, FILT-03, FILT-04, RUN-03, RUN-04.

**Deliberately NOT in this phase:** any LLM call, ranking, scoring or rationale (Phases 3/5); CV modelling, tailoring, LaTeX compile (Phases 4/6); application tracker (Phase 7); scheduling / next-run / UI health endpoint (Phase 8); phone-first responsive pass (Phase 8, D-16); Adzuna adapter (v2/Phase 8 conditional); cross-source "also seen on…" links (SRC-12, v2).

</domain>

<decisions>
## Implementation Decisions

### Merge policy & revert (discussed)
- **D-25:** **High-confidence matches merge automatically during the run** — no propose-and-confirm review queue. Undoing the *user-visible* half means reworking the ingest stage and the queue/merge UI, but the triggering rationale is the daily-loop cost: "High confidence matches merge automatically." — **Reversibility:** costly — reverting to propose-and-confirm touches the dedup stage, the queue read model and the merge UI, and any listings already merged would need unpicking via the snapshot.
- **D-26:** **A full, inspectable record of the merged twin is retained and surfaced in the job's detail view.** The user's words: "Do maintain a record of what the job listing was so that the user can inspect themselves. Maybe show it in the details of the job." Implemented via `listing_dupes.snapshot_json` (column already ships in migration 0001), shown as "merged from N sources" with the twin's original fields.
- **D-27:** **First-seen listing stays canonical; blanks are filled from the twin; nothing non-null is ever overwritten.** The listing that arrived first keeps title, company and `canonical_url`; a later matching source only contributes to NULL/empty fields (salary, location, description). — **Reversibility:** costly — a later switch to source-priority or per-field precedence rewrites already-merged listings; the snapshot makes the data recoverable, but the rule change touches every merged row.
- **D-28:** **Revert = full undo + negative memory.** Reverting restores the surviving listing's snapshot fields, un-hides the twin and marks `listing_dupes.reverted_at`; the pair is recorded as deliberately-distinct so the next run does not silently re-merge it.
- **D-29:** **Dedicated Merges audit view + merge-rate stat**, with one-click revert; job detail also shows "merged from N sources" with the snapshot. Satisfies QUEUE-09 directly ("see the merge rate and the rows behind it") and gives revert a home. — **Reversibility:** reversible.
- **D-30 (agent discretion):** **Merge timing** — Tier-2 dedup runs as a **post-persist stage inside `run_pipeline()`** (after all sources' rows are persisted), not inline per source, because a cross-source candidate pair needs both rows to exist before it can be scored. Consistent with `research/ARCHITECTURE.md` §8.1 (dedup placement).
- **D-31 (agent discretion):** **Tier-2 algorithm** — `rapidfuzz` token-set ratio over the normalised `(company, title, location)` tuple already produced by `app/domain/listing.py` (`normalise_company_name`, `title_norm`, `company_norm`, `location_norm`), with `listings.blocking_key` (indexed) used to narrow candidates before scoring. **θ is a Settings value with a tuning task against the first real corpus, never a frozen constant** (ROADMAP Phase 2 Notes + STATE.md Phase-2 blocker). `rapidfuzz` is not yet declared in `pyproject.toml` — it must be added deliberately. — **Reversibility:** reversible.

### Criteria & filter tunability (discussed)
- **D-32:** **One unified named search carries both the fetch query and its own exclusion rules.** A named search (e.g. "Dublin Python, remote, €70k+") holds keywords / location / remote / salary floor / seniority **and** its exclusion rules; enabling it adds it to the run, and the queue unions all enabled searches (scope-to-one supported). Reuses `searches.criteria_json` + `searches.enabled` + `searches.is_default`. — **Reversibility:** costly — splitting later into "searches fetch, one global filter set" would re-home every rule and rework the criteria + queue UI.
- **D-33:** **Past-run reproducibility = criteria snapshot stored on each run + `searches.version` bumped on edit.** No version-history table and no diff/rollback UI in v1: a run row carries the exact query+rules it used, and each `listing_exclusions`/`scores` row records `criteria_version`. — **Reversibility:** reversible — adding a `criteria_versions` history table later is additive.
- **D-34:** **Filter rules are typed rows in a new `filter_rules` table** (migration 0002): `kind` (`salary_floor` | `exclude_keyword` | `location` | `remote` | `seniority` | `company_blocklist`), `params_json`, `enabled`, ordering, and a `search_id` FK. The UI renders a purpose-built **form per kind** — no raw JSON editor, no Jinja in any logic position. Evaluators are **pure functions in `app/domain`** (the domain-import-discipline test forbids I/O there). Every rejection writes `listing_exclusions(rule_id, rule_kind, detail_json, run_id)`.
- **D-35:** **"Why was this excluded" is an inline `Show excluded` toggle on the queue** — rejected listings appear dimmed with a chip naming the firing rule and a per-rule count; excluded listings are out of the default view and out of any future LLM spend. Satisfies FILT-03 without a second browsing surface.
- **D-36:** **Rules are re-evaluated from scratch every run; exclusions are per-run observations, not permanent blacklist state.** One `listing_exclusions` row per listing+run+rule (full history, per-rule counts per run). Retuning a rule can bring a previously-excluded listing back into the queue; a listing the board no longer returns simply stops appearing.
- **D-37 (carried, pre-answered):** The **criteria compiler must consume each adapter's declared capabilities so an unsupported filter is reported, not silently ignored** (ROADMAP Phase 2 Notes; SRC-09). `compile_query_for_source()` + `CapabilityWarning` already ship in `app/sources/base.py` and are currently unconsumed — Phase 2 consumes them.
- **D-38 (carried, pre-answered):** Extend `app/domain/sanitize.py` with an **`_INJECTION_PATTERNS`-style injection rule set**, exactly as deferred from Phase 1 (ROADMAP Phase 2 Notes): pattern-copied from Resume-Matcher's `improver.py`, **attributed per Apache-2.0 §4**. The existing `looks_like_instructions` / `INSTRUCTION_MARKERS` seam is the insertion point.

### Queue browse signals (discussed)
- **D-39:** **"New since last visit" is a DB watermark** — `last_queue_view_at` in a small user-state row, updated when the queue is opened, plus an explicit **"Mark all as seen"** action that advances it deliberately. Cross-device, restart-safe and assertable in the DB-backed test harness (a cookie was explicitly rejected). — **Reversibility:** reversible.
- **D-40:** **Stale = `last_seen_at` older than a configurable `stale_after_days` (default ~14) OR `is_active = false`.** Robust to partial runs and board pagination (SRC-05); reuses existing columns. Stale rows get a badge but stay searchable.
- **D-41:** **Save and Hide are distinct actions**, written as **append-only `listing_events`** (event types already exist: `save`/`unsave`/`hide`/`unhide`/`shortlist`/`view`) with current state projected from the latest event. Hidden listings leave the default queue and are reachable via a `Hidden` filter with one-tap undo; saved listings get a `Saved` filter and a star. The Phase-1 append-only triggers are reused unchanged.
- **D-42:** **FTS5 MATCH over `title` + `company_norm` + `description`** (the existing `listing_fts` external-content table), ranked by **bm25 only when a query is present**; with no query the queue keeps the deterministic recent-first order the Phase-1 tests pin (`first_seen_at desc, id desc`). Pagination is HTMX "Load more"; **MATCH uses bound parameters only** (established FTS discipline). Search stays inside the active criteria scope and respects the Hide / Show-excluded toggles.

### Run history & explainability (discussed)
- **D-43:** **Dedicated `/runs` page** — one row per run (started/finished, trigger `manual|schedule`, per-source fetched, `deduped_count`, `filtered_count`, errors, duration) expandable to detail — plus a compact **last-run strip on the queue** linking there. Gives RUN-04 a real surface and makes the existing (partly unwritten) `runs` counters meaningful. — **Reversibility:** reversible.
- **D-44:** **A thin/empty queue is explained by a persisted structured reason + counts + a rendered sentence**, plus a **collapsible raw stage log**. Reason enum at minimum: `no_sources_enabled` | `all_sources_failed` | `zero_fetched` | `all_filtered` | `nothing_new` | `mixed`, each with the counts behind it (per-source fetched/blocked, filtered-by-rule breakdown, duplicates-already-seen). Computed **deterministically — no LLM** (Phase 3 is not available yet).
- **D-45:** **"Run search now" runs every enabled search**; the criteria page additionally offers a per-search **"Run this one"** action for iterating on a single query. No picker dialog on the main trigger (stays one tap). The planner decides the `runs`-row shape when several searches run (one run per search vs one run with per-search sections).

### Carried from Phase 1 / research (pre-answered — do not re-litigate)
- **D-46:** Stack and schema are locked: Python 3.13, FastAPI 0.141.1, uvicorn `--workers 1`, SQLite WAL + SQLAlchemy 2.0 + Alembic, **FTS5 external-content (`porter unicode61`)**, Jinja2 + HTMX + Alpine + Tailwind (no CDN). Tier-1 upsert is the two-key design; `current_user` is on every route with **no `user_id` columns in v1**; `run_pipeline()` is the single pipeline callable; filtering is deterministic and precedes any LLM; `app.domain.*` imports no I/O. (Phase-1 D-17…D-24.)
- **D-47:** Migration 0001 already ships the Phase-2 scaffolding — `listing_dupes` (with `snapshot_json`/`reverted_at`), `listing_exclusions`, `listing_events` with append-only triggers, `searches` (+`version`), the `runs` counters, `listings.blocking_key`, and `listing_fts` + its triggers — but **none of the Phase-2 behaviour, repositories, routes, settings or templates exist**.

### the agent's Discretion
- Exact **θ default** and the tuning procedure (D-31); whether the fuzzy score or the normalised-tuple match is the primary gate; the **rules-in-a-blocking-window** candidate strategy.
- **Merge stage placement and ordering** within `run_pipeline()` (D-30) and how a merge interacts with the run's `deduped_count`.
- The exact **`_INJECTION_PATTERNS` catalogue** (D-38) and which identifiers are dropped vs hashed.
- The **`runs`-row shape when multiple searches run** (one run per search vs one run with per-search sections), and the "Run this one" URL/route shape (D-45).
- **Run-history retention/pruning** policy, queue **page size**, and the exact default rule vocabulary shipped on day one.
- Whether **`Show excluded`** also lists excluded-but-merged rows, and how `Load more` interacts with the excluded toggle (D-42).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition & requirements
- `.planning/ROADMAP.md` — Phase 2 goal, the five success criteria, the Phase-2 **Notes** (θ as a setting + tuning task; `_INJECTION_PATTERNS` extension; criteria compiler consumes capabilities), and the Phase-2 dependency on Phase 1.
- `.planning/REQUIREMENTS.md` — QUEUE-03/04/06/07/08/09, CRIT-01/02/03, FILT-01/02/03/04, RUN-03/04; plus the Out-of-Scope table (vector ranking, per-listing notifications, board-specific columns, 100% ATS optimisation).
- `.planning/PROJECT.md` — Core Value, Constraints (local-only, no-auth, cost), Key Decisions.
- `.planning/STATE.md` — Blockers/Concerns, in particular **[Phase 2] Dedup threshold θ and the merge-rate band are untunable without a real corpus — leave as a setting + tuning task**, and the accumulated Phase-01 decisions D-17…D-24.
- `.planning/WINDOWS.md` — open items #1/#2/#4 (compose smoke unrun; dependency-legitimacy human check at phase verification; `/health` probe not a reliable proxy for `fetch()`).

### Phase 1 artifacts (the codebase's own conventions)
- `.planning/phases/01-walking-skeleton-foundations/01-CONTEXT.md` — **D-01…D-24 are locked decisions**; read before planning (stack, adapter contract, two-key upsert, migration-is-the-schema-test, auth seam, run execution, sanitize stage, domain import discipline).
- `.planning/phases/01-walking-skeleton-foundations/01-PATTERNS.md` — the reuse patterns Phase 2 must follow unchanged (purity + import discipline, total boundary functions, universal auth seam, PII-unrepresentable, blocking-call boundary, migration-is-the-schema-test, config-not-constants, bound FTS params, HTMX 286).
- `.planning/phases/01-walking-skeleton-foundations/01-VERIFICATION.md` and the `01-*-SUMMARY.md` files — what was actually built and the recorded residual/human-judgment items.

### Research — authoritative for this phase
- `.planning/research/ARCHITECTURE.md` — **§8.1 (dedup placement)**, §9.1–9.3 (schema + FTS5 + the `search` port), **§9.4 (schema-phase acceptance criteria)**, §12 (Patterns 3/4/5/6), §13 (anti-patterns), §14.3 (build order).
- `.planning/research/PITFALLS.md` — **P3 (dedup)**, P8 (non-backfillable data model), **M4 (FTS5)**, **P9 / Pattern 6 (why is the queue empty?)**, m10 (no global last-run), P10 (total functions at boundaries).
- `.planning/research/SUMMARY.md` — Disagreements Resolved (D1–D10) and the **Phase 2** section.
- `.planning/research/FEATURES.md` — MVP "Launch With (v1)" and anti-features AF-1…AF-15 (entity-stuffing, alert fatigue, etc.).
- `.planning/research/STACK.md` — Q4 (SQLite/SQLAlchemy/Alembic + the Tier-2 `rapidfuzz` design), Q7 (opencode — later phases), and "What NOT to Use" (`LIKE '%term%'` → FTS5).
- `.planning/research/RESUME-MATCHER-SPIKE.md` — the `_INJECTION_PATTERNS` reuse point and the required Apache-2.0 §4 attribution (D-38).

### Code — what Phase 2 builds on
- `alembic/versions/0001_initial_schema.py` — the full schema, FTS5 + triggers, and the two Tier-1 dedup indexes (read before writing migration 0002).
- `app/db/models.py` — ORM mirror of 0001; the authoritative table/column inventory.
- `app/db/repositories/listing_repo.py` — the Tier-1 two-key upsert (`upsert_listing_source`, `upsert_listing`, `UpsertOutcome`) to extend for Tier-2.
- `app/db/repositories/source_repo.py` — read-model/repo shape to copy for criteria/runs/events/exclusions/dupes/FTS repos.
- `app/domain/listing.py` — `canonical_url`, `blocking_key`, `content_hash`, `raw_fingerprint`, `normalise_company_name`, `annualise_salary` (pure inputs to dedup + filter rules).
- `app/domain/sanitize.py` — `sanitize_text`, `looks_like_instructions`, `INSTRUCTION_MARKERS` (the D-38 insertion point).
- `app/pipeline/run.py`, `app/pipeline/stages.py` — `run_pipeline()`, `_persist_result`, `normalise_listing`, `Stage`/`StageCounts` (where dedup + filter stages land).
- `app/sources/base.py` — `compile_query_for_source`, `CapabilityWarning`, `SearchQuery`, `SourceCapabilities` (D-37).
- `app/api/runs.py`, `app/web/routes.py`, `app/web/templates/html/*` — run trigger/poll, the queue read, and the HTMX fragment patterns to extend.
- `app/config.py` — the single `Settings` class; `thresholds()` in `app/probe/survival.py` is the settings-reader pattern for θ and `stale_after_days`.
- `tests/conftest.py`, `tests/db/test_migration_contract.py`, `tests/test_import_discipline.py`, `tests/test_no_credentials.py`, `tests/db/test_no_pii_columns.py`, `tests/test_auth_seam.py`, `tests/test_config.py`, `tests/db/test_fts_triggers.py` — the guards Phase 2 must not break (see code_context).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/db/repositories/listing_repo.py` — `upsert_listing_source` / `upsert_listing` / `UpsertOutcome`: the Tier-1 key-hit/miss pattern to extend for Tier-2 merge.
- `app/db/repositories/source_repo.py` — `enabled_source_names`, `ensure_registered_sources`, `get_source_health`, `SourceHealth`: the read-model + repo shape to copy for criteria/search, runs, events, exclusions, dupes and FTS repos.
- `app/domain/listing.py` — `canonical_url`, `blocking_key`, `content_hash`, `raw_fingerprint`, `normalise_company_name`, `annualise_salary` — pure, unit-tested inputs to dedup and filter rules.
- `app/domain/sanitize.py` — `sanitize_text`, `looks_like_instructions`, `INSTRUCTION_MARKERS` — the extension seam for the D-38 injection catalogue.
- `app/pipeline/stages.py` — `normalise_listing`, the `Stage` protocol and `StageCounts` — the stage/counter pattern new dedup and filter stages follow.
- `app/sources/base.py` — `compile_query_for_source` + `CapabilityWarning` already ship, unconsumed; Phase 2 is their first consumer (D-37).
- `app/api/runs.py` — `render_run_fragment`, `TERMINAL_STATUSES`, the background-task set: the template for run-history and event routes.
- `tests/conftest.py` — `migrated_db`, `session_factory`, `client`, `registry_snapshot`, `OfflineLLMBackend`: reuse for every Phase-2 test lane.

### Established Patterns
- **Repositories are the only place SQL lives**; functions take an `AsyncSession` explicitly and never commit (the caller owns the commit).
- **`app.domain.*` is pure** — the AST test forbids `httpx`, `sqlalchemy`, `jobspy`, `jinja2`, `subprocess`. Fuzzy scoring and rule evaluation belong in `app/domain`; every DB write stays in a repository.
- **Settings, not constants** — one `Settings` class; `thresholds()`-style readers; `tests/test_config.py` scans `app/probe` + `app/pipeline` for hard-coded distinctive literals. θ and `stale_after_days` must be settings.
- **Append-only events are enforced by DB triggers**, not application code (`listing_events`).
- **HTMX** — `hx-get`/`hx-post` with `hx-trigger="every 2s"`, `hx-swap`; the polling fragment stops on HTTP **286** + `HX-Reswap: outerHTML`; Jinja autoescape; no CDN.
- **One `runs` row per trigger** — the request commits the row and passes `run_id` into `run_pipeline()`; the pipeline is never awaited (202).
- **structlog** with stage-named events; counts/errors persist into `runs.source_counts_json` / `runs.errors_json`.
- **FTS MATCH uses bound parameters only** (`tests/db/test_fts_triggers.py`) — Phase 2 must not regress this.
- **Queue ordering determinism** (`first_seen_at desc, id desc`) is pinned by a Phase-1 e2e test.

### Integration Points
- `app/pipeline/run.py` — insert the **dedup (Tier-2) and hard-filter stages** after persist and before `_finish`; populate `deduped_count` (currently mis-set to the created count) and `filtered_count` (currently never written); write `listing_exclusions` and `listing_dupes`.
- `app/pipeline/run.py` `_fetch_one` — where `compile_query_for_source`'s capability warnings get surfaced to the criteria compiler.
- `app/web/routes.py` `queue()` — replace the inline query with a queue repository + FTS/new/stale/filter params; add search, flag and event HTMX partials.
- `app/api/runs.py` — add run-history and exclusion-detail routes (the runs page + last-run strip).
- `app/main.py` — register the new routers.
- `app/config.py` — add `dedup_*`, `stale_after_days`, filter/rule settings.
- `app/db/repositories/` — add criteria/search, run, listing-event, listing-exclusion, listing-dupe and FTS repositories.

### Hard constraints Phase 2 must not break
- **Migration contract:** `tests/db/test_migration_contract.py` asserts **`alembic_version == ["0001"]` and a single head**. Adding **migration 0002** (required for `filter_rules`, the last-visit watermark, run reason/raw-log columns, and any criteria-snapshot columns on `runs`) will fail that test — it must be **deliberately updated alongside** the migration, not treated as a regression.
- **PII-negative JSON allow-list:** `tests/db/test_no_pii_columns.py` asserts exact equality against `EXPECTED_JSON_COLUMNS`; every new JSON column must be added deliberately and no column may carry email/phone tokens.
- **No credential path:** `tests/test_no_credentials.py` flags env reads/kwargs/calls matching password/token/cookie/login/email/phone; criteria/filter UI code must not trip the raw-token scan.
- **Auth seam:** `tests/test_auth_seam.py` requires every route to depend on `current_user` and forbids `user_id`/`owner_id`/`tenant_id` columns.
- **Single-run-row:** `tests/api/test_run_trigger.py` — one trigger = one `runs` row.
- **Dependency gap:** `rapidfuzz` is **not declared** in `pyproject.toml` yet — it must be added before Tier-2 dedup can land.

</code_context>

<specifics>
## Specific Ideas

- The user's own framing of merge transparency: *"Do maintain a record of what the job listing was so that the user can inspect themselves. Maybe show it in the details of the job."* The twin snapshot must be human-inspectable from the job detail, not merely a DB row.
- The daily-loop cost is the yardstick: the merge path is auto because waiting for confirmation on every duplicate re-introduces the dead time the project exists to remove.
- θ and the merge-rate band are explicitly **not** to be frozen — the 10–15% band in research comes from a different market and query shape (ROADMAP Phase 2 Notes / STATE.md Phase-2 blocker).
- "Why is the queue empty today?" is a first-class product question (PITFALLS P9 / Pattern 6), not a debugging afterthought — hence the structured reason enum.

</specifics>

<deferred>
## Deferred Ideas

- **Cross-source "also seen on…" links (SRC-12)** — v2, not Phase 2. The Merges audit view and the job-detail "merged from N sources" snapshot are the in-phase equivalents; they audit a merge, they are not the v2 cross-linking feature.
- **Adzuna adapter (SRC-11)** — v2; promoted from hedge to primary only if the Phase-1 survival verdict says LinkedIn/Indeed do not survive (decided at Phase 8, D-04).
- **Ranking, scoring, rationale (Phase 5)** — Phase 2 filters and cleans only; it makes no LLM call.
- **CV fact store / LaTeX compile (Phase 4, parallel) and tailoring (Phase 6)** — untouched here.
- **Application tracker (Phase 7)** — Save/Hide are queue signals, deliberately not application stages (D-41).
- **Scheduling, next-run display, UI health endpoint, phone-first pass (Phase 8)** — Phase 2 keeps the manual trigger and the desktop-first layout.
- **Criteria version-history table with diff/rollback** — consciously deferred (D-33); the snapshot-plus-version design keeps the option open.

</deferred>

---

*Phase: 2-Clean, Filtered, Queryable Queue*
*Context gathered: 2026-09-15*
