"""Queue repository — the ONLY place the queue's SQL lives.

**Bound parameters only.** User search text is never interpolated into SQL: it is
transformed by `app.domain.search_query.build_match_expression` (pure, tested
against the real parser) and handed to `MATCH` as the bound parameter
`:match_expression`. There is no f-string anywhere near the FTS clause.

**Every ordering ends with a unique tie-break.** `bm25()` alone is not
deterministic — two rows with an identical score came back in different orders from
two equivalent queries (RESEARCH §Q3, Finding 1). The FTS branch therefore orders
`score, listings.id DESC` and the no-query branch keeps Phase 1's
`first_seen_at DESC, id DESC`, so two identical requests return the same page.

**Postgres substitution.** On Postgres the FTS5 virtual table becomes a `tsvector`
column with a GIN index, `MATCH` becomes `@@` with `to_tsquery`/`plainto_tsquery`,
and `bm25()` becomes `ts_rank_cd`. `build_match_expression()` is FTS5-specific: its
per-token quoting is replaced by `plainto_tsquery`'s own tokenisation. That is
exactly why the transform and the `MATCH` clause sit behind this module rather than
in a route — the swap is one module, not a scatter of call sites.

**Paging.** `LIMIT`/`OFFSET` with `total` from a count query over the same predicate
set; `has_more` is `offset + len(rows) < total`. Keyset paging on `(score, id)` /
`(first_seen_at, id)` is the documented upgrade path, not needed for one person's
queue. Any predicate change resets `offset` to 0 (see `QueueQuery.query_string`).

**Semantics of an exclusion.** `listing_exclusions` is a per-run observation (D-36).
A listing excluded by an *older* run but not by the latest is **not** excluded: the
default view shows it again, and the `Show excluded` toggle shows the latest run's
reason only. That is what makes retuning a rule bring listings back with no
deletion.

**Semantics of `scope_search_id`.** There is deliberately no listing-to-search link
(the A4 union scope), so "scope" is expressed through the rules that produced the
exclusions: a listing is in scope when it has **no exclusion at all**, or when at
least one of its exclusions was produced by one of the scoped search's rules. A
listing excluded only by another search's rules is out of scope. This is coarse by
construction — it is the honest consequence of the union scope, and plan 02-08's
criteria UI can rely on it without inventing a link column.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy import (
    ColumnElement,
    Integer,
    cast,
    column,
    exists,
    func,
    literal_column,
    or_,
    select,
    table,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select

from app.db.models import (
    FilterRule,
    Listing,
    ListingDupe,
    ListingExclusion,
    ListingSource,
    Run,
)
from app.db.repositories import event_repo
from app.db.repositories.dupe_repo import merge_summary_for_listings
from app.db.repositories.exclusion_repo import (
    excluded_counts_for_run,
    rule_counts_for_listings,
)
from app.domain.search_query import build_match_expression

#: Fallback page size when a caller passes none. The route always passes
#: `Settings.queue_page_size`, so this is a defensive default, never the live knob.
PAGE_LIMIT_DEFAULT = 25

#: BM25 per-column weights, in the FTS column order `(title, company_norm,
#: description)`: a title hit outranks a company hit which outranks a description
#: hit, so the top of the queue is where the *name* matched. These are ranking
#: heuristics, not an operating envelope — they are deliberately not `Settings`
#: knobs (the distinctive-literal scan covers `app/pipeline` and `app/probe`).
BM25_TITLE_WEIGHT = 10.0
BM25_COMPANY_WEIGHT = 5.0
BM25_DESCRIPTION_WEIGHT = 1.0

#: The `listing_fts` virtual table as a Core clause. It is external-content
#: (`content='listings'`), so `rowid` joins to `listings.id`. A `table()` clause
#: rather than an ORM entity because the FTS5 module has no SQLAlchemy mapper, and
#: `literal_column("listing_fts")` gives `bm25()` the bare table name it requires.
_LISTING_FTS = table(
    "listing_fts",
    column("rowid"),
    column("title"),
    column("company_norm"),
    column("description"),
)
_BM25 = func.bm25(
    literal_column("listing_fts"),
    BM25_TITLE_WEIGHT,
    BM25_COMPANY_WEIGHT,
    BM25_DESCRIPTION_WEIGHT,
).label("score")

#: The only raw-SQL fragment in `app/`: FTS5's `MATCH` operator cannot be expressed
#: through the ORM, and the expression is a **bound parameter**.
_MATCH = text("listing_fts MATCH :match_expression")


@dataclass(frozen=True)
class QueueQuery:
    """The queue's filters, as data. Built by the route from the query string."""

    q: str | None = None
    excluded: bool = False
    hidden: bool = False
    saved: bool = False
    scope_search_id: int | None = None
    offset: int = 0
    limit: int = PAGE_LIMIT_DEFAULT

    def query_string(self, *, offset: int | None = None) -> str:
        """The predicate set as a URL query string, optionally with an `offset`.

        A predicate change is emitted with no `offset`, which is the reset: page N
        of a *different* filtered set is meaningless, so the toggle links restart at
        the first page and only the Load-more control passes the current offset on.
        """
        params: dict[str, str] = {}
        if self.q:
            params["q"] = self.q
        if self.excluded:
            params["excluded"] = "1"
        if self.hidden:
            params["hidden"] = "1"
        if self.saved:
            params["saved"] = "1"
        if self.scope_search_id is not None:
            params["scope"] = str(self.scope_search_id)
        if offset:
            params["offset"] = str(int(offset))
        return urlencode(params)


