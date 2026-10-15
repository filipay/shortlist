# Shortlist

> Working title — rename freely once branding matters.

## What This Is

A local, self-hosted job-search pipeline for the author and a few friends. It
aggregates listings from pluggable sources (LinkedIn and Indeed first), cuts them
down with deterministic rules, ranks the survivors with an LLM against the user's
CV and stated preferences, produces an honest tailored CV per job, and exposes a
web UI to browse, review, and track applications.

It exists to replace the daily dead time of manually checking portals, reading
every listing, judging fit from scratch, and hand-editing a CV — turning that loop
into one ranked, review-ready queue. The human stays in the loop at the point that
matters: they review the draft and press submit themselves.

## Core Value

Every morning there is one ranked, explained, apply-ready queue of jobs worth
considering — so the search→judge→tailor loop costs minutes instead of hours.

If everything else fails, this must work: listings come in, get filtered, get
scored against the user's CV with a reason attached, and land in a queue the user
can act on. Every other feature is downstream of that.

**Still the right priority after v1.0** — the shipped pipeline delivers exactly this
end to end, and every later direction (hosted deployment, OAuth, Adzuna promotion,
an MCP surface) is downstream of keeping the queue trustworthy and cheap.

## Current State

**Shipped: v1.0 MVP (2026-10-15).** All nine phases (1–8 plus the inserted 07.1)
complete; 82 plans, 203 tasks, 74/74 v1 requirements verified.

- **Scale:** ~77,300 lines of Python (~29k `app/`, ~48k `tests/`), 678 files
  changed over 30 days (2026-09-15 → 2026-10-15).
- **Stack:** FastAPI + Jinja2/HTMX/Alpine + Tailwind 4; SQLite (WAL) + SQLAlchemy
  2.0 + Alembic (head 0008); APScheduler 3.11.3 for the daily run; Tectonic 0.17.0
  for LaTeX→PDF; the opencode **V2** HTTP API (pinned 2.0.26) as the LLM backend;
  JobSpy + Adzuna adapters; single Docker container.
- **What works end to end:** ingest → dedup → deterministic filtering → FTS5 queue
  → six-factor CV-grounded ranking → typed-patch tailoring with an 11-check
  two-layer verifier → assisted apply + append-only tracker → a daily scheduled run
  and a `/status` self-report.

### Known debt carried out of v1.0

