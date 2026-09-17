# Queue posting links, Dismiss, and the guarded data reset

**Date:** 2026-09-17
**Status:** approved (design); ready for plan
**Scope:** one small cycle — three surfaces on the queue/corpus, no schema migration

## Problem

Two gaps surfaced during Phase-2 real-corpus use.

**1. The queue cannot reach the job.** A listing row shows title, company,
location, sources, posted date and badges, but nothing links out to the actual
posting. Verified: `QueueRow` (`app/db/repositories/queue_repo.py:163`) has no URL
field at all, `_listing_row.html` contains no external anchor, no template in the
app contains a single `href="http…"`, and there is no `GET /listings/{id}` route.
The data exists and is unused: `listings.canonical_url` (`models.py:117`) and
`listing_sources.source_url` / `canonical_source_url` (`models.py:169-170`).

This is an oversight, not a deferral. Phase 7 is *Assisted Apply + Tracker* —
prefilling an application for the user to submit — and reading the posting on the
board is a prerequisite for that, not a later concern.

**2. There is no way to clear the queue.** Hiding is per-listing only
(`listing_events` + the Unhide button). There is no bulk action and no
configuration surface: the nav is four hardcoded links (`base.html:28-31`) and
`/settings` does not exist.

## Decisions (approved)

| Fork | Decision | Why |
|---|---|---|
| Where the local keyword operators act | Board translation **plus** a local backstop, matching **title only** | Parked — see Non-goals. Recorded because it settled the `fields` default. |
| What "clear the queue" means | **Both**: a Dismiss on the queue, plus a destructive reset in Settings | Everyday action convenient; dangerous action tucked away |
| Reset scope | **Data only** — saved searches and their rules survive | Keeps tuned configuration; the next run rebuilds a clean corpus |
| Reset guard | **Type-to-confirm + automatic pre-reset snapshot** | The project's own best-practices list flags "existing state changed with no recovery path" |

## Design

### 1. Queue row → posting

- `QueueRow` gains two fields: `url: str | None` (from `listings.canonical_url`)
  and `source_links: tuple[SourceLink, ...]`.
- New frozen dataclass `SourceLink` in `queue_repo` with three fields:
  `source: str` (`"indeed"` / `"linkedin"`), `url: str` (the board's own posting
  page, from `listing_sources.source_url`), and `employer_url: str | None`
  (`listing_sources.canonical_source_url`, populated only when it differs from `url`).
- Both are populated by extending the batch read that row enrichment already
  performs for source names — **one query for the page, never N+1**.
- `_listing_row.html`: the title becomes
  `<a href="{{ row.url }}" target="_blank" rel="noopener noreferrer">{{ row.title }}</a>`.
  When `row.url` is falsy the title renders as plain text, exactly as today.
- **Which URL is which — verified against the live corpus.** `listings.canonical_url`
  is the board's posting page (`http://ie.indeed.com/job/<slug>-<hash>`; 0 null or
  empty across all 108 listings). `listing_sources.source_url` is the board's
  canonical job URL (`https://ie.indeed.com/viewjob?jk=<id>`,
  `https://www.linkedin.com/jobs/view/<id>`; 0 null or empty across all 283 rows).
  `listing_sources.canonical_source_url` is the **employer / ATS** page, and the two
  differ in exactly the way that matters: **Indeed 155/155 differ**
  (`jobs.ebayinc.com`, `careers.cognizant.com`, `arthurcox.pinpointhq.com`, or a
  `click.appcast.io` redirect) while **LinkedIn 0/128 differ** (both columns hold the
  same `/jobs/view/<id>` URL).
- So the Sources cell renders, per `SourceLink`: the board link always, plus a second
  `Apply` link to `employer_url` when present. That one guard produces the right
  result with no source-specific branching — a LinkedIn row shows one link, an Indeed
  row shows the board page *and* the employer's own posting, which is the page the
  user was actually asking for.
- A merged listing carries one `SourceLink` per `listing_sources` row, so a merge
  never hides half its provenance behind a single URL.

No new route, no migration.

### 2. Dismiss queue

- `event_repo` gains
  `async def hide_listings(session, *, listing_ids: Sequence[int], occurred_at: datetime) -> int`.
  It appends one `hide` event per listing — append-only, like every other event,
  so the existing `listing_events_no_update` / `no_delete` triggers stay satisfied.
- New `POST /queue/dismiss` in `app/web/routes.py`, behind
  `Depends(current_user)`, mirroring `queue_mark_seen` (`routes.py:240`):
  read the queued listing ids, append the events, commit, then re-read the page
  **after** the write so the returned `#queue-list` fragment already shows the
  empty queue.
