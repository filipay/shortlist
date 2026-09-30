"""`applications` + `application_events` write/read path (D-128 … D-135).

House rules, as everywhere in `app/db/repositories/`:

* repositories are the **only** place SQL lives;
* they take an `AsyncSession` explicitly and **never commit** — the caller owns the
  single commit;
* the write is wrapped in a SAVEPOINT (`session.begin_nested()`) so a failure here
  cannot poison the caller's outer transaction;
* `now` is injectable so a caller (or a test) can pin the clock.

**Current state on the row, history in the event table (D-131).** Every status change
sets `applications.status` AND appends exactly one `application_events` row in the SAME
`begin_nested()` block, so a crash between the two writes is impossible. The event
table is insert-only, trigger-enforced by migration 0006; this module exposes no
update/delete for it, and no caller may write `applications.status` any other way.

**The `applied` gate (D-118 / D-129).** A transition to `applied` requires an
`ok` artefact, resolved through `cv_artifact_repo.read_for_download(ok_only=True)` —
the `compile_status == "ok"` predicate is applied IN SQL, so a `blocked`/`failed` row
is unreachable **even by id**, and a refusal writes nothing. The stored
`applications.cv_artifact_id` is the historical "exact CV that was sent": the tracker
read deliberately does NOT re-filter the linked artefact on `compile_status`, so a
link survives a later artefact status change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Application,
    ApplicationEvent,
    Company,
    CvArtifact,
    Listing,
)
from app.db.repositories import cv_artifact_repo

#: The eight frozen status values, mirroring `ck_applications_status` (migration 0001)
#: exactly. This is the allow-list the routes validate against — the vocabulary is
#: never widened here without a coordinated migration on the CHECK.
APPLICATION_STATUSES: tuple[str, ...] = (
    "discovered",
    "queued",
    "shortlisted",
    "applied",
    "interviewing",
    "offer",
    "rejected",
    "withdrawn",
)

#: The stages from which the needs-action order excludes a row (D-133). Also the
#: stages a `next_action_at` no longer implies follow-up on.
TERMINAL_STATUSES: tuple[str, ...] = ("offer", "rejected", "withdrawn")


@dataclass(frozen=True)
class ArtifactOption:
    """One selectable `ok` artefact for the applied picker (D-129)."""

    id: int
    created_at: datetime | None


@dataclass(frozen=True)
class ApplicationRecord:
    """One `applications` row joined to its listing/company, ready to render.

    Frozen: nothing mutates back. `is_overdue` and `next_action_date` are derived at
    read time (the template does no date arithmetic), and `event_count` is the
    `History (n)` summary count — computed in SQL, never a client recount.
    """

    id: int
    listing_id: int
    status: str
    cv_artifact_id: int | None
    applied_at: datetime | None
    next_action_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    listing_title: str | None
    company: str | None
    event_count: int
    is_overdue: bool
    next_action_date: str
    ok_artifacts: tuple[ArtifactOption, ...]


@dataclass(frozen=True)
class ApplicationEventRecord:
    """One `application_events` row, ready to render (frozen)."""

    id: int
    application_id: int
    from_status: str | None
    to_status: str
    occurred_at: datetime
    note: str | None


def _naive(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; normalise tz-aware ones before comparing."""
    if value is None:
        return None
    return value.replace(tzinfo=None) if value.tzinfo else value


