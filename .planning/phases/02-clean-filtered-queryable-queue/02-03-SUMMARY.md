---
phase: 02-clean-filtered-queryable-queue
plan: "03"
subsystem: domain
tags: [pure-functions, filter-rules, criteria, prompt-injection, sanitize, apache-2.0, dataclasses]

# Dependency graph
requires:
  - phase: 01-walking-skeleton-foundations
    provides: app/domain/{listing,sanitize,models}.py (the purity contract, annualise_salary, INSTRUCTION_MARKERS/SanitizeReport), app/sources/base.py SearchQuery, and tests/test_import_discipline.py
  - phase: 02-clean-filtered-queryable-queue
    provides: migration 0002's ck_filter_rules_kind vocabulary (plan 02-01)
provides:
  - app/domain/filter.py — RULE_KINDS, RuleSpec/ListingFacts/RuleOutcome, a total evaluate()
  - app/domain/criteria.py — search_query_from() and rule_specs_from()
  - app/domain/sanitize.py extended — INJECTION_PATTERNS, count_injection_patterns, SanitizeReport.patterns_matched
affects: [02-05 filter stage + skipped-rule stage log, 02-07 FTS search query, 02-08 criteria and filter-rules UI]

# Actuals (#2632) — same estimateTokens scale (chars/4 over the realized diff).
actuals:
  tokens: 13313
  tasks: 3
  commits: 3
  plan_head_before: 260dc5105c1973b2e8139e3d23f342d289ab0c11

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Total pure functions over frozen dataclasses (no I/O, no settings, never raise)"
    - "Allow-list field access: an exclude_keyword field must be in LISTING_FACT_FIELDS"
    - "Flag-and-count, never redact: the injection catalogue never rewrites text"
    - "Apache-2.0 §4(c) origin + significant-change notice in the module, never a template"

key-files:
  created:
    - app/domain/filter.py
    - app/domain/criteria.py
    - tests/domain/test_filter.py
    - tests/domain/test_criteria.py
    - tests/domain/test_injection_patterns.py
  modified:
    - app/domain/sanitize.py

key-decisions:
  - "An absent/unknown value is never a rejection reason: salary, remote, seniority and location rules reject only on a present, contradicting value (resolved A2/A3)"
  - "salary_floor consults the BEST known annualised figure (max, else min), so a range that straddles the floor is not rejected — the same anti-over-rejection bias applied to a range"
  - "A malformed rule (unknown kind, non-mapping params, wrong-typed required key) is skipped and produces no outcome; the caller's stage log records the skip (T-02-09)"
  - "exclude_keyword reads only LISTING_FACT_FIELDS, so a hostile `fields` value cannot reach an attribute that is not a listing field (T-02-06)"
  - "criteria.py imports app.sources.base.SearchQuery only — importing it pulls neither jobspy nor any I/O (verified: jobspy/tls_client stay unloaded)"
  - "The pattern-5 literal is described rather than quoted in the comment block, so each raw pattern string appears exactly once (in the compiled tuple)"

patterns-established:
  - "One outcome per firing rule, ordered by (position, rule_id): never merged, so per-rule GROUP BY counts are exact"
  - "A deterministic order over an unstable input order: rule_specs_from sorts by (search_id, position, rule_id)"
  - "PII-free evidence: RuleOutcome.detail carries terms, field names and counts only; the matched field text is never included"

requirements-completed: []

