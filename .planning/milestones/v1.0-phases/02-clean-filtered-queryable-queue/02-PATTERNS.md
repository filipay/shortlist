# Phase 2: Clean, Filtered, Queryable Queue - Pattern Map

**Mapped:** 2026-09-16
**Files analyzed:** 46 (14 new source, 9 modified source, 23 new/modified tests)
**Analogs found:** 44 / 46 (the two `rapidfuzz`-dependent items have an in-repo install-pattern analog; the only true no-analog is the new pinned dependency itself)

> Phase 1 was greenfield (0 in-repo analogs). Phase 2 is the opposite: migration
> 0001 already ships almost every table, and **every new file has a strong in-repo
> analog**. Copy the analog's shape, not the research sketch, wherever they differ.
> All analog paths below are git-tracked (`git ls-files -- <path>` non-empty);
> none is a gitignored mirror.

---

## File Classification

### New source files

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/domain/dedup.py` | utility (pure domain) | transform | `app/domain/listing.py` | exact |
| `app/domain/filter.py` | utility (pure domain) | transform | `app/domain/listing.py` + `app/domain/models.py` | exact |
| `app/domain/criteria.py` | utility (pure domain) | transform | `app/domain/listing.py` + `app/sources/base.py` | role-match |
| `app/domain/search_query.py` | utility (pure domain) | transform | `app/domain/listing.py` | exact |
| `app/domain/run_reason.py` | utility (pure domain) | batch/transform | `app/probe/survival.py` (pure signals) | role-match |
| `app/db/repositories/search_repo.py` | repository | CRUD | `app/db/repositories/source_repo.py` | exact |
| `app/db/repositories/run_repo.py` | repository | CRUD (read model) | `app/db/repositories/source_repo.py` | exact |
| `app/db/repositories/event_repo.py` | repository | event-driven | `app/db/repositories/source_repo.py` | role-match |
| `app/db/repositories/exclusion_repo.py` | repository | CRUD/batch | `app/db/repositories/source_repo.py` | role-match |
| `app/db/repositories/dupe_repo.py` | repository | CRUD | `app/db/repositories/listing_repo.py` | role-match |
| `app/db/repositories/queue_repo.py` | repository | request-response (FTS/read) | `app/db/repositories/source_repo.py` + `tests/db/test_fts_triggers.py` | role-match |
| `app/db/repositories/state_repo.py` | repository | CRUD | `app/db/repositories/source_repo.py` | role-match |
| `app/pipeline/dedup_stage.py` | service (pipeline stage) | batch | `app/pipeline/stages.py` | exact |
| `app/pipeline/filter_stage.py` | service (pipeline stage) | batch | `app/pipeline/stages.py` | exact |
| `alembic/versions/0002_*.py` | migration | batch DDL | `alembic/versions/0001_initial_schema.py` | exact |
| `app/api/events.py` | controller/route | request-response | `app/api/runs.py` | exact |
| `app/api/searches.py` | controller/route | CRUD | `app/api/runs.py` + `app/api/health.py` | role-match |
| `app/web/templates/html/queue_list.html` | component (partial) | request-response | `app/web/templates/html/queue.html` | role-match |
| `app/web/templates/html/_listing_row.html` | component (partial) | request-response | `app/web/templates/html/_run_status.html` | role-match |
| `app/web/templates/html/criteria.html` | component (page) | CRUD | `app/web/templates/html/queue.html` | role-match |
| `app/web/templates/html/runs.html` | component (page) | request-response | `app/web/templates/html/queue.html` + `_run_status.html` | role-match |
| `app/web/templates/html/merges.html` | component (page) | request-response | `app/web/templates/html/queue.html` | role-match |

### Modified source files

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/domain/sanitize.py` (EXTEND) | utility (pure domain) | transform | itself — `INSTRUCTION_MARKERS`/`looks_like_instructions` seam | exact (in-place extension) |
| `app/pipeline/run.py` (EXTEND) | orchestrator | event-driven/batch | itself — insert stages before `_finish` | exact (in-place extension) |
| `app/db/models.py` (EXTEND) | model | CRUD | itself — mirror 0001 conventions | exact (in-place extension) |
| `app/web/routes.py` (EXTEND) | controller/route | request-response | itself — replace inline query with `queue_repo` | exact (in-place extension) |
| `app/api/runs.py` (EXTEND) | controller/route | request-response | itself — add history/merges routes | exact (in-place extension) |
| `app/main.py` (EXTEND) | provider/app factory | request-response | itself — `include_router` | exact (in-place extension) |
| `app/config.py` (EXTEND) | config | — | itself + `thresholds()` in `app/probe/survival.py` | exact |
| `pyproject.toml` (EXTEND) | config/build | — | itself — exact-pin convention | exact |
| `requirements.txt` (EXTEND) | config/build | — | itself — mirrors `pyproject.toml` exactly | exact |

