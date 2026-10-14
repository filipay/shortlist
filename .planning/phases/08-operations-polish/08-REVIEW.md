---
phase: 08-operations-polish
reviewed: 2026-10-14T21:00:01Z
depth: standard
files_reviewed: 52
files_reviewed_list:
  - Dockerfile
  - alembic/versions/0008_operations_config.py
  - app/api/health.py
  - app/api/health_page.py
  - app/api/settings.py
  - app/config.py
  - app/db/models.py
  - app/db/repositories/operations_config_repo.py
  - app/db/repositories/retention_repo.py
  - app/db/repositories/run_repo.py
  - app/db/repositories/source_repo.py
  - app/jobs/__init__.py
  - app/jobs/scheduler.py
  - app/main.py
  - app/web/templates/html/_application_history.html
  - app/web/templates/html/_application_row.html
  - app/web/templates/html/_health_strip.html
  - app/web/templates/html/_listing_row.html
  - app/web/templates/html/_screening_drafts.html
  - app/web/templates/html/applications_list.html
  - app/web/templates/html/base.html
  - app/web/templates/html/health.html
  - app/web/templates/html/listing_detail.html
  - app/web/templates/html/merges.html
  - app/web/templates/html/queue_list.html
  - app/web/templates/html/runs.html
  - app/web/templates/html/settings.html
  - assets/tailwind/input.css
  - compose.yml
  - entrypoint.sh
  - pyproject.toml
  - requirements.txt
  - static/vendor/app.css
  - tests/api/test_apply_package.py
  - tests/api/test_health.py
  - tests/api/test_health_page.py
  - tests/api/test_queue_links.py
  - tests/api/test_schedule_settings.py
  - tests/api/test_settings_page.py
  - tests/api/test_settings_prune.py
  - tests/api/test_settings_reset.py
  - tests/db/test_migration_contract.py
  - tests/db/test_no_pii_columns.py
  - tests/db/test_orm_drift.py
  - tests/db/test_retention_repo.py
  - tests/db/test_skeleton_boot.py
  - tests/jobs/__init__.py
  - tests/jobs/test_scheduler.py
  - tests/pipeline/test_ingest_e2e.py
  - tests/test_auth_seam.py
  - tests/test_config.py
  - tests/test_dependency_pins.py
findings:
  critical: 1
  warning: 3
  info: 5
  total: 9
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-10-14T21:00:01Z
**Depth:** standard
**Files Reviewed:** 54
**Status:** issues_found

## Summary

