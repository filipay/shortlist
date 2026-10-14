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
DEFAULT_SCHEDULE = ScheduleConfig(
    enabled=False, hour=7, minute=0, timezone="Europe/Dublin"
)


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
            f"unknown timezone {schedule.timezone!r}; "
            f"expected one of {sorted(ALLOWED_TIMEZONES)}"
        )

    payload = {
        "enabled": bool(schedule.enabled),
        "hour": int(schedule.hour),
        "minute": int(schedule.minute),
        "timezone": schedule.timezone,
    }
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
    "read_schedule",
    "read_skip_notice",
    "write_schedule",
    "write_skip_notice",
]