### Modified/new tests

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/domain/test_search_query.py` | test | unit | `tests/sources/test_capabilities.py` (pure-unit lane) | role-match |
| `tests/domain/test_dedup.py` | test | unit | `tests/domain/test_normalize.py` | exact |
| `tests/domain/test_filter.py` | test | unit | `tests/domain/test_normalize.py` | role-match |
| `tests/domain/test_run_reason.py` | test | unit | `tests/probe/test_thresholds.py` | role-match |
| `tests/domain/test_injection_patterns.py` | test | unit | `tests/domain/test_sanitize.py` | exact |
| `tests/db/test_queue_state.py` | test | DB | `tests/db/test_source_seeding.py` | role-match |
| `tests/db/test_exclusions.py` | test | DB | `tests/db/test_two_key_upsert.py` | role-match |
| `tests/db/test_listing_events.py` | test | DB + append-only | `tests/db/test_migration_contract.py::test_listing_events_append_only` | role-match |
| `tests/db/test_dupes.py` | test | DB | `tests/db/test_two_key_upsert.py` | role-match |
| `tests/pipeline/test_dedup_merge.py` | test | integration | `tests/pipeline/test_ingest_e2e.py` | exact |
| `tests/pipeline/test_dedup_revert.py` | test | integration | `tests/pipeline/test_ingest_e2e.py` | exact |
| `tests/pipeline/test_filter_stage.py` | test | integration | `tests/pipeline/test_ingest_e2e.py` | exact |
| `tests/pipeline/test_criteria_snapshot.py` | test | integration | `tests/pipeline/test_ingest_e2e.py` | role-match |
| `tests/pipeline/test_capability_surface.py` | test | integration | `tests/pipeline/test_partial_failure.py` | role-match |
| `tests/api/test_queue_search.py` | test | API/HTMX | `tests/api/test_run_trigger.py` | exact |
| `tests/api/test_queue_signals.py` | test | API/HTMX | `tests/api/test_run_trigger.py` | exact |
| `tests/api/test_queue_excluded.py` | test | API/HTMX | `tests/api/test_run_trigger.py` | exact |
| `tests/api/test_listing_events.py` | test | API/HTMX | `tests/api/test_run_trigger.py` | exact |
| `tests/api/test_searches_crud.py` | test | API | `tests/api/test_run_trigger.py` | role-match |
| `tests/api/test_run_history.py` | test | API | `tests/api/test_run_trigger.py` | role-match |
| `tests/api/test_run_reason.py` | test | API | `tests/api/test_run_trigger.py` | role-match |
| `tests/api/test_merges_view.py` | test | API | `tests/api/test_run_trigger.py` | role-match |
| `tests/db/test_migration_contract.py` (EDIT) | test (guard) | schema contract | itself — add items 10–13 | exact |
| `tests/db/test_no_pii_columns.py` (EDIT) | test (guard) | schema contract | itself — extend `EXPECTED_JSON_COLUMNS` | exact |
| `tests/test_config.py` (EDIT) | test (guard) | config | itself — extend field tuples | exact |

---

## Pattern Assignments

### Pure domain modules — `app/domain/{dedup,filter,criteria,search_query,run_reason}.py` (utility, transform)

**Analog:** `app/domain/listing.py`, `app/domain/models.py`, `app/domain/sanitize.py`
**Enforced by:** `tests/test_import_discipline.py`

**Module header + purity contract** (`app/domain/listing.py:1-10`):
```python
"""Pure listing-field derivation: the functions that carry the dedup guarantee.

No I/O, no settings — every function is deterministic and unit-testable. The
normalise stage (`app/pipeline/stages.py`) composes these into a
`NormalisedListing`.
"""
```

**The import discipline every new domain module must satisfy** (`tests/test_import_discipline.py:14-16, 64-82`):
```python
FORBIDDEN_TOP_LEVEL_MODULES = frozenset(
    {"httpx", "sqlalchemy", "jobspy", "jinja2", "subprocess", "fastapi"}
)
# app/domain/** is AST-walked; any forbidden import fails the suite.
# `rapidfuzz` is NOT forbidden → dedup scoring belongs here (and nowhere else
# touches a session).
```

**Frozen dataclasses as the domain boundary** (`app/domain/models.py:37-74`):
```python
@dataclass(frozen=True)
class NormalisedListing:
    """The canonical shape one board's raw observation collapses into."""
    canonical_url: str
    ...
    @property
    def remote_flag(self) -> bool | None:
        """The DB column name for `is_remote`."""
        return self.is_remote
