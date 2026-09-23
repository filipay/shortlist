"""FILT-03 / D-35 / D-36 — rejected listings are reachable, with the rule that fired.

The toggle is a VIEW over `listing_exclusions`, not a second page, and the reason it
shows is the LATEST run's observation: a listing excluded by an older run but not by
the newest is back in the default view. That is D-36's per-run semantics made
visible, and it is what lets retuning a rule bring listings back with no deletion.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import FilterRule, Run, Search, Source
from app.db.repositories.exclusion_repo import record_exclusions
from app.db.repositories.listing_repo import upsert_listing_source
from app.domain.filter import RuleOutcome
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
RULE_KIND = "exclude_keyword"

TOGGLE_RE = re.compile(r'<input[^>]*id="queue-toggle-excluded"[^>]*>', re.S)
PAGER_PREV_RE = re.compile(r'id="queue-page-prev"[^>]*hx-get="([^"]+)"', re.S)
PAGER_NEXT_RE = re.compile(r'id="queue-page-next"[^>]*hx-get="([^"]+)"', re.S)
ROW_ID_RE = re.compile(r'<tr id="listing-row-(\d+)"')


def _rows(body: str) -> list[int]:
    return [int(value) for value in ROW_ID_RE.findall(body)]


async def _register_sources(
    session_factory: async_sessionmaker[AsyncSession], *names: str
) -> None:
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _seed_search_and_rule(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[int, int]:
    """One enabled search and one enabled rule — the rule id the exclusion references."""
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
            kind=RULE_KIND,
            params_json={"terms": ["crypto"]},
            enabled=True,
            position=0,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(rule)
        await session.flush()
        ids = (int(search.id), int(rule.id))
        await session.commit()
    return ids


async def _seed_run(
    session_factory: async_sessionmaker[AsyncSession], *, started_at: datetime = NOW
) -> int:
    async with session_factory() as session:
        run = Run(
            trigger="manual",
            status="done",
            started_at=started_at,
            finished_at=started_at,
            fetched_count=2,
        )
        session.add(run)
        await session.flush()
        run_id = int(run.id)
        await session.commit()
    return run_id


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession], *, title: str, index: int
) -> int:
    raw = RawListing(
        source="linkedin",  # type: ignore[arg-type]
        source_listing_id=f"linkedin-{index}",
        source_url=f"https://linkedin.example.com/jobs/{index}",
        direct_url=None,
        title=title,
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="We are building a crypto trading desk.",
        posted_at=date(2026, 9, 1),
    )
    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session, source="linkedin", norm=normalise_listing(raw), run_id=None, now=NOW
        )
        listing_id = int(outcome.listing_id)
        await session.commit()
    return listing_id


async def _exclude(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    listing_id: int,
    run_id: int,
    rule_id: int,
) -> None:
    """The same write path production uses (plan 02-05's repository)."""
    outcome = RuleOutcome(
        excluded=True,
        rule_id=str(rule_id),
        rule_kind=RULE_KIND,
        detail={"term": "crypto", "field": "description", "count": 1},
    )
    async with session_factory() as session:
        await record_exclusions(
            session,
            listing_id=listing_id,
            run_id=run_id,
            outcomes=[outcome],
            criteria_version=1,
            now=NOW,
        )
        await session.commit()


async def _fixture(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[int, int, int, int]:
    """`(run_id, rule_id, excluded_listing_id, kept_listing_id)`."""
    await _register_sources(session_factory, "linkedin")
    _search_id, rule_id = await _seed_search_and_rule(session_factory)
    run_id = await _seed_run(session_factory)
    excluded = await _seed_listing(session_factory, title="Crypto Trader", index=1)
    kept = await _seed_listing(session_factory, title="Backend Engineer", index=2)
    await _exclude(
        session_factory, listing_id=excluded, run_id=run_id, rule_id=rule_id
    )
    return run_id, rule_id, excluded, kept


# --- the toggle ----------------------------------------------------------------


async def test_the_default_view_hides_excluded_listings_and_the_toggle_reveals_them(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _run_id, _rule_id, excluded, kept = await _fixture(session_factory)

    default = await client.get("/")
    toggled = await client.get("/", params={"excluded": "1"})

    assert default.status_code == 200 and toggled.status_code == 200

    # The default view withholds the excluded listing entirely — no title, no class.
    assert "Crypto Trader" not in default.text
    assert "dimmed" not in default.text
    assert _rows(default.text) == [kept]

    # The toggle shows both, with the excluded one dimmed and chipped.
    assert "Crypto Trader" in toggled.text
    assert "dimmed" in toggled.text
    assert sorted(_rows(toggled.text)) == sorted([excluded, kept])
    assert f'class="rule-chip rule-chip-{RULE_KIND}"' in toggled.text
    assert RULE_KIND in toggled.text, "the chip names the rule kind"


async def test_a_search_does_not_surface_an_excluded_listing_unless_the_toggle_is_on(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The FTS branch keeps the excluded predicate; the toggle is the only override.

    Without this, an edit that stopped passing `predicates` to the `MATCH`
    statement would leak every rejected listing back in the moment the user typed.
    """
    _run_id, _rule_id, excluded, kept = await _fixture(session_factory)

    default = await client.get("/", params={"q": "crypto"})

    assert default.status_code == 200
    assert "Crypto Trader" not in default.text, "a search must not bypass the exclusion"
    assert _rows(default.text) == [kept], "the kept listing still matches the query"

    toggled = await client.get("/", params={"q": "crypto", "excluded": "1"})

    assert toggled.status_code == 200
    assert sorted(_rows(toggled.text)) == sorted([excluded, kept]), (
        "the toggle is the only way back in"
    )


async def test_a_listing_excluded_only_by_an_older_run_returns_to_the_default_view(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """D-36 per-run observations: the toggle shows the LATEST run's reason only."""
    _run_id, rule_id, excluded, _kept = await _fixture(session_factory)

    hidden = await client.get("/")
    assert "Crypto Trader" not in hidden.text

    # Run 2 starts later and excludes nothing, so the listing is back by default —
    # the exclusion predicate asks only about the LATEST run.
    second_run = await _seed_run(session_factory, started_at=NOW + timedelta(hours=1))
    assert second_run > _run_id, "the second run must be the latest one"
    assert rule_id is not None

    async with session_factory() as session:
        rows = (await session.execute(select(Run))).scalars().all()
    assert len(rows) == 2, "both runs are still auditable; only the latest is consulted"

    revealed = await client.get("/")
    assert "Crypto Trader" in revealed.text, "an older run's exclusion no longer applies"

    toggled = await client.get("/", params={"excluded": "1"})
    assert "rule-chip" not in toggled.text, "the chip is gone with the latest run's reason"


async def test_the_chip_count_is_grouped_over_the_run_not_per_row(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Two listings rejected by the same rule read `(2)`, not `(1)` twice."""
    await _register_sources(session_factory, "linkedin")
    _search_id, rule_id = await _seed_search_and_rule(session_factory)
    run_id = await _seed_run(session_factory)
    first = await _seed_listing(session_factory, title="Crypto Trader", index=1)
    second = await _seed_listing(session_factory, title="Crypto Analyst", index=2)
    await _exclude(session_factory, listing_id=first, run_id=run_id, rule_id=rule_id)
    await _exclude(session_factory, listing_id=second, run_id=run_id, rule_id=rule_id)

    response = await client.get("/", params={"excluded": "1"})

    assert response.status_code == 200
    assert f"{RULE_KIND} (2)" in response.text, "the count is the run's, not the row's"
    assert f"{RULE_KIND} (1)" not in response.text


# --- paging -------------------------------------------------------------------


async def test_a_predicate_change_resets_the_page_and_the_pager_carries_it(
    client, session_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    """Page N of a DIFFERENT filtered set is meaningless, so the toggle restarts."""
    monkeypatch.setattr(settings, "queue_page_size", 2)
    await _register_sources(session_factory, "linkedin")
    for index in range(1, 6):
        await _seed_listing(session_factory, title=f"Engineer {index}", index=index)

    page = await client.get("/")

    toggle = TOGGLE_RE.search(page.text)
    assert toggle is not None, "the Show excluded toggle must be on the page"
    assert 'hx-get="/queue/list"' in toggle.group(0)
    assert "offset" not in toggle.group(0), "a predicate change must not carry an offset"

    fragment = await client.get("/queue/list", params={"excluded": "0", "offset": "2"})

    next_match = PAGER_NEXT_RE.search(fragment.text)
    assert next_match is not None, "page 2 of 3 must offer Next"
    assert "offset=4" in next_match.group(1), "Next carries the next offset"
    assert "excluded=" not in next_match.group(1), "and the current predicate set"

    prev_match = PAGER_PREV_RE.search(fragment.text)
    assert prev_match is not None, "page 2 of 3 must offer Previous"
    assert "offset" not in prev_match.group(1), (
        "the previous page of page 2 is offset 0, which the query string omits"
    )

    assert "Page 2 of 3 (2 per page)" in fragment.text


async def test_the_first_page_has_no_previous_and_the_last_has_no_next(
    client, session_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    """The pager's two ends: nothing before page 1, nothing after the last page."""
    monkeypatch.setattr(settings, "queue_page_size", 2)
    await _register_sources(session_factory, "linkedin")
    for index in range(1, 6):
        await _seed_listing(session_factory, title=f"Engineer {index}", index=index)

    first = await client.get("/queue/list")

    assert PAGER_PREV_RE.search(first.text) is None, "page 1 has no Previous"
    first_next = PAGER_NEXT_RE.search(first.text)
    assert first_next is not None and "offset=2" in first_next.group(1)
    assert "Page 1 of 3 (2 per page)" in first.text

    last = await client.get("/queue/list", params={"offset": "4"})

    assert PAGER_NEXT_RE.search(last.text) is None, "the last page has no Next"
    last_prev = PAGER_PREV_RE.search(last.text)
    assert last_prev is not None and "offset=2" in last_prev.group(1), (
        "the previous page of page 3 is offset 2"
    )
    assert "Page 3 of 3 (2 per page)" in last.text


async def test_the_page_size_is_server_fixed_and_only_surfaced(
    client, session_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    """T-02-28: `limit` is never read from the request; the pager only displays it."""
    monkeypatch.setattr(settings, "queue_page_size", 2)
    await _register_sources(session_factory, "linkedin")
    for index in range(1, 6):
        await _seed_listing(session_factory, title=f"Engineer {index}", index=index)

    default = await client.get("/queue/list")
    attempted = await client.get("/queue/list", params={"limit": "1"})

    assert len(_rows(attempted.text)) == 2, "a request-supplied limit must be ignored"
    assert _rows(attempted.text) == _rows(default.text), (
        "?limit=1 returns the same rows as the server-fixed page size"
    )
    assert "(2 per page)" in attempted.text, "the position line shows the server value"


async def test_the_full_page_renders_the_pager_and_the_position_line(
    client, session_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    """The pager lives in the shared partial, so the page renders it too."""
    monkeypatch.setattr(settings, "queue_page_size", 2)
    await _register_sources(session_factory, "linkedin")
    for index in range(1, 6):
        await _seed_listing(session_factory, title=f"Engineer {index}", index=index)

    page = await client.get("/")

    assert 'id="queue-page-next"' in page.text
    assert "Page 1 of 3 (2 per page)" in page.text
