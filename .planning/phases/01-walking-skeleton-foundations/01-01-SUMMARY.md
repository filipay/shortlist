---
phase: 01-walking-skeleton-foundations
plan: 01
subsystem: infra
tags: [fastapi, sqlalchemy, alembic, sqlite, wal, fts5, pydantic-settings, jinja2, htmx, alpine, tailwind, docker, compose]

# Dependency graph
requires: []
provides:
  - "migration 0001 — the one-way schema (17 tables incl. listing_fts), both Tier-1 dedup indexes, named CHECKs, append-only listing_events triggers"
  - "app/db/session.py — async engine + the four D-17 PRAGMAs on engine.sync_engine"
  - "app/db/repositories/listing_repo.py — ordered two-key Tier-1 upsert with SAVEPOINT-guarded race handling"
  - "app/api/deps.py — LOCAL_USER + current_user() auth seam"
  - "app/config.py — one Settings class carrying the whole D-02 probe envelope (PLAT-04)"
  - "app/main.py create_app() + app/web/routes.py GET / — queue page rendered from a real DB read"
  - "compose.yml / Dockerfile / entrypoint.sh — the app-only deployment path and the image-build migration smoke"
  - "static/vendor/{app.css,htmx.min.js,alpine.min.js} — committed, no CDN"
  - "tests/conftest.py — alembic-migrated temp-DB fixtures (template + per-test copy)"
affects: ["Phase 1 plans 01-02..01-07", "Phases 2-8 (schema, session, repo, auth seam, asset pipeline)"]

# Actuals (#2632) — pairs with the plan's estimate (58000 tokens / 3 tasks).
# Same estimateTokens scale: chars/4 over the realized diff (241883 chars).
# NOTE: ~150315 of those chars are the committed minified vendor assets
# (htmx 51238 + alpine 55886 + app.css 43191), not authored application code.
actuals:
  tokens: 60471
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: [fastapi 0.141.1, uvicorn 0.53.0, sqlalchemy 2.0.53, alembic 1.20.0, aiosqlite 0.22.1, pydantic 2.13.5, pydantic-settings 2.15.0, jinja2 3.1.6, httpx 0.28.1, tenacity 9.1.4, structlog 26.1.0, pytest 9.1.1, pytest-asyncio 1.4.0, ruff 0.16.7, pyyaml 6.0.3, htmx 2.0.10, alpinejs 3.17.3, tailwindcss 4.3.3]
  patterns: ["two-key ordered Tier-1 upsert", "PRAGMA listener on sync_engine", "migration-as-schema-test", "auth seam dependency on every route", "app factory with a hard-fail-free lifespan", "vendored asset pipeline"]

key-files:
  created:
    - pyproject.toml
    - requirements.txt
    - alembic.ini
    - alembic/env.py
    - alembic/script.py.mako
    - alembic/versions/0001_initial_schema.py
    - app/config.py
    - app/main.py
    - app/domain/models.py
    - app/api/deps.py
    - app/db/base.py
    - app/db/session.py
    - app/db/models.py
    - app/db/repositories/listing_repo.py
    - app/web/routes.py
    - app/web/templates/html/base.html
    - app/web/templates/html/queue.html
    - compose.yml
    - Dockerfile
    - entrypoint.sh
    - .env.example
    - assets/tailwind/input.css
    - static/vendor/app.css
    - static/vendor/htmx.min.js
    - static/vendor/alpine.min.js
    - tests/conftest.py
    - tests/db/test_skeleton_boot.py
    - tests/db/test_two_key_upsert.py
    - tests/db/test_persistence.py
    - tests/db/test_pragmas.py
    - tests/test_deploy_manifest.py
  modified:
    - .gitignore
    - pyproject.toml

key-decisions:
  - "Alembic's sync engine applies the same four PRAGMAs as the app, so the first migration lands in WAL + synchronous=NORMAL (D-17) instead of the rollback journal; this also cut migration wall-clock from ~16s to ~5s on this filesystem, which matters before the entrypoint's `alembic upgrade head` on every boot."
  - "The PRAGMA autocommit toggle is guarded with getattr: the pysqlite driver needs it for `foreign_keys=ON`, but SQLAlchemy's aiosqlite adapter exposes no `autocommit` attribute at all — an unguarded access raised AttributeError on every connection."
  - "conftest keeps a session-scoped migrated template DB and gives each test a copied file, so tests get an empty migrated database without paying `alembic upgrade head` per test (full suite 19 tests in ~4-7s, inside the <30s quick-lane budget)."
  - "`listing_sources.source` keeps its FK to `sources.name`, so tests/tasks must register a source row before ingesting; the alternative (dropping the FK) would lose the referential guarantee M8 exists to provide."
  - "queue.html ships only the list, count and empty state in this plan. The 'Run search now' button and per-source health strip are owned by plans 01-03 and 01-06 — deliberately not stubbed here."
  - "pyyaml was added to the dev extra because tests/test_deploy_manifest.py parses compose.yml; relying on the transitive pyyaml that arrives via uvicorn[standard] would be an undeclared test dependency."

