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
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.health import dependency_report
from app.config import settings
from app.db.repositories import operations_config_repo, run_repo
from app.db.repositories.run_repo import RunSummary
from app.db.repositories.source_repo import (
    board_evidence,
    get_source_health_with_signals,
)
from app.db.session import get_session
from app.domain.models import User
from app.jobs import scheduler as scheduler_module
from app.latex import get_latex_engine
from app.latex.base import LatexEngine
from app.llm import auth_configured, get_llm_backend
from app.llm.base import LLMBackend
from app.pipeline.rank import CV_FILENAME
from app.probe.survival import BoardEvidence, adzuna_promotion_condition
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

#: The boards the survival probe documents (D-04 §6). The promotion condition is
#: defined over these scraped boards — Adzuna is the hedge that would be promoted
#: if one of them stops being usable.
PROMOTION_BOARDS: tuple[str, ...] = ("indeed", "linkedin")

#: The verdict document the line links to. A committed repo path, never a network
#: asset (T-08-19).
PROBE_VERDICT_DOCUMENT = "docs/probes/2026-09-15-scraper-survival.md"


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
        source_health = await get_source_health_with_signals(session)
    except Exception as exc:  # noqa: BLE001 — a broken read degrades to an empty table
        log.warning("health_page.sources_failed", error=type(exc).__name__)
        source_health = []

    schedule_line = await _schedule_line(session)
    skip_notice = await _skip_notice(session)
    last_run = await _last_run(session)
    board_verdicts = await _board_verdicts(session)

    opencode = report["opencode"]
    return {
        "user": None,
        "dependency_rows": _dependency_rows(report),
        "source_health": source_health,
        "cv": report["cv"],
        "schedule_line": schedule_line,
        "skip_notice": skip_notice,
        "last_run": last_run,
        "board_verdicts": board_verdicts,
        # The `_health_strip.html` context names, fed from the shared report.
        "opencode_reachable": opencode["reachable"],
        "opencode_version": opencode["version"],
        "opencode_error": opencode["error"],
        "opencode_auth_configured": opencode["auth_configured"],
    }


def _countdown(next_run: datetime, *, now: datetime) -> str:
    """Hours-and-minutes until `next_run`, never negative and never from `None`.

    A past-due fire time floors at `0m` rather than counting backwards: the page
    states the scheduled time beside it, so the countdown is the urgent part.
    """
    minutes = max(0, int((next_run - now).total_seconds())) // 60
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


async def _schedule_line(session: AsyncSession) -> dict[str, Any]:
    """The next-run line. Total: any failure degrades to an honest state.

    The STORED schedule is the authority on enabled/disabled (a scheduler that
    failed to start must still render the user's configured state), and the live
    job is only consulted for its next fire time. `None` is an honest state —
    `Scheduling off`, or "no run scheduled" — and a countdown is never computed
    from it (RESEARCH Pitfall 6).
    """
    try:
        schedule = await operations_config_repo.read_schedule(session)
    except Exception as exc:  # noqa: BLE001 — a decorative line must not 500 the page
        log.warning("health_page.schedule_read_failed", error=type(exc).__name__)
        return {"state": "unscheduled"}

    if not schedule.enabled:
        return {"state": "off"}

    next_run = scheduler_module.next_run_at()
    if next_run is None:
        return {"state": "unscheduled"}

    try:
        zone = ZoneInfo(schedule.timezone)
    except Exception as exc:  # noqa: BLE001 — a missing tz database is data, not a 500
        log.warning("health_page.zone_missing", error=type(exc).__name__)
        return {"state": "unscheduled"}

    now = datetime.now(zone)
    return {
        "state": "scheduled",
        "at": f"{next_run.astimezone(zone).strftime('%H:%M')} {schedule.timezone}",
        "countdown": _countdown(next_run, now=now),
    }


async def _skip_notice(session: AsyncSession) -> dict[str, Any] | None:
    """The D-154 notice from the durable skip record. Total.

    It is produced ONLY by a recorded notice — never inferred from a gap in the
    run history, which would be a fabricated statement about the user's machine.
    """
    try:
        notice = await operations_config_repo.read_skip_notice(session)
    except Exception as exc:  # noqa: BLE001 — decorative data must not 500 the page
        log.warning("health_page.skip_notice_failed", error=type(exc).__name__)
        return None
    if not notice:
        return None
    reason = notice.get("reason")
    if reason == "missed":
        return {
            "kind": "missed",
            "sentence": "Last scheduled run was missed. Missed runs are skipped, never caught up.",
        }
    if reason == "in_flight":
        return {
            "kind": "in_flight",
            "sentence": (
                "A scheduled run was skipped: a run was already in progress. "
                "Runs are never overlapped."
            ),
        }
    return None


async def _last_run(session: AsyncSession) -> RunSummary | None:
    """The newest run, or `None` when no run has happened. Total."""
    try:
        runs = await run_repo.list_runs(session, limit=1)
    except Exception as exc:  # noqa: BLE001 — decorative data must not 500 the page
        log.warning("health_page.last_run_failed", error=type(exc).__name__)
        return None
    return runs[0] if runs else None


def _verdict_view(board: str, evidence: BoardEvidence | None) -> dict[str, Any]:
    """The read-only verdict row for one board (D-158).

    The number is the P-1 result's observed fraction and the met/not-met flag is
    P-1's status — `adzuna_promotion_condition` is the ONE definition of the
    condition, so the page cannot disagree with the probe document about whether it
    fired. `skip` means the window is not full, so there is no verdict yet and a
    number must never be printed (D-158 / RESEARCH Pattern 7).
    """
    hedge = f"{board.title()} hedge"
    absent = {
        "board": board,
        "state": "absent",
        "token": "health-empty",
        "observed": None,
        "sentence": f"{hedge}: no verdict recorded yet.",
        "document": PROBE_VERDICT_DOCUMENT,
    }
    if evidence is None:
        return absent

    p1 = next(
        (result for result in adzuna_promotion_condition(evidence) if result.signal == "P-1"),
        None,
    )
    if p1 is None or p1.status == "skip":
        return absent

    met = p1.status == "fail"
    observed = str(p1.observed)
    return {
        "board": board,
        "state": "met" if met else "not_met",
        "token": "req-met" if met else "req-partial",
        "observed": observed,
        "sentence": (
            f"{hedge}: {observed} blocked runs — condition {'met' if met else 'not met'}"
        ),
        "document": PROBE_VERDICT_DOCUMENT,
    }


async def _board_verdicts(session: AsyncSession) -> list[dict[str, Any]]:
    """One verdict row per board the survival probe documents. Total.

    Each board's guard is its own, so one board's failure degrades that one line to
    the honest absent state rather than losing the whole section.
    """
    verdicts: list[dict[str, Any]] = []
    for board in PROMOTION_BOARDS:
        try:
            evidence = await board_evidence(session, board)
        except Exception as exc:  # noqa: BLE001 — decorative data must not 500 the page
            log.warning("health_page.verdict_failed", board=board, error=type(exc).__name__)
            evidence = None
        verdicts.append(_verdict_view(board, evidence))
    return verdicts


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


__all__ = [
    "HEALTH_PAGE_PATH",
    "HEALTH_TEMPLATE",
    "PROBE_VERDICT_DOCUMENT",
    "PROMOTION_BOARDS",
    "dependency_report_failed",
    "page_context",
    "router",
]
