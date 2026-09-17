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
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from markupsafe import Markup
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.runs import render_run_fragment
from app.config import settings
from app.db.repositories import event_repo, run_repo, state_repo
from app.db.repositories.queue_repo import QueuePage, QueueQuery, read_queue
from app.db.repositories.run_repo import RunSummary
from app.db.repositories.source_repo import SourceHealth, get_source_health
from app.db.session import get_session
from app.domain.models import User
from app.llm import get_llm_backend
from app.llm.base import LLMBackend
from app.web.template_env import make_templates

log = structlog.get_logger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

router = APIRouter()
templates = make_templates(TEMPLATE_DIR)

PAGE_TEMPLATE = "html/queue.html"
LIST_TEMPLATE = "html/queue_list.html"

#: Dismiss's hard CEILING, not a page size: `_queued_listing_ids` pages through the
#: queue until it has every matched id, and refuses the whole action (writing nothing)
#: when the match count exceeds this. 10_000 is far above any real queue.
_DISMISS_LIMIT = 10_000

#: Which surface a bulk dismissal came from — a small MACHINE fact, never listing
#: text (mirrors `app.api.events.ACTION_CONTEXT`, which tags a per-listing hide as
#: `surface="queue"`). This is what keeps the two kinds of hide distinguishable in
#: the append-only audit log even though both append the same event KIND.
_DISMISS_CONTEXT: dict[str, str] = {"surface": "queue_dismiss"}


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


def _dismiss_over_limit() -> HTMLResponse:
    """Refuse a whole-queue dismissal that exceeds `_DISMISS_LIMIT`.

    Follows the app's existing refused-action convention (`app.api.events._error_row`,
    `app.api.runs`): a 4xx status plus a small HTML fragment carrying a machine-readable
    `data-error` reason. Nothing is written, so a refused dismissal is never partial.
    `empty-state` is an existing class, so no stylesheet rule is needed.
    """
    return HTMLResponse(
        '<p class="empty-state" id="queue-dismiss-error" '
        'data-error="dismiss-over-limit">'
        "Too many listings to dismiss at once. Narrow the queue with a filter and try "
        "again."
        "</p>",
        status_code=400,
    )


async def _queued_listing_ids(
    session: AsyncSession, params: Mapping[str, str], *, now: datetime
) -> list[int] | None:
    """Every id the current predicate matches, or `None` when the queue is too large.

    Dismiss is a whole-queue action, so it must not inherit the page limit the
    fragment uses: this pages through `read_queue` until it has collected every
    matched id. The predicate is the shared `parse_queue_query`, so it cannot drift
    from what the table shows, with two deliberate exceptions — the free-text search
    is dropped (a dismissal scoped to typed text would be ambiguous) and the hidden
    toggle is forced off (an already-hidden listing must not gain a second event).

    `_DISMISS_LIMIT` is a hard ceiling, not a page size. Above it the caller must
    abort without committing, which the `None` return signals: a "Dismiss all" that
    silently stopped at the cap would be a lie.
    """
    query = parse_queue_query(params)
    base = replace(query, q=None, hidden=False, offset=0)
    ids: list[int] = []
    offset = 0
    while True:
        page = await read_queue(
            session,
            query=replace(base, offset=offset),
            now=now,
            stale_after_days=settings.stale_after_days,
            watermark=await state_repo.get_watermark(session),
        )
        if page.total > _DISMISS_LIMIT:
            return None
        ids.extend(row.id for row in page.rows)
        if not page.rows or offset + len(page.rows) >= page.total:
            return ids
        offset += len(page.rows)


async def _last_run_strip(
    request: Request, session: AsyncSession
) -> tuple[RunSummary | None, Markup | None]:
    """`(latest run, its pre-rendered fragment)` — never raises.

    A decorative strip must not 500 the product page (the same rule `_health_strip`
    follows), so any failure yields `(None, None)` and the queue simply renders without
    a strip.

    The fragment is produced by `render_run_fragment` from `app/api/runs.py`, which
    renders the existing `_run_status.html` — so the queue strip and the run control's
    polling fragment are one renderer and one partial, never a parallel copy (D-43).
    `RunSummary` exposes the `errors_json` name that partial reads, so the renderer
    needs no shim.

    It is wrapped in `Markup` because it IS markup: Jinja would otherwise escape the
    whole fragment into visible text. `Markup` keeps the escaping decision in Python,
    where it was made by the renderer, and keeps the template free of a safe-marking
    filter — so the "no `|safe`" rule holds without an exception.
    """
    try:
        runs = await run_repo.list_runs(session, limit=1)
        latest = runs[0] if runs else None
        if latest is None:
            return None, None
        # The RENDER is inside the guard too: the docstring promises this is
        # decorative, and a hand-edited/older `stage_log_json` the partial cannot
        # traverse must not 500 the product page.
        fragment = Markup(render_run_fragment(request, latest, latest.sources))
    except Exception as exc:  # noqa: BLE001 — decorative data must not 500 the queue
        log.warning("queue.last_run_read_failed", error=type(exc).__name__)
        return None, None
    return latest, fragment


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

    last_run, last_run_fragment = await _last_run_strip(request, session)
    source_health, reachable, version, error = await _health_strip(session, backend)

    return templates.TemplateResponse(
        request,
        PAGE_TEMPLATE,
        {
            **_queue_context(page),
            "user": user,
            "last_run": last_run,
            "last_run_fragment": last_run_fragment,
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


@router.post("/queue/dismiss", response_class=HTMLResponse)
async def queue_dismiss(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Hide every listing the user can currently see, and return the empty fragment.

    Scope is the queue predicate with the free-text search dropped and the hidden
    toggle forced off: what the user would see with an empty search box and the
    default toggles. It is deliberately NOT "every row in `listings`" — an
    already-hidden listing must not gain a second event, and an absorbed merge twin
    must never be dismissed. If the matched set exceeds `_DISMISS_LIMIT` the action is
    refused outright and nothing is committed.

    The page is read AFTER the write, so the returned fragment already shows the empty
    queue; otherwise Dismiss would look like a no-op until the next reload.
    """
    now = datetime.now(UTC)
    ids = await _queued_listing_ids(session, request.query_params, now=now)
    if ids is None:
        return _dismiss_over_limit()
    if ids:
        await event_repo.hide_listings(
            session,
            listing_ids=ids,
            occurred_at=now,
            context=_DISMISS_CONTEXT,
        )
        await session.commit()

    refreshed = await _read_queue_page(
        session,
        request.query_params,
        now=now,
        watermark=await state_repo.get_watermark(session),
    )
    return templates.TemplateResponse(request, LIST_TEMPLATE, _queue_context(refreshed))


__all__ = ["parse_queue_query", "router"]
