"""`cv_drafts` write/read path — the one live generated draft per listing.

House rules, as everywhere in `app/db/repositories/`:

* repositories are the **only** place SQL lives;
* they take an `AsyncSession` explicitly and **never commit** — the caller owns the
  single commit;
* the write is wrapped in a SAVEPOINT (`session.begin_nested()`) so a failure here
  cannot poison the caller's outer transaction;
* `now` is injectable so a caller (or a test) can pin the clock.

**One row per listing.** The generated patch is kept so a reload reconnects to it
(D-108 superseded), and ``upsert_draft`` deliberately REPLACES the previous row for
that listing rather than accumulating history: ``cv_artifacts`` is the retained
compile history, this table is a single live draft. The UNIQUE constraint
``uq_cv_drafts_listing`` backs the same invariant in the schema.

The stored ``patch_json`` is the typed :class:`~app.domain.cv.TailoringPatch`
serialised with Pydantic — fact IDs, weights and reasons, never free text. The stored
``fact_store_hash`` is the semantic ``facts_hash`` captured at generate time, so the
D-109 guard can still refuse a compile after the fact store moves. The schema is
created only by the Alembic migration; there is deliberately no ORM-level table build
in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CvDraft


@dataclass(frozen=True)
class CvDraftRecord:
    """One `cv_drafts` row, ready to render. Frozen: nothing mutates back."""

    id: int
    listing_id: int
    base_cv_version_id: int | None
    patch_json: dict[str, Any]
    fact_store_hash: str | None
    created_at: datetime
    requested_model: str | None = None


def _to_record(row: CvDraft) -> CvDraftRecord:
    """One ORM row as its frozen read value. The single mapping, so write and read
    cannot disagree about a field."""
    return CvDraftRecord(
        id=int(row.id),
        listing_id=int(row.listing_id),
        base_cv_version_id=(
            int(row.base_cv_version_id) if row.base_cv_version_id is not None else None
        ),
        patch_json=dict(row.patch_json) if isinstance(row.patch_json, dict) else row.patch_json,
        fact_store_hash=row.fact_store_hash,
        created_at=row.created_at,
        requested_model=row.requested_model,
    )


async def upsert_draft(
    session: AsyncSession,
    *,
    listing_id: int,
    base_cv_version_id: int | None,
    patch_json: dict[str, Any],
    fact_store_hash: str | None,
    requested_model: str | None = None,
    now: datetime | None = None,
) -> CvDraftRecord:
    """Replace the live draft for one listing and return it. Never commits.

    Regenerating must not accumulate rows: the previous row (if any) is deleted and a
    fresh one inserted inside the same SAVEPOINT, so the pair rolls back together.
    """
    moment = now if now is not None else datetime.now(UTC)
    listing_id = int(listing_id)
    async with session.begin_nested():
        await session.execute(delete(CvDraft).where(CvDraft.listing_id == listing_id))
        row = CvDraft(
            listing_id=listing_id,
            base_cv_version_id=(
                int(base_cv_version_id) if base_cv_version_id is not None else None
            ),
            patch_json=patch_json,
            fact_store_hash=fact_store_hash,
            requested_model=requested_model,
            created_at=moment,
        )
        session.add(row)
        await session.flush()

    return _to_record(row)


async def read_draft(session: AsyncSession, listing_id: int) -> CvDraftRecord | None:
    """The live draft for one listing, or `None`. Never commits, never raises."""
    row = await session.scalar(select(CvDraft).where(CvDraft.listing_id == int(listing_id)))
    return _to_record(row) if row is not None else None


async def delete_draft(session: AsyncSession, listing_id: int) -> bool:
    """Delete the live draft for one listing; `True` if a row was removed.

    The only removal path for a draft. Never commits.
    """
    result = await session.execute(delete(CvDraft).where(CvDraft.listing_id == int(listing_id)))
    return bool(result.rowcount)


__all__ = [
    "CvDraftRecord",
    "delete_draft",
    "read_draft",
    "upsert_draft",
]
