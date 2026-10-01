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

**The score ordering is a Python-side sort over a bounded scan** (D-97 / D-100).
The default `sort="score"` selects every matching id ordered `first_seen_at DESC, id
DESC`, bounded by `SCORE_SORT_SCAN_LIMIT`, enriches them, computes each row's
read-time total with `rubric.weighted_total` under the weights CURRENTLY in force,
applies the `min_score` threshold, sorts by total descending with unscored rows last
and a deterministic `(confidence tier, id DESC)` tie-break, and slices the page. On
this path `total` is the count of rows that SURVIVE THE THRESHOLD (unscored rows are
always kept and always counted, D-98), not a SQL `COUNT(*)`. The `sort="recent"` path
is today's SQL `LIMIT`/`OFFSET` code, unchanged, so the previous ordering is one query
parameter away. The MATCH predicate is a FILTER and the sort is an ORDERING: with a
query set, `sort="score"` still selects through the bound `:match_expression` and then
orders the matched set by the read-time total, so the score ordering wins over `bm25`
without removing it from the FTS branch.

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
from urllib.parse import urlencode, urlsplit

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
    Company,
    FilterRule,
    Listing,
    ListingDupe,
    ListingExclusion,
    ListingSource,
    Run,
)
from app.db.repositories import event_repo, ranking_config_repo, score_repo
from app.db.repositories.dupe_repo import merge_summary_for_listings
from app.db.repositories.exclusion_repo import (
    excluded_counts_for_run,
    rule_counts_for_listings,
)
from app.domain import rubric
from app.domain.listing import canonical_url
from app.domain.search_query import build_match_expression

#: Fallback page size when a caller passes none. The route always passes
#: `Settings.queue_page_size`, so this is a defensive default, never the live knob.
PAGE_LIMIT_DEFAULT = 25

#: The score path's bounded scan (T-05-20). The read-time total cannot be sorted in
#: SQL: the denominator is dynamic (absent factors re-normalise, D-85) and the total
#: is derived in Python from the stored sub-scores under the weights in force (D-100),
#: so the ordering is a Python-side sort. To keep that bounded, the score path scans
#: at most this many matching ids before sorting.
#:
#: ponytail: a personal-scale ceiling. If a queue ever approaches it, materialise the
#: read-time total (a column or a SQL expression over a fixed denominator) and sort in
#: SQL — do NOT raise this number and keep scanning.
SCORE_SORT_SCAN_LIMIT = 5000

#: Ordering rank for the score sort's confidence-tier tie-break: a higher tier sorts
#: first among equal totals (D-85 makes the tier the "how much evidence" signal). A
#: row with no tier (unscored) ranks last within its group, but the group itself is
#: already last.
_TIER_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}
_TIER_RANK_UNKNOWN = 3

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
    #: The ordering: `"score"` (D-97's default — the read-time total descending with
    #: unscored listings last) or `"recent"` (the retained `first_seen_at DESC, id
    #: DESC` Phase-1 order). Any other value is treated as `"score"` by the route.
    sort: str = "score"
    #: The view-only minimum-score threshold (D-98). `None` means no threshold; an
    #: unscored listing is ALWAYS kept because its total is `None`, never 0.0.
    min_score: float | None = None

    def query_string(self, *, offset: int | None = None) -> str:
        """The predicate set as a URL query string, optionally with an `offset`.

        A predicate change is emitted with no `offset`, which is the reset: page N
        of a *different* filtered set is meaningless, so the toggle links restart at
        the first page and only the Load-more control passes the current offset on.
        The default sort is omitted from the URL so the common case stays short; a
        non-default sort or a threshold rides along so a swap or a Load-more keeps
        the ordering and the filter the user is looking at.
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
        if self.sort and self.sort != "score":
            params["sort"] = self.sort
        if self.min_score is not None:
            params["min_score"] = f"{float(self.min_score):g}"
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
class SourceLink:
    """One board's provenance for a listing, as the row renders it.

    `url` is the board's own page for this posting (`listing_sources.source_url`).
    `employer_url` is the employer/ATS page (`listing_sources.canonical_source_url`)
    and is populated ONLY when it differs from `url`. That single guard is what makes
    the rendering correct with no source-specific branching: a LinkedIn row renders
    one link, an Indeed row renders the board page plus the employer's own posting.
    """

    source: str
    url: str
    employer_url: str | None = None


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
    #: The posting page (`listings.canonical_url`), or None when the row has none.
    url: str | None = None
    #: One entry per `listing_sources` row, so a merge never hides half its provenance.
    source_links: tuple[SourceLink, ...] = ()
    #: True when the listing's `quality_signals_json` records an instruction-like
    #: finding (§6.3). Read through a tolerant accessor, so a NULL, non-mapping or
    #: malformed value degrades to False rather than breaking the page.
    instruction_like: bool = False
    #: The read-time total under the weights CURRENTLY in force (D-100), or `None`
    #: when the listing has never been scored. `None` and a real `0.0` are distinct:
    #: an unscored listing must never read as a genuine zero score.
    total_score: float | None = None
    #: The D-85 confidence tier of the newest score row, or `None` when unscored.
    confidence_tier: str | None = None
    #: The newest score row's per-factor sub-scores, in `rubric.FACTORS` order.
    factor_scores: tuple[tuple[str, float], ...] = ()


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

    # The four accessors below are pure derivations of `offset`/`limit`/`total`, which
    # `read_queue` always sets (and clamps `limit` at >= 1). The `max(1, ...)` guards
    # exist only so a hand-constructed instance cannot raise `ZeroDivisionError` or
    # report a 0-page queue — they never change a value `read_queue` produces.
    @property
    def has_prev(self) -> bool:
        """True when a previous page exists (the current page is not the first)."""
        return self.offset > 0

    @property
    def prev_offset(self) -> int:
        """The offset of the previous page, never negative; 0 when there is no previous page."""
        return max(0, self.offset - self.limit)

    @property
    def page_index(self) -> int:
        """The 1-based index of the page currently shown."""
        return self.offset // max(1, self.limit) + 1

    @property
    def page_count(self) -> int:
        """The number of pages at this page size, never below 1 (the current page always exists); total==0 reads as one page."""
        return max(1, (self.total + max(1, self.limit) - 1) // max(1, self.limit))


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


def _score_sort_key(row: QueueRow) -> tuple[int, float, int, int]:
    """The score path's ordering key: total DESC, unscored last, deterministic.

    Unscored rows sort after every scored row (the leading `0`/`1` flag) and are never
    given a synthetic 0.0 (UI-01). Within a group the keys are `-total` (descending),
    the confidence-tier rank (a higher tier first) and finally `-id` (id DESC), so two
    identical requests return the same page.
    """
    tier = _TIER_RANK.get(row.confidence_tier or "", _TIER_RANK_UNKNOWN)
    if row.total_score is None:
        return (1, 0.0, tier, -row.id)
    return (0, -float(row.total_score), tier, -row.id)


async def _sql_page_ids(
    session: AsyncSession,
    *,
    expression: str | None,
    predicates: Sequence[ColumnElement[bool]],
    limit: int,
    offset: int,
) -> tuple[list[int], int]:
    """The `recent` path: today's SQL `LIMIT`/`OFFSET` id selection, unchanged."""
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
    return ids, total


