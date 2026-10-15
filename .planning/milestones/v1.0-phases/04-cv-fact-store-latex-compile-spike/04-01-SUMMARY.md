---
phase: 04-cv-fact-store-latex-compile-spike
plan: 01
subsystem: infra
tags: [dependencies, pypdf, pyyaml, pytest-markers, supply-chain]

# Dependency graph
requires:
  - phase: 02-clean-filtered-queryable-queue
    provides: the T-02-04 pin-guard precedent (tests/test_dependency_pins.py) this plan generalises
  - phase: 03-llm-port-structured-output
    provides: the `live` pytest lane idiom (registered marker + addopts exclusion) the `latex` lane copies
provides:
  - pypdf==6.19.0 installed and declared as a runtime pin in both manifests
  - pyyaml promoted from dev-only to a runtime pin, declared exactly once in both manifests
  - the `latex` pytest marker registered and excluded from the default lane (addopts = -m 'not live and not latex')
  - app/latex/ package marker, so plans 04-02 and 04-03 have no file edge between them
  - one dependency guard binding all three pins to the installed distributions, with a can-fail companion
affects: [04-02, 04-03, 04-04, 04-05, phase-06]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
# Same estimateTokens scale (chars/4 over the realized diff), never a harness token count.
actuals:
  tokens: 1694
  tasks: 2
  commits: 1
plan_head_before: 87124ea46fa317adbe376770b8dae2a38d28db78

# Tech tracking
tech-stack:
  added:
    - "pypdf==6.19.0 (new runtime pin: PDF page count + text extraction)"
    - "pyyaml==6.0.3 (promoted dev-only → runtime: the cv.yaml loader)"
  patterns:
    - "Table-driven dependency-pin guard with a split-out checker and a can-fail companion"
    - "A pytest lane's registration and its addopts exclusion asserted in one test so neither drifts alone"

key-files:
  created:
    - app/latex/__init__.py
  modified:
    - requirements.txt
    - pyproject.toml
    - tests/test_dependency_pins.py
    - tests/llm/test_contract_snapshot.py

key-decisions:
  - "Both package-legitimacy SUS verdicts were cleared by a blocking human checkpoint before any install or manifest edit (approved: pypdf=6.19.0 pyyaml=6.0.3)."
  - "pyyaml was removed from [project.optional-dependencies].dev rather than duplicated — a dev+runtime double declaration is exactly the drift the promotion exists to prevent."
  - "addopts was widened additively to 'not live and not latex' so the D-68 byte-exact golden regression keeps its default-lane coverage."
  - "pypdf was installed from the pure-Python wheel (pypdf-6.19.0-py3-none-any.whl); no build step executed."

patterns-established:
  - "Dependency guard: _declaration_misses() is a pure checker so a negative-control test can prove it discriminates rather than passing vacuously."
  - "Lane contract: the marker string and the addopts exclusion for a lane are asserted together in one test."

requirements-completed: [CV-01, CV-03, CV-05]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "pypdf 6.19.0 is installed into the default-lane interpreter and imports at the approved pin"
    requirement: CV-03
    verification:
      - kind: other
        ref: '.venv/bin/python -c "import pypdf; print(pypdf.__version__)" -> 6.19.0'
        status: pass
    human_judgment: false
  - id: D2
    description: "pyyaml is a runtime pin, declared exactly once, mirrored verbatim in requirements.txt and pyproject.toml; pypdf is mirrored too"
    requirement: CV-01
    verification:
      - kind: unit
        ref: "tests/test_dependency_pins.py::test_pinned_package_is_declared_exactly"
        status: pass
      - kind: other
        ref: "tomllib assertion: pyyaml absent from [dev], present in [project].dependencies"
        status: pass
    human_judgment: false
  - id: D3
    description: "The `latex` marker is registered and excluded from the hermetic default lane"
    requirement: CV-05
    verification:
      - kind: unit
        ref: "tests/test_dependency_pins.py::test_the_latex_marker_is_registered_and_excluded"
        status: pass
      - kind: other
        ref: ".venv/bin/python -m pytest -q -m 'not live and not latex' --collect-only -q (851 collected, no unknown-marker warning)"
        status: pass
    human_judgment: false
  - id: D4
    description: "All three pinned distributions are bound to their installed versions, and the guard can actually fail"
    verification:
      - kind: unit
        ref: "tests/test_dependency_pins.py::test_pinned_package_imports_at_the_pinned_version"
        status: pass
      - kind: unit
        ref: "tests/test_dependency_pins.py::test_the_pin_checker_can_actually_fail"
        status: pass
    human_judgment: false
  - id: D5
    description: "app/latex/__init__.py exists as a package marker only (docstring, no code), opening the lane for plans 04-02/04-03"
    verification:
      - kind: other
        ref: "pathlib assertion: file exists, contains no 'import' and no 'def '"
        status: pass
    human_judgment: false
  - id: D6
    description: "A human explicitly confirmed each SUS package's name, version, source and no-build-step before the install ran"
    requirement: CV-01
    verification: []
    human_judgment: true
    rationale: "Package legitimacy is a trust decision the protocol forbids automating; the approval is an out-of-band human signal, not a test."
  - id: D7
    description: "The full hermetic suite stays green after adding a dependency and widening the lane"
    verification:
      - kind: integration
        ref: ".venv/bin/python -m pytest -q -> 847 passed, 4 deselected"
        status: pass
    human_judgment: false

# Metrics
duration: 7 min
completed: 2026-09-21
status: complete
---

# Phase 4 Plan 1: Dependencies + LaTeX Lane Summary

**pypdf 6.19.0 installed and pinned, pyyaml promoted dev→runtime in both manifests, and the `latex` pytest lane registered and excluded — behind a human-cleared supply-chain gate**

