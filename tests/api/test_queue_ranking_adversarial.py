"""Adversarial Nyquist probes for Phase 5's ranked-queue surface — UI-01 / RANK-08.

These encode behaviours the phase's own tests do **not** cover; they were filed as
CR-01 and WR-03 by `05-REVIEW.md`. Each is expected to FAIL against the current
implementation, so each carries an ``xfail(strict=True)`` sentinel: the default
lane stays green while the gap is open, and a fix turns the expected failure into
an XPASS that fails the suite and forces the sentinel's removal.

Run uncensored with ``.venv/bin/python -m pytest --runxfail`` to see the real
assertion error.
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Run
from tests.api.test_queue_ranked import (
    DAY,
    _ids,
    _register_sources,
    _seed_listing,
    _seed_run,
    _seed_score,
)


async def _seed_run_with_coverage(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    ranked_count: int,
    survivors: int,
) -> int:
    """A finished run whose own candidate population differs from the queue page."""
    async with session_factory() as session:
        run = Run(
            trigger="manual",
            status="done",
            started_at=DAY,
            finished_at=DAY,
            ranked_count=ranked_count,
            reason_counts_json={"survivors": survivors},
        )
        session.add(run)
        await session.commit()
        return int(run.id)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "05-REVIEW WR-03: ?min_score=nan passes _float_or_none's float() check, and "
        "`total >= nan` is False for every scored row, so a junk threshold silently "
        "hides every scored listing instead of degrading to None (T-05-19)"
    ),
)
async def test_nan_min_score_degrades_to_no_threshold(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """UI-01 / T-05-19: a non-finite threshold is junk and must not hide listings."""
    await _register_sources(session_factory, "linkedin")
    scored = await _seed_listing(session_factory, index=1, title="Scored")
    await _seed_listing(session_factory, index=2, title="Unranked")
    run_id = await _seed_run(session_factory)
    await _seed_score(session_factory, listing_id=scored, run_id=run_id, value=0.9)

    body = (await client.get("/queue/list", params={"min_score": "nan"})).text

    assert scored in _ids(body), "nan is junk — it must degrade to no threshold"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "05-REVIEW CR-01: the ranking strip's denominator is the current page total "
        "(`page.total`) while its numerator is the run's `ranked_count`, so the two "
        "numbers come from different populations and the strip routinely reads "
        "'Ranked 30 of 5'"
    ),
)
async def test_ranking_strip_denominator_is_the_runs_own_candidates(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """RANK-08 / UI-01: the strip ratio must come from one population."""
    await _register_sources(session_factory, "linkedin")
    await _seed_listing(session_factory, index=1, title="One")
    await _seed_listing(session_factory, index=2, title="Two")
    # The run scored 5 candidates; only 2 listings are visible on this queue page.
    await _seed_run_with_coverage(session_factory, ranked_count=5, survivors=30)

    body = (await client.get("/")).text
    rendered = re.search(r"Ranked \d+ of \d+", body)

    assert "Ranked 5 of 30" in body, rendered.group(0) if rendered else "no strip"
