# Phase 8: Operations + Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-14
**Phase:** 8-Operations + Polish
**Areas discussed:** Scheduling model & run safety, Health surface & source signals, Responsive scope & acceptance, Retention / pruning of history

---

## Scheduling model & run safety

### Q1 — Scope of the schedule

| Option | Description | Selected |
|--------|-------------|----------|
| One global schedule | One cron for the whole pipeline, mirroring today's `POST /runs` (`search_id=None` → all enabled searches) | ✓ |
| Per-search schedule | Each search gets its own cadence; `searches.schedule_cron` finally gets a writer | |
| Both global and per-search | A global default plus per-search overrides | |

**User's choice:** One global schedule.
**Notes:** `searches.schedule_cron` stays unused. Matches the shape of the existing manual trigger exactly, so `run_pipeline` needs no new mode.

### Q2 — What the user actually configures

| Option | Description | Selected |
|--------|-------------|----------|
| Daily time-of-day preset | Pick a time; the app derives the cron | ✓ |
| Preset + weekdays | Time plus day-of-week selection | |
| Raw cron string | The user types a cron expression | |
| Preset + cron escape hatch | Preset UI with an override box | |

**User's choice:** Settings-page field with a **time picker**, choosing the time **and the timezone**. Weekday selection deferred.
**Notes:** The user's words: *"Should be a user field in the settings, you could use a datetime view so they can pick what time to run it at and timezone. In the future we can support which days of the week if needs be"*. Cron is an acceptable internal representation; the user never types it.

### Q3 — Where the schedule lives

| Option | Description | Selected |
|--------|-------------|----------|
| DB row, runtime-editable | A new singleton config row the Settings page edits, no restart | ✓ |
| Env var in `app/config.py` | Static config changed by editing `.env` and restarting | |
| Reuse `searches.schedule_cron` | Put the cron on the existing search row | |

**User's choice:** DB table for settings, runtime-editable.
**Notes:** User's words: *"DB table for settings, I will say in the future we could support mulitple users so keep that in mind. I would like to potentially support authentik login"*. Keep the row shape open for a future `user_id`, but do not pay for auth now (D-21: no `user_id` columns in v1). Mirrors `RankingConfig`/`ApplyConfig`.

### Q4 — Missed runs and overlapping runs

| Option | Description | Selected |
|--------|-------------|----------|
| Skip stale, surface it, never overlap | Missed > 1h grace → skip, never back-fill, but tell the user; in-flight run → skip the scheduled trigger and record why | ✓ |
| Catch up on boot | Run once on startup if runs were missed | |
| Silent default behaviour | Let APScheduler's defaults decide, no surfacing | |

**User's choice:** Skip stale, surface it, never overlap.
**Notes:** Misfires are never back-filled. The absence itself is reported to the user rather than hidden.

---

## Health surface & source signals

### Q1 — Where health lives

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated `/health` page + keep queue strip | Full page for system + per-source detail; the compact queue-page strip stays | ✓ |
| Reuse the existing queue strip only | No new page | |
| Dedicated page, drop the strip | One place for health, queue gets nothing | |

**User's choice:** Dedicated `/health` page plus the existing compact strip.

### Q2 — What drives the source badge

| Option | Description | Selected |
|--------|-------------|----------|
| Recorded run outcomes; no board probe from health | Badge comes from recorded run results / stop signals over the last N runs; viewing health never contacts a board | ✓ |
| Recorded outcomes + a live probe column | Both, the probe kept as a separate column | |
| Keep the probe as source of truth | Status stays the live probe stamp | |

**User's choice:** Recorded run outcomes; the health page reads the DB only.
**Notes:** A page view must never be a scrape. The live probe survives, but only as an explicit operator action.

### Q3 — What the system section contains

| Option | Description | Selected |
|--------|-------------|----------|
| Four probes + next run + last run reason | db, opencode (incl. `auth_configured`), Tectonic, CV fact store; next scheduled run; last run status + one-line reason | ✓ |
| Dependency probes only | No schedule visibility on the page | |
| Probes + next/last + live in-flight run | Adds a live stage-log indicator | |

