# Phase 1: Walking Skeleton + Foundations - Pattern Map

**Mapped:** 2026-09-15
**Files analyzed:** 40 (created or modified this phase)
**Analogs found:** 0 / 40 in-repo — **40 / 40 via research-supplied pattern**

> **Greenfield notice.** `git ls-files` returns 17 files: `.planning/**`,
> `AGENTS.md`, `.gitignore`. There is **no application code, no `app/`, no
> `tests/`, no Docker files**. Therefore *no* new file has a codebase analog.
> Per the pattern-mapping brief, each file is mapped to the **research-supplied
> pattern** that governs it — the verified excerpts in
> `01-RESEARCH.md` and the module rules in
> `.planning/research/ARCHITECTURE.md`. Every excerpt below is **copied from
> those two files** with a source + line reference; no new code is authored here.
> The planner should quote from these excerpts in PLAN.md action sections.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `pyproject.toml` | config | build-config | none in-repo → RESEARCH §Standard Stack (L117-202) + §Wave 0 Gaps (L1180) | research-only |
| `compose.yml` | config (infra) | n/a | none in-repo → RESEARCH Code Examples → compose.yml (L917-939) | research-only |
| `Dockerfile` | config (build) | batch (image build) | none in-repo → RESEARCH §Migration Mechanics 6 (L427) + ARCHITECTURE §3 (L127) | research-only |
| `entrypoint.sh` | utility (shell) | batch | none in-repo → RESEARCH L427 + compose L934 | research-only |
| `.env.example` | config | n/a | none in-repo → RESEARCH D-07 (L25-29) + D-06 (L24) | research-only |
| `alembic.ini` | config | n/a | none in-repo → RESEARCH §Migration Mechanics 4 (L425) | research-only |
| `alembic/versions/0001_*.py` | migration | batch (DDL) | none in-repo → RESEARCH §Migration 0001 (L394-430) + Code Examples (L795-861) | research-only |
| `app/main.py` | app factory / provider | request-response | none in-repo → ARCHITECTURE §3 (L131) + RESEARCH L596 | research-only |
| `app/config.py` | config | n/a | none in-repo → RESEARCH §config-driven envelope (L472-487) | research-only |
| `app/db/base.py` | model (declarative base) | CRUD | none in-repo → ARCHITECTURE §3 (L187-189) | research-only |
| `app/db/session.py` | service (infra) | request-response | none in-repo → RESEARCH PRAGMA example (L769-791) | research-only |
| `app/db/models.py` | model | CRUD | none in-repo → ARCHITECTURE §9.1 (L827-969) | research-only |
| `app/db/repositories/listing_repo.py` | repository | CRUD | none in-repo → RESEARCH Two-Key Upsert (L728-767) | research-only |
| `app/domain/models.py` | model (pure) | transform | none in-repo → ARCHITECTURE §5.1 (L394-459) | research-only |
| `app/domain/listing.py` | utility (pure) | transform | none in-repo → RESEARCH derived fields (L941-963) | research-only |
| `app/domain/sanitize.py` | utility (pure) | transform | none in-repo → RESEARCH Pitfall 7 (L1000-1003) | research-only |
| `app/sources/base.py` | port / ABC | request-response | none in-repo → ARCHITECTURE §5.1 (L385-481) | research-only |
| `app/sources/registry.py` | registry | n/a | none in-repo → ARCHITECTURE §5.2 R7 (L493) | research-only |
| `app/sources/_jobspy_transport.py` | adapter (only jobspy importer) | blocking I/O | none in-repo → RESEARCH blocking-call boundary (L863-884) | research-only |
| `app/sources/linkedin.py` | adapter | request-response | none in-repo → ARCHITECTURE §5.3 (L495-501) | research-only |
| `app/sources/indeed.py` | adapter | request-response | none in-repo → RESEARCH §2.1 (L340) | research-only |
| `app/ingest/sanitize.py` | pipeline stage | transform | none in-repo → RESEARCH Pattern 3 (L663-666) | research-only |
| `app/pipeline/run.py` | orchestrator | event-driven / batch | none in-repo → RESEARCH Pattern 5 (L684-687) | research-only |
| `app/pipeline/stages.py` | orchestrator | event-driven | none in-repo → RESEARCH Pattern 6 (L689-692) | research-only |
| `app/probe/probe.py` | service | outbound request-response | none in-repo → RESEARCH probe design (L432-493) | research-only |
| `app/probe/survival.py` | service (pure-ish) | batch / transform | none in-repo → RESEARCH S1-S6 (L448-470) | research-only |
| `app/llm/base.py` | port | request-response | none in-repo → ARCHITECTURE §6.1 (L534-563) | research-only |
| `app/llm/opencode_server.py` | adapter | request-response | none in-repo → RESEARCH D-08/D-09/D-11 (L26-33) | research-only |
| `app/api/deps.py` | middleware / dependency | request-response | none in-repo → ARCHITECTURE §11.1 (L1087-1102) | research-only |
| `app/api/runs.py` | controller / route | request-response + event-driven | none in-repo → RESEARCH Pattern 5 (L684-687) + HTMX 286 (L900-913) | research-only |
| `app/api/health.py` | controller / route | request-response | none in-repo → RESEARCH D-03/D-08 (L23-30) | research-only |
| `app/web/routes.py` | controller / route | request-response | none in-repo → RESEARCH D-13 (L33) | research-only |
| `app/web/templates/html/*.html` | component (template) | request-response | none in-repo → RESEARCH HTMX example (L890-898) | research-only |
| `static/vendor/*` | asset | n/a | none in-repo → RESEARCH UI-07 / Pitfall 12 (L1025-1028) | research-only |
| `tests/conftest.py` | test (fixture) | n/a | none in-repo → RESEARCH §Wave 0 Gaps (L1181) | research-only |
| `tests/db/test_migration_contract.py` | test (schema contract) | n/a | none in-repo → RESEARCH §Migration Mechanics 7 (L428-430) | research-only |
| `tests/test_import_discipline.py` | test (static AST) | n/a | none in-repo → ARCHITECTURE §12 Pattern 1 (L1136-1144) | research-only |
| `tests/test_no_credentials.py` / `test_no_cdn.py` / `test_auth_seam.py` | test (static/introspection) | n/a | none in-repo → RESEARCH L1149-1162 | research-only |
| `docs/probes/YYYY-MM-DD-scraper-survival.md` | doc (deliverable) | n/a | none in-repo → RESEARCH D-03 (L489-493) + L495-513 | research-only |
| `scripts/compose-smoke.sh` | utility (operator) | n/a | none in-repo → RESEARCH L1189 + L1138 | research-only |

