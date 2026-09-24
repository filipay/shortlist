---
phase: "6"
slug: "tailoring-verification"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-24"
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded by plan-phase from `06-RESEARCH.md` §Validation Architecture. Per-task rows are
> filled by `/gsd-validate-phase` once plans exist.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/python -m pytest tests/verify tests/domain -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` (default lane; `addopts = "-m 'not live and not latex'"`) |
| **Engine lane** | `.venv/bin/python -m pytest -m latex` (container only, D-69) |
| **Estimated runtime** | ~5–20 seconds (hermetic lane; no engine, no server) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/verify tests/domain -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green; `pytest -m latex` run explicitly in the container for the compile integration
- **Max feedback latency:** ~20 seconds (hermetic); engine lane is not on the sampling path

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | TAIL-01 | T-06-01 | Listing text only in `parts`; ids-only return | integration (stub LLM) | `.venv/bin/python -m pytest tests/api/test_tailoring_generate.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TAIL-02 | T-06-02 | Typed patch; no free-text on the PDF path | unit | `.venv/bin/python -m pytest tests/domain/test_patch_ops.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TAIL-03 | T-06-03 | Bullet text immutable; canary never reaches `.tex` | unit | `.venv/bin/python -m pytest tests/verify/test_no_free_text_path.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TAIL-04 | T-06-04 | All 10 checks, both layers, block semantics | unit (fixtures) | `.venv/bin/python -m pytest tests/verify/ -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TAIL-05 | T-06-05 | Blocked artifact never downloadable (repo + route) | unit + route | `.venv/bin/python -m pytest tests/api/test_cv_artifact_blocked.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TAIL-06 | T-06-06 | No repair path; fail ⇒ blocked row | unit | `.venv/bin/python -m pytest tests/verify/test_block_no_repair.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TAIL-07 | — | Review page shows preview + change log before compile | route | `.venv/bin/python -m pytest tests/api/test_tailoring_review.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TAIL-08 | — | Drops listed with a reason | unit | `.venv/bin/python -m pytest tests/domain/test_patch_ops.py::test_drop_reason -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | UI-05 | T-06-07 | PDF preview inline + `?download=1`; 404 on blocked | route | `.venv/bin/python -m pytest tests/api/test_cv_pdf_route.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/verify/fixtures.py` — the `(facts, plan, patch, text, expected)` builder (PITFALLS P13)
- [ ] `tests/fixtures/verify/*.txt` — committed extracted-text samples (pass + one per fail)
- [ ] `tests/verify/test_plan_checks.py` / `test_text_checks.py` / `test_numbers.py` / `test_grounding.py`
- [ ] `tests/domain/test_patch_ops.py` — real `apply_patch` semantics (replacing `tests/domain/test_cv_ids.py:185-225`)
- [ ] `tests/api/test_cv_artifact_blocked.py` — the P14 blocked-artifact negative test
- [ ] `tests/api/test_cv_pdf_route.py` — inline vs `?download=1`, 404 on blocked
- [ ] `tests/api/test_tailoring_generate.py` / `test_tailoring_review.py` — with a stub LLM
- [ ] `tests/verify/test_no_free_text_path.py` — the canary test (TAIL-02/03)
- [ ] No framework install needed — pytest + pytest-asyncio are present

*The hermetic lane needs neither a LaTeX engine nor an opencode server: the verifier consumes fixtures, and the LLM is stubbed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tectonic compile of a tailored plan | TAIL-04/TAIL-07 | Tectonic is absent from the dry host by design (D-69) | In the container: generate + compile a listing with a stored score; confirm a PDF and a passing `verification_json` |
| Real opencode structured-output contract | TAIL-01 | No server in the default lane | Run the `/doc` contract test against the pinned opencode image; confirm `format`/`outputFormat` field name |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
