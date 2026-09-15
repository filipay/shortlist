"""Boot-tolerant `/health`.

Phase 1 needs `/health` to answer promptly **while a pipeline run is in flight**
(RUN-02). Plan 01-06 extends this with the opencode reachability report and the
per-source probe; nothing here may require an LLM backend (D-08).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_session
from app.domain.models import User

router = APIRouter()


@router.get("/health")
async def health(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Always answers. A failing dependency is reported, never raised."""
    database = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 — health is a total function
        database = "unreachable"
    return {"status": "ok", "database": database}


__all__ = ["router"]
