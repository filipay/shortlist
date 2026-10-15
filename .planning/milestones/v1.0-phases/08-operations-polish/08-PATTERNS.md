# Phase 8: Operations + Polish — Pattern Map

**Mapped:** 2026-10-14
**Files analyzed:** 33 (12 new + 21 modified)
**Analogs found:** 30 / 33 (3 have no direct analog — all are tests of new surfaces)

> **Scope fence.** Everything below is grounded in the shipped code read this
> session. Three open decisions in `08-RESEARCH.md` change *which* files exist,
> not the patterns: **C1** (the health page's path — the map assumes a distinct
> page path so `GET /health` stays JSON), **C2** (D-167's hard delete — the map
> assumes option (b), reusing the reset's trigger-suspend), **A6** (the skip
> record lives in JSON on the ops row, not a fifth `runs.status`).
> **`08-UI-SPEC.md` assumes the opposite for C1** ("the JSON moves to
> `/health.json`"); the planner must resolve that collision before planning the
> page route. The pattern work is identical either way.

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/jobs/__init__.py` | config (package init) | — | `app/probe/__init__.py` | exact |
| `app/jobs/scheduler.py` | service (scheduler) | event-driven | `app/main.py` + `app/api/runs.py` | role-match |
| `app/db/repositories/operations_config_repo.py` | model/repo | CRUD (singleton JSON) | `app/db/repositories/apply_config_repo.py` | exact |
| `app/db/repositories/retention_repo.py` | model/repo | batch (delete + unlink) | `app/api/settings.py` reset phase | role-match |
| `app/api/health_page.py` | controller (route) | request-response | `app/api/health.py` + `app/api/runs.py` | exact |
| `alembic/versions/0008_operations_config.py` | migration | — | `alembic/versions/0004_ranking_config.py` | exact |
| `app/web/templates/html/health.html` | component (page) | request-response | `app/web/templates/html/queue.html` | exact |
| `docs/runbook-responsive-ui.md` | config (docs) | — | `docs/runbook-compose-smoke.md` | exact |
| `tests/jobs/test_scheduler.py` | test | event-driven | `tests/db/test_source_seeding.py` | role-match |
| `tests/db/test_retention_repo.py` | test | batch | `tests/api/test_settings_reset.py` | role-match |
| `tests/api/test_health_page.py` | test | request-response | `tests/api/test_health.py` | exact |
| `tests/api/test_schedule_settings.py` | test | request-response | `tests/api/test_settings_reset.py` | exact |
| `app/db/models.py` | model | — | `RankingConfig` / `ApplyConfig` classes | exact |
| `app/api/settings.py` | controller (route) | request-response | itself (weights card + reset phase) | exact |
| `app/main.py` | config (wiring) | — | itself (`lifespan`) | exact |
| `app/api/health.py` | controller (route) | request-response | itself (`_opencode_report` etc.) | exact |
| `app/db/repositories/source_repo.py` | model/repo | CRUD (read model) | itself (`get_source_health`) | exact |
| `app/web/templates/html/_health_strip.html` | component (partial) | request-response | itself | exact |
| `app/web/templates/html/settings.html` | component (page) | request-response | itself (danger zone card) | exact |
| `assets/tailwind/input.css` | config (CSS build input) | — | itself (`.queue-table` / `.health-table`) | exact |
| `static/vendor/app.css` | build artifact | — | itself (committed build) | exact |
| `app/config.py` | config | — | itself (Phase 4/5 knob blocks) | exact |
| `pyproject.toml` + `requirements.txt` | config | — | itself (`rapidfuzz` / `pypdf` pins) | exact |
| `tests/test_dependency_pins.py` | test (guard) | — | itself (`PINNED_PACKAGES`) | exact |
| `tests/test_auth_seam.py` | test (guard) | — | itself (`EXPECTED_SEAM_ROUTES`) | exact |
| `tests/test_config.py` | test (guard) | — | itself (`REQUIRED_SETTINGS_FIELDS`) | exact |
| `tests/db/test_migration_contract.py` | test (guard) | — | itself (item 15) | exact |
| `tests/db/test_no_pii_columns.py` | test (guard) | — | itself (`EXPECTED_JSON_COLUMNS`) | exact |
| `tests/db/test_orm_drift.py` | test (guard) | — | itself (`_is_internal`) | exact |
| `docs/runbook-compose-smoke.md` | config (docs) | — | itself | exact |
| `compose.yml` | config | — | itself (Phase 2/4 passthrough block) | exact |
| `Dockerfile` / `Dockerfile.texlive` | config | — | itself (Tectonic/JobSpy build-time proofs) | exact |
| `entrypoint.sh` | config | — | itself (`--workers 1`) | exact |

---

## Pattern Assignments

### `app/db/repositories/operations_config_repo.py` (repo, singleton JSON CRUD)

**Analog:** `app/db/repositories/apply_config_repo.py` (and `ranking_config_repo.py`, which is the stricter twin — read both; the ops repo needs apply_config's *total-read/absent-row-fallback* but ranking_config's *strict-write validation*).

**Module docstring — the house rules every repo restates** (`apply_config_repo.py:1-15`):
```python
"""The screening-question document — the only place its SQL lives (D-124).

Mirrors ``ranking_config_repo``: one row (``id = 1``, enforced by
``ck_apply_config_singleton``), a JSON ``questions_json`` column, and the house
repository rules — it takes an ``AsyncSession``, **never commits**, and wraps its
write in a SAVEPOINT so a failure cannot poison the caller's outer transaction.
``now`` is injectable so a caller (or a test) can pin the clock.

The read is **total**: an absent row falls back to the code-level ...
"""
```

**Imports + singleton id + code-level defaults** (`apply_config_repo.py:17-37`):
```python
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApplyConfig

#: The pinned singleton row id (mirrors ``ck_apply_config_singleton``).
SINGLETON_ID = 1

#: The fresh-install question list. Used only when no ``apply_config`` row exists.
DEFAULT_QUESTIONS: tuple[str, ...] = (...)
```

**Total read (absent row → default, never raises)** (`apply_config_repo.py:45-56`):
```python
async def read_questions(session: AsyncSession) -> list[str]:
    row = await session.get(ApplyConfig, SINGLETON_ID)
    stored = row.questions_json if row is not None else None
    if isinstance(stored, list):
        return _clean(stored)
    return list(DEFAULT_QUESTIONS)
```

**Write: upsert + injectable `now` + SAVEPOINT** (`apply_config_repo.py:59-83`):
```python
async def write_questions(
    session: AsyncSession,
    questions: Iterable[str],
    *,
    now: datetime | None = None,
) -> list[str]:
    cleaned = _clean(questions)
    moment = now if now is not None else datetime.now(UTC)
    statement = (
        sqlite_insert(ApplyConfig)
        .values(id=SINGLETON_ID, questions_json=cleaned, updated_at=moment)
        .on_conflict_do_update(
            index_elements=["id"],
            set_={"questions_json": cleaned, "updated_at": moment},
        )
    )
    async with session.begin_nested():
        await session.execute(statement)
        await session.flush()
    return cleaned
```

**Storage-boundary validation before any SQL** (`ranking_config_repo.py:73-96`) — copy this shape for the schedule (`hour in 0..23`, `minute in 0..59`, `timezone` against a fixed allow-list `{"Europe/Dublin"}`) and for each retention threshold (a positive int):
```python
    unknown = sorted(str(key) for key in weights if key not in rubric.FACTORS)
    if unknown:
        raise ValueError(...)
    ...
    raise ValueError(f"weight for {factor!r} must be a finite float >= 0.0, got {weights[factor]!r}")
```

**`__all__` at the foot** (`apply_config_repo.py:86`). One module, two payload columns
(`schedule_json`, `retention_json`) → two read/write pairs, or one `read_document`/
`write_schedule`/`write_retention` triple. Two columns, not one blob (RESEARCH §Naming note).

---

### `app/db/repositories/retention_repo.py` (repo, batch delete + disk unlink)

**Analog:** `app/api/settings.py`'s reset delete phase (the *only* existing
DELETE path) plus the repo house rules from `cv_artifact_repo.py`.

**House rules + "retention is Phase 8" marker it now fulfils** (`cv_artifact_repo.py:1-28`):
```python
"""...* repositories are the **only** place SQL lives;
 * they take an `AsyncSession` explicitly and **never commit** — the caller owns
   the single commit;
 * the write is wrapped in a SAVEPOINT (`session.begin_nested()`) ...
"""
```
`cv_artifact_repo.py:23` says verbatim: *"Retention/pruning is deliberately Phase 8
and is not implemented here."*

**The append-only trigger suspension — reuse these two functions, do not rewrite them**
(`app/api/settings.py:638-675`):
```python
_APPEND_ONLY_TRIGGER = "listing_events_no_delete"

async def _suspend_append_only_trigger(session: AsyncSession) -> str | None:
    ddl = await session.scalar(
        text("SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = :name"),
        {"name": _APPEND_ONLY_TRIGGER},
    )
    connection = await session.connection()
    await connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {_APPEND_ONLY_TRIGGER}")
    return str(ddl) if ddl else None

async def _restore_append_only_trigger(session: AsyncSession, ddl: str | None) -> None:
    if ddl:
        connection = await session.connection()
        await connection.exec_driver_sql(ddl)
```
The DDL is transactional because `build_engine` issues an explicit `BEGIN`
(`app/db/session.py:45-70`). **Do not `await session.commit()` inside the repo** —
return the file paths to unlink and let the route commit, then unlink (see below).

**The delete ordering (children first, FK-safe)** (`app/api/settings.py:147-162`):
```python
RESET_DELETE_ORDER: tuple[str, ...] = (
    "scores", "listing_exclusions", "listing_events", "listing_dupes",
    "listing_sources", "cv_artifacts", "cv_drafts", "screening_drafts",
    "listings", "llm_calls", "source_request_log", "runs", "queue_state", "companies",
)
```
Phase 8's per-category queries use `NOT EXISTS` guards (RESEARCH §Code Examples
carries the exact SQL). Note from RESEARCH C2: `queue_state` is a **global** watermark
row with no `listing_id` — it is not a per-listing child; D-167's "its `queue_state`"
is a wording slip. The per-listing children to delete are
`scores`, `listing_sources`, `listing_exclusions`, `listing_dupes` (both columns),
`cv_artifacts`, `cv_drafts`, `screening_drafts` (+ `listing_events` only under C2(b)).

**Guard 4 must mirror the read it protects** (`cv_artifact_repo.py:163-177`):
```python
async def latest_for_listing(
    session: AsyncSession, listing_id: int, *, ok_only: bool = True
) -> CvArtifactRecord | None:
    statement = select(CvArtifact).where(CvArtifact.listing_id == int(listing_id))
    if ok_only:
        statement = statement.where(CvArtifact.compile_status == "ok")
    statement = statement.order_by(CvArtifact.created_at.desc(), CvArtifact.id.desc()).limit(1)
```
The prune's "never delete the newest `ok` artifact per listing" predicate must be the
exact SQL complement of this `ORDER BY created_at DESC, id DESC` (RESEARCH
Don't-Hand-Roll row 2).

**The one definition for "is a run in flight?"** (`app/api/settings.py:623-626`) —
move this into the repo and have both the reset guard and the scheduler import it:
```python
async def _running_run_id(session: AsyncSession) -> int | None:
    return await session.scalar(
        select(Run.id).where(Run.status.not_in(tuple(TERMINAL_STATUSES))).limit(1)
    )
```

**The route owns the transaction boundary and the post-commit unlink** — modelled on
the reset route (`app/api/settings.py:760-800`): suspend → delete → restore →
`await session.commit()` → then unlink files; a failure before the commit renders the
honest refusal and rolls back (`await session.rollback()` **before** re-rendering any
template that runs count queries — see `:771-774`). File paths must be resolved and
asserted inside `Path(settings.artifacts_dir)` before each unlink (RESEARCH §Security
Domain — path traversal).

**Preview == delete: one predicate, two statements** — `snapshot_database()`
(`app/api/settings.py:595-620`) is the existing cheap-insurance precedent for the
listing category; the preview is `COUNT(*)` + `Path(p).stat().st_size` over the *same*
SELECT.

---

### `app/jobs/scheduler.py` (service, event-driven)

**Analogs:** `app/main.py` (`lifespan`, the only legal start/stop site), `app/api/runs.py`
(the background-task shape the target mirrors), `app/db/session.py` (engine + pragmas).

**The lifespan contract: log-and-continue, never hard-fail (D-08)** (`app/main.py:36-50`):
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        async with async_session_maker() as session:
            inserted = await source_repo.ensure_registered_sources(session)
            await session.commit()
        if inserted:
            log.info("startup.sources_seeded", sources=inserted)
    except Exception as exc:  # noqa: BLE001 — boot must not depend on the seeding
        log.warning("startup.sources_seed_failed", error=type(exc).__name__)
    yield
```
Add `start_scheduler()` before the `yield` and `stop_scheduler()` after it, each in its
own try/except returning a status string (RESEARCH Pattern 1). `tests/db/test_source_seeding.py:138`
calls `main_module.lifespan(None)`, so **`start_scheduler` must not require the `app` object**.

**The background-task shape the scheduled target mirrors** (`app/api/runs.py:92-110`):
```python
    run = Run(search_id=None, trigger="manual", status="running", started_at=datetime.now(UTC))
    session.add(run)
    await session.commit()
    await session.refresh(run)
    task = asyncio.create_task(run_pipeline("manual", None, session_factory, run_id=run.id))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
```
The scheduled target is simpler: `run_pipeline("schedule", None, factory)` (no
pre-created row; `run_id` already defaults to `None`).

**The pipeline entry point — the scheduler is a caller, not a code path** (`app/pipeline/run.py:706-729`):
```python
async def run_pipeline(
    trigger: str,
    search_id: int | None,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    adapters: Sequence[JobSource] | None = None,
    query: SearchQuery | None = None,
    run_id: int | None = None,
    llm: LLMBackend | None = None,
) -> int:
    """...
    `run_id` lets a caller that already created (and committed) the `runs` row ...
    Phase 8's scheduler simply omits it and the pipeline creates its own row.
    """
```

**`TERMINAL_STATUSES` and the in-flight guard** (`app/pipeline/run.py:67`;
`app/api/settings.py:623-626`). `max_instances=1` cannot see `POST /runs`
(RESEARCH Pattern 3) — the DB query is the real guard.

**Resolve the session factory inside the call, never pass it in** (`app/db/session.py:83-90`):
```python
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """The factory a *background* task should use.

    A request-scoped session cannot outlive its response ...
    """
    return async_session_maker
```
Why this matters (`app/api/runs.py:56` docstring + RESEARCH Pitfall 3): APScheduler
pickles `args`/`kwargs`, and an `async_sessionmaker` holds an engine — unpicklable. The
job target must be **module-level, argument-free, `async def`**.

**The jobstore's own engine needs the same pragmas, but NOT `build_engine`**
(`app/db/session.py:23-42, 45-70`):
```python
def apply_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    ...
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
```
`SQLAlchemyJobStore(engine=...)` needs a **sync** engine from `settings.database_url_sync`
(`app/config.py:45`). Attach `apply_sqlite_pragmas` via
`event.listens_for(engine, "connect")`; the two async-only listeners in `build_engine`
are not applicable to a sync engine.

**Register the router at the app factory** (`app/main.py:61-70`) — add
`app.include_router(health_page_routes.router)` next to the other includes.

---

### `app/api/health_page.py` (route, request-response) + `app/api/health.py` edit

**Analog:** `app/api/health.py` — the four probes already exist there as **total**
module-level helpers; the page must **share the builders**, not re-implement them
(D-138: the page and the JSON cannot disagree about `auth_configured`).

**The builders to extract into one shareable `dependency_report()`** (`app/api/health.py:46-97`):
```python
async def _opencode_report(backend: LLMBackend) -> dict[str, Any]:
    """`{reachable, version, error, auth_configured}`. A backend bug must not break `/health`."""
    configured = auth_configured()
    try:
        outcome = await backend.health()
    except Exception as exc:  # noqa: BLE001 — health is a total function
        return {"reachable": False, "version": None, "error": type(exc).__name__,
                "auth_configured": configured}
    return {"reachable": bool(outcome.reachable), "version": outcome.version,
            "error": outcome.error, "auth_configured": configured}

def _cv_report() -> dict[str, Any]:
    """... `error` is the exception CLASS NAME only, never a message ..."""
    return fact_store_report(Path(settings.cv_dir) / CV_FILENAME)
```
Keep the returned **key names identical** — 25 existing assertions read this JSON
(RESEARCH C1).

**The DB-only rule for the page** — the JSON endpoint currently calls `probe_all(...)`
(`app/api/health.py:118-122`), which is the live board probe. **The page must not.**
D-156: a page view must never be a scrape. The page's source badge comes from the
run-derived read, not from `probes`:
```python
    try:
        probes = await probe_all(session_factory=session_factory)
    except Exception as exc:  # noqa: BLE001 — a probe failure must not break /health
        log.warning("health.probe_failed", error=type(exc).__name__)
        probes = {}
```

**The page route shape** (`app/api/runs.py:125-139` — the closest existing plain
`TemplateResponse` page route):
```python
@router.get("/runs", response_class=HTMLResponse)
async def run_history(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    runs = await run_repo.list_runs(session)
    return templates.TemplateResponse(request, RUN_TEMPLATE, {"runs": runs, "user": user})
```
Every route needs `user: User = Depends(current_user)` — `tests/test_auth_seam.py:122-133`
walks *every* leaf route dynamically and fails otherwise. Templates come from
`app/web/template_env.py::make_templates`.

**The "decorative reads never raise" convention the page inherits** (`app/web/routes.py:74-94`):
```python
async def _health_strip(
    session: AsyncSession, backend: LLMBackend
) -> tuple[list[SourceHealth], bool, str | None, str | None, bool]:
    """`(rows, reachable, version, error, auth_configured)` — never raises. ..."""
    try:
        rows = await get_source_health(session)
    except Exception as exc:  # noqa: BLE001 — decorative data must not 500 the page
        log.warning("queue.health_read_failed", error=type(exc).__name__)
        rows = []
    ...
    return rows, bool(outcome.reachable), outcome.version, outcome.error, auth_configured()
```

**The next-run accessor must be total** (RESEARCH Pattern 5 / Pitfall 6):
```python
job = get_scheduler().get_job(SCHEDULED_JOB_ID)          # None when absent/off
next_run = job.next_run_time if job is not None else None  # tz-aware datetime, or None
```
Wrap in try/except (a scheduler that failed to start must degrade the line, not 500).
`None` ⇒ `Scheduling off` when the stored row says disabled, else `No run scheduled` —
never a fabricated time. The countdown is computed at render from
`datetime.now(ZoneInfo(tz))`, never stored.

**Read-only Adzuna verdict** — the pure functions already exist:
`app/probe/survival.py:521 adzuna_promotion_condition(evidence)` over
`app/probe/survival.py:490-509 BoardEvidence`, with `baseline_from_row(row)`
(`survival.py:723`). **There is no builder from persisted rows in `app/`** — Phase 8
must write one (RESEARCH Pattern 7). The badge vocabulary must reuse
`source_repo.VALID_HEALTH` (`app/db/repositories/source_repo.py:36`) so no new CSS token
is needed.

---

### `app/db/repositories/source_repo.py` edit (repo, run-derived read)

**Analog:** itself. The run-derived facts D-156 needs **already exist** — extend them.

**The existing window constant + run-derived readers** (`source_repo.py:39, 100-121`):
```python
RECENT_RUN_LIMIT = 20

def _source_entry(run: Run, name: str) -> dict[str, Any] | None:
    counts = run.source_counts_json
    if not isinstance(counts, dict):
        return None
    entry = counts.get(name)
    return entry if isinstance(entry, dict) else None

def _last_success_run(runs: Sequence[Run], name: str) -> Run | None:
    """The most recent run in which *this source* reported `ok`."""
    for run in runs:
        entry = _source_entry(run, name)
        if entry is not None and entry.get("status") == "ok":
            return run
    return None
```

**The read-model structure to extend** (`source_repo.py:204-259`) — `get_source_health`
already assembles `SourceHealth(...)` from `sources` + the last `RECENT_RUN_LIMIT` runs.
The stop signals are **already recorded** at ingest (`app/sources/_ledger.py` writes
`stop_signal` into `source_request_log.note` — RESEARCH Pattern 7), so the badge read is a
new query over recorded rows, not a new write. Classify with the existing pure
`app/probe/survival.py:417 classify_block_vs_parse(...)`.

**The deterministic-ordering rule** (`source_repo.py:124-131`): every read is
`.order_by(...)` explicitly; `get_source_health` orders by `Source.name` and runs by
`started_at.desc(), id.desc()`.

---

### `app/db/models.py` edit (+ `OperationsConfig`)

**Analog:** `RankingConfig` (`models.py:111-137`) and `ApplyConfig` (`models.py:493-512`) —
the singleton-config precedent is exact.

**The model shape to copy** (`models.py:129-137`):
```python
    __tablename__ = "ranking_config"

    id = Column(Integer, primary_key=True)
    weights_json = Column(JSON, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_ranking_config_singleton"),
    )
```
The docstring convention (`models.py:118-126`) states the singleton pin, the JSON
column's allow-list requirement, and **why there is no FK** (a global setting, not an
observation about a run) — restate that reasoning for `operations_config`.

