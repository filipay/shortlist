# Phase 5: Ranking — CORE VALUE - Pattern Map

**Mapped:** 2026-09-22
**Files analyzed:** 24 (11 new/modified app files, 8 new tests, 5 modified guards/config)
**Analogs found:** 21 / 24 (3 with only partial/role-match analogs)

> This phase is **assembly over existing seams**, not new infrastructure. Every
> pattern below is copied from tracked source in this repo; consult the named
> analog before writing the file. Two RESEARCH corrections override CONTEXT and
> are baked into the assignments: (1) `llm_calls.created_at` is **not** indexed;
> (2) `llm_calls` has **no `error_kind` column** — encode the cause in `error`.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/domain/rubric.py` | domain (pure constants + arithmetic) | transform | `app/domain/run_reason.py` | exact |
| `app/domain/schemas/ranking.py` | domain schema | transform | `app/domain/schemas/probe.py` | exact |
| `app/db/repositories/score_repo.py` | repository | CRUD (upsert + read) | `app/db/repositories/llm_call_repo.py` + `listing_repo.py` | role-match (composite) |
| `app/pipeline/rank.py` | pipeline service | request-response + event-driven (detached) | `app/pipeline/filter_stage.py` + `app/api/runs.py` | role-match (composite) |
| `app/api/listings.py` | controller (route) | request-response | `app/api/events.py` | exact |
| `app/web/templates/html/listing_detail.html` | template (full page) | request-response | `app/web/templates/html/settings.html` | role-match |
| `app/web/templates/html/_weights_form.html` (or macro) | template (fragment + macro) | request-response | `app/web/templates/html/criteria.html` | exact |
| `alembic/versions/0004_ranking_config.py` | migration | file-I/O (schema) | `alembic/versions/0003_llm_call_server_version.py` | role-match |
| `tests/domain/test_rubric.py` | test (unit, pure) | transform | `tests/domain/test_run_reason.py` | exact |
| `tests/db/test_score_repo.py` | test (integration DB) | CRUD | `tests/db/test_llm_call_repo.py` | exact |
| `tests/pipeline/test_rank_stage.py` | test (pipeline) | request-response | `tests/pipeline/test_filter_stage.py` | exact |
| `tests/pipeline/test_rank_caps.py` | test (pipeline) | event-driven | `tests/pipeline/test_finish_llm_counters.py` | role-match |
| `tests/pipeline/test_rank_optional.py` | test (pipeline) | request-response | `tests/pipeline/test_finish_llm_counters.py` | role-match |
| `tests/api/test_queue_ranked.py` | test (API) | request-response | `tests/api/test_queue_excluded.py` | role-match |
| `tests/api/test_listing_detail.py` | test (API) | request-response | `tests/api/test_listing_events.py` | exact |
| `tests/api/test_ranking_weights.py` | test (API) | request-response | `tests/api/test_settings_page.py` | role-match |
| `app/pipeline/run.py` (mod) | pipeline runner | request-response | itself (`_finish` seam, L614-623) | exact |
| `app/db/repositories/llm_call_repo.py` (mod) | repository | CRUD read | itself (`llm_totals_for_run`, L185-205) | exact |
| `app/db/repositories/queue_repo.py` (mod) | repository read model | CRUD read | itself (`read_queue`/`_enrich`, L315-544) | exact |
| `app/api/settings.py` (mod) | controller (form route) | request-response | `app/api/searches.py` (form/fragment) | exact |
| `app/config.py` (mod) | config | transform | itself (Phase 4 block, L129-170) | exact |
| `tests/test_config.py` (mod) | test (guard) | transform | itself (`REQUIRED_SETTINGS_FIELDS`/`LIMIT_FIELDS`) | exact |
| `tests/test_auth_seam.py` (mod) | test (guard) | transform | itself (`EXPECTED_SEAM_ROUTES`, L31-41) | exact |
| `tests/pipeline/test_finish_llm_counters.py` + `test_filter_stage.py` (mod) | test (guard) | transform | itself (D-102 rewrite) | exact |

---

## Pattern Assignments

### `app/domain/rubric.py` (domain, transform)

**Analog:** `app/domain/run_reason.py`

This is the closest possible match: a pure, I/O-free domain module exposing a
frozen tuple of named enum values, a `RUBRIC_VERSION`-style constant, and pure
arithmetic over them. `run_reason.py` is the precedent for "persist the
decomposition, compute the aggregate" — exactly D-78/D-79's shape.

**Purity contract + module docstring pattern** (lines 1-27): the docstring states
"Pure: standard library only, no I/O, no `Settings`, no LLM." `tests/test_import_discipline.py` (L14-16, L65-83) enforces no `httpx`/`sqlalchemy`/`jinja2`/`fastapi`/`subprocess` imports anywhere under `app/domain`. `rubric.py` must not import `Settings` either (D-24).

**Named-value constant pattern** (lines 34-41):
```python
#: The reason enum, in **precedence order**. ... Mirrored by the named
#: `ck_runs_reason` CHECK ... keep this the single in-code source.
REASONS: tuple[str, ...] = (
    "no_sources_enabled",
    "all_sources_failed",
    ...
)
```
Copy this for the six factor keys (D-82):
```python
FACTORS: tuple[str, ...] = ("skills", "seniority", "domain", "location", "evidence", "compensation")
RUBRIC_VERSION = "v1"          # D-80: hand-bumped, never content-hashed
```

**Pure typed-input dataclass pattern** (lines 48-65): `RunCounts` is a frozen
dataclass carrying the decomposition. Mirror it if the rubric needs a typed input
(e.g. a `FactorScores` mapping wrapper) — but a plain
`dict[str, float]`/`Mapping` input is equally consistent with `compute_empty_reason`'s
signature.

**Pure decision function pattern** (lines 77-138): `compute_empty_reason(counts) -> str`
is total and branch-documented. `weighted_total()` follows this exact shape —
pure, total, documented, returning a sentinel rather than raising:
```python
def weighted_total(sub_scores: dict[str, float], weights: dict[str, float]) -> float | None:
    """Normalised weighted mean over PRESENT factors. None when none are present."""
    present = [(weights[f], s) for f, s in sub_scores.items() if f in weights and s is not None]
    denom = sum(w for w, _ in present)
    if denom <= 0:
        return None                       # Pitfall 6a: never a ZeroDivisionError
    return sum(w * s for w, s in present) / denom
