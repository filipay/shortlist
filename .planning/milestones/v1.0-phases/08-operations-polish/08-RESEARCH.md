# Phase 8: Operations + Polish — Research

**Researched:** 2026-10-14
**Domain:** In-process scheduling (APScheduler 3.11.3), scheduled-run safety, manual retention/pruning of SQLite rows + on-disk artifacts, accessible responsive CSS (Tailwind 4.3.3), a DB-only health surface
**Confidence:** HIGH on the scheduler mechanics and the CSS mechanism (both verified against the pinned artefacts themselves); HIGH on the in-repo constraints (every one read from the source this session); MEDIUM on retention *numbers* and on the two D-164/D-167 contradictions, which are open decisions rather than facts.

## Summary

Phase 8 adds a caller to an existing pipeline, a page over existing data, a CSS block over existing markup, and a delete path over existing rows. Almost nothing in it is new capability — the research therefore concentrates on the four places where a plausible-looking implementation silently breaks an existing invariant.

**1. The scheduler must not be a second pipeline.** `run_pipeline(trigger, search_id, session_factory, run_id=)` already exists, already accepts `'schedule'` as a trigger value (`ck_runs_trigger`), and its own docstring names Phase 8 as a caller. The scheduler adds a module-level wrapper function and a `CronTrigger` — not a code path.

**2. Three hard, non-obvious mechanics govern the APScheduler wiring** (all verified against the pinned 3.11.3 sdist read this session):
   - `AsyncIOScheduler`, not `BackgroundScheduler`. `AsyncIOExecutor` is the async scheduler's default executor and `create_task()`s a coroutine function; `BackgroundScheduler`'s `ThreadPoolExecutor` would call the `async def` and never await the returned coroutine — a job that logs success and does nothing.
   - **The job arguments are pickled.** `Job.__getstate__` serialises `func` as a `module:qualname` text ref (raising `ValueError` for a lambda/nested function) and puts `args`/`kwargs` through `pickle`. `async_sessionmaker` is not picklable, so the job target must take **no arguments** and resolve `get_session_factory()` itself.
   - **`replace_existing=True` at every boot destroys the missed-run signal.** `_real_add_job` only computes `next_run_time` `if not hasattr(job, "next_run_time")` and then `update_job`s the stored state, so re-registering a persisted job at startup overwrites the past-due fire time with the next *future* one and `EVENT_JOB_MISSED` can never fire. The boot reconciliation must therefore be **create-if-absent**, not unconditional-replace.

**3. Pruning collides with two invariants the phase is forbidden to weaken.** The `listing_events` `BEFORE DELETE` trigger and its `NO ACTION` FK to `listings` (verified in migration 0001 and `test_migration_contract.py`) mean D-167's "hard delete the listing and everything hanging off it" **cannot** be executed for any listing that has an event row while D-164 keeps the trigger intact. Separately, `llm_calls.run_id` is a nullable FK to `runs` and guard 2 forbids pruning the ledger, so deleting a run must `SET NULL` its ledger rows rather than orphan or refuse. Both need an explicit decision before a plan is written.

**4. The `/health` page cannot take the `/health` path cheaply.** `GET /health` is pinned as JSON by 25 assertions, `tests/test_auth_seam.py`'s route inventory, and `scripts/compose-smoke.sh` (which `curl`s it and parses JSON). `08-UI-SPEC.md` assumption 3 proposes moving the JSON to `/health.json`; that is the *expensive* option. A distinct page path costs one route and one nav entry.

