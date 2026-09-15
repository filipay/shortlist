"""Listing repository — the two-key Tier-1 upsert.

``norm`` is currently a mapping (dict-like). Plan 01-03 swaps in the typed
``NormalisedListing``; the accessor below accepts either a mapping or an object
so that swap is additive.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Listing, ListingSource


@dataclass(frozen=True)
class UpsertOutcome:
    """Result of a Tier-1 upsert: what happened and to which rows."""

    kind: str  # "created" | "updated"
    listing_id: int
    listing_source_id: int


def _value(norm: Any, key: str, default: Any = None) -> Any:
    if isinstance(norm, Mapping):
        return norm.get(key, default)
    return getattr(norm, key, default)


_LISTING_FIELDS = (
    "apply_url",
    "title_norm",
    "company_id",
    "company_norm",
    "location_raw",
    "city",
    "region",
    "country_code",
    "location_norm",
    "remote_flag",
    "seniority",
    "description",
    "description_hash",
    "salary_min",
    "salary_max",
    "salary_interval",
    "salary_currency",
    "salary_source",
    "posted_at",
    "quality_signals_json",
    "source_extras_json",
    "blocking_key",
)


async def upsert_listing(session: AsyncSession, *, norm: Any, now: datetime) -> int:
    """Maintain the canonical ``listings`` row, keyed by ``canonical_url``.

    ``first_seen_at`` is set on insert; ``last_seen_at`` is refreshed on update.
    Returns the listing primary key.
    """
    canonical_url = _value(norm, "canonical_url")
    row = await session.scalar(
        select(Listing).where(Listing.canonical_url == canonical_url)
    )

    if row is None:
        row = Listing(
            canonical_url=canonical_url,
            title=_value(norm, "title") or "",
            first_seen_at=now,
            last_seen_at=now,
            content_hash=_value(norm, "content_hash") or "",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        for field in _LISTING_FIELDS:
            value = _value(norm, field)
            if value is not None:
                setattr(row, field, value)
        session.add(row)
    else:
        row.last_seen_at = now
        row.updated_at = now
        new_content_hash = _value(norm, "content_hash")
        if new_content_hash is not None:
            row.content_hash = new_content_hash
        for field in _LISTING_FIELDS:
            value = _value(norm, field)
            if value is not None:
                setattr(row, field, value)

    await session.flush()
    return row.id


async def _find_by_keys(
    session: AsyncSession,
    *,
    source: str,
    source_listing_id: str | None,
    canonical_source_url: str,
) -> ListingSource | None:
    """The ORDERED two-key lookup.

    Key A ``(source, source_listing_id)`` applies only when the value is not
    NULL. Why not a single ``ON CONFLICT (source, source_listing_id)``? Because
    SQLite treats NULLs as *distinct* in a UNIQUE index, so when JobSpy returns
    ``id=None`` the conflict NEVER fires and every run inserts a duplicate. That
    is PITFALLS m9 / AP7, and it is why key B exists.
    """
    row: ListingSource | None = None
    if source_listing_id is not None:
        row = await session.scalar(
            select(ListingSource).where(
                ListingSource.source == source,
                ListingSource.source_listing_id == source_listing_id,
            )
        )
    if row is None:
        row = await session.scalar(
            select(ListingSource).where(
                ListingSource.source == source,
                ListingSource.canonical_source_url == canonical_source_url,
            )
        )
    return row


async def upsert_listing_source(
    session: AsyncSession,
    *,
    source: str,
    norm: Any,
    run_id: int | None,
    now: datetime,
) -> UpsertOutcome:
    """Two-key Tier-1 upsert of one source's listing row.

    On a key hit, ``last_seen_at`` is refreshed. On a miss, INSERT; a concurrent
    inserter can still race, so an ``IntegrityError`` is caught inside a
    SAVEPOINT, re-SELECTed and reported as ``updated``.
    """
    listing_id = await upsert_listing(session, norm=norm, now=now)

    source_listing_id = _value(norm, "source_listing_id")
    canonical_source_url = _value(norm, "canonical_source_url") or _value(
        norm, "canonical_url"
    )
    raw_hash = _value(norm, "raw_hash") or _value(norm, "content_hash") or ""
    source_url = _value(norm, "source_url") or canonical_source_url

    row = await _find_by_keys(
        session,
        source=source,
        source_listing_id=source_listing_id,
        canonical_source_url=canonical_source_url,
    )
    if row is not None:
        row.last_seen_at = now
        return UpsertOutcome("updated", row.listing_id, row.id)

    new_row = ListingSource(
        listing_id=listing_id,
        source=source,
        source_listing_id=source_listing_id,
        source_url=source_url,
        canonical_source_url=canonical_source_url,
        direct_url=_value(norm, "direct_url"),
        first_seen_at=now,
        last_seen_at=now,
        raw_hash=raw_hash,
    )
    try:
        # A SAVEPOINT keeps the outer transaction usable when the race fires.
        async with session.begin_nested():
            session.add(new_row)
            await session.flush()
    except IntegrityError:
        existing = await _find_by_keys(
            session,
            source=source,
            source_listing_id=source_listing_id,
            canonical_source_url=canonical_source_url,
        )
        if existing is None:
            raise
        existing.last_seen_at = now
        await session.flush()
        return UpsertOutcome("updated", existing.listing_id, existing.id)

    return UpsertOutcome("created", listing_id, new_row.id)