def parse_next_action(value: str | None) -> datetime | None:
    """Parse an ISO date/datetime form value, or `None` for an absent/blank one.

    Never trusts a caller's clock for `applied_at`/`occurred_at`; this is only the
    user-set follow-up date (D-135). An unparseable value is dropped, not raised: a
    bad form field must not 500 the row.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed


def _record(
    *,
    row: Application,
    listing_title: str | None,
    company: str | None,
    event_count: int,
    now: datetime | None,
    ok_artifacts: tuple[ArtifactOption, ...],
) -> ApplicationRecord:
    overdue = False
    moment = _naive(now)
    next_action = _naive(row.next_action_at)
    if moment is not None and next_action is not None and row.status not in TERMINAL_STATUSES:
        overdue = next_action < moment
    return ApplicationRecord(
        id=int(row.id),
        listing_id=int(row.listing_id),
        status=row.status,
        cv_artifact_id=int(row.cv_artifact_id) if row.cv_artifact_id is not None else None,
        applied_at=row.applied_at,
        next_action_at=row.next_action_at,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
        listing_title=listing_title,
        company=company,
        event_count=int(event_count),
        is_overdue=overdue,
        next_action_date=row.next_action_at.date().isoformat() if row.next_action_at else "",
        ok_artifacts=ok_artifacts,
    )


async def _ok_artifacts_by_listing(
    session: AsyncSession, listing_ids: set[int]
) -> dict[int, tuple[ArtifactOption, ...]]:
    """Every `ok` artefact for the given listings, newest first, in **one** query.

    This is the ok-only picker's source (D-129): the same SQL-level `compile_status`
    predicate `read_for_download` uses, so a blocked/failed CV can never be offered.
    """
    if not listing_ids:
        return {}
    rows = (
        await session.execute(
            select(CvArtifact.id, CvArtifact.listing_id, CvArtifact.created_at)
            .where(
                CvArtifact.listing_id.in_(sorted(listing_ids)),
                CvArtifact.compile_status == "ok",
            )
            .order_by(
                CvArtifact.listing_id,
                CvArtifact.created_at.desc(),
                CvArtifact.id.desc(),
            )
        )
    ).all()
    grouped: dict[int, list[ArtifactOption]] = {}
    for artifact_id, listing_id, created_at in rows:
        grouped.setdefault(int(listing_id), []).append(
            ArtifactOption(id=int(artifact_id), created_at=created_at)
        )
    return {listing_id: tuple(options) for listing_id, options in grouped.items()}


async def read_tracker(
    session: AsyncSession, *, now: datetime | None = None
) -> list[ApplicationRecord]:
    """Every application, joined to its listing/company, newest first.

    Bounded scan accepted at 1-5 users (the tracker holds tens of rows); the upgrade
    path is an index on `applications(next_action_at)` if it ever grows.
    # ponytail: bounded full scan accepted; add the next_action_at index if the tracker grows.
    """
    rows = (
        await session.execute(
            select(
                Application,
                Listing.title,
                Company.name,
                func.count(ApplicationEvent.id),
            )
            .join(Listing, Application.listing_id == Listing.id)
            .outerjoin(Company, Listing.company_id == Company.id)
            .outerjoin(ApplicationEvent, ApplicationEvent.application_id == Application.id)
            .group_by(Application.id, Listing.title, Company.name)
            .order_by(Application.updated_at.desc(), Application.id.desc())
        )
    ).all()
    options = await _ok_artifacts_by_listing(session, {int(row.listing_id) for row, *_ in rows})
    return [
        _record(
            row=row,
            listing_title=title,
            company=company,
            event_count=count,
            now=now,
            ok_artifacts=options.get(int(row.listing_id), ()),
        )
        for row, title, company, count in rows
    ]


async def read_application(
    session: AsyncSession, application_id: int, *, now: datetime | None = None
) -> ApplicationRecord | None:
    """One application by id, joined the same way `read_tracker` joins it."""
    result = (
        await session.execute(
            select(
                Application,
                Listing.title,
                Company.name,
                func.count(ApplicationEvent.id),
            )
            .join(Listing, Application.listing_id == Listing.id)
            .outerjoin(Company, Listing.company_id == Company.id)
            .outerjoin(ApplicationEvent, ApplicationEvent.application_id == Application.id)
            .where(Application.id == int(application_id))
            .group_by(Application.id, Listing.title, Company.name)
        )
    ).first()
    if result is None:
        return None
    row, title, company, count = result
    options = await _ok_artifacts_by_listing(session, {int(row.listing_id)})
    return _record(
        row=row,
        listing_title=title,
        company=company,
        event_count=count,
        now=now,
        ok_artifacts=options.get(int(row.listing_id), ()),
    )


async def read_history(
    session: AsyncSession, application_id: int
) -> list[ApplicationEventRecord]:
    """One application's events, chronological `(occurred_at, id)` (D-134)."""
    rows = (
        (
            await session.execute(
                select(ApplicationEvent)
                .where(ApplicationEvent.application_id == int(application_id))
                .order_by(ApplicationEvent.occurred_at, ApplicationEvent.id)
            )
        )
        .scalars()
        .all()
    )
    return [
        ApplicationEventRecord(
            id=int(row.id),
            application_id=int(row.application_id),
            from_status=row.from_status,
            to_status=row.to_status,
            occurred_at=row.occurred_at,
            note=row.note,
        )
        for row in rows
    ]


