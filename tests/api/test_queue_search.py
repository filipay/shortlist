"""QUEUE-06 / T-02-26 / T-02-27 — the queue is searchable, safely and deterministically.

Three properties are asserted here rather than assumed: hostile input never 500s,
the row order is identical across two identical requests (the tie-break contract),
and the visibility predicate that hides an absorbed twin is decided by an automated
check rather than by prose.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingDupe, Source
from app.db.repositories.dupe_repo import apply_merge, revert_merge
from app.db.repositories.listing_repo import upsert_listing_source
from app.domain.dedup import MergeDecision
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

ROW_ID_RE = re.compile(r'id="listing-row-(\d+)"')
ROW_TR_RE = re.compile(r'<tr id="listing-row-(\d+)"')

DAY = datetime(2026, 9, 1, tzinfo=UTC)
REVERTED_AT = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)


def _norm(
    source: str,
    *,
    title: str,
    index: int,
    description: str = "Build the thing.",
    location: str | None = "Dublin, Ireland",
) -> object:
    return normalise_listing(
        RawListing(
            source=source,  # type: ignore[arg-type]
            source_listing_id=f"{source}-{index}",
            source_url=f"https://{source}.example.com/jobs/{index}",
            direct_url=None,
            title=title,
            company_name="Acme",
            location_raw=location,
            description=description,
            posted_at=date(2026, 9, 1),
        )
    )


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
    source: str,
    label: str,
    title: str,
    index: int,
    first_seen: datetime = DAY,
    description: str = "Build the thing.",
    location: str | None = "Dublin, Ireland",
) -> int:
    """One listing through the production normalise + upsert path."""
    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session,
            source=source,
            norm=_norm(
                source,
                title=title,
                index=index,
                description=description,
                location=location,
            ),
            run_id=None,
            now=first_seen,
        )
        await session.commit()
        assert outcome.listing_id is not None, label
        return int(outcome.listing_id)


def _ids(body: str) -> list[int]:
    return [int(value) for value in ROW_TR_RE.findall(body)]


# --- search -------------------------------------------------------------------


async def test_search_returns_the_matching_row_and_not_the_other(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _register_sources(session_factory, "linkedin")
    await _seed(
        session_factory, source="linkedin", label="match", title="Senior Python Engineer", index=1
    )
    await _seed(
        session_factory, source="linkedin", label="other", title="Data Scientist", index=2
    )

    response = await client.get("/", params={"q": "engineer"})

    assert response.status_code == 200
    assert "Senior Python Engineer" in response.text
    assert "Data Scientist" not in response.text
    assert "1 listing" in response.text


async def test_an_apostrophe_query_returns_200_not_500(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The exact Pitfall 3 case: raw `it's` is an FTS5 syntax error."""
    await _register_sources(session_factory, "linkedin")
    await _seed(session_factory, source="linkedin", label="one", title="Engineer", index=1)

    response = await client.get("/", params={"q": "it's"})

    assert response.status_code == 200


