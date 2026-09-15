# Phase 1: Walking Skeleton + Foundations - Context

**Gathered:** 2026-09-15
**Status:** Ready for planning

<domain>
## Phase Boundary

One `docker compose up` brings up the full walking skeleton: a FastAPI app + SQLite database with **migration 0001 carrying the non-backfillable schema set**, the source-adapter port and registry with LinkedIn and Indeed adapters over a shared JobSpy transport, the ingest path (sanitise → normalise → Tier‑1 upsert), a minimal browseable queue UI with a manual run trigger that executes in the background, per-source health plus a scraper-survival probe, the `current_user` auth seam on every route, and all UI assets vendored locally.

**Requirement scope:** SRC‑01…SRC‑10, QUEUE‑01, QUEUE‑02, QUEUE‑05, RUN‑01, RUN‑02, PLAT‑01, PLAT‑03, PLAT‑04, UI‑07.

**Deliberately NOT in this phase:** Tier‑2 fuzzy dedup/merge + revert (QUEUE‑03/04, Phase 2), criteria CRUD + filter compiler + exclusions UI (CRIT/FILT, Phase 2), FTS search + new/stale badges (Phase 2), any LLM call or ranking (Phases 3/5), tailoring/compile (Phases 4/6), scheduling (Phase 8), phone-layout acceptance (Phase 8).

</domain>

<decisions>
## Implementation Decisions

