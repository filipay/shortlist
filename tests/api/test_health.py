"""SRC-07 / D-08 / D-13 / T-01-30 — `/health` and the visible health strip.

`/health` must answer **HTTP 200 in every case**: an unreachable opencode server, a
failing probe, a dead database, even a backend that raises. The strip must render
last success, listings returned and field fill-rate per source, and must say "LLM
backend unreachable" instead of failing mysteriously.

Nothing here touches the network: the LLM backend is a stub and the probe is either
the real cached orchestrator over a stub adapter or a canned mapping.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import health as health_module
from app.config import Settings, settings
from app.db.models import Run, Source
from app.db.repositories.listing_repo import upsert_listing_source
from app.db.session import get_session, get_session_factory
from app.latex import get_latex_engine
from app.latex.base import EngineProbe
from app.llm import get_llm_backend
from app.llm.base import DiscoveryResult, ProbeOutcome
from app.main import create_app
from app.probe.probe import clear_cache
from app.sources import registry
from app.sources.base import FetchBudget, FetchResult, JobSource, SearchQuery
from app.sources.linkedin import CAPABILITIES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STRIP_TEMPLATE = PROJECT_ROOT / "app" / "web" / "templates" / "html" / "_health_strip.html"
QUEUE_TEMPLATE = PROJECT_ROOT / "app" / "web" / "templates" / "html" / "queue.html"
CV_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.yaml"

SENTINEL = json.loads(
    (PROJECT_ROOT / "tests" / "fixtures" / "opencode_providers.json").read_text(
        encoding="utf-8"
    )
)["provider"]["data"][0]["key"]

#: No key in the body may carry a raw upstream payload (T-01-30).
FORBIDDEN_BODY_KEYS = frozenset(
    {
        "raw",
        "raw_body",
        "raw_response",
        "body",
        "payload",
        "provider_payload",
        "providers",
        "api_key",
        "key",
        "config",
    }
)

#: Generous: this is a DB-only path with a stubbed backend; the point is that it is
#: nowhere near the multi-second scale of a scrape.
PROMPTNESS_BUDGET_SECONDS = 1.0


class StubBackend:
    """A controllable LLM backend. Never opens a socket."""

    def __init__(self, outcome: ProbeOutcome | None = None) -> None:
        self.outcome = outcome or ProbeOutcome(reachable=False, error="ConnectError")
        #: Stands in for a naively-implemented backend that kept the raw response.
        self.raw_body: str | None = None

    async def health(self) -> ProbeOutcome:
        return self.outcome

    async def discover_models(self) -> DiscoveryResult:
        return DiscoveryResult(reachable=False, error="not used by /health")


class StubIndeed(JobSource):
    """A registered adapter that probes as `degraded`, with no I/O."""

    name = "indeed"
    capabilities = CAPABILITIES

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "degraded"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(source=self.name, items=[], status="ok")


#: `source -> probe invocation count`, so the TTL cache is asserted end to end.
PROBE_CALLS: dict[str, int] = {}


class CountingIndeed(JobSource):
    """A registered adapter that counts how often its probe is invoked."""

    name = "indeed"
    capabilities = CAPABILITIES

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        PROBE_CALLS[self.name] = PROBE_CALLS.get(self.name, 0) + 1
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(source=self.name, items=[], status="ok")


@dataclass
class HealthEnv:
    client: AsyncClient
    app: FastAPI
    backend: StubBackend
    session_factory: async_sessionmaker[AsyncSession]


@pytest_asyncio.fixture
async def health_env(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[HealthEnv]:
    clear_cache()
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
        yield HealthEnv(
            client=http, app=app, backend=backend, session_factory=session_factory

        )

    app.dependency_overrides.clear()
    clear_cache()


def _probe_stub(mapping: dict[str, str]) -> Any:
    async def _probe_all(
        *, force: bool = False, names: Any = None, session_factory: Any = None
    ) -> dict[str, str]:
        return dict(sorted(mapping.items()))

    return _probe_all


def _all_keys(payload: Any) -> Iterator[str]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key
            yield from _all_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _all_keys(item)


def _norm(index: int, *, description: str) -> dict[str, object]:
    url = f"https://ie.indeed.com/viewjob?jk={index}"
    return {
        "canonical_url": url,
        "source_listing_id": f"sid-{index}",
        "source_url": url,
        "canonical_source_url": url,
        "direct_url": f"https://acme.example.com/jobs/{index}" if index == 1 else None,
        "title": f"Engineer {index}",
        "company_name": "Acme",
        "company_norm": "acme",
        "location_raw": "Dublin, Ireland",
        "description": description,
        "content_hash": f"content-hash-{index}",
        "raw_hash": f"raw-hash-{index}",
        "posted_at": datetime(2026, 9, 1, tzinfo=UTC),
    }


async def _seed_source_run_and_listings(
    session_factory: async_sessionmaker[AsyncSession],
) -> Run:
    """One enabled source, one successful run, two listings (one blank description)."""
    moment = datetime.now(UTC)
    async with session_factory() as session:
        session.add(Source(name="indeed", display_name="Indeed"))
        run = Run(
            search_id=None,
            trigger="manual",
            status="done",
            started_at=moment,
            finished_at=moment,
            source_counts_json={
                "indeed": {"status": "ok", "fetched": 2, "created": 2, "updated": 0}
            },
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)

    # The pipeline stamps every row it touches with the run's own clock, which is
    # how the read model scopes a run's records.
    later = datetime.now(UTC)
    async with session_factory() as session:
        for index, description in enumerate(("Build the thing.", "   "), start=1):
            await upsert_listing_source(
                session,
                source="indeed",
                norm=_norm(index, description=description),
                run_id=run.id,
                now=later,
            )
        await session.commit()
    return run


# --- /health is total ---------------------------------------------------------


async def test_health_returns_200_and_reports_opencode_unreachable(
    health_env: HealthEnv,
) -> None:
    response = await health_env.client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok", "an unreachable LLM backend must not degrade the app"
    assert body["db"] == "ok"
    assert body["opencode"]["reachable"] is False
    assert body["opencode"]["error"] == "ConnectError"
    assert body["opencode"]["auth_configured"] is False


async def test_health_reports_the_opencode_version_when_reachable(
    health_env: HealthEnv,
) -> None:
    health_env.backend.outcome = ProbeOutcome(reachable=True, version="1.2.3")

    response = await health_env.client.get("/health")

    assert response.status_code == 200
    assert response.json()["opencode"] == {
        "reachable": True,
        "version": "1.2.3",
        "error": None,
        "auth_configured": False,
    }


async def test_health_reports_auth_configured_when_a_password_is_set(
    health_env: HealthEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "opencode_server_password", "a-real-password")

    body = (await health_env.client.get("/health")).json()

    assert body["opencode"]["auth_configured"] is True


async def test_health_never_leaks_the_server_password(
    health_env: HealthEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    sentinel = "do-not-leak-this-password"
    monkeypatch.setattr(settings, "opencode_server_password", sentinel)

    response = await health_env.client.get("/health")

    assert response.json()["opencode"]["auth_configured"] is True
    assert sentinel not in response.text


async def test_health_auth_report_ignores_the_ambient_environment(
    health_env: HealthEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default lane's settings must not inherit the developer's `.env`/env.

    `settings = Settings()` runs at import and reads the ambient environment, so a
    leaked `OPENCODE_SERVER_PASSWORD` flips `/health`'s `auth_configured` to True —
    the exact defect this suite was bitten by. `monkeypatch.setenv` proves the
    vector is live (a freshly constructed `Settings()` sees the leaked value)
    while the hermetic fixture keeps the app's own settings on the documented
    default. The guard is only non-vacuous where an ambient leak exists: in a
    clean environment the pinned default already matches the ambient one.
    """
    monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "ambient-leak")
    monkeypatch.setenv("OPENCODE_MODEL", "ambient-model")
    monkeypatch.setenv("OPENCODE_BASE_URL", "http://ambient.invalid:1")

    # The ambient vector is real: a fresh Settings() would inherit it ...
    assert Settings().opencode_server_password == "ambient-leak"

    # ... but the app's own settings, and `/health`, stay on the documented default.
    assert settings.opencode_server_password == ""
    assert settings.opencode_model == "minimax-m3"
    body = (await health_env.client.get("/health")).json()
    assert body["opencode"]["auth_configured"] is False


