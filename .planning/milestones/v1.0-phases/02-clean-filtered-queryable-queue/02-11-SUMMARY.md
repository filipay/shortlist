---
phase: 02-clean-filtered-queryable-queue
plan: "11"
subsystem: ui
tags: [queue, posting-links, dismiss, settings, data-reset, sqlite, transactional-ddl, htmx, jinja2]

# Dependency graph
requires:
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-07's thin `queue()` handler, the `#run-control` block and the `#run-status-slot`"
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-09's toggle-driven queue filtering — the hidden gate and the visible ceiling the dismiss has to respect"
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-10's run history and the derived last-run strip the queue renders"
provides:
  - "`QueueRow.url` and `QueueRow.source_links` — the posting URL and one entry per `listing_sources` row, carried by a single batched read in `queue_repo`"
  - "the queue row's links: title → posting, one link per source, and an `Apply` link to the employer/ATS page only when it genuinely differs"
  - "`Dismiss all queued listings` — a bulk hide that appends one `hide` event per listing through the append-only `append_event` path"
  - "`GET /settings` — the danger zone, per-table row counts, the confirm token and a fifth current-marking nav link"
  - "`POST /settings/reset` — snapshot then reset, behind four guards, refusing in four distinct ways"
  - "`app/db/session.build_engine` — explicit `BEGIN` transaction control, making DDL transactional"
affects: []

# Actuals (#2632) — measured, not narrated.
actuals:
  tokens: 43594        # chars/4 of `git diff 228fcad..d436425` => 174374/4
  tasks: 8
  commits: 15          # MEASURED: git rev-list --count 228fcad..d436425

plan_head_before: 228fcad
commits:
  - 9e9eb46   # feat(queue): carry the posting URL and per-source links on every row
  - 484d89b   # fix(queue): compare board and employer URLs like-for-like
  - 482e416   # feat(ui): link each queue row to the posting and the employer page
  - 5dde21a   # fix(queue): only render http(s) URLs as links
  - 7590ddb   # feat(queue): dismiss the whole queue with one action
  - f497bc1   # fix(queue): make dismiss respect the hidden gate and the ceiling
  - e165274   # feat(settings): add the settings page and its danger zone
  - e017e00   # feat(settings): snapshot then reset the queue data behind explicit guards
  - b8061bb   # test(settings): cover the snapshot-failure branch and harden the reset coverage guard
  - 182605a   # docs: record the queue links, dismiss and guarded reset
  - ec19ac0   # fix(queue): dismiss the whole default queue, dropping every toggle
  - 80a9b33   # docs: correct the change record for the dismiss scope fix
  - c16023a   # fix(settings): suspend the append-only trigger inside the reset transaction
  - 6720f1c   # chore(settings): log reset failures with a traceback
  - d436425   # docs: record the engine transaction change as a deliberate decision

tech-stack:
  added: []            # no new dependency — HTMX, Jinja, SQLAlchemy and the stdlib `sqlite3` module were already in use
  patterns:
    - "Link, don't decorate: a row's afforced navigation is the posting URL, and the employer/ATS link is rendered only when that URL genuinely differs — one template stays correct for both boards with no source-specific branching"
    - "Escaping decided in Python, not in the template: `_http_url` gates every `href`, so only `http(s)` ever reaches the attribute"
    - "Read the page back after the write: the dismiss re-renders from the database rather than trusting the in-memory delta, so the returned fragment already shows the empty queue"
    - "Guards before snapshots before deletes: the confirm token, the in-flight run and the tracked-work checks all refuse before anything touches the file, and the snapshot is taken before the first delete"
    - "The snapshot's destination is derived from the database actually being mutated (`session.get_bind().url.database`), so it can never disagree with the file it protects"
    - "Suspend and re-arm inside the transaction: the append-only trigger is dropped from its own `sqlite_master` DDL and restored before the commit, so a failed delete phase rolls the deletes and the suspension back together"
    - "Make the invariant enforceable before relying on it: transactional DDL was a precondition for that suspension, so `build_engine` gained explicit `BEGIN` control and the change was recorded as a decision in its own right"

key-files:
  created:
    - app/web/templates/html/settings.html
    - app/api/settings.py
    - tests/db/test_queue_row_links.py
    - tests/api/test_queue_links.py
    - tests/api/test_queue_dismiss.py
    - tests/api/test_settings_page.py
    - tests/api/test_settings_reset.py
    - tests/db/test_reset_coverage.py
  modified:
    - app/db/repositories/queue_repo.py
    - app/db/repositories/event_repo.py
    - app/db/session.py
    - app/web/routes.py
    - app/web/templates/html/_listing_row.html
    - app/web/templates/html/queue_list.html
    - app/web/templates/html/base.html
    - app/main.py
    - assets/tailwind/input.css
    - static/vendor/app.css
    - tests/pipeline/test_ingest_e2e.py
    - docs/superpowers/specs/2026-09-17-queue-links-dismiss-and-reset-design.md
    - docs/implementation-notes.md

duration: 212min
completed: 2026-09-17
---