coverage:
  - id: D1
    description: "The six filter-rule evaluators exist as pure functions and each kind is exercised in both directions"
    requirement: FILT-01
    verification:
      - kind: unit
        ref: "tests/domain/test_filter.py (27 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "An unknown value is never a rejection reason, an unknown kind is skipped, and malformed params never raise"
    requirement: FILT-01
    verification:
      - kind: unit
        ref: "tests/domain/test_filter.py#test_unknown_values_are_never_a_rejection_reason"
        status: pass
      - kind: unit
        ref: "tests/domain/test_filter.py#test_an_unknown_kind_is_skipped"
        status: pass
      - kind: unit
        ref: "tests/domain/test_filter.py#test_a_non_mapping_params_is_skipped_without_raising"
        status: pass
    human_judgment: false
  - id: D3
    description: "Rule evidence is PII-free: detail key-sets are exact per kind and the matched field's text never appears"
    requirement: FILT-02
    verification:
      - kind: unit
        ref: "tests/domain/test_filter.py#test_exclude_keyword_never_persists_the_field_text"
        status: pass
      - kind: unit
        ref: "tests/domain/test_filter.py#test_detail_keys_are_exact_per_kind"
        status: pass
    human_judgment: false
  - id: D4
    description: "Criteria and rule rows assemble into SearchQuery and an ordered RuleSpec list through pure, settings-free functions"
    requirement: CRIT-01
    verification:
      - kind: unit
        ref: "tests/domain/test_criteria.py (13 passed)"
        status: pass
      - kind: unit
        ref: "tests/domain/test_criteria.py#test_rule_specs_order_is_stable_under_an_unstable_input_order"
        status: pass
      - kind: unit
        ref: "tests/domain/test_criteria.py#test_module_does_not_import_settings_or_the_capability_compiler"
        status: pass
    human_judgment: false
  - id: D5
    description: "The three domain modules import no I/O — the AST import-discipline guard still passes"
    verification:
      - kind: unit
        ref: "tests/test_import_discipline.py (4 passed)"
        status: pass
    human_judgment: false
  - id: D6
    description: "The injection catalogue flags and counts matches without mutating text, with the Apache-2.0 §4(c) origin notice present"
    requirement: FILT-02
    verification:
      - kind: unit
        ref: "tests/domain/test_injection_patterns.py (17 passed)"
        status: pass
      - kind: unit
        ref: "tests/domain/test_injection_patterns.py#test_a_matched_pattern_is_flagged_but_never_redacted"
        status: pass
      - kind: unit
        ref: "tests/domain/test_injection_patterns.py#test_the_catalogue_is_never_used_to_rewrite_text"
        status: pass
    human_judgment: false
  - id: D7
    description: "Every Phase-1 sanitiser behaviour is unchanged (PII drop, truncation, HTML, counts) and the no-CDN guard still passes"
    verification:
      - kind: unit
        ref: "tests/domain/test_sanitize.py tests/domain/test_sanitize_pii.py tests/domain/test_sanitize_edge.py (all passed, unchanged)"
        status: pass
      - kind: unit
        ref: "tests/test_no_cdn.py (11 passed)"
        status: pass
    human_judgment: false

# Metrics
duration: 15min
completed: 2026-09-16
status: complete
---

# Phase 2 Plan 03: The pure decision layer — filter rules, criteria assembly, and the injection catalogue

