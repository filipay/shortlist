"""`screening_drafts` write/read path — one drafted answer per question, per listing.

House rules, as everywhere in ``app/db/repositories/``:

* repositories are the **only** place SQL lives;
* they take an ``AsyncSession`` explicitly and **never commit** — the caller owns the
  single commit;
* every write is wrapped in a SAVEPOINT (``session.begin_nested()``) so a failure
  here cannot poison the caller's outer transaction;
* ``now`` is injectable so a caller (or a test) can pin the clock.

**Replace-all per listing.** A regeneration replaces the listing's whole draft set
rather than accumulating rows: the delete and the inserts happen inside ONE
SAVEPOINT, so the pair rolls back together and a crash can never leave a half-written
set. The stored ``evidence_json`` carries only the grounded fact ids an answer cited
— never listing text and never model prose beyond the answer itself (D-125 / T-07-03-03).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ScreeningDraft


@dataclass(frozen=True)
class ScreeningDraftInput:
    """One draft to persist. ``evidence_json`` holds grounded fact ids only."""

    question_text: str
    answer_text: str | None = None
    evidence_json: list[str] = field(default_factory=list)
    unsupported: bool = False


@dataclass(frozen=True)
class ScreeningDraftRecord:
    """One ``screening_drafts`` row, ready to render. Frozen: nothing mutates back."""

    id: int
    listing_id: int
    question_text: str
    answer_text: str | None
    evidence_json: list[str]
    unsupported: bool
    created_at: datetime


def _to_record(row: ScreeningDraft) -> ScreeningDraftRecord:
    """One ORM row as its frozen read value. The single mapping, so write and read
    cannot disagree about a field."""
    evidence = row.evidence_json
    return ScreeningDraftRecord(
        id=int(row.id),
        listing_id=int(row.listing_id),
        question_text=row.question_text,
        answer_text=row.answer_text,
        evidence_json=list(evidence) if isinstance(evidence, list) else [],
        unsupported=bool(row.unsupported),
        created_at=row.created_at,
    )


async def read_for_listing(session: AsyncSession, listing_id: int) -> list[ScreeningDraftRecord]:
    """The listing's drafts ordered ``(created_at, id)``. Never commits, never raises.

    The ``id`` tie-break makes the read deterministic when a batch shares one
    ``created_at``.
    """
    rows = (
        await session.execute(
            select(ScreeningDraft)
            .where(ScreeningDraft.listing_id == int(listing_id))
            .order_by(ScreeningDraft.created_at, ScreeningDraft.id)
        )
    ).scalars().all()
    return [_to_record(row) for row in rows]


async def replace_for_listing(
    session: AsyncSession,
    *,
    listing_id: int,
    drafts: Sequence[ScreeningDraftInput],
    now: datetime | None = None,
) -> list[ScreeningDraftRecord]:
    """Replace the listing's whole draft set and return it. Never commits.

    The delete and the inserts share ONE SAVEPOINT, so an invalid insert (an unknown
    ``listing_id`` FK, for instance) rolls the whole set back without poisoning the
    caller's transaction. An empty ``drafts`` clears the listing's rows.
    """
    moment = now if now is not None else datetime.now(UTC)
    listing_id = int(listing_id)
    async with session.begin_nested():
        await session.execute(
            delete(ScreeningDraft).where(ScreeningDraft.listing_id == listing_id)
        )
        for draft in drafts:
            session.add(
                ScreeningDraft(
                    listing_id=listing_id,
                    question_text=draft.question_text,
                    answer_text=draft.answer_text,
                    evidence_json=list(draft.evidence_json),
                    unsupported=bool(draft.unsupported),
                    created_at=moment,
                )
            )
        await session.flush()

    return await read_for_listing(session, listing_id)


async def append_draft(
    session: AsyncSession,
    *,
    listing_id: int,
    draft: ScreeningDraftInput,
    now: datetime | None = None,
) -> ScreeningDraftRecord:
    """Insert ONE draft without touching the listing's existing rows. Never commits.

    The ad-hoc-question path (D-124) adds a single row. Routing it through
    ``replace_for_listing`` re-issues every existing row's primary key and resets its
    ``created_at``, stranding any page already open on those ``draft_id`` values. One
    insert keeps the existing rows' identity (and their per-answer delete targets)
    intact. Wrapped in a SAVEPOINT like every write here.
    """
    moment = now if now is not None else datetime.now(UTC)
    row = ScreeningDraft(
        listing_id=int(listing_id),
        question_text=draft.question_text,
        answer_text=draft.answer_text,
        evidence_json=list(draft.evidence_json),
        unsupported=bool(draft.unsupported),
        created_at=moment,
    )
    async with session.begin_nested():
        session.add(row)
        await session.flush()
    return _to_record(row)


async def delete_for_listing(session: AsyncSession, listing_id: int) -> bool:
    """Delete every draft for one listing; ``True`` if any row was removed. Never commits."""
    result = await session.execute(
        delete(ScreeningDraft).where(ScreeningDraft.listing_id == int(listing_id))
    )
    return bool(result.rowcount)


async def delete_draft(session: AsyncSession, *, listing_id: int, draft_id: int) -> bool:
    """Delete ONE draft, scoped to its listing; ``True`` when a row was removed.

    The per-answer removal the package page's delete consumes (07-05). Scoping by
    ``listing_id`` as well as ``draft_id`` means a stale/cross-listing id removes
    nothing. Never commits.
    """
    result = await session.execute(
        delete(ScreeningDraft).where(
            ScreeningDraft.id == int(draft_id),
            ScreeningDraft.listing_id == int(listing_id),
        )
    )
    return bool(result.rowcount)


__all__ = [
    "ScreeningDraftInput",
    "ScreeningDraftRecord",
    "append_draft",
    "delete_draft",
    "delete_for_listing",
    "read_for_listing",
    "replace_for_listing",
]