# Plan 02-11 — queue posting links, dismiss-all, and the guarded data reset

**Plan 02-11 is the GSD record of the `2026-09-17` SDD cycle.** The cycle itself ran
out of tree under `.superpowers/sdd/2026-09-17-queue-links-dismiss-and-reset/`
(briefs, reports, per-task reviews), with its own spec
(`docs/superpowers/specs/2026-09-17-queue-links-dismiss-and-reset-design.md`) and
its own human plan (`docs/superpowers/plans/2026-09-17-queue-links-dismiss-and-reset.md`).
This summary therefore has an unusual shape: **the plan describes work that had
already shipped** when the plan was written, and the three commits at the top of
the range exist because the operator ran the feature against the real database
and found a defect the test suite could not see.

## What shipped

### 1. Queue rows carry and render their links

`queue_repo` gained `QueueRow.url` plus `QueueRow.source_links` (one entry per
`listing_sources` row, so a merged listing shows every source rather than hiding
half its provenance), populated by **one batched read** over the page's listing
ids — not a per-row query. `_listing_row.html` renders the title as an anchor to
the posting in a new tab with `rel="noopener noreferrer"`, and the source cell
lists each source.

The **Apply** link to the employer/ATS page appears only when that URL genuinely
differs from the board URL. That single inequality guard is what makes one
template correct for both boards (Indeed mostly differs; LinkedIn does not).
`_http_url` gates every `href`, so a `javascript:` or `data:` URL can never reach
the attribute, and a row with no usable URL falls back to plain unlinked text.

Two commits in this arm are corrections rather than features: `484d89b` made the
board/employer comparison like-for-like (a trailing-slash difference was enough
to render a redundant Apply link), and `5dde21a` restricted rendering to `http(s)`.

### 2. `Dismiss all queued listings`

One action hides every listing the **default** queue shows — empty search box, no
toggles selected — which is the queue's own definition of "everything", not a
hardcoded status filter. It appends one `hide` event per listing through the
existing append-only `append_event` path, tagged
`context={"surface": "queue_dismiss"}`, and touches nothing already hidden,
absorbed as a merge twin, or excluded by the latest run. After the write it reads
the page back, so the returned fragment already shows the empty queue, and the
dismissal survives a reload. `Unhide` restores exactly one row.

`f497bc1` made dismiss respect the hidden gate and the ceiling; `ec19ac0` (found
by the final whole-branch review) made it drop **every** toggle rather than
honouring a partially-selected filter row.

### 3. The settings page and the guarded reset

`GET /settings` renders the danger zone, the per-table row counts, the confirm
token and a fifth `Settings` nav link that marks itself current.

`POST /settings/reset` refuses in four distinct, tested ways, each leaving the
corpus untouched:

| Condition | Status |
|---|---|
| Wrong confirmation text | `400` |
| A pipeline run is currently in flight | `409` |
| Tracked work exists (any row in `applications` or `cv_artifacts`) | `409` |
| The snapshot could not be written | `500` |
| The delete phase failed for any reason | `500` |

On the happy path it snapshots the live database with `VACUUM INTO` to
`<db_dir>/reset-backups/jobsearch-<UTC timestamp>Z.db` **before the first delete**,
refusing to overwrite an existing file, then empties `RESET_DELETE_ORDER`
child-first in one transaction, keeps `searches` / `filter_rules` / `sources`, and
reports the snapshot filename. Recovery is deliberately **not** a button: restore
is stop-the-container, copy the file, start the container.

### 4. The post-completion fix arc

The operator rebuilt the container and ran the feature for real. The reset failed
with a bare `500`. Three commits closed it:

- **`c16023a` — suspend the append-only trigger inside the reset transaction.**
  `listing_events` is append-only (a `BEFORE DELETE` trigger) *and* `NO ACTION`
  foreign-keyed, while `RESET_DELETE_ORDER` lists it first. The delete was refused
  and the abort escaped the route's narrow `except` as an unhandled 500. The fix
  drops the trigger from its `sqlite_master` DDL inside the same transaction and
  re-arms it before the commit, and broadens the handler to `except Exception`
  with a `rollback()` **before** the re-render so the honest "nothing was deleted"
  page is rendered from a rolled-back session. The coverage corpus was extended
  into every table in the delete order.
- **`6720f1c` — log reset failures with a traceback**, so the next real-world
  failure arrives with evidence instead of a status code.
- **`d436425` — record the engine transaction change as a deliberate decision.**

**The engine change is not an incidental part of that fix.** `build_engine`
(`app/db/session.py`) no longer lets the driver manage transactions: a second
`connect` listener sets `dbapi_connection.isolation_level = None` and a `begin`
listener issues an explicit `BEGIN`, both attached to `engine.sync_engine`.
pysqlite's default mode does not open a transaction for DDL and implicitly
commits before it — SQLAlchemy's own docs call this "incorrect support for
transactional DDL" — so the trigger suspension above was **only safe once DDL
became transactional**. Without it, a failed reset could have left the append-only
invariant permanently disabled. Its blast radius was checked and recorded (pragmas
unaffected, `expire_on_commit=False` orthogonal, every `begin_nested()` site now
emits `BEGIN` before the SAVEPOINT, Alembic builds its own engine, the APScheduler
job store does not exist until Phase 8), together with the one thing to watch:
non-legacy mode is more susceptible to locked-database errors, which is a
non-issue at one worker / one writer / WAL / 5000 ms busy timeout, and must be
revisited if the app ever gains a second writer.

