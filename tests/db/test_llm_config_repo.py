"""Selection storage is strict, durable, isolated from other operations settings."""

import pytest
from sqlalchemy import text

from app.llm.base import ProviderModel


async def test_pair_round_trip_clear_and_other_config_preservation(session_factory):
    from app.db.repositories import llm_config_repo, operations_config_repo
    schedule = operations_config_repo.ScheduleConfig(
        enabled=True, hour=9, minute=37, timezone="Europe/Dublin"
    )
    async with session_factory() as session:
        assert await llm_config_repo.read_selection(session) is None
        await operations_config_repo.write_schedule(session, schedule)
        await operations_config_repo.write_retention(session, "runs", 37)
        await operations_config_repo.write_skip_notice(session, reason="busy")
        await session.commit()
    pair = ProviderModel(provider_id='提供/"B', model_id='model/x/"雪')
    async with session_factory() as session:
        await llm_config_repo.write_selection(session, pair)
        await session.commit()
    async with session_factory() as session:
        assert await llm_config_repo.read_selection(session) == pair
        assert await operations_config_repo.read_retention(session) == {"runs": 37}
        assert (await operations_config_repo.read_skip_notice(session))["reason"] == "busy"
        await llm_config_repo.write_selection(session, None)
        await session.commit()
    async with session_factory() as session:
        assert await llm_config_repo.read_selection(session) is None
        assert await operations_config_repo.read_schedule(session) == schedule


async def test_writer_does_not_commit_and_validation_precedes_sql(session_factory):
    from app.db.repositories import llm_config_repo
    async with session_factory() as session:
        with pytest.raises(ValueError):
            await llm_config_repo.write_selection(
                session, ProviderModel(provider_id=" ", model_id="X")
            )
        assert not session.in_transaction()
        await llm_config_repo.write_selection(session, ProviderModel(provider_id="B", model_id="X"))
    async with session_factory() as session:
        assert await llm_config_repo.read_selection(session) is None


async def test_corrupt_half_pair_is_not_treated_as_environment_default(db_session):
    from app.db.repositories import llm_config_repo
    await db_session.execute(text("PRAGMA ignore_check_constraints=ON"))
    await db_session.execute(text(
        "INSERT INTO operations_config "
        "(id,schedule_json,retention_json,updated_at,llm_provider_id) "
        "VALUES (1,'{}','{}','2026-10-15','B')"
    ))
    with pytest.raises(ValueError):
        await llm_config_repo.read_selection(db_session)
