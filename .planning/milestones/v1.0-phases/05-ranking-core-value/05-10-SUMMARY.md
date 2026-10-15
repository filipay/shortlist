---
phase: 05-ranking-core-value
plan: 10
subsystem: ui
tags: [ranking, cv, fact-store, disclosure, gap-closure, jinja2, health, settings, queue]

# Dependency graph
requires:
  - phase: 05-ranking-core-value
    provides: "05-08's reason_counts_json['ranking'] marker, RunSummary.ranking_state and the #ranking-strip"
  - phase: 05-ranking-core-value
    provides: "05-09's detail-page disclosure of the same fact-store skip (this plan parallels it on Settings, the queue and /health)"
  - phase: 04-cv-data-model
    provides: "load_facts and its one path-qualified CvFactStoreError (D-66); scripts/cv-tex-spike.sh and its review draft"
provides:
  - "app.cv.factstore.fact_store_report(path) — a total, read-only {available, path, error} probe; error is the exception CLASS NAME only"
  - "The /settings #cv-fact-store card: the loader's path, its readable/unreadable state, and the four supply steps"
  - "The queue's unconditional #cv-fact-store-status line beside the LLM indicator"
  - "GET /health's cv object (available/path/error), mirroring the tectonic report and never degrading status"
  - "The documented promotion step (review draft -> cv/cv.yaml) in both probe documents, pinned by a test"
affects: [gsd-verify-work, tailoring]

# Actuals (#2632) — pairs with the plan's estimate (36000 tokens / 3 tasks, confidence low).
# Same estimateTokens scale (chars/4 over the authored diff). The generated, minified
# static/vendor/app.css is excluded: its one-rule change replaces a ~35 KB single line,
# which would double-count the whole artifact and corrupt the calibration.
actuals:
  tokens: 5388
  tasks: 3
  commits: 4
  plan_head_before: df50228414623d167dfed11f1afff1f5a9da26ee

tech-stack:
  added: []
  patterns:
    - "One total probe, three disclosures: the path and load outcome are computed once from Settings.cv_dir + rank.CV_FILENAME and shared by the Settings card, the queue line and /health, so no surface can disagree"
    - "Report-the-class-name: a total reporter catches, keeps only type(exc).__name__, and never echoes the exception message, because a YAML/validation message can carry document text"

key-files:
  created: []
  modified:
    - app/cv/factstore.py
    - app/api/settings.py
    - app/web/templates/html/settings.html
    - app/web/routes.py
    - app/web/templates/html/_health_strip.html
    - app/api/health.py
    - tests/cv/test_factstore.py
    - tests/api/test_settings_page.py
    - tests/api/test_health.py
    - tests/test_cv_tex_spike_docs.py
    - docs/probes/2026-09-21-cv-tex-spike.md
    - docs/probes/README.md
    - static/vendor/app.css

key-decisions:
  - "fact_store_report returns the exception CLASS NAME only, never its message — the one channel that could carry document text into a page or the /health JSON"
  - "The displayed path is str(Path(settings.cv_dir) / CV_FILENAME) everywhere (never a hardcoded /cv/cv.yaml); the tests derive the same expression so they do not pin the container default"
  - "The /health cv object carries path, not version (unlike tectonic): a fact store is a data document with no engine version, and the path is the operator's actionable datum"
  - "The copy says 'no readable CV fact store', never 'missing file', because D-94's one reason deliberately covers absent, unreadable and non-decodable alike (05-06)"
  - "The new #cv-fact-store-status line uses class cv-status; its stylesheet rule was added directly to the committed static/vendor/app.css, matching the repo's convention for post-05-03 component classes"

patterns-established:
  - "Disclosure-only prerequisite: the app names a host file and its supply procedure and never accepts it — no upload, no multipart, no write (D-58)"

requirements-completed: [RANK-08, UI-01]

