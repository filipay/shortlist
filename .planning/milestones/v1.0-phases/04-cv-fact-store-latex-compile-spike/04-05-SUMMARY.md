---
phase: 04-cv-fact-store-latex-compile-spike
plan: 05
subsystem: cv
tags: [latex, tectonic, texlive, bounded-parser, cv-fact-store, probe, verdict]

requires:
  - phase: 04-cv-fact-store-latex-compile-spike
    provides: "04-02 the LatexEngine port + compile path + the committed fixture; 04-03 the CvFacts fact store + deterministic renderer; 04-04 PDF fact extraction + the revision log"
provides:
  - "app/cv/import_tex.py — the bounded, human-reviewed `.tex` importer and its report type"
  - "scripts/cv-tex-spike.sh — the re-runnable spike entry point (D-60)"
  - "docs/probes/2026-09-21-cv-tex-spike.md — the partial verdict plus the real-document trigger (D-62)"
  - "docs/runbook-latex-compile.md — the operator runbook for the container lane and the engine switch"
affects: [phase-05, phase-06]

actuals:
  tokens: 13100
  tasks: 3
  commits: 6
  plan_head_before: f7ae494

tech-stack:
  added: []
  patterns:
    - "Bounded parser + curation: learn arity from the `\\newcommand` declaration, capture that many balanced groups at each call site, report everything else by name and count — never guess"
    - "A PARTIAL verdict with a proven-versus-unproven split and a named trigger command rather than a claimed measurement"
    - "The importer writes only to a caller-chosen destination; a hash assertion proves the source document is untouched"

key-files:
  created:
    - app/cv/import_tex.py
    - tests/cv/test_import_tex.py
    - scripts/cv-tex-spike.sh
    - docs/runbook-latex-compile.md
    - docs/probes/2026-09-21-cv-tex-spike.md
  modified:
    - docs/probes/README.md
    - .planning/STATE.md

key-decisions:
  - "Entry arity is learned from the preamble declaration and applied at call sites; a wrong-arity parser is asserted to report a different entry count, so the mechanism is load-bearing rather than present"
  - "A field the parser could not fill is emitted absent, so the fact store fails loudly at that path — unresolved is never indistinguishable from empty"
  - "The verdict carries exactly one PARTIAL marker; the real document is not in the repo by design, so an UNRESOLVED section names the command that closes it"
  - "The engine version, the D-75 flag confirmation, bundle coverage and the D-76 fallback measurement are recorded as NOT TAKEN in this environment rather than implied"

patterns-established:
  - "The spike script is a thin entry point over the importer, so a human reading either file can reproduce the measurement"
  - "The runbook's gate command is the same string the lane tests name in their skip reasons"

requirements-completed: [CV-01, CV-02, CV-05]

coverage:
  - id: D1
    description: "The bounded importer parses sections, entry macros by arity, bullets and packages from a LaTeX CV and reports everything else by name, count and line — with the source document provably unmodified"
    requirement: "CV-01, CV-02"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest -q tests/cv/test_import_tex.py -x (17 passed)"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -c \"... parse_tex + write_draft + sha256 before/after ...\" (read-only import ok)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The re-runnable spike script: syntax-valid, dry-run names both paths, a missing source is a loud distinct failure, and its summary prints counts, unresolved names and the truncation flag"
    requirement: "CV-05"
    verification:
      - kind: unit
        ref: "bash -n scripts/cv-tex-spike.sh && bash scripts/cv-tex-spike.sh --dry-run (exit 0); missing source exits 3 naming the path"
        status: pass
    human_judgment: false
  - id: D3
    description: "The operator runbook names the one gate command, the first-run directory step, the offline failure mode, the D-75 flag confirmation, the fallback's own sandbox and the one-off fallback build"
    requirement: "CV-05"
    verification:
      - kind: unit
        ref: ".venv/bin/python -c \"... runbook content assertions ...\" (runbook ok)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The dated verdict carries exactly one PARTIAL marker, a proven-versus-unproven split, an UNRESOLVED trigger and no contact-shaped string; the README points at it and STATE.md points at the trigger"
    requirement: "CV-01, CV-05"
    verification:
      - kind: unit
        ref: ".venv/bin/python -c \"... verdict shape, no contact shapes, single marker ...\" (all pass)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The real document's decomposition, the engine's bundle coverage, the D-75 flag confirmation inside the image, and the D-76 fallback measurement"
    requirement: "CV-01, CV-05"
    verification: []
    human_judgment: true
    rationale: "Unmeasurable in the executor environment: no container runtime and no LaTeX engine are present (D-69). The exact operator commands are recorded in the verdict document and the runbook; the stand-in counts are measured, but a stand-in result must never be presented as a real-document measurement."

