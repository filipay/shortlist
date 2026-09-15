"""Server-rendered queue page."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.models import Listing, ListingSource
from app.db.session import get_session
from app.domain.models import User

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


@router.get("/", response_class=HTMLResponse)
async def queue(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Render the persisted queue plus an empty state.

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

    return templates.TemplateResponse(
        request,
        "html/queue.html",
        {
            "listings": listings,
            "count": len(listings),
            "is_empty": len(listings) == 0,
            "user": user,
        },
    )
