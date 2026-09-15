"""Shared test fixtures.

The schema is created by running **`alembic upgrade head`** against a real temp
file (never `:memory:` — WAL and FTS5 behaviour differ, and never
`Base.metadata.create_all`, which would not exercise the migration).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_alembic_upgrade(db_path: Path) -> None:
    """Run the real migration against `db_path` as a subprocess."""
    env = {**os.environ, "DATABASE_URL_SYNC": f"sqlite:///{db_path}"}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


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
    shutil.copy2(migrated_db_template, dest)
    for suffix in ("-wal", "-shm"):
        src = Path(f"{migrated_db_template}{suffix}")
        if src.exists():
            shutil.copy2(src, Path(f"{dest}{suffix}"))
    return dest


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
    than the configured `/data/jobsearch.db`.
    """
    from app.db.session import get_session, get_session_factory
    from app.main import create_app

    app = create_app()

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_session_factory] = lambda: session_factory

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