async def _score_candidate_ids(
    session: AsyncSession,
    *,
    expression: str | None,
    predicates: Sequence[ColumnElement[bool]],
) -> list[int]:
    """Every matching id for the score path, newest-first, bounded by the scan limit.

    The MATCH predicate is applied here exactly as the `recent` path applies it: the
    ordering is what differs. `first_seen_at DESC, id DESC` is the pre-sort scan order
    (stable and deterministic); `_score_sort_key` re-sorts the enriched rows.
    """
    params: dict[str, object] = {}
    if expression is not None:
        source = _LISTING_FTS.join(Listing, Listing.id == _LISTING_FTS.c.rowid)
        stmt = (
            select(Listing.id)
            .select_from(source)
            .where(_MATCH, *predicates)
            .order_by(Listing.first_seen_at.desc(), Listing.id.desc())
            .limit(SCORE_SORT_SCAN_LIMIT)
        )
        params["match_expression"] = expression
    else:
        stmt = (
            select(Listing.id)
            .where(*predicates)
            .order_by(Listing.first_seen_at.desc(), Listing.id.desc())
            .limit(SCORE_SORT_SCAN_LIMIT)
        )
    return [int(value) for value in (await session.execute(stmt, params)).scalars().all()]


async def read_queue(
    session: AsyncSession,
    *,
    query: QueueQuery,
    now: datetime,
    stale_after_days: int,
    watermark: datetime | None,
) -> QueuePage:
    """One page of the queue, fully enriched. Never commits (the caller owns it).

    `sort="score"` (the default) orders by the read-time total with unscored rows
    last; `sort="recent"` is the retained SQL `first_seen_at DESC, id DESC` path.
    """
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

    rule_counts = await _page_rule_counts(session, query=query)

    if query.sort == "recent":
        ids, total = await _sql_page_ids(
            session,
            expression=expression,
            predicates=predicates,
            limit=limit,
            offset=offset,
        )
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
            rule_counts=rule_counts,
        )

    # The score path (D-97/D-100): the total is computed in Python, so the ordering is
    # a Python-side sort over a bounded scan.
    candidate_ids = await _score_candidate_ids(
        session, expression=expression, predicates=predicates
    )
    enriched = await _enrich(
        session,
        candidate_ids,
        query=query,
        now=now,
        stale_after_days=stale_after_days,
        watermark=watermark,
    )
    if query.min_score is not None:
        # D-98: a view-only threshold. An unscored row (total None) is ALWAYS kept —
        # a listing with no score is not a listing with a low score.
        threshold = float(query.min_score)
        enriched = [
            row
            for row in enriched
            if row.total_score is None or row.total_score >= threshold
        ]
    enriched.sort(key=_score_sort_key)
    total = len(enriched)
    page_rows = enriched[offset : offset + limit]
    return QueuePage(
        rows=tuple(page_rows),
        total=total,
        offset=offset,
        limit=limit,
        has_more=(offset + len(page_rows)) < total,
        query=query,
        rule_counts=rule_counts,
    )


