"""Adversarial Nyquist probes for Phase 5 — RANK-08 / D-94 and RANK-03.

These encode requirement behaviours the phase's own plan tests do **not** cover;
they were filed as WR-02 and WR-05 by `05-REVIEW.md`. Each is expected to FAIL
against the current implementation, so each carries an ``xfail(strict=True)``
sentinel: the default lane stays green while the gap is open, and a fix turns the
expected failure into an XPASS that fails the suite and forces the sentinel's
removal.

Run uncensored with ``.venv/bin/python -m pytest --runxfail`` to see the real
assertion error.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import LlmCall, RankingConfig, Score
from app.db.repositories import ranking_config_repo
from app.domain import rubric
from app.pipeline import rank as rank_module
from app.pipeline.rank import run_ranking
from tests.pipeline.test_rank_stage import StubBackend, _add_listing, _seed_run


@pytest.mark.xfail(
    strict=True,
    reason=(
        "05-REVIEW WR-02: a non-UTF-8 cv.yaml raises UnicodeDecodeError (a "
        "ValueError) which the D-94 guard's (CvFactStoreError, OSError) misses, "
        "so an unreadable fact store escapes the detached ranking task instead "
        "of taking the documented clean-skip path"
    ),
)
async def test_unreadable_non_utf8_fact_store_is_a_clean_skip(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RANK-08 / D-94: an unreadable fact store must write zero rows, never raise."""
    # A cv.yaml that exists but cannot be decoded as UTF-8 — the "unreadable" half
    # of the documented "absent or unreadable" skip condition.
    (tmp_path / rank_module.CV_FILENAME).write_bytes(b"\xff\xfe\x00\x01 not utf-8")
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))

    run_id = await _seed_run(session_factory)
    await _add_listing(session_factory, title="Role")

    # Must not raise: a skip is not a failure.
    await run_ranking(session_factory, run_id=run_id, llm=StubBackend())

    async with session_factory() as session:
        calls = int(await session.scalar(select(func.count()).select_from(LlmCall)) or 0)
        scores = int(await session.scalar(select(func.count()).select_from(Score)) or 0)
    assert calls == 0
    assert scores == 0


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
