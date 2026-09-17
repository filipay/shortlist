# Implementation notes

The git-commit-equivalent record of every applied change. One dated section per
cycle: what shipped, the commits that carry it, and what was deliberately left out.

---

## 2026-09-17 — Queue posting links, dismiss-all, and the guarded data reset

**Spec:** `docs/superpowers/specs/2026-09-17-queue-links-dismiss-and-reset-design.md`
**Plan:** `docs/superpowers/plans/2026-09-17-queue-links-dismiss-and-reset.md`

### Status

Committed on `master` at `ec19ac0`. **Not yet applied live** — the container has
not been rebuilt, so nothing here has been exercised against the operator's real
database. Suite: `710 passed, 2 deselected`; `ruff check app tests` clean.

### Commits

| Task | Commits |
|---|---|
| 1 — carry the posting URL and per-source links on every row | `9e9eb46`, `484d89b` |
| 2 — link each queue row to the posting and the employer page | `482e416`, `5dde21a` |
| 3 — dismiss the whole queue with one action | `7590ddb`, `f497bc1` |
| 4 — the settings page and its danger zone | `e165274` |
| 5 — snapshot then reset behind explicit guards | `e017e00`, `b8061bb` |
| 3 — dismiss scope correction (found by the final review) | `ec19ac0` |

### 1. Queue rows link to the posting

Each row's title is an anchor to the posting page, and the source cell lists one
link per source (a merged row shows every source rather than hiding half its
provenance) plus an **Apply** link to the employer/ATS page.

The Apply link is rendered **only when the employer URL genuinely differs** from
the board URL — that single inequality guard is what makes one template correct
for both boards with no source-specific branching (Indeed mostly differs; LinkedIn
does not).

Both URLs are derived from the existing single batched `listing_sources` read, so
no query was added and no N+1 was introduced. `SourceLink(source, url,
employer_url)` is frozen; `QueueRow` gained `url` and `source_links`.

Only `http`/`https` URLs are ever rendered as links (`_http_url` in
`queue_repo.py`): scraped `source_url` is stored raw and `canonical_url` is not a
scheme gate, so a non-web scheme would otherwise reach an `href`. A gated-to-empty
URL renders the title/source as plain text.

### 2. Dismiss the whole queue

`POST /queue/dismiss` hides **every listing in the default queue**, not just the
rendered page. The row count in the button label was dropped deliberately: the
label's count described the rendered predicate, while the action drops the
free-text search and **all UI toggles** (`excluded`, `hidden`, `saved`, `scope`),
so a number there would have disagreed with what actually happened. Dismiss acts on
the queue as it appears with an empty search box and no toggles selected.

The inherent gates are still respected — an already-hidden listing must never gain
a second `hide` event (it would have polluted the append-only event log), an
absorbed merge twin is never dismissed, and a listing excluded by the latest run is
not in the queue. Only the search text and the toggles are dropped; those gates are
built into `read_queue` rather than carried as toggles.

`DISMISS_LIMIT` is a hard ceiling, not a page size. Every matching page is read
until the total is covered; if the total exceeds the ceiling the route refuses and
commits nothing rather than partially dismissing. Dismissal writes one `hide`
event per listing through `append_event` (reusing the existing event type) with
`context={"surface": "queue_dismiss"}`, and the route owns the single commit.

### 3. Settings page and the guarded reset

`GET /settings` shows the per-table row counts and a danger zone. `POST
/settings/reset` is **the only irreversible action in the app**.

**Delete order** (children first, so `foreign_keys=ON` holds at every step):

```
scores, listing_exclusions, listing_events, listing_dupes, listing_sources,
listings, llm_calls, source_request_log, runs, queue_state, companies
```

`companies` is deleted because it is derived from listings; leaving it behind only
creates orphans.

`listing_events` is **append-only**: migration 0001 installs a `BEFORE DELETE`
trigger that `RAISE(ABORT, 'listing_events is append-only')`, and its `listing_id`
FK to `listings` is `NO ACTION`. Those rows can neither be deleted (the trigger
aborts) nor left behind while `listings` is deleted (the FK refuses). The reset is
the one operation allowed to empty that log, so the delete phase **suspends the
trigger inside its transaction**: it reads the trigger's DDL from `sqlite_master`
(never a hardcoded copy), drops it, deletes every table in `RESET_DELETE_ORDER`,
and re-creates the trigger from that DDL **before the commit**. The engine makes
DDL transactional (`build_engine` disables the driver's transaction control and
issues an explicit `BEGIN`), so a failure anywhere rolls the `DROP TRIGGER` back
with the deletes — the append-only invariant is never left disabled. A database
without the trigger still resets (the DROP is `IF EXISTS`).

**Preserved:** `searches`, `filter_rules` and `sources` — the user's own
configuration and the board lookup the next run's upsert needs. (`cv_versions` is
also never deleted, being absent from the delete order; it is not listed on the
page.)

**Refusal conditions** — every one of them commits nothing:

| Condition | Status |
|---|---|
| Wrong confirmation text | `400` |
| A pipeline run is currently in flight | `409` |
| Tracked work exists (any row in `applications` or `cv_artifacts`) | `409` |
| The snapshot could not be written | `500` |
| The delete phase failed for any reason | `500` |

The last row is why the append-only trigger work exists: the delete phase is wrapped,
so a failure rolls the transaction back (trigger included) and re-renders the honest
"nothing was deleted" page instead of escaping as a bare `500`.

The confirmation text is `DELETE`, case-sensitive: the point is a deliberate act,
not a habitual click. **It is a fat-finger and prefetch affordance, not a security
control** — it is rendered into the page in plain text. The real mitigation is the
snapshot, which is taken *before* any delete. Because v1 has no authentication
there is no ambient credential for a cross-site request to abuse, so the route is
not CSRF-exploitable today; it becomes one the moment session authentication
lands, and will need a CSRF token at that point.

**Snapshot:** written with the stdlib `sqlite3` module via `VACUUM INTO`, to

```
<db_dir>/reset-backups/jobsearch-<UTC timestamp>Z.db
```

It refuses to overwrite an existing file. The destination is derived from the
database actually being mutated (`session.get_bind().url.database`) rather than
from configuration, so it can never disagree with the file it is protecting.

### Recovery

Recovery is deliberately **not** a button. To restore a snapshot: stop the
container, replace the database file with the snapshot, start the container. A
restore button would be a second irreversible action guarded by the same
page-visible token, and the file copy is easier to do correctly by hand.

### Known gaps

- A dismissal matching more than the ceiling (10,000 visible listings) refuses
  with a `400` that htmx does not swap, so the user sees no feedback. Unreachable
  at any realistic queue size, and strictly safer than partially dismissing; the
  proper fix is an app-wide htmx error handler.
- The `VACUUM INTO` destination is interpolated as an SQL literal rather than
  bound. Safe today because the path is server-derived with no request-controlled
  component, but it relies on that staying true.
- Two cosmetic test-strength items: the settings page's deleted/kept assertion is
  built from the same constants the template renders (so it cannot catch a wrong
  constant value), and one danger-button hover declaration is redundant.