**Two JSON columns, one table** (`schedule_json`, `retention_json`), a named
`ck_operations_config_singleton`, `updated_at`. A future `user_id` column is additive;
**do not add one now** (D-21 / AP14 — `tests/test_auth_seam.py:162-185` scans every table
for `user_id`/`owner_id`/`tenant_id` and fails).

**The `runs.trigger` CHECK already permits `'schedule'`** (`models.py:334-338`):
```python
        CheckConstraint(
            "trigger IN ('manual','schedule')",
            name="ck_runs_trigger",
        ),
```
No migration for the trigger value. `runs.status` permits only
`('running','done','failed','partial')` (`models.py:339-342`) — hence A6's "store the
skip on the ops row, not a fifth status".

---

### `alembic/versions/0008_operations_config.py` (migration)

**Analog:** `alembic/versions/0004_ranking_config.py` — a one-table, purely-additive
singleton migration. Copy its exact structure and its two documented choices.

**The whole file shape** (`0004_ranking_config.py:29-53`):
```python
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ranking_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("weights_json", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.CheckConstraint("id = 1", name="ck_ranking_config_singleton"),
    )


def downgrade() -> None:
    # Symmetric: drop exactly the one table this revision added.
    op.drop_table("ranking_config")
```
`0008` is `revision = "0008"`, `down_revision = "0007"`. **The table is not seeded**
(`0004:18-23`): the repository's code-level defaults handle an absent row, and a
migration must not import application code. Named CHECK only — an unnamed one is dropped
by a later `batch_alter_table` (`0004:24-26`).

