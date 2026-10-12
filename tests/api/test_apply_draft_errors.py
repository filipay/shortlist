"""G-07-2 — the draft route tells an unusable response apart from an empty one.

The UAT recorded a schema-invalid model response collapsing into the same 502
``drafting_empty`` copy the route uses for a genuinely empty-but-valid response.
These tests drive the real route with an overridden offline backend so the two
refusals are asserted to carry different reasons and different copy, and neither
wipes the user's stored drafts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import ScreeningDraft
from app.db.repositories.apply_config_repo import DEFAULT_QUESTIONS
from app.domain.schemas.screening import ScreeningAnswer, ScreeningDraftResponse
from app.llm import opencode_server
from app.llm.base import StructuredCallResult
from tests.api.test_apply_package import (
    FIXTURE,
    _seed_artifact,
    _seed_drafts,
    _seed_listing,
)
from tests.conftest import OfflineLLMBackend
from tests.llm.test_salvage import LITERAL_CAPTURED_PAYLOAD


async def _stored_questions(
    session_factory: async_sessionmaker[AsyncSession], listing_id: int
) -> list[str]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(ScreeningDraft).where(ScreeningDraft.listing_id == listing_id)
            )
        ).scalars().all()
    return [row.question_text for row in rows]


async def _post_with_result(
    client: Any,
    monkeypatch: Any,
    listing_id: int,
    result: StructuredCallResult,
) -> Any:
    async def _stub(self: Any, **kwargs: Any) -> StructuredCallResult:
        return result

    monkeypatch.setattr(OfflineLLMBackend, "complete_structured", _stub)
    return await client.post(f"/listings/{listing_id}/apply/draft")


async def test_a_schema_invalid_response_is_reported_as_unusable(
    client,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`status="invalid"` (the recorded list-type failure) is NOT "returned no answers"."""
    (tmp_path / "cv.yaml").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))

    listing_id = await _seed_listing(session_factory)
    await _seed_artifact(session_factory, listing_id, status="ok")
    await _seed_drafts(
        session_factory, listing_id, [{"question": "Kept question", "answer": "kept answer"}]
    )

    response = await _post_with_result(
        client,
        monkeypatch,
        listing_id,
        StructuredCallResult(
            ok=False,
            status="invalid",
            error="validation failed: Input should be a valid list",
        ),
    )

    assert response.status_code == 502
    assert 'data-error="drafting_failed"' in response.text
    assert "did not return a usable response" in response.text
    # Honest copy: it must not claim the model returned nothing, nor invent an
    # unreachable backend (the backend answered — the payload was unparseable).
    assert "returned no answers" not in response.text
    assert "unreachable" not in response.text.lower()
    assert await _stored_questions(session_factory, listing_id) == ["Kept question"]


async def test_a_valid_but_empty_response_is_reported_as_empty(
    client,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "cv.yaml").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))

    listing_id = await _seed_listing(session_factory, index=2)
    await _seed_artifact(session_factory, listing_id, status="ok")
    await _seed_drafts(
        session_factory, listing_id, [{"question": "Kept question", "answer": "kept answer"}]
    )

    response = await _post_with_result(
        client,
        monkeypatch,
        listing_id,
        StructuredCallResult(
            ok=True, status="ok", data=ScreeningDraftResponse(answers=[])
        ),
    )

    assert response.status_code == 502
    assert 'data-error="drafting_empty"' in response.text
    assert "returned no answers" in response.text
    assert await _stored_questions(session_factory, listing_id) == ["Kept question"]


