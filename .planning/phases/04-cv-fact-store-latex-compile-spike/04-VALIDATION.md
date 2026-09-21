---
phase: "4"
slug: "cv-fact-store-latex-compile-spike"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-21"
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

**Reconciliation note (planning, 2026-09-21).** The Per-Task Verification Map below is reconciled against the final five-plan set (`04-01` … `04-05`). The seeded rows in the original draft used a three-plan shape (`04-01-01` … `04-03-01`) that no longer exists, so every row here has been rewritten to name a real task. `validate-phase` remains the authority that flips `status` and sets `nyquist_compliant`.

---

## Sampling Rate

- **After every task commit:** `.venv/bin/python -m pytest -q -m 'not live and not latex'` (hermetic; no engine, no network)
- **After every plan wave:** `.venv/bin/python -m pytest -q -m 'not live and not latex'`
- **Before `/gsd-verify-work`:** the hermetic suite must be green, the `-m latex` lane must have run at least once in-container, and `docs/probes/2026-09-21-cv-tex-spike.md` must exist with its `PARTIAL` marker and its UNRESOLVED trigger
- **Max feedback latency:** 120 seconds (hermetic); the container lane is operator-run and is not bound by this budget
- **Not sampled:** the live scraper lane (`-m live`) and any real-CV path. Both are operator-run and outside this phase's gate.

---

## Per-Task Verification Map

Reconciled against the final five-plan set. Every row names a task that exists in a PLAN.md.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 04-01 | 1 | CV-01, CV-03, CV-05 | T-04-01, T-04-02, T-04-SC | No package is installed before a human approves the exact pin; legitimacy checkpoints are never auto-approvable | checkpoint (`gate="blocking-human"`) | *(none — a human gate has no automated command)* | ❌ W0 | ⬜ pending |
| 04-01-02 | 04-01 | 1 | CV-01, CV-03, CV-05 | T-04-03, T-04-04 | Both manifests declare both pins identically; the `latex` lane is excluded from the hermetic pass | unit | `.venv/bin/python -m pytest -q tests/test_dependency_pins.py -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 04-02 | 2 | CV-05 | T-04-05, T-04-06, T-04-07, T-04-08, T-04-09, T-04-10, T-04-12 | Fixed argv list; `--untrusted` on every compile; the unstable code-execution option never enabled; the offline flag asserted; checksum verified in the same layer; bounded timeout; `to_thread` for PDF parsing | unit + tracer | `.venv/bin/python -m pytest -q tests/latex -x -rs` then, in the image, `docker compose run --rm app pytest -m latex -k fixture_compiles -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 04-02 | 2 | CV-05 | T-04-07, T-04-09 | The cache path is deterministic and identical between image and settings; the volume mounts and every env passthrough exist in all three surfaces | unit | `.venv/bin/python -m pytest -q tests/test_deploy_manifest.py -x` | ❌ W0 | ⬜ pending |
| 04-02-03 | 04-02 | 2 | CV-05, PLAT-04 | T-04-11 | The engine actually used matches the configured engine — no silent substitution; `/health` reports the engine without ever raising | unit | `.venv/bin/python -m pytest -q tests/test_latex_engine_seam.py tests/api/test_health.py tests/test_config.py -x` | ❌ W0 | ⬜ pending |
| 04-03-01 | 04-03 | 2 | CV-01, CV-04, CV-06 | T-04-16, T-04-17 | IDs derive from immutable identity only; the escaper is total and deterministic with the backslash first; the predicate is strict membership | unit | `.venv/bin/python -m pytest -q tests/domain -x` | ❌ W0 | ⬜ pending |
| 04-03-02 | 04-03 | 2 | CV-01, CV-02 | T-04-14, T-04-15 | The safe YAML loader only; no default-filling; the real CV is structurally gitignored and proven by a guard | unit | `.venv/bin/python -m pytest -q tests/cv/test_factstore.py tests/test_cv_hygiene.py -x` | ❌ W0 | ⬜ pending |
| 04-03-03 | 04-03 | 2 | CV-02, CV-03, CV-04, CV-06 | T-04-13, T-04-18, T-04-19, T-04-20 | One non-bypassable escape choke point with no escaping filter registered; byte-exact golden with a mutation control; no clock or randomness reachable from the render path | unit (golden) | `.venv/bin/python -m pytest -q tests/golden tests/test_render_determinism.py -x` | ❌ W0 | ⬜ pending |
| 04-04-01 | 04-04 | 3 | CV-03, CV-06 | T-04-21, T-04-22 | Exact membership after normalisation with a fact-count floor; the mutation control must FAIL; a hostile bullet survives extraction | integration (`latex`) | `docker compose run --rm app pytest -m latex -x` | ❌ W0 | ⬜ pending |
| 04-04-02 | 04-04 | 3 | CV-01, CV-05 | T-04-23, T-04-24, T-04-25 | The schema version is stored as the string the column expects; the repository never commits; no synthetic artefact row | integration (DB) | `.venv/bin/python -m pytest -q tests/db/test_cv_repo.py tests/db/test_migration_contract.py -x` | ❌ W0 | ⬜ pending |
| 04-05-01 | 04-05 | 4 | CV-01, CV-02 | T-04-27, T-04-30, T-04-31 | The parser reports rather than guesses; the document it read is byte-identical afterwards; both bounds report instead of raising | unit | `.venv/bin/python -m pytest -q tests/cv/test_import_tex.py -x` | ❌ W0 | ⬜ pending |
| 04-05-02 | 04-05 | 4 | CV-05 | T-04-32 | One documented gate command shared by the runbook and the lane skip reasons; no automatic engine switch | unit (script + doc) | `bash -n scripts/cv-tex-spike.sh && bash scripts/cv-tex-spike.sh --dry-run` | ❌ W0 | ⬜ pending |
| 04-05-03 | 04-05 | 4 | CV-01, CV-05 | T-04-28, T-04-29 | The verdict claims only what it measured and separates the proven from the unresolved; no CV text or personal detail is committed | unit (doc) | `.venv/bin/python -m pytest -q -m 'not live and not latex'` plus the document-shape assertions in plan 04-05 Task 3's `<verify>` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Task `04-01-01` is a `checkpoint:human-verify gate="blocking-human"` task: it legitimately has no `<automated>` command, and that is not a Nyquist gap — a human gate cannot be automated and is exempt by design.*