duration: 21 min
completed: 2026-09-21
status: complete
---

# Phase 04 Plan 05: CV `.tex` Decomposition Spike Summary

**A bounded, human-reviewed LaTeX-to-fact-store importer with a counts-and-names report, a re-runnable spike script, an operator compile runbook, and a dated PARTIAL verdict that names the real-document trigger instead of claiming a measurement**

## Performance

- **Duration:** 21 min
- **Started:** 2026-09-21T14:57Z (approx.)
- **Completed:** 2026-09-21T15:18Z
- **Tasks:** 3
- **Files modified:** 7 (5 created, 2 modified)

## Accomplishments

- `app/cv/import_tex.py` — a bounded parser that learns each entry macro's arity
  from its preamble declaration, captures exactly that many balanced brace groups
  at every call site, and reports everything else by name, count and line. It
  guesses nothing: a field it could not fill is emitted absent so the fact store
  fails loudly at that path.
- `scripts/cv-tex-spike.sh` — one re-runnable command over the importer, with a
  preflight, distinct exit codes, a review-draft destination that is not
  `cv.yaml`, a dry-run, and a counts-only summary.
- `docs/runbook-latex-compile.md` — the operator runbook: the one gate command
  (`docker compose run --rm app pytest -m latex`), the first-run `mkdir`, the
  offline failure mode, the D-75 flag confirmation, the fallback's own
  `-no-shell-escape`, and the one-off `Dockerfile.texlive` measurement.
- `docs/probes/2026-09-21-cv-tex-spike.md` — the dated verdict: one `PARTIAL`
  marker, the measured stand-in counts, and an `UNRESOLVED — blocked on the real
  document` section naming the exact command and path.
- `docs/probes/README.md` extended with the second probe (same page, two
  instruments and cadences), and STATE.md's blocking unknown #1 still open, now
  pointing at the trigger.

## Task Commits

Each task was committed atomically; Task 1 ran the RED→GREEN cycle:

1. **Task 1 RED: failing importer tests** — `2f116b5` (test)
2. **Task 1 GREEN: the bounded importer** — `9c7d5ff` (feat)
3. **Task 1 fix: scanner skipped the declaration body** — `f5ae205` (fix)
4. **Task 2: the spike script and the compile runbook** — `d1032ce` (feat)
5. **Task 3: the verdict, the README section and the STATE trigger** — `120a812` (docs)
6. **Task 3 follow-up: runbook wording** — `78edc2c` (docs)

**Plan metadata:** the SUMMARY commit that carries this file.

## Files Created/Modified

- `app/cv/import_tex.py` — `ImportReport`, `parse_tex`, `write_draft`, the bounded scanner
- `tests/cv/test_import_tex.py` — 17 tests, including an arity guard-can-fail companion
- `scripts/cv-tex-spike.sh` — the D-60 executable spike
- `docs/runbook-latex-compile.md` — the container lane and engine-switch runbook
- `docs/probes/2026-09-21-cv-tex-spike.md` — the partial verdict and trigger
- `docs/probes/README.md` — the LaTeX probe section
- `.planning/STATE.md` — the Phase-4 blocking-unknown entry only (see Deviations)

## Decisions Made

- Entry arity is read from the declaration and applied at call sites; the test suite
  includes a wrong-arity control that asserts a different entry count, so the
  mechanism is exercised rather than merely present.
- A draft field the parser could not fill is emitted **absent**, so the fact store's
  validator fails loudly naming the path — "unresolved" cannot masquerade as "empty".
- The verdict records the engine version, the D-75 flag names, bundle coverage and
  the D-76 fallback measurement as **not taken in this environment**, with the exact
  operator commands, rather than implying a measurement that was not made.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The scanner re-read the `\newcommand` declaration as a call site**
