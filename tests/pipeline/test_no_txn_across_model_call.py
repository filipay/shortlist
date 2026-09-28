"""Regression: no read transaction may span the model call.

A read transaction held open across a multi-second network call goes stale the
moment any other connection commits (the concurrent ranking task commits once per
listing); the following write then tries to upgrade that stale snapshot and SQLite
rejects it immediately with ``SQLITE_BUSY_SNAPSHOT`` — the production
``database is locked``. ``tailor_listing`` and ``rank_listing`` therefore commit
their read-only preamble before calling the model. This pins the invariant directly:
the stub asserts the session holds no transaction at the moment the model is called.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing
from app.llm.base import StructuredCallResult
from app.pipeline import rank as rank_module
from app.pipeline.rank import rank_listing
from app.pipeline.tailor import tailor_listing
from tests.pipeline.test_rank_stage import (
    NOW,
    StubBackend as RankStubBackend,
    _add_listing,
    _facts,
    _seed_run,
)
from tests.pipeline.test_tailor_stage import StubBackend as TailorStubBackend

_ASSERTION = "read transaction must not span the model call"


class _TxAssertingTailorBackend(TailorStubBackend):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    async def complete_structured(self, **kwargs: Any) -> StructuredCallResult:
        assert not self._session.in_transaction(), _ASSERTION
        return await super().complete_structured(**kwargs)


class _TxAssertingRankBackend(RankStubBackend):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    async def complete_structured(self, **kwargs: Any) -> StructuredCallResult:
        assert not self._session.in_transaction(), _ASSERTION
        return await super().complete_structured(**kwargs)


@pytest.fixture(autouse=True)
def _reset_in_flight(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`tailor_listing` reserves the shared module-level in-flight slot."""
    monkeypatch.setattr(rank_module, "_in_flight", 0)
    yield
    monkeypatch.setattr(rank_module, "_in_flight", 0)


async def test_tailor_holds_no_transaction_when_the_model_is_called(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _add_listing(session_factory, title="Txn Tailor Role")

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        stub = _TxAssertingTailorBackend(session)
        await tailor_listing(
            stub, session, listing=listing, facts=_facts(), requirements=[], now=NOW
        )
        await session.commit()

    assert len(stub.calls) == 1


async def test_rank_holds_no_transaction_when_the_model_is_called(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _seed_run(session_factory)
    listing_id = await _add_listing(session_factory, title="Txn Rank Role")

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        stub = _TxAssertingRankBackend(session)
        await rank_listing(
            stub,
            session,
            listing=listing,
            facts=_facts(),
            run_id=run_id,
            criteria_version=0,
            now=NOW,
        )
        await session.commit()

    assert len(stub.calls) == 1


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