---

## Pattern Assignments

### `compose.yml` (config/infra)

**Analog:** none in-repo. **Pattern source:** `01-RESEARCH.md` Code Examples (lines 919-937).

Copy this shape wholesale — it encodes D-05 (no opencode service), D-06
(`extra_hosts` so the `OPENCODE_BASE_URL` default works on Linux), and D-08
(nothing in `up` may depend on an LLM backend):

```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]            # v1 is local-only; do not expose beyond the host
    volumes:
      - ./data:/data                # jobsearch.db (+ -wal, -shm) — back up the WAL too (M8)
    extra_hosts:
      - "host.docker.internal:host-gateway"    # makes the OPENCODE_BASE_URL default work on Linux
    environment:
      - OPENCODE_BASE_URL=${OPENCODE_BASE_URL:-http://host.docker.internal:4096}
      - OPENCODE_MODEL=${OPENCODE_MODEL:-deepseek-v4.1-flash}
      - OPENCODE_SERVER_PASSWORD=${OPENCODE_SERVER_PASSWORD:-}   # from an uncommitted .env
      - DATABASE_URL=sqlite+aiosqlite:////data/jobsearch.db
      - DATABASE_URL_SYNC=sqlite:////data/jobsearch.db           # Alembic uses this
    command: ["./entrypoint.sh"]     # alembic upgrade head; exec uvicorn app.main:app --workers 1
    # NO depends_on. opencode is external and user-managed (D-05); nothing in
    # `docker compose up` may depend on an LLM backend being reachable (D-08).
```

**Deliberately absent** (RESEARCH line 939): an `opencode` service, a dependency
on it, and any published 4096 port (M10).

**Data flow:** n/a (static infra config). **Verification:** operator-run only —
Docker is absent from the agent sandbox (RESEARCH L1107, L1117, L1138).

---

### `pyproject.toml` (config/build)

**Analog:** none in-repo. **Pattern source:** `01-RESEARCH.md` §Standard Stack (lines 119-202) and §Wave 0 Gaps (line 1180).

Exact pins from the verified version table (RESEARCH L193-201) — no floating
ranges (Note (a) mitigation, L235-237):

```toml
# fastapi 0.141.1 · uvicorn[standard] 0.53.0 · sqlalchemy 2.0.53 · alembic 1.20.0
# aiosqlite 0.22.1 · pydantic 2.13.5 · pydantic-settings 2.15.0 · jinja2 3.1.6
# httpx 0.28.1 · tenacity 9.1.4 · structlog 26.1.0
# pytest 9.1.1 · pytest-asyncio 1.4.0 · ruff 0.16.7
# JobSpy: git+https://github.com/speedyapply/JobSpy.git@fda080a373e8226f3fd60635323f5da9af9892b1
```

The pytest config is a **Wave 0 hard requirement** (RESEARCH L1133, L1180;
`01-VALIDATION.md` L24): `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`,
`testpaths = ["tests"]`, and a `live` marker. `[tool.ruff]` config also lands
here. Do **not** install `python-jobspy` from PyPI — it is the stale 1.1.82
release (RESEARCH L198-204).

---

### `Dockerfile` + `entrypoint.sh` (config/build)

**Analog:** none in-repo. **Pattern sources:** RESEARCH §Migration Mechanics 6 (line 427), compose `command` (line 934), ARCHITECTURE §3 (line 127).

- Base image **`python:3.13-slim`** — never develop against the sandbox's 3.14.7
  (D-17, RESEARCH L123, L1108).
