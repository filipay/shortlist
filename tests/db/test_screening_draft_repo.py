"""The `screening_drafts` write/read path — replace-all per listing, one row per question.

The load-bearing properties:

* a regenerate REPLACES the listing's whole set (never accumulates);
* the replace is atomic — an invalid insert rolls the set back without poisoning the
  caller's outer transaction;
* the repository never commits (the caller owns the commit).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ScreeningDraft
from app.db.repositories.screening_draft_repo import (
    ScreeningDraftInput,
    ScreeningDraftRecord,
    append_draft,
    delete_draft,
    delete_for_listing,
    read_for_listing,
    replace_for_listing,
)

NOW = datetime(2026, 9, 30, 10, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 30, 10, 0, 5, tzinfo=UTC)


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession], listing_id: int = 1
) -> int:
    """A real `listings` row: `screening_drafts.listing_id` carries a foreign key."""
    async with session_factory() as session:
        listing = Listing(
            canonical_url=f"https://example.com/jobs/{listing_id}",
            title=f"Screening Role {listing_id}",
            first_seen_at=NOW,
            last_seen_at=NOW,
            content_hash=f"screening-hash-{listing_id}",
            created_at=NOW,
            updated_at=NOW,
            is_active=True,
        )
        session.add(listing)
        await session.commit()
        return int(listing.id)


@pytest_asyncio.fixture(autouse=True)
async def _seeded_listing(session_factory: async_sessionmaker[AsyncSession]) -> None:
    await _seed_listing(session_factory)


async def _count_all(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return int((await session.scalar(select(func.count()).select_from(ScreeningDraft))) or 0)


# --- the write contract --------------------------------------------------------


async def test_replace_read_delete_round_trip(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        written = await replace_for_listing(
            session,
            listing_id=1,
            drafts=[
                ScreeningDraftInput(
                    question_text="Why this role?",
                    answer_text="Because of the pipeline work.",
                    evidence_json=["bul/northwind-labs-2021/1"],
                    unsupported=False,
                ),
                ScreeningDraftInput(
                    question_text="Notice period?",
                    answer_text="Four weeks.",
                    evidence_json=[],
                    unsupported=True,
                ),
            ],
            now=NOW,
        )
        await session.commit()

    assert [type(r) for r in written] == [ScreeningDraftRecord, ScreeningDraftRecord]
    assert [r.question_text for r in written] == ["Why this role?", "Notice period?"]
    assert written[0].evidence_json == ["bul/northwind-labs-2021/1"]
    assert written[1].unsupported is True

    async with session_factory() as session:
        read = await read_for_listing(session, 1)
    assert [r.question_text for r in read] == ["Why this role?", "Notice period?"]
    # SQLite round-trips a DateTime naive; compare the wall-clock value.
    assert read[0].created_at.replace(tzinfo=None) == NOW.replace(tzinfo=None)

    async with session_factory() as session:
        assert await delete_for_listing(session, 1) is True
        await session.commit()

    async with session_factory() as session:
        assert await read_for_listing(session, 1) == []


async def test_replace_round_trips_the_specific_warnings_and_band(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """G-07-3: the checker's findings and the advisory band survive persistence."""
    async with session_factory() as session:
        written = await replace_for_listing(
            session,
            listing_id=1,
            drafts=[
                ScreeningDraftInput(
                    question_text="Why this role?",
                    answer_text="I shipped 97% of it.",
                    evidence_json=["bul/northwind-labs-2021/1"],
                    warnings_json=[
                        "unsupported evidence id 'bul/missing/9': not a fact id in the candidate's CV",
                        "unsupported number '97': appears in neither the CV facts nor the listing",
                    ],
                    band="ungrounded",
                    unsupported=True,
                )
            ],
            now=NOW,
        )
        await session.commit()

    assert written[0].warnings_json == [
        "unsupported evidence id 'bul/missing/9': not a fact id in the candidate's CV",
        "unsupported number '97': appears in neither the CV facts nor the listing",
    ]
    assert written[0].band == "ungrounded"

    async with session_factory() as session:
        read = await read_for_listing(session, 1)
    assert read[0].warnings_json == written[0].warnings_json
    assert read[0].band == "ungrounded"


