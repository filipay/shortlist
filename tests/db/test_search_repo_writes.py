"""CRIT-01 / CRIT-03 / D-33 / D-36 — the search/rule write half and its version contract.

The DB lane uses a manual session with explicit commits (the `source_repo` contract:
the repository never commits). It pins the four behaviours that make a run's
`criteria_snapshot_json` + `searches.version` meaningful:

* a real criteria change bumps the version by exactly one, an identical re-submit
  does not;
* a whole-search enable/disable does not bump it, but a rule toggle does;
* a rule write bumps the *owning search's* version;
* deleting a search removes only its own rows — a run's snapshot survives.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import (
    FilterRule,
    Listing,
    ListingDupe,
    ListingExclusion,
    Run,
    Search,
)
from app.db.repositories import search_repo

NOW = datetime(2026, 9, 1, tzinfo=UTC)
LATER = datetime(2026, 9, 2, tzinfo=UTC)


async def _make_search(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str = "Dublin Python",
    criteria: dict[str, object] | None = None,
) -> int:
    async with session_factory() as session:
        record = await search_repo.create_search(
            session, name=name, criteria=criteria or {"keywords": "python"}, now=NOW
        )
        await session.commit()
        return record.id


async def _version(
    session_factory: async_sessionmaker[AsyncSession], search_id: int
) -> int:
    async with session_factory() as session:
        row = await session.get(Search, search_id)
        assert row is not None
        return int(row.version)


async def _count(session_factory: async_sessionmaker[AsyncSession], model: type) -> int:
    async with session_factory() as session:
        return int(
            (await session.scalar(select(func.count()).select_from(model))) or 0
        )


async def test_update_search_bumps_the_version_only_on_a_real_change(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    search_id = await _make_search(session_factory)
    assert await _version(session_factory, search_id) == 1

    async with session_factory() as session:
        # Identical criteria: no churn.
        await search_repo.update_search(
            session, search_id=search_id, criteria={"keywords": "python"}, now=LATER
        )
        await session.commit()
    assert await _version(session_factory, search_id) == 1

    async with session_factory() as session:
        # A changed mapping: exactly one bump.
        await search_repo.update_search(
            session, search_id=search_id, criteria={"keywords": "python", "location": "Dublin"},
            now=LATER,
        )
        await session.commit()
    assert await _version(session_factory, search_id) == 2


async def test_two_sequential_edits_after_a_create_give_version_three(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    search_id = await _make_search(session_factory)
    async with session_factory() as session:
        await search_repo.update_search(
            session, search_id=search_id, name="Renamed", now=LATER
        )
        await session.commit()
    async with session_factory() as session:
        await search_repo.update_search(
            session, search_id=search_id, criteria={"keywords": "go"}, now=LATER
        )
        await session.commit()
    assert await _version(session_factory, search_id) == 3


async def test_enable_disable_does_not_bump_the_version(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    search_id = await _make_search(session_factory)

    async with session_factory() as session:
        record = await search_repo.set_search_enabled(
            session, search_id=search_id, enabled=False, now=LATER
        )
        await session.commit()

    assert record is not None
    assert record.enabled is False
    assert await _version(session_factory, search_id) == 1, "a toggle is not a criteria change"

    async with session_factory() as session:
        record = await search_repo.set_search_enabled(
            session, search_id=search_id, enabled=True, now=LATER
        )
        await session.commit()

    assert record is not None
    assert record.enabled is True
    assert await _version(session_factory, search_id) == 1


async def test_rule_writes_bump_the_owning_search_version(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    search_id = await _make_search(session_factory)

    async with session_factory() as session:
        rule = await search_repo.create_rule(
            session,
            search_id=search_id,
            kind="exclude_keyword",
            params={"terms": ["crypto"]},
            position=0,
            now=LATER,
        )
        await session.commit()
    assert await _version(session_factory, search_id) == 2

    # An identical update is not a change.
    async with session_factory() as session:
        await search_repo.update_rule(
            session, rule_id=int(rule.rule_id), params={"terms": ["crypto"]}, now=LATER
        )
        await session.commit()
    assert await _version(session_factory, search_id) == 2

    # A changed params mapping is.
    async with session_factory() as session:
        await search_repo.update_rule(
            session, rule_id=int(rule.rule_id), params={"terms": ["crypto", "nft"]}, now=LATER
        )
        await session.commit()
    assert await _version(session_factory, search_id) == 3


async def test_toggling_a_rule_bumps_the_version_unlike_toggling_a_search(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    search_id = await _make_search(session_factory)
    async with session_factory() as session:
        rule = await search_repo.create_rule(
            session,
            search_id=search_id,
            kind="remote",
            params={"require": True},
            position=0,
            now=LATER,
        )
        await session.commit()
    assert await _version(session_factory, search_id) == 2

    async with session_factory() as session:
        updated = await search_repo.update_rule(
            session, rule_id=int(rule.rule_id), enabled=False, now=LATER
        )
        await session.commit()

    assert updated is not None
    assert updated.enabled is False
    assert await _version(session_factory, search_id) == 3, (
        "which rules are enabled is part of the effective criteria"
    )


async def test_delete_rule_removes_one_row_and_bumps_the_version(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    search_id = await _make_search(session_factory)
    async with session_factory() as session:
        first = await search_repo.create_rule(
            session, search_id=search_id, kind="remote", params={"require": True},
            position=0, now=LATER,
        )
        second = await search_repo.create_rule(
            session, search_id=search_id, kind="company_blocklist",
            params={"companies": ["acme"]}, position=1, now=LATER,
        )
        await session.commit()
    before = await _version(session_factory, search_id)

    async with session_factory() as session:
        deleted = await search_repo.delete_rule(session, rule_id=int(first.rule_id))
        await session.commit()
    assert deleted is True
    assert await _version(session_factory, search_id) == before + 1

    async with session_factory() as session:
        rows = (
            (await session.execute(select(FilterRule).order_by(FilterRule.id))).scalars().all()
        )
    assert [int(row.id) for row in rows] == [int(second.rule_id)]

    async with session_factory() as session:
        again = await search_repo.delete_rule(session, rule_id=int(first.rule_id))
        await session.commit()
    assert again is False


async def test_delete_search_removes_it_and_all_its_rules_only(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    search_id = await _make_search(session_factory)
    other_id = await _make_search(session_factory, name="Other", criteria={"keywords": "go"})

    async with session_factory() as session:
        for index, kind in enumerate(("remote", "company_blocklist")):
            params = {"require": True} if kind == "remote" else {"companies": ["acme"]}
            await search_repo.create_rule(
                session, search_id=search_id, kind=kind, params=params,
                position=index, now=LATER,
            )
        await search_repo.create_rule(
            session, search_id=other_id, kind="remote", params={"require": True},
            position=0, now=LATER,
        )
        await session.commit()

    # Seed the things a delete must NOT touch.
    async with session_factory() as session:
        await _seed_protected_rows(session, search_id)
        await session.commit()

    protected = (Listing, ListingExclusion, ListingDupe, Run)
    before = {model.__name__: await _count(session_factory, model) for model in protected}
    assert all(value > 0 for value in before.values()), "the protected counts must be non-zero"

    async with session_factory() as session:
        deleted = await search_repo.delete_search(session, search_id=search_id)
        await session.commit()
    assert deleted is True

    async with session_factory() as session:
        remaining_rules = (
            (
                await session.execute(
                    select(FilterRule).where(FilterRule.search_id == search_id)
                )
            )
            .scalars()
            .all()
        )
        surviving = await session.get(Search, search_id)
    assert remaining_rules == []
    assert surviving is None

    after = {model.__name__: await _count(session_factory, model) for model in protected}
    assert after == before, "a search delete must not remove listings, exclusions, dupes or runs"


async def test_a_deleted_searchs_run_keeps_its_criteria_snapshot(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    search_id = await _make_search(session_factory)
    snapshot = {str(search_id): {"name": "Dublin Python", "version": 1}}
    async with session_factory() as session:
        run = Run(
            search_id=search_id,
            trigger="manual",
            status="done",
            started_at=NOW,
            finished_at=LATER,
            criteria_snapshot_json=snapshot,
        )
        session.add(run)
        await session.commit()
        run_id = int(run.id)

    async with session_factory() as session:
        assert await search_repo.delete_search(session, search_id=search_id) is True
        await session.commit()

    async with session_factory() as session:
        stored = await session.get(Run, run_id)
    assert stored is not None, "the run row survives"
    assert stored.criteria_snapshot_json == snapshot, "reproducibility survives the delete"


async def test_updates_and_deletes_on_unknown_ids_do_not_raise(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        assert await search_repo.update_search(
            session, search_id=9999, name="x", now=LATER
        ) is None
        assert await search_repo.set_search_enabled(
            session, search_id=9999, enabled=False, now=LATER
        ) is None
        assert (
            await search_repo.update_rule(
                session, rule_id=9999, enabled=False, now=LATER
            )
        ) is None
        assert await search_repo.delete_rule(session, rule_id=9999) is False
        assert await search_repo.delete_search(session, search_id=9999) is False
        await session.commit()


async def test_create_rule_with_an_unknown_kind_writes_no_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    search_id = await _make_search(session_factory)

    assert search_repo.validate_rule_params("not_a_kind", {}) != []

    async with session_factory() as session:
        with pytest.raises(ValueError):
            await search_repo.create_rule(
                session,
                search_id=search_id,
                kind="not_a_kind",
                params={},
                position=0,
                now=LATER,
            )
        await session.rollback()

    assert await _count(session_factory, FilterRule) == 0


async def _seed_protected_rows(session: AsyncSession, search_id: int) -> None:
    """A listing pair, an exclusion, a merge audit row and a run pointing at `search_id`.

    These are the rows T-02-34 forbids `delete_search` from touching. The listings
    are flushed first so the FK-carrying rows can reference real ids.
    """
    listing = Listing(
        canonical_url="https://example.com/jobs/1",
        title="Engineer",
        company_norm="acme",
        first_seen_at=NOW,
        last_seen_at=NOW,
        content_hash="hash-1",
        created_at=NOW,
        updated_at=NOW,
    )
    twin = Listing(
        canonical_url="https://example.com/jobs/2",
        title="Engineer II",
        company_norm="acme",
        first_seen_at=NOW,
        last_seen_at=NOW,
        content_hash="hash-2",
        created_at=NOW,
        updated_at=NOW,
    )
    session.add_all([listing, twin])
    await session.flush()

    session.add(
        ListingExclusion(
            listing_id=listing.id,
            run_id=None,
            rule_id="1",
            rule_kind="remote",
            detail_json={"require": True},
            created_at=NOW,
            criteria_version=1,
        )
    )
    session.add(
        ListingDupe(
            listing_id=listing.id,
            dup_listing_id=twin.id,
            method="fuzzy",
            score=95.0,
            merged_at=NOW,
        )
    )
    session.add(
        Run(
            search_id=search_id,
            trigger="manual",
            status="done",
            started_at=NOW,
            finished_at=LATER,
            criteria_snapshot_json={str(search_id): {"name": "Dublin Python", "version": 1}},
        )
    )


__all__ = []
