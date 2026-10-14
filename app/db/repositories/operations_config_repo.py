"""The operations document — the only place its SQL lives (D-153 / D-168).

House rules, as everywhere in `app/db/repositories/`:

* repositories are the **only** place SQL lives;
* they take an `AsyncSession` explicitly and **never commit** — the caller owns
  the single commit;
* writes are wrapped in a SAVEPOINT (`session.begin_nested()`) so a failure here
  cannot poison the caller's outer transaction;
* `now` is injectable so a caller (or a test) can pin the clock.

One row, `id = 1`, enforced by `ck_operations_config_singleton`. The schedule read
is **total**: an absent row or a malformed payload falls back to
:data:`DEFAULT_SCHEDULE`, so a fresh install has a usable (disabled) schedule with
no seed row. The schedule write is **strict**: hour, minute and timezone are
validated before any SQL, so no request-derived value reaches a statement or the
trigger builder unchecked (D-34 / T-08-10).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OperationsConfig
from app.db.repositories import retention_repo

#: The pinned singleton row id (mirrors ``ck_operations_config_singleton``).
SINGLETON_ID = 1

#: The timezones the schedule picker may offer. A frozen allow-list, because the
#: value crosses the browser boundary into the trigger builder (T-08-10).
ALLOWED_TIMEZONES = frozenset({"Europe/Dublin"})


@dataclass(frozen=True)
class ScheduleConfig:
    """The stored schedule. Frozen so a caller cannot mutate the read result."""

    enabled: bool
    hour: int
    minute: int
    timezone: str


#: The fresh-install schedule. Disabled on purpose: scheduling is deliberately
#: late and an off default is the safe state.
DEFAULT_SCHEDULE = ScheduleConfig(enabled=False, hour=7, minute=0, timezone="Europe/Dublin")


def _schedule_payload(schedule: ScheduleConfig) -> dict[str, Any]:
    """The stored JSON document for a schedule. One builder, so a create and an
    update cannot disagree about the shape."""
    return {
        "enabled": bool(schedule.enabled),
        "hour": int(schedule.hour),
        "minute": int(schedule.minute),
        "timezone": schedule.timezone,
    }


def _in_range(value: Any, low: int, high: int) -> int | None:
    """An integer in ``[low, high]``, or ``None`` for anything unusable."""
    if isinstance(value, bool):
        return None
    if not isinstance(value, int):
        return None
    return value if low <= value <= high else None


def _parse_schedule(stored: Any) -> ScheduleConfig:
    """A total parse of the stored payload: anything malformed → the default.

    Falling back for the WHOLE document (rather than per-field) keeps the read
    simple and honest: a half-written schedule is not a schedule, and the default
    (disabled, 07:00 Europe/Dublin) is always a safe, expressible state.
    """
    if not isinstance(stored, Mapping):
        return DEFAULT_SCHEDULE
    hour = _in_range(stored.get("hour"), 0, 23)
    minute = _in_range(stored.get("minute"), 0, 59)
    timezone = stored.get("timezone")
    if hour is None or minute is None:
        return DEFAULT_SCHEDULE
    if not isinstance(timezone, str) or timezone not in ALLOWED_TIMEZONES:
        return DEFAULT_SCHEDULE
    return ScheduleConfig(
        enabled=bool(stored.get("enabled")),
        hour=hour,
        minute=minute,
        timezone=timezone,
    )


async def read_schedule(session: AsyncSession) -> ScheduleConfig:
    """The stored schedule, or :data:`DEFAULT_SCHEDULE` when it is unusable.

    Total by construction: an absent row, a non-mapping payload or an out-of-range
    value all yield the default rather than raising. Never commits.
    """
    row = await session.get(OperationsConfig, SINGLETON_ID)
    stored = row.schedule_json if row is not None else None
    return _parse_schedule(stored)


async def write_schedule(
    session: AsyncSession,
    schedule: ScheduleConfig,
    *,
    now: datetime | None = None,
) -> ScheduleConfig:
    """Validate and upsert the schedule. Never commits.

    Raises `ValueError` **before any SQL** when the hour, minute or timezone is not
    valid — the caller gets a legible storage-boundary error rather than an
    out-of-range value in the trigger. ``retention_json`` is written with ``{}``
    when the row is first created so a NOT NULL column is never left unset; it is
    neither read nor interpreted here (plan 08-05 owns it).
    """
    if _in_range(schedule.hour, 0, 23) is None:
        raise ValueError(f"hour must be an integer in 0..23, got {schedule.hour!r}")
    if _in_range(schedule.minute, 0, 59) is None:
        raise ValueError(f"minute must be an integer in 0..59, got {schedule.minute!r}")
    if schedule.timezone not in ALLOWED_TIMEZONES:
        raise ValueError(
            f"unknown timezone {schedule.timezone!r}; expected one of {sorted(ALLOWED_TIMEZONES)}"
        )

    payload = _schedule_payload(schedule)
    moment = now if now is not None else datetime.now(UTC)
    statement = (
        sqlite_insert(OperationsConfig)
        .values(
            id=SINGLETON_ID,
            schedule_json=payload,
            retention_json={},
            updated_at=moment,
        )
        .on_conflict_do_update(
            index_elements=["id"],
            set_={"schedule_json": payload, "updated_at": moment},
        )
    )
    async with session.begin_nested():
        await session.execute(statement)
        await session.flush()
    return ScheduleConfig(
        enabled=bool(schedule.enabled),
        hour=int(schedule.hour),
        minute=int(schedule.minute),
        timezone=schedule.timezone,
    )


def _parse_retention(stored: Any) -> dict[str, int]:
    """A total parse of the stored retention payload: only usable entries survive.

    Per-entry rather than whole-document (unlike the schedule): a half-written
    threshold is simply absent, and a category with no stored age still has a default
    at the form, so no state is lost that a malformed document could hide.

    Keys are narrowed to `retention_repo.PRUNE_CATEGORIES` (IN-05): a hand-edited or
    legacy `retention_json` can otherwise surface an arbitrary key in the "Stored
    thresholds" line. The write path validates the same set, so a value that survives
    the read is one the prune can actually act on.
    """
    if not isinstance(stored, Mapping):
        return {}
    parsed: dict[str, int] = {}
    for key, value in stored.items():
        if not isinstance(key, str) or isinstance(value, bool):
            continue
        if key not in retention_repo.PRUNE_CATEGORIES:
            continue
        try:
            age = int(value)
        except (TypeError, ValueError):
            continue
        if age > 0:
            parsed[key] = age
    return parsed


async def read_retention(session: AsyncSession) -> dict[str, int]:
    """The stored per-category retention thresholds (D-168), or `{}`. Total.

    An absent row, a non-mapping payload or a non-positive value all degrade rather
    than raising, so a fresh install has no stored thresholds and each category falls
    back to the form's own default. Never commits.
    """
    row = await session.get(OperationsConfig, SINGLETON_ID)
    stored = row.retention_json if row is not None else None
    return _parse_retention(stored)


async def write_retention(
    session: AsyncSession,
    category: str,
    age_days: int,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Merge one category's age threshold into the stored retention payload. Never commits.

    Raises `ValueError` before any SQL for a category outside
    `retention_repo.PRUNE_CATEGORIES` or a non-positive age — a zero/negative
    threshold would make every record eligible, and an unknown category has no
    prune behind it.

    The singleton row has TWO NOT NULL payload columns and is created lazily, so a
    create from this writer must supply ``schedule_json`` too: the *stored* schedule
    document when the row exists, and the code-level default when it does not. Without
    that, the first prune-threshold save on a database where nobody has saved a
    schedule yet fails the NOT NULL constraint — a failure that appears only on a
    fresh install. Symmetrically the ``set_`` clause carries ONLY ``retention_json``
    and ``updated_at``, so a retention write can never clobber a stored schedule.
    """
    if not isinstance(category, str) or category not in retention_repo.PRUNE_CATEGORIES:
        raise ValueError(
            f"category must be one of {sorted(retention_repo.PRUNE_CATEGORIES)}, got {category!r}"
        )
    if isinstance(age_days, bool) or not isinstance(age_days, int) or age_days <= 0:
        raise ValueError("age_days must be a positive integer")

    row = await session.get(OperationsConfig, SINGLETON_ID)
    stored_schedule = row.schedule_json if row is not None else None
    schedule_on_create = (
        dict(stored_schedule)
        if isinstance(stored_schedule, Mapping)
        else _schedule_payload(DEFAULT_SCHEDULE)
    )
    merged = dict(_parse_retention(row.retention_json if row is not None else None))
    merged[category] = int(age_days)

    moment = now if now is not None else datetime.now(UTC)
    statement = (
        sqlite_insert(OperationsConfig)
        .values(
            id=SINGLETON_ID,
            schedule_json=schedule_on_create,
            retention_json=merged,
            updated_at=moment,
        )
        .on_conflict_do_update(
            index_elements=["id"],
            set_={"retention_json": merged, "updated_at": moment},
        )
    )
    async with session.begin_nested():
        await session.execute(statement)
        await session.flush()
    return merged


