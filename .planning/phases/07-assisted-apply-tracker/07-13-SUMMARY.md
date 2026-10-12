---
phase: 07-assisted-apply-tracker
plan: 13
subsystem: ui
tags: [tailwind, css, build-reproducibility, guard, gap-closure, cr-01]

requires:
  - phase: 07-assisted-apply-tracker
    provides: the phase-5/6/7 template component rules that lived only in the hand-appended block of the built `static/vendor/app.css` (07-11, D-132)
provides:
  - "`assets/tailwind/input.css` is the reconciled source of truth: every component rule the templates use is defined there, so a fresh build emits all of them"
  - "`static/vendor/app.css` is the byte-identical build of its source (pinned tailwindcss/@tailwindcss/cli 4.3.3, the `Dockerfile:19` command)"
  - "two Node-free source-coverage guards and a build-reproducibility guard that would have caught CR-01"
affects: [07-uat, ui, tracker, apply-package, listing-detail, settings, tailoring]

actuals:
  tokens: 23669
  tasks: 3
  commits: 3
plan_head_before: 384374326aec6266887d4e2e090214b93e592262

tech-stack:
  added: []
  patterns:
    - "the committed stylesheet is a build artifact of its source (`input.css`), never hand-edited: a Node-free source-coverage guard plus a byte-identity reproducibility guard keep the deployed artifact a function of its source"

key-files:
  created: []
  modified:
    - assets/tailwind/input.css
    - static/vendor/app.css
    - tests/test_stylesheet_coverage.py
    - .planning/phases/07-assisted-apply-tracker/07-UI-SPEC.md

key-decisions:
  - "Backfill the source FIRST, then regenerate the artifact — the review's prescribed order; a rebuild-before-backfill would delete the 30 template rules from the shipped stylesheet (the exact CR-01 mechanism)."
  - "The static token scan drops a token ending in `-`, so the eleven dynamic-suffix values (eight `badge-stage-*` over APPLICATION_STATUSES, three `badge-score-tier-*`) are an explicit asserted list — mirroring how `input.css` already enumerates `run-status-*` / `health-*` / `rule-chip-*`."
  - "The reconciliation is additive only: one new `@layer components` block appended at the end of `input.css`; every pre-existing declaration (`.listing-*`, `.badge*`, `.queue-*`, `.rule-chip*`, `.settings-*`, `.cv-delete`, `.htmx-indicator`, `input[type=file]`, the 07-11 `.tracker-*`) is byte-unchanged."
  - "The reproducibility guard emits a visible `pytest.skip` naming the arming command when `node`/the CLI is absent — never a bare `return`; the Node-free source guards still fail closed in that environment (CONVENTIONS rule 2/6)."
  - "Not re-adding already-present rules (`.tracker-note`/`.tracker-actions`/`.tracker-action`, `.htmx-indicator`, `.cv-delete`, `input[type=file]`), per prohibition #3 and the plan's explicit do-not-re-add list."
  - "UI-SPEC prose corrected to name `assets/tailwind/input.css` as the source of truth: describing the built file as hand-extended is what let CR-01 stand (CONVENTIONS rule 6)."

patterns-established:
  - "Source-of-truth stylesheet: component rules live in `assets/tailwind/input.css` inside `@layer components`; the committed artifact is regenerated with the pinned CLI and guarded by byte-identity, so the Dockerfile rebuild can never diverge silently."

requirements-completed: [UI-04, APPLY-01]

