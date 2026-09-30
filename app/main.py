"""FastAPI app factory.

The lifespan opens only things that cannot hard-fail. Nothing here may require
the opencode server (D-08): `docker compose up` must never depend on an LLM
backend being reachable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import applications as application_routes
from app.api import apply as apply_routes
from app.api import events as event_routes
from app.api import health as health_routes
from app.api import listings as listing_routes
from app.api import runs as run_routes
from app.api import searches as search_routes
from app.api import settings as settings_routes
from app.api import tailoring as tailoring_routes
from app.db.repositories import source_repo
from app.db.session import async_session_maker
from app.web import routes as web_routes

log = structlog.get_logger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Seed the `sources` allow-list from the adapter registry. Without it a freshly
    # migrated database has no enabled rows and every run resolves zero adapters.
    # It must not hard-fail boot (D-08): a seeding failure is logged and the app
    # still serves, exactly like an unreachable opencode server.
    try:
        async with async_session_maker() as session:
            inserted = await source_repo.ensure_registered_sources(session)
            await session.commit()
        if inserted:
            log.info("startup.sources_seeded", sources=inserted)
    except Exception as exc:  # noqa: BLE001 — boot must not depend on the seeding
        log.warning("startup.sources_seed_failed", error=type(exc).__name__)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Job Search Copilot", lifespan=lifespan)

    # Vendored assets only (UI-07) — no CDN. The directory is created if absent
    # so the app is importable before the asset build runs.
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(web_routes.router)
    app.include_router(run_routes.router)
    app.include_router(search_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(event_routes.router)
    app.include_router(listing_routes.router)
    app.include_router(tailoring_routes.router)
    app.include_router(apply_routes.router)
    app.include_router(application_routes.router)
    app.include_router(health_routes.router)
    return app


app = create_app()