@dataclass(frozen=True)
class QueueRule:
    """One rule that fired against a listing, as the row's chip renders it."""

    rule_id: str
    kind: str
    count: int


@dataclass(frozen=True)
class QueueRow:
    """One queue row, fully resolved: nothing is computed in the template."""

    id: int
    title: str
    company: str
    location: str
    sources: tuple[str, ...]
    posted: str
    first_seen: str
    is_new: bool
    is_stale: bool
    merged_from: int
    #: Projected from `listing_events` (plan 02-09), never from a column.
    saved: bool = False
    hidden: bool = False
    rules: tuple[QueueRule, ...] = ()


@dataclass(frozen=True)
class QueuePage:
    """One rendered page of the queue plus everything the fragment needs."""

    rows: tuple[QueueRow, ...]
    total: int
    offset: int
    limit: int
    has_more: bool
    query: QueueQuery
    #: Per-rule firing counts for the latest run, for the toggle's chip numbers.
    rule_counts: Mapping[str, int] = field(default_factory=dict)

    @property
    def next_offset(self) -> int:
        return self.offset + len(self.rows)


# --- predicates ---------------------------------------------------------------


def _not_absorbed_twin() -> ColumnElement[bool]:
    """A standing merge hides its absorbed twin; a revert un-hides it.

    This is the queue's whole visibility rule for merges: there is no `hidden`
    column and no `listing_events` row for a merge, so `reverted_at` being NULL is
    what keeps the twin out — and clearing it is what brings the twin back.
    """
    return ~exists(
        select(ListingDupe.id).where(
            ListingDupe.dup_listing_id == Listing.id,
            ListingDupe.reverted_at.is_(None),
        )
    )


def _latest_run_id() -> Select[int]:
    """The latest run's id, by the repository ordering convention."""
    return select(Run.id).order_by(Run.started_at.desc(), Run.id.desc()).limit(1)


def _excluded_by_latest_run() -> ColumnElement[bool]:
    """True when the listing carries an exclusion row for the latest run.

    A correlated `NOT EXISTS` against the latest run id, so the predicate is
    index-usable (`ix_listing_exclusions_run` covers `run_id`) and no `listings`
    column had to be added.
    """
    return exists(
        select(ListingExclusion.id).where(
            ListingExclusion.listing_id == Listing.id,
            ListingExclusion.run_id == _latest_run_id().scalar_subquery(),
        )
    )


def _in_scope(scope_search_id: int) -> ColumnElement[bool]:
    """The `scope_search_id` semantics documented in the module docstring."""
    scoped = aliased(FilterRule)
    return or_(
        ~exists(select(ListingExclusion.id).where(ListingExclusion.listing_id == Listing.id)),
        exists(
            select(ListingExclusion.id)
            .join(scoped, cast(ListingExclusion.rule_id, Integer) == scoped.id)
            .where(
                ListingExclusion.listing_id == Listing.id,
                scoped.search_id == scope_search_id,
            )
        ),
    )


