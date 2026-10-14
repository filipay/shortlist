"""Retention pruning — the only place the prune SQL lives (D-163 … D-168).

House rules, as everywhere in `app/db/repositories/`:

* repositories are the **only** place SQL lives;
* they take an `AsyncSession` explicitly and **never commit** — the caller owns the
  single commit;
* writes are wrapped in a SAVEPOINT (`session.begin_nested()`) so a failure here
  cannot poison the caller's outer transaction;
* `now` is injectable so a caller (or a test) can pin the clock.

The four prunable categories are D-163's: the run history with its stage logs, the
tailored CV artifacts (rows **and** the `.tex`/`.pdf` files on disk), the source
request log, and inactive or stale listings. Pruning is **per-category and
per-threshold** — the caller picks one category and one age.

Three properties this module is built around, all from the phase research:

* **One predicate per category.** `preview` and `delete` run the *same* select, so
  the count shown before destruction cannot disagree with the number removed.
* **Guards are the queries' own conditions** (D-165), never a post-filter: the
  recent-runs floor, the `llm_calls` ledger, an artifact referenced by an
  application, and each listing's newest successful artifact. A guard expressed as a
  `WHERE` clause cannot be forgotten at the confirm step.
* **No request-derived string reaches a statement.** A category is validated against
  ``PRUNE_CATEGORIES`` and mapped to a pre-built statement through a frozen mapping,
  so the SQL is fixed at import time.

**D-164 amendment (recorded, not implied).** The audit logs are never pruned
*except* by the deletion of their parent listing, which is itself a user-confirmed,
previewed, snapshotted, one-way action. Deleting a listing needs its `listing_events`
children gone, the append-only `BEFORE DELETE` trigger therefore has to be suspended
for the duration of that one transaction, and the caller (the route) owns that
suspension — this module only reports which categories need it
(``TRIGGER_CARVE_OUT_CATEGORIES``) and never re-implements the drop/re-arm pair.

**D-167 accepted consequence.** `listing_sources` carries the
``UNIQUE(source, source_listing_id)`` upsert key, so once those provenance rows are
gone a re-post of the same job returns as a **new** listing with a new
``first_seen_at``, and prior dismissals are gone. There is no tombstone; the
snapshot taken immediately before is the only recovery.

``queue_state`` is a **global** watermark row with no listing column, so it is not a
per-listing child and is never deleted here: doing so would silently reset
"new since last visit" for every listing (D-167's "its `queue_state`" is a wording
slip, per research C2).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models import (
    Application,
    CvArtifact,
    CvDraft,
    Listing,
    ListingDupe,
    ListingEvent,
    ListingExclusion,
    ListingSource,
    LlmCall,
    Run,
    Score,
    ScreeningDraft,
    SourceRequestLog,
)
from app.db.repositories import run_repo

#: D-163 — every category the routes may be asked to prune. The allow-list: a
#: category arriving from the browser is validated against this before any SQL.
PRUNE_CATEGORIES: frozenset[str] = frozenset(
    {"runs", "artifacts", "source_request_log", "listings"}
)

#: D-165 guard 1 — the retention floor, in runs. Reusing `RUN_HISTORY_LIMIT` is
#: deliberate: it is the LARGEST existing run-read window (at least the source-health
#: window and the probe windows), so one floor satisfies every reader by construction.
RUN_FLOOR: int = run_repo.RUN_HISTORY_LIMIT

#: The `BEFORE DELETE` trigger migration 0001 creates to keep `listing_events`
#: append-only. A single definition of the name, shared with the reset's
#: suspend/restore pair so the two cannot drift.
APPEND_ONLY_TRIGGER = "listing_events_no_delete"

#: The categories whose delete needs the append-only trigger suspended around it.
#: Only `listings`: its event children are undeletable while the trigger stands, and
#: the D-164 carve-out above is what lifts that. Everything else is a plain delete.
TRIGGER_CARVE_OUT_CATEGORIES: frozenset[str] = frozenset({"listings"})


@dataclass(frozen=True)
class PrunePreview:
    """A dry run: what one category at one age would delete, and how much disk it frees."""

    category: str
    age_days: int
    count: int
    size_bytes: int
    noun_singular: str
    noun_plural: str
    #: Stored paths that were missing, or that resolved outside the artifacts
    #: directory and were therefore not measured (T-08-23). Reported, never fatal.
    missing_files: int = 0

    @property
    def noun(self) -> str:
        """The item noun for this count, pluralised."""
        return self.noun_singular if self.count == 1 else self.noun_plural

    @property
    def size_display(self) -> str:
        """The on-disk total as a human string (`3.1 GB`), never a database sum."""
        return _human_size(self.size_bytes)


def _human_size(size: int) -> str:
    """Bytes as a compact human string. Zero is `0 B`, never an empty string."""
    value = float(max(0, int(size)))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024.0 or unit == "GB":
            if unit == "B":
                return str(int(value)) + " B"
            return "{:.1f}".format(value) + " " + unit
    return str(int(value)) + " B"  # pragma: no cover — the loop always returns


@dataclass(frozen=True)
class _Category:
    """One prunable category: its select, its file paths, its delete, its nouns.

    `select` builds the candidate-id statement, `paths` extracts the file paths the
    route must unlink AFTER the commit, and `delete` executes the deletes (children
    before parents, foreign-key safe). `nouns` is the preview sentence's
    (singular, plural) pair.
    """

    select: Callable[[datetime], Any]
    paths: Callable[[AsyncSession, list[int]], Awaitable[list[str]]]
    delete: Callable[[AsyncSession, list[int]], Awaitable[None]]
    nouns: tuple[str, str]


def _validate(category: Any, age_days: Any) -> tuple[str, int]:
    """`(category, age_days)` for a well-formed request, else `ValueError`.

    Raises before any SQL. A zero or negative threshold would make EVERY record
    eligible, so it is refused rather than clamped (T-08-25).
    """
    if not isinstance(category, str) or category not in PRUNE_CATEGORIES:
        raise ValueError("unknown prune category: " + repr(category))
    if isinstance(age_days, str):
        try:
            age_days = int(age_days.strip())
        except (TypeError, ValueError):
            raise ValueError("age_days must be a positive integer") from None
    if isinstance(age_days, bool) or not isinstance(age_days, int) or age_days <= 0:
        raise ValueError("age_days must be a positive integer")
    return category, age_days


def _cutoff(age_days: int, now: datetime | None) -> datetime:
    """The age threshold as an instant: records before it qualify."""
    moment = now if now is not None else datetime.now(UTC)
    return moment - timedelta(days=age_days)


def _floor_ids() -> Any:
    """The newest `RUN_FLOOR` runs by `(started_at DESC, id DESC)` — guard 1's window."""
    return select(Run.id).order_by(Run.started_at.desc(), Run.id.desc()).limit(RUN_FLOOR)


