"""`cv_versions` write path — the revision log every rendered artefact names (D-77).

House rules, as everywhere in `app/db/repositories/`:

* repositories are the **only** place SQL lives;
* they take an `AsyncSession` explicitly and **never commit** — the caller owns
  the single commit;
* the write is wrapped in a SAVEPOINT (`session.begin_nested()`) so a failure
  here cannot poison the caller's outer transaction;
* the clock is injectable so a caller (or a test) can pin it.

This is the producer of the revision identifier a rendered CV artefact points at
(`cv_artifacts.base_cv_version_id`), so "which revision of my CV was this PDF
built from" is answerable rather than guessed.

The vocabulary is **application-level**: `cv_versions.source` is a `String(16)`
with no CHECK constraint, so this module validates the source before any SQL is
issued and raises a clear `ValueError` rather than a raw `IntegrityError`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CvVersion

#: The legal `cv_versions.source` values. The column carries no CHECK constraint,
#: so this frozenset is the guard; widening it is a coordinated change here.
SOURCES: frozenset[str] = frozenset({"import_tex", "hand"})


@dataclass(frozen=True)
class CvVersionRecord:
    """One `cv_versions` row, ready to render. Frozen: nothing mutates back."""

    id: int
    label: str | None
    schema_version: str | None
    source: str | None
    created_at: datetime
    is_current: bool


async def snapshot_version(
    session: AsyncSession,
    *,
    facts_json: dict[str, Any],
    schema_version: int | str,
    source: str,
    label: str | None = None,
    now: datetime | None = None,
) -> CvVersionRecord:
    """Snapshot one accepted CV revision and make it the current row. Never commits.

    The previous current row's flag is cleared and the new row is inserted with the
    flag set, inside one SAVEPOINT, so the caller's commit decides whether the
    revision exists at all.

    `schema_version` is stored **as a string** deliberately. The column is a
    bounded `String(32)` while the fact store's value is an integer; SQLite's type
    affinity would silently coerce the int anyway, so the bug would stay invisible
    until a Postgres migration — or until a drift check compared the stored `"1"`
    against the YAML `1` and never found them equal. Stringifying here makes the
    stored representation explicit and the later comparison meaningful.
    """
    if source not in SOURCES:
        raise ValueError(
            f"unknown source {source!r}; expected one of {sorted(SOURCES)}"
        )

    moment = now if now is not None else datetime.now(UTC)
    version_text = str(schema_version)

    row = CvVersion(
        label=label,
        schema_version=version_text,
        facts_json=facts_json,
        source=source,
        created_at=moment,
        is_current=True,
    )
    # BOTH statements live inside the SAVEPOINT: clearing the previous current
    # flag and inserting the new row roll back together, so a failed insert
    # cannot leave the table with zero current rows (WR-01). Issue the clear
    # before `session.add(row)` so the INSERT is not autoflushed ahead of it.
    async with session.begin_nested():
        await session.execute(
            update(CvVersion)
            .where(CvVersion.is_current.is_(True))
            .values(is_current=False)
        )
        session.add(row)
        await session.flush()

    return _to_record(row)


async def current_version(session: AsyncSession) -> CvVersionRecord | None:
    """The newest revision by `created_at` descending then `id` descending.

    Returns `None` on an empty table, never commits and never raises. The `id`
    tie-break is not decoration: two revisions written within one second share a
    `created_at`, and the same rule already governs `llm_call_repo.latest_probe`
    and `event_repo`'s projection.
    """
    row = await session.scalar(
        select(CvVersion)
        .order_by(CvVersion.created_at.desc(), CvVersion.id.desc())
        .limit(1)
    )
    return _to_record(row) if row is not None else None


def _to_record(row: CvVersion) -> CvVersionRecord:
    """One ORM row as its frozen read value — the single mapping, so the write and
    the read cannot disagree about a field."""
    return CvVersionRecord(
        id=int(row.id),
        label=row.label,
        schema_version=row.schema_version,
        source=row.source,
        created_at=row.created_at,
        is_current=bool(row.is_current),
    )


__all__ = ["SOURCES", "CvVersionRecord", "current_version", "snapshot_version"]
