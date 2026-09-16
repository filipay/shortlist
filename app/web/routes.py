"""Server-rendered queue page, with the per-source health strip (SRC-07 / D-13).

The queue is the product and is queried unguarded; the health strip is
informational, so its two data sources (the source read model and the LLM backend)
degrade to an empty strip rather than taking the page down. Neither call touches a
job board — the live probe belongs to `/health`, and it is TTL-cached there.

The route is **thin**: every queue predicate, join and enrichment lives in
`app.db.repositories.queue_repo`, so there is exactly one place the queue SQL can be
changed and one place the FTS `MATCH` clause exists.

Two routes serve the queue, and they must render identically:

* `GET /` returns the whole page (search box, toggles, health strip);
* `GET /queue/list` returns only the fragment the search box and the toggles swap
  into `#queue-list`. The fragment is the same `queue_list.html` the page includes,
  so a swapped fragment and a freshly loaded page cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.config import settings
from app.db.repositories import state_repo
from app.db.repositories.queue_repo import QueuePage, QueueQuery, read_queue
from app.db.repositories.source_repo import SourceHealth, get_source_health
from app.db.session import get_session
from app.domain.models import User
from app.llm import get_llm_backend
from app.llm.base import LLMBackend

log = structlog.get_logger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

PAGE_TEMPLATE = "html/queue.html"
LIST_TEMPLATE = "html/queue_list.html"


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


def _flag(value: str | None) -> bool:
    """A checkbox-style parameter. Absent, empty and `"0"` are all false."""
    return value is not None and value.strip().casefold() not in {"", "0", "false", "no"}


def _int_or_none(value: str | None) -> int | None:
    """A tolerant integer parse: junk degrades to the default, never to a 500."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_queue_query(params: Mapping[str, str]) -> QueueQuery:
    """The query string as a `QueueQuery`.

    `limit` comes from `Settings.queue_page_size` and **never** from the request: a
    client-supplied page size is a self-inflicted deep scan (T-02-28). `offset` is
    clamped at zero, so a negative or junk value lands on the first page.
    """
    return QueueQuery(
        q=(params.get("q") or "").strip() or None,
        excluded=_flag(params.get("excluded")),
        hidden=_flag(params.get("hidden")),
        saved=_flag(params.get("saved")),
        scope_search_id=_int_or_none(params.get("scope")),
        offset=max(0, _int_or_none(params.get("offset")) or 0),
        limit=settings.queue_page_size,
    )


def _queue_context(page: QueuePage) -> dict[str, Any]:
    """The context both queue templates render from.

    `listings`/`count`/`is_empty` are kept because the Phase-1 queue page pinned
    them (`tests/api/test_run_trigger.py` asserts the rendered `"0 listings"` and
    `"No listings yet"`); `page` carries everything the fragment needs to rebuild
    its own Load-more URL.
    """
    return {
        "page": page,
        "listings": page.rows,
        "count": page.total,
        "is_empty": not page.rows,
    }


async def _read_queue_page(
    session: AsyncSession,
    params: Mapping[str, str],
    *,
    now: datetime,
    watermark: datetime | None,
) -> QueuePage:
    """Read one page at the given watermark. The caller owns any commit."""
    return await read_queue(
        session,
        query=parse_queue_query(params),
        now=now,
        stale_after_days=settings.stale_after_days,
        watermark=watermark,
    )


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
    now = datetime.now(UTC)
    watermark = await state_repo.get_watermark(session)
    page = await _read_queue_page(
        session, request.query_params, now=now, watermark=watermark
    )

    # The advance happens AFTER the read, so the render the user is looking at keeps
    # the badges it was rendered with. This is the only IMPLICIT advance in the whole
    # application — the other writer is the explicit `Mark all as seen` action.
    await state_repo.advance_watermark(session, now=now)
    await session.commit()

    source_health, reachable, version, error = await _health_strip(session, backend)

    return templates.TemplateResponse(
        request,
        PAGE_TEMPLATE,
        {
            **_queue_context(page),
            "user": user,
            "source_health": source_health,
            "opencode_reachable": reachable,
            "opencode_version": version,
            "opencode_error": error,
        },
    )


@router.get("/queue/list", response_class=HTMLResponse)
async def queue_list(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """The queue fragment the search box and the toggles swap into `#queue-list`.

    A fragment read does **not** advance the watermark: only opening the page
    (`GET /`) and the explicit `Mark all as seen` action do.
    """
    page = await _read_queue_page(
        session,
        request.query_params,
        now=datetime.now(UTC),
        watermark=await state_repo.get_watermark(session),
    )
    return templates.TemplateResponse(request, LIST_TEMPLATE, _queue_context(page))


@router.post("/queue/mark-seen", response_class=HTMLResponse)
async def queue_mark_seen(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Advance the watermark and return the refreshed queue fragment.

    The page is read **after** marking, so the new badges are already cleared in the
    fragment the user sees — otherwise `Mark all as seen` would look like a no-op
    until the next reload.
    """
    now = datetime.now(UTC)
    await state_repo.mark_all_seen(session, now=now)
    await session.commit()

    page = await _read_queue_page(session, request.query_params, now=now, watermark=now)
    return templates.TemplateResponse(request, LIST_TEMPLATE, _queue_context(page))


__all__ = ["parse_queue_query", "router"]
