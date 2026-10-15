---
phase: 04-cv-fact-store-latex-compile-spike
plan: 02
subsystem: infra
tags: [latex, tectonic, texlive, docker, xelatex, pypdf, fastapi, dependency-injection, health]

# Dependency graph
requires:
  - phase: 04-cv-fact-store-latex-compile-spike
    plan: 01
    provides: "pypdf + pyyaml runtime pins, the `latex` pytest marker excluded from the hermetic lane, and the bare app/latex package marker"
provides:
  - "app/latex/base.py — LatexEngine Protocol, CompileResult, EngineProbe (failure-as-value, extra=forbid)"
  - "app/latex/compile.py — TectonicEngine, TexLiveEngine, shared compile core, asyncio.to_thread page count"
  - "app/latex/__init__.py — get_latex_engine() DI factory that never substitutes silently"
  - "app/config.py — ten LaTeX-engine/volume/importer Settings fields"
  - "app/api/health.py — the reported `tectonic` key at HTTP 200 in every case"
  - "Dockerfile — pinned Tectonic tarball + checksum, --help capture, deterministic cache ENV, COPY tests + pytest, build-time cache prime"
  - "Dockerfile.texlive — the curated TeX Live fallback image"
  - "compose.yml + .env.example — ./cv + ./artifacts volumes and the ten engine env passthroughs"
  - "tests/fixtures/cv/awesomecv_standin.tex — the committed synthetic document"
  - "tests/latex/*, tests/test_latex_engine_seam.py — the lane and the DI-seam guard"
affects: [04-03, 04-04, 04-05, 05, 06]

actuals:
  tokens: 27123
  tasks: 3
  commits: 3

tech-stack:
  added:
    - "Tectonic 0.17.0 (pinned static musl binary, sha256 8533d07f9ccbd7a65824b9e0459041bca34af1eb33daba48f59215593753a3b7)"
    - "TeX Live curated subset as the documented xelatex fallback"
  patterns:
    - "Engine port: runtime-checkable Protocol + failure-as-value result types, copied from app/llm/base.py"
    - "DI factory (get_latex_engine) overridable via app.dependency_overrides"
    - "Process hosts declared in one place (SUBPROCESS_EXEMPT_DIRS) with a mirror test proving the carve-out is real"

key-files:
  created:
    - app/latex/base.py
    - app/latex/compile.py
    - Dockerfile.texlive
    - tests/fixtures/cv/awesomecv_standin.tex
    - tests/latex/__init__.py
    - tests/latex/test_compile.py
    - tests/test_latex_engine_seam.py
  modified:
    - app/config.py
    - app/latex/__init__.py
    - app/api/health.py
    - Dockerfile
    - compose.yml
    - .env.example
    - tests/test_import_discipline.py
    - tests/test_config.py
    - tests/test_deploy_manifest.py
    - tests/api/test_health.py

key-decisions:
  - "D-75 enforced in code: get_latex_engine() selects exactly one engine and never falls back to the other."
  - "A single shared compile ceiling (tectonic_timeout_seconds) bounds both engines, deliberately not split into two fields."
  - "pdflatex is named only as 'pdfTeX' in app/latex source so the literal token can never appear there (acceptance criterion + plan-level grep)."
  - "TectonicEngine and TexLiveEngine share one private compile core; only the argv, environment and engine name differ."
  - "The subprocess import guard became a declared-process-host rule with app/latex added, plus a mirror test."

patterns-established:
  - "Engine seam: Protocol + compile(*, tex, workdir) -> CompileResult, never raises; failure carries an error_kind."
  - "Every new ceiling is a Settings field and the PLAT-04 absence scan covers app/latex and app/cv."

requirements-completed: [CV-05]