- Multi-stage: the Tailwind CLI build output and the vendored JS are extracted at
  image build (D-14, RESEARCH L592 — "multi-stage: python:3.13-slim; Tailwind CLI
  build; alembic smoke").
- Acceptance item 9 (RESEARCH L427): *"an entrypoint that runs `alembic upgrade
  head` then `exec uvicorn …`, **plus** a build/CI step that exercises the same
  command against a throwaway SQLite file — proving the migration applies to a
  clean database, not merely that it was written."*
- The `entrypoint.sh` idiom is `alembic upgrade head` → `exec "$@"`; compose sets
  `command: ["./entrypoint.sh"]` (RESEARCH L934).

---

### `.env.example` (config)

**Analog:** none in-repo. **Pattern source:** RESEARCH D-07 (lines 25-29) + D-06 (line 24).

`.env` is already gitignored (`.gitignore` line 5). `.env.example` documents the
keys without values:

- `OPENCODE_BASE_URL` — default `http://host.docker.internal:4096`.
- `OPENCODE_MODEL` — default a cheap model, e.g. `deepseek-v4.1-flash`.
- `OPENCODE_SERVER_PASSWORD` — **optional**, uncommitted; must never be hard-coded
  or committed (D-07). This is a local LLM credential, explicitly *not* a portal
  credential (SRC-06 applies to portals).

---

### `alembic.ini` (config)

**Analog:** none in-repo. **Pattern source:** RESEARCH §Migration Mechanics 4 (line 425).

Two URLs, two engines — Alembic uses the **sync** driver while the app uses
`aiosqlite`, both pointing at the same file:

> *"Alembic runs on the **sync** driver (`sqlite:////data/jobsearch.db`) while the
> app runs `sqlite+aiosqlite:////data/jobsearch.db`; both point at the same file.
> Hold both in settings, never derive one from the other by string surgery inside
> a migration."* (RESEARCH L425)

---

### `alembic/versions/0001_*.py` (migration, batch DDL)

**Analog:** none in-repo. **Primary pattern source:** RESEARCH §Migration 0001 — Design Contract (lines 394-430) + Code Examples (lines 795-861); acceptance gate is ARCHITECTURE §9.4 (lines 981-993).

This is the phase's highest-risk file. Read RESEARCH L394-430 in full before
planning it. The mechanics that are easy to get wrong (RESEARCH L420-430):

1. **Both dedup indexes** — partial unique + unconditional unique, `sqlite_where=`
   dialect kwarg:

```python
    # Acceptance item 6 — BOTH indexes; neither alone is sufficient.
    op.create_index("uq_listing_sources_source_sid", "listing_sources",
                    ["source", "source_listing_id"], unique=True,
                    sqlite_where=sa.text("source_listing_id IS NOT NULL"))   # ← dialect kwarg form
    op.create_index("uq_listing_sources_source_url", "listing_sources",
                    ["source", "canonical_source_url"], unique=True)
```

2. **Named CHECK, never `sa.Enum`** (batch-mode drops unnamed constraints):

```python
    # Acceptance item 4 — explicitly NAMED check, because a later
    # batch_alter_table recreates the table and drops UNNAMED CHECK constraints.
    op.create_table(
        "cv_artifacts",
        # …
        sa.Column("compile_status", sa.String(16), nullable=False),
        sa.CheckConstraint("compile_status IN ('ok','failed','blocked')",
                           name="ck_cv_artifacts_compile_status"),
        sa.Column("verification_json", sa.JSON, nullable=True),
    )
```

3. **FTS5 via `op.execute()` with all three triggers** — creating the table
   without its triggers is the M4 silent-divergence failure (RESEARCH L831-858):

```python
    op.execute("""
        CREATE VIRTUAL TABLE listing_fts USING fts5(
            title, company_norm, description,
            content='listings', content_rowid='id',
            tokenize='porter unicode61');
    """)
    op.execute("""
        CREATE TRIGGER listings_ai AFTER INSERT ON listings BEGIN
          INSERT INTO listing_fts(rowid, title, company_norm, description)
          VALUES (new.id, new.title, new.company_norm, new.description);
        END;
    """)
    op.execute("""
        CREATE TRIGGER listings_ad AFTER DELETE ON listings BEGIN
          INSERT INTO listing_fts(listing_fts, rowid, title, company_norm, description)
          VALUES('delete', old.id, old.title, old.company_norm, old.description);
        END;
    """)
    op.execute("""
        CREATE TRIGGER listings_au AFTER UPDATE ON listings BEGIN
          INSERT INTO listing_fts(listing_fts, rowid, title, company_norm, description)
          VALUES('delete', old.id, old.title, old.company_norm, old.description);
          INSERT INTO listing_fts(rowid, title, company_norm, description)
          VALUES (new.id, new.title, new.company_norm, new.description);
        END;
    """)
```

**Tables 0001 must create** (RESEARCH L398-418): `sources`, `companies`,
`listings`, `listing_sources`, `listing_dupes`, `listing_events`,
`listing_exclusions`, `searches`, `runs`, `scores`, `cv_versions`,
`cv_artifacts`, `applications`, `application_events`, `llm_calls`,
`source_request_log`, `listing_fts` + 3 triggers.

**Verification is itself a deliverable:** turn the 9-item checklist into 9
assertions in `tests/db/test_migration_contract.py` (RESEARCH L428-430) —
`alembic upgrade head` against a temp file, then `PRAGMA table_info` /
`index_list` / `index_info` / `sqlite_master`. One-way migration; nothing here
can be backfilled (D-20).

---

### `app/main.py` (app factory / provider, request-response)

**Analog:** none in-repo. **Pattern source:** ARCHITECTURE §3 (line 131) + RESEARCH structure (line 596).

> `main.py` — *"FastAPI app factory + lifespan (opens nothing that can fail
> hard)"* (RESEARCH L596); ARCHITECTURE L131: *"FastAPI app factory + lifespan
> (scheduler start/stop)"*.

The Phase-1 lifespan opens **only** things that cannot hard-fail: the DB engine
and the static mount. It must **not** require the opencode server (D-08). Mounts
`StaticFiles` over `static/` and wires `api/routes` + `web/routes`.

---

### `app/config.py` (config)

**Analog:** none in-repo. **Primary pattern source:** RESEARCH §config-driven envelope (lines 472-487).

Every knob lives here so PLAT-04 is satisfied by inspection. The verified
Phase-1 envelope (RESEARCH L476-487):

| Setting | Default | Rationale |
|---------|---------|-----------|
| `probe_max_requests` | `2` | 1 search + ≤1 detail pass per board |
| `probe_max_results` | `50` | The documented personal-scale ceiling is ≤50–100 (P2) |
| `probe_max_detail_fetches` | `0` in Phase 1 | `linkedin_fetch_description` is O(n); leave it **off** |
| `probe_deadline_seconds` | `180` | Wall-clock ceiling per source |
| `probe_results_wanted` | `50` | Passed to `scrape_jobs(results_wanted=…)` — library default is `15` |
| `probe_country_indeed` | `"ireland"` | **Not** the library default `"usa"` |
| `probe_enabled` | `true` | Disable the live probe without removing code |
| `description_max_chars` | e.g. `20000` | Truncation policy at sanitise time (C2) |

Plus the surfaces required elsewhere: `local_user_id` (ARCHITECTURE §11.1 L1089),
`database_url_async` / `database_url_sync` (RESEARCH L425), `opencode_base_url`,
`opencode_model`, `opencode_server_password` (D-06/D-07). Use `pydantic-settings`
2.15.0 — *"one `Settings` class"* (RESEARCH L717).

