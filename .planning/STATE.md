---
gsd_state_version: "1.0"
current_phase: 05
current_phase_name: Ranking — CORE VALUE
status: executing
stopped_at: Completed 05-01-PLAN.md
last_updated: "2026-09-22T12:11:10.990Z"
last_activity: 2026-09-22
last_activity_desc: Phase 05 execution started
state_head: 443eddd7c823148f800d0afd3c0172090524b2d0
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 37
  completed_plans: 34
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-21)

**Core value:** Every morning there is one ranked, explained, apply-ready queue of jobs worth considering — so the search→judge→tailor loop costs minutes instead of hours.
**Current focus:** Phase 05 — Ranking — CORE VALUE

## Current Position

Phase: 05 (Ranking — CORE VALUE) — EXECUTING
Plan: 2 of 4
Status: Ready to execute
Last activity: 2026-09-22 — Phase 05 execution started

Progress: [░░░░░░░░░░] 0%

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

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1] Blocking unknown #2 — scrape survival at personal scale is unmeasured; the Phase 1 probe answers it and re-ranks Adzuna from hedge to primary if LinkedIn/Indeed fail.
- [Phase 4] Blocking unknown #1 — the real `.tex` is **not in this repo**; `.tex → cv.yaml` import cost and Tectonic bundle coverage remain unmeasured **for the real document**. Stays **open**, now with a named trigger: place the document at `cv/base.tex`, run `bash scripts/cv-tex-spike.sh`, and record the counts in `docs/probes/2026-09-21-cv-tex-spike.md` (`cv-tex-spike`), whose `UNRESOLVED` section names the exact checks (real-document decomposition, per-package bundle search, the engine's own flag names). Hard gate before Phase 6 is estimated.
- [Phase 3] RESOLVED by 03-10: the `format` vs `outputFormat` contract is pinned in `app/llm/contract.py` (`format` / `info.structured`, no adaptive fallback) and confirmed by the live schema-constrained call; the deny-ruleset half needed a carve-out for the server-internal `StructuredOutput` tool, now shipped and guarded.
- [Phase 3] Advisory, non-blocking — resolve before Phase 5 routes CV content through the port: session-handshake failures report `attempts=0` and drop the resolved D-12 identity; the generic failure handler persists a raw exception class name as `error_kind`, outside the D-52 taxonomy; the differential cause can over-attribute on an empty `parts` list. Code review 03: 0 Critical / 3 Warning / 5 Info (`/gsd-code-review 03 --fix`).
- [Phase 3] Security enforcement is enabled but no `03-SECURITY.md` exists — run `/gsd-secure-phase 03` before advancing if the threat model matters here.
- [Phase 5] Ranking batching (one call per listing vs per K) and budget-cap semantics are unresolved; decide in the plan.
- [Phase 2] RESOLVED at the end-of-phase UAT (2026-09-17): θ=88 was assessed against the real corpus and retained, and the research 10–15% merge-rate band was judged non-transferable to this market — the blocking key plus the grade guard do the discriminating, which the cross-source-only merge rule then hardened. No longer a blocker for planning.

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-09-22T12:10:54.685Z
Stopped at: Completed 05-01-PLAN.md
Resume file: None