---

## Wave 0 Requirements

Every item below is created by a task in this phase; none exists today (verified: a repo-wide grep for the CV fact-store and LaTeX renderer symbols returned zero matches).

- [ ] `tests/fixtures/cv/awesomecv_standin.tex` — the committed synthetic macro-heavy document (plan 04-02 T1; D-61). **Blocking for the container lane and for the build-time cache prime (D-74).**
- [ ] `tests/fixtures/cv/awesomecv_standin.yaml` — its fixture fact store, mirroring the document (plan 04-03 T2; O4)
- [ ] `tests/golden/base.rendered.tex` — the byte-exact baseline, generated once from a reviewed render and then committed (plan 04-03 T3; D-68)
- [ ] `tests/golden/__init__.py`, `tests/cv/__init__.py`, `tests/latex/__init__.py` — the repo's test packages all carry `__init__.py`; keep the convention
- [ ] `pyproject.toml` — the `latex` marker registered and `addopts` widened to `-m 'not live and not latex'` (plan 04-01 T2; D-69)
- [ ] `pypdf` + `pyyaml` in BOTH `requirements.txt` and `pyproject.toml`, with `pyyaml` removed from the dev group (plan 04-01 T2; D-17)
- [ ] `tests/test_import_discipline.py` subprocess carve-out widened for `app/latex`, with its mirror test (plan 04-02 T1; Pitfall 5)
- [ ] `tests/test_config.py` — the new ceilings added to the guard lists and `app/latex`/`app/cv` added to the absence scan (plan 04-02 T3; PLAT-04)
- [ ] `.gitignore` — `cv/` and `artifacts/` entries (plan 04-03 T2; D-58)
- [ ] `.gitattributes` — line-ending pins for the golden and template paths (plan 04-03 T3; Pitfall 9)
- [ ] `app/domain/tex.py`, `app/domain/cv.py` — the pure layer everything else imports (plan 04-03 T1)
- [ ] `app/latex/base.py`, `app/latex/__init__.py`, `app/latex/compile.py`, `app/latex/env.py`, `app/latex/render.py`, `app/latex/templates/cv.tex.jinja` (plans 04-02, 04-03)
- [ ] `app/cv/__init__.py`, `app/cv/factstore.py`, `app/cv/import_tex.py` (plans 04-03, 04-05)
- [ ] `app/db/repositories/cv_repo.py` + `tests/db/test_cv_repo.py` (plan 04-04 T2)
- [ ] `Dockerfile` Tectonic install and prime layers; `Dockerfile.texlive`; `compose.yml` volumes and passthroughs (plan 04-02 T1/T2)
- [ ] No framework install is needed — `pytest` and `pytest-asyncio` are already pinned dev dependencies. The two new runtime pins need the `checkpoint:human-verify` first (plan 04-01 T1).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-document decomposition verdict | CV-01, CV-02 | The real `.tex` is deliberately not in this repository (D-58) and the user has no document placed yet; this is STATE.md blocking unknown #1 and is unmeasurable by an automated test by design (D-62) | `mkdir -p cv artifacts`, place the real CV at `cv/base.tex`, run `bash scripts/cv-tex-spike.sh`, and record the counts plus the verdict in `docs/probes/2026-09-21-cv-tex-spike.md`. Counts and names only — never CV text. |
| TeX Live fallback proven once | CV-05 | Building a second, multi-gigabyte image is a one-off operator action, not a CI lane (D-76) | `docker build -f Dockerfile.texlive -t job-search-copilot:texlive .` then compile the committed fixture through it with `LATEX_ENGINE=texlive`; record the image size, build duration, argv and resulting page count in the verdict document — or record explicitly that the measurement has not been taken, in which case the fallback is not claimed as available |
| Tectonic bundle coverage for the real preamble | CV-05 | The preamble is unknown until the real document exists (D-62; research assumptions A1/A2) | Run the engine's bundle-search command once per preamble package; record which packages the bundle holds in the verdict document's UNRESOLVED section |
| Font-resolution form accepted by the engine | CV-05 | Tectonic resolves fonts by filename rather than symbolic name, and the 0.17.0 behaviour on Linux is unmeasured (research assumptions A3/A4) | The fixture carries both declaration forms with the by-name one commented; compile each once in the image and record which form the engine accepted in the verdict document |
| Container lane run | CV-03, CV-05, CV-06 | The engine lives only inside the image and Docker is not observable from the planning environment (D-69) | `docker compose build app && docker compose run --rm app pytest -m latex`; a lane reporting zero passed tests was skipped, not verified |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