Phase 08 adds five new surfaces: the schedule (migration `0008` + `operations_config`
singleton + APScheduler), the `/status` page over the shared `dependency_report`
builder, the per-category retention prune over `retention_repo`, the responsive UI
contract, and the `apscheduler` pin. I read every listed file plus the call chains they
reach (`app/db/session.py`, `app/sources/base.py`, `app/probe/survival.py`,
`app/api/searches.py::read_form`, `app/api/deps.py`, migration `0001`'s FTS5/trigger DDL),
and I verified the scheduler mechanics against the installed APScheduler 3.11.3 source.

The engineering quality here is high and the failure modes are mostly designed for:
the prune runs one predicate for preview and delete, guards are expressed as query
conditions rather than post-filters, the reset orders every refusal before the first
DELETE and suspends the append-only trigger inside a transactional DDL window, the
schedule read is total and the write strict, `/status` degrades every dependency to data,
and the FTS5 `listings_ad` trigger keeps the search index consistent when a listing is
hard-deleted. The full suite passes locally (1903 passed, 15 deselected, 2 xfailed).

The one blocking issue is a security defect the phase's own docstring asserts away: every
state-changing settings route (including the corpus reset and the CV overwrite) is an
unauthenticated POST with no origin check, and the "type DELETE to confirm" affordance is a
hard-coded constant, so a cross-site form submission from any page the user's browser
loads can destroy the corpus. Three warnings follow: a retention threshold the form never
pre-fills, a scheduler drift check that cannot see a timezone change, and a stop-signal
parse anchored on `repr()` quoting rather than structure.

## Critical Issues

### CR-01: The destructive settings routes are CSRF-executable, and the docstring claims they are not

**File:** `app/api/settings.py:12-17` (the claim), `app/api/settings.py:822` (`POST /settings/reset`), `app/api/settings.py:1070` (`POST /settings/prune`), `app/api/settings.py:1029` (`POST /settings/prune/preview`), `app/api/settings.py:576` (`POST /settings/cv`), `app/api/settings.py:1198` (`POST /settings/llm-test`); `compose.yml:11`

**Issue.** The module docstring states:

> v1 has no authentication at all (D-21), so there is no ambient credential for a
> cross-site request to abuse and these routes are not CSRF-exploitable today.

That reasoning is inverted. CSRF does not require an ambient credential to *abuse* — it
requires only that a request from another origin is accepted and has a side effect. With
no authentication at all, **every** cross-origin request is fully authorised, so the
absence of a session cookie removes the *benefit* of CSRF while leaving the *capability*
intact. A plain HTML form is a "simple request": no preflight, and the response is never
read.

Concretely, while `docker compose up` is running on the user's machine, any page the user's
browser visits can execute:

```html
<form id="f" method="post" action="http://127.0.0.1:8000/settings/reset">
  <input name="confirm" value="DELETE">
</form><script>f.submit()</script>
```

`RESET_CONFIRM_TOKEN = "DELETE"` (`settings.py:168`) is a source constant, is rendered into
the page in plain text, and is exactly what the route compares
(`settings.py:842`). So the "fat-finger and prefetch affordance" is also a published
constant, not a secret. The result is the full corpus reset, with only the
`reset-backups/` snapshot as recovery. The same one-line form against `/settings/cv` with
`cv_tex=<attacker LaTeX>` **replaces the user's live `cv.yaml`** (and the second call also
overwrites the `.bak` that `_publish_cv` keeps at `settings.py:549`); against
`/settings/prune` with `category=listings` it hard-deletes every stale listing; against
`/settings/llm-test` it spends real tokens on the user's opencode account.

The docstring also enumerates only four routes as "future CSRF holes" and omits
`/settings/cv`, `/settings/llm-test`, `/settings/weights`, `/settings/screening-questions`
and `/settings/cv-layout`, so even the deferred-risk inventory is incomplete.

Scope/limits, stated honestly so this is not dismissed as theoretical: recent Chrome's
Private Network Access may gate a public-origin fetch to `localhost` (Firefox and Safari
have no such gate), and it does not gate plain form submissions at all. It also does not
apply to a LAN-reachable deployment — `entrypoint.sh` binds `0.0.0.0` and `compose.yml`
publishes `8000:8000`, so on a home server the app is reachable by IP and by any page served
from another origin on that network. `tests/test_auth_seam.py` proves only that the routes
carry the identity seam, which is irrelevant while the seam returns a constant local user
(`app/api/deps.py`).

This is the CONVENTIONS rule-6 failure as well: the docstring asserts a guarantee the code
does not deliver, which is precisely the property that suppresses scrutiny of these routes.

**Fix.** Enforce same-origin on the mutating methods. The cheapest complete version, added
in `create_app()`, needs no dependency and no token plumbing:

```python
from fastapi import Request
from fastapi.responses import PlainTextResponse

@app.middleware("http")
async def _same_origin_guard(request: Request, call_next):
    """Destructive POSTs are same-origin only until a real CSRF token lands.

    Browsers send Sec-Fetch-Site on every request; forms and fetches from another
    origin arrive as 'cross-site'. Absent header (curl, tests, htmx same-origin
    requests) is allowed — the guard targets the browser-driven vector.
    """
    if request.method not in ("GET", "HEAD") and request.headers.get(
        "sec-fetch-site", "same-origin"
    ) not in ("same-origin", "none"):
        return PlainTextResponse("cross-origin request refused", status_code=403)
    return await call_next(request)
```

