"""QUEUE-03 — the merge repository's invariants, over the migrated temp database.

D-27 (fill blanks only, an empty string counts as blank), the audit snapshot, A5
(no `listing_sources` re-pointing), the FTS trigger firing on a fill, and the D-28
negative-memory orientations are each asserted here rather than assumed.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingDupe, ListingSource, Source
from app.db.repositories.dupe_repo import apply_merge, merged_pairs, reverted_pairs
from app.db.repositories.listing_repo import _LISTING_FIELDS, upsert_listing_source
from app.domain.dedup import MergeDecision

SURVIVOR_URL = "https://linkedin.example.com/jobs/1"
TWIN_URL = "https://indeed.example.com/jobs/1"
MERGE_NOW = datetime(2026, 9, 2, tzinfo=UTC)
FILLED_LOCATION = "Dublin, Ireland"


def _norm(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "canonical_url": SURVIVOR_URL,
        "source_listing_id": "li-1",
        "source_url": SURVIVOR_URL,
        "canonical_source_url": SURVIVOR_URL,
        "title": "Senior Python Engineer",
        "company_name": "Acme",
        "company_norm": "acme",
        "location_raw": FILLED_LOCATION,
        "description": "Build the thing.",
        "content_hash": "content-hash-1",
        "raw_hash": "raw-hash-1",
        "posted_at": datetime(2026, 9, 1, tzinfo=UTC),
        "salary_min": 50000.0,
        "salary_max": 80000.0,
        "salary_interval": "year",
        "salary_currency": "EUR",
    }
    base.update(overrides)
    return base


def _pair_norms(
    *, survivor: dict | None = None, twin: dict | None = None, suffix: str = "1"
) -> tuple[dict, dict]:
    survivor_norm = _norm(
        canonical_url=f"https://linkedin.example.com/jobs/{suffix}",
        source_url=f"https://linkedin.example.com/jobs/{suffix}",
        canonical_source_url=f"https://linkedin.example.com/jobs/{suffix}",
        source_listing_id=f"li-{suffix}",
    )
    twin_norm = _norm(
        canonical_url=f"https://indeed.example.com/jobs/{suffix}",
        source_url=f"https://indeed.example.com/jobs/{suffix}",
        canonical_source_url=f"https://indeed.example.com/jobs/{suffix}",
        source_listing_id=f"in-{suffix}",
    )
    survivor_norm.update(survivor or {})
    twin_norm.update(twin or {})
    return survivor_norm, twin_norm


async def _register_sources(session_factory: async_sessionmaker[AsyncSession], *names: str) -> None:
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _seed(
    session_factory: async_sessionmaker[AsyncSession],
    survivor_norm: dict,
    twin_norm: dict,
) -> tuple[int, int]:
    async with session_factory() as session:
        survivor = await upsert_listing_source(
            session, source="linkedin", norm=survivor_norm, run_id=None, now=MERGE_NOW
        )
        twin = await upsert_listing_source(
            session, source="indeed", norm=twin_norm, run_id=None, now=MERGE_NOW
        )
        await session.commit()
    return survivor.listing_id, twin.listing_id


async def _merge(
    session_factory: async_sessionmaker[AsyncSession], survivor_id: int, twin_id: int
) -> int:
    decision = MergeDecision(
        survivor_id=survivor_id,
        absorbed_id=twin_id,
        score=95.0,
        method="fuzzy_tuple",
    )
    async with session_factory() as session:
        row_id = await apply_merge(session, decision=decision, now=MERGE_NOW, run_id=None)
        await session.commit()
    return row_id


async def _count(session_factory: async_sessionmaker[AsyncSession], table: type) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(table)) or 0


async def _match(session: AsyncSession, term: str) -> list[int]:
    result = await session.execute(
        text("SELECT rowid FROM listing_fts WHERE listing_fts MATCH :term"),
        {"term": term},
    )
    return [row[0] for row in result.all()]


# --- negative memory (D-28) ---------------------------------------------------
async def test_reverted_pairs_is_empty_then_returns_both_orientations(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    survivor_id, twin_id = await _seed(session_factory, *_pair_norms())
    await _merge(session_factory, survivor_id, twin_id)

    async with session_factory() as session:
        assert await reverted_pairs(session, listing_ids={survivor_id, twin_id}) == set()
        assert await merged_pairs(session, listing_ids={survivor_id, twin_id}) == {
            (survivor_id, twin_id),
            (twin_id, survivor_id),
        }
        dupe = (await session.execute(select(ListingDupe))).scalar_one()
        dupe.reverted_at = MERGE_NOW
        await session.commit()

    async with session_factory() as session:
        pairs = await reverted_pairs(session, listing_ids={survivor_id, twin_id})
        still_merged = await merged_pairs(session, listing_ids={survivor_id, twin_id})
    assert pairs == {(survivor_id, twin_id), (twin_id, survivor_id)}
    assert still_merged == set(), "a reverted pair is no longer an already-merged pair"

    # The orientation of the query set does not matter.
    async with session_factory() as session:
        reversed_query = await reverted_pairs(session, listing_ids={twin_id, survivor_id})
    assert reversed_query == pairs


# --- fill blanks only (D-27) --------------------------------------------------
async def test_merge_fills_blanks_and_never_overwrites_a_non_null(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    survivor_id, twin_id = await _seed(
        session_factory,
        *_pair_norms(
            survivor={"location_raw": None, "salary_min": 50000.0},
            twin={"location_raw": FILLED_LOCATION, "salary_min": 70000.0},
        ),
    )

    row_id = await _merge(session_factory, survivor_id, twin_id)

    async with session_factory() as session:
        survivor = await session.get(Listing, survivor_id)
        twin = await session.get(Listing, twin_id)
        dupes = (await session.execute(select(ListingDupe))).scalars().all()

    assert isinstance(row_id, int)
    assert len(dupes) == 1
    assert dupes[0].id == row_id
    assert survivor is not None and twin is not None
    # The blank was filled from the twin ...
    assert survivor.location_raw == FILLED_LOCATION
    # ... and the survivor's own non-null value was not touched.
    assert survivor.salary_min == 50000.0
    # The twin keeps everything it had.
    assert twin.salary_min == 70000.0
    assert twin.location_raw == FILLED_LOCATION


async def test_an_empty_string_counts_as_blank_but_a_real_value_does_not(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")

    empty_id, empty_twin = await _seed(
        session_factory,
        *_pair_norms(survivor={"location_raw": ""}, twin={"location_raw": FILLED_LOCATION}),
    )
    real_id, real_twin = await _seed(
        session_factory,
        *_pair_norms(
            survivor={"location_raw": "Galway, Ireland"},
            twin={"location_raw": FILLED_LOCATION},
            suffix="2",
        ),
    )

    await _merge(session_factory, empty_id, empty_twin)
    await _merge(session_factory, real_id, real_twin)

    async with session_factory() as session:
        empty = await session.get(Listing, empty_id)
        real = await session.get(Listing, real_id)

    assert empty is not None and empty.location_raw == FILLED_LOCATION
    assert real is not None and real.location_raw == "Galway, Ireland"


# --- the audit snapshot -------------------------------------------------------
async def test_snapshot_records_exactly_the_written_fields_and_their_prior_values(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    survivor_id, twin_id = await _seed(
        session_factory,
        *_pair_norms(
            survivor={"location_raw": None, "salary_min": 50000.0},
            twin={"location_raw": FILLED_LOCATION, "salary_min": 70000.0},
        ),
    )

    await _merge(session_factory, survivor_id, twin_id)

    async with session_factory() as session:
        dupe = (await session.execute(select(ListingDupe))).scalar_one()

    assert set(dupe.snapshot_json) == {"location_raw"}
    assert dupe.snapshot_json["location_raw"] is None
    assert set(dupe.snapshot_json) <= set(_LISTING_FIELDS)
    assert dupe.method == "fuzzy_tuple"
    assert dupe.merged_at == MERGE_NOW.replace(tzinfo=None)
    assert dupe.reverted_at is None


# --- retention (A5) and no deletion -------------------------------------------
async def test_the_merge_deletes_nothing_and_re_points_no_source_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    survivor_id, twin_id = await _seed(
        session_factory,
        *_pair_norms(survivor={"location_raw": None}, twin={"location_raw": FILLED_LOCATION}),
    )

    await _merge(session_factory, survivor_id, twin_id)

    assert await _count(session_factory, Listing) == 2, "the absorbed listing still exists"
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(ListingSource.listing_id, ListingSource.source).order_by(ListingSource.id)
            )
        ).all()
        twin = await session.get(Listing, twin_id)

    assert twin is not None and twin.is_active is True
    assert [(int(listing_id), source) for listing_id, source in rows] == [
        (survivor_id, "linkedin"),
        (twin_id, "indeed"),
    ], "A5: listing_sources rows are NOT re-pointed at the survivor"


# --- FTS stays in sync through the fill (T-02-14) -----------------------------
async def test_a_filled_description_is_searchable_on_the_survivor(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    survivor_id, twin_id = await _seed(
        session_factory,
        *_pair_norms(
            survivor={"description": "", "location_raw": None},
            twin={"description": "Zephyr platform work", "location_raw": FILLED_LOCATION},
        ),
    )

    async with session_factory() as session:
        assert await _match(session, "Zephyr") == [twin_id], (
            "before the merge only the twin carries the term"
        )

    await _merge(session_factory, survivor_id, twin_id)

    async with session_factory() as session:
        found = await _match(session, "Zephyr")

    assert survivor_id in found, "the ORM fill must have fired the listings_au FTS trigger"
    assert set(found) == {survivor_id, twin_id}


# --- the unique index covers one orientation only -----------------------------
async def test_a_same_orientation_duplicate_raises_but_the_reversed_pair_does_not(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    survivor_id, twin_id = await _seed(session_factory, *_pair_norms())
    await _merge(session_factory, survivor_id, twin_id)

    async with session_factory() as session:
        session.add(ListingDupe(listing_id=survivor_id, dup_listing_id=twin_id))
        with pytest.raises(IntegrityError) as error:
            await session.flush()

    assert isinstance(error.value.orig, sqlite3.IntegrityError)

    # The reversed pair is a DIFFERENT key, so the index does not stop it — which
    # is exactly why `reverted_pairs` (both orientations) is the load-bearing
    # negative-memory control rather than the index.
    async with session_factory() as session:
        session.add(ListingDupe(listing_id=twin_id, dup_listing_id=survivor_id))
        await session.flush()
        await session.commit()

    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(ListingDupe))

    assert count == 2