**User's choice:** Four probes + next run + last run reason, assembled from data that already exists — no new measurement.

### Q4 — The Adzuna escalation machinery

| Option | Description | Selected |
|--------|-------------|----------|
| Show the verdict read-only; never auto-act | Display the computed condition as evidence, link the probe doc; the decision stays human | ✓ |
| No escalation info in the UI at all | Keep it entirely in the probe docs | |
| Manual enable-Adzuna action | A button that promotes the adapter | |

**User's choice:** Show the verdict read-only; nothing escalates or changes adapters automatically.
**Notes:** A manual enable control is SRC-11 v2 scope, explicitly not this phase.

---

## Responsive scope & acceptance

### Q1 — How far phone support reaches

| Option | Description | Selected |
|--------|-------------|----------|
| Primary journey on phone, admin desktop-first | Queue, listing detail, `/health`, run control, applications comfortable; admin surfaces must not break but stay desktop-first | ✓ |
| Full parity everywhere | Every page including criteria editor and settings | |
| Queue glance only | Just the listing list | |

**User's choice:** Primary journey phone-comfortable; admin surfaces desktop-first.

### Q2 — How the responsive work is done

| Option | Description | Selected |
|--------|-------------|----------|
| Tailwind media queries + targeted card reflow | Author rules in `assets/tailwind/input.css`; card-reflow only the journey tables (queue, applications, health); other tables get an accessible scroll region; no JS | ✓ |
| Card-reflow all tables | Reflow every table on the site | |
| Accessible horizontal scroll only | Add scroll regions everywhere, no reflow | |

**User's choice:** Tailwind media queries with card-reflow for the journey tables only; accessible scroll regions (`tabindex="0"`, `role="region"`, `aria-label`) elsewhere; no JavaScript.

### Q3 — How "usable on a phone" is proven

| Option | Description | Selected |
|--------|-------------|----------|
| `gsd-ui-review` audit + operator viewport checklist | The project's existing 6-pillar audit plus a runbook checklist at named widths (320/375/768) × journey pages | ✓ |
| Automated headless-browser test | Add Playwright | |
| Informal manual check | A quick look, no record | |

**User's choice:** `/gsd-ui-review` audit plus a documented operator-run checklist in a runbook.
**Notes:** Docker and a browser are absent from the agent sandbox, so operator-run checks are the established norm (`docs/runbook-compose-smoke.md`).

### Q4 — What a phone queue row shows

| Option | Description | Selected |
|--------|-------------|----------|
| Restack all row data, hide nothing | Label:value lines carrying title, company, location, badges, score, posted date, exclusion chips, actions | ✓ |
| Trimmed mobile row | Show fewer fields on narrow screens | |
| Leave it to the UI-SPEC | Defer the decision to `/gsd-ui-phase` | |

**User's choice:** Restack all row data; nothing hidden, nothing needing a second tap.

**Checkpoint:** offered "Next area" vs "More questions" — user chose **Next area**.

---

## Retention / pruning of history

### Q1 — Which history may be pruned

| Option | Description | Selected |
|--------|-------------|----------|
| Runs history + stage logs | `runs` rows beyond a window; `stage_log_json` is the fat part | ✓ |
| Tailored CV artifacts (rows + files on disk) | D-117's deferred debt, including the `.tex`/`.pdf` files | ✓ |
| Source request log | The raw per-request fetch log | ✓ |
| Listing / application audit events | The audit trail and tracker timeline | ✓ |
| Inactive (stale) listings | Listings past `stale_after_days`, currently only flagged `is_active=false` | ✓ |

**User's choice:** All of them, **plus**: *"Allow the user to choose which one they want to prune and how old do they need to be to qualify"*.
**Notes:** Pruning is per-category and per-age-threshold, user-selected — not one global switch. Audit events were selected here, which triggered the follow-up below.

### Q2 — Audit events vs the append-only trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude audit events from pruning | Keep `application_events` append-only; age-based deletion never touches them | ✓ |
| Prune events only with their parent | Events go only when the listing/application they belong to goes | |
| Age-based, drop the append-only guarantee | Events get an age threshold like everything else | |