---

### `app/web/templates/html/health.html` (page template)

**Analog:** `app/web/templates/html/queue.html` (extends base, includes the strip
partial) + `_health_strip.html` itself.

**Page skeleton + the strip include** (`queue.html:1-5, 178-181`):
```jinja
{% extends "html/base.html" %}

{% block title %}Queue · Shortlist{% endblock %}

{% block content %}
...
{% include "html/_health_strip.html" %}
{% endblock %}
```
The health page does the same: system section (`<section id="health-system">`), the
schedule line, the last-run line, the read-only Adzuna line, then
`{% include "html/_health_strip.html" %}` **verbatim** — so the page and the queue strip
cannot drift (D-156 / `08-UI-SPEC.md` §B). Context names the partial reads are pinned by
`tests/api/test_health.py` (`opencode_reachable`, `opencode_version`,
`opencode_auth_configured`, `opencode_error`, `cv`, `source_health`).

**Status lines reuse existing classes** — `.ranking-strip` (`queue.html:149`) for the
next-run/last-run lines and `.health-badge health-{ok|degraded|unreachable|unknown}`
(`_health_strip.html:54`) for the dependency rows. No new colour tokens
(`08-UI-SPEC.md` §Component Inventory).

**The nav entry** (`app/web/templates/html/base.html:27-34`) — one more `<a class="nav-link ...">`;
note the `nav_path`-binding convention (`base.html:18-26`) and that the base renders
harmless fragments with no `request`, so the new entry must stay inside that guard.

