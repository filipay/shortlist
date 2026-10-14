"""The `/status` health page (RUN-07 / D-155 .. D-158).

Two rules this page is built on, and neither is negotiable:

* **It reads the database only and never contacts a job board (D-156).** The
  source badge is computed from recorded run outcomes and recorded stop signals;
  the live probe stays an explicit operator action on the JSON endpoint. A page
  view that put a request on a board would be the scrape this project exists not
  to be (T-08-17).
* **It is a decorative read that never raises (D-08).** A degraded dependency, a
  broken database read, a missing scheduler or an absent verdict is REPORTED as
  data, so the page always answers rather than 500-ing (T-08-20).

WHY `/status` AND NOT `/health`: the JSON endpoint is pinned at `/health` by 25
`.json()` assertions, `tests/test_auth_seam.py`'s route inventory and
`scripts/compose-smoke.sh`. FastAPI matches routes in declaration order, so a page
route that also declared `/health` would shadow it; the page takes its own path and
keeps the nav label `Health`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.health import dependency_report
from app.config import settings
from app.db.repositories.source_repo import get_source_health
from app.db.session import get_session
from app.domain.models import User
from app.latex import get_latex_engine
from app.latex.base import LatexEngine
from app.llm import auth_configured, get_llm_backend
from app.llm.base import LLMBackend
from app.pipeline.rank import CV_FILENAME
from app.web.template_env import make_templates

log = structlog.get_logger(__name__)

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = make_templates(TEMPLATE_DIR)

HEALTH_TEMPLATE = "html/health.html"

#: The page's own path. It must not be `/health`: FastAPI is first-match-wins and
#: `/health` is pinned as JSON by the existing assertions and the compose smoke
#: script (see the module docstring).
HEALTH_PAGE_PATH = "/status"


def dependency_report_failed(error: str) -> dict[str, Any]:
    """The all-degraded dependency report, carrying an exception CLASS NAME only.

    `dependency_report` is itself total, so this is the insurance policy for the
    one case it cannot cover: assembly raising before any probe ran. Mirroring the
    probes' own convention, `error` is the class name and never a message, so no
    upstream content can reach the page (T-08-18).
    """
    return {
        "db": "unreachable",
        "opencode": {
            "reachable": False,
            "version": None,
            "error": error,
            "auth_configured": auth_configured(),
        },
        "tectonic": {"available": False, "version": None, "error": error},
        "cv": {
            "available": False,
            "path": str(Path(settings.cv_dir) / CV_FILENAME),
            "error": error,
        },
    }


def _opencode_detail(opencode: dict[str, Any]) -> str:
    """The LLM-backend row's detail text.

    `auth_configured` is INERT with respect to the badge and to `status`; it only
    selects the honest wording for an unreachable backend (D-08 / UI-SPEC §Color).
    """
    if opencode["reachable"]:
        version = opencode.get("version")
        return f"reachable — version {version}" if version else "reachable"
    if not opencode.get("auth_configured"):
        return "no server password configured"
    return f"unreachable ({opencode['error']})" if opencode.get("error") else "unreachable"


def _tectonic_detail(tectonic: dict[str, Any]) -> str:
    """The LaTeX-engine row's detail text."""
    if not tectonic["available"]:
        return f"not available ({tectonic['error']})" if tectonic.get("error") else "not available"
    version = tectonic.get("version")
    return f"available — version {version}" if version else "available"


def _dependency_rows(report: dict[str, Any]) -> list[dict[str, str]]:
    """The four system-section rows: label, badge tone and detail text.

    The tones are the shipped `_health_strip.html` vocabulary, so no new colour
    token is needed. A missing CV fact store reads `unknown` and never degrades
    `status` (D-08).
    """
    opencode = report["opencode"]
    tectonic = report["tectonic"]
    cv = report["cv"]
    if cv["available"]:
        cv_detail = f"loaded from {cv['path']}"
    else:
        cv_detail = (
            f"no readable CV fact store at {cv['path']} — "
            "ranking is skipped until one is supplied."
        )
    return [
        {
            "label": "Database",
            "tone": "ok" if report["db"] == "ok" else "unreachable",
            "detail": report["db"],
        },
        {
            "label": "LLM backend",
            "tone": "ok" if opencode["reachable"] else "unreachable",
            "detail": _opencode_detail(opencode),
        },
        {
            "label": "LaTeX engine",
            "tone": "ok" if tectonic["available"] else "unreachable",
            "detail": _tectonic_detail(tectonic),
        },
        {
            "label": "CV fact store",
            "tone": "ok" if cv["available"] else "unknown",
            "detail": cv_detail,
        },
    ]


async def page_context(
    session: AsyncSession, backend: LLMBackend, engine: LatexEngine
) -> dict[str, Any]:
    """The page's whole context. Total: every read degrades rather than raising.

    The dependency report is the SAME builder the JSON endpoint calls, so the two
    surfaces cannot disagree about opencode reachability or `auth_configured`
    (D-138). The context names the `_health_strip.html` partial reads are supplied
    here unchanged, which is what lets the page include the queue's partial
    verbatim instead of a parallel copy (D-155).
    """
    try:
        report = await dependency_report(session, backend, engine)
    except Exception as exc:  # noqa: BLE001 — the page must answer in every case (D-08)
        log.warning("health_page.dependency_report_failed", error=type(exc).__name__)
        report = dependency_report_failed(type(exc).__name__)

    try:
        source_health = await get_source_health(session)
    except Exception as exc:  # noqa: BLE001 — a broken read degrades to an empty table
        log.warning("health_page.sources_failed", error=type(exc).__name__)
        source_health = []

    opencode = report["opencode"]
    return {
        "user": None,
        "dependency_rows": _dependency_rows(report),
        "source_health": source_health,
        "cv": report["cv"],
        # The `_health_strip.html` context names, fed from the shared report.
        "opencode_reachable": opencode["reachable"],
        "opencode_version": opencode["version"],
        "opencode_error": opencode["error"],
        "opencode_auth_configured": opencode["auth_configured"],
    }


@router.get(HEALTH_PAGE_PATH, response_class=HTMLResponse)
async def health_page(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    backend: LLMBackend = Depends(get_llm_backend),
    engine: LatexEngine = Depends(get_latex_engine),
) -> HTMLResponse:
    """The human health page: the system section plus the full per-source table.

    It reads the database only — no live probe, no adapter, no scheduler side
    effect — and every failure is data (see the module docstring).
    """
    context = await page_context(session, backend, engine)
    context["user"] = user
    return templates.TemplateResponse(request, HEALTH_TEMPLATE, context)


__all__ = ["HEALTH_PAGE_PATH", "HEALTH_TEMPLATE", "router"]