coverage:
  - id: D1
    description: "A fresh build of `assets/tailwind/input.css` by the pinned 4.3.3 CLI is byte-identical to the committed `static/vendor/app.css` (`cmp` exits 0 on the `Dockerfile:19` command)."
    requirement: UI-04
    verification:
      - kind: other
        ref: "test_the_committed_stylesheet_is_the_build_of_its_source (runs the CLI into tmp_path, asserts byte-equality)"
        status: pass
      - kind: other
        ref: "container-free: `cmp static/vendor/app.css /tmp/opencode/app-rebuilt.css` → identical"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every literal class token in the phase templates has a rule in `assets/tailwind/input.css` (the 30 classes the fresh build previously dropped, incl. `.answer-text`, `.apply-link`, `.listing-detail-link`, `.next-overdue`, `.requirement-list`)."
    requirement: UI-04
    verification:
      - kind: unit
        ref: "tests/test_stylesheet_coverage.py#test_every_template_class_has_a_rule_in_the_source_stylesheet"
        status: pass
    human_judgment: false
  - id: D3
    description: "All eleven dynamic-suffix values (eight `.badge-stage-*` + three `badge-score-tier-*`) are defined in the source and present as distinct selectors in the shipped artifact."
    requirement: APPLY-01
    verification:
      - kind: unit
        ref: "tests/test_stylesheet_coverage.py#test_every_dynamic_suffix_class_is_defined_in_the_source_stylesheet"
        status: pass
      - kind: other
        ref: "grep -o 'badge-stage-[a-z]*' static/vendor/app.css | sort -u | wc -l → 8; badge-score-tier → 3"
        status: pass
    human_judgment: false
  - id: D4
    description: "The guards cannot pass vacuously, and deleting a value to make them pass is itself a failure."
    requirement: UI-04
    verification:
      - kind: unit
        ref: "tests/test_stylesheet_coverage.py#test_the_source_guard_flags_an_unstyled_class"
        status: pass
      - kind: unit
        ref: "tests/test_stylesheet_coverage.py#test_the_dynamic_suffix_class_list_is_justified"
        status: pass
    human_judgment: false
  - id: D5
    description: "The two source guards are demonstrably RED on the pre-Task-2 source: exactly 30 missing literal classes and exactly eleven missing suffix values (recorded below)."
    requirement: UI-04
    verification:
      - kind: other
        ref: "RED run before Task 2: 2 failed, 7 passed — 30 missing classes and 11 missing values"
        status: pass
    human_judgment: false
  - id: D6
    description: "With `node`/the CLI absent the byte-identity test visibly skips (naming the arming command), never silently passes; the Node-free guards still run."
    requirement: UI-04
    verification:
      - kind: unit
        ref: "pytest with node hidden from PATH: 9 passed, 1 skipped (skip message names the npm install command)"
        status: pass
    human_judgment: false

duration: ~10min
completed: 2026-10-12
status: complete
---

# Phase 07 Plan 13: CR-01 reconcile the Tailwind source with the shipped stylesheet Summary

**The committed `static/vendor/app.css` is now the byte-identical build of `assets/tailwind/input.css` — the 30 template component rules and eleven dynamic-suffix badge rules backfilled into the source first, the artifact regenerated with the pinned 4.3.3 CLI, and three new guards (two Node-free source-coverage, one byte-identity) that would have caught CR-01.**

## Performance

- **Duration:** ~10 min
- **Tasks:** 3
- **Files modified:** 4
- **Commits:** 3 (measured `git rev-list --count 3843743..HEAD`)

## Accomplishments

