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

import inspect
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
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

from app.api.health_page import (
    HEALTH_PAGE_PATH,
    PROBE_VERDICT_DOCUMENT,
    PROMOTION_BOARDS,
)
from app.config import settings
from app.db.models import Run, Source
from app.db.repositories import operations_config_repo, source_repo
from app.db.session import get_session, get_session_factory
from app.jobs import scheduler as scheduler_module
from app.latex import get_latex_engine
from app.latex.base import EngineProbe
from app.llm import get_llm_backend
from app.llm.base import ProbeOutcome
from app.main import create_app
from app.probe import probe as probe_module
from app.probe.probe import clear_cache
from app.probe.survival import adzuna_promotion_condition
from app.sources import registry
from app.sources._ledger import record_fetch_outcome
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


async def test_the_health_page_is_surfaced_in_the_nav(page_env: PageEnv) -> None:
    """RUN-07 says the health surface is reached *from the UI* — the nav is that link.

    A route with no nav entry is only reachable by typing the URL, so a dropped
    entry is a regression the route's own 200 cannot catch.
    """
    queue = await page_env.client.get("/")
    assert queue.status_code == 200
    assert re.search(r'<a class="nav-link[^"]*" href="/status"[^>]*>Health</a>', queue.text)

    page = await page_env.client.get(HEALTH_PAGE_PATH)
    assert re.search(
        r'<a class="nav-link nav-current touch-target" href="/status" aria-current="page">Health</a>',
        page.text,
    ), "the Health nav entry must read as the current page on /status"


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


# --- the schedule line, the missed notice and the last run ---------------------


async def _write_schedule(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    enabled: bool,
    hour: int = 7,
    minute: int = 0,
) -> None:
    async with session_factory() as session:
        await operations_config_repo.write_schedule(
            session,
            operations_config_repo.ScheduleConfig(
                enabled=enabled, hour=hour, minute=minute, timezone="Europe/Dublin"
            ),
        )
        await session.commit()


async def _write_skip_notice(
    session_factory: async_sessionmaker[AsyncSession], *, reason: str
) -> None:
    async with session_factory() as session:
        await operations_config_repo.write_skip_notice(session, reason=reason)
        await session.commit()


def _line(text: str, element_id: str) -> str:
    """The single element's own markup, so an assertion cannot read another line's."""
    match = re.search(
        rf'<p class="ranking-strip" id="{element_id}">.*?</p>', text, re.DOTALL
    )
    assert match is not None, f"the page rendered no #{element_id}"
    return match.group(0)


async def test_the_next_run_line_renders_a_countdown_for_a_registered_job(
    page_env: PageEnv,
) -> None:
    await _write_schedule(page_env.session_factory, enabled=True, hour=7, minute=0)
    status = await scheduler_module.reconcile(
        page_env.scheduler, page_env.session_factory
    )
    assert status == "registered"

    text = (await page_env.client.get(HEALTH_PAGE_PATH)).text
    line = _line(text, "health-schedule")

    assert "Next run at 07:00 Europe/Dublin — in" in line
    assert re.search(r'id="health-next-run">\d+(h \d+)?m<', line), line


async def test_a_disabled_schedule_reads_scheduling_off(page_env: PageEnv) -> None:
    await _write_schedule(page_env.session_factory, enabled=False)

    text = (await page_env.client.get(HEALTH_PAGE_PATH)).text

    assert "Scheduling off" in _line(text, "health-schedule")


async def test_an_enabled_schedule_with_no_job_never_fabricates_a_time(
    page_env: PageEnv,
) -> None:
    """Enabled but unregistered: the honest no-run state, and no countdown chip."""
    await _write_schedule(page_env.session_factory, enabled=True)
    assert page_env.scheduler.get_jobs() == []

    line = _line((await page_env.client.get(HEALTH_PAGE_PATH)).text, "health-schedule")

    assert "No run currently scheduled." in line
    assert "reason-value" not in line, "a countdown was computed from a missing value"
    assert not re.search(r"\d", line), line