coverage:
  - id: D1
    description: "LatexEngine Protocol with CompileResult/EngineProbe, failure-as-value and extra=forbid"
    requirement: CV-05
    verification:
      - kind: unit
        ref: "tests/test_latex_engine_seam.py#test_every_engine_satisfies_the_latex_engine_contract"
        status: pass
    human_judgment: false
  - id: D2
    description: "TectonicEngine builds a fixed argv, bounds the child, and returns ok=False with a named error_kind for every failure class"
    requirement: CV-05
    verification:
      - kind: unit
        ref: "tests/test_latex_engine_seam.py + shell assertion of _argv"
        status: pass
    human_judgment: false
  - id: D3
    description: "A committed .tex compiles to a real PDF through Tectonic, offline, inside the image"
    requirement: CV-05
    verification:
      - kind: e2e
        ref: "docker compose run --rm app pytest -m latex -k fixture_compiles -x"
        status: unknown
    rationale: "Docker is not observable from the agent sandbox (D-69). The lane is operator-run; the nodes are collected and skipped on this host. The hermetic half (fixed argv, failure-as-value, skip-not-deselect) is verified."
    human_judgment: true
  - id: D4
    description: "The engine is selected by LATEX_ENGINE through one factory that never substitutes silently"
    requirement: CV-05
    verification:
      - kind: unit
        ref: "tests/test_latex_engine_seam.py#test_the_factory_never_silently_substitutes_an_engine"
        status: pass
    human_judgment: false
  - id: D5
    description: "/health reports a tectonic object at HTTP 200 in every case, and a missing/raising engine never changes status"
    requirement: CV-05
    verification:
      - kind: integration
        ref: "tests/api/test_health.py#test_health_reports_a_raising_engine_instead_of_propagating"
        status: pass
    human_judgment: false
  - id: D6
    description: "Ten engine/volume/importer Settings fields exist and the PLAT-04 guards cover app/latex and app/cv"
    requirement: CV-05
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_the_phase_four_ceilings_are_guarded"
        status: pass
    human_judgment: false
  - id: D7
    description: "compose.yml mounts ./cv and ./artifacts and forwards all ten engine keys with Settings-derived defaults; .env.example documents them"
    requirement: CV-05
    verification:
      - kind: unit
        ref: "tests/test_deploy_manifest.py#test_compose_and_env_example_forward_every_engine_key"
        status: pass
    human_judgment: false
  - id: D8
    description: "The Tectonic install + cache prime build succeeds, and Dockerfile.texlive has a recorded one-off measurement"
    requirement: CV-05
    verification:
      - kind: manual_procedural
        ref: "docker compose build app; docker build -f Dockerfile.texlive ...; record size/duration/argv/page_count in docs/probes/2026-09-21-cv-tex-spike.md"
        status: unknown
    rationale: "Requires Docker, which is denied in this sandbox. The instruction is recorded verbatim in Dockerfile.texlive's header; plan 04-05 owns the verdict document."
    human_judgment: true

duration: 22min
completed: 2026-09-21
status: complete
---

# Phase 4 Plan 2: LaTeX Compile Spike — Summary

**Tectonic compiles a committed `.tex` to a PDF offline behind a `LatexEngine` port, the engine is selected by configuration and never substituted silently, and `/health` reports it without ever changing the app's own status.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-09-21T14:00:10Z
- **Completed:** 2026-09-21T14:22:06Z
- **Tasks:** 3
- **Files modified:** 17

## Accomplishments

- The `LatexEngine` port (`Protocol` + `CompileResult`/`EngineProbe`, failure-as-value, `extra="forbid"`) with two concrete engines behind one shared compile core.
- `TectonicEngine` passes a **fixed** argv (`--only-cached` when offline, `--untrusted`, `--keep-logs`, `--outdir`), bounds the child, reads the page count through `asyncio.to_thread`, and never raises — every failure is `ok=False` with a named `error_kind`.
- `TexLiveEngine` (xelatex, never pdfTeX) carries its **own** `-no-shell-escape` control, because `--untrusted` means nothing to xelatex.
- `get_latex_engine()` selects by `LATEX_ENGINE` and never falls back; `/health` gained a reported `tectonic` key that answers 200 even when the engine raises.
- Ten new `Settings` fields make the engine, its paths, its timeout, its offline mode, the volumes and the importer bounds configuration; the PLAT-04 absence scan now covers `app/latex` and `app/cv`.
- The `Dockerfile` installs the checksum-pinned Tectonic tarball, captures the binary's own `--help` (D-75), sets a HOME-independent cache, ships the test tree + pytest pins, and primes the package cache at build time by compiling the fixture.
- `Dockerfile.texlive` and the `./cv` + `./artifacts` volumes with all ten env passthroughs.

## Task Commits

Each task was committed atomically:

1. **Task 1: the thinnest real engine path** - `59c1030` (feat)
2. **Task 2: the fallback engine, volumes, and the switch** - `a147356` (feat)
3. **Task 3: the engine is configuration all the way down** - `b4d3b42` (feat)

**Plan metadata:** pending (docs commit for this SUMMARY)

## Files Created/Modified