```
`app/domain/filter.py` must mirror this: frozen `RuleSpec`, `ListingFacts`, `RuleOutcome`
— **pure dataclasses, never the ORM `FilterRule` row** (RESEARCH Q4, lines 419-464).

**Pure inputs already available to reuse (do not re-derive)** (`app/domain/listing.py`):
- `normalise_company_name` — `listing.py:67-74` (casefold, strip punctuation + `LEGAL_SUFFIXES:24-43`)
- `blocking_key` — `listing.py:77-82` (`f"{company_norm}|{' '.join(sorted(title_tokens))}"[:255]`)
- `annualise_salary` — `listing.py:225-249` (interval→annual multiplier; unknown interval passes through)
- `content_hash` — `listing.py:169-182` (raw `_digest:164-166`)
- `normalise_title`/`normalise_location`/`collapse_whitespace` — `listing.py:46-64`

**Total-function / never-raise shape to copy** (`app/domain/sanitize.py:104-125, 141-143`):
```python
def strip_pii(value: str) -> tuple[str, int, int]:
    if not value:
        return "", 0, 0
    ...
def looks_like_instructions(value: str) -> bool:
    if not value:
        return False
    lowered = value.casefold()
    return any(marker in lowered for marker in INSTRUCTION_MARKERS)

def sanitize_text(value: str | None, *, max_chars: int) -> SanitisedText:
    if not value:
        return SanitisedText("", SanitizeReport())
```
`build_match_expression()` (`search_query.py`), `evaluate()` (`filter.py`) and
`compute_empty_reason()` (`run_reason.py`) must each satisfy this contract: a
malformed/empty input degrades to a recorded outcome, never an exception
(RESEARCH Q3/Q4/Q5, ARCHITECTURE §12 Pattern 2).

**`__all__` at the foot of every domain module** (`listing.py:252-268`, `sanitize.py:172-183`):
```python
__all__ = [
    "ANNUAL_MULTIPLIERS",
    "annualise_salary",
    ...
]
```

**`app/domain/sanitize.py` extension (D-38)** — extend the existing flag seam, do
not copy Resume-Matcher's redaction (`sanitize.py:38-51, 121-125`, RESEARCH Q6 L595-627):
```python
#: Imperative / system-style markers that suggest injected instructions.
#: Phase 1 only *flags* them; the full rule catalogue is Phase 2.
INSTRUCTION_MARKERS = (...)
```
Add `INJECTION_PATTERNS: tuple[re.Pattern[str], ...]` (8 compiled regexes) plus a
`patterns_matched: int` on `SanitizeReport` (`sanitize.py:54-71`), keeping
`instruction_like` as the boolean so Phase-1 callers are untouched. **Flag-and-count,
never mutate** — a redaction changes `content_hash` (`listing.py:169-182`) and breaks
repost detection. Apache-2.0 §4 attribution goes in the `.py` comment, **never** in a
template (a bare `http://` URL in a template fails `tests/test_no_cdn.py:28`).

**`app/domain/run_reason.py` shape** — the pure-signal pattern from
`app/probe/survival.py:99-128` (a `Thresholds` snapshot read from settings) recurs here
as a `RunCounts` input; `compute_empty_reason()` is the deterministic precedence
function from RESEARCH Q5 (L524-538).

---

### Repositories — `app/db/repositories/{search,run,event,exclusion,dupe,queue,state}_repo.py` (repository, CRUD/read)

**Primary analog:** `app/db/repositories/source_repo.py` (read-model + write shape)
**Secondary analog:** `app/db/repositories/listing_repo.py` (upsert / SAVEPOINT)

**Module docstring explains the boundary** (`source_repo.py:1-19`):
```python
"""Source repository — the probe write path and the per-source health read model.
...
Nothing here imports `app.probe`: the status vocabulary is validated locally and
enforced by the `ck_sources_health` CHECK constraint.
"""
```

**Import + explicit-`AsyncSession` signature — the contract** (`source_repo.py:21-33, 124-131`):
```python
from __future__ import annotations
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Listing, ListingSource, Run, Source
from app.sources import registry
```
Every function takes `session: AsyncSession` **explicitly as the first positional arg**,
never commits (the caller owns the commit), and `await session.flush()` at the end.
Examples: `enabled_source_names` (`source_repo.py:124-131`), `record_probe_result:177-201`,
`record_baseline` (`survival.py:698-720`).

**Read model = frozen dataclass + deterministic ordering** (`source_repo.py:58-68, 204-215`):
```python
@dataclass(frozen=True)
class SourceHealth:
    """One row of the per-source health strip (SRC-07 / D-13)."""
    name: str
    enabled: bool
    health: str | None
    ...
def get_source_health(session: AsyncSession) -> list[SourceHealth]:
    sources = (await session.execute(select(Source).order_by(Source.name))).scalars().all()
    runs = (await session.execute(
        select(Run).order_by(Run.started_at.desc(), Run.id.desc()).limit(RECENT_RUN_LIMIT)
    )).scalars().all()
```
Copy this for `Run` history (`run_repo.py`), the queue read model (`queue_repo.py`),
and the merges list (`dupe_repo.py`). **Always append the unique tie-break** —
`run_repo`/`queue_repo` order must end `..., l.id DESC` (RESEARCH Q3 Finding 1).

