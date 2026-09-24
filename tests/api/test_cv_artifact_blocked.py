"""TAIL-05 / PITFALLS P14 — the failure-path suite: a blocked CV is unreachable.

A `blocked` or `failed` artifact must not be downloadable by route OR by repository
accessor, a newer blocked attempt must not hide an older verified CV, and a warn-only
artifact must still download (D-114). The blocked page must explain the failure from its
persisted findings and offer no repair control (D-118 / TAIL-05).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.repositories import cv_artifact_repo
from app.db.repositories.cv_artifact_repo import latest_for_listing, read_for_download
from tests.api.test_listing_detail import _seed_scored_listing

NOW = datetime(2026, 9, 24, 12, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 24, 12, 0, 5, tzinfo=UTC)

BLOCKED_VERIFICATION = {
    "passed": False,
    "checks": [
        {
            "id": "metric_containment",
            "status": "fail",
            "detail": "1 numeric token is absent from its region's source facts",
            "offending": ["exp/northwind-labs-2021:95"],
        },
        {
            "id": "page_budget",
            "status": "warn",
            "detail": "the rendered CV is 3 page(s) against a budget of 2",
            "offending": [],
        },
    ],
}
WARN_ONLY_VERIFICATION = {
    "passed": True,
    "checks": [
        {
            "id": "page_budget",
            "status": "warn",
            "detail": "the rendered CV is 3 page(s) against a budget of 2",
            "offending": [],
        }
    ],
}


@pytest.fixture
def blocked_client(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncClient:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "artifacts_dir", str(artifacts))
    return client


def _write_pdf(name: str = "cv.pdf", body: bytes = b"%PDF-1.4 the verified one\n") -> str:
    base = Path(settings.artifacts_dir) / "1"
    base.mkdir(parents=True, exist_ok=True)
    path = base / name
    path.write_bytes(body)
    return str(path)


async def _seed_artifact(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    listing_id: int,
    compile_status: str,
    verification_json: dict,
    now: datetime,
    pdf_path: str | None = None,
):
    async with session_factory() as session:
        record = await cv_artifact_repo.insert_artifact(
            session,
            listing_id=listing_id,
            base_cv_version_id=None,
            patch_json={"listing_id": listing_id},
            change_log_json=[],
            compile_status=compile_status,
            verification_json=verification_json,
            page_count=1,
            tex_path="/artifacts/1/cv.tex",
            pdf_path=pdf_path,
            now=now,
        )
        await session.commit()
        return record


async def _seed_listing_id(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """A SCORED listing: the page's blocked state needs a stored score (D-110)."""
    return await _seed_scored_listing(session_factory, title="Blocked Artifact Role")


# --- blocked and failed are unreachable ----------------------------------------


async def test_a_blocked_artifact_is_never_downloadable(
    blocked_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_listing_id(session_factory)
    # `pdf_path` is set deliberately: even a blocked row that points at a real file
    # must not be served.
    record = await _seed_artifact(
        session_factory,
        listing_id=listing_id,
        compile_status="blocked",
        verification_json=BLOCKED_VERIFICATION,
        now=NOW,
        pdf_path=_write_pdf(),
    )

    pdf = await blocked_client.get(f"/listings/{listing_id}/cv/pdf")
    assert pdf.status_code == 404

    async with session_factory() as session:
        assert await latest_for_listing(session, listing_id, ok_only=True) is None
        assert await read_for_download(session, record.id, ok_only=True) is None

    page = await blocked_client.get(f"/listings/{listing_id}/cv")
    body = page.text
    assert "metric_containment" in body, "the failing check is named"
    assert "Why this CV was blocked" in body
    assert "/cv/pdf" not in body, "a blocked artifact has no download affordance"
    assert "repair" not in body.casefold(), "no repair control is offered"


async def test_a_failed_artifact_is_never_downloadable(
    blocked_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_listing_id(session_factory)
    record = await _seed_artifact(
        session_factory,
        listing_id=listing_id,
        compile_status="failed",
        verification_json={"passed": False, "checks": []},
        now=NOW,
    )

    pdf = await blocked_client.get(f"/listings/{listing_id}/cv/pdf")
    assert pdf.status_code == 404

    async with session_factory() as session:
        assert await latest_for_listing(session, listing_id, ok_only=True) is None
        assert await read_for_download(session, record.id, ok_only=True) is None


# --- recency never beats the ok-only selection ---------------------------------


async def test_a_blocked_row_over_an_ok_row_still_serves_the_ok_pdf(
    blocked_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_listing_id(session_factory)
    ok_bytes = b"%PDF-1.4 the older verified artifact\n"
    await _seed_artifact(
        session_factory,
        listing_id=listing_id,
        compile_status="ok",
        verification_json={"passed": True, "checks": []},
        now=NOW,
        pdf_path=_write_pdf("ok.pdf", ok_bytes),
    )
    await _seed_artifact(
        session_factory,
        listing_id=listing_id,
        compile_status="blocked",
        verification_json=BLOCKED_VERIFICATION,
        now=LATER,
        pdf_path=_write_pdf("blocked.pdf", b"%PDF-1.4 the blocked newer artifact\n"),
    )

    response = await blocked_client.get(f"/listings/{listing_id}/cv/pdf")

    assert response.status_code == 200
    assert response.content == ok_bytes, "the ok-only selection wins over recency"


# --- warn-only is not blocked (D-114) ------------------------------------------


async def test_a_warn_only_artifact_is_downloadable(
    blocked_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_listing_id(session_factory)
    record = await _seed_artifact(
        session_factory,
        listing_id=listing_id,
        compile_status="ok",
        verification_json=WARN_ONLY_VERIFICATION,
        now=NOW,
        pdf_path=_write_pdf(),
    )

    assert record.compile_status == "ok"

    async with session_factory() as session:
        selected = await latest_for_listing(session, listing_id, ok_only=True)
    assert selected is not None and selected.id == record.id

    response = await blocked_client.get(f"/listings/{listing_id}/cv/pdf")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