## Verification

Measured at `d436425`:

| Check | Command | Result |
|---|---|---|
| Commits in range are ancestors of HEAD | `git merge-base --is-ancestor <sha> HEAD` ×15 + `ec19ac0` | all OK |
| The six feature lanes | `pytest -q` over the six cycle test files | **52 passed** (11/7/12/8/**9**/5 — the reset module grew 7→9) |
| The guard lanes | `pytest -q` over `test_auth_seam`, `test_stylesheet_coverage`, `test_no_cdn`, `test_ingest_e2e` | **21 passed** |
| Whole suite | `.venv/bin/python -m pytest -q` | **712 passed, 2 deselected** (108 s) |
| Lint | `.venv/bin/python -m ruff check app tests` | `All checks passed!` |
| Live | the operator rebuilt the container and ran the feature end to end | **reset succeeds**; queue empties and stays empty |

The human-check in the plan originally asserted the *pre-fix* behaviour (the reset
failing with a 500). That step now states the reset **succeeds**, while the
contract text is retained verbatim so canonical phase verification can re-run it
rather than trust the narrative.

## Requirement traceability — the gap, and why it is not being closed

`requirements:` on this plan is `[QUEUE-08]` (search and hide as recorded
events), which the dismiss arm genuinely advances. **The posting-links arm, the
guarded-reset arm, and the post-completion fix arc are shipped but untraced** —
no `REQUIREMENTS.md` ID describes them.

Adding those IDs was considered and **rejected**. A requirement written after, and
derived from, the implementation traces nothing; retro-fitting must-haves onto a
phase whose `02-VERIFICATION.md` already reads `status: passed` at 54/54 would
risk making a passed verification inconsistent or newly unmet. The honest
consequence is this paragraph: phase 2's coverage report will not list this
feature by requirement ID. If real requirement IDs are wanted, that is a
separate, intent-level exercise — not a side effect of closing a plan.

## Flagged assumptions and carried-forward discrepancies

1. **Reconciled here:** `docs/implementation-notes.md`'s `Status` still said
   `ec19ac0` / `not yet applied live` / `710 passed`, and its `Commits` table
   stopped at `ec19ac0`, even though `c16023a`, `6720f1c` and `d436425` had
   already extended the section body. The header now reads `d436425`, records the
   live confirmation, reports `712 passed`, and the table carries both post-cycle
   rows. The body was already current and was not rewritten.
2. **Still open, pre-existing:** `tests/api/test_queue_links.py`'s docstring labels
   its cases `(QUEUE-06)`, which is a different requirement.
3. **Still open, pre-existing:** the SDD ledger's own close-out line says "11
   commits"; the range is 15 once the fix arc is included.
4. **Documented, not a defect:** a dismissal that matches more than the ceiling
   (10,000 visible listings) refuses with a `400` that htmx does not swap, so the
   user sees no feedback. Unreachable at any realistic queue size and strictly
   safer than a partial dismissal; the proper fix is an app-wide htmx error
   handler.
5. **Documented, not a defect:** the `VACUUM INTO` destination is interpolated as
   an SQL literal rather than bound. Safe today because the path is server-derived
   with no request-controlled component, but it relies on that staying true.

## Deviations

- **Task typing.** No task is typed `tracer`. The cycle's thinnest vertical slice
  is commits `9e9eb46`→`5dde21a` **as a pair** — the repository lane and the render
  lane were deliberately split because each was reviewed separately. Task 1 does
  not touch every layer, so claiming it did would have been the dishonest option.
- **The fix arc is appended, not interleaved.** Tasks 7 and 8 sit after tasks 1–6
  so the original cycle stays legible as what shipped first and the fix arc reads
  as what it was: a correction after the operator ran the feature for real.
- **`c16023a` is one atomic commit carrying both surfaces** (the reset fix and the
  engine change). The task split is framing for review, not a claim of two commits.

*Completed: 2026-09-17*

## Self-Check: PASSED

- All 21 `files_modified` paths verified tracked with `git ls-files`.
- All 15 plan commits verified in `git log` and ancestor-checked against HEAD with
  `git merge-base --is-ancestor <sha> HEAD` (plus `ec19ac0`).
- Full suite green: `712 passed, 2 deselected`; `ruff check app tests` clean.
- `verify.plan-structure` on `02-11-PLAN.md`: `valid: true`, no errors, no warnings, 8 tasks.
- `frontmatter.validate` on `02-11-PLAN.md` and `02-11-SUMMARY.md`: `valid: true`.
- `docs/implementation-notes.md` header reconciled (Status → `d436425`, live
  confirmation recorded, suite count corrected, post-cycle commits added to the table);
  its section body was already current and was not rewritten.
- No missing items.
