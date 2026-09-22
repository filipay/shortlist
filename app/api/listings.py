"""The job detail page (UI-02 / D-96).

One route, one page: the score, the per-factor breakdown with each factor's weight,
the grounded rationale, and the requirement-by-requirement fit list with named gaps.
It reuses `queue_repo.read_row` — the same enrichment the queue row uses — so the
detail page and the row cannot drift, and `score_repo` for the stored score.

**The total is never recomputed here.** It arrives on `row.total_score`, already
derived at read time from the stored sub-scores under the weights CURRENTLY in force
(D-100). The route reads the weights only so the page can show each factor's weight.

The identity seam is universal (`user: User = Depends(current_user)`), and an unknown
id returns a small 404 HTML fragment carrying `data-error="unknown-listing"` rather
than a bare JSON 404, matching the events route's convention.

Jinja autoescape is the only escaping: the title, company, location and the model's
stored rationale all derive from untrusted listing text, and nothing here is ever
marked safe.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.config import settings
from app.db.repositories import ranking_config_repo, score_repo, state_repo
from app.db.repositories.queue_repo import QueueQuery, read_row
from app.db.session import get_session
from app.domain import rubric
from app.domain.models import User
from app.web.template_env import make_templates

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = make_templates(TEMPLATE_DIR)

#: The full detail page. A page, not a fragment: the breakdown is rich and Phase 6's
#: CV preview is expected to hang off this same surface (D-96).
DETAIL_TEMPLATE = "html/listing_detail.html"


def _flag(value: str | None) -> bool:
    """A checkbox-style parameter. Absent, empty and `"0"` are all false."""
    return value is not None and value.strip().casefold() not in {"", "0", "false", "no"}


def _not_found() -> HTMLResponse:
    """A small HTML fragment, not a bare JSON 404 — the events route's convention."""
    return HTMLResponse(
        '<div class="detail-empty" data-error="unknown-listing">Unknown listing.</div>',
        status_code=404,
    )


@router.get("/listings/{listing_id}", response_class=HTMLResponse)
async def listing_detail(
    listing_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """The full detail page for one listing, or the 404 fragment for an unknown id.

    The listing is resolved through `queue_repo.read_row`, so the flags, badges,
    source links and the read-time total all come from the one queue code path.
    """
    query = QueueQuery(excluded=_flag(request.query_params.get("excluded")))
    row = await read_row(
        session,
        listing_id=listing_id,
        query=query,
        now=datetime.now(UTC),
        stale_after_days=settings.stale_after_days,
        watermark=await state_repo.get_watermark(session),
    )
    if row is None:
        return _not_found()

    score = await score_repo.read_score_for_listing(session, listing_id=listing_id)
    weights = await ranking_config_repo.read_weights(session)
    # The ordered (key, label) pairs the factor table renders, in rubric.FACTORS order.
    factors = tuple((key, rubric.FACTOR_LABELS[key]) for key in rubric.FACTORS)

    return templates.TemplateResponse(
        request,
        DETAIL_TEMPLATE,
        {
            "row": row,
            "score": score,
            "weights": weights,
            "factors": factors,
            "queue_query": query.query_string(),
            "user": user,
        },
    )


__all__ = ["router"]
