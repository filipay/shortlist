"""TAIL-01 / D-119 — the tailoring stage end to end.

A stubbed backend implements `complete_structured` and records what it received, so
the call SHAPE is asserted directly: exactly one call per generate, exactly one
listing per prompt, a frozen system prompt, and one audit row with `run_id=None`.
The rolling-24h read is purpose-aware (the O1 regression pin).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.cv.factstore import CvFactStoreError
from app.db.models import Listing, LlmCall
from app.db.repositories import llm_call_repo
from app.domain.cv import BulletWeight, TailoringPatch
from app.llm.base import DiscoveryResult, ProbeOutcome, StructuredCallResult
from app.pipeline import rank as rank_module
from app.pipeline import tailor as tailor_module
from app.pipeline.tailor import TAILOR_SYSTEM_PROMPT, tailor_listing
from tests.pipeline.test_rank_stage import _add_listing, _facts

NOW = datetime(2026, 9, 22, tzinfo=UTC)


class StubBackend:
    """A fixed structured response that records the calls it received."""

    def __init__(
        self,
        patch: TailoringPatch | None = None,
        *,
        fail: bool = False,
        raise_on_call: bool = False,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._patch = patch or TailoringPatch(
            listing_id=1,
            ops=[
                BulletWeight(
                    op="reweight_bullet",
                    bullet_id="bul/northwind-labs-2021/1",
                    weight=2.0,
                )
            ],
        )
        self._fail = fail
        self._raise_on_call = raise_on_call

    async def health(self) -> ProbeOutcome:
        return ProbeOutcome(reachable=True)

    async def discover_models(self) -> DiscoveryResult:
        return DiscoveryResult(reachable=True)

    async def complete_structured(
        self,
        *,
        schema: type,
        system: str,
        parts: Sequence[str],
        model: str | None = None,
        agent: str | None = None,
        tools: Sequence[str] = (),
        retries: int | None = None,
    ) -> StructuredCallResult:
        self.calls.append(
            {
                "system": system,
                "text": "\n".join(parts),
                "tools": tuple(tools),
                "schema": schema,
            }
        )
        if self._raise_on_call:
            raise RuntimeError("transport down")
        if self._fail:
            return StructuredCallResult(ok=False, status="invalid", error="schema invalid")
        return StructuredCallResult(
            ok=True, status="ok", data=self._patch, provider="opencode", model="minimax-m3"
        )


@pytest.fixture(autouse=True)
def _reset_in_flight(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The shared in-flight counter is module-level; a leaked slot would poison tests."""
    monkeypatch.setattr(rank_module, "_in_flight", 0)
    yield
    monkeypatch.setattr(rank_module, "_in_flight", 0)


# --- the frozen prompt ---------------------------------------------------------


def test_the_tailor_system_prompt_is_a_frozen_constant_with_no_interpolation() -> None:
    """T-06-01: untrusted content has no path into `system`."""
    source = (Path(__file__).resolve().parents[2] / "app" / "pipeline" / "tailor.py").read_text(
        encoding="utf-8"
    )

    assert "TAILOR_SYSTEM_PROMPT = (" in source, "must be a module-level plain literal"
    assert "TAILOR_SYSTEM_PROMPT = f" not in source
    assert "{" not in TAILOR_SYSTEM_PROMPT
    assert "%s" not in TAILOR_SYSTEM_PROMPT
    # The exclusivity rule the live duplicate-target refusal (InvalidPatchError) broke.
    assert "AT MOST ONE operation" in TAILOR_SYSTEM_PROMPT
    assert "never named twice" in TAILOR_SYSTEM_PROMPT
    # The never-invent sentences stay intact.
    assert "NEVER invent" in TAILOR_SYSTEM_PROMPT
    assert "never add a bullet" in TAILOR_SYSTEM_PROMPT


# --- the one call, one listing shape -------------------------------------------


