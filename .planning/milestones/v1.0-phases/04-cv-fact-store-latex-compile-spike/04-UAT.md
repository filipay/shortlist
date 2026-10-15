---
status: testing
phase: 04-cv-fact-store-latex-compile-spike
source: 04-VERIFICATION.md
started: 2026-09-21T16:00:00Z
updated: 2026-09-21T18:05:00Z
audit_acknowledged:
  milestone: v1.0
  at: 2026-10-15
  gap_snapshot: "testing::scenarios=2"
---

# Phase 04 — Human Verification (UAT)

Verification first returned `human_needed` (20/29, then 26/29). No must-have ever
FAILED, so this was never a gap-closure cycle: the phase was hermetically proven
but its two externally dependent halves — the in-container Tectonic compile and
the real-document fact-equivalence/spike — had never been executed in this
environment.

This UAT changed that. The operator built the image and ran the container lane,
which caught two real defects (below). The three code-review warnings that then
held verification at `human_needed` were fixed with failing-first tests, and
re-verification returned **`passed`, 29/29 must-haves**. The phase was marked
complete on that basis. The items still outstanding below are deferred
operator-only checks, not blockers.

Every item below is **operator-only**. None of them can be satisfied by a
hermetic test run, and none may be recorded as passed until it is actually run.

## Current Test