async def record_application(
    session: AsyncSession,
    *,
    listing_id: int,
    status: str,
    cv_artifact_id: int | None,
    notes: str | None,
    next_action_at: datetime | None,
    now: datetime,
) -> int | None:
    """Insert one application and exactly one `created` event, in one SAVEPOINT.

    Returns the new application id, or `None` for a typed refusal (an `applied` stage
    with no `ok` artefact). Validates `status` against `APPLICATION_STATUSES` **before
    any SQL**, so an unknown value is a clear `ValueError`, not a raw `IntegrityError`.
    Never commits — the caller commits once, so the row and its event land together.
    """
    if status not in APPLICATION_STATUSES:
        raise ValueError(
            f"unknown status {status!r}; expected one of {list(APPLICATION_STATUSES)}"
        )

    artifact_id: int | None = None
    if status == "applied":
        if cv_artifact_id is None:
            return None
        record = await cv_artifact_repo.read_for_download(
            session, cv_artifact_id, ok_only=True
        )
        if record is None:
            return None
        artifact_id = record.id

    row = Application(
        listing_id=int(listing_id),
        status=status,
        cv_artifact_id=artifact_id,
        applied_at=now if status == "applied" else None,
        next_action_at=next_action_at,
        notes=notes,
        created_at=now,
        updated_at=now,
    )
    async with session.begin_nested():
        session.add(row)
        await session.flush()
        session.add(
            ApplicationEvent(
                application_id=int(row.id),
                from_status=None,
                to_status=status,
                occurred_at=now,
                note=notes,
            )
        )
        await session.flush()
    return int(row.id)


async def transition_application(
    session: AsyncSession,
    *,
    application_id: int,
    to_status: str,
    cv_artifact_id: int | None = None,
    note: str | None = None,
    now: datetime,
) -> int | None:
    """Move one application to `to_status`, appending exactly one event in the SAME block.

    The row update and the event append share one `begin_nested()`, so they commit or
    roll back together. A transition to `applied` requires an `ok` artefact through the
    same SQL-level gate as `record_application`; a refusal (missing/blocked artefact,
    unknown application) writes nothing and returns `None`. `applied_at` is stamped
    server-side (`now`), never read from a form (D-130). Never commits.
    """
    if to_status not in APPLICATION_STATUSES:
        raise ValueError(
            f"unknown status {to_status!r}; expected one of {list(APPLICATION_STATUSES)}"
        )

    row = await session.get(Application, int(application_id))
    if row is None:
        return None

    artifact_id = row.cv_artifact_id
    if to_status == "applied":
        if cv_artifact_id is None:
            return None
        record = await cv_artifact_repo.read_for_download(
            session, cv_artifact_id, ok_only=True
        )
        if record is None:
            return None
        artifact_id = record.id

    from_status = row.status
    async with session.begin_nested():
        row.status = to_status
        row.updated_at = now
        row.cv_artifact_id = artifact_id
        if to_status == "applied":
            row.applied_at = now
        session.add(
            ApplicationEvent(
                application_id=int(row.id),
                from_status=from_status,
                to_status=to_status,
                occurred_at=now,
                note=note,
            )
        )
        await session.flush()
    return int(row.id)


async def update_application(
    session: AsyncSession,
    *,
    application_id: int,
    notes: str | None,
    next_action_at: datetime | None,
    now: datetime,
) -> int | None:
    """Edit the ordinary mutable columns only (D-135) — appends NO event.

    `notes` and `next_action_at` carry no analytic history, so a status change is the
    only thing that writes to `application_events`. Never commits.
    """
    row = await session.get(Application, int(application_id))
    if row is None:
        return None
    async with session.begin_nested():
        row.notes = notes
        row.next_action_at = next_action_at
        row.updated_at = now
        await session.flush()
    return int(row.id)


__all__ = [
    "APPLICATION_STATUSES",
    "TERMINAL_STATUSES",
    "ApplicationEventRecord",
    "ApplicationRecord",
    "ArtifactOption",
    "parse_next_action",
    "read_application",
    "read_history",
    "read_tracker",
    "record_application",
    "transition_application",
    "update_application",
]