async def test_health_reports_database_reachability(health_env: HealthEnv) -> None:
    class BrokenSession:
        async def execute(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("database is locked")

    async def _broken_session() -> Any:
        return BrokenSession()

    health_env.app.dependency_overrides[get_session] = _broken_session

    response = await health_env.client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["db"] == "unreachable"
    assert body["status"] == "degraded"


async def test_health_survives_a_probe_that_raises(
    health_env: HealthEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _explode(*args: Any, **kwargs: Any) -> dict[str, str]:
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(health_module, "probe_all", _explode)

    response = await health_env.client.get("/health")

    assert response.status_code == 200
    assert response.json()["sources"] == {}


async def test_health_reports_the_per_source_probe_status(
    health_env: HealthEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health_module, "probe_all", _probe_stub({"indeed": "degraded"}))

    body = (await health_env.client.get("/health")).json()

    assert body["sources"]["indeed"]["probe"] == "degraded"


async def test_health_reports_persisted_source_health(
    health_env: HealthEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_source_run_and_listings(health_env.session_factory)
    monkeypatch.setattr(health_module, "probe_all", _probe_stub({"indeed": "ok"}))

    entry = (await health_env.client.get("/health")).json()["sources"]["indeed"]

    assert entry["name"] == "indeed"
    assert entry["enabled"] is True
    assert entry["probe"] == "ok"
    assert entry["listings_returned"] == 2
    assert entry["last_success_at"] is not None
    assert entry["field_fill_rate"]["description"] == 0.5


@pytest.mark.usefixtures("registry_snapshot")
async def test_health_records_the_probe_result_on_the_sources_row(
    health_env: HealthEnv,
) -> None:
    registry.clear()
    registry.register(StubIndeed)
    async with health_env.session_factory() as session:
        session.add(Source(name="indeed", display_name="Indeed"))
        await session.commit()

    response = await health_env.client.get("/health")

    assert response.status_code == 200
    assert response.json()["sources"]["indeed"]["probe"] == "degraded"
    async with health_env.session_factory() as session:
        row = await session.scalar(select(Source).where(Source.name == "indeed"))
    assert row is not None
    assert row.health == "degraded"
    assert row.last_probe_at is not None


@pytest.mark.usefixtures("registry_snapshot")
async def test_repeated_health_loads_probe_each_source_once(
    health_env: HealthEnv,
) -> None:
    """The TTL cache is what stops a page load from hammering a board (T-01-31)."""
    PROBE_CALLS.clear()
    registry.clear()
    registry.register(CountingIndeed)
    async with health_env.session_factory() as session:
        session.add(Source(name="indeed", display_name="Indeed"))
        await session.commit()

    responses = [await health_env.client.get("/health") for _ in range(3)]

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert responses[0].json()["sources"]["indeed"]["probe"] == "ok"
    assert PROBE_CALLS == {"indeed": 1}, "a repeated /health load re-probed the board"


async def test_health_answers_promptly_while_a_run_is_in_flight(
    health_env: HealthEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with health_env.session_factory() as session:
        run = Run(
            search_id=None,
            trigger="manual",
            status="running",
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)

    monkeypatch.setattr(health_module, "probe_all", _probe_stub({"indeed": "ok"}))

    started = time.perf_counter()
    response = await health_env.client.get("/health")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert elapsed < PROMPTNESS_BUDGET_SECONDS, f"/health took {elapsed:.2f}s mid-run"
    async with health_env.session_factory() as session:
        still_running = await session.scalar(select(Run).where(Run.id == run.id))
    assert still_running is not None and still_running.status == "running"


async def test_the_health_body_carries_no_raw_upstream_payload(
    health_env: HealthEnv,
) -> None:
    # A backend that naively kept the raw discovery response must still not have it
    # echoed: /health is built from typed fields only (T-01-30).
    health_env.backend.raw_body = json.dumps({"providers": [{"api_key": SENTINEL}]})

    body = (await health_env.client.get("/health")).json()

    # The exact-key-set pin is a DELIBERATE premise change: the test exists to pin
    # the body's shape, and the shape now has one more reported dependency (`cv`).
    assert set(body) == {"status", "db", "opencode", "tectonic", "cv", "sources"}
    assert set(_all_keys(body)) & FORBIDDEN_BODY_KEYS == set()
    assert SENTINEL not in json.dumps(body)


# --- the LaTeX engine is reported, never raised (CV-05 / T-04-05) -------------


class _ProbeEngine:
    """A LatexEngine-shaped stub whose probe outcome is fixed."""

    def __init__(self, probe: EngineProbe) -> None:
        self._probe = probe

    async def health(self) -> EngineProbe:
        return self._probe

    async def compile(self, **kwargs: Any) -> Any:  # pragma: no cover - never called
        return None


class _ExplodingEngine:
    """A LatexEngine stub that raises: `/health` must still answer 200."""

    async def health(self) -> EngineProbe:
        raise RuntimeError("engine exploded")

    async def compile(self, **kwargs: Any) -> Any:  # pragma: no cover - never called
        return None


async def test_health_always_reports_a_tectonic_object(
    health_env: HealthEnv,
) -> None:
    response = await health_env.client.get("/health")

    assert response.status_code == 200
    tectonic = response.json()["tectonic"]
    assert set(tectonic) == {"available", "version", "error"}
    assert isinstance(tectonic["available"], bool)


async def test_health_reports_a_missing_engine_at_200_without_degrading_status(
    health_env: HealthEnv,
) -> None:
    health_env.app.dependency_overrides[get_latex_engine] = lambda: _ProbeEngine(
        EngineProbe(available=False, error="not_found")
    )

    response = await health_env.client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok", "a missing engine must not degrade the app"
    assert body["tectonic"] == {
        "available": False,
        "version": None,
        "error": "not_found",
    }


async def test_health_reports_a_raising_engine_instead_of_propagating(
    health_env: HealthEnv,
) -> None:
    health_env.app.dependency_overrides[get_latex_engine] = lambda: _ExplodingEngine()

    response = await health_env.client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["tectonic"]["available"] is False
    assert body["tectonic"]["error"] == "RuntimeError"
    assert body["status"] == "ok"


# --- the CV fact store is reported, never raised (G-05-2 / RANK-08) -----------


async def test_health_always_reports_a_cv_object(health_env: HealthEnv) -> None:
    response = await health_env.client.get("/health")

    assert response.status_code == 200
    cv = response.json()["cv"]
    assert set(cv) == {"available", "path", "error"}
    assert isinstance(cv["available"], bool)


async def test_health_reports_a_missing_store_without_degrading_status(
    health_env: HealthEnv, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path / "empty"))

    response = await health_env.client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok", "a missing fact store must not degrade the app"
    assert body["cv"]["available"] is False
    assert body["cv"]["error"] == "CvFactStoreError"
    assert body["cv"]["path"] == str(tmp_path / "empty" / "cv.yaml")


async def test_health_reports_a_readable_store(
    health_env: HealthEnv, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "cv.yaml").write_text(
        CV_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))

    body = (await health_env.client.get("/health")).json()

    assert body["cv"]["available"] is True
    assert body["cv"]["error"] is None
    assert body["status"] == "ok"


async def test_the_queue_page_renders_the_cv_status_line(
    health_env: HealthEnv,
) -> None:
    response = await health_env.client.get("/")

    assert response.status_code == 200
    assert 'id="cv-fact-store-status"' in response.text
    assert str(Path(settings.cv_dir) / "cv.yaml") in response.text


# --- the visible health strip (D-13) ------------------------------------------


async def test_the_queue_page_renders_the_strip_and_the_llm_indicator(
    health_env: HealthEnv,
) -> None:
    response = await health_env.client.get("/")

    assert response.status_code == 200
    assert 'id="source-health"' in response.text
    assert 'id="llm-backend-unreachable"' in response.text
    assert "LLM backend unreachable" in response.text


async def test_the_strip_reports_a_reachable_backend(
    health_env: HealthEnv,
) -> None:
    health_env.backend.outcome = ProbeOutcome(reachable=True, version="9.9.9")

    response = await health_env.client.get("/")

    assert 'id="llm-backend-reachable"' in response.text
    assert "version 9.9.9" in response.text


async def test_the_strip_names_missing_auth_when_the_backend_is_unreachable(
    health_env: HealthEnv,
) -> None:
    # Default lane: no password configured and the stub backend is unreachable.
    response = await health_env.client.get("/")

    assert 'id="llm-backend-auth-missing"' in response.text
    assert "OPENCODE_SERVER_PASSWORD" in response.text


async def test_the_strip_omits_the_auth_hint_once_a_password_is_configured(
    health_env: HealthEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "opencode_server_password", "a-real-password")

    response = await health_env.client.get("/")

    # An auth-configured-but-unreachable backend is a different situation.
    assert 'id="llm-backend-auth-missing"' not in response.text
    assert 'id="llm-backend-unreachable"' in response.text


async def test_the_strip_renders_last_success_returned_and_fill_rate(
    health_env: HealthEnv,
) -> None:
    await _seed_source_run_and_listings(health_env.session_factory)

    response = await health_env.client.get("/")

    assert response.status_code == 200
    match = re.search(
        r'<tr class="health-row" id="source-health-indeed".*?</tr>',
        response.text,
        re.DOTALL,
    )
    assert match is not None, "the strip rendered no row for indeed"
    block = match.group(0)

    assert 'class="health-source" data-label="Source">indeed' in block
    assert 'class="health-returned" data-label="Returned">2' in block
    assert "never" not in block, "a recorded last success must render as a timestamp"
    # A blank description counts as empty: 1 of 2 filled, not 2 of 2 (RESEARCH S2).
    assert "description 50%" in block
    assert "title 100%" in block


def test_the_strip_template_declares_the_three_health_columns() -> None:
    text = STRIP_TEMPLATE.read_text(encoding="utf-8")

    assert "health-last-success" in text
    assert "health-returned" in text
    assert "health-fill-rate" in text


def test_the_queue_page_includes_the_strip() -> None:
    assert '_health_strip.html' in QUEUE_TEMPLATE.read_text(encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
