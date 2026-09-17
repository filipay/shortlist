"""Dismiss the queue: one hide event per queued listing, and the fragment comes back empty.

Scope is "what the user sees with no filters applied" — NOT "every row in `listings`".
An already-hidden listing must not gain a second event, and an absorbed merge twin must
never be dismissed (it is not in the queue).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingDupe, ListingEvent, Source
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


async def _register_sources(
    session_factory: async_sessionmaker[AsyncSession], *names: str
) -> None:
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession], *, index: int
) -> int:
    raw = RawListing(
        source="linkedin",  # type: ignore[arg-type]
        source_listing_id=f"linkedin-{index}",
        source_url=f"https://linkedin.example.com/jobs/{index}",
        direct_url=None,
        title=f"Backend Engineer {index}",
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )
    norm = normalise_listing(raw)
    async with session_factory() as session:
        await upsert_listing_source(
            session, source="linkedin", norm=norm, run_id=None, now=NOW
        )
        await session.commit()
    async with session_factory() as session:
        return int(
            await session.scalar(
                select(Listing.id).where(Listing.canonical_url == norm.canonical_url)
            )
        )


async def _hide_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(ListingEvent)
                .where(ListingEvent.event_type == "hide")
            )
            or 0
        )


async def test_dismiss_appends_one_hide_event_per_queued_listing(
    client, session_factory
) -> None:
    await _register_sources(session_factory, "linkedin")
    for index in (1, 2, 3):
        await _seed_listing(session_factory, index=index)

    response = await client.post("/queue/dismiss")

    assert response.status_code == 200
    assert await _hide_count(session_factory) == 3
    assert "No listings yet" in response.text


async def test_dismissed_listings_stay_hidden_on_a_re_read(client, session_factory) -> None:
    await _register_sources(session_factory, "linkedin")
    await _seed_listing(session_factory, index=4)

    await client.post("/queue/dismiss")
    re_read = await client.get("/queue/list")

    assert 'id="listing-row-' not in re_read.text


async def test_dismiss_covers_the_whole_queue_not_just_the_page(
    client, session_factory
) -> None:
    """The page size is 25; the queue here is 30. A page-scoped dismiss would leave 5."""
    await _register_sources(session_factory, "linkedin")
    for index in range(10, 40):
        await _seed_listing(session_factory, index=index)

    await client.post("/queue/dismiss")

    assert await _hide_count(session_factory) == 30


async def test_dismiss_ignores_the_text_filter_but_not_the_hidden_gate(
    client, session_factory
) -> None:
    """`?q=` must not narrow the dismissal; already-hidden rows must not be re-hidden."""
    await _register_sources(session_factory, "linkedin")
    first = await _seed_listing(session_factory, index=50)
    await _seed_listing(session_factory, index=51)

    # Hide one listing by hand, then dismiss with a text filter set.
    await client.post(f"/listings/{first}/events", data={"event_type": "hide"})
    assert await _hide_count(session_factory) == 1

    await client.post("/queue/dismiss?q=Backend")

    # The hand-hidden listing keeps exactly one event; the visible one gains one.
    assert await _hide_count(session_factory) == 2


async def test_an_empty_queue_is_a_no_op(client, session_factory) -> None:
    response = await client.post("/queue/dismiss")

    assert response.status_code == 200
    assert await _hide_count(session_factory) == 0


async def test_dismiss_does_not_touch_an_absorbed_twin(client, session_factory) -> None:
    """A twin absorbed by a merge is out of the queue and must never be dismissed."""
    await _register_sources(session_factory, "linkedin", "indeed")
    survivor = await _seed_listing(session_factory, index=60)
    twin = await _seed_listing(session_factory, index=61)
    async with session_factory() as session:
        session.add(
            ListingDupe(
                listing_id=survivor,
                dup_listing_id=twin,
                method="fuzzy",
                score=0.97,
                merged_at=NOW,
            )
        )
        await session.commit()

    await client.post("/queue/dismiss")

    assert await _hide_count(session_factory) == 1
