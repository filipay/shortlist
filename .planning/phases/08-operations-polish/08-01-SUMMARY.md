---
phase: 08-operations-polish
plan: 01
subsystem: infra
tags: [apscheduler, scheduling, pydantic-settings, docker, timezone, dependency-pins]

# Dependency graph
requires: []
provides:
  - "apscheduler==3.11.3 installed in the project venv and pinned identically in pyproject.toml and requirements.txt"
  - "Settings.schedule_timezone (default Europe/Dublin) and Settings.schedule_misfire_grace_seconds (default 3600), covered by the config surface/ceiling/literal-scan guards"
  - "Both schedule knobs forwarded through compose.yml"
  - "Dockerfile ENV TZ=Europe/Dublin plus a build-time ZoneInfo('Europe/Dublin') assertion"
  - "entrypoint.sh --workers 1 rationale extended to name the scheduler"
affects: [08-03 (scheduler + migration), 08-04 (next-run display), 08-05 (health page)]

# Actuals (#2632) — chars/4 over the realized diff (git diff HEAD~1..HEAD = 8804 chars), same scale as the estimate.
actuals:
  tokens: 2201
  tasks: 1
  commits: 1

# Tech tracking
tech-stack:
  added:
    - "apscheduler==3.11.3 (persistent in-process cron scheduler; transitive tzlocal, deliberately unpinned)"
  patterns:
    - "A new runtime dependency is admitted behind a blocking-human legitimacy gate, then pinned verbatim in BOTH manifests and bound to the installed distribution by a PINNED_PACKAGES row"
    - "Schedule ceilings are Settings fields (PLAT-04), not module constants"
    - "An environment fact the runtime depends on (the tz database) is proven by a build-time RUN assertion, next to the Tectonic/JobSpy proofs"

key-files:
  created: []
  modified:
    - pyproject.toml
    - requirements.txt
    - tests/test_dependency_pins.py
    - app/config.py
    - tests/test_config.py
    - compose.yml
    - Dockerfile
    - entrypoint.sh

key-decisions:
  - "Installed apscheduler==3.11.3 at the exact pin the human approved; 4.x remains alpha and out (D-17)."
  - "tzlocal is a transitive dependency and is deliberately NOT exact-pinned, matching the JobSpy/pandas precedent."
  - "Installed into the venv's real 3.14 site-packages (.venv/lib/python3.14/site-packages) as well as the sandbox's 3.11 path, because .venv/bin/python resolves inconsistently in this sandbox."
  - "schedule_timezone is guarded by the surface tier only; schedule_misfire_grace_seconds is also in LIMIT_FIELDS because its 3600 default is a distinctive integer."

requirements-completed: [RUN-05]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "apscheduler installed at 3.11.3 and declared at that exact pin in both manifests, bound to the installed distribution"
    requirement: "RUN-05"
    verification:
      - kind: unit
        ref: "tests/test_dependency_pins.py#test_pinned_package_imports_at_the_pinned_version"
        status: pass
      - kind: unit
        ref: "tests/test_dependency_pins.py#test_pinned_package_declared_exactly (PINNED_PACKAGES row)"
        status: pass
      - kind: other
        ref: ".venv/bin/python -c \"import apscheduler; print(apscheduler.__version__)\" -> 3.11.3"
        status: pass
    human_judgment: false
  - id: D2
    description: "Settings.schedule_timezone defaults to Europe/Dublin and is asserted by the surface guard"
    requirement: "RUN-05"
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_documented_defaults"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_settings_exposes_every_documented_knob"
        status: pass
    human_judgment: false
  - id: D3
    description: "Settings.schedule_misfire_grace_seconds defaults to 3600, covered by both guards"
    requirement: "RUN-05"
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_documented_defaults"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_every_limit_field_is_a_required_numeric_ceiling"
        status: pass
    human_judgment: false
  - id: D4
    description: "Literal scan widened to app/jobs so a hard-coded schedule ceiling there is caught"
    requirement: "PLAT-06"
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_no_distinctive_threshold_literal_remains_in_probe_or_pipeline"
        status: pass
    human_judgment: false
  - id: D5
    description: "Both schedule knobs forwarded through compose.yml with defaults matching app/config.py"
    requirement: "RUN-05"
    verification:
      - kind: other
        ref: "grep -n 'SCHEDULE_MISFIRE_GRACE_SECONDS' compose.yml -> defaults 3600"
        status: pass
    human_judgment: false
  - id: D6
    description: "The image proves ZoneInfo('Europe/Dublin') resolves at build time, and entrypoint.sh records the scheduler as the second reason for --workers 1"
    verification: []
    human_judgment: true
    rationale: "Docker is absent from the agent sandbox, so the build-time tz assertion cannot be executed here; the operator confirms it with `docker compose build`. Recorded as WINDOWS.md #14."

