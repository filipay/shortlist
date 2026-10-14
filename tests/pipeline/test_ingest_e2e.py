"""SRC-01 / SRC-05 / QUEUE-02 — a LinkedIn fixture run ingests, persists and renders."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingSource, Run, Source
from app.pipeline.run import run_pipeline
from app.sources import registry
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    SearchQuery,
    SourceCapabilities,
)
from app.sources.linkedin import CAPABILITIES, map_jobspy_row

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "listings"


def _without_new_signal(body: str) -> str:
    """`body` with the `new`-since-last-visit signal stripped.

    Plan 02-07's watermark advance makes exactly this one difference legitimate
    between two consecutive queue loads, so normalising it out lets a byte comparison
    still catch any OTHER divergence.
    """
    body = re.sub(r' data-new="\d"', "", body)
    return body.replace('<span class="badge badge-new">new</span>', "")


class FixtureLinkedIn(JobSource):
    """A fixture-backed LinkedIn adapter registered under the real board name."""

    name = "linkedin"
    capabilities: SourceCapabilities = CAPABILITIES

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        rows = json.loads((FIXTURES / "linkedin_page1.json").read_text(encoding="utf-8"))
        return FetchResult(
            source=self.name,
            items=[map_jobspy_row(row, source=self.name) for row in rows],
            status="ok",
            requests_used=1,
        )


@pytest.fixture
def fixture_registry() -> Iterator[None]:
    """Swap the registry for the duration of one test, then restore it."""
    saved = registry.all_adapters()
    try:
        yield
    finally:
        registry.clear()
        for adapter_cls in saved.values():
            registry.register(adapter_cls)


async def _register_source(
    session_factory: async_sessionmaker[AsyncSession], name: str
) -> None:
    async with session_factory() as session:
        session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _count(
    session_factory: async_sessionmaker[AsyncSession], table: type
) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(table)) or 0


@pytest.mark.usefixtures("fixture_registry")
async def test_ingest_e2e_persists_dedups_and_renders(
    session_factory: async_sessionmaker[AsyncSession],
    client,
) -> None:
    registry.register(FixtureLinkedIn)
    await _register_source(session_factory, "linkedin")

    run_id = await run_pipeline("manual", None, session_factory)

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        titles = sorted(
            (await session.execute(select(Listing.title))).scalars().all()
        )

    assert run is not None
    assert run.status == "done"
    assert run.finished_at is not None
    # Exactly one listing_sources row per fixture item (two rows in page1).
    assert await _count(session_factory, ListingSource) == 2
    assert await _count(session_factory, Listing) == 2
    assert titles == ["Platform Engineer", "Senior Python Engineer"]

    response = await client.get("/")
    assert response.status_code == 200
    assert "Senior Python Engineer" in response.text
    assert "2 listings" in response.text


@pytest.mark.usefixtures("fixture_registry")
async def test_reingesting_the_identical_payload_does_not_duplicate(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry.register(FixtureLinkedIn)
    await _register_source(session_factory, "linkedin")

    await run_pipeline("manual", None, session_factory)
    first = await _count(session_factory, ListingSource)

    run_id = await run_pipeline("manual", None, session_factory)
    second = await _count(session_factory, ListingSource)

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert first == 2
    assert second == 2, "re-ingesting the same payload must not create a second row"
    assert run is not None and run.status == "done"


@pytest.mark.usefixtures("fixture_registry")
async def test_sanitise_stage_ran_and_dropped_the_email_canary(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry.register(FixtureLinkedIn)
    await _register_source(session_factory, "linkedin")

    await run_pipeline("manual", None, session_factory)

    async with session_factory() as session:
        descriptions = (await session.execute(select(Listing.description))).scalars().all()
        events = (await session.execute(select(Run.errors_json))).scalars().all()

    joined = " ".join(text or "" for text in descriptions)
    assert "PII-CANARY-EMAIL-VALUE" not in joined
    assert "PII-CANARY-EMAIL-VALUE" not in repr(events)
    assert any("Build the thing" in (text or "") for text in descriptions)


@pytest.mark.usefixtures("fixture_registry")
async def test_queue_order_is_deterministic_when_first_seen_at_is_equal(
    session_factory: async_sessionmaker[AsyncSession],
    client,
) -> None:
    """Both fixture items are persisted with the SAME `first_seen_at`, so the
    id-descending tie-break is the only thing that can order them — and two
    identical requests must render the same rows in the same order.

    Plan 02-07 narrowed this from a whole-body byte comparison. Opening the queue now
    advances the `queue_state` watermark (D-39), so the SECOND render legitimately
    drops the `new` signal the first one showed — that is the feature, not drift. The
    contract this test exists for is the ROW ORDER, so it is asserted directly, and
    the two bodies are asserted byte-identical once the one deliberate difference is
    normalised out (catching any OTHER divergence between two identical requests).
    """
    registry.register(FixtureLinkedIn)
    await _register_source(session_factory, "linkedin")

    await run_pipeline("manual", None, session_factory)

    first = await client.get("/")
    second = await client.get("/")

    assert _without_new_signal(first.text) == _without_new_signal(second.text), (
        "two identical requests must differ only in the new-since-last-visit signal"
    )

    # The title cell now optionally wraps the title in the posting anchor, so the
    # extraction tolerates the anchor rather than dropping it; the asserted titles
    # are unchanged.
    titles = re.findall(
        r'<td class="listing-title" data-label="Title">(?:<a [^>]*>)?([^<]+)',
        first.text,
    )
    assert titles == ["Platform Engineer", "Senior Python Engineer"], (
        "expected id-descending order as the tie-break on equal first_seen_at"
    )
    assert titles == re.findall(
        r'<td class="listing-title" data-label="Title">(?:<a [^>]*>)?([^<]+)',
        second.text,
    ), (
        "the order must not change between two identical requests"
    )
