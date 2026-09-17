"""The queue row reaches the posting: title anchor plus per-source links (QUEUE-06).

Two shapes are asserted, because they are what the live corpus actually contains:
an Indeed row whose employer URL differs from the board URL (155/155 differ) and a
LinkedIn row whose two URL columns are identical (0/128 differ).
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingSource, Source
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
    session_factory: async_sessionmaker[AsyncSession],
    *,
    source: str = "linkedin",
    index: int,
    title: str = "Backend Engineer",
    canonical_url: str | None = None,
    canonical_source_url: str | None = None,
) -> int:
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


async def test_the_title_links_to_the_posting(client, session_factory) -> None:
    await _register_sources(session_factory, "linkedin")
    await _seed_listing(
        session_factory, index=1, canonical_url="https://boards.example.com/job/1"
    )

    response = await client.get("/")

    assert response.status_code == 200
    assert (
        '<a class="listing-title-link" href="https://boards.example.com/job/1"'
        ' target="_blank" rel="noopener noreferrer">Backend Engineer</a>' in response.text
    )


async def test_a_listing_without_a_url_renders_a_plain_title(
    client, session_factory
) -> None:
    await _register_sources(session_factory, "linkedin")
    await _seed_listing(session_factory, index=2, canonical_url="")

    response = await client.get("/")

    assert '<td class="listing-title">Backend Engineer</td>' in response.text


async def test_an_indeed_row_offers_the_board_and_the_employer_link(
    client, session_factory
) -> None:
    await _register_sources(session_factory, "indeed")
    await _seed_listing(
        session_factory,
        source="indeed",
        index=3,
        canonical_source_url="https://employer.example.com/careers/3",
    )

    response = await client.get("/")

    assert (
        '<a class="source-link" href="https://indeed.example.com/jobs/3"'
        ' target="_blank" rel="noopener noreferrer">indeed</a>' in response.text
    )
    assert (
        '<a class="source-apply" href="https://employer.example.com/careers/3"'
        ' target="_blank" rel="noopener noreferrer">Apply</a>' in response.text
    )


async def test_a_linkedin_row_renders_one_link_and_no_apply_link(
    client, session_factory
) -> None:
    await _register_sources(session_factory, "linkedin")
    await _seed_listing(
        session_factory,
        index=4,
        canonical_source_url="https://linkedin.example.com/jobs/4",
    )

    response = await client.get("/")

    assert 'class="source-apply"' not in response.text
    assert (
        '<a class="source-link" href="https://linkedin.example.com/jobs/4"'
        ' target="_blank" rel="noopener noreferrer">linkedin</a>' in response.text
    )


async def test_a_merged_listing_renders_each_source(client, session_factory) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    listing_id = await _seed_listing(session_factory, index=5)
    async with session_factory() as session:
        first = await session.scalar(
            select(ListingSource).where(ListingSource.listing_id == listing_id)
        )
        assert first is not None
        session.add(
            ListingSource(
                listing_id=listing_id,
                source="indeed",
                source_listing_id="indeed-5",
                source_url="https://indeed.example.com/jobs/5",
                canonical_source_url="https://employer.example.com/careers/5",
                first_seen_at=first.first_seen_at,
                last_seen_at=first.last_seen_at,
                raw_hash="hash-5",
            )
        )
        await session.commit()

    response = await client.get("/")

    assert "https://linkedin.example.com/jobs/5" in response.text
    assert "https://indeed.example.com/jobs/5" in response.text
    assert "https://employer.example.com/careers/5" in response.text


async def test_every_external_link_is_target_blank_and_rel_noopener(
    client, session_factory
) -> None:
    await _register_sources(session_factory, "indeed")
    await _seed_listing(
        session_factory,
        source="indeed",
        index=6,
        canonical_url="https://boards.example.com/job/6",
        canonical_source_url="https://employer.example.com/careers/6",
    )

    response = await client.get("/")
    body = response.text

    # Every href in the page is either an absolute web URL or a root-relative path.
    # A `javascript:`/`data:` href would satisfy neither, which the narrower
    # `https?://` anchor scan below cannot even see.
    hrefs = re.findall(r'href="([^"]*)"', body)
    assert hrefs, "the queue page must contain at least one link"
    for href in hrefs:
        assert href.startswith(("http://", "https://")) or (
            href.startswith("/") and not href.startswith("//")
        ), href

    for anchor in re.findall(r"<a [^>]*href=\"https?://[^\"]+\"[^>]*>", body):
        assert 'target="_blank"' in anchor, anchor
        assert 'rel="noopener noreferrer"' in anchor, anchor


async def test_a_non_web_source_url_renders_the_source_name_as_plain_text(
    client, session_factory
) -> None:
    """The repository gate empties a `javascript:` URL; the row must then emit no anchor."""
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(session_factory, index=7)
    async with session_factory() as session:
        link = await session.scalar(
            select(ListingSource).where(ListingSource.listing_id == listing_id)
        )
        assert link is not None
        link.source_url = "javascript:alert(1)"
        link.canonical_source_url = "javascript:alert(1)"
        await session.commit()

    response = await client.get("/")

    assert response.status_code == 200
    assert "javascript:" not in response.text
    assert 'class="source-link"' not in response.text
    assert re.search(
        r'<td class="listing-source">\s*linkedin\s*</td>', response.text
    ), response.text

