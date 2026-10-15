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

The global last-visit watermark is a single row with no listing column, so it is not a
per-listing child and is never deleted here: doing so would silently reset
"new since last visit" for every listing (D-167's "its queue watermark" is a wording
slip, per research C2).
"""

from __future__ import annotations

import stat
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any

import structlog
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

log = structlog.get_logger(__name__)

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
    #: Stored paths that could not be measured: a path that is missing or could not be
    #: resolved, a path that resolved outside the artifacts directory, or a path that
    #: resolved inside the root but is not a regular file (a directory, a device, a
    #: FIFO or a socket). Each is reported here rather than summed into `size_bytes`,
    #: so the total never reads as complete when part of it was not measured (T-08-23).
    #: Reported, never fatal.
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
            return f"{value:.1f}" + " " + unit
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

    An `ok` row with a NULL `listing_id` (an orphan) has no listing to protect, so
    guard 4 cannot apply to it: the correlated subquery compares
    `newer.listing_id == CvArtifact.listing_id`, and `NULL = NULL` is NULL in SQL,
    so without the explicit `listing_id.is_(None)` disjunct such a row would never be
    selected and would leak forever (IN-02). It is therefore eligible on age alone.
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
    app_linked = select(Application.id).where(Application.cv_artifact_id == CvArtifact.id).exists()
    return select(CvArtifact.id).where(
        CvArtifact.created_at < cutoff,
        ~app_linked,
        or_(
            CvArtifact.listing_id.is_(None),
            CvArtifact.compile_status != "ok",
            newer_ok,
        ),
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


def _select_runs(cutoff: datetime) -> Any:
    """Old runs, minus the floor and minus any run whose events cannot be deleted.

    Guard 1: a run inside the newest `RUN_FLOOR` runs (by `started_at`, `id`) survives
    whatever its age — the source-health badge and the Adzuna promotion verdict read
    that window, so starving it would make the health page lie.

    The event constraint is an EXCLUSION, not an error path (C3): a run with
    `listing_events` children cannot be deleted while the append-only trigger stands,
    and the runs category does not suspend it. Excluding the run here means the dry-run
    preview tells the truth, instead of a foreign-key failure at the operator's confirm
    step. Do not "simplify" this away — the alternative is a delete that fails live.
    """
    undeletable = select(ListingEvent.id).where(ListingEvent.run_id == Run.id).exists()
    return select(Run.id).where(
        Run.started_at.is_not(None),
        Run.started_at < cutoff,
        Run.id.not_in(_floor_ids()),
        ~undeletable,
    )


async def _delete_runs(session: AsyncSession, ids: list[int]) -> None:
    """Delete the selected runs: children first, then the runner — never the ledger.

    `scores` carries a NOT NULL foreign key to `runs`, so a naive delete fails at run
    time; `listing_exclusions` and `source_request_log` are nullable but still block.
    The DELIBERATE EXCEPTION to "delete the children" is `llm_calls`: guard 2 forbids
    pruning the call ledger, so its rows SURVIVE with `run_id` set to NULL. Those rows
    back the per-run and rolling-24h spend ceilings — deleting them would silently
    uncap spending.
    """
    await session.execute(sa_delete(Score).where(Score.run_id.in_(ids)))
    await session.execute(sa_delete(ListingExclusion).where(ListingExclusion.run_id.in_(ids)))
    await session.execute(sa_delete(SourceRequestLog).where(SourceRequestLog.run_id.in_(ids)))
    await session.execute(update(LlmCall).where(LlmCall.run_id.in_(ids)).values(run_id=None))
    await session.execute(sa_delete(Run).where(Run.id.in_(ids)))


def _select_source_request_log(cutoff: datetime) -> Any:
    """Old request-log rows, but never a row belonging to a retained run.

    Age alone is not sufficient: `app/probe/survival.py` names `source_request_log` as
    a verdict input, so the rows that feed the survival verdict must survive with the
    runs they belong to. This floor is a genuine ADDITION to the stated invariants
    (D-165's floor covers runs, not this log) — not a re-statement of one. A row with
    no run reference has no verdict input to protect and is eligible on age alone.
    """
    return select(SourceRequestLog.id).where(
        SourceRequestLog.occurred_at < cutoff,
        or_(
            SourceRequestLog.run_id.is_(None),
            SourceRequestLog.run_id.not_in(_floor_ids()),
        ),
    )


async def _delete_source_request_log(session: AsyncSession, ids: list[int]) -> None:
    """Delete the selected request-log rows. No children, no files."""
    await session.execute(sa_delete(SourceRequestLog).where(SourceRequestLog.id.in_(ids)))


async def _no_paths(session: AsyncSession, ids: list[int]) -> list[str]:
    """The `paths` callable for a category that owns no files on disk."""
    return []


def _select_listings(cutoff: datetime) -> Any:
    """Stale listings, minus the three guards that protect a reader's work.

    Excluded when ANY of these hold: the listing has an application (genuine user
    work); it has an artifact row (so the artifact guards cannot be bypassed by
    deleting the parent first); or either side of the dupes audit references it (the
    audit must stay reversible).

    NOT excluded merely because it has `listing_events` rows. That exclusion is what
    the D-164 carve-out lifts, and it is the whole point of the caller's transaction:
    the audit logs are never pruned *except* by the deletion of their parent listing.
    Restricting this category to never-touched listings instead would make it useless
    and the preview would honestly report a count of nearly zero.
    """
    app_linked = select(Application.id).where(Application.listing_id == Listing.id).exists()
    artifact_linked = select(CvArtifact.id).where(CvArtifact.listing_id == Listing.id).exists()
    dupe_linked = (
        select(ListingDupe.id)
        .where(
            or_(
                ListingDupe.listing_id == Listing.id,
                ListingDupe.dup_listing_id == Listing.id,
            )
        )
        .exists()
    )
    return select(Listing.id).where(
        Listing.last_seen_at < cutoff,
        ~app_linked,
        ~artifact_linked,
        ~dupe_linked,
    )


async def _paths_for_listings(session: AsyncSession, ids: list[int]) -> list[str]:
    """The `.tex`/`.pdf` paths of the artifact rows about to be deleted as children.

    Always `[]` by construction: `_select_listings` excludes every listing that has
    any `cv_artifacts` row (`~artifact_linked`), so no id handed here can be the
    `listing_id` of an artifact. Kept (and paired with the defensive `CvArtifact`
    delete in `_delete_listings`) rather than dropped, so a later relaxation of that
    guard cannot silently orphan files: the paths would then be returned and
    unlinked. Do not "fix" the empty result by relaxing the guard.
    """
    if not ids:
        return []
    rows = await session.execute(
        select(CvArtifact.tex_path, CvArtifact.pdf_path).where(CvArtifact.listing_id.in_(ids))
    )
    return [path for row in rows for path in row if path]


async def _delete_listings(session: AsyncSession, ids: list[int]) -> None:
    """Hard-delete the selected listings and their per-listing children (D-167).

    Children before parents, in foreign-key order: `scores`, the source provenance
    rows, the exclusions, BOTH sides of the dupes audit, the CV artifacts, the CV
    drafts and the screening drafts, then the listing events, then the listing itself.
    `PRAGMA foreign_keys=ON` is on every connection, so any other order fails with
    `FOREIGN KEY constraint failed`.

    This is the ONE category that needs the append-only trigger suspended, and the
    caller must have done it (see `TRIGGER_CARVE_OUT_CATEGORIES`): `listing_events`
    rows cannot be deleted while the trigger stands. The suspension and the re-arm
    happen inside the caller's single transaction, so a failure rolls both back.

    D-167's accepted consequence: `listing_sources` carries the
    ``UNIQUE(source, source_listing_id)`` upsert key, so a re-post of the same job
    returns as a **new** listing with a new `first_seen_at` and prior dismissals are
    gone. There is no tombstone. The global last-visit watermark is NOT touched — it
    has no listing reference, and deleting it would silently mark every listing new.
    """
    await session.execute(sa_delete(Score).where(Score.listing_id.in_(ids)))
    await session.execute(sa_delete(ListingSource).where(ListingSource.listing_id.in_(ids)))
    await session.execute(sa_delete(ListingExclusion).where(ListingExclusion.listing_id.in_(ids)))
    await session.execute(
        sa_delete(ListingDupe).where(
            or_(ListingDupe.listing_id.in_(ids), ListingDupe.dup_listing_id.in_(ids))
        )
    )
    # Defensive: `_select_listings` excludes any listing with an artifact row, so
    # this matches zero rows today. Kept so a future relaxation of that guard cannot
    # leave orphaned artifact rows (paired with `_paths_for_listings`).
    await session.execute(sa_delete(CvArtifact).where(CvArtifact.listing_id.in_(ids)))
    await session.execute(sa_delete(CvDraft).where(CvDraft.listing_id.in_(ids)))
    await session.execute(sa_delete(ScreeningDraft).where(ScreeningDraft.listing_id.in_(ids)))
    await session.execute(sa_delete(ListingEvent).where(ListingEvent.listing_id.in_(ids)))
    await session.execute(sa_delete(Listing).where(Listing.id.in_(ids)))


#: The frozen category mapping every request lookup goes through. Adding a category
#: is one entry here plus its selection functions; no request-derived string ever
#: reaches a statement because the keys are checked against `PRUNE_CATEGORIES` first.
_CATEGORIES: Mapping[str, _Category] = MappingProxyType(
    {
        "runs": _Category(
            select=_select_runs,
            paths=_no_paths,
            delete=_delete_runs,
            nouns=("run", "runs"),
        ),
        "artifacts": _Category(
            select=_select_artifacts,
            paths=_paths_for_artifacts,
            delete=_delete_artifacts,
            nouns=("artifact", "artifacts"),
        ),
        "source_request_log": _Category(
            select=_select_source_request_log,
            paths=_no_paths,
            delete=_delete_source_request_log,
            nouns=("request log row", "request log rows"),
        ),
        "listings": _Category(
            select=_select_listings,
            paths=_paths_for_listings,
            delete=_delete_listings,
            nouns=("listing", "listings"),
        ),
    }
)


def _size_inside(raw: str, root: Path) -> int | None:
    """Bytes for a stored path that resolves INSIDE `root` and IS a regular file, or `None`.

    Containment is applied here as well as at the unlink (T-08-23): a `stat()` on an
    arbitrary path would otherwise leak file existence into the audit line, and a
    legacy or hand-edited row could point anywhere. A path that fails containment is
    logged with no `stat` at all, so this cannot disclose whether an outside path exists.

    The measurement is gated on `stat.S_ISREG`: a regular file's `st_size` is the size
    the unlink will free, whereas a directory, a device, a FIFO or a socket reports a
    number that means nothing for this preview, and a bind mount can report an `st_size`
    that is not the file's. A non-regular entry is therefore not measurable and returns
    `None`, exactly like a missing file — the caller counts it through `missing_files`
    instead of summing a meaningless number.

    There is deliberately NO plausibility bound. A cap is a second guess layered on a
    guess and would silently rewrite a genuinely large regular file's true size, so a
    large regular file is reported at its exact `st_size`. The DEBUG event below is what
    makes a bogus size (a bind mount reporting one) identifiable on a live walk.

    One event per outcome: a measured file logs DEBUG; a not-measurable path logs WARNING
    with a reason; an outside-root path logs WARNING and is never `stat`ed.
    """
    try:
        resolved = Path(raw).resolve()
    except (OSError, ValueError):
        log.warning("prune.size_not_measured", path=str(raw), reason="unresolvable")
        return None
    if resolved != root and root not in resolved.parents:
        log.warning("prune.size_outside_artifacts_dir", path=str(raw))
        return None
    try:
        st = resolved.stat()
    except OSError:
        log.warning("prune.size_not_measured", path=str(resolved), reason="missing")
        return None
    if not stat.S_ISREG(st.st_mode):
        log.warning(
            "prune.size_not_measured",
            path=str(resolved),
            mode=st.st_mode,
            reason="not_regular",
        )
        return None
    log.debug("prune.size_measured", path=str(resolved), mode=st.st_mode, size=st.st_size)
    return st.st_size


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