---

### `assets/tailwind/input.css` edit (CSS build input)

**Analog:** itself. The reflow rules copy the declarations of the two journey table
shells already in the file.

**`.queue-table` shell** (`input.css:531-566`) and **`.health-table` shell**
(`input.css:1607-1651`) — both already carry `display:block; overflow-x:auto;
max-width:100%`:
```css
  .queue-table {
    display: block;
    overflow-x: auto;
    max-width: 100%;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    background-color: var(--color-paper);
  }
```

**Where to author:** inside a new `@layer components { ... }` block (the file already has
14 of them; `@layer components` rules are not tree-shaken and are the shipped
convention — do **not** use `@utility`, RESEARCH Pattern 8 consequence). Add
`.table-scroll`, `.touch-target`, `.health-system` first, then the reflow block **last**
so it can override the desktop rules.

**The reflow block, verified against the pinned CLI** (RESEARCH Pattern 8):
```css
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
Name the media query `width < 48rem` (or `@variant max-md`) — **not** `max-width: 767px`
(RESEARCH Pitfall 8: 767.01–767.99px matches neither regime). Extend the selector list
to `.health-table` (the second journey table).

**Rebuild is mandatory and gated** (`tests/test_stylesheet_coverage.py:232-265` asserts
byte-identity of `static/vendor/app.css`):
```bash
./node_modules/.bin/tailwindcss -i ./assets/tailwind/input.css -o ./static/vendor/app.css --minify
pytest tests/test_stylesheet_coverage.py -x
```
`data-label` values must equal the `<th>` text verbatim (no-JS, `attr()` pattern).

---

### `app/web/templates/html/_health_strip.html` edit (partial)

**Analog:** itself. Only `data-label` attributes are added (`08-UI-SPEC.md` says the
partial is otherwise unchanged) — D-162 requires the phone row to restack **all** the
desktop data.

**The table to annotate** (`_health_strip.html:39-65`):
```jinja
  <table class="health-table">
    <thead>
      <tr>
        <th scope="col">Source</th>
        <th scope="col">Health</th>
        <th scope="col">Last success</th>
        <th scope="col">Returned</th>
        <th scope="col">Field fill-rate</th>
      </tr>
    </thead>
    <tbody>
      {% for row in source_health %}
      <tr class="health-row" id="source-health-{{ row.name }}">
        <td class="health-source">{{ row.name }}</td>
        <td class="health-badge health-{{ row.health or 'unknown' }}">{{ row.health or 'unknown' }}</td>
        ...
