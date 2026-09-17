"""D-48 / D-50 / D-52 — one POST runs one call and records exactly one row.

The default lane overrides `get_llm_backend` with `OfflineLLMBackend`, so these
tests prove the route contract without a socket: exactly one `llm_calls` row with
`purpose='probe'` and `run_id IS NULL`, no `runs` row, the full D-52 detail
rendered (never a bare badge), and a plain (non-HTMX) form.

`record_llm_call`'s own contract — vocabulary validation before SQL, never
commits — is asserted at the bottom of this file.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import settings as settings_module
from app.api.settings import LLM_TEST_PATH, SELFTEST_SYSTEM_PROMPT, SELFTEST_USER_PART
from app.db.models import Base, LlmCall
from app.db.repositories.llm_call_repo import record_llm_call
from app.domain.schemas.probe import ProbeResult
from app.llm.base import StructuredCallResult
from tests.conftest import OfflineLLMBackend


async def _count(session_factory: async_sessionmaker[AsyncSession], table: str) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(select(func.count()).select_from(Base.metadata.tables[table])) or 0
        )


# --- the form is a plain POST, never an HTMX swap ------------------------------


async def test_the_selftest_form_is_a_plain_post(client) -> None:
    response = await client.get("/settings")

    assert response.status_code == 200
    assert '<form method="post" action="/settings/llm-test">' in response.text
    assert "hx-post" not in response.text


def test_the_route_path_is_the_documented_constant() -> None:
    assert LLM_TEST_PATH == "/settings/llm-test"


# --- one POST == one row == no run --------------------------------------------


async def test_one_post_writes_exactly_one_probe_row_and_no_run(client, session_factory) -> None:
    # Guard-can-fail: assert the empty starting state, so "exactly one" cannot
    # pass because another test or a prior run left a row behind.
    assert await _count(session_factory, "llm_calls") == 0
    assert await _count(session_factory, "runs") == 0

    response = await client.post(LLM_TEST_PATH)

    assert response.status_code == 200
    assert await _count(session_factory, "llm_calls") == 1
    assert await _count(session_factory, "runs") == 0

    async with session_factory() as session:
        row = (await session.execute(select(LlmCall))).scalar_one()
    assert row.purpose == "probe"
    assert row.run_id is None
    assert row.status == "error"  # the offline stub's honest outcome
    assert row.error == "offline-test-lane"


async def test_a_second_post_writes_a_second_row(client, session_factory) -> None:
    """Each invocation is one call — the route is not cached."""
    await client.post(LLM_TEST_PATH)
    await client.post(LLM_TEST_PATH)

    assert await _count(session_factory, "llm_calls") == 2


async def test_a_plain_get_performs_no_call_and_writes_no_row(client, session_factory) -> None:
    response = await client.get("/settings")

    assert response.status_code == 200
    assert await _count(session_factory, "llm_calls") == 0
    assert await _count(session_factory, "runs") == 0


# --- D-52: the full outcome is rendered, not a badge ---------------------------


async def test_the_response_renders_the_cause_attempts_and_latency(client, session_factory) -> None:
    response = await client.post(LLM_TEST_PATH)

    assert "status <strong>error</strong>" in response.text
    assert "offline-test-lane" in response.text
    assert "Attempts: 0" in response.text
    assert "Latency:" in response.text
    # Reload persistence: a subsequent GET renders the recorded row too.
    reloaded = await client.get("/settings")
    assert "offline-test-lane" in reloaded.text
    assert "Attempts: 0" in reloaded.text


async def test_the_page_renders_every_recorded_value(client, monkeypatch) -> None:
    """A rich result renders its values — not a class name or a bare badge."""

    async def _rich(self, **kwargs: object) -> StructuredCallResult:
        return StructuredCallResult(
            ok=True,
            data=ProbeResult(acknowledged=True),
            status="ok",
            attempts=2,
            latency_ms=1234,
            provider="opencode-go",
            model="deepseek-v4.1-flash",
            server_version="1.18.31",
            provider_tokens=22,
        )

    monkeypatch.setattr(OfflineLLMBackend, "complete_structured", _rich)

    response = await client.post(LLM_TEST_PATH)

    assert "status <strong>ok</strong>" in response.text
    assert "Attempts: 2" in response.text
    assert "1234 ms" in response.text
    assert "Provider: opencode-go" in response.text
    assert "Model: deepseek-v4.1-flash" in response.text
    assert "Server version: 1.18.31" in response.text


# --- the prompt boundary -------------------------------------------------------


async def test_the_system_prompt_is_rendered_so_constantness_is_checkable(
    client,
) -> None:
    response = await client.post(LLM_TEST_PATH)

    assert SELFTEST_SYSTEM_PROMPT in response.text
    # The canned adversarial snippet is the USER turn, never the system prompt.
    assert SELFTEST_USER_PART not in SELFTEST_SYSTEM_PROMPT


def test_the_system_prompt_is_a_literal_with_no_interpolation() -> None:
    """The trust boundary: no f-string, no `%`, no `.format`, no concatenation."""
    source = Path(settings_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(settings_module.__file__))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "SELFTEST_SYSTEM_PROMPT"
            for target in node.targets
        )
    )

    # Adjacent string literals fold to one Constant; a `+` or an f-string would not.
    assert isinstance(assignment.value, ast.Constant)
    assert isinstance(assignment.value.value, str)
    assert "%" not in assignment.value.value


# --- the repository contract ---------------------------------------------------


async def test_record_llm_call_rejects_an_unknown_purpose_before_sql(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ValueError, match="unknown purpose"):
        await record_llm_call(db_session, purpose="nonsense", status="ok")

    assert not any(isinstance(obj, LlmCall) for obj in db_session.new)


async def test_record_llm_call_rejects_an_unknown_status_before_sql(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ValueError, match="unknown status"):
        await record_llm_call(db_session, purpose="probe", status="nonsense")

    assert not any(isinstance(obj, LlmCall) for obj in db_session.new)


async def test_record_llm_call_never_commits(session_factory) -> None:
    """A caller that does not commit leaves no row — the caller owns the commit."""
    async with session_factory() as writer:
        await record_llm_call(writer, purpose="probe", status="ok")
        # deliberately no commit
    assert await _count(session_factory, "llm_calls") == 0


async def test_record_llm_call_maps_a_port_result(db_session: AsyncSession) -> None:
    result = StructuredCallResult(
        ok=False,
        status="invalid",
        error="schema mismatch",
        attempts=3,
        latency_ms=42,
        provider="opencode-go",
        model="deepseek-v4.1-flash",
        server_version="1.18.31",
        provider_tokens=17,
    )

    record = await record_llm_call(db_session, purpose="probe", status=result.status, result=result)

    assert record.purpose == "probe"
    assert record.status == "invalid"
    assert record.error == "schema mismatch"
    assert record.attempts == 3
    assert record.latency_ms == 42
    assert record.provider == "opencode-go"
    assert record.model == "deepseek-v4.1-flash"
    assert record.completion_tokens == 17
    # The column lands in plan 03-04; the returned record carries it from the call.
    assert record.server_version == "1.18.31"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
