"""The concrete LaTeX engines behind the `LatexEngine` port.

`TectonicEngine` runs the pinned, static Tectonic binary; `TexLiveEngine` runs the
`xelatex` fallback. Both:

- build a **fixed** `list[str]` argv in their own `_argv` and never interpolate
  document content into it, then hand it to `asyncio.create_subprocess_exec(*argv)`
  — a list, so no TeX text can ever become shell syntax (T-04-06);
- bound the child with `wait_for(...)` so a hung engine is a value, not a pinned
  worker (T-04-08);
- return `CompileResult(ok=False, error_kind=...)` for every failure class instead
  of raising (failure is a value).

The two engines are genuinely different, not variants of one another: only
Tectonic has a package cache to prime and a network mode to refuse, and only
Tectonic understands `--untrusted`. So each carries its **own** explicit
code-execution control (T-04-05), and the shared compile core below takes the
argv and environment they each build.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from pypdf import PdfReader

from app.latex.base import CompileResult, EngineProbe

#: The V1-CLI option names Tectonic actually documents for cached-only mode and
#: untrusted mode. D-75 requires these to be confirmed against the INSTALLED
#: binary's `--help`, not carried from documentation — the lane test reads the
#: names from here so the test and the argv cannot diverge.
TECTONIC_CACHED_ONLY_FLAG = "--only-cached"
TECTONIC_UNTRUSTED_FLAG = "--untrusted"
#: The fallback's OWN code-execution control. `--untrusted` is a Tectonic option
#: and means nothing to `xelatex`, so the fallback needs an explicit control of
#: its own or selecting it would silently drop the sandbox (T-04-05).
TEXLIVE_NO_SHELL_ESCAPE_FLAG = "-no-shell-escape"

#: The `--version` probe timeout, deliberately short: `/health` calls it, and a
#: probe must never approach the compile ceiling.
_HEALTH_TIMEOUT_SECONDS = 5.0
#: The engine log is reduced to a bounded tail before it lands on `CompileResult`.
_LOG_TAIL_CHARS = 4000
#: The staged source filename and the basename the engine writes its PDF under.
_SOURCE_NAME = "cv.tex"
_PDF_NAME = "cv.pdf"


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


async def _probe(binary: str, timeout: float = _HEALTH_TIMEOUT_SECONDS) -> EngineProbe:
    """Run `<binary> --version` with a short bounded timeout. Never raises."""
    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            "--version",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
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


async def _compile(
    *,
    engine_name: str,
    binary: str,
    build_argv: Callable[[Path, Path], list[str]],
    tex: str,
    workdir: Path,
    timeout: float,
    env: dict[str, str],
) -> CompileResult:
    """The shared compile core: stage, spawn, bound, read back. Never raises."""
    started = time.monotonic()
    source = workdir / _SOURCE_NAME
    pdf_path = workdir / _PDF_NAME
    tex_hash = _sha256_hex(tex.encode("utf-8"))
    try:
        source.write_text(tex, encoding="utf-8", newline="\n")
        argv = build_argv(source, workdir)
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(workdir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return CompileResult(
                ok=False,
                engine=engine_name,
                tex_hash=tex_hash,
                error=f"the engine exceeded the {timeout}s ceiling",
                error_kind="timeout",
                duration_ms=_elapsed_ms(started),
            )
        output = _tail((stdout or b"").decode("utf-8", errors="replace"))
        if proc.returncode != 0:
            return CompileResult(
                ok=False,
                engine=engine_name,
                tex_hash=tex_hash,
                compile_log=output,
                error=f"the engine exited {proc.returncode}",
                error_kind=f"exit_{proc.returncode}",
                duration_ms=_elapsed_ms(started),
            )
        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            return CompileResult(
                ok=False,
                engine=engine_name,
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
            engine=engine_name,
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
            engine=engine_name,
            tex_hash=tex_hash,
            error=f"the engine binary was not found: {binary}",
            error_kind="not_found",
            duration_ms=_elapsed_ms(started),
        )
    except Exception as exc:  # noqa: BLE001 — failure is a value, never a raise
        return CompileResult(
            ok=False,
            engine=engine_name,
            tex_hash=tex_hash,
            error=f"{type(exc).__name__}: {exc}",
            error_kind="compile_error",
            duration_ms=_elapsed_ms(started),
        )


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
        return await _compile(
            engine_name="tectonic",
            binary=self._binary,
            build_argv=self._argv,
            tex=tex,
            workdir=workdir,
            timeout=self._timeout,
            env={**os.environ, "TECTONIC_CACHE_DIR": self._cache_dir},
        )

    async def health(self) -> EngineProbe:
        return await _probe(self._binary)


class TexLiveEngine:
    """The TeX Live fallback: XeLaTeX, never pdfTeX (Pitfall 10).

    pdfTeX cannot load `fontspec` at all, so a pdfTeX fallback would be available
    in name only. `-no-shell-escape` is this engine's **own** explicit
    code-execution control and is deliberately not inherited from the Tectonic
    path: `--untrusted` is a Tectonic option that means nothing to `xelatex`, so
    without it, selecting the fallback would silently drop the sandbox the primary
    engine has. Do not "fix" this asymmetry away.

    It takes no `cache_dir` and no `offline`: TeX Live has no package cache to
    prime and no network mode to refuse (its distributions are pre-installed).
    """

    def __init__(self, *, binary: str, timeout: float) -> None:
        self._binary = binary
        self._timeout = timeout

    def _argv(self, source: Path, outdir: Path) -> list[str]:
        return [
            self._binary,
            "-interaction=nonstopmode",
            "-halt-on-error",
            TEXLIVE_NO_SHELL_ESCAPE_FLAG,
            "-output-directory",
            str(outdir),
            str(source),
        ]

    async def compile(self, *, tex: str, workdir: Path) -> CompileResult:
        """Compile `tex` to a PDF inside `workdir`. Never raises; failure is a value.

        No `TECTONIC_CACHE_DIR` override: that variable means nothing to TeX Live.
        """
        return await _compile(
            engine_name="texlive",
            binary=self._binary,
            build_argv=self._argv,
            tex=tex,
            workdir=workdir,
            timeout=self._timeout,
            env={**os.environ},
        )

    async def health(self) -> EngineProbe:
        return await _probe(self._binary)
