"""`cv_artifacts` write/read path — one row per compile (D-115 / D-117 / D-118).

House rules, as everywhere in `app/db/repositories/`:

* repositories are the **only** place SQL lives;
* they take an `AsyncSession` explicitly and **never commit** — the caller owns the
  single commit;
* the write is wrapped in a SAVEPOINT (`session.begin_nested()`) so a failure here
  cannot poison the caller's outer transaction;
* `now` is injectable so a caller (or a test) can pin the clock.

**`ok`-only is the artifact-access control (D-118).** Every download/link accessor —
`latest_for_listing(ok_only=True)` and `read_for_download(ok_only=True)` — applies the
`compile_status == "ok"` predicate **IN SQL** (never as a Python post-filter over every
fetched row), so a `blocked` or `failed` row is unreachable even by artifact id. This is
the contract Phase 7's application-attach path consumes: a CV that failed verification
cannot be downloaded, linked or attached. The `ok_only=False` variants exist only for the
status read the tailoring page performs, which must be able to SHOW a blocked row.

**Every compile inserts a NEW row (D-117).** Older rows are never overwritten, so the
history of what was generated stays answerable. `history_for_listing` therefore returns
every row — blocked and failed included — because a blocked attempt is explained, never
silently hidden. Retention/pruning is deliberately Phase 8 and is not implemented here.

The `compile_status` vocabulary is validated against `COMPILE_STATUSES` before any SQL,
mirroring `ck_cv_artifacts_compile_status`. The schema is created only by the Alembic
migration; there is deliberately no ORM-level table build in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CvArtifact

#: Mirrors `ck_cv_artifacts_compile_status` (migration 0001).
COMPILE_STATUSES: frozenset[str] = frozenset({"ok", "failed", "blocked"})


@dataclass(frozen=True)
class CvArtifactRecord:
    """One `cv_artifacts` row, ready to render. Frozen: nothing mutates back."""

    id: int
    listing_id: int | None
    base_cv_version_id: int | None
    patch_json: dict[str, Any] | None
    change_log_json: list[Any] | None
    tex_path: str | None
    pdf_path: str | None
    tex_hash: str | None
    pdf_hash: str | None
    compiled_at: datetime | None
    compile_status: str
    compile_log: str | None
    verification_json: dict[str, Any] | None
    page_count: int | None
    ats_checks_json: Any
    backend: str | None
    provider: str | None
    model: str | None
    created_at: datetime


def _to_record(row: CvArtifact) -> CvArtifactRecord:
    """One ORM row as its frozen read value. The single mapping, so write and read
    cannot disagree about a field."""
    return CvArtifactRecord(
        id=int(row.id),
        listing_id=int(row.listing_id) if row.listing_id is not None else None,
        base_cv_version_id=(
            int(row.base_cv_version_id) if row.base_cv_version_id is not None else None
        ),
        patch_json=dict(row.patch_json) if isinstance(row.patch_json, dict) else row.patch_json,
        change_log_json=list(row.change_log_json)
        if isinstance(row.change_log_json, list)
        else row.change_log_json,
        tex_path=row.tex_path,
        pdf_path=row.pdf_path,
        tex_hash=row.tex_hash,
        pdf_hash=row.pdf_hash,
        compiled_at=row.compiled_at,
        compile_status=row.compile_status,
        compile_log=row.compile_log,
        verification_json=(
            dict(row.verification_json)
            if isinstance(row.verification_json, dict)
            else row.verification_json
        ),
        page_count=int(row.page_count) if row.page_count is not None else None,
        ats_checks_json=row.ats_checks_json,
        backend=row.backend,
        provider=row.provider,
        model=row.model,
        created_at=row.created_at,
    )


async def insert_artifact(
    session: AsyncSession,
    *,
    listing_id: int | None,
    base_cv_version_id: int | None,
    patch_json: dict[str, Any],
    change_log_json: list[Any],
    compile_status: str,
    verification_json: dict[str, Any],
    page_count: int | None,
    ats_checks_json: Any = None,
    tex_path: str | None = None,
    pdf_path: str | None = None,
    tex_hash: str | None = None,
    pdf_hash: str | None = None,
    compile_log: str | None = None,
    backend: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    now: datetime | None = None,
) -> CvArtifactRecord:
    """Insert exactly one `cv_artifacts` row and return it. Never commits.

    `compiled_at` is set only on an `ok` row: a blocked or failed compile never
    produced a PDF, so recording a compiled moment for one would be a lie.
    """
    if compile_status not in COMPILE_STATUSES:
        raise ValueError(
            f"unknown compile_status {compile_status!r}; expected one of {sorted(COMPILE_STATUSES)}"
        )

    moment = now if now is not None else datetime.now(UTC)
    row = CvArtifact(
        listing_id=int(listing_id) if listing_id is not None else None,
        base_cv_version_id=(int(base_cv_version_id) if base_cv_version_id is not None else None),
        patch_json=patch_json,
        change_log_json=change_log_json,
        tex_path=tex_path,
        pdf_path=pdf_path,
        tex_hash=tex_hash,
        pdf_hash=pdf_hash,
        compiled_at=moment if compile_status == "ok" else None,
        compile_status=compile_status,
        compile_log=compile_log,
        verification_json=verification_json,
        page_count=int(page_count) if page_count is not None else None,
        ats_checks_json=ats_checks_json,
        backend=backend,
        provider=provider,
        model=model,
        created_at=moment,
    )
    async with session.begin_nested():
        session.add(row)
        await session.flush()

    return _to_record(row)


async def latest_for_listing(
    session: AsyncSession, listing_id: int, *, ok_only: bool = True
) -> CvArtifactRecord | None:
    """The newest artifact for one listing, or `None`.

    Ordered `(created_at, id)` descending. When `ok_only` is true the
    `compile_status == "ok"` predicate is applied IN SQL, so a blocked or failed
    row is unreachable — this is D-118's access control. Never commits, never raises.
    """
    statement = select(CvArtifact).where(CvArtifact.listing_id == int(listing_id))
    if ok_only:
        statement = statement.where(CvArtifact.compile_status == "ok")
    statement = statement.order_by(CvArtifact.created_at.desc(), CvArtifact.id.desc()).limit(1)
    row = await session.scalar(statement)
    return _to_record(row) if row is not None else None


async def read_for_download(
    session: AsyncSession, artifact_id: int, *, ok_only: bool = True
) -> CvArtifactRecord | None:
    """One artifact by id, for a download/link/attach query, or `None`.

    When `ok_only` is true (the default) the `compile_status == "ok"` predicate is
    applied IN SQL, so a `blocked` or `failed` row is unreachable **even by id** —
    D-118's access control, and the contract Phase 7's attach path consumes. Never
    commits, never raises.
    """
    statement = select(CvArtifact).where(CvArtifact.id == int(artifact_id))
    if ok_only:
        statement = statement.where(CvArtifact.compile_status == "ok")
    row = await session.scalar(statement)
    return _to_record(row) if row is not None else None


async def history_for_listing(session: AsyncSession, listing_id: int) -> list[CvArtifactRecord]:
    """Every artifact for one listing, newest first (D-117's retained history)."""
    rows = (
        (
            await session.execute(
                select(CvArtifact)
                .where(CvArtifact.listing_id == int(listing_id))
                .order_by(CvArtifact.created_at.desc(), CvArtifact.id.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_to_record(row) for row in rows]


__all__ = [
    "COMPILE_STATUSES",
    "CvArtifactRecord",
    "history_for_listing",
    "insert_artifact",
    "latest_for_listing",
    "read_for_download",
]
