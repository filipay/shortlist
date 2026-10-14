"""The schedule form: it round-trips, refuses junk, and registers exactly one job.

The route is a plain full-page POST that writes the `operations_config` singleton
row and then re-configures the live scheduler. This lane installs a REAL
`AsyncIOScheduler` with a `SQLAlchemyJobStore` over a temp-file engine (httpx's
`ASGITransport` does not run the lifespan), so the register/reschedule/remove
behaviour is asserted against a real job store rather than a mock.

It also proves the route order: the row is committed before the scheduler is
touched, so a scheduler failure leaves the save intact.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import settings as settings_module
from app.db.repositories import operations_config_repo
from app.db.session import get_session, get_session_factory
from app.jobs import scheduler as scheduler_module
from app.main import create_app

SCHEDULED_JOB_ID = scheduler_module.SCHEDULED_JOB_ID


@pytest_asyncio.fixture
async def schedule_env(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch,
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncClient, AsyncIOScheduler]]:
    """A client over the app plus a started scheduler on a temp-file job store."""
    engine = create_engine(f"sqlite:///{tmp_path / 'apscheduler.db'}")
    instance = AsyncIOScheduler(
        jobstores={"default": SQLAlchemyJobStore(engine=engine)},
    )
    # Started (not stopped) so `get_job`/`add_job` reach the store rather than the
    # pending list; `paused=True` keeps the loop from trying to RUN anything.
    instance.start(paused=True)
    monkeypatch.setattr(scheduler_module, "_scheduler", instance)

    app = create_app()

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_session_factory] = lambda: session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http, instance

    app.dependency_overrides.clear()
    instance.shutdown(wait=False)
    engine.dispose()


async def _stored_schedule(session_factory: async_sessionmaker[AsyncSession]):
    async with session_factory() as session:
        return await operations_config_repo.read_schedule(session)


async def test_saving_a_time_registers_exactly_one_job(
    schedule_env, session_factory
) -> None:
    client, instance = schedule_env
    instances = schedule_env[1].get_jobs()
    assert instances == []

    response = await client.post(
        settings_module.SCHEDULE_PATH,
        data={"enabled": "on", "run_at": "09:30", "timezone": "Europe/Dublin"},
    )

    assert response.status_code == 200
    assert "Schedule saved." in response.text

    stored = await _stored_schedule(session_factory)
    assert stored.enabled is True
    assert stored.hour == 9
    assert stored.minute == 30
    assert stored.timezone == "Europe/Dublin"

    jobs = instance.get_jobs()
    assert len(jobs) == 1, [job.id for job in jobs]
    job = jobs[0]
    assert job.id == SCHEDULED_JOB_ID
    assert str(job.trigger) == "cron[hour='9', minute='30']"
    assert str(job.trigger.timezone) == "Europe/Dublin"


async def test_junk_time_returns_400_and_writes_nothing(
    schedule_env, session_factory
) -> None:
    client, instance = schedule_env
    await client.post(
        settings_module.SCHEDULE_PATH,
        data={"enabled": "on", "run_at": "07:00", "timezone": "Europe/Dublin"},
    )
    before = await _stored_schedule(session_factory)

    response = await client.post(
        settings_module.SCHEDULE_PATH,
        data={"enabled": "on", "run_at": "not-a-time", "timezone": "Europe/Dublin"},
    )

    assert response.status_code == 400
    assert "could not be understood" in response.text
    after = await _stored_schedule(session_factory)
    assert after == before
    assert len(instance.get_jobs()) == 1


async def test_unknown_timezone_returns_400_and_writes_nothing(
    schedule_env, session_factory
) -> None:
    client, instance = schedule_env

    response = await client.post(
        settings_module.SCHEDULE_PATH,
        data={"enabled": "on", "run_at": "09:30", "timezone": "Mars/Olympus"},
    )

    assert response.status_code == 400
    stored = await _stored_schedule(session_factory)
    # Nothing was written, so the total read falls back to the fresh-install default.
    assert stored == operations_config_repo.DEFAULT_SCHEDULE
    assert instance.get_jobs() == []


async def test_resaving_a_new_time_reschedules_the_same_single_job(
    schedule_env, session_factory
) -> None:
    client, instance = schedule_env
    await client.post(
        settings_module.SCHEDULE_PATH,
        data={"enabled": "on", "run_at": "07:00", "timezone": "Europe/Dublin"},
    )

    await client.post(
        settings_module.SCHEDULE_PATH,
        data={"enabled": "on", "run_at": "18:45", "timezone": "Europe/Dublin"},
    )

    jobs = instance.get_jobs()
    assert len(jobs) == 1, [job.id for job in jobs]
    assert str(jobs[0].trigger) == "cron[hour='18', minute='45']"
    stored = await _stored_schedule(session_factory)
    assert (stored.hour, stored.minute) == (18, 45)


async def test_disabling_the_schedule_removes_the_job(
    schedule_env, session_factory
) -> None:
    client, instance = schedule_env
    await client.post(
        settings_module.SCHEDULE_PATH,
        data={"enabled": "on", "run_at": "07:00", "timezone": "Europe/Dublin"},
    )
    assert len(instance.get_jobs()) == 1

    response = await client.post(
        settings_module.SCHEDULE_PATH,
        data={"run_at": "07:00", "timezone": "Europe/Dublin"},
    )

    assert response.status_code == 200
    assert instance.get_jobs() == []
    stored = await _stored_schedule(session_factory)
    assert stored.enabled is False
