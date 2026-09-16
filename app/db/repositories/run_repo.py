"""Run-history read model (RUN-03's rendering half, RUN-04, D-43 / D-44).

Nothing here recomputes a run's outcome. `runs.status` is carried verbatim so the
Phase-1 rule survives ("`done` only when it actually ran, every board was healthy and
every item persisted"), the reason is the value plan 02-05 persisted, and the counts
are the decomposition that run wrote. The ONE derived value is the human sentence, and
it is computed from those persisted counts through the pure
`app.domain.run_reason.reason_sentence` — never stored, so a historical run's sentence
cannot drift from its own numbers (Pattern 4: persist the decomposition, compute the
aggregate).

Two robustness rules this module keeps:

* **Every JSON column on `runs` is nullable**, because a run can die mid-flight. Each
  accessor defaults to an empty mapping/list rather than raising, so a half-written run
  still renders instead of 500-ing the page.
* **The stage log is bounded here as well as at write time.** Plan 02-05 caps entries
  and per-entry errors on the way in; the read model caps again on the way out, so a
  row written by an older build (or edited by hand) cannot blow up the page.

Ordering is `(started_at DESC, id DESC)`. `started_at` is nullable, so the ordering
tolerates `NULL` (SQLite sorts `NULL` first in `DESC`); the unique `id` tie-break keeps
it deterministic regardless, which matters because two runs started in the same second
are the norm when a user clicks twice.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run
from app.db.repositories.exclusion_repo import excluded_counts_for_run
from app.domain.run_reason import RunCounts, reason_sentence

#: How many runs the history page renders, newest first. An explicit `limit` means a
#: history that grows once per trigger cannot make the page slow; pruning is a Phase-8
#: operations item, not a delete here.
RUN_HISTORY_LIMIT = 50

#: Defence in depth for the stage log, mirroring plan 02-05's write-time caps
#: (`app.pipeline.run.STAGE_LOG_MAX_ENTRIES` / `STAGE_LOG_MAX_ERRORS`). Deliberately a
#: separate constant: the read model must not import the pipeline, and a row from an
#: older build is exactly the case this guards.
STAGE_LOG_RENDER_LIMIT = 12
STAGE_LOG_ERROR_LIMIT = 10


def _mapping(value: Any) -> dict[str, Any]:
    """A JSON object column as a dict, or `{}` — never raises."""
    return dict(value) if isinstance(value, Mapping) else {}


def _entries(value: Any) -> list[Any]:
    """A JSON array column as a list, or `[]` — never raises."""
    return list(value) if isinstance(value, (list, tuple)) else []


def _int(value: Any) -> int:
    """An integer, or 0 for anything unusable (a half-written row is still renderable)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _duration(started_at: datetime | None, finished_at: datetime | None) -> float | None:
    """Seconds between the two stamps, or `None` when the run has not finished.

    `None` rather than `0.0`: a run still in flight must not read as "finished
    instantly". SQLite returns naive datetimes for both, so the subtraction is safe.
    """
    if started_at is None or finished_at is None:
        return None
    return max(0.0, (finished_at - started_at).total_seconds())


def run_counts_for(row: Run) -> RunCounts:
    """Rebuild the pure `RunCounts` from what the run persisted.

    Sources of truth, in order: the persisted decomposition (`reason_counts_json`) for
    the reason's own inputs, and `runs.fetched_count` for the total — `_finish` writes
    it as exactly the sum of the per-source fetched counts, so the sentence cannot cite
    a number the run did not record.
    """
    payload = _mapping(row.reason_counts_json)
    sources = _mapping(payload.get("sources"))
    statuses = tuple(
        str(entry.get("status", ""))
        for entry in sources.values()
        if isinstance(entry, Mapping)
    )
    return RunCounts(
        adapters_resolved=_int(payload.get("adapters_resolved")),
        statuses=statuses,
        fetched=_int(row.fetched_count),
        excluded_by_rule={
            str(key): _int(value)
            for key, value in _mapping(payload.get("excluded_by_rule")).items()
        },
        survivors=_int(payload.get("survivors")),
        new_since_watermark=_int(payload.get("new_since_watermark")),
    )


def sentence_for(row: Run) -> str:
    """The displayed sentence, derived from the persisted reason plus counts.

    An absent reason (a run that died before plan 02-05's reason write) still produces
    a sentence rather than an empty cell: `mixed` is the enum's own "something else"
    value, and the counts are read as zeroes rather than invented.
    """
    reason = str(row.reason or "mixed")
    return reason_sentence(reason, run_counts_for(row))


