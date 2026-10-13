"""Shared test fixtures.

The schema is created by running **`alembic upgrade head`** against a real temp
file (never `:memory:` — WAL and FTS5 behaviour differ, and never
`Base.metadata.create_all`, which would not exercise the migration).

The default lane is offline: the app's LLM backend dependency is overridden with a
stub that never opens a socket. `/health` and the queue page must be honest about
an unreachable backend (D-08), and a test must never reach a live opencode server.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings, settings
from app.llm import get_llm_backend
from app.llm.base import DiscoveryResult, ProbeOutcome, StructuredCallResult

PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: The opencode settings the default lane must not inherit from the machine.
#: `settings = Settings()` runs at import and reads `.env` and the ambient
#: environment, so without pinning a developer's `.env` silently changes what the
#: suite observes — a non-empty `OPENCODE_SERVER_PASSWORD` flips `/health`'s
#: `auth_configured`, `OPENCODE_MODEL` changes what the stub backends advertise,
#: and the timeouts change what a call believes its budget is.
OPENCODE_SETTINGS_FIELDS = (
    "opencode_base_url",
    "opencode_model",
    "opencode_server_password",
    "opencode_timeout_seconds",
    "opencode_completion_timeout_seconds",
    "opencode_max_retries",
    "opencode_structured_retry_count",
    "opencode_discovery_retry_delay_seconds",
    "opencode_discovery_timeout_seconds",
)


@pytest.fixture(autouse=True)
def _pin_opencode_settings(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pin the app's opencode settings to their declared defaults, per test.

    The default lane must not depend on the developer's `.env` or exported env
    vars (the defect this fixture closes: a non-empty `OPENCODE_SERVER_PASSWORD`
    made `/health` report `auth_configured: True`). A test that wants a
    non-default value sets it itself with `monkeypatch.setattr`; the pin is the
    starting point, not a ceiling. The operator lanes (`-m live` / `-m latex`)
    deliberately read the real environment and are left untouched.
    """
    if request.node.get_closest_marker("live") or request.node.get_closest_marker(
        "latex"
    ):
        return
    for field in OPENCODE_SETTINGS_FIELDS:
        monkeypatch.setattr(settings, field, Settings.model_fields[field].default)


class OfflineLLMBackend:
    """Stands in for `OpenCodeServerBackend` without touching the network.

    "Unreachable" is the honest default here: it is the state the app must boot and
    serve in (D-08), and it keeps the health strip deterministic.
    """

    async def health(self) -> ProbeOutcome:
        return ProbeOutcome(reachable=False, error="offline-test-lane")

    async def discover_models(self) -> DiscoveryResult:
        return DiscoveryResult(reachable=False, error="offline-test-lane")

    async def complete_structured(self, **kwargs: object) -> StructuredCallResult:
        """Present so the selftest route cannot AttributeError — or reach a socket.

        Without this the default lane overrides `get_llm_backend` with a stub that
        lacks the method, and a careless test could fall through to the real
        `OpenCodeServerBackend` (Pitfall P10). The failure is the honest offline
        outcome, never a network call.
        """
        return StructuredCallResult(ok=False, status="error", error="offline-test-lane")



def _run_alembic_upgrade(db_path: Path, revision: str = "head") -> None:
    """Run the real migration against `db_path` as a subprocess."""
    env = {**os.environ, "DATABASE_URL_SYNC": f"sqlite:///{db_path}"}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


#: The tables that carry a foreign key to ``runs.id``. Migration 0002's
#: ``ck_runs_reason`` triggers Alembic's SQLite batch path
#: (CREATE -> COPY -> DROP -> RENAME); ``DROP TABLE runs`` fails while
#: ``foreign_keys=ON`` if any of these holds a row with a non-NULL ``run_id``.
RUN_REFERENCING_TABLES = (
    "listing_events",
    "listing_exclusions",
    "scores",
    "llm_calls",
    "source_request_log",
)


