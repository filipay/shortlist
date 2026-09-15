"""Server-rendered queue page, with the per-source health strip (SRC-07 / D-13).

The queue is the product and is queried unguarded; the health strip is
informational, so its two data sources (the source read model and the LLM backend)
degrade to an empty strip rather than taking the page down. Neither call touches a
job board — the live probe belongs to `/health`, and it is TTL-cached there.
"""

from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.models import Listing, ListingSource
from app.db.repositories.source_repo import SourceHealth, get_source_health
from app.db.session import get_session
from app.domain.models import User
from app.llm import get_llm_backend
from app.llm.base import LLMBackend

log = structlog.get_logger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


async def _health_strip(
    session: AsyncSession, backend: LLMBackend
) -> tuple[list[SourceHealth], bool, str | None, str | None]:
    """`(rows, reachable, version, error)` — never raises, never probes a board."""
    try:
        rows = await get_source_health(session)
    except Exception as exc:  # noqa: BLE001 — decorative data must not 500 the page
        log.warning("queue.health_read_failed", error=type(exc).__name__)
        rows = []

    try:
        outcome = await backend.health()
    except Exception as exc:  # noqa: BLE001 — ditto
        log.warning("queue.llm_health_failed", error=type(exc).__name__)
        return rows, False, None, type(exc).__name__

    return rows, bool(outcome.reachable), outcome.version, outcome.error


@router.get("/", response_class=HTMLResponse)
async def queue(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    backend: LLMBackend = Depends(get_llm_backend),
) -> HTMLResponse:
    """Render the persisted queue plus an empty state and the health strip.

    Desktop-first by explicit scoping decision (D-16); the phone-first layout
    pass is Phase 8.
    """
    rows = (
        await session.execute(
            select(Listing, ListingSource.source)
            .join(ListingSource, ListingSource.listing_id == Listing.id, isouter=True)
            .order_by(Listing.first_seen_at.desc(), Listing.id.desc())
        )
    ).all()

    by_id: dict[int, dict[str, object]] = {}
    for listing, source in rows:
        entry = by_id.setdefault(
            listing.id,
            {
                "id": listing.id,
                "title": listing.title,
                "company": listing.company_norm or "",
                "location": listing.location_raw or "",
                "sources": [],
                "posted": listing.posted_at.isoformat() if listing.posted_at else "",
                "first_seen": (
                    listing.first_seen_at.isoformat() if listing.first_seen_at else ""
                ),
            },
        )
        if source:
            entry["sources"].append(source)  # type: ignore[union-attr]

    listings = list(by_id.values())
    for entry in listings:
        sources = sorted(set(entry["sources"]))  # type: ignore[arg-type]
        entry["source"] = ", ".join(sources)

    source_health, reachable, version, error = await _health_strip(session, backend)

    return templates.TemplateResponse(
        request,
        "html/queue.html",
        {
            "listings": listings,
            "count": len(listings),
            "is_empty": len(listings) == 0,
            "user": user,
            "source_health": source_health,
            "opencode_reachable": reachable,
            "opencode_version": version,
            "opencode_error": error,
        },
    )