patterns-established:
  - "Versioned, explicitly named SQLite constraints: sa.String + named CheckConstraint, never sa.Enum (unnamed CHECKs are dropped by batch_alter_table)."
  - "Schema creation in tests only ever via `alembic upgrade head` against a temp file — never :memory:, never Base.metadata.create_all."
  - "Ordered two-key lookup (key A only when the value is non-NULL, then key B) with the INSERT wrapped in a SAVEPOINT so a race can be re-SELECTed without poisoning the outer transaction."
  - "Deployment contract asserted without Docker: compose/Dockerfile/entrypoint/vendored-asset invariants are ordinary pytest assertions."

# Declared by this plan (frontmatter `requirements`):
#   QUEUE-01, QUEUE-02, QUEUE-05, PLAT-01, PLAT-03, PLAT-04, UI-07
# Only QUEUE-01 is marked complete: `requirements.ready-ids` reports the other
# six as blocked because sibling plans (01-02, 01-03, 01-05, 01-06, 01-07) also
# declare them and have produced no SUMMARY yet. They are re-evaluated as each
# sibling plan finishes.
requirements-completed: [QUEUE-01]

# Coverage metadata (#1602) — one entry per shipped deliverable.
coverage:
  - id: D1
    description: "Migration 0001 applies to a clean database and leaves a single head at 0001, creating all 17 schema objects"
    requirement: null
    verification:
      - kind: integration
        ref: "tests/db/test_skeleton_boot.py#test_migration_creates_every_table_at_revision_0001"
        status: pass
      - kind: other
        ref: "alembic heads -> 0001 (head)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Two-key Tier-1 upsert is idempotent: repeated ids, key-B collisions and the source_listing_id=None case each yield exactly one listing_sources row; a concurrent-insert IntegrityError resolves to updated"
    requirement: "QUEUE-02"
    verification:
      - kind: integration
        ref: "tests/db/test_two_key_upsert.py#test_same_source_listing_id_upserts_one_row"
        status: pass
      - kind: integration
        ref: "tests/db/test_two_key_upsert.py#test_two_null_source_listing_ids_upsert_one_row"
        status: pass
      - kind: integration
        ref: "tests/db/test_two_key_upsert.py#test_concurrent_insert_race_is_caught_and_resolved"
        status: pass
    human_judgment: false
  - id: D3
    description: "The queue persists across an engine restart, and committed data is readable from the main DB file without the -wal sidecar"
    requirement: "QUEUE-01"
    verification:
      - kind: integration
        ref: "tests/db/test_persistence.py#test_listing_survives_an_engine_restart"
        status: pass
      - kind: integration
        ref: "tests/db/test_persistence.py#test_committed_data_is_readable_without_the_wal_sidecar"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every application connection reports journal_mode=wal, foreign_keys=1 and busy_timeout=5000, and the SQLite build exposes ENABLE_FTS5"
    requirement: "QUEUE-05"
    verification:
      - kind: unit
        ref: "tests/db/test_pragmas.py#test_connection_pragmas_are_applied"
        status: pass
      - kind: unit
        ref: "tests/db/test_pragmas.py#test_sqlite_build_has_fts5"
        status: pass
    human_judgment: false
  - id: D5
    description: "GET / renders a persisted, normalised listing from a real DB read (title/company/location/source/posted + count) and an empty state on an empty database"
    requirement: null
    verification:
      - kind: integration
        ref: "tests/db/test_skeleton_boot.py#test_repository_write_is_rendered_by_get"
        status: pass
      - kind: integration
        ref: "tests/db/test_skeleton_boot.py#test_empty_database_renders_empty_state"
        status: pass
    human_judgment: false
  - id: D6
    description: "The deployment manifest matches the PLAT-01 contract: one app service, host-gateway extra_hosts, no published 4096 port, migration in the entrypoint, python:3.13-slim, and the three vendored assets committed"
    requirement: "PLAT-01"
    verification:
      - kind: unit
        ref: "tests/test_deploy_manifest.py"
        status: pass
    human_judgment: false
  - id: D7
    description: "The operator can actually start the whole stack with `docker compose up` and reach /health, then restart and see listings persist"
    requirement: "PLAT-01"
    verification: []
    human_judgment: true
    rationale: "Docker is absent from the agent sandbox, so the compose smoke and restart check cannot be executed here. Plan 01-07 owns the operator-run `scripts/compose-smoke.sh` check; recorded in .planning/WINDOWS.md."
  - id: D8
    description: "The auth seam is present on the app's route(s), so no route can be added without current_user"
    requirement: "PLAT-03"
    verification:
      - kind: other
        ref: "grep -c 'Depends(current_user)' app/web/routes.py -> 1"
        status: pass
    human_judgment: true
    rationale: "Only one route exists in this plan; the universal route-introspection test (tests/test_auth_seam.py) is owned by plan 01-05. Automation here proves the existing route only."

