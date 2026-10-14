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

## Requirements

### Validated

- ✓ **PLAT-02** — The LLM is reached through opencode as a sibling service with no
      second provider key required (Phase 3). A real schema-constrained call completes
      through `opencode serve` end to end on the shipped default model.
- ✓ **PLAT-05** — The opencode structured-output contract is covered by a test that
      fails loudly on an upgrade (Phase 3). The `@pytest.mark.live` lane diffs the
      live `/doc` spec against the pinned fixture, so a wire-shape change surfaces
      immediately rather than silently corrupting structured output.
- ✓ **RANK-01, RANK-02, RANK-03** — Every surviving listing is scored against the CV
      using named, inspectable factors; the per-factor sub-scores are stored and the
      total is computed in code under the current weights (Phase 5). The queue's
      displayed total is derived on read, so a weight change re-derives the ranking
      with zero LLM calls.
- ✓ **RANK-04** — The user can adjust factor weights from the UI and see rankings
      re-derive without a new LLM call (Phase 5). Weights persist as one
      `ranking_config` document (migration 0004).
- ✓ **RANK-05, RANK-06** — Each ranked listing carries a rationale grounded in stored
      evidence, and the job detail view shows a requirement-by-requirement fit
      breakdown with named gaps (Phase 5).
- ✓ **RANK-07** — Scoring is absolute per listing and stable across repeated runs —
      one `complete_structured` call per listing, never a relative ranking of a batch
      (Phase 5); confirmed against the live model at UAT.
- ✓ **RANK-08** — LLM spend is capped per run and per rolling 24 h, refused *before*
      the call is made, measured from the single `llm_calls` ledger (Phase 5).
- ✓ **UI-01, UI-02, UI-03** — The web UI browses the ranked queue, opens a job detail
      showing the fit breakdown and ranking rationale, and edits search criteria and
      ranking weights (Phase 5).

### Active

- [ ] Pluggable source-adapter architecture that can aggregate listings from
      multiple job portals with a shared normalized listing schema
- [ ] LinkedIn and Indeed adapters implemented as the first two sources
- [ ] User-defined search criteria (role/keywords, location, remote, salary floor,
      seniority, excluded terms) stored and editable
- [ ] Deterministic hard-rule filtering applied before any LLM spend
- [ ] LaTeX-CV tailoring per listing: reorder and re-weight existing content,
      suggest adjustments, and flag gaps — never fabricate experience, employers,
      dates, or skills
- [ ] Assisted apply: generate the tailored CV PDF and pre-fill application
      material for the user to review and submit themselves
- [ ] Web UI: application tracker (applied / interviewing / rejected / etc.)
- [ ] Web UI: preview the tailored CV and download the compiled PDF
- [ ] Manual "run search now" trigger plus scheduled runs (e.g. daily)
- [ ] Runs as a Docker container locally for easy access

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

## Context

- **User situation**: the author is actively job hunting. The trigger for this
  project is the tedium of checking portals, evaluating each listing, adjusting a
  CV, and applying — repeated daily across multiple sites.
- **Environment**: the user is Europe/Dublin based and already runs Home Assistant
  (`/workspace`) with a `compose.yml`. Docker is familiar territory. The work in
  this repo is deliberately isolated at `/workspace/job-search/` so it does not
  touch the HA project.
- **CV**: the source of truth is a LaTeX (`.tex`) document. This is a favourable
  starting point — tailoring can template and recompile a clean PDF rather than
  fighting a binary format.
- **LLM**: the user runs opencode and wants to reuse it rather than manage a second
  provider key. `opencode serve` (HTTP) is the primary integration shape; shelling
  out to the opencode CLI is an acceptable fallback.
- **Prior art**: the user explicitly asked that existing solutions be surveyed
  before building anything, so the research phase is expected to surface prior-art
  tools, what they do well, and where they fall short.
- **Known hard problem to resolve in research**: LinkedIn and Indeed are the
  primary requested sources *and* the most hostile to automation. Whether adapters
  can use official APIs, permitted feeds, or must scrape — and what the resulting
  reliability and legal posture is — must be settled before implementation, not
  discovered late.

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
- **Auth**: none in v1. The code should not architecturally block adding Authentik
  OAuth later, but must not pay for it now.
- **Cost**: LLM calls are the dominant variable cost. Hard-rule filtering before
  ranking is a deliberate cost-control measure, not an optimisation to skip.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Assisted apply, not full auto-submit | Avoid LinkedIn/Indeed account bans and low-quality mass applications; user chose it deliberately | — Pending |