```
Add `data-label="Source"`, `data-label="Health"`, etc. The queue rows to annotate are in
`app/web/templates/html/_listing_row.html` (every `<td>` — title, badges, score, posted,
exclusion chips, actions; D-162). **Do not** add `data-label` to admin tables (merges,
runs, factor) — they get `.table-scroll` instead (D-160).

---

### `app/web/templates/html/settings.html` edit (schedule card + prune card)

**Analog:** itself. The schedule card copies the weights/screening card shape; the prune
card copies the danger zone.

**The plain-POST form card + banner convention** (`settings.html:86-111`):
```jinja
<section class="settings-card" id="ranking-weights">
  <h3>Ranking weights</h3>
  <p class="settings-note">...</p>
  <form class="weights-form" method="post" action="/settings/weights">
    <div class="weight-grid">...</div>
    <div class="form-actions">
      <button type="submit" id="weights-submit">Save weights</button>
    </div>
  </form>
</section>
```

**The danger zone the prune control joins** (`settings.html:235-258`) — the
type-to-confirm token, the "snapshot is written before anything is deleted" note, and the
`POST` form:
```jinja
<section class="danger-card" id="danger-zone">
  <h3>Danger zone</h3>
  ...
  <form method="post" action="/settings/reset">
    <div class="field">
      <label for="reset-confirm">Type {{ confirm_token }} to confirm ...</label>
      <input type="text" id="reset-confirm" name="confirm" autocomplete="off" placeholder="{{ confirm_token }}">
    </div>
    <div class="form-actions">
      <button type="submit" id="reset-submit">Reset queue data</button>
    </div>
  </form>