- `assets/tailwind/input.css` gained ONE appended `@layer components` block carrying every rule the phase-5/6/7 templates use but the source lacked: `.badge-score`, the three `badge-score-tier-*`, `.listing-detail-link`(+hover), `.detail-rationale`, `.detail-not-ranked`, `.detail-empty`, the `.factor-table` family, `.factor-absent`, the `.requirement-list` family, `.req-met/-partial/-gap`, `.badge-unranked`, `.ranking-strip`, `.badge-flagged`, `.cv-status`, `.queue-sort`, `.queue-threshold`(+ shared selector), the `.weights-*` family, `.tailoring-review`, `.tailoring-empty`, `.cv-generate`, `.cv-download`, all eight `.badge-stage-*`, `.next-overdue`, `.apply-assurance`, `.apply-link`(+hover), `.answer-text`, `.answer-warning`.
- `static/vendor/app.css` regenerated from the source with the pinned CLI (tailwindcss / @tailwindcss/cli **4.3.3**) — replaces the minified phase-5 build plus the hand-appended block with a single one-line build (38,842 bytes). `cmp` against a fresh build exits 0.
- The `Dockerfile:19` command now emits a stylesheet carrying every template class, so `Dockerfile:116` ships a styled tracker / apply-package / listing-detail / settings / tailoring UI.
- Three guards added to `tests/test_stylesheet_coverage.py`: `test_every_template_class_has_a_rule_in_the_source_stylesheet` (Node-free), `test_every_dynamic_suffix_class_is_defined_in_the_source_stylesheet` (+ its justification and not-vacuous siblings), and `test_the_committed_stylesheet_is_the_build_of_its_source` (runs the CLI, asserts byte-identity, visible `pytest.skip` when the toolchain is absent).
- `07-UI-SPEC.md` prose corrected: the Design System `Tool` row, the Component Inventory citation note, and the `.tracker-note` "Defined" cell now name `assets/tailwind/input.css` as the source of truth and `static/vendor/app.css` as its checked-in build — no token/colour/spacing/typography value changed.

## Task Commits

Each task was committed atomically:

1. **Task 1: The two source guards (RED)** — `fb0d3b8` (test)
2. **Task 2: Backfill the source, regenerate the artifact, correct the UI-SPEC prose** — `319df0c` (fix)
3. **Task 3: The reproducibility guard** — `2ae0d47` (test)

**Plan metadata:** see the final docs commit.

_Note: the plan file is `type: execute`; Tasks 1 and 3 were `tdd="true"` and Task 1 was executed RED-first (see `## Verification`). Task 2 was `type="tracer"`: its automated `<verify>` was re-run end-to-end after the task (interactive mode, `human_verify_mode: end-of-phase`), it passed, and execution continued with no checkpoint._

## Files Created/Modified

- `assets/tailwind/input.css` (modified, +68 lines) — one appended `@layer components` block (CR-01 reconciliation header + the reconciled rules). Purely additive; no existing line removed or reordered.
- `static/vendor/app.css` (regenerated) — the pinned 4.3.3 build of the reconciled source; 1 line, 38,842 bytes.
- `tests/test_stylesheet_coverage.py` (modified, +111 lines) — `SOURCE_STYLESHEET`, `DYNAMIC_SUFFIX_CLASSES`, `TAILWIND_CLI`, and five new tests. Existing `EXEMPT_CLASSES`, `_literal_class_tokens`, `_stylesheet_has_class` and `test_every_template_class_has_a_stylesheet_rule` are byte-unchanged.
- `.planning/phases/07-assisted-apply-tracker/07-UI-SPEC.md` (modified, three prose edits) — source-of-truth wording only.

## Decisions Made

