"""The settings surface and the guarded data reset.

The reset is the only destructive route in the application, so its guards are explicit
and ordered: confirm token, no run in flight, no tracked work, a snapshot on disk, and
only then the deletes. It refuses rather than improvises at every step.

No auth in v1 (D-21) means no CSRF token is available; the type-to-confirm token plus
the automatic snapshot are this route's specific mitigation, and `POST` is required so
a link or a prefetch can never trigger it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.models import Base
from app.db.session import get_session
from app.domain.models import User
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
