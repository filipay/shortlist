---
status: testing
phase: 04-cv-fact-store-latex-compile-spike
source: 04-VERIFICATION.md
started: 2026-09-21T16:00:00Z
updated: 2026-09-21T16:00:00Z
---

# Phase 04 — Human Verification (UAT)

Verification returned `human_needed` with 20/29 must-haves verified. No must-have
FAILED, so this is not a gap-closure cycle: the phase is hermetically proven but
its two externally dependent halves — the in-container Tectonic compile and the
real-document fact-equivalence/spike — were never executed in this environment.

Every item below is **operator-only**. None of them can be satisfied by a
hermetic test run, and none may be recorded as passed until it is actually run.

## Current Test

**Test 1 of 6 — Run the container LaTeX lane**
- expected: the 10 latex-marked nodes run (not skipped) and report at least one passed with no failures; the fixture compiles offline to a real PDF and both fact-equivalence compiles pass
- awaiting: operator (requires Docker + the pinned Tectonic image)

## Tests

### 1. Run the container LaTeX lane
test: `docker compose run --rm app pytest -m latex`
expected: The 10 latex-marked nodes run (not skipped) and report at least one passed with no failures; offline compile of the fixture produces a real PDF and both fact-equivalence compiles pass.
why_human: Docker and Tectonic are absent here; the lane is collected-and-skipped (10 skipped). An UNRUN check must not be recorded as passed.
result: [pending]

### 2. Confirm the installed engine's own option names (D-75)
test: `docker compose run --rm app tectonic --help`
expected: The help output contains `--only-cached` and `--untrusted`. If it does not, the argv in `app/latex/compile.py` is wrong and must be corrected, not the assertion relaxed.
why_human: The flag names are currently carried from the constants in `compile.py`; the installed binary has never been read in this environment.
result: [pending]

### 3. Bundle coverage per preamble package
test: `docker compose run --rm app tectonic -X bundle search <package>` for each of fontspec, geometry, tabularx, paracol, enumitem, titlesec, hyperref
expected: Each package is reported as held by the bundle (or the missing ones are added to the build-time prime and the image rebuilt).
why_human: Requires the pinned binary inside the image.
result: [pending]

### 4. Measure the TeX Live fallback (D-76) or leave it unclaimed
test: `docker build -f Dockerfile.texlive -t job-search-copilot:texlive .` then compile the fixture with `LATEX_ENGINE=texlive`
expected: Image size, build duration, compile argv and page count recorded in `docs/probes/2026-09-21-cv-tex-spike.md` §5 — or §5 stays "Not taken" and the fallback stays not-claimed (which is its current, honest state).
why_human: Building a second multi-GB image is a one-off operator action; the verdict correctly records the measurement as NOT TAKEN rather than implying it.
result: [pending]

### 5. Take the real-document measurement that closes STATE blocking unknown #1
test: `mkdir -p cv artifacts`, place the real LaTeX CV at `cv/base.tex`, run `bash scripts/cv-tex-spike.sh`, then append the counts and unresolved names to `docs/probes/2026-09-21-cv-tex-spike.md` §4
expected: Sections/entries/bullets/lines counts, unresolved macro names with counts and lines, the truncation flag, and per-package bundle coverage are recorded — or the document stays PARTIAL and the blocking unknown stays open. Counts/names only; never CV text.
why_human: The real document is deliberately not in this repository (D-58); every current number measures the synthetic stand-in. SC-4 is satisfied only as scoped by D-62 (partial verdict + trigger), so the real decomposition remains unproven.
result: [pending]

### 6. Attest the package-legitimacy decision (04-01 D6)
test: confirm the human saw and approved `pypdf==6.19.0` (source https://github.com/py-pdf/pypdf, pure-Python wheel) and `pyyaml==6.0.3` before install
expected: The approval is genuine and predates the manifest edits; the recorded string `approved: pypdf=6.19.0 pyyaml=6.0.3` reflects a real human decision.
why_human: Legitimacy checkpoints are never auto-approvable; the gate is an out-of-band human signal that no test can verify.
result: [pending]

## Summary

- total: 6
- passed: 0
- failed: 0
- pending: 6

## Gaps

No blocking product gaps. Four known non-blocking code warnings are recorded in
`04-REVIEW.md` (WR-01 `cv_repo.py` `is_current` cleared outside the SAVEPOINT;
WR-02 `import_tex.py` silent slug-collision of distinct organisation names;
WR-03 hard-coded `_HEALTH_TIMEOUT_SECONDS`/`_LOG_TAIL_CHARS`; WR-04 `_flatten`
leaving a dangling backslash) and five non-blocking companion-assertion gaps in
`04-SECURITY.md`. None of these fail a requirement. Suggested follow-up:
`/gsd-code-review 04 --fix`.
