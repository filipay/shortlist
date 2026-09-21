"""The `latex` lane — the real engine, which lives only inside the image (D-69).

Run it with:

    docker compose run --rm app pytest -m latex

The engine binary is deliberately absent from dev machines, so `pyproject.toml`
excludes the `latex` marker from the hermetic default lane. On a host without the
engine these nodes are COLLECTED and SKIPPED (never deselected), so a skipped run
tells the reader exactly what to do.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

from app.config import settings
from app.latex.compile import (
    TECTONIC_CACHED_ONLY_FLAG,
    TECTONIC_UNTRUSTED_FLAG,
    TectonicEngine,
)

pytestmark = [
    pytest.mark.latex,
    pytest.mark.skipif(
        shutil.which(settings.tectonic_binary) is None,
        reason=(
            "the LaTeX engine lives only inside the image: "
            "docker compose run --rm app pytest -m latex"
        ),
    ),
]

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "cv" / "awesomecv_standin.tex"
)


def _engine(**overrides: object) -> TectonicEngine:
    kwargs: dict[str, object] = {
        "binary": settings.tectonic_binary,
        "cache_dir": settings.tectonic_cache_dir,
        "offline": True,
        "timeout": settings.tectonic_timeout_seconds,
    }
    kwargs.update(overrides)
    return TectonicEngine(**kwargs)  # type: ignore[arg-type]


async def test_the_fixture_compiles_offline_to_a_real_pdf(tmp_path: Path) -> None:
    """The committed `.tex` becomes a real, multi-faceted PDF with the network refused."""
    tex = FIXTURE.read_text(encoding="utf-8")

    result = await _engine(offline=True).compile(tex=tex, workdir=tmp_path)

    assert result.ok is True, result
    assert result.page_count is not None and result.page_count >= 1
    assert result.pdf_path is not None
    assert Path(result.pdf_path).read_bytes()[:4] == b"%PDF"


async def test_every_engine_failure_is_a_value_not_an_exception(tmp_path: Path) -> None:
    missing = await _engine(binary="/nonexistent/tectonic").compile(
        tex="x", workdir=tmp_path
    )
    assert missing.ok is False
    assert missing.error_kind == "not_found"

    malformed = await _engine().compile(
        tex="\\documentclass{article}\\begin{document}", workdir=tmp_path
    )
    assert malformed.ok is False
    assert malformed.compile_log


async def test_the_offline_flag_is_the_one_the_installed_binary_documents() -> None:
    """D-75: confirm the flag names against the INSTALLED binary, not documentation.

    The hermetic argv test proves *what we pass*; this one proves *the binary
    accepts it*. If the installed help documents a different name, the argv is
    wrong and must be corrected rather than the assertion relaxed.
    """
    proc = await asyncio.create_subprocess_exec(
        settings.tectonic_binary,
        "--help",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    help_text = (stdout or b"").decode("utf-8", errors="replace")

    assert TECTONIC_CACHED_ONLY_FLAG in help_text, help_text
    assert TECTONIC_UNTRUSTED_FLAG in help_text, help_text
