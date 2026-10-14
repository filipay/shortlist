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
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.api import applications as application_routes
from app.api import apply as apply_routes
from app.api import events as event_routes
from app.api import health as health_routes
from app.api import health_page as health_page_routes
from app.api import listings as listing_routes
from app.api import runs as run_routes
from app.api import searches as search_routes
from app.api import settings as settings_routes
from app.api import tailoring as tailoring_routes
from app.db.repositories import source_repo
from app.db.session import async_session_maker
from app.jobs import scheduler as scheduler_module
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

    # The in-process daily scheduler (D-151..D-154 / PLAT-06). Its own non-fatal
    # guard: a scheduler that cannot start degrades the feature and the app still
    # serves (D-08), exactly like the seeding above.
    try:
        status = await scheduler_module.start_scheduler()
        log.info("startup.scheduler", status=status)
    except Exception as exc:  # noqa: BLE001 — boot must not depend on the scheduler
        log.warning("startup.scheduler_failed", error=type(exc).__name__)

    yield

    try:
        await scheduler_module.stop_scheduler()
    except Exception as exc:  # noqa: BLE001 — shutdown must never raise
        log.warning("shutdown.scheduler_failed", error=type(exc).__name__)


#: The `Sec-Fetch-Site` values a same-origin browser request can carry. `none` is a
#: user-initiated navigation to this app; `same-origin` is this app's own form/fetch.
_SAFE_FETCH_SITES = frozenset({"same-origin", "none"})


def _is_cross_site(request: Request) -> bool:
    """True only when the browser positively identifies a cross-site initiator.

    Browsers attach `Sec-Fetch-Site` to every request, so a form or fetch from
    another origin arrives as `cross-site` (or `same-site` for a sibling
    host/port). When that header is absent the `Origin` header is the fallback,
    compared against this request's own origin. A non-browser caller (curl) and
    the test client send neither header and are allowed: the guard targets the
    browser vector without breaking scripted callers. Absent metadata is never
    treated as cross-site.
    """
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None:
        return fetch_site not in _SAFE_FETCH_SITES
    origin = request.headers.get("origin")
    if origin is None:
        return False
    host = request.headers.get("host", "")
    return origin.rstrip("/") != f"{request.url.scheme}://{host}"


def create_app() -> FastAPI:
    app = FastAPI(title="Shortlist", lifespan=lifespan)

    @app.middleware("http")
    async def _same_origin_guard(request: Request, call_next):
        """Refuse a cross-site state-changing request (CR-01 / T-08-32).

        v1 runs with no authentication (D-21), so every cross-origin POST is fully
        authorised: with no session cookie to abuse there is no *benefit* to CSRF,
        but the *capability* is intact — a plain form from any page the user's
        browser loads is a "simple request" that reaches every mutating route
        (reset, prune, CV overwrite, schedule, LLM selftest). This refuses such a
        request with 403. It is a same-origin guard, not a CSRF token: it stops the
        browser-driven vector and does not authenticate the local user.
        """
        if request.method not in ("GET", "HEAD", "OPTIONS") and _is_cross_site(request):
            return PlainTextResponse("cross-origin request refused", status_code=403)
        return await call_next(request)

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
    app.include_router(health_page_routes.router)
    return app


app = create_app()