| LaTeX as the CV source and tailoring target | Templates and recompiles cleanly; avoids brittle PDF/DOCX manipulation | — Pending |
| opencode as the LLM backend | Reuses the user's existing opencode setup and models; no second provider or key to manage | ✓ Good — validated in Phase 3: a real schema-constrained call completes end to end through `opencode serve` with no second provider key |
| Pin the opencode wire contract and guard it with a live contract test | The opencode HTTP API is still evolving (a `format` vs `outputFormat` inconsistency exists today) and structured output is load-bearing for ranking and tailoring; a silently changed wire shape would corrupt results instead of failing. Pinning the server version plus a `@pytest.mark.live` `/doc` diff makes an upgrade fail loudly | ✓ Good — shipped in Phase 3 (`PLAT-05`); lane is deselected by default and run by the operator |
| Pluggable source adapters from day one | User wants LinkedIn/Indeed first but intends to add sources; bolting this on later would be a rewrite | — Pending |
| Rules filter before LLM ranking | Caps LLM spend and makes results explainable; user selected this over pure LLM scoring | — Pending |
| No auth in v1 | Keeps first implementation small; Authentik OAuth is an explicit later feature | — Pending |
| Python-first stack | Best ecosystem fit for scraping, LLM orchestration, LaTeX compilation, and scheduling | — Pending |
| Docker for local deployment | One-command access locally, and a path to hosted deployment without repackaging | — Pending |
| Conditional greenfield — confirmed by the Resume-Matcher spike | Prior art (Resume-Matcher, 28.4k★, Apache-2.0) covers the CV half but breaks three of the four differentiators: HTML→Chromium output (its "LaTeX" is a React/CSS theme), no opencode-compatible LLM path, and no ingestion. Its anti-fabrication policy is repair-not-block — the opposite of ours. Verdict: pattern-copy | ✓ Good |
| Never fabricate CV content | Ethical hard line; tailoring is reorder/re-weight/suggest/flag only | — Pending |
| Model the CV as structured data (enumerated IDs), never free-text `.tex` from the LLM | Makes fabrication structurally impossible — the model can only reorder and re-weight real bullet IDs, so it cannot invent an employer or skill the schema does not have; the renderer stays deterministic and testable | ✓ Good — shipped in Phase 4: `app/domain/cv.py` carries stable enumerated IDs, escaping is centralised at one non-bypassable Jinja `finalize` choke point, and the committed golden baseline renders byte-identically |
| Tectonic as the LaTeX engine, pinned by version and SHA256, with the package cache primed at image build | ~124 MB vs multi-GB TeX Live, auto-fetches packages, and a pinned digest makes a swapped binary fail the build rather than silently change output | ✓ Good — validated in Phase 4: the container's offline compile of the committed fixture passed 10/10 and the installed binary's own `--help` confirmed the argv flags (D-75) |
| Ranking is one `complete_structured` call per listing, with requirement extraction co-located in that same call | Batching would make each score relative to its batch and break the absolute-score/stability requirement; folding extraction in removes a second call per listing | ✓ Good — validated in Phase 5: RANK-07 stability held across repeated live-model runs |
| Ranking spend caps are reserve-then-call, measured from the single `llm_calls` ledger, with two independent `Settings` ceilings (per-run and rolling-24 h) | The ledger is already the D-12 audit record, so the caps cannot drift from actual spend; refusing *before* the request is what makes a cap a cap | ✓ Good — shipped in Phase 5 (RANK-08): a refusal writes one `budget_exceeded` row and no request is made |
| The queue's displayed total is computed on read under the current weights; `scores.total_score` stays an audit snapshot | A weight edit re-derives the whole ranking with zero LLM calls (success criterion 3), while the stored score remains the record of what the model actually produced | ✓ Good — shipped in Phase 5 (D-100); the score sort is a Python-side bounded scan, with a materialised total column as the upgrade path |

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
*Last updated: 2026-10-14 after Phase 6 (Tailoring + Verification) — the tail of the pipeline is closed: a tailored CV is generated as a typed patch over enumerated IDs, previewed with its change log before compiling, and gated on the compiled PDF — a CV that fails verification is blocked outright, never auto-repaired. Phases 1-7 (including the inserted 07.1 opencode V2 migration) are complete; Phase 8 (Operations + Polish) is next*
