"""QUEUE-07 / D-39 / D-40 — new since last visit, stale, and the explicit action.

`new` and `stale` are asserted to be two INDEPENDENT badges: a listing that was just
ingested and is already inactive is both, and neither suppresses the other. The
watermark is a database row advanced by opening the queue or by `Mark all as seen`,
never by any other read, and never backwards.
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import Listing, QueueState, Source
from app.db.repositories.listing_repo import upsert_listing_source
from app.db.repositories.state_repo import advance_watermark, get_watermark
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

#: id -> {"new": bool, "stale": bool}, read off the row's own data attributes.
ROW_RE = re.compile(
    r'<tr id="listing-row-(\d+)"[^>]*data-new="(\d)"[^>]*data-stale="(\d)"'
)

STALE_DAYS = settings.stale_after_days


def _naive(value: datetime) -> datetime:
    """SQLite stores and returns naive datetimes; compare on the instant."""
    return value.replace(tzinfo=None) if value.tzinfo else value


def _rows(body: str) -> dict[int, dict[str, bool]]:
    return {
        int(match.group(1)): {"new": match.group(2) == "1", "stale": match.group(3) == "1"}
        for match in ROW_RE.finditer(body)
    }


async def _register_sources(
    session_factory: async_sessionmaker[AsyncSession], *names: str
) -> None:
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _seed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    title: str,
    index: int,
    first_seen: datetime,
    last_seen: datetime,
    active: bool = True,
) -> int:
    raw = RawListing(
        source="linkedin",  # type: ignore[arg-type]
        source_listing_id=f"linkedin-{index}",
        source_url=f"https://linkedin.example.com/jobs/{index}",
        direct_url=None,
        title=title,
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )
    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session,
            source="linkedin",
            norm=normalise_listing(raw),
            run_id=None,
            now=last_seen,
        )
        listing_id = int(outcome.listing_id)
        await session.commit()

    # `upsert_listing_source` stamps `first_seen_at` with the same clock it is given,
    # so the two timestamps are set explicitly here to model a real listing whose
    # first sighting and last sighting differ.
    async with session_factory() as session:
        await session.execute(
            update(Listing)
            .where(Listing.id == listing_id)
            .values(first_seen_at=first_seen, last_seen_at=last_seen, is_active=active)
        )
        await session.commit()
    return listing_id


async def _set_watermark(
    session_factory: async_sessionmaker[AsyncSession], moment: datetime
) -> None:
    async with session_factory() as session:
        await advance_watermark(session, now=moment)
        await session.commit()


# --- new ----------------------------------------------------------------------


async def test_listings_after_the_watermark_are_new_and_before_it_are_not(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    now = datetime.now(UTC)
    anchor = now - timedelta(days=3)
    await _register_sources(session_factory, "linkedin")
    await _set_watermark(session_factory, anchor)
    older = await _seed(
        session_factory,
        title="Seen Already",
        index=1,
        first_seen=anchor - timedelta(days=1),
        last_seen=now,
    )
    newer = await _seed(
        session_factory,
        title="Brand New",
        index=2,
        first_seen=anchor + timedelta(days=1),
        last_seen=now,
    )

    response = await client.get("/")

    assert response.status_code == 200
    rows = _rows(response.text)
    assert rows[older]["new"] is False, "a listing older than the watermark is not new"
    assert rows[newer]["new"] is True, "a listing newer than the watermark is new"


async def test_a_null_watermark_marks_every_listing_new(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """`NULL` is "never viewed", which is the honest default on a fresh database."""
    now = datetime.now(UTC)
    await _register_sources(session_factory, "linkedin")
    first = await _seed(
        session_factory, title="One", index=1, first_seen=now, last_seen=now
    )
    second = await _seed(
        session_factory, title="Two", index=2, first_seen=now, last_seen=now
    )

    response = await client.get("/")

    rows = _rows(response.text)
    assert rows[first]["new"] is True
    assert rows[second]["new"] is True
    assert "badge-new" in response.text


# --- stale --------------------------------------------------------------------


async def test_the_stale_boundary_is_n_minus_one_n_and_n_plus_one(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    now = datetime.now(UTC)
    await _register_sources(session_factory, "linkedin")
    fresh = await _seed(
        session_factory,
        title="Fresh",
        index=1,
        first_seen=now,
        last_seen=now - timedelta(days=STALE_DAYS - 1),
    )
    boundary = await _seed(
        session_factory,
        title="Boundary",
        index=2,
        first_seen=now,
        last_seen=now - timedelta(days=STALE_DAYS),
    )
    old = await _seed(
        session_factory,
        title="Old",
        index=3,
        first_seen=now,
        last_seen=now - timedelta(days=STALE_DAYS + 1),
    )

    response = await client.get("/")

    rows = _rows(response.text)
    assert rows[fresh]["stale"] is False, "N-1 days is not stale"
    assert rows[boundary]["stale"] is True, "exactly N days IS stale (<= now - N)"
    assert rows[old]["stale"] is True, "N+1 days is stale"


async def test_an_inactive_listing_is_stale_regardless_of_last_seen(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    now = datetime.now(UTC)
    await _register_sources(session_factory, "linkedin")
    inactive = await _seed(
        session_factory,
        title="Withdrawn",
        index=1,
        first_seen=now,
        last_seen=now,
        active=False,
    )

    response = await client.get("/")

    assert _rows(response.text)[inactive]["stale"] is True


async def test_a_listing_can_be_both_new_and_stale(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The independence assumption: neither badge suppresses the other."""
    now = datetime.now(UTC)
    anchor = now - timedelta(days=5)
    await _register_sources(session_factory, "linkedin")
    await _set_watermark(session_factory, anchor)
    both = await _seed(
        session_factory,
        title="Just In And Already Gone",
        index=1,
        first_seen=anchor + timedelta(days=1),
        last_seen=now - timedelta(days=STALE_DAYS + 2),
        active=False,
    )

    response = await client.get("/")

    row = _rows(response.text)[both]
    assert row["new"] is True and row["stale"] is True
    assert "badge-new" in response.text and "badge-stale" in response.text