</section>
```
The prune **preview and confirm are two separate submit steps**; the confirm form renders
only when the preview returned a non-zero count (RESEARCH §Security Domain). Preview
reuses `.settings-counts`; the one banner/refusal convention is
`templates.TemplateResponse(..., status_code=400/500)` with `banner=` + `error=True`
(`app/api/settings.py:326-333`).

**The context dict that every render funnels through** — `_settings_context`
(`app/api/settings.py:194-255`): add `schedule`, `retention`, `prune_preview` there, so
the initial render and the post-save re-render read one source and cannot disagree
(the weights/screening precedent, `settings.py:224-231`).

---

### `app/api/settings.py` edit (routes)

**Analog:** itself — `save_weights` is the exact template for `POST /settings/schedule`.

**Validate → refuse-with-banner (no 500) → write → commit → re-render** (`settings.py:304-342`):
```python
@router.post(WEIGHTS_PATH, response_class=HTMLResponse)
async def save_weights(request, user=Depends(current_user), session=Depends(get_session)):
    form = await read_form(request)
    current = await ranking_config_repo.read_weights(session)
    weights, errors = _parse_weights(form, current)

    if errors:
        log.info("settings.weights_rejected", errors=len(errors))
        return templates.TemplateResponse(
            request, SETTINGS_TEMPLATE,
            await _settings_context(session, banner=" ".join(errors), error=True),
            status_code=400,
        )

    await ranking_config_repo.write_weights(session, weights, now=datetime.now(UTC))
    await session.commit()
    return templates.TemplateResponse(
        request, SETTINGS_TEMPLATE,
        await _settings_context(session, banner="Weights saved."),
    )
