"""Provenance as data: every queue row carries the posting URL and its per-source links.

The queue row must never make the template do work, and the links must not cost a
second query per row. `employer_url` is populated ONLY when it differs from the board
URL — that single guard is what makes an Indeed row (where the two columns differ,
155/155 in the live corpus) offer the employer's own posting while a LinkedIn row
(where they are identical, 0/128) renders one link.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingSource, Source
from app.db.repositories.listing_repo import upsert_listing_source
from app.db.repositories.queue_repo import QueueQuery, SourceLink, read_queue
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


@contextmanager
def _statements_matching(engine, needle: str) -> Iterator[list[str]]:
    """Record every statement whose SQL contains `needle`, for one block."""
    seen: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        if needle in statement:
            seen.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _record)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _record)


async def _register_sources(
    session_factory: async_sessionmaker[AsyncSession], *names: str
) -> None:
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    source: str = "linkedin",
    index: int,
    title: str = "Backend Engineer",
    canonical_url: str | None = None,
    canonical_source_url: str | None = None,
) -> int:
    """Seed one listing through the real ingestion path, then pin the URL columns.

    Ingestion is used so every NOT NULL column and every normalised field is filled
    by the code that owns that mapping. The URL columns are then set explicitly,
    because this lane is about RENDERING provenance, not about how an adapter fills
    those columns (covered by `tests/db/test_two_key_upsert.py`).
    """
    raw = RawListing(
        source=source,  # type: ignore[arg-type]
        source_listing_id=f"{source}-{index}",
        source_url=f"https://{source}.example.com/jobs/{index}",
        direct_url=None,
        title=title,
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )
    norm = normalise_listing(raw)
    async with session_factory() as session:
        await upsert_listing_source(session, source=source, norm=norm, run_id=None, now=NOW)
        await session.commit()

    async with session_factory() as session:
        listing_id = int(
            await session.scalar(
                select(Listing.id).where(Listing.canonical_url == norm.canonical_url)
            )
        )
        if canonical_url is not None:
            listing = await session.get(Listing, listing_id)
            assert listing is not None
            listing.canonical_url = canonical_url
        if canonical_source_url is not None:
            link = await session.scalar(
                select(ListingSource).where(ListingSource.listing_id == listing_id)
            )
            assert link is not None
            link.canonical_source_url = canonical_source_url
        await session.commit()
    return listing_id


async def _read_one(
    session_factory: async_sessionmaker[AsyncSession], listing_id: int
):
    async with session_factory() as session:
        page = await read_queue(
            session,
            query=QueueQuery(),
            now=NOW,
            stale_after_days=14,
            watermark=None,
        )
    return next(row for row in page.rows if row.id == listing_id)


async def test_row_carries_the_canonical_url(session_factory) -> None:
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(
        session_factory, index=1, canonical_url="https://boards.example.com/job/1"
    )

    row = await _read_one(session_factory, listing_id)

    assert row.url == "https://boards.example.com/job/1"


async def test_a_listing_without_a_canonical_url_reports_none(session_factory) -> None:
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(session_factory, index=2, canonical_url="")

    row = await _read_one(session_factory, listing_id)

    assert row.url is None


async def test_one_link_per_source_with_the_board_url(session_factory) -> None:
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(session_factory, index=3)

    row = await _read_one(session_factory, listing_id)

    assert row.source_links == (
        SourceLink(source="linkedin", url="https://linkedin.example.com/jobs/3"),
    )
    assert row.sources == ("linkedin",)


async def test_employer_url_is_omitted_when_it_matches_the_board_url(
    session_factory,
) -> None:
    """The LinkedIn shape: both columns hold the same /jobs/view/<id> URL."""
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(
        session_factory,
        index=4,
        canonical_source_url="https://linkedin.example.com/jobs/4",
    )

    row = await _read_one(session_factory, listing_id)

    assert row.source_links[0].employer_url is None


async def test_employer_url_is_kept_when_it_differs(session_factory) -> None:
    """The Indeed shape: the board page and the employer's own posting both exist."""
    await _register_sources(session_factory, "indeed")
    listing_id = await _seed_listing(
        session_factory,
        source="indeed",
        index=5,
        canonical_source_url="https://employer.example.com/careers/5",
    )

    row = await _read_one(session_factory, listing_id)

    assert row.source_links == (
        SourceLink(
            source="indeed",
            url="https://indeed.example.com/jobs/5",
            employer_url="https://employer.example.com/careers/5",
        ),
    )


async def test_a_second_source_row_is_a_second_link(session_factory) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    listing_id = await _seed_listing(session_factory, index=6)
    async with session_factory() as session:
        first = await session.scalar(
            select(ListingSource).where(ListingSource.listing_id == listing_id)
        )
        assert first is not None
        session.add(
            ListingSource(
                listing_id=listing_id,
                source="indeed",
                source_listing_id="indeed-6",
                source_url="https://indeed.example.com/jobs/6",
                canonical_source_url="https://employer.example.com/careers/6",
                first_seen_at=first.first_seen_at,
                last_seen_at=first.last_seen_at,
                raw_hash="hash-6",
            )
        )
        await session.commit()

    row = await _read_one(session_factory, listing_id)

    assert [link.source for link in row.source_links] == ["indeed", "linkedin"]
    assert row.sources == ("indeed", "linkedin")


async def test_the_page_reads_provenance_in_one_query(
    session_factory, db_engine
) -> None:
    await _register_sources(session_factory, "linkedin")
    for index in range(7, 12):
        await _seed_listing(session_factory, index=index)

    with _statements_matching(db_engine, "FROM listing_sources") as statements:
        async with session_factory() as session:
            await read_queue(
                session,
                query=QueueQuery(limit=25),
                now=NOW,
                stale_after_days=14,
                watermark=None,
            )

    assert len(statements) == 1, statements