def _naive(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; normalise both sides of a comparison.

    Without this a tz-aware `now` from the route compared against a naive
    `last_seen_at` raises `TypeError` — the same hazard plan 02-05 hit on the
    watermark, handled the same way.
    """
    if value is None:
        return None
    return value.replace(tzinfo=None) if value.tzinfo else value


def _row_flags(
    row: Listing, *, now: datetime, stale_after_days: int, watermark: datetime | None
) -> tuple[bool, bool]:
    """`(is_new, is_stale)` — two independent badges, never a state machine.

    A newly ingested listing that is already inactive is legitimately both, so
    neither flag suppresses the other.
    """
    first_seen = _naive(row.first_seen_at)
    moment = _naive(now)
    mark = _naive(watermark)
    is_new = mark is None or (first_seen is not None and first_seen > mark)

    cutoff = moment - timedelta(days=int(stale_after_days)) if moment is not None else None
    last_seen = _naive(row.last_seen_at)
    is_stale = (not row.is_active) or (
        cutoff is not None and last_seen is not None and last_seen <= cutoff
    )
    return bool(is_new), bool(is_stale)


# --- the read ------------------------------------------------------------------


async def read_queue(
    session: AsyncSession,
    *,
    query: QueueQuery,
    now: datetime,
    stale_after_days: int,
    watermark: datetime | None,
) -> QueuePage:
    """One page of the queue, fully enriched. Never commits (the caller owns it)."""
    offset = max(0, int(query.offset))
    limit = max(1, int(query.limit or PAGE_LIMIT_DEFAULT))
    expression = build_match_expression(query.q)

    predicates: list[ColumnElement[bool]] = [_not_absorbed_twin()]
    # The save/hide predicates come from `event_repo`, which owns the projection: their
    # rules are `save`/`unsave` and `hide`/`unhide` restricted to the LATEST event of
    # the pair, so a `view` after a `save` cannot make the listing look unsaved. Building
    # them here from a bare "latest event type" was plan 02-07's placeholder and was
    # wrong for exactly that reason.
    #
    # A hide composes with `_not_absorbed_twin` above rather than replacing it: an
    # absorbed twin is out of the queue whether or not anyone also hid it.
    if not query.hidden:
        predicates.append(~event_repo.hidden_predicate())
    if query.saved:
        predicates.append(event_repo.saved_predicate())
    if query.scope_search_id is not None:
        predicates.append(_in_scope(int(query.scope_search_id)))
    if not query.excluded:
        predicates.append(~_excluded_by_latest_run())

    params: dict[str, object] = {}
    if expression is not None:
        # The FTS branch. `select_from` is the virtual table joined to `listings`
        # through `rowid` (external-content); the match expression is BOUND.
        source = _LISTING_FTS.join(Listing, Listing.id == _LISTING_FTS.c.rowid)
        id_stmt = (
            select(Listing.id)
            .select_from(source)
            .where(_MATCH, *predicates)
            .order_by(_BM25, Listing.id.desc())
            .limit(limit)
            .offset(offset)
        )
        count_stmt = select(func.count()).select_from(source).where(_MATCH, *predicates)
        params["match_expression"] = expression
    else:
        # The no-query branch: NO `listing_fts` join at all, and Phase 1's order.
        id_stmt = (
            select(Listing.id)
            .where(*predicates)
            .order_by(Listing.first_seen_at.desc(), Listing.id.desc())
            .limit(limit)
            .offset(offset)
        )
        count_stmt = select(func.count()).select_from(Listing).where(*predicates)

    ids = [int(value) for value in (await session.execute(id_stmt, params)).scalars().all()]
    total = int(await session.scalar(count_stmt, params) or 0)

    rows = await _enrich(
        session,
        ids,
        query=query,
        now=now,
        stale_after_days=stale_after_days,
        watermark=watermark,
    )

    return QueuePage(
        rows=tuple(rows),
        total=total,
        offset=offset,
        limit=limit,
        has_more=(offset + len(rows)) < total,
        query=query,
        rule_counts=await _page_rule_counts(session, query=query),
    )


async def _enrich(
    session: AsyncSession,
    ids: Sequence[int],
    *,
    query: QueueQuery,
    now: datetime,
    stale_after_days: int,
    watermark: datetime | None,
) -> list[QueueRow]:
    """Resolve the page's ids into rows, preserving the SQL's order."""
    if not ids:
        return []

    listings = {
        int(row.id): row
        for row in (
            await session.execute(select(Listing).where(Listing.id.in_(list(ids))))
        )
        .scalars()
        .all()
    }

    grouped: dict[int, list[str]] = {}
    for listing_id, source in (
        await session.execute(
            select(ListingSource.listing_id, ListingSource.source)
            .where(ListingSource.listing_id.in_(list(ids)))
            .order_by(ListingSource.listing_id, ListingSource.source)
        )
    ).all():
        grouped.setdefault(int(listing_id), []).append(str(source))

    # The merge indicator and the firing-rule ids both come from the repositories
    # that own those queries (plans 02-06 and 02-05); neither join is rebuilt here.
    merged_from = await merge_summary_for_listings(session, listing_ids=list(ids))

    # The saved/hidden flags come from the append-only event log, projected in ONE
    # query for the whole page (plan 02-09). No flag is read per row, and no template
    # recomputes them.
    states = await event_repo.state_for_listings(session, listing_ids=list(ids))

    firing: dict[int, list[str]] = {}
    kinds: dict[str, str] = {}
    latest_run_id = await _latest_run_id_value(session)
    if latest_run_id is not None:
        firing = await rule_counts_for_listings(session, run_id=latest_run_id)
        kinds = await _rule_kinds(session, firing.values())
    rule_counts = await _page_rule_counts(session, query=query)

    rows: list[QueueRow] = []
    for listing_id in ids:
        listing = listings.get(listing_id)
        if listing is None:  # pragma: no cover — the id came from this table
            continue
        is_new, is_stale = _row_flags(
            listing, now=now, stale_after_days=stale_after_days, watermark=watermark
        )
        chips: list[QueueRule] = []
        if query.excluded:
            for rule_id in firing.get(listing_id, ()):
                chips.append(
                    QueueRule(
                        rule_id=rule_id,
                        kind=kinds.get(rule_id, "unknown"),
                        count=rule_counts.get(rule_id, 1),
                    )
                )
        state = states.get(listing_id, event_repo.NO_STATE)
        rows.append(
            QueueRow(
                id=listing_id,
                title=listing.title or "",
                company=listing.company_norm or "",
                location=listing.location_raw or "",
                sources=tuple(grouped.get(listing_id, ())),
                posted=listing.posted_at.isoformat() if listing.posted_at else "",
                first_seen=(
                    listing.first_seen_at.isoformat() if listing.first_seen_at else ""
                ),
                is_new=is_new,
                is_stale=is_stale,
                merged_from=int(merged_from.get(listing_id, 0)),
                saved=state.saved,
                hidden=state.hidden,
                rules=tuple(chips),
            )
        )
    return rows


async def read_row(
    session: AsyncSession,
    *,
    listing_id: int,
    query: QueueQuery,
    now: datetime,
    stale_after_days: int,
    watermark: datetime | None,
) -> QueueRow | None:
    """One fully-enriched row, by id.

    The seam plan 02-09's event routes swap back after a save/hide click. It goes
    through the same `_enrich` the page does, so a swapped row cannot render
    differently from the row it replaces — the badges, the merge indicator, the
    exclusion chips and the projected flags all come from one code path.
    """
    rows = await _enrich(
        session,
        [int(listing_id)],
        query=query,
        now=now,
        stale_after_days=stale_after_days,
        watermark=watermark,
    )
    return rows[0] if rows else None


async def _latest_run_id_value(session: AsyncSession) -> int | None:
    value = await session.scalar(_latest_run_id())
    return int(value) if value is not None else None


async def _rule_kinds(session: AsyncSession, rule_ids: Iterable[Iterable[str]]) -> dict[str, str]:
    """`{rule id as string: kind}` for the firing rules on this page.

    Keyed by the **string** form to match `listing_exclusions.rule_id`, which is a
    `String(64)` column — the same rendering `rule_counts_for_listings` returns. A
    keyed-by-int mapping would silently label every chip "unknown".

    Only the id-to-label lookup happens here: the firing-rule SQL itself stays in
    `exclusion_repo.rule_counts_for_listings`, which is what produced the ids.
    """
    numbers = {int(rule_id) for group in rule_ids for rule_id in group if str(rule_id).isdigit()}
    if not numbers:
        return {}
    rows = (
        await session.execute(
            select(FilterRule.id, FilterRule.kind).where(FilterRule.id.in_(sorted(numbers)))
        )
    ).all()
    return {str(int(rule_id)): str(kind or "unknown") for rule_id, kind in rows}


async def _page_rule_counts(session: AsyncSession, *, query: QueueQuery) -> dict[str, int]:
    """Per-rule firing counts for the latest run, for the toggle's chips.

    Grouped over the run, not summed per row, so "excluded by rule X (N)" states how
    many listings the run actually rejected rather than how many are on this page.
    """
    latest_run_id = await _latest_run_id_value(session)
    if latest_run_id is None:
        return {}
    return await excluded_counts_for_run(session, run_id=latest_run_id)


__all__ = [
    "BM25_COMPANY_WEIGHT",
    "BM25_DESCRIPTION_WEIGHT",
    "BM25_TITLE_WEIGHT",
    "PAGE_LIMIT_DEFAULT",
    "QueuePage",
    "QueueQuery",
    "QueueRow",
    "QueueRule",
    "read_queue",
    "read_row",
]