async def read_skip_notice(session: AsyncSession) -> dict[str, Any] | None:
    """The last D-154 skip notice, or ``None`` when no run has been skipped. Total."""
    row = await session.get(OperationsConfig, SINGLETON_ID)
    stored = row.last_schedule_skip_json if row is not None else None
    return dict(stored) if isinstance(stored, Mapping) else None


async def write_skip_notice(
    session: AsyncSession,
    *,
    reason: str,
    when: datetime | None = None,
    run_id: int | None = None,
    now: datetime | None = None,
) -> None:
    """Record why a scheduled run was skipped, on the operations row. Never commits.

    The notice is a small JSON object on ``last_schedule_skip_json`` — never a new
    ``runs`` row, and never a fifth run status: the status vocabulary has no value
    for a skip and widening it would need a batch recreation of ``runs``.
    """
    payload: dict[str, Any] = {
        "reason": str(reason),
        "scheduled_for": when.isoformat() if when is not None else None,
    }
    if run_id is not None:
        payload["run_id"] = int(run_id)

    moment = now if now is not None else datetime.now(UTC)
    statement = (
        sqlite_insert(OperationsConfig)
        .values(
            id=SINGLETON_ID,
            schedule_json={},
            retention_json={},
            last_schedule_skip_json=payload,
            updated_at=moment,
        )
        .on_conflict_do_update(
            index_elements=["id"],
            set_={"last_schedule_skip_json": payload, "updated_at": moment},
        )
    )
    async with session.begin_nested():
        await session.execute(statement)
        await session.flush()


__all__ = [
    "ALLOWED_TIMEZONES",
    "DEFAULT_SCHEDULE",
    "SINGLETON_ID",
    "ScheduleConfig",
    "read_retention",
    "read_schedule",
    "read_skip_notice",
    "write_retention",
    "write_schedule",
    "write_skip_notice",
]
