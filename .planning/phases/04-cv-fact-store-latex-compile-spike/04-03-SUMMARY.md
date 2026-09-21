---
phase: 04-cv-fact-store-latex-compile-spike
plan: 03
subsystem: domain-cv-latex
tags: [latex, jinja2, pydantic, yaml, golden-test, escaping, determinism, fact-store]

requires:
  - phase: 04-cv-fact-store-latex-compile-spike
    plan: 01
    provides: the pyyaml runtime pin and the hermetic default test lane
  - phase: 04-cv-fact-store-latex-compile-spike
    plan: 02
    provides: the compiled .tex fixture whose facts this plan's YAML mirrors

provides:
  - "app/domain/tex.py — escape_tex, normalise_for_compare, squash, facts_present_in/facts_compared, sanitise_preamble"
  - "app/domain/cv.py — the CvFacts model family, SECTION_TITLES, stable ID derivation, RenderPlan, the three declared patch types, identity-only apply_patch"
  - "app/cv/factstore.py — the single loud, path-qualified cv.yaml reader"
  - "app/latex/env.py + app/latex/render.py + app/latex/templates/cv.tex.jinja — the deterministic renderer and its single escaping choke point"
  - "tests/fixtures/cv/awesomecv_standin.yaml — the synthetic fixture fact store"
  - "tests/golden/base.rendered.tex — the committed byte-exact renderer baseline"

affects: [04-04, 05, 06]

actuals:
  tokens: 21220
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "One Jinja finalize callback as a non-bypassable escaping choke point (D-67)"
    - "Filesystem-committed golden file compared with read_bytes, never auto-overwritten (D-72)"
    - "AST scan proving no clock/randomness import is reachable from a render path"
    - "Path-qualified Pydantic validation errors at a trust boundary (D-66)"

key-files:
  created:
    - app/domain/tex.py
    - app/domain/cv.py
    - app/cv/__init__.py
    - app/cv/factstore.py
    - app/latex/env.py
    - app/latex/render.py
    - app/latex/templates/cv.tex.jinja
    - tests/fixtures/cv/awesomecv_standin.yaml
    - tests/golden/base.rendered.tex
    - tests/domain/test_tex_escape.py
    - tests/domain/test_tex_preamble.py
    - tests/domain/test_cv_ids.py
    - tests/cv/test_factstore.py
    - tests/test_cv_hygiene.py
    - tests/golden/test_render_bytes.py
    - tests/test_render_determinism.py
  modified:
    - .gitignore
    - .gitattributes

key-decisions:
  - "escape_tex neutralises the backslash into a sentinel and re-injects its command last; a literal ordered replace corrupts the command's own braces"
  - "D-64's retirement is represented as retire-and-append: an edited bullet gets a NEW index, never a reuse of the frozen one"
  - "RenderPlan carries the identity block so the renderer needs nothing but a plan and cannot reach the fact store or a clock"
  - "CvFacts rejects duplicate IDs structurally AND factstore re-checks at load: the guarantee and the loud typed gate are separate"

patterns-established:
  - "Golden renderer baseline: committed, read_bytes comparison, in-test mutation control, .gitattributes LF pin"
  - "Determinism enemy scan: AST import check over the render path with a can-fail companion"
  - "Escape once at the environment: no escaping filter registered; Markup is the only opt-out"

requirements-completed: [CV-01, CV-02, CV-03, CV-04, CV-06]

