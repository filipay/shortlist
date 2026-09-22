"""Adversarial Nyquist probes for Phase 5's ranked-queue surface — UI-01 / RANK-08.

The WR-03 probe below encodes a behaviour the phase's own tests do **not** cover; it
was filed by `05-REVIEW.md` and is expected to FAIL against the current
implementation, so it carries an ``xfail(strict=True)`` sentinel: the default lane
stays green while the gap is open, and a fix turns the expected failure into an XPASS
that fails the suite and forces the sentinel's removal.

(The former CR-01 sentinel on the ranking strip's denominator was retired by plan
05-05 — its fix landed and its coverage was re-homed as first-class tests in
``tests/api/test_queue_ranked.py``.)

Run uncensored with ``.venv/bin/python -m pytest --runxfail`` to see the real
assertion error.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.api.test_queue_ranked import (
    _ids,
    _register_sources,
    _seed_listing,
    _seed_run,
    _seed_score,
)


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
