"""RANK-02 / RANK-03 / D-99 / D-100 — the `scores` writer and the weights store.

The `scores` table shipped in migration 0001 with no writer. These tests pin the
two things that matter about the writer: the per-factor decomposition is stored
(never one opaque number), and exactly one row exists per
``(listing, run, criteria_version)`` triple so a re-score updates in place. The
weights store is covered here too — it is the read the queue's read-time total
depends on (D-100).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, RankingConfig, Run, Score, Source
from app.db.repositories import ranking_config_repo, score_repo

NOW = datetime(2026, 9, 22, tzinfo=UTC)
LATER = datetime(2026, 9, 23, tzinfo=UTC)


async def _seed_run_and_listing(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    started_at: datetime = NOW,
    url: str = "https://example.com/jobs/1",
    register_source: bool = True,
) -> tuple[int, int]:
    async with session_factory() as session:
        if register_source:
            session.add(Source(name="linkedin", display_name="Linkedin"))
        run = Run(trigger="manual", status="done", started_at=started_at)
        session.add(run)
        await session.flush()
        listing = Listing(
            canonical_url=url,
            title="Backend Engineer",
            first_seen_at=started_at,
            last_seen_at=started_at,
            content_hash=f"hash-{url}",
            created_at=started_at,
            updated_at=started_at,
            is_active=True,
        )
        session.add(listing)
        await session.commit()
        return int(run.id), int(listing.id)


async def _count(session_factory: async_sessionmaker[AsyncSession], table: type) -> int:
    async with session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(table)) or 0)


async def _upsert(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    listing_id: int,
    run_id: int,
    criteria_version: int = 1,
    sub_scores: dict[str, float] | None = None,
    total_score: float | None = 0.5,
    rationale: str = "Grounded in the listed requirements.",
) -> score_repo.ScoreRecord:
    async with session_factory() as session:
        record = await score_repo.upsert_score(
            session,
            listing_id=listing_id,
            run_id=run_id,
            criteria_version=criteria_version,
            sub_scores=sub_scores if sub_scores is not None else {"skills": 0.5, "domain": 0.5},
            weights={"skills": 1.0, "domain": 1.0},
            rubric_version="v1",
            confidence_tier="medium",
            rationale=rationale,
            requirements=[
                {"text": "Python experience", "verdict": "met", "evidence_id": "skill.python"},
                {"text": "Kubernetes", "verdict": "gap", "evidence_id": None},
            ],
            total_score=total_score,
            provider="opencode",
            model="minimax-m3",
            backend="opencode_server",
            now=NOW,
        )
        await session.commit()
        return record


# --- the decomposition (RANK-02) ----------------------------------------------


async def test_one_upsert_stores_the_per_factor_entries_and_never_a_bare_total(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id, listing_id = await _seed_run_and_listing(session_factory)

    await _upsert(session_factory, listing_id=listing_id, run_id=run_id)

    async with session_factory() as session:
        row = (await session.execute(select(Score))).scalar_one()

    assert row.factor_scores_json == {"skills": 0.5, "domain": 0.5}
    assert "total" not in row.factor_scores_json
    assert row.total_score == 0.5
    assert row.gaps_json == [
        {"text": "Python experience", "verdict": "met", "evidence_id": "skill.python"},
        {"text": "Kubernetes", "verdict": "gap", "evidence_id": None},
    ]
    assert row.weights_json == {
        "skills": 1.0,
        "seniority": 0.0,
        "domain": 1.0,
        "location": 0.0,
        "evidence": 0.0,
        "compensation": 0.0,
    }


async def test_a_present_zero_is_stored_as_zero_and_not_conflated_with_absent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id, listing_id = await _seed_run_and_listing(session_factory)

    record = await _upsert(
        session_factory,
        listing_id=listing_id,
        run_id=run_id,
        sub_scores={"skills": 0.0, "domain": -1.0},
    )

    assert dict(record.factor_scores) == {"skills": 0.0}
    assert "domain" not in dict(record.factor_scores)


async def test_the_row_records_provider_and_model_identity(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id, listing_id = await _seed_run_and_listing(session_factory)

    record = await _upsert(session_factory, listing_id=listing_id, run_id=run_id)

    assert (record.provider, record.model) == ("opencode", "minimax-m3")


# --- one row per triple (D-101) ------------------------------------------------


async def test_a_second_upsert_for_the_same_triple_updates_in_place(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id, listing_id = await _seed_run_and_listing(session_factory)
    await _upsert(session_factory, listing_id=listing_id, run_id=run_id, total_score=0.1)

    await _upsert(
        session_factory,
        listing_id=listing_id,
        run_id=run_id,
        sub_scores={"skills": 0.9},
        total_score=0.9,
        rationale="A corrected rationale.",
    )

    assert await _count(session_factory, Score) == 1
    async with session_factory() as session:
        row = (await session.execute(select(Score))).scalar_one()
    assert row.factor_scores_json == {"skills": 0.9}
    assert row.total_score == 0.9
    assert row.rationale == "A corrected rationale."


# --- criteria_version is mandatory and non-NULL (Pitfall 5) --------------------


async def test_criteria_version_none_is_rejected(session_factory: async_sessionmaker[AsyncSession]) -> None:
    run_id, listing_id = await _seed_run_and_listing(session_factory)

    async with session_factory() as session:
        with pytest.raises(ValueError):
            await score_repo.upsert_score(
                session,
                listing_id=listing_id,
                run_id=run_id,
                criteria_version=None,  # type: ignore[arg-type]
                sub_scores={"skills": 0.5},
                weights={"skills": 1.0},
                rubric_version="v1",
                confidence_tier="low",
                rationale="",
                requirements=[],
                total_score=0.5,
                provider="opencode",
                model="minimax-m3",
            )

    assert await _count(session_factory, Score) == 0, "no SQL may be issued"


async def test_an_unknown_confidence_tier_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id, listing_id = await _seed_run_and_listing(session_factory)

    async with session_factory() as session:
        with pytest.raises(ValueError):
            await score_repo.upsert_score(
                session,
                listing_id=listing_id,
                run_id=run_id,
                criteria_version=1,
                sub_scores={"skills": 0.5},
                weights={"skills": 1.0},
                rubric_version="v1",
                confidence_tier="excellent",
                rationale="",
                requirements=[],
                total_score=0.5,
                provider="opencode",
                model="minimax-m3",
            )


# --- the newest-row reads (Pitfall 4) ------------------------------------------


async def test_latest_for_listings_returns_the_newest_runs_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first_run, listing_id = await _seed_run_and_listing(session_factory, started_at=NOW)
    second_run, _ = await _seed_run_and_listing(
        session_factory,
        started_at=LATER,
        url="https://example.com/jobs/2",
        register_source=False,
    )
    assert second_run > first_run

    await _upsert(
        session_factory, listing_id=listing_id, run_id=first_run, sub_scores={"skills": 0.1}
    )
    await _upsert(
        session_factory, listing_id=listing_id, run_id=second_run, sub_scores={"skills": 0.9}
    )

    async with session_factory() as session:
        newest = await score_repo.latest_for_listings(session, [listing_id])

    assert dict(newest[listing_id].factor_scores) == {"skills": 0.9}
    assert newest[listing_id].run_id == second_run


async def test_read_score_for_listing_is_none_for_an_unscored_listing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, listing_id = await _seed_run_and_listing(session_factory)

    async with session_factory() as session:
        assert await score_repo.read_score_for_listing(session, listing_id) is None


async def test_read_score_for_listing_returns_the_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id, listing_id = await _seed_run_and_listing(session_factory)
    await _upsert(session_factory, listing_id=listing_id, run_id=run_id)

    async with session_factory() as session:
        record = await score_repo.read_score_for_listing(session, listing_id)

    assert record is not None
    assert record.listing_id == listing_id
    assert record.criteria_version == 1


# --- the weights store (D-99 / D-100) ------------------------------------------


async def test_read_weights_falls_back_to_the_rubric_defaults(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        weights = await ranking_config_repo.read_weights(session)

    assert weights == {"skills": 1.0, "seniority": 1.0, "domain": 1.0,
                       "location": 1.0, "evidence": 1.0, "compensation": 1.0}


async def test_write_weights_upserts_the_single_row_and_round_trips(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    weights = {"skills": 2.0, "seniority": 1.5, "domain": 1.0,
               "location": 0.5, "evidence": 3.0, "compensation": 0.0}

    async with session_factory() as session:
        await ranking_config_repo.write_weights(session, weights, now=NOW)
        await session.commit()

    async with session_factory() as session:
        assert await ranking_config_repo.read_weights(session) == weights
        count = int(await session.scalar(select(func.count()).select_from(RankingConfig)) or 0)
    assert count == 1

    # A second write updates the one row in place.
    async with session_factory() as session:
        await ranking_config_repo.write_weights(session, {**weights, "skills": 9.0}, now=LATER)
        await session.commit()

    async with session_factory() as session:
        assert (await ranking_config_repo.read_weights(session))["skills"] == 9.0
        count = int(await session.scalar(select(func.count()).select_from(RankingConfig)) or 0)
    assert count == 1


async def test_read_weights_drops_unknown_keys_and_fills_missing_ones(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add(
            RankingConfig(
                id=1,
                weights_json={"skills": 2.0, "nonsense": 7.0},
                updated_at=NOW,
            )
        )
        await session.commit()

    async with session_factory() as session:
        weights = await ranking_config_repo.read_weights(session)

    assert weights["skills"] == 2.0
    assert "nonsense" not in weights
    assert weights["compensation"] == 1.0


async def test_write_weights_rejects_an_unknown_key_and_a_negative_value(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(ValueError):
            await ranking_config_repo.write_weights(
                session, {"skills": 1.0, "nonsense": 1.0}
            )
        with pytest.raises(ValueError):
            await ranking_config_repo.write_weights(
                session, {"skills": -1.0}
            )
