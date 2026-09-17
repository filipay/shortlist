"""Listing-event repository — the append-only log and its state projection (D-41).

`listing_events` is **Phase 1's** table (migration `0001_initial_schema.py`), not a
Phase-2 addition. It ships a CHECK constraining `event_type` and two BEFORE triggers
that `RAISE(ABORT, 'listing_events is append-only')` on UPDATE and DELETE. Nothing in
this module writes anything but INSERTs, and there is no migration in this plan.

Why a projection instead of a column
------------------------------------
"Saved" and "hidden" are not columns on `listings`. They are folded from that
listing's events, so the history stays complete and a wrong click is undone by
appending another event rather than by editing one — there is no state row to tamper
with (T-02-36). The projection table this module implements:

===================  =====================  ==========================================
flag                 reads                  rule
===================  =====================  ==========================================
`saved`              `save`, `unsave`       the LATEST of the pair is `save`
`hidden`             `hide`, `unhide`       the LATEST of the pair is `hide`
`shortlisted`        `shortlist`, `unsave`  a `shortlist` was appended and no LATER
                                            `unsave` contradicts it (a shortlist is a
                                            stronger form of save, so an unsave drops
                                            both)
`last_viewed_at`     `view`                 the latest `view`
`viewed`             `view`                 `last_viewed_at is not None`
===================  =====================  ==========================================

A `view` after a `hide` therefore leaves the listing hidden: "I looked at it" is not
"put it back". That is the least obvious rule here and the easiest to get wrong, so a
test pins it. An absent event type leaves its flag at its default (`False`/`None`), and
a listing with no events at all projects to `NO_STATE` — an explicit value rather than
a missing key, so a caller cannot mistake "no events" for "unreadable".

Ordering and cost
-----------------
Latest is `(occurred_at, id)`. The `id` tie-break is load-bearing: two clicks inside
one second share an `occurred_at`, which is the common case, and without the tie-break
the projection would be non-deterministic. `ix_listing_events_listing_occurred` covers
`(listing_id, occurred_at)`, so the page query is index-usable.

`state_for_listings` issues **one** query for a whole page — a per-row query is
forbidden, because it would make the queue N+1 at exactly the point paging matters.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Listing, ListingEvent

#: The six event types, mirroring `ck_listing_events_event_type` from migration 0001
#: exactly. This is the allow-list the route validates against — a second vocabulary
#: is never minted, and widening it is a coordinated migration plus a change here.
EVENT_TYPES: tuple[str, ...] = ("save", "unsave", "hide", "unhide", "shortlist", "view")

#: The event pairs each projected flag reads. Kept beside `EVENT_TYPES` so the
#: projection rule lives in one place, and exported so `queue_repo` can build its
#: filter predicates from the same grouping instead of restating it.
SAVE_EVENTS: tuple[str, ...] = ("save", "unsave")
HIDE_EVENTS: tuple[str, ...] = ("hide", "unhide")


@dataclass(frozen=True)
class ListingState:
    """A listing's current state, projected from its events.

    A frozen value, never an ORM row: callers cannot mutate it back into the
    database, which is the point of projecting rather than storing.
    """

    saved: bool = False
    hidden: bool = False
    shortlisted: bool = False
    last_viewed_at: datetime | None = None

    @property
    def viewed(self) -> bool:
        return self.last_viewed_at is not None


#: The explicit "this listing has no events" value. A distinct object rather than an
#: empty mapping key, so `state_for_listings` can return an entry for every requested
#: id without inventing a second sentinel.
NO_STATE = ListingState()


def _naive(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; normalise before comparing or sorting."""
    return value.replace(tzinfo=None) if value.tzinfo else value


def _sort_key(event: ListingEvent) -> tuple[datetime, int]:
    """`(occurred_at, id)` — the projection's total order.

    `occurred_at` is NOT NULL, so the fallback is unreachable; it exists so the key is
    total without an `assert` in a hot path.
    """
    moment = event.occurred_at
    stamped = _naive(moment) if moment is not None else datetime(1970, 1, 1)
    return (stamped, int(event.id))


def _fold_events(events: Iterable[ListingEvent]) -> ListingState:
    """Fold ONE listing's events into its current state.

    The single shared fold: `state_for_listings` and `latest_state` both go through it,
    so the page projection and the single-listing projection cannot drift apart.
    Events may arrive in any order — they are sorted here.
    """
    saved = False
    hidden = False
    shortlisted = False
    last_viewed_at: datetime | None = None

    for event in sorted(events, key=_sort_key):
        kind = event.event_type
        if kind == "save":
            saved = True
        elif kind == "unsave":
            saved = False
            shortlisted = False
        elif kind == "hide":
            hidden = True
        elif kind == "unhide":
            hidden = False
        elif kind == "shortlist":
            shortlisted = True
        elif kind == "view":
            last_viewed_at = event.occurred_at
        # An unrecognised kind is IGNORED rather than fatal: a row written before a
        # vocabulary change must not break a page read. The CHECK makes it unreachable
        # in practice, and `EVENT_TYPES` is the allow-list for writes.

    return ListingState(
        saved=saved,
        hidden=hidden,
        shortlisted=shortlisted,
        last_viewed_at=last_viewed_at,
    )


