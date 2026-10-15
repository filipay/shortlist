---
phase: "6"
slug: "tailoring-verification"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
# Requirement-level automated coverage is complete (22/22 task rows green, 9/9 requirements).
# nyquist_compliant is false because the adversarial audit surfaced escalated findings that are
# not covered by a passing test: ESC-06-A (CR-02 residual region mis-anchor, critical) and
# ESC-06-B (silent region skip, warning). Both are independently corroborated by 06-REVIEW.md
# 2026-09-25. See "Escalated Findings" below. #2117 PARTIAL = validated + nyquist_compliant: false.
nyquist_compliant: false
wave_0_complete: true
created: "2026-09-24"
validated: "2026-09-25"
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded by plan-phase from `06-RESEARCH.md` §Validation Architecture; this file was audited
> and the per-task map filled by `/gsd-validate-phase` on 2026-09-25 (State A).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/python -m pytest tests/verify tests/domain -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` (default lane; `addopts = "-m 'not live and not latex'"`) |
| **Phase suite command** | `.venv/bin/python -m pytest tests/verify tests/domain/test_patch_ops.py tests/api/test_tailoring_generate.py tests/api/test_tailoring_review.py tests/api/test_cv_artifact_blocked.py tests/api/test_cv_pdf_route.py tests/pipeline/test_tailor_stage.py tests/db/test_cv_artifact_repo.py -q` (138 tests, ~32 s) |
| **Engine lane** | `.venv/bin/python -m pytest -m latex` (container only, D-69) |
| **Estimated runtime** | ~32 s (phase suite, hermetic); ~360 s (full lane); no engine, no server |

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
| 06-01-01 | 01 | 1 | TAIL-02, TAIL-03 | T-06-02 | All-or-nothing typed patch over enumerated ids; `Bullet.text` byte-immutable | unit | `.venv/bin/python -m pytest tests/domain/test_patch_ops.py -q` | ✅ | ✅ green |
| 06-01-02 | 01 | 1 | TAIL-01 | T-06-01 | Listing text and CV prose only in `parts`; frozen `system`; ids-only return; one call/one audit row; O1 purpose-aware 24h read | unit | `.venv/bin/python -m pytest tests/pipeline/test_tailor_stage.py -q` | ✅ | ✅ green |
| 06-01-03 | 01 | 1 | TAIL-01, TAIL-02 | T-06-04, T-06-07 | Layer-1 checks; artifact persistence; page/route; redacted verdicts | unit + integration | `.venv/bin/python -m pytest tests/verify/test_plan_checks.py tests/api/test_tailoring_generate.py -q` | ✅ | ✅ green |
| 06-02-01 | 02 | 2 | TAIL-04 | T-06-08, T-06-09 | Ten checks as eleven results; tokeniser; region-scoped metric containment; injection residue blocks | unit | `.venv/bin/python -m pytest tests/verify/test_numbers.py tests/verify/test_text_checks.py -q` | ✅ | ✅ green |
| 06-02-02 | 02 | 2 | TAIL-04 | T-06-10 | Advisory grounding band can never flip `passed` (A1/D-70) | unit | `.venv/bin/python -m pytest tests/verify/test_grounding.py -q` | ✅ | ✅ green |
| 06-02-03 | 02 | 2 | TAIL-06, TAIL-02 | T-06-11 | Block-don't-repair; no canary/reason/requirement reaches the rendered `.tex` | unit | `.venv/bin/python -m pytest tests/verify/test_block_no_repair.py tests/verify/test_no_free_text_path.py -q` | ✅ | ✅ green |
| 06-03-01 | 03 | 2 | TAIL-07 | T-06-13, T-06-15 | Dedicated page + five-state vocabulary; detail-page link; no control on unscored | route | `.venv/bin/python -m pytest tests/api/test_tailoring_review.py -q` | ✅ | ✅ green |
| 06-03-02 | 03 | 2 | TAIL-07, TAIL-08 | T-06-16 | Preview beside change log; dropped/demoted bullets struck with reasons; no `\|safe` | route | `.venv/bin/python -m pytest tests/api/test_tailoring_review.py -q` | ✅ | ✅ green |
| 06-03-03 | 03 | 2 | TAIL-07 | T-06-14 | Stale-patch 409: recomputed `facts_hash` + fresh `current_version`; no artifact, no retry | route | `.venv/bin/python -m pytest tests/api/test_tailoring_review.py::test_a_stale_fact_store_refuses_the_compile_and_writes_no_row -q` | ✅ | ✅ green |
| 06-04-01 | 04 | 3 | TAIL-05 | T-06-18 | `compile_status == "ok"` predicate applied in SQL on both accessors | unit | `.venv/bin/python -m pytest tests/db/test_cv_artifact_repo.py -q` | ✅ | ✅ green |
| 06-04-02 | 04 | 3 | UI-05 | T-06-19 | Inline vs `?download=1`; path built from integer ids; 404 on non-`ok`/absent; path-like query ignored | route | `.venv/bin/python -m pytest tests/api/test_cv_pdf_route.py -q` | ✅ | ✅ green |
| 06-04-03 | 04 | 3 | TAIL-05 | T-06-18, T-06-20, T-06-21 | Blocked/failed findings visible but never downloadable; history retained | route | `.venv/bin/python -m pytest tests/api/test_cv_artifact_blocked.py -q` | ✅ | ✅ green |
| 06-05-01 | 05 | 1 | TAIL-04 | T-06-23, T-06-24 | Region-LOCAL date/page/structured exclusion (no document-wide union); novel metric still fails | unit | `.venv/bin/python -m pytest tests/verify/test_numbers.py -q` | ✅ | ✅ green |
| 06-05-02 | 05 | 1 | TAIL-04 | T-06-23, T-06-25, T-06-26 | Committed digit-skill extraction passes; `VERIFIER_VERSION` 1.0.1 provenance; `offending` ids+cores only | unit | `.venv/bin/python -m pytest tests/verify/test_numbers.py tests/verify/test_text_checks.py -q` | ✅ | ✅ green |
| 06-06-01 | 06 | 1 | TAIL-08 | T-06-27, T-06-28 | Op ids grounded per family at the validation boundary; non-family id raises before `_build_plan` | unit | `.venv/bin/python -m pytest tests/domain/test_patch_ops.py -q` | ✅ | ✅ green |
| 06-06-02 | 06 | 1 | TAIL-08 | T-06-27 | Change-log honesty: every `ChangeRecord` names a real source fact at the right locus | unit | `.venv/bin/python -m pytest tests/domain/test_patch_ops.py::test_every_change_record_describes_an_effect_at_the_right_locus -q` | ✅ | ✅ green |
| 06-07-01 | 07 | 1 | TAIL-01 | T-06-30, T-06-31, T-06-32 | Compile route honours `tailoring_enabled=False` with 409 before any read/render/engine/insert; escaped refusal | route | `.venv/bin/python -m pytest tests/api/test_tailoring_review.py::test_the_compile_route_refuses_when_tailoring_is_disabled -q` | ✅ | ✅ green |
| 06-07-02 | 07 | 1 | TAIL-01, UI-05 | T-06-30 | Off switch is live both directions; `GET .../cv/pdf` deliberately ungated | route | `.venv/bin/python -m pytest tests/api/test_tailoring_review.py -q` | ✅ | ✅ green |
| 06-08-01 | 08 | 1 | TAIL-04 | T-06-34, T-06-36 | Location digit core folded into the entry's OWN `allowed` set; digit-bearing location passes check 4 | unit | `.venv/bin/python -m pytest tests/verify/test_numbers.py::test_a_digit_bearing_location_is_not_a_surplus_candidate -q` | ✅ | ✅ green |
| 06-08-02 | 08 | 1 | TAIL-04 | T-06-35, T-06-37 | Region anchored on the org-AND-title header line; split header reported `found=False`; `VERIFIER_VERSION` 1.0.2 | unit | `.venv/bin/python -m pytest tests/verify/test_numbers.py::test_a_bullet_naming_a_later_employer_does_not_bleed_into_its_region -q` | ✅ | ✅ green |
| 06-09-01 | 09 | 1 | TAIL-02 | T-06-39, T-06-41 | Raised transport error → one `purpose=tailor status=error` row + typed 502, never a 500 | integration | `.venv/bin/python -m pytest tests/api/test_tailoring_generate.py::test_generate_returns_a_typed_error_and_one_audit_row_when_the_backend_raises -q` | ✅ | ✅ green |
| 06-09-02 | 09 | 1 | TAIL-02 | T-06-40, T-06-42 | Pipeline returns `None` on raise; class-only `error`; shared in-flight slot released | unit | `.venv/bin/python -m pytest tests/pipeline/test_tailor_stage.py::test_a_raised_backend_error_still_writes_one_tailor_row_and_returns_none -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Audited 2026-09-25:** 138/138 phase-suite tests pass (`tests/verify`, `tests/domain/test_patch_ops.py`, the four tailoring API files, `tests/pipeline/test_tailor_stage.py`, `tests/db/test_cv_artifact_repo.py`). The full hermetic lane is 1238 passed / 14 deselected / 2 xfailed.