coverage:
  - id: D1
    description: "cv.yaml loads as validated structured data with stable enumerated IDs; unknown keys, missing required fields, duplicate IDs, an unmapped title_key and a schema-version mismatch each fail loudly, path-qualified, with nothing default-filled"
    requirement: CV-01
    verification:
      - kind: unit
        ref: "tests/cv/test_factstore.py + tests/domain/test_cv_ids.py"
        status: pass
      - kind: other
        ref: ".venv/bin/python -c \"...load_facts('tests/fixtures/cv/awesomecv_standin.yaml')...\" -> 'fixture ok 4 ids'"
        status: pass
    human_judgment: false
  - id: D2
    description: "The human's base.tex is byte-identical across a load+identity-patch cycle, and cv/ + artifacts/ are structurally excluded from git by a guard test"
    requirement: CV-02
    verification:
      - kind: unit
        ref: "tests/cv/test_factstore.py::test_a_full_load_and_identity_patch_leaves_base_tex_byte_identical + tests/test_cv_hygiene.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Rendering the same plan twice is byte-identical, the committed golden baseline fails the build on any renderer or template change, and no clock/random/uuid import is reachable from the render path"
    requirement: CV-04
    verification:
      - kind: unit
        ref: "tests/golden/test_render_bytes.py + tests/test_render_determinism.py"
        status: pass
      - kind: other
        ref: ".venv/bin/python -c \"...render_plan_to_tex(apply_patch(f)) twice...\" -> 'render ok 2273 chars'"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every interpolated value is escaped at one non-bypassable choke point (the Environment finalize); non-ASCII passes through unchanged; no escaping filter is registered and Markup is the only opt-out"
    requirement: CV-06
    verification:
      - kind: unit
        ref: "tests/test_render_determinism.py + tests/domain/test_tex_escape.py"
        status: pass
      - kind: other
        ref: ".venv/bin/python -c \"import app.latex.env as e; env.finalize is e._latex_finalize...\" -> 'choke point installed'"
        status: pass
    human_judgment: false
  - id: D5
    description: "The three declared patch types are declared, and apply_patch performs only identity and ordering — every mutating operation raises UnsupportedPatchOp rather than being silently ignored"
    requirement: CV-01
    verification:
      - kind: unit
        ref: "tests/domain/test_cv_ids.py::test_each_mutating_operation_raises_rather_than_being_ignored"
        status: pass
    human_judgment: false
  - id: D6
    description: "The residual CV-R1 check on the REAL document: re-run the fact-store load and the renderer against cv/cv.yaml once the human has authored it, and record whether the decomposition reproduces the real document's facts"
    requirement: CV-03
    verification: []
    human_judgment: true
    rationale: "The real .tex is not in this repo; this plan's fixture is a synthetic stand-in. Plan 04-05's verdict document and the 04-VALIDATION.md manual-only entry own this check."

duration: 14min
completed: 2026-09-21
status: complete
---

# Phase 4 Plan 03: CV Fact Store + Deterministic LaTeX Render Summary

**A validated `cv.yaml` fact store with stable enumerated IDs, a byte-deterministic LaTeX renderer whose single Jinja `finalize` callback escapes every interpolated value, and a committed golden baseline that fails the build on any renderer change**

## Performance

- **Duration:** 14 min
- **Started:** 2026-09-21T14:28:06Z
- **Completed:** 2026-09-21T14:42:10Z
- **Tasks:** 3
- **Files modified:** 20 (18 created, 2 modified)

## Accomplishments

- The machine-canonical CV document is real: `tests/fixtures/cv/awesomecv_standin.yaml`
  loads into a validated `CvFacts` whose entries and bullets carry stable,
  enumerated, hierarchical IDs (`exp/northwind-labs-2021`,
  `bul/northwind-labs-2021/1`), mirroring the `.tex` fixture fact for fact.
- Every malformed or ambiguous input fails loudly and path-qualified
  (`sections.0.entries.0.bullets.0.text: …`), with no default-filling and no
  partial load; the safe YAML loader is the only loader reachable.
- One total, deterministic `escape_tex` is installed as the LaTeX Jinja
  Environment's `finalize` — a single non-bypassable choke point. The HTML
  escapers are removed from the environment so `Markup` is the only opt-out.
- Rendering is byte-deterministic and guarded by a committed, never-written
  golden baseline (`tests/golden/base.rendered.tex`) with an in-test mutation
  control; an AST scan proves no clock, randomness or uuid import is reachable.
- `cv/` and `artifacts/` are structurally excluded from git by a guard test, and
  the committed fixture carries only reserved-`.invalid` contact details.

## Task Commits

Each task was committed atomically:

1. **Task 1: The pure core — stable IDs, one total escaper, strict comparison** - `6cd28e2` (feat)
2. **Task 2: The fact store loads loudly, and the real CV can never be committed** - `f51565f` (feat)
3. **Task 3: The renderer — one escape choke point, byte-for-byte determinism, a golden file that can fail** - `267b231` (feat)

**Plan metadata:** committed with this file (`docs(04-03): complete …`)

## Files Created/Modified

- `app/domain/tex.py` — `escape_tex` (ten TeX-special chars, backslash-first), the comparison normaliser (`normalise_for_compare`, `squash`), `facts_present_in`/`facts_compared`, and the conservative preamble sanitiser
- `app/domain/cv.py` — the `CvFacts` model family, `SECTION_TITLES`, stable ID derivation with the recorded collision rule, `RenderPlan`, the three declared patch types, and the identity-only `apply_patch`
- `app/cv/factstore.py` — the single `cv.yaml` reader: safe loader, path-qualified validation, schema-version and ID-uniqueness gates
- `app/latex/env.py` — the second LaTeX Jinja `Environment` with the delimiter/determinism pins and the escaping `finalize`
- `app/latex/render.py` — `render_plan_to_tex` and a bytes-only `write_rendered`
- `app/latex/templates/cv.tex.jinja` — the committed application template (D-71)
- `tests/fixtures/cv/awesomecv_standin.yaml` — the synthetic fixture fact store
- `tests/golden/base.rendered.tex` — the committed byte-exact renderer baseline
- `.gitignore` — `cv/` and `artifacts/` volume exclusions, with code-directory negations
- `.gitattributes` — LF pins for the golden and template paths