- The real `.tex` is **not in this repo** — `.tex → cv.yaml` import cost and Tectonic
  bundle coverage stay unmeasured for the *real* document (STATE.md blocking
  unknown #1; trigger: place it at `cv/base.tex`, run `scripts/cv-tex-spike.sh`).
- No real CV fact store is committed, so ranking takes the documented
  `fact_store_absent` skip until a `cv.yaml` is supplied.
- Verification fingerprints for phases 1–8 are `stale` at the milestone boundary
  (later phases legitimately edited shared `covered_files`); closed with an explicit
  override, not by rewriting the digests.
- 22 audit items acknowledged at close (7 debug sessions, 2 quick tasks, 2 seeds,
  2 todos, 3 UAT gaps, 6 deferred items) — see STATE.md `## Deferred Items`.
- Residual: opencode V2 has no `system` field, so an accepted prompt-injection risk
  applies (fabrication is still structurally blocked); blocking-warning on the
  Tailwind build guard in a Node-less environment.

## Requirements

### Validated (v1.0)

- ✓ **SRC-01 … SRC-10** — Pluggable source-adapter architecture with LinkedIn and
      Indeed adapters, a consent/ToS-audit record, and a recorded scraper-survival
      probe verdict (Phase 1).
- ✓ **QUEUE-01 … QUEUE-09** — Exact + fuzzy dedup with a reversible dupe audit,
      FTS5 search, save/hide as append-only events, new/stale derivation, and two-way
      pagination (Phases 1–2).
- ✓ **CRIT-01 … CRIT-03** — Version-stamped named search criteria, a capability
      pre-run report, and per-search "run this one" (Phase 2).
- ✓ **FILT-01 … FILT-04** — Deterministic hard-rule filtering applied before any LLM
      spend, with the fired rule and reason recorded for every exclusion (Phase 2).
- ✓ **RANK-01 … RANK-08** — Six-factor CV-grounded ranking with stored sub-scores, a
      read-time total, a grounded rationale and named gaps, absolute per-listing
      scoring, plus per-run and rolling-24 h spend caps (Phase 5).
- ✓ **CV-01 … CV-06** — `cv.yaml` fact store with stable enumerated IDs, a
      byte-deterministic renderer behind one escape choke point, pinned Tectonic, and
      a fact-equivalence lane with its mutation control (Phase 4).
- ✓ **TAIL-01 … TAIL-08** — A typed reorder/re-weight/demote/drop patch over
      enumerated IDs, preview with change log before compile, and an 11-check
      two-layer verification gate that blocks rather than repairs (Phase 6).
- ✓ **APPLY-01 … APPLY-06** — An `ok`-artefact-gated apply package, deterministic
      grounded screening-answer drafting, an append-only application tracker linked
      to the exact verified artefact, and no submit path anywhere (Phase 7).
- ✓ **RUN-01 … RUN-07** — Manual run trigger and a daily APScheduler run with
      overlap guard and durable skip record, run history, a `/status` self-report, and
      a guarded manual prune (Phases 1–2, 8).
- ✓ **UI-01 … UI-07** — Ranked queue browse, job detail fit breakdown, criteria and
      weights editors, CV preview/download, tracker, phone-breakpoint reflow with
      vendored assets (Phases 5–8).
- ✓ **PLAT-01 … PLAT-06** — No credential path anywhere, a `current_user` auth seam,
      opencode as a sibling service with a pinned structured-output contract, the V2
      HTTP migration, and a container that runs the daily schedule on `Europe/Dublin`
      (Phases 1, 3, 8).

### Active

None yet — the next milestone's requirements are defined fresh via
`/gsd-new-milestone`.

### Out of Scope

- Unattended full-auto application submission — account-ban risk on
  LinkedIn/Indeed and poor application quality; the user explicitly chose
  assisted apply
- Authentication and multi-tenancy in v1 — the user already runs Authentik and
  wants OAuth as a later feature, not a v1 cost
- Public internet exposure — v1 is local-only Docker; web exposure is a future
  milestone
- MCP server exposing the tool to opencode conversationally — valuable, but
  deferred to a future feature per the user
- Fabricating, embellishing, or inflating CV content — ethical hard line. The tool
  reorders, re-weights, suggests, and flags; it never invents
- Email/notification digests — not requested for v1
- A hosted SaaS for strangers — "me and my friends" is the ceiling for now

## Next Milestone Goals

Not yet defined. Candidate directions surfaced during v1.0 (pick and shape via
`/gsd-new-milestone`):

- **Real CV onboarding** — close blocking unknown #1: import the real `.tex` into
  `cv.yaml` and measure Tectonic bundle coverage against the real preamble.
- **Adzuna promotion** (SRC-11) — the Phase 1 probe verdict re-ranks Adzuna from
  hedge to primary; the adapter seam makes this a config/priority change.
- **Authentik OAuth** — the `current_user` seam exists and was deliberately kept
  cheap; this is the natural first v1.x credential feature.
- **Hosted deployment** — portability was a design constraint from day one (DSN swap
  to Postgres, FTS variant, advisory-lock scheduling).
- **Settings model picker** — the deferred D-146 seam (`discover_models` was
  retargeted to V2 in 07.1 precisely for this).

## Context

- **User situation**: the author is actively job hunting. The trigger for this
  project is the tedium of checking portals, evaluating each listing, adjusting a
  CV, and applying — repeated daily across multiple sites.
- **Environment**: the user is Europe/Dublin based and already runs Home Assistant
  (`/workspace`) with a `compose.yml`. Docker is familiar territory. The work in
  this repo is deliberately isolated at `/workspace/job-search/` so it does not
  touch the HA project.
- **CV**: the source of truth is a LaTeX (`.tex`) document, but the real document is
  not yet in this repo. The structured `cv.yaml` fact store is the tailoring
  substrate; the `.tex`→`cv.yaml` spike is bounded and awaiting the real file.
- **LLM**: the user runs opencode and reuses it rather than a second provider key.
  As of opencode 2.0.26 the V1 root routes are dead and **auth is required in
  practice** (a freshly generated server password on every start); the app targets
  the V2 HTTP API with runtime surface detection and a retained dual-support lane.
- **Prior art**: surveyed before building (Resume-Matcher, TailorCV, resumorph,
  tailit). Verdict was conditional greenfield: reuse JobSpy/Tectonic, pattern-copy
  the anti-fabrication design, build the pipeline and LaTeX-CV tailoring ourselves.
- **Known hard problem — resolved for v1**: LinkedIn and Indeed are hostile to
  automation; the Phase 1 probe retired this as a *measurement*, and applying stayed
  assisted-only with scraping validated before it became load-bearing.

## Constraints

- **Tech stack**: Python-first backend — the scraping, LLM, PDF/LaTeX, and
  scheduling ecosystems are strongest there, and the user selected it explicitly.
- **CV source format**: LaTeX. Tailoring must operate on `.tex` and compile to PDF.
- **LLM backend**: opencode (`serve` preferred, CLI fallback). No second provider
  key should be required for v1.
- **Deployment**: Docker container on a local machine. Must remain portable to a
  hosted deployment later without a rewrite.
- **Legal / ToS**: LinkedIn and Indeed actively detect and ban automation. This is
  why applying is assisted-only and why scraping approach must be validated before
  it becomes load-bearing.
- **Privacy**: CVs and personal job-search data are sensitive. Everything runs
  locally for v1; no third party sees the user's CV content.
- **Auth**: none in v1. The code does not architecturally block adding Authentik
  OAuth later (the `current_user` seam), and does not pay for it now.
- **Cost**: LLM calls are the dominant variable cost. Hard-rule filtering before
  ranking and the reserve-then-call spend caps are deliberate cost controls.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Assisted apply, not full auto-submit | Avoid LinkedIn/Indeed account bans and low-quality mass applications; user chose it deliberately | ✓ Good — shipped in Phase 7: the apply package and every answer surface are copy-only, with a test that fails if any submit path is added |
| LaTeX as the CV source and tailoring target | Templates and recompiles cleanly; avoids brittle PDF/DOCX manipulation | ✓ Good — shipped in Phases 4 & 6 |
| opencode as the LLM backend | Reuses the user's existing opencode setup and models; no second provider or key to manage | ✓ Good — validated in Phase 3; migrated to the V2 HTTP API in 07.1 |
| Pin the opencode wire contract and guard it with a live contract test | The HTTP API is evolving and structured output is load-bearing; a silently changed wire shape would corrupt results. Pin the version plus a live `/doc`-equivalent diff so an upgrade fails loudly | ✓ Good — shipped in Phase 3 (`PLAT-05`) and retargeted to V2 in 07.1 |
| Pluggable source adapters from day one | User wants LinkedIn/Indeed first but intends to add sources; bolting this on later would be a rewrite | ✓ Good — shipped in Phase 1 (adapter port + extensibility proof); Adzuna remains a config-level hedge |
| Rules filter before LLM ranking | Caps LLM spend and makes results explainable; user selected this over pure LLM scoring | ✓ Good — shipped in Phase 2 (FILT-*), with the fired rule recorded per exclusion |
| No auth in v1 | Keeps first implementation small; Authentik OAuth is an explicit later feature | ✓ Good — no auth shipped; the `current_user` seam keeps the later addition cheap |
| Python-first stack | Best ecosystem fit for scraping, LLM orchestration, LaTeX compilation, and scheduling | ✓ Good — shipped |
| Docker for local deployment | One-command access locally, and a path to hosted deployment without repackaging | ✓ Good — single container, `--workers 1` |
| Conditional greenfield — confirmed by the Resume-Matcher spike | Prior art (Resume-Matcher, 28.4k★, Apache-2.0) covers the CV half but breaks three of the four differentiators: HTML→Chromium output, no opencode-compatible LLM path, and no ingestion. Its anti-fabrication policy is repair-not-block — the opposite of ours. Verdict: pattern-copy | ✓ Good |
| Never fabricate CV content | Ethical hard line; tailoring is reorder/re-weight/suggest/flag only | ✓ Good — shipped in Phases 4 & 6: fabrication is structurally impossible and the verifier blocks rather than repairs |
| Model the CV as structured data (enumerated IDs), never free-text `.tex` from the LLM | Makes fabrication structurally impossible — the model can only reorder and re-weight real bullet IDs; the renderer stays deterministic and testable | ✓ Good — shipped in Phase 4 (`app/domain/cv.py`, one Jinja `finalize` escape choke point, byte-identical golden baseline) |
| Tectonic as the LaTeX engine, pinned by version and SHA256, with the package cache primed at image build | ~124 MB vs multi-GB TeX Live, auto-fetches packages, and a pinned digest makes a swapped binary fail the build rather than silently change output | ✓ Good — validated in Phase 4 (offline compile 10/10; D-75) |
| Ranking is one `complete_structured` call per listing, with requirement extraction co-located in that same call | Batching would make each score relative to its batch and break the absolute-score/stability requirement; folding extraction in removes a second call per listing | ✓ Good — validated in Phase 5: RANK-07 stability held across repeated live-model runs |
| Ranking spend caps are reserve-then-call, measured from the single `llm_calls` ledger, with two independent `Settings` ceilings (per-run and rolling-24 h) | The ledger is already the audit record, so the caps cannot drift from actual spend; refusing *before* the request is what makes a cap a cap | ✓ Good — shipped in Phase 5 (RANK-08): a refusal writes one `budget_exceeded` row and no request is made |
| The queue's displayed total is computed on read under the current weights; `scores.total_score` stays an audit snapshot | A weight edit re-derives the whole ranking with zero LLM calls, while the stored score remains the record of what the model produced | ✓ Good — shipped in Phase 5 (D-100) |
| Verification blocks, never repairs, and artefacts are gated on an `ok` status | "Repair pressure is fabrication pressure"; an `ok`-only SQL predicate keeps a blocked/failed artefact unreachable even by id | ✓ Good — shipped in Phases 6 & 7 (D-115/D-118/D-121) |
| Migrate the LLM backend to the opencode V2 HTTP API with runtime surface detection and a retained V1 lane | The pinned V1 contract died on opencode 2.0.26 (root routes serve SPA HTML, `POST /session` is a hard 405); dual-support with detection keeps a V1 server working byte-identically | ✓ Good — shipped in Phase 07.1 (D-147/D-148); auth is required in practice on 2.0.26 (D-136 corrected) |
| Schedule in-process with APScheduler 3.11.3, one persistent job store, `max_instances=1` | No broker for one nightly job; persistence survives restarts; a single worker is pinned so the job cannot run N times | ✓ Good — shipped in Phase 8 (RUN-05), with `Europe/Dublin` proven at build time |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-15 after v1.0 milestone — v1.0 MVP shipped: all nine phases complete (82 plans, 203 tasks, 74/74 requirements verified). The full loop works end to end (ingest → dedup → filter → rank → tailor → verify → assisted apply → track → schedule). Next milestone requirements are defined fresh via `/gsd-new-milestone`.*