## Performance

- **Duration:** 7 min
- **Started:** 2026-09-21T13:46:14Z
- **Completed:** 2026-09-21T13:54:04Z
- **Tasks:** 2 (1 pre-approved human-verify checkpoint + 1 auto task)
- **Files modified:** 5 in the commit (4 planned + 1 Rule-1 deviation fix)

## Accomplishments

- Installed `pypdf==6.19.0` — the human-approved pure-Python wheel (`pypdf-6.19.0-py3-none-any.whl`, no build step) — into the default-lane interpreter `.venv/bin/python`.
- Promoted `pyyaml==6.0.3` from dev-only to a runtime dependency in `pyproject.toml` and added the mirrored pin to `requirements.txt`; the dev-list entry was **removed**, so it is declared exactly once.
- Registered the `latex` pytest marker and widened `addopts` additively to `-m 'not live and not latex'`, keeping the D-68 golden renderer regression in the hermetic lane while a machine with no TeX engine stays green.
- Generalised `tests/test_dependency_pins.py` into a table-driven guard for `pypdf`/`pyyaml` (the `rapidfuzz` tests are unchanged in substance) and added a can-fail companion proving the checker discriminates.
- Created `app/latex/__init__.py` as a package marker only, so wave-2 plans 04-02 and 04-03 have no file edge between them.
- Recorded the human approval of both `[SUS]` packages: `approved: pypdf=6.19.0 pyyaml=6.0.3` — pypdf 6.19.0 is PyPI latest with a pure-Python universal wheel and source `https://github.com/py-pdf/pypdf`; pyyaml 6.0.3 is PyPI latest, already installed in both venvs, Home-page `https://pyyaml.org/`, no install required.

## Task Commits

Each task was committed atomically:

1. **Task 1: Confirm the pypdf and pyyaml pins (checkpoint:human-verify, gate="blocking-human")** — no commit (human approval, out of band: `approved: pypdf=6.19.0 pyyaml=6.0.3`)
2. **Task 2: Install the approved pins, promote pyyaml to runtime in both manifests, and open the latex lane** — `320e2e2` (chore)

**Plan metadata:** `320e2e2` (task commit; SUMMARY committed separately)

## Files Created/Modified

- `app/latex/__init__.py` — created; package docstring only (the lane's marker, filled by plan 04-02)
- `pyproject.toml` — `pypdf==6.19.0` + `pyyaml==6.0.3` added to `[project].dependencies`; the dev-only pyyaml entry removed; `markers` gained `latex`; `addopts` widened
- `requirements.txt` — the two pins mirrored verbatim with consumer comments
- `tests/test_dependency_pins.py` — helpers refactored, `PINNED_PACKAGES` table, three new tests plus a can-fail companion
- `tests/llm/test_contract_snapshot.py` — Phase-3 launcher test unfrozen from the exact old addopts string (Rule 1 fix, see Deviations)

## Decisions Made

- Human approval recorded before any install or manifest change, per the `[SUS]` gate; the approved pins are `pypdf==6.19.0` and `pyyaml==6.0.3`.
- `pyyaml` removed from `[dev]` rather than left duplicated — a package declared in both runtime and dev is the drift the promotion exists to prevent.
- `addopts` widened **additively** (`not live and not latex`) so the existing `live` exclusion and the hermetic golden regression both survive.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Unfroze a Phase-3 test that hard-coded the old `addopts` string**
- **Found during:** Task 2 ("full hermetic suite is green" acceptance criterion)
- **Issue:** `tests/llm/test_contract_snapshot.py::test_the_default_lane_cannot_run_the_live_lane` asserted `"-m 'not live'" in ini_options["addopts"]`. The plan-mandated widening to `-m 'not live and not latex'` broke it (`1 failed, 846 passed`). The plan's `files_modified` list did not include this test.
- **Fix:** Changed the assertion to `"not live" in ini_options["addopts"]`, preserving the guard's intent (the `live` lane must stay deselected) without freezing the whole string.
- **Files modified:** `tests/llm/test_contract_snapshot.py`
- **Verification:** `.venv/bin/python -m pytest -q` → `847 passed, 4 deselected`
- **Committed in:** `320e2e2` (part of the Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** The fix was forced by the plan's own acceptance criterion ("the full hermetic suite is green") and is directly caused by the plan-mandated `addopts` change. It touches one file outside the declared `files_modified` set; no other scope creep.

## Issues Encountered

- The full hermetic suite initially failed on the Phase-3 launcher test described above; resolved as a Rule-1 fix and re-verified green.
- `.venv` has no `pip` module, so `pypdf` was installed with `.venv-host/bin/python -m pip install --target "$(.venv/bin/python -c 'import site;print(site.getsitepackages()[0])')"`, the first of the two routes the plan verified. `pyyaml` needed no install (already present at 6.0.3).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `pypdf` is importable and pinned; `pyyaml` is a runtime declaration in both manifests — the dependency prerequisites for plans 04-03 (`app/cv/factstore.py`) and 04-04 (PDF fact-equivalence) are in place.
- The `latex` marker exists and is excluded from the default lane, so plans 04-02 and 04-04 can add `latex`-marked tests without breaking a machine with no TeX engine. Run them with an explicit `pytest -m latex`.
- `app/latex/` exists as a package marker; plans 04-02 and 04-03 can fill it in the same wave with no shared-file edge.
- Pre-existing untracked files (`.gsd/`, `.planning/milestone.lock`, `jobsearch.db`) were left untouched; they are outside this plan's scope.

## Self-Check: PASSED

---
*Phase: 04-cv-fact-store-latex-compile-spike*
*Completed: 2026-09-21*