## Decisions Made

- **Backslash sentinel in `escape_tex`.** The plan's literal ordered-replace would
  have corrupted the backslash command's own braces (`\` → `\textbackslash\{\}`).
  The backslash is neutralised first and its command re-injected last.
- **D-64 as retire-and-append.** Because bullet IDs are positional within a frozen
  entry, an edited bullet is represented as a NEW appended bullet; the test pins
  that the old ID retires and is absent from the new set.
- **`RenderPlan` carries the identity block** so the renderer needs nothing but a
  plan — it cannot reach the fact store or a clock.
- **Duplicate IDs are rejected twice**: structurally by the `CvFacts` model and
  again at load by `factstore._assert_ids_unique`, so the typed loud gate exists
  at the trust boundary independently of the model.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The prescribed escape loop corrupts the backslash replacement**
- **Found during:** Task 1 (the pure core)
- **Issue:** Applying `_TEX_ESCAPES` as a literal ordered `value.replace()` loop
  produces `\textbackslash\{\}` for an input backslash, because the backslash
  command's own `{}` are escaped by the later brace pass. The plan's own tests would
  not have caught it, but every real backslash would render wrongly.
- **Fix:** Backslash is neutralised into a NUL sentinel first, the remaining nine
  escapes run in tuple order, and the backslash command is re-injected last. The
  tuple keeps the backslash pair at index 0 and the ordering comment is retained.
- **Files modified:** `app/domain/tex.py`, `tests/domain/test_tex_escape.py`
- **Verification:** `escape_tex("\\") == r"\textbackslash{}"` and no
  `\textbackslash\{\}` appears; full domain suite green.
- **Committed in:** `6cd28e2` (Task 1 commit)

**2. [Rule 3 - Blocking] The unanchored `cv/` gitignore rule ignored the plan's own files**
- **Found during:** Task 2 (committing the fact store)
- **Issue:** `.gitignore` entry `cv/` (required verbatim by the plan's verify
  one-liner and hygiene guard) matches any directory named `cv` at any depth, so it
  also ignored `app/cv/`, `tests/cv/` and `tests/fixtures/cv/` — `git add` refused
  the plan's own deliverables.
- **Fix:** Kept the mandated exact `cv/` and `artifacts/` lines and added the
  negations `!app/cv/`, `!tests/cv/`, `!tests/fixtures/cv/`. Root `cv/` and
  `artifacts/` remain ignored (verified with `git check-ignore`).
- **Files modified:** `.gitignore`
- **Verification:** `git check-ignore` reports `cv/base.tex` and `artifacts/x.pdf`
  ignored while the three code/test directories are not; all 7 files commit.
- **Committed in:** `f51565f` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both were necessary for correctness and to make the plan's own
deliverables committable. No scope creep: no file outside the plan's
`files_modified` set was touched.

## Issues Encountered

- The Task 3 verify one-liners emit a Python `SyntaxWarning` from the shell's own
  escaping of the nested backslashes in the `-c` string; the assertions themselves
  pass. No code issue.
- The `f51565f` commit body lost the literal `` `cv/` `` text in one line because
  the message contained backticks interpreted by the shell. Cosmetic only.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for plan 04-04: `facts_present_in`/`facts_compared` in `app/domain/tex.py`
  and the fixture YAML are in place for the fact-equivalence lane, and
  `app/latex/compile.py` is untouched for that plan to add `extract_pdf_text`.
- Ready for Phases 5 and 6: the enumerated-ID model makes a fabricated employer or
  title unrepresentable, and the renderer's choke point is where Phase 6's
  untrusted listing text will arrive.
- **Residual (honest):** the decomposition has never been run against the real
  `cv/cv.yaml` — it is not in this repo. That manual-only check is plan 04-05's and
  the 04-VALIDATION.md entry's.

## Self-Check: PASSED

- All 20 created/modified files exist on disk and are committed.
- Commits verified in `git log`: `6cd28e2`, `f51565f`, `267b231`.
- `.planning/STATE.md` and `.planning/ROADMAP.md` are unmodified (orchestrator-owned).

---
*Phase: 04-cv-fact-store-latex-compile-spike*
*Completed: 2026-09-21*