def _seed_0001(db_path: Path) -> dict[str, int]:
    """Populate a revision-0001 database with the rows the defect needs.

    Every table with an FK to ``runs.id`` gets exactly one row whose ``run_id``
    is non-NULL. Column names and NOT NULL requirements come from the actual
    0001 DDL, not from a guessed INSERT. Returns the per-table row counts so the
    upgrade test can prove none were lost.
    """
    connection = sqlite3.connect(db_path, isolation_level=None)
    try:
        now = "2026-09-16 00:00:00"

        connection.execute(
            "INSERT INTO sources (name, display_name) VALUES ('linkedin', 'LinkedIn')"
        )
        connection.execute(
            "INSERT INTO runs (trigger, status, started_at, finished_at) "
            "VALUES ('manual', 'done', ?, ?)",
            (now, now),
        )
        run_id = int(connection.execute("SELECT id FROM runs").fetchone()[0])
        connection.execute(
            "INSERT INTO listings "
            "(canonical_url, title, first_seen_at, last_seen_at, content_hash, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "https://example.com/populated/1",
                "Populated Role",
                now,
                now,
                "populated-hash-1",
                now,
                now,
            ),
        )
        listing_id = int(connection.execute("SELECT id FROM listings").fetchone()[0])

        # One row per runs.id child table, each with a non-NULL run_id.
        connection.execute(
            "INSERT INTO listing_events (listing_id, event_type, occurred_at, run_id) "
            "VALUES (?, 'view', ?, ?)",
            (listing_id, now, run_id),
        )
        connection.execute(
            "INSERT INTO listing_exclusions (listing_id, run_id, created_at) "
            "VALUES (?, ?, ?)",
            (listing_id, run_id, now),
        )
        connection.execute(
            "INSERT INTO scores (listing_id, run_id, created_at) VALUES (?, ?, ?)",
            (listing_id, run_id, now),
        )
        connection.execute(
            "INSERT INTO llm_calls (run_id, purpose, status, created_at) "
            "VALUES (?, 'rank', 'ok', ?)",
            (run_id, now),
        )
        connection.execute(
            "INSERT INTO source_request_log "
            "(source, run_id, occurred_at, kind) VALUES ('linkedin', ?, ?, 'search')",
            (run_id, now),
        )

        # Fold the WAL back into the main file so the copy is self-contained.
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in RUN_REFERENCING_TABLES
        }
        counts["runs"] = int(connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0])
        counts["listings"] = int(
            connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        )
        counts["sources"] = int(
            connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        )
        return counts
    finally:
        connection.close()


def _copy_sqlite(src: Path, dest: Path) -> None:
    """Copy a self-contained SQLite database (plus any sidecars) into place."""
    shutil.copy2(src, dest)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{src}{suffix}")
        if sidecar.exists():
            shutil.copy2(sidecar, Path(f"{dest}{suffix}"))


@pytest.fixture(scope="session")
def migrated_db_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A session-scoped temp directory holding one migrated template DB."""
    db_dir = tmp_path_factory.mktemp("jobsearch-db")
    db_path = db_dir / "template.db"
    _run_alembic_upgrade(db_path)
    return db_path


@pytest.fixture
def migrated_db(migrated_db_template: Path, tmp_path: Path) -> Path:
    """A fresh, empty, fully-migrated database file for one test."""
    dest = tmp_path / "jobsearch.db"
    _copy_sqlite(migrated_db_template, dest)
    return dest


@pytest.fixture(scope="session")
def populated_0001_template(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, dict[str, int]]:
    """A session-scoped revision-0001 database populated for the upgrade test.

    Built by running the real migration only to ``0001`` and then seeding it;
    it is deliberately **not** upgraded to head so each test can drive the
    upgrade itself and observe the failure on an unfixed ``env.py``.
    """
    db_dir = tmp_path_factory.mktemp("jobsearch-populated-0001")
    db_path = db_dir / "populated-0001.db"
    _run_alembic_upgrade(db_path, "0001")
    counts = _seed_0001(db_path)
    return db_path, counts


@pytest.fixture
def populated_0001(
    populated_0001_template: tuple[Path, dict[str, int]],
    tmp_path: Path,
) -> tuple[Path, dict[str, int]]:
    """A per-test copy of the populated 0001 database plus its expected counts."""
    template_path, counts = populated_0001_template
    dest = tmp_path / "populated-0001.db"
    _copy_sqlite(template_path, dest)
    return dest, counts


@pytest_asyncio.fixture
async def db_engine(migrated_db: Path) -> AsyncIterator[AsyncEngine]:
    """An async engine (with the PRAGMA listener) over the migrated temp file."""
    from app.db.session import build_engine

    engine = build_engine(f"sqlite+aiosqlite:///{migrated_db}")
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(
    db_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """An httpx client over the ASGI app, pointed at the temp DB.

    Both the request-scoped session and the *background-task* session factory are
    overridden, so a `POST /runs` pipeline writes to the temp database rather
    than the configured `/data/jobsearch.db`. The LLM backend is overridden with
    the offline stub so no test in the default lane opens a socket.
    """
    from app.db.session import get_session, get_session_factory
    from app.main import create_app

    app = create_app()

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_llm_backend] = OfflineLLMBackend

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http

    app.dependency_overrides.clear()


@pytest.fixture
def registry_snapshot() -> Iterator[None]:
    """Swap the adapter registry for one test, then restore it exactly."""
    from app.sources import registry

    saved = registry.all_adapters()
    try:
        yield
    finally:
        registry.clear()
        for adapter_cls in saved.values():
            registry.register(adapter_cls)
