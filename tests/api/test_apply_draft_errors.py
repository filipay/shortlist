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
from app.domain.schemas.screening import ScreeningDraftResponse
from app.llm.base import StructuredCallResult
from tests.api.test_apply_package import (
    FIXTURE,
    _seed_artifact,
    _seed_drafts,
    _seed_listing,
)
from tests.conftest import OfflineLLMBackend


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


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