# Metrics
duration: 23min
completed: 2026-09-15
status: complete
---

# Phase 01 Plan 01: Walking Skeleton — migrate, write, read, render, deploy

**A bootable FastAPI app on migration 0001: a real two-key upsert writes a listing that `GET /` renders from SQLite, with WAL/PRAGMA guarantees pinned by tests and an app-only `docker compose up` deployment path serving vendored assets.**

## Performance

- **Duration:** 23 min
- **Started:** 2026-09-15T16:53:49Z
- **Completed:** 2026-09-15T17:16:52Z
- **Tasks:** 3 of 3
- **Files modified:** 40 (31 created application/test/config files + 3 vendored assets + 2 modified)

## Accomplishments

- **The one-way door is walked.** Migration 0001 creates the full schema — 16 tables plus the FTS5 external-content `listing_fts` virtual table — with both Tier-1 dedup indexes, explicitly named CHECK constraints, append-only `listing_events` triggers, and the three FTS5 maintenance triggers. `alembic upgrade head` on an empty file leaves a single head at `0001`.
- **A real write and a real read.** The ordered two-key Tier-1 upsert is idempotent for repeated ids, for key-B collisions on a shared canonical URL, and for the mandatory `source_listing_id = NULL` case; a listing written through the repository is rendered by `GET /` together with a count, and an empty database renders an empty state.
- **Every connection is configured.** `journal_mode=wal`, `foreign_keys=1` and `busy_timeout=5000` are applied through a listener on `engine.sync_engine`, and `ENABLE_FTS5` is present in the build's compile options.
- **The deployment path exists and is smokeable.** `compose.yml` defines the app service only (no opencode service, no `depends_on`, no published 4096 port, `host.docker.internal:host-gateway`), the entrypoint migrates then execs `uvicorn --workers 1`, the Dockerfile pins `python:3.13-slim` and exercises the migration against a throwaway file at build, and the Tailwind-built CSS plus HTMX/Alpine bundles are committed under `static/vendor/`.
- **The seams later phases inherit are in place.** One `Settings` class carries the whole D-02 probe envelope; `current_user()` is declared on the route; `create_app()`'s lifespan opens nothing that can fail hard.

## Task Commits

Each task was committed atomically:

1. **Task 1: Tracer — migrate → write → read → render, end to end** - `4c7a0c9` (feat)
2. **Task 2: Deployment skeleton — compose, Dockerfile, entrypoint, vendored assets** - `9e5eb01` (feat)
3. **Task 3: DB guarantees — two-key idempotency, persistence, PRAGMAs** - `8945024` (test)

**Plan metadata:** `docs(01-01): complete walking-skeleton plan` (SUMMARY + STATE + ROADMAP + REQUIREMENTS + WINDOWS)

_Note: the tracer task carried an automated-only `<verify>`, so the tracer feedback gate re-ran `tests/db/test_skeleton_boot.py` end-to-end after the Task 1 commit and continued without a checkpoint (interactive run, `human_verify_mode = end-of-phase`)._

## Files Created/Modified

