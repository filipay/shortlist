"""The LaTeX engine DI seam and its invariants, in the hermetic default lane.

No engine is installed here: every assertion is about the *contract*, not a real
compile. The regression this file exists to catch is the singular assumption — a
future phase reintroducing one required engine, or an engine that is not
overridable, fails here rather than in the container.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import AsyncClient

import app.latex as latex_module
from app.config import settings
from app.latex import TexLiveEngine, TectonicEngine, get_latex_engine
from app.latex.base import CompileResult, EngineProbe, LatexEngine

#: Builders that give each engine a caller-supplied binary, so the contract test
#: can point it at a path that cannot exist without touching a real engine.
ENGINE_BUILDERS = {
    "tectonic": lambda binary: TectonicEngine(
        binary=binary, cache_dir="/tmp/cache", offline=True, timeout=5
    ),
    "texlive": lambda binary: TexLiveEngine(binary=binary, timeout=5),
}


class FakeEngine:
    """A tiny engine satisfying the Protocol, for the dependency-override proof."""

    async def compile(self, *, tex: str, workdir: Path) -> CompileResult:
        return CompileResult(ok=True, engine="fake")

    async def health(self) -> EngineProbe:
        return EngineProbe(available=True, version="fake-9.9.9")


def test_the_configured_engine_selects_through_the_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "latex_engine", "tectonic")
    assert isinstance(get_latex_engine(), TectonicEngine)

    monkeypatch.setattr(settings, "latex_engine", "texlive")
    assert isinstance(get_latex_engine(), TexLiveEngine)


def test_the_factory_constructs_nothing_at_import_time() -> None:
    instances = [
        name
        for name, value in vars(latex_module).items()
        if not isinstance(value, type) and isinstance(value, LatexEngine)
    ]

    assert instances == [], f"an engine was constructed at import time: {instances}"


def test_the_factory_never_silently_substitutes_an_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-75/T-04-11: the configured engine is the one that ran, or a config lie."""
    monkeypatch.setattr(settings, "latex_engine", "texlive")
    assert not isinstance(get_latex_engine(), TectonicEngine)

    monkeypatch.setattr(settings, "latex_engine", "tectonic")
    assert not isinstance(get_latex_engine(), TexLiveEngine)


@pytest.mark.parametrize("choice", sorted(ENGINE_BUILDERS))
def test_every_engine_satisfies_the_latex_engine_contract(
    monkeypatch: pytest.MonkeyPatch, choice: str, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "latex_engine", choice)
    engine = get_latex_engine()

    assert isinstance(engine, LatexEngine)

    source = Path("/w/cv.tex")
    argv = engine._argv(source, Path("/w"))  # type: ignore[attr-defined]
    assert isinstance(argv, list)
    assert argv and all(isinstance(argument, str) for argument in argv)
    assert argv[-1] == str(source)

    # Each engine must carry its OWN code-execution control (T-04-05).
    assert any(control in argv for control in ("--untrusted", "-no-shell-escape"))

    # Failure is a value: a binary that cannot exist must not raise.
    missing = ENGINE_BUILDERS[choice]("/nonexistent/engine")
    result = asyncio.run(missing.compile(tex="x", workdir=tmp_path))
    assert result.ok is False
    assert result.error_kind == "not_found"

    probe = asyncio.run(missing.health())
    assert isinstance(probe, EngineProbe)
    assert probe.available is False


async def test_the_seam_is_overridable_through_dependency_overrides(
    client: AsyncClient,
) -> None:
    """The seam a test overrides is the one the app consumes."""
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_latex_engine] = lambda: FakeEngine()
    try:
        body = (await client.get("/health")).json()
    finally:
        app.dependency_overrides.pop(get_latex_engine, None)

    assert body["tectonic"]["available"] is True
    assert body["tectonic"]["version"] == "fake-9.9.9"


def test_the_protocol_check_can_actually_fail() -> None:
    """A guard that cannot fail is not a guard."""

    class NotAnEngine:
        pass

    assert not isinstance(NotAnEngine(), LatexEngine)