# Metrics
duration: 11min
completed: 2026-10-14
status: complete
---

# Phase 8 Plan 01: One new dependency, behind a human gate — Summary

**`apscheduler==3.11.3` admitted behind a cleared blocking-human gate, pinned identically in both manifests behind a guard test, with the two schedule knobs shipped as `Settings` fields, forwarded through compose, and the image's `Europe/Dublin` tz database proven at build time.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-10-14T17:12:10Z (first edit)
- **Completed:** 2026-10-14T17:23:23Z (task commit)
- **Tasks:** 1 executable task (Task 1 was a `checkpoint:human-verify` gate, no commit)
- **Files modified:** 8

## Accomplishments
- `apscheduler==3.11.3` installed and declared as a standalone exact pin in **both** `pyproject.toml` `[project].dependencies` and `requirements.txt`, with a `PINNED_PACKAGES` row binding the declaration to the installed distribution.
- Two new `Settings` fields shipped with their documented defaults — `schedule_timezone = "Europe/Dublin"` (never container UTC) and `schedule_misfire_grace_seconds = 3600` — both covered by the config surface guard, the grace additionally by the numeric-ceiling guard, and `app/jobs` added to the literal scan.
- Both knobs forwarded through `compose.yml`, closing the unforwarded-knob defect class.
- The image now proves `ZoneInfo("Europe/Dublin")` at build time (`ENV TZ` + a one-line `RUN` assertion next to the Tectonic/JobSpy proofs).
- `entrypoint.sh` keeps `--workers 1` and now names the scheduler as its second reason.

## Task Commits

Each task was committed atomically:

1. **Task 2: Install and pin apscheduler, then declare the two schedule knobs and prove the image's tz database** - `431a639` (feat)

**Plan metadata:** pending in the SUMMARY/WINDOWS/deferred-items commit (the orchestrator owns STATE.md/ROADMAP.md writes).

## Files Created/Modified
- `pyproject.toml` - added `"apscheduler==3.11.3"` to `[project].dependencies` with a documenting comment.
- `requirements.txt` - mirrored the identical pin line and comment.
- `tests/test_dependency_pins.py` - added the `apscheduler` row to `PINNED_PACKAGES` and a docstring line.
- `app/config.py` - added the Phase-8 schedule block (`schedule_timezone`, `schedule_misfire_grace_seconds`).
- `tests/test_config.py` - both fields in `REQUIRED_SETTINGS_FIELDS`, the grace in `LIMIT_FIELDS`, `"app/jobs"` in `SCANNED_DIRS`, both defaults asserted in `test_documented_defaults`.
- `compose.yml` - `SCHEDULE_TIMEZONE` and `SCHEDULE_MISFIRE_GRACE_SECONDS` passthrough entries.
- `Dockerfile` - `ENV TZ=Europe/Dublin` plus the build-time `ZoneInfo` assertion.
- `entrypoint.sh` - extended `--workers 1` comment (command unchanged).

## Decisions Made
- The checkpoint was resolved by a human at `approved: apscheduler=3.11.3` before any install or manifest edit; only that exact pin was installed.
- `tzlocal` (transitive) is deliberately not exact-pinned.
- `schedule_timezone` stays out of `LIMIT_FIELDS` (it is a string); `schedule_misfire_grace_seconds` is in it (distinctive integer 3600).