- The ids come from **the same `read_queue` predicate the row list uses** — the
  hidden / saved / absorbed-twin / scope / latest-run-exclusion gates all still
  apply — with only the free-text search and the UI toggles dropped. Precisely:
  dismiss acts on what the user would see with an empty search box and no toggles
  selected. That is what makes "Dismiss all N" honest. It is explicitly *not*
  "every row in `listings`": already-hidden listings must not collect a second
  event, and an absorbed twin must never be dismissed.
- Scope: it dismisses **the whole queue**, ignoring any active search text or
  filter, and the label says so — `Dismiss all N queued listings`. Dismissing only
  the filtered page would be ambiguous whenever the filter hides most of the queue.
- The event type is the existing `hide`, deliberately, rather than a new
  `dismiss` event: the hidden predicate and the per-listing Unhide button already
  work, and a 7th event type would require a migration to widen the
  `listing_events.event_type` CHECK. Accepted cost: a bulk dismissal is
  indistinguishable in the audit trail from hiding each listing by hand.
- Empty queue → no-op, returns the empty state.
- UI: a second button beside `Mark all as seen` in `queue_list.html`, with
  `hx-confirm` because it is bulk.

### 3. `/settings` and the guarded reset

**Surface.** New router `app/api/settings.py` (matching `api/runs.py` /
`api/searches.py`), registered in `app/main.py`; a fifth nav link in
`base.html`; new template `app/web/templates/html/settings.html` extending
`base.html`.

**`GET /settings`** — a Danger zone card: plain wording of exactly what is
deleted and what is kept, the type-to-confirm field, and the destructive button.

**`POST /settings/reset`**, strictly in this order, aborting at the first failure:

1. **Confirm.** `confirm.strip() == "DELETE"` (case-sensitive). Otherwise **400**
   and re-render with an error. Nothing is touched.
2. **Refuse while a run is in flight.** `runs.status NOT IN ('done','partial','failed')`
   → **409** "a run is in progress". This is real: `start_run` writes a `running`
   row *before* enqueuing (`app/api/runs.py:92-104`), and
   `TERMINAL_STATUSES = {'done','partial','failed'}` (`app/pipeline/run.py:59`).
   Accepted consequence: a run that died without being marked terminal leaves an
   abandoned `running` row that blocks every future reset. That is the fail-safe
   direction — refusing is recoverable, deleting under a live run is not — and the
   409 message names the offending run id so the operator can resolve it.
   Auto-terminating stale runs is a follow-up, not part of this cycle.
3. **Refuse if non-corpus listing data exists.** If `applications` or
   `cv_artifacts` hold any row → **409** with an explicit message. They FK to
   `listings` (`models.py:376`, `models.py:411`), so deleting listings under them
   would either hard-fail or destroy the user's tracked work and generated CVs.
   Both tables are empty today; the check exists so a later phase fails loudly
   instead of corrupting or refusing cryptically.
4. **Snapshot before deleting anything.** `VACUUM INTO
   '<db_dir>/reset-backups/jobsearch-<YYYYMMDDTHHMMSSZ>.db'` (timestamp in **UTC**;
   the directory is created if absent), executed on a
   dedicated **sync** `sqlite3` connection inside `asyncio.to_thread`.
   `VACUUM INTO` cannot run inside a transaction — it is a single statement that
   writes a consistent copy, WAL-safe, with no new dependency. The directory is
   derived from the configured sync URL's path (`app/config.py:28`), so it lands
   on the mounted volume in Docker and in `data/` locally. If the target exists,
   or the snapshot fails for any reason, **abort and delete nothing** — a snapshot
   taken after the deletes would be worthless.
5. **Delete, in this exact order** (children first; `foreign_keys=ON` is enforced
   at runtime by `app/db/session.py`, so order is not cosmetic):
   `scores` → `listing_exclusions` → `listing_events` → `listing_dupes` →
   `listing_sources` → `listings` → `llm_calls` → `source_request_log` → `runs` →
   `queue_state` → `companies`.
   - `listing_fts` needs no explicit handling: the `listings_ad` trigger maintains it.
   - `companies` is **added** to the approved list because it is derived from
     listings; leaving it behind leaves orphan rows for no benefit.
   - **`sources` is preserved.** It is a lookup table (`linkedin`, `indeed`) that
     the next run's upsert requires; only the `listing_sources` join rows go.
   - `searches` and `filter_rules` are untouched.
6. **Report.** Re-render `/settings` with a success banner naming the snapshot
   file written in step 4.

**Deliberately not built:**
- **No restore button.** A restore is a second destructive path with its own
  failure modes. Recovery is a documented manual operator step (stop the
  container, replace `jobsearch.db` with the snapshot). A backup nobody can
  restore is theatre, so the step gets written down rather than automated.
- **No snapshot pruning.** Resets will be rare and the directory is ignored by
  git; pruning would add delete logic to the dangerous path. Follow-up if it
  ever matters.