- `app/latex/base.py` - `LatexEngine` Protocol, `CompileResult`, `EngineProbe`
- `app/latex/compile.py` - `TectonicEngine`, `TexLiveEngine`, shared `_compile`/`_probe`/`_count_pages`
- `app/latex/__init__.py` - `get_latex_engine()` DI factory and re-exports
- `app/config.py` - ten LaTeX-engine/volume/importer settings
- `app/api/health.py` - `_tectonic_report()` and the `tectonic` key
- `Dockerfile` - Tectonic install + `--help` capture + cache ENV + tests/pytest + prime
- `Dockerfile.texlive` - the curated TeX Live fallback image
- `compose.yml`, `.env.example` - volumes and the ten env passthroughs
- `tests/fixtures/cv/awesomecv_standin.tex` - the committed synthetic document
- `tests/latex/__init__.py`, `tests/latex/test_compile.py` - the operator-run lane
- `tests/test_latex_engine_seam.py`, `tests/test_import_discipline.py`, `tests/test_config.py`, `tests/test_deploy_manifest.py`, `tests/api/test_health.py` - the guards

## Decisions Made

- **D-75 in code, not prose:** the factory selects exactly one engine and never falls back, so `LATEX_ENGINE` always describes what ran.
- **One shared compile ceiling:** `tectonic_timeout_seconds` bounds both engines deliberately (comment says so), rather than two fields that could drift.
- **`pdfTeX` not `pdflatex` in `app/latex` source:** the acceptance criterion and the plan-level `grep -v '^#' | grep -c pdflatex == 0` check both require the literal token to be absent; the rationale survives as the word "pdfTeX" and in `Dockerfile.texlive`'s comments.
- **Shared compile core:** `TectonicEngine` and `TexLiveEngine` delegate to one private `_compile`, differing only in argv, environment and engine name — less duplication without weakening either engine's own sandbox control.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `curl` to the runtime stage's apt install**
- **Found during:** Task 1 (Dockerfile Tectonic install)
- **Issue:** the plan's Tectonic install `RUN` uses `curl -fsSL`, but `python:3.13-slim` ships no `curl`; the build would fail at the first Tectonic layer.
- **Fix:** installed `curl` alongside `git` in the existing apt layer, with a comment naming why.
- **Files modified:** `Dockerfile`
- **Verification:** `grep` confirms `git curl` in the install line; the Dockerfile remains single-line-shell with no heredoc (the existing manifest guard passes).
- **Committed in:** `59c1030` (part of task commit)

**2. [Rule 1 - Bug] Removed the literal `pdflatex` token from `app/latex` source**
- **Found during:** Task 2 (fallback engine)
- **Issue:** the plan's action asked the `TexLiveEngine` docstring to name `pdflatex`, but the same plan's acceptance criterion ("the string `pdflatex` appears nowhere in `app/latex/`") and its plan-level verify (`grep -v '^#' app/latex/compile.py | grep -c 'pdflatex'` returns 0) both forbid the literal token in a non-comment line.
- **Fix:** the docstring names **pdfTeX** instead, preserving the rationale (pdfTeX cannot load `fontspec`) while keeping the literal token absent. The `pdflatex` explanation also remains in `Dockerfile.texlive`'s comments.
- **Files modified:** `app/latex/compile.py`
- **Verification:** `grep -rn pdflatex app/latex/` → none; plan-level grep → 0.
- **Committed in:** `a147356` (part of task commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug/plan-conflict reconciliation)
**Impact on plan:** Neither changes the design. The `curl` fix is required for the image to build at all; the token rename reconciles two contradictory plan statements in favour of the mechanical acceptance criterion.

## Issues Encountered

- **A plan verify command is not valid Python.** Task 2's verify one-liner contains `assert '-no-shell-escape' in a, 'the fallback has no code-execution control of its own', a` — a three-argument `assert`, which is a `SyntaxError`. I ran the semantically equivalent corrected form (single message argument) and it passed, exercising both engines' argvs. No source change was needed; the plan literal is malformed.
- **Docker is denied in this sandbox.** All Docker-based verify steps (`docker compose build app`, `docker compose run --rm app pytest -m latex`, `docker compose run --rm app tectonic --help`, the `Dockerfile.texlive` build) were **not run**. This is expected per D-69: the lane is operator-run and recorded as a Manual-Only action in `04-VALIDATION.md`. Nothing was faked. What remains unverified: the Tectonic install+prime build, the real fixture compile offline, the installed binary's own `--help` flag names (D-75's implementation-time confirmation), and the `Dockerfile.texlive` one-off measurement. The hermetic half of each claim (fixed argv, fail-closed behaviour, skip-not-deselect) is verified.
- **The Tectonic SHA256 was independently re-derived.** Fetched the asset from the GitHub Releases API for tag `tectonic@0.17.0`, downloaded it, and confirmed sha256 `8533d07f9ccbd7a65824b9e0459041bca34af1eb33daba48f59215593753a3b7` — a match, so no hard stop. Also confirmed the tarball contains `tectonic` at its root, validating the `tar -xzf ... tectonic` form.

