"""Success criterion 1, end to end: one REAL schema-constrained call through the app.

**Never runs in the default lane.** `pyproject.toml` sets
`addopts = "-m 'not live'"`, so the default suite structurally cannot open a socket
(D-53); this module is selected explicitly with `-m live`. The interpreter MUST
match the platform you run on — a musl container venv cannot load on a glibc host
(`ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`), exactly as
`tests/llm/test_contract_live.py` records. Run it in the container with
`.venv/bin/python`, or on the host with `.venv-host/bin/python`.

Unlike `tests/llm/test_contract_live.py` (spec fetch + diff only, D-57), this lane
performs the real call: it builds the app the way the shared `client` fixture does
and overrides `get_llm_backend` with the live `OpenCodeServerBackend` class instead
of the offline stub, then drives the actual `POST /settings/llm-test` route. That
route owns the one audit row, so this is the executable evidence that success
criterion 1 holds — not a one-off in-process monkeypatch.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.settings import LLM_TEST_PATH
from app.config import settings
from app.db.models import Base, LlmCall
from app.db.session import get_session, get_session_factory
from app.llm import get_llm_backend
from app.llm.opencode_server import OpenCodeServerBackend

pytestmark = pytest.mark.live

#: The one `parts[].type` a healthy structured response must carry (the server's
#: own injected tool), alongside the structured payload key.
TOOL_PART_TYPE = "tool"


@pytest_asyncio.fixture
async def live_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """The app over the temp DB, with the REAL backend dependency.

    The `client` fixture's other overrides are reproduced verbatim; the ONLY
    difference is `get_llm_backend`, which must be a CALLABLE: FastAPI invokes a
    dependency override as a provider, and `OfflineLLMBackend`/`OpenCodeServerBackend`
    (the class itself, which takes no required arguments) is callable while a bare
    `OpenCodeServerBackend()` instance is not.
    """
    from app.main import create_app

    app = create_app()

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_llm_backend] = OpenCodeServerBackend

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http

    app.dependency_overrides.clear()


async def _count(
    session_factory: async_sessionmaker[AsyncSession], table: str
) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(Base.metadata.tables[table])
            )
            or 0
        )


def _rendered_part_types(html: str) -> list[str]:
    """The part TYPE names the page rendered, parsed from the observation line."""
    marker = "Returned part types: "
    start = html.find(marker)
    assert start != -1, "the observation block was not rendered"
    tail = html[start + len(marker) :]
    line = tail.split("\n", 1)[0].split("<", 1)[0]
    return [part.strip() for part in line.split(",") if part.strip()]


async def test_a_real_schema_constrained_call_succeeds_end_to_end(
    live_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Reachability first, then the real route: 200, ok, tool part, one probe row."""
    # 1. Reachability FIRST, so an unreachable server fails as a NAMED check rather
    #    than as a mystery assertion deep in the rendered page.
    probe = await OpenCodeServerBackend().health()
    assert probe.reachable is True, (
        f"opencode serve is not reachable at {settings.opencode_base_url}: "
        f"{probe.error}"
    )
    assert probe.version is not None and probe.version.startswith("1.18"), (
        f"unexpected server version {probe.version!r}; the contract targets 1.18.31"
    )

    # 2. The audit table starts empty, so "exactly one row" cannot pass on residue.
    assert await _count(session_factory, "llm_calls") == 0
    assert await _count(session_factory, "runs") == 0

    # 3. The real call, through the real route, with the live backend.
    response = await live_client.post(LLM_TEST_PATH)

    assert response.status_code == 200
    assert "status <strong>ok</strong>" in response.text
    assert "Structured payload: present" in response.text
    assert f"Model: {settings.opencode_model}" in response.text
    assert TOOL_PART_TYPE in _rendered_part_types(response.text), (
        f"the response carried no {TOOL_PART_TYPE!r} part: "
        f"{_rendered_part_types(response.text)!r}"
    )

    # 4. Exactly one probe row with a NULL run id, and no runs row.
    assert await _count(session_factory, "llm_calls") == 1
    assert await _count(session_factory, "runs") == 0
    async with session_factory() as session:
        row = (await session.execute(select(LlmCall))).scalar_one()
    assert row.purpose == "probe"
    assert row.run_id is None
    assert row.status == "ok"
    assert row.server_version is not None


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-m", "live"])
