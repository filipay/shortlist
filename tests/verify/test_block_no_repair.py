"""TAIL-06 / D-111 / D-115 / D-118 / P14 — a fail always BLOCKS, it never repairs.

Hermetic: a temporary ``artifacts_dir`` and an injected fake engine (never Tectonic),
with ``extract_pdf_text`` monkeypatched so no real PDF is needed. The load-bearing
pins are that a Layer-1 fail never reaches the engine, that a Layer-2 fail retains the
PDF it needs for diagnosis but stays unreachable to download, and that a blocked
artifact is never silently regenerated or mutated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import CvArtifact, Listing
from app.db.repositories import cv_artifact_repo
from app.db.repositories.cv_artifact_repo import CvArtifactRecord
from app.domain.cv import BulletWeight, GapFinding, TailoringPatch
from app.latex.base import CompileResult, EngineProbe
from app.pipeline import tailor as tailor_module
from app.pipeline.tailor import compile_tailored
from tests.pipeline.test_rank_stage import _add_listing
from tests.verify.fixtures import FACTS_YAML, VERIFY_FIXTURES, load_standin_facts

NOW = datetime(2026, 9, 24, tzinfo=UTC)
BULLET1 = "bul/northwind-labs-2021/1"


class FakeEngine:
    """A canned compile that records how many times it was reached."""

    def __init__(self, *, ok: bool = True) -> None:
        self.calls: list[str] = []
        self._ok = ok

    async def compile(self, *, tex: str, workdir: Path) -> CompileResult:
        self.calls.append(tex)
        workdir.mkdir(parents=True, exist_ok=True)
        if not self._ok:
            return CompileResult(ok=False, engine="fake", error="boom", error_kind="compile_error")
        pdf = workdir / "cv.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake\n")
        return CompileResult(
            ok=True,
            engine="fake",
            pdf_path=str(pdf),
            page_count=1,
            tex_hash="a" * 64,
            pdf_hash="b" * 64,
            compile_log="ok",
        )

    async def health(self) -> EngineProbe:
        return EngineProbe(available=True)


def _layer_one_blocking_patch(listing_id: int) -> TailoringPatch:
    """A ``direct`` finding with no evidence id fails ``requirement_evidence``."""
    return TailoringPatch(
        listing_id=listing_id,
        gaps=[GapFinding(requirement="Rust", status="direct", evidence_ids=[])],
    )


async def _compile(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
    *,
    title: str,
    patch: TailoringPatch,
    engine_ok: bool = True,
    extract_name: str | None = None,
) -> tuple[int, CvArtifactRecord, FakeEngine]:
    listing_id = await _add_listing(session_factory, title=title)
    if extract_name is not None:
        text = (VERIFY_FIXTURES / extract_name).read_text(encoding="utf-8")
        monkeypatch.setattr(tailor_module, "extract_pdf_text", lambda path: text)
    engine = FakeEngine(ok=engine_ok)
    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        record = await compile_tailored(
            session,
            listing=listing,
            facts=load_standin_facts(),
            patch=patch,
            base_cv_version_id=None,
            engine=engine,
            artifacts_dir=tmp_path / "artifacts",
            now=NOW,
        )
        await session.commit()
    return listing_id, record, engine


async def _rows(session_factory: async_sessionmaker[AsyncSession]) -> list[CvArtifact]:
    async with session_factory() as session:
        return list((await session.execute(select(CvArtifact))).scalars().all())


async def test_a_layer_one_fail_never_reaches_the_engine(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    listing_id, record, engine = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Layer One Blocked",
        patch=_layer_one_blocking_patch(1),
    )

    assert record.compile_status == "blocked"
    assert record.tex_path is None
    assert record.pdf_path is None
    assert record.verification_json, "a blocked row carries its findings"
    assert engine.calls == [], "a Layer-1 fail must never reach the engine"
    rows = await _rows(session_factory)
    assert len(rows) == 1


async def test_a_layer_two_fail_retains_the_pdf_but_is_not_downloadable(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    listing_id, record, engine = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Layer Two Blocked",
        patch=TailoringPatch(listing_id=1),
        extract_name="novel_metric_extract.txt",
    )

    assert record.compile_status == "blocked"
    assert record.pdf_path is not None, "a Layer-2 fail retains the PDF for diagnosis"
    assert engine.calls, "a Layer-2 fail is reached AFTER a real compile"

    async with session_factory() as session:
        reachable = await cv_artifact_repo.latest_for_listing(session, listing_id, ok_only=True)
    assert reachable is None, "a blocked artifact is unreachable through the default selection"


async def test_an_engine_failure_is_failed_not_blocked(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, record, engine = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Engine Failed",
        patch=TailoringPatch(listing_id=1),
        engine_ok=False,
    )

    assert record.compile_status == "failed"
    rows = await _rows(session_factory)
    assert all(row.compile_status != "blocked" for row in rows)


async def test_a_blocked_artifact_is_never_regenerated(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    """No repair branch: the stored inputs are unchanged and re-reading adds no row."""
    patch = TailoringPatch(
        listing_id=1,
        ops=[BulletWeight(op="reweight_bullet", bullet_id=BULLET1, weight=2.0)],
    )
    facts_before = FACTS_YAML.read_bytes()

    listing_id, record, _ = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Never Repaired",
        patch=patch,
        extract_name="reworded_verbatim_extract.txt",
    )

    # The fixture above rewrites a VERBATIM bullet, so this is a Layer-2 fail on a
    # real compile — the case where a "helpful" repair would be most tempting.
    assert record.compile_status == "blocked"

    async with session_factory() as session:
        rows = list((await session.execute(select(CvArtifact))).scalars().all())
        assert len(rows) == 1
        assert rows[0].patch_json == patch.model_dump(mode="json")
        assert rows[0].change_log_json is not None
        # Re-reading the artifact must not create a new row.
        await cv_artifact_repo.latest_for_listing(session, listing_id, ok_only=False)
        await cv_artifact_repo.latest_for_listing(session, listing_id, ok_only=False)
        rows_after = list((await session.execute(select(CvArtifact))).scalars().all())

    assert len(rows_after) == 1, "a blocked artifact is never silently regenerated"
    assert FACTS_YAML.read_bytes() == facts_before, "the fact store is never mutated"


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
