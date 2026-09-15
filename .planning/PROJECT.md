# Job Search Copilot

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

(None yet — ship to validate)

### Active

- [ ] Pluggable source-adapter architecture that can aggregate listings from
      multiple job portals with a shared normalized listing schema
- [ ] LinkedIn and Indeed adapters implemented as the first two sources
- [ ] User-defined search criteria (role/keywords, location, remote, salary floor,
      seniority, excluded terms) stored and editable
- [ ] Deterministic hard-rule filtering applied before any LLM spend
- [ ] LLM ranking of surviving listings against the user's CV and preferences,
      with a per-listing score and a human-readable rationale
- [ ] Fit breakdown for a listing: requirement-by-requirement match and explicit
      gaps between the user's CV and the role
- [ ] LaTeX-CV tailoring per listing: reorder and re-weight existing content,
      suggest adjustments, and flag gaps — never fabricate experience, employers,
      dates, or skills
- [ ] Assisted apply: generate the tailored CV PDF and pre-fill application
      material for the user to review and submit themselves
- [ ] Web UI: browse ranked jobs
- [ ] Web UI: job detail with fit breakdown and ranking rationale
- [ ] Web UI: edit search criteria and ranking weights
- [ ] Web UI: application tracker (applied / interviewing / rejected / etc.)
- [ ] Web UI: preview the tailored CV and download the compiled PDF
- [ ] Manual "run search now" trigger plus scheduled runs (e.g. daily)
- [ ] Runs as a Docker container locally for easy access
- [ ] opencode as the LLM backend (via `opencode serve`, CLI as fallback)

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
| opencode as the LLM backend | Reuses the user's existing opencode setup and models; no second provider or key to manage | — Pending |
| Pluggable source adapters from day one | User wants LinkedIn/Indeed first but intends to add sources; bolting this on later would be a rewrite | — Pending |
| Rules filter before LLM ranking | Caps LLM spend and makes results explainable; user selected this over pure LLM scoring | — Pending |
| No auth in v1 | Keeps first implementation small; Authentik OAuth is an explicit later feature | — Pending |
| Python-first stack | Best ecosystem fit for scraping, LLM orchestration, LaTeX compilation, and scheduling | — Pending |
| Docker for local deployment | One-command access locally, and a path to hosted deployment without repackaging | — Pending |
| Conditional greenfield — confirmed by the Resume-Matcher spike | Prior art (Resume-Matcher, 28.4k★, Apache-2.0) covers the CV half but breaks three of the four differentiators: HTML→Chromium output (its "LaTeX" is a React/CSS theme), no opencode-compatible LLM path, and no ingestion. Its anti-fabrication policy is repair-not-block — the opposite of ours. Verdict: pattern-copy | ✓ Good |
| Never fabricate CV content | Ethical hard line; tailoring is reorder/re-weight/suggest/flag only | — Pending |

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
*Last updated: 2026-09-15 after project research and the Resume-Matcher reuse spike (D9 closed: pattern-copy, greenfield confirmed)*