```
`read_form` is `app/api/searches.py:120-127` — urlencoded only, `python-multipart`
deliberately absent. The route **commits first, then touches the scheduler** and wraps
the scheduler call so an unavailable scheduler cannot 500 the page (RESEARCH Pattern 4).

**The reset route's guard ordering** (`settings.py:678-800`): confirm token → in-flight
run → blocking row → snapshot → suspend trigger → deletes → restore → commit. The prune
routes reuse this shape (guards are the repo's WHERE clauses, so they cannot be forgotten
at the confirm step).

**Add `operations_config` to `RESET_KEPT_TABLES`** (`settings.py:169-175`):
```python
RESET_KEPT_TABLES: tuple[str, ...] = (
    "searches", "filter_rules", "sources", "ranking_config", "apply_config",
)
```
It is the user's own configuration — same category as `ranking_config`/`apply_config`.

**Extend the module docstring's stated CSRF caveat** (`settings.py:12-15`) to name the
new destructive prune routes (RESEARCH §Security Domain V4) — the comment currently
covers only `/settings/reset`.

---

### `app/config.py` edit (Settings)

**Analog:** itself — the Phase-4/5 knob blocks (`config.py:156-238`). Every numeric
ceiling is a field with a documented default (PLAT-04).

New fields the research implies: a schedule timezone (`schedule_timezone: str =
"Europe/Dublin"` — never inherit container UTC, D-153/AGENTS.md) and a misfire grace
(`schedule_misfire_grace_seconds: int = 3600`). Both must be added to
`tests/test_config.py`'s `REQUIRED_SETTINGS_FIELDS` and, if integer +
`>= DISTINCTIVE_THRESHOLD_FLOOR`, to `LIMIT_FIELDS` (`test_config.py:32-140`); the
literal scan then covers `app/jobs` if it is added to `SCANNED_DIRS`
(`test_config.py:212`). Forward both through `compose.yml` (see below) — an
unforwarded knob silently loses the host override (`compose.yml:24-30` comment).

---

### `docs/runbook-responsive-ui.md` (new, docs)

**Analog:** `docs/runbook-compose-smoke.md` — the established operator-run-check shape:
a title naming the success criterion, a **Prerequisites** list, fenced `bash` Commands,
"**What a pass looks like**" numbered steps, and an override section
(`runbook-compose-smoke.md:1-50`). It states explicitly why it is operator-run (no Docker
/ no browser in the sandbox) and that it is recorded in `.planning/WINDOWS.md` as an
unrun verify. Phase 8's checklist is 320/375/768 crossed with the journey pages
(queue, listing detail, /health, run control, applications) — D-161.

---

## Shared Patterns

### The auth seam (every route, no exceptions)
**Source:** `app/api/deps.py:13-22`
**Apply to:** `app/api/health_page.py`, every new route in `app/api/settings.py`
```python
LOCAL_USER = User(id=settings.local_user_id, name="Local", email=None)

async def current_user() -> User:
    """v1: the single local user. Later: OIDC/Authentik via authlib."""
    return LOCAL_USER
