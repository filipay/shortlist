"""RUN-03's rendering half / D-44 — the queue explains its own emptiness, in place.

The strip renders the run's PERSISTED reason and a sentence derived from that run's own
counts. The decisive assertion is the last one in the `all_filtered` case: the number in
the sentence equals the integer in `runs.reason_counts_json`, so the page cannot invent a
figure the run never recorded (Pattern 4).
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import FilterRule, Run, Search, Source
from app.db.repositories import state_repo
from app.pipeline.run import run_pipeline
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
    SearchQuery,
    SourceCapabilities,
)

NOW = datetime.now(UTC)
CRYPTO_TERM = "crypto"

REASON_VALUE_RE = re.compile(r'id="last-run-reason-value">([^<]+)<')

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


async def _register_sources(
    session_factory: async_sessionmaker[AsyncSession], *names: str
) -> None:
    async with session_factory() as session:
        for name in names:
            if await session.scalar(select(Source.id).where(Source.name == name)) is None:
                session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _seed_reject_everything_rule(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """One enabled search whose single rule rejects every fetched listing."""
    async with session_factory() as session:
        search = Search(
            name="Dublin Python",
            enabled=True,
            criteria_json={"keywords": "python"},
            version=1,
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
    return rule_id


async def _run_row(
    session_factory: async_sessionmaker[AsyncSession], run_id: int
) -> Run:
    async with session_factory() as session:
        row = await session.get(Run, run_id)
    assert row is not None
    return row


def _reason_value(body: str) -> str:
    match = REASON_VALUE_RE.search(body)
    assert match is not None, "the strip must show the reason value"
    return match.group(1)


# --- all_filtered -------------------------------------------------------------


async def test_an_all_filtered_run_explains_the_empty_queue_with_persisted_numbers(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _register_sources(session_factory, "linkedin")
    await _seed_reject_everything_rule(session_factory)

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
    row = await _run_row(session_factory, run_id)
    assert row.reason == "all_filtered"

    response = await client.get("/")

    assert response.status_code == 200
    assert _reason_value(response.text) == "all_filtered"
    assert "All 1 fetched listings were rejected by the rules" in response.text
    assert "0 listings" in response.text, "the queue really is empty"

    # The page cannot invent a number: every figure in the sentence comes from that
    # run's own persisted decomposition.
    persisted = row.reason_counts_json or {}
    excluded_total = sum(int(value) for value in (persisted.get("excluded_by_rule") or {}).values())
    assert excluded_total == 1, "the run recorded exactly one exclusion"
    assert f"({excluded_total} exclusion recorded)" in response.text


# --- nothing_new --------------------------------------------------------------


async def test_a_nothing_new_run_says_so(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Listing survived the rules, but none is newer than the watermark."""
    await _register_sources(session_factory, "linkedin")
    async with session_factory() as session:
        await state_repo.advance_watermark(session, now=NOW + timedelta(days=1))
        await session.commit()

    run_id = await run_pipeline(
        "manual", None, session_factory, adapters=[StubAdapter("linkedin", [_raw("linkedin")])]
    )
    row = await _run_row(session_factory, run_id)
    assert row.reason == "nothing_new", f"expected nothing_new, got {row.reason!r}"

    response = await client.get("/")

    assert response.status_code == 200
    assert _reason_value(response.text) == "nothing_new"
    assert "1 listings survived the rules but 0 are new since the queue" in response.text


# --- no_sources_enabled -------------------------------------------------------


async def test_a_no_sources_run_keeps_the_phase_one_degraded_message(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The reason enum names the condition; the Phase-1 vocabulary still explains it."""
    run_id = await run_pipeline("manual", None, session_factory, adapters=[])
    row = await _run_row(session_factory, run_id)
    assert row.reason == "no_sources_enabled"

    response = await client.get("/")

    assert response.status_code == 200
    assert _reason_value(response.text) == "no_sources_enabled"
    assert 'id="run-degraded"' in response.text, "the pre-existing degraded message"
    assert "No sources ran" in response.text


# --- the strip itself ---------------------------------------------------------


async def test_the_strip_links_to_the_run_history(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _register_sources(session_factory, "linkedin")
    await run_pipeline(
        "manual", None, session_factory, adapters=[StubAdapter("linkedin", [_raw("linkedin")])]
    )

    response = await client.get("/")

    assert response.status_code == 200
    assert 'id="last-run"' in response.text
    assert 'href="/runs"' in response.text
    assert 'id="run-history-link"' in response.text
    # One renderer: the strip carries the existing run partial's own root.
    assert 'id="run-status"' in response.text


async def test_the_strip_is_absent_when_no_run_exists(client) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert 'id="last-run"' not in response.text
    assert 'id="run-history-link"' not in response.text


async def test_the_pinned_phase_one_queue_contract_survives_the_strip(client) -> None:
    """The empty corpus: no run, no listings, and every pinned assertion intact."""
    response = await client.get("/")

    assert response.status_code == 200
    assert 'hx-post="/runs"' in response.text
    assert 'id="run-status-slot"' in response.text
    assert "0 listings" in response.text
    assert "No listings yet" in response.text


async def test_a_render_failure_in_the_strip_does_not_500_the_queue(
    client, session_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    """WR-01: the strip is decorative, so its RENDER must sit inside the guard too.

    Before the fix only `list_runs` was guarded; a template failure (an older or
    hand-edited `stage_log_json`) escaped as a 500 on `GET /` — the product page.
    """
    await _register_sources(session_factory, "linkedin")
    await run_pipeline(
        "manual", None, session_factory, adapters=[StubAdapter("linkedin", [_raw("linkedin")])]
    )

    from app.web import routes as web_routes

    def _boom(request, run, sources):  # noqa: ANN001
        raise RuntimeError("the partial cannot traverse this run row")

    monkeypatch.setattr(web_routes, "render_run_fragment", _boom)

    response = await client.get("/")

    assert response.status_code == 200, "a decorative strip must never 500 the queue"
    assert 'id="last-run"' not in response.text, "the strip degrades to absent"