## Verification Evidence (verbatim)

```
# plan-level: hermetic lane
$ .venv/bin/python -m pytest -q -m 'not live and not latex'
862 passed, 7 deselected in 140.76s (0:02:20)

# plan-level: process spawn is a fixed argv list
$ .venv/bin/python -c "import app.latex.compile as m, inspect; src=inspect.getsource(m); assert 'create_subprocess_exec' in src; assert 'shell=True' not in src"
OK: fixed argv, no shell=True

# plan-level: no pdflatex in app/latex
$ grep -v '^#' app/latex/compile.py | grep -c 'pdflatex'
0

# Task 1: argv shape (offline flag, untrusted flag, no shell-escape, source last)
argv ok: ['/usr/local/bin/tectonic', '--only-cached', '--untrusted', '--keep-logs', '--outdir', '/w', '/w/cv.tex']

# Task 1: failure is a value
failure is a value: not_found

# Task 1: the latex lane collects and SKIPS (never deselects) on a host without the engine
$ .venv/bin/python -m pytest -q -m latex tests/latex -x -rs
3 skipped in 0.45s

# Task 2: both engines carry their own code-execution control
texlive : ['/usr/bin/xelatex', '-interaction=nonstopmode', '-halt-on-error', '-no-shell-escape', '-output-directory', '/w', '/w/cv.tex']
tectonic: ['/usr/local/bin/tectonic', '--only-cached', '--untrusted', '--keep-logs', '--outdir', '/w', '/w/cv.tex']

# Task 2: compose surface
compose surface ok
# Task 2: $ .venv/bin/python -m pytest -q tests/test_deploy_manifest.py tests/test_import_discipline.py -x
27 passed in 2.57s

# Task 3: $ .venv/bin/python -m pytest -q tests/test_latex_engine_seam.py -x
7 passed in 5.91s
# Task 3: $ .venv/bin/python -m pytest -q tests/api/test_health.py tests/test_config.py -x
33 passed in 12.19s
# Task 3: engine settings one-liner
engine settings ok

# NOT RUN — Docker denied in this sandbox (operator-run, D-69):
#   docker compose build app && docker compose run --rm app pytest -m latex -k fixture_compiles -x
#   docker compose run --rm app tectonic --help
#   docker build -f Dockerfile.texlive -t job-search-copilot:texlive .
```

## User Setup Required

Docker is required to build the image and run the `latex` lane. On the operator machine:

- Confirm `docker compose version` reports v2.x (Docker Engine >= 20.10 with the Compose v2 plugin).
- `mkdir -p cv artifacts` in the repo root before the first `docker compose up`, or Docker creates them root-owned (Pitfall 11b).
- Then run `docker compose build app && docker compose run --rm app pytest -m latex` and record the result in `docs/probes/2026-09-21-cv-tex-spike.md` (plan 04-05).

## Next Phase Readiness

- Plan 04-03 can proceed: `app/latex/__init__.py` no longer contends for the package marker, and `app/latex/compile.py` now holds both engines.
- The engine seam is ready for the renderer to bind to; the `latex` lane and the build-time prime both exist and are wired to the same committed fixture.
- Open risk carried forward: the container-only claims (build, offline compile, installed-binary flag names, fallback measurement) are unverified until the operator runs the Docker steps.

---

*Phase: 04-cv-fact-store-latex-compile-spike*
*Completed: 2026-09-21*

## Self-Check: PASSED

- Created files exist: `app/latex/base.py`, `app/latex/compile.py`, `tests/test_latex_engine_seam.py`, `Dockerfile.texlive`, `tests/fixtures/cv/awesomecv_standin.tex` — all FOUND.
- Commits exist: `59c1030`, `a147356`, `b4d3b42` — all FOUND.
- SUMMARY.md: FOUND.
- Hermetic lane re-run: `862 passed, 7 deselected`.
- Not self-checkable here (Docker denied): the container build/compile steps, recorded above as unverified with the exact operator commands.
