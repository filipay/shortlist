"""The settings surface and the guarded data reset.

The reset is the only destructive route in the application, so its guards are explicit
and ordered: confirm token, no run in flight, no tracked work, a snapshot on disk, and
only then the deletes. It refuses rather than improvises at every step.

No auth in v1 (D-21) means no CSRF token is available; the type-to-confirm token plus
the automatic snapshot are this route's specific mitigation, and `POST` is required so
a link or a prefetch can never trigger it.
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.searches import read_form
from app.db.models import Base, Run
from app.db.session import get_session
from app.domain.models import User
from app.pipeline.run import TERMINAL_STATUSES
from app.web.template_env import make_templates

log = structlog.get_logger(__name__)

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = make_templates(TEMPLATE_DIR)

SETTINGS_TEMPLATE = "html/settings.html"

#: The exact text the user must type. Case-sensitive on purpose: the point is a
#: deliberate act, not a habitual click.
RESET_CONFIRM_TOKEN = "DELETE"

#: Emptied by a reset, children first, so `foreign_keys=ON` holds at every step.
#: `companies` is here because it is derived from listings — leaving it behind only
#: creates orphans. `sources`, `searches`, `filter_rules` and `cv_versions` are
#: deliberately absent: `sources` is the board lookup the next run's upsert needs, and
#: the rest are the user's own configuration.
RESET_DELETE_ORDER: tuple[str, ...] = (
    "scores",
    "listing_exclusions",
    "listing_events",
    "listing_dupes",
    "listing_sources",
    "listings",
    "llm_calls",
    "source_request_log",
    "runs",
    "queue_state",
    "companies",
)

#: Shown on the page as kept.
RESET_KEPT_TABLES: tuple[str, ...] = ("searches", "filter_rules", "sources")

#: Tables that reference `listings` and are NOT deleted: a reset refuses while any of
#: them holds a row, so a later phase fails loudly instead of corrupting tracked work.
RESET_BLOCKING_TABLES: tuple[str, ...] = ("applications", "cv_artifacts")


async def _counts(session: AsyncSession) -> list[dict[str, Any]]:
    """Row counts for the page, one query per table (11 + 3, all trivial)."""
    rows: list[dict[str, Any]] = []
    for table in (*RESET_DELETE_ORDER, *RESET_KEPT_TABLES):
        count = await session.scalar(
            select(func.count()).select_from(Base.metadata.tables[table])
        )
        rows.append({"table": table, "count": int(count or 0)})
    return rows


async def _settings_context(
    session: AsyncSession,
    *,
    banner: str | None = None,
    error: bool = False,
) -> dict[str, Any]:
    backend = session.get_bind()
    database_path = Path(str(backend.url.database or ""))
    return {
        "banner": banner,
        "error": error,
        "counts": await _counts(session),
        "deleted_tables": RESET_DELETE_ORDER,
        "kept_tables": RESET_KEPT_TABLES,
        "backup_dir": str(database_path.parent / "reset-backups"),
        "confirm_token": RESET_CONFIRM_TOKEN,
    }


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """State exactly what a reset deletes, what it keeps, and how to recover."""
    return templates.TemplateResponse(
        request, SETTINGS_TEMPLATE, await _settings_context(session)
    )


class ResetRefused(Exception):
    """A guard declined the reset. Nothing has been deleted."""


def snapshot_database(*, db_path: Path, backups_dir: Path, moment: datetime) -> Path:
    """Copy the live database with `VACUUM INTO`. Returns the snapshot path.

    Runs on a plain SYNC `sqlite3` connection in autocommit: `VACUUM` cannot run inside
    a transaction, and the async engine would wrap it in one. `VACUUM INTO` is a single
    statement, it is WAL-safe, and it needs no new dependency.

    The destination is written as an escaped SQL literal rather than a bound parameter:
    `VACUUM INTO` takes an expression, and a literal removes any doubt about how the
    statement is prepared. The path is ours — a database directory plus a generated
    filename — and single quotes are doubled anyway.
    """
    backups_dir.mkdir(parents=True, exist_ok=True)
    destination = backups_dir / f"jobsearch-{moment.strftime('%Y%m%dT%H%M%SZ')}.db"
    if destination.exists():
        raise ResetRefused(f"snapshot target already exists: {destination.name}")

    literal = str(destination).replace("'", "''")
    connection = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        connection.execute(f"VACUUM INTO '{literal}'")
    finally:
        connection.close()
    return destination


async def _running_run_id(session: AsyncSession) -> int | None:
    return await session.scalar(
        select(Run.id).where(Run.status.not_in(tuple(TERMINAL_STATUSES))).limit(1)
    )


async def _blocking_row(session: AsyncSession) -> str | None:
    """The first blocking table that holds a row, or None."""
    for table in RESET_BLOCKING_TABLES:
        count = await session.scalar(
            select(func.count()).select_from(Base.metadata.tables[table])
        )
        if int(count or 0):
            return table
    return None


@router.post("/settings/reset", response_class=HTMLResponse)
async def reset_data(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Snapshot, then empty the corpus. Refuses at the first failed guard.

    The order is the whole safety property: every refusal happens before the first
    DELETE, and the snapshot happens before it too. A snapshot taken after the deletes
    would be worthless.
    """
    form = await read_form(request)
    confirm = str(form.get("confirm") or "").strip()
    if confirm != RESET_CONFIRM_TOKEN:
        return templates.TemplateResponse(
            request,
            SETTINGS_TEMPLATE,
            await _settings_context(
                session,
                banner=f"Nothing was deleted: type {RESET_CONFIRM_TOKEN} exactly to confirm.",
                error=True,
            ),
            status_code=400,
        )

    running_id = await _running_run_id(session)
    if running_id is not None:
        return templates.TemplateResponse(
            request,
            SETTINGS_TEMPLATE,
            await _settings_context(
                session,
                banner=f"Nothing was deleted: run {running_id} is still in flight.",
                error=True,
            ),
            status_code=409,
        )

    blocking = await _blocking_row(session)
    if blocking is not None:
        return templates.TemplateResponse(
            request,
            SETTINGS_TEMPLATE,
            await _settings_context(
                session,
                banner=(
                    f"Nothing was deleted: {blocking} holds tracked work. "
                    "Clear it in a later phase before resetting."
                ),
                error=True,
            ),
            status_code=409,
        )

    database_path = Path(str(session.get_bind().url.database or ""))
    try:
        snapshot = await asyncio.to_thread(
            snapshot_database,
            db_path=database_path,
            backups_dir=database_path.parent / "reset-backups",
            moment=datetime.now(UTC),
        )
    except (ResetRefused, sqlite3.Error, OSError) as exc:
        log.warning("reset.snapshot_failed", error=str(exc))
        return templates.TemplateResponse(
            request,
            SETTINGS_TEMPLATE,
            await _settings_context(
                session,
                banner=f"Nothing was deleted: the snapshot failed ({exc}).",
                error=True,
            ),
            status_code=500,
        )

    for table in RESET_DELETE_ORDER:
        await session.execute(delete(Base.metadata.tables[table]))
    await session.commit()

    log.info("reset.completed", snapshot=snapshot.name)
    return templates.TemplateResponse(
        request,
        SETTINGS_TEMPLATE,
        await _settings_context(
            session,
            banner=f"Queue data deleted. Snapshot: {snapshot.name}.",
        ),
    )
