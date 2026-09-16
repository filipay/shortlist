"""RUN-04 / RUN-03 (rendering half) / D-43 / T-02-43 — the run history surface.

The page renders what each run PERSISTED. These tests therefore assert the persisted
values appear verbatim (the status, the counters, the reason), that the sentence is
derived from the persisted counts, and that a half-written or unfinished run still
renders rather than 500-ing the page.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import FilterRule, Run, Search, Source
from app.db.repositories.exclusion_repo import record_exclusions
from app.db.repositories.listing_repo import upsert_listing_source
from app.domain.filter import RuleOutcome
from app.domain.run_reason import REASONS
from app.pipeline.run import run_pipeline
from app.pipeline.stages import normalise_listing
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
    SearchQuery,
    SourceCapabilities,
)

ROW_ID_RE = re.compile(r'<tr id="run-row-(\d+)"')

NOW = datetime.now(UTC)
XSS_ERROR = "<script>x</script> the board returned garbage"
ESCAPED_XSS_ERROR = "&lt;script&gt;x&lt;/script&gt; the board returned garbage"

CAPABILITIES = SourceCapabilities(
    supports_salary=False,
    supports_salary_min_filter=False,
    supports_remote_flag=True,
    supports_seniority=False,
    supports_full_description_in_search=False,
    requires_second_pass_for_description=False,
    supports_offset_paging=True,
    max_results_per_query=1000,
)

CRYPTO_TERM = "crypto"


class StubAdapter(JobSource):
    """A total adapter with scripted items — no network, no jobspy."""

    capabilities = CAPABILITIES

    def __init__(self, name: str, items: list[RawListing]) -> None:
        self.name = name  # type: ignore[assignment]
        self._items = list(items)

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(
            source=self.name,  # type: ignore[arg-type]
            items=self._items,
            status="ok",
            requests_used=1,
        )


def _raw(source: str, index: int = 1, *, description: str = "Build the thing.") -> RawListing:
    return RawListing(
        source=source,  # type: ignore[arg-type]
        source_listing_id=f"{source}-{index}",
        source_url=f"https://{source}.example.com/jobs/{index}",
        direct_url=None,
        title=f"Engineer {index}",
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description=description,
        posted_at=date(2026, 9, 1),
    )


def _run_ids(body: str) -> list[int]:
    return [int(value) for value in ROW_ID_RE.findall(body)]


async def _register_sources(
    session_factory: async_sessionmaker[AsyncSession], *names: str
) -> None:
    async with session_factory() as session:
        for name in names:
            if await session.scalar(select(Source.id).where(Source.name == name)) is None:
                session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _drive_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str = "linkedin",
    items: list[RawListing] | None = None,
) -> int:
    await _register_sources(session_factory, name)
    return await run_pipeline(
        "manual",
        None,
        session_factory,
        adapters=[StubAdapter(name, items or [_raw(name)])],
    )


async def _insert_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    status: str = "running",
    finished: datetime | None = None,
    errors: list[dict] | None = None,
) -> int:
    async with session_factory() as session:
        run = Run(
            trigger="manual",
            status=status,
            started_at=NOW - timedelta(seconds=30),
            finished_at=finished,
            fetched_count=1,
            deduped_count=0,
            filtered_count=0,
            errors_json=errors,
        )
        session.add(run)
        await session.flush()
        run_id = int(run.id)
        await session.commit()
    return run_id


# --- the empty page -----------------------------------------------------------


async def test_a_fresh_database_shows_the_empty_state(client) -> None:
    response = await client.get("/runs")

    assert response.status_code == 200
    assert 'id="runs-empty"' in response.text
    assert "No runs yet" in response.text
    assert 'hx-post="/runs"' not in response.text, "the history page is not the run control"


# --- a real run ---------------------------------------------------------------


async def test_a_run_renders_its_persisted_status_counters_and_reason(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    run_id = await _drive_run(session_factory)

    response = await client.get("/runs")

    assert response.status_code == 200
    text = response.text
    assert f'id="run-row-{run_id}"' in text
    assert 'data-status="done"' in text, "the persisted status is rendered verbatim"
    assert 'class="run-status run-status-done"' in text

    reason = re.search(rf'id="run-reason-{run_id}">([^<]+)<', text)
    assert reason is not None, "the reason value must be visible"
    assert reason.group(1) in REASONS, f"{reason.group(1)!r} is not one of the six"

    # The sentence is DERIVED from the persisted counts, and for this run those counts
    # are 1 fetched / 1 survivor / 0 exclusions.
    assert "1 listings survived the rules out of 1 fetched" in text
    assert "0 exclusions were recorded" in text

    assert '<td class="run-deduped">0</td>' in text
    assert '<td class="run-filtered">0</td>' in text
    assert '<td class="run-trigger">manual</td>' in text


async def test_two_identical_requests_return_identical_bodies(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The surface is read-only, so a repeat request must be a pure re-render."""
    await _drive_run(session_factory)

    first = await client.get("/runs")
    second = await client.get("/runs")

    assert first.status_code == 200 and second.status_code == 200
    assert first.text == second.text


