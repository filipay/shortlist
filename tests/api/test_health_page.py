"""RUN-07 / D-155..D-158 / T-08-17..T-08-22 — the `/status` health page.

Three contracts this lane exists to prove, each of which has already failed in this
codebase's history in some other form:

* the page and the JSON endpoint cannot disagree (D-138), because both read the one
  `dependency_report` builder;
* a page view issues NO board request (D-156 / T-08-17) — a sentinel adapter counts
  every call and the live probe cache is asserted untouched;
* every failure degrades to data (D-08 / T-08-20) — a broken database read, an
  exploding dependency probe and an absent scheduler each yield a page, not a 500.

The lane is fully offline: the LLM backend is a stub, the scheduler runs on a
temp-file job store and no adapter is ever called.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest
import pytest_asyncio
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from zoneinfo import ZoneInfo

from app.api.health_page import HEALTH_PAGE_PATH
from app.config import settings
from app.db.models import Source
from app.db.session import get_session, get_session_factory
from app.jobs import scheduler as scheduler_module
from app.latex import get_latex_engine
from app.latex.base import EngineProbe
from app.llm import get_llm_backend
from app.llm.base import ProbeOutcome
from app.main import create_app
from app.probe import probe as probe_module
from app.probe.probe import clear_cache
from app.sources import registry
from app.sources.base import FetchBudget, FetchResult, JobSource, SearchQuery
from app.sources.linkedin import CAPABILITIES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CV_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.yaml"
HEALTH_PAGE_SOURCE = PROJECT_ROOT / "app" / "api" / "health_page.py"

#: `surface -> invocation count`, so a page view that touches a board is visible.
SENTINEL_CALLS: dict[str, int] = {}


class StubBackend:
    """A controllable LLM backend. Never opens a socket."""

    def __init__(self, outcome: ProbeOutcome | None = None) -> None:
        self.outcome = outcome or ProbeOutcome(reachable=False, error="ConnectError")

    async def health(self) -> ProbeOutcome:
        return self.outcome


class SentinelIndeed(JobSource):
    """A registered adapter that counts any outbound call and refuses to make one."""

    name = "indeed"
    capabilities = CAPABILITIES

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        SENTINEL_CALLS["probe"] = SENTINEL_CALLS.get("probe", 0) + 1
        raise AssertionError("the health page must not probe a job board")

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        SENTINEL_CALLS["fetch"] = SENTINEL_CALLS.get("fetch", 0) + 1
        raise AssertionError("the health page must not fetch from a job board")


class ExplodingEngine:
    """A LatexEngine stub that raises: the page must still answer 200."""

    async def health(self) -> EngineProbe:
        raise RuntimeError("engine exploded")

    async def compile(self, **kwargs: Any) -> Any:  # pragma: no cover - never called
        return None


@dataclass
class PageEnv:
    client: AsyncClient
    app: FastAPI
    backend: StubBackend
    session_factory: async_sessionmaker[AsyncSession]
    scheduler: AsyncIOScheduler


@pytest_asyncio.fixture
async def page_env(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> AsyncIterator[PageEnv]:
    """A client over the app, plus a real (paused) scheduler on a temp job store.

    The scheduler is installed explicitly because `next_run_at()` builds a real
    `AsyncIOScheduler` on first use, and a test must never let that happen over the
    configured database path. `paused=True` keeps the loop from running anything.
    """
    clear_cache()
    SENTINEL_CALLS.clear()

    engine = create_engine(f"sqlite:///{tmp_path / 'apscheduler.db'}")
    scheduler = AsyncIOScheduler(
        jobstores={"default": SQLAlchemyJobStore(engine=engine)},
        timezone=ZoneInfo("Europe/Dublin"),
    )
    scheduler.start(paused=True)
    monkeypatch.setattr(scheduler_module, "_scheduler", scheduler)

    app = create_app()
    backend = StubBackend()
    app.dependency_overrides[get_llm_backend] = lambda: backend

    async def _override_get_session() -> Any:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_session_factory] = lambda: session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield PageEnv(
            client=http,
            app=app,
            backend=backend,
            session_factory=session_factory,
            scheduler=scheduler,
        )

    app.dependency_overrides.clear()
    scheduler.shutdown(wait=False)
    engine.dispose()
    clear_cache()
    SENTINEL_CALLS.clear()


# --- the system section renders from the shared builder ------------------------


async def test_the_page_renders_the_four_dependency_rows(
    page_env: PageEnv, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "cv.yaml").write_text(
        CV_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))
    page_env.backend.outcome = ProbeOutcome(reachable=True, version="1.2.3")

    response = await page_env.client.get(HEALTH_PAGE_PATH)

    assert response.status_code == 200
    assert "<h2>Health</h2>" in response.text
    for label in ("Database", "LLM backend", "LaTeX engine", "CV fact store"):
        assert f"<dt>{label}</dt>" in response.text, label
    # A reachable stubbed backend and a loadable fact store both read `ok`.
    assert "health-badge health-ok" in response.text
    assert str(tmp_path / "cv.yaml") in response.text
    # The per-source table is the queue's own partial, included verbatim.
    assert 'id="source-health"' in response.text


def test_the_page_declares_status_and_not_health() -> None:
    source = HEALTH_PAGE_SOURCE.read_text(encoding="utf-8")

    assert HEALTH_PAGE_PATH == "/status"
    assert 'HEALTH_PAGE_PATH = "/status"' in source
    assert '"/health"' not in source, "the page must not claim the JSON endpoint's path"
    assert "probe_all" not in source, "a page view must never put a request on a board"


async def test_the_page_and_the_json_cannot_disagree(
    page_env: PageEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-138: one builder, so one answer for opencode reachability and `auth_configured`."""
    page_env.backend.outcome = ProbeOutcome(reachable=True, version="9.9.9")
    body = (await page_env.client.get("/health")).json()
    page = (await page_env.client.get(HEALTH_PAGE_PATH)).text
    assert body["opencode"] == {
        "reachable": True,
        "version": "9.9.9",
        "error": None,
        "auth_configured": False,
    }
    assert "reachable — version 9.9.9" in page
    assert 'id="llm-backend-auth-missing"' not in page

    page_env.backend.outcome = ProbeOutcome(reachable=False, error="ConnectError")
    body = (await page_env.client.get("/health")).json()
    page = (await page_env.client.get(HEALTH_PAGE_PATH)).text
    assert body["opencode"]["reachable"] is False
    assert body["opencode"]["auth_configured"] is False
    assert "no server password configured" in page
    # The strip's auth hint is driven by the same `auth_configured` the JSON reports.
    assert 'id="llm-backend-auth-missing"' in page

    monkeypatch.setattr(settings, "opencode_server_password", "a-real-password")
    body = (await page_env.client.get("/health")).json()
    page = (await page_env.client.get(HEALTH_PAGE_PATH)).text
    assert body["opencode"]["auth_configured"] is True
    assert "no server password configured" not in page
    assert 'id="llm-backend-auth-missing"' not in page