coverage:
  - id: D1
    description: "fact_store_report(path) is a total, read-only probe returning {available, path, error}; error is the exception class name only, so no document text can reach a page or the /health JSON"
    requirement: RANK-08
    verification:
      - kind: unit
        ref: "tests/cv/test_factstore.py#test_fact_store_report_is_total_and_names_the_path"
        status: pass
      - kind: unit
        ref: "tests/cv/test_factstore.py#test_the_report_carries_the_exception_class_name_only"
        status: pass
    human_judgment: false
  - id: D2
    description: "The /settings #cv-fact-store card names the loader's exact path, states whether a readable store is present, and gives the four supply steps (cv/base.tex -> cv-tex-spike.sh -> cv.draft.yaml -> cv.yaml)"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "tests/api/test_settings_page.py#test_the_cv_card_names_the_path_and_the_supply_steps"
        status: pass
      - kind: unit
        ref: "tests/api/test_settings_page.py#test_the_cv_card_reports_a_readable_store"
        status: pass
    human_judgment: false
  - id: D3
    description: "The queue page carries an unconditional #cv-fact-store-status line beside the LLM indicator, naming the path and saying ranking is skipped until a store is supplied"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "tests/api/test_health.py#test_the_queue_page_renders_the_cv_status_line"
        status: pass
    human_judgment: false
  - id: D4
    description: "GET /health reports a cv object with available/path/error; a missing store is reported and never degrades status, and the object never carries a message"
    requirement: RANK-08
    verification:
      - kind: unit
        ref: "tests/api/test_health.py#test_health_always_reports_a_cv_object"
        status: pass
      - kind: unit
        ref: "tests/api/test_health.py#test_health_reports_a_missing_store_without_degrading_status"
        status: pass
      - kind: unit
        ref: "tests/api/test_health.py#test_health_reports_a_readable_store"
        status: pass
    human_judgment: false
  - id: D5
    description: "Both probe documents state the promotion from the review draft to cv/cv.yaml and the container path /cv/cv.yaml, so the in-app supply steps do not inherit the dead end the diagnosis found"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "tests/test_cv_tex_spike_docs.py#test_the_probe_docs_document_the_promotion_to_the_fact_store"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-09-23
status: complete
---

# Phase 05 Plan 10: Disclose the CV fact-store prerequisite Summary

**The app now says out loud that ranking needs a host-placed CV fact store: Settings names the loader's exact path and the four supply steps, the queue carries an unconditional status line beside the LLM indicator, `GET /health` reports a `cv` object mirroring `tectonic`, and the probe docs state the promotion to `cv/cv.yaml` — all from one total probe, with no upload and no write.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-09-23T10:37:53Z
- **Completed:** 2026-09-23T10:57:35Z
- **Tasks:** 3
- **Files modified:** 13

## Accomplishments