---

## Wave 0 Requirements

- [x] `tests/verify/fixtures.py` — the `(facts, plan, patch, text, expected)` builder (PITFALLS P13)
- [x] `tests/fixtures/verify/*.txt` — committed extracted-text samples (base pass + one per fail/warn: `missing_entity`, `novel_metric`, `injection_residue`, `reworded_verbatim`, `three_page`, `missing_heading`, `digit_skill`, `digit_location`)
- [x] `tests/verify/test_plan_checks.py` / `test_text_checks.py` / `test_numbers.py` / `test_grounding.py`
- [x] `tests/domain/test_patch_ops.py` — real `apply_patch` semantics (replacing `tests/domain/test_cv_ids.py:185-225`)
- [x] `tests/api/test_cv_artifact_blocked.py` — the P14 blocked-artifact negative test
- [x] `tests/api/test_cv_pdf_route.py` — inline vs `?download=1`, 404 on blocked
- [x] `tests/api/test_tailoring_generate.py` / `test_tailoring_review.py` — with a stub LLM
- [x] `tests/verify/test_no_free_text_path.py` — the canary test (TAIL-02/03)
- [x] No framework install needed — pytest + pytest-asyncio are present

*The hermetic lane needs neither a LaTeX engine nor an opencode server: the verifier consumes fixtures, and the LLM is stubbed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tectonic compile of a tailored plan | TAIL-04/TAIL-07 | Tectonic is absent from the dry host by design (D-69) | In the container: generate + compile a listing with a stored score; confirm a PDF and a passing `verification_json` |
| Real opencode structured-output contract | TAIL-01 | No server in the default lane | Run the `/doc` contract test against the pinned opencode image; confirm `format`/`outputFormat` field name |
| ESC-06-A: region mis-anchor when an earlier bullet contains a later entry's org AND title | TAIL-04 | Implementation defect (ESCALATED 2026-09-25; independently re-raised as CR-01 in `06-REVIEW.md` 2026-09-25) — no passing test exists; the fix is an implementation change owned by the developer, not the auditor | Repro in "Escalated Findings" below; after a fix, add it as a regression test in `tests/verify/test_numbers.py` and delete this row |
| ESC-06-B: check 4 silently skips a region it cannot anchor (empty/ wrapped org+title), so a fabricated digit there is never caught | TAIL-04 | Coverage gap (ESCALATED 2026-09-25; independently raised as WR-01 in `06-REVIEW.md` 2026-09-25) | Repro in "Escalated Findings" below; after a fix, assert the skip is a visible `warn` or a collision-resistant anchor in `tests/verify/test_text_checks.py` |