async def test_a_hyphenated_query_returns_200_not_500(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Raw `runner-up` fails with `no such column: up`."""
    await _register_sources(session_factory, "linkedin")
    await _seed(session_factory, source="linkedin", label="one", title="Engineer", index=1)

    response = await client.get("/", params={"q": "runner-up"})

    assert response.status_code == 200


async def test_identical_search_requests_return_an_identical_row_order(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The tie-break contract: three rows with an IDENTICAL bm25 score must still
    come back in one deterministic order, and that order is `id DESC`."""
    await _register_sources(session_factory, "linkedin")
    first = await _seed(session_factory, source="linkedin", label="a", title="Engineer", index=1)
    second = await _seed(session_factory, source="linkedin", label="b", title="Engineer", index=2)
    third = await _seed(session_factory, source="linkedin", label="c", title="Engineer", index=3)

    one = await client.get("/queue/list", params={"q": "engineer"})
    two = await client.get("/queue/list", params={"q": "engineer"})

    assert one.status_code == 200 and two.status_code == 200
    assert _ids(one.text) == _ids(two.text), "two identical requests must not reorder"
    assert _ids(one.text) == [third, second, first], "the unique tie-break is id DESC"


async def test_no_query_keeps_the_phase_one_order(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """`first_seen_at DESC, id DESC` — NOT id order.

    The second listing is seeded with an EARLIER `first_seen_at` than the first, so
    an implementation that fell back to `id DESC` alone would fail this.
    """
    await _register_sources(session_factory, "linkedin")
    newer = await _seed(
        session_factory,
        source="linkedin",
        label="newer",
        title="Newer Role",
        index=1,
        first_seen=DAY + timedelta(days=5),
    )
    older = await _seed(
        session_factory,
        source="linkedin",
        label="older",
        title="Older Role",
        index=2,
        first_seen=DAY,
    )

    response = await client.get("/queue/list")

    assert response.status_code == 200
    assert _ids(response.text) == [newer, older]


async def test_a_search_still_keeps_the_phase_one_pinned_page_contract(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A predicate change must not disturb the pinned Phase-1 queue assertions."""
    await _register_sources(session_factory, "linkedin")
    await _seed(session_factory, source="linkedin", label="one", title="Engineer", index=1)

    response = await client.get("/")

    assert response.status_code == 200
    assert 'hx-post="/runs"' in response.text
    assert 'id="run-status-slot"' in response.text
    assert 'id="queue-list"' in response.text
    assert "No listings yet" not in response.text, "there is a listing to show"


async def test_an_empty_queue_still_renders_the_pinned_strings(client) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "0 listings" in response.text
    assert "No listings yet" in response.text
    assert 'hx-post="/runs"' in response.text
    assert 'id="run-status-slot"' in response.text


# --- the merge-visibility predicate (this plan owns it) -----------------------


async def _seed_merged_pair(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[int, int, int]:
    """Two listings and one audited, un-reverted merge — via the production write path."""
    await _register_sources(session_factory, "linkedin", "indeed")
    survivor_id = await _seed(
        session_factory,
        source="linkedin",
        label="survivor",
        title="Senior Python Engineer",
        index=1,
        location=None,
    )
    twin_id = await _seed(
        session_factory,
        source="indeed",
        label="twin",
        title="Senior Python Engineer (m/f/d)",
        index=1,
    )
    async with session_factory() as session:
        dupe_id = await apply_merge(
            session,
            decision=MergeDecision(
                survivor_id=survivor_id, absorbed_id=twin_id, score=95.0, method="fuzzy_tuple"
            ),
            now=DAY,
            run_id=None,
        )
        await session.commit()
    return dupe_id, survivor_id, twin_id


async def test_queue_hides_absorbed_twin_until_revert(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Success criterion 1, machine-decided.

    An absorbed twin is out of the queue *because* an un-reverted `listing_dupes` row
    covers it — not because of a hide event. Clearing `reverted_at` therefore brings
    it back with no separate un-hide step, and this test is the executable form of
    that claim: it seeds the merge, asserts absence, reverts through the same
    repository function the Merges route calls, and asserts presence.
    """
    dupe_id, survivor_id, twin_id = await _seed_merged_pair(session_factory)

    hidden = await client.get("/")

    assert hidden.status_code == 200
    assert "Senior Python Engineer (m/f/d)" not in hidden.text, (
        "the absorbed twin must be absent while its listing_dupes row is un-reverted"
    )
    assert "Senior Python Engineer" in hidden.text, "the survivor stays"
    assert "merged from 1 sources" in hidden.text, "the D-26/D-29 indicator"
    assert _ids(hidden.text) == [survivor_id], "exactly one of the two listings is shown"

    async with session_factory() as session:
        result = await revert_merge(session, dupe_id=dupe_id, now=REVERTED_AT)
        await session.commit()
    assert result.status == "reverted"

    revealed = await client.get("/")

    assert revealed.status_code == 200
    assert "Senior Python Engineer (m/f/d)" in revealed.text, (
        "a revert re-shows the twin with no un-hide event"
    )
    assert sorted(_ids(revealed.text)) == sorted([survivor_id, twin_id])
    assert "merged from" not in revealed.text, "the indicator disappears with the merge"

    async with session_factory() as session:
        dupes = (await session.execute(select(ListingDupe))).scalars().all()
        listings = (await session.execute(select(Listing))).scalars().all()

    assert len(dupes) == 1, "the audit row is never deleted"
    assert len(listings) == 2
