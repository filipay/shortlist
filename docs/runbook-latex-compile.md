# Runbook — the LaTeX compile lane and the engine switch (CV-05)

Phase 4 success criterion 3: *"the CV compiles to a PDF offline inside the
container, with the LaTeX engine selectable as configuration and a working
fallback."*

The engine is absent from developer machines by design, so the compile lane is
**operator-run inside the image**. This page is the operator half of the
`04-VALIDATION.md` Manual-Only table; the written verdict is
`docs/probes/2026-09-21-cv-tex-spike.md`.

## The one gate command

```bash
docker compose run --rm app pytest -m latex
```

**This exact string also appears in the lane tests' skip reasons**
(`tests/latex/test_compile.py`, `tests/latex/test_fact_equivalence.py`), so a run
that reports the lane as skipped points straight back here.

On a host without the engine the lane's nodes are **collected and skipped**, never
deselected — a skip tells you the gate was not run; a deselect would hide it.

## Why it needs the image

`tectonic` exists only inside the container. The runtime stage installs the test
dependencies and copies the test tree explicitly, so the gate command above works
against the committed fixtures without a host-side install.

## First run: create the two host directories

```bash
mkdir -p cv artifacts
```

Do this **before the first `docker compose up`**. If the directories do not exist,
Docker creates them root-owned and a later non-root write into the volume fails.

## The offline guarantee and its failure mode

Compilation runs in the engine's **cached-only** mode, so the container never needs
the network at run time. The package cache is primed at image build by compiling
the committed fixture (`Dockerfile`, the build-time prime step).

A package the bundle does not hold fails loudly, naming the package. The fix is
recorded, not guessed:

1. add the package (or the priming document that pulls it in) to the build-time
   prime step, and
2. rebuild the image.

**The engine is never switched automatically on failure.** A silent fallback would
make `LATEX_ENGINE` stop describing what actually ran, so a compile failure stays a
failure until a human changes the setting.

## Confirm the flag against the installed binary (D-75)

The option names must come from the installed binary's own help, never from
documentation:

```bash
docker compose run --rm app tectonic --help
```

Compare the cached-only flag and the untrusted-mode option it prints against the
ones the engine's argv passes (`app/config.py`'s `tectonic_offline` selects
`--only-cached`; `--untrusted` is always passed). **Record the observed names in the
verdict document.** If they differ, the argv is corrected to match the binary — the
flag is never assumed, and the assertion is never relaxed.

## The fallback's own code-execution control

The TeX Live path carries `-no-shell-escape` in its argv **and** the equivalent
disabled setting in its image. `--untrusted` is a Tectonic option and means nothing
to `xelatex`, so without the fallback's own control, selecting it would silently
drop the sandbox the primary engine has. Do not "simplify" that asymmetry away.

## The fallback is a separate image (D-76)

`Dockerfile.texlive` is **not** part of `docker compose up`. It is built once, by
hand, to *measure* the fallback:

```bash
docker build -f Dockerfile.texlive -t job-search-copilot:texlive .
LATEX_ENGINE=texlive docker run --rm job-search-copilot:texlive pytest -m latex
```

Record the image size **in megabytes**, the build duration **in minutes**, the
compile argv and the resulting page count in the verdict document — or record
explicitly that the measurement has not been taken, in which case the fallback is
not claimed as available. Sizes and durations always carry their unit.

## What "pass" looks like

- `docker compose run --rm app pytest -m latex` reaches a terminal state with at
  least one test **passed** and none failed.
- The committed fixtures compile to a real PDF with a page count of at least one,
  in cached-only mode, with no shell-escape.

**A lane reporting zero passed tests was skipped, not verified.** Investigate the
engine's presence in the image before treating the run as evidence.

## Bundle coverage, one command per preamble package

For each `\usepackage` name in the document's preamble, ask the bundle directly:

```bash
docker compose run --rm app tectonic -X bundle search <package-name>
```

A package the bundle does not hold is either added to the build-time prime step and
the image rebuilt, or named in the verdict document's UNRESOLVED section.

## Where the result goes

Append the observed counts and flags to
`docs/probes/2026-09-21-cv-tex-spike.md`, then run `/gsd-verify-work` for the
phase. This page is committed: it carries commands, flags, versions and
unit-suffixed measurements only — never CV content or personal detail.