async def test_the_missed_run_notice_renders_from_a_recorded_skip(
    page_env: PageEnv,
) -> None:
    async with page_env.session_factory() as session:
        await operations_config_repo.write_skip_notice(
            session, reason="missed", when=datetime.now(UTC)
        )
        await session.commit()

    line = _line((await page_env.client.get(HEALTH_PAGE_PATH)).text, "health-skip")

    assert "Last scheduled run was missed." in line
    assert "Missed runs are skipped, never caught up." in line


async def test_the_in_flight_skip_renders_its_own_wording(page_env: PageEnv) -> None:
    await _write_skip_notice(page_env.session_factory, reason="in_flight")

    line = _line((await page_env.client.get(HEALTH_PAGE_PATH)).text, "health-skip")

    assert "already in progress" in line


async def test_no_notice_renders_without_a_recorded_skip(page_env: PageEnv) -> None:
    """A gap in the run history is not evidence of a missed run (D-154)."""
    async with page_env.session_factory() as session:
        session.add(
            Run(
                search_id=None,
                trigger="schedule",
                status="done",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
        )
        await session.commit()

    text = (await page_env.client.get(HEALTH_PAGE_PATH)).text

    assert 'id="health-skip"' not in text


async def test_the_last_run_line_names_the_status_and_reason(page_env: PageEnv) -> None:
    async with page_env.session_factory() as session:
        session.add(
            Run(
                search_id=None,
                trigger="manual",
                status="done",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                fetched_count=3,
                reason="nothing_new",
                reason_counts_json={"survivors": 3},
            )
        )
        await session.commit()

    line = _line((await page_env.client.get(HEALTH_PAGE_PATH)).text, "health-last-run")

    assert "Last run: done —" in line
    assert "3 listings survived the rules but 0 are new" in line
    assert 'href="/runs"' in line
    assert "Run history" in line


async def test_the_last_run_line_is_absent_with_no_runs(page_env: PageEnv) -> None:
    text = (await page_env.client.get(HEALTH_PAGE_PATH)).text

    assert 'id="health-last-run"' not in text


# --- the stop-signal-aware per-source badge -----------------------------------


@pytest.mark.usefixtures("registry_snapshot")
async def test_a_recorded_stop_signal_classifies_the_badge_fetch_side(
    page_env: PageEnv,
) -> None:
    registry.clear()
    registry.register(SentinelIndeed)
    async with page_env.session_factory() as session:
        session.add(Source(name="indeed", display_name="Indeed"))
        await session.commit()
    async with page_env.session_factory() as session:
        # Exactly what ingest writes: a stop signal recorded in the ledger note.
        await record_fetch_outcome(
            session,
            source="indeed",
            run_id=None,
            result_status="blocked",
            parsed_items=0,
        )
        await session.commit()

    async with page_env.session_factory() as session:
        rows = await source_repo.get_source_health_with_signals(session)
    assert [row.classification for row in rows] == ["fetch-side"]
    assert rows[0].stop_signal == "blocked"
    assert rows[0].health == "degraded"

    text = (await page_env.client.get(HEALTH_PAGE_PATH)).text

    assert 'id="source-health-indeed"' in text
    assert "health-badge health-degraded" in text
    assert SENTINEL_CALLS == {}, "the stop-signal read put a request on a board"


async def test_a_source_with_no_recorded_request_keeps_its_stored_value(
    page_env: PageEnv,
) -> None:
    async with page_env.session_factory() as session:
        session.add(Source(name="indeed", display_name="Indeed"))
        await session.commit()

    async with page_env.session_factory() as session:
        rows = await source_repo.get_source_health_with_signals(session)

    assert rows[0].classification is None
    assert rows[0].health is None, "a never-fetched source must not read as a failure"


def test_the_derived_badge_vocabulary_is_the_shared_one() -> None:
    assert set(source_repo.CLASSIFICATION_HEALTH.values()) <= source_repo.VALID_HEALTH


# --- the Adzuna promotion verdict, read-only (D-158) ---------------------------


async def _seed_board_runs(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    board: str,
    statuses: list[str],
) -> None:
    """One run per status, each recording `board`, oldest-to-newest."""
    async with session_factory() as session:
        for index, status in enumerate(statuses):
            session.add(
                Run(
                    search_id=None,
                    trigger="manual",
                    status="done",
                    started_at=datetime(2026, 9, 1 + index, 6, 0, tzinfo=UTC),
                    finished_at=datetime(2026, 9, 1 + index, 6, 5, tzinfo=UTC),
                    fetched_count=10,
                    source_counts_json={
                        board: {"status": status, "fetched": 10, "created": 10}
                    },
                )
            )
        await session.commit()


async def test_the_verdict_line_carries_the_recorded_fraction(page_env: PageEnv) -> None:
    await _seed_board_runs(
        page_env.session_factory,
        board="indeed",
        statuses=["blocked", "blocked", "blocked", "ok", "ok"],
    )

    text = (await page_env.client.get(HEALTH_PAGE_PATH)).text

    # One predicate, one source of truth: recompute the condition the page reads.
    async with page_env.session_factory() as session:
        evidence = await source_repo.board_evidence(session, "indeed")
    assert evidence is not None
    p1 = next(
        result
        for result in adzuna_promotion_condition(evidence)
        if result.signal == "P-1"
    )
    assert p1.status == "fail"

    line = _line(text, "adzuna-verdict-indeed")
    assert f"{p1.observed} blocked runs" in line, line
    assert "condition met" in line
    assert "condition not met" not in line
    assert "Read the probe verdict" in line
    assert PROBE_VERDICT_DOCUMENT in line


async def test_a_not_met_window_renders_the_not_met_wording(page_env: PageEnv) -> None:
    await _seed_board_runs(
        page_env.session_factory, board="indeed", statuses=["ok"] * 5
    )

    line = _line(
        (await page_env.client.get(HEALTH_PAGE_PATH)).text, "adzuna-verdict-indeed"
    )

    assert "0/5 blocked runs" in line
    assert "condition not met" in line


async def test_a_short_window_renders_no_verdict_and_no_number(page_env: PageEnv) -> None:
    await _seed_board_runs(page_env.session_factory, board="indeed", statuses=["blocked"])

    line = _line(
        (await page_env.client.get(HEALTH_PAGE_PATH)).text, "adzuna-verdict-indeed"
    )

    assert "no verdict recorded yet" in line
    sentence = re.search(r'<span class="[^"]*">(.*?)</span>', line, re.DOTALL).group(1)
    assert not re.search(r"\d", sentence), f"a number was printed with no verdict: {sentence}"


async def test_the_verdict_region_offers_no_control(page_env: PageEnv) -> None:
    await _seed_board_runs(
        page_env.session_factory, board="indeed", statuses=["blocked"] * 4
    )

    text = (await page_env.client.get(HEALTH_PAGE_PATH)).text
    region = re.search(
        r'<section id="adzuna-verdict".*?</section>', text, re.DOTALL
    ).group(0)

    assert "<form" not in region
    assert "<button" not in region
    anchors = re.findall(r"<a\b[^>]*>", region)
    assert len(anchors) == len(PROMOTION_BOARDS), anchors
    for anchor in anchors:
        assert "probe-verdict" in anchor, anchor
    assert "promote" not in region.lower().replace("promotion", "")
    assert "enable" not in region.lower()


async def test_the_absent_verdict_region_still_says_so(page_env: PageEnv) -> None:
    text = (await page_env.client.get(HEALTH_PAGE_PATH)).text

    for board in PROMOTION_BOARDS:
        assert "no verdict recorded yet" in _line(text, f"adzuna-verdict-{board}")


async def test_the_verdict_read_issues_no_board_request(
    page_env: PageEnv,
) -> None:
    await _seed_board_runs(
        page_env.session_factory, board="indeed", statuses=["blocked"] * 5
    )

    response = await page_env.client.get(HEALTH_PAGE_PATH)

    assert response.status_code == 200
    assert SENTINEL_CALLS == {}, "the verdict read put a request on a board"


# --- the repository contract the page leans on --------------------------------


def test_the_board_evidence_builder_lives_in_the_repository_layer() -> None:
    builder = getattr(source_repo, "board_evidence", None)
    assert callable(builder), "the board-evidence builder must live in the repository layer"
    assert inspect.iscoroutinefunction(builder), "the builder must be async"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
