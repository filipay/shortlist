"""FILT-02 / D-36 / T-02-17 — the exclusion table's DB-level invariants.

The pure lane (`tests/domain/test_filter.py`) proves *what* fires. This lane proves
what is **stored** when it does: one row per firing rule per listing per run, the
evidence preserved verbatim, a per-rule count that is exact because it is a
`GROUP BY` over one row per rule — and, load-bearing for the privacy boundary, that
the evidence never becomes a copy of the listing's own prose.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingExclusion, Run
from app.db.repositories.exclusion_repo import excluded_counts_for_run, record_exclusions
from app.domain.filter import RuleOutcome

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)

#: The description the exclusion must NEVER leak. Its distinctive phrases are
#: asserted absent below; the term itself legitimately appears as `detail["term"]`.
DESCRIPTION = "We are building a crypto trading desk on the Zephyr platform."
CRYPTO_TERM = "crypto"
DESCRIPTION_PHRASES = ("trading desk", "Zephyr platform", "We are building")


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession], *, index: int = 1
) -> int:
    async with session_factory() as session:
        listing = Listing(
            canonical_url=f"https://example.com/jobs/{index}",
            title="Backend Engineer",
            title_norm="backend engineer",
            description=DESCRIPTION,
            company_norm="acme",
            first_seen_at=NOW,
            last_seen_at=NOW,
            content_hash=f"content-hash-{index}",
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(listing)
        await session.flush()
        listing_id = int(listing.id)
        await session.commit()
    return listing_id


async def _seed_run(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        run = Run(trigger="manual", status="running", started_at=NOW)
        session.add(run)
        await session.flush()
        run_id = int(run.id)
        await session.commit()
    return run_id


def _keyword_outcome(rule_id: str) -> RuleOutcome:
    return RuleOutcome(
        excluded=True,
        rule_id=rule_id,
        rule_kind="exclude_keyword",
        detail={"term": CRYPTO_TERM, "field": "description", "count": 1},
    )


def _salary_outcome(rule_id: str) -> RuleOutcome:
    return RuleOutcome(
        excluded=True,
        rule_id=rule_id,
        rule_kind="salary_floor",
        detail={"floor": 70000.0, "salary_min": 50000.0, "interval": "year", "currency": "EUR"},
    )


async def _write(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    listing_id: int,
    run_id: int,
    outcomes: list[RuleOutcome],
    criteria_version: int | None,
) -> int:
    async with session_factory() as session:
        written = await record_exclusions(
            session,
            listing_id=listing_id,
            run_id=run_id,
            outcomes=outcomes,
            criteria_version=criteria_version,
            now=NOW,
        )
        await session.commit()
    return written


# --- one row per firing rule, evidence verbatim -------------------------------
async def test_one_row_per_outcome_with_detail_preserved_verbatim(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)
    run_id = await _seed_run(session_factory)
    outcomes = [_keyword_outcome("7"), _salary_outcome("9")]

    written = await _write(
        session_factory,
        listing_id=listing_id,
        run_id=run_id,
        outcomes=outcomes,
        criteria_version=6,
    )

    assert written == 2, "one row per firing rule, never a merged row"
    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(ListingExclusion).order_by(ListingExclusion.rule_id)
                )
            )
            .scalars()
            .all()
        )

    assert [row.rule_id for row in rows] == ["7", "9"]
    assert [row.rule_kind for row in rows] == ["exclude_keyword", "salary_floor"]
    assert rows[0].detail_json == outcomes[0].detail
    assert rows[1].detail_json == outcomes[1].detail
    assert rows[0].created_at == NOW.replace(tzinfo=None)


async def test_no_outcomes_writes_nothing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)
    run_id = await _seed_run(session_factory)

    written = await _write(
        session_factory,
        listing_id=listing_id,
        run_id=run_id,
        outcomes=[],
        criteria_version=1,
    )

    assert written == 0
    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(ListingExclusion))
    assert count == 0


# --- per-rule counts are exact and deterministically ordered -------------------
async def test_excluded_counts_for_run_is_an_exact_deterministically_ordered_mapping(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first = await _seed_listing(session_factory, index=1)
    second = await _seed_listing(session_factory, index=2)
    run_id = await _seed_run(session_factory)

    # Rule 9 fires once; rule 7 fires for both listings — so the counts differ and
    # a per-rule (not per-listing) GROUP BY is the only shape that gets 7 -> 2.
    await _write(
        session_factory, listing_id=first, run_id=run_id, outcomes=[_keyword_outcome("7")],
        criteria_version=1,
    )
    await _write(
        session_factory, listing_id=second, run_id=run_id,
        outcomes=[_keyword_outcome("7"), _salary_outcome("9")], criteria_version=1,
    )

    async with session_factory() as session:
        counts = await excluded_counts_for_run(session, run_id=run_id)

    assert counts == {"7": 2, "9": 1}
    # Byte-stable between identical runs: the ordering is part of the contract.
    assert list(counts) == ["7", "9"]
    assert all(isinstance(value, int) for value in counts.values())
    # Round-tripping the mapping is what the persisted JSON does.
    assert json.loads(json.dumps(counts)) == counts


async def test_excluded_counts_for_run_is_empty_for_a_run_with_no_exclusions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _seed_run(session_factory)

    async with session_factory() as session:
        counts = await excluded_counts_for_run(session, run_id=run_id)

    assert counts == {}


# --- criteria_version is the caller's value, never invented --------------------
async def test_criteria_version_is_persisted_and_null_when_not_supplied(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    versioned = await _seed_listing(session_factory, index=1)
    unversioned = await _seed_listing(session_factory, index=2)
    run_id = await _seed_run(session_factory)

    await _write(
        session_factory, listing_id=versioned, run_id=run_id,
        outcomes=[_keyword_outcome("7")], criteria_version=6,
    )
    await _write(
        session_factory, listing_id=unversioned, run_id=run_id,
        outcomes=[_keyword_outcome("7")], criteria_version=None,
    )

    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(ListingExclusion).order_by(ListingExclusion.listing_id)
                )
            )
            .scalars()
            .all()
        )

    assert rows[0].criteria_version == 6
    assert rows[1].criteria_version is None, "the repo never invents a version"


# --- append-only per run (D-36) -----------------------------------------------
async def test_a_listing_excluded_in_two_runs_has_one_row_per_run_and_no_update(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)
    first_run = await _seed_run(session_factory)
    second_run = await _seed_run(session_factory)

    await _write(
        session_factory, listing_id=listing_id, run_id=first_run,
        outcomes=[_keyword_outcome("7")], criteria_version=1,
    )
    async with session_factory() as session:
        before = (
            await session.execute(
                select(ListingExclusion).where(ListingExclusion.run_id == first_run)
            )
        ).scalar_one()
        before_detail = json.loads(json.dumps(before.detail_json))
        before_created = before.created_at

    # The same listing, rejected again by the same rule on a later run.
    await _write(
        session_factory, listing_id=listing_id, run_id=second_run,
        outcomes=[_keyword_outcome("7")], criteria_version=2,
    )

    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(ListingExclusion).order_by(ListingExclusion.run_id)
                )
            )
            .scalars()
            .all()
        )
        after = (
            await session.execute(
                select(ListingExclusion).where(ListingExclusion.run_id == first_run)
            )
        ).scalar_one()

    assert len(rows) == 2, "per-run observations: append, never update"
    assert [row.run_id for row in rows] == [first_run, second_run]
    assert [row.criteria_version for row in rows] == [1, 2]
    # The earlier observation is byte-identical on a re-read.
    assert after.detail_json == before_detail
    assert after.created_at == before_created


# --- the evidence never becomes a copy of the listing prose (T-02-17) ---------
async def test_keyword_evidence_carries_the_term_but_never_the_description_prose(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)
    run_id = await _seed_run(session_factory)

    await _write(
        session_factory, listing_id=listing_id, run_id=run_id,
        outcomes=[_keyword_outcome("7")], criteria_version=1,
    )

    async with session_factory() as session:
        detail = (await session.execute(select(ListingExclusion))).scalar_one().detail_json

    rendered = json.dumps(detail)

    # The term and the field NAME are the evidence — that much is by design.
    assert detail["term"] == CRYPTO_TERM
    assert detail["field"] == "description"
    assert detail["count"] == 1

    # The field's TEXT is not. Neither the whole description nor any distinctive
    # phrase from it appears in the stored evidence.
    assert DESCRIPTION not in rendered
    for phrase in DESCRIPTION_PHRASES:
        assert phrase not in rendered, f"the evidence leaked listing prose: {phrase!r}"

    # A bound is the honest structural twin of the phrase checks: prose cannot fit.
    assert len(rendered) < len(DESCRIPTION), "the evidence blob is longer than the description"