**Primary recommendation:** One module `app/jobs/scheduler.py` owning one `AsyncIOScheduler` + `SQLAlchemyJobStore` over `Settings.database_url_sync`, one argument-free module-level target `run_scheduled_pipeline()` that (a) resolves the session factory at call time, (b) refuses when a non-terminal `runs` row already exists (APScheduler's `max_instances=1` cannot see a manual `POST /runs`), and (c) records the skip on the new ops row; the schedule itself and the prune thresholds live in one new singleton `operations_config` row (migration 0008), read by the lifespan which **creates the job only when absent**; the health page lives at a new path and reads the DB only; pruning lives in a new `app/db/repositories/retention_repo.py` where the four D-165 guards are WHERE clauses and the disk unlink happens **after** the commit.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-151:** **One global schedule**, not per-search. It runs the pipeline exactly as today's `POST /runs` does — `search_id=None`, i.e. the union of all enabled searches. The existing `searches.schedule_cron` column stays **unused and unpopulated**; it is not the storage for this feature.
- **D-152:** The user configures the schedule on the **Settings page with a time picker: pick the time-of-day and the timezone**. A cron string is a fine internal representation but the user never types cron. Days-of-week selection is explicitly deferred.
- **D-153:** The schedule lives in a **new singleton DB config row**, runtime-editable with no restart — the same shape as `RankingConfig`/`ApplyConfig` (`id = 1` pinned by a named CheckConstraint, JSON payload, `updated_at`). It must be shaped so a future `user_id` column can be added, but **no `user_id` column exists in v1** (D-21). — **Reversibility:** costly — swapping storage later means a new Alembic migration plus every reader/writer of the row; the shape decision is what makes the multi-user future cheap or expensive.
- **D-154:** **Missed runs are skipped, surfaced, and never overlapped.** A scheduled run missed by more than the 1-hour grace window is skipped outright — never back-filled or caught up — but its absence IS surfaced to the user ("last scheduled run was missed"). A scheduled trigger that fires while a run is already in flight **skips** rather than starting a second concurrent pipeline, and records why it skipped.
- **D-155:** Health lives on a **dedicated `/health` page** (a system section plus the full per-source table) **and the existing compact queue-page strip stays**.
- **D-156:** The **source health badge is computed from RECORDED run outcomes** — per-source fetch status and recorded stop signals over the last N runs — not from the live probe stamp. **The health page reads the DB only and never puts a request on a job board**: a page view must not be a scrape. The live probe survives as an explicit, separate operator action, never as a side effect of viewing health.
- **D-157:** The system section is **assembly of data that already exists, not new measurement**: the four dependency probes (database, opencode including `auth_configured`, Tectonic/LaTeX engine, CV fact store) **+ the next scheduled run** ("next run in 3h 12m" / "scheduling off") **+ the last run's status and one-line reason**.
- **D-158:** The computed **Adzuna promotion verdict is shown READ-ONLY on `/health` as evidence** (e.g. "Adzuna hedge: 2/3 blocked runs — condition not met") with a link to the probe document. **Nothing escalates or switches adapters automatically**; the decision stays human. A manual enable-Adzuna control is not in this phase.
- **D-159:** **The primary journey must be genuinely comfortable on a phone**: the queue, listing detail, `/health`, the run control, and the applications tracker. **Admin surfaces** (criteria editor, merges audit, runs history, settings) must not break, but stay desktop-first.
- **D-160:** Responsive rules are authored in **`assets/tailwind/input.css`** — the existing Tailwind 4.3.3 build input — and rebuilt with the pinned CLI into `static/vendor/app.css`. **Card-reflow** (rows becoming label:value blocks) is used **only for the journey tables** (queue, applications, health). Every other table keeps its current markup wrapped in an **accessible scroll region (`tabindex="0"`, `role="region"`, `aria-label`)**. **No JavaScript.**
- **D-161:** Verification is the project's existing pattern: a **`/gsd-ui-review` 6-pillar audit** over the responsive surfaces (as phases 02/05/06/07 did) **plus a documented operator-run checklist in a runbook** — named viewport widths (320/375/768) crossed with the journey pages. Docker and a browser are absent from the agent sandbox, so operator-run checks are the established norm (`docs/runbook-compose-smoke.md`).
- **D-162:** On a phone, a queue row **restacks ALL the data the desktop row shows** — title, company, location, badges, score, posted date, exclusion chips, actions — as label:value lines. Nothing hidden, nothing requiring a second tap.
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

### Deferred Ideas (OUT OF SCOPE)

- **Weekday / days-of-week scheduling** — deliberately deferred by the user ("In the future we can support which days of the week if needs be").
- **Multiple users + Authentik login** — keep the settings row's shape open for a future `user_id`; do not pay for auth now (D-21).
- **Manual "enable Adzuna" control** — SRC-11, v2 scope.
- **Live in-flight run indicator on `/health`** — would need htmx polling of the stage log; not this phase.
- **Full responsive parity on admin surfaces** — criteria editor, merges audit, runs history, settings stay desktop-first.
- **Automatic pruning on the nightly run** — deliberately rejected in favour of manual + preview + confirm.
- **Residual prompt-injection risk** (carried from 07.1) — accepted and documented in `docs/runbook-opencode-contract.md` and `README`; candidates for a future fix are the experimental per-session instructions endpoint or a plugin `context` hook.
- **Settings model picker** (carried from 07.1) — its own phase.
- **`unwrap_single_key_mapping` WR-02** (`07-REVIEW.md`) — a two-node mutual `{"item": …}` cycle loops while its docstring claims it "cannot hang". Not wire-reachable. Resolve via `/gsd-code-review 07 --fix` **if Phase 8 reuses the helper**.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RUN-05 | User can schedule recurring runs | §Standard Stack (APScheduler 3.11.3 pin + `SUS` legitimacy gate), §Pattern 1 (lifespan wiring), §Pattern 2 (create-if-absent reconciliation), §Pattern 3 (the module-level argument-free target), §Pattern 4 (settings save = create/remove/reschedule) |
| RUN-06 | User can see when the next scheduled run will happen | §Pattern 5 (`Job.next_run_time` read + the "scheduling off" branch), §Pitfall 6 (reading `next_run_time` from a paused/absent job must degrade to `None`, never raise) |
| RUN-07 | User can check system and source health from a health endpoint surfaced in the UI | §Pattern 6 (one dependency-report builder shared by the JSON endpoint and the page), §Pattern 7 (run-derived source badge + read-only Adzuna verdict from the same repository), §Critical constraint C1 (the `/health` path is pinned as JSON) |
| PLAT-06 | Scheduled runs are single-worker safe and persist across restarts | §Pattern 2 (why create-if-absent is required), §Pattern 3 (the `_running_run_id` guard — `max_instances=1` is blind to a manual run), §Pitfall 1 (`AsyncIOScheduler` loop ownership), §Testing-architecture note (httpx `ASGITransport` does not run lifespan) |
| UI-06 | The UI is usable from both a laptop and a phone browser | §Pattern 8 (the `data-label` reflow, verified by building it with the pinned CLI), §Pitfall 8 (`@variant max-md` vs `max-width: 767px`), §Pitfall 9 (`thead` hiding vs duplicated screen-reader labels), §Pattern 9 (the scroll region) |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Deciding *when* a run fires | **API / backend process** (APScheduler in the FastAPI lifespan) | — | v1 is one process, one event loop, `--workers 1`. A cron daemon or a second container would be a new deployment surface for one nightly job, and the STACK doc already rejected it. |
| Persisting the schedule (time-of-day, tz, on/off) | **Database** (new singleton `operations_config` row) | API (reads it at boot) | D-153 makes the schedule runtime-editable state, not configuration; `Settings` is for ceiling/threshold *policies* (PLAT-04). It is also the only thing that makes "runtime-editable with no restart" possible, because the value survives the process. |
| Persisting the *job* (next fire time, coalescing state) | **Database** (APScheduler's own `apscheduler_jobs` table) | API (scheduler jobstore) | Only a persistent store makes a fire time that elapsed while the container was down visible to the misfire machinery. Its cost is a table APScheduler creates itself — see Pitfall 4. |
| Executing a scheduled run | **API / backend process** (existing `run_pipeline`) | — | The scheduler is a caller. All pipeline semantics (budget, ranking, dedup, exclusion) stay where they are. |
| Detecting "a manual run is in flight" | **Database** (`runs.status NOT IN TERMINAL_STATUSES`) | — | APScheduler's `max_instances=1` counts only its own job instances, so it cannot see `POST /runs`. The DB is already the single source of truth for run state ("no in-memory `RunState` registry", `run_pipeline` docstring). |
| Computing the run-derived source badge | **Database read** (`source_repo`, new query) | API (route renders it) | D-156: a page view must not be a scrape. The live probe tier (`app/probe/probe.py`) is deliberately **not** on the page path. |
| Assembling the system dependency report | **API / backend process** (existing probe functions) | — | The four probes already exist as total functions in `app/api/health.py`; the page and the JSON endpoint must call the *same* builders or they can disagree (D-138). |
| Retention/pruning execution | **Database** (row deletes) **plus** **filesystem** (`artifacts_dir` unlink) | API (route owns the transaction + the commit) | Repositories never commit (house rule), so the route owns the transaction boundary; the unlink must be a separate, post-commit step because it is not transactional. |
| Responsive layout | **Browser / client** (CSS only, no JS) | — | D-160: the reflow is authored in the Tailwind build input and expresses itself in media queries. No server-side user-agent branching, no Alpine. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `apscheduler` | **3.11.3** (exact pin) | In-process cron scheduling with a persistent job store | The only thing this phase adds. Chosen in the STACK doc: no broker, persistent job store, API-driven jobs, survives restarts. **4.x is alpha and is not to be used.** |
| `SQLAlchemyJobStore` (part of `apscheduler`) | ships with 3.11.3 | Job persistence across restarts | Lets APScheduler's own misfire machinery see a fire time that elapsed while the container was down (`docs: jobstores/sqlalchemy.html`). |
| `zoneinfo.ZoneInfo` | stdlib (Python 3.13) | `Europe/Dublin` tz for the cron trigger | APScheduler 3.11.3 itself imports `zoneinfo`; no `pytz` needed. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tzlocal` | transitive (`apscheduler` requires `>= 3.0`) | APScheduler's *default* local timezone | Never relied on — the trigger's timezone is always passed explicitly as `Europe/Dublin`. It is a transitive dep and is therefore **not** exact-pinned by the project's convention (same situation as JobSpy's `pandas`). |
| `tailwindcss` / `@tailwindcss/cli` | **4.3.3** (already pinned, `Dockerfile:15-16`) | Build `assets/tailwind/input.css` → `static/vendor/app.css` | The responsive work: add the media block, rebuild with the same command the Dockerfile runs. No new toolchain. |
| `node` | present in `node_modules/.bin/tailwindcss` (verified: reports `v4.3.3`) | Running the pinned CLI locally | Required by `tests/test_stylesheet_coverage.py::test_the_committed_stylesheet_is_the_build_of_its_source`, which `pytest.skip`s (never silently passes) when absent. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `SQLAlchemyJobStore` | Default `MemoryJobStore` | **This is a real alternative and the planner should consciously reject it.** With an in-memory store the schedule still survives a restart (D-153's row is re-read at boot), but a fire time that elapsed while the container was **down** leaves no trace at all: on boot the trigger computes the *next future* fire and the missed one is never reported, so D-154's "its absence IS surfaced" can only be satisfied by hand-rolling our own comparison against a stored expected-fire timestamp. The persistent store gives that signal free. Cost of choosing it: one table outside Alembic (Pitfall 4) and the picklability constraint (Pitfall 3, which applies either way if you want the store to be swappable). |
| `AsyncIOScheduler` | `BackgroundScheduler` | **Rejected outright.** `BaseExecutor.submit_job` → `ThreadPoolExecutor._do_submit_job` calls `run_job`, which does `retval = job.func(*job.args, **job.kwargs)` — for `async def` that returns a coroutine that is never awaited. The job would appear to succeed (`EVENT_JOB_EXECUTED`) while running nothing. `AsyncIOScheduler`'s default `AsyncIOExecutor` uses `iscoroutinefunction_partial` and `create_task()`s `run_coroutine_job` instead. |
| A `ThreadPoolExecutor` + `asyncio.run` inside the job | any sync scheduler | Adds a second event loop and a second engine; breaks the single-loop assumption every part of this app relies on. Do not. |
| `celery` / container cron | APScheduler | Already rejected in the STACK doc (broker + second process for one nightly job; cron lives outside git and cannot be driven by the API). |
| New `/health` page + moving the JSON endpoint | Keeping the page off `/health` | See **Critical constraint C1** below. Recommend keeping `GET /health` as JSON. |

**Installation:**

```bash
# pyproject.toml AND requirements.txt, exact pin in both (D-17 / test_dependency_pins).
apscheduler==3.11.3
```

**Version verification:** `pip download --no-deps apscheduler==3.11.3` succeeded in this session and the sdist was unpacked and read (`apscheduler-3.11.3.tar.gz`). `requires-python = ">= 3.8"`, `dependencies = ["tzlocal >= 3.0"]`.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `apscheduler` | PyPI | publishedAt reported as 2026-06-28 (latest release) | unknown (PyPI reports no download count) | **not declared in the PyPI metadata** | **[SUS]** | Flagged — plan **must** insert a `checkpoint:human-verify` before the install, exactly as `rapidfuzz`/`pypdf`/`pyyaml` were handled |

`gsd_run query package-legitimacy check --ecosystem pypi apscheduler` → `{"verdict":"SUS","reasons":["unknown-downloads","no-repository"]}`. The signal is metadata absence, **not** a young package: APScheduler is the long-standing, widely-used Python scheduler and its real source is `github.com/agronholm/apscheduler` — but the registry row does not advertise it, so the gate correctly refuses to rate it `OK`.

**Consequence for the plan (concrete):**
1. Add an explicit blocking `checkpoint:human-verify` task before the install, per `<package_legitimacy_protocol>` and the `rapidfuzz`/`pypdf` precedent.
2. Add a `PINNED_PACKAGES` row to `tests/test_dependency_pins.py` (`("apscheduler", "apscheduler==3.11.3", "3.11.3")`) — its module docstring already names this exact workflow ("a new runtime dependency whose package-legitimacy gate returned `SUS`").
3. The pin must appear **verbatim in both** `pyproject.toml` and `requirements.txt`; that test asserts both.
4. No `postinstall` equivalent exists on PyPI; nothing to check there.

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** `apscheduler`.

## Architecture Patterns

### Critical constraints discovered in this research (read these first)

**C1 — `GET /health` is pinned as JSON and must stay JSON unless the plan pays a real price.** Evidence, all read this session:
- 25 call sites do `.json()` on `client.get("/health")` (`tests/api/test_health.py` alone has 20; also `tests/db/test_source_seeding.py:148`, `tests/test_latex_engine_seam.py:109`).
- `tests/test_auth_seam.py:36` lists `"/health"` in `EXPECTED_SEAM_ROUTES`, and `test_the_helper_recognises_the_seam_it_asserts` reads `checked["/health"]`.
- `scripts/compose-smoke.sh:46` does `curl -fsS "$BASE_URL/health"` and then parses the body as JSON (`HEALTH_BODY="$(cat /tmp/compose-smoke-health.json)"`, then `$DB_STATE`/`$OPENCODE_STATE` are extracted). `docs/runbook-compose-smoke.md` documents `curl … /health | python3 -m json.tool`.

Three options, in ascending cost:
1. **Page at a distinct path** (e.g. `GET /health/view`) + a `Health` nav entry pointing there. Cost: one route, one nav line. `RUN-07` is satisfied literally ("a health endpoint surfaced in the UI"). **Recommended.**
2. **Content negotiation on `Accept`** at `/health`: return HTML when the header lists `text/html`, JSON otherwise. Zero test churn (httpx sends `Accept: */*`; curl sends `*/*`) and the browser and the nav link both get the page, but one path then answers two content types and the "always 200 JSON" contract becomes conditional. Defensible, but subtle.
3. **Move JSON to `/health.json`** (`08-UI-SPEC.md` assumption 3). Cost: ~25 test edits, `test_auth_seam.py`, `scripts/compose-smoke.sh`, `docs/runbook-compose-smoke.md`, and the `README`/runbook health references. Choose only if the literal `/health` path matters more than that churn.

Whichever is chosen, the page and the JSON **must** share the report builders (Pattern 6) — D-138's "cannot disagree about `auth_configured`" is the one non-negotiable.

**C2 — D-167 (hard-delete a listing and everything hanging off it) is not executable as written while D-164 holds.** Verified from `app/db/models.py` and `alembic/versions/0001_initial_schema.py`:
- `listing_events.listing_id` is `NOT NULL` with `ForeignKey("listings.id")` and no `ondelete` (⇒ `NO ACTION`) — `models.py:260`.
- `alembic/versions/0001_initial_schema.py:344-352` creates `CREATE TRIGGER listing_events_no_delete BEFORE DELETE ON listing_events` which raises `… append-only…`.
- `PRAGMA foreign_keys=ON` is applied to every connection (`app/db/session.py:38`).

Therefore `DELETE FROM listings WHERE id = ?` fails with `FOREIGN KEY constraint failed` for any listing that has an event row, and the event rows themselves cannot be deleted while the trigger stands. D-164 says the trigger "survives intact"; D-167's accepted consequence ("prior dismissals / seen-before memory are gone") can only happen if event rows go. **The plan must pick one and cite it explicitly:**
- **(a) Conservative — honour D-164 literally.** Restrict the stale-listing category to listings with **no** `listing_events`, **no** `listing_dupes`, **no** `applications`, **no** `cv_*` and **no** `screening_drafts` rows (i.e. a listing that was never touched). Simple, safe, and the preview count honestly reports a small number. Loses most of the useful pruning.
- **(b) Carve-out — mirror the reset's proven mechanism.** The reset already suspends the `listing_events_no_delete` trigger inside the same transaction and re-arms it before commit (`app/api/settings.py:643-675`, `_suspend_append_only_trigger` / `_restore_append_only_trigger`), and the engine makes DDL transactional (`app/db/session.py:45-70`). Reuse those exact two functions for the listing prune. This needs an explicit amendment to D-164 ("never pruned" → "never pruned *except* by the deletion of their parent listing") recorded in the plan, because it is a deliberate weakening of an invariant the context flags as costly to reverse.
- **(c) Scope change.** Delete listings only via `is_active=false` soft state and never hard-delete. Contradicts D-167.

Recommend **(b) with the wording change recorded**, because the reset already ships the mechanism and its transactionality is tested; recommend the plan also add a test asserting the trigger is **re-armed** after a prune (the reset has no such assertion today — `tests/api/test_settings_reset.py` covers the delete, not the re-arm).

Also note: **`queue_state` is not per-listing.** D-167 names "its `queue_state`" but `QueueState` (`models.py:104-108`) is one global watermark row (`id`, `last_queue_view_at`, `updated_at`) with no `listing_id`. The per-listing children that actually need deleting are `scores`, `listing_sources`, `listing_exclusions`, `listing_dupes` (**both** `listing_id` and `dup_listing_id`), `cv_artifacts`, `cv_drafts`, `screening_drafts` — and `listing_events` only under option (b). Treat the CONTEXT's "queue_state" as a wording slip and delete the correct set.

**C3 — Deleting a `runs` row must `SET NULL` its `llm_calls` children.** `llm_calls.run_id` is nullable with a `NO ACTION` FK to `runs` (`models.py:556`), and guard 2 forbids pruning the ledger. So the runs category must, in order: delete `scores` (NOT NULL FK), `listing_exclusions` (nullable FK), `listing_events` (nullable FK — but append-only! see C2; a run's events are the *listing* events, so the same trigger problem arises for any run whose listings had events), `source_request_log` (nullable FK — but only if the request-log category is not itself the target), then `UPDATE llm_calls SET run_id = NULL WHERE run_id IN (pruned)`, then `DELETE FROM runs`. Alternatively restrict the runs category to runs with no `listing_events` rows. This ordering must be written down; a naive `DELETE FROM runs` fails at runtime with `FOREIGN KEY constraint failed` and the failure surfaces only in the operator's dry-run→confirm step.

### System Architecture Diagram

```
                    ┌──────────────────────────────────────────────┐
   user (laptop) ──▶│  GET /settings  ──▶ schedule card + prune    │
   user (phone)  ──▶│                     card (plain form POST)   │
                    └───────┬───────────────────────┬──────────────┘
                            │ POST /settings/schedule│ POST .../prune/preview|confirm
                            ▼                        ▼
                 ┌────────────────────┐   ┌──────────────────────────────┐
                 │ operations_config  │   │ retention_repo               │
                 │ (singleton row)    │   │  guards = WHERE clauses      │
                 │  schedule_json     │   │  preview = COUNT + SUM(size) │
                 │  retention_json    │   └──────────┬───────────────────┘
                 └─────────┬──────────┘              │ rows deleted, commit
                           │ read at boot            ▼ then unlink (post-commit)
                           │                  artifacts_dir/*.tex|*.pdf
    FastAPI lifespan ──────┤
    (app/main.py)          │  create-if-ABSENT (never unconditional replace: Pitfall 2)
                           ▼
                 ┌──────────────────────────┐        ┌───────────────────────┐
                 │ AsyncIOScheduler         │◀──────▶│ SQLAlchemyJobStore    │
                 │  tz=Europe/Dublin        │        │  apscheduler_jobs     │
                 │  CronTrigger(hour,min)   │        │  (sync engine, WAL)   │
                 │  max_instances=1         │        └───────────────────────┘
                 │  coalesce=True           │
                 │  misfire_grace_time=3600 │
                 └───────┬──────────────────┘
                         │ fires
                         ▼
              run_scheduled_pipeline()          ◀── module-level, ZERO arguments
              (app/jobs/scheduler.py:.py)            (picklability: Pitfall 3)
                         │
                         ├─ (a) SELECT non-terminal runs row?  ──yes──▶ record skip
                         │        (max_instances cannot see POST /runs)   on ops row
                         │
                         ├─ (b) no in-flight run ──▶ run_pipeline("schedule", None,
                         │                                        factory)
                         ▼
                 ┌──────────────────────────────┐
                 │ runs row (trigger='schedule')│  ← already permitted by ck_runs_trigger
                 │ llm_calls · scores · stage log│     (models.py:334-338), no migration
                 └──────────────────────────────┘
                         │
                         ▼ reads DB only (never a board request, D-156)
                 ┌──────────────────────────────┐
                 │ health page (new path)       │   system probes (shared builders)
                 │  + existing _health_strip    │   next run from Job.next_run_time
                 │  (queue page strip unchanged)│   run-derived source badge
                 └──────────────────────────────┘   Adzuna verdict (read-only)
```

### Recommended Project Structure

```
app/
├── jobs/
│   ├── __init__.py
│   └── scheduler.py        # NEW — the AsyncIOScheduler, its jobstore, start/stop,
│                           #        the create-if-absent reconciliation, the
│                           #        argument-free target, and the event listeners
├── db/
│   ├── models.py           # + OperationsConfig (singleton, id=1, two JSON columns)
│   └── repositories/
│       ├── operations_config_repo.py   # NEW — schedule + retention JSON, mirrors
│       │                               #        apply_config_repo exactly
│       └── retention_repo.py           # NEW — the only place the prune SQL lives
├── api/
│   ├── health_page.py      # NEW — the HTML page route (keeps api/health.py's JSON
│   │                       #        endpoint untouched; see C1)
│   └── settings.py         # + POST /settings/schedule, + the prune preview/confirm
│                           #        routes, + the ops row in RESET_KEPT_TABLES
alembic/versions/0008_operations_config.py   # NEW — the one migration
app/web/templates/html/
├── health.html             # NEW — the page (includes _health_strip.html verbatim)
├── _health_strip.html      # edited — only the data-label attributes (D-162)
└── settings.html           # edited — the schedule card + the prune card
assets/tailwind/input.css   # edited — @layer components + the @variant max-md block
docs/runbook-responsive-ui.md  # NEW — the D-161 operator checklist
tests/
├── jobs/test_scheduler.py  # NEW
├── db/test_retention_repo.py  # NEW
└── api/test_health_page.py    # NEW
```

**Naming note (discretion, D-153/D-168):** one table for both payloads. Recommended `operations_config` with `schedule_json`, `retention_json`, `updated_at` and `ck_operations_config_singleton` (`id = 1`). Two columns rather than one blob because they are written by two different forms and a single blob would make each save a read-modify-write of the other's data. Keep the singleton shape so a future `user_id` column is additive.

### Pattern 1: `AsyncIOScheduler` started and stopped from the lifespan

**What:** One module owns the scheduler object; the lifespan is the only start/stop site; both are idempotent and neither can hard-fail boot (D-08).
**When to use:** Always — this is the only legal wiring.

```python
# app/jobs/scheduler.py  (shape, not final code)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import create_engine, event

SCHEDULED_JOB_ID = "shortlist-daily-run"

_scheduler: AsyncIOScheduler | None = None


def _sync_engine():
    """The jobstore's own engine. It does NOT inherit app.db.session's pragmas."""
    engine = create_engine(settings.database_url_sync)        # sqlite:////data/jobsearch.db
    event.listens_for(engine, "connect")(apply_sqlite_pragmas)  # reuse session.py's
    return engine


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            jobstores={"default": SQLAlchemyJobStore(engine=_sync_engine())},
            timezone=ZoneInfo(settings.schedule_timezone),      # Europe/Dublin, explicit
        )
        _scheduler.add_listener(_on_scheduler_event,
                                EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES | EVENT_JOB_ERROR)
    return _scheduler


async def start_scheduler(session_factory) -> str:
    """Returns a short status string for the log. NEVER raises (D-08)."""
    try:
        scheduler = get_scheduler()
        await _reconcile(scheduler, session_factory)   # Pattern 2 — create-if-absent
        if not scheduler.running:
            scheduler.start()                          # must be inside the running loop
        return "started"
    except Exception as exc:                           # noqa: BLE001
        log.warning("scheduler.start_failed", error=type(exc).__name__)
        return "unavailable"


async def stop_scheduler() -> None:
    scheduler = _scheduler
    if scheduler is None or not scheduler.running:
        return                                          # idempotent: shutdown() raises otherwise
    try:
        scheduler.shutdown(wait=False)                  # NOT awaited; it is sync
    except SchedulerNotRunningError:
        pass
```

Verified against the pinned 3.11.3 source:
- `AsyncIOScheduler.start()` — `self._eventloop = asyncio.get_running_loop()`, so it must be called from inside the running loop. FastAPI's lifespan is. Calling it from a sync context raises `RuntimeError`.
- `AsyncIOScheduler.shutdown()` raises `SchedulerNotRunningError` when `not self.running`, so the `if not scheduler.running` guard is required for idempotency.
- `_shutdown` is decorated with `run_in_event_loop` → it does `self._eventloop.call_soon_threadsafe(...)`, i.e. `shutdown()` returns **before** the scheduler has stopped and clears `_eventloop` only inside that callback. Do not assert "stopped" immediately after calling it.
- The lifespan body runs with `app=None` in the existing test (`tests/db/test_source_seeding.py:138` does `async with main_module.lifespan(None)`), so `start_scheduler` must not require the app object.

### Pattern 2: Create-if-absent reconciliation (the reason PLAT-06 and D-154 coexist)

**What:** At boot, add the job **only when it is absent**. Replace it **only when its trigger differs from the stored config**.

```python
async def _reconcile(scheduler, session_factory) -> None:
    async with session_factory() as session:
        schedule = await operations_config_repo.read_schedule(session)

    existing = scheduler.get_job(SCHEDULED_JOB_ID)     # None when absent
    if not schedule.enabled:
        if existing is not None:
            scheduler.remove_job(SCHEDULED_JOB_ID)
        return

    trigger = CronTrigger(hour=schedule.hour, minute=schedule.minute,
                          timezone=ZoneInfo(schedule.timezone))
    if existing is None:
        scheduler.add_job(run_scheduled_pipeline, trigger, id=SCHEDULED_JOB_ID,
                          replace_existing=False, coalesce=True, max_instances=1,
                          misfire_grace_time=settings.schedule_misfire_grace_seconds)
    elif str(existing.trigger) != str(trigger):
        # User changed the time while we were down, or the config drifted.
        scheduler.reschedule_job(SCHEDULED_JOB_ID, trigger=trigger)
    # else: leave it alone — its persisted next_run_time may be PAST DUE, and that is
    # exactly the state the misfire listener needs to see (Pitfall 2).
```

`reschedule_job(job_id, jobstore=None, trigger=None, **trigger_args)` is documented and present in 3.11.3 ("Constructs a new trigger for a job and updates its next run time").

**Why this exact shape:** `BaseScheduler._real_add_job` (3.11.3 source) contains

```python
        # Calculate the next run time if there is none defined
        if not hasattr(job, "next_run_time"):
            now = datetime.now(self.timezone)
            replacements["next_run_time"] = job.trigger.get_next_fire_time(None, now)
        job._modify(**replacements)
        try:
            store.add_job(job)
        except ConflictingIdError:
            if replace_existing:
                store.update_job(job)
```

`update_job` writes `next_run_time` and the whole pickled `job_state`. An unconditional `replace_existing=True` at every boot therefore recomputes `next_run_time` to the next **future** fire, discarding the past-due one before `get_due_jobs(now)` can ever return it — `EVENT_JOB_MISSED` becomes unreachable and D-154's "its absence IS surfaced" silently stops working. The APScheduler userguide's own advice ("you **MUST** define an explicit ID … and use `replace_existing=True`") is about avoiding *duplicate* jobs, which `replace_existing=False` + an explicit id also achieves via `ConflictingIdError`.

### Pattern 3: The scheduled target is an argument-free, module-level async function

**What:** `app/jobs/scheduler.py:run_scheduled_pipeline` — no parameters, module scope, `async def`.

```python
async def run_scheduled_pipeline() -> int | None:
    """The scheduled entry point. Never raises into APScheduler."""
    factory = get_session_factory()          # resolved HERE, not passed in
    async with factory() as session:
        in_flight = await session.scalar(
            select(Run.id).where(Run.status.not_in(tuple(TERMINAL_STATUSES))).limit(1)
        )
    if in_flight is not None:
        await _record_skip(factory, reason="in_flight", run_id=int(in_flight))
        return None
    return await run_pipeline("schedule", None, factory)
```

Three independent justifications, each verified:

1. **Picklability.** `Job.__getstate__` returns `{"func": self.func_ref, …, "args": args, "kwargs": self.kwargs, …}` and `SQLAlchemyJobStore.add_job` does `pickle.dumps(job.__getstate__(), self.pickle_protocol)`. `func_ref` is the `module:qualname` text reference and `__getstate__` **raises** `ValueError("This Job cannot be serialized since the reference to its callable … could not be determined…")` for a lambda or a nested function. So: module-level function, not a closure, not a bound method, not a `functools.partial`. `args`/`kwargs` still go through `pickle`, and `async_sessionmaker` (the object `POST /runs` passes today) holds an engine and is not picklable — hence an argument-free signature that resolves the factory itself. A bound method would additionally put `self` into `args` (the source says so explicitly: "Instance methods cannot survive serialization as-is, so store the 'self' argument explicitly").
2. **The in-flight guard is genuinely needed.** `BaseExecutor.submit_job` raises `MaxInstancesReachedError` only when its own `self._instances[job.id]` reaches `job.max_instances`; `_instances` is incremented by APScheduler's own submissions. A pipeline started by the manual `POST /runs` (`app/api/runs.py:104`, `asyncio.create_task`) is invisible to that counter, so `max_instances=1` alone does **not** satisfy "never overlapped" (D-154). The `_running_run_id` query already exists verbatim in `app/api/settings.py:623-626` — extract it to a repository rather than copying it.
3. **`trigger='schedule'` needs no migration.** `ck_runs_trigger` already reads `"trigger IN ('manual','schedule')"` (`models.py:335-338`), and `run_pipeline` already accepts an arbitrary `trigger` string.

Also: `run_pipeline`'s except-clauses are all `except Exception`, so a `CancelledError` (which is a `BaseException` in 3.8+) during container shutdown leaves the row in `running` forever — which then blocks `POST /settings/reset` (`_running_run_id`) and, with Pattern 3, blocks every future scheduled run. **Recommend a small startup reconciliation**: any `runs` row still non-terminal at boot is stale by definition (the process that owned it is gone) — mark it `partial`/`failed` with an error entry. This is 6 lines and it removes a permanently-stuck state.

### Pattern 4: The settings save re-configures the live scheduler without a restart

**What:** `POST /settings/schedule` writes the row, commits, then calls the same `_reconcile`-style helper.
**When to use:** Any time the user changes time/tz/enabled. This is how D-153's "runtime-editable with no restart" is delivered.

The route order matters: **commit first, then touch the scheduler.** If the scheduler call fails, the schedule is still saved and the next boot reconciles — the failure is reported in the banner, never rolled back into a lost save. And the scheduler call is wrapped: an unavailable scheduler must not 500 the settings page.

### Pattern 5: Reading the next run for RUN-06

```python
job = get_scheduler().get_job(SCHEDULED_JOB_ID)          # None when absent/off
next_run = job.next_run_time if job is not None else None  # tz-aware datetime, or None
```

`Job.next_run_time` is a documented attribute (`datetime.datetime` — "the next scheduled run time of this job"). It is `None` for a paused job (`add_job(..., next_run_time=None)` adds the job paused) and is absent when the job does not exist. The render path must therefore be total: `next_run is None` ⇒ render `Scheduling off` (when the stored row says disabled) **or** `No run scheduled` — never a fabricated time. The countdown is computed at render time from `datetime.now(ZoneInfo(tz))`, not stored (the same "persist the fact, compute the sentence" rule `run_repo` follows).

**Pitfall:** this is the one place where the health page would touch the scheduler object rather than the DB. Wrap it in try/except like `_health_strip` — a scheduler that failed to start must degrade the line, never 500 the page. And the *stored* schedule row (not the live job) is the authority on enabled/disabled, so a scheduler that failed to start still renders the user's configured time.

### Pattern 6: One dependency-report builder shared by the JSON endpoint and the page

**What:** Move `_opencode_report`, `_tectonic_report`, `_cv_report` and the `database` check into a function that returns the report dict, and have both `GET /health` (JSON) and the page call it.

`app/api/health.py` already has all four as module-level helpers, and `app/llm.auth_configured()` is documented as "the ONE definition of 'is opencode auth configured'; /health and the queue strip both import it so they cannot disagree (D-138)". The page adds a **third** consumer, so the safe move is to make the *builder* shareable, not just the boolean. The page additionally must **not** call `probe_all(...)` (that is the live job-board probe, TTL-cached on the JSON endpoint) — D-156 puts the page on a DB-only path.

**Recommended shape:**

```python
async def dependency_report(session, backend, engine) -> dict[str, Any]:
    """The four probes, total. One definition, three consumers (JSON /health,
    the page, and any future uptime check)."""
```

Keep the returned key names identical to today's JSON so the 25 existing assertions keep passing.

### Pattern 7: The run-derived source badge and the read-only Adzuna verdict

**What:** A new repository read that computes per-source status from **recorded run outcomes** over the last N runs, plus the existing pure classifier for stop signals.

Reusable pieces that already exist (all verified):
- `source_repo._latest_run_for(runs, name)` and `source_repo._last_success_run(runs, name)` — already read `Run.source_counts_json[source].status`, i.e. already run-derived (`source_repo.py:100-121`). D-156 extends this; it does not invent it.
- `source_repo.RECENT_RUN_LIMIT = 20` — the existing window for that read.
- `app/probe/survival.py:classify_block_vs_parse(...)` → `S5` is the pure classifier that turns `(status, status_code, parsed_items, stop_signal)` into fetch-side vs parse-side. `app/sources/_ledger.py:record_fetch_outcome` writes exactly that `stop_signal` (`result_status in ("blocked","rate_limited")`) into `source_request_log.note` at ingest time, so the stop signals are **already recorded** and need no new write.
- `adzuna_promotion_condition(evidence: BoardEvidence) -> list[SignalResult]` — a pure function, currently called **only from tests**. `BoardEvidence` is a frozen dataclass of `(source, run_statuses, output_counts, new_listing_counts, fill_rates, baseline, probe_statuses, window_days)` (`survival.py:491-506`). Phase 8 must **build** it from persisted rows; there is no existing builder in `app/`. `baseline_from_row(row)` (`survival.py:723`) exists for the `baseline` member; the rest comes from `runs.source_counts_json` over `settings.probe_promotion_window_runs` runs plus `listing_sources` fill rates (the same `compute_fill_rates`/`fill_rate_record_from_raw` pair already used by `run_pipeline`).
- The verdict link target `docs/probes/2026-09-15-scraper-survival.md` exists (verified), and `docs/probes/README.md` documents how it is written.

The badge vocabulary must reuse `VALID_HEALTH` (`{"ok","degraded","unreachable"}`, mirrors `ck_sources_health`) so the page's badges use the existing `.health-ok/.health-degraded/.health-unreachable/.health-unknown` classes and `test_stylesheet_coverage` needs no new tokens.

### Pattern 8: The phone card-reflow, built and verified with the pinned CLI

**What:** `data-label` on each journey-table `<td>` + a media block in `assets/tailwind/input.css`.

**Verified in this session by running the pinned `tailwindcss@4.3.3` CLI against a probe stylesheet inside the repo:**

```css
@layer components {
  .touch-target { min-height: 2.75rem; min-width: 2.75rem; }
  .touch-target { @variant md { min-height: auto; } }   /* → @media (width >= 48rem) */
}

@layer components {
  @media (width < 48rem) {                              /* or @variant max-md { … } */
    .queue-table, .queue-table thead, .queue-table tbody,
    .queue-table tr, .queue-table td { display: block; }
    .queue-table td[data-label]::before {
      content: attr(data-label);
      font-weight: 600;
      color: var(--color-muted);
      display: block;
    }
  }
}
```

Build output (verbatim from the probe run): the `@layer components` body is emitted **verbatim** including the nested media block; `@variant md { … }` compiled to `@media (width >= 48rem) { .touch-target { min-height: auto; } }`; `@media (width < 48rem)` passed through unchanged; `content: attr(data-label)` survived; `@media (width >= theme(--breakpoint-md))` resolved `theme()` to `48rem` at build time.

Consequences:
- **`@layer components` is the right place.** It is a native cascade layer in v4; user rules there are not tree-shaken, and the existing 1885-line `input.css` is already 14 such blocks. Do **not** reach for `@utility` — it changes how the class participates in variant/sort ordering and would be a gratuitous deviation from the shipped file.
- **Prefer `@variant max-md` (or `width < 48rem`) over `max-width: 767px`.** Tailwind's `md` is `width >= 48rem`; `max-width: 767px` leaves 767.01–767.99px in neither regime. `08-UI-SPEC.md` states 767px; the equivalent-and-exact form is `width < 48rem`. (Discretion item — either satisfies D-160; the exact complement is the better default and the operator checklist's named widths are unaffected.)
- **Rebuild is mandatory and gated.** `tests/test_stylesheet_coverage.py::test_the_committed_stylesheet_is_the_build_of_its_source` asserts the committed `static/vendor/app.css` is the **byte-identical** build of `input.css` with the pinned CLI, and `test_every_template_class_has_a_rule_in_the_source_stylesheet` asserts every template class is definable from the source. Node and the CLI are present here (verified `v4.3.3`), so the rebuild can be run and proved locally:
  `./node_modules/.bin/tailwindcss -i ./assets/tailwind/input.css -o ./static/vendor/app.css --minify`
  Then verify byte-identity **without** touching the committed artefact by running `pytest tests/test_stylesheet_coverage.py -x`.
  Historical warning (from `07-13`): `static/vendor/app.css` had been hand-appended out of sync with the source, and a rebuild-before-backfill deleted 30 template rules. The source is now in sync — do the CSS edit **first**, then rebuild.

### Pattern 9: The accessible scroll region for every non-journey table

```html
<div class="table-scroll" role="region" tabindex="0" aria-label="Run history">
  <table class="runs-table"> … </table>
</div>
```

- Wrap the **table**, never put `role="region"` on the `<table>` (it would override the table role).
- `tabindex="0"` is what makes the region keyboard-scrollable; `role="region"` requires an accessible name, hence `aria-label`.
- The four non-journey tables are in `merges.html`, `runs.html`, `listing_detail.html` (factor table) and `applications_list.html` doubles as the tracker *list* — check per page whether it is the journey table (queue/tracker/health) or the admin one before wrapping.
- `.table-scroll { overflow-x: auto; max-width: 100%; }` — note `.queue-table` and `.health-table` **already** carry `overflow-x: auto` in the shipped sheet (per `08-UI-SPEC.md`), so the journey tables keep their rule and get the reflow; the scroll-region class is for the rest.

### Anti-Patterns to Avoid

- **`BackgroundScheduler`** with an `async def` target — the job reports success and runs nothing (verified: `ThreadPoolExecutor` calls `run_func` synchronously).
- **Passing `session_factory` (or a `Settings`, a session, or a bound method) as a job argument** — `pickle` fails at `add_job` and, with `SQLAlchemyJobStore`, it fails at *boot*, taking the scheduler down (which under D-08 must fall back to "unavailable", not crash the app).
- **`replace_existing=True` unconditionally at boot** — silently kills the missed-run signal (Pattern 2).
- **Trusting `max_instances=1` for "never overlapped"** — it cannot see a manual run (Pattern 3).
- **Letting the health page call `probe_all`** — that is a request on a board that bans automation, from a page view (D-156, T-01-31).
- **Deleting DB rows and unlinking files in the same step** — the unlink is not transactional; a rolled-back commit would then leave live rows with missing files. Commit first, unlink second, report unlink failures.
- **`DELETE FROM runs` / `DELETE FROM listings` without the ordering in C2/C3** — `PRAGMA foreign_keys=ON` is on every connection, so these fail with `FOREIGN KEY constraint failed` at the operator's confirm step.
- **Editing `static/vendor/app.css` by hand** — the byte-identity guard fails and a later real rebuild drops the hand-written rules.
- **A new JSON column without listing it in `tests/db/test_no_pii_columns.py::EXPECTED_JSON_COLUMNS`** — that guard fails by design ("A new free-form blob must be added here deliberately (and justified) or this fails").
- **A new route without `user: User = Depends(current_user)`** — `tests/test_auth_seam.py::test_every_route_with_a_dependant_declares_current_user` walks every leaf route dynamically and fails, not just the listed ones.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cron parsing, tz-aware next-fire computation, DST handling | A datetime comparison loop | `apscheduler.triggers.cron.CronTrigger` with `ZoneInfo` | `Europe/Dublin` has a DST transition; a hand-rolled "next 07:00" drifts by an hour twice a year and an IST/GMT shift is exactly how a morning run lands at 08:00. |
| Picking the latest artifact per listing | A Python `max()` over `history_for_listing` | A correlated `NOT EXISTS` / window function mirroring `latest_for_listing(ok_only=True)`'s `ORDER BY created_at DESC, id DESC` | The guard must be the exact complement of the read that shows the artifact; a Python-side approximation drifts and deletes a visible CV. |
| Suspending the append-only trigger for a prune | A new `DROP TRIGGER`/`CREATE TRIGGER` pair | `app/api/settings.py:_suspend_append_only_trigger` / `_restore_append_only_trigger` (read the DDL from `sqlite_master`, re-arm in the same transaction) | Already written, already relies on the engine's transactional DDL, and re-reads the DDL rather than hard-coding it so it cannot drift from the migration. |
| The "is a run in flight?" check | A second query | The `_running_run_id` predicate in `app/api/settings.py:623-626`, moved into a repository | Two definitions of "in flight" (one for the reset guard, one for the scheduler) will disagree, and the disagreement is a concurrent pipeline or a blocked reset. |
| Snapshotting before a destructive operation | A fresh backup implementation | `snapshot_database()` (`VACUUM INTO`, `app/api/settings.py:595`) | The prune is destructive and D-166 demands a preview; a snapshot is the existing mitigation precedent and is one call. |
| Byte sizes for the dry-run preview | A database `SUM()` | `Path(p).stat().st_size` over the selected rows, skipped/zero for a missing file | Sizes live only on disk; the DB has no size column and the preview must not lie about a missing file. |
| A responsive table pattern | JS, or `display:grid` column pairing | `data-label` + `content: attr(data-label)` in a media query | D-160 forbids JavaScript; the `attr()` pattern is the standard no-JS reflow and is verified to survive the pinned build. |
| A health page data model | A new metrics table | The existing probes + `runs` + `source_request_log` + `listing_sources` | D-157 is explicit: assembly of existing data, not new measurement. New measurement is exactly what a page view must not do. |

## Runtime State Inventory (retention + scheduler scope)

Phase 8 is not a rename, but it **destroys state and creates a table outside Alembic**, so the same inventory applies. Every category is answered explicitly; "None" means checked, not skipped.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | (1) `runs` — 1 row per run, unbounded; its children are `scores` (NOT NULL FK), `listing_exclusions` (nullable FK), `listing_events` (nullable FK, append-only), `source_request_log` (nullable FK), `llm_calls` (nullable FK, never pruned). (2) `cv_artifacts` — 1 row per compile by design (D-117); referenced by `applications.cv_artifact_id`. (3) `source_request_log` — 1 row per outbound request; **read by the survival/verdict path** (`survival.py:5` names it as a verdict input), so it carries an implicit floor. (4) `listings` + their `scores`/`listing_sources`/`listing_exclusions`/`listing_dupes`/`cv_artifacts`/`cv_drafts`/`screening_drafts`. (5) **NEW** `operations_config` row (schedule + retention thresholds). (6) **NEW** `apscheduler_jobs` (APScheduler's own table). | Data migration = the new migration **0008** (creates `operations_config`). Code edit = `retention_repo`. Decide C2 + C3 ordering **before** writing the delete queries. |
| **Live service config** | The schedule exists **only** in the DB row and in `apscheduler_jobs`. Nothing external (no n8n, no Datadog, no Tailscale). `searches.schedule_cron` exists from migration 0001 but D-151 leaves it **unused and unpopulated** — a future reader must not "wire it up". | Add a comment on the column's non-use, or at minimum do not populate it. `docs/runbook-*.md` must state that the schedule is edited from `/settings` and nowhere else. |
| **OS-registered state** | **None.** No cron entry, no systemd unit, no Task Scheduler task, no launchd plist. The entire point of APScheduler-in-process is that nothing lives outside git. | None. Confirm the plan does not add a `crontab` line to the Dockerfile. |
| **Secrets / env vars** | **None new.** The scheduler inherits `DATABASE_URL_SYNC` (already set in `compose.yml`) and the new `schedule_*` Settings fields. No new secret. | Forward any new Settings field through `compose.yml` — the file already documents why (compose uses `.env` only for `${…}` substitution, so an unforwarded knobs silently loses the host override). |
| **Build artefacts / installed packages** | (1) `static/vendor/app.css` is a **committed build artefact** that must be regenerated and must stay byte-identical to a fresh build (guarded). (2) `apscheduler` becomes a new installed distribution → `pyproject.toml` + `requirements.txt` + a `test_dependency_pins.py` row. (3) The Docker image's `HOST`, `TZ` — see Pitfall 7. | Rebuild the CSS with the pinned CLI and commit it. Add the pin in both manifests. Consider a build-time assertion that `ZoneInfo("Europe/Dublin")` resolves. |
| **On-disk artefacts the DB thinks are rows** | `cv_artifacts.tex_path` / `pdf_path` point under `settings.artifacts_dir` (`/artifacts`, a bind mount `./artifacts`). `app/api/settings.py:144-146` already records the known gap: "the reset is DB-only and never touches the files under `artifacts_dir`, so deleting artifact rows leaves orphaned PDF/`.tex` files on disk (known, accepted follow-up)". | This phase is where that follow-up is paid: the artifact prune must unlink the files **after** committing the row deletes, scoped to paths that resolve under `artifacts_dir`. |

## Common Pitfalls

### Pitfall 1: `AsyncIOScheduler` and event-loop ownership
**What goes wrong:** `scheduler.start()` from a sync context raises `RuntimeError: no running event loop`; or a scheduler created in one loop is started in another and never fires.
**Why it happens:** `AsyncIOScheduler.start()` does `self._eventloop = asyncio.get_running_loop()`, and `_shutdown` clears `_eventloop` **inside** a `call_soon_threadsafe` callback.
**How to avoid:** create and start it inside the lifespan; keep the module-level singleton so tests and the settings route reach the same object; never `await` `shutdown()` (it is sync) and never assert "stopped" synchronously after it.
**Warning signs:** the settings page shows a next-run time but no run ever happens; `SchedulerNotRunningError` in the logs.

### Pitfall 2: `replace_existing=True` at boot silences `EVENT_JOB_MISSED`
**What goes wrong:** a run missed while the container was down is never reported on `/health`, so a dead scheduler looks identical to a scheduler with nothing to do — the exact failure mode this whole phase exists to prevent.
**Why it happens:** `_real_add_job` recomputes `next_run_time` for a job that has no such attribute and `update_job`s the stored state, discarding the past-due fire time.
**How to avoid:** Pattern 2 — create-if-absent, reschedule only on trigger drift.
**Warning signs:** a `runs` gap across a known restart with no "Last scheduled run was missed" line. Test it directly: write `apscheduler_jobs` with a past `next_run_time` (>1h ago) and assert the listener fires on start.

### Pitfall 3: The job's `func`/args must survive `pickle`
**What goes wrong:** `TypeError: cannot pickle '…' object` or `ValueError: This Job cannot be serialized…` at `add_job` — i.e. during boot — which (under D-08) degrades the scheduler to unavailable and the feature silently does nothing.
**Why it happens:** `Job.__getstate__` stores `func` as a `module:qualname` ref and passes `args`/`kwargs` through `pickle`.
**How to avoid:** module-level argument-free target; resolve dependencies inside the call. Add a test that only calls `scheduler.add_job(...)` against a real `SQLAlchemyJobStore` — it fails fast and loudly.
**Warning signs:** the scheduler never starts; `scheduler.start_failed` in the log.

### Pitfall 4: `SQLAlchemyJobStore` creates `apscheduler_jobs` outside Alembic — and a guard test notices
**What goes wrong:** `tests/db/test_orm_drift.py::test_orm_metadata_matches_migrated_schema` asserts `application_tables == set(Base.metadata.tables)` where `application_tables` excludes only `alembic_version`, `listing_fts*` and `sqlite_*`. `apscheduler_jobs` is neither an ORM table nor in that exclusion list ⇒ **db-only table ⇒ the guard fails** as soon as the table exists in a DB the test inspects. It also breaks the project's stated property that "the migration is the only schema writer".
**Why it happens:** `SQLAlchemyJobStore.start()` calls `self.jobs_t.create(self.engine, True)`, building its own `MetaData()` with `id Unicode(191) PK`, `next_run_time Float(25) indexed`, `job_state LargeBinary NOT NULL`.
**How to avoid — pick one and record it:**
  - **(a) Documented exemption (recommended).** Extend `_is_internal` in `tests/db/test_orm_drift.py` to exclude `apscheduler_jobs`, with a comment saying whose table it is and that its DDL is owned by the library. Cheapest, most honest: the table genuinely is not an application table.
  - **(b) Declare it in an Alembic migration** mirroring the library's shape. Preserves "migration is the only schema writer" but hard-couples the repo to a third-party internal schema, and an APScheduler upgrade that changes the columns then needs a hand-written migration.
  - **(c) Avoid the persistent store** (MemoryJobStore) — then you must hand-roll missed-run detection (see Alternatives).
**Warning signs:** the drift test failing only when a scheduler-started app has touched the temp DB. Note that httpx's `ASGITransport` does **not** run the lifespan (only `tests/db/test_source_seeding.py:138` invokes `main_module.lifespan(None)` explicitly), so this test can stay green in CI while the production DB has the extra table — decide deliberately rather than by accident.

### Pitfall 5: "One worker" is necessary but the check is not what you think
**What goes wrong:** the plan claims single-worker safety from `--workers 1` alone.
**Why it happens:** `--workers 1` (already pinned in `entrypoint.sh`) does guarantee one scheduler instance, and the userguide states the related rule that job stores "must never be shared between schedulers". But "execute only once" also has to survive a manual run being in flight, which `max_instances` cannot see.
**How to avoid:** keep `--workers 1` (add a brief comment in `entrypoint.sh` naming the scheduler as a second reason, since the file currently cites only the ranking task set) and add Pattern 3's DB guard.
**Warning signs:** two concurrent `runs` rows both `running`; doubled `llm_calls` in a rolling window.

### Pitfall 6: Reading `next_run_time` where it can be absent or `None`
**What goes wrong:** `get_job(...).next_run_time` raises `AttributeError` when the job does not exist, and returns `None` for a paused job. A health page that assumes a datetime 500s (violating every "decorative reads never raise" convention) or prints "in 0m".
**How to avoid:** total accessor returning `datetime | None`; branch `None` → `Scheduling off` when the stored row is disabled, else a distinct "no run scheduled" line. Never compute a countdown from `None`.
**Warning signs:** a `/health` page that 500s only on a fresh install.

### Pitfall 7: `Europe/Dublin` needs zone data in the image, and `tzlocal` sits behind it
**What goes wrong:** `ZoneInfo("Europe/Dublin")` raises `ZoneInfoNotFoundError` if the image ships no tz database; the scheduler then fails to build its trigger.
**Why it happens:** `zoneinfo` reads `/usr/share/zoneinfo` (or the `tzdata` PyPI package as a fallback). APScheduler 3.11.3 itself imports `zoneinfo` and requires `tzlocal` (whose `get_localzone()` is the *default* when no tz is passed — we always pass one, so `tzlocal` is not on our path).
**How to avoid:** add `ENV TZ=Europe/Dublin` and either confirm `python -c "from zoneinfo import ZoneInfo; ZoneInfo('Europe/Dublin')"` succeeds in the image or `apt-get install -y --no-install-recommends tzdata`. Given this project's established pattern of proving environment facts **at image build time** (the Tectonic `--version`/prime RUN, the JobSpy VCS assertion), the consistent move is a one-line `RUN` assertion next to those.
**Status:** `[ASSUMED]` — Debian's `debian:bookworm-slim` base generally carries `tzdata`, but that was **not** verified in this sandbox (no Docker). Treat as a confirmation checkpoint, not a fact.
**Warning signs:** `ZoneInfoNotFoundError` in the boot log; the scheduler reports "unavailable".

### Pitfall 8: Breakpoint arithmetic
**What goes wrong:** `@media (max-width: 767px)` plus Tailwind's `md` (`width >= 48rem`, i.e. 768px) leaves 767.01–767.99px matching **neither** regime — the desktop table with no reflow, or the reflow with no desktop rule.
**How to avoid:** `@variant max-md { … }` or `@media (width < 48rem)`, which are exact complements and were both verified to compile to `@media (width < 48rem)` with the pinned CLI.
**Warning signs:** the operator checklist at exactly 768px shows an apparently-broken table.

### Pitfall 9: Hiding `thead` while also emitting `data-label`
**What goes wrong:** the header text and the label text are the same words; a screen reader that still has the (clipped but present) `thead` may announce both, and `display:block` on `<tr>`/`<td>` already makes some engines drop table semantics.
**Why it happens:** the `data-label` pattern's known trade-off. `08-UI-SPEC.md` chooses clip-not-`display:none` to keep header semantics "best-effort".
**How to avoid:** pick one and state it: either `display:none` the `thead` below the breakpoint (the label carries the information; the table semantics are already degraded by `display:block`), or keep the clip and accept the possible duplication. Whichever is chosen, do not claim an accessibility guarantee the CSS does not deliver (CONVENTIONS rule 6 — no false guarantees, including in template comments and docstrings).
**Warning signs:** a UI-review finding that the phone table announces each field twice.

## Code Examples

### The prune query shape (guards as WHERE clauses)

Illustrative SQL; the real queries belong in `app/db/repositories/retention_repo.py` (repo rules: take an `AsyncSession`, never commit, wrap writes in `session.begin_nested()`).

```sql
-- Runs: floor = the newest RUN_HISTORY_LIMIT runs are never eligible, whatever the age.
-- (Reuse run_repo.RUN_HISTORY_LIMIT rather than inventing a number: it is already >=
--  source_repo.RECENT_RUN_LIMIT=20 and >= the probe windows 5/5/2, so one floor
--  satisfies D-165(1) for every reader by construction.)
SELECT id FROM runs
WHERE started_at < :cutoff
  AND id NOT IN (SELECT id FROM runs ORDER BY started_at DESC, id DESC LIMIT :floor)
  -- C3: a run whose events are undeletable cannot go
  AND NOT EXISTS (SELECT 1 FROM listing_events e WHERE e.run_id = runs.id);

-- Artifacts: guards 3 and 4, mirroring latest_for_listing(ok_only=True)'s ORDER BY.
SELECT id, tex_path, pdf_path FROM cv_artifacts
WHERE created_at < :cutoff
  AND NOT EXISTS (SELECT 1 FROM applications a WHERE a.cv_artifact_id = cv_artifacts.id)
  AND NOT EXISTS (
        SELECT 1 FROM cv_artifacts newer
        WHERE newer.listing_id = cv_artifacts.listing_id
          AND newer.compile_status = 'ok'
          AND (newer.created_at > cv_artifacts.created_at
               OR (newer.created_at = cv_artifacts.created_at AND newer.id > cv_artifacts.id)));

-- Source request log: age alone is not enough — the survival verdict reads it, so its
-- rows belonging to the retained run floor must survive (a genuine gap in D-165).
SELECT id FROM source_request_log
WHERE occurred_at < :cutoff
  AND (run_id IS NULL
       OR run_id NOT IN (SELECT id FROM runs ORDER BY started_at DESC, id DESC LIMIT :floor));

-- Listings (hard delete — see C2 for the decision this depends on)
SELECT id FROM listings
WHERE last_seen_at < :cutoff
  AND NOT EXISTS (SELECT 1 FROM applications a WHERE a.listing_id = listings.id)
  AND NOT EXISTS (SELECT 1 FROM listing_events e WHERE e.listing_id = listings.id)  -- C2(a)
  AND NOT EXISTS (SELECT 1 FROM listing_dupes d
                  WHERE d.listing_id = listings.id OR d.dup_listing_id = listings.id)
  AND NOT EXISTS (SELECT 1 FROM cv_artifacts c WHERE c.listing_id = listings.id);
```

The dry-run preview is `COUNT(*)` plus `SUM(stat().st_size)` over the **same** SELECT, so the number shown before destruction and the number deleted come from one predicate — never two.

### The two event listeners (D-154's two skip reasons)

```python
from apscheduler.events import (EVENT_JOB_MISSED, EVENT_JOB_MAX_INSTANCES,
                                JobExecutionEvent, JobSubmissionEvent)

def _on_scheduler_event(event) -> None:
    if event.code == EVENT_JOB_MISSED:            # JobExecutionEvent
        _queue_skip_notice("missed", when=event.scheduled_run_time)
    elif event.code == EVENT_JOB_MAX_INSTANCES:   # JobSubmissionEvent
        _queue_skip_notice("in_flight", when=event.scheduled_run_times)
```

Verified payloads from the 3.11.3 source: `EVENT_JOB_MISSED` is constructed as `JobExecutionEvent(EVENT_JOB_MISSED, job.id, jobstore_alias, run_time)` — it carries **`scheduled_run_time`**; `EVENT_JOB_MAX_INSTANCES` is constructed as `JobSubmissionEvent(EVENT_JOB_MAX_INSTANCES, job.id, jobstore_alias, run_times)` — it carries **`scheduled_run_times`** (a list). Both are dispatched only when the scheduler processes jobs, so the notice must be written durably.

**Where to record the skip — recommendation.** `runs.status` is `CHECK (status IN ('running','done','failed','partial'))` (`models.py:339-342`), so a "skipped" run is **not** representable as a `runs` row without a batch recreation of `runs` — the exact hazard `test_upgrade_populated_0001_to_head` guards against. A missed fire is also not a run. Recommended: store the notice as JSON on the `operations_config` row (`last_schedule_skip_json`), rendered on `/health` and on the settings schedule card, and confined to one small read. Cheaper than a migration, semantically honest, and it cannot be mistaken for a run. The `runs`-row alternative (adding a fifth status) is the option to reject explicitly.

### The CSS block (authoring order)

1. Edit `assets/tailwind/input.css`: add `.table-scroll`, `.touch-target`, `.health-system` to the `@layer components` blocks; add the `@variant max-md { … }` reflow block last (so it can override the desktop rules it reflows).
2. Add `data-label` to the journey-table `<td>`s and wrap the non-journey tables in `.table-scroll`.
3. Rebuild: `./node_modules/.bin/tailwindcss -i ./assets/tailwind/input.css -o ./static/vendor/app.css --minify`
4. Prove: `pytest tests/test_stylesheet_coverage.py -x` (byte-identity + every template class definable from source).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| APScheduler 3.x stores `func` by pickling the function object | 3.11.x stores a `module:qualname` text ref and **raises** on a lambda/nested function | by 3.11.3 | A local closure now fails loudly at `add_job` instead of producing an unpicklable blob — a better error, but the "module-level only" rule is now enforced by the library. |
| The 3.x userguide lists `job_defaults = {'coalesce': False, 'max_instances': 3}` | The 3.11.3 source sets `coalesce` default `True`, `max_instances` default `1`, `misfire_grace_time` default `1` | drift in the docs | Never rely on the defaults; pass all four explicitly (Phase 8 does). |
| Tailwind v3 hijacked `@layer components` and made its classes variant-capable | v4 uses native cascade layers and `@utility` for variant-capable custom utilities | v4.0 | A class defined in `@layer components` cannot be used as `md:my-class` in HTML. Phase 8 does not need that: the variant lives **inside** the CSS. |
| Hand-rolled `@media (max-width: 767px)` | `@variant max-md` / range syntax `@media (width >= 48rem)` | Tailwind 4 | Exact complements of the generated breakpoints; verified in the pinned build. |

**Deprecated/outdated:**
- **APScheduler 4.x** (`AsyncScheduler`, `SQLAlchemyDataStore`, `CoalescePolicy`, `add_schedule`, `max_running_jobs`) — alpha, and a completely different API. Context7's `/agronholm/apscheduler` snippets are **4.x** (they document `AsyncScheduler`, `CoalescePolicy.latest`, `JobOutcome.missed_start_deadline`). Do not take API names from them; the 3.11.3 facts in this document were read from the pinned sdist instead.
- **`pytz`** — APScheduler 3.11.3 uses stdlib `zoneinfo`; `pytz` is only an optional/test dependency. No new pin.
- **`searches.schedule_cron`** — a v1 placeholder, deliberately unused (D-151).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `debian:bookworm-slim` (the `python:3.13-slim` base) ships the system tz database, so `ZoneInfo("Europe/Dublin")` resolves without installing `tzdata`. | Pitfall 7, Environment Availability | The scheduler cannot build its trigger; scheduled runs never fire while everything else looks healthy. Mitigation: a build-time assertion (`RUN python -c "…ZoneInfo('Europe/Dublin')…"`) next to the existing Tectonic/JobSpy build-time proofs. |
| A2 | The `apscheduler` PyPI metadata's missing project URL is a metadata gap, not a slopsquat signal — the package is the real `agronholm/apscheduler`. | Package Legitimacy Audit | Installing a hijacked distribution. Mitigation: the mandatory `checkpoint:human-verify` before install, plus the fact that the 3.11.3 sdist in this session contains the genuine docs/tests/examples tree and the `tzlocal>=3.0` dependency the real project declares. |
| A3 | `RUN_HISTORY_LIMIT = 50` is an adequate expression of D-165(1)'s "floor of recent runs" (it is ≥ `source_repo.RECENT_RUN_LIMIT = 20`, ≥ `probe_promotion_window_runs = 5`, ≥ `probe_count_trailing_runs = 5`). | Pattern 8 / prune SQL | If any reader needs a longer window than 50, a prune could starve it. Cheap to re-derive: the floor should be `max(existing read windows)`, and 50 is the maximum today. |
| A4 | The 4 dependency probes on the page can reuse the *existing* `_opencode_report` / `_tectonic_report` / `_cv_report` behaviour unchanged (report, never raise). | Pattern 6 | A page that 500s on a degraded dependency, breaking D-08's contract that a missing backend never degrades the app's own health. |
| A5 | A new `/health` **page** path (rather than taking over `/health`) satisfies RUN-07's "health endpoint surfaced in the UI". | Critical constraint C1 | The requirement is read as "the page must be at `/health`" and the plan has to pay the C1 option-3 churn. This is a naming decision the user can settle in one line. |
| A6 | Recording a missed/in-flight skip as JSON on the operations row (not a `runs` row) satisfies D-154's "records why it skipped". | Pattern 3 / listener example | If a `runs` row is required, migration 0008 must also batch-recreate `runs` to add a fifth status — the exact hazard `test_upgrade_populated_0001_to_head` exists to catch. |
| A7 | The `queue_state` in D-167 is a wording slip for the per-listing child tables. | Critical constraint C2 | If it is taken literally, the plan tries to delete a global singleton row per listing and either corrupts the watermark or no-ops. |

## Open Questions (RESOLVED)

All five were settled as binding decisions in the planning session that followed this
research. Each is implemented by a plan; the resolution line names it. Nothing here is
left open, so a downstream reader does not have to rediscover the answer.

1. **C2 — does D-167's hard delete get a D-164 carve-out, or is it restricted to untouched listings?**
   - What we know: the trigger + FK make the delete impossible for any listing with an event row; the reset already ships a tested mechanism (`_suspend_append_only_trigger`) that suspends and re-arms it inside one transaction.
   - What's unclear: whether the user accepts an explicit "never pruned *except* when their parent listing is hard-deleted" amendment to D-164.
   - Recommendation: option (b) — reuse the reset's mechanism, record the amendment in the plan, and add the re-arm assertion the reset itself lacks. If the user prefers strict D-164, take option (a) and accept that the stale-listing category only ever matches never-touched listings.
   - **RESOLVED (orchestrator decision 2, 2026-10-14): option (b).** The carve-out reuses `_suspend_append_only_trigger` / `_restore_append_only_trigger` inside one transaction, the D-164 amendment is recorded explicitly, and the re-arm assertion the reset itself lacks is added. Implemented by plan 08-05 Task 3.

2. **C1 — which `/health` path wins?**
   - What we know: the JSON path is pinned in 25 assertions, the auth-seam route inventory, and `scripts/compose-smoke.sh`.
   - Recommendation: page at a distinct path + a `Health` nav entry (zero churn). Confirm with the user only if the literal path matters.
   - **RESOLVED (orchestrator decision 1, 2026-10-14): the JSON endpoint keeps `/health`; the page takes `/status`** and the nav entry keeps the label `Health`. FastAPI matches routes in declaration order, so the page must not also declare `/health`. Implemented by plan 08-04 Task 1.

3. **Should the `source_request_log` prune carry a run-floor guard?**
   - What we know: `survival.py:5` names `source_request_log` as a verdict input; D-165(1)'s floor covers `runs` but not the log.
   - Recommendation: yes — keep rows whose `run_id` is in the retained run floor (see the prune SQL). Otherwise an aggressive age threshold silently degrades the Adzuna verdict the same page is displaying.
   - **RESOLVED (orchestrator decision 3, 2026-10-14): yes.** The source-request-log prune keeps every row whose run is inside the retained run floor. Implemented by plan 08-05 Task 2.

4. **Stale `running` run rows after an unclean shutdown.**
   - What we know: `run_pipeline` catches `except Exception` only, and `AsyncIOExecutor.shutdown` cancels in-flight futures; a cancelled run keeps `status='running'` forever, which then blocks `POST /settings/reset` and every future scheduled run (Pattern 3).
   - Recommendation: a small boot-time reconciliation marking non-terminal runs from a previous process as `partial` with a recorded error. Not a requirement — but the failure it prevents is a permanently stuck feature.
   - **RESOLVED (orchestrator decision 4, 2026-10-14): yes, and the terminal value is pinned to `partial` with a recorded error.** Implemented by plan 08-03 Task 2.

5. **Does the prune need a `snapshot_database()` call first?**
   - What we know: `snapshot_database` exists and the reset uses it; D-166 asks only for a preview + confirm and says nothing about a snapshot.
   - Recommendation: a snapshot for the *listing* category (one-way delete, D-167) is cheap insurance; skip it for the reversible-by-regeneration categories. Decide explicitly rather than by omission.
   - **RESOLVED (orchestrator decision 5, 2026-10-14): snapshot the stale-listing category only;** the regenerable categories are not snapshotted. Implemented by plan 08-05 Task 3.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node + pinned Tailwind CLI | Rebuilding `static/vendor/app.css` (UI-06) | ✓ | `tailwindcss v4.3.3` at `node_modules/.bin/tailwindcss` (verified) | None needed — and `tests/test_stylesheet_coverage.py` **skips visibly** (never silently passes) when absent |
| `pip` + PyPI network | Installing the new pin | ✓ | `pip3` present; `pip download --no-deps apscheduler==3.11.3` succeeded | — |
| `apscheduler` | RUN-05/06, PLAT-06 | ✗ | — | None — it is the phase's one new dependency and must be installed + pinned in both manifests |
| Project Python env (`.venv` with deps) | Running the test suite | ✗ | sandbox `python3` is 3.11.2 with no project deps | Operator/container: `docker compose run --rm app pytest` (the Dockerfile explicitly supports it) |
| Docker Engine + Compose v2 | `compose-smoke.sh`, the persistence half of PLAT-06 | ✗ | — | `docs/runbook-compose-smoke.md` (established operator-run pattern) |
| A browser + device emulation | D-161's 320/375/768 checklist | ✗ | — | `docs/runbook-responsive-ui.md` operator checklist (new) |
| `zoneinfo` tz database in the image | `Europe/Dublin` trigger | Unverified | — | `apt-get install --no-install-recommends tzdata`, or the `tzdata` PyPI package. See A1 |
| Tectonic | nothing in this phase | ✗ (absent from sandbox) | — | The `latex` lane stays operator-run (D-69) |
| `gh` / a GitHub token | nothing in this phase | — | — | — |

**Missing dependencies with no fallback:**
- `apscheduler` — must be installed; blocked behind the `[SUS]` legitimacy checkpoint (see the audit).

**Missing dependencies with fallback:**
- Project Python env, Docker, a browser — all covered by the established operator-run pattern. The plan must not silently assume they exist; use `pytest.skip` with a named arming command (the `test_stylesheet_coverage` precedent), never a silent pass.

## Validation Architecture

Framework: the project's existing lane, no new tooling.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest==9.1.1` + `pytest-asyncio==1.4.0` (`asyncio_mode = "auto"`) |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `addopts = "-m 'not live and not latex'"`) |
| Quick run command | `docker compose run --rm app pytest tests/jobs/test_scheduler.py tests/db/test_retention_repo.py -x -q` (local `.venv`: `pytest <same paths> -x -q`) |
| Full suite command | `docker compose run --rm app pytest` — the default lane is hermetic (offline LLM stub, temp migrated DB) |
| CSS guard (needs node) | `pytest tests/test_stylesheet_coverage.py -x` — byte-identity of `static/vendor/app.css` against a fresh pinned build |

