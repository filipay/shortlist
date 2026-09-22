"""UI-02 / D-96 — the job detail page explains the score, and only the score.

The page is proven to render the total and tier, each factor's sub-score alongside the
weight in force (with a dropped factor marked absent, never zero), the stored rationale,
the requirement-by-requirement fit list with named gaps and evidencing CV fact ids, the
merged-from record, and — critically — to render an UNSCORED listing as not yet ranked
rather than as a real 0.0 (the UI-02 transparency prohibition).

Untrusted listing text and stored model prose are escaped by Jinja autoescape only: the
XSS fixture shape matches `tests/api/test_listing_events.py` so the two suites agree on
what escaping looks like.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ListingDupe, Run, Source
from app.db.repositories import score_repo
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)

XSS_TITLE = "<script>x</script> Senior Engineer"
XSS_RATIONALE = "Strong match on <script>x</script> and the ingest work."

FACTOR_SCORES = {
    "skills": 0.8,
    "seniority": 0.6,
    "domain": 0.7,
    "location": 1.0,
    "evidence": 0.5,
}
#: (0.8 + 0.6 + 0.7 + 1.0 + 0.5) / 5 under the equal default weights.
EXPECTED_TOTAL = "0.72"

REQUIREMENTS = [
    {"text": "Python and SQL", "verdict": "met", "evidence_id": "skill.python"},
    {"text": "Kubernetes", "verdict": "partial", "evidence_id": None},
    {"text": "Team leadership", "verdict": "gap", "evidence_id": None},
]
GAP_TEXT = "Team leadership"


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
    index: int = 1,
    title: str = "Backend Engineer",
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
            session, source="linkedin", norm=normalise_listing(raw), run_id=None, now=NOW
        )
        await session.commit()
        return int(outcome.listing_id)


async def _seed_run(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        run = Run(trigger="manual", status="done", started_at=NOW, finished_at=NOW)
        session.add(run)
        await session.commit()
        return int(run.id)


async def _seed_score(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    listing_id: int,
    run_id: int,
    rationale: str = "Grounded in the listing's stated requirements and the CV facts.",
    sub_scores: dict[str, float] | None = None,
    requirements: list[dict[str, object]] | None = None,
) -> None:
    async with session_factory() as session:
        await score_repo.upsert_score(
            session,
            listing_id=listing_id,
            run_id=run_id,
            criteria_version=1,
            sub_scores=FACTOR_SCORES if sub_scores is None else sub_scores,
            weights={"skills": 1.0, "seniority": 1.0, "domain": 1.0,
                     "location": 1.0, "evidence": 1.0, "compensation": 1.0},
            rubric_version="v1",
            confidence_tier="medium",
            rationale=rationale,
            requirements=REQUIREMENTS if requirements is None else requirements,
            total_score=None,
            provider="opencode",
            model="minimax-m3",
            backend="opencode_server",
            now=NOW,
        )
        await session.commit()


async def _seed_merge(
    session_factory: async_sessionmaker[AsyncSession], *, survivor: int, twin: int
) -> None:
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


async def _seed_scored_listing(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    title: str = "Backend Engineer",
    rationale: str = "Grounded in the listing's stated requirements and the CV facts.",
    merge: bool = False,
) -> int:
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(session_factory, index=1, title=title)
    run_id = await _seed_run(session_factory)
    await _seed_score(
        session_factory, listing_id=listing_id, run_id=run_id, rationale=rationale
    )
    if merge:
        twin = await _seed_listing(session_factory, index=2, title="Duplicate Role")
        await _seed_merge(session_factory, survivor=listing_id, twin=twin)
    return listing_id


# --- the breakdown -------------------------------------------------------------


async def test_detail_page_renders_breakdown(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_scored_listing(session_factory, merge=True)

    response = await client.get(f"/listings/{listing_id}")

    assert response.status_code == 200
    body = response.text
    assert EXPECTED_TOTAL in body, "the read-time total must render"
    assert "badge-score-tier-medium" in body, "the confidence tier must render"
    assert "stated requirements and the CV facts" in body, "the rationale must render"
    assert "req-met" in body
    assert "req-partial" in body
    assert "req-gap" in body
    # Every factor renders its weight; a dropped factor reads as absent, not zero.
    assert "Skills" in body
    assert "no data" in body, "the dropped compensation factor must read as absent"
    assert "merged from 1 sources" in body


async def test_detail_shows_requirements_and_gaps(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_scored_listing(session_factory)

    response = await client.get(f"/listings/{listing_id}")

    body = response.text
    assert "<code>skill.python</code>" in body, (
        "the evidencing CV fact id renders as plain text, never as a link"
    )
    assert GAP_TEXT in body, "a gap verdict is a named gap, not an omission"
    assert "<strong>gap</strong>" in body
    assert "<strong>met</strong>" in body
    assert "<strong>partial</strong>" in body


async def test_unscored_listing_renders_not_yet_ranked(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(session_factory, index=3)

    response = await client.get(f"/listings/{listing_id}")

    assert response.status_code == 200
    body = response.text
    assert "Not yet ranked" in body
    assert "Fit score" not in body, "an unscored listing has no score region"
    assert "0.0" not in body, "an unscored listing must never read as a real zero"
    assert "Factor breakdown" not in body


async def test_detail_escapes_untrusted_title_and_rationale(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_scored_listing(
        session_factory, title=XSS_TITLE, rationale=XSS_RATIONALE
    )

    response = await client.get(f"/listings/{listing_id}")

    body = response.text
    assert "<script>x</script>" not in body, "a raw script tag must never be emitted"
    assert "&lt;script&gt;" in body, "the escaped form must render"


async def test_unknown_listing_returns_404_fragment(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = await client.get("/listings/9999")

    assert response.status_code == 404
    assert 'data-error="unknown-listing"' in response.text
