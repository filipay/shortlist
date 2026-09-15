"""The operator's live probe lane — one bounded search per board.

**Never runs in the default lane** (`addopts = "-m 'not live'"`). It performs real
outbound requests against hostile third-party boards, so it is selected explicitly:

    pytest -q -m live

What it does: one bounded search per enabled board through the real adapters, with
the configured envelope, writing exactly the rows the verdict document is derived
from — a `runs` row, one `source_request_log` row per outbound request, and the S2
baseline on the first successful run.

What it deliberately does NOT do: assert a survival outcome. Survival is a
measurement over ≥3 distinct days, not a single test run; a test that asserted
"scraping works" would be the CI equivalent of fabricating a verdict (P13).

Run it once per day on separate days via `scripts/run-probe.sh`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.db.models import Run, Source, SourceRequestLog
from app.db.session import async_session_maker
from app.pipeline.run import run_pipeline
from app.sources import registry

pytestmark = pytest.mark.live


async def _enabled_sources() -> list[str]:
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                select(Source.name).where(Source.enabled.is_(True)).order_by(Source.name)
            )
        ).scalars().all()
    return list(rows)


async def _count(table: type) -> int:
    async with async_session_maker() as session:
        return int(await session.scalar(select(func.count()).select_from(table)) or 0)


async def test_one_bounded_probe_run_per_board_respects_the_envelope() -> None:
    """One real search per board, then assert the envelope — not a verdict."""
    if not settings.probe_enabled:
        pytest.skip("probe_enabled is false")

    names = await _enabled_sources()
    assert names, (
        "no enabled sources rows — insert one per board before probing "
        "(see docs/probes/README.md)"
    )

    adapters = [registry.get(name)() for name in names]
    before_log = await _count(SourceRequestLog)

    run_id = await run_pipeline("manual", None, async_session_maker, adapters=adapters)

    async with async_session_maker() as session:
        run = await session.get(Run, run_id)
    assert run is not None
    assert run.status in {"done", "partial", "failed"}
    assert run.source_counts_json, "the run recorded no per-source counts"

    # The envelope: one search per board, no detail pass, within the ceilings.
    per_source = run.source_counts_json or {}
    assert len(per_source) <= len(adapters)
    for name, counts in per_source.items():
        assert counts.get("requests_used", 0) <= settings.probe_max_requests, name
        assert counts.get("fetched", 0) <= settings.probe_max_results, name
        assert settings.probe_max_detail_fetches == 0, (
            "the detail pass must stay off for a probe run"
        )

    # Every outbound request left exactly the ledger row the verdict derives from.
    after_log = await _count(SourceRequestLog)
    written = after_log - before_log
    assert written >= len(per_source), (
        f"{len(per_source)} source(s) reported but only {written} ledger row(s) written"
    )

    async with async_session_maker() as session:
        rows = (await session.execute(select(SourceRequestLog))).scalars().all()

    for row in rows:
        assert row.kind in {"search", "detail"}
        assert row.note, "every ledger row must carry a fetch-side/parse-side note"
        assert row.occurred_at is not None

    print(f"probe run {run_id}: {per_source}")  # noqa: T201 — the operator's evidence


async def test_the_ledger_is_derivable_for_every_recorded_run() -> None:
    """The verdict's evidence base: one ledger row per source per recorded run."""
    async with async_session_maker() as session:
        runs = (await session.execute(select(Run))).scalars().all()
        logged = (
            await session.execute(
                select(func.count()).select_from(SourceRequestLog)
            )
        ).scalar() or 0

    if not runs:
        pytest.skip("no probe runs recorded yet — run scripts/run-probe.sh first")

    expected = sum(len(run.source_counts_json or {}) for run in runs)
    assert logged >= expected, (
        f"{expected} source-run(s) recorded but only {logged} ledger row(s); "
        "the verdict would not be derivable from the recorded rows"
    )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-m", "live"])