---

### `app/db/session.py` (service/infra, request-response)

**Analog:** none in-repo. **Pattern source:** RESEARCH PRAGMA example (lines 769-791), verified against SQLAlchemy docs (L389, L426).

Copy verbatim — the `sync_engine` target and the autocommit dance are both
non-obvious and both documented (M8):

```python
# app/db/session.py
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(settings.database_url_async)  # sqlite+aiosqlite:////data/jobsearch.db

@event.listens_for(engine.sync_engine, "connect")   # ← sync_engine, per SQLAlchemy async docs
def _sqlite_pragmas(dbapi_connection, connection_record):
    # SQLAlchemy's SQLite docs: the driver will NOT apply PRAGMA foreign_keys
    # while autocommit is False. Toggle it for the duration of the pragma.
    ac = dbapi_connection.autocommit
    dbapi_connection.autocommit = True
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()
    dbapi_connection.autocommit = ac
```

A connection-level test asserts all four pragmas (RESEARCH L1007, L1166).

---

### `app/db/models.py` (model, CRUD)

**Analog:** none in-repo. **Pattern source:** ARCHITECTURE §9.1 column lists (lines 827-969).

Load-bearing columns to mirror exactly (column lists are "the *load-bearing*
columns, not exhaustive DDL" — ARCHITECTURE L823): `listings.first_seen_at /
last_seen_at / content_hash` all **NOT NULL** (L871-873), `listing_sources`
nullable `source_listing_id` + both unique indexes (L885-890), append-only
`listing_events` (L896-899), `scores.factor_scores_json` + `weights_json` +
`criteria_version` (L907-922), `cv_artifacts.verification_json` +
`compile_status` (L936-938), `applications.cv_artifact_id` (L948),
`sources.capabilities_json` + `tos_audited_at` (L829-836), `listings.blocking_key`
indexed (L975). Use `sa.String` + explicit `CheckConstraint` — **not** `sa.Enum`
(RESEARCH L424).

---

### `app/db/repositories/listing_repo.py` (repository, CRUD)

**Analog:** none in-repo. **Primary pattern source:** RESEARCH Two-Key Tier-1 Upsert (lines 728-767).

The ordered lookup — **not** a single `ON CONFLICT` (AP7/m9):

```python
# app/db/repositories/listing_repo.py — shape, not final code
async def upsert_listing_source(session, *, source: str, norm: NormalisedListing,
                                run_id: int, now: datetime) -> UpsertOutcome:
    """Two-key Tier-1. Order matters: key A only applies when the value is not NULL.

    Why not one `insert(...).on_conflict_do_update(index_elements=["source",
    "source_listing_id"])`? Because SQLite treats NULLs as distinct in a UNIQUE
    index, so when JobSpy returns id=None the conflict NEVER fires and the
    statement inserts a duplicate on every run. That is PITFALLS m9 / AP7.
    """
    row = None
    if norm.source_listing_id is not None:
        row = await session.scalar(
            select(ListingSource).where(
                ListingSource.source == source,
                ListingSource.source_listing_id == norm.source_listing_id,
            )
        )
    if row is None:
        row = await session.scalar(
            select(ListingSource).where(
                ListingSource.source == source,
                ListingSource.canonical_source_url == norm.canonical_url,
            )
        )
    if row is not None:
        row.last_seen_at = now
        # content_hash change ⇒ repost/update signal (Phase 2 acts on it)
        return UpsertOutcome(kind="updated", listed_source_id=row.id)

    # INSERT; a concurrent inserter (background run vs request) can still race —
    # catch IntegrityError, re-SELECT, and treat that as 'updated'.
    ...
    return UpsertOutcome(kind="created", listed_source_id=new_row.id)
```

All repository functions take an explicit `user`/`user_id` **argument at the
service layer** without adding a column (ARCHITECTURE §11.2 L1120-1122).
Establish bound-parameter FTS `MATCH` here so Phase 2 cannot regress it
(RESEARCH L1218).

---

### `app/domain/models.py`, `app/domain/listing.py`, `app/domain/sanitize.py` (pure domain)

**Analog:** none in-repo. **Pattern sources:** ARCHITECTURE §5.1 dataclasses (L394-459), RESEARCH derived-field functions (L941-963), RESEARCH Pitfall 7 (L1000-1003).

The domain is **pure — no I/O imports — enforced by a test** (D-24):

```python
# tests/test_import_discipline.py
FORBIDDEN_IN_DOMAIN = {"httpx", "sqlalchemy", "jobspy", "subprocess", "jinja2", "fastapi"}

def test_domain_is_pure():
    for module in modules_under("app.domain"):
        assert not (imported_names(module) & FORBIDDEN_IN_DOMAIN), \
            f"{module} imports I/O — move it behind a port"
```
(ARCHITECTURE §12 Pattern 1, L1136-1144; RESEARCH L1185.)

`listing.py` derives the fields that carry the dedup guarantee (RESEARCH L943-963):

```python
# app/domain/listing.py — pure, no I/O, unit-testable
TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"gh_src", "lever-source", "src", "ref", "trk"}

def canonical_url(raw: str, direct: str | None = None) -> str:
    """Lowercase scheme+host, drop default port, strip tracking params, sort the
    rest, drop the fragment, normalise a trailing slash. Prefer `direct` (the
    employer's own listing) when present — it is the Tier-2a cross-source signal."""
    ...

def content_hash(*, title: str, company_name: str | None, location_raw: str | None,
                 description: str | None) -> str:
    """Stable hash over the SANITISED fields. Used for repost/update detection
    and as a Tier-2c duplicate signal. Must not include volatile fields
    (e.g. salary or last_seen_at) or every run looks like a change."""
    ...

def annualise_salary(minimum, maximum, interval, currency):  # memo: Ireland ⇒ JobSpy gives
    ...                                                       # no description-derived salary
