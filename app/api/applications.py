"""The `/applications` tracker (D-128 … D-135).

Five routes over the existing `applications` / `application_events` schema:

* ``GET /applications`` — the tracker page shell.
* ``GET /applications/list`` — the same table fragment the page embeds, so a swap
  cannot drift from the page (one definition, the `queue_list.html` pattern).
* ``POST /applications/record`` — record one application and its single `created`
  event. The `applied` stage requires an `ok` artefact (D-129).
* ``GET /applications/{application_id}/history`` — the inline timeline partial.
* ``POST /applications/{application_id}/status`` — a guided transition (Task 2).
* ``POST /applications/{application_id}`` — the notes/next-action edit (Task 3).

REGISTRATION ORDER IS LOAD-BEARING: ``POST /applications/record`` is declared
BEFORE every dynamic ``POST /applications/{application_id}`` route, because FastAPI
matches in declaration order and a dynamic route registered first would capture
``/applications/record`` with ``application_id="record"`` and 422.

Every route declares the identity seam (``user: User = Depends(current_user)``).
Jinja autoescape is the only escaping: listing titles, companies and notes are
untrusted form/stored text and are rendered as text, never marked safe.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.searches import read_form
from app.db.models import Listing
from app.db.repositories import application_repo
from app.db.session import get_session
from app.domain.models import User
from app.web.template_env import make_templates

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = make_templates(TEMPLATE_DIR)

PAGE_TEMPLATE = "html/applications.html"
LIST_TEMPLATE = "html/applications_list.html"
ROW_TEMPLATE = "html/_application_row.html"
HISTORY_TEMPLATE = "html/_application_history.html"


def _optional_int(value: Any) -> int | None:
    """A whole number from a form field, or `None` — never a raised conversion error."""
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    """A non-empty form string, or `None`. An empty field is a missing one."""
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def _error_fragment(reason: str, message: str, status_code: int) -> HTMLResponse:
    """A small `data-error` HTML fragment, the app's refusal convention."""
    return HTMLResponse(
        f'<p class="detail-empty" data-error="{html.escape(reason)}">{html.escape(message)}</p>',
        status_code=status_code,
    )


def _row_error(
    application_id: int, *, reason: str, message: str, status_code: int
) -> HTMLResponse:
    """A `<tr>` carrying the row id, so a mis-targeted ``outerHTML`` swap cannot empty the DOM."""
    return HTMLResponse(
        f'<tr id="application-row-{int(application_id)}" '
        f'class="listing-row listing-error" data-error="{html.escape(reason)}">'
        f'<td colspan="6">{html.escape(message)}</td></tr>',
        status_code=status_code,
    )


async def _list_context(session: AsyncSession) -> dict[str, Any]:
    """The shared tracker fragment context, so the page and the list swap cannot drift."""
    rows = await application_repo.read_tracker(session, now=datetime.now(UTC))
    return {
        "rows": rows,
        "count": len(rows),
        "is_empty": not rows,
        "statuses": application_repo.APPLICATION_STATUSES,
        "now": datetime.now(UTC),
    }