async def test_the_two_refusals_share_neither_reason_nor_copy(
    client,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The distinctness guarantee: two causes, two reasons, two messages."""
    (tmp_path / "cv.yaml").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))

    listing_id = await _seed_listing(session_factory, index=3)
    await _seed_artifact(session_factory, listing_id, status="ok")
    await _seed_drafts(
        session_factory, listing_id, [{"question": "Kept question", "answer": "kept answer"}]
    )

    unusable = await _post_with_result(
        client,
        monkeypatch,
        listing_id,
        StructuredCallResult(ok=False, status="invalid", error="schema invalid"),
    )
    empty = await _post_with_result(
        client,
        monkeypatch,
        listing_id,
        StructuredCallResult(ok=True, status="ok", data=ScreeningDraftResponse(answers=[])),
    )

    assert 'data-error="drafting_failed"' in unusable.text
    assert 'data-error="drafting_empty"' in empty.text
    assert unusable.text != empty.text
    # Both are 5xx and both keep the seeded draft.
    assert unusable.status_code == 502
    assert empty.status_code == 502
    assert await _stored_questions(session_factory, listing_id) == ["Kept question"]


async def test_a_partial_response_keeps_unanswered_ad_hoc_rows(
    client,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    """CR-01: a valid-but-partial response must not delete unanswered/ad-hoc rows.

    The verifier's reproduction, locked in. Seven questions are asked (four
    ``DEFAULT_QUESTIONS`` plus three seeded ad-hoc rows) and the model returns ONE
    answer. The route must refuse with ``drafting_partial`` BEFORE reaching
    ``replace_for_listing`` (whose first act is a DELETE), so all three ad-hoc
    ``question_text`` values survive — three rows stay three, not collapse to one.
    """
    (tmp_path / "cv.yaml").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))

    listing_id = await _seed_listing(session_factory, index=4)
    await _seed_artifact(session_factory, listing_id, status="ok")
    ad_hoc = ["Ad-hoc A", "Ad-hoc B", "Ad-hoc C"]
    await _seed_drafts(
        session_factory,
        listing_id,
        [{"question": question, "answer": f"answer for {question}"} for question in ad_hoc],
    )

    partial = ScreeningDraftResponse(
        answers=[
            ScreeningAnswer(
                question=DEFAULT_QUESTIONS[0],
                answer="Because I build pipelines.",
                evidence_ids=[],
            )
        ]
    )
    response = await _post_with_result(
        client,
        monkeypatch,
        listing_id,
        StructuredCallResult(ok=True, status="ok", data=partial),
    )

    assert response.status_code == 502
    assert 'data-error="drafting_partial"' in response.text
    assert "Your existing drafts were kept." in response.text
    stored = await _stored_questions(session_factory, listing_id)
    assert set(stored) == set(ad_hoc), "every seeded ad-hoc question must survive"
    assert len(stored) == 3, "3 seeded rows must remain 3, not collapse to 1"


async def test_a_complete_response_persists_the_full_asked_set(
    client,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The partial guard must not over-refuse: one answer per asked question → 200."""
    (tmp_path / "cv.yaml").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))

    listing_id = await _seed_listing(session_factory, index=5)
    await _seed_artifact(session_factory, listing_id, status="ok")
    ad_hoc = ["Ad-hoc A", "Ad-hoc B", "Ad-hoc C"]
    await _seed_drafts(
        session_factory,
        listing_id,
        [{"question": question, "answer": f"answer for {question}"} for question in ad_hoc],
    )

    asked = [*DEFAULT_QUESTIONS, *ad_hoc]
    complete = ScreeningDraftResponse(
        answers=[
            ScreeningAnswer(question=question, answer=f"answered {question}", evidence_ids=[])
            for question in asked
        ]
    )
    response = await _post_with_result(
        client,
        monkeypatch,
        listing_id,
        StructuredCallResult(ok=True, status="ok", data=complete),
    )

    assert response.status_code == 200
    stored = await _stored_questions(session_factory, listing_id)
    assert stored == asked, "a complete response persists the full asked set in order"


async def test_a_repeated_partial_post_is_idempotent_over_the_stored_set(
    client,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    """APPLY-01: the refusal writes no rows, so a second identical POST changes nothing."""
    (tmp_path / "cv.yaml").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))

    listing_id = await _seed_listing(session_factory, index=6)
    await _seed_artifact(session_factory, listing_id, status="ok")
    ad_hoc = ["Ad-hoc A", "Ad-hoc B", "Ad-hoc C"]
    await _seed_drafts(
        session_factory,
        listing_id,
        [{"question": question, "answer": f"answer for {question}"} for question in ad_hoc],
    )

    partial = ScreeningDraftResponse(
        answers=[
            ScreeningAnswer(
                question=DEFAULT_QUESTIONS[0],
                answer="Because I build pipelines.",
                evidence_ids=[],
            )
        ]
    )
    first = await _post_with_result(
        client, monkeypatch, listing_id, StructuredCallResult(ok=True, status="ok", data=partial)
    )
    after_first = await _stored_questions(session_factory, listing_id)
    second = await _post_with_result(
        client, monkeypatch, listing_id, StructuredCallResult(ok=True, status="ok", data=partial)
    )
    after_second = await _stored_questions(session_factory, listing_id)

    assert first.status_code == 502
    assert second.status_code == 502
    assert 'data-error="drafting_partial"' in first.text
    assert 'data-error="drafting_partial"' in second.text
    assert set(after_first) == set(ad_hoc), "the ad-hoc rows survive the first partial POST"
    assert after_first == after_second, "a repeated partial POST must not grow or shrink the set"
    assert len(after_second) == 3


async def test_the_literal_wrapped_payload_persists_four_rows(
    client,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    """G-07-7: the literal `{"item": ...}` payload is a usable draft, not a 502.

    The real route + stage run with the payload routed through the PRODUCTION
    ``_salvage`` (so the coercion is exercised, not bypassed). The wrapped
    ``evidence_ids`` must unwrap, all four ``DEFAULT_QUESTIONS`` must be answered
    (so the CR-01 partial guard does not trip), and four rows persist — never a
    ``drafting_failed`` refusal.
    """
    (tmp_path / "cv.yaml").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))

    listing_id = await _seed_listing(session_factory, index=7)
    await _seed_artifact(session_factory, listing_id, status="ok")

    salvaged = opencode_server._salvage(ScreeningDraftResponse, LITERAL_CAPTURED_PAYLOAD)
    response = await _post_with_result(
        client,
        monkeypatch,
        listing_id,
        StructuredCallResult(ok=True, status="ok", data=salvaged),
    )

    assert response.status_code == 200
    assert 'data-error="drafting_failed"' not in response.text
    stored = await _stored_questions(session_factory, listing_id)
    assert stored == list(DEFAULT_QUESTIONS), "all four asked questions persist"


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