@dataclass(frozen=True)
class RunSummary:
    """One `runs` row, ready to render. Frozen: nothing can be mutated back."""

    id: int
    trigger: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None
    search_id: int | None
    fetched_count: int
    deduped_count: int
    filtered_count: int
    sources: Mapping[str, Any]
    #: The first `STAGE_LOG_ERROR_LIMIT` errors, so no row can render unbounded.
    errors: tuple[Mapping[str, Any], ...]
    #: The TRUE number of persisted errors, which the display list above is bounded to.
    error_count: int
    reason: str | None
    sentence: str

    @property
    def in_flight(self) -> bool:
        return self.finished_at is None

    @property
    def errors_json(self) -> tuple[Mapping[str, Any], ...]:
        """The errors under the COLUMN's own name.

        `_run_status.html` reads `run.errors_json`, and the queue's last-run strip
        renders through that same partial, so exposing this name is what lets one run
        renderer serve both surfaces without a second template or a shim object.
        """
        return self.errors


@dataclass(frozen=True)
class RunDetail(RunSummary):
    """A summary plus the expansion: the counts, the stage log and the criteria used."""

    reason_counts: Mapping[str, Any] = field(default_factory=dict)
    stage_log: tuple[Mapping[str, Any], ...] = ()
    excluded_by_rule: Mapping[str, int] = field(default_factory=dict)
    criteria_snapshot: Mapping[str, Any] = field(default_factory=dict)

    @property
    def searches(self) -> tuple[Mapping[str, Any], ...]:
        """The criteria snapshot's per-search sections (D-45/A6: keyed by search id).

        Read as a sorted tuple so the page's order is deterministic rather than
        dependent on JSON key order.
        """
        return tuple(
            entry
            for _key, entry in sorted(self.criteria_snapshot.items())
            if isinstance(entry, Mapping)
        )


def _stage_log(value: Any) -> tuple[Mapping[str, Any], ...]:
    """The persisted stage log, bounded again on the way out.

    Each entry's `errors` list is truncated as well, so a pathological entry cannot
    render an unbounded block even though the writer already capped it.
    """
    entries: list[Mapping[str, Any]] = []
    for entry in _entries(value)[:STAGE_LOG_RENDER_LIMIT]:
        if not isinstance(entry, Mapping):
            continue
        bounded = dict(entry)
        bounded["errors"] = [
            str(message) for message in _entries(entry.get("errors"))[:STAGE_LOG_ERROR_LIMIT]
        ]
        entries.append(bounded)
    return tuple(entries)


def _summary(row: Run) -> RunSummary:
    all_errors = tuple(
        entry for entry in _entries(row.errors_json) if isinstance(entry, Mapping)
    )
    return RunSummary(
        id=int(row.id),
        trigger=str(row.trigger or ""),
        status=str(row.status or ""),
        started_at=row.started_at,
        finished_at=row.finished_at,
        duration_seconds=_duration(row.started_at, row.finished_at),
        search_id=row.search_id,
        fetched_count=_int(row.fetched_count),
        deduped_count=_int(row.deduped_count),
        filtered_count=_int(row.filtered_count),
        sources=_mapping(row.source_counts_json),
        errors=all_errors[:STAGE_LOG_ERROR_LIMIT],
        error_count=len(all_errors),
        reason=row.reason,
        sentence=sentence_for(row),
    )


async def list_runs(
    session: AsyncSession, *, limit: int = RUN_HISTORY_LIMIT
) -> list[RunSummary]:
    """Every run, newest first, bounded by `limit`. Never commits (the caller owns it)."""
    bound = max(1, int(limit))
    rows = (
        (
            await session.execute(
                select(Run).order_by(Run.started_at.desc(), Run.id.desc()).limit(bound)
            )
        )
        .scalars()
        .all()
    )
    return [_summary(row) for row in rows]


async def get_run_detail(session: AsyncSession, *, run_id: int) -> RunDetail | None:
    """One run with its expansion, or `None` when there is no such run."""
    row = await session.get(Run, int(run_id))
    if row is None:
        return None

    summary = _summary(row)
    values = {each.name: getattr(summary, each.name) for each in dataclass_fields(summary)}
    return RunDetail(
        **values,
        reason_counts=_mapping(row.reason_counts_json),
        stage_log=_stage_log(row.stage_log_json),
        excluded_by_rule=await excluded_counts_for_run(session, run_id=int(run_id)),
        criteria_snapshot=_mapping(row.criteria_snapshot_json),
    )


__all__ = [
    "RUN_HISTORY_LIMIT",
    "STAGE_LOG_ERROR_LIMIT",
    "STAGE_LOG_RENDER_LIMIT",
    "RunDetail",
    "RunSummary",
    "get_run_detail",
    "list_runs",
    "run_counts_for",
    "sentence_for",
]
