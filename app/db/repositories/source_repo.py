"""Source repository — the probe write path and the per-source health read model.

The pipeline owns the ingest side of the `sources` table. What Phase 1 needs from
it beyond that is small and split by concern: which sources are enabled and the
write path for a probe result (`last_probe_at`, `health`), then the read model
SRC-07 / D-13 requires the UI strip to render — last success, listings returned
and per-field fill-rate. `ensure_registered_sources` seeds the enabled set from the
adapter registry, so a freshly migrated database is usable without hand-inserted
rows.

Nothing here imports the live probe orchestration (`app.probe.probe`): the status
vocabulary is validated locally and enforced by the `ck_sources_health` CHECK
constraint, and a health read must never put a request on a board (D-156). The
*pure* survival instruments are imported — `classify_block_vs_parse` and the
`BoardEvidence` types are functions over rows with no I/O — because the recorded
stop signals and the promotion evidence are read from the same ledger this module
already queries.

**Fill-rate is computed over normalised records** (RESEARCH §S2), so an
all-blank description counts as empty rather than as a non-null string. The schema
has no direct listing-to-run link, so a run's records are the source's rows whose
`last_seen_at` falls at or after that run's `started_at` — the pipeline stamps
every row it touches with the run's own clock.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Listing, ListingSource, Run, Source, SourceRequestLog
from app.probe.survival import (
    BoardEvidence,
    SignalResult,
    baseline_from_row,
    classify_block_vs_parse,
)
from app.sources import registry

#: Mirrors `ck_sources_health` on the `sources` table.
VALID_HEALTH: frozenset[str] = frozenset({"ok", "degraded", "unreachable"})

#: How far back the read model looks for per-source history.
RECENT_RUN_LIMIT = 20

#: The badge a recorded S5 classification projects onto, drawn from `VALID_HEALTH`
#: only — a fetch-side (or transport-error) request degrades the source; a clean
#: one keeps it. Nothing new is added to the vocabulary (T-08-21).
CLASSIFICATION_HEALTH: dict[str, str] = {"pass": "ok", "warn": "degraded"}

#: The prefix `classify_response` writes for a raised transport failure. Anchored
#: (never a substring scan) because it is emitted by exactly one function.
TRANSPORT_ERROR_PREFIX = "fetch-side: transport error"

#: The prefix `classify_response` writes around a recorded stop signal.
STOP_SIGNAL_PREFIX = "fetch-side: stop signal '"

#: `(label, listings attribute, listing_sources attribute)` for the S2 fill-rate.
#: `salary_min`/`salary_max` are reported but never *targeted*: JobSpy's
#: description-salary extraction is USA-only, so an Irish search is structurally
#: low here (RESEARCH §S2) and only deltas are meaningful.
FILL_RATE_FIELDS: tuple[tuple[str, str, str | None], ...] = (
    ("title", "title", None),
    ("company_name", "company_norm", None),
    ("location_raw", "location_raw", None),
    ("description", "description", None),
    ("posted_at", "posted_at", None),
    ("salary_min", "salary_min", None),
    ("salary_max", "salary_max", None),
    ("source_listing_id", "source_listing_id", "source_listing_id"),
    ("direct_url", "direct_url", "direct_url"),
)


@dataclass(frozen=True)
class SourceHealth:
    """One row of the per-source health strip (SRC-07 / D-13)."""

    name: str
    enabled: bool
    health: str | None
    last_probe_at: datetime | None
    last_success_at: datetime | None
    listings_returned: int
    field_fill_rate: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceHealthDetail(SourceHealth):
    """A `SourceHealth` row plus the recorded stop-signal classification (D-156).

    `classification` is the S5 side of the newest recorded request in the ledger
    window (`fetch-side` / `parse-side`) and `stop_signal` is the signal that was
    recorded with it, both carried for the operator. The inherited `health` value
    is the projection of that classification onto the shared vocabulary, so the
    page's badge reflects what the pipeline actually recorded rather than the
    last live probe.
    """

    classification: str | None = None
    stop_signal: str | None = None


def _populated(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _fill_rate(rows: Sequence[tuple[Listing, ListingSource]]) -> dict[str, float]:
    """Populated-over-total per field, over normalised records."""
    total = len(rows)
    if total == 0:
        return {}

    rates: dict[str, float] = {}
    for label, listing_attr, source_attr in FILL_RATE_FIELDS:
        populated = 0
        for listing, listing_source in rows:
            value = (
                getattr(listing_source, source_attr)
                if source_attr is not None
                else getattr(listing, listing_attr)
            )
            if _populated(value):
                populated += 1
        rates[label] = populated / total
    return rates


def _source_entry(run: Run, name: str) -> dict[str, Any] | None:
    counts = run.source_counts_json
    if not isinstance(counts, dict):
        return None
    entry = counts.get(name)
    return entry if isinstance(entry, dict) else None


def _latest_run_for(runs: Sequence[Run], name: str) -> Run | None:
    for run in runs:
        if _source_entry(run, name) is not None:
            return run
    return None


def _last_success_run(runs: Sequence[Run], name: str) -> Run | None:
    """The most recent run in which *this source* reported `ok`."""
    for run in runs:
        entry = _source_entry(run, name)
        if entry is not None and entry.get("status") == "ok":
            return run
    return None


def _recorded_stop_signal(note: Any) -> str | None:
    """The stop signal `classify_response` wrote into a ledger row's note.

    Anchored on the exact prefix that ONE function emits, so free text cannot
    satisfy it by accident (CONVENTIONS rule 1). Anything else — including a
    parse-side or clean note — is `None`.
    """
    if not isinstance(note, str) or not note.startswith(STOP_SIGNAL_PREFIX):
        return None
    return note.removeprefix(STOP_SIGNAL_PREFIX).split("'", 1)[0] or None


def _classify_ledger_row(row: SourceRequestLog) -> SignalResult:
    """S5 for one recorded request, from the row's own columns.

    Three inputs beyond the stop signal are reconstructed so the pure classifier
    reproduces what ingest recorded: a transport error is its own fetch-side
    branch, the stop signal is read off the note's emitted prefix, and `ok`
    separates a request that returned rows from one that returned none.
    """
    note = row.note if isinstance(row.note, str) else ""
    return classify_block_vs_parse(
        status_code=row.status_code,
        parsed_items=1 if row.ok else 0,
        stop_signal=_recorded_stop_signal(note),
        status="error" if note.startswith(TRANSPORT_ERROR_PREFIX) else None,
    )


def _derived_health(stored: str | None, classification: SignalResult | None) -> str | None:
    """Project an S5 classification onto the shared health vocabulary.

    No recorded request leaves the stored value untouched — a source that has
    never been fetched is never a failure. A fetch-side request degrades the
    badge; a clean one keeps the stored value, defaulting to `ok`.
    """
    if classification is None:
        return stored
    if classification.status == "warn":
        return CLASSIFICATION_HEALTH["warn"]
    return stored or CLASSIFICATION_HEALTH["pass"]


async def enabled_source_names(session: AsyncSession) -> list[str]:
    """Names of the enabled `sources` rows, deterministically ordered."""
    rows = (
        await session.execute(
            select(Source.name).where(Source.enabled.is_(True)).order_by(Source.name)
        )
    ).scalars().all()
    return list(rows)


def _display_name(name: str) -> str:
    """A deterministic human label for a registered adapter.

    `JobSource` exposes only `name` and `capabilities`, so there is no
    `display_name` to read; `name.title()` is the convention the tests already use.
    """
    return name.title()


async def ensure_registered_sources(session: AsyncSession) -> list[str]:
    """Seed one `sources` row per registered adapter, idempotently.

    The `sources` table is the run-time allow-list (`enabled_source_names`, and the
    pipeline's `_resolve_adapters`), but nothing in production ever created its rows
    — a freshly migrated database had zero enabled sources, so every run resolved
    zero adapters. The registry (`app/sources/registry.py`) is the code-level source
    of truth, so this inserts exactly its adapters, each `enabled=True` (the registry
    is the truth and `enabled` has no other writer in v1).

    Safe to call on every boot: a name already present is skipped and a racing
    insert (`uq_sources_name`) is swallowed by a SAVEPOINT, so a re-run inserts
    nothing. Returns the names inserted this call. The caller owns the commit, like
    every other function in this module.
    """
    existing = set(
        (await session.execute(select(Source.name))).scalars().all()
    )
    missing = [name for name in registry.all_adapters() if name not in existing]
    if not missing:
        return []

    try:
        async with session.begin_nested():
            session.add_all(
                Source(name=name, display_name=_display_name(name), enabled=True)
                for name in missing
            )
    except IntegrityError:
        # A concurrent seeder won the race; the rows now exist, which is the goal.
        return []
    return missing


async def record_probe_result(
    session: AsyncSession,
    *,
    source: str,
    status: str,
    now: datetime | None = None,
) -> bool:
    """Stamp `last_probe_at` and `health` on one source row.

    Returns `False` when no row carries that name — a registered adapter with no
    `sources` row is not an error, and the probe must not fail over it.
    """
    if status not in VALID_HEALTH:
        raise ValueError(
            f"invalid probe status {status!r}; expected one of {sorted(VALID_HEALTH)}"
        )

    row = await session.scalar(select(Source).where(Source.name == source))
    if row is None:
        return False

    row.last_probe_at = now or datetime.now(UTC)
    row.health = status
    await session.flush()
    return True


async def get_source_health(session: AsyncSession) -> list[SourceHealth]:
    """The per-source read model: liveness, last success, volume and fill-rate."""
    sources = (
        await session.execute(select(Source).order_by(Source.name))
    ).scalars().all()
    runs = (
        await session.execute(
            select(Run)
            .order_by(Run.started_at.desc(), Run.id.desc())
            .limit(RECENT_RUN_LIMIT)
        )
    ).scalars().all()

    health: list[SourceHealth] = []
    for source in sources:
        latest = _latest_run_for(runs, source.name)
        last_success = _last_success_run(runs, source.name)

        rows: list[tuple[Listing, ListingSource]] = []
        if latest is not None and latest.started_at is not None:
            rows = list(
                (
                    await session.execute(
                        select(Listing, ListingSource)
                        .join(ListingSource, ListingSource.listing_id == Listing.id)
                        .where(
                            ListingSource.source == source.name,
                            ListingSource.last_seen_at >= latest.started_at,
                        )
                    )
                ).all()
            )

        returned = 0
        if latest is not None:
            entry = _source_entry(latest, source.name) or {}
            try:
                returned = int(entry.get("fetched") or 0)
            except (TypeError, ValueError):
                returned = 0
        if not returned and rows:
            returned = len(rows)

        health.append(
            SourceHealth(
                name=source.name,
                enabled=bool(source.enabled),
                health=source.health,
                last_probe_at=source.last_probe_at,
                last_success_at=last_success.started_at if last_success else None,
                listings_returned=returned,
                field_fill_rate=_fill_rate(rows),
            )
        )

    return health


async def get_source_health_with_signals(
    session: AsyncSession,
) -> list[SourceHealthDetail]:
    """`get_source_health` plus the recorded stop-signal classification (D-156).

    The base read is the existing run-derived one; this adds, per source, the
    newest `settings.probe_count_trailing_runs` `source_request_log` rows — the
    stop signals the pipeline already wrote at ingest — classified with the pure
    `classify_block_vs_parse`. The newest classification projects onto the shared
    `VALID_HEALTH` vocabulary, so a board that pushed back reads `degraded` even
    when its last *run* recorded `ok`.

    A DATABASE read only: it never calls `record_probe_result`, `probe_all` or an
    adapter, so a page view can never become a scrape. Ordering matches
    `get_source_health` (`Source.name`, then `occurred_at DESC, id DESC`).
    """
    rows = await get_source_health(session)
    details: list[SourceHealthDetail] = []
    for row in rows:
        log_rows = (
            (
                await session.execute(
                    select(SourceRequestLog)
                    .where(SourceRequestLog.source == row.name)
                    .order_by(
                        SourceRequestLog.occurred_at.desc(),
                        SourceRequestLog.id.desc(),
                    )
                    .limit(max(1, int(settings.probe_count_trailing_runs)))
                )
            )
            .scalars()
            .all()
        )
        newest = log_rows[0] if log_rows else None
        classification = _classify_ledger_row(newest) if newest is not None else None
        details.append(
            SourceHealthDetail(
                name=row.name,
                enabled=row.enabled,
                health=_derived_health(row.health, classification),
                last_probe_at=row.last_probe_at,
                last_success_at=row.last_success_at,
                listings_returned=row.listings_returned,
                field_fill_rate=row.field_fill_rate,
                classification=(
                    str(classification.observed) if classification is not None else None
                ),
                stop_signal=(
                    _recorded_stop_signal(newest.note) if newest is not None else None
                ),
            )
        )
    return details


def _count(value: Any) -> int:
    """An integer count, or 0 for anything unusable — never raises."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _window_days(moments: Sequence[datetime | None]) -> int:
    """The span of recorded runs in whole days, floored at 1 (0 when none)."""
    stamps = [moment for moment in moments if moment is not None]
    if not stamps:
        return 0
    if len(stamps) == 1:
        return 1
    span = max(stamps) - min(stamps)
    return max(1, span.days + (1 if span.seconds or span.microseconds else 0))


def _ledger_probe_status(row: SourceRequestLog) -> str:
    """The liveness a ledger row implies, in `probe()`'s own vocabulary.

    A recorded transport error is `unreachable`; any other failed row is
    `degraded`; a clean row is `ok`. The ledger records `fetch()`, not `probe()`,
    so this is the closest recorded proxy for P-4 — stated, not assumed.
    """
    if row.ok:
        return "ok"
    note = row.note if isinstance(row.note, str) else ""
    if note.startswith(TRANSPORT_ERROR_PREFIX):
        return "unreachable"
    return "degraded"


async def board_evidence(session: AsyncSession, source_name: str) -> BoardEvidence | None:
    """One board's persisted evidence for the Adzuna promotion condition (D-158).

    Assembled from persisted rows only, so viewing the verdict can never put a
    request on a board: the newest `settings.probe_promotion_window_runs` runs that
    recorded this board, the board's recorded baseline, and its newest recorded
    requests. Returns `None` when the board has no recorded evidence at all, so the
    caller renders the no-verdict state rather than a fabricated zero. A board with
    fewer rows than the window yields a genuinely short window — nothing is padded.

    Per-run fill-rates use the same scoping `get_source_health` uses for a run
    (rows whose `last_seen_at` is at or after that run's start), so the two reads
    cannot report different fill-rates for the same run. That scoping is cumulative
    across runs — a trade-off of a schema with no direct listing-to-run link — and a
    run with no rows contributes no sample rather than a zeroed one.
    """
    window = max(1, int(settings.probe_promotion_window_runs))
    recent = (
        (
            await session.execute(
                select(Run).order_by(Run.started_at.desc(), Run.id.desc()).limit(window)
            )
        )
        .scalars()
        .all()
    )

    recorded: list[tuple[Run, dict[str, Any]]] = []
    for run in recent:
        entry = _source_entry(run, source_name)
        if entry is not None:
            recorded.append((run, entry))
    if not recorded:
        return None
    recorded.reverse()  # oldest-to-newest, the order every signal reads

    fill_rates: list[dict[str, float]] = []
    for run, _entry in recorded:
        if run.started_at is None:
            continue
        rows = list(
            (
                await session.execute(
                    select(Listing, ListingSource)
                    .join(ListingSource, ListingSource.listing_id == Listing.id)
                    .where(
                        ListingSource.source == source_name,
                        ListingSource.last_seen_at >= run.started_at,
                    )
                )
            ).all()
        )
        if rows:
            fill_rates.append(_fill_rate(rows))

    source_row = await session.scalar(select(Source).where(Source.name == source_name))
    baseline = baseline_from_row(source_row) if source_row is not None else None

    log_rows = (
        (
            await session.execute(
                select(SourceRequestLog)
                .where(SourceRequestLog.source == source_name)
                .order_by(
                    SourceRequestLog.occurred_at.desc(), SourceRequestLog.id.desc()
                )
                .limit(window)
            )
        )
        .scalars()
        .all()
    )

    return BoardEvidence(
        source=source_name,
        run_statuses=[str(entry.get("status") or "") for _run, entry in recorded],
        output_counts=[_count(entry.get("fetched")) for _run, entry in recorded],
        new_listing_counts=[_count(entry.get("created")) for _run, entry in recorded],
        fill_rates=tuple(fill_rates),
        baseline=baseline.rates if baseline is not None else None,
        probe_statuses=[_ledger_probe_status(row) for row in reversed(log_rows)],
        window_days=_window_days([run.started_at for run, _entry in recorded]),
    )


__all__ = [
    "CLASSIFICATION_HEALTH",
    "FILL_RATE_FIELDS",
    "RECENT_RUN_LIMIT",
    "VALID_HEALTH",
    "SourceHealth",
    "SourceHealthDetail",
    "board_evidence",
    "enabled_source_names",
    "ensure_registered_sources",
    "get_source_health",
    "get_source_health_with_signals",
    "record_probe_result",
]