```

**Sanitise scope for Phase 1 (Pitfall 7, RESEARCH L1002):** email/phone stripping,
HTML/boilerplate reduction + whitespace collapse, truncation to
`description_max_chars`, and a **flag field** for instruction-like text — with the
*pattern catalogue itself* deferred to Phase 2. **Drop PII; do not hash it**, and
never log the removed value (record only a count). `RawListing` has **no `emails`
field** — unrepresentable, not filtered (D-18, ARCHITECTURE R2 L488).

`models.py` holds `RawListing`/`NormalisedListing`/`ListingSourceRef` dataclasses;
the canonical shapes are in ARCHITECTURE §5.1 (L430-459).

---

### `app/sources/base.py` (port / ABC, request-response)

**Analog:** none in-repo. **Primary pattern source:** ARCHITECTURE §5.1 (lines 385-481).

The full contract is specified there. The load-bearing shapes (copied):

```python
@dataclass(frozen=True)
class SourceCapabilities:
    supports_salary: bool
    supports_salary_min_filter: bool
    supports_remote_flag: bool
    supports_seniority: bool
    supports_full_description_in_search: bool
    requires_second_pass_for_description: bool   # LinkedIn: extra request per job
    supports_offset_paging: bool
    max_results_per_query: int | None            # boards cap ~1000
    # Mutually exclusive filter groups. LinkedIn honours ONLY ONE of
    # {hours_old, easy_apply}; supplying several is SILENTLY ignored upstream.
    exclusive_filter_groups: tuple[frozenset[str], ...] = ()

@dataclass(frozen=True)
class FetchBudget:
    max_requests: int
    max_results: int
    max_detail_fetches: int
    deadline: datetime

@dataclass(frozen=True)
class FetchResult:
    """A total, never an exception. Partial success is a first-class outcome."""
    source: SourceName
    items: list[RawListing] = field(default_factory=list)
    status: Literal["ok", "partial", "blocked", "rate_limited", "error"] = "ok"
    requests_used: int = 0
    error: str | None = None

class JobSource(ABC):
    """The ONLY surface the pipeline depends on. One instance per board."""
    name: SourceName
    capabilities: SourceCapabilities

    @abstractmethod
    async def probe(self) -> Literal["ok", "degraded", "unreachable"]: ...

    @abstractmethod
    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult: ...

    async def fetch_details(
        self, refs: list[RawListing], budget: FetchBudget
    ) -> dict[str, RawListing]:
        """Optional second pass. Default: no-op. Overridden only where the board
        requires O(n) extra requests (LinkedIn). Budgeted separately."""
        return {}
```

The seven contract rules are ARCHITECTURE §5.2 (L483-493): R1 never raises, R2
sanitises before returning / no `emails`, R3 capabilities consulted + warned, R4
description is a separate budgeted pass, R5 never touches DB/dedup/filter/LLM,
R6 `source_extras` for board fields, R7 registry keyed by `name`.

---

### `app/sources/registry.py` (registry)

**Analog:** none in-repo. **Pattern source:** ARCHITECTURE §5.2 R7 (line 493).

> *"Adapters are keyed by `name` in an explicit registry, resolved from the
> `sources` table at run start."* — "implement `JobSource`, register it, insert a
> `sources` row, run it. If it requires editing the pipeline or the schema, ADR-1
> … has failed."

---

### `app/sources/_jobspy_transport.py` (adapter, blocking I/O)

**Analog:** none in-repo. **Primary pattern source:** RESEARCH blocking-call boundary (lines 863-884).

The **only** module allowed to `import jobspy` (AP1, ARCHITECTURE L203):

```python
# app/sources/_jobspy_transport.py — the ONLY module allowed to `import jobspy`
import asyncio, jobspy

async def run_scrape(*, site: str, kwargs: dict, deadline_s: float) -> object:
    """JobSpy is synchronous and spawns its own ThreadPoolExecutor internally
    (verified in jobspy/__init__.py), so it MUST NOT run on the event loop.
    """
    # NOTE: scrape_jobs() does NOT accept request_timeout — ScraperInput's
    # request_timeout=60 is not passed through (verified). So the *only* time
    # bound we can impose is the outer wait_for below. asyncio.to_thread cannot
    # be cancelled: on timeout the worker thread keeps running to completion in
    # the background. Therefore the real budget control must be PRE-CALL
    # (refuse to start a fetch whose remaining budget cannot cover it) and the
    # timeout is a UI-protection guard, not a hard kill.
    return await asyncio.wait_for(
        asyncio.to_thread(jobspy.scrape_jobs, site_name=site, **kwargs),
        timeout=deadline_s,
    )