### Phase Requirements → Test Map
| Req ID | Behaviour | Test Type | Automated Command | File Exists? |
|--------|-----------|-----------|-------------------|--------------|
| RUN-05 | Saving the settings form creates/replaces exactly one APScheduler job with the right `CronTrigger` and tz; disabling removes it | integration (real `SQLAlchemyJobStore` on a temp DB) | `pytest tests/api/test_schedule_settings.py -x` | ❌ Wave 0 |
| RUN-05 | `run_scheduled_pipeline` calls `run_pipeline("schedule", None, factory)` and writes exactly one `runs` row with `trigger='schedule'` | integration | `pytest tests/jobs/test_scheduler.py::test_target_runs_the_pipeline -x` | ❌ Wave 0 |
| RUN-06 | `next_run_time` renders as a countdown; absent job → `Scheduling off`; paused job → no fabricated time | unit + route | `pytest tests/api/test_health_page.py -x` | ❌ Wave 0 |
| PLAT-06 | Re-registration at boot does **not** overwrite a persisted past-due `next_run_time` (Pitfall 2) | integration (seed `apscheduler_jobs`, start, assert the stored row is untouched) | `pytest tests/jobs/test_scheduler.py::test_boot_does_not_clobber_a_past_due_run -x` | ❌ Wave 0 |
| PLAT-06 | A fire while a manual run is in flight skips and records why (Pattern 3) | integration (insert a non-terminal `runs` row, invoke the target) | `pytest tests/jobs/test_scheduler.py::test_in_flight_run_is_not_overlapped -x` | ❌ Wave 0 |
| PLAT-06 | `EVENT_JOB_MISSED` with a `scheduled_run_time` older than the grace window records the missed notice | unit (synthetic `JobExecutionEvent`) | `pytest tests/jobs/test_scheduler.py::test_missed_fire_is_surfaced -x` | ❌ Wave 0 |
| PLAT-06 | `start_scheduler`/`stop_scheduler` are idempotent and never raise; a broken jobstore degrades to "unavailable" | unit (D-08) | `pytest tests/jobs/test_scheduler.py::test_start_is_total -x` | ❌ Wave 0 |
| RUN-07 | The page and the JSON `/health` agree on `auth_configured` and opencode reachability (D-138) | route pair | `pytest tests/api/test_health_page.py::test_page_and_json_cannot_disagree -x` | ❌ Wave 0 |
| RUN-07 | The page's source badge is computed from recorded runs and **makes no board request** (assert the probe cache is untouched / the adapter is never called) | integration with a sentinel adapter (the `tests/api/test_health.py` pattern) | `pytest tests/api/test_health_page.py -x` | ❌ Wave 0 |
| RUN-07 | The Adzuna verdict line is read-only: no control, no escalation, and the number matches `adzuna_promotion_condition` on the same evidence | unit + template assertion | `pytest tests/api/test_health_page.py -x` | ❌ Wave 0 |
| RUN-07 | The page never raises on a degraded dependency, a broken DB, or a missing scheduler | unit (D-08 totality) | `pytest tests/api/test_health_page.py -x` | ❌ Wave 0 |
| Retention (D-163…D-168) | Each guard holds: floor of runs kept; no `llm_calls` deleted; application-linked artifact kept; newest `ok` artifact per listing kept (parametrized over the failure class, CONVENTIONS rule 4) | unit against a migrated temp DB | `pytest tests/db/test_retention_repo.py -x` | ❌ Wave 0 |
| Retention | The dry-run preview count/size equals what the real prune deletes — same predicate, one definition | integration (preview then prune, compare) | `pytest tests/db/test_retention_repo.py -x` | ❌ Wave 0 |
| Retention | The artifact prune unlinks `.tex`/`.pdf` **after** commit, never a path outside `artifacts_dir`, and reports a missing file rather than failing | unit (tmp_path artefacts dir) | `pytest tests/db/test_retention_repo.py -x` | ❌ Wave 0 |
| Retention | Deleting a listing in the C2(a) case leaves the append-only trigger armed and the FK invariants intact; in the C2(b) case the trigger is **re-armed** after the transaction | integration (`sqlite_master` assertion, `test_migration_contract.py` style) | `pytest tests/db/test_retention_repo.py -x` | ❌ Wave 0 |
| Retention | Migration 0008 creates `operations_config` with the named singleton CHECK; `EXPECTED_JSON_COLUMNS` gains the new columns; the head moves 0007 → 0008 | migration contract | `pytest tests/db/test_migration_contract.py tests/db/test_no_pii_columns.py tests/db/test_orm_drift.py -x` | ⚠️ exists, must be **edited** (head pin + JSON allow-list + the Pitfall-4 exemption decision) |
| UI-06 | Every new class has a rule in the source stylesheet and the committed CSS is its byte-identical build | guard (exists) | `pytest tests/test_stylesheet_coverage.py -x` | ✅ exists |
| UI-06 | No CDN reference was introduced by the new page/nav | guard (exists) | `pytest tests/test_no_cdn.py -x` | ✅ exists |
| UI-06 | The reflow actually emits the card layout at the phone breakpoint and the desktop rules at ≥768px | operator-run (no browser in the sandbox) | `docs/runbook-responsive-ui.md` checklist | ❌ Wave 0 (new runbook) |
| UI-06 | 320/375/768 × {queue, listing detail, health, run control, applications} manually inspected | operator-run | same runbook, signed off in UAT | ❌ Wave 0 |
| PLAT-06 (persistence half) | Schedule survives `docker compose restart` and fires exactly once | operator-run | `docs/runbook-compose-smoke.md` + a new schedule step | ⚠️ exists, must be **extended** |