- **G-05-2 closed for the page-level surfaces.** `fact_store_report(path)` is the one total, read-only probe (`{available, path, error}`, class name only); the Settings card, the queue status line and `/health` all compute the path the loader actually reads (`Settings.cv_dir` + `rank.CV_FILENAME`) and share the same load attempt, so the three cannot disagree.
- **The question the user asked is answered in the product.** "Where do I provide my own CV?" — the Settings card states the steps: place the LaTeX CV at `cv/base.tex`, run `bash scripts/cv-tex-spike.sh`, review `cv/cv.draft.yaml`, promote the reviewed draft to `cv/cv.yaml` (the checkout's `cv/` is what the container mounts at `/cv`). It also says plainly that there is deliberately no upload control.
- **A fresh checkout is no longer mute.** The queue's `#cv-fact-store-status` line renders unconditionally beside the LLM indicator; on an unreadable store it names the path and points at `/settings`.
- **`/health` reports the dependency without degrading.** The `cv` object carries `available`/`path`/`error`; a missing store is REPORTED, never raised, and `status` stays `ok` — the same rule `tectonic` already follows.
- **The documented escape hatch is now complete.** Both `docs/probes/2026-09-21-cv-tex-spike.md` and `docs/probes/README.md` state the promotion to `cv/cv.yaml` and the container path, pinned by a test in the module that already pins those documents.

## Task Commits

Each task was committed atomically:

1. **Task 1: One total fact-store probe, and the Settings card** - `a729797` (feat)
2. **Task 2: The queue page states the CV prerequisite, and `/health` reports it** - `45b62a1` (feat)
3. **Task 3: Complete the documented escape hatch and pin it** - `5ed10ea` (docs)
4. **Deviation fix: the `cv-status` stylesheet rule** - `7df8af4` (fix)

**Plan metadata:** committed separately after this SUMMARY (docs).

## Files Created/Modified

- `app/cv/factstore.py` — `fact_store_report(path)`, a total read-only probe; `__all__` extended. Carries the exception class name only.
- `app/api/settings.py` — imports `fact_store_report` and `CV_FILENAME`; adds the `cv` entry to `_settings_context`.
- `app/web/templates/html/settings.html` — the `#cv-fact-store` card (status sentence + four supply steps), reusing the `settings-note`/`<code>` shape; no form, no `hx-`.
- `app/web/routes.py` — `_cv_status()` and the `cv` key on the `queue()` route context; the ranking strip, health tuple and watermark logic are untouched.
- `app/web/templates/html/_health_strip.html` — the unconditional `#cv-fact-store-status` line after the LLM indicator; header comment updated.
- `app/api/health.py` — `_cv_report()` and the `cv` key in the response body; adds `pathlib`, `app.config`, `fact_store_report` and `CV_FILENAME` imports.
- `tests/cv/test_factstore.py` — the report's totality/path and no-message pins.
- `tests/api/test_settings_page.py` — the card's path + supply-step pins and the readable-store case.
- `tests/api/test_health.py` — the `cv` object shape, missing-store no-degrade, readable case and queue-line pins; the exact-key-set assertion updated deliberately.
- `tests/test_cv_tex_spike_docs.py` — the promotion-step documentation pin; module docstring extended.
- `docs/probes/2026-09-21-cv-tex-spike.md`, `docs/probes/README.md` — the promotion step and container path.
- `static/vendor/app.css` — the `.cv-status` rule (deviation; see below).

## Decisions Made

- **One probe, three disclosures.** The path and load outcome are computed once and shared, so the Settings card, the queue line and `/health` cannot drift.
- **Class name only, never the message.** `fact_store_report` keeps `type(exc).__name__`; a YAML or validation message can echo document text, and the dict is rendered and returned as JSON (T-05-43).
- **`path`, not `version`, on the `cv` object.** A fact store is a data document with no engine version; the path is the operator's actionable datum — the one place this plan departs from a literal reading of the `tectonic` shape.
- **"Not readable", never "missing".** D-94's single reason covers absent, unreadable and non-decodable (05-06), so "missing file" would be false for two of the three cases.
- **No intake, by design.** No upload route, no multipart, no write to the fact store; the CV stays a host file (D-58).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added the `.cv-status` stylesheet rule**
- **Found during:** Full-suite verification after Task 3 (the project's `tests/test_stylesheet_coverage.py` guard)
- **Issue:** The new `#cv-fact-store-status` line uses `class="cv-status"`, and the repo guard requires every class in a template to have a rule in the committed `static/vendor/app.css`. `cv-status` had none, so the guard failed and the line would have rendered unstyled.
- **Fix:** Added a neutral-surface `.cv-status` rule (surface background, border, muted text) directly to `static/vendor/app.css`, beside the `.llm-*` rules. A full Tailwind regeneration was rejected: `assets/tailwind/input.css` is stale for post-05-03 component classes (it lacks `detail-rationale`, `badge-score`, `ranking-strip`, `weights-form`, `queue-sort`, etc.), so rebuilding would have dropped 19 classes the templates use. The repo's own convention since 05-03 is direct edits to the built stylesheet.
- **Files modified:** `static/vendor/app.css`
- **Verification:** `tests/test_stylesheet_coverage.py` (5 passed) and the full suite green.
- **Committed in:** `7df8af4` (separate deviation commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** The stylesheet rule is required for the plan's own markup to render as intended and to satisfy a committed project guard; it is not scope creep. The plan's `files_modified` omitted the stylesheet.

## Issues Encountered

- The first attempt regenerated `static/vendor/app.css` from `assets/tailwind/input.css`; the coverage guard then failed on 19 classes (`detail-rationale`, `badge-score`, `ranking-strip`, `weights-form`, `queue-sort`, …) that live only in the committed built file, proving `input.css` is not the current build source for later component classes. Both files were reverted and the single rule hand-added instead, keeping the diff to one line.

## User Setup Required

None - no external service configuration required. The CV fact store remains a host file by design (D-58); this plan only discloses where the loader reads it and how to supply it.

## Known Stubs

None - every disclosure is wired to a real load attempt; no hardcoded empty values or placeholder text was introduced.

## Next Phase Readiness

- G-05-2's page-level disclosure is complete across Settings, the queue and `/health`, all driven by one probe; the row badge and queue empty state remain declared out of scope in the plan with rationale.
- Phase-05 round-2 gap closure (05-08, 05-09, 05-10) is complete; `/gsd-verify-work`'s round-2 UAT re-run is the remaining step.
- Full suite green: `1065 passed, 14 deselected, 2 xfailed`; build (`compileall -q app`) clean.

---
*Phase: 05-ranking-core-value*
*Completed: 2026-09-23*

## Self-Check: PASSED

- FOUND: `.planning/phases/05-ranking-core-value/05-10-SUMMARY.md`
- FOUND commit: `a729797` (Task 1)
- FOUND commit: `45b62a1` (Task 2)
- FOUND commit: `5ed10ea` (Task 3)
- FOUND commit: `7df8af4` (deviation fix)
- Full suite: `1065 passed, 14 deselected, 2 xfailed`; build `compileall -q app` clean.
