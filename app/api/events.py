"""The listing-event write surface (QUEUE-08 / D-41).

Save and Hide are **distinct** actions with distinct event types (`save`/`unsave` and
`hide`/`unhide`). One never implies the other: the projection tracks them independently
and the row renders two separately-labelled controls, so the user can always tell which
one they performed (T-02-39).

This is the only writer of `listing_events`, and it only ever INSERTs. The Phase-1
triggers refuse an UPDATE or a DELETE at the database, and
`app.db.repositories.event_repo` exposes no such call, so an "undo" is always another
append rather than an edit.

The POST returns the `_listing_row.html` fragment for the affected listing, so an
`hx-post` swaps exactly one row in place. Two properties are deliberate:

* `occurred_at` is **server-side** — the route never reads a timestamp from the form, so
  an event's time cannot be forged (T-02-37);
* the row is re-resolved through `queue_repo.read_row`, the same enrichment the page
  uses, so a swapped row cannot render differently from the row it replaces.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.searches import read_form
from app.config import settings
from app.db.models import Listing
from app.db.repositories import event_repo, state_repo
from app.db.repositories.queue_repo import QueueQuery, read_row
from app.db.session import get_session
from app.domain.models import User
from app.web.template_env import make_templates

log = structlog.get_logger(__name__)

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = make_templates(TEMPLATE_DIR)

#: The row partial, re-rendered as the swap target. The queue renders the same file,
#: so there is one rendering path and not two (T-02-38).
ROW_TEMPLATE = "html/_listing_row.html"

#: Which surface the action came from — a small MACHINE fact, never listing text.
ACTION_CONTEXT: dict[str, str] = {"surface": "queue"}


def _flag(value: str | None) -> bool:
    """A checkbox-style parameter. Absent, empty and `"0"` are all false."""
    return value is not None and value.strip().casefold() not in {"", "0", "false", "no"}


def _error_row(
    listing_id: int, *, reason: str, message: str, status_code: int
) -> HTMLResponse:
    """A fragment carrying the row id, so a mis-targeted swap cannot empty the DOM.

    `listing_id` is an `int` path parameter, so nothing here can inject markup.
    """
    return HTMLResponse(
        f'<tr id="listing-row-{int(listing_id)}" class="listing-row listing-error" '
        f'data-error="{reason}"><td colspan="7">{message}</td></tr>',
        status_code=status_code,
    )


@router.post("/listings/{listing_id}/events", response_class=HTMLResponse)
async def append_listing_event(
    listing_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Append one event and swap the affected row back.

    422 for an event type outside `event_repo.EVENT_TYPES` (the allow-list that mirrors
    the database CHECK) and 404 for an unknown listing — both **before** any write, so a
    rejected request appends nothing.
    """
    # `read_form` parses the urlencoded body with the standard library: this project
    # deliberately does not depend on `python-multipart`, which Starlette's
    # `request.form()` requires for any form parsing at all.
    form = await read_form(request)
    event_type = str(form.get("event_type") or "").strip()

    if event_type not in event_repo.EVENT_TYPES:
        return _error_row(
            listing_id,
            reason="unknown-event-type",
            message="Unknown action.",
            status_code=422,
        )

    listing = await session.get(Listing, listing_id)
    if listing is None:
        # Rejected ahead of the insert: the FK would raise anyway, and a 500 is not an
        # answer the user can act on.
        return _error_row(
            listing_id,
            reason="unknown-listing",
            message="Unknown listing.",
            status_code=404,
        )

    await event_repo.append_event(
        session,
        listing_id=listing_id,
        event_type=event_type,
        now=datetime.now(UTC),
        context=ACTION_CONTEXT,
    )
    await session.commit()

    # `excluded` rides on the action URL so the swapped row keeps the exclusion column
    # the user is currently looking at. A predicate swap is not a visit, so nothing here
    # touches the watermark; it is only READ, so the `new` badge matches the queue.
    query = QueueQuery(excluded=_flag(request.query_params.get("excluded")))
    row = await read_row(
        session,
        listing_id=listing_id,
        query=query,
        now=datetime.now(UTC),
        stale_after_days=settings.stale_after_days,
        watermark=await state_repo.get_watermark(session),
    )
    if row is None:  # pragma: no cover — the listing was fetched a moment ago
        return _error_row(
            listing_id,
            reason="unknown-listing",
            message="Unknown listing.",
            status_code=404,
        )

    log.info("listing_event.appended", listing_id=listing_id, event_type=event_type)
    # `queue_query` is what the partial builds the action URL from. It is passed
    # explicitly (not inferred) so the swapped row keeps the exact predicate set
    # the page is showing — dropping it would strip `?excluded=1` from the form,
    # and a second click would then render a row without the exclusion column.
    return templates.TemplateResponse(
        request,
        ROW_TEMPLATE,
        {
            "row": row,
            "show_excluded": query.excluded,
            "queue_query": query.query_string(),
        },
    )


__all__ = ["router"]