def _select_artifacts(cutoff: datetime) -> Any:
    """Old artifacts minus guards 3 and 4 (D-165).

    Guard 3: no row referenced by an application's artifact column.
    Guard 4: no row that IS its listing's newest successful artifact — the exact
    complement of `cv_artifact_repo.latest_for_listing(ok_only=True)`'s
    `ORDER BY created_at DESC, id DESC` restricted to `compile_status = 'ok'`, so the
    prune can never delete an artifact the listing page is showing. A `blocked` or
    `failed` row is not a successful artifact and so is not guarded by this one.
    """
    newer = aliased(CvArtifact)
    newer_ok = (
        select(newer.id)
        .where(
            newer.listing_id == CvArtifact.listing_id,
            newer.compile_status == "ok",
            or_(
                newer.created_at > CvArtifact.created_at,
                and_(
                    newer.created_at == CvArtifact.created_at,
                    newer.id > CvArtifact.id,
                ),
            ),
        )
        .exists()
    )
    app_linked = (
        select(Application.id).where(Application.cv_artifact_id == CvArtifact.id).exists()
    )
    return select(CvArtifact.id).where(
        CvArtifact.created_at < cutoff,
        ~app_linked,
        or_(CvArtifact.compile_status != "ok", newer_ok),
    )


async def _paths_for_artifacts(session: AsyncSession, ids: list[int]) -> list[str]:
    """Both file paths of every selected artifact row, blanks dropped."""
    if not ids:
        return []
    rows = await session.execute(
        select(CvArtifact.tex_path, CvArtifact.pdf_path).where(CvArtifact.id.in_(ids))
    )
    return [path for row in rows for path in row if path]


