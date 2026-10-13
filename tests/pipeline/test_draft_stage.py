"""D-125 / D-119 — the screening-drafting stage end to end.

A stubbed backend implements `complete_structured` and records what it received, so
the call SHAPE is asserted directly: exactly one call per draft, the frozen system
prompt, the CV facts/listing/questions all in the parts, one audit row with
`run_id=None`, a refusal BEFORE any call, and a transport error as a value.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import Listing, LlmCall
from app.domain.schemas.screening import ScreeningAnswer, ScreeningDraftResponse
from app.llm import detection
from app.llm.base import DiscoveryResult, ProbeOutcome, StructuredCallResult
from app.pipeline import draft as draft_module
from app.pipeline import rank as rank_module
from app.pipeline.draft import DRAFT_SYSTEM_PROMPT, draft_screening_answers
from tests.llm.test_v2_generate import Recorder, _v2_backend
from tests.pipeline.test_rank_stage import _add_listing, _facts

NOW = datetime(2026, 9, 30, tzinfo=UTC)

KNOWN_BULLET = "bul/northwind-labs-2021/1"


class StubBackend:
    """A fixed structured response that records the calls it received."""

    def __init__(
        self,
        response: ScreeningDraftResponse | None = None,
        *,
        fail: bool = False,
        raise_on_call: bool = False,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._response = response or ScreeningDraftResponse(
            answers=[
                ScreeningAnswer(
                    question="Have you cut latency?",
                    answer="Yes — I reduced p99 latency by 40%.",
                    evidence_ids=[KNOWN_BULLET],
                ),
                ScreeningAnswer(
                    question="Do you know Kubernetes?",
                    answer="Yes, extensively.",
                    evidence_ids=["bul/does-not-exist/9"],
                ),
            ]
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
            ok=True, status="ok", data=self._response, provider="opencode", model="minimax-m3"
        )


@pytest.fixture(autouse=True)
def _reset_in_flight(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The shared in-flight counter is module-level; a leaked slot would poison tests."""
    monkeypatch.setattr(rank_module, "_in_flight", 0)
    yield
    monkeypatch.setattr(rank_module, "_in_flight", 0)


@pytest.fixture(autouse=True)
def _clear_surface_cache() -> Iterator[None]:
    """A recorder's probe must be authoritative; a leaked V1/V2 verdict is not."""
    detection.clear_cache()
    yield
    detection.clear_cache()


# --- the frozen prompt ---------------------------------------------------------


def test_the_draft_system_prompt_is_a_frozen_constant_with_no_interpolation() -> None:
    """T-07-03-01: untrusted content has no path into `system`."""
    source = (Path(__file__).resolve().parents[2] / "app" / "pipeline" / "draft.py").read_text(
        encoding="utf-8"
    )

    assert "DRAFT_SYSTEM_PROMPT = (" in source, "must be a module-level plain literal"
    assert "DRAFT_SYSTEM_PROMPT = f" not in source
    assert "{" not in DRAFT_SYSTEM_PROMPT
    assert "%s" not in DRAFT_SYSTEM_PROMPT


# --- the one call shape --------------------------------------------------------


