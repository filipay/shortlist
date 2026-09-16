"""Run trigger and status polling (Pattern 5 + the HTMX 286 stop condition).

`POST /runs` creates the `runs` row, commits it, schedules the pipeline as a
background task and returns **202 with a status fragment immediately**. The
handler must never await the pipeline: a run takes tens of seconds even without
an LLM call, and a request that waits for it looks broken (AP6 / RUN-02).

`GET /runs/{id}/status` returns **HTTP 286** once the run is terminal — htmx's
documented "stop polling" signal. A poll with no stop condition is a silent
battery/latency leak that is invisible until the machine is on battery.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import current_user
from app.db.models import Run
from app.db.repositories import run_repo
from app.db.repositories.dupe_repo import (
    MergeRate,
    MergeRecord,
    list_merges,
    merge_rate,
    revert_merge,
)
from app.db.repositories.run_repo import RunDetail
from app.db.session import get_session, get_session_factory
from app.domain.models import User
from app.pipeline.run import TERMINAL_STATUSES, run_pipeline

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

#: The Merges audit page (D-29 / QUEUE-09). The table markup lives in a macro inside
#: this one template so the page and the revert fragment cannot drift apart.
MERGE_TEMPLATE = "html/merges.html"

#: The run-history page (D-43 / RUN-04). Its list and its detail expansion are two
#: macros in this one template, so both surfaces have exactly one definition.
RUN_TEMPLATE = "html/runs.html"

#: Strong references to in-flight run tasks, so the event loop cannot garbage
#: collect a fire-and-forget pipeline before it finishes.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


class RunFragmentSource(Protocol):
    """What `_run_status.html` actually reads.

    Deliberately structural: the ORM `Run` row and `run_repo.RunSummary` both satisfy
    it, which is what lets ONE renderer serve the run control's polling fragment and
    the queue's last-run strip (D-43) without a shim object or a second template.
    """

    @property
    def id(self) -> int: ...

    @property
    def status(self) -> str: ...

    @property
    def errors_json(self) -> object: ...


def render_run_fragment(
    request: Request, run: RunFragmentSource, source_counts: Mapping[str, Any] | None
) -> str:
    template = templates.get_template("html/_run_status.html")
    return template.render(request=request, run=run, sources=source_counts or {})


@router.post("/runs", response_class=HTMLResponse)
async def start_run(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> HTMLResponse:
    """Create the run row, enqueue the pipeline, return 202 with a fragment."""
    run = Run(
        search_id=None,
        trigger="manual",
        status="running",
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    # Enqueued, never awaited (AP6). The task owns its own sessions and updates
    # the row this handler just created (`run_id=`), so one trigger == one run.
    task = asyncio.create_task(run_pipeline("manual", None, session_factory, run_id=run.id))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    return HTMLResponse(
        render_run_fragment(request, run, None), status_code=202
    )


def render_run_detail(detail: RunDetail) -> str:
    """Render the `#run-detail-{id}` fragment from the macro in `runs.html`.

    The detail markup lives in a macro inside the page template, so the list and the
    expansion render from one definition. `Template.make_module` obtains the macro; it
    also runs the page body, which is why the same `runs` value the block needs is
    passed in (an empty list renders the empty state, harmlessly).
    """
    module = templates.get_template(RUN_TEMPLATE).make_module({"runs": []})
    return str(module.run_detail(detail=detail))


@router.get("/runs", response_class=HTMLResponse)
async def run_history(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """The run-history page: one row per run, newest first.

    Read-only by construction — the only mutating run route is `POST /runs`, which
    lives on the queue's run control and is unchanged (T-02-42).
    """
    runs = await run_repo.list_runs(session)
    return templates.TemplateResponse(
        request, RUN_TEMPLATE, {"runs": runs, "user": user}
    )


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail_route(
    run_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """The expansion fragment: counts, per-rule exclusions, criteria and the stage log.

    A separate request on purpose, so the list page never carries every run's log and
    the stage log stays collapsed until the user asks for it (T-02-44).
    """
    detail = await run_repo.get_run_detail(session, run_id=run_id)
    if detail is None:
        return HTMLResponse(
            f'<div id="run-detail-{int(run_id)}" class="run-detail" '
            f'data-error="unknown-run">Unknown run.</div>',
            status_code=404,
        )
    return HTMLResponse(render_run_detail(detail))


@router.get("/runs/{run_id}/status", response_class=HTMLResponse)
async def run_status(
    run_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """200 while the run is in flight; 286 once it is terminal."""
    run = await session.get(Run, run_id)
    if run is None:
        return HTMLResponse(
            '<div id="run-status">Unknown run.</div>', status_code=404
        )

    fragment = render_run_fragment(request, run, run.source_counts_json)
    if run.status in TERMINAL_STATUSES:
        return HTMLResponse(
            fragment, status_code=286, headers={"HX-Reswap": "outerHTML"}
        )
    return HTMLResponse(fragment)


def render_merges_table(
    merges: list[MergeRecord],
    rate: MergeRate,
    *,
    note: str | None = None,
) -> str:
    """Render the `#merges-table` fragment without rendering the whole page.

    The panel markup lives in a Jinja **macro** inside `merges.html`, so the page and
    the revert swap render from a single definition — there is no second copy of the
    markup to drift. `Template.make_module` is Jinja's API for obtaining a template's
    macros; it also runs the template body, and for an extending template that body is
    the `content` block. So the same three variables the block needs are passed in,
    which keeps `render_merges_table` working as long as `merges.html`'s page body
    only references `merges`, `rate` and `note` — the macro itself takes them
    explicitly and needs no request context, so both call sites escape identically.

    The rate sits **inside** the fragment root on purpose: reverting a merge moves the
    rate and the reverted count, so the swap must carry them or the page would show a
    stale number next to a fresh table (T-02-25).
    """
    module = templates.get_template(MERGE_TEMPLATE).make_module(
        {"merges": merges, "rate": rate, "note": note}
    )
    return str(module.merges_table(merges=merges, rate=rate, note=note))


@router.get("/merges", response_class=HTMLResponse)
async def merges_view(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """The merge audit page: the rate with its window named, and the rows behind it."""
    records = await list_merges(session)
    rate = await merge_rate(session)
    return templates.TemplateResponse(
        request,
        MERGE_TEMPLATE,
        {"merges": records, "rate": rate, "note": None, "user": user},
    )


@router.post("/merges/{dupe_id}/revert", response_class=HTMLResponse)
async def revert_merge_route(
    dupe_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Undo one merge and return the re-rendered panel for an `hx-swap` swap.

    The route owns the commit; the repository never commits (the `source_repo`
    contract). A not-found row answers 404 with a distinguishable body; an
    already-reverted row answers 200 with the current panel plus a note, so a double
    click is idempotent and its (absent) effect is legible rather than silent.
    """
    result = await revert_merge(session, dupe_id=dupe_id, now=datetime.now(UTC))

    if not result.found:
        return HTMLResponse(
            '<div id="merges-table">'
            '<p id="merges-note" class="merges-note">Unknown merge record.</p>'
            "</div>",
            status_code=404,
        )

    await session.commit()

    records = await list_merges(session)
    rate = await merge_rate(session)
    if result.wrote:
        note = (
            f"Merge #{dupe_id} reverted — {len(result.restored)} field(s) restored, "
            f"{len(result.skipped)} skipped."
        )
    else:
        note = f"Merge #{dupe_id} was already reverted."
    return HTMLResponse(render_merges_table(records, rate, note=note))


__all__ = [
    "render_merges_table",
    "render_run_detail",
    "render_run_fragment",
    "router",
]
