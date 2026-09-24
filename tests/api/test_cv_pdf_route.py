"""UI-05 / T-06-19 / T-06-22 — the PDF route: inline preview, on-demand download, 404.

The route reads its artifact through the `ok`-only repository selection, so a blocked
or failed row (or no row at all) is a 404 HTML fragment. The served path is always the
row's own stored `pdf_path`; the download filename is built from the two integer ids,
and a request carrying a path-like parameter still serves the row's own file.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.repositories import cv_artifact_repo
from tests.api.test_listing_detail import _register_sources, _seed_listing

NOW = datetime(2026, 9, 24, 11, 0, 0, tzinfo=UTC)


@pytest.fixture
def pdf_client(client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AsyncClient:
    """The app client with `artifacts_dir` pointed at a per-test temp directory."""
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "artifacts_dir", str(artifacts))
    return client


def _write_pdf(name: str = "cv.pdf", body: bytes = b"%PDF-1.4 real enough\n") -> str:
    base = Path(settings.artifacts_dir) / "1"
    base.mkdir(parents=True, exist_ok=True)
    path = base / name
    path.write_bytes(body)
    return str(path)


async def _seed_artifact(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    listing_id: int,
    compile_status: str = "ok",
    pdf_path: str | None = None,
    now: datetime = NOW,
):
    async with session_factory() as session:
        record = await cv_artifact_repo.insert_artifact(
            session,
            listing_id=listing_id,
            base_cv_version_id=None,
            patch_json={"listing_id": listing_id},
            change_log_json=[],
            compile_status=compile_status,
            verification_json={"passed": compile_status == "ok"},
            page_count=1 if compile_status == "ok" else None,
            tex_path="/artifacts/1/cv.tex",
            pdf_path=pdf_path,
            now=now,
        )
        await session.commit()
        return record


async def _seed_listing_id(session_factory: async_sessionmaker[AsyncSession]) -> int:
    await _register_sources(session_factory, "linkedin")
    return await _seed_listing(session_factory, index=41, title="PDF Route Role")


# --- the ok artifact -----------------------------------------------------------


async def test_the_default_disposition_is_inline(
    pdf_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_listing_id(session_factory)
    await _seed_artifact(session_factory, listing_id=listing_id, pdf_path=_write_pdf())

    response = await pdf_client.get(f"/listings/{listing_id}/cv/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"].startswith("inline")
    assert response.content.startswith(b"%PDF")


async def test_download_1_sets_an_attachment_disposition(
    pdf_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_listing_id(session_factory)
    await _seed_artifact(session_factory, listing_id=listing_id, pdf_path=_write_pdf())

    response = await pdf_client.get(f"/listings/{listing_id}/cv/pdf?download=1")

    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment")
    assert disposition.rstrip('"').endswith(".pdf")


async def test_a_missing_file_is_a_404_not_a_500(
    pdf_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_listing_id(session_factory)
    missing = str(Path(settings.artifacts_dir) / "1" / "gone.pdf")
    await _seed_artifact(session_factory, listing_id=listing_id, pdf_path=missing)

    response = await pdf_client.get(f"/listings/{listing_id}/cv/pdf")

    assert response.status_code == 404
    assert 'data-error="no-ok-artifact"' in response.text


# --- the refusals --------------------------------------------------------------


async def test_a_blocked_only_listing_returns_404(
    pdf_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_listing_id(session_factory)
    await _seed_artifact(session_factory, listing_id=listing_id, compile_status="blocked")

    response = await pdf_client.get(f"/listings/{listing_id}/cv/pdf")

    assert response.status_code == 404
    assert 'data-error="no-ok-artifact"' in response.text


async def test_a_failed_only_listing_returns_404(
    pdf_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_listing_id(session_factory)
    await _seed_artifact(session_factory, listing_id=listing_id, compile_status="failed")

    response = await pdf_client.get(f"/listings/{listing_id}/cv/pdf")

    assert response.status_code == 404


async def test_no_artifact_returns_404(
    pdf_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_listing_id(session_factory)

    response = await pdf_client.get(f"/listings/{listing_id}/cv/pdf")

    assert response.status_code == 404


# --- the path is never built from request text ---------------------------------


async def test_the_route_ignores_a_path_like_query_param(
    pdf_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_listing_id(session_factory)
    await _seed_artifact(session_factory, listing_id=listing_id, pdf_path=_write_pdf())

    response = await pdf_client.get(
        f"/listings/{listing_id}/cv/pdf?path=/etc/passwd&filename=../../etc/passwd"
    )

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF"), "the row's own file is served"


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
