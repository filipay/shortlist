---
gsd_state_version: "1.0"
current_phase: 06
current_phase_name: Tailoring + Verification
status: executing
stopped_at: Completed 06-01-PLAN.md
last_updated: "2026-09-24T16:26:19.876Z"
last_activity: 2026-09-24
last_activity_desc: Phase 06 execution started
state_head: 404d9951f757e8954232a630d3aaef51894a79a8
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 49
  completed_plans: 46
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-24)

**Core value:** Every morning there is one ranked, explained, apply-ready queue of jobs worth considering — so the search→judge→tailor loop costs minutes instead of hours.
**Current focus:** Phase 06 — Tailoring + Verification

## Current Position

Phase: 06 (Tailoring + Verification) — EXECUTING
Plan: 2 of 4
Status: Ready to execute
Last activity: 2026-09-24 — Phase 06 execution started

Progress: [████████████████████] 45/45 plans ([░░░░░░░░░░] 0%)

## Performance Metrics

**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 23 min | 3 tasks | 40 files |
| Phase 01 P02 | 5 min | 2 tasks | 3 files |
| Phase 01 P03 | 15 min | 3 tasks | 34 files |
| Phase 01 P04 | 8min | 2 tasks | 12 files |
| Phase 01 P05 | 22 min | 2 tasks | 11 files |
| Phase 01 P06 | 22 min | 3 tasks | 20 files |
| Phase 01 P07 | 22 min | 3 tasks | 35 files |
| Phase 02 P01 | 8 min | 3 tasks | 8 files |
| Phase 02 P02 | 4 min | 2 tasks | 3 files |
| Phase 02 P03 | 15 min | 3 tasks | 6 files |
| Phase 02 P04 | 15 min | 2 tasks | 7 files |
| Phase 02 P05 | 22 min | 3 tasks | 10 files |
| Phase 02 P06 | 15 min | 2 tasks | 5 files |
| Phase 02 P07 | 22 min | 3 tasks | 13 files |
| Phase 02 P08 | 32 min | 3 tasks | 10 files |
| Phase 02 P09 | 20 min | 2 tasks | 8 files |
| Phase 02 P10 | 17 min | 2 tasks | 7 files |
| Phase 02 P11 | 212 min | 8 tasks | 21 files |
| Phase 03 P01 | 21 min | 3 tasks | 18 files |
| Phase 03 P02 | 8 min | 2 tasks | 4 files |
| Phase 03 P03 | 9 min | 2 tasks | 3 files |
| Phase 03 P04 | 8 min | 3 tasks | 7 files |
| Phase 03 P05 | 5 min | 2 tasks | 3 files |
| Phase 03 P06 | 13 min | 3 tasks | 10 files |
| Phase 03 P07 | 10 min | 3 tasks | 8 files |
| Phase 03 P08 | 5 min | 3 tasks | 5 files |
| Phase 03 P09 | 13 min | 3 tasks | 6 files |
| Phase 03 P10 | 13 min | 3 tasks | 12 files |
| Phase 05 P01 | 28 min | 3 tasks | 17 files |
| Phase 05 P02 | 20 min | 3 tasks | 12 files |
| Phase 05 P03 | 10 min | 3 tasks | 8 files |
| Phase 05 P04 | 26 min | 3 tasks | 12 files |
| Phase 05 P05 | 8 min | 2 tasks | 5 files |
| Phase 05 P06 | 6 min | 2 tasks | 4 files |
| Phase 05 P07 | 9min | 2 tasks | 3 files |
| Phase 05 P08 | 13min | 3 tasks | 7 files |
| Phase 05 P09 | 7min | 2 tasks | 3 files |
| Phase 05 P10 | 20 | 3 tasks | 13 files |
| Phase 05 P11 | 10min | 3 tasks | 6 files |
| Phase 05 P12 | 11 min | 3 tasks | 8 files |
| Phase 06 P01 | 47 min | 3 tasks | 22 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Ranking (Phase 5) precedes tailoring (Phase 6) — tailoring consumes the requirement gaps ranking produces.
- [Roadmap]: Scheduling is late (Phase 8) on purpose — a cron job over an unstable pipeline hides failures.
- Phases 01–03 decisions are archived in their phase SUMMARYs (`.planning/phases/0{1,2,3}-*/`); this section now tracks only what Phase 4 onward still needs.
- [Phase 03]: `opencode_model` default is `minimax-m3` — the previous default was rejected upstream with HTTP 400 on a forced tool call; `KNOWN_FORCED_TOOL_CHOICE_INCOMPATIBLE_MODELS` guards only the shipped default, and an operator stays free to configure any model.
- [Phase 03]: `DEFAULT_DENY_RULES` is order-enforced — the catch-all deny stays first and the server-internal `StructuredOutput` carve-out follows it, evaluated last-match-wins; reordering fails a default-lane test.
- [Phase 03]: the wire contract is pinned in `app/llm/contract.py` (`format` / `info.structured`, no adaptive fallback) and a `@pytest.mark.live` lane diffs the live `/doc` against the committed fixture, so an opencode upgrade fails loudly instead of silently corrupting structured output.
- [Phase 03]: a structured-output failure persists its differential cause on `llm_calls.error`, distinguishing "the ruleset did not grant the tool" from "the grant survived but the model emitted no tool part" — and it survives a page reload with no new column.
- [Phase 04]: the CV is modeled as structured data with stable enumerated IDs, never free-text `.tex` from the model — fabrication becomes structurally impossible, and escaping is centralised at one non-bypassable Jinja `finalize` choke point with a committed golden baseline that renders byte-identically.
- [Phase 04]: Tectonic is the LaTeX engine, pinned by version **and** SHA256 with the package cache primed at image build; the container's offline compile of the committed fixture passed 10/10 and the installed binary's own `--help` confirmed the argv flags (D-75).
- [Phase 04]: the `latex` pytest lane is collected-but-skipped in the hermetic pass by design (D-69) — a skipped lane is **not** a pass, so engine-dependent claims stay recorded as UNRUN rather than rounded up.
- [Phase 04]: engine ceilings are Settings fields (`latex_probe_timeout_seconds`, `latex_log_tail_chars`), not module constants, so the container and `.env` can tune them.
- [Phase 05]: Phase 05: the ranking call writes exactly one llm_calls row per call (success and failure) — D-12 audit plus the rows plan 05-02's spend caps count
- [Phase 05]: Phase 05: factor_scores_json stores only sub-scores >= 0.0; a negative value is the absent convention, so an all-sentinel response stores {}
- [Phase 05]: Phase 05: the queue's displayed total is computed on read under the CURRENT weights; scores.total_score stays an audit snapshot (D-100)
- [Phase 05]: Phase 05: both ranking spend ceilings are measured from the single llm_calls ledger; a refusal writes one budget_exceeded row because the table has no error_kind column
- [Phase 05]: Phase 05: the rolling-24h ranking cap reads llm_calls.created_at with an accepted full scan; no index migration
- [Phase 05]: Phase 05: ranking is optional via Settings.ranking_enabled plus the fact-store absent/unreadable state; start-or-skip single-flight, no persistent job queue
- [Phase 05]: Phase 05: the detail page reuses queue_repo.read_row so it cannot drift from the queue row, and never recomputes the total in the route
- [Phase 05]: Phase 05: an unscored listing renders a not-yet-ranked state with no score region; a dropped factor renders 'no data', never zero
- [Phase 05]: Phase 05: the queue's default order is the read-time total descending with unscored last; sort=recent retains the phase-one order; the score sort wins over bm25 when q is set
- [Phase 05]: Phase 05: ?min_score= is a view-only threshold that stores nothing and always keeps an unscored listing visible (D-98)
- [Phase 05]: Phase 05: the weights editor writes one ranking_config document and re-derives the queue with zero llm_calls rows (success criterion 3)
- [Phase 05]: Phase 05: the score ordering is a Python-side sort over a bounded scan; the upgrade path is a materialised total column
- [Phase 05]: Phase 05: the ranking strip's two numbers come from ONE run — `ranked_count` over that run's own `reason_counts_json['survivors']` (`RunSummary.candidate_count`) — never this request's page total; an absent count degrades to the numerator alone
- [Phase 05]: Phase 05: `_optional_int` is a separate helper from `_int` — for a value a surface divides BY, an absent/non-numeric value stays `None` rather than coercing to a fabricated `0`
- [Phase 05]: Phase 05: `load_facts` catches `(OSError, UnicodeError)` and re-raises a path-qualified `CvFactStoreError`, so a non-decodable `cv.yaml` is one typed failure at the shared reader — the fix belongs there, not in `rank.py`'s guard, and Phase 6 tailoring inherits it
- [Phase 05]: Phase 05: the unreadable fact store reuses D-94's existing `fact_store_absent` skip reason (same operator-visible situation), now pinned by an asserted `pipeline.rank_skipped` event rather than inferred from the absence of rows
- [Phase 05]: 05-07: a non-positive candidate count is not a denominator — excluded at the run read boundary (run_repo._optional_int), with a truthiness gate at the render site
- [Phase 05]: Phase 05: a ranking pass's outcome is persisted as reason_counts_json['ranking'] by _finish (the sole writer), while the live 'running' state is derived at render time from the in-process task and never persisted
- [Phase 05]: Phase 05: the four ranking skip reasons (ranking_disabled/fact_store_absent/ranking_in_flight/rank_start_failed) have exactly one definition in app/pipeline/rank.py (RANK_SKIP_* + RANK_SKIP_LABELS), read by the guard, the precheck and the render layer
- [Phase 05]: Phase 05: the job detail page names the last run's ranking state (reusing RunSummary.ranking_state) and, on the fact-store skip, discloses the exact loader path (Settings.cv_dir + rank.CV_FILENAME) with a /settings pointer
- [Phase 05]: 05-10: one total fact_store_report(path) probe (available/path/error, class name only) is shared by the Settings CV card, the queue status line and /health, so the three cannot disagree about the path or the load outcome
- [Phase 05]: 05-10: the /health cv object carries path, not version (a fact store is a data document); a missing store is reported and never degrades status, mirroring the tectonic rule
- [Phase 05]: 05-10: every disclosed path is str(Path(settings.cv_dir) / rank.CV_FILENAME) — the expression the loader uses — and the copy says 'no readable CV fact store', never 'missing file' (D-94 covers absent/unreadable/non-decodable)
- [Phase 05]: The pager renders on every non-empty queue page, not gated on has_more, so the position line shows the server-fixed page size even for a single-page queue
- [Phase 05]: No htmx history/URL-push for paging: a fragment URL in browser history reloads as a bare fragment, so the in-page Previous control is the backward affordance
- [Phase 05]: QueuePage's four page accessors are pure derivations of offset/limit/total with max(1, limit) guards, so a degenerate instance cannot 500 the queue
- [Phase 05]: 05-12: the action surface is an allow-listed hidden field (ACTION_SURFACES = queue|detail), not the htmx HX-Target header — explicit, travels with event_type, pinnable from the test client
- [Phase 05]: 05-12: one shared _action_forms.html defines the Save/Hide controls for both the queue row and the detail section, so the target drift that shipped G-05-8 is structurally impossible
- [Phase 05]: 05-12: the same POST /listings/{id}/events returns a surface-aware fragment (row or detail section); no second route, so the write and the re-render cannot drift
- [Phase 05]: 05-12: saved discoverability is a link to the existing saved view (?saved=1) plus a projected state indicator, never a recomputed count that could disagree with read_queue
- [Phase 06]: Phase 06: the tailoring patch is a typed operation over enumerated fact IDs — no field of TailoringPatch becomes PDF text, so even a successful prompt injection cannot reach the renderer
- [Phase 06]: Phase 06: an empty patch and patch=None are both the identity RenderPlan, preserving the three shipped no-argument apply_patch(facts) callers byte-for-byte
- [Phase 06]: Phase 06: reweight is within-entry ordering (declaration-order stable sort by weight DESC, unreweighted default 1.0), demote is lowest prominence in declaration order, move is the explicit positional override applied after base ordering
- [Phase 06]: Phase 06: the tailoring call shares the rolling-24h ceiling through a purpose-aware calls_since and the rank reserve-then-call lock; no per-run tailoring ceiling and no new numeric ceiling (O1)
- [Phase 06]: Phase 06: a Layer-1 fail short-circuits before the engine and writes a blocked cv_artifacts row with NULL paths; the ok-only repository selection is the artifact-access control (D-115/D-118)

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1] Blocking unknown #2 — scrape survival at personal scale is unmeasured; the Phase 1 probe answers it and re-ranks Adzuna from hedge to primary if LinkedIn/Indeed fail.
- [Phase 4] Blocking unknown #1 — the real `.tex` is **not in this repo**; `.tex → cv.yaml` import cost and Tectonic bundle coverage remain unmeasured **for the real document**. Stays **open**, now with a named trigger: place the document at `cv/base.tex`, run `bash scripts/cv-tex-spike.sh`, and record the counts in `docs/probes/2026-09-21-cv-tex-spike.md` (`cv-tex-spike`), whose `UNRESOLVED` section names the exact checks (real-document decomposition, per-package bundle search, the engine's own flag names). Hard gate before Phase 6 is estimated.
- [Phase 3] Advisory, non-blocking — session-handshake failures report `attempts=0` and drop the resolved D-12 identity; the generic failure handler persists a raw exception class name as `error_kind`, outside the D-52 taxonomy; the differential cause can over-attribute on an empty `parts` list. Code review 03: 0 Critical / 3 Warning / 5 Info (`/gsd-code-review 03 --fix`).
- [Phase 3] Security enforcement is enabled but no `03-SECURITY.md` exists — run `/gsd-secure-phase 03` before advancing if the threat model matters here.
- [Phase 5] No real CV fact store exists yet, so a ranking pass takes the documented `fact_store_absent` skip — the ranking path is exercised end-to-end only once a `cv.yaml` is supplied. The skip and the exact loader path are now disclosed on `/settings`, the queue and `/health` (05-10), so this reads as a missing prerequisite, not a silent failure.
- [Phase 5] Code review round 4 (`05-REVIEW.md`) reports `issues_found` on the 05-12 detail-action delta: 0 Critical / 1 Warning / 3 Info — run `/gsd-code-review 05 --fix` if the warning matters before Phase 6 reuses the action-surface pattern.

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-09-24T16:26:19.740Z
Stopped at: Completed 06-01-PLAN.md
Resume file: None