**User's choice:** Exclude audit events from pruning.
**Notes:** `application_events` is append-only by DB trigger (D-131) and backs the per-row timeline (D-134). Both survive intact.

### Q3 — Hard guards

| Option | Description | Selected |
|--------|-------------|----------|
| Keep a floor of recent runs regardless of age | The source badge and the Adzuna verdict read the last N runs (`probe_count_trailing_runs=5`, `promotion_window_runs=5`) | ✓ |
| Never prune the `llm_calls` ledger | It backs the per-run (40) and rolling-24h (400) spend ceilings | ✓ |
| Never prune an artifact linked to an application | D-129's applied row points at the specific `ok` artefact sent | ✓ |
| Never prune the newest `ok` artifact per listing | D-117: the listing page shows the most recent one | ✓ |

**User's choice:** All four guards hold, even under an aggressive age threshold.

### Q4 — How the pruning control works

| Option | Description | Selected |
|--------|-------------|----------|
| Manual, dry-run preview + confirm | Pick category + age in the Settings danger-zone, see counts/sizes first, confirm, and an audit line records what went | ✓ |
| Manual + automatic on the nightly run | Same control, plus the nightly run prunes with saved thresholds | |
| Automatic only | Prune every run from saved thresholds, no button | |

**User's choice:** Manual, dry-run preview + confirm.
**Notes:** Nothing is destroyed silently. No automatic pruning on the nightly run.

### Q5 — What pruning a stale listing does

| Option | Description | Selected |
|--------|-------------|----------|
| Hard delete the listing and everything hanging off it | Removes the listing, its scores, its `listing_sources` provenance, its `queue_state` | ✓ |
| Keep the listing + provenance, drop the bulk | Keep the row and upsert keys; delete only description text and score rationale | |
| Don't delete listings at all | Limit pruning to runs, artifacts and the request log | |

**User's choice:** Hard delete.
**Notes:** Accepted consequence: because `listing_sources` carries the `UNIQUE(source, source_listing_id)` upsert key, a re-post returns as a brand-new listing with a new `first_seen_at`, and prior dismissals / seen-before memory are gone.

### Q6 — Where the thresholds live

| Option | Description | Selected |
|--------|-------------|----------|
| Same settings row as the schedule | One singleton config row holding schedule + per-category retention thresholds as JSON | ✓ |
| Separate table | A dedicated retention table | |
| `app/config.py` | Env vars, restart to change | |

**User's choice:** Same settings row as the schedule — one table, one migration.
**Notes:** `app/config.py` contradicted the runtime-editable decision from Area 1; the `ApplyConfig` precedent (it already holds the user's screening questions) settles it.

**Checkpoint:** offered "More questions" vs "Next" — user chose **More questions**, which produced Q5 and Q6 above. Then, on the closing check, the user chose **I'm ready for context**.

---

## the agent's Discretion

- Exact table name and JSON key names for the new settings row; the exact route path for the prune control and its preview.
- Precise copy for status/warning text (badge vocabulary, the "missed" notice, the preview wording).
- Whether `/health` reuses the `_health_strip` renderer or gets its own partial — provided the two cannot disagree about `auth_configured` (D-138's constraint).
- Breakpoint values and the exact CSS mechanism, within the no-JS / accessible-scroll constraint.
- Whether the "floor of recent runs" guard is expressed as a count or a minimum age.

## Deferred Ideas

- Weekday / days-of-week scheduling (user deferred explicitly)
- Multiple users + Authentik login (keep the row shape open; no `user_id` in v1)
- Manual "enable Adzuna" control — SRC-11 v2
- Live in-flight run indicator on `/health`
- Full responsive parity on admin surfaces
- Automatic pruning on the nightly run (rejected in favour of manual + preview + confirm)
- Settings model picker (carried from 07.1, its own phase)
- Residual prompt-injection risk (carried from 07.1, accepted + documented)
- `unwrap_single_key_mapping` WR-02 from `07-REVIEW.md` (resolve if Phase 8 reuses the helper)