**Six total filter-rule evaluators, two pure criteria assemblers, and an Apache-2.0-attributed injection catalogue that flags and counts without ever mutating stored listing text.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-09-16T09:19:30Z (approximate — the start-time capture was missed and is bounded by plan 02-02's final commit at 09:19:24Z)
- **Completed:** 2026-09-16T09:34:13Z
- **Tasks:** 3
- **Files modified:** 6 (5 created, 1 extended)

## Accomplishments

- **`app/domain/filter.py`** implements the six `filter_rules.kind` values as total pure functions. `evaluate()` returns **one outcome per firing rule**, ordered by `(position, rule_id)`; a `kind` outside `RULE_KINDS`, a non-mapping `params`, a missing or wrong-typed required key all skip that rule without raising, and a skipped rule produces no outcome at all (never a silent "applied").
- **An absent value is never a rejection reason.** `salary_floor` passes when no salary is known, `remote` passes `None`, `seniority` passes `None` (when `unknown_passes`), `location` passes `None` — the resolved A2/A3 decision, asserted by a single all-six-kinds test that expects exactly zero outcomes.
- **Evidence is PII-free.** `RuleOutcome.detail` key-sets are asserted exactly per kind, and the `exclude_keyword` test proves the matched field's text never reaches the detail — only the term, the field *name* and a count.
- **`app/domain/criteria.py`** assembles `SearchQuery` and `RuleSpec`s through settings-free pure functions. Documented keys pass through, absent keys fall back to the `SearchQuery` default, unknown keys are ignored, `seniority` is normalised to a tuple, and `rule_specs_from` orders by `(search_id, position, rule_id)` so the union across searches is deterministic regardless of input order. Disabled rows and unknown-kind rows are dropped.
- **`app/domain/sanitize.py`** gained `INJECTION_PATTERNS` (eight compiled regexes), a total `count_injection_patterns()`, and `SanitizeReport.patterns_matched`, with `merge()` summing it. `looks_like_instructions` now consults both the Phase-1 marker pre-check and the catalogue; its boolean contract is unchanged. **No `re.sub` was added** — the catalogue never rewrites text, so the sanitised description (and therefore `content_hash`) is byte-identical to Phase 1's output for the same input.
- The Apache-2.0 §4(c) obligation is discharged in the module: the comment block names `srbhr/resume-matcher`, `apps/backend/app/services/improver.py`, the licence, and the **significant change** (upstream redacts; this catalogue flags and counts). No URL was placed anywhere, and the attribution is asserted to be in the `.py` module, not a template.

## Task Commits

Each task was committed atomically:

1. **Task 1: The six pure rule evaluators, proven end-to-end over a mapped rule row** - `b028fcc` (feat)
2. **Task 2: Criteria-to-query and rules-to-specs assemblers** - `d38aa4e` (feat)
3. **Task 3: Extend the sanitiser with the attributed injection catalogue — flag and count, never redact** - `acf0238` (feat)

**Plan metadata:** _committed with STATE/ROADMAP after this file_

Tracer gate (task 1): its `<verify>` is automated-only and `human_verify_mode=end-of-phase`, so the verify was re-run and execution continued without a synthesized checkpoint.

## Files Created/Modified

- `app/domain/filter.py` — `RULE_KINDS`, `LISTING_FACT_FIELDS`, `RuleSpec`, `ListingFacts`, `RuleOutcome`, `evaluate()`; six private evaluators.
- `app/domain/criteria.py` — `search_query_from()`, `rule_specs_from()`; the A4 union scope and D-32 are stated in the docstring.
- `app/domain/sanitize.py` — `INJECTION_PATTERNS`, `count_injection_patterns()`, `SanitizeReport.patterns_matched`, widened `looks_like_instructions`, `sanitize_text` populating the count, `__all__` extended, module docstring updated to reflect the catalogue's arrival.
- `tests/domain/test_filter.py` — 27 tests.
- `tests/domain/test_criteria.py` — 13 tests.
- `tests/domain/test_injection_patterns.py` — 17 tests.

## Decisions Made

- **`salary_floor` consults the best known annualised figure (max, else min).** A range whose top could meet the floor is not rejected. The phase's explicit anti-over-rejection stance (A2/A3) applied to a range rather than to an absent value; the alternative (compare `min`) would reject a role that could pay enough.
- **`exclude_keyword` uses the `LISTING_FACT_FIELDS` allow-list** rather than a bare `getattr(facts, field)`, so a hostile `fields` value cannot reach a non-field attribute.
- **`rule_specs_from` accepts `id` as a fallback for `rule_id`** and both `params`/`params_json`, so the repository can pass a raw ORM row dict without a second adapter — which is what the plan's dual-key allowance is for.
- **The comment block describes pattern 5 rather than quoting it**, so the "each raw pattern appears exactly once" property (and the acceptance grep) holds.
- **No `Settings` reader here.** `search_query_from` returns empty keywords for a missing/empty value and states that contract in its docstring, keeping the module configuration-free as the plan requires.

## Deviations from Plan

### Environment substitution (not a plan defect)

- **`<verify>` commands ran through `.venv/bin/python -m pytest`**, not `.venv-host/bin/pytest`: that console script's shebang is stale and `.venv-host`'s `pydantic_core` wheel is broken (gnu/musl mismatch). Same Python 3.14.7 and package versions. Recorded in `deferred-items.md` by plan 02-01.

**Total deviations:** 0 auto-fixed (no bugs, missing functionality or blockers encountered).
**Impact on plan:** None on committed artifacts; every acceptance criterion and the plan-level `<verification>` commands passed under the working interpreter.

## Issues Encountered

- **Two test-authoring mistakes, both fixed before their task committed** (neither is a plan deviation): the `salary_floor` detail-keys case initially inherited `salary_max=90000` from the shared fixture and therefore did not fire under the best-case rule; and the catalogue-source test initially counted pattern 5 twice because the comment quoted it. Both were corrected and the full suite is green.
- `ruff` flagged line length in the first test draft and an import order in the third; both were fixed and all six new/changed files are `ruff check` clean.
- A first full-suite run reported 53.5s wall-clock (above the usual ~17s lane); two clean re-runs reported 16.57s and a `tests/domain tests/db` run 8.12s — machine contention from parallel work, not a regression.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-05 can now import `evaluate`, `RuleSpec`/`ListingFacts`, and `rule_specs_from` to build the filter stage, and it has `RULE_KINDS` as the single in-code vocabulary shared with the `ck_filter_rules_kind` CHECK.
- Plan 02-07's FTS safety transform remains deliberately absent (`app/domain/search_query.py` belongs with its consumer); `criteria.py` does not pre-empt it.
- Plan 02-05 must record skipped rules in the run's stage log — `evaluate()` deliberately produces no outcome for a skipped rule, and the docstring states the obligation (T-02-09).
- Requirements **FILT-01, FILT-02 and CRIT-01 were deliberately NOT marked complete**: the shared-ID gate reported `0/3 ready` because sibling plans in this phase also declare them and have no SUMMARY yet.

---
*Phase: 02-clean-filtered-queryable-queue*
*Completed: 2026-09-16*

## Self-Check: PASSED

- All six plan files exist on disk (3 modules, 3 test modules).
- All three task commits exist: `b028fcc`, `d38aa4e`, `acf0238`; measured count `3` over `plan_head_before=260dc5105c1973b2e8139e3d23f342d289ab0c11`.
- Plan-level verification re-run: `tests/domain tests/test_no_cdn.py tests/test_import_discipline.py` → `123 passed`; `tests/domain tests/db tests/pipeline` → `159 passed`; full suite → `380 passed, 2 deselected in 16.57s`.
- `ruff check` is clean on all six new/changed files.
- Note: this plan's `gsd-plan-head-before` ledger was written one step late and derived from the first task commit's parent (`260dc51`, the 02-02 metadata commit), which was HEAD at plan start — the measured commit count is unaffected.