- **Found during:** Task 2 (running the spike against the committed fixture)
- **Issue:** After the preflight, the scanner advanced past the `\newcommand` token and
  then matched the macro's own name at its declaration site, capturing its body's
  commands into the unresolved report (a false `cventry` entry, and a false
  unresolved section heading count of 2 from `\titleformat{\section}` /
  `\titlespacing*{\section}`).
- **Fix:** The `newcommand` branch now skips the whole declaration, body included; a
  `\section` token with no brace group is reported as a token without counting a
  heading.
- **Files modified:** `app/cv/import_tex.py`
- **Verification:** The spike run now reports `unresolved section headings: 0` with no
  false `cventry`; `tests/cv/test_import_tex.py` still 17 passed.
- **Committed in:** `f5ae205`

**2. [Rule 1 - Bug, test expectation] The unresolved line reference was miscounted**
- **Found during:** Task 1 GREEN
- **Issue:** The inline document's `\mystery` token sits on line 5, not line 3; the
  test asserted `(3,)`.
- **Fix:** Corrected the assertion to `(5,)`. The parser was right.
- **Files modified:** `tests/cv/test_import_tex.py` (folded into the GREEN commit)
- **Verification:** 17 passed.
- **Committed in:** `9c7d5ff`

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs, one production and one test expectation).
**Impact on plan:** No scope creep. The production fix was required for the report to be
truthful; the test correction reconciled a miscount.

## Issues Encountered

**Docker and the LaTeX engine are unavailable in this environment.** `docker`,
`tectonic`, `xelatex` and `pdflatex` are all absent, so four operator-only checks
could **not** be run and are recorded as unrun rather than faked:

1. the container lane — `docker compose run --rm app pytest -m latex`;
2. the installed binary's flag names (D-75) — `docker compose run --rm app tectonic --help`;
3. bundle coverage per preamble package — `docker compose run --rm app tectonic -X bundle search <package>`;
4. the TeX Live fallback measurement (D-76) — `docker build -f Dockerfile.texlive ...`.

All four are named in `docs/probes/2026-09-21-cv-tex-spike.md` (header + `UNRESOLVED`)
and in the runbook. Nothing was presented as measured that was not. The hermetic half
(parser, script, document shape, the full default lane) is verified.

**Scope note.** `.planning/WINDOWS.md` was **not** modified — it is outside this plan's
`files_modified` set. The four unrun operator checks above are the ledger-worthy items
and are surfaced here and in the verdict instead. `docs/implementation-notes.md` was
read for its pattern but not modified, for the same reason. No requirement checkbox in
`REQUIREMENTS.md` was touched; requirement marking is the orchestrator's step.

## User Setup Required

The plan's `user_setup` is an operator action, not a service: create `cv/` and
`artifacts/`, place the real LaTeX CV at `cv/base.tex`, then run
`bash scripts/cv-tex-spike.sh` and append the counts (never CV text) to
`docs/probes/2026-09-21-cv-tex-spike.md`. No `USER-SETUP.md` file was created —
it is outside this plan's `files_modified` set, and the same instruction is already
in the verdict's `UNRESOLVED` section and in `04-VALIDATION.md`'s Manual-Only table.

## Next Phase Readiness

- The importer, the spike and the verdict shape are ready for the operator's one real
  run; blocking unknown #1 stays open with a named command.
- The container lane and the fallback remain unverified until an operator with Docker
  runs the four commands above.
- Phase 6 estimation can proceed knowing the decomposition measurement is outstanding,
  exactly as D-62 provides.

---

*Phase: 04-cv-fact-store-latex-compile-spike*
*Completed: 2026-09-21*

## Self-Check: PASSED

- Created files on disk: `app/cv/import_tex.py`, `tests/cv/test_import_tex.py`,
  `scripts/cv-tex-spike.sh`, `docs/runbook-latex-compile.md`,
  `docs/probes/2026-09-21-cv-tex-spike.md`, `docs/probes/README.md` — all FOUND.
- Commits present: `2f116b5`, `9c7d5ff`, `f5ae205`, `d1032ce`, `120a812`, `78edc2c` — all FOUND.
- Verifications re-run: `tests/cv/test_import_tex.py` 17 passed; `tests/cv` +
  `tests/test_import_discipline.py` 35 passed; hermetic lane 945 passed,
  14 deselected; verdict shape / no-contact / single-marker / README / STATE
  assertions all pass.
- Not self-checkable here: the four Docker/engine operator checks, recorded above
  as unverified with their exact commands.
