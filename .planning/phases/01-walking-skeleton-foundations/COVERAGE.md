# API Coverage — JobSpy (LinkedIn/Indeed) · opencode server · scrape escalation ladder

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Detector note: the deterministic probe returned `detected:false` for this phase's prose (no
> `integration`/`endpoint` verb-noun pair in the ROADMAP section). Per the phase-specific guidance
> this phase **is** API-integrating, so the matrix is produced rather than skipped.

## JobSpy (git pin `fda080a…`) — acquisition transport

| capability | decision | reason |
|---|---|---|
| Per-board search (`site_name="linkedin"`) | INTEGRATE | SRC-01; one adapter per board over `_jobspy_transport.py` (D-18) |
| Per-board search (`site_name="indeed"`) | INTEGRATE | SRC-02; explicit `country_indeed="ireland"` |
| `job_url` → canonical URL key | INTEGRATE | QUEUE-02 two-key Tier-1 (unconditional `(source, canonical_source_url)` index) |
| `job_url_direct` → `direct_url` | INTEGRATE | best apply target; nullable by contract |
| Structured compensation (`min_amount`/`max_amount`/`interval`/`currency`) | INTEGRATE | mapped when present |
| `desired_order` DataFrame column contract | INTEGRATE | probe signal S6 schema-drift check |
| `date_posted` / `is_remote` / `job_type` / `job_level` | INTEGRATE | normalised fields + `source_extras` (R6) |
| Description fetch (`linkedin_fetch_description`) | INTEGRATE | implemented as `fetch_details()`; **default off** (`probe_max_detail_fetches=0`) because it is O(n) and materially raises block risk (R4, Open Q6) |
| `country_indeed` parameter | INTEGRATE | must be `"ireland"`, never the library default `"usa"` |
| `results_wanted` / `offset` / `hours_old` / `distance` / `is_remote` | INTEGRATE | mapped from `SearchQuery` + `FetchBudget` ceilings |
| Description-derived salary extraction (`extract_salary`) | OPT-OUT | structurally unavailable for Ireland — the branch guards on `Country.USA` and the regex is `$`-anchored (RESEARCH §JobSpy Verified Contract 2.5). Records the observed fill-rate rather than a target |
| Proxy support (`proxies=`) | OPT-OUT | escalation rung 4; paid; only if the Phase 1 probe verdict demands it (Phase 8) |
| `JOBSPY_CREDS` / authenticated session | OPT-OUT | architectural bright line — a credential path must not exist (SRC-06, PITFALLS P2). Not a Phase 1 deferral; a permanent exclusion |
| `site_name=["linkedin","indeed"]` single call | OPT-OUT | one call = one thread pool = no per-board budget/health/attribution (AP16, D-18) |
| Other boards (glassdoor, google, zip_recruiter, bayt, naukri) | OPT-OUT | not Phase 1 scope; the registry makes each a one-module addition (SRC-04). Phase 2+ / v2 |
| `request_timeout` pass-through | OPT-OUT | `scrape_jobs()` accepts `**kwargs` and does **not** forward it (RESEARCH §2.3) — budget is enforced **pre-call** instead |

## Escalation ladder (RESEARCH §Q1 Option B)

| capability | decision | reason |
|---|---|---|
| Rung 1 — polite pacing / jitter / UA | INTEGRATE | always on; part of the transport + config envelope (D-02) |
| Rung 2 — TLS/JA3 impersonation | INTEGRATE | already built into JobSpy's `tls-client` path on LinkedIn, so no separate `curl_cffi` adapter is written in Phase 1 — the capability is covered without new code |
| Rung 3 — stealth browser (`invisible-playwright`) | OPT-OUT | contingency only; Phase 8 escalation if a board requires JS |
| Rung 4 — residential proxies | OPT-OUT | paid spend; gated on the Phase 1 probe verdict |
| Rung 5 — Adzuna aggregator | OPT-OUT | SRC-11 is v2; promotion from hedge to primary is decided at **Phase 8** against the recorded Phase 1 probe condition (D-04) |
| Adzuna analytics endpoints (`/histogram`, `/history`, `/top_companies`) | OPT-OUT | v2; only reachable once the Adzuna adapter exists |

## opencode server (external, user-managed — D-05)

| capability | decision | reason |
|---|---|---|
| `GET /global/health` | INTEGRATE | D-08 boot-tolerant reachability report on `/health` |
| `GET /config/providers` (configured provider/model IDs only) | INTEGRATE | D-09/D-11 — read-only available-model list; raw response never logged or persisted |
| `GET /doc` (OpenAPI 3.1 contract) | OPT-OUT | Phase 3 contract test (PLAT-05); Phase 1 makes no LLM call |
| `POST /session`, `POST /session/:id/message` (structured output) | OPT-OUT | Phase 3 (PLAT-02/PLAT-05) |
| `POST /session/:id/prompt_async` | OPT-OUT | Phase 3+ |
| `GET /event` (SSE progress stream) | OPT-OUT | Phase 3+/Phase 8; Phase 1 polls the DB, not opencode |
| `GET /provider` (full vendor catalogue) | OPT-OUT | ~6 MB, 217 providers / ~7,756 models — not the user's entitlement (D-09) |
| `GET /agent`, provider/agent selection | OPT-OUT | Phase 3 |
| `POST /session/:id/shell`, `/file/*`, tool execution | OPT-OUT | never used; Phase 3 enables calls with `tools=[]` (AP9) |
| `/config` write surface | OPT-OUT | opencode config is user-managed; the app never mutates it |

## Internal ports (non-network, listed for completeness)

| capability | decision | reason |
|---|---|---|
| SQLite FTS5 table + trigger maintenance | INTEGRATE | the external-content virtual table and its three triggers ship in migration 0001 (plans 01-01 and 01-02) |
| SQLite FTS5 `MATCH` query surface | OPT-OUT | the query API is Phase 2 (QUEUE-06); the table ships now so Phase 2 needs no migration |
| `JobSource.fetch_details()` second pass | INTEGRATE | contract ships; budget default-off in Phase 1 |
| `probe()` liveness surface | INTEGRATE | SRC-07 |
| Survival measurement S1–S6 | INTEGRATE | the phase's research flag; verdict is a phase gate |