Alternatively check `Origin`/`Referer` against the request `Host`. Whichever is chosen, the
docstring must be corrected in the same change: state that these routes are
CSRF-reachable today and name the guard that stops it, rather than asserting the opposite.
If the decision is to accept the risk for v1 instead, that acceptance must be recorded as
such (with the reset/POST-token reasoning spelled out) — the current text is not an
accepted risk, it is an incorrect claim.

## Warnings

### WR-01: The prune form never pre-fills the stored retention threshold

**File:** `app/api/settings.py:276-281` and `app/web/templates/html/settings.html:318-323`

**Issue.** `_settings_context` reads the stored thresholds and documents the read as:

> The retention thresholds (D-168). One read backs both the initial render and the
> re-render after a preview, so the field's default and the stored value cannot
> disagree.

They can, and do. The age input is hardcoded to a literal:

```jinja
value="{{ prune_preview.age_days if prune_preview else 30 }}"
```

`retention` is used only for the "Stored thresholds: …" text line (line 327). So a user who
saved `listings = 7` days reopens `/settings` and sees `30` in the field — the control D-168
says "remembers it" does not, and the docstring asserts a property the template does not
implement. This is the same class as CR-01: prose claiming a guarantee the code omits
(CONVENTIONS rule 6).

**Fix.** Pre-fill from the stored per-category threshold, which requires the category too.
Minimal version: have the route pass the stored value for the category the preview carried
(when one exists) and otherwise fall back to the stored value of the select's current
default, e.g.

```jinja
value="{{ prune_preview.age_days if prune_preview else (retention.get(prune_categories[0][0]) or 30) }}"
```

and drop the docstring claim unless the general case is actually handled. A cleaner fix is
to make the select re-render server-side on a category change so the threshold follows the
category; if that is deliberately out of scope, say so in place of the guarantee.

### WR-02: `reconcile()` cannot detect a timezone change — `str(CronTrigger)` omits it

**File:** `app/jobs/scheduler.py:265`

**Issue.**

```python
if str(existing.trigger) != str(trigger):
    scheduler.reschedule_job(SCHEDULED_JOB_ID, trigger=trigger)
```

Verified against the installed APScheduler 3.11.3 source:

```python
def __str__(self):
    options = [f"{f.name}='{f}'" for f in self.fields if not f.is_default]
    return "cron[{}]".format(", ".join(options))
```

The timezone is not a field, so it never appears in the string. `CronTrigger(hour=7,
minute=0, timezone=ZoneInfo("Europe/Dublin"))` and `CronTrigger(hour=7, minute=0,
timezone=ZoneInfo("UTC"))` both stringify to `cron[hour='7', minute='0']`. Today this is
unreachable through the UI (`ALLOWED_TIMEZONES = {"Europe/Dublin"}`, one member), so it is a
latent defect rather than a live one — but it becomes a silent no-op the moment a second
timezone is offered, which is the obvious next change: the user switches timezone, the
settings page says "Schedule saved.", and the nightly job keeps firing at the old absolute
time because `reconcile` concludes `unchanged`. The surrounding comment block
("Create the job only when absent; reschedule only on trigger drift") states the intent that
the comparison fails to honour.

**Fix.** Compare the schedule's own identity, not the trigger's repr:

```python
existing_tz = getattr(existing.trigger, "timezone", None)
drifted = (
    not isinstance(existing.trigger, CronTrigger)
    or (existing.trigger.fields, str(existing_tz))
    != (trigger.fields, str(trigger.timezone))
)
```

or, simpler and sufficient, compare `(existing.trigger, existing.trigger.timezone)` field
values explicitly plus `str(existing_tz) != str(schedule.timezone)`.

### WR-03: The recorded stop signal is parsed by `repr()` quoting, not by structure