```
Same 15-line, no-numpy approach RESEARCH §Don't Hand-Roll mandates.

**`__all__` at the foot** (lines 179-184): every domain module ends with an explicit
`__all__`; copy it (`FACTORS`, `RUBRIC_VERSION`, `FACTOR_LABELS`, `weighted_total`, `tier`).

> **Never re-read this analog:** it is 184 lines; one pass is enough.

---

### `app/domain/schemas/ranking.py` (domain schema, transform)

**Analog:** `app/domain/schemas/probe.py`

The probe schema is the precedent for a schema-constrained response model. Two
rules it encodes are load-bearing here:

**Every field has a default, `extra="ignore"`** (lines 22-31):
```python
class ProbeResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    acknowledged: bool = False
    instruction_detected: bool = False
    echo: str = ""
```
The port's salvage path substitutes defaults only for `ValidationError`s whose
`loc` length is 1 **and** whose type is in `TOLERATED_SCHEMA_ERRORS =
frozenset({"missing", "int_parsing"})` (`opencode_server.py:93, 673-687`). A
**nested** error re-raises as `invalid`. Therefore (RESEARCH Pattern 1) the
ranking schema MUST use **top-level scalars**, one per factor:

```python
class RankingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    skills: float = -1.0        # -1.0 sentinel = "factor absent" (D-85), distinct from 0.0
    seniority: float = -1.0
    domain: float = -1.0
    location: float = -1.0
    evidence: float = -1.0
    compensation: float = -1.0
    rationale: str = ""
    requirements: list[RequirementFit] = Field(default_factory=list)

