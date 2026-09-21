"""The LaTeX engine port — one compile, and a binary-health probe.

Mirrors `app/llm/base.py`: a `@runtime_checkable` Protocol whose methods **never
raise** (failure is a value), result types with `extra="forbid"`, and a redaction
property at the type level. Nothing on these types can carry a raw PDF byte
string, the TeX body, or the engine's full output — only paths, hashes, counts, a
bounded tail of the engine log, and a short error label.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class CompileResult(BaseModel):
    """The outcome of one compile — a value, never an exception.

    `extra="forbid"` is the redaction control, exactly as on `StructuredCallResult`:
    every field is a path, a hash, a count or a short label, so a future
    contributor cannot quietly attach the TeX body or a raw PDF byte string and
    have it persisted against a CV artefact row.
    """

    model_config = ConfigDict(extra="forbid")

    ok: bool
    engine: str
    pdf_path: str | None = None
    page_count: int | None = None
    tex_hash: str | None = None
    pdf_hash: str | None = None
    #: A bounded TAIL of the engine's merged stdout/stderr. On a non-zero exit this
    #: is what names the missing package D-75 requires to be loud.
    compile_log: str | None = None
    error: str | None = None
    #: A short machine-readable class: `not_found`, `timeout`, `exit_<code>`,
    #: `no_output`, or `compile_error`.
    error_kind: str | None = None
    duration_ms: int | None = None


class EngineProbe(BaseModel):
    """A non-raising binary-availability result. Health probes never raise (D-08)."""

    model_config = ConfigDict(extra="forbid")

    available: bool
    version: str | None = None
    error: str | None = None


@runtime_checkable
class LatexEngine(Protocol):
    """The ONLY surface the app depends on for compilation."""

    async def compile(self, *, tex: str, workdir: Path) -> CompileResult:
        """Compile `tex` to PDF in `workdir`. Never raises; failure is a value."""
        ...

    async def health(self) -> EngineProbe:
        """Binary availability + version. Never raises; failure is a value."""
        ...


__all__ = ["CompileResult", "EngineProbe", "LatexEngine"]