```
`tests/test_auth_seam.py:122-133` walks **every** leaf route dynamically — a new route
without `user: User = Depends(current_user)` fails, and the new page path must be added to
`EXPECTED_SEAM_ROUTES` (`test_auth_seam.py:31-66`) or the non-vacuity assertion at
`:108-116` can miss it.

### Repositories never commit
**Source:** `app/db/repositories/apply_config_repo.py:1-15`,
`app/db/repositories/cv_artifact_repo.py:1-10`
**Apply to:** `operations_config_repo.py`, `retention_repo.py`
The repo takes an `AsyncSession`, wraps writes in `session.begin_nested()`, and returns a
value; the **route** owns the single `commit()`.

### Decorative / total reads
**Source:** `app/web/routes.py:74-94` (`_health_strip`), `app/api/health.py:46-97`
**Apply to:** the `/health` page, the next-run line, the source badge, the preview
`stat()` calls. A degraded dependency is **reported as data**, never raised, and never
changes `status`.

### Structured logging
**Source:** `app/api/settings.py:327, 337`; `app/main.py:47, 49`
**Apply to:** the scheduler boot/skip events, the prune audit line, the rejected-form
paths. `log.info("settings.weights_saved")` style — a dotted event name plus keyword
fields, never a formatted string.

### Guard tests that must be edited, not worked around
**Source:** each guard's own module docstring ("A guard that cannot fail is not a guard")
| File | Edit |
|---|---|
| `tests/test_dependency_pins.py:32-35` | add `("apscheduler", "apscheduler==3.11.3", "3.11.3")` to `PINNED_PACKAGES`; pin verbatim in **both** `pyproject.toml:13-40` and `requirements.txt` |
| `tests/test_auth_seam.py:31-66` | add the new page path (and any new route) to `EXPECTED_SEAM_ROUTES` |
| `tests/test_config.py:32-140` | add every new `Settings` field to `REQUIRED_SETTINGS_FIELDS`/`LIMIT_FIELDS` |
| `tests/db/test_migration_contract.py:285-306, 737` | head `0007` → `0008` (appears **twice**: the item-9 test and the populated-upgrade assertion) |
| `tests/db/test_no_pii_columns.py:30-83` | add `operations_config` to `EXPECTED_JSON_COLUMNS` with its two columns |
| `tests/db/test_orm_drift.py:50-57` | if Pitfall-4 decision (a): add `apscheduler_jobs` to `_is_internal` with a comment naming its owner |

### `app/main.py` wiring
**Source:** `app/main.py:18-29, 61-70`
**Apply to:** import the new routers/modules and `include_router` them in `create_app`;
start/stop the scheduler in `lifespan` (never in `create_app`).

### `compose.yml` knob forwarding
**Source:** `compose.yml:24-53` (the Phase-2/4/5 passthrough blocks)
**Apply to:** every new `Settings` field. Compose uses `.env` only for `${...}`
substitution and the image contains no `.env`, so an unforwarded knob silently loses the
host override. Add `TZ`-related settings here too if the scheduler needs one.

### Build-time environment proof
**Source:** `Dockerfile:15-19` (Tailwind), and the Tectonic/JobSpy proof RUNs referenced
by AGENTS.md
**Apply to:** a one-line `RUN python -c "from zoneinfo import ZoneInfo; ZoneInfo('Europe/Dublin')"`
in the runtime stage, plus `ENV TZ=Europe/Dublin` — RESEARCH Pitfall 7 / Assumption A1
(the tz database in `python:3.13-slim` is **unverified**; treat as a confirmation
checkpoint).

### `entrypoint.sh` `--workers 1`
**Source:** `entrypoint.sh:8`
```sh
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```
Keep it; add a one-line comment naming the scheduler as a second reason (the file
currently cites only the ranking task set) — RESEARCH Pitfall 5.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `tests/jobs/test_scheduler.py` | test | event-driven | No scheduler exists yet; build the fixture from `tests/db/test_source_seeding.py:138` (`async with main_module.lifespan(None)`) plus a real `SQLAlchemyJobStore` on a temp file. httpx's `ASGITransport` does **not** run the lifespan. |
| `tests/db/test_retention_repo.py` | test | batch | No destructive batch path is tested outside the reset; seed from `tests/api/test_settings_reset.py:72-120` + a `tmp_path` artefacts dir. |
| `tests/api/test_schedule_settings.py` | test | request-response | The settings-form route is new; the client/fixture shape comes from the `tests/api/test_health.py:123-150` `health_env` fixture. |
| `app/probe/survival.py` — a `BoardEvidence` **builder from persisted rows** | service | batch read | `adzuna_promotion_condition` exists but is called only from tests; `baseline_from_row` exists; **no builder joins `runs` + `listing_sources` into a `BoardEvidence`** (RESEARCH Pattern 7). Write it (likely here or in `source_repo`). |
| `app/jobs/scheduler.py` — the APScheduler wiring itself | service | event-driven | No scheduler analog; follow RESEARCH Patterns 1–5 literally (they were verified against the pinned 3.11.3 sdist: `AsyncIOScheduler`, module-level argument-free target, create-if-absent reconciliation, explicit `coalesce`/`max_instances`/`misfire_grace_time`/`replace_existing`). |

---

## Metadata

**Analog search scope:** `app/`, `alembic/versions/`, `app/web/templates/html/`,
`assets/tailwind/`, `tests/`, `docs/`, `compose.yml`, `Dockerfile*`, `entrypoint.sh`,
`pyproject.toml`, `requirements.txt`
**Files scanned:** ~45 source/test/doc files read or grepped this session
**Analogs read in full:** `apply_config_repo.py`, `ranking_config_repo.py`,
`health.py`, `runs.py`, `main.py`, `session.py`, `config.py`, `settings.py`,
`run_repo.py`, `source_repo.py`, `cv_artifact_repo.py`, `0004_ranking_config.py`,
`0007_screening_draft_warnings.py`, `queue.html`, `_health_strip.html`,
`settings.html`, `base.html`, `_listing_row.html`, `applications_list.html`,
`test_migration_contract.py`, `test_orm_drift.py`, `test_no_pii_columns.py`,
`test_config.py`, `test_stylesheet_coverage.py`, `test_dependency_pins.py`,
`test_auth_seam.py`, `test_health.py`, `test_settings_reset.py`, `deps.py`
**All analog paths verified git-tracked** (`git ls-files -- <path>` non-empty) — no
gitignored install mirrors referenced.
**Pattern extraction date:** 2026-10-14
**Pattern mapping complete.**