```

Two consequences (RESEARCH L886): `FetchBudget.deadline` is **advisory** at the
transport and must be a pre-call decision + a `status="error"/"partial"` outcome
on timeout; the detail pass is a *separate* budgeted call. `source_request_log`
is written by the transport (RESEARCH L1089).

---

### `app/sources/linkedin.py` and `app/sources/indeed.py` (adapters, request-response)

**Analog:** none in-repo. **Pattern sources:** ARCHITECTURE §5.3 (L495-501), RESEARCH §2 (L294-359).

**One adapter per board, sharing the transport — never one call with a
`site_name` list** (D-18, AP16):

> *"Critically: never call JobSpy once with a `site_name` list. One call = one
> thread pool = one failure mode = no per-board budget, health, or
> `first_seen_at` attribution at the board level. Invoke per board."*
> (ARCHITECTURE §5.3, L501)

**Indeed must set `country_indeed="ireland"`** — the library default is `"usa"`
and silently returns US listings (RESEARCH L340, Pitfall 6 L995-998):
`Country.IRELAND = ("ireland", "ie", "ie")` (RESEARCH L340).

**LinkedIn declares `exclusive_filter_groups=({hours_old, easy_apply},)`**
(RESEARCH L80, ARCHITECTURE L406-407); the declared-and-warned path ships in
Phase 1, consumption is Phase 2.

`desired_order` (RESEARCH L324-336) is the pinned column contract for S6 schema
drift. The `JobPost` field map — including `id: str | None = None` and
`emails: list[str] | None = None` — is RESEARCH L252-274. **Drop `emails` at the
mapping boundary; never add it to `RawListing`.**

---

### `app/ingest/sanitize.py` (pipeline stage, transform)

**Analog:** none in-repo. **Pattern source:** RESEARCH Pattern 3 (lines 663-666).

> *"`ingest/sanitize.py` wraps the pure `domain/sanitize.py`, so it has a name, a
> log line and a counter… a helper buried in the adapter would silently diverge
> across two adapters."*

The hard ordering rule: **sanitise before the listing is persisted OR prompted**
(ARCHITECTURE L268).

---

### `app/pipeline/run.py` (orchestrator, event-driven/batch)

**Analog:** none in-repo. **Primary pattern source:** RESEARCH Pattern 5 (lines 684-687); flow is RESEARCH L528-582.

```python
# app/pipeline/run.py — run_pipeline(trigger, search_id)
```

> *"`pipeline/run.py:run_pipeline(trigger, search_id)` is a plain async callable.
> `POST /runs` enqueues it and returns `202` **immediately**; Phase 8's scheduler
> will call the same function."* (RESEARCH L685)

`run_pipeline` writes a `runs` row (`status=running`, `started_at`), loops enabled
sources concurrently each with its own `FetchBudget`, and updates the row
(`status=done|partial`, `source_counts_json`, `errors_json`) on completion
(RESEARCH L543-567). **Never awaited inside a request handler** (AP6). Run state
is read from the DB — default to the database as the single source of truth and
treat any in-memory registry as lazily-created and keyed by `run_id` only
(RESEARCH Open Q3 L1081-1084).

---

### `app/pipeline/stages.py` (orchestrator, event-driven)

**Analog:** none in-repo. **Pattern source:** RESEARCH Pattern 6 (lines 689-692).

> *"`runs` rows carry per-source counts and structured errors; `source_request_log`
> carries the politeness ledger; `sources` carries the fill-rate baseline."*

Each stage is a callable with a name and a counter; per-stage counts/errors go to
`runs.errors_json` via `structlog` (ARCHITECTURE §12 Pattern 6 L1170-1174). Use
`structlog` with stage names — *"in this phase every hand-rolled candidate is a
silent-failure candidate"* (RESEARCH L720-722).

---

### `app/probe/probe.py` and `app/probe/survival.py` (service; outbound / batch)

**Analog:** none in-repo. **Primary pattern sources:** RESEARCH §Scraper-Survival Probe Design (L432-522); the split is settled by RESEARCH Open Q4 (L1086-1089).

**Split the instrument by concern** (RESEARCH L1086-1089):

> *"`probe()` on the adapter (board knowledge), the S1–S6 computation in
> `app/probe/survival.py` (board-agnostic), and `source_request_log` written by
> the transport."*

`probe()` must assert a **known answer**, not a 200 (RESEARCH L446): require
(a) HTTP 200, (b) a body above a minimum length, (c) the presence of an expected
structural marker, and (d) absence of recorded stop-signal strings. `degraded` =
reachable but marker absent / stop signal present; `unreachable` = transport error
or non-200. TTL-cache it (~5 min, RESEARCH L441, L1060).

`survival.py` computes S1–S6 (RESEARCH L448-470). Thresholds — the WARN/FAIL
boundaries the tests must fire at (RESEARCH L458-468):

- **S2 fill-rate:** WARN at ≥10-point drop vs baseline / rolling 7-run average; **FAIL at ≥25 points**. Do **not** set a target for `salary_min`/`salary_max` — JobSpy's description-salary extraction is USA-only, so an Irish search is structurally low (RESEARCH L358, L462).
- **S3 count delta:** `N = 5` trailing mean; **WARN at ≤ −25%**, **FAIL at ≤ −50%**; require ≥2 prior runs before arming.
- **S4 freshness:** **FAIL** if no new listing for the source in **≥3 consecutive daily runs** while `status == "ok"`.
- **S5** records `source_request_log.status_code`, `ok`, and a `note` classifying fetch-side vs parse-side; stop signals recorded verbatim and **stop — do not escalate** (P2).
- **S6 schema drift:** missing expected `desired_order` column (RESEARCH L470).

The Adzuna promotion condition (P-1…P-5) is RESEARCH L495-513 and must appear in
the verdict document. The three recording places are RESEARCH L489-493.

---

### `app/llm/base.py` and `app/llm/opencode_server.py` (port + adapter, request-response)

**Analog:** none in-repo. **Pattern sources:** ARCHITECTURE §6.1 (L534-563), RESEARCH recommended structure (L621-623), D-08/D-09/D-11 (L26-33).

Phase-1 scope is **health + discovery only; Phase 1 makes NO LLM call**
(RESEARCH L622-623, L1025). The port shape (ARCHITECTURE L541-563) exists so
Phase 3 swaps in calls without touching route signatures.

Discovery rules that are Phase-1 deliverables:

- Health via **`GET /global/health`**; boot-tolerant → report `unreachable`, never
  crash (D-08).
- Model discovery via **`GET /config/providers`** — **never `GET /provider`** (the
  6 MB catalogue, D-09).
- **Redaction boundary (D-11, the phase's most concrete security hazard):**
  *"parse into a Pydantic model with **only** `provider.id` and `model.id` fields;
  never bind the raw body to a long-lived variable; assert the absence with a test
  that runs discovery against a fixture containing a sentinel key and then scans
  `caplog` output **and** every table for that sentinel."* (RESEARCH L1021-1022)
- `httpx` is allowed **here only** — never in `app.domain.*` (ARCHITECTURE L605).

---

### `app/api/deps.py` (middleware/dependency, request-response)

**Analog:** none in-repo. **Primary pattern source:** ARCHITECTURE §11.1 (lines 1087-1102).

```python
# app/api/deps.py
LOCAL_USER = User(id=settings.local_user_id, name="Local", email=None)