## Deviations from Plan

None - plan executed exactly as written, with one environment reconciliation:

### Environment reconciliation (not a code deviation)

**1. Venv interpreter mismatch in the agent sandbox**
- **Found during:** Task 2 (install step).
- **Issue:** `.venv/bin/python` resolves via a stale symlink to the sandbox's Python 3.11.2 (the venv was created for 3.14.7, whose compiled extensions under `.venv/lib/python3.14/site-packages` are musl-linked while the only local 3.14 is glibc). The plan's documented `--target` fallback was therefore used, installing into `.venv/lib/python3.11/site-packages` so the default-lane command works here — **and additionally** into `.venv/lib/python3.14/site-packages`, which is the venv's real site-packages on a correct host.
- **Fix:** Installed `apscheduler==3.11.3` (+ transitive `tzlocal==5.4.4`) into both site-packages with `python3 -m pip install --target …`; no third-party package besides the approved `apscheduler` (and its transitive `tzlocal`) was installed.
- **Files modified:** none in git (`.venv/` is gitignored — no repository trace).
- **Verification:** `import apscheduler` prints `3.11.3` from `.venv/bin/python`, and from the glibc 3.14 interpreter pointed at `.venv/lib/python3.14/site-packages`.

---

**Total deviations:** 0 code deviations; 1 environment reconciliation (sandbox interpreter mismatch, no repo change).
**Impact on plan:** None on the shipped artefact; the pin, manifests and guards are exactly as the plan specified.

## Issues Encountered

- **Project venv is unusable as-is in this sandbox** (musl-built extensions vs glibc Python 3.14; `bin/python` stale). Tests were run with a working Python 3.11 (`/tmp/gsdvenv`) plus `PYTHONPATH` covering the project root and `.venv/lib/python3.11/site-packages`.
- **Full hermetic suite:** `1804 passed, 1 failed, 15 deselected, 2 xfailed`. The single failure is `tests/test_stylesheet_coverage.py::test_the_committed_stylesheet_is_the_build_of_its_source` — a pre-existing CSS-artifact drift unrelated to this plan's files (no CSS/template/stylesheet file is touched). Logged to `deferred-items.md`; not fixed (out of scope).
- **Docker absent** — the build-time tz assertion could not be executed. Recorded as `WINDOWS.md` #14 (`unrun-verify`) with the operator's arming step `docker compose build`; `tzdata` is the documented remedy if the assertion fails.

## Verification Results

| Check | Result |
|---|---|
| `.venv/bin/python -c "import apscheduler; print(apscheduler.__version__)"` | `3.11.3` — pass |
| `tests/test_dependency_pins.py` | 6 passed |
| `tests/test_config.py` | 29 passed |
| Exact pin present in both manifests (tomllib + requirements scan) | pass |
| `Settings` schedule defaults assert | pass |
| `grep SCHEDULE_MISFIRE_GRACE_SECONDS compose.yml` | present, defaults 3600 |
| `grep ZoneInfo Dockerfile` | present (build-time proof) |
| Full suite `-m 'not live and not latex'` | 1804 passed, 1 pre-existing failure (stylesheet), 2 xfailed |

## User Setup Required

None — no external service configuration. The only operator step is `docker compose build` (to exercise the tz assertion; see `WINDOWS.md` #14).

## Next Phase Readiness
- Plan 08-03 can `import apscheduler.schedulers.asyncio` / `apscheduler.jobstores.sqlalchemy` at module scope, with `Settings.database_url_sync` available for the `SQLAlchemyJobStore` and the two schedule knobs ready to be read.
- No blockers. The `app/jobs` literal-scan coverage is already in place, so a hard-coded schedule ceiling in 08-03 fails `tests/test_config.py`.

---
*Phase: 08-operations-polish*
*Completed: 2026-10-14*

## Self-Check: PASSED

- Files created: 08-01-SUMMARY.md, deferred-items.md — found.
- Commits: 431a639, 90e3208 — found.
- STATE.md / state.json left as pre-existing dirty files (not staged, not committed by this run).
