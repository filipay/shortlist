"""260930-lay — compile_tailored renders the remembered layout, trim included.

Reuses the scripted-engine harness from ``tests/pipeline/test_page_trim.py``: a
temporary ``artifacts_dir``, a fake engine whose page counts are scripted, and a
monkeypatched extraction. Only the ``settings.cv_dir`` preference file varies.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.cv.layout import write_layout
from app.domain.cv import TailoringPatch
from tests.pipeline.test_page_trim import _compile

CLASSIC_MARKER = r"\begin{center}"
MODERN_MARKER = r"\MakeUppercase"
COMPACT_MARKER = r"\geometry{margin=0.65in}"


def _cv_dir(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "cv"
    path.mkdir()
    monkeypatch.setattr(settings, "cv_dir", str(path))
    return path


async def test_compile_uses_the_stored_layout(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_layout(_cv_dir(tmp_path, monkeypatch), "modern")

    _, record, engine = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Modern Layout",
        patch=TailoringPatch(listing_id=1),
        outcomes=[2],
    )

    assert record.compile_status == "ok"
    assert len(engine.calls) == 1
    assert MODERN_MARKER in engine.calls[0]
    assert CLASSIC_MARKER not in engine.calls[0]


async def test_a_trim_re_render_keeps_the_chosen_layout(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_layout(_cv_dir(tmp_path, monkeypatch), "compact")

    _, record, engine = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Compact Trim Layout",
        patch=TailoringPatch(listing_id=1),
        outcomes=[3, 2],
    )

    assert record.compile_status == "ok"
    assert record.page_count == 2
    assert len(engine.calls) == 2, "the initial render plus one trim re-render"
    assert all(COMPACT_MARKER in tex for tex in engine.calls)
    assert all(CLASSIC_MARKER not in tex for tex in engine.calls)


async def test_without_a_preference_the_compile_renders_classic(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    _cv_dir(tmp_path, monkeypatch)  # a CV volume with no layout file

    _, record, engine = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Default Layout",
        patch=TailoringPatch(listing_id=1),
        outcomes=[2],
    )

    assert record.compile_status == "ok"
    assert CLASSIC_MARKER in engine.calls[0]


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
