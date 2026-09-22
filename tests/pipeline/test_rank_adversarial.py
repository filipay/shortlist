"""Adversarial Nyquist probes for Phase 5 — RANK-08 / D-94 and RANK-03.

These encode requirement behaviours the phase's own plan tests do **not** cover;
they were filed as WR-02 and WR-05 by `05-REVIEW.md`. WR-02 (the non-UTF-8 fact
store took neither the guard nor the documented clean-skip path) was closed by the
fact-store boundary fix in plan 05-06; its strict-xfail sentinel was retired here
and the coverage re-homed as a first-class test in
``tests/pipeline/test_rank_optional.py``.

Only the WR-05 sentinel remains: it is expected to FAIL against the current
implementation, so it carries an ``xfail(strict=True)`` marker — the default lane
stays green while the gap is open, and a fix turns the expected failure into an
XPASS that fails the suite and forces the sentinel's removal.

Run uncensored with ``.venv/bin/python -m pytest --runxfail`` to see the real
assertion error.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import RankingConfig
from app.db.repositories import ranking_config_repo
from app.domain import rubric


@pytest.mark.xfail(
    strict=True,
    reason=(
        "05-REVIEW WR-05: read_weights returns a negative stored weight verbatim, "
        "so a hand-edited/legacy ranking_config document can drive the read-time "
        "total out of range or to None and silently un-rank every listing"
    ),
)
async def test_read_weights_rejects_a_negative_stored_weight(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """RANK-03: every weight the total is derived from stays finite and >= 0."""
    async with session_factory() as session:
        session.add(
            RankingConfig(
                id=1,
                weights_json={"skills": -5.0},
                updated_at=datetime(2026, 9, 22, tzinfo=UTC),
            )
        )
        await session.commit()

    async with session_factory() as session:
        weights = await ranking_config_repo.read_weights(session)

    assert weights["skills"] == float(rubric.DEFAULT_WEIGHTS["skills"])
    assert all(value >= 0.0 for value in weights.values())
