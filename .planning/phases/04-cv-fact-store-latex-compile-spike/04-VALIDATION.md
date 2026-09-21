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
| **Framework** | pytest + pytest-asyncio (already installed) |
| **Config file** | `pyproject.toml` (`addopts = "-m 'not live'"` — hermetic pass excludes live/marked lanes) |
| **Quick run command** | `.venv/bin/python -m pytest -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` |
| **Container PDF lane** | `docker compose run --rm app pytest -m latex` (D-69 — needs Tectonic inside the image) |
| **Estimated runtime** | ~60 seconds (hermetic) / +~30s for the in-container `latex` lane |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green; the `-m latex` lane must have run at least once in-container
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | CV-01 | — | N/A | unit | `.venv/bin/python -m pytest -q` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | CV-02 | T-4-01 | Tool never writes `cv/base.tex` | unit | `.venv/bin/python -m pytest -q` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | CV-04 | — | N/A | unit | `.venv/bin/python -m pytest -q` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 1 | CV-06 | T-4-02 | Escaping closes the LaTeX-injection path | unit | `.venv/bin/python -m pytest -q` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | CV-03 | — | N/A | unit (golden) | `.venv/bin/python -m pytest -q` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | CV-03 | — | N/A | integration (marked) | `docker compose run --rm app pytest -m latex` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 2 | CV-05 | T-4-03 | No `-Z shell-escape`; `--untrusted` enforced | integration (marked) | `docker compose run --rm app pytest -m latex` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Rows above are a seed derived from the REQUIREMENTS CV-01..CV-06 mapping and are authoritative only after `validate-phase` reconciles them against the final PLAN.md task IDs.*

---

## Wave 0 Requirements

- [ ] `tests/golden/` — directory does not exist yet; created by D-68's golden/test fixtures
- [ ] `tests/fixtures/cv/` — committed synthetic `.tex` fixture + fixture fact store (D-58/D-61)
- [ ] `pyyaml` + `pypdf` added to BOTH `requirements.txt` and `pyproject.toml` (mirrored per D-17)
- [ ] `latex` pytest marker registered in `pyproject.toml` (D-69) with skip-if-`tectonic`-absent guard
- [ ] `tests/test_import_discipline.py` subprocess carve-out widened for `app/latex` (mirror-test pattern)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-CV decomposition verdict | CV-01, CV-04 | The user has no `.tex` yet; the real document is unavailable to automated tests by design (D-61/D-62) | Run the spike script against `cv/base.tex`, record counts + verdict in `docs/probes/2026-09-21-cv-tex-spike.md` |
| TeX Live fallback proven once | CV-05 | Building a second image is a one-off operator action, not a CI lane (D-76) | `docker build -f Dockerfile.texlive .` then compile the fixture through it; record the result in the verdict doc |
| Tectonic bundle coverage for the real preamble | CV-05 | Same reason as the decomposition verdict (D-62) | Run `tectonic -X bundle search <pkg>` for each preamble package; record in the verdict doc's UNRESOLVED section |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