**File:** `app/db/repositories/source_repo.py:63` and `app/db/repositories/source_repo.py:164-173`

**Issue.** The ledger note is written by `classify_response` (`app/sources/base.py:180`) as

```python
f"fetch-side: stop signal {stop_signal!r}; recorded and stopped, never retried"
```

and read back with a prefix that bakes in Python's `repr` quoting:

```python
STOP_SIGNAL_PREFIX = "fetch-side: stop signal '"
...
if not isinstance(note, str) or not note.startswith(STOP_SIGNAL_PREFIX):
    return None
return note.removeprefix(STOP_SIGNAL_PREFIX).split("'", 1)[0] or None
```

`{stop_signal!r}` emits single quotes only while the value contains no single quote;
`repr("it's")` is `'"it\'s"'` — with **double** quotes — and the prefix then misses, so
`_recorded_stop_signal` returns `None` and the stop signal silently disappears from both
`/status`'s classification and the S5 projection (`_derived_health` then reports the source
as healthy rather than degraded — a false negative on exactly the signal that detects a
block page returning 200). `BLOCK_SIGNALS` (`app/sources/base.py:34-41`) is a fixed set of
quote-free lowercase words today, so this is latent, not live — but the parse anchors on a
formatting detail of the producer rather than on its structure, which is the anti-pattern
CONVENTIONS rule 1 names, and rule 2 forbids the silent-`None` degradation it causes.

**Fix.** Parse structurally and let a quoted-but-unrecognised note be a visible warning
rather than a silent `None`:

```python
_STOP_SIGNAL_RE = re.compile(r"^fetch-side: stop signal (?P<q>['\"])(?P<sig>.*?)(?P=q);")

def _recorded_stop_signal(note: Any) -> str | None:
    if not isinstance(note, str):
        return None
    match = _STOP_SIGNAL_RE.match(note)
    return match.group("sig") or None if match else None
```

The durable fix is to record the signal in its own column instead of in free-text `note`.

## Info

### IN-01: The `listings` prune can never yield a path or a size — the artefact branch is unreachable

**File:** `app/db/repositories/retention_repo.py:335-342` (`_paths_for_listings`), `:316` (`artifact_linked`), `:375` (the `CvArtifact` delete inside `_delete_listings`)