class RequirementFit(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str = ""
    verdict: Literal["met", "partial", "gap"] = "gap"
    evidence_id: str | None = None
```
- Bound floats with `Annotated[float, Field(ge=0.0, le=1.0)]` — out-of-range must be rejected, not clamped (RESEARCH Pattern 1).
- A bad `Literal` verdict is **not** tolerated, so it re-raises → `invalid` → D-95's no-score path. That is correct.
- `evidence_id` values are `cv.yaml` fact IDs from `iter_fact_ids()` (`app/domain/cv.py:306-321`), i.e. `bul/...`, `exp/...`, `sec/...`.

---

### `app/db/repositories/score_repo.py` (repository, CRUD)

**Analogs:** `app/db/repositories/llm_call_repo.py` (house rules) + `app/db/repositories/listing_repo.py` (upsert mechanics)

**Repository house rules** (`llm_call_repo.py:1-25`): repositories are the **only**
place SQL lives; they take an `AsyncSession` explicitly and **never commit** (the
caller owns the single commit); writes are wrapped in a SAVEPOINT
(`session.begin_nested()`) so a failure cannot poison the caller's transaction;
`now` is injectable. Every repository opens with this docstring block — copy it.

**Frozen read-value + mapping pattern** (lines 47-66, 136-154): `LlmCallRecord` is a
frozen dataclass and `_to_record(row)` is the single ORM→value mapping. Mirror with
a `ScoreRecord` dataclass and `_to_record`.

**Vocabulary validated before SQL** (lines 95-98): validate `confidence_tier`
against `{"high","medium","low"}` before issuing SQL, raising a clear `ValueError`
rather than a raw `IntegrityError`.

**Tolerant reads** (lines 157-162, 185-205): `_tolerant_int` maps NULL/unusable to 0;
reads never raise because a page must still render. Copy the same tolerance for
`factor_scores_json`/`weights_json` (a dict or `{}`, never raising — see
`run_repo._mapping` at `run_repo.py:55-57`).

**Upsert — `sqlite_on_conflict_do_update`** (RESEARCH §Code Examples; enforced by
`uq_scores_listing_run_criteria`, `models.py:346-349`):
```python
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
stmt = sqlite_insert(Score).values(**values).on_conflict_do_update(
    index_elements=["listing_id", "run_id", "criteria_version"],   # the uq columns
    set_={...},
)
```
**The `criteria_version` MUST be non-NULL** (Pitfall 5): SQLite treats NULLs as
distinct, so a NULL silently defeats the unique constraint. The `listing_repo`
SAVEPOINT-on-`IntegrityError` pattern (lines 213-229) is the belt-and-braces
precedent if a race is possible.

**Latest-score-per-listing read** (Pitfall 4): one score row per **run**, so the
queue read must select the newest score per listing (max `run_id`, tie-break max
`id`). Order with the repo's existing `(created_at DESC, id DESC)` convention
(`llm_call_repo.latest_probe`, L176-182; `queue_repo._latest_run_id`, L243-245).

**Name/API:** `upsert_score(session, *, listing_id, run_id, criteria_version,
sub_scores, weights, rubric_version, confidence_tier, rationale, requirements,
provider, model, agent, now) -> ScoreRecord`, `latest_for_listings(session,
listing_ids) -> dict[int, ScoreRecord]`, `read_score_for_listing(session,
listing_id) -> ScoreRecord | None`. Keep `__all__` at the foot.

---

### `app/pipeline/rank.py` (pipeline service, request-response + detached task)

**Analogs:** `app/pipeline/filter_stage.py` (stage shape + count/error contract) +
`app/api/runs.py:54-56,104-106` (detached task idiom) + `app/api/settings.py:410-464` (the LLM call construction).

**Stage shape** (`filter_stage.py`): the stage function takes
`session_factory, run_id, *, now=None` and returns `StageResult`; it builds a
`StageCounts` (`app/pipeline/stages.py:31-49`), bumps named counters, calls
`counts.fail(...)` on per-item errors and **continues** (lines 99-109, 134-141),
and commits once at the end (line 147). The stage is total — one bad listing is
logged and skipped, never aborts. Follow this exactly (D-94/D-95).

**Detached task with a strong reference** (`runs.py:54-56`):
```python
#: Strong references to in-flight run tasks, so the event loop cannot garbage
#: collect a fire-and-forget pipeline before it finishes.
_BACKGROUND_TASKS: set[asyncio.Task] = set()
```
and the enqueue (`runs.py:104-106`):
```python
task = asyncio.create_task(run_pipeline("manual", None, session_factory, run_id=run.id))
_BACKGROUND_TASKS.add(task)
task.add_done_callback(_BACKGROUND_TASKS.discard)
```
Put the set + `start_ranking_task()` in `app/pipeline/rank.py` (NOT in `app/api`,
which `run.py` must not import). Single-flight guard per RESEARCH Open Question 3:
a module-level `_RANKING_TASK: asyncio.Task | None`; if live, start-or-skip.
`# ponytail: start-or-skip single-flight, upgrade to a queue only if overlap proves real.`

**The LLM call construction** (`settings.py:410-419`): pass `schema=`, a
module-level `system` constant (no f-string — see `SELFTEST_SYSTEM_PROMPT`,
L63-67), `parts=[...]` for all untrusted content, `tools=()`,
`retries=settings.opencode_max_retries`. The route then records exactly one
`llm_calls` row via `record_llm_call` (L433-441 / L455-464). The ranking loop does
the same per listing, but calls `record_llm_call(...)` with `purpose="rank"` and
`run_id=run_id`.

**Trust boundary (§6.3 / m5 / D-38):** the listing text, CV prose and the
(deferred) user rubric override go in `parts` ONLY. `system` is a frozen module
constant; `to_message_body` has no argument that can reach it (`builders.py:55-108`).

**Cap reservation (D-92, RESEARCH §Code Examples):**
```python
_reserve_lock = asyncio.Lock()
_in_flight = 0

async def _reserve(day_total: int, run_total: int, *, cap_day: int, cap_run: int) -> bool:
    global _in_flight
    async with _reserve_lock:
        if day_total + _in_flight >= cap_day or run_total + _in_flight >= cap_run:
            return False
        _in_flight += 1
        return True
```
Release in a `finally`. A cap hit is a **graceful stop**, not an error (D-93).

**Backend injection (Pitfall 7):** `run_pipeline()` takes no backend today
(`run.py:690-698`). Thread an `llm: LLMBackend | None = None` keyword through
`run_pipeline`/`start_ranking_task` (defaulting to `get_llm_backend()`), otherwise
the test lane's `OfflineLLMBackend` override (`conftest.py:270`) never reaches it.

**Purity note:** `app/pipeline` may import `app.llm` (the port), but must never
import `httpx` or `subprocess` (`test_import_discipline.py:126-140`). The rubric
module is imported from `app.domain` — import it, do not re-declare factor keys here.

---

### `app/api/listings.py` (controller, request-response)

**Analog:** `app/api/events.py`

This is the closest existing route: a per-listing `GET`/`POST` that resolves the
listing, calls `queue_repo.read_row()`, and renders a template. Copy this file's
shape for `GET /listings/{listing_id}` (D-96).

**Router + template wiring** (lines 44-51):
```python
router = APIRouter()
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = make_templates(TEMPLATE_DIR)
```
Register the router in `app/main.py:57-62` via `app.include_router(listings_routes.router)`.

**Route signature — the auth seam is mandatory** (lines 76-82):
```python
@router.post("/listings/{listing_id}/events", response_class=HTMLResponse)
async def append_listing_event(
    listing_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
```
`tests/test_auth_seam.py:31-41` `EXPECTED_SEAM_ROUTES` must gain `"/listings/{listing_id}"`.

**`read_row` data source** (lines 126-141): the detail route reuses exactly this:
```python
query = QueueQuery(excluded=_flag(request.query_params.get("excluded")))
row = await read_row(
    session, listing_id=listing_id, query=query, now=datetime.now(UTC),
    stale_after_days=settings.stale_after_days,
    watermark=await state_repo.get_watermark(session),
)
```
`row is None` → 404. `read_row` returns the same `QueueRow` as the queue, so the
detail page and row partial cannot drift (queue_repo.py:547-571).

**404 convention** (lines 62-73, 103-112): a small HTML fragment with
`data-error="unknown-listing"` and a `status_code=404`, never a bare JSON 404.

**Detail page extras:** the route additionally loads the score
(`score_repo.read_score_for_listing`) and the latest weights (`rubric`/config) and
passes them into `listing_detail.html`. Score is a read-time `weighted_total` (D-100).

---

### `app/web/templates/html/listing_detail.html` (template, full page)

**Analogs:** `app/web/templates/html/settings.html` (full-page structure) + `_listing_row.html` (badges/actions markup)

**Page shell** (settings.html lines 1-14): `{% extends "html/base.html" %}`, a
`{% block title %}`, then `{% block content %}`. Copy it.
**Note:** autoescape is the only escaping — no `|safe` anywhere; the listing title
and rationale are untrusted. External links carry `rel="noopener noreferrer"` and
only render as anchors when `row.url` is truthy (`_listing_row.html:37`).

**Save/hide/shortlist actions** (lines 59-86): reuse the exact two-form
`hx-post="/listings/{{ row.id }}/events"` block from `_listing_row.html` — do not
re-invent it. The detail page and the row must issue the same event types.

**Badges** (`_listing_row.html:38-45`): `badge-saved`, `badge-hidden`, `badge-new`,
`badge-stale`, `badge-merged`, `badge-flagged`. Add a `confidence_tier` badge in
the same style (`badge-...`) and define its CSS rule.

**CSS coverage is mandatory:** `tests/test_stylesheet_coverage.py` extracts every
literal class token from every template and requires a rule in
`static/vendor/app.css` (or an entry in `EXEMPT_CLASSES`, L39-57). Every new class
in the detail page and weights form needs a rule. Assets stay vendored
(`tests/test_no_cdn.py`).

**Requirement breakdown rendering:** iterate the stored requirements list;
`verdict` renders as a label class (`req-met`/`req-partial`/`req-gap`), with the
evidencing `evidence_id` shown as text (never a link — it is a CV fact ID, not a URL).

---

### `app/web/templates/html/_weights_form.html` (template macro, fragment)

**Analog:** `app/web/templates/html/criteria.html` (the `criteria_list` macro) + `app/api/searches.py`

**Macro that serves page and swap** (criteria.html:263-337): the list markup lives
in `{% macro criteria_list(searches, errors=None, note=None) %}` inside the page
template, so the page and every `hx-post` swap render from ONE definition. Copy
this for the weights form: a macro returning a `<div id="ranking-weights">` root
containing six labelled number inputs + a submit button.

**Renderer pairing** (`searches.py:393-409):
```python
def render_criteria_list(searches, *, errors=None, note=None) -> str:
    module = templates.get_template(CRITERIA_TEMPLATE).make_module(
        {"searches": searches, "errors": errors, "note": note}
    )
    return str(module.criteria_list(searches=searches, errors=errors, note=note))
```
Copy as `render_weights_form(...)`.

**Form parsing helpers** (`searches.py:79-159`): `read_form()` uses stdlib
`parse_qsl` — **no `python-multipart`**. `_field`, `_checkbox`, `_int_field` are the
reusable validation helpers. For weights, parse each of the six factors as a
non-negative number and validate at the storage boundary (D-34); return the
re-rendered fragment with an error note on invalid input (the `_render_list`
pattern, L412-424).

**Route shape** (`searches.py` mutating POST): commit in the route, then
`return await _render_list(request, session, note="Weights saved.")`. The route
declares `user: User = Depends(current_user)`. **Zero LLM calls on this path**
(D-100/SC-3) — it only writes the weights document.

---

### `alembic/versions/0004_ranking_config.py` (migration)

**Analog:** `alembic/versions/0003_llm_call_server_version.py`

**Migration shape** (0003 lines 25-44):
```python
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("llm_calls", sa.Column("server_version", sa.String(32)))

def downgrade() -> None:
    op.drop_column("llm_calls", "server_version")
```
- A new table (RESEARCH Open Question 1 recommendation: `app_settings(key TEXT
  PRIMARY KEY, value_json JSON)` or `ranking_weights(id, weights_json, updated_at)`)
  is net-new DDL; follow migration 0002's create-table pattern.
- **Pinned head:** `tests/db/test_migration_contract.py:295` asserts
  `versions == ["0003"]` and L306 `head_lines[0].startswith("0003")` — update both
  to `"0004"` in lockstep.
- Add the new table to `conftest.RUN_REFERENCING_TABLES` **only if it has an FK to
  `runs.id`** (it should not).
- Migrations are one-way (D-20): the `downgrade()` must still be symmetric.

> **Blocking decision:** RESEARCH Open Question 1 says this migration is the
> phase's single highest-risk unstated item. The planner must resolve where the
> current weights live BEFORE writing code. `Settings`-only cannot satisfy SC-3
> past a restart; `scores.weights_json` is an audit snapshot, not the live value.

---

## Modified Files

### `app/pipeline/run.py` — the ranking stage call site

**Analog:** itself, the `_finish` seam (L566-624) and the filter-stage invocation (L869-881).

The ranking stage is spawned **after** the filter stage and **before/around**
`_finish`, per D-87 but superseded in time by D-88's detached shape. Copy the
filter-stage best-effort invocation pattern (L869-881): `try/except`, record the
failure as an error dict, never sink the run. Then call
`start_ranking_task(resolved_run_id, session_factory, llm=backend)`.

**Critical:** `_finish` cannot pass LLM totals it never had (ranking is detached).
Per RESEARCH Pattern 3, the ranking task should write `runs.llm_calls`/
`runs.llm_tokens` itself after its loop, mirroring D-89's `ranked_count` ownership.
`_finish`'s guarded write seam (L619-622) stays as-is. `ranked_count` remains
untouched by `_finish` (L623).

Also add the `llm: LLMBackend | None = None` keyword (Pitfall 7).

### `app/db/repositories/llm_call_repo.py` — rolling-24h aggregate (D-91)

**Analog:** itself, `llm_totals_for_run` (L185-205).

Copy the tolerant, never-committing read shape:
```python
async def rank_calls_since(session: AsyncSession, *, now: datetime | None = None) -> int:
    """`purpose='rank'` call count in the trailing 24h. Never commits, never raises."""
    moment = (now or datetime.now(UTC)).replace(tzinfo=None)
    cutoff = moment - timedelta(hours=24)
    return int(await session.scalar(
        select(func.count()).select_from(LlmCall).where(
            LlmCall.purpose == "rank", LlmCall.created_at >= cutoff
        )
    ) or 0)
```
**Pitfall 1:** `llm_calls.created_at` is NOT indexed — accept a full scan, do NOT
add an index migration just for this. `PURPOSES` already contains `"rank"`
(L41). Add the new function to `__all__`.

### `app/db/repositories/queue_repo.py` — read-time total, sort, threshold (D-97/D-98/D-100)

**Analog:** itself, `read_queue` (L315-392) and `_enrich` (L422-544).

- **Read-time total:** extend `QueueRow` with `total_score: float | None`,
  `confidence_tier: str | None`, `factor_scores: tuple[...]`, and compute the total
  via `rubric.weighted_total` under the **current** weights (D-100). This makes the
  queue's order a computed expression, not `scores.total_score`.
- **Ordering:** D-97 default `score DESC` with unranked last; keep
  `first_seen_at DESC, id DESC` available. Tie-break at equal score by higher
  `confidence_tier` (Pitfall 6b). The existing ordering ends with a unique tie-break
  by convention (module docstring L8-12) — preserve that.
- **Threshold (D-98):** add a `min_score: float | None` field to `QueueQuery`
  (L119-151) and a predicate that keeps **un-scored** listings visible. Update
  `query_string()` so the view filter is shareable (mirror `excluded`/`hidden`/
  `saved`, L139-151).
- **Pitfall 3:** `ix_scores_listing_total` is `(listing_id, total_score)` —
  listing_id-leading; it was never a cross-listing sort index. Do not build a plan
  that claims it accelerates the sort.

### `app/api/settings.py` — weights editor route (D-99)

**Analog:** `app/api/searches.py` form/fragment pattern (L79-159, L393-424) — see the
`_weights_form.html` assignment above. The settings route follows the existing
`_settings_context` render pattern (L121-160) and the `read_form` import already
present (L33). The weights editor is a mutating POST returning the re-rendered
fragment (or the full settings page — match the page's existing full-page form
convention at L36-40; the fragment-swap shape is for the criteria page).

### `app/config.py` — cap knobs (D-91)

**Analog:** itself, the Phase 4 block (L129-170).

Add two new `Settings` fields (per-run and rolling-24h ranking call ceilings).
**Pitfall 8:** choose defaults that do NOT collide with any existing distinctive
integer under `SCANNED_DIRS = ("app/probe", "app/pipeline", "app/latex", "app/cv")`.
Existing colliders include `25` (`queue_page_size`), plus the stage-log caps in
`run.py`. Then update `tests/test_config.py` `REQUIRED_SETTINGS_FIELDS` (L32-76)
and `LIMIT_FIELDS` (L79-111) in lockstep, plus `compose.yml`/`.env.example`.

### Test guards to edit (D-102)

- `tests/pipeline/test_finish_llm_counters.py::test_a_pipeline_run_writes_zero_llm_calls` (L135-162) and `tests/pipeline/test_filter_stage.py:197` — **rewrite** to assert the D-94 posture (ranking skipped without `cv.yaml`/when disabled), not D-49. Do not delete; keep them meaningful.
- `tests/test_auth_seam.py` `EXPECTED_SEAM_ROUTES` (L31-41) — add `"/listings/{listing_id}"`.
- `tests/db/test_migration_contract.py` (L295, L306) — bump the pinned Alembic head if a migration lands.

---

## Shared Patterns

### Auth seam
**Source:** `app/api/deps.py` + `app/api/events.py:80`
**Apply to:** every new/modified route (`app/api/listings.py`, the settings weights route).
```python
user: User = Depends(current_user)
```
`tests/test_auth_seam.py:97-108` fails any route with a dependant that omits it.
No identity columns ever (`FORBIDDEN_IDENTITY_COLUMNS`, L44).

### Repository contract
**Source:** `app/db/repositories/llm_call_repo.py:1-25`
**Apply to:** `score_repo.py`, the `llm_call_repo` aggregate, the `queue_repo` read model.
- SQL lives only in repositories; never commit (caller owns the commit).
- Writes in a SAVEPOINT; reads total/tolerant.
- `now` injectable.

### Background task (detached)
**Source:** `app/api/runs.py:54-56,104-106`
**Apply to:** `app/pipeline/rank.py::start_ranking_task`.
Module-level `set[asyncio.Task]` + `add_done_callback(discard)`; never `await` in a
request handler (AP6/RUN-02). Single-flight guard for ranking.

### Failure is a value
**Source:** `app/pipeline/filter_stage.py:99-109` / `app/llm/base.py:59-98`
**Apply to:** `app/pipeline/rank.py`, `score_repo.py`.
Per-item failures are caught, counted (`StageCounts.fail`), logged, and the loop
continues. No retry loop in `rank.py` — retries stay inside `llm/` via `retryCount`
(D-56/D-95).

### Error handling / cause recording
**Source:** `app/llm/opencode_server.py:77-83` (`ERROR_KIND_*`), `app/db/repositories/llm_call_repo.py:69-133`
**Apply to:** the ranking loop's `record_llm_call(purpose="rank", status=result.status, run_id=run_id)`.
**Pitfall 2:** `llm_calls` has **no `error_kind` column** and `record_llm_call` has
no such parameter. Persist the cause inside `error` (e.g. `f"{result.error_kind}: {result.error}"`)
or a literal `"budget_exceeded"`. Passing `error_kind=` would be a `TypeError`.

### Form + fragment swap
**Source:** `app/api/searches.py:79-159,393-424` + `criteria.html` macro
**Apply to:** the weights editor.
`read_form()` (stdlib `parse_qsl`, no `python-multipart`), `_field`/`_checkbox`/
`_int_field`, a Jinja macro for the fragment, and `make_module` so page and swap
share one definition.

### Pure weighted arithmetic
**Source:** `app/domain/run_reason.py`
**Apply to:** `app/domain/rubric.py`.
Pure, I/O-free, deterministic, no `Settings` — `tests/test_import_discipline.py`
enforces the import ban.

### CSS coverage + vendored assets
**Source:** `tests/test_stylesheet_coverage.py:39-57`, `tests/test_no_cdn.py`
**Apply to:** every new template class.
Every new class token needs a rule in `static/vendor/app.css` or an `EXEMPT_CLASSES`
entry with a stated reason.

---

## No Analog Found

Files with no close match in the codebase (planner should use RESEARCH.md patterns
instead):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/domain/schemas/ranking.py` | domain schema | transform | Only `probe.py` exists; the **top-level-scalar** requirement (salvage `loc` length 1) is a RESEARCH-derived constraint with no in-repo precedent — copy `probe.py` for defaults/`extra="ignore"` but derive the shape from RESEARCH Pattern 1. |
| `app/pipeline/rank.py` (the detached task lifecycle) | pipeline service | event-driven | No detached *ranking*-shaped task exists. The `runs.py` idiom exists for run tasks, but the single-flight guard + startup-recovery semantics (RESEARCH Open Questions 3-4) are design judgment, not in-repo precedent. |
| `app/db/repositories/score_repo.py` (the `scores` writer) | repository | CRUD | The `scores` table has **never been written**; no score-row upsert precedent exists. Composite analog (`llm_call_repo` house rules + `listing_repo` upsert) is the best available. |

---

## Metadata

**Analog search scope:** `app/domain`, `app/db/repositories`, `app/pipeline`,
`app/api`, `app/web`, `app/llm`, `app/cv`, `app/config.py`, `alembic/versions`,
`tests/`, `static/vendor`.
**Files scanned:** 18 analogs read in full or in targeted non-overlapping ranges;
repo structure enumerated across ~90 Python modules and 11 templates.
**Tracked-source gate:** every analog path was verified with `git ls-files -- <path>`
(non-empty) — all are tracked source, no gitignored mirrors.
**Pattern extraction date:** 2026-09-22
**RESEARCH corrections applied:** (1) `llm_calls.created_at` not indexed;
(2) no `llm_calls.error_kind` column; (3) `ix_scores_listing_total` is
listing_id-leading; (4) one score row per run ⇒ latest-per-listing read.
