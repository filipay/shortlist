"""QUEUE-09 / D-29 / T-02-21 / T-02-23 — the merge rate, the rows behind it, revert.

The page's job is to make an automatic merge *safe to leave switched on*: the rate
and the rows behind it are on one page, both listings are shown by their own fields,
and a wrong merge is one click from undone without deleting anything.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingDupe, Run, Source
from app.db.repositories.dupe_repo import apply_merge
from app.db.repositories.listing_repo import upsert_listing_source
from app.domain.dedup import MergeDecision
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

MERGED_AT = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
#: An earlier run's clock. Every merge written at `MERGED_AT` belongs to the latest
#: run's window; a merge at this instant belongs to the prior run's window.
EARLIER_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
FILLED_LOCATION = "Dublin, Ireland"

#: A title that is unambiguous evidence of the escaping rule: `base.html` contains
#: `<script src=...>` tags, so the payload is asserted whole rather than by tag name.
XSS_TITLE = "<script>x</script> Senior Engineer"
ESCAPED_XSS_TITLE = "&lt;script&gt;x&lt;/script&gt; Senior Engineer"


def _norm(
    source: str,
    *,
    title: str,
    location_raw: str | None,
    index: int = 1,
) -> object:
    """The production normalisation path, so the fixture writes what a run writes."""
    return normalise_listing(
        RawListing(
            source=source,  # type: ignore[arg-type]
            source_listing_id=f"{source}-{index}",
            source_url=f"https://{source}.example.com/jobs/{index}",
            direct_url=None,
            title=title,
            company_name="Acme",
            location_raw=location_raw,
            description="Build the thing.",
            posted_at=date(2026, 9, 1),
        )
    )


async def _register_sources(
    session_factory: async_sessionmaker[AsyncSession], *names: str
) -> None:
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    source: str,
    norm: object,
) -> int:
    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session, source=source, norm=norm, run_id=None, now=MERGED_AT
        )
        await session.commit()
    return outcome.listing_id


async def _seed_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    fetched: int,
    started_at: datetime = MERGED_AT,
) -> int:
    """One run, so `merge_rate` has a window to name."""
    async with session_factory() as session:
        run = Run(
            trigger="manual",
            status="done",
            started_at=started_at,
            finished_at=started_at,
            fetched_count=fetched,
        )
        session.add(run)
        await session.flush()
        run_id = int(run.id)
        await session.commit()
    return run_id


async def _seed_merged_pair(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    survivor_title: str = "Senior Python Engineer",
    twin_title: str = "Senior Python Engineer (m/f/d)",
) -> tuple[int, int, int]:
    """Two listings and one audited merge, written through the production repo."""
    await _register_sources(session_factory, "linkedin", "indeed")
    survivor_id = await _seed_listing(
        session_factory,
        source="linkedin",
        norm=_norm("linkedin", title=survivor_title, location_raw=None),
    )
    twin_id = await _seed_listing(
        session_factory,
        source="indeed",
        norm=_norm("indeed", title=twin_title, location_raw=FILLED_LOCATION),
    )

    async with session_factory() as session:
        dupe_id = await apply_merge(
            session,
            decision=MergeDecision(
                survivor_id=survivor_id, absorbed_id=twin_id, score=95.0, method="fuzzy_tuple"
            ),
            now=MERGED_AT,
            run_id=None,
        )
        await session.commit()
    return dupe_id, survivor_id, twin_id


async def _apply_merge_at(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    survivor_id: int,
    twin_id: int,
    merged_at: datetime,
) -> int:
    """One audited merge on a caller-supplied clock (so a run window can own it)."""
    async with session_factory() as session:
        dupe_id = await apply_merge(
            session,
            decision=MergeDecision(
                survivor_id=survivor_id, absorbed_id=twin_id, score=95.0, method="fuzzy_tuple"
            ),
            now=merged_at,
            run_id=None,
        )
        await session.commit()
    return dupe_id


# --- the page -----------------------------------------------------------------


async def test_merges_page_lists_the_rate_its_window_and_the_rows_behind_it(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    dupe_id, survivor_id, twin_id = await _seed_merged_pair(session_factory)
    await _seed_run(session_factory, fetched=3)

    response = await client.get("/merges")

    assert response.status_code == 200
    text = response.text

    # The rate is a percentage with BOTH integers beside it, and the window is named
    # rather than left as an unlabelled all-time aggregate. The label is deliberately
    # "this run only", not "latest run": the latter reads as the latest measurement of
    # the OVERALL rate, which is how a 0% window got misread as broken dedup.
    assert "33%" in text, "1 merge over 3 fetched must render 33%"
    assert "1 merged / 3 fetched" in text
    assert "this run only" in text
    assert "0 reverted" in text

    # The narrow scope is spelled out in prose too, so a 0% on a well-deduped corpus
    # cannot be read as a failure.
    assert 'id="merge-rate-scope"' in text
    assert "not an all-time rate" in text

    # The rows behind the number are on the same page, newest-first with stable ids.
    assert 'id="merges-table"' in text
    assert f'id="merge-row-{dupe_id}"' in text
    assert "Senior Python Engineer" in text
    assert "Senior Python Engineer (m/f/d)" in text
    assert "fuzzy_tuple" in text
    assert "95.0" in text

    # Both endpoints are identified by their OWN fields, including their sources.
    assert "linkedin" in text
    assert "indeed" in text

    # The survivor's pre-merge values are readable (D-26: judge the merge yourself).
    assert "location_raw" in text

    # The router is wired: both listings still exist and the row is un-reverted.
    async with session_factory() as session:
        listings = (await session.execute(select(Listing))).scalars().all()
        dupe = await session.get(ListingDupe, dupe_id)

    assert {listing.id for listing in listings} == {survivor_id, twin_id}
    assert dupe is not None and dupe.reverted_at is None


async def test_merge_rate_windows_both_operands_to_the_latest_run(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """CR-01: the rate must not divide an all-time merge count by one run's fetched.

    Two runs, one merge in each window, the latest run fetched 3. The page names the
    latest run as its window, so it must report that window's rate (1 merged / 3
    fetched = 33%) — never the all-time merge count (2) over that denominator (67%,
    a number that would exceed 100% as more runs merge).
    """
    await _register_sources(session_factory, "linkedin", "indeed")
    early_survivor = await _seed_listing(
        session_factory,
        source="linkedin",
        norm=_norm("linkedin", title="Early Role", location_raw=None, index=1),
    )
    early_twin = await _seed_listing(
        session_factory,
        source="indeed",
        norm=_norm("indeed", title="Early Role (m/f/d)", location_raw=FILLED_LOCATION, index=1),
    )
    latest_survivor = await _seed_listing(
        session_factory,
        source="linkedin",
        norm=_norm("linkedin", title="Latest Role", location_raw=None, index=2),
    )
    latest_twin = await _seed_listing(
        session_factory,
        source="indeed",
        norm=_norm("indeed", title="Latest Role (m/f/d)", location_raw=FILLED_LOCATION, index=2),
    )

    await _apply_merge_at(
        session_factory, survivor_id=early_survivor, twin_id=early_twin, merged_at=EARLIER_AT
    )
    await _apply_merge_at(
        session_factory, survivor_id=latest_survivor, twin_id=latest_twin, merged_at=MERGED_AT
    )

    await _seed_run(session_factory, fetched=10, started_at=EARLIER_AT)
    await _seed_run(session_factory, fetched=3, started_at=MERGED_AT)

    response = await client.get("/merges")

    assert response.status_code == 200
    text = response.text
    assert "33%" in text, "1 merge in the latest window over 3 fetched must render 33%"
    assert "1 merged / 3 fetched" in text
    assert "2 merged" not in text, "the all-time numerator must not be used"
    # The window narrows the RATE, not the audit list: both merges are still shown.
    assert text.count("merge-row") >= 2


async def test_merges_page_escapes_listing_text(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """T-02-23: listing text is untrusted; autoescape is the only escaping in play."""
    await _seed_merged_pair(session_factory, survivor_title=XSS_TITLE)

    response = await client.get("/merges")

    assert response.status_code == 200
    assert ESCAPED_XSS_TITLE in response.text, "the escaped form must be rendered"
    assert XSS_TITLE not in response.text, "the raw tag must never reach the page"


async def test_the_page_has_no_unsafe_filter_on_listing_text() -> None:
    """A guard on the template source, so a later edit cannot quietly opt out."""
    template = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "web"
        / "templates"
        / "html"
        / "merges.html"
    ).read_text(encoding="utf-8")

    assert "|safe" not in template
    assert 'id="merges-table"' in template


# --- revert -------------------------------------------------------------------


async def test_reverting_a_merge_restores_the_survivor_and_marks_the_audit_row(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    dupe_id, survivor_id, _twin_id = await _seed_merged_pair(session_factory)
    await _seed_run(session_factory, fetched=2)

    async with session_factory() as session:
        before = await session.get(Listing, survivor_id)
    assert before is not None and before.location_raw == FILLED_LOCATION

    response = await client.post(f"/merges/{dupe_id}/revert")

    assert response.status_code == 200
    assert 'id="merges-table"' in response.text, "the swap target must survive the swap"
    assert "reverted" in response.text
    # The rate moves on swap: 0 merges left in force after the revert.
    assert "0 merged / 2 fetched" in response.text

    async with session_factory() as session:
        dupe = await session.get(ListingDupe, dupe_id)
        survivor = await session.get(Listing, survivor_id)
        total = (await session.execute(select(ListingDupe))).scalars().all()

    assert dupe is not None, "the audit row is never deleted (T-02-21)"
    assert dupe.reverted_at is not None
    assert dupe.reverted_by == "local"
    assert len(total) == 1
    assert survivor is not None
    assert survivor.location_raw is None, "the snapshot value was restored"
    assert survivor.title == "Senior Python Engineer", "only snapshot fields are touched"


async def test_reverting_an_unknown_merge_is_a_404(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _register_sources(session_factory, "linkedin")

    response = await client.post("/merges/9999/revert")

    assert response.status_code == 404
    assert "Unknown merge" in response.text


async def test_a_second_revert_writes_nothing_and_is_idempotent(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    dupe_id, survivor_id, _twin_id = await _seed_merged_pair(session_factory)

    first = await client.post(f"/merges/{dupe_id}/revert")
    assert first.status_code == 200

    async with session_factory() as session:
        dupe = await session.get(ListingDupe, dupe_id)
        assert dupe is not None and dupe.reverted_at is not None
        first_reverted_at = dupe.reverted_at

    # A decisive probe: if the second revert re-applied the snapshot it would reset
    # this sentinel back to `None`.
    async with session_factory() as session:
        survivor = await session.get(Listing, survivor_id)
        assert survivor is not None
        survivor.location_raw = "Galway, Ireland"
        await session.commit()

    second = await client.post(f"/merges/{dupe_id}/revert")

    assert second.status_code == 200
    assert "already reverted" in second.text

    async with session_factory() as session:
        dupe = await session.get(ListingDupe, dupe_id)
        survivor = await session.get(Listing, survivor_id)

    assert dupe is not None and dupe.reverted_at == first_reverted_at, (
        "an already-reverted row must not have its flag rewritten"
    )
    assert survivor is not None and survivor.location_raw == "Galway, Ireland", (
        "the survivor must not be restored twice"
    )