- `pyproject.toml` / `requirements.txt` - exact pins (D-17), pytest `asyncio_mode = "auto"` + `live` marker + `pythonpath`, ruff config; JobSpy pinned to the full git SHA, never PyPI
- `app/config.py` - the single `Settings` class: auth seam id, both DB URLs, opencode surface, sanitise policy, the whole D-02 probe envelope, and the S2/S3/S4 thresholds
- `app/db/models.py` - SQLAlchemy 2.0 models for all 16 tables, `sa.String` + named `CheckConstraint`
- `alembic/versions/0001_initial_schema.py` - the one-way migration (`revision = "0001"`, `down_revision = None`)
- `alembic/env.py` / `alembic.ini` / `alembic/script.py.mako` - sync-URL Alembic setup with the PRAGMA listener
- `app/db/base.py`, `app/db/session.py` - declarative base, async engine, `apply_sqlite_pragmas`, `get_session()` dependency
- `app/db/repositories/listing_repo.py` - `UpsertOutcome`, `upsert_listing()`, `upsert_listing_source()`
- `app/api/deps.py`, `app/domain/models.py` - `LOCAL_USER`, `current_user()`, the frozen `User` dataclass
- `app/main.py`, `app/web/routes.py` - app factory, static mount, the queue route
- `app/web/templates/html/base.html`, `queue.html` - the layout and the queue list/empty state
- `compose.yml`, `Dockerfile`, `entrypoint.sh`, `.env.example` - the deployment surface
- `assets/tailwind/input.css`, `static/vendor/*` - the vendored asset pipeline
- `tests/conftest.py` - migrated-template + per-test-copy DB fixtures, engine/session/factory/client fixtures
- `tests/db/test_skeleton_boot.py`, `test_two_key_upsert.py`, `test_persistence.py`, `test_pragmas.py`, `tests/test_deploy_manifest.py` - 19 tests

## Decisions Made

- **Alembic uses the same PRAGMAs as the app.** The entrypoint runs `alembic upgrade head` before `uvicorn`, so the database should already be in the D-17 configuration when the first migration lands. Doing so also removed a real cost: the untuned rollback journal made the migration take ~16 s of fsync-bound wall-clock on this filesystem versus ~5 s in WAL + `synchronous=NORMAL`.
- **Guarded the PRAGMA autocommit toggle.** The documented `autocommit` dance is a pysqlite requirement; SQLAlchemy's aiosqlite adapter has no such attribute. `getattr(...)` keeps the documented behaviour on pysqlite while making the aiosqlite path work.
- **Test isolation via a template copy.** One session-scoped `alembic upgrade head` produces a template; each test copies the file, so it gets an empty *migrated* database without paying migration cost per test.
- **Kept `listing_sources.source` as a FK to `sources.name`.** Ingestion therefore requires a registered source row — the honest model, and it keeps referential integrity enforceable.
- **No queue-page stub.** The "Run search now" button and health strip are owned by plans 01-03 and 01-06, so `queue.html` ships only what this plan can make work.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `AsyncAdapt_aiosqlite_connection` has no `autocommit` attribute**
- **Found during:** Task 1 (tracer)
- **Issue:** The verbatim RESEARCH PRAGMA snippet (`dbapi_connection.autocommit = True`) raised `AttributeError` on every connection under `sqlite+aiosqlite`, so the app could not open the database at all.
- **Fix:** Toggle `autocommit` only when the DBAPI connection exposes it (`getattr` guard), which preserves the documented pysqlite behaviour and lets the aiosqlite connect-event path apply the pragmas directly (verified: `PRAGMA foreign_keys` returns 1).
- **Files modified:** `app/db/session.py`
- **Verification:** `tests/db/test_pragmas.py` passes; FK violations are now actually enforced (a `listing_sources` insert without a `sources` row correctly aborts).
- **Committed in:** `4c7a0c9` (Task 1 commit)

**2. [Rule 2 - Missing Critical] Alembic's engine was not applying the D-17 PRAGMAs**
- **Found during:** Task 1 (tracer) — the first migration ran in rollback-journal mode with `synchronous=FULL`, taking ~16 s of fsync-bound wall-clock and leaving the file out of the mode the app documents.
- **Fix:** Attach `apply_sqlite_pragmas` to the Alembic engine's `connect` event so the migrated database is WAL + `synchronous=NORMAL` from the first byte. Migration wall-clock fell to ~5 s.
- **Files modified:** `alembic/env.py`, `app/db/session.py` (helper made importable)
- **Verification:** `DATABASE_URL_SYNC=sqlite:////… alembic upgrade head` then `PRAGMA journal_mode` → `wal`; full suite runtime dropped from ~17 s to ~3 s.
- **Committed in:** `4c7a0c9` (Task 1 commit)

**3. [Rule 3 - Blocking] `pyyaml` was an undeclared test dependency**
- **Found during:** Task 2 (deployment manifest)
- **Issue:** `tests/test_deploy_manifest.py` must parse `compose.yml`; `yaml` was only present transitively via `uvicorn[standard]`, so the test would break if that extra changed.
- **Fix:** Added `pyyaml==6.0.3` to the `dev` extra with an explanatory comment. Verified against the pinned version table.
- **Files modified:** `pyproject.toml`
- **Verification:** `pip install` resolved it; the deploy-manifest test passes.
- **Committed in:** `9e5eb01` (Task 2 commit)