async def current_user() -> User:
    """v1: the single local user. Later: OIDC/Authentik via authlib.
    ROUTE SIGNATURES DO NOT CHANGE."""
    return LOCAL_USER
```

Every route, from day one, declares `user: User = Depends(current_user)`.
**Do not pre-add `user_id` columns** (AP14, ARCHITECTURE L1116) — thread the user
at the service layer only (L1120-1122).

---

### `app/api/runs.py` (controller/route, request-response + event-driven)

**Analog:** none in-repo. **Pattern sources:** RESEARCH Pattern 5 (L684-687) + HTMX 286 stop condition (L890-913).

`POST /runs` creates the `runs` row, spawns the background task, and returns
**202 + a status fragment immediately** (RESEARCH L540-542, L685). It must **not**
await the pipeline (AP6 RUN-02).

Status polling returns HTTP **286** to stop (RESEARCH L900-913):

```python
# app/api/runs.py — the server decides when polling stops
@router.get("/runs/{run_id}/status")
async def run_status(run_id: int, user: User = Depends(current_user), ...):
    run = await repo.get_run(run_id)
    if run.status in {"done", "partial", "failed"}:
        # HTTP 286 is htmx's documented "stop polling" signal.
        return Response(
            content=render_run_fragment(run),
            status_code=286,
            headers={"HX-Reswap": "outerHTML"},
        )
    return templates.TemplateResponse("_run_status.html", {"run": run})