*All other phase behaviors have automated verification.*

---

## Escalated Findings (adversarial audit 2026-09-25)

### ESC-06-A — CR-02 residual: a bullet containing a later entry's org **and** title still mis-anchors the region (high)

**Class:** the same defect class 06-08 closed for org-only bleed (T-06-35 / T-06-36):
a blocking check hard-fails a valid CV and the only recovery (a fresh tailor) re-runs the
same predicate, so preview and download are dead.

**Implementation:** `app/verify/numbers.py:120-160` (`_entry_lines`). The anchor is
`org_needle in line and title_needle in line`. A bullet that contains both the later
entry's org and its (squashed) title — e.g. "Mentored the Acme Analyst team of 5" for
entry B (`Acme` / `Analyst`) — still starts B's region one line early, so the earlier
entry's digit bleeds into B's region as a surplus candidate. T-06-35's stated mitigation
("a bullet mentioning a later employer cannot start that employer's region and cannot
donate its digits") is therefore incomplete.

**Reproduced (fails):**

```python
entry_a = RenderedEntry(id="exp/acme-2018", org="Acme", title="Engineer",
    dates="2018-01 -- 2018-12",
    bullets=[Bullet(id="bul/acme-2018/1", text="Mentored the Acme Analyst team of 5")])
entry_b = RenderedEntry(id="exp/acme-2019", org="Acme", title="Analyst",
    dates="2019-01 -- 2019-12", bullets=[])
plan = RenderPlan(sections=[RenderedSection(id="sec.experience", title="Experience",
    entries=[entry_a, entry_b])])
text = ("Acme --- Engineer\n2018-01 -- 2018-12\n"
        "Mentored the Acme Analyst team of 5\n"
        "Acme --- Analyst\n2019-01 -- 2019-12\n")
# region exp/acme-2019 candidates == ['5']  (expected [])  -> check_metric_containment == "fail"
```

**Expected:** `exp/acme-2019` region candidates `[]`; `check_metric_containment` passes.
**Actual:** `exp/acme-2019` candidates `['5']`; `check_metric_containment` fails.

**Debug iterations:** 1 (the writing is correct; the failure is in the implementation,
which is READ-ONLY for this audit). **Action:** escalated to the developer. The planned
06-08 fix chose org+title as "equivalent" to a header anchor; a header anchor that cannot
match a bullet (e.g. one that also requires the `---`/em-dash header separator, or the
dates-adjacency discriminator proposed in `06-REVIEW.md`) would close this residual. Do
not weaken check 4.

**Independent corroboration:** `06-REVIEW.md` (2026-09-25) reproduced this same class and
re-raised it as its **CR-01** (Critical), with a dates-adjacency fix that keeps the
`base_extract.txt` header found and the `novel_metric_extract.txt` negative control failing.

### ESC-06-B — check 4 silently skips an unanchorable region, so a fabricated digit is never caught (medium)

**Class:** the same check-4 region logic, opposite direction — a silent false **negative**
in the one blocking check whose job is to catch a renderer-introduced number.

**Implementation:** `app/verify/numbers.py:151` (anchor guard), `:249-264`
(`position < 0` → `found=False`, `candidates=[]`), consumed by
`app/verify/text_checks.py:86-88` (`not report.found` skip). When no single squashed line
carries both org and title — an empty/all-punctuation `title`, or a long org+title that
wraps across two extracted lines — the region is skipped and a fabricated digit inside it
is not reported. `06-REVIEW.md` (2026-09-25) independently raised this as its **WR-01** and
reproduced a fabricated `99` passing check 4.

**Expected:** the operator can see that an entry was not metric-checked (a `warn`), or the
anchor falls back to a collision-resistant form. **Actual:** silent skip, `check` passes.
**Action:** escalated (relates to `06-REVIEW.md` WR-01). The existing test
`test_a_split_header_entry_is_reported_not_found_not_mislocated` pins the skip as a
deliberate trade-off but does not assert the integrity consequence.

**No red test was committed** — per the validate-phase contract, escalated gaps are
recorded here rather than left failing in the suite.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter — **deliberately left false: two escalated findings (ESC-06-A critical, ESC-06-B warning) remain**

**Approval:** approved 2026-09-25 with 2 escalated findings (PARTIAL)

---

## Validation Audit 2026-09-25

| Metric | Count |
|--------|-------|
| Requirement/task rows filled (TBD → green) | 22 |
| Resolved | 22 |
| Escalated (new adversarial findings: ESC-06-A, ESC-06-B) | 2 |
| Requirements with green automated coverage | 9/9 |
| Phase-suite result | 138 passed, 0 failed |
