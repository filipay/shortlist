---
phase: 02-clean-filtered-queryable-queue
plan: "02"
subsystem: dependencies
tags: [rapidfuzz, pip, pyproject, requirements, supply-chain, dependency-pins]

# Dependency graph
requires:
  - phase: 01-walking-skeleton-foundations
    provides: the exact-pin convention and the manifest-guard test style (tests/test_deploy_manifest.py)
provides:
  - rapidfuzz==3.14.6 installed in .venv-host and importable (fuzz.token_sort_ratio / fuzz.token_set_ratio callable)
  - the exact pin declared in pyproject.toml [project].dependencies and mirrored verbatim in requirements.txt
  - tests/test_dependency_pins.py — binds the declared pin to the installed version and rejects an unpinned entry
affects: [02-04 dedup stage, which imports rapidfuzz.fuzz.token_sort_ratio]

# Actuals (#2632) — same estimateTokens scale (chars/4 over the realized diff).
actuals:
  tokens: 1087
  tasks: 2
  commits: 1
  plan_head_before: b783419d20df6152916b5127887363782b21b389

# Tech tracking
tech-stack:
  added: [rapidfuzz 3.14.6 (MIT, pre-compiled musllinux wheel)]
  patterns:
    - "Exact pins only — the resolved artefact set is the reviewable supply-chain surface (D-17)"
    - "Declared pin bound to the installed version by a test (no silent pip drift)"

key-files:
  created:
    - tests/test_dependency_pins.py
  modified:
    - pyproject.toml
    - requirements.txt

key-decisions:
  - "rapidfuzz==3.14.6 is pinned exactly in both manifests, positioned before the python-jobspy git pin"
  - "The token_set_ratio subset-returns-100 pathology is captured as executable evidence so plan 02-04 cannot silently gate on it"
  - "The pin is installed in BOTH venvs: .venv-host (the plan's stated target) and .venv (the only venv the suite runs in)"

patterns-established:
  - "Dependency-pin guard: parse pyproject.toml with stdlib tomllib, mirror-check requirements.txt, and assert the installed __version__ equals the declared pin"
  - "Unpinned-entry rejection: a package name without `==` in either manifest fails the guard"

requirements-completed: []

coverage:
  - id: D1
    description: "rapidfuzz 3.14.6 is installed in .venv-host and importable, with both token_sort_ratio and token_set_ratio callable"
    requirement: QUEUE-03
    verification:
      - kind: other
        ref: ".venv-host/bin/python -c \"import rapidfuzz; print(rapidfuzz.__version__)\" -> 3.14.6"
        status: pass
      - kind: unit
        ref: "tests/test_dependency_pins.py#test_rapidfuzz_imports_at_the_pinned_version"
        status: pass
    human_judgment: false
  - id: D2
    description: "The exact pin is declared once in pyproject.toml [project].dependencies and mirrored verbatim in requirements.txt, with no floating range in either file"
    requirement: FILT-01
    verification:
      - kind: unit
        ref: "tests/test_dependency_pins.py#test_rapidfuzz_pin_is_declared_exactly"
        status: pass
      - kind: other
        ref: "git diff --numstat pyproject.toml requirements.txt -> '4 0' and '4 0' (additions only)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The install is exercised end to end: tests/test_dependency_pins.py and the deployment-manifest guard both pass, and the full suite stays green"
    requirement: QUEUE-03
    verification:
      - kind: integration
        ref: "tests/test_deploy_manifest.py (15 passed, unchanged)"
        status: pass
      - kind: integration
        ref: ".venv/bin/python -m pytest -q -> 323 passed, 2 deselected"
        status: pass
    human_judgment: false
  - id: D4
    description: "A human explicitly approved the pin (version, source repository and wheel-vs-source-build) before any install command ran"
    requirement: QUEUE-03
    verification: []
    human_judgment: true
    rationale: "The whole deliverable IS the human sign-off required by the package-legitimacy SUS verdict (T-02-04, golden rule 6). It was surfaced out-of-band by the orchestrator with the pip-index/PyPI-metadata/wheel evidence and resolved with user_response \"approved\"; an approval cannot be machine-verified, so this routes to a human by design rather than being marked auto-pass."

# Metrics
duration: 4min
completed: 2026-09-16
status: complete
---

# Phase 2 Plan 02: The one new dependency, behind a human gate

**`rapidfuzz==3.14.6` installed and pinned exactly in both dependency manifests, with a guard test binding the declared pin to the installed version and capturing the `token_set_ratio` subset hazard as executable evidence.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-09-16T09:14:33Z
- **Completed:** 2026-09-16T09:18:19Z
- **Tasks:** 2 (1 checkpoint + 1 auto)
- **Files modified:** 3

## Accomplishments