@pytest.mark.usefixtures("registry_snapshot")
async def test_the_page_issues_no_board_request(page_env: PageEnv) -> None:
    registry.clear()
    registry.register(SentinelIndeed)
    async with page_env.session_factory() as session:
        session.add(Source(name="indeed", display_name="Indeed"))
        await session.commit()
    clear_cache()

    response = await page_env.client.get(HEALTH_PAGE_PATH)

    assert response.status_code == 200
    assert SENTINEL_CALLS == {}, "the page put a request on a job board (T-08-17)"
    assert probe_module._CACHE == {}, "the page populated the live probe cache"


# --- totality: every failure is data ------------------------------------------


async def test_the_page_answers_when_the_database_read_fails(page_env: PageEnv) -> None:
    class BrokenSession:
        async def execute(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("database is locked")

    async def _broken_session() -> Any:
        return BrokenSession()

    page_env.app.dependency_overrides[get_session] = _broken_session

    response = await page_env.client.get(HEALTH_PAGE_PATH)

    assert response.status_code == 200
    assert "health-badge health-unreachable" in response.text
    assert "<dt>Database</dt>" in response.text


async def test_the_page_answers_when_a_dependency_probe_raises(
    page_env: PageEnv,
) -> None:
    page_env.app.dependency_overrides[get_latex_engine] = lambda: ExplodingEngine()

    response = await page_env.client.get(HEALTH_PAGE_PATH)

    assert response.status_code == 200
    assert "not available (RuntimeError)" in response.text


async def test_the_page_answers_when_the_scheduler_raises(
    page_env: PageEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenScheduler:
        def get_job(self, job_id: str) -> Any:
            raise RuntimeError("the scheduler is gone")

    monkeypatch.setattr(scheduler_module, "_scheduler", BrokenScheduler())

    response = await page_env.client.get(HEALTH_PAGE_PATH)

    assert response.status_code == 200


# --- the repository types these tests lean on ---------------------------------


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