### Scraper-survival probe & verdict (discussed)
- **D-01:** "Scraping survives" is defined by **explicit numeric signals plus a written verdict** — not one or the other. Signals: per-source `FetchResult.status` outcome distribution, per-field fill-rate vs a recorded baseline, output-count delta vs a trailing average, and freshness. The verdict is human-readable and **must spell out the Adzuna promotion condition** so the decision is actionable at Phase 8.
- **D-02:** Probe traffic stays inside a **config-driven envelope** — `max_requests` / `max_results` / `max_detail_fetches` / `deadline` live in config. Documented personal-scale recommendation: **1 search per board, ≤50–100 results, once per day**. This is the ban-risk line from PITFALLS P2 and must be adjustable without a code change (PLAT‑04).
- **D-03:** The verdict is recorded in **three places**: (a) a dated verdict document committed in the repo; (b) raw evidence rows in `runs` and `source_request_log`; (c) `probe()` status surfaced in `/health` and the per-source health strip. The verdict must be reachable by both a human and the code.
- **D-04:** Phase 1 **records the Adzuna promotion trigger condition only**; no Adzuna adapter is built. Promotion from hedge to primary is decided at Phase 8 against the recorded condition (consistent with SRC‑11 being v2 and with ROADMAP.md's contingency note).

### opencode endpoint & model selection (discussed)
- **D-05:** **No opencode service is defined in `compose.yml`.** The opencode server is user-managed (`opencode serve --hostname 0.0.0.0 --port 4096`) and already running; the app assumes the endpoint is available. The app container must NOT try to own, pin, or start it. — **Reversibility:** reversible — adding a compose service later is additive.
- **D-06:** The app reaches opencode through a configurable **`OPENCODE_BASE_URL`** (default `http://host.docker.internal:4096`, with `extra_hosts: host.docker.internal:host-gateway` on Linux so the default works). Keeping this configurable preserves the "portable to a hosted deployment later without a rewrite" constraint.
- **D-07:** `OPENCODE_SERVER_PASSWORD` (or equivalent key) is optional and supplied from an **uncommitted `.env`**. It must never be hard-coded or committed. SRC‑06's "no credential path" rule refers to **portal credentials**; a local LLM server credential is a different thing and is explicitly allowed as config.
- **D-08:** opencode health is **degraded-tolerant**: the app boots without it, and `/health` plus the source-health strip report it as `unreachable` rather than crashing. The UI must be able to say "LLM backend unreachable" instead of failing mysteriously (STACK Q8 / PITFALLS M10 intent).
- **D-09:** Model discovery reads **`GET /config/providers`** — the subscription-scoped, configured provider/model set (~29 KB on the verified server) — and exposes a **read-only available-model list** (via `/health` or a small `/models` read). It must NOT use `GET /provider`, which returns the full vendor catalogue (~6 MB, 217 providers / ~7,756 models) and is not the user's actual entitlement.
- **D-10:** **`OPENCODE_MODEL` (env) selects the model**, with a documented cheap default (e.g. `deepseek-v4.1-flash`) that is overridable. No model-picker UI in Phase 1. — **Reversibility:** reversible.
- **D-11:** **Security constraint on discovery:** the `/config/providers` response contains the provider API key in plaintext. The app must extract only provider/model IDs and must **never persist or log the raw response**. Verify this with a test.
- **D-12:** Phase 3 (not Phase 1) must record the **model + version per call** so model drift cannot silently change quality/cost (PITFALLS M9). Captured here so the Phase 3 planner inherits it.

### Minimal queue UI & asset pipeline (discussed)
- **D-13:** Phase 1 UI ships: a server-rendered **list** of normalised fields (title, company, location, source, posted), an **empty state**, a **count**, a **"Run search now"** button that triggers the background run, **status polling** for that run, and a **minimal per-source health strip** (last success, listings returned, field fill-rate). The health strip is required because SRC‑07 says the user *can see* per-source health — a JSON-only surface would only half-satisfy it.
- **D-14:** Styling is **Tailwind CSS 4 via a CLI build at image build time**, with the output vendored as a local static file. No CDN (UI‑07). This deliberately establishes the styling system the Phase 5 ranking UI will need rather than migrating later. — **Reversibility:** costly — undoing means re-styling every template and reworking the image build.
- **D-15:** **HTMX 2.x + Alpine 3.x are vendored locally in Phase 1** and HTMX drives the run trigger + status polling. Phase 2's queue filtering/pagination reuses the same pattern. — **Reversibility:** reversible.
- **D-16:** **Phase 1 is built desktop-first; the phone-first layout pass happens in Phase 8 (UI‑06).** — **Reversibility:** costly — retrofitting responsive layout across all Phase 1–7 views is a cross-cutting rework. ⚠️ **Conflict recorded, not hidden:** PROJECT.md's Constraints and REQUIREMENTS.md's Out-of-Scope both state "Phone-first responsive design; primary access is a phone" / "Desktop-first design" is out of scope. The user was shown this conflict and confirmed desktop-first for Phase 1. The planner must NOT silently treat desktop-first as consistent with PROJECT.md; it is a scoping decision with a Phase 8 payoff.

### Carried from research (pre-answered — do not re-litigate)
- **D-17:** Stack is locked: Python 3.13 (not 3.14), FastAPI 0.141.1, uvicorn `--workers 1`, SQLite WAL (`journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=5000`) + SQLAlchemy 2.0.53 + Alembic 1.20.0 + aiosqlite, FTS5 external-content (`porter unicode61`), Jinja2 + HTMX + Alpine + Tailwind, no CDN. JobSpy installed **from git at a pinned commit**, never PyPI.
- **D-18:** Adapter contract is locked: **one adapter per board** (LinkedIn, Indeed) sharing `sources/_jobspy_transport.py`; never one JobSpy call with a `site_name` list. `fetch`/`fetch_details` never raise; `RawListing` has **no `emails` field**; capabilities declared and consulted; `FetchResult.status ∈ {ok, partial, blocked, rate_limited, error}`; `FetchBudget{max_requests, max_results, max_detail_fetches, deadline}`; board fields go in `source_extras`; registry keyed by `name` resolved from the `sources` table.
- **D-19:** Tier‑1 upsert is a **two-key** design: partial unique `(source, source_listing_id) WHERE source_listing_id IS NOT NULL` **plus** an unconditional unique `(source, canonical_url)`. JobSpy's `id` can be `None` (PITFALLS m9), so the partial index alone is insufficient.
- **D-20:** **Migration 0001 is one-way.** It must satisfy the 9-item acceptance checklist (ROADMAP.md Phase 1 / ARCHITECTURE.md §9.4): NOT NULL `first_seen_at`/`last_seen_at`/`content_hash`; append-only `listing_events`; `scores.factor_scores_json` + `weights_json` + `criteria_version`; `cv_artifacts.verification_json` + `compile_status='blocked'`; `applications.cv_artifact_id`; the two dedup indexes; `sources.capabilities_json` + `sources.tos_audited_at`; `listings.blocking_key` indexed; Alembic at 0001 with `alembic upgrade head` exercised in the container build. — **Reversibility:** one-way — these columns describe the past and cannot be backfilled.
- **D-21:** Auth seam is locked: a `current_user()` FastAPI dependency on **every** route; `LOCAL_USER` from `settings.local_user_id`; **no `user_id` columns in v1**; thread `user`/`user_id` at the service layer only (ARCHITECTURE.md §11.1–11.2). Research rates this MEDIUM confidence, so the planner should keep the seam typed and swappable (Authentik OIDC later) without paying for the data model now.
- **D-22:** Run execution is locked: **one `run_pipeline()` callable**, driven by both the manual trigger and (later) the scheduler; runs are enqueued, not executed inline in the request; blocking JobSpy/Tectonic work is wrapped in `asyncio.to_thread` (PITFALLS M3).
- **D-23:** Deterministic-filter-before-LLM and the on-demand-vs-batch pipeline split are architectural givens; sanitisation is a **named pure stage at the ingest boundary** (`domain/sanitize.py` + `ingest/sanitize.py` wrapper, per ARCHITECTURE.md §3 / C2).
- **D-24:** The domain-import-discipline test is required from Phase 1: `app.domain.*` must not import `httpx | sqlalchemy | jobspy | jinja2 | subprocess`.

### the agent's Discretion
- **PII rule enumeration (not selected for discussion):** the baseline is locked — PII (recruiter emails/phones) is stripped at the adapter boundary and **never stored** (SRC‑10), and `RawListing` exposes no `emails` field (D‑18). The *exact* rule set (regex catalogue, which identifiers, hashing vs dropping) is left to research/planning. The `_INJECTION_PATTERNS`-style injection rule set is explicitly an **additive Phase 2 task** (pattern-copied from Resume-Matcher `improver.py` with Apache-2.0 attribution), not Phase 1.
- **Probe document naming/location, health-strip layout, and the `/models` vs `/health`-embedded discovery surface** are left to the planner — the constraints are captured in D‑01…D‑13.
- **Degradation semantics for a partially-failed run** (what the UI shows when one board is `blocked` and the other is `ok`) is left to the planner, bounded by SRC‑05 (partial result, never abort the run).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition & requirements
- `.planning/ROADMAP.md` — Phase 1 goal, success criteria, the 9-item migration 0001 acceptance checklist, and the research flag ("scraper-survival probe design … needs an explicit probe + instrumentation task").
- `.planning/REQUIREMENTS.md` — SRC‑01…SRC‑10, QUEUE‑01/02/05, RUN‑01/02, PLAT‑01/03/04, UI‑07; plus the Out-of-Scope table (auto-apply, credentialed scraping, LLM-emitted LaTeX, vector ranking).
- `.planning/PROJECT.md` — Core Value, Constraints (phone-first, Docker, no-auth, cost), Key Decisions; note the phone-first constraint conflict with D‑16.

### Research — authoritative for this phase
- `.planning/research/SUMMARY.md` — read the **Disagreements Resolved (D1–D10)**, the **Phase 1** section, **Research Flags**, and **Gaps to Address**. This is the single highest-value read.
- `.planning/research/ARCHITECTURE.md` — §1.1 (modular monolith + ports), §2 (component boundaries), §3 (project structure — the exact module paths Phase 1 must create), §4.1 (Flow A), §5.1–5.4 (adapter port, the seven contract rules, one-adapter-per-board), §8.1 (dedup placement), §9.1–9.3 (schema + FTS5 + `search` port), **§9.4 (schema-phase acceptance criteria)**, §11.1–11.2 (auth seam), §12 (Patterns 1/5/6), §13 (anti-patterns), §14.1–14.3 (dependency graph + build order), §16.1–16.2 (integration points), §17 (open questions).
- `.planning/research/PITFALLS.md` — **P1** (scraper breakage is permanent; `probe()` + fill-rate baseline), **P2** (never log in; volume ceiling), P3 (dedup), **P8** (non-backfillable data model), **P10** (total functions at boundaries), P12 (scheduler), **P13/P14** (testing against a hostile live site; failure paths are the product), **M3** (`asyncio.to_thread`), M4 (FTS5), M6 (multi-user scope), **M8** (SQLite PRAGMAs + WAL backup), **M10** (do not expose opencode/app), m1 (JobSpy from git), m4 (no CDN), m9 (`id` can be `None`), m10 (no global last-run).
- `.planning/research/STACK.md` — Installation, Critical Version Corrections, Q1 (acquisition + escalation rungs + Adzuna), Q3 (FastAPI), Q4 (SQLite/SQLAlchemy/Alembic + schema), Q5 (APScheduler — Phase 8, but the sync-engine note matters), Q7 (opencode HTTP endpoints + structured output), Q8 (frontend + Docker deployment), "What NOT to Use".
- `.planning/research/FEATURES.md` — "MVP Definition → Launch With (v1)" (TS‑1/2/4/9), "Gaps and open questions", anti-features AF‑1…AF‑15.
- `.planning/research/RESUME-MATCHER-SPIKE.md` — VERDICT (conditional greenfield → pattern-copy), "What We Reuse / What We Build", Roadmap Impact. Phase 1 relevance is small: confirms greenfield, and defers `_INJECTION_PATTERNS` to Phase 2.

### Project conventions
- `AGENTS.md` — GSD workflow enforcement; GSD stack/architecture blocks are generated from the research files above.

</canonical_refs>

<code_context>
## Existing Code Insights

**Greenfield — the repository contains no application code yet** (only `.planning/`, `AGENTS.md`, `.gitignore`). The "existing code insights" below are the research-prescribed patterns Phase 1 must instantiate, plus the live external integration point that was probed during this discussion.

### Reusable Assets
- None in-repo. The external assets Phase 1 builds on: **JobSpy** (git, pinned commit), **Tectonic** (Phase 4, not Phase 1), **Tailwind CLI**, and vendored **HTMX 2.x / Alpine 3.x** static files.

### Established Patterns (prescribed by research, must be followed)
- **Ports with enforced import discipline** — `app.domain.*` imports no I/O; a test asserts it (ARCHITECTURE.md Pattern 1 / §12).
- **Total functions at the boundary** — adapters return a `FetchResult` and never raise; one board's failure cannot empty the queue (PITFALLS P10).
- **One pipeline callable, two triggers** — `run_pipeline()` used by both the manual trigger and the future scheduler (Pattern 5).
- **Stage-wrapped pipeline with structured run logging** — every stage writes progress/errors so "why is the queue empty?" is answerable (Pattern 6, PITFALLS P9).
- **Append-only event log beside mutable state** — `listing_events` from migration 0001 (Pattern 4).
- **Persist the decomposition, compute the aggregate** — applies to scores; the schema shape (`factor_scores_json`) ships in 0001 even though ranking is Phase 5 (Pattern 3).

### Integration Points
- **opencode server (live, user-managed):** `GET http://127.0.0.1:4096/global/health` → `{"healthy":true,"version":"1.18.29"}`, listening `0.0.0.0:4096`. Discovery endpoint to use: `GET /config/providers`. Endpoint to avoid: `GET /provider` (6 MB catalogue). Base URL is config — see D‑06.
- **SQLite database file** — single writer, `--workers 1`, WAL, backed up with the WAL (M8).
- **Docker Compose** — app container only; opencode is external (D‑05). `extra_hosts: host.docker.internal:host-gateway` for the default base URL (D‑06).
- **Source boards (LinkedIn, Indeed)** — reached only through adapters over the shared JobSpy transport; public logged-out pages only, no credential path anywhere (PITFALLS P2, SRC‑06).

</code_context>

<specifics>
## Specific Ideas

- **Verified live opencode facts (probed 2026-09-15, server v1.18.29):** health endpoint is `/global/health`; configured-model discovery is `/config/providers`; the full catalogue is `/provider`; `/doc` returns the OpenAPI 3.1 spec (paths include both `/api/*` and legacy top-level aliases such as `/session`, `/provider`, `/config`, `/global/health`). `OPENCODE_SERVER_PASSWORD` was empty on the observed server.
- **Subscription-scoped model set observed:** `opencode-go` (OpenCode Go, 27 models — includes `deepseek-v4.1-flash`, `qwen3.7-max`, `glm-5.2`, `kimi-k2.6`, `longcat-2.0`, `minimax-m3`) and `opencode` (OpenCode Zen, 7 models). The user stressed these depend on their subscription, so nothing may be hard-coded.
- **The plaintext provider key in the `/config/providers` response is a concrete hazard**, not a hypothetical — D‑11 requires extraction of IDs only and a test that the raw response is never logged/persisted.
- The probe is a **measurement, not a reading** — it needs its own task and instrumentation, and its result can change the roadmap (Adzuna hedge → primary).
- **`docker compose up` must stay startable at all times** — because opencode is external and treated as degraded-tolerant (D‑08), no Phase 1 dependency may make `up` require an LLM backend.

</specifics>

<deferred>
## Deferred Ideas

- **Adzuna adapter (SRC‑11)** — promote from hedge to primary only if the Phase 1 probe verdict says LinkedIn/Indeed do not survive; decided at Phase 8 (D‑04).
- **Model-picker UI** — a persisted model-selection screen is deferred; Phase 1 uses discovery + `OPENCODE_MODEL` config only (D‑10).
- **`_INJECTION_PATTERNS`-style injection sanitisation rule set** — additive Phase 2 task, pattern-copied from Resume-Matcher `improver.py` with Apache-2.0 attribution (ROADMAP.md Phase 2 Notes).
- **Model + version recording per LLM call** — belongs to Phase 3 (PITFALLS M9); captured in D‑12 so it is not lost.
- **Phone-first layout pass (UI‑06)** — deferred to Phase 8 by explicit user decision (D‑16), with the PROJECT.md conflict recorded.
- **Scheduling (RUN‑05/06, PLAT‑06)** — Phase 8 by roadmap intent; Phase 1 ships manual trigger only.
- **Authentik OIDC / multi-user (PLAT‑07)** and the **MCP server (PLAT‑08)** — future milestone, not v1.

</deferred>

---

*Phase: 1-Walking Skeleton + Foundations*
*Context gathered: 2026-09-15*
