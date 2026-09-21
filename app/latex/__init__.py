"""The LaTeX lane: deterministic rendering and PDF compilation.

This package holds the escaping environment, the renderer, and the engine port
with its concrete implementations.
"""

from app.config import settings
from app.latex.base import CompileResult, EngineProbe, LatexEngine
from app.latex.compile import TectonicEngine, TexLiveEngine


def get_latex_engine() -> LatexEngine:
    """FastAPI dependency: the configured compile engine, built per request.

    A function rather than a module-level instance for the same two reasons as
    `get_llm_backend`: a test can override it
    (`app.dependency_overrides[get_latex_engine]` — the default lane must never
    need an engine binary), and no engine state is shared between requests.

    D-75 is enforced here in code: the selector picks exactly ONE engine and the
    factory **never** falls back to the other. A silent fallback would make
    `LATEX_ENGINE` stop describing what actually ran.

    The fallback shares `tectonic_timeout_seconds`: it is the single compile
    ceiling for BOTH engines (a hung engine must not pin the single worker). Do not
    "fix" the shared ceiling into two fields.
    """
    if settings.latex_engine == "tectonic":
        return TectonicEngine(
            binary=settings.tectonic_binary,
            cache_dir=settings.tectonic_cache_dir,
            offline=settings.tectonic_offline,
            timeout=settings.tectonic_timeout_seconds,
        )
    return TexLiveEngine(
        binary=settings.latex_xelatex_binary,
        timeout=settings.tectonic_timeout_seconds,
    )


__all__ = [
    "CompileResult",
    "EngineProbe",
    "LatexEngine",
    "TectonicEngine",
    "TexLiveEngine",
    "get_latex_engine",
]