async def test_a_draft_without_specifics_reads_back_empty_and_none(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Fail-closed degradation: a legacy/directly-seeded row has no specifics."""
    async with session_factory() as session:
        written = await replace_for_listing(
            session,
            listing_id=1,
            drafts=[ScreeningDraftInput(question_text="Q", unsupported=True)],
            now=NOW,
        )
        await session.commit()

    assert written[0].warnings_json == []
    assert written[0].band is None

    async with session_factory() as session:
        read = await read_for_listing(session, 1)
    assert read[0].warnings_json == []
    assert read[0].band is None


async def test_append_draft_preserves_existing_rows_warnings(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await replace_for_listing(
            session,
            listing_id=1,
            drafts=[
                ScreeningDraftInput(
                    question_text="Q1",
                    warnings_json=["unsupported number '12': appears in neither source"],
                    band="borderline",
                    unsupported=True,
                )
            ],
            now=NOW,
        )
        await session.commit()

    async with session_factory() as session:
        await append_draft(
            session,
            listing_id=1,
            draft=ScreeningDraftInput(question_text="Ad-hoc"),
            now=LATER,
        )
        await session.commit()

    async with session_factory() as session:
        after = await read_for_listing(session, 1)
    assert [r.question_text for r in after] == ["Q1", "Ad-hoc"]
    assert after[0].warnings_json == ["unsupported number '12': appears in neither source"]
    assert after[0].band == "borderline"
    assert after[0].id == first[0].id


async def test_a_second_replace_replaces_and_never_accumulates(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await replace_for_listing(
            session,
            listing_id=1,
            drafts=[
                ScreeningDraftInput(question_text="Q1"),
                ScreeningDraftInput(question_text="Q2"),
                ScreeningDraftInput(question_text="Q3"),
            ],
            now=NOW,
        )
        await session.commit()

    async with session_factory() as session:
        second = await replace_for_listing(
            session,
            listing_id=1,
            drafts=[ScreeningDraftInput(question_text="Only")],
            now=LATER,
        )
        await session.commit()

    assert [r.question_text for r in second] == ["Only"]
    assert await _count_all(session_factory) == 1, "a regenerate replaces the set"


async def test_an_empty_draft_set_clears_the_listing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await replace_for_listing(
            session,
            listing_id=1,
            drafts=[ScreeningDraftInput(question_text="Q1")],
            now=NOW,
        )
        await session.commit()

    async with session_factory() as session:
        cleared = await replace_for_listing(session, listing_id=1, drafts=[], now=LATER)
        await session.commit()

    assert cleared == []
    assert await _count_all(session_factory) == 0, "an empty set leaves no stale rows"


async def test_replace_never_commits(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as writer:
        await replace_for_listing(
            writer,
            listing_id=1,
            drafts=[ScreeningDraftInput(question_text="Q")],
            now=NOW,
        )
        # deliberately no commit

    assert await _count_all(session_factory) == 0, "the writer must not commit"
    async with session_factory() as session:
        assert await read_for_listing(session, 1) == []


async def test_an_unknown_listing_fk_rolls_back_without_poisoning_the_outer_transaction(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await replace_for_listing(
                session,
                listing_id=999,
                drafts=[ScreeningDraftInput(question_text="Orphan")],
                now=NOW,
            )
        # The SAVEPOINT rolled back; the outer transaction must still be usable.
        recovered = await replace_for_listing(
            session,
            listing_id=1,
            drafts=[ScreeningDraftInput(question_text="Valid")],
            now=LATER,
        )
        await session.commit()

    assert [r.question_text for r in recovered] == ["Valid"]
    async with session_factory() as session:
        assert [r.question_text for r in await read_for_listing(session, 1)] == ["Valid"]


# --- the single-row append ------------------------------------------------------


async def test_append_draft_inserts_one_row_and_keeps_existing_ids(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """IN-02: appending must not re-issue the existing rows' ids/created_at."""
    async with session_factory() as session:
        first = await replace_for_listing(
            session,
            listing_id=1,
            drafts=[
                ScreeningDraftInput(question_text="Q1", answer_text="one"),
                ScreeningDraftInput(question_text="Q2", answer_text="two"),
            ],
            now=NOW,
        )
        await session.commit()

    async with session_factory() as session:
        appended = await append_draft(
            session,
            listing_id=1,
            draft=ScreeningDraftInput(question_text="Ad-hoc"),
            now=LATER,
        )
        await session.commit()

    assert appended.question_text == "Ad-hoc"
    async with session_factory() as session:
        after = await read_for_listing(session, 1)
    assert [r.question_text for r in after] == ["Q1", "Q2", "Ad-hoc"]
    assert [r.id for r in after[:2]] == [first[0].id, first[1].id], "ids must survive"
    assert after[0].created_at.replace(tzinfo=None) == NOW.replace(tzinfo=None)
    assert after[2].created_at.replace(tzinfo=None) == LATER.replace(tzinfo=None)


async def test_append_draft_never_commits(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as writer:
        await append_draft(
            writer, listing_id=1, draft=ScreeningDraftInput(question_text="Q"), now=NOW
        )
        # deliberately no commit

    assert await _count_all(session_factory) == 0, "the writer must not commit"


# --- the per-row delete --------------------------------------------------------


async def test_delete_draft_removes_only_the_named_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        written = await replace_for_listing(
            session,
            listing_id=1,
            drafts=[
                ScreeningDraftInput(question_text="Q1"),
                ScreeningDraftInput(question_text="Q2"),
                ScreeningDraftInput(question_text="Q3"),
            ],
            now=NOW,
        )
        await session.commit()

    target = written[1]
    async with session_factory() as session:
        removed = await delete_draft(session, listing_id=1, draft_id=target.id)
        await session.commit()
    assert removed is True

    async with session_factory() as session:
        remaining = await read_for_listing(session, 1)
    assert [r.question_text for r in remaining] == ["Q1", "Q3"]

    # Deleting the same row again removes nothing.
    async with session_factory() as session:
        assert await delete_draft(session, listing_id=1, draft_id=target.id) is False


async def test_delete_draft_scoped_to_its_listing_removes_nothing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        written = await replace_for_listing(
            session,
            listing_id=1,
            drafts=[ScreeningDraftInput(question_text="Q1")],
            now=NOW,
        )
        await session.commit()

    async with session_factory() as session:
        # Correct id, wrong listing: the row belongs to listing 1.
        assert await delete_draft(session, listing_id=2, draft_id=written[0].id) is False

    async with session_factory() as session:
        assert await read_for_listing(session, 1) != []


async def test_read_for_listing_on_an_empty_table_returns_empty(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        assert await read_for_listing(session, 1) == []
        assert await delete_for_listing(session, 1) is False


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