async def append_event(
    session: AsyncSession,
    *,
    listing_id: int,
    event_type: str,
    now: datetime,
    run_id: int | None = None,
    context: Mapping[str, Any] | None = None,
) -> ListingEvent:
    """Append exactly one event. The only write this module performs, and it is INSERT.

    `now` is supplied by the caller and stored as-is, so the route can pin the clock in
    a test — and so a caller-supplied `occurred_at` (which the route never accepts) can
    never forge an event's time.

    `context_json` carries small MACHINE facts only (which surface the action came
    from, for instance) — never listing text, never anything a board sent us.

    The insert is wrapped in a SAVEPOINT as `source_repo` does: a failure here must not
    poison the caller's outer transaction. There is deliberately no update and no
    delete function in this module, and the Phase-1 triggers would refuse one anyway.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(
            f"unknown event_type {event_type!r}; expected one of {list(EVENT_TYPES)}"
        )

    event = ListingEvent(
        listing_id=int(listing_id),
        event_type=event_type,
        occurred_at=now,
        context_json=dict(context) if context else None,
        run_id=run_id,
    )
    async with session.begin_nested():
        session.add(event)
        await session.flush()
    return event


async def hide_listings(
    session: AsyncSession,
    *,
    listing_ids: Sequence[int],
    occurred_at: datetime,
) -> int:
    """Append one `hide` event per listing. Returns how many were appended.

    Reuses the existing `hide` event rather than minting a `dismiss` type: the
    projected `hidden` flag and the per-listing `Unhide` control already work, and a
    seventh event type would need a migration to widen
    `ck_listing_events_event_type`. The accepted cost is that a bulk dismissal is
    indistinguishable in the audit trail from hiding each listing by hand.

    One event per listing, so the log stays per-listing and `Unhide` can reverse a
    single row. The insert goes through `append_event`, so the SAVEPOINT, the
    allow-list check and the `occurred_at` contract all apply unchanged.
    """
    ids = sorted({int(listing_id) for listing_id in listing_ids})
    for listing_id in ids:
        await append_event(
            session, listing_id=listing_id, event_type="hide", now=occurred_at
        )
    return len(ids)


async def state_for_listings(
    session: AsyncSession, *, listing_ids: Iterable[int]
) -> dict[int, ListingState]:
    """Current projected state for a page of listings, in **one** query.

    Cost is one `SELECT` for the whole page no matter how many ids are asked for; a
    per-row query is forbidden, because the queue would become N+1 exactly where paging
    matters. `ix_listing_events_listing_occurred` keeps the read index-usable and the
    fold happens in Python, where the projection rules live.

    **Every requested id appears in the returned mapping**, `NO_STATE` when that listing
    has no events, so a caller can never confuse "no events" with "missing from the
    result". An empty id list returns `{}` and issues no query at all.
    """
    ids = sorted({int(listing_id) for listing_id in (listing_ids or ())})
    if not ids:
        return {}

    events = (
        (
            await session.execute(
                select(ListingEvent)
                .where(ListingEvent.listing_id.in_(ids))
                .order_by(
                    ListingEvent.listing_id, ListingEvent.occurred_at, ListingEvent.id
                )
            )
        )
        .scalars()
        .all()
    )

    grouped: dict[int, list[ListingEvent]] = {listing_id: [] for listing_id in ids}
    for event in events:
        grouped[int(event.listing_id)].append(event)

    return {listing_id: _fold_events(rows) for listing_id, rows in grouped.items()}


async def latest_state(session: AsyncSession, *, listing_id: int) -> ListingState:
    """One listing's projected state — the convenience the POST route swaps a row with.

    Deliberately routed through `state_for_listings` (one id) so there is exactly one
    fold and one ordering in the codebase.
    """
    return (await state_for_listings(session, listing_ids=[listing_id]))[int(listing_id)]


def latest_event_type_in(event_types: Sequence[str]) -> ColumnElement[str]:
    """The listing's latest event type **restricted to** `event_types`, or `''`.

    The restriction is the whole point: an unrestricted "latest event" would make a
    `view` after a `save` look unsaved, and a `view` after a `hide` look visible. This
    is the SQL twin of `_fold_events`' per-flag rule, expressed once here so
    `queue_repo`'s filters cannot drift from the projection.

    `coalesce` is required: `NULL != 'hide'` is NULL in SQL, and a WHERE clause that
    evaluates to NULL drops the row — so a listing with no events of the group would
    silently vanish from the queue.
    """
    return func.coalesce(
        select(ListingEvent.event_type)
        .where(
            ListingEvent.listing_id == Listing.id,
            ListingEvent.event_type.in_(tuple(event_types)),
        )
        .order_by(ListingEvent.occurred_at.desc(), ListingEvent.id.desc())
        .limit(1)
        .scalar_subquery(),
        "",
    )


def saved_predicate() -> ColumnElement[bool]:
    """`Saved` filter: the latest of `save`/`unsave` is `save`."""
    return latest_event_type_in(SAVE_EVENTS) == "save"


def hidden_predicate() -> ColumnElement[bool]:
    """`Hidden` filter: the latest of `hide`/`unhide` is `hide`.

    Negated by `queue_repo` for the default view. A listing with no events projects to
    `''`, so it is visible — the "no events" case is explicitly not hidden.
    """
    return latest_event_type_in(HIDE_EVENTS) == "hide"


__all__ = [
    "EVENT_TYPES",
    "HIDE_EVENTS",
    "NO_STATE",
    "SAVE_EVENTS",
    "ListingState",
    "append_event",
    "hidden_predicate",
    "hide_listings",
    "latest_event_type_in",
    "latest_state",
    "saved_predicate",
    "state_for_listings",
]