**Idempotent write + SAVEPOINT-around-a-race** (`source_repo.py:143-174`, `listing_repo.py:213-229`):
```python
try:
    async with session.begin_nested():
        session.add_all(...)
except IntegrityError:
    # A concurrent seeder won the race; the rows now exist, which is the goal.
    return []
```
`dupe_repo.apply_merge` and `event_repo.append` must write inside the caller's
transaction; the fallible insert is wrapped in `begin_nested()` so one bad row
cannot poison the run (Pattern 2 / PITFALLS P10).

**Negative-memory pre-check belongs in `dupe_repo`** (RESEARCH Q1 L234-246):
```python
# Skip any candidate pair with a reverted listing_dupes row in EITHER orientation.
# UNIQUE(listing_id, dup_listing_id) (0002) alone does NOT stop the reversed pair.
```

**Fill-blanks-not-overwrite loop to reuse for the merge** (`listing_repo.py:37-60, 112-126`):
```python
_LISTING_FIELDS = ("apply_url", "title_norm", ...)  # deliberately omits title/company_id/canonical_url
for field in _LISTING_FIELDS:
    value = _value(norm, field)
    if value is not None:
        setattr(row, field, value)
```
D-27 extends this with an **empty-string-is-a-blank** rule (the existing loop treats
`None` only). Merge field-fills must go through the **`listings` ORM row**, never raw
SQL, so the `listings_au` FTS trigger fires (PITFALL 10).

**FTS `MATCH` — bound parameter only** (`tests/db/test_fts_triggers.py:39-45`):
```python
result = await session.execute(
    text("SELECT rowid FROM listing_fts WHERE listing_fts MATCH :term"),
    {"term": term},
)
```
`queue_repo.py` owns the verified query from RESEARCH Q3 (L1087-1103) verbatim:
```sql
SELECT l.id, l.title, bm25(listing_fts, 10.0, 5.0, 1.0) AS score
FROM listing_fts JOIN listings l ON l.id = listing_fts.rowid
WHERE listing_fts MATCH :match_expression AND l.is_active = 1
ORDER BY score, l.id DESC LIMIT :limit OFFSET :offset
```
The **no-query branch must not join `listing_fts`** and keeps
`ORDER BY l.first_seen_at DESC, l.id DESC` (D-42 / Phase-1 pin). Add a module
docstring naming the Postgres `tsvector`+GIN substitution (RESEARCH Q3 L412-415).

---

### Pipeline stages — `app/pipeline/{dedup_stage,filter_stage}.py` (service, batch)

**Analog:** `app/pipeline/stages.py` (`Stage` protocol + `StageCounts`) and the
stage placement inside `app/pipeline/run.py`.

**Reuse — do not invent a second counter type** (`stages.py:30-57`):
```python
@dataclass
class StageCounts:
    """Per-stage counters that are written into `runs.source_counts_json`."""
    counts: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    def bump(self, key: str, amount: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + amount
    def fail(self, message: str) -> None:
        self.errors.append(message)

@dataclass(frozen=True)
class StageResult:
    name: str
    counts: dict[str, int]
    errors: list[str]

@runtime_checkable
class Stage(Protocol):
    name: str
    async def run(self, payload: object) -> StageResult: ...
```

**Pure-decision / impure-write split** (`stages.py:60-115` `normalise_listing` is pure;
the stage owns the session) — RESEARCH Pattern 1 (L906-918):
```python
# app/pipeline/dedup_stage.py — the stage owns ORM + session; the decision is pure
outcomes = merge_plan(candidates, threshold=settings.dedup_fuzzy_threshold)
for plan in outcomes:
    await apply_merge(session, plan=plan, now=now, run_id=run_id)
```

**Stage placement + the two counters to fix** (`run.py:252-352`):
```python
# after the per-source _persist_result loop (run.py:307-309), before _finish (run.py:338)
results: list[FetchResult] = []
for result, capability_warnings in fetched:
    errors.extend(capability_warnings)          # run.py:305 — D-37 surface
    results.append(result)
    source_counts[result.source] = await _persist_result(...)
```
`_finish` (`run.py:231-249`) currently sets `deduped_count = created` (line 248) — this
must be repurposed to "rows absorbed by a merge" and gain `filtered_count`, `reason`,
`reason_counts_json`, `stage_log_json`, `criteria_snapshot_json` (RUN-03/D-33/D-44).
Do **not** create a new status value: `NO_SOURCES_REASON` (`run.py:47-51`) is the
existing `no_sources_enabled` vocabulary to recognise, not replace.

