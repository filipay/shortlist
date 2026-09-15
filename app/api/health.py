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
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import current_user
from app.db.repositories.source_repo import get_source_health
from app.db.session import get_session, get_session_factory
from app.domain.models import User
from app.llm import get_llm_backend
from app.llm.base import LLMBackend
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


@router.get("/health")
async def health(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    backend: LLMBackend = Depends(get_llm_backend),
) -> dict[str, Any]:
    """Always answers with 200. Degraded state is data, never an exception."""
    database = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 — health is a total function
        database = "unreachable"

    opencode = await _opencode_report(backend)

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
        "status": "ok" if database == "ok" else "degraded",
        "db": database,
        "opencode": opencode,
        "sources": sources,
    }


__all__ = ["router"]