async def test_exactly_one_call_carries_one_listing_and_the_stored_requirements(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _add_listing(session_factory, title="Alpha Tailor Role")
    stub = StubBackend()

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        outcome = await tailor_listing(
            stub,
            session,
            listing=listing,
            facts=_facts(),
            requirements=[{"text": "Kubernetes", "verdict": "gap", "evidence_id": None}],
            now=NOW,
        )
        await session.commit()

    assert isinstance(outcome.patch, TailoringPatch)
    assert len(stub.calls) == 1, "exactly one call per generate"
    call = stub.calls[0]
    assert call["system"] == TAILOR_SYSTEM_PROMPT
    assert call["tools"] == (), "tools is explicitly empty on every tailoring call"
    assert call["schema"] is TailoringPatch
    assert "Alpha Tailor Role" in call["text"], "the one listing is in the parts"
    assert "Kubernetes" in call["text"], "the stored requirement text is in the parts"
    assert "Northwind Labs" in call["text"], "the CV facts are in the parts"


async def test_a_successful_call_writes_one_tailor_row_with_a_null_run_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _add_listing(session_factory, title="Row Role")

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        await tailor_listing(
            StubBackend(), session, listing=listing, facts=_facts(), requirements=[], now=NOW
        )
        await session.commit()

    async with session_factory() as session:
        rows = (await session.execute(select(LlmCall))).scalars().all()

    assert len(rows) == 1, "exactly one audit row per call"
    assert rows[0].purpose == "tailor"
    assert rows[0].run_id is None, "an interactive tailor has no run"
    assert rows[0].status == "ok"


async def test_a_failed_call_writes_one_tailor_row_and_returns_none(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _add_listing(session_factory, title="Broken Role")

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        result = await tailor_listing(
            StubBackend(fail=True),
            session,
            listing=listing,
            facts=_facts(),
            requirements=[],
            now=NOW,
        )
        await session.commit()

    assert result is None

    async with session_factory() as session:
        rows = (await session.execute(select(LlmCall))).scalars().all()

    assert len(rows) == 1
    assert rows[0].purpose == "tailor"
    assert rows[0].run_id is None


async def test_a_raised_backend_error_still_writes_one_tailor_row_and_returns_none(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """WR-01: a raised transport error is a value — one class-only row, slot released."""
    listing_id = await _add_listing(session_factory, title="Raising Role")

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        result = await tailor_listing(
            StubBackend(raise_on_call=True),
            session,
            listing=listing,
            facts=_facts(),
            requirements=[],
            now=NOW,
        )
        await session.commit()

    assert result is None, "a raised backend error must not escape the pipeline"

    async with session_factory() as session:
        rows = (await session.execute(select(LlmCall))).scalars().all()

    assert len(rows) == 1
    assert rows[0].purpose == "tailor"
    assert rows[0].status == "error"
    assert rows[0].run_id is None
    assert rows[0].error == "RuntimeError", "the class only, never the message"
    assert rank_module._in_flight == 0, "the shared in-flight slot was released on the raise path"


# --- the skip vocabulary -------------------------------------------------------


def test_tailoring_disabled_skips_before_any_call_or_filesystem_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("load_facts must not be touched when tailoring is disabled")

    monkeypatch.setattr(tailor_module, "load_facts", _boom)
    monkeypatch.setattr(settings, "tailoring_enabled", False)

    assert tailor_module.tailoring_skip_reason() == tailor_module.TAILOR_SKIP_DISABLED


def test_tailoring_skip_reason_is_none_when_a_store_loads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "tailoring_enabled", True)
    monkeypatch.setattr(tailor_module, "load_facts", lambda path: object())

    assert tailor_module.tailoring_skip_reason() is None


def test_tailoring_skip_reason_reports_an_absent_fact_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _missing(path: object) -> object:
        raise CvFactStoreError("no store")

    monkeypatch.setattr(settings, "tailoring_enabled", True)
    monkeypatch.setattr(tailor_module, "load_facts", _missing)

    assert tailor_module.tailoring_skip_reason() == tailor_module.TAILOR_SKIP_FACT_STORE


# --- O1: the rolling-24h read is purpose-aware ---------------------------------


async def test_calls_since_is_purpose_aware_while_rank_calls_since_is_not(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    recent = datetime.now(UTC) - timedelta(hours=1)
    async with session_factory() as session:
        await llm_call_repo.record_llm_call(session, purpose="tailor", status="ok", now=recent)
        await llm_call_repo.record_llm_call(session, purpose="rank", status="ok", now=recent)
        await session.commit()

    async with session_factory() as session:
        assert await llm_call_repo.calls_since(session, purpose="tailor") == 1
        assert await llm_call_repo.calls_since(session, purpose="rank") == 1
        # The Phase-5 read still counts ONLY rank rows — the O1 regression pin.
        assert await llm_call_repo.rank_calls_since(session) == 1
        with pytest.raises(ValueError):
            await llm_call_repo.calls_since(session, purpose="bogus")


async def test_calls_since_excludes_rows_outside_the_window(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    recent = datetime.now(UTC) - timedelta(hours=1)
    stale = datetime.now(UTC) - timedelta(hours=25)
    async with session_factory() as session:
        await llm_call_repo.record_llm_call(session, purpose="tailor", status="ok", now=recent)
        await llm_call_repo.record_llm_call(session, purpose="tailor", status="ok", now=stale)
        await session.commit()

    async with session_factory() as session:
        assert await llm_call_repo.calls_since(session, purpose="tailor") == 1


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