**Stage order is fixed** (RESEARCH Q4 L511-517): fetch → sanitise → normalise →
**dedup/merge** → **hard filter** → cap. Filtering or capping before merging discards
the copy that carried the salary (anti-pattern AP4).

**Capability-warning consumption** (`run.py:107-132`, `app/sources/base.py:236-296`):
```python
compiled = compile_query_for_source(query, adapter.capabilities, source=adapter.name)
warnings: list[dict[str, Any]] = [
    {"source": adapter.name, "status": "warning",
     "error": f"filter not applied: {warning.filter_name} — {warning.reason}"}
    for warning in compiled.warnings
]
```
Phase 2 additionally persists these into `runs.stage_log_json` under a
`{"stage": "criteria_compile", "warnings": [...]}` entry (RESEARCH Q8 L720-728).

---

### Migration — `alembic/versions/0002_*.py` (migration, batch DDL)

**Analog:** `alembic/versions/0001_initial_schema.py`

**Revision header + one-way doctrine** (`0001:1-31`):
```python
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None
```
0002 is `revision = "0002"`, `down_revision = "0001"`. Alembic runs on the **sync**
driver (`tests/conftest.py:47-57`), so `upgrade()` is plain synchronous code — no
`run_sync`, no async engine.

**`create_table` shape + named CHECK + `server_default` convention**
(`0001:38-59, 71-105`):
```python
op.create_table(
    "sources",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("1")),
    sa.UniqueConstraint("name", name="uq_sources_name"),
    sa.CheckConstraint(
        "health IS NULL OR health IN ('ok','degraded','unreachable')",
        name="ck_sources_health",
    ),
)
```
Copy for the new `filter_rules` (named CHECK on `kind` + `sa.UniqueConstraint` style)
and `queue_state` tables. `server_default=sa.text("1")` for booleans, `sa.text("0")`
for `is_default` (`0001:76`). **Name every CHECK explicitly** (`models.py:1-6`).

**`op.add_column` for new columns** — nullable in-place ALTER (RESEARCH Q2 L270-279):
`runs.reason`, `runs.reason_counts_json`, `runs.stage_log_json`,
`runs.criteria_snapshot_json`, `listing_exclusions.criteria_version`.
Adding a CHECK/UNIQUE/NOT-NULL needs `op.batch_alter_table(...)` (the env already sets
`render_as_batch=True`, `alembic/env.py:38-71`).

**Index creation pattern** (`0001:387-414`):
```python
op.create_index("ix_listings_blocking_key", "listings", ["blocking_key"])
```
Add `UNIQUE(listing_id, dup_listing_id)` + `ix_listing_dupes_dup_listing_id`.

**Do NOT touch** the append-only triggers (`0001:343-350`) or the FTS5 objects
(`0001:355-380`) — they are correct and recreating `listing_fts` risks divergence
(RESEARCH Q2 L332-336).

**`downgrade()`** follows the drop-in-reverse shape (`0001:417-458`).

---

### Models — `app/db/models.py` (EXTEND) (model, CRUD)

**Mirror every 0002 object/column in the ORM** (contract test reads the DB, not the
ORM, so drift is a silent application bug — RESEARCH Q2 item 4 L328-330).
Copy the exact column conventions from the neighbors:
- `ListingDupe` (`models.py:152-165`) — extend its `__table_args__` with the UNIQUE index.
- `ListingExclusion` (`models.py:189-200`) — add `criteria_version`.
- `Search` (`models.py:203-217`) already has `enabled`, `is_default`, `criteria_json`,
  `version`, `last_run_at` — **no new column needed for CRIT-03**.
- `Run` (`models.py:220-249`) — add the four new columns inside the existing
  `__table_args__` block that names `ck_runs_trigger`/`ck_runs_status`.
- New `FilterRule` + `QueueState` classes follow `Source`/`Company` (`models.py:29-69`).

`sa.String` + explicitly-named `CheckConstraint`, **never `sa.Enum`** (`models.py:1-6`).

---

### Routes — `app/api/events.py`, `app/api/searches.py` (NEW); `app/api/runs.py` (EXTEND); `app/web/routes.py` (EXTEND)

**Analog:** `app/api/runs.py` (fragment routes + 286 stop) and `app/web/routes.py`.

**Router + templates boilerplate** (`runs.py:30-33`, `web/routes.py:30-33`):
```python
router = APIRouter()
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
```

**The auth seam on EVERY route** (`runs.py:45-51`, `web/routes.py:55-61`,
`health.py:53-59`):
```python
@router.post("/runs", response_class=HTMLResponse)
async def start_run(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> HTMLResponse:
```
`tests/test_auth_seam.py:87-98` fails any new route without `Depends(current_user)`.
`EXPECTED_SEAM_ROUTES` (`test_auth_seam.py:31`) is a **subset** assertion — it does not
need editing when routes are added, but every added route must carry the seam.