### Sampling Rate
- **Per task commit:** the touched test file(s), `pytest <paths> -x -q`.
- **Per wave merge:** `docker compose run --rm app pytest` (full hermetic suite; it includes the CSS byte-identity guard and the migration contract).
- **Phase gate:** full suite green **plus** the two operator runbooks (compose-smoke with the new schedule step, responsive UI checklist) before `/gsd-verify-work`. The `latex` lane stays operator-run and its result must be recorded as UNRUN rather than rounded up (D-69) — but this phase changes nothing in the LaTeX path, so it is not a gate.

### Wave 0 Gaps
- [ ] `tests/jobs/test_scheduler.py` — needs a fixture that builds a real `AsyncIOScheduler` + `SQLAlchemyJobStore` on a temp file **without** the app lifespan (httpx's `ASGITransport` does not run lifespan; only `tests/db/test_source_seeding.py:138` invokes it explicitly).
- [ ] `tests/db/test_retention_repo.py` — needs a seeded migrated DB with a floor-exceeding set of runs, an application-linked artifact, two `ok` artifacts for one listing, and a real `artifacts_dir` under `tmp_path`.
- [ ] `tests/api/test_health_page.py` — a page-level analogue of `tests/api/test_health.py`'s backend/probe stubs, plus the sentinel-adapter assertion that no board request happened.
- [ ] `tests/api/test_schedule_settings.py` — form round-trip (valid time, junk time, timezone allow-list).
- [ ] `docs/runbook-responsive-ui.md` — the D-161 checklist (320/375/768 × journey pages).
- [ ] Edits to **existing** guards that will fail until updated: `tests/db/test_migration_contract.py` (head `0007` → `0008`; `versions == ["0007"]` appears twice), `tests/db/test_no_pii_columns.py` (the new JSON columns), `tests/db/test_orm_drift.py` (only if the Pitfall-4 decision is (a)), `tests/test_config.py` (`REQUIRED_SETTINGS_SURFACE` / `LIMIT_FIELDS` for any new numeric `Settings` field, e.g. the misfire grace), `tests/test_dependency_pins.py` (the `apscheduler` row), `tests/test_auth_seam.py` (`EXPECTED_SEAM_ROUTES` + the new page route must carry `current_user`).
- [ ] Framework install: none — the lane already exists.

## Security Domain

`security_enforcement` is enabled (no `security_enforcement: false` in `.planning/config.json`; `STATE.md` records the Phase-3 note that enforcement is on). This phase adds one new destructive route and one new page, so the ASVS surface is small but non-empty.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | v1 has no authentication by decision (D-21); every new route still carries `Depends(current_user)` so the seam is universal (PLAT-03, asserted by `tests/test_auth_seam.py`). |
| V3 Session Management | no | No sessions exist in v1. |
| V4 Access Control | partial | No authorization model exists in v1 — every route is the local user's. The relevant control is the **route inventory**: the new page and the two prune routes must all declare the seam, or `tests/test_auth_seam.py` fails. The prune joins `POST /settings/reset` in the danger zone and inherits its documented caveat: *"v1 has no authentication at all (D-21), so there is no ambient credential for a cross-site request to abuse and this route is not CSRF-exploitable today. That changes the moment session authentication lands… unless a CSRF token is added"* (`app/api/settings.py:12-15`). Phase 8 must **extend that comment to the prune routes** rather than leave the new destructive route undiscussed. |
| V5 Input Validation | yes | The settings form is the attack surface: `time` and `timezone` come from the browser and must be validated server-side (the criterion/timezone pattern — validate against an allow-list and re-render a refusal, never `eval`/`exec`, never a raw cron string). The prune `category` must be an **allow-listed literal** mapping to a fixed query — never interpolated into SQL. The age threshold must be a positive integer (a `0` or negative threshold deletes everything eligible). Every new form path must reuse `app/api/searches.read_form` (urlencoded, `python-multipart` deliberately absent) and the existing `templates.TemplateResponse` refusal convention (400 + banner), never a bare 500. |
| V6 Cryptography | no | No new crypto. The CV verification hashes and the artefact `ok`-only access control are unchanged. **Do not** introduce a hash-based "prune receipt"; the audit line is a log line and a JSON field. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| **Path traversal via `cv_artifacts.tex_path`/`pdf_path`** — a hand-edited or legacy row pointing at `/etc/…` would be unlinked by the prune | Tampering / Elevation | Resolve each path and assert it is inside `Path(settings.artifacts_dir)` **before** unlinking; skip and report anything that is not. The same guard belongs in the dry-run's size computation (a `stat()` on an arbitrary path is itself an information leak in the log). |
| **SQL injection through the prune category** | Tampering | `category` maps through a frozen `dict[str, Query]` of pre-built statements (the `ACTION_SURFACES` allow-list precedent in `app/api/events.py`); no f-string ever reaches a statement. |
| **Destructive action triggered by a GET / prefetch / link** | Tampering | Both prune steps are `POST` forms (the reset precedent), the preview and the confirm are **separate** submits, and the confirm form only exists when the preview returned a non-zero count. |
| **Unbounded deletion from a mis-typed threshold** | Denial of Service (self-inflicted, data-destroying) | The threshold is a bounded positive integer; the preview is mandatory and is the same predicate as the delete; the D-165 guards are WHERE clauses, so they cannot be forgotten at the confirm step. Never pre-fill the threshold with a destructive default. |
| **Health page as a scraping trigger** | — (ban risk, not STRIDE) | The page reads the DB only; `probe_all` is not on its path. Asserted by a sentinel-adapter test (T-01-31's pattern). |
| **Health page echoing raw upstream/DB content** | Information Disclosure | Keep `_opencode_report`/`_tectonic_report`'s convention of exposing the exception **class name only** and a bounded, already-disclosed path; no raw `compile_log`, no listing text, no exception messages. |
| **CSRF on the prune routes once auth lands** | Spoofing | Documented in the extended `app/api/settings.py` module docstring (see V4) so it is a recorded known future requirement, not a rediscovery. |

## Sources

### Primary (HIGH confidence)
- **`apscheduler` 3.11.3 pinned sdist, read directly this session** (`pip download --no-deps apscheduler==3.11.3`, unpacked at `/tmp/opencode/aps/x/apscheduler-3.11.3`) — `src/apscheduler/schedulers/base.py` (`_job_defaults`, `_real_add_job`, `_process_jobs`, `reschedule_job`), `src/apscheduler/schedulers/asyncio.py` (`start`, `_shutdown`, `_create_default_executor`), `src/apscheduler/executors/base.py` (`submit_job`, `run_job`, `run_coroutine_job`), `src/apscheduler/executors/asyncio.py` (`iscoroutinefunction_partial`, `create_task`), `src/apscheduler/job.py` (`__getstate__`, `func_ref`), `src/apscheduler/jobstores/sqlalchemy.py` (`jobs_t.create(engine, True)`, `pickle.dumps(job.__getstate__())`), `pyproject.toml` (`dependencies = ["tzlocal >= 3.0"]`).
- **The pinned Tailwind CLI in this repo** — `./node_modules/.bin/tailwindcss` reports `v4.3.3`; a probe stylesheet was built through it and its output inspected (`@layer components` emitted verbatim, `@variant md` → `@media (width >= 48rem)`, `@variant max-md` → `@media (width < 48rem)`, `theme(--breakpoint-md)` → `48rem`, `content: attr(data-label)` preserved).
- **This repository, read this session:** `app/main.py`, `app/config.py`, `app/db/session.py`, `app/db/models.py` (L100-608), `app/db/repositories/{run_repo,source_repo,cv_artifact_repo,apply_config_repo}.py`, `app/api/{runs,health,settings}.py`, `app/web/routes.py`, `app/pipeline/run.py`, `app/probe/{probe,survival}.py`, `app/sources/_ledger.py`, `app/api/deps.py`, `alembic/versions/0001_initial_schema.py` + `0006_screening_drafts.py`, `assets/tailwind/input.css` (structure), `static/vendor/app.css` (presence of theme vars), `Dockerfile`, `entrypoint.sh`, `compose.yml`, `pyproject.toml`, `docs/probe/README.md`, `docs/runbook-compose-smoke.md`, `scripts/compose-smoke.sh`, and eleven `tests/` files (`test_stylesheet_coverage.py`, `test_migration_contract.py`, `test_orm_drift.py`, `test_auth_seam.py`, `test_no_pii_columns.py`, `test_dependency_pins.py`, `test_no_cdn.py`, `test_config.py` (surface + LIMIT_FIELDS), `test_health.py` (head), `test_deploy_manifest.py` (head), `test_source_seeding.py` (lifespan usage)), plus `08-CONTEXT.md` and `08-UI-SPEC.md`.
- **APScheduler 3.x docs (readthedocs, `/en/3.x/`)** — `modules/events.html` (the `EVENT_JOB_MISSED`/`EVENT_JOB_MAX_INSTANCES` table and their event classes), `modules/schedulers/base.html` (`add_job`/`reschedule_job`/`get_job`/`remove_job`/`start`/`shutdown(wait=)` signatures), `modules/job.html` (`next_run_time` — "the next scheduled run time of this job"), `userguide.html` (job-store persistence, the misfire section, "job stores must never be shared between schedulers", the explicit-id + `replace_existing` note).
- **`pip download`/PyPI JSON** — `apscheduler==3.11.3` exists and downloads; `requires-python = ">= 3.8"`.

### Secondary (MEDIUM confidence)
- GitHub discussion `agronholm/apscheduler#1088` (2025-11-17) — the recommended FastAPI + gunicorn multi-worker pattern: one scheduler process, or leader election, because "every worker gets its own scheduler instance — so your jobs run N times". Corroborates the `--workers 1` requirement.
- Stack Overflow 71984085 / GitHub issues `agronholm/apscheduler#872`, `#933`, `#871` — real-world `SQLAlchemyJobStore` pickling failures (`Base`, `_io.TextIOWrapper`, `_asyncio.Task`, `TaskStepMethWrapper`) confirm the pickle constraint in practice and that `MemoryJobStore` "does not pickle anything".
- Individual Tailwind docs pages (`adding-custom-styles`, `upgrade-guide`, `responsive-design`, `theme`, `functions-and-directives`) — `@variant`, `@custom-variant`, `@utility`, `@theme`, the default breakpoint table and the `theme()` CSS-variable guidance. Corroborated by the local build.

### Tertiary (LOW confidence)
- **Context7 `/agronholm/apscheduler` snippets returned the 4.x API** (`AsyncScheduler`, `SQLAlchemyDataStore`, `CoalescePolicy`, `add_schedule`, `max_running_jobs`, `JobOutcome.missed_start_deadline`). Recorded here as a **warning**, not as a source: those names are wrong for 3.11.3 and must not enter the plan. The 3.x facts above were taken from the pinned sdist instead.
- `websearch` snippet text for the 3.x userguide's `job_defaults` example (`{'coalesce': False, 'max_instances': 3}`) contradicts the 3.11.3 source (`coalesce=True`, `max_instances=1`, `misfire_grace_time=1`). The source wins; the plan passes all four options explicitly so the discrepancy is moot.

## Metadata

**Confidence breakdown:**
- Standard stack / scheduler mechanics: **HIGH** — every load-bearing claim was read from the pinned 3.11.3 sdist or its readthedocs 3.x pages, and the event constants/payloads were read from the constructor call sites.
- Architecture (wiring, reconciliation, in-flight guard, the two contradictions): **HIGH** for the mechanics; **MEDIUM** for the *resolution* of C2/C1/A6, which are user decisions.
- Retention SQL: **MEDIUM-HIGH** — the FK graph, the trigger and the guard-4 read were all read from source, but the ordering (C2/C3) rests on a decision not yet taken, and the `source_request_log` floor is a guard D-165 does not state.
- Pitfalls: **HIGH** except Pitfall 7 (tz data in the image), which is `[ASSUMED]` and cheap to confirm at build time.
- CSS/responsive: **HIGH** — verified by building with the pinned CLI in this repo.
- Validation architecture: **MEDIUM** — the operator-run half cannot be executed here (no Docker, no browser) and is deliberately planned as a runbook, per the project's established norm.

**Research date:** 2026-10-14
**Valid until:** ~2026-11-13 (30 days) for the repo-internal findings; the APScheduler 3.11.3 facts are pinned and do not expire, and the Tailwind findings are pinned to 4.3.3.

## RESEARCH COMPLETE

Phase 8 is implementable as planned, with **three decisions the planner must take deliberately rather than by default**:
1. **C1** — the health page's path (recommend a distinct path; `/health` stays JSON).
2. **C2** — whether D-167 gets a D-164 carve-out (recommend reusing the reset's trigger-suspend, recorded as an amendment) or is restricted to untouched listings.
3. **A6** — where a skipped/missed fire is recorded (recommend JSON on the ops row; do not add a fifth `runs.status`).

Everything else is grounded: `AsyncIOScheduler` + `SQLAlchemyJobStore(engine=<sync engine with the WAL pragmas>)`, one argument-free module-level target that guards on a non-terminal `runs` row, create-if-absent boot reconciliation so `EVENT_JOB_MISSED` stays reachable, one migration (0008) for the `operations_config` singleton, the four D-165 guards as WHERE clauses with the FK ordering spelled out, and a `data-label` reflow built and proven with the pinned Tailwind CLI.