- **Backfill-then-rebuild order** (prohibition #1 honoured): the source was edited first, then the artifact regenerated, so a real build could not delete the rules.
- **Explicit eleven-value list** for the dynamic suffixes the static token scan cannot derive — with a justification test so deleting a value is itself a failure.
- **No silent pass**: the byte-identity guard's absent-toolchain path is a `pytest.skip` naming `npm install --no-save --no-audit --no-fund tailwindcss@4.3.3 @tailwindcss/cli@4.3.3`.
- **No dependency/manifest change**: `node_modules/` is gitignored and untouched in git; no root `package.json`/lockfile created; `shutil`/`subprocess` are stdlib.

## Deviations from Plan

None — the plan was executed exactly as written, in the prescribed order (RED source guards → backfill/regenerate/prose → reproducibility guard).

### Environment repair (blocking, non-code)

- **Found during:** first Task 1 verification.
- **Issue:** the sandbox's `.venv` is a broken Python 3.14 venv (`No module named pytest`), so the plan's declared `.venv/bin/python -m pytest` cannot run here.
- **Fix:** ran the plan's declared test command through the provisioned interpreter `/tmp/opencode/gsdvenv13/bin/python -m pytest` (Python 3.13.16, pytest 9.1.1), per the sandbox instructions. No repo file, dependency manifest or lockfile was changed.
- **Risk:** none material to this plan — the guards are pure-Python/Node-CLI and version-independent.

## Issues Encountered

- The pre-Task-2 RED evidence is exact: **30 missing literal classes** (matching the plan's enumeration byte-for-byte) and **all eleven** dynamic-suffix values missing, with the two justification/flag tests passing.
- No code-facing problems. The only edit-tool friction was inserting the Task 3 test before the `if __name__` block (the first attempt's anchor included the not-yet-written test); resolved with a corrected anchor.

## Verification

Plan declared command (environment substituted per the deviation above):

- **RED (Task 1):** `.venv/bin/python -m pytest -q tests/test_stylesheet_coverage.py -x` → **2 failed, 7 passed**; the failure named all 30 missing literal classes and, run without `-x`, all eleven missing suffix values.
- **GREEN + end-to-end (Task 2):** `tailwindcss -i ./assets/tailwind/input.css -o /tmp/opencode/app-rebuilt.css --minify && cmp static/vendor/app.css /tmp/opencode/app-rebuilt.css && pytest -x` → `cmp` **identical**, suite **9 passed**. Distinct-selector counts: `badge-stage-*` = **8**, `badge-score-tier-*` = **3**.
- **Guard (Task 3):** `pytest -q tests/test_stylesheet_coverage.py -x && ruff check tests/test_stylesheet_coverage.py` → **10 passed**, ruff **All checks passed**. With `node` hidden from PATH: **9 passed, 1 skipped** (skip message names the arming command).
- **Regression lane:** `pytest -q tests/test_stylesheet_coverage.py tests/api/test_applications_tracker.py tests/api/test_apply_package.py tests/test_import_discipline.py -x` → **68 passed**.
- **Full default lane:** `pytest -q` → **1697 passed, 14 deselected, 2 xfailed** in 226.72s.
- **Catches-bad direction:** byte-identity fails on a hand-edited artifact; the source guard fails when a rule is removed from `input.css`; the suffix guard fails when a `badge-stage-*`/`badge-score-tier-*` value is deleted; removing a value from `DYNAMIC_SUFFIX_CLASSES` fails the justification test.
- **Accepts-valid direction:** `EXEMPT_CLASSES`, `_literal_class_tokens`, `_stylesheet_has_class` and `test_every_template_class_has_a_stylesheet_rule` are byte-unchanged and green.

## Threat Surface

- T-07-13-01 / T-07-13-02 (mitigate): the byte-identity guard + the Node-free source guard now make a divergent or hand-edited artifact a test failure; the UI-SPEC no longer documents hand-extension.
- T-07-13-03 (mitigate): the reproducibility guard fails closed when it can build and visibly skips (naming the arming command) when it cannot; the source guards run in both environments.
- T-07-13-04 / T-07-13-SC (accept): no new package (both CLI packages are already the `Dockerfile:15-16` pins at 4.3.3), no manifest/lockfile touch, `node_modules/` gitignored and uncommitted.

## Known Stubs

None — no stub, placeholder or unwired data source was introduced.

## Next Phase Readiness

- CR-01 is closed: the deployed image now serves a stylesheet carrying every phase-7 template class; the tracker/apply/detail/settings surfaces are styled rather than unstyled.
- The manual UAT re-run items carried by the plan remain (rendered-rect G-07-6 check, clipboard multi-paragraph fidelity, UAT tests 1–2 at 1280px/375px) — no browser dependency was added.

---
*Phase: 07-assisted-apply-tracker*
*Completed: 2026-10-12*

## Self-Check: PASSED

- SUMMARY.md: FOUND
- Commit `fb0d3b8` (Task 1, RED): FOUND
- Commit `319df0c` (Task 2, fix): FOUND
- Commit `2ae0d47` (Task 3, guard): FOUND
- `assets/tailwind/input.css` reconciled block: FOUND
- `static/vendor/app.css` byte-identical build: FOUND
- `07-UI-SPEC.md` source-of-truth prose: FOUND