async def test_runs_render_newest_first_and_stably(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """`(started_at DESC, id DESC)` — the id tie-break matters when two runs share a
    second, which is the norm when a user clicks twice."""
    first = await _drive_run(session_factory)
    second = await _drive_run(session_factory)
    assert second > first

    one = await client.get("/runs")
    two = await client.get("/runs")

    assert _run_ids(one.text) == [second, first], "newest first"
    assert _run_ids(two.text) == _run_ids(one.text), "stable across identical requests"


# --- a run that never finished ------------------------------------------------


async def test_an_unfinished_run_renders_in_flight_with_an_em_dash(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    run_id = await _insert_run(session_factory, status="running", finished=None)

    response = await client.get("/runs")

    assert response.status_code == 200
    text = response.text
    assert f'id="run-row-{run_id}"' in text
    assert 'data-in-flight="1"' in text
    assert '<td class="run-duration">—</td>' in text, "an em dash, never 0s"
    assert "0.0s" not in text and ">0s<" not in text


async def test_a_half_written_run_still_renders(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Every JSON column is nullable, so a run that died mid-flight must not 500."""
    run_id = await _insert_run(
        session_factory, status="failed", finished=NOW, errors=None
    )

    response = await client.get("/runs")
    detail = await client.get(f"/runs/{run_id}")

    assert response.status_code == 200
    assert f'id="run-row-{run_id}"' in response.text
    assert 'data-status="failed"' in response.text, "a failed run is never a clean success"
    assert detail.status_code == 200
    assert "No counts were persisted for this run." in detail.text


# --- the expansion ------------------------------------------------------------


async def test_the_detail_fragment_carries_the_stage_log_and_the_per_rule_counts(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A run that filtered everything: the detail explains it and stays bounded."""
    await _register_sources(session_factory, "linkedin")
    async with session_factory() as session:
        search = Search(
            name="Dublin Python",
            enabled=True,
            criteria_json={"keywords": "python"},
            version=3,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(search)
        await session.flush()
        rule = FilterRule(
            search_id=search.id,
            kind="exclude_keyword",
            params_json={"terms": [CRYPTO_TERM], "fields": ["description"]},
            enabled=True,
            position=0,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(rule)
        await session.flush()
        rule_id = int(rule.id)
        await session.commit()

    run_id = await run_pipeline(
        "manual",
        None,
        session_factory,
        adapters=[
            StubAdapter(
                "linkedin",
                [_raw("linkedin", description=f"We are building a {CRYPTO_TERM} desk.")],
            )
        ],
    )

    response = await client.get(f"/runs/{run_id}")

    assert response.status_code == 200
    text = response.text
    assert f'id="run-detail-{run_id}"' in text
    assert "<details" in text and "<summary>" in text, "the stage log is collapsible"
    assert "Raw stage log" in text
    assert "criteria_compile" in text, "plan 02-05's criteria-compile entry survives"
    assert "persist:linkedin" in text, "the per-source persist summary is in the log"
    assert f"rule {rule_id}: 1" in text, "the per-rule excluded count"
    assert "Dublin Python (version 3)" in text, "the criteria snapshot section"


async def test_the_detail_route_404s_for_an_unknown_run(client) -> None:
    response = await client.get("/runs/9999")

    assert response.status_code == 404
    assert 'id="run-detail-9999"' in response.text


# --- the expansion rows carry the list the run reported ------------------------


async def test_a_directly_seeded_exclusion_appears_in_the_detail(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """`excluded_counts_for_run` is the read side, exercised on a hand-built run."""
    await _register_sources(session_factory, "linkedin")
    run_id = await _insert_run(session_factory, status="done", finished=NOW)

    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session,
            source="linkedin",
            norm=normalise_listing(_raw("linkedin")),
            run_id=None,
            now=NOW,
        )
        listing_id = int(outcome.listing_id)
        await session.commit()

    async with session_factory() as session:
        await record_exclusions(
            session,
            listing_id=listing_id,
            run_id=run_id,
            outcomes=[
                RuleOutcome(
                    excluded=True,
                    rule_id="7",
                    rule_kind="exclude_keyword",
                    detail={"term": CRYPTO_TERM, "field": "description", "count": 1},
                )
            ],
            criteria_version=1,
            now=NOW,
        )
        await session.commit()

    response = await client.get(f"/runs/{run_id}")

    assert response.status_code == 200
    assert "rule 7: 1" in response.text


# --- escaping -----------------------------------------------------------------


async def test_the_page_escapes_a_board_derived_error_string(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """T-02-41: `errors_json` carries board-derived text, so it is rendered as text."""
    run_id = await _insert_run(
        session_factory,
        status="partial",
        finished=NOW,
        errors=[{"source": "linkedin", "status": "error", "error": XSS_ERROR}],
    )

    listing = await client.get("/runs")
    detail = await client.get(f"/runs/{run_id}")

    for response in (listing, detail):
        assert response.status_code == 200
        assert ESCAPED_XSS_ERROR in response.text, "the escaped form is rendered"
        assert XSS_ERROR not in response.text, "the raw tag must never reach the page"
