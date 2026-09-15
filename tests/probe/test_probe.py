"""SRC-07 / T-01-31 — the liveness probe is cached, isolated and non-raising.

`probe()` is liveness, not the survival measurement (RESEARCH §Two distinct
instruments): one cheap request per board, TTL-cached so `/health` cannot hammer a
board, and total so one bad board never takes another down with it.

The stubs are registered under names of their own so these tests never touch the
real adapters — and the registry is cleared first, because `probe_all()` with no
`names` and no `session_factory` probes *every* registered adapter.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import Source
from app.probe.probe import clear_cache, probe_all, probe_source
from app.sources import registry
from app.sources.base import FetchBudget, FetchResult, JobSource, SearchQuery
from app.sources.linkedin import CAPABILITIES

SourceStatus = Literal["ok", "degraded", "unreachable"]

#: `name -> probe invocation count`, so caching is asserted behaviourally.
CALLS: dict[str, int] = {}


class StubAdapter(JobSource):
    """A registrable adapter whose probe is scripted by class attribute."""

    name = "stub_a"
    capabilities = CAPABILITIES
    status: SourceStatus | BaseException = "ok"

    async def probe(self) -> SourceStatus:
        CALLS[self.name] = CALLS.get(self.name, 0) + 1
        if isinstance(self.status, BaseException):
            raise self.status
        return self.status

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(source=self.name, items=[], status="ok")


class StubA(StubAdapter):
    name = "stub_a"
    status = "ok"


class StubB(StubAdapter):
    name = "stub_b"
    status = "degraded"


class BrokenA(StubAdapter):
    """`probe()` raises: the transport-error case, which must not propagate."""

    name = "stub_a"
    status = RuntimeError("connection reset by peer")


class UnknownStatus(StubAdapter):
    """A stub returning a value outside the contract."""

    name = "stub_a"
    status = "healthy"  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _fresh_probe_state() -> Iterator[None]:
    clear_cache()
    CALLS.clear()
    yield
    clear_cache()
    CALLS.clear()


@pytest.fixture
def stub_registry() -> Iterator[None]:
    """An empty registry holding only what a test registers."""
    saved = registry.all_adapters()
    registry.clear()
    try:
        yield
    finally:
        registry.clear()
        for adapter_cls in saved.values():
            registry.register(adapter_cls)


# --- shape --------------------------------------------------------------------


@pytest.mark.usefixtures("stub_registry")
async def test_probe_all_returns_one_entry_per_registered_adapter() -> None:
    registry.register(StubA)
    registry.register(StubB)

    result = await probe_all()

    assert result == {"stub_a": "ok", "stub_b": "degraded"}


@pytest.mark.usefixtures("stub_registry")
async def test_an_explicit_name_list_narrows_the_probe() -> None:
    registry.register(StubA)
    registry.register(StubB)

    result = await probe_all(names=("stub_b",))

    assert result == {"stub_b": "degraded"}
    assert CALLS == {"stub_b": 1}


@pytest.mark.usefixtures("stub_registry")
async def test_results_are_deterministically_ordered_by_source_name() -> None:
    registry.register(StubA)
    registry.register(StubB)

    result = await probe_all(names=("stub_b", "stub_a"))

    assert list(result) == ["stub_a", "stub_b"]


# --- isolation and totality ---------------------------------------------------


@pytest.mark.usefixtures("stub_registry")
async def test_one_raising_adapter_does_not_affect_the_other() -> None:
    registry.register(BrokenA)
    registry.register(StubB)

    result = await probe_all()

    assert result == {"stub_a": "unreachable", "stub_b": "degraded"}


@pytest.mark.usefixtures("stub_registry")
async def test_an_out_of_contract_status_is_reported_unreachable() -> None:
    registry.register(UnknownStatus)

    assert await probe_all() == {"stub_a": "unreachable"}


async def test_probe_source_is_total_for_an_unknown_name() -> None:
    assert await probe_source("no_such_board") == "unreachable"


@pytest.mark.usefixtures("stub_registry")
async def test_an_enabled_row_with_no_adapter_is_skipped_not_reported() -> None:
    registry.register(StubA)

    result = await probe_all(names=("stub_a", "ghost_board"))

    assert result == {"stub_a": "ok"}


# --- the TTL cache ------------------------------------------------------------


@pytest.mark.usefixtures("stub_registry")
async def test_a_second_call_inside_the_ttl_window_does_not_re_probe() -> None:
    registry.register(StubA)
    registry.register(StubB)

    await probe_all()
    second = await probe_all()

    assert second == {"stub_a": "ok", "stub_b": "degraded"}
    assert CALLS == {"stub_a": 1, "stub_b": 1}, "the TTL cache did not hold"


@pytest.mark.usefixtures("stub_registry")
async def test_force_bypasses_the_cache() -> None:
    registry.register(StubA)

    await probe_all()
    await probe_all(force=True)

    assert CALLS == {"stub_a": 2}


@pytest.mark.usefixtures("stub_registry")
async def test_clear_cache_re_opens_the_window() -> None:
    registry.register(StubA)

    await probe_all()
    clear_cache()
    await probe_all()

    assert CALLS == {"stub_a": 2}


@pytest.mark.usefixtures("stub_registry")
async def test_probe_source_caches_on_its_own() -> None:
    registry.register(StubA)

    assert await probe_source("stub_a") == "ok"
    assert await probe_source("stub_a") == "ok"

    assert CALLS == {"stub_a": 1}


@pytest.mark.usefixtures("stub_registry")
async def test_the_ttl_window_is_read_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry.register(StubA)
    # The window is stamped when a result is stored, so it must be patched before
    # the first probe: a hard-coded TTL would keep the second call a cache hit.
    monkeypatch.setattr(settings, "probe_cache_ttl_seconds", 0)

    await probe_all()
    await probe_all()

    assert CALLS == {"stub_a": 2}, "a zero TTL must expire immediately"


# --- persistence --------------------------------------------------------------


@pytest.mark.usefixtures("stub_registry")
async def test_a_fresh_probe_writes_the_sources_health_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry.register(StubB)
    async with session_factory() as session:
        session.add(Source(name="stub_b", display_name="Stub B"))
        await session.commit()

    result = await probe_all(session_factory=session_factory)

    assert result == {"stub_b": "degraded"}
    async with session_factory() as session:
        row = await session.scalar(select(Source).where(Source.name == "stub_b"))
    assert row is not None
    assert row.health == "degraded"
    assert row.last_probe_at is not None


@pytest.mark.usefixtures("stub_registry")
async def test_enabled_rows_are_resolved_from_the_database(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A registered adapter with no enabled `sources` row is not probed."""
    registry.register(StubA)
    registry.register(StubB)
    async with session_factory() as session:
        session.add(Source(name="stub_b", display_name="Stub B"))
        await session.commit()

    result = await probe_all(session_factory=session_factory)

    assert result == {"stub_b": "degraded"}
    assert "stub_a" not in CALLS


@pytest.mark.usefixtures("stub_registry")
async def test_a_cache_hit_does_not_rewrite_the_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry.register(StubA)
    async with session_factory() as session:
        session.add(Source(name="stub_a", display_name="Stub A"))
        await session.commit()

    await probe_all(session_factory=session_factory)
    async with session_factory() as session:
        first = await session.scalar(select(Source).where(Source.name == "stub_a"))
    await probe_all(session_factory=session_factory)
    async with session_factory() as session:
        second = await session.scalar(select(Source).where(Source.name == "stub_a"))

    assert first is not None and second is not None
    assert first.last_probe_at == second.last_probe_at, "a cache hit re-stamped last_probe_at"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
