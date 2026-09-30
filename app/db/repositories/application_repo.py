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
from urllib.parse import urlencode

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

#: Fallback tracker page size when a caller passes none. The route always passes
#: `Settings.queue_page_size` (the tracker pages like the queue), so this is a
#: defensive default, never the live knob.
TRACKER_PAGE_LIMIT_DEFAULT = 25


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


@dataclass(frozen=True)
class TrackerQuery:
    """The tracker's filters, as data. Built by the route from the query string.

    Mirrors `queue_repo.QueueQuery`: a predicate change is emitted with no `offset`
    (the reset), and only the pager carries one.
    """

    stage: str | None = None
    q: str | None = None
    #: `"needs_action"` (D-133) or `None`. Validated against the allow-list before SQL.
    view: str | None = None
    offset: int = 0
    limit: int = TRACKER_PAGE_LIMIT_DEFAULT

    def query_string(self, *, offset: int | None = None) -> str:
        """The predicate set as a URL query string, optionally with an `offset`.

        A predicate change carries no `offset`, so page N of a *different* filtered
        set can never be requested; only the pager passes the current offset on.
        """
        params: dict[str, str] = {}
        if self.q:
            params["q"] = self.q
        if self.stage:
            params["stage"] = self.stage
        if self.view:
            params["view"] = self.view
        if offset:
            params["offset"] = str(int(offset))
        return urlencode(params)


@dataclass(frozen=True)
class TrackerPage:
    """One rendered page of the tracker plus everything the fragment needs.

    Mirrors `queue_repo.QueuePage`: the four accessor properties are pure
    derivations of `offset`/`limit`/`total`, and the `max(1, ...)` guards exist only
    so a hand-constructed instance cannot divide by zero.
    """

    rows: tuple[ApplicationRecord, ...]
    total: int
    offset: int
    limit: int
    has_more: bool
    query: TrackerQuery

    @property
    def next_offset(self) -> int:
        return self.offset + len(self.rows)

    @property
    def has_prev(self) -> bool:
        """True when a previous page exists (the current page is not the first)."""
        return self.offset > 0

    @property
    def prev_offset(self) -> int:
        """The offset of the previous page, never negative; 0 when there is none."""
        return max(0, self.offset - self.limit)

    @property
    def page_index(self) -> int:
        """The 1-based index of the page currently shown."""
        return self.offset // max(1, self.limit) + 1

    @property
    def page_count(self) -> int:
        """The number of pages at this page size, never below 1."""
        return max(1, (self.total + max(1, self.limit) - 1) // max(1, self.limit))


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


def _row_matches(row: Application, title: str | None, company: str | None, needle: str) -> bool:
    """True when the casefolded `needle` is a substring of title, company or notes.

    `needle` is already casefolded by the caller. `None` fields degrade to empty
    strings, so a row with no company or notes still matches on its title.
    """
    return any(
        needle in field.casefold() for field in (title or "", company or "", row.notes or "")
    )


async def read_tracker(
    session: AsyncSession,
    *,
    stage: str | None = None,
    q: str | None = None,
    view: str | None = None,
    offset: int = 0,
    limit: int = TRACKER_PAGE_LIMIT_DEFAULT,
    now: datetime | None = None,
) -> TrackerPage:
    """One page of the tracker, joined to its listing/company, filtered and sliced.

    `stage` (D-133) and `view` are validated against their allow-lists **before any
    SQL** — an unknown value is a `ValueError`, never a silently-empty result (T-07-04-01).
    `q` is a bounded Python-side casefold substring over `listings.title`,
    `companies.name` and `applications.notes` (T-07-04-01): the whole row set is
    swept, which is the accepted pattern at 1-5 users. Default order is newest-first;
    `view="needs_action"` orders `(next_action_at IS NULL), next_action_at ASC` with a
    deterministic `id DESC` tie-break and excludes `TERMINAL_STATUSES` (D-133).
    """
    if stage is not None and stage not in APPLICATION_STATUSES:
        raise ValueError(
            f"unknown stage {stage!r}; expected one of {list(APPLICATION_STATUSES)}"
        )
    if view not in (None, "needs_action"):
        raise ValueError(f"unknown view {view!r}; expected 'needs_action' or None")

    offset = max(0, int(offset))
    limit = max(1, int(limit or TRACKER_PAGE_LIMIT_DEFAULT))

    stmt = (
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
    )
    if stage is not None:
        stmt = stmt.where(Application.status == stage)
    if view == "needs_action":
        # SQLite yields 0 for a non-null date, so dated rows sort first ascending
        # (oldest/overdue first); NULL dates sort last.
        stmt = stmt.where(Application.status.not_in(TERMINAL_STATUSES)).order_by(
            Application.next_action_at.is_(None),
            Application.next_action_at.asc(),
            Application.id.desc(),
        )
    else:
        stmt = stmt.order_by(Application.updated_at.desc(), Application.id.desc())

    rows = (await session.execute(stmt)).all()
    needle = q.casefold() if q else None
    if needle is not None:
        # ponytail: bounded Python scan accepted at 1-5 users (tens of rows); the
        # upgrade path is an FTS index over listings(title, company) + applications(notes)
        # if the tracker ever grows past a few hundred.
        rows = [row for row in rows if _row_matches(row[0], row[1], row[2], needle)]

    total = len(rows)
    page_rows = rows[offset : offset + limit]
    options = await _ok_artifacts_by_listing(
        session, {int(row.listing_id) for row, *_ in page_rows}
    )
    records = tuple(
        _record(
            row=row,
            listing_title=title,
            company=company,
            event_count=count,
            now=now,
            ok_artifacts=options.get(int(row.listing_id), ()),
        )
        for row, title, company, count in page_rows
    )
    return TrackerPage(
        rows=records,
        total=total,
        offset=offset,
        limit=limit,
        has_more=(offset + len(records)) < total,
        query=TrackerQuery(stage=stage, q=q, view=view, offset=offset, limit=limit),
    )


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
    "TRACKER_PAGE_LIMIT_DEFAULT",
    "ApplicationEventRecord",
    "ApplicationRecord",
    "ArtifactOption",
    "TrackerPage",
    "TrackerQuery",
    "parse_next_action",
    "read_application",
    "read_history",
    "read_tracker",
    "record_application",
    "transition_application",
    "update_application",
]