```

---

### `app/api/health.py` (controller/route, request-response)

**Analog:** none in-repo. **Pattern sources:** D-03 (L23), D-08 (L26), D-13 (L33).

`/health` reports **db + opencode reachability + per-source `probe()`**. It must
be boot-tolerant when opencode is down and must not hammer a board (TTL-cached
probe). **The raw `/config/providers` response is never surfaced** (D-11).

---

### `app/web/routes.py` + `app/web/templates/html/*.html` (controller + templates, request-response)

**Analog:** none in-repo. **Pattern sources:** D-13 (L33), RESEARCH HTMX example (L890-898), Pitfall 12 (L1025-1028).

Phase-1 UI ships (D-13): a server-rendered **list** (title, company, location,
source, posted), an **empty state**, a **count**, a **"Run search now"** button, a
**status poll**, and a **per-source health strip** (last success, listings
returned, field fill-rate). Templates: `base.html`, `queue.html`,
`_health_strip.html`, `_run_status.html` (RESEARCH L604).

HTMX polling fragment (copy from RESEARCH L890-898):

```html
<!-- app/web/templates/html/_run_status.html -->
<div id="run-status"
     hx-get="/runs/{{ run.id }}/status"
     hx-trigger="every 2s"
     hx-swap="outerHTML">
  Running… {{ run.stage }} ({{ run.fetched_count }} fetched)
</div>
```

Template hardening (V5/V7, RESEARCH L1204, L1217): Jinja2 **autoescape ON**, no
`|safe`, no `Markup`, listing text never enters client-side templates. The
degradation semantics when one board is `blocked` and the other `ok` are the
planner's discretion, bounded by SRC-05 + Pitfall 10 (L1015-1018): the badge
reads **`partial`**, names the degraded source, and states what the healthy source
delivered.

---

### `static/vendor/*` (assets)

**Analog:** none in-repo. **Pattern sources:** D-14 (L34), D-15 (L35), Pitfall 12 (L1025-1028).

- `htmx.min.js` (2.0.10), `alpine.min.js` (3.17.3), built `app.css` — **no CDN**
  (UI-07).
- Tailwind 4 CLI build at image build: `npx @tailwindcss/cli -i ./src/input.css -o ./src/output.css`
  with `@import "tailwindcss";` + `@source "../templates";` (RESEARCH L392, L1027).
- Commit the built `app.css` and the two JS files so the repo runs without Node;
  keep the build in the Dockerfile (RESEARCH Open Q7 L1099-1101).
- `tests/test_no_cdn.py` scans templates for `http://`/`https://` asset refs and
  checks the vendored files exist (RESEARCH L1027, L1162).

---

### `tests/` tree (Wave 0)

**Analog:** none in-repo. **Primary pattern source:** RESEARCH §Validation Architecture → Wave 0 Gaps (lines 1124-1190); duplicated in `01-VALIDATION.md` §Wave 0.

Wave 0 gaps to create (RESEARCH L1180-1190):

- `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"`, `live` marker, `[tool.ruff]`.
- `tests/conftest.py` — async-Engine fixture backed by a **temp file** (not `:memory:` — WAL and FTS5 behaviour differ), PRAGMAs applied, schema via **`alembic upgrade head`** (never `create_all`).
- `tests/db/test_migration_contract.py` — the 9-item checklist as assertions (**the single highest-value test in the phase**).
- `tests/fixtures/listings/*.json` — captured/hand-built raw payloads, `emails` stripped, committed; never fetched in CI.
- `tests/sources/test_linkedin.py` / `test_indeed.py` — fixture-driven; include `id=None`, empty description, `country_indeed` regression guard.
- `tests/test_import_discipline.py` — AST walk (see domain section above).
- `tests/test_no_credentials.py`, `tests/test_no_cdn.py`, `tests/test_auth_seam.py` — the three static/introspection guards.
- `tests/probe/test_thresholds.py` — one test per WARN/FAIL boundary.
- `static/vendor/` and `scripts/compose-smoke.sh` + runbook note.

The auth-seam introspection test (RESEARCH L671-681) is copied in Shared Patterns
below. The full Req → Test map is RESEARCH L1142-1167.

---

### `docs/probes/YYYY-MM-DD-scraper-survival.md` (doc deliverable)

**Analog:** none in-repo. **Pattern sources:** D-03 (L489-493), verdict spec (L491), Adzuna condition (L495-513).

Contents (RESEARCH L491): raw per-source numbers, the baseline used, each
signal's observed value vs threshold, explicit PASS/FAIL per signal, the
**provisional/final** marker, and the Adzuna decision paragraph. The verdict must
be *derivable from* the `runs` + `source_request_log` rows; if not, the
instrumentation is incomplete. If the evidence base is thinner than 5 runs, write
**PROVISIONAL** with the reason — never fabricate a verdict from one run
(RESEARCH L513).

---

### `scripts/compose-smoke.sh` (operator utility)

**Analog:** none in-repo. **Pattern source:** RESEARCH §Environment Availability (L1107, L1117, L1138) + Wave 0 (L1189).

```bash
docker compose up -d --wait && curl -fsS localhost:8000/health
```

**Operator-run, not agent-run** — Docker is absent from the sandbox. This is an
explicit human verification task, not a gap to quietly drop (RESEARCH L1117).

---

## Shared Patterns

### Ports with enforced import discipline (D-24)
**Source:** ARCHITECTURE §12 Pattern 1 (L1136-1144); RESEARCH L1185.
**Apply to:** `tests/test_import_discipline.py`; every file under `app/domain/`.

```python
# tests/test_import_discipline.py
FORBIDDEN_IN_DOMAIN = {"httpx", "sqlalchemy", "jobspy", "subprocess", "jinja2", "fastapi"}

def test_domain_is_pure():
    for module in modules_under("app.domain"):
        assert not (imported_names(module) & FORBIDDEN_IN_DOMAIN), \
            f"{module} imports I/O — move it behind a port"
```

### Total functions at the boundary (SRC-05, R1)
**Source:** RESEARCH Pattern 1 (L647-656); ARCHITECTURE §12 Pattern 2 (L1146-1150).
**Apply to:** every adapter, `probe()`, `app/llm/opencode_server.py`, `run_pipeline`.

```python
# Source: ARCHITECTURE.md §5.1 (verbatim contract, restated for Phase 1)
@dataclass(frozen=True)
class FetchResult:
    source: SourceName
    items: list[RawListing] = field(default_factory=list)
    status: Literal["ok", "partial", "blocked", "rate_limited", "error"] = "ok"
    requests_used: int = 0
    error: str | None = None
```

### Auth seam proven universal (PLAT-03)
**Source:** RESEARCH Pattern 4 (L671-681).
**Apply to:** `app/api/deps.py` + every route in `app/api/` and `app/web/`.

```python
# tests/test_auth_seam.py — the test that makes PLAT-03 falsifiable
def test_every_route_declares_current_user(app):
    missing = []
    for route in app.routes:
        if not getattr(route, "dependant", None):
            continue
        if not _depends_on(route.dependant, current_user):
            missing.append(getattr(route, "path", repr(route)))
    assert missing == [], f"routes without current_user: {missing}"
```

### PII unrepresentable (SRC-10)
**Source:** ARCHITECTURE R2 (L488), RESEARCH L279, Pitfall 7 (L1002).
**Apply to:** `RawListing`, `domain/sanitize.py`, the migration, every template/log.

`RawListing` has no `emails` field; drop (not hash) recruiter emails/phones; never
log the removed value — record only a count. Negative schema test:
`tests/db/test_no_pii_columns.py`.

### Blocking-call boundary (RUN-02, M3)
**Source:** RESEARCH L863-884.
**Apply to:** `_jobspy_transport.py`; any future subprocess (Tectonic, Phase 4).

`asyncio.to_thread` + outer `asyncio.wait_for`; budget enforced **pre-call**
because `to_thread` cannot be cancelled.

### Migration is the schema test (P8/M8)
**Source:** RESEARCH §Migration Mechanics 7 (L428-430).
**Apply to:** `tests/db/test_migration_contract.py` — 9 assertions via
`PRAGMA table_info` / `index_list` / `index_info` / `sqlite_master`.

### Config, not constants (PLAT-04)
**Source:** RESEARCH L472-487, L717.
**Apply to:** `app/config.py`; all thresholds in `app/probe/survival.py` are read
from settings, never inlined.

---

## No Analog Found

Every file in this phase has no in-repo analog, because the repository is
greenfield (17 tracked files, zero application code). This is expected and is
**not** a coverage gap: each file maps to an explicit research-supplied pattern
above.

| File group | Role | Data Flow | Reason |
|------------|------|-----------|--------|
| all 40 files listed in §File Classification | mixed | mixed | No application code exists in the repo; patterns come from `01-RESEARCH.md` + `ARCHITECTURE.md` (both git-tracked). |

**Analog search scope:** `job-search/` tree (all of it), verified via
`git ls-files` (17 tracked files: `.planning/**`, `AGENTS.md`, `.gitignore`).
**Files scanned:** 17 tracked + the phase docs. **No gitignored mirror paths were
used** — all cited sources are tracked under `.planning/`.

---

## Metadata

**Analog search scope:** `/workspace/job-search` (whole repo).
**In-repo candidates scanned:** 17 (all `.planning/**` + `AGENTS.md` + `.gitignore`).
**Pattern sources (tracked):**
- `.planning/phases/01-walking-skeleton-foundations/01-RESEARCH.md` (1277 lines)
- `.planning/research/ARCHITECTURE.md` (1420 lines, §3/§5/§9/§11/§12/§13/§14 used)
- `.planning/phases/01-walking-skeleton-foundations/01-CONTEXT.md`
- `.planning/phases/01-walking-skeleton-foundations/01-VALIDATION.md`
**Pattern extraction date:** 2026-09-15
**Coverage:** 40 files classified; 40 mapped to a research-supplied pattern; 0 in-repo analogs (greenfield).