- **Task 1 (blocking human checkpoint) resolved with the human's `approved`.** The `SUS` package-legitimacy verdict on `rapidfuzz` was cleared out-of-band: the orchestrator presented `pip index versions rapidfuzz` (3.14.6 latest), the PyPI JSON `Project-URL`/`Repository` matching `https://github.com/rapidfuzz/RapidFuzz` (no slopsquat signal), and a pre-compiled wheel selection. No install command ran before that approval.
- `rapidfuzz==3.14.6` is installed in **both** venvs and imports cleanly at exactly `3.14.6`; the selected artefact was the pre-compiled `rapidfuzz-3.14.6-cp314-cp314-musllinux_1_2_x86_64.whl` (4.3 MB) on both installs — no source build.
- The pin is declared once in `pyproject.toml`'s `[project].dependencies` (with a comment naming Tier-2 dedup, D-31) and mirrored **verbatim** in `requirements.txt`, in the same position relative to the other entries so the file's "mirrors `[project].dependencies` exactly" claim holds. `git diff --numstat` shows additions only.
- `tests/test_dependency_pins.py` binds the declaration to the installed distribution: it parses `pyproject.toml` with stdlib `tomllib`, asserts a standalone `rapidfuzz==3.14.6` line in `requirements.txt`, rejects any `rapidfuzz` entry without `==`, and asserts `rapidfuzz.__version__ == "3.14.6"` plus both fuzz functions callable.
- The `token_set_ratio("fuzzy was a bear but not a dog", "fuzzy was a bear") == 100.0` assertion is executable evidence for RESEARCH finding 3 — the reason plan 02-04 gates on `token_sort_ratio` and treats token-set as a diagnostic.

## Task Commits

Each task was committed atomically:

1. **Task 1: Confirm the rapidfuzz pin before it is installed** — checkpoint only, no artefact (`checkpoint:human-verify`, resolved with `approved`)
2. **Task 2: Install the approved pin, declare it in both manifests, and bind the declaration to the installed version** - `a7df39d` (chore)

**Plan metadata:** _committed with STATE/ROADMAP after this file_

## Files Created/Modified

- `pyproject.toml` — adds `"rapidfuzz==3.14.6"` to `[project].dependencies`, before the `python-jobspy` git pin, with a two-line rationale comment.
- `requirements.txt` — mirrors `rapidfuzz==3.14.6` verbatim, so the Dockerfile installs the library the dedup stage needs.
- `tests/test_dependency_pins.py` — new guard module: `test_rapidfuzz_pin_is_declared_exactly`, `test_rapidfuzz_imports_at_the_pinned_version`.

## Decisions Made

- **Installed into both venvs.** The plan names `.venv-host` as the only venv with pip, but `.venv` is the only venv in which the test suite runs (`.venv-host` has a broken `pydantic_core` compiled dependency). The exact same wheel was installed into both with `pip --python`, so the plan's must-have (`.venv-host` importable) holds *and* plan 02-04's import-under-test works.
- **Placed the pin before the git dependency.** `pyproject.toml` groups the registry pins and then the single git reference; inserting `rapidfuzz` before `python-jobspy` keeps that grouping and matches the mirrored position in `requirements.txt`.
- **No `dedup_fuzzy_threshold` coupling.** This plan adds no assertion tying θ to a merge outcome (A1/02-01 owns θ), and asserts no merge-rate band (the QUEUE-03 residue is a reported statistic in 02-06, not an assertion).

## Deviations from Plan

### Environment substitutions (not plan defects)

- **`<verify>` commands ran through `.venv/bin/python -m pytest`.** The plan writes `.venv-host/bin/pytest`; that console script's shebang points at a stale absolute path and `.venv-host`'s `pydantic_core` wheel is broken (gnu/musl mismatch), so the suite cannot run there. Every command has an exact equivalent under the working `.venv` (same Python 3.14.7, same package versions). Already recorded in `deferred-items.md` by plan 02-01.
- **Dual-venv install.** The plan's action names only `.venv-host`; the install was additionally performed into `.venv` with `pip --python`, because the test runner is `.venv` and plan 02-04 imports `rapidfuzz` under it. Directed by the orchestrator's environment facts; it strengthens rather than weakens the plan's must-have.

**Total deviations:** 0 auto-fixed (no bugs, missing functionality or blockers encountered).
**Impact on plan:** None on committed artifacts; the substitutions are sandbox-only and every acceptance criterion was still met.

## Authentication Gates

- **Task 1 was a `checkpoint:human-verify gate="blocking-human"`** (package legitimacy, T-02-04). It was surfaced to the human out-of-band with the version/source/build-step evidence and resolved with `user_response = "approved"`. No re-prompt was needed and no install ran before the approval. Kinds of change this gate protects: a slopsquatted distribution or an arbitrary source build. Evidence seen: `pip index versions` → 3.14.6 latest; PyPI JSON `Project-URL` → `github.com/rapidfuzz/RapidFuzz`; wheel-only install.

## Issues Encountered

- None. The first full-suite run reported `32.06s` wall-clock (above the usual ~20s lane) but a clean re-run reported `16.72s` — machine contention, not a regression.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The Tier-2 dedup slice (02-04) can now `import rapidfuzz.fuzz.token_sort_ratio`; `rapidfuzz.__version__` is bound to the declared pin.
- `requirements.txt` carries the pin, so the container build installs it.
- Requirements **QUEUE-03 and FILT-01 were deliberately NOT marked complete**: both are declared by sibling plans in this phase with no SUMMARY yet, so the shared-ID gate (`requirements.ready-ids` → `0/2 ready`) holds them until the last declaring plan finishes.

---
*Phase: 02-clean-filtered-queryable-queue*
*Completed: 2026-09-16*

## Self-Check: PASSED

- Created/modified files exist on disk: `pyproject.toml`, `requirements.txt`, `tests/test_dependency_pins.py`.
- Commit `a7df39d` exists; base `b783419` unchanged.
- `rapidfuzz` imports at exactly `3.14.6` in both `.venv-host` and `.venv`.
- `git diff --numstat pyproject.toml requirements.txt` → `4 0` / `4 0` (additions only).
- Full suite re-run green: `323 passed, 2 deselected in 16.72s`.
