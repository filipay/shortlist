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
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import current_user
from app.db.models import Run
from app.db.session import get_session, get_session_factory
from app.domain.models import User
from app.pipeline.run import TERMINAL_STATUSES, run_pipeline

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

#: Strong references to in-flight run tasks, so the event loop cannot garbage
#: collect a fire-and-forget pipeline before it finishes.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def render_run_fragment(request: Request, run: Run, source_counts: dict | None) -> str:
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


__all__ = ["render_run_fragment", "router"]