@router.get("/applications", response_class=HTMLResponse)
async def applications_page(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """The tracker page shell, embedding the shared list fragment."""
    return templates.TemplateResponse(request, PAGE_TEMPLATE, await _list_context(session))


@router.get("/applications/list", response_class=HTMLResponse)
async def applications_list(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """The tracker table fragment, for the in-place `hx-get` swap."""
    return templates.TemplateResponse(request, LIST_TEMPLATE, await _list_context(session))


# NOTE: declared BEFORE every dynamic `POST /applications/{application_id}` route.
@router.post("/applications/record", response_class=HTMLResponse)
async def record_application_route(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Record one application and its single `created` event, then re-render the table.

    An unknown listing or a refused `applied` (no `ok` artefact) returns a `data-error`
    fragment and writes nothing. `applied_at` is stamped server-side (D-130); it is
    never read from the form.
    """
    form = await read_form(request)

    listing_id = _optional_int(form.get("listing_id"))
    if listing_id is None:
        return _error_fragment("unknown-listing", "Unknown listing.", 422)
    listing = await session.get(Listing, listing_id)
    if listing is None:
        return _error_fragment("unknown-listing", "Unknown listing.", 404)

    status = str(form.get("status") or "discovered").strip()
    if status not in application_repo.APPLICATION_STATUSES:
        return _error_fragment("unknown-status", "Unknown stage.", 422)

    new_id = await application_repo.record_application(
        session,
        listing_id=listing_id,
        status=status,
        cv_artifact_id=_optional_int(form.get("cv_artifact_id")),
        notes=_text(form.get("notes")),
        next_action_at=application_repo.parse_next_action(form.get("next_action_at")),
        now=datetime.now(UTC),
    )
    if new_id is None:
        return _error_fragment(
            "applied-needs-ok-artifact",
            "Record a verified CV first — there is no verified CV to link to this application.",
            409,
        )
    await session.commit()
    return templates.TemplateResponse(request, LIST_TEMPLATE, await _list_context(session))


@router.get("/applications/{application_id}/history", response_class=HTMLResponse)
async def application_history(
    application_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """The inline timeline partial: every event, chronological, `from → to` + note."""
    record = await application_repo.read_application(session, application_id)
    if record is None:
        return _error_fragment("unknown-application", "Unknown application.", 404)
    events = await application_repo.read_history(session, application_id)
    return templates.TemplateResponse(
        request, HISTORY_TEMPLATE, {"events": events, "count": len(events)}
    )


@router.post("/applications/{application_id}/status", response_class=HTMLResponse)
async def transition_application_route(
    application_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Move one application to a stage, appending exactly one event, and swap the row.

    The `applied` stage requires an `ok` artefact (D-118/D-129); a missing or non-`ok`
    `cv_artifact_id` is a 4xx `data-error` fragment re-rendered in the row slot and
    writes NOTHING — no status change, no event. `applied_at` is stamped server-side
    (D-130), never read from the form.
    """
    form = await read_form(request)

    to_status = str(form.get("status") or "").strip()
    if to_status not in application_repo.APPLICATION_STATUSES:
        return _row_error(
            application_id, reason="unknown-status", message="Unknown stage.", status_code=422
        )

    record = await application_repo.read_application(session, application_id)
    if record is None:
        return _row_error(
            application_id,
            reason="unknown-application",
            message="Unknown application.",
            status_code=404,
        )

    new_id = await application_repo.transition_application(
        session,
        application_id=application_id,
        to_status=to_status,
        cv_artifact_id=_optional_int(form.get("cv_artifact_id")),
        note=_text(form.get("note")),
        now=datetime.now(UTC),
    )
    if new_id is None:
        return _row_error(
            application_id,
            reason="applied-needs-ok-artifact",
            message=(
                "Record a verified CV first — there is no verified CV to link to "
                "this application."
            ),
            status_code=409,
        )

    await session.commit()
    updated = await application_repo.read_application(
        session, application_id, now=datetime.now(UTC)
    )
    return templates.TemplateResponse(
        request, ROW_TEMPLATE, {"row": updated, "statuses": application_repo.APPLICATION_STATUSES}
    )


# NOTE: still AFTER `POST /applications/record` — the dynamic path must never
# shadow the static `/applications/record` path (declaration-order matching).
@router.post("/applications/{application_id}", response_class=HTMLResponse)
async def update_application_route(
    application_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Edit notes and the next-action date in place — NO event is appended (D-135).

    These are ordinary mutable columns; only a status change is an append-only event.
    An absent/blank `next_action_at` clears it. Never trusts a form clock for
    `applied_at`/`occurred_at`.
    """
    form = await read_form(request)

    updated_id = await application_repo.update_application(
        session,
        application_id=application_id,
        notes=_text(form.get("notes")),
        next_action_at=application_repo.parse_next_action(form.get("next_action_at")),
        now=datetime.now(UTC),
    )
    if updated_id is None:
        return _row_error(
            application_id,
            reason="unknown-application",
            message="Unknown application.",
            status_code=404,
        )

    await session.commit()
    updated = await application_repo.read_application(
        session, application_id, now=datetime.now(UTC)
    )
    return templates.TemplateResponse(
        request, ROW_TEMPLATE, {"row": updated, "statuses": application_repo.APPLICATION_STATUSES}
    )


__all__ = ["router"]
