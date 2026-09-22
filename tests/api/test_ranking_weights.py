"""RANK-04 / UI-03 / D-99 / D-100 — editing the weights re-derives the queue for free.

The weights editor is the mechanism behind success criterion 3: a weight change
rewrites ONE `ranking_config` document and the queue recomputes every total on read
from the stored sub-scores, so the order changes with **zero** new `llm_calls` rows.
Invalid input (non-numeric, negative, or an all-zero set) is refused at the storage
boundary and writes nothing.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import LlmCall, RankingConfig, Run, Source
from app.db.repositories import ranking_config_repo, score_repo
from app.db.repositories.listing_repo import upsert_listing_source
from app.domain import rubric
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
    session_factory: async_sessionmaker[AsyncSession], *, index: int, title: str
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
            session, source="linkedin", norm=normalise_listing(raw), run_id=None, now=DAY
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
    sub_scores: dict[str, float],
) -> None:
    async with session_factory() as session:
        await score_repo.upsert_score(
            session,
            listing_id=listing_id,
            run_id=run_id,
            criteria_version=1,
            sub_scores=sub_scores,
            weights={"skills": 1.0, "domain": 1.0},
            rubric_version="v1",
            confidence_tier="medium",
            rationale="Grounded in the listing's stated requirements and the CV facts.",
            requirements=[],
            total_score=None,
            provider="opencode",
            model="minimax-m3",
            backend="opencode_server",
            now=DAY,
        )
        await session.commit()


async def _count(session_factory: async_sessionmaker[AsyncSession], model: type) -> int:
    async with session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def _stored_weights(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, float]:
    async with session_factory() as session:
        return await ranking_config_repo.read_weights(session)


# --- saving --------------------------------------------------------------------


async def test_weights_form_saves_and_rerenders(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    submitted = {
        "skills": "2",
        "seniority": "1.5",
        "domain": "1",
        "location": "0.5",
        "evidence": "3",
        "compensation": "0",
    }

    response = await client.post("/settings/weights", data=submitted)

    assert response.status_code == 200
    assert "Weights saved." in response.text
    stored = await _stored_weights(session_factory)
    assert stored == {key: float(value) for key, value in submitted.items()}
    assert await _count(session_factory, RankingConfig) == 1


async def test_a_missing_field_keeps_the_stored_value(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/settings/weights", data={"skills": "4"})

    stored = await _stored_weights(session_factory)

    assert stored["skills"] == 4.0
    assert stored["domain"] == rubric.DEFAULT_WEIGHTS["domain"]


# --- zero new model calls (success criterion 3) --------------------------------


async def test_weight_change_writes_zero_llm_calls(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    before = await _count(session_factory, LlmCall)

    response = await client.post("/settings/weights", data={"skills": "3"})

    assert response.status_code == 200
    assert await _count(session_factory, LlmCall) == before, (
        "a weight change must never issue a model call"
    )


async def test_weight_change_reorders_the_queue(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Two scored listings swap order when one factor's weight is raised, for free."""
    await _register_sources(session_factory, "linkedin")
    skills_led = await _seed_listing(session_factory, index=1, title="Skills Led")
    domain_led = await _seed_listing(session_factory, index=2, title="Domain Led")
    run_id = await _seed_run(session_factory)
    await _seed_score(
        session_factory, listing_id=skills_led, run_id=run_id,
        sub_scores={"skills": 1.0, "domain": 0.0},
    )
    await _seed_score(
        session_factory, listing_id=domain_led, run_id=run_id,
        sub_scores={"skills": 0.2, "domain": 0.9},
    )

    before = _ids((await client.get("/queue/list")).text)
    llm_before = await _count(session_factory, LlmCall)
    saved = await client.post("/settings/weights", data={"skills": "5"})
    after = _ids((await client.get("/queue/list")).text)

    assert saved.status_code == 200
    assert before[0] == domain_led, "under equal weights the domain-led listing leads"
    assert after[0] == skills_led, "raising the skills weight flips the order"
    assert await _count(session_factory, LlmCall) == llm_before, (
        "reordering costs zero model calls"
    )


# --- rejections (T-05-17 / T-05-18) --------------------------------------------


async def test_invalid_weight_writes_nothing(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    valid = {factor: "2" for factor in rubric.FACTORS}
    assert (await client.post("/settings/weights", data=valid)).status_code == 200
    baseline = await _stored_weights(session_factory)

    for bad in ("-1", "abc", "nan"):
        response = await client.post("/settings/weights", data={"skills": bad})

        assert response.status_code == 400, bad
        assert "weight" in response.text.lower()
        assert await _stored_weights(session_factory) == baseline, (
            f"an invalid {bad!r} submission must write nothing"
        )


async def test_all_zero_weights_are_rejected(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """T-05-18: a zero denominator makes every total None, so an all-zero set is refused."""
    response = await client.post(
        "/settings/weights", data={factor: "0" for factor in rubric.FACTORS}
    )

    assert response.status_code == 400
    assert "greater than zero" in response.text
    assert await _count(session_factory, RankingConfig) == 0
    assert await _stored_weights(session_factory) == rubric.DEFAULT_WEIGHTS


# --- the existing settings surfaces survive ------------------------------------


async def test_settings_page_still_renders_existing_cards(client) -> None:
    response = await client.get("/settings")

    assert response.status_code == 200
    assert 'id="danger-zone"' in response.text
    assert 'id="llm-backend"' in response.text
    assert 'id="ranking-weights"' in response.text
    assert 'name="skills"' in response.text