def _instruction_like(value: object) -> bool:
    """`quality_signals_json["instruction_like"]`, or False when unusable.

    Total by design: the column is nullable, a half-written row is possible, and a
    queue page must render either way. Only the boolean flag is read — never a
    count, and never any prose (there is none in the payload to begin with).
    """
    if not isinstance(value, Mapping):
        return False
    return bool(value.get("instruction_like", False))


def http_url(value: str | None) -> str:
    """Return `value` only when it is an http(s) URL, else "".

    `listing_sources.source_url` is stored raw and `canonical_url` is not a scheme
    gate, so a non-web scheme must render as no link at all: the row falls back to
    a plain, unlinked title. Jinja autoescaping does not block `javascript:`.

    The ORIGINAL string is returned unchanged when allowed — this is a gate, not a
    normalisation, so tracking parameters and casing survive exactly as stored.
    """
    if urlsplit(value or "").scheme.casefold() not in {"http", "https"}:
        return ""
    return value or ""


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

    listing_rows = (
        await session.execute(
            select(Listing, Company)
            .outerjoin(Company, Listing.company_id == Company.id)
            .where(Listing.id.in_(list(ids)))
        )
    ).all()
    listings: dict[int, Listing] = {}
    companies: dict[int, Company | None] = {}
    for listing, company in listing_rows:
        listings[int(listing.id)] = listing
        companies[int(listing.id)] = company

    grouped: dict[int, list[SourceLink]] = {}
    for listing_id, source, source_url, canonical_source_url in (
        await session.execute(
            select(
                ListingSource.listing_id,
                ListingSource.source,
                ListingSource.source_url,
                ListingSource.canonical_source_url,
            )
            .where(ListingSource.listing_id.in_(list(ids)))
            .order_by(ListingSource.listing_id, ListingSource.source)
        )
    ).all():
        # Both URLs are gated to http(s) before the comparison below. An empty
        # board URL therefore cannot suppress a valid employer link: `canonical_url("")`
        # is `""`, which still differs from the employer page.
        board_url = http_url(source_url)
        employer_url = http_url(canonical_source_url)
        # `source_url` is stored raw while `canonical_source_url` is the normalised
        # `canonical_url(source_url, direct_url)`, so compare the board page's
        # normalised form against it: raw-vs-normalised would call one page two
        # whenever the raw URL carries a tracking param or fragment. `canonical_url`
        # is idempotent, so this is a like-for-like comparison.
        employer_page = (
            employer_url
            if employer_url and canonical_url(board_url) != employer_url
            else None
        )
        grouped.setdefault(int(listing_id), []).append(
            SourceLink(
                source=str(source),
                url=board_url,
                employer_url=employer_page,
            )
        )

    # The merge indicator and the firing-rule ids both come from the repositories
    # that own those queries (plans 02-06 and 02-05); neither join is rebuilt here.
    merged_from = await merge_summary_for_listings(session, listing_ids=list(ids))

    # The saved/hidden flags come from the append-only event log, projected in ONE
    # query for the whole page (plan 02-09). No flag is read per row, and no template
    # recomputes them.
    states = await event_repo.state_for_listings(session, listing_ids=list(ids))

    # The read-time total (D-100): the NEWEST score row per listing combined with the
    # weights CURRENTLY in force — the stored `scores.total_score` is an audit
    # snapshot, never the sort source. The weights document is read ONCE per page,
    # never once per row.
    newest_scores = await score_repo.latest_for_listings(session, list(ids))
    weights = await ranking_config_repo.read_weights(session)

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
        company = companies.get(listing_id)
        links = tuple(grouped.get(listing_id, ()))
        score = newest_scores.get(listing_id)
        factor_scores = score.factor_scores if score is not None else ()
        total_score = (
            rubric.weighted_total(dict(factor_scores), weights)
            if score is not None
            else None
        )
        rows.append(
            QueueRow(
                id=listing_id,
                title=listing.title or "",
                company=(company.name if company else None) or listing.company_norm or "",
                location=listing.location_raw or "",
                sources=tuple(link.source for link in links),
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
                url=http_url(listing.canonical_url) or None,
                source_links=links,
                instruction_like=_instruction_like(listing.quality_signals_json),
                total_score=total_score,
                confidence_tier=score.confidence_tier if score is not None else None,
                factor_scores=factor_scores,
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
    "SCORE_SORT_SCAN_LIMIT",
    "QueuePage",
    "QueueQuery",
    "QueueRow",
    "QueueRule",
    "SourceLink",
    "http_url",
    "read_queue",
    "read_row",
]