**Issue.** `_select_listings` excludes every listing that has any `cv_artifacts` row
(`~artifact_linked`), so the ids handed to `paths` can never be the `listing_id` of an
artefact: `_paths_for_listings` always returns `[]`, the `listings` preview's `size_bytes`
is always `0` (`settings.html:338` renders "· 0 B"), and the `sa_delete(CvArtifact)` at
`:375` always matches zero rows. `tests/db/test_retention_repo.py:644` and `:647` document
this ("the only child artifact belonged to `artefacted`, which is kept", "a listing with an
artifact is never selected and yields no paths"), so the count is right and the deletion is
safe — the defect is only that a child-delete and a paths callable are written for a case
the guard provably excludes, which invites a later edit to "fix" the empty paths by relaxing
the guard. `CvDraft`/`ScreeningDraft`/`ListingEvent` children are genuinely reachable; only
the artefact half is dead.

**Fix.** Either drop `_paths_for_listings` (and leave a comment at the `CvArtifact` delete
explaining it is defensive), or keep both and note in `_paths_for_listings`' docstring that
`_select_listings` excludes artefacts, so the empty result is by construction rather than an
oversight.

### IN-02: `ok` artefacts with a NULL `listing_id` are permanently unprunable

**File:** `app/db/repositories/retention_repo.py:193-216`

**Issue.** Guard 4's correlated subquery compares `newer.listing_id == CvArtifact.listing_id`.
`cv_artifacts.listing_id` is nullable (`app/db/models.py:405`), and `NULL = NULL` is `NULL`
in SQL, so for an `ok` row with `listing_id IS NULL` the subquery is never satisfied and
`or_(compile_status != "ok", newer_ok)` is false — the row is never selected. Such rows leak
forever and their `.tex`/`.pdf` files are never unlinked by the `artifacts` category. This
fails safe (nothing is wrongly deleted), so it is a growth leak rather than a data-loss risk.

**Fix.** Treat a NULL `listing_id` as unguarded by the newest-artefact rule, e.g.
`or_(CvArtifact.listing_id.is_(None), newer_ok)` in the selection's `or_`, or state in the
docstring that orphan rows are out of the prune's scope.

### IN-03: `reconcile_stale_runs` discards any errors already on the row

**File:** `app/jobs/scheduler.py:217`

**Issue.** `run.errors_json = [{...one reconciled entry...}]` replaces the column rather than
appending to it, while the docstring says "with the reason recorded in the row's existing
error storage" — wording that implies preservation. Reachability is low today because
`errors_json` is written only at `_finish` (`app/pipeline/run.py:604`, same commit that sets
a terminal status), so a row left `running` normally has none; but a row that was mid-flight
when a previous build persisted errors would lose them.

**Fix.** Append instead of replace, preserving any existing entries:

```python
run.errors_json = [*list(run.errors_json or []), {"source": "*", "error": "..."}]
```

or correct the docstring to say the column is overwritten.

### IN-04: Lint violations in files this phase added

**File:** `app/db/repositories/retention_repo.py:134`, `tests/api/test_health_page.py:17`, `tests/api/test_settings_prune.py:211`, `tests/db/test_retention_repo.py:331`, `tests/db/test_retention_repo.py:604`, `tests/jobs/test_scheduler.py:10`

**Issue.** `ruff check` (the repo's own pinned 0.16.7, with `select = ["E","F","I","UP","B"]`
in `pyproject.toml`) reports six violations in files added by this phase:

- `app/db/repositories/retention_repo.py:134` — `UP032` (`"{:.1f}".format(value)` should be an f-string);
- `tests/api/test_health_page.py:17` and `tests/jobs/test_scheduler.py:10` — `I001` unsorted import block;
- `tests/api/test_settings_prune.py:211` and `tests/db/test_retention_repo.py:331` — `E501` over 100 columns;
- `tests/db/test_retention_repo.py:604` — `F841` local `corpus` assigned and never used.

The `F841` is worth more than a style nit: the test is named
`test_the_listing_selection_excludes_applications_artifacts_and_both_dupe_sides` but asserts
only `result.count == 2`, so it does not pin *which* two of the six eligible listings were
selected — a selection that kept the two dupe sides instead of `clean`+`eventful` would pass.
The sibling test at `:616` does assert identities, so the gap is covered elsewhere; using
`corpus` here would close it locally.

**Fix.** Run `ruff check --fix` for the import order and the f-string, wrap the two long
lines, and assert identities in the selection test, e.g.
`assert {i for i in (corpus["clean"], corpus["eventful"])} == await _listing_ids(...)` scoped
to the pre-delete set, or assert the exclusions individually.

### IN-05: `read_retention` accepts arbitrary keys while both writers validate their input

**File:** `app/db/repositories/operations_config_repo.py:162-181`

**Issue.** `_parse_retention` keeps any string key with a positive integer value and does not
restrict keys to `retention_repo.PRUNE_CATEGORIES`; `write_retention` (line 216) likewise
only checks "non-empty string". Only the route's `_validate` path constrains the category,
so a hand-edited or legacy `retention_json` can surface an arbitrary key in the
"Stored thresholds: …" line (`settings.html:327`). Jinja autoescape makes this a display
oddity, not an injection, and nothing acts on an unknown key.

**Fix.** Filter to the known categories in `_parse_retention`
(`if key not in retention_repo.PRUNE_CATEGORIES: continue`) — but note that would introduce a
repository→repository import; alternatively restrict in `write_retention` and leave the read
tolerant, and record that choice in the docstring.

---

_Reviewed: 2026-10-14T21:00:01Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
