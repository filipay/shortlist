"""UI-01 / D-97 / D-98 / D-100 — the queue is ranked, and the ranking is inspectable.

The default order is the read-time total descending with unscored listings last and a
deterministic tie-break; the Phase-1 `first_seen_at DESC, id DESC` order stays
selectable via `?sort=recent`; a `?min_score=` threshold hides low-scored listings but
NEVER hides an unscored one (a listing with no score is not a listing with a low
score); and with a query set the score ordering wins over `bm25` while the MATCH
predicate still filters.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Run, Source
from app.db.repositories import score_repo
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

DAY = datetime(2026, 9, 1, tzinfo=UTC)
TR_RE = re.compile(r'<tr id="listing-row-(\d+)"')


def _ids(body: str) -> list[int]:
    return [int(value) for value in TR_RE.findall(body)]


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
    index: int,
    title: str,
    description: str = "Build the thing.",
    first_seen: datetime = DAY,
) -> int:
    raw = RawListing(
        source="linkedin",  # type: ignore[arg-type]
        source_listing_id=f"linkedin-{index}",
        source_url=f"https://linkedin.example.com/jobs/{index}",
        direct_url=None,
        title=title,
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description=description,
        posted_at=date(2026, 9, 1),
    )
    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session, source="linkedin", norm=normalise_listing(raw), run_id=None, now=first_seen
        )
        await session.commit()
        return int(outcome.listing_id)


async def _seed_run(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        run = Run(trigger="manual", status="done", started_at=DAY, finished_at=DAY)
        session.add(run)
        await session.commit()
        return int(run.id)


async def _seed_score(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    listing_id: int,
    run_id: int,
    value: float,
    confidence_tier: str = "medium",
) -> None:
    async with session_factory() as session:
        await score_repo.upsert_score(
            session,
            listing_id=listing_id,
            run_id=run_id,
            criteria_version=1,
            sub_scores={"skills": value},
            weights={"skills": 1.0},
            rubric_version="v1",
            confidence_tier=confidence_tier,
            rationale="Grounded in the listing's stated requirements and the CV facts.",
            requirements=[],
            total_score=value,
            provider="opencode",
            model="minimax-m3",
            backend="opencode_server",
            now=DAY,
        )
        await session.commit()


# --- the default order (D-97) --------------------------------------------------


async def test_unranked_row_renders_the_badge(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """UI-01 adjacency: the unscored row carries a distinct, non-numeric badge."""
    await _register_sources(session_factory, "linkedin")
    scored = await _seed_listing(session_factory, index=1, title="Scored")
    unscored = await _seed_listing(session_factory, index=2, title="Unranked")
    run_id = await _seed_run(session_factory)
    await _seed_score(session_factory, listing_id=scored, run_id=run_id, value=0.7)

    body = (await client.get("/queue/list")).text

    assert f'id="listing-unranked-{unscored}"' in body
    assert "badge-unranked" in body
    assert "not ranked" in body


async def test_default_order_is_score_desc_unranked_last(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _register_sources(session_factory, "linkedin")
    high = await _seed_listing(session_factory, index=1, title="High Fit")
    low = await _seed_listing(session_factory, index=2, title="Low Fit")
    unscored = await _seed_listing(session_factory, index=3, title="Not Scored")
    run_id = await _seed_run(session_factory)
    await _seed_score(session_factory, listing_id=high, run_id=run_id, value=0.9)
    await _seed_score(session_factory, listing_id=low, run_id=run_id, value=0.2)

    response = await client.get("/queue/list")

    assert response.status_code == 200
    ids = _ids(response.text)
    assert ids == [high, low, unscored]
    assert ids.index(unscored) > ids.index(high)
    assert ids.index(unscored) > ids.index(low), "an unscored row sorts after every scored row"


async def test_unscored_listing_renders_no_numeric_total(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """An unscored listing is never given a synthetic 0.0 (the UI-01 prohibition).

    The distinct unranked badge is added with the template in Task 2; this task's
    deliverable is the read model's `total_score is None`.
    """
    await _register_sources(session_factory, "linkedin")
    scored = await _seed_listing(session_factory, index=1, title="Scored")
    unscored = await _seed_listing(session_factory, index=2, title="Unranked")
    run_id = await _seed_run(session_factory)
    await _seed_score(session_factory, listing_id=scored, run_id=run_id, value=0.7)

    body = (await client.get("/queue/list")).text

    assert f'id="listing-score-{scored}"' in body
    assert f'id="listing-score-{unscored}"' not in body, "an unscored row has no score badge"
    assert "0.0" not in body, "an unscored listing must never render a numeric zero"


async def test_sort_recent_restores_first_seen_order(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _register_sources(session_factory, "linkedin")
    newer = await _seed_listing(
        session_factory, index=1, title="Newer Role", first_seen=DAY + timedelta(days=5)
    )
    older = await _seed_listing(
        session_factory, index=2, title="Older Role", first_seen=DAY
    )

    recent = await client.get("/queue/list", params={"sort": "recent"})
    default = await client.get("/queue/list")

    assert _ids(recent.text) == [newer, older], "first_seen_at DESC, id DESC"
    assert _ids(default.text) == [older, newer], (
        "the default score order tie-breaks unscored rows by id DESC"
    )


# --- the minimum-score filter (D-98) -------------------------------------------


async def test_min_score_keeps_unscored_visible(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _register_sources(session_factory, "linkedin")
    best = await _seed_listing(session_factory, index=1, title="Best Fit")
    weak = await _seed_listing(session_factory, index=2, title="Weak Fit")
    unscored = await _seed_listing(session_factory, index=3, title="Not Scored")
    run_id = await _seed_run(session_factory)
    await _seed_score(session_factory, listing_id=best, run_id=run_id, value=0.9)
    await _seed_score(session_factory, listing_id=weak, run_id=run_id, value=0.2)

    response = await client.get("/queue/list", params={"min_score": "0.95"})

    ids = _ids(response.text)
    assert weak not in ids, "a below-threshold scored listing is hidden"
    assert best not in ids, "the threshold is above every scored total"
    assert unscored in ids, "an unscored listing is ALWAYS kept under the threshold"


async def test_junk_min_score_degrades_to_no_threshold(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(session_factory, index=1, title="Any Role")

    response = await client.get("/queue/list", params={"min_score": "abc"})

    assert response.status_code == 200
    assert _ids(response.text) == [listing_id]


# --- the FTS/sort precedence ---------------------------------------------------


async def test_score_sort_wins_over_bm25_when_q_is_set(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """With a query set the MATCH predicate still filters; the SORT is the score order.

    Listing A matches `python` in its description only (weak bm25) but has the higher
    read-time total; listing B matches in its title (strong bm25) but scores lower. The
    default sort must return A first — the reverse of the relevance order, which the
    retained `sort=recent` path still produces.
    """
    await _register_sources(session_factory, "linkedin")
    strong_total = await _seed_listing(
        session_factory,
        index=1,
        title="Backend Engineer",
        description="python and more python in this description",
    )
    strong_relevance = await _seed_listing(
        session_factory, index=2, title="Python Engineer", description="Build the thing."
    )
    run_id = await _seed_run(session_factory)
    await _seed_score(session_factory, listing_id=strong_total, run_id=run_id, value=0.9)
    await _seed_score(session_factory, listing_id=strong_relevance, run_id=run_id, value=0.2)

    scored = await client.get("/queue/list", params={"q": "python"})
    recent = await client.get("/queue/list", params={"q": "python", "sort": "recent"})

    assert scored.status_code == 200 and recent.status_code == 200
    assert _ids(scored.text) == [strong_total, strong_relevance], (
        "the score ordering wins over bm25"
    )
    assert _ids(recent.text) == [strong_relevance, strong_total], (
        "the retained relevance ordering is unchanged"
    )


async def test_two_identical_requests_return_the_same_row_order(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _register_sources(session_factory, "linkedin")
    first = await _seed_listing(session_factory, index=1, title="First")
    second = await _seed_listing(session_factory, index=2, title="Second")
    third = await _seed_listing(session_factory, index=3, title="Third")
    run_id = await _seed_run(session_factory)
    # The SAME total for two listings forces the deterministic tie-break.
    await _seed_score(session_factory, listing_id=first, run_id=run_id, value=0.5)
    await _seed_score(session_factory, listing_id=second, run_id=run_id, value=0.5)
    await _seed_score(session_factory, listing_id=third, run_id=run_id, value=0.5)

    one = await client.get("/queue/list")
    two = await client.get("/queue/list")

    assert _ids(one.text) == _ids(two.text), "two identical requests must not reorder"
    assert _ids(one.text) == [third, second, first], "the unique tie-break is id DESC"


async def test_empty_queue_renders_the_empty_state(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "No listings yet" in response.text
    assert _ids(response.text) == []
