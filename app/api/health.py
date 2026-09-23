"""Boot-tolerant `/health`: database, opencode and per-source liveness (SRC-07).

`/health` answers **HTTP 200 in every case** (D-08). `docker compose up`, the queue
page and any uptime check must not depend on an LLM backend, a job board, or even a
reachable database. Every dependency is *reported*, never raised.

The per-source probe comes from the TTL-cached orchestration in
`app/probe/probe.py`, never from the adapters directly, so loading this endpoint
cannot put a request on a board that bans automation (T-01-31). The response is
built from typed fields only: no raw upstream payload is echoed (T-01-30).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import current_user
from app.config import settings
from app.cv.factstore import fact_store_report
from app.db.repositories.source_repo import get_source_health
from app.db.session import get_session, get_session_factory
from app.domain.models import User
from app.latex import get_latex_engine
from app.latex.base import LatexEngine
from app.llm import get_llm_backend
from app.llm.base import LLMBackend
from app.pipeline.rank import CV_FILENAME
from app.probe.probe import probe_all

log = structlog.get_logger(__name__)

router = APIRouter()


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment is not None else None


async def _opencode_report(backend: LLMBackend) -> dict[str, Any]:
    """`{reachable, version, error}`. A backend bug must not break `/health`."""
    try:
        outcome = await backend.health()
    except Exception as exc:  # noqa: BLE001 — health is a total function
        return {"reachable": False, "version": None, "error": type(exc).__name__}
    return {
        "reachable": bool(outcome.reachable),
        "version": outcome.version,
        "error": outcome.error,
    }


async def _tectonic_report(engine: LatexEngine) -> dict[str, Any]:
    """`{available, version, error}`. An engine bug must not break `/health`.

    Mirrors `_opencode_report` exactly (O5): the probe is the cheap binary-version
    check, never a compile.
    """
    try:
        probe = await engine.health()
    except Exception as exc:  # noqa: BLE001 — health is a total function
        return {"available": False, "version": None, "error": type(exc).__name__}
    return {
        "available": bool(probe.available),
        "version": probe.version,
        "error": probe.error,
    }


def _cv_report() -> dict[str, Any]:
    """`{available, path, error}`. A store problem must not break `/health`.

    Mirrors `_tectonic_report`'s totality: the probe is total, so a failure is
    REPORTED, never raised, and never changes `status`. Unlike `tectonic` the object
    carries `path` instead of `version` — a fact store is a data document with no
    engine version, and the path is the operator's actionable datum. `error` is the
    exception CLASS NAME only, never a message, so no document text can reach the JSON.
    """
    return fact_store_report(Path(settings.cv_dir) / CV_FILENAME)


@router.get("/health")
async def health(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    backend: LLMBackend = Depends(get_llm_backend),
    engine: LatexEngine = Depends(get_latex_engine),
) -> dict[str, Any]:
    """Always answers with 200. Degraded state is data, never an exception."""
    database = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 — health is a total function
        database = "unreachable"

    opencode = await _opencode_report(backend)
    tectonic = await _tectonic_report(engine)

    try:
        probes = await probe_all(session_factory=session_factory)
    except Exception as exc:  # noqa: BLE001 — a probe failure must not break /health
        log.warning("health.probe_failed", error=type(exc).__name__)
        probes = {}

    try:
        rows = await get_source_health(session)
    except Exception as exc:  # noqa: BLE001 — the source map degrades to empty
        log.warning("health.sources_failed", error=type(exc).__name__)
        rows = []

    sources: dict[str, Any] = {}
    for row in rows:
        sources[row.name] = {
            "name": row.name,
            "enabled": row.enabled,
            "health": row.health,
            "probe": probes.get(row.name),
            "last_probe_at": _iso(row.last_probe_at),
            "last_success_at": _iso(row.last_success_at),
            "listings_returned": row.listings_returned,
            "field_fill_rate": row.field_fill_rate,
        }
    # A registered adapter with no `sources` row still reports its liveness.
    for name in sorted(set(probes) - set(sources)):
        sources[name] = {
            "name": name,
            "enabled": None,
            "health": None,
            "probe": probes[name],
            "last_probe_at": None,
            "last_success_at": None,
            "listings_returned": 0,
            "field_fill_rate": {},
        }

    return {
        # The LLM backend being down does NOT degrade the app's own health (D-08).
        # The same rule applies to the LaTeX engine: a missing binary is REPORTED
        # here, never raised, and never changes "status".
        "status": "ok" if database == "ok" else "degraded",
        "db": database,
        "opencode": opencode,
        "tectonic": tectonic,
        # A missing or unreadable CV fact store never degrades "status" — the same
        # rule the LaTeX engine already follows. Ranking is skipped, and that is data.
        "cv": _cv_report(),
        "sources": sources,
    }


__all__ = ["router"]
