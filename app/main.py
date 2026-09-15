"""FastAPI app factory.

The lifespan opens only things that cannot hard-fail. Nothing here may require
the opencode server (D-08): `docker compose up` must never depend on an LLM
backend being reachable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import health as health_routes
from app.api import runs as run_routes
from app.web import routes as web_routes

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # The engine is created at import time and connects lazily; there is nothing
    # to fail hard here and no external service is contacted.
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Job Search Copilot", lifespan=lifespan)

    # Vendored assets only (UI-07) — no CDN. The directory is created if absent
    # so the app is importable before the asset build runs.
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(web_routes.router)
    app.include_router(run_routes.router)
    app.include_router(health_routes.router)
    return app


app = create_app()