## Interfaces

| Kind | Exact |
|---|---|
| Dataclass | `SourceLink(source: str, url: str, employer_url: str \| None)` — `frozen=True`, in `queue_repo` |
| Fields | `QueueRow.url: str \| None`, `QueueRow.source_links: tuple[SourceLink, ...]` |
| Repository | `event_repo.hide_listings(session, *, listing_ids: Sequence[int], occurred_at: datetime) -> int` |
| Routes | `GET /settings`, `POST /settings/reset` (new `app/api/settings.py`), `POST /queue/dismiss` (in `app/web/routes.py`) |
| Tokens | confirm word `DELETE`; snapshot dir `<db_dir>/reset-backups/` |
| Tables deleted | `scores`, `listing_exclusions`, `listing_events`, `listing_dupes`, `listing_sources`, `listings`, `llm_calls`, `source_request_log`, `runs`, `queue_state`, `companies` |
| Tables never touched | `sources`, `searches`, `filter_rules`, `cv_versions` — not deleted by any path |
| Tables that block instead of being deleted | `applications`, `cv_artifacts` (and `application_events` transitively) — never deleted; if non-empty the reset returns 409 rather than destroying tracked work |

## Failure modes

| Failure | Behaviour |
|---|---|
| Wrong confirm word | 400, re-render settings with an error, nothing changed |
| Run in flight | 409, nothing changed |
| `applications` / `cv_artifacts` non-empty | 409, nothing changed |
| Snapshot cannot be written | 500, **nothing deleted** — the abort happens before the first DELETE |
| Delete fails mid-transaction | Rolled back by the transaction; the snapshot still exists |
| Listing has no `canonical_url` | Title renders as plain text, no anchor |
| A source row's `canonical_source_url` equals its `source_url` | Only the board link is rendered (the LinkedIn case, 128/128 today) |
| Abandoned `running` run row | 409 naming the run id; the reset stays blocked until resolved |

## Testing

| Lane | Pins |
|---|---|
| `tests/api/test_queue_links.py` | Title anchor carries the canonical URL with `target="_blank" rel="noopener noreferrer"`; an Indeed-shaped row (employer URL differs) renders the board link **and** the employer link, a LinkedIn-shaped row (identical URLs) renders only one; a merged listing renders one link pair per source; a listing without a URL renders no anchor; the page's source reads happen in a bounded number of statements (no N+1) |
| `tests/api/test_queue_dismiss.py` | Dismisses **every** queued listing even with a page smaller than the queue; the returned fragment shows the empty state; dismissed listings stay hidden on a re-read; Unhide restores one; an empty queue is a no-op; an already-hidden listing gains no second event and an absorbed twin is never dismissed |
| `tests/api/test_settings_reset.py` | Wrong confirm → 400 with counts unchanged; correct confirm → every deleted table empty and `searches` / `filter_rules` / `sources` intact; the snapshot exists, opens, and holds the **pre-reset** row counts; 409 while a `running` run exists; 409 when `applications` is non-empty; works when only terminal runs exist |
| `tests/db/test_models.py` (extend) | Enumerate every table with an FK to `listings` from the metadata and assert each is either in the reset's delete list or in an explicit preserved list — so a future table forces a decision instead of failing cryptically |
| `tests/test_stylesheet_coverage.py` | Existing guard: every new class needs a rule or an exemption, and `static/vendor/app.css` must be rebuilt |
| `tests/test_auth_seam.py` | Existing guard: both new routes must resolve `current_user` in their dependency tree |

Run with `.venv/bin/python -m pytest -q`; lint with `.venv/bin/python -m ruff check app tests`.

## Non-goals

- **Search operators in keywords.** Parked by the user, who is content with
  current results. Recorded so it is not re-litigated: the *exclude* half already
  exists as the `exclude_keyword` rule kind (`filter.py:288`, which already
  accepts a `fields` allow-list defaulting to `title` + `description`), so the
  only genuinely missing piece was a must-include counterpart.
- **Keyword-driven or operator-driven board query rewriting.**
- **Authentication or CSRF work.** v1 has no auth, and CSRF is an accepted risk;
  type-to-confirm is this route's specific mitigation, not a general fix.
- **A listing detail page.** The row links out; an in-app detail view is not needed
  to reach the posting.

## Follow-ups (not this cycle)

- Snapshot pruning / retention if resets become frequent.
- `searches.is_default` remains dead after the union-fetch decision.
- `02-SECURITY.md` W-01: assert `rapidfuzz` is present in the built image.
- The operator's outstanding Phase-2 steps: rebuild, revert the six wrong merges,
  switch the location rule to `county` mode, add a `seniority` rule, then
  `/gsd-verify-work 2`.