**POST route returns a fragment immediately; never awaits the pipeline** (`runs.py:45-71`):
```python
task = asyncio.create_task(run_pipeline("manual", None, session_factory, run_id=run.id))
_BACKGROUND_TASKS.add(task)
task.add_done_callback(_BACKGROUND_TASKS.discard)
return HTMLResponse(render_run_fragment(request, run, None), status_code=202)
```

**Polling stop = HTTP 286 + `HX-Reswap: outerHTML`** (`runs.py:88-93`):
```python
if run.status in TERMINAL_STATUSES:
    return HTMLResponse(fragment, status_code=286, headers={"HX-Reswap": "outerHTML"})
return HTMLResponse(fragment)
```

**`render_run_fragment` reuse for the last-run strip** (`runs.py:40-42`) — D-43 says the
queue strip reuses this renderer rather than a parallel one.

**Route becomes thin once the repository owns the query** — replace the inline query
(`web/routes.py:67-73`) with a `queue_repo` call; keep the `_health_strip` degradation
wrapper (`web/routes.py:36-52`) as the model for any decorative data.

**Register new routers in `app/main.py:46-57`** via `app.include_router(...)`.

---

### Templates — `queue.html` (EXTEND), new `queue_list.html`, `_listing_row.html`, `criteria.html`, `runs.html`, `merges.html`

**Analog:** `app/web/templates/html/{base,queue,_run_status,_health_strip}.html`

**Page template shell** (`queue.html:1-5`):
```jinja
{% extends "html/base.html" %}
{% block title %}Queue · Job Search Copilot{% endblock %}
{% block content %}
```
**Partial shell** (`_run_status.html:1-4`) — root element carries the htmx attributes:
```html
<div id="run-status"
     hx-get="/runs/{{ run.id }}/status"
     hx-trigger="every 2s"
     hx-swap="outerHTML">
```

**Action controls** (`queue.html:7-14`):
```html
<button type="button"
        id="run-search-now"
        hx-post="/runs"
        hx-target="#run-status-slot"
        hx-swap="innerHTML">
  Run search now
</button>
<div id="run-status-slot"></div>
```
Per-row save/hide must add a stable id — `id="listing-row-{{ listing.id }}"` — the
current queue table has no per-row id (RESEARCH Q7 L680-683).

**Jinja autoescape, no `|safe` on listing text, no CDN** (`base.html:5-11`,
`tests/test_no_cdn.py:28`). Rule-kind field visibility comes from Alpine `x-data`/
`x-show` or server-rendered blocks per kind — **never** `{{ ... }}` in a logic position
(D-34).

**Pinned IDs the Phase-1 e2e asserts** (`tests/api/test_run_trigger.py:160-167`):
`'hx-post="/runs"'`, `'id="run-status-slot"'`, `"0 listings"`, `"No listings yet"` —
keep them when extending `queue.html`, or update that test deliberately.

**The template count element** (`queue.html:19`) `{{ count }} listing{% if count != 1 %}s{% endif %}`
is what renders `"0 listings"`; `queue_list.html` must preserve it.

---

### Settings — `app/config.py` (EXTEND), `pyproject.toml` / `requirements.txt` (EXTEND)

**Analog:** `app/config.py:13-78` + `thresholds()` in `app/probe/survival.py:115-128`.

**Add fields to the single `Settings` class** (`config.py:13-21, 42-57`):
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", ..., extra="ignore")
    ...
    probe_max_requests: int = 2
```
New: `dedup_fuzzy_threshold` (int 0–100, high-80s/low-90s default),
`dedup_posted_window_days`, `stale_after_days` (default ~14), `queue_page_size`.
**Defaults belong in `Settings`** or `tests/test_config.py:130-162`'s distinctive-literal
scan over `app/pipeline` fails (RESEARCH Q2 item 3).

**Settings-reader pattern** — dataclass snapshot read per call, never a module constant
(`survival.py:99-128`):
```python
@dataclass(frozen=True)
class Thresholds:
    fill_warn_points: int
    ...
def thresholds() -> Thresholds:
    """Read every boundary from `Settings` on each call — never from a literal."""
    return Thresholds(
        fill_warn_points=settings.probe_fill_rate_warn_drop_points,
        ...
    )