No blocking test is awaiting. The phase advanced on `verification.status: passed`
(29/29 must-haves) after the three code-review warnings were fixed. Two operator
checks remain deferred by design — item 4 (optional TeX Live measurement) and
item 5 (the real-document spike, which keeps STATE blocking unknown #1 open).
Item 3 was superseded by item 1 and is no longer outstanding.

## Container evidence gathered during UAT

Two real defects surfaced only once the image built and the lane actually ran.
Both were fixed, guarded, and committed; neither was reachable from the hermetic
lane, which is precisely why they are recorded here rather than in REVIEW.md.

**1. Tectonic does not create its `--outdir` (commit `0edde77`).**
The build-time cache prime passed `--outdir /tmp/prime` without creating the
directory, so the image build failed with `output directory "/tmp/prime" does
not exist`. The runtime path never hits this because `_compile()` is always
handed an existing staged workdir. Fixed by creating the directory in the same
`RUN`; guarded by
`tests/test_deploy_manifest.py::test_dockerfile_creates_every_outdir_it_hands_to_an_engine`.

**2. Staging did not create the directory it writes into (commit `a8a5321`).**
`_compile()` writes `cv.tex` into `workdir` *before* spawning the engine and
never created `workdir`. `tests/latex/test_fact_equivalence.py` passes
`tmp_path_factory.mktemp(...) / "human"`, a non-existent subdirectory, so the
staging write raised `FileNotFoundError`, which the broad handler at the bottom
of `_compile()` reported as `the engine binary was not found:
/usr/local/bin/tectonic` with `error_kind="not_found"` and `duration_ms=0`.
A present, working engine was reported missing. Fixed by
`workdir.mkdir(parents=True, exist_ok=True)` immediately before the write;
guarded by `tests/test_latex_engine_seam.py::test_compile_creates_the_workdir_it_stages_into`
(parametrised over both engines, hermetic — fails pre-fix).

Confirmed alongside them: Tectonic 0.17.0 is present and working at
`/usr/local/bin/tectonic`, its tarball verifies against the pinned SHA256
(`8533d07f…53a3b7`), and the image builds healthy in ~287 s.

## Tests

### 1. Run the container LaTeX lane

test: `docker compose run --rm app pytest -m latex`
expected: The 10 latex-marked nodes run (not skipped) and report at least one passed with no failures; offline compile of the fixture produces a real PDF and both fact-equivalence compiles pass.
why_human: Docker and Tectonic are absent here; the lane is collected-and-skipped (10 skipped). An UNRUN check must not be recorded as passed.
result: PASSED — `10 passed, 968 deselected in 9.75s` (`test_compile.py ...` 3 passed, `test_fact_equivalence.py .......` 7 passed). First run was `5 passed, 5 errors`; the 5 errors were the staging bug above, not a compile failure.

### 2. Confirm the installed engine's own option names (D-75)

test: `docker compose run --rm app tectonic --help`
expected: The help output contains `--only-cached` and `--untrusted`. If it does not, the argv in `app/latex/compile.py` is wrong and must be corrected, not the assertion relaxed.
why_human: The flag names are currently carried from the constants in `compile.py`; the installed binary has never been read in this environment.
result: PASSED — confirmed twice. The build log's `RUN tectonic --help` printed `-C, --only-cached` and `--untrusted`, and
`tests/latex/test_compile.py::test_the_offline_flag_is_the_one_the_installed_binary_documents`
now passes in-container, reading the binary's own help. The existing argv is correct; no change needed.

### 3. Bundle coverage per preamble package

test: `docker compose run --rm app tectonic -X bundle search <package>` for each of fontspec, geometry, tabularx, paracol, enumitem, titlesec, hyperref
expected: Each package is reported as held by the bundle (or the missing ones are added to the build-time prime and the image rebuilt).
why_human: Requires the pinned binary inside the image.
result: SUPERSEDED by item 1 — run inside the container it printed only the version/workspace notes and no package lines, which is inconclusive rather than negative (the offline container has no fetched bundle index) and is the wrong proof anyway: `bundle search` queries the full default bundle, not the primed cache. Item 1 is authoritative: the stand-in requests exactly these seven packages and compiled offline under `--only-cached` (10/10 passed). Not recorded as passed on an empty result.

### 4. Measure the TeX Live fallback (D-76) or leave it unclaimed

test: `docker build -f Dockerfile.texlive -t job-search-copilot:texlive .` then compile the fixture with `LATEX_ENGINE=texlive`
expected: Image size, build duration, compile argv and page count recorded in `docs/probes/2026-09-21-cv-tex-spike.md` §5 — or §5 stays "Not taken" and the fallback stays not-claimed (which is its current, honest state).
why_human: Building a second multi-GB image is a one-off operator action; the verdict correctly records the measurement as NOT TAKEN rather than implying it.
result: [pending] — optional by design. `LATEX_ENGINE` is a runtime env var, not a build arg; the build still needs its context path (`.`) as the final argument.

### 5. Take the real-document measurement that closes STATE blocking unknown #1

test: `mkdir -p cv artifacts`, place the real LaTeX CV at `cv/base.tex`, run `bash scripts/cv-tex-spike.sh`, then append the counts and unresolved names to `docs/probes/2026-09-21-cv-tex-spike.md` §4
expected: Sections/entries/bullets/lines counts, unresolved macro names with counts and lines, the truncation flag, and per-package bundle coverage are recorded — or the document stays PARTIAL and the blocking unknown stays open. Counts/names only; never CV text.
why_human: The real document is deliberately not in this repository (D-58); every current number measures the synthetic stand-in. SC-4 is satisfied only as scoped by D-62 (partial verdict + trigger), so the real decomposition remains unproven.
result: [pending] — deliberately deferred; the verdict doc is PARTIAL by design and carries the trigger command. STATE blocking unknown #1 stays OPEN until this runs.

### 6. Attest the package-legitimacy decision (04-01 D6)

test: confirm the human saw and approved `pypdf==6.19.0` (source https://github.com/py-pdf/pypdf, pure-Python wheel) and `pyyaml==6.0.3` before install
expected: The approval is genuine and predates the manifest edits; the recorded string `approved: pypdf=6.19.0 pyyaml=6.0.3` reflects a real human decision.
why_human: Legitimacy checkpoints are never auto-approvable; the gate is an out-of-band human signal that no test can verify.
result: PASSED — approve/reject checkpoint presented with read-only evidence (PyPI metadata, wheel type, source repo) and answered `approved: pypdf=6.19.0 pyyaml=6.0.3` before either manifest was edited.

## Summary

- total: 6
- passed: 3
- failed: 0
- superseded: 1 (item 3 — superseded by item 1)
- pending: 2 (items 4, 5 — both deferred by design)

Item 3 returned no result lines and is superseded by item 1, which is
authoritative because the stand-in requests exactly the seven preamble packages
and compiled offline under `--only-cached` (10/10 passed). Item 4 is optional and
may legitimately stay "Not taken". Item 5 depends on a document that is
deliberately absent from this repository and is the only item that is a real
external blocker, so STATE blocking unknown #1 stays open until it runs.

## Gaps

No blocking product gaps. Two defects found by this UAT are fixed, guarded and
committed (`0edde77`, `a8a5321`); the hermetic suite is now at **971 passed
(14 deselected)**.

The three code-review warnings that held verification at `human_needed` are
fixed, each shipping a regression test that failed before the fix:

| Finding | Fix commit | Regression test |
| --- | --- | --- |
| WR-01 `cv_repo.py` `is_current` cleared outside the SAVEPOINT | `6dabe66` | `tests/db/test_cv_repo.py::test_a_failed_insert_leaves_the_previous_revision_current` |
| WR-03 hard-coded `_HEALTH_TIMEOUT_SECONDS`/`_LOG_TAIL_CHARS` | `2665764` | `tests/test_config.py` ceiling + call-time tests |
| WR-02 slug-collision of distinct organisation names (+ IN-02 missing identity name) | `8711cbb` | `tests/cv/test_import_tex.py` collision + `unresolved_fields` tests |

Re-verification after those fixes returned `passed`, 29/29 must-haves.

Still open deliberately (recorded in `04-REVIEW.md` → "Left open deliberately"):
WR-04 (`_flatten` leaving a dangling backslash), IN-01, IN-03..IN-07, plus five
non-blocking companion-assertion gaps in `04-SECURITY.md`. None of these fail a
requirement.