# --- the watermark lifecycle --------------------------------------------------


async def test_mark_all_as_seen_clears_the_badges_and_keeps_the_rows(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    now = datetime.now(UTC)
    await _register_sources(session_factory, "linkedin")
    first = await _seed(session_factory, title="One", index=1, first_seen=now, last_seen=now)
    second = await _seed(session_factory, title="Two", index=2, first_seen=now, last_seen=now)

    before = await client.get("/")
    assert all(row["new"] for row in _rows(before.text).values())

    marked = await client.post("/queue/mark-seen")

    assert marked.status_code == 200
    assert "badge-new" not in marked.text, "the fragment already shows the cleared state"
    assert "listing-row-" in marked.text
    assert sorted(_rows(marked.text)) == sorted([first, second]), "no row disappeared"

    after = await client.get("/")
    assert "badge-new" not in after.text
    assert sorted(_rows(after.text)) == sorted([first, second])


async def test_opening_the_queue_advances_the_watermark_every_time(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The documented per-open advance — and only one writer of the row."""
    await _register_sources(session_factory, "linkedin")
    moment = datetime.now(UTC)
    await _seed(session_factory, title="One", index=1, first_seen=moment, last_seen=moment)
    anchor = moment - timedelta(days=30)
    await _set_watermark(session_factory, anchor)

    await client.get("/")
    async with session_factory() as session:
        first = await get_watermark(session)
    assert first is not None and _naive(first) > _naive(anchor), "the first open advanced it"

    await asyncio.sleep(0.005)  # guarantee an observable clock delta between requests
    await client.get("/")
    async with session_factory() as session:
        second = await get_watermark(session)
    assert second is not None and _naive(second) > _naive(first), "the second open advanced it too"


async def test_a_fragment_read_does_not_advance_the_watermark(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A predicate swap is not a visit: only `GET /` and `Mark all as seen` write."""
    await _register_sources(session_factory, "linkedin")
    anchor = datetime.now(UTC) - timedelta(days=30)
    await _set_watermark(session_factory, anchor)

    response = await client.get("/queue/list")

    assert response.status_code == 200
    async with session_factory() as session:
        stored = await get_watermark(session)
    assert stored is not None
    assert _naive(stored) == _naive(anchor), "the fragment read must not write"


async def test_the_queue_state_table_stays_single_row(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _register_sources(session_factory, "linkedin")
    await client.get("/")
    await client.post("/queue/mark-seen")
    await client.get("/")

    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(QueueState))
    assert count == 1