```
`dedup_stage`/`filter_stage` read θ and `stale_after_days` this way.

**Dependency pin** — add `rapidfuzz==3.14.6` to `[project].dependencies`
(`pyproject.toml:13-30`) and mirror it in `requirements.txt` (`requirements.txt:1-20`
documents "mirrors `[project].dependencies` exactly (D-17)"). Exact pins only — no
floating ranges (`pyproject.toml:11-12`). The `rapidfuzz` package-legitimacy verdict is
**SUS**, so the install task is gated by `checkpoint:human-verify` (RESEARCH L794-813).

---

### Tests — unit lane (`tests/domain/`), DB lane (`tests/db/`), pipeline lane (`tests/pipeline/`), API lane (`tests/api/`)

**Analog:** `tests/conftest.py` fixtures + the closest existing lane file.

**Fixtures — reuse unchanged (no harness change needed)** (`conftest.py:59-136`):
`migrated_db` (session-scoped template auto-migrates to 0002), `db_engine`,
`session_factory`, `db_session`, `client` (both session overrides + `OfflineLLMBackend`),
`registry_snapshot`.

**Pure domain unit test** (mirror `tests/domain/test_normalize.py` — direct function
calls, no DB) — the Wave-0 gaps in RESEARCH L1333-1349.

**DB repository test** — manual session + explicit commit (`test_two_key_upsert.py:47-74`):
```python
async def test_same_source_listing_id_upserts_one_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_source(session_factory)
    async with session_factory() as session:
        created = await upsert_listing_source(session, ..., now=first_seen)
        await session.commit()