**4. [Rule 2 - Missing Critical] `.gitignore` did not cover generated runtime output**
- **Found during:** Task 2 (deployment skeleton)
- **Issue:** The plan asked only for `data/` and `node_modules/`, but the test run creates `.pytest_cache/` and `pytest-of-*/`, which would otherwise surface as untracked noise and risk an accidental commit.
- **Fix:** Added `data/`, `node_modules/`, `.pytest_cache/`, `pytest-of-*/` to `.gitignore` (the `.env` entry was kept).
- **Files modified:** `.gitignore`
- **Verification:** `git status --short` no longer lists the pytest temp directory.
- **Committed in:** `9e5eb01` (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (1 bug, 2 missing critical, 1 blocking)
**Impact on plan:** No scope creep. Deviation 1 was required for the app to open a database at all; deviations 2 and 4 protect the D-17 configuration and the repo's hygiene; deviation 3 keeps the test honest about its own dependency. Nothing architectural was changed.

## Issues Encountered

- **Sandbox packaging constraints (not plan issues, recorded for the next executor).** The root filesystem is 100% full, `ensurepip` is broken and system `pip` is PEP-668 externally-managed. The suite was run from a venv created with `python3 -m venv --without-pip` and populated via `python3 -m pip install --target .venv/lib/python3.14/site-packages …`; `npm` needed `npm_config_cache`/`TMPDIR` redirected onto `/workspace`. The local interpreter is **3.14.7** while the image pins **3.13** (D-17) — no application code depends on 3.14.
- **`repositories.listing_repo` import in tests** was made an explicit `from app.db.repositories import listing_repo` so the module-level monkeypatch target is unambiguous.

## User Setup Required

**External services require manual configuration.** See this plan's frontmatter `user_setup` for:
- **Docker Engine ≥ 20.10 + Compose v2** (the `host-gateway` mapping needs ≥20.10) — required to run the operator compose smoke, which is deferred to plan 01-07.
- **opencode server** — external and user-managed; Phase 1 only reports reachability and never blocks on it, so `docker compose up` needs no setup. `.env.example` documents `OPENCODE_BASE_URL`, `OPENCODE_MODEL` and the optional `OPENCODE_SERVER_PASSWORD`.

The plan's consolidated **dependency-legitimacy human-check** (resolved set vs the RESEARCH Package Legitimacy Audit; `aiosqlite`/`structlog` home pages; JobSpy resolving to the full SHA) is collected at phase verification per `workflow.human_verify_mode = end-of-phase`, and is recorded in `.planning/WINDOWS.md`.

## Next Phase Readiness

- **Ready for plan 01-02** (the 9-item migration acceptance checklist as assertions, PII-negative schema, FTS5 trigger proof): the migration exists, `tests/conftest.py` exposes `migrated_db` (a migrated temp file), `db_engine`, `session_factory`, `db_session` and `client`, and `alembic heads` reports `0001`.
- **Carried forward for later plans:** `norm` is still a mapping — plan 01-03 swaps in the typed `NormalisedListing`; `upsert_listing_source` already takes `run_id` and `now` for that path. Tests that ingest must register the `sources` row first (the FK is live, and `foreign_keys=ON` is actually enforced).
- **Blockers:** none for Phase 1 coding. The two open phase gates are (a) the operator compose smoke (Docker absent here → plan 01-07) and (b) the end-of-phase dependency-legitimacy human check. Both are recorded in `.planning/WINDOWS.md` so they cannot be forgotten at ship time.

---

*Phase: 01-walking-skeleton-foundations*
*Completed: 2026-09-15*

## Self-Check: PASSED

- All 31 key files listed in `key-files.created`/`modified` exist on disk (`[ -f ]` per path).
- Task commits `4c7a0c9`, `9e5eb01`, `8945024` are present in `git log --oneline --all`.
- Plan verification re-run: `python -m pytest -q tests/db/test_skeleton_boot.py tests/db/test_two_key_upsert.py tests/db/test_persistence.py tests/db/test_pragmas.py tests/test_deploy_manifest.py -x` → **19 passed**; `python -m pytest -q` → **19 passed**; `ruff check .` → **All checks passed**; `alembic heads` → **0001 (head)**.
- No stubs: the only `placeholder` match in the tree is Tailwind's `::placeholder` pseudo-element in the committed stylesheet.
