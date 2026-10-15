---
phase: "4"
slug: "cv-fact-store-latex-compile-spike"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
# PARTIAL, not compliant: the engine lane and the real-document decomposition are
# operator-only and cannot be automated in this environment (D-62/D-69/D-76).
nyquist_compliant: false
wave_0_complete: true
created: "2026-09-21"
validated: "2026-09-21"
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (already installed) |
| **Config file** | `pyproject.toml` (`addopts = "-m 'not live and not latex'"` — the hermetic pass excludes both the live and the engine lanes) |
| **Quick run command** | `.venv/bin/python -m pytest -q -m 'not live and not latex'` |
| **Full suite command** | `.venv/bin/python -m pytest -q -m 'not live and not latex'` |
| **Container PDF lane** | `docker compose run --rm app pytest -m latex` (D-69 — needs the primed Tectonic cache inside the image) |
| **New marker (plan 04-01)** | `latex: compiles LaTeX through the engine; requires the container image and a primed Tectonic cache — operator-run only, never in the hermetic default lane (D-69)` |
| **Estimated runtime** | ~60-90 seconds (hermetic) / +~30-60s for the in-container `latex` lane |
| **Measured runtime (audit, 2026-09-21)** | **166 s** hermetic (961 passed, 14 deselected) — see the sign-off note on the 120 s budget |

**Reconciliation note (planning, 2026-09-21).** The Per-Task Verification Map below is reconciled against the final five-plan set (`04-01` … `04-05`). The seeded rows in the original draft used a three-plan shape (`04-01-01` … `04-03-01`) that no longer exists, so every row here has been rewritten to name a real task. `validate-phase` remains the authority that flips `status` and sets `nyquist_compliant`.

**Audit note (2026-09-21).** Two tasks (`04-05-02`, `04-05-03`) had only ad-hoc shell one-liner verifies recorded in their PLAN `<verify>` blocks, not tests in the sampled suite. This audit wrapped those contracts in hermetic pytest files (`tests/test_cv_tex_spike_script.py`, `tests/test_cv_tex_spike_docs.py`) and added a lane-contract guard (`tests/test_latex_lane_contract.py`) for the collected-and-skipped claim. No application code, Dockerfile, manifest, planning state or existing test was changed.

---

## Sampling Rate

- **After every task commit:** `.venv/bin/python -m pytest -q -m 'not live and not latex'` (hermetic; no engine, no network)
- **After every plan wave:** `.venv/bin/python -m pytest -q -m 'not live and not latex'`
- **Before `/gsd-verify-work`:** the hermetic suite must be green, the `-m latex` lane must have run at least once in-container, and `docs/probes/2026-09-21-cv-tex-spike.md` must exist with its `PARTIAL` marker and its UNRESOLVED trigger
- **Max feedback latency:** 120 seconds (hermetic) — **currently exceeded at ~166 s**; recorded honestly rather than asserted, since the full hermetic suite is the sampling command. The container lane is operator-run and is not bound by this budget
- **Not sampled:** the live scraper lane (`-m live`) and any real-CV path. Both are operator-run and outside this phase's gate.

---

## Per-Task Verification Map