```

**Append-only event test** — reuse the abort assertions
(`test_migration_contract.py:104-126`): an `UPDATE`/`DELETE` on `listing_events` must
raise `sqlite3.IntegrityError` with `"append-only"` in the message.

**API/HTMX fragment test** — `client.get("/")` / `client.post("/runs")`, assert the
response text carries the pinned ids (`test_run_trigger.py:97-119, 160-167`).

### Guard tests — the three mandatory edits (Q2)

**`tests/db/test_migration_contract.py:257-283`** — `test_alembic_at_revision_0001`
asserts `versions == ["0001"]` (L267) and `head_lines[0].startswith("0001")` (L278).
Both become `"0002"`; rename to `test_alembic_at_latest_revision`; reword the module
docstring (L1-11). **Add** items 10–13 via the existing introspection helpers
(`_table_info:36-38`, `_index_list:41-43`, `_master:51-57`). The Dockerfile assertion
(L280-283) is unchanged.

**`tests/db/test_no_pii_columns.py:30-58`** — `EXPECTED_JSON_COLUMNS` is compared by
**exact equality** against discovered JSON columns (L110-117). Add
`"filter_rules": frozenset({"params_json"})` and the three new `runs` JSON columns.
`queue_state` has **no** JSON column → must **not** appear (empty entries are dropped
on both sides, L110-114).

**`tests/test_config.py:28-50`** — add the new required fields to
`REQUIRED_SETTINGS_FIELDS` and the new ceilings to `LIMIT_FIELDS` so the
distinctive-literal scan (L121-162) actually covers them.

---

## Shared Patterns

### Pure decision / impure write split (D-24)
**Source:** `app/domain/listing.py:1-10`; `tests/test_import_discipline.py:14-16, 64-82`.
**Apply to:** every new `app/domain/*.py`, every new repository.

```python
FORBIDDEN_TOP_LEVEL_MODULES = frozenset(
    {"httpx", "sqlalchemy", "jobspy", "jinja2", "subprocess", "fastapi"}
)
# The domain decides; only a repository touches the session.
```

### Total functions at the boundary (Pattern 2 / PITFALLS P10)
**Source:** `app/domain/sanitize.py:104-125, 141-143`; `app/sources/base.py:120-129,145-187`.
**Apply to:** `build_match_expression`, `evaluate`, `compute_empty_reason`, every repo read.

```python
def strip_pii(value: str) -> tuple[str, int, int]:
    if not value:
        return "", 0, 0
```
A malformed rule / hostile FTS string / empty corpus degrades to a recorded outcome —
never raises. **`build_match_expression` returning `None` is the D-42 no-query branch.**

### App-level append-only event log (QUEUE-08)
**Source:** `alembic/versions/0001_initial_schema.py:343-350`; `app/db/models.py:168-186`.
**Apply to:** `event_repo.py`, save/hide routes and partials.

```sql
CREATE TRIGGER listing_events_no_update BEFORE UPDATE ON listing_events
BEGIN SELECT RAISE(ABORT, 'listing_events is append-only'); END;
```
Current state is **projected from the latest event**, never a mutable `is_hidden` column.

### Auth seam proven universal (D-21)
**Source:** `app/api/deps.py:16-22`; `tests/test_auth_seam.py:87-98`.
**Apply to:** every route in `app/api/events.py`, `app/api/searches.py`, and the
extended `app/api/runs.py` / `app/web/routes.py`.

```python
async def current_user() -> User:
    return LOCAL_USER
# Every route: `user: User = Depends(current_user)`. Adding Authentik changes
# only this body — route signatures never change.
```

### HTMX 286 polling stop (UI-06)
**Source:** `app/api/runs.py:88-93`; `app/web/templates/html/_run_status.html:1-4`.
**Apply to:** every polling fragment, including the `/runs` page and the run strip.

```python
if run.status in TERMINAL_STATUSES:
    return HTMLResponse(fragment, status_code=286, headers={"HX-Reswap": "outerHTML"})
```

### PII unrepresentable (SRC-10, extended to `detail_json`)
**Source:** `app/domain/sanitize.py:8-10, 104-112`; `tests/db/test_no_pii_columns.py:30-58`.
**Apply to:** `filter.py` `RuleOutcome.detail`, the injection log, every new JSON column.

`detail_json` carries **terms, field names and counts only — never a description
snippet** (a snippet can carry a recruiter name). The injection rule records a count,
never the matched text. PII is **dropped, never hashed**.

### Migration is the schema test (P8/M8)
**Source:** `tests/db/test_migration_contract.py:1-11, 36-64`.
**Apply to:** migration 0002 + models.py, in the same task.

Every 0002 acceptance item is asserted by `PRAGMA table_info` / `index_list` /
`sqlite_master` against the **migrated** DB — never ORM metadata.

### Config, not constants (PLAT-04)
**Source:** `app/config.py:13-78`; `app/probe/survival.py:115-128`; `tests/test_config.py:121-162`.
**Apply to:** θ, `stale_after_days`, `queue_page_size`, every filter boundary.

```python
def thresholds() -> Thresholds:
    """Read every boundary from `Settings` on each call — never from a literal."""
    return Thresholds(fill_warn_points=settings.probe_fill_rate_warn_drop_points, ...)
```

### Bound-parameter FTS discipline (M4)
**Source:** `tests/db/test_fts_triggers.py:39-45`.
**Apply to:** `queue_repo.py` — `MATCH :match_expression`, never an f-string.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `rapidfuzz==3.14.6` pin in `pyproject.toml`/`requirements.txt` | dependency | — | No third-party fuzzy-match dependency exists yet. **Not a gap**: the exact-pin convention (`pyproject.toml:11-12`) supplies the shape; the install is gated by `checkpoint:human-verify` (SUS verdict, RESEARCH L794-813). |
| `app/domain/criteria.py` (the `SearchQuery` assembler) | utility (pure domain) | transform | No existing pure module composes settings+caps into `SearchQuery`; nearest analog is `app/sources/base.py:64-79` (`SearchQuery` itself) + `compile_query_for_source` (`base.py:236-296`). Planner should treat `base.py` as the interface contract. |

Everything else has an in-repo analog from migration 0001 / Phase 1.

---

## Metadata

**Analog search scope:** `/workspace/job-search` — `app/`, `alembic/`, `tests/`,
`pyproject.toml`, `requirements.txt`. Every cited analog verified git-tracked via
`git ls-files -- <path>` (non-empty). No gitignored mirror paths used
(`.gsd/`, `.venv*/`, `data/`, `pytest-of-unknown/` were excluded from the search).
**Files scanned:** read 24 analog files in full plus targeted reads of the guard tests
and teardown shapes.
**Pattern sources (tracked):**
- `app/db/repositories/source_repo.py` (271), `listing_repo.py` (231)
- `app/domain/listing.py` (268), `sanitize.py` (183), `models.py` (87)
- `app/pipeline/run.py` (362), `stages.py` (136)
- `alembic/versions/0001_initial_schema.py` (458)
- `app/db/models.py` (418), `app/db/session.py` (69)
- `app/web/routes.py` (114), `app/web/templates/html/*` (4 files)
- `app/api/runs.py` (96), `health.py` (115), `deps.py` (22)
- `app/sources/base.py` (327), `registry.py` (78)
- `app/config.py` (78), `app/probe/survival.py` (761), `app/ingest/sanitize.py` (87)
- `tests/conftest.py` (150), `tests/api/test_run_trigger.py` (173),
  `tests/db/test_two_key_upsert.py` (197), `tests/db/test_fts_triggers.py` (123),
  `tests/db/test_migration_contract.py` (283), `tests/db/test_no_pii_columns.py` (122),
  `tests/test_config.py` (181), `tests/test_auth_seam.py` (154),
  `tests/test_import_discipline.py` (86), `tests/test_no_credentials.py` (306),
  `tests/test_no_cdn.py` (109)
**Cross-phase conventions read:** `.planning/phases/01-walking-skeleton-foundations/01-PATTERNS.md:832-934`
(Shared Patterns to follow unchanged).
**Pattern extraction date:** 2026-09-16
**Coverage:** 46 files classified; 44 with an in-repo analog; 2 mapped to the
exact-pin convention (no behavioral analog needed).