async def test_exactly_one_call_carries_the_listing_questions_and_cv_facts(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _add_listing(session_factory, title="Alpha Draft Role")
    stub = StubBackend()

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        verdicts = await draft_screening_answers(
            stub,
            session,
            listing=listing,
            facts=_facts(),
            questions=["Why this role?", "Notice period?"],
            now=NOW,
        )
        await session.commit()

    assert verdicts is not None
    assert len(stub.calls) == 1, "exactly one call per draft"
    call = stub.calls[0]
    assert call["system"] == DRAFT_SYSTEM_PROMPT
    assert call["tools"] == (), "tools is explicitly empty on every drafting call"
    assert call["schema"] is ScreeningDraftResponse
    assert "Alpha Draft Role" in call["text"], "the one listing is in the parts"
    assert "Why this role?" in call["text"], "the questions are in the parts"
    assert "Northwind Labs" in call["text"], "the CV facts are in the parts"


async def test_the_returned_verdicts_carry_the_grounding_flags(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _add_listing(session_factory, title="Grounded Role")

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        verdicts = await draft_screening_answers(
            StubBackend(),
            session,
            listing=listing,
            facts=_facts(),
            questions=["Q1", "Q2"],
            now=NOW,
        )
        await session.commit()

    assert verdicts is not None
    assert len(verdicts) == 2
    assert verdicts[0].unsupported is False
    assert verdicts[0].grounded_evidence_ids == [KNOWN_BULLET]
    assert verdicts[1].unsupported is True
    assert any("bul/does-not-exist/9" in w for w in verdicts[1].warnings)


# --- the audit trail -----------------------------------------------------------


async def test_a_successful_call_writes_one_row_with_a_null_run_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _add_listing(session_factory, title="Row Draft Role")

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        await draft_screening_answers(
            StubBackend(), session, listing=listing, facts=_facts(), questions=["Q"], now=NOW
        )
        await session.commit()

    async with session_factory() as session:
        rows = (await session.execute(select(LlmCall))).scalars().all()

    assert len(rows) == 1, "exactly one audit row per call"
    assert rows[0].purpose == "tailor"
    assert rows[0].run_id is None, "an interactive draft has no run"
    assert rows[0].status == "ok"


async def test_a_failed_call_writes_one_row_and_returns_none(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _add_listing(session_factory, title="Broken Draft Role")

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        result = await draft_screening_answers(
            StubBackend(fail=True),
            session,
            listing=listing,
            facts=_facts(),
            questions=["Q"],
            now=NOW,
        )
        await session.commit()

    assert result is None

    async with session_factory() as session:
        rows = (await session.execute(select(LlmCall))).scalars().all()

    assert len(rows) == 1
    assert rows[0].purpose == "tailor"


async def test_a_raised_backend_error_writes_one_class_only_row_and_returns_none(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _add_listing(session_factory, title="Raising Draft Role")

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        result = await draft_screening_answers(
            StubBackend(raise_on_call=True),
            session,
            listing=listing,
            facts=_facts(),
            questions=["Q"],
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


# --- the ceiling is enforced BEFORE the call -----------------------------------


async def test_a_cap_refusal_writes_one_budget_row_and_makes_no_call(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listing_id = await _add_listing(session_factory, title="Capped Draft Role")
    monkeypatch.setattr(settings, "ranking_max_calls_per_day", 0)
    stub = StubBackend()

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        result = await draft_screening_answers(
            stub, session, listing=listing, facts=_facts(), questions=["Q"], now=NOW
        )
        await session.commit()

    assert result is None
    assert stub.calls == [], "a refusal must not reach the backend"

    async with session_factory() as session:
        rows = (await session.execute(select(LlmCall))).scalars().all()

    assert len(rows) == 1
    assert rows[0].purpose == "tailor"
    assert rows[0].status == "error"
    assert rows[0].error is not None
    assert rows[0].error.startswith("budget_exceeded")
    assert rank_module._in_flight == 0, "a refusal reserves no slot to leak"


# --- the skip vocabulary -------------------------------------------------------


def test_drafting_disabled_skips_before_any_filesystem_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("load_facts must not be touched when drafting is disabled")

    monkeypatch.setattr(draft_module, "load_facts", _boom)
    monkeypatch.setattr(settings, "apply_drafting_enabled", False)

    assert draft_module.drafting_skip_reason() == draft_module.DRAFT_SKIP_DISABLED


def test_drafting_skip_reason_is_none_when_a_store_loads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "apply_drafting_enabled", True)
    monkeypatch.setattr(draft_module, "load_facts", lambda path: object())

    assert draft_module.drafting_skip_reason() is None


# --- FIX 1: the prompt, the extractor and the schema agree on the object shape --
#
# The live 07.1 failure: `DRAFT_SYSTEM_PROMPT` asked for a top-level JSON array,
# but `_extract_json` returns the first balanced `{…}` OBJECT and
# `ScreeningDraftResponse` requires an object with an `answers` array. The model's
# array-shaped reply was salvaged to one inner answer object, failed validation and
# surfaced as "The drafting call did not return a usable response."

#: The literal `generate` text for the agreed shape (CONVENTIONS rule 3: a literal
#: reproduction fixture, not assembled from the schema).
OBJECT_SHAPE_TEXT = json.dumps(
    {
        "answers": [
            {
                "question": "Have you cut latency?",
                "answer": "Yes — I reduced p99 latency by 40%.",
                "evidence_ids": [KNOWN_BULLET],
            },
            {
                "question": "Do you know Kubernetes?",
                "answer": "Yes, extensively.",
                "evidence_ids": ["bul/does-not-exist/9"],
            },
        ]
    }
)

#: The OLD shape the prompt used to request — a top-level JSON array. `_extract_json`
#: keeps only the first inner object, so this cannot validate as the schema.
OLD_ARRAY_SHAPE_TEXT = json.dumps(
    [
        {
            "question": "Have you cut latency?",
            "answer": "Yes — I reduced p99 latency by 40%.",
            "evidence_ids": [KNOWN_BULLET],
        },
        {
            "question": "Do you know Kubernetes?",
            "answer": "Yes, extensively.",
            "evidence_ids": ["bul/does-not-exist/9"],
        },
    ]
)


def test_the_prompt_instructs_the_object_shape_the_schema_requires() -> None:
    """Drift guard: the prompt must request the OBJECT `_extract_json` returns.

    Anchored on ``ScreeningDraftResponse``/``ScreeningAnswer.model_fields`` so a field
    rename fails this, and on the "single JSON object" instruction that the old
    array-shaped prompt lacked — that is the exact drift that broke the live run.
    """
    assert "single JSON object" in DRAFT_SYSTEM_PROMPT, (
        "`_extract_json` returns the first balanced {...} OBJECT and "
        "`ScreeningDraftResponse` requires one — the prompt must ask for a single "
        "JSON object, not a top-level array"
    )
    top_level = next(iter(ScreeningDraftResponse.model_fields))
    assert f'"{top_level}"' in DRAFT_SYSTEM_PROMPT
    for field in ScreeningAnswer.model_fields:
        assert f'"{field}"' in DRAFT_SYSTEM_PROMPT


async def test_the_object_shape_reaches_a_usable_grounded_draft_end_to_end(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model text → `_extract_json` → `_salvage` → `draft_screening_answers`.

    The real `OpenCodeServerBackend` (no socket) turns the recorded object-shaped V2
    reply into a usable `ScreeningDraftResponse`, and the drafting consumer into
    grounded verdicts — the path the array-shaped prompt broke.
    """
    listing_id = await _add_listing(session_factory, title="Object Shape Role")
    recorder = Recorder(generate=(200, {"data": {"text": OBJECT_SHAPE_TEXT}}))
    backend = _v2_backend(monkeypatch, recorder)

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        verdicts = await draft_screening_answers(
            backend,
            session,
            listing=listing,
            facts=_facts(),
            questions=["Have you cut latency?", "Do you know Kubernetes?"],
            now=NOW,
        )
        await session.commit()

    assert verdicts is not None
    assert [verdict.unsupported for verdict in verdicts] == [False, True]


async def test_the_old_top_level_array_shape_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative control: the shape the prompt used to request yields no draft."""
    listing_id = await _add_listing(session_factory, title="Array Shape Role")
    recorder = Recorder(generate=(200, {"data": {"text": OLD_ARRAY_SHAPE_TEXT}}))
    backend = _v2_backend(monkeypatch, recorder)

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        verdicts = await draft_screening_answers(
            backend,
            session,
            listing=listing,
            facts=_facts(),
            questions=["Have you cut latency?"],
            now=NOW,
        )
        await session.commit()

    assert verdicts is None


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
