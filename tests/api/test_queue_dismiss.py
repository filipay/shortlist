"""Dismiss the queue: one hide event per queued listing, and the fragment comes back empty.

Scope is "what the user sees with an empty search box and no toggles selected": the
free-text search and every UI toggle (`excluded`, `hidden`, `saved`, `scope`) are
dropped — NOT "every row in `listings`". An already-hidden listing must not gain a
second event, and an absorbed merge twin must never be dismissed (it is not in the
queue).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import (
    FilterRule,
    Listing,
    ListingDupe,
    ListingEvent,
    ListingExclusion,
    Run,
    Search,
    Source,
)
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing
from app.web import routes

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


async def test_dismiss_with_the_hidden_toggle_does_not_rehide_hidden_rows(
    client, session_factory
) -> None:
    """`?hidden=1` shows hidden rows, but dismiss must still not re-hide them.

    The hidden toggle is dropped alongside the text filter, so a bulk dismissal can
    never append a second `hide` to a listing that already carries one.
    """
    await _register_sources(session_factory, "linkedin")
    already_hidden = await _seed_listing(session_factory, index=70)
    await _seed_listing(session_factory, index=71)

    await client.post(f"/listings/{already_hidden}/events", data={"event_type": "hide"})
    assert await _hide_count(session_factory) == 1

    response = await client.post("/queue/dismiss?hidden=1")

    assert response.status_code == 200
    assert 'id="queue-dismiss"' in response.text
    # The already-hidden listing keeps exactly its one event; only the visible row gains one.
    assert await _hide_count(session_factory) == 2
    async with session_factory() as session:
        rehides = await session.scalar(
            select(func.count())
            .select_from(ListingEvent)
            .where(
                ListingEvent.listing_id == already_hidden,
                ListingEvent.event_type == "hide",
            )
        )
    assert rehides == 1


async def test_dismiss_refuses_when_the_queue_exceeds_the_ceiling(
    client, session_factory, monkeypatch
) -> None:
    """Over `_DISMISS_LIMIT`, refuse the whole action — never partially dismiss."""
    monkeypatch.setattr(routes, "_DISMISS_LIMIT", 2)
    await _register_sources(session_factory, "linkedin")
    for index in (80, 81, 82):
        await _seed_listing(session_factory, index=index)

    response = await client.post("/queue/dismiss")

    assert response.status_code == 400
    assert 'data-error="dismiss-over-limit"' in response.text
    assert await _hide_count(session_factory) == 0


async def test_dismiss_events_record_the_bulk_surface(client, session_factory) -> None:
    """A bulk dismissal is distinguishable from a hand-hide in the audit trail."""
    await _register_sources(session_factory, "linkedin")
    await _seed_listing(session_factory, index=90)

    await client.post("/queue/dismiss")

    async with session_factory() as session:
        contexts = (
            await session.scalars(
                select(ListingEvent.context_json).where(ListingEvent.event_type == "hide")
            )
        ).all()
    assert contexts == [{"surface": "queue_dismiss"}]


async def test_dismiss_ignores_the_saved_toggle(client, session_factory) -> None:
    """`?saved=1` must not narrow the dismissal to only the saved listings."""
    await _register_sources(session_factory, "linkedin")
    saved = await _seed_listing(session_factory, index=100)
    await _seed_listing(session_factory, index=101)

    await client.post(f"/listings/{saved}/events", data={"event_type": "save"})

    await client.post("/queue/dismiss?saved=1")

    # Both listings are hidden: the saved toggle was dropped, not honoured.
    assert await _hide_count(session_factory) == 2


async def test_dismiss_ignores_the_scope_toggle(client, session_factory) -> None:
    """`?scope=N` must not narrow the dismissal to that search's scope."""
    await _register_sources(session_factory, "linkedin")
    await _seed_listing(session_factory, index=110)
    out_of_scope = await _seed_listing(session_factory, index=111)

    async with session_factory() as session:
        scoped = Search(
            name="Scoped", enabled=True, criteria_json={}, created_at=NOW, updated_at=NOW
        )
        other = Search(
            name="Other", enabled=True, criteria_json={}, created_at=NOW, updated_at=NOW
        )
        session.add_all([scoped, other])
        await session.flush()
        rule = FilterRule(
            search_id=int(other.id),
            kind="location",
            params_json={"location": "Cork"},
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(rule)
        await session.flush()
        # An OLD run excluded the listing through the other search's rule, so it is out
        # of `scoped` but still in the default queue (the exclusion is not from the
        # latest run). A newer run is the latest and excludes nothing.
        old_run = Run(
            search_id=None,
            trigger="manual",
            status="done",
            started_at=NOW,
            finished_at=NOW,
        )
        latest_run = Run(
            search_id=None,
            trigger="manual",
            status="done",
            started_at=NOW + timedelta(hours=1),
            finished_at=NOW + timedelta(hours=1),
        )
        session.add_all([old_run, latest_run])
        await session.flush()
        session.add(
            ListingExclusion(
                listing_id=out_of_scope,
                run_id=int(old_run.id),
                rule_id=str(int(rule.id)),
                created_at=NOW,
            )
        )
        await session.commit()
        scope_id = int(scoped.id)

    response = await client.post(f"/queue/dismiss?scope={scope_id}")

    assert response.status_code == 200
    # Both listings are hidden: the scope toggle was dropped, not honoured.
    assert await _hide_count(session_factory) == 2


async def test_dismiss_ignores_the_excluded_toggle_and_spares_excluded_rows(
    client, session_factory
) -> None:
    """`?excluded=1` must not drag latest-run-excluded rows into the dismissal.

    This is the over-dismissal direction: honouring the excluded toggle would hide
    listings that are not in the queue at all, not merely leave some behind.
    """
    await _register_sources(session_factory, "linkedin")
    excluded = await _seed_listing(session_factory, index=120)
    visible = await _seed_listing(session_factory, index=121)

    async with session_factory() as session:
        run = Run(
            search_id=None,
            trigger="manual",
            status="done",
            started_at=NOW,
            finished_at=NOW,
        )
        session.add(run)
        await session.flush()
        session.add(
            ListingExclusion(
                listing_id=excluded,
                run_id=int(run.id),
                created_at=NOW,
            )
        )
        await session.commit()

    response = await client.post("/queue/dismiss?excluded=1")

    assert response.status_code == 200
    async with session_factory() as session:
        hides_by_listing = dict(
            (
                await session.execute(
                    select(ListingEvent.listing_id, func.count())
                    .where(ListingEvent.event_type == "hide")
                    .group_by(ListingEvent.listing_id)
                )
            ).all()
        )
    # The excluded row is not in the queue, so it must not have gained a hide event.
    assert hides_by_listing == {visible: 1}
