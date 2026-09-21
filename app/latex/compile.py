"""The concrete LaTeX engines behind the `LatexEngine` port.

`TectonicEngine` runs the pinned, static Tectonic binary; `TexLiveEngine` runs the
`xelatex` fallback. Both:

- build a **fixed** `list[str]` argv here and never interpolate document content
  into it, then hand it to `asyncio.create_subprocess_exec(*argv)` — a list, so no
  TeX text can ever become shell syntax (T-04-06);
- bound the child with `wait_for(...)` so a hung engine is a value, not a pinned
  worker (T-04-08);
- return `CompileResult(ok=False, error_kind=...)` for every failure class instead
  of raising (failure is a value).

The flag names are module-level constants so `_argv` and the lane's D-75 assertion
(`tests/latex/test_compile.py`, which reads the installed binary's own `--help`)
cannot drift apart.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
import time
from pathlib import Path

from pypdf import PdfReader

from app.latex.base import CompileResult, EngineProbe

#: The V1-CLI option names Tectonic actually documents for cached-only mode and
#: untrusted mode. D-75 requires these to be confirmed against the INSTALLED
#: binary's `--help`, not carried from documentation — the lane test does exactly
#: that, reading the names from here so the test and the argv cannot diverge.
TECTONIC_CACHED_ONLY_FLAG = "--only-cached"
TECTONIC_UNTRUSTED_FLAG = "--untrusted"
#: The fallback's OWN code-execution control. `--untrusted` is a Tectonic option
#: and means nothing to `xelatex`, so the fallback needs an explicit control of its
#: own or selecting it would silently drop the sandbox (T-04-05).
TEXLIVE_NO_SHELL_ESCAPE_FLAG = "-no-shell-escape"

#: The `--version` probe timeout, deliberately short: `/health` calls it, and a
#: probe must never approach the compile ceiling.
_HEALTH_TIMEOUT_SECONDS = 5.0
#: The engine log is reduced to a bounded tail before it lands on `CompileResult`.
_LOG_TAIL_CHARS = 4000


def _count_pages(pdf_path: Path) -> int:
    """PDF page count via `pypdf`. Synchronous by nature.

    Only ever reached through `asyncio.to_thread` (Pitfall 14): running `pypdf` on
    the event loop would stall the single worker, and a CV PDF is untrusted input.
    """
    return len(PdfReader(str(pdf_path)).pages)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tail(text: str, limit: int = _LOG_TAIL_CHARS) -> str:
    return text[-limit:] if len(text) > limit else text


def _first_line(text: str) -> str | None:
    """The first non-empty line of `--version` output, bounded."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:200]
    return None


def _elapsed_ms(started: float) -> int:
    return int(round((time.monotonic() - started) * 1000))


class TectonicEngine:
    """The pinned Tectonic binary: no shell, no shell-escape, always untrusted."""

    def __init__(self, *, binary: str, cache_dir: str, offline: bool, timeout: float) -> None:
        self._binary = binary
        self._cache_dir = cache_dir
        self._offline = offline
        self._timeout = timeout

    def _argv(self, source: Path, outdir: Path) -> list[str]:
        """The fixed argv for one compile.

        Built here and never interpolated from document content; the unstable
        option namespace is never enabled and the engine's code-execution feature
        is never turned on. `--untrusted` disables shell-escape and other insecure
        features regardless of any other option, so it is passed on every compile.
        """
        argv = [self._binary]
        if self._offline:
            argv.append(TECTONIC_CACHED_ONLY_FLAG)
        argv += [
            TECTONIC_UNTRUSTED_FLAG,
            "--keep-logs",  # so CompileResult.compile_log carries a real engine log
            "--outdir",
            str(outdir),
            str(source),
        ]
        return argv

    async def compile(self, *, tex: str, workdir: Path) -> CompileResult:
        """Compile `tex` to a PDF inside `workdir`. Never raises; failure is a value."""
        started = time.monotonic()
        source = workdir / "cv.tex"
        pdf_path = workdir / "cv.pdf"
        tex_hash = _sha256_hex(tex.encode("utf-8"))
        try:
            source.write_text(tex, encoding="utf-8", newline="\n")
            argv = self._argv(source, workdir)
            env = {**os.environ, "TECTONIC_CACHE_DIR": self._cache_dir}
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(workdir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(), timeout=self._timeout
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                return CompileResult(
                    ok=False,
                    engine="tectonic",
                    tex_hash=tex_hash,
                    error=f"the engine exceeded the {self._timeout}s ceiling",
                    error_kind="timeout",
                    duration_ms=_elapsed_ms(started),
                )
            output = _tail((stdout or b"").decode("utf-8", errors="replace"))
            if proc.returncode != 0:
                return CompileResult(
                    ok=False,
                    engine="tectonic",
                    tex_hash=tex_hash,
                    compile_log=output,
                    error=f"the engine exited {proc.returncode}",
                    error_kind=f"exit_{proc.returncode}",
                    duration_ms=_elapsed_ms(started),
                )
            if not pdf_path.exists() or pdf_path.stat().st_size == 0:
                return CompileResult(
                    ok=False,
                    engine="tectonic",
                    tex_hash=tex_hash,
                    compile_log=output,
                    error="the engine produced no PDF",
                    error_kind="no_output",
                    duration_ms=_elapsed_ms(started),
                )
            pdf_bytes = pdf_path.read_bytes()
            page_count = await asyncio.to_thread(_count_pages, pdf_path)
            return CompileResult(
                ok=True,
                engine="tectonic",
                pdf_path=str(pdf_path),
                page_count=page_count,
                tex_hash=tex_hash,
                pdf_hash=_sha256_hex(pdf_bytes),
                compile_log=output,
                duration_ms=_elapsed_ms(started),
            )
        except FileNotFoundError:
            return CompileResult(
                ok=False,
                engine="tectonic",
                tex_hash=tex_hash,
                error=f"the engine binary was not found: {self._binary}",
                error_kind="not_found",
                duration_ms=_elapsed_ms(started),
            )
        except Exception as exc:  # noqa: BLE001 — failure is a value, never a raise
            return CompileResult(
                ok=False,
                engine="tectonic",
                tex_hash=tex_hash,
                error=f"{type(exc).__name__}: {exc}",
                error_kind="compile_error",
                duration_ms=_elapsed_ms(started),
            )

    async def health(self) -> EngineProbe:
        """Run `<binary> --version` with a short bounded timeout. Never raises."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self._binary,
                "--version",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(), timeout=_HEALTH_TIMEOUT_SECONDS
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                return EngineProbe(available=False, error="timeout")
            if proc.returncode != 0:
                return EngineProbe(available=False, error=f"exit_{proc.returncode}")
            return EngineProbe(
                available=True,
                version=_first_line((stdout or b"").decode("utf-8", errors="replace")),
            )
        except FileNotFoundError:
            return EngineProbe(available=False, error="not_found")
        except Exception as exc:  # noqa: BLE001 — health is a total function
            return EngineProbe(available=False, error=type(exc).__name__)