Reconciled against the final five-plan set. Every row names a task that exists in a PLAN.md.
Status vocabulary: ✅ green (runs in the hermetic lane) · ⚠️ operator (hermetic half green; the requirement itself needs the container/real document) · ⬜ exempt (human gate).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 04-01 | 1 | CV-01, CV-03, CV-05 | T-04-01, T-04-02, T-04-SC | No package is installed before a human approves the exact pin; legitimacy checkpoints are never auto-approvable | checkpoint (`gate="blocking-human"`) | *(none — a human gate has no automated command)* | n/a | ⬜ exempt |
| 04-01-02 | 04-01 | 1 | CV-01, CV-03, CV-05 | T-04-03, T-04-04 | Both manifests declare both pins identically; the `latex` lane is excluded from the hermetic pass | unit | `.venv/bin/python -m pytest -q tests/test_dependency_pins.py -x` | ✅ | ✅ green |
| 04-02-01 | 04-02 | 2 | CV-05 | T-04-05, T-04-06, T-04-07, T-04-08, T-04-09, T-04-10, T-04-12 | Fixed argv list; each engine carries its own code-execution control; the offline flag asserted; checksum verified in the same layer; bounded timeout; `to_thread` for PDF parsing | unit + tracer | hermetic half: `.venv/bin/python -m pytest -q tests/test_latex_engine_seam.py tests/test_latex_lane_contract.py -x`; operator half: `docker compose run --rm app pytest -m latex -k fixture_compiles -x` then `docker compose run --rm app tectonic --help` for D-75 | ✅ | ⚠️ operator |
| 04-02-02 | 04-02 | 2 | CV-05 | T-04-07, T-04-09 | The cache path is deterministic and identical between image and settings; the volume mounts and every env passthrough exist in all three surfaces | unit | `.venv/bin/python -m pytest -q tests/test_deploy_manifest.py -x` | ✅ | ✅ green |
| 04-02-03 | 04-02 | 2 | CV-05, PLAT-04 | T-04-11 | The engine actually used matches the configured engine — no silent substitution; `/health` reports the engine without ever raising | unit | `.venv/bin/python -m pytest -q tests/test_latex_engine_seam.py tests/api/test_health.py tests/test_config.py -x` | ✅ | ✅ green |
| 04-03-01 | 04-03 | 2 | CV-01, CV-04, CV-06 | T-04-16, T-04-17 | IDs derive from immutable identity only; the escaper is total and deterministic with the backslash first; the predicate is strict membership | unit | `.venv/bin/python -m pytest -q tests/domain -x` | ✅ | ✅ green |
| 04-03-02 | 04-03 | 2 | CV-01, CV-02 | T-04-14, T-04-15 | The safe YAML loader only; no default-filling; the real CV is structurally gitignored and proven by a guard | unit | `.venv/bin/python -m pytest -q tests/cv/test_factstore.py tests/test_cv_hygiene.py -x` | ✅ | ✅ green |
| 04-03-03 | 04-03 | 2 | CV-02, CV-03, CV-04, CV-06 | T-04-13, T-04-18, T-04-19, T-04-20 | One non-bypassable escape choke point with no escaping filter registered; byte-exact golden with a mutation control; no clock or randomness reachable from the render path | unit (golden) | `.venv/bin/python -m pytest -q tests/golden tests/test_render_determinism.py -x` | ✅ | ✅ green |
| 04-04-01 | 04-04 | 3 | CV-03, CV-06 | T-04-21, T-04-22 | Exact membership after normalisation with a fact-count floor; the mutation control must FAIL; a hostile bullet survives extraction | integration (`latex`) | hermetic lane-contract guard: `.venv/bin/python -m pytest -q tests/test_latex_lane_contract.py -x`; operator: `docker compose run --rm app pytest -m latex -x` | ✅ | ⚠️ operator |
| 04-04-02 | 04-04 | 3 | CV-01, CV-05 | T-04-23, T-04-24, T-04-25 | The schema version is stored as the string the column expects; the repository never commits; no synthetic artefact row | integration (DB) | `.venv/bin/python -m pytest -q tests/db/test_cv_repo.py tests/db/test_migration_contract.py -x` | ✅ | ✅ green |
| 04-05-01 | 04-05 | 4 | CV-01, CV-02 | T-04-27, T-04-30, T-04-31 | The parser reports rather than guesses; the document it read is byte-identical afterwards; both bounds report instead of raising | unit | `.venv/bin/python -m pytest -q tests/cv/test_import_tex.py -x` | ✅ | ✅ green |
| 04-05-02 | 04-05 | 4 | CV-05 | T-04-32 | One documented gate command shared by the runbook and the lane skip reasons; no automatic engine switch | unit (script + doc) | `.venv/bin/python -m pytest -q tests/test_cv_tex_spike_script.py tests/test_latex_lane_contract.py -x` | ✅ | ✅ green |
| 04-05-03 | 04-05 | 4 | CV-01, CV-05 | T-04-28, T-04-29 | The verdict claims only what it measured and separates the proven from the unresolved; no CV text or personal detail is committed | unit (doc) | `.venv/bin/python -m pytest -q tests/test_cv_tex_spike_docs.py -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky* (extended here with ⚠️ operator and ⬜ exempt as described above.)

*Task `04-01-01` is a `checkpoint:human-verify gate="blocking-human"` task: it legitimately has no `<automated>` command, and that is not a Nyquist gap — a human gate cannot be automated and is exempt by design.*

*Rows `04-02-01` and `04-04-01` are `⚠️ operator` deliberately: the hermetic half is green, but the requirement itself (a real offline compile and a fact-equivalence run over two compiled PDFs) lives in the container lane and is recorded UNRUN, not passed. Do not read this map as claiming those two are green.*

---

## Wave 0 Requirements

All items below exist and are committed (verified 2026-09-21 during this audit).

- [x] `tests/fixtures/cv/awesomecv_standin.tex` — the committed synthetic macro-heavy document (plan 04-02 T1; D-61). **Blocking for the container lane and for the build-time cache prime (D-74).**
- [x] `tests/fixtures/cv/awesomecv_standin.yaml` — its fixture fact store, mirroring the document (plan 04-03 T2; O4)
- [x] `tests/golden/base.rendered.tex` — the byte-exact baseline, generated once from a reviewed render and then committed (plan 04-03 T3; D-68)
- [x] `tests/golden/__init__.py`, `tests/cv/__init__.py`, `tests/latex/__init__.py` — the repo's test packages all carry `__init__.py`; keep the convention
- [x] `pyproject.toml` — the `latex` marker registered and `addopts` widened to `-m 'not live and not latex'` (plan 04-01 T2; D-69)
- [x] `pypdf` + `pyyaml` in BOTH `requirements.txt` and `pyproject.toml`, with `pyyaml` removed from the dev group (plan 04-01 T2; D-17)
- [x] `tests/test_import_discipline.py` subprocess carve-out widened for `app/latex`, with its mirror test (plan 04-02 T1; Pitfall 5)
- [x] `tests/test_config.py` — the new ceilings added to the guard lists and `app/latex`/`app/cv` added to the absence scan (plan 04-02 T3; PLAT-04)
- [x] `.gitignore` — `cv/` and `artifacts/` entries (plan 04-03 T2; D-58)
- [x] `.gitattributes` — line-ending pins for the golden and template paths (plan 04-03 T3; Pitfall 9)
- [x] `app/domain/tex.py`, `app/domain/cv.py` — the pure layer everything else imports (plan 04-03 T1)
- [x] `app/latex/base.py`, `app/latex/__init__.py`, `app/latex/compile.py`, `app/latex/env.py`, `app/latex/render.py`, `app/latex/templates/cv.tex.jinja` (plans 04-02, 04-03)
- [x] `app/cv/__init__.py`, `app/cv/factstore.py`, `app/cv/import_tex.py` (plans 04-03, 04-05)
- [x] `app/db/repositories/cv_repo.py` + `tests/db/test_cv_repo.py` (plan 04-04 T2)
- [x] `Dockerfile` Tectonic install and prime layers; `Dockerfile.texlive`; `compose.yml` volumes and passthroughs (plan 04-02 T1/T2)
- [x] No framework install is needed — `pytest` and `pytest-asyncio` are already pinned dev dependencies. The two new runtime pins needed the `checkpoint:human-verify` first (plan 04-01 T1).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-document decomposition verdict | CV-01, CV-02 | The real `.tex` is deliberately not in this repository (D-58) and the user has no document placed yet; this is STATE.md blocking unknown #1 and is unmeasurable by an automated test by design (D-62) | `mkdir -p cv artifacts`, place the real CV at `cv/base.tex`, run `bash scripts/cv-tex-spike.sh`, and record the counts plus the verdict in `docs/probes/2026-09-21-cv-tex-spike.md`. Counts and names only — never CV text. |
| TeX Live fallback proven once | CV-05 | Building a second, multi-gigabyte image is a one-off operator action, not a CI lane (D-76) | `docker build -f Dockerfile.texlive -t job-search-copilot:texlive .` then compile the committed fixture through it with `LATEX_ENGINE=texlive`; record the image size, build duration, argv and resulting page count in the verdict document — or record explicitly that the measurement has not been taken, in which case the fallback is not claimed as available |
| Tectonic bundle coverage for the real preamble | CV-05 | The preamble is unknown until the real document exists (D-62; research assumptions A1/A2) | Run the engine's bundle-search command once per preamble package; record which packages the bundle holds in the verdict document's UNRESOLVED section |
| The cached-only flag confirmed against the installed binary | CV-05 | D-75 requires verification against `tectonic --help` at implementation time; documentation alone is not accepted, and the engine exists only inside the image | `docker compose run --rm app tectonic --help`; record the flag and the untrusted-mode option it names, then confirm the engine's argv passes exactly those. A difference is an argv defect to fix — never an assertion to relax |
| The TeX Live argv's own code-execution control | CV-05 | The fallback engine is a separate image with a separate flag vocabulary; `--untrusted` is a Tectonic option and means nothing to `xelatex` | The argv unit assertion covers `-no-shell-escape`; the one-off fallback build records the image's own configuration alongside its size, duration and page count |
| Font-resolution form accepted by the engine | CV-05 | Tectonic resolves fonts by filename rather than symbolic name, and the 0.17.0 behaviour on Linux is unmeasured (research assumptions A3/A4) | The fixture carries both declaration forms with the by-name one commented; compile each once in the image and record which form the engine accepted in the verdict document |
| Container lane run | CV-03, CV-05, CV-06 | The engine lives only inside the image and Docker is not observable from the planning environment (D-69) | `docker compose build app && docker compose run --rm app pytest -m latex`; a lane reporting zero passed tests was skipped, not verified |

The four operator-only checks above that cannot run in this environment remain **UNRUN** and are not faked: `docker compose run --rm app pytest -m latex`; `docker compose run --rm app tectonic --help`; `docker compose run --rm app tectonic -X bundle search <package>`; `docker build -f Dockerfile.texlive ...`.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (or are an exempt human gate)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (all present and committed)
- [x] No watch-mode flags
- [ ] Feedback latency < 120s — **measured ~166 s**; left unchecked rather than asserted. The suite is the sampling command, so this budget is currently exceeded; reducing it is a future task, not a validation gap
- [ ] `nyquist_compliant: true` set in frontmatter — **not set**: the engine lane and the real-document decomposition are operator-only (see Manual-Only)

**Approval:** validated 2026-09-21 — PARTIAL (automated hermetic coverage complete; operator-only items remain)

---

## Validation Audit 2026-09-21

| Metric | Count |
|--------|-------|
| Gaps found | 2 |
| Resolved | 2 |
| Escalated | 0 |

**Gaps filled**

| Task ID | Requirement | Gap | Test file | Command |
|---------|-------------|-----|-----------|---------|
| 04-05-02 | CV-05 | The spike script's contract (`bash -n`, `--dry-run` names a review draft that is not `cv.yaml`, missing source exits 3, unknown option exits 2, a real run writes a draft that loads through the fact store and leaves the source byte-identical) existed only as ad-hoc shell one-liners | `tests/test_cv_tex_spike_script.py` | `.venv/bin/python -m pytest -q tests/test_cv_tex_spike_script.py -x` |
| 04-05-03 | CV-01, CV-05 | The committed verdict/runbook/README invariants (exactly one `PARTIAL` marker, trigger command + `cv/base.tex` named, no email/phone shape, no fixture content, fallback measured-or-declared-unmeasured, the one gate command shared with the lane skip reasons) existed only as ad-hoc shell one-liners | `tests/test_cv_tex_spike_docs.py` | `.venv/bin/python -m pytest -q tests/test_cv_tex_spike_docs.py -x` |

**Additional hermetic guard added (no gap row, honesty control)**

| Concern | Test file | Command |
|---------|-----------|---------|
| D-69's collected-and-skipped (never deselected) claim: the default lane deselects the `latex` nodes, and an explicit `-m latex` collects them | `tests/test_latex_lane_contract.py` | `.venv/bin/python -m pytest -q tests/test_latex_lane_contract.py -x` |

**Adversarial controls run**

- Mutation control 1: `**Status:** PARTIAL` temporarily changed to `FINAL` → `test_the_verdict_carries_exactly_one_status_marker_and_it_is_partial` **failed**, then the document was restored via `git checkout`.
- Mutation control 2: the script's missing-source `exit 3` temporarily changed to `exit 4` → `test_a_missing_source_exits_3_and_names_the_path` **failed**, then the script was restored via `git checkout`.
- The lane-contract test failed for real on its first run (pytest exits 5 when every node is deselected at collection); the assertion was corrected, not the implementation.

**Audit observation (reported, not fixed — outside this audit's write scope)**

`app/domain/tex.py::sanitise_preamble` has **no production caller**: its only references are `tests/domain/test_tex_preamble.py`. The committed verdict's §6 states "the codebase's answer is preamble sanitisation", but nothing on the compile path invokes it. This does not fail any per-task requirement (plan 04-03 Task 1 required the pure function and its tests, both present), so it is recorded as an observation rather than an escalation. If the intent is for the compile path to sanitise a human preamble before handing it to the engine, that wiring is a future task.

---

## Hermetic suite result (audit)

```
$ .venv/bin/python -m pytest -q
961 passed, 14 deselected in 166.44s
```

Baseline before this audit: `945 passed, 14 deselected`. The 16 added tests are the three files listed above. The `latex` lane remains collected-and-skipped (10 nodes) on this dry host; it is not counted as a pass.
