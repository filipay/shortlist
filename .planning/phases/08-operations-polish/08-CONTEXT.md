# Phase 8: Operations + Polish - Context

**Gathered:** 2026-10-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 8 makes the pipeline finish the job it started: it runs itself on a schedule, tells the truth about its own health without a human going to look, and can be driven from a phone. It also pays down the two retention debts the earlier phases deliberately deferred.

**In scope (the 5 requirements):**
- **RUN-05** — user can schedule recurring runs
- **RUN-06** — user can see when the next scheduled run will happen
- **RUN-07** — user can check system and source health from a health endpoint surfaced in the UI
- **PLAT-06** — scheduled runs are single-worker safe and persist across restarts
- **UI-06** — the UI is usable from both a laptop and a phone browser

**Also in scope by explicit deferral from earlier phases:**
- Retention/pruning of history — `cv_artifacts` (D-117, deferred twice to Phase 8), run history (`run_repo.RUN_HISTORY_LIMIT`'s own comment: "pruning is a Phase-8 operations item"), and the growth-prone logs.

**Out of scope (do not build):**
- Any automatic adapter escalation or a manual "enable Adzuna" control (SRC-11, v2)
- Weekday/days-of-week scheduling, multi-user, Authentik login
- A live in-flight run indicator on the health page
- Automatic/scheduled pruning
- Full responsive parity on admin surfaces (criteria editor, merges audit, runs history, settings)
- "Also seen on", export, batched notifications (v2, per ROADMAP)

**Success Criteria (from ROADMAP, what must be TRUE):**
1. User can schedule recurring runs and see when the next run will happen.
2. Scheduled runs persist across restarts and execute only once with a single worker.
3. User can check system and source health from a health endpoint surfaced in the UI, with source status surfaced from recorded stop signals rather than auto-escalation.
4. The UI is usable from both a laptop and a phone browser, with all assets vendored locally and no CDN dependency. *(Note: UI-07's vendoring is already satisfied in the current codebase — see Code Context.)*

</domain>

<decisions>
## Implementation Decisions

### Scheduling model & run safety

- **D-151:** **One global schedule**, not per-search. It runs the pipeline exactly as today's `POST /runs` does — `search_id=None`, i.e. the union of all enabled searches. The existing `searches.schedule_cron` column stays **unused and unpopulated**; it is not the storage for this feature.
- **D-152:** The user configures the schedule on the **Settings page with a time picker: pick the time-of-day and the timezone**. A cron string is a fine internal representation but the user never types cron. Days-of-week selection is explicitly deferred.
- **D-153:** The schedule lives in a **new singleton DB config row**, runtime-editable with no restart — the same shape as `RankingConfig`/`ApplyConfig` (`id = 1` pinned by a named CheckConstraint, JSON payload, `updated_at`). It must be shaped so a future `user_id` column can be added, but **no `user_id` column exists in v1** (D-21). — **Reversibility:** costly — swapping storage later means a new Alembic migration plus every reader/writer of the row; the shape decision is what makes the multi-user future cheap or expensive.
- **D-154:** **Missed runs are skipped, surfaced, and never overlapped.** A scheduled run missed by more than the 1-hour grace window is skipped outright — never back-filled or caught up — but its absence IS surfaced to the user ("last scheduled run was missed"). A scheduled trigger that fires while a run is already in flight **skips** rather than starting a second concurrent pipeline, and records why it skipped.

### Health surface & source signals

- **D-155:** Health lives on a **dedicated `/health` page** (a system section plus the full per-source table) **and the existing compact queue-page strip stays**.
- **D-156:** The **source health badge is computed from RECORDED run outcomes** — per-source fetch status and recorded stop signals over the last N runs — not from the live probe stamp. **The health page reads the DB only and never puts a request on a job board**: a page view must not be a scrape. The live probe survives as an explicit, separate operator action, never as a side effect of viewing health.
- **D-157:** The system section is **assembly of data that already exists, not new measurement**: the four dependency probes (database, opencode including `auth_configured`, Tectonic/LaTeX engine, CV fact store) **+ the next scheduled run** ("next run in 3h 12m" / "scheduling off") **+ the last run's status and one-line reason**.
- **D-158:** The computed **Adzuna promotion verdict is shown READ-ONLY on `/health` as evidence** (e.g. "Adzuna hedge: 2/3 blocked runs — condition not met") with a link to the probe document. **Nothing escalates or switches adapters automatically**; the decision stays human. A manual enable-Adzuna control is not in this phase.

### Responsive scope & acceptance

- **D-159:** **The primary journey must be genuinely comfortable on a phone**: the queue, listing detail, `/health`, the run control, and the applications tracker. **Admin surfaces** (criteria editor, merges audit, runs history, settings) must not break, but stay desktop-first.
- **D-160:** Responsive rules are authored in **`assets/tailwind/input.css`** — the existing Tailwind 4.3.3 build input — and rebuilt with the pinned CLI into `static/vendor/app.css`. **Card-reflow** (rows becoming label:value blocks) is used **only for the journey tables** (queue, applications, health). Every other table keeps its current markup wrapped in an **accessible scroll region (`tabindex="0"`, `role="region"`, `aria-label`)**. **No JavaScript.**
- **D-161:** Verification is the project's existing pattern: a **`/gsd-ui-review` 6-pillar audit** over the responsive surfaces (as phases 02/05/06/07 did) **plus a documented operator-run checklist in a runbook** — named viewport widths (320/375/768) crossed with the journey pages. Docker and a browser are absent from the agent sandbox, so operator-run checks are the established norm (`docs/runbook-compose-smoke.md`).
- **D-162:** On a phone, a queue row **restacks ALL the data the desktop row shows** — title, company, location, badges, score, posted date, exclusion chips, actions — as label:value lines. Nothing hidden, nothing requiring a second tap.

### Retention / pruning of history

- **D-163:** Phase 8 may prune: **runs history + stage logs**, **tailored CV artifacts (the DB rows AND the `.tex`/`.pdf` files on disk)**, the **source request log**, and **inactive/stale listings**. **The user chooses which category to prune and how old a record must be to qualify** — pruning is per-category and per-threshold, not one global switch.
- **D-164:** **Audit events are excluded from pruning.** `listing_events` and `application_events` are never pruned; the append-only trigger (D-131) and the per-row history timeline (D-134) both survive intact. — **Reversibility:** costly — reversing this later means deliberately weakening or bypassing a DB trigger that currently makes the tracker's history tamper-evident.
- **D-165:** Four **hard guards** hold even under an aggressive age threshold:
  1. **A floor of recent runs is always kept** regardless of age, because the source badge and the Adzuna promotion verdict read the last N runs.
  2. **The `llm_calls` ledger is never pruned** — it backs the per-run and rolling-24h spend ceilings, so pruning it would silently uncap spending.
  3. **An artifact linked to an application is never pruned** (D-129 — an applied row points at the specific `ok` artefact that was sent).
  4. **The newest `ok` artifact per listing is never pruned** (D-117 — the listing page shows the most recent one per listing).
- **D-166:** **Pruning is manual only.** A control in the Settings danger-zone: pick a category and an age threshold, see a **dry-run preview** ("this will delete 42 runs, 118 artifacts, 3.1 GB"), **confirm**, and an **audit line records what was deleted**. Nothing is destroyed silently. There is **no automatic pruning on the nightly run**.
- **D-167:** **Pruning a stale listing is a HARD DELETE** of the listing and everything hanging off it — its scores, its `listing_sources` provenance rows, its `queue_state`. **Accepted consequence:** `listing_sources` carries the `UNIQUE(source, source_listing_id)` upsert key, so once those rows are gone a re-post of the same job returns as a brand-**new** listing with a new `first_seen_at`, and prior dismissals / seen-before memory are gone. — **Reversibility:** one-way — deleted listing rows, scores and provenance are unrecoverable; there is no tombstone and the upsert key that would have recognised a re-post has been removed by the same operation.
- **D-168:** The per-category age thresholds live **in the same new singleton settings row as the schedule** (D-153), stored as a JSON payload — one table, one migration, mirroring how `ApplyConfig` already holds the user's screening questions.

### the agent's Discretion

- Exact table name and JSON key names for the new settings row; the exact route path for the prune control and its preview.
- Precise copy for status/warning text (the badge vocabulary, the "missed" notice, the preview wording).
- Whether the `/health` page reuses the existing `_health_strip` renderer or has its own partial, provided the two cannot disagree about `auth_configured` (the D-138 constraint `app/web/routes.py` documents today).
- Breakpoint values and the exact CSS mechanism, within D-160's constraints.
- Whether the retention floor in D-165(1) is expressed as a count or as a minimum age.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition & requirements
- `.planning/ROADMAP.md` — Phase 8 entry (goal, mode `mvp`, `Depends on: Phase 7`, the 5 requirements, the 4 success criteria, the "scheduling is deliberately late" note)
- `.planning/REQUIREMENTS.md` — RUN-05, RUN-06, RUN-07, PLAT-06, UI-06; plus the Out of Scope rows ("Mobile app — Web-first; the responsive UI covers phone use", "Real-time listing feeds")
- `.planning/STATE.md` — current focus, blocking unknowns, deferred items

### Stack & conventions (binding)
- `AGENTS.md` §Technology Stack — **APScheduler 3.11.3** (`4.x is still alpha — do not use it`), uvicorn `--workers 1` (N workers ⇒ N schedulers), APScheduler's `SQLAlchemyJobStore` needs a **sync** engine, `coalesce=True` / `max_instances=1` / `misfire_grace_time=3600` / `replace_existing=True`, timezone explicitly **`Europe/Dublin`** (don't inherit container UTC; don't let DST shift the morning run); UI-07 vendoring; multi-stage Docker healthcheck
- `.planning/CONVENTIONS.md` — the seven binding verification rules (anchor structurally never lexically; fail closed visibly; fixtures with the literal repro string; test the failure class not the instance; the fix author does not certify closure; no false guarantees in prose; asymmetric verification pressure)
- `pyproject.toml` — the exact-pin convention (D-17 / PLAT-04). **Adding APScheduler means adding a new exact pin here.**

### Scheduling & the pipeline entry point
- `app/pipeline/run.py` — `run_pipeline(trigger, search_id, session_factory, run_id=)`; its docstring already names Phase 8's scheduler as a caller; `TERMINAL_STATUSES`
- `app/api/runs.py` — the manual `POST /runs` path the scheduler must mirror (background task + strong-ref set + `202` + fragment); D-43's `286` + `HX-Trigger: run-finished` polling contract
- `app/main.py` — `lifespan`, the only place a scheduler start/stop can go, and the D-08 rule that it must not hard-fail
- `app/db/session.py` — `get_session_factory()` (the factory background work must use) and `build_engine`'s WAL pragmas
- `app/config.py` — `Settings`; **`database_url_sync`** exists specifically for tools that need a sync engine

### Health & source signals
- `app/api/health.py` — `GET /health` always answers 200; the `opencode.auth_configured` field and the D-08 degraded-tolerant contract
- `app/db/repositories/source_repo.py` — `get_source_health`, `VALID_HEALTH`, `record_probe_result` (its only caller is the probe), `_last_success_run` / `_latest_run_for` (already run-derived — the precedent for D-156)
- `app/probe/probe.py` — `SourceStatus`, `probe_all(session_factory=...)`, the TTL cache
- `app/probe/survival.py` — the S1–S6 signals, `classify_fetch_side(..., stop_signal=...)`, `adzuna_promotion_condition(evidence)` (the verdict D-158 shows read-only)
- `app/web/routes.py` — `_health_strip` (never raises) and the D-138 rule that the strip and `/health` must not disagree
- `app/web/templates/html/_health_strip.html`, `app/web/templates/html/queue.html`

### Retention
- `app/db/repositories/run_repo.py` — `RUN_HISTORY_LIMIT = 50` and its "pruning is a Phase-8 operations item" comment; `STAGE_LOG_RENDER_LIMIT` / `STAGE_LOG_ERROR_LIMIT`
- `app/db/repositories/cv_artifact_repo.py` — "Retention/pruning is deliberately Phase 8 and is not implemented here"
- `app/db/models.py` — `CvArtifact` (L399–431), `Application` (L462–483), `ApplicationEvent` (L486–494) + its append-only trigger, `Run` (L334+), `ListingSource` (`UNIQUE(source, source_listing_id)`), `RankingConfig` (L111–137) and `ApplyConfig` (L493–512) as the singleton-config precedent
- `.planning/phases/06-tailoring-and-verification/06-CONTEXT.md` — **D-117** (every compile inserts a NEW row; older rows retained as history; retention deferred to Phase 8)
- `.planning/phases/07-apply-package-and-tracker/07-CONTEXT.md` — **D-129** (applied requires an `ok` artefact), D-131 (append-only trigger), D-134 (timeline), and the explicit "application retention/pruning and scheduled runs — Phase 8" deferral

### Responsive UI & verification
- `assets/tailwind/input.css` — **the only place responsive CSS may be authored** (D-160)
- `Dockerfile` L14–19 (and `Dockerfile.texlive` L32–37) — the pinned `tailwindcss@4.3.3` build that produces `static/vendor/app.css`
- `app/web/templates/html/base.html` — viewport meta, vendored asset tags, nav
- `app/web/templates/html/settings.html` — the danger-zone section the prune control joins
- `docs/runbook-compose-smoke.md` — the operator-run-check precedent that D-161's checklist follows
- `.planning/phases/07.1-*/07.1-UI-SPEC.md`, `.planning/ui-reviews/`, `02-UI-REVIEW.md`, `05-UI-REVIEW.md`, `06-UI-REVIEW.md`, `07-UI-REVIEW.md` — the established 6-pillar audit artefacts

### LLM backend seam (constrains the health page's opencode report)
- `docs/runbook-opencode-contract.md` — the V2 contract, the pinned server version, and the **accepted residual prompt-injection risk**
- `.planning/phases/07.1-*/07.1-CONTEXT.md` — D-136/D-137 (`auth_configured`, `ERROR_KIND_UNAUTHENTICATED`, the 401-is-not-a-boot-failure rule)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`run_pipeline(trigger, search_id, session_factory, run_id=)`** (`app/pipeline/run.py:706`) — already the single pipeline entry point, already documented as Phase 8's call target, already accepts a pre-created `Run` id. The scheduler adds a caller, not a code path.
- **`Run.trigger` already permits `'schedule'`** via `ck_runs_trigger` (`models.py:334-338`) — no migration needed for the trigger value.
- **`asyncio.create_task` + `_BACKGROUND_TASKS` strong-ref set** (`app/api/runs.py:56`) — the established background-task shape a scheduled trigger can reuse.
- **`get_session_factory()`** (`app/db/session.py`) — deliberately exists so background work does not outlive a request-scoped session.
- **`RankingConfig` / `ApplyConfig` singleton pattern** — `id = 1` CheckConstraint + JSON payload + `updated_at`; the exact template for D-153/D-168, including the `tests/db/test_no_pii_columns.py` allow-list requirement for a new JSON column and the `RESET_KEPT_TABLES` question in `app/api/settings.py` for user configuration.
- **`_health_strip(session, backend)`** (`app/web/routes.py:74`) — a decorative read that never raises and already computes `auth_configured` from the same helper `/health` uses.
- **`get_source_health` + `_last_success_run` / `_latest_run_for`** — run-derived source facts already exist; D-156 extends that, it does not invent it.
- **`adzuna_promotion_condition` / `classify_fetch_side(stop_signal=...)`** — the verdict and the stop-signal classification D-158 surfaces read-only already exist as pure functions.
- **`daily`-shaped APScheduler kwargs** the stack doc prescribes (`coalesce`, `max_instances`, `misfire_grace_time`, `replace_existing`) map 1:1 onto D-154's skip-and-surface policy.
- **`assets/tailwind/input.css` + the pinned Tailwind CLI** — the responsive work is a build-input edit plus a rebuild; no new toolchain.

### Established Patterns
- New persisted state = **new table + new Alembic migration**; repositories are the only place SQL lives, they take an `AsyncSession` and **never commit** (the route owns the commit).
- Every numeric ceiling/threshold is a **`Settings` field** (PLAT-04) — but D-153/D-168 deliberately put *user-editable runtime* thresholds in the DB row instead, which is the `ApplyConfig`/`RankingConfig` precedent, not a violation.
- Every route carries the **`current_user` auth seam** (PLAT-03); `app/api/deps.py` documents that Authentik later replaces only that function's body.
- **Decorative reads must never raise** — `_health_strip`'s convention; the new `/health` page inherits it.
- **Jinja macros live inside the page template** so a page and its fragment share one definition.
- Tests use `app.dependency_overrides`; `tests/db/test_migration_contract.py` pins the migration head.

### Integration Points
- **`app/main.py:lifespan`** — the only legal start/stop site for the scheduler, under the D-08 "must not hard-fail" rule; the scheduler target is `run_pipeline`, not a new pipeline.
- **`app/api/settings.py`** — hosts the settings page's POST handlers; the schedule field, the time picker, the danger-zone prune control and the prune preview route all attach here (or to a new sibling router registered in `create_app`).
- **`app/api/health.py`** vs a new `/health` **page** route — the JSON endpoint and the human page must agree about opencode reachability and `auth_configured` (D-138's constraint, already enforced once).
- **`app/db/repositories/*`** — new prune queries belong in repositories, never in the route; the four D-165 guards are the WHERE clauses.
- **`assets/tailwind/input.css` + Dockerfile stage 1** — CSS authored here; the image build compiles it, so a local `node_modules` rebuild is what the operator checklist will need to see.

</code_context>

<specifics>
## Specific Ideas

- **On the schedule field**, the user's own words: *"Should be a user field in the settings, you could use a datetime view so they can pick what time to run it at and timezone. In the future we can support which days of the week if needs be"*.
- **On the settings storage**, the user's own words: *"DB table for settings, I will say in the future we could support mulitple users so keep that in mind. I would like to potentially support authentik login"*.
- **On pruning**, the user's own words: *"Allow the user to choose which one they want to prune and how old do they need to be to qualify"* — the control is category-by-category with a user-set age, not a single switch.
- Health copy should make the schedule legible at a glance — "next run in 3h 12m" / "scheduling off" — and the Adzuna line reads as evidence with a number in it ("2/3 blocked runs — condition not met"), not a verdict without support.
- The prune preview's value is the number it shows before anything is destroyed.

</specifics>

<deferred>
## Deferred Ideas

- **Weekday / days-of-week scheduling** — deliberately deferred by the user ("In the future we can support which days of the week if needs be").
- **Multiple users + Authentik login** — keep the settings row's shape open for a future `user_id`; do not pay for auth now (D-21).
- **Manual "enable Adzuna" control** — SRC-11, v2 scope.
- **Live in-flight run indicator on `/health`** — would need htmx polling of the stage log; not this phase.
- **Full responsive parity on admin surfaces** — criteria editor, merges audit, runs history, settings stay desktop-first.
- **Automatic pruning on the nightly run** — deliberately rejected in favour of manual + preview + confirm.
- **Residual prompt-injection risk** (carried from 07.1) — accepted and documented in `docs/runbook-opencode-contract.md` and `README`; candidates for a future fix are the experimental per-session instructions endpoint or a plugin `context` hook. User's words: *"we need to document it tho and in the future we probably need to address it. for now its fine"*.
- **Settings model picker** (carried from 07.1) — its own phase; 07.1 preserved the seam only (`discover_models` retargeted to V2). Open unknown: V2's `GET /api/model` and `/api/provider` returned an empty array over HTTP for this project directory while `opencode models` listed 40 models.
- **`unwrap_single_key_mapping` WR-02** (`07-REVIEW.md`) — a two-node mutual `{"item": …}` cycle loops while its docstring claims it "cannot hang". Not wire-reachable. Resolve via `/gsd-code-review 07 --fix` **if Phase 8 reuses the helper**.

</deferred>

---

*Phase: 8-Operations + Polish*
*Context gathered: 2026-10-14*
