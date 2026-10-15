"""Strict global requested model selection. The caller owns the commit."""

from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OperationsConfig
from app.db.repositories.operations_config_repo import DEFAULT_SCHEDULE, SINGLETON_ID
from app.llm.base import ProviderModel

MAX_IDENTIFIER_LENGTH = 512


def validate_selection(selection: ProviderModel) -> ProviderModel:
    for value in (selection.provider_id, selection.model_id):
        if not isinstance(value, str) or not value.strip() or len(value) > MAX_IDENTIFIER_LENGTH:
            raise ValueError("Model selection requires two nonblank bounded identifiers")
    return selection


async def read_selection(session: AsyncSession) -> ProviderModel | None:
    row = (await session.execute(select(
        OperationsConfig.llm_provider_id, OperationsConfig.llm_model_id
    ).where(OperationsConfig.id == SINGLETON_ID))).one_or_none()
    if row is None or (row[0] is None and row[1] is None):
        return None
    if row[0] is None or row[1] is None:
        raise ValueError("Stored model selection is inconsistent")
    return validate_selection(ProviderModel(provider_id=row[0], model_id=row[1]))


async def write_selection(
    session: AsyncSession, selection: ProviderModel | None, *, now: datetime | None = None
) -> None:
    if selection is not None:
        validate_selection(selection)
    values = {
        "llm_provider_id": selection.provider_id if selection else None,
        "llm_model_id": selection.model_id if selection else None,
        "updated_at": now if now is not None else datetime.now(UTC),
    }
    statement = sqlite_insert(OperationsConfig).values(
        id=SINGLETON_ID, schedule_json=asdict(DEFAULT_SCHEDULE), retention_json={}, **values
    ).on_conflict_do_update(index_elements=["id"], set_=values)
    async with session.begin_nested():
        await session.execute(statement)
        await session.flush()