async def _delete_artifacts(session: AsyncSession, ids: list[int]) -> None:
    """Delete the selected `cv_artifacts` rows. The files are the caller's job."""
    await session.execute(sa_delete(CvArtifact).where(CvArtifact.id.in_(ids)))


#: The frozen category mapping every request lookup goes through. Adding a category
#: is one entry here plus its selection functions; no request-derived string ever
#: reaches a statement because the keys are checked against `PRUNE_CATEGORIES` first.
_CATEGORIES: Mapping[str, _Category] = MappingProxyType(
    {
        "artifacts": _Category(
            select=_select_artifacts,
            paths=_paths_for_artifacts,
            delete=_delete_artifacts,
            nouns=("artifact", "artifacts"),
        ),
    }
)


def _size_inside(raw: str, root: Path) -> int | None:
    """Bytes for a stored path that resolves INSIDE `root`, or `None`.

    Containment is applied here as well as at the unlink (T-08-23): a `stat()` on an
    arbitrary path would otherwise leak file existence into the audit line, and a
    legacy or hand-edited row could point anywhere. A missing file returns `None`
    too — the caller reports the count rather than raising.
    """
    try:
        resolved = Path(raw).resolve()
    except (OSError, ValueError):
        return None
    if resolved != root and root not in resolved.parents:
        return None
    try:
        return resolved.stat().st_size
    except OSError:
        return None


async def _select_ids(session: AsyncSession, category: str, cutoff: datetime) -> list[int]:
    """The candidate ids for one category at one cutoff. Never commits."""
    rows = (await session.execute(_CATEGORIES[category].select(cutoff))).scalars().all()
    return [int(row) for row in rows]


async def preview(
    session: AsyncSession,
    *,
    category: Any,
    age_days: Any,
    artifacts_root: Path,
    now: datetime | None = None,
) -> PrunePreview:
    """Count and summed on-disk size for a prune that has NOT happened. Never commits.

    Raises `ValueError` for a bad category or a non-positive age, before any SQL.
    """
    name, days = _validate(category, age_days)
    cutoff = _cutoff(days, now)
    spec = _CATEGORIES[name]
    ids = await _select_ids(session, name, cutoff)
    root = Path(artifacts_root).resolve()
    total = 0
    missing = 0
    for raw in await spec.paths(session, ids):
        size = _size_inside(raw, root)
        if size is None:
            missing += 1
        else:
            total += size
    return PrunePreview(
        category=name,
        age_days=days,
        count=len(ids),
        size_bytes=total,
        noun_singular=spec.nouns[0],
        noun_plural=spec.nouns[1],
        missing_files=missing,
    )


async def delete(
    session: AsyncSession,
    *,
    category: Any,
    age_days: Any,
    now: datetime | None = None,
) -> tuple[int, list[Path]]:
    """Delete the selected rows. Returns `(count, paths_to_unlink_after_the_commit)`.

    Runs the SAME selection `preview` runs, so the count cannot disagree. Never
    commits and never unlinks: the caller commits first and unlinks strictly after,
    because the unlink is not transactional — a rolled-back commit must never leave
    live rows pointing at missing files (T-08-30).

    Raises `ValueError` for a bad category or a non-positive age, before any SQL.
    """
    name, days = _validate(category, age_days)
    cutoff = _cutoff(days, now)
    spec = _CATEGORIES[name]
    ids = await _select_ids(session, name, cutoff)
    if not ids:
        return 0, []
    paths = [Path(raw) for raw in await spec.paths(session, ids)]
    async with session.begin_nested():
        await spec.delete(session, ids)
    return len(ids), paths


__all__ = [
    "APPEND_ONLY_TRIGGER",
    "PRUNE_CATEGORIES",
    "RUN_FLOOR",
    "TRIGGER_CARVE_OUT_CATEGORIES",
    "PrunePreview",
    "delete",
    "preview",
]
