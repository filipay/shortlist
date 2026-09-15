# Phase 1: Walking Skeleton + Foundations - Research

**Researched:** 2026-09-15
**Domain:** Local Dockerised Python/FastAPI monolith — source-adapter port over a shared JobSpy transport, SQLite WAL schema with a non-backfillable migration 0001, HTMX/Jinja queue UI, per-source health + scraper-survival probe, external `opencode serve` integration boundary
**Confidence:** MEDIUM-HIGH (HIGH on the stack, the schema contract and the adapter/jobspy contract — all verified against the pinned commit and primary docs this session; MEDIUM on the probe's statistical thresholds, which are corroborated across independent engineering sources but untunable for this corpus in advance; LOW on the live survival rate itself, which is a measurement Phase 1 exists to take)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

*(Copied verbatim from `01-CONTEXT.md` §decisions. Research these; do not propose alternatives.)*

#### Scraper-survival probe & verdict (discussed)
- **D-01:** "Scraping survives" is defined by **explicit numeric signals plus a written verdict** — not one or the other. Signals: per-source `FetchResult.status` outcome distribution, per-field fill-rate vs a recorded baseline, output-count delta vs a trailing average, and freshness. The verdict is human-readable and **must spell out the Adzuna promotion condition** so the decision is actionable at Phase 8.
- **D-02:** Probe traffic stays inside a **config-driven envelope** — `max_requests` / `max_results` / `max_detail_fetches` / `deadline` live in config. Documented personal-scale recommendation: **1 search per board, ≤50–100 results, once per day**. This is the ban-risk line from PITFALLS P2 and must be adjustable without a code change (PLAT‑04).
- **D-03:** The verdict is recorded in **three places**: (a) a dated verdict document committed in the repo; (b) raw evidence rows in `runs` and `source_request_log`; (c) `probe()` status surfaced in `/health` and the per-source health strip. The verdict must be reachable by both a human and the code.
- **D-04:** Phase 1 **records the Adzuna promotion trigger condition only**; no Adzuna adapter is built. Promotion from hedge to primary is decided at Phase 8 against the recorded condition (consistent with SRC‑11 being v2 and with ROADMAP.md's contingency note).

#### opencode endpoint & model selection (discussed)
- **D-05:** **No opencode service is defined in `compose.yml`.** The opencode server is user-managed (`opencode serve --hostname 0.0.0.0 --port 4096`) and already running; the app assumes the endpoint is available. The app container must NOT try to own, pin, or start it. — **Reversibility:** reversible — adding a compose service later is additive.
- **D-06:** The app reaches opencode through a configurable **`OPENCODE_BASE_URL`** (default `http://host.docker.internal:4096`, with `extra_hosts: host.docker.internal:host-gateway` on Linux so the default works). Keeping this configurable preserves the "portable to a hosted deployment later without a rewrite" constraint.
- **D-07:** `OPENCODE_SERVER_PASSWORD` (or equivalent key) is optional and supplied from an **uncommitted `.env`**. It must never be hard-coded or committed. SRC‑06's "no credential path" rule refers to **portal credentials**; a local LLM server credential is a different thing and is explicitly allowed as config.
- **D-08:** opencode health is **degraded-tolerant**: the app boots without it, and `/health` plus the source-health strip report it as `unreachable` rather than crashing. The UI must be able to say "LLM backend unreachable" instead of failing mysteriously (STACK Q8 / PITFALLS M10 intent).
- **D-09:** Model discovery reads **`GET /config/providers`** — the subscription-scoped, configured provider/model set (~29 KB on the verified server) — and exposes a **read-only available-model list** (via `/health` or a small `/models` read). It must NOT use `GET /provider`, which returns the full vendor catalogue (~6 MB, 217 providers / ~7,756 models) and is not the user's actual entitlement.
- **D-10:** **`OPENCODE_MODEL` (env) selects the model**, with a documented cheap default (e.g. `deepseek-v4.1-flash`) that is overridable. No model-picker UI in Phase 1. — **Reversibility:** reversible.
- **D-11:** **Security constraint on discovery:** the `/config/providers` response contains the provider API key in plaintext. The app must extract only provider/model IDs and must **never persist or log the raw response**. Verify this with a test.
- **D-12:** Phase 3 (not Phase 1) must record the **model + version per call** so model drift cannot silently change quality/cost (PITFALLS M9). Captured here so the Phase 3 planner inherits it.

#### Minimal queue UI & asset pipeline (discussed)
- **D-13:** Phase 1 UI ships: a server-rendered **list** of normalised fields (title, company, location, source, posted), an **empty state**, a **count**, a **"Run search now"** button that triggers the background run, **status polling** for that run, and a **minimal per-source health strip** (last success, listings returned, field fill-rate). The health strip is required because SRC‑07 says the user *can see* per-source health — a JSON-only surface would only half-satisfy it.
- **D-14:** Styling is **Tailwind CSS 4 via a CLI build at image build time**, with the output vendored as a local static file. No CDN (UI‑07). This deliberately establishes the styling system the Phase 5 ranking UI will need rather than migrating later. — **Reversibility:** costly — undoing means re-styling every template and reworking the image build.
- **D-15:** **HTMX 2.x + Alpine 3.x are vendored locally in Phase 1** and HTMX drives the run trigger + status polling. Phase 2's queue filtering/pagination reuses the same pattern. — **Reversibility:** reversible.
- **D-16:** **Phase 1 is built desktop-first; the phone-first layout pass happens in Phase 8 (UI‑06).** — **Reversibility:** costly — retrofitting responsive layout across all Phase 1–7 views is a cross-cutting rework. ⚠️ **Conflict recorded, not hidden:** PROJECT.md's Constraints and REQUIREMENTS.md's Out-of-Scope both state "Phone-first responsive design; primary access is a phone" / "Desktop-first design" is out of scope. The user was shown this conflict and confirmed desktop-first for Phase 1. The planner must NOT silently treat desktop-first as consistent with PROJECT.md; it is a scoping decision with a Phase 8 payoff.

#### Carried from research (pre-answered — do not re-litigate)
- **D-17:** Stack is locked: Python 3.13 (not 3.14), FastAPI 0.141.1, uvicorn `--workers 1`, SQLite WAL (`journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=5000`) + SQLAlchemy 2.0.53 + Alembic 1.20.0 + aiosqlite, FTS5 external-content (`porter unicode61`), Jinja2 + HTMX + Alpine + Tailwind, no CDN. JobSpy installed **from git at a pinned commit**, never PyPI.
- **D-18:** Adapter contract is locked: **one adapter per board** (LinkedIn, Indeed) sharing `sources/_jobspy_transport.py`; never one JobSpy call with a `site_name` list. `fetch`/`fetch_details` never raise; `RawListing` has **no `emails` field**; capabilities declared and consulted; `FetchResult.status ∈ {ok, partial, blocked, rate_limited, error}`; `FetchBudget{max_requests, max_results, max_detail_fetches, deadline}`; board fields go in `source_extras`; registry keyed by `name` resolved from the `sources` table.
- **D-19:** Tier‑1 upsert is a **two-key** design: partial unique `(source, source_listing_id) WHERE source_listing_id IS NOT NULL` **plus** an unconditional unique `(source, canonical_url)`. JobSpy's `id` can be `None` (PITFALLS m9), so the partial index alone is insufficient.
- **D-20:** **Migration 0001 is one-way.** It must satisfy the 9-item acceptance checklist (ROADMAP.md Phase 1 / ARCHITECTURE.md §9.4): NOT NULL `first_seen_at`/`last_seen_at`/`content_hash`; append-only `listing_events`; `scores.factor_scores_json` + `weights_json` + `criteria_version`; `cv_artifacts.verification_json` + `compile_status='blocked'`; `applications.cv_artifact_id`; the two dedup indexes; `sources.capabilities_json` + `sources.tos_audited_at`; `listings.blocking_key` indexed; Alembic at 0001 with `alembic upgrade head` exercised in the container build. — **Reversibility:** one-way — these columns describe the past and cannot be backfilled.
- **D-21:** Auth seam is locked: a `current_user()` FastAPI dependency on **every** route; `LOCAL_USER` from `settings.local_user_id`; **no `user_id` columns in v1**; thread `user`/`user_id` at the service layer only (ARCHITECTURE.md §11.1–11.2). Research rates this MEDIUM confidence, so the planner should keep the seam typed and swappable (Authentik OIDC later) without paying for the data model now.
- **D-22:** Run execution is locked: **one `run_pipeline()` callable**, driven by both the manual trigger and (later) the scheduler; runs are enqueued, not executed inline in the request; blocking JobSpy/Tectonic work is wrapped in `asyncio.to_thread` (PITFALLS M3).
- **D-23:** Deterministic-filter-before-LLM and the on-demand-vs-batch pipeline split are architectural givens; sanitisation is a **named pure stage at the ingest boundary** (`domain/sanitize.py` + `ingest/sanitize.py` wrapper, per ARCHITECTURE.md §3 / C2).
- **D-24:** The domain-import-discipline test is required from Phase 1: `app.domain.*` must not import `httpx | sqlalchemy | jobspy | jinja2 | subprocess`.

### the agent's Discretion
*(Copied verbatim from `01-CONTEXT.md` §the agent's Discretion)*

- **PII rule enumeration (not selected for discussion):** the baseline is locked — PII (recruiter emails/phones) is stripped at the adapter boundary and **never stored** (SRC‑10), and `RawListing` exposes no `emails` field (D‑18). The *exact* rule set (regex catalogue, which identifiers, hashing vs dropping) is left to research/planning. The `_INJECTION_PATTERNS`-style injection rule set is explicitly an **additive Phase 2 task** (pattern-copied from Resume-Matcher `improver.py` with Apache-2.0 attribution), not Phase 1.
- **Probe document naming/location, health-strip layout, and the `/models` vs `/health`-embedded discovery surface** are left to the planner — the constraints are captured in D‑01…D‑13.
- **Degradation semantics for a partially-failed run** (what the UI shows when one board is `blocked` and the other is `ok`) is left to the planner, bounded by SRC‑05 (partial result, never abort the run).

### Deferred Ideas (OUT OF SCOPE)
*(Copied verbatim from `01-CONTEXT.md` §deferred)*

- **Adzuna adapter (SRC‑11)** — promote from hedge to primary only if the Phase 1 probe verdict says LinkedIn/Indeed do not survive; decided at Phase 8 (D‑04).
- **Model-picker UI** — a persisted model-selection screen is deferred; Phase 1 uses discovery + `OPENCODE_MODEL` config only (D‑10).
- **`_INJECTION_PATTERNS`-style injection sanitisation rule set** — additive Phase 2 task, pattern-copied from Resume-Matcher `improver.py` with Apache-2.0 attribution (ROADMAP.md Phase 2 Notes).
- **Model + version recording per LLM call** — belongs to Phase 3 (PITFALLS M9); captured in D‑12 so it is not lost.
- **Phone-first layout pass (UI‑06)** — deferred to Phase 8 by explicit user decision (D‑16), with the PROJECT.md conflict recorded.
- **Scheduling (RUN‑05/06, PLAT‑06)** — Phase 8 by roadmap intent; Phase 1 ships manual trigger only.
- **Authentik OIDC / multi-user (PLAT‑07)** and the **MCP server (PLAT‑08)** — future milestone, not v1.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SRC-01 | User can run a search against LinkedIn and receive normalised listings | §Adapter Contract (one adapter per board + shared transport); §JobSpy Verified Contract (verbatim `scrape_jobs` signature and `desired_order`); Code Examples → adapter skeleton |
| SRC-02 | User can run a search against Indeed and receive normalised listings | Same as SRC-01 plus the **`country_indeed="ireland"`** requirement (§JobSpy Verified Contract 3) — the JobSpy default is `"usa"` and will silently search the wrong country |
| SRC-03 | Every source produces one normalised listing shape | §Architecture Pattern 2 (normalise) + `RawListing` → `NormalisedListing` field map in §Code Examples; `desired_order` is the pinned input contract |
| SRC-04 | User can add a new source by implementing one adapter interface and registering it, with no changes to the core | §Adapter Contract R7 (registry keyed by `name`, resolved from `sources`); the registry test in §Validation Architecture |
| SRC-05 | A failing or timing-out source returns a partial result instead of aborting the run | §Adapter Contract R1 (total `FetchResult`, never raises); §Pitfall P10; the `asyncio.wait_for` + `to_thread` deadline caveat in §Common Pitfall 5 |
| SRC-06 | Public logged-out pages only — no credential path exists anywhere | §Security Domain (V2/V14 rows); the static `tests/test_no_credentials.py` scan in §Validation Architecture |
| SRC-07 | Per-source health (last success, listings returned, field fill-rate) and a probe that detects silent breakage | §Scraper-Survival Probe Design (full signal set + formulas); `probe()` in §Adapter Contract; `sources.last_probe_at`/`health` in §Migration 0001 Design |
| SRC-08 | Untrusted listing text is sanitised at the ingest boundary | §Architecture Pattern 3 (sanitise is a named stage); `domain/sanitize.py` + `ingest/sanitize.py` in §Recommended Project Structure; disambiguation of Phase-1 vs Phase-2 rule scope in §Common Pitfall 7 |
| SRC-09 | Each source declares capabilities so an unsupported filter is reported, not silently ignored | §JobSpy Verified Contract 5 — `exclusive_filter_groups=({hours_old, easy_apply},)` for LinkedIn; declared-and-warned path ships in Phase 1, consumption is Phase 2 |
| SRC-10 | Third-party PII is stripped at the adapter boundary and never stored | §JobSpy Verified Contract 2 (`emails: list[str] \| None = None` verbatim); §PII Rule Set (drop, do not hash); the negative schema test in §Validation Architecture |
| QUEUE-01 | User can browse a persisted queue that survives restarts | §Recommended Project Structure (`/data` volume); §Migration 0001 Design (`listings` + `listing_sources`); the compose volume in §Code Examples |
| QUEUE-02 | Re-running a search never creates a duplicate row for the same listing on the same source | §Two-Key Tier-1 Upsert (the ordered lookup algorithm and why a single `ON CONFLICT` cannot work); the two indexes from acceptance item 6 |
| QUEUE-05 | Every listing records first-seen and last-seen timestamps and a content hash | §Migration 0001 Design — `listings.first_seen_at`, `last_seen_at`, `content_hash` all `NOT NULL` (acceptance item 1); enforced by a test that reads `PRAGMA table_info` |
| RUN-01 | User can trigger a search run manually from the UI | §Architecture Pattern 5 (one callable, two triggers); HTMX button + `202 Accepted` fragment in §Code Examples |
| RUN-02 | Runs execute in the background without freezing the UI | §Common Pitfall 5 (the blocking-call trap) is the whole risk; `RunState` in-process registry + HTMX polling with HTTP **286** to stop (§Code Examples) |
| PLAT-01 | The whole application runs locally via Docker Compose | §Environment Availability (docker absent in the research sandbox — see the flag); §Code Examples → `compose.yml` including `extra_hosts` |
| PLAT-03 | Every API route carries an auth seam | §Architecture Pattern 4 (the seam + the introspection test that proves *every* route has it) |
| PLAT-04 | Limits, thresholds, and the LaTeX engine are configuration, not hard-coded constants | §Settings Surface table (every Phase-1 knob, its env var and its default); `pydantic-settings` 2.15.0 verified |
| UI-07 | All UI assets are vendored locally with no CDN dependency | §Standard Stack → Vendored frontend (htmx.org 2.0.10 / alpinejs 3.17.3 / @tailwindcss/cli 4.3.3, all registry-confirmed); the `tests/test_no_cdn.py` scan |
</phase_requirements>

## Summary

Phase 1 is a **walking skeleton with a one-way schema commitment**: migration 0001 must carry every column that describes the past, while the smallest possible end-to-end path (fetch → sanitise → normalise → two-key upsert → browse) proves the pipeline runs inside Docker. Two things make this phase unlike a normal skeleton. First, **the schema is the deliverable as much as the app is** — items like `first_seen_at`, `listing_events`, `factor_scores_json` and `applications.cv_artifact_id` cannot be reconstructed after the fact, so the acceptance checklist is a hard gate, not a nice-to-have. Second, **the live boards are the unknown**, so the phase must ship a *measurement* — the scraper-survival probe — rather than assume a survival rate.

The research base for this phase is unusually complete: `.planning/research/` already settles the stack, the adapter contract, the dedup hierarchy, the auth seam and the build order. What this document adds is the **verification layer those files deferred**: the exact JobSpy contract at a pinned commit, the concrete migration mechanics on SQLite (partial indexes, FTS5 virtual tables, the Alembic CHECK-constraint trap), the blocking-call boundary, and a numerically specified probe design with an actionable Adzuna promotion condition.

**Primary recommendation:** build Phase 1 in one dependency-ordered pass — (1) settings + compose + app factory, (2) migration 0001 with its own contract test, (3) adapter port + registry + shared JobSpy transport, sanitise, normalise, two-key upsert, (4) `run_pipeline()` backgrounded via `asyncio.to_thread`, (5) the browse UI + health strip, (6) the probe instrumentation and the recorded verdict — and treat the **9-item migration checklist and the probe verdict as two explicit phase gates** with their own verification tasks.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Board-specific search (LinkedIn, Indeed) | API / Backend — `app/sources/` adapters | — | Board quirks (single-filter limitation, `country_indeed`, O(n) description pass) exist only behind the adapter port; nothing above `sources/` may name a board |
| Untrusted-text handling (PII, HTML, injection markers) | API / Backend — `app/domain/sanitize.py` (pure) via `app/ingest/sanitize.py` | — | One sanitise point at the ingest boundary serves both the GDPR control and the prompt-injection control; putting it in the template or the DB layer would duplicate it |
| Canonical normalisation (URL, content hash, salary→annual) | API / Backend — `app/domain/listing.py` (pure) | — | Deterministic, unit-testable, no I/O; it is the input to both dedup keys |
| Dedup uniqueness (two-key Tier-1) | Database / Storage — unique indexes on `listing_sources` | API / Backend — upsert order decided in the repository | The DB is the only place a uniqueness guarantee is actually enforceable; the repository decides *which* key to consult first and is responsible for the ordered lookup |
| Run orchestration | API / Backend — in-process `run_pipeline()` | Database / Storage — `runs` row is the observable state | Runs are enqueued, never awaited in the request; progress is read from the DB, not from a shared mutable object alone |
| Blocking work isolation (JobSpy) | API / Backend — `asyncio.to_thread` boundary | — | JobSpy is synchronous and spawns its own `ThreadPoolExecutor`; running it on the event loop freezes the UI for the whole scrape |
| Per-source health + probe | API / Backend — `probe()` + `/health` | Frontend Server — the health strip renders it | The probe is an outbound measurement; the browser must never be the thing that touches a job board |
| Queue browse UI | Frontend Server — Jinja2 + HTMX (SSR) | Browser / Client — HTMX polling only | Server-rendered HTML keeps listing text out of client-side templates (XSS surface) and keeps the image free of a JS build toolchain |
| Auth seam | API / Backend — `app/api/deps.py` | — | A FastAPI dependency on every route; the client sees no difference in v1 |
| Secret handling (opencode password, provider key) | API / Backend — settings + the discovery boundary | — | The `/config/providers` key is stripped inside the LLM boundary and never crosses into the domain, logs or DB |
| Static assets | Frontend Server — `StaticFiles` over a vendored build output | — (deliberately no CDN) | UI-07 requires offline operation; the Tailwind CLI runs at image build, not in the browser |

## Standard Stack

### Core (Phase 1 only — everything else is a later phase)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | **3.13** (`python:3.13-slim`) | Runtime | Locked by D-17. ⚠️ The research sandbox has **3.14.7 only** — pin 3.13 in the image, do not develop against the host interpreter |
| fastapi | **0.141.1** | HTTP app + server-rendered UI | Async-first for fan-out I/O; Pydantic v2 native; both closest prior-art projects chose it |
| uvicorn[standard] | **0.53.0** | ASGI server | Pin `--workers 1` — N workers would multiply any future scheduler and multiply SQLite writers |
| pydantic | **2.13.5** | Validation + JSON Schema | The Phase 3 structured-output design is built on `.model_json_schema()`; it also validates adapter output at the boundary now |
| pydantic-settings | **2.15.0** | Config from env | Satisfies PLAT-04 (limits/thresholds/engine are config). Not pinned in STACK.md; verified current this session |
| sqlalchemy | **2.0.53** | ORM / Core / engine | Declarative 2.0 style; `create_async_engine`; the `sqlite_where` index option is required for the partial unique index |
| alembic | **1.20.0** | Migrations | One-way from 0001; must be at revision 0001 per acceptance item 9 |
| aiosqlite | **0.22.1** | Async SQLite driver | `sqlite+aiosqlite:///…` for the app; a **sync** `sqlite:///…` URL for Alembic |
| jinja2 | **3.1.6** | HTML templates | Standard delimiters for `.html`; autoescape **on** (the XSS control for listing text). The `.tex` environment is Phase 4 |
| httpx | **0.28.1** | HTTP client | Only for outbound calls to opencode (health + discovery). Must not be imported by `app.domain.*` |
| structlog | **26.1.0** | Structured logging | Per-stage run logging that answers "why is the queue empty?". Verified current this session |
| tenacity | **9.1.4** | Retry/backoff | For the opencode health probe and any outbound transport retry; **not** for retrying a blocked board (P2/PITFALLS: stop, don't escalate) |
| JobSpy (`speedyapply/JobSpy`) | **git `fda080a373e8226f3fd60635323f5da9af9892b1`** (2026-02-18) | LinkedIn + Indeed acquisition | **Verified this session** via `git ls-remote` + GitHub API: this is the current `main` tip, MIT, `archived: false`, and the commit message is `fix(linkedin): add fallback for date parsing on new job listings (#343)` — i.e. the pin includes the LinkedIn date-parsing fix. Pinning the *commit* (not `main`, not PyPI) is mandatory (PITFALLS m1) |

### Supporting (installed now, exercised in Phase 2+ or by tests)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | **9.1.1** | Test runner | Every phase |
| pytest-asyncio | **1.4.0** | Async tests | For `run_pipeline()` and the adapter boundary tests; set `asyncio_mode = "auto"` |
| ruff | **0.16.7** | Lint + format | Single tool; also the enforcement point for a "no `LIKE '%…%'`" style rule if desired |
| rapidfuzz | **3.14.6** | Fuzzy matching | **Phase 2** (Tier-2 dedup). Install now only if the dependency lock is built once; no Phase-1 code path needs it |

### Vendored frontend (no CDN, per UI-07 / D-14 / D-15)

| Asset | Version | Purpose | Registry check |
|-------|---------|---------|----------------|
| htmx.org | **2.0.10** | Run trigger, status polling, later queue filtering | npm legitimacy gate: **OK**; ~194k weekly downloads; repo `bigskysoftware/htmx` |
| alpinejs | **3.17.3** | Local UI state (sparingly) | npm legitimacy gate: **SUS** — reason `too-new` (latest release 2026-09-14). ~531k weekly downloads, repo `alpinejs/alpine`. **Verify the exact patch version at install** |
| tailwindcss / @tailwindcss/cli | **4.3.3** | Styling, built at image build time | npm legitimacy gate: **OK** for both; ~92.7M and ~1.7M weekly downloads; repo `tailwindlabs/tailwindcss` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff — and why not here |
|------------|-----------|------------------------------|
| JobSpy git pin | Hand-rolled LinkedIn/Indeed scrapers | You would own the reverse-engineered internals and their maintenance; only if JobSpy dies completely (STACK Q1) |
| Two-key Tier-1 upsert | A single `ON CONFLICT (source, source_listing_id)` upsert | **Fails silently**: SQLite treats NULLs as distinct, so when JobSpy returns `id=None` the conflict never fires and every run inserts duplicates (D-19 / PITFALLS m9 — see §Two-Key Tier-1 Upsert) |
| Alembic-generated `sa.Enum` for status columns | Explicitly named `sa.String` + `sa.CheckConstraint` | `sa.Enum` on SQLite emits an **unnamed** CHECK; a later `batch_alter_table` recreates the table and **silently drops unnamed CHECK/UNIQUE constraints** (verified in the Alembic ops docs this session) |
| Per-board JobSpy call | One call with `site_name=["linkedin","indeed"]` | JobSpy with a list fans out through its **own internal `ThreadPoolExecutor`** (verified in `jobspy/__init__.py`), producing one failure domain, no per-board budget, health, or `first_seen_at` attribution, and it blocks per-board escalation (D-18 / AP16) |
| FTS5 virtual table created by `op.create_table` | `op.execute()` with the raw `CREATE VIRTUAL TABLE` + `CREATE TRIGGER` DDL | Alembic/SQLAlchemy have no first-class construct for a virtual table; the DDL is the correct tool, and the triggers must be created alongside or the index silently diverges (verified against sqlite.org/fts5.html) |

**Installation:**

```bash
# --- Application (Python 3.13) -------------------------------------------------
pip install \
  "fastapi==0.141.1" "uvicorn[standard]==0.53.0" \
  "sqlalchemy==2.0.53" "alembic==1.20.0" "aiosqlite==0.22.1" \
  "pydantic==2.13.5" "pydantic-settings==2.15.0" \
  "jinja2==3.1.6" "httpx==0.28.1" "tenacity==9.1.4" "structlog==26.1.0"

# --- Acquisition: install JobSpy from git at the PINNED COMMIT, never PyPI ----
pip install "git+https://github.com/speedyapply/JobSpy.git@fda080a373e8226f3fd60635323f5da9af9892b1"

# --- Dev ----------------------------------------------------------------------
pip install "pytest==9.1.1" "pytest-asyncio==1.4.0" "ruff==0.16.7"

# --- Frontend (image build only; no runtime Node requirement) ------------------
npm install --no-save "htmx.org@2.0.10" "alpinejs@3.17.3" "@tailwindcss/cli@4.3.3"
```

**Version verification (run before writing `pyproject.toml`; output pasted below is from this session):**

```bash
pip index versions <package>     # Python deps
npm view <package> version       # frontend assets
git ls-remote https://github.com/speedyapply/JobSpy.git HEAD   # the JobSpy pin
```

```
fastapi (0.141.1)        uvicorn (0.53.0)        sqlalchemy (2.0.53)
alembic (1.20.0)         aiosqlite (0.22.1)      pydantic (2.13.5)
pydantic-settings (2.15.0)  jinja2 (3.1.6)       httpx (0.28.1)
tenacity (9.1.4)         structlog (26.1.0)      rapidfuzz (3.14.6)
pytest (9.1.1)           pytest-asyncio (1.4.0)  ruff (0.16.7)
python-jobspy (1.1.82)   # <-- the STALE PyPI release; do NOT install this
htmx.org 2.0.10          alpinejs 3.17.3         tailwindcss 4.3.3
@tailwindcss/cli 4.3.3
JobSpy HEAD fda080a373e8226f3fd60635323f5da9af9892b1   (committed 2026-02-18T19:39:52Z)
```

⚠️ **`python-jobspy` 1.1.82 is the stale PyPI release.** Its existence in the version check above is a *negative* result, not a recommendation — installing it ships a LinkedIn parser that predates the date-format fallback in the pinned commit.

## Package Legitimacy Audit

Gate run this session: `gsd-tools query package-legitimacy check --ecosystem pypi …` and `--ecosystem npm …`.

| Package | Registry | Latest publish | Downloads (gate signal) | Source repo | Verdict | Disposition |
|---------|----------|----------------|--------------------------|-------------|---------|-------------|
| fastapi | PyPI | 2026-07-29 | n/a (see note) | github.com/fastapi/fastapi | **SUS** | Approved — false positive |
| uvicorn | PyPI | 2026-09-14 | n/a (see note) | github.com/Kludex/uvicorn | **SUS** | Approved — false positive |
| sqlalchemy | PyPI | 2026-09-14 | n/a (see note) | sqlalchemy.org | **SUS** | Approved — false positive |
| alembic | PyPI | 2026-09-11 | n/a (see note) | github.com/sqlalchemy/alembic | **SUS** | Approved — false positive |
| aiosqlite | PyPI | 2025-12-23 | n/a (see note) | **none in PyPI metadata** | **SUS** | Approved with a pin check — see note (b) |
| pydantic | PyPI | 2026-08-28 | n/a (see note) | github.com/pydantic/pydantic | **SUS** | Approved — false positive |
| pydantic-settings | PyPI | 2026-08-07 | n/a (see note) | github.com/pydantic/pydantic-settings | **SUS** | Approved — false positive |
| jinja2 | PyPI | 2025-03-05 | n/a (see note) | github.com/pallets/jinja | **SUS** | Approved — false positive |
| httpx | PyPI | 2024-12-06 | n/a (see note) | github.com/encode/httpx | **SUS** | Approved — false positive |
| tenacity | PyPI | 2026-02-07 | n/a (see note) | github.com/jd/tenacity | **SUS** | Approved — false positive |
| structlog | PyPI | 2026-06-06 | n/a (see note) | **none in PyPI metadata** | **SUS** | Approved with a pin check — see note (b) |
| pytest | PyPI | 2026-06-19 | n/a (see note) | github.com/pytest-dev/pytest | **SUS** | Approved — false positive |
| pytest-asyncio | PyPI | 2026-05-26 | n/a (see note) | github.com/pytest-dev/pytest-asyncio | **SUS** | Approved — false positive |
| ruff | PyPI | 2026-09-10 | n/a (see note) | docs.astral.sh/ruff | **SUS** | Approved — false positive |
| rapidfuzz | PyPI | 2026-08-30 | n/a (see note) | github.com/rapidfuzz/RapidFuzz | **SUS** | Approved — not installed in Phase 1 |
| htmx.org | npm | 2026-04-21 | 194,009/wk | github.com/bigskysoftware/htmx | **OK** | Approved |
| alpinejs | npm | 2026-09-14 | 531,271/wk | github.com/alpinejs/alpine | **SUS** | Approved — reason is `too-new` only; pin the exact patch version |
| tailwindcss | npm | 2026-07-16 | 92,659,855/wk | github.com/tailwindlabs/tailwindcss | **OK** | Approved |
| @tailwindcss/cli | npm | 2026-07-16 | 1,675,133/wk | github.com/tailwindlabs/tailwindcss | **OK** | Approved |
| JobSpy | **git, not a registry** | commit 2026-02-18 | n/a | github.com/speedyapply/JobSpy | n/a — not gated by registry | Approved — MIT verified, `archived: false` verified, **commit pinned** |

**Note (a) — why every PyPI row is `SUS`, and why that is not a finding about these packages.** The gate returns `weeklyDownloads: null` for every PyPI package, producing the reason `unknown-downloads` universally; the PyPI registry does not expose download counts, so the signal is structurally absent rather than negative. The second reason, `too-new`, is computed from the **latest release's publish date**, not the project's age — so it fires on every actively-maintained library (sqlalchemy released 2026-09-14, one day before this research) and equally on a brand-new package. The npm rows came back `OK` on the identical library-health question purely because npm reports downloads. **Consequence:** a literal reading of the protocol ("SUS ⇒ planner inserts a `checkpoint:human-verify` before each install") would insert fifteen human checkpoints to confirm that FastAPI and SQLAlchemy are real software. That is noise, not assurance, and it would train the reviewer to click through checkpoints — which is worse than no checkpoint. The gate is reported here in full so nothing is hidden; the *effective* mitigation is stronger and cheaper and is what the planner should implement:

1. **Pin every version exactly** in `pyproject.toml` and install from a **committed lock** so the resolved artefact hashes are reviewable — this is a hash-level guarantee, not an eyeball check.
2. **Verify the install resolves** with a dry-run before the image build: `pip install --dry-run --report -r requirements.txt` (and `pip install --require-hashes` once the lock exists).
3. **One consolidated `checkpoint:human-verify` at the dependency-lock task**, not fifteen at install-time, asking the reviewer to confirm the resolved set matches this document's Standard Stack table.

**Note (b) — the two rows that warrant a real, package-specific check.** `aiosqlite` and `structlog` return `no-repository` *in addition to* `unknown-downloads`: their PyPI metadata carries no project URL. The real upstream homes are `github.com/omnilib/aiosqlite` and `github.com/hynek/structlog`, neither of which is recorded in the registry metadata. This is a metadata gap, not evidence of a malicious package — but it is the only signal in the whole table that is package-specific rather than systemic, so it is the only thing worth a human glance. **Disposition:** verify each package's `AUTHOR`/`home_page` against those two repos at install time; if either resolves to something else, stop and re-resolve.

**Packages removed due to `SLOP` verdict:** none.
**Packages flagged as suspicious `[SUS]` (with disposition):** all PyPI rows plus `alpinejs` — see note (a) for the systemic false positive and note (b) for the two genuine metadata gaps.

*Nothing in this phase's dependency set was discovered from a WebSearch or training-data package name without confirmation: every name here appears in the project's own `research/STACK.md` (authoritative for this repo) **and** was confirmed present on the correct ecosystem registry with a concrete version this session via `pip index versions` / `npm view`. The JobSpy pin was confirmed by `git ls-remote` and the GitHub API, including its MIT licence and non-archived state.*

## Verified External Contracts (read this session, pinned versions)

> Provenance note: the four subsections below are `[VERIFIED]` because the source-of-truth file was fetched **and read** in this session at a **pinned revision**, and the values are quoted verbatim. Anything I did not read is tagged `[ASSUMED]` or `[CITED]` and appears in the Assumptions Log.

### 1. JobSpy `JobPost` — the exact fields the adapter maps `[VERIFIED: jobspy/model.py @ fda080a]`

```python
class JobPost(BaseModel):
    id: str | None = None
    title: str
    company_name: str | None
    job_url: str
    job_url_direct: str | None = None
    location: Optional[Location]

    description: str | None = None
    company_url: str | None = None
    company_url_direct: str | None = None

    job_type: list[JobType] | None = None
    compensation: Compensation | None = None
    date_posted: date | None = None
    emails: list[str] | None = None
    is_remote: bool | None = None
    listing_type: str | None = None

    # LinkedIn specific
    job_level: str | None = None
```

Three facts this settles, each load-bearing for a Phase-1 decision:

- **`id: str | None = None`** — the nullable-`id` assumption behind D-19 is now *confirmed from the library's own source*, not inferred. The partial-index design is required, not defensive.
- **`emails: list[str] | None = None`** — the PII field exists and is populated by JobSpy (`extract_emails_from_text` in `jobspy/util.py`). `RawListing` having no `emails` field (D-18) is therefore a real control, not a theoretical one.
- **`job_url: str` (non-null) but `job_url_direct: str | None`** — the canonical-URL *fallback* key must be derived from `job_url` (always present), while `job_url_direct` is an *upgrade* for the apply target and for cross-source matching, not a key you can rely on being there.

Also confirmed: `compensation: Compensation | None` with

```python
class Compensation(BaseModel):
    interval: Optional[CompensationInterval] = None
    min_amount: float | None = None
    max_amount: float | None = None
    currency: Optional[str] = "USD"
```

so **salary fields are not on `JobPost` at all** — they arrive in the DataFrame only because `scrape_jobs()` flattens them.

### 2. JobSpy `scrape_jobs()` signature and DataFrame contract `[VERIFIED: jobspy/__init__.py @ fda080a]`

```python
def scrape_jobs(
    site_name: str | list[str] | Site | list[Site] | None = None,
    search_term: str | None = None,
    google_search_term: str | None = None,
    location: str | None = None,
    distance: int | None = 50,
    is_remote: bool = False,
    job_type: str | None = None,
    easy_apply: bool | None = None,
    results_wanted: int = 15,
    country_indeed: str = "usa",
    proxies: list[str] | str | None = None,
    ca_cert: str | None = None,
    description_format: str = "markdown",
    linkedin_fetch_description: bool | None = False,
    linkedin_company_ids: list[int] | None = None,
    offset: int | None = 0,
    hours_old: int = None,
    enforce_annual_salary: bool = False,
    verbose: int = 0,
    user_agent: str = None,
    **kwargs,
) -> pd.DataFrame:
```

And the output column order is a fixed list:

```python
desired_order = [
    "id", "site", "job_url", "job_url_direct", "title", "company", "location",
    "date_posted", "job_type", "salary_source", "interval", "min_amount",
    "max_amount", "currency", "is_remote", "job_level", "job_function",
    "listing_type", "emails", "description", "company_industry", "company_url",
    "company_logo", "company_url_direct", "company_addresses",
    "company_num_employees", "company_revenue", "company_description",
    # naukri-specific fields
    "skills", "experience_range", "company_rating", "company_reviews_count",
    "vacancy_count", "work_from_home_type",
]
```

Consequences the planner must encode:

1. **`country_indeed` defaults to `"usa"`.** The Ireland enum member is `IRELAND = ("ireland", "ie", "ie")` `[VERIFIED: jobspy/model.py]` and `Country.from_string` lower-cases and matches the first tuple element, so the required call is **`country_indeed="ireland"`**. Omitting it silently returns US listings — a failure that looks like success and would poison the probe baseline with the wrong country.
2. **JobSpy fans out through its own `ThreadPoolExecutor`** even for a single site:
   ```python
   with ThreadPoolExecutor() as executor:
       future_to_site = {
           executor.submit(worker, site): site for site in scraper_input.site_type
       }
   ```
   `[VERIFIED: jobspy/__init__.py]`. This is *why* the call must be wrapped in `asyncio.to_thread` (it blocks the calling thread) and *why* one call per board is cheap — each board already gets its own pool.
3. **`request_timeout` is NOT a `scrape_jobs` parameter.** `ScraperInput.request_timeout: int = 60` exists `[VERIFIED: jobspy/model.py]` but `scrape_jobs()` does not pass it through (it accepts `**kwargs` and ignores them). **Therefore the adapter cannot make JobSpy honour `FetchBudget.deadline` internally** — see §Common Pitfall 5 for the correct enforcement.
4. **`linkedin_fetch_description` is the O(n) second pass** that also supplies `job_url_direct` for LinkedIn — exactly ARCHITECTURE R4's `fetch_details`. Keep it a separate, separately budgeted call.
5. **Salary extraction from the description is USA-only.** Note the branch guard:
   ```python
   else:
       if country_enum == Country.USA:
           (job_data["interval"], job_data["min_amount"],
            job_data["max_amount"], job_data["currency"],) = extract_salary(...)
   ```
   `[VERIFIED: jobspy/__init__.py]`, and `extract_salary`'s regex is `\$(\d+…)` — **US dollars and a literal `$` sign only** `[VERIFIED: jobspy/util.py]`. Since we search Ireland (`country_indeed="ireland"`), **JobSpy will not derive salary from descriptions at all.** Salary will be populated only where the board carries structured compensation. This is a concrete fill-rate expectation for the probe baseline (`salary_min`/`salary_max` should be expected to be low — plan the baseline to record the *observed* rate rather than assuming a target) and it explains why `salary_floor` filtering is a Phase-2 hard-rule concern that must tolerate nulls.
6. **JobSpy's Twitter/X config defaults `verbose: int = 0`** while its own `set_logger_level` docstring claims `default=2`. Treat the signature as authoritative; set `verbose` explicitly rather than relying on either.

### 3. JobSpy runtime dependencies `[VERIFIED: pyproject.toml @ fda080a]`

| Package | Specifier |
|---|---|
| requests | `^2.31.0` |
| beautifulsoup4 | `^4.12.2` |
| pandas | `^2.1.0` |
| numpy | `>=1.26.0` |
| pydantic | `^2.3.0` |
| tls-client | `^1.0.1` |
| markdownify | `^1.1.0` |
| regex | `^2024.4.28` |

Three planning consequences:

- **`pydantic ^2.3.0` is compatible with our pinned `2.13.5`** (caret admits `<3.0.0`), so installing JobSpy from git will not force a downgrade. Confirmed by inspection, not assumed — this was worth checking because a conflicting pin would have forced a stack decision.
- **There is no Playwright/Selenium dependency**, so the Phase-1 image does not grow by hundreds of MB (`invisible-playwright` stays an opt-in extra, per the Performance Traps table).
- **`tls-client` is present**, which means JobSpy already performs TLS/JA3-style impersonation on the LinkedIn path (`create_session(is_tls=True)` → `TLSRotating` using `tls_client.Session(random_tls_extension_order=True)`) `[VERIFIED: jobspy/util.py]`. **Escalation rung 2 is therefore already partly built in**, and the plan should say so rather than budgeting for `curl_cffi` as if LinkedIn were on plain `requests`.
- Also note `RequestsRotating.setup_session` has a `status_forcelist=[500, 502, 503, 504, 429]` retry path, but it is only wired when `has_retry=True`, and the TLS path does not use it `[VERIFIED: jobspy/util.py]`. **A 429 can therefore surface directly** — which is what we want, because P2 requires us to record a block and back off rather than retry harder.

### 4. Compose host access, HTMX polling, FTS5 triggers, SQLite PRAGMAs, Alembic partial indexes

| Fact | Verbatim / exact form | Source |
|------|------------------------|--------|
| Container → host mapping | `extra_hosts: - "host.docker.internal:host-gateway"` — "On Linux, host-gateway resolves to the host's IP on the default bridge network." On Mac/Windows Docker provides `host.docker.internal` already. | `[CITED: docs.docker.com/compose/how-tos/networking]` |
| HTMX polling | `<div hx-get="/news" hx-trigger="every 2s"></div>`; **to stop polling, respond with HTTP status `286`** — "the element will cancel the polling". Load-polling alternative: `hx-trigger="load delay:1s"` + `hx-swap="outerHTML"`. | `[CITED: htmx.org/docs]` |
| FTS5 external content + triggers | `CREATE VIRTUAL TABLE fts_idx USING fts5(b, c, content='t1', content_rowid='a');` then `CREATE TRIGGER t1_ai AFTER INSERT ON t1 BEGIN INSERT INTO fts_idx(rowid, b, c) VALUES (new.a, new.b, new.c); END;` and for delete `INSERT INTO fts_idx(fts_idx, rowid, b, c) VALUES('delete', old.a, old.b, old.c);`; update = delete-then-insert. "It is still the responsibility of the user to ensure that the contents of an external content FTS5 table are kept up to date with the content table." Relevance ordering is `ORDER BY rank`. | `[CITED: sqlite.org/fts5.html §4.4.3]` |
| FTS5 delete ordering | "to delete a row from both the content table and the FTS5 external content table, the FTS5 table must be updated first (so that the content table row is still available to it)." | `[CITED: sqlite.org/fts5.html §4.4.4.1]` |
| PRAGMA on an async engine | Listener must target `engine.sync_engine`, not `engine`: `@event.listens_for(engine.sync_engine, "connect")`. For `PRAGMA foreign_keys=ON` the docs note the sqlite3 driver "will not set PRAGMA foreign_keys if autocommit=False; set to True temporarily". | `[CITED: docs.sqlalchemy.org/en/20/dialects/sqlite.html, /orm/extensions/asyncio.html]` |
| Alembic dialect kwargs | `create_index(..., **kw)` — "Additional keyword arguments not mentioned above are dialect specific, and passed in the form `<dialectname>_<argname>`" ⇒ the partial unique index uses **`sqlite_where=`**. | `[CITED: alembic.sqlalchemy.org/en/latest/ops.html]` |
| Alembic batch-mode trap | "The table copy operation will currently not copy CHECK constraints, and may not copy UNIQUE constraints that are unnamed, as is possible on SQLite." | `[CITED: alembic.sqlalchemy.org/en/latest/ops.html]` |
| Tailwind 4 CLI | `npx @tailwindcss/cli -i ./src/input.css -o ./src/output.css`; the input starts with `@import "tailwindcss";`; explicit sources via `@source "../views";`; v4 "automatically bundles `@import` statements". Note the v4 CLI lives in `@tailwindcss/cli`, not `tailwindcss`. | `[CITED: tailwindcss.com/docs/installation/tailwind-cli, /docs/functions-and-directives, /docs/upgrade-guide]` |

## Migration 0001 — Design Contract

The 9-item checklist from ROADMAP/ARCHITECTURE §9.4 is the acceptance gate. This section adds the *mechanics* that make each item actually true on SQLite.

### Tables to create in 0001

| Table | Carries acceptance item | Notes |
|-------|-------------------------|-------|
| `sources` | **7** (`capabilities_json`, `tos_audited_at`) | Also `name` UQ, `display_name`, `enabled`, `transport`, `rate_limit_json`, `quota_json`, `last_probe_at`, `health`, `robots_policy_json` — the health strip reads the last two |
| `companies` | — | `name`, `name_norm` UQ, `aliases_json`; the dedup anchor |
| `listings` | **1, 8** | `first_seen_at`/`last_seen_at`/`content_hash` **NOT NULL**; `blocking_key` **indexed** |
| `listing_sources` | **6** | Both indexes; `source_listing_id` nullable |
| `listing_dupes` | — | Audit + `snapshot_json` + `reverted_at`. Table ships now; Tier-2 logic is Phase 2 |
| `listing_events` | **2** | Append-only; `occurred_at NOT NULL` |
| `listing_exclusions` | — | Phase 2 fills it; the table ships now so the filter's output has a home |
| `searches` | common pitfall **m10** | Per-search `last_run_at` — never a global |
| `runs` | — | `status`, `source_counts_json`, counts, `errors_json` |
| `scores` | **3** | `factor_scores_json`, `weights_json`, `criteria_version` (+ `rubric_version`, `backend`, `provider`, `model`) — **not `total_score` alone** |
| `cv_versions` | — | `facts_json`, `is_current` |
| `cv_artifacts` | **4** | `verification_json` + a `compile_status` that can be `'blocked'` |
| `applications` | **5** | `cv_artifact_id` FK NULL |
| `application_events` | — | Append-only |
| `llm_calls` | — | Cost/audit; Phase 3 fills it |
| `source_request_log` | D-03(b) | The politeness/quota ledger the probe evidence lives in |
| `listing_fts` + 3 triggers | — | FTS5 **external-content** virtual table; Phase 2 queries it, 0001 creates it so the schema is complete |

### Mechanics that are easy to get wrong

1. **Partial unique index (item 6).** In the model: `sa.Index("uq_listing_sources_source_sid", "source", "source_listing_id", unique=True, sqlite_where=sa.text("source_listing_id IS NOT NULL"))`. In the migration the same index via `op.create_index(..., unique=True, sqlite_where=sa.text("source_listing_id IS NOT NULL"))`. The **unconditional** partner is `sa.Index("uq_listing_sources_source_url", "source", "canonical_source_url", unique=True)`. Both must exist; neither alone satisfies QUEUE-02.
2. **FTS5 cannot be created with `op.create_table`.** Use `op.execute()` for the `CREATE VIRTUAL TABLE … USING fts5(title, company_norm, description, content='listings', content_rowid='id', tokenize='porter unicode61')` and for the three triggers, copied from the sqlite.org pattern in §Verified External Contracts 4 — including `VALUES('delete', old.id, …)` for the delete trigger. Creating the table without its triggers is the M4 failure mode: the index silently diverges and search misses newly inserted rows.
3. **Name every constraint; avoid `sa.Enum` on SQLite.** Because batch-mode table recreation drops **unnamed** CHECK/UNIQUE constraints, `sa.Enum` (which emits an unnamed CHECK on SQLite) is a trap for every future migration. Use `sa.String` + `sa.CheckConstraint(..., name="ck_cv_artifacts_compile_status")` — precisely so that item 4's `'blocked'` state survives later migrations.
4. **Two URLs, two engines.** Alembic runs on the **sync** driver (`sqlite:////data/jobsearch.db`) while the app runs `sqlite+aiosqlite:////data/jobsearch.db`; both point at the same file. Hold both in settings, never derive one from the other by string surgery inside a migration.
5. **PRAGMAs belong on the sync engine of the async engine** — `@event.listens_for(engine.sync_engine, "connect")` — and `foreign_keys=ON` needs the temporary `autocommit=True` dance quoted above, or it is a silent no-op (M8). `journal_mode=WAL` is persistent (a file property) but re-issuing it per connection is harmless and self-healing.
6. **Item 9 in practice:** an entrypoint that runs `alembic upgrade head` then `exec uvicorn …`, **plus** a build/CI step that exercises the same command against a throwaway SQLite file — proving the migration applies to a clean database, not merely that it was written. `Dockerfile` `RUN alembic -x db=… upgrade head` style smoke test, or a `tests/db/test_migration_contract.py` (recommended — see §Validation Architecture).
7. **Make the migration itself the schema test.** The strongest cheap verification of the whole checklist is a test that runs `alembic upgrade head` against a temp file and asserts every item via `PRAGMA table_info`, `PRAGMA index_list`, `PRAGMA index_info` and `sqlite_master`. That converts a 9-item prose checklist into 9 assertions that fail loudly — which is exactly what P8/P14 ask for.

7. **Make the migration itself the schema test.** The strongest cheap verification of the whole checklist is a test that runs `alembic upgrade head` against a temp file and asserts every item via `PRAGMA table_info`, `PRAGMA index_list`, `PRAGMA index_info` and `sqlite_master`. That converts a 9-item prose checklist into 9 assertions that fail loudly — which is exactly what P8/P14 ask for.

## Scraper-Survival Probe Design (the phase's primary research flag)

> "Scraping survives" is not a reading. It is a measurement Phase 1 must take (D-01…D-04). This section specifies the instrument, the envelope, the thresholds, and the decision rule. **No live scraping was performed during research** — every threshold below is a design decision, tagged accordingly.

### Two distinct instruments — do not conflate them

| | `probe()` — liveness | Survival measurement — the verdict |
|---|---|---|
| **Cost** | 1 cheap request per board | One bounded search per board (the real ingest path) |
| **Cadence** | On `/health` load, TTL-cached (e.g. 5 min) | Once per day, manual in Phase 1; scheduled in Phase 8 |
| **Output** | `Literal["ok","degraded","unreachable"]` | The five numeric signal families below + a written verdict |
| **Answers** | "Is the board reachable *right now*?" | "Does scraping survive at personal scale, and should Adzuna be promoted?" |
| **Never** | Raises, retries hard, or escalates | Aborts the run on one board's failure |

`probe()` must assert a *known answer*, not merely a 200 — a block page returns 200 and parses as valid HTML (P1). The cheapest sufficient assertion: fetch one fixed, known-stable public URL for the board and require (a) HTTP 200, (b) a body above a minimum length, (c) the presence of an expected structural marker, and (d) absence of the recorded stop-signal strings (CAPTCHA / "unusual activity" / forced-login markers). `degraded` = reachable but the marker is absent or a stop signal is present; `unreachable` = transport error or non-200.

### The five signal families (D-01)

Computed per source, per run, written to `runs.source_counts_json` / `sources.field_fill_baseline_json` / `source_request_log`.

**S1 — `FetchResult.status` outcome distribution.** Counts of `ok | partial | blocked | rate_limited | error` per source across the run. This is the headline signal and it is *the adapter's* to produce (R1: total function, never raises).

**S2 — Per-field fill-rate vs a recorded baseline.** For each source and each canonical field, `fill_rate = populated / total`, computed on the *normalised* records (post-sanitise, post-normalise, so an all-blank description counts as empty rather than as a non-null string):

`title`, `company_name`, `location_raw`, `description`, `posted_at`, `salary_min`, `salary_max`, `source_listing_id`, `direct_url`.

Baseline is written on the **first successful run per source** (`field_fill_baseline_json` on `sources`, with `baseline_recorded_at`), and the delta is `current − baseline` in percentage points. Corroborated thresholds `[CITED: dev.to schema-drift write-up; spyderproxy data-quality KPIs; link.sc]`:

- **WARN** at a **≥10-point** drop from the baseline or from the rolling 7-run average.
- **FAIL** at a **≥25-point** drop.
- Do **not** set a *target* fill-rate for `salary_min`/`salary_max` on this stack: per §JobSpy Verified Contract 2.5, JobSpy's description-salary extraction is USA-only and its regex is `$`-anchored, so an Irish search will show a *structurally low* salary fill-rate. Record what is observed and flag only *deltas* from it. This is the single most likely way to misread the probe as a failure.

**S3 — Output-count delta vs a trailing average.** `delta_pct = (count_now − trailing_mean(count, last N)) / trailing_mean`, with `N = 5`. Corroborated regression lines: the Apify freshness watchdog alerts at a **25%** row-count regression; `scraper-monitor` uses an expected count with a **±5%** tolerance band `[CITED: apify.com/convenient_yarn/scraper-freshness-watchdog; github.com/kingerson/scraper-monitor]`. Design: **WARN at ≤ −25%**, **FAIL at ≤ −50%**; require `≥2` prior runs before the signal is considered armed (otherwise it is a hard-coded guess, not a baseline). Rationale for being looser than ±5%: a job board's result count legitimately moves with the market, and a ±5% band on a personal-scale query would fire constantly.

**S4 — Freshness.** Two values: `newest_posted_at` (max `posted_at` returned) and `newest_first_seen_at` (max `first_seen_at` written). A source whose `newest_first_seen_at` stops advancing has silently stopped producing even if every other metric looks healthy `[CITED: shifter.io blogging; apify watchdog]`. FAIL if no new listing has been written for the source in **≥3 consecutive daily runs** while `FetchResult.status == "ok"` — the contradiction between "ok" and "nothing new" *is* the silent-breakage signature.

**S5 — Block-vs-parse classification.** A *fetch* problem (403, 429, CAPTCHA, forced login, suspiciously short body) and a *parse* problem (valid page, missing field) need opposite fixes and both present as empty data `[CITED: link.sc]`. Record `source_request_log.status_code`, `ok`, and a `note` distinguishing them; record the stop signals verbatim when seen and **stop — do not escalate** (P2). A `blocked`/`rate_limited` status with a plausible body is the "silent breakage" case and must be classified as fetch-side.

**S6 (cheap bonus, recommended) — schema drift.** The expected column contract is exactly JobSpy's `desired_order` (a fixed, pinned list — §Verified External Contracts 2). Any *missing* expected column is drift; a *renamed* column breaks the adapter at the normalise step. This costs one set-difference and catches a JobSpy upgrade or a board change that silently reshapes the DataFrame.

### The config-driven envelope (D-02, PLAT-04)

All of the following live in `settings` (env-overridable, no code change):

| Setting | Default | Rationale |
|---------|---------|-----------|
| `probe_max_requests` | `2` | 1 search + ≤1 detail pass per board |
| `probe_max_results` | `50` | The documented personal-scale ceiling is ≤50–100 (P2) |
| `probe_max_detail_fetches` | `0` in Phase 1 | `linkedin_fetch_description` is O(n) and "significantly increases the risk of rate limiting"; leave it **off** until a measured need appears |
| `probe_deadline_seconds` | `180` | Wall-clock ceiling per source |
| `probe_results_wanted` | `50` | Passed to `scrape_jobs(results_wanted=…)` — note the library default is `15`, so this must be explicit |
| `probe_country_indeed` | `"ireland"` | **Not** the library default `"usa"` |
| `probe_enabled` | `true` | Allows disabling the live probe without removing code |
| `description_max_chars` | e.g. `20000` | Truncation policy at sanitise time (C2) |

Documented operating envelope to state in the repo (not just in a plan): **1 search per board, ≤50–100 results, once per day, one IP, honest User-Agent.** This is the ban-risk line and it must be visible where a future contributor would change it.

### The verdict document and the three recording places (D-03)

1. **Repo document** — recommend `docs/probes/YYYY-MM-DD-scraper-survival.md`, committed. Contents: the raw per-source numbers, the baseline used, each signal's observed value vs its threshold, an explicit PASS/FAIL per signal, the **provisional/final** marker, and the Adzuna decision paragraph below. Naming/location is the planner's call (agent's discretion), but it must be dated and in-repo so it is greppable and diffable.
2. **Raw evidence rows** — `runs` (one row, with `source_counts_json` and `errors_json`) and `source_request_log` (one row per request, `kind ∈ {search, detail}`, `status_code`, `ok`, `note`). The verdict document must be *derivable from* these rows; if it is not, the instrumentation is incomplete.
3. **Surfaced status** — `probe()` result on `/health` and in the per-source health strip (SRC-07's "user can see"). The strip shows last success, listings returned this run, and the field fill-rate, per D-13.

### The Adzuna promotion condition (D-04) — the actionable rule

**Promote Adzuna from hedge to primary at Phase 8 if ANY of the following holds** on the Phase-1 probe evidence:

| # | Condition | Signal |
|---|-----------|--------|
| P-1 | A board returns `blocked` or `rate_limited` on **≥3 of 5** probe runs in the window | S1 |
| P-2 | A board's fill-rate for `title` **or** `company_name` **or** `location_raw` drops **≥25 points** below baseline on **≥2 consecutive** runs | S2 |
| P-3 | A board's output count falls **≤25% of the trailing average** on **≥2 consecutive** runs | S3 |
| P-4 | `probe()` reports `unreachable` on **≥2 consecutive** days | `probe()` |
| P-5 | A board returns `ok` with zero new listings for **≥3 consecutive** runs (the S4 contradiction) | S4 |

**Keep as hedge while:** both boards return `ok`/`partial`, `title`/`company_name`/`location_raw` fill-rate stays within 25 points of baseline, and output stays within 25% of the trailing average.

**Required properties of the written condition** (these are what make it actionable rather than decorative):
- It must **name which board failed**, because only one may need replacing — "scraping failed" is not a decision.
- It must state the **observation window and the run count** the verdict is based on, so a later reader can tell a 3-day measurement from a 30-day one.
- It must be **checkable by code**: the same thresholds live in settings and the verdict document cites them by name, so Phase 8 can re-evaluate without re-reading prose.
- If the evidence base is thinner than 5 runs, the verdict is written **PROVISIONAL** with the reason, and the Adzuna decision stays explicitly deferred to Phase 8 (which the roadmap already provides for). **Do not fabricate a verdict from one run** — that is the measurement equivalent of a fabricated CV claim.

### Instrumentation tasks this implies (the plan must contain them)

1. `probe()` implemented per adapter + TTL cache + `/health` surfacing + the health strip rendering.
2. Fill-rate computation and baseline recording on `sources`.
3. Trailing-average computation over `runs` per source.
4. `source_request_log` write on every outbound request (the politeness ledger).
5. A **fixture-driven test** for each signal's WARN/FAIL boundary (no network — P13/P14).
6. An operator runbook task: run the probe ≥3 times on ≥3 distinct days, then write the verdict document. **This is a phase deliverable, not a background hope** — schedule it explicitly, because a phase that ends with "the probe exists" but no recorded verdict fails success criterion 4.

## Architecture Patterns

### System Architecture Diagram — Phase 1 slice

```
  OPERATOR (browser, laptop)
        │
        │  1. GET /                (queue page, SSR)
        │  2. POST /runs  ─────────► "Run search now"
        │  3. GET /runs/{id}/status  (HTMX poll; 200 = keep polling, 286 = stop)
        ▼
┌─────────────────────────────── FastAPI app (uvicorn --workers 1) ────────────────────────────────┐
│                                                                                                  │
│  app/web/routes.py ──► Jinja2 (autoescape ON) ◄── app/web/templates/html/*                       │
│  app/api/*.py      ──► every route: user: User = Depends(current_user)   ◄── app/api/deps.py      │
│                                                                                                  │
│  ┌── POST /runs handler ────────────────────────────────────────────────────────────────────────┐ │
│  │  create runs row (status=running) → spawn background task → return 202 + status fragment     │ │
│  └──────────────────────┬───────────────────────────────────────────────────────────────────────┘ │
│                         ▼  asyncio.create_task                                             (never   │
│  ┌── pipeline/run.py : run_pipeline(trigger, search_id) ──────────────────────── inline in a      │ │
│  │                                                                              request)          │ │
│  │  for each enabled source (concurrently, each with its own FetchBudget):                       │ │
│  │     ┌──────────────────────────────────────────────────────────────┐                          │ │
│  │     │ sources/linkedin.py  ──┐                                     │                          │ │
│  │     │                       ├──► sources/_jobspy_transport.py     │                          │ │
│  │     │ sources/indeed.py    ──┘     (the ONLY `import jobspy`)     │                          │ │
│  │     │        │  asyncio.to_thread( jobspy.scrape_jobs(site_name="linkedin" | "indeed", …) )  │ │
│  │     │        ▼                                                                                │ │
│  │     │  DataFrame (desired_order) ──► map to RawListing  ──► FetchResult(status=…)            │ │
│  │     └────────┬───────────────────────────────────────────────┬──────────────────────────────┘ │ │
│  │              │ DROP `emails` here (never mapped)             │ source_request_log row          │ │
│  │              ▼                                              ▼                                 │ │
│  │     ingest/sanitize.py → domain/sanitize.py   (PII, HTML, truncate)   [pure]                   │ │
│  │              ▼                                                                                │ │
│  │     domain/listing.py   (canonical_url, content_hash, salary→annual)  [pure]                   │ │
│  │              ▼                                                                                │ │
│  │     db/repositories/listing_repo.py                                                            │ │
│  │        Tier-0 in-run collapse (canonical_url, in memory)                                       │ │
│  │        Tier-1 upsert: key A (source, source_listing_id) if not NULL → else key B               │ │
│  │                      (source, canonical_source_url); UPDATE last_seen_at / content_hash        │ │
│  │              ▼                                                                                │ │
│  │     UPDATE runs (status=done|partial, source_counts_json, errors_json)                          │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                                  │
│  app/domain/*  ── import discipline enforced by tests/test_import_discipline.py ──                │
│  (no httpx | sqlalchemy | jobspy | jinja2 | subprocess)                                           │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
        │                                          │
        ▼                                          ▼
┌───────────────────────────┐        ┌──────────────────────────────────────────┐
│ SQLite  /data/jobsearch.db│        │ opencode server (EXTERNAL, user-managed) │
│  WAL · foreign_keys=ON    │        │  host.docker.internal:4096 (extra_hosts) │
│  listings/listing_sources │        │  GET /global/health   → boot-tolerant    │
│  listing_events · runs    │        │  GET /config/providers→ IDs ONLY, never  │
│  source_request_log       │        │                        logged or stored   │
│  listing_fts (FTS5)       │        │  (Phase 1 makes NO LLM call)             │
└───────────────────────────┘        └──────────────────────────────────────────┘
```

The reader can trace the primary use case — press Run, see a listing — by following the arrows from the browser down through the adapter, sanitise, normalise and upsert, then back up through the status poll.

### Recommended Project Structure (Phase-1 subset of ARCHITECTURE §3)

```
job-search/
├── pyproject.toml                 # exact pins (no floating ranges)
├── compose.yml                    # app service only; extra_hosts for host.docker.internal
├── Dockerfile                     # multi-stage: python:3.13-slim; Tailwind CLI build; alembic smoke
├── alembic.ini                    # SYNC url
├── alembic/versions/0001_*.py     # the one-way migration
├── app/
│   ├── main.py                    # app factory + lifespan (opens nothing that can fail hard)
│   ├── config.py                  # pydantic-settings: the whole Phase-1 settings surface
│   ├── api/
│   │   ├── deps.py                # current_user()
│   │   ├── runs.py                # POST /runs, GET /runs/{id}/status
│   │   └── health.py              # /health: db, opencode, per-source probe
│   ├── web/
│   │   ├── routes.py              # GET / (queue list + empty state + count + health strip)
│   │   └── templates/html/        # base.html, queue.html, _health_strip.html, _run_status.html
│   │                              # (templates/latex/ is Phase 4)
│   ├── domain/                    # PURE. No I/O imports. Enforced by a test.
│   │   ├── models.py              # Listing, ListingSourceRef, RawListing, NormalisedListing
│   │   ├── listing.py             # canonical_url + content_hash + salary normalisation
│   │   └── sanitize.py            # PII + HTML + truncation (pure)
│   ├── sources/
│   │   ├── base.py                # JobSource ABC, SourceCapabilities, SearchQuery, FetchResult, FetchBudget
│   │   ├── registry.py            # name → adapter class
│   │   ├── _jobspy_transport.py   # the ONLY module that imports jobspy
│   │   ├── linkedin.py
│   │   └── indeed.py
│   ├── ingest/
│   │   └── sanitize.py            # stage wrapper (calls domain.sanitize) + logging
│   ├── pipeline/
│   │   ├── run.py                 # run_pipeline(trigger, search_id)  ← one path, two triggers
│   │   └── stages.py              # stage protocol + run-log instrumentation
│   ├── llm/
│   │   ├── base.py                # LLMBackend Protocol + redaction boundary       ← Phase 1: health only
│   │   └── opencode_server.py     # httpx: /global/health, /config/providers (Phase 3 adds calls)
│   ├── probe/
│   │   ├── probe.py               # probe() per source + TTL cache
│   │   └── survival.py            # S1–S6 signal computation + thresholds
│   └── db/
│       ├── base.py  session.py  models.py
│       └── repositories/listing_repo.py
├── static/vendor/                 # htmx.min.js, alpine.min.js, app.css (built, vendored — no CDN)
├── data/                          # volume: jobsearch.db (+ -wal, -shm)
├── docs/probes/                   # the dated verdict documents
└── tests/
    ├── domain/                    # pure unit tests (fast, no DB, no network)
    ├── sources/                   # adapter + capabilities + probe tests
    ├── db/                        # migration contract, upsert, PRAGMA, PII-negative
    ├── pipeline/                  # partial-failure, background, deadline
    ├── fixtures/listings/         # captured/synthetic raw payloads per source
    └── test_import_discipline.py  test_no_credentials.py  test_no_cdn.py
```

### Pattern 1 — Total functions at the boundary
**What:** every external call returns a result object; expected failures never raise. `FetchResult(status=…)`, `probe() → Literal[…]`, and a `ProbeOutcome` for discovery failures.
**When:** all adapter calls, the opencode health/discovery calls, and the compile call in later phases.
**Why here:** it is *the* pattern that makes `runs.status='partial'` meaningful and prevents one board's 429 from emptying the queue (P10/SRC-05).

```python
# Source: ARCHITECTURE.md §5.1 (verbatim contract, restated for Phase 1)
@dataclass(frozen=True)
class FetchResult:
    source: SourceName
    items: list[RawListing] = field(default_factory=list)
    status: Literal["ok", "partial", "blocked", "rate_limited", "error"] = "ok"
    requests_used: int = 0
    error: str | None = None
```

### Pattern 2 — Normalise once, at the boundary
**What:** `RawListing` (board-shaped) → `NormalisedListing` (canonical) in one pure function, which also computes `canonical_url` and `content_hash`.
**When:** immediately after sanitise, before any persistence.
**Why here:** both dedup keys depend on it, and purity makes it unit-testable without a database or a network.

### Pattern 3 — Sanitise is a named stage, not a helper
**What:** `ingest/sanitize.py` wraps the pure `domain/sanitize.py`, so it has a name, a log line and a counter.
**When:** the single point between "raw observation" and "anything persisted or prompted".
**Why here:** it is simultaneously the GDPR control, the injection control and the PII control; a helper buried in the adapter would silently diverge across two adapters.

### Pattern 4 — The auth seam plus a test that proves it is universal
**What:** `user: User = Depends(current_user)` on every route, and an **introspection test** that walks `app.routes` and asserts each route's dependant tree contains `current_user`.

```python
# tests/test_auth_seam.py — the test that makes PLAT-03 falsifiable
def test_every_route_declares_current_user(app):
    missing = []
    for route in app.routes:
        if not getattr(route, "dependant", None):
            continue
        if not _depends_on(route.dependant, current_user):
            missing.append(getattr(route, "path", repr(route)))
    assert missing == [], f"routes without current_user: {missing}"
```
A route added later without the seam fails CI. That is worth more than the seam itself.

### Pattern 5 — One pipeline callable, two triggers
**What:** `pipeline/run.py:run_pipeline(trigger, search_id)` is a plain async callable. `POST /runs` enqueues it and returns `202` **immediately**; Phase 8's scheduler will call the same function.
**When:** from the first runnable pipeline (D-22).
**Why here:** manual and scheduled runs stay behaviourally identical and share one log, one budget and one failure path. The trade-off is that the UI must poll — which is why D-13 specifies status polling.

### Pattern 6 — Persist the observation, not just the conclusion
**What:** `runs` rows carry per-source counts and structured errors; `source_request_log` carries the politeness ledger; `sources` carries the fill-rate baseline.
**When:** from migration 0001.
**Why here:** "why is the queue empty?" and "did LinkedIn block us or did nothing match?" must be answerable from the database months later (P9).

### Anti-Patterns to Avoid (the ones Phase 1 can actually commit)

- **The single-`ON CONFLICT` upsert.** Looks correct, silently inserts duplicates whenever `source_listing_id` is NULL — which is a documented JobSpy contract, not an edge case (AP7/m9).
- **Running the pipeline inside the request handler.** LLM-free Phase 1 runs still take tens of seconds; the request times out and the UI looks broken (AP6).
- **Calling `jobspy.scrape_jobs` anywhere but `_jobspy_transport.py`.** Every board breakage becomes a codebase-wide risk and per-board escalation becomes impossible (AP1).
- **Passing `site_name=["linkedin","indeed"]`.** One failure domain, no per-board budget/health attribution (AP16).
- **Building the credentialed path "for when it breaks".** The bright line is architectural: it must not exist to be reasoned about (P2). A static test enforces it.
- **Adding `user_id` columns "for later auth".** Complexity now, a guessed model, and every unique constraint complicated — for a feature explicitly deferred (AP14).
- **Creating the FTS table without its triggers.** The index silently diverges and search misses new rows (M4).
- **`sa.Enum` for `compile_status`.** Emits an unnamed CHECK that a later batch migration silently drops (see §Migration 0001 Mechanics 3).
- **Logging the opencode discovery response.** It contains a plaintext provider key (D-11) — this is the phase's most concrete security mistake.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LinkedIn/Indeed parsing | Your own scrapers | JobSpy at the pinned commit, behind per-board adapters | Reverse-engineered internals + ongoing board drift; MIT; already does TLS impersonation on the LinkedIn path |
| Retry/backoff on transport | A hand-rolled loop | `tenacity` | Jitter, exponential backoff and stop-condition correctness; and it makes "stop, don't escalate" explicit in code |
| Migrations | `Base.metadata.create_all()` in the app path | Alembic 1.20.0 from 0001 | `create_all` cannot evolve the non-backfillable schema and destroys the Postgres portability path |
| Queue search | `LIKE '%term%'` | FTS5 external-content + BM25 `rank` | Index-less scans; FTS5 is in the stdlib amalgamation and "shockingly good" at this size (M4) |
| Full-text index maintenance | Manual reindex calls | The three SQLite triggers, created with the virtual table | Missing one trigger is the silent-divergence failure; SQLite fires them for free |
| URL canonicalisation | Ad-hoc string cleanup at each call site | One pure `canonical_url()` in `domain/listing.py` | Tracking params (`utm_*`, `gh_src`, `lever-source`, `trk`…), default ports, query ordering, trailing slash — every miss is a duplicate that Tier-1 fails to catch |
| HTML stripping | Regex tag removal | JobSpy's `description_format="markdown"` + a small, tested boilerplate reducer | Regex HTML parsing is the canonical footgun; JobSpy already ships `markdownify`/`bs4` |
| Config plumbing | `os.environ.get` scattered through the code | `pydantic-settings` (2.15.0), one `Settings` class | Typed defaults, `.env` loading, and PLAT-04 is satisfiable by inspection |
| CSS | Hand-written stylesheets | Tailwind CLI at image build, vendored output | D-14 is a deliberate long-term bet; re-styling every template later is the expensive path |
| UI partial updates | A hand-rolled `fetch`/`setInterval` poll | HTMX `hx-trigger="every Ns"` + HTTP 286 to stop | The stop condition is the fiddly part and htmx has a defined protocol for it |
| Structured run logging | `print`/bare `logging` | `structlog` with stage names and counters | "Which stage dropped 90%?" must be greppable, not excavated |

**Key insight:** in this phase every hand-rolled candidate is a *silent-failure* candidate. The stack's whole design — total `FetchResult`s, one importer for jobspy, FTS5 triggers, Alembic from 0001 — exists to convert silent wrongness into loud signals. Building any of it by hand reintroduces exactly the failure mode the phase is trying to make observable.

## Code Examples

Verified patterns for the Phase-1 shapes that are not obvious.

### Two-Key Tier-1 Upsert (the ordered lookup — not a single `ON CONFLICT`)

```python
# app/db/repositories/listing_repo.py — shape, not final code
async def upsert_listing_source(session, *, source: str, norm: NormalisedListing,
                                run_id: int, now: datetime) -> UpsertOutcome:
    """Two-key Tier-1. Order matters: key A only applies when the value is not NULL.

    Why not one `insert(...).on_conflict_do_update(index_elements=["source",
    "source_listing_id"])`? Because SQLite treats NULLs as distinct in a UNIQUE
    index, so when JobSpy returns id=None the conflict NEVER fires and the
    statement inserts a duplicate on every run. That is PITFALLS m9 / AP7.
    """
    row = None
    if norm.source_listing_id is not None:
        row = await session.scalar(
            select(ListingSource).where(
                ListingSource.source == source,
                ListingSource.source_listing_id == norm.source_listing_id,
            )
        )
    if row is None:
        row = await session.scalar(
            select(ListingSource).where(
                ListingSource.source == source,
                ListingSource.canonical_source_url == norm.canonical_url,
            )
        )
    if row is not None:
        row.last_seen_at = now
        # content_hash change ⇒ repost/update signal (Phase 2 acts on it)
        return UpsertOutcome(kind="updated", listed_source_id=row.id)

    # INSERT; a concurrent inserter (background run vs request) can still race —
    # catch IntegrityError, re-SELECT, and treat that as 'updated'.
    ...
    return UpsertOutcome(kind="created", listed_source_id=new_row.id)
```

The index pair that makes this correct (see §Migration 0001 Mechanics 1): a **partial** unique index on `(source, source_listing_id) WHERE source_listing_id IS NOT NULL` **and** an **unconditional** unique index on `(source, canonical_source_url)`.

### PRAGMAs on an async engine (the documented target is `sync_engine`)

```python
# app/db/session.py
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(settings.database_url_async)  # sqlite+aiosqlite:////data/jobsearch.db

@event.listens_for(engine.sync_engine, "connect")   # ← sync_engine, per SQLAlchemy async docs
def _sqlite_pragmas(dbapi_connection, connection_record):
    # SQLAlchemy's SQLite docs: the driver will NOT apply PRAGMA foreign_keys
    # while autocommit is False. Toggle it for the duration of the pragma.
    ac = dbapi_connection.autocommit
    dbapi_connection.autocommit = True
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()
    dbapi_connection.autocommit = ac
```

`[CITED: docs.sqlalchemy.org/en/20/dialects/sqlite.html + /orm/extensions/asyncio.html]` — both the `sync_engine` target and the autocommit dance come from those pages, quoted in §Verified External Contracts 4.

### Migration 0001 — partial unique index, named CHECK, FTS5 virtual table

```python
# alembic/versions/0001_initial.py
def upgrade() -> None:
    op.create_table(
        "listing_sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("source", sa.String(32), sa.ForeignKey("sources.name"), nullable=False),
        sa.Column("source_listing_id", sa.String(255), nullable=True),   # JobSpy id can be None
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("canonical_source_url", sa.Text, nullable=False),
        sa.Column("direct_url", sa.Text, nullable=True),
        sa.Column("first_seen_at", sa.DateTime, nullable=False),
        sa.Column("last_seen_at", sa.DateTime, nullable=False),
        sa.Column("raw_hash", sa.String(64), nullable=False),
    )
    # Acceptance item 6 — BOTH indexes; neither alone is sufficient.
    op.create_index("uq_listing_sources_source_sid", "listing_sources",
                    ["source", "source_listing_id"], unique=True,
                    sqlite_where=sa.text("source_listing_id IS NOT NULL"))   # ← dialect kwarg form
    op.create_index("uq_listing_sources_source_url", "listing_sources",
                    ["source", "canonical_source_url"], unique=True)

    # Acceptance item 4 — explicitly NAMED check, because a later
    # batch_alter_table recreates the table and drops UNNAMED CHECK constraints.
    op.create_table(
        "cv_artifacts",
        # …
        sa.Column("compile_status", sa.String(16), nullable=False),
        sa.CheckConstraint("compile_status IN ('ok','failed','blocked')",
                           name="ck_cv_artifacts_compile_status"),
        sa.Column("verification_json", sa.JSON, nullable=True),
    )

    # FTS5 cannot be expressed as a Table — raw DDL, and the triggers MUST ship
    # with it or the index silently diverges (PITFALLS M4).
    op.execute("""
        CREATE VIRTUAL TABLE listing_fts USING fts5(
            title, company_norm, description,
            content='listings', content_rowid='id',
            tokenize='porter unicode61');
    """)
    op.execute("""
        CREATE TRIGGER listings_ai AFTER INSERT ON listings BEGIN
          INSERT INTO listing_fts(rowid, title, company_norm, description)
          VALUES (new.id, new.title, new.company_norm, new.description);
        END;
    """)
    op.execute("""
        CREATE TRIGGER listings_ad AFTER DELETE ON listings BEGIN
          INSERT INTO listing_fts(listing_fts, rowid, title, company_norm, description)
          VALUES('delete', old.id, old.title, old.company_norm, old.description);
        END;
    """)
    op.execute("""
        CREATE TRIGGER listings_au AFTER UPDATE ON listings BEGIN
          INSERT INTO listing_fts(listing_fts, rowid, title, company_norm, description)
          VALUES('delete', old.id, old.title, old.company_norm, old.description);
          INSERT INTO listing_fts(rowid, title, company_norm, description)
          VALUES (new.id, new.title, new.company_norm, new.description);
        END;
    """)
```

`[CITED: alembic.sqlalchemy.org/en/latest/ops.html (dialect kwargs, batch-mode constraint caveat); sqlite.org/fts5.html §4.4.3 (trigger DDL, quoted verbatim in §Verified External Contracts 4)]`

### The blocking-call boundary and the deadline caveat

```python
# app/sources/_jobspy_transport.py — the ONLY module allowed to `import jobspy`
import asyncio, jobspy

async def run_scrape(*, site: str, kwargs: dict, deadline_s: float) -> object:
    """JobSpy is synchronous and spawns its own ThreadPoolExecutor internally
    (verified in jobspy/__init__.py), so it MUST NOT run on the event loop.
    """
    # NOTE: scrape_jobs() does NOT accept request_timeout — ScraperInput's
    # request_timeout=60 is not passed through (verified). So the *only* time
    # bound we can impose is the outer wait_for below. asyncio.to_thread cannot
    # be cancelled: on timeout the worker thread keeps running to completion in
    # the background. Therefore the real budget control must be PRE-CALL
    # (refuse to start a fetch whose remaining budget cannot cover it) and the
    # timeout is a UI-protection guard, not a hard kill.
    return await asyncio.wait_for(
        asyncio.to_thread(jobspy.scrape_jobs, site_name=site, **kwargs),
        timeout=deadline_s,
    )
```

Two consequences for the plan: (1) `FetchBudget.deadline` is advisory at the transport and must be enforced as a **pre-call** decision plus a `status="error"`/`"partial"` outcome on timeout; (2) a per-source detail pass (`linkedin_fetch_description=True`) must be a *separate* budgeted call (R4), because it multiplies requests by O(n) and cannot be abandoned mid-flight.

### HTMX polling with the documented stop condition

```html
<!-- app/web/templates/html/_run_status.html -->
<div id="run-status"
     hx-get="/runs/{{ run.id }}/status"
     hx-trigger="every 2s"
     hx-swap="outerHTML">
  Running… {{ run.stage }} ({{ run.fetched_count }} fetched)
</div>
```

```python
# app/api/runs.py — the server decides when polling stops
@router.get("/runs/{run_id}/status")
async def run_status(run_id: int, user: User = Depends(current_user), ...):
    run = await repo.get_run(run_id)
    if run.status in {"done", "partial", "failed"}:
        # HTTP 286 is htmx's documented "stop polling" signal.
        return Response(
            content=render_run_fragment(run),
            status_code=286,
            headers={"HX-Reswap": "outerHTML"},
        )
    return templates.TemplateResponse("_run_status.html", {"run": run})
```

`[CITED: htmx.org/docs — "respond with HTTP status code 286 … the element will cancel the polling"]`. The failure to avoid is a poll that never terminates after the run finishes (a silent battery/latency leak that is invisible until the machine is on battery).

### `compose.yml` — app only, with host access for the external opencode server

```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]            # v1 is local-only; do not expose beyond the host
    volumes:
      - ./data:/data                # jobsearch.db (+ -wal, -shm) — back up the WAL too (M8)
    extra_hosts:
      - "host.docker.internal:host-gateway"    # makes the OPENCODE_BASE_URL default work on Linux
    environment:
      - OPENCODE_BASE_URL=${OPENCODE_BASE_URL:-http://host.docker.internal:4096}
      - OPENCODE_MODEL=${OPENCODE_MODEL:-deepseek-v4.1-flash}
      - OPENCODE_SERVER_PASSWORD=${OPENCODE_SERVER_PASSWORD:-}   # from an uncommitted .env
      - DATABASE_URL=sqlite+aiosqlite:////data/jobsearch.db
      - DATABASE_URL_SYNC=sqlite:////data/jobsearch.db           # Alembic uses this
    command: ["./entrypoint.sh"]     # alembic upgrade head; exec uvicorn app.main:app --workers 1
    # NO depends_on. opencode is external and user-managed (D-05); nothing in
    # `docker compose up` may depend on an LLM backend being reachable (D-08).
```

`[CITED: docs.docker.com/compose/how-tos/networking for `extra_hosts` / `host-gateway`]`. **Deliberately absent:** an `opencode` service, a dependency on it, and any published 4096 port (M10).

### Fields to derive at normalise time (the small pure functions that carry the dedup guarantee)

```python
# app/domain/listing.py — pure, no I/O, unit-testable
TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"gh_src", "lever-source", "src", "ref", "trk"}

def canonical_url(raw: str, direct: str | None = None) -> str:
    """Lowercase scheme+host, drop default port, strip tracking params, sort the
    rest, drop the fragment, normalise a trailing slash. Prefer `direct` (the
    employer's own listing) when present — it is the Tier-2a cross-source signal."""
    ...

def content_hash(*, title: str, company_name: str | None, location_raw: str | None,
                 description: str | None) -> str:
    """Stable hash over the SANITISED fields. Used for repost/update detection
    and as a Tier-2c duplicate signal. Must not include volatile fields
    (e.g. salary or last_seen_at) or every run looks like a change."""
    ...

def annualise_salary(minimum, maximum, interval, currency):  # memo: Ireland ⇒ JobSpy gives
    ...                                                       # no description-derived salary
```

## Common Pitfalls

### Pitfall 1 — Treating a green run as a healthy scrape
**What goes wrong:** a board renames a CSS class or starts serving a block page; HTTP stays 200, the parse "succeeds", the run reports `done`, and the queue quietly thins out or fills with nulls. Nobody notices until the user compares against the portal (P1).
**Why it happens:** the fetch succeeded and the parse succeeded, so nothing looks abnormal. Row count and error rate do not move; only per-field fill-rate does.
**How to avoid:** the five probe signal families (§Scraper-Survival Probe Design), per-source (not global) success rate, and a `probe()` that asserts a **known answer** rather than a 200.
**Warning signs:** fetched count drops 200 → 4 with no error; one field's fill-rate falls off a cliff; `status='done'` with `ranked_count=0` and no recorded reason.

### Pitfall 2 — Building the credentialed path "just in case"
**What goes wrong:** the first block triggers "add a session cookie / log in as the user", converting a maintenance problem into a personal account-ban problem with the user's real professional identity as collateral (P2). AIHawk's contributors were banned and the project retreated from LinkedIn entirely.
**Why it happens:** every tutorial and JobSpy's own `JOBSPY_CREDS` fallback make it the obvious next rung.
**How to avoid:** the bright line is **architectural** — make the credential path unrepresentable. `RawListing` has no credential/session field; no adapter reads `LINKEDIN_*`/`INDEED_*`; a static test asserts the absence (`tests/test_no_credentials.py`). Also encode the stop signals (CAPTCHA / forced re-login / "unusual activity" / sudden result drop) as "stop and rest", never "retry harder".
**Warning signs:** a `LINKEDIN_USERNAME` read anywhere; a design note saying "when blocked, fall back to authenticated scraping"; `results_wanted` raised above the documented envelope.

### Pitfall 3 — A `UNIQUE` key that silently does nothing
**What goes wrong:** `UNIQUE(source, source_listing_id)` is accepted as the Tier-1 upsert key, but JobSpy documents `id` as `str | None` and SQLite treats NULLs as *distinct*. On any board that omits `id`, the constraint permits unlimited duplicates — the exact failure it was added to prevent (P3/AP7/m9).
**How to avoid:** the two-key design (D-19) with the **ordered** lookup in §Two-Key Tier-1 Upsert, plus a seeded test that inserts the same listing twice with `source_listing_id=None` and asserts exactly one row.
**Warning signs:** duplicates multiplying on one board while `PRAGMA index_list` shows the unique index exists; `id` never populated in `source_extras`.

### Pitfall 4 — The blocking call that freezes the UI
**What goes wrong:** JobSpy runs on the event loop inside the single uvicorn worker; the browser hangs for the whole scrape, `/health` takes seconds, and it looks like a crash (M3). This is documented as the *first* real scaling pain.
**Why it happens:** the naive `await scrape_jobs(...)` compiles fine and works in a demo with three results.
**How to avoid:** `asyncio.to_thread` at the transport boundary (§blocking-call boundary), `run_pipeline()` enqueued rather than awaited (Pattern 5), and — because `to_thread` cannot be cancelled — a **pre-call** budget check rather than relying on the timeout to reclaim resources.
**Warning signs:** the tab hangs during a run; a `/health` request takes seconds mid-run; the pipeline is awaited inside a handler.

### Pitfall 5 — `FetchBudget.deadline` that JobSpy cannot honour
**What goes wrong:** the design says the adapter enforces a deadline; the implementation passes a timeout that `scrape_jobs()` silently ignores (it accepts `**kwargs` and does not forward `request_timeout`), so a hung board blocks a worker thread indefinitely.
**How to avoid:** the outer `asyncio.wait_for(asyncio.to_thread(...))` as a UI-protection guard, **plus** a pre-call budget check, **plus** recording a `status="error"`/`"partial"` outcome on timeout (never raising — R1). Document the thread-leak caveat in the transport docstring so a later reader does not assume cancellation works.
**Warning signs:** a run that never reaches `finished_at`; a thread count that grows across runs; `deadline` set but never read.

### Pitfall 6 — `country_indeed` left at its default
**What goes wrong:** JobSpy's default is `country_indeed="usa"`; omitting it returns US listings that look perfectly valid. In a Dublin-based search this silently poisons the corpus *and* the probe baseline, and the error is invisible because every record parses.
**How to avoid:** set `country_indeed="ireland"` explicitly (`Country.IRELAND = ("ireland","ie","ie")` is the enum member), and assert it in an adapter test that fails if the literal is absent.
**Warning signs:** US city names in `location_raw`; a suspiciously rich salary fill-rate (because US compensation is structured) that collapses once the country is fixed.

### Pitfall 7 — Sanitising more (or less) than Phase 1 owns
**What goes wrong:** two opposite failures. Over-reaching: building the full `_INJECTION_PATTERNS` catalogue now, which is an explicitly deferred Phase-2 task. Under-reaching: storing `emails` because JobSpy provides it, which is a direct SRC-10 violation.
**How to avoid:** Phase 1 ships the **named stage** with (a) email/phone stripping, (b) HTML/boilerplate reduction + whitespace collapse, (c) description truncation to `description_max_chars`, and (d) a **flag field** for detected instruction-like text — with the *pattern catalogue itself* left for Phase 2. Drop PII; **do not hash it** (a hashed phone number is still personal data and serves no product purpose) and never log the removed value — record only a count.
**Warning signs:** `emails` appearing in any model, DB column, log line or template; an injection regex set landing in Phase 1; the sanitise stage having no log line or counter.

### Pitfall 8 — SQLite configured by default
**What goes wrong:** `journal_mode=DELETE` blocks readers during writes; `foreign_keys=OFF` means referential integrity is silently unenforced; an unset `busy_timeout` turns mild contention into immediate `database is locked`; and a backup that copies only `jobsearch.db` loses committed-but-uncheckpointed WAL data (M8).
**How to avoid:** the PRAGMA listener above (note the `autocommit` requirement for `foreign_keys`), a connection-level test that asserts all four pragmas, and a documented backup that includes `-wal`/`-shm` (or SQLite's online-backup API). Verify `ENABLE_FTS5` via `PRAGMA compile_options` **in the container**, not on the host — Python's stdlib amalgamation ships it, but that is a claim to check, not assume.
**Warning signs:** `database is locked`; FK violations not caught; a restored backup missing the last run's writes.

### Pitfall 9 — Migration 0001 that is *not quite* the checklist
**What goes wrong:** "we'll add `listing_events` when we need it" / "`total_score` is enough for now" / "`blocking_key` can be a view". Each omission describes the past and cannot be backfilled (P8). Recovery cost is **unrecoverable**.
**How to avoid:** turn the 9-item checklist into 9 assertions in `tests/db/test_migration_contract.py` that run `alembic upgrade head` on a temp file and introspect `PRAGMA table_info` / `index_list` / `sqlite_master`. Also add the negative assertions (e.g. `first_seen_at` is `NOT NULL`, not merely present).
**Warning signs:** a migration review containing "when we need it"; a `scores` table with only `total_score`; `listing_events` absent because "nothing reads it yet".

### Pitfall 10 — A partially-failed run presented as a whole failure
**What goes wrong:** one board returns `partial`/`blocked` and the run either aborts (no queue that morning) or reports a clean success (the user believes the corpus is complete). Both destroy the story the queue is supposed to tell (P10, D-13's discretion item).
**How to avoid:** the run's status is `partial` when any source is not `ok`; the UI must name the degraded source *and* state what the `ok` source delivered ("37 from Indeed · LinkedIn rate-limited after page 4"). This is the planner's discretion area — the bound is SRC-05 (never abort) plus the observation that a `partial` that looks identical to `ok` is a trust failure, not a cosmetic one.
**Warning signs:** a single `status` for the whole pipeline with no per-source counts; a `blocked` board rendering as an empty list with no message.

### Pitfall 11 — Logging or persisting the opencode discovery response
**What goes wrong:** `GET /config/providers` returns the provider API key in plaintext (D-11, verified on the user's own server). A single `logger.debug(response.json())`, a cached `raw_response` on a model, or a stored fixture checked into git leaks a live credential.
**How to avoid:** parse into a Pydantic model with **only** `provider.id` and `model.id` fields; never bind the raw body to a long-lived variable; assert the absence with a test that runs discovery against a fixture containing a sentinel key and then scans `caplog` output **and** every table for that sentinel.
**Warning signs:** `response.text` in a log; a `raw` field on the discovery model; a test fixture containing a real-looking key.

### Pitfall 12 — Phase-1 asset pipeline done in the browser
**What goes wrong:** HTMX/Alpine/Tailwind are referenced from a CDN "temporarily", or the Tailwind CLI is expected at runtime. The local self-hosted tool then breaks or loses its styling offline — a UI-07 violation (m4) that is invisible on a machine that happens to be online.
**How to avoid:** vendor `htmx.min.js` and `alpine.min.js` into `static/vendor/`; run `@tailwindcss/cli` at image build with `@import "tailwindcss";` plus an explicit `@source "../templates";` pointing at the Jinja templates; serve everything through `StaticFiles`. A static test scans templates for `http://`/`https://` asset references and fails.
**Warning signs:** an `integrity=` CDN link; a template referencing `unpkg`/`jsdelivr`/`cdn`; Tailwind classes with no built `app.css`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact for this phase |
|--------------|------------------|--------------|------------------------|
| `pip install python-jobspy` (PyPI 1.1.82, 2025-07-28) | Install from git at a pinned commit (`fda080a…`, 2026-02-18) | PyPI has lagged the repo since 2025; the repo's URL moved to `speedyapply/JobSpy` | The pinned commit *is* the LinkedIn date-parsing fallback; the PyPI release predates it |
| APScheduler 4.x | APScheduler **3.11.3** (4.0 is still alpha) | 4.0.0a6 was 2025-04-27 and has not stabilised | Phase 1 only needs to *not* preclude it: `--workers 1` now, scheduler wiring in Phase 8 |
| `tailwindcss` CLI | **`@tailwindcss/cli`** package, config-less v4 | v4 moved the CLI and made `@import "tailwindcss"` + `@source` the configuration surface | The image-build command must name the new package or it resolves the wrong binary |
| HTMX "just poll forever" | Explicit `hx-trigger="every Ns"` **+ HTTP 286 to stop** | Documented htmx protocol | A poll with no stop condition is a battery/latency leak |
| `sa.Enum` for status columns on SQLite | `sa.String` + an **explicitly named** `CheckConstraint` | Alembic's batch-mode recreation drops unnamed CHECK/UNIQUE constraints (documented caveat) | Directly protects acceptance item 4 (`compile_status='blocked'`) through Phase 6's migrations |
| `sqlite3` + hand-managed connections | SQLAlchemy 2.0 async + `aiosqlite`, PRAGMAs via `sync_engine` listeners | Documented async pattern | The `sync_engine` target and the autocommit requirement are both non-obvious and both verified |
| FTS4 / `LIKE` search | **FTS5 external-content** + BM25 `rank` | Stdlib amalgamation since 3.9 | External-content keeps the description out of a second copy; the triggers are the maintenance contract |

**Deprecated / outdated:**
- **Indeed Publisher API** — retired; no self-serve read API exists. Do not chase an "Indeed API key" tutorial (STACK Q1).
- **LinkedIn official read APIs** — employer-side only; "not accepting new partnerships". Ruled out.
- **`python-jobspy` on PyPI** — stale, and its project URL 301-redirects.
- **APScheduler 4.x** — alpha; API churn.
- **`--workers > 1` with any future in-process scheduler** — N workers ⇒ N schedulers.
- **A single `UNIQUE(source, source_listing_id)` as the Tier-1 key** — silently degraded by nullable `id`.

## Assumptions Log

> Every claim below is `[ASSUMED]` — based on training knowledge or inference, **not** verified this session. Each needs confirmation before it becomes a locked plan decision.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pydantic-settings` **2.15.0** is the correct current pin for the settings layer (STACK.md did not specify one) | §Standard Stack | Low — any 2.x works; a wrong pin only surfaces at install. Verify with `pip index versions` at lock time |
| A2 | The exact JSON **shape of `GET /config/providers`** (`providers[].id`, `providers[].models[].id`) | §Probe/open question; D-09/D-11 | **Medium-high** — the endpoint itself is verified live on the user's server, but its response schema was **not** read this session. If the keys differ, discovery returns empty and the model list is wrong. Must be verified against the live server before the discovery parser is written. The environment facts given to this research are authoritative that the endpoint exists and is ~29 KB; the field names are not |
| A3 | The probe's numeric thresholds (10/25-point fill-rate drops; 25%/50% count deltas; 3-consecutive-run freshness rule) are appropriate for a personal-scale, single-keyword, twice-daily corpus | §Scraper-Survival Probe Design | Medium — the numbers are corroborated across independent engineering sources but were derived for higher-volume pipelines. They are deliberately loose; a tuning task with real data may tighten them. They are settings, not constants, precisely for this reason |
| A4 | `pytest-asyncio` 1.4.0 supports `asyncio_mode = "auto"` and works with `TestClient`/`httpx.AsyncClient` ASGI transport | §Validation Architecture | Low-medium — standard for the 1.x line, but the 1.0 release removed some legacy config; verify the config key at framework-install time |
| A5 | A 5-minute TTL is the right cache window for `probe()` on `/health` | §Probe Design | Low — it exists to stop `/health` from hammering a job board on every page load. Any TTL ≥1 min is defensible; the *existence* of a TTL is the load-bearing part |
| A6 | `--workers 1` plus SQLite WAL is sufficient for the Phase-1 concurrency (one background run + request-time reads) | §Pitfall 4, §Environment | Medium — this is the documented design, but Phase 1 is where it is first measured. The `busy_timeout=5000` pragma is the mitigation; if writes collide, the evidence will be a `database is locked` in `runs.errors_json` |
| A7 | Vendoring `htmx.min.js` and `alpine.min.js` from the npm packages into `static/vendor/` at image build is acceptable and does not require a bundler | §Standard Stack, §Pitfall 12 | Low — both ship pre-built browser bundles; the only question is whether the plan documents the extraction step rather than assuming a build tool |
| A8 | The JobSpy `desired_order` column set is stable enough to be the schema-drift contract for S6 | §Probe Design S6 | Low — it is pinned at our commit, so drift is only a risk on an intentional JobSpy upgrade, which the pin already discourages |
| A9 | `app/domain/**` purity can be enforced by static AST/import introspection in a test (rather than a plugin) | §Pattern / Validation | Low — a straightforward `ast` walk over the package is sufficient; no external tool needed |
| A10 | Docker Compose on the operator's machine provides `docker compose` v2 and `host-gateway` support | §Environment Availability | Medium — **docker is absent from the research sandbox entirely**, so this could not be probed. `host-gateway` requires Docker Engine ≥20.10; the operator is stated to run Docker already, but the version is unconfirmed |

**If this table were empty** it would mean every claim in this research had been verified — it is not empty, and A2 (the `/config/providers` response shape) is the one item that should be resolved *before* the discovery-parser task is written, not during it.

## Open Questions

1. **How many probe runs does the Phase-1 verdict require, and what if fewer are possible?**
   - What we know: the verdict's count-delta and fill-rate signals need a baseline **and** at least one prior run; honesty requires an observation window rather than a single sample.
   - What's unclear: whether the operator will actually run the probe on ≥3 distinct days inside the phase's calendar.
   - **Recommendation:** the plan must contain the runbook as a **task with a dated verdict document as its deliverable**, requiring **≥3 runs on ≥3 distinct days** where possible. If the window cannot be met, the verdict is written **PROVISIONAL**, states the run count, and the Adzuna decision remains deferred to Phase 8 (which the roadmap already provides for). Do **not** let a single run masquerade as a measurement.

2. **Does the FTS5 index get populated correctly when the table and triggers are created *after* rows already exist?**
   - What we know: sqlite.org states explicitly that "creating the triggers does not copy existing rows from the content table into the FTS index", and that `rebuild` is the remedy.
   - What's unclear: whether Phase 1's migration ordering can ever hit this (0001 runs before any rows exist, so presumably not) — but a later migration or a test fixture that seeds data before creating the index could.
   - **Recommendation:** always create the FTS table and triggers in the same migration as `listings` (0001, before any data), and note the `INSERT INTO listing_fts(listing_fts) VALUES('rebuild')` remedy in the migration comment for future migrations. Add a test that inserts a listing *through the ORM* and asserts it is findable via `MATCH`.

3. **Is the in-process `RunState` registry needed at all, given `runs` is in the database?**
   - What we know: `runs` is the durable, observable state; the UI polls it.
   - What's unclear: whether a shared in-memory object adds anything. It carries the risk of a **module-level mutable cache** — the exact pattern M6 flags as a future cross-user leak, and it would be the first thing a multi-user migration has to unpick.
   - **Recommendation:** **default to the database as the single source of truth for run state** and treat any in-memory registry as a *lazily-created, explicitly keyed* structure (or omit it). If a registry is used, key it by `run_id` and never let it hold listing or CV content.

4. **Does `probe()` belong on the `JobSource` ABC or in `app/probe/`?**
   - What we know: ARCHITECTURE §5.1 puts `async def probe(self)` on the ABC, which makes per-board knowledge (the known-stable URL, the expected marker) live in the adapter — where the other board specifics already are.
   - What's unclear: whether the *signal computation* (S1–S6) should also live there. It should not: it is board-agnostic arithmetic over persisted rows.
   - **Recommendation:** `probe()` on the adapter (board knowledge), the S1–S6 computation in `app/probe/survival.py` (board-agnostic), and `source_request_log` written by the transport. This keeps the ABC small and the maths testable without a board.

5. **What does the UI show when one board is `blocked` and the other is `ok`?**
   - What we know: SRC-05 forbids aborting the run; D-13 requires the health strip; the degradation semantics are explicitly the planner's discretion.
   - **Recommendation:** the run badge reads **`partial`** (not "failed"), names the degraded source, and states what the healthy source delivered; the health strip shows the degraded source's `probe()` status and last successful run. Treat "partial that looks identical to ok" as a defect, not a cosmetic choice.

6. **Should `linkedin_fetch_description` be exercised at all in Phase 1?**
   - What we know: it is the O(n) pass that also yields `job_url_direct` for LinkedIn (useful for Tier-2a dedup in Phase 2), and it "significantly increases the risk of rate limiting".
   - **Recommendation:** default it **off** in Phase 1 (`probe_max_detail_fetches = 0`), implement `fetch_details()` as a working but unbudgeted-by-default path, and let the Phase-2 dedup measurement decide whether to enable it. Enabling it during the survival measurement would confound the very measurement it is meant to inform.

7. **Where do the vendored JS/CSS artefacts live in git?**
   - What we know: UI-07 requires local assets; D-14 builds Tailwind at image build.
   - **Recommendation:** commit the built `app.css` (so the repo is runnable without Node) and the two vendored JS files; keep the npm install + CLI build in the Dockerfile so the build is reproducible. Document that editing templates requires re-running the CLI.

## Environment Availability

| Dependency | Required By | Available (research sandbox) | Version | Fallback |
|------------|-------------|------------------------------|---------|----------|
| **Docker / Compose** | PLAT-01 (`docker compose up`) | **✗ NOT FOUND** | — | **None in the sandbox.** The plan's compose task can be *written* here but not *verified* here. The operator's machine is the verification target (PROJECT.md states the user runs Docker). **Flag for the planner: the compose smoke test is an operator-run, not an agent-run, verification step.** |
| Python 3.13 | Runtime pin (D-17) | ✗ (3.14.7 present) | 3.14.7 | Pin `python:3.13-slim` in the image; do not develop against the host interpreter |
| Node / npm | Tailwind CLI at image build | ✓ | v24.18.1 / 11.12.1 | — |
| pip | Dependency install + version verification | ✓ | 26.1.2 | — |
| git | JobSpy git pin | ✓ | 2.54.0 | — |
| Network egress | JobSpy install, npm assets, opencode calls | ✓ | verified via `git ls-remote` + registry queries | — |
| `opencode` server | Phase 3; Phase 1 health/discovery wiring only | ✗ not reachable from the sandbox (stated) | server v1.18.29 (given) | `/health` must be **boot-tolerant** (D-08); Phase 1 makes no LLM call, so its absence cannot block this phase |
| `uv` | Optional (STACK.md mentions uv-managed) | ✗ | — | Use `pip` with an exact-pin `requirements.txt`; uv is a convenience, not a constraint |

**Missing with no fallback:**
- **Docker** — blocks *verification* of PLAT-01 in this environment, not implementation. The planner must put the `docker compose up` check in an explicit human/operator verification task rather than an agent-executed test.

**Missing with fallback:**
- Python 3.13 — pin in the image (correct behaviour anyway per D-17).
- `uv` — use pip + a committed lock.
- Live opencode — boot-tolerant by design (D-08); Phase 1 needs no LLM call.

## Validation Architecture

`workflow.nyquist_validation` is `true` in `.planning/config.json`, so this section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | **pytest 9.1.1** + **pytest-asyncio 1.4.0** (verified current this session) |
| Config file | **none — Wave 0 creates `pyproject.toml` `[tool.pytest.ini_options]`** with `asyncio_mode = "auto"`, `testpaths = ["tests"]`, and a marker for the slow/live lane |
| Quick run command | `pytest -q tests/domain tests/db tests/sources tests/test_import_discipline.py` (pure; no network, no Docker, target < 15 s) |
| Full suite command | `pytest -q` (adds pipeline + api integration tests against a temp SQLite file) |
| Slow / operator lane | `pytest -q -m live` — **never in CI**; the canary/probe only (P13) |
| Schema gate | `pytest -q tests/db/test_migration_contract.py` — runs `alembic upgrade head` on a temp DB and asserts all 9 checklist items |
| Container smoke (operator-run) | `docker compose up -d --wait && curl -fsS localhost:8000/health` — **Docker is unavailable in the agent sandbox**, so this is a human verification step |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| SRC-01 | LinkedIn search returns normalised listings | unit (fixture-driven, no network) | `pytest tests/sources/test_linkedin.py -x` | ❌ Wave 0 |
| SRC-02 | Indeed search returns normalised listings | unit | `pytest tests/sources/test_indeed.py -x` | ❌ Wave 0 |
| SRC-03 | One normalised listing shape across sources | unit | `pytest tests/domain/test_normalize.py -x` | ❌ Wave 0 |
| SRC-04 | New source = one adapter + one registry entry, no pipeline change | unit + introspection | `pytest tests/sources/test_registry.py tests/test_import_discipline.py -x` | ❌ Wave 0 |
| SRC-05 | Failing source returns partial; the run completes | integration | `pytest tests/pipeline/test_partial_failure.py -x` | ❌ Wave 0 |
| SRC-06 | No credential path anywhere | static scan | `pytest tests/test_no_credentials.py -x` | ❌ Wave 0 |
| SRC-07 | Per-source health + probe detectable | unit + api | `pytest tests/probe/test_signals.py tests/api/test_health.py -x` | ❌ Wave 0 |
| SRC-08 | Untrusted text sanitised at the ingest boundary | unit | `pytest tests/domain/test_sanitize.py -x` | ❌ Wave 0 |
| SRC-09 | Capabilities declared *and* an unsupported filter is warned, not ignored | unit | `pytest tests/sources/test_capabilities.py -x` | ❌ Wave 0 |
| SRC-10 | PII stripped and never stored | unit + negative schema | `pytest tests/domain/test_sanitize_pii.py tests/db/test_no_pii_columns.py -x` | ❌ Wave 0 |
| QUEUE-01 | Persisted queue survives a restart | integration | `pytest tests/db/test_persistence.py -x` | ❌ Wave 0 |
| QUEUE-02 | Re-running never duplicates a row for the same listing/source | integration (the `id=None` seed is the key case) | `pytest tests/db/test_two_key_upsert.py -x` | ❌ Wave 0 |
| QUEUE-05 | `first_seen_at`/`last_seen_at`/`content_hash` recorded and NOT NULL | schema contract | `pytest tests/db/test_migration_contract.py::test_listings_timestamps_not_null -x` | ❌ Wave 0 |
| RUN-01 | Manual trigger from the UI | api integration (`TestClient`) | `pytest tests/api/test_run_trigger.py -x` | ❌ Wave 0 |
| RUN-02 | Runs run in the background; the UI is not frozen | api integration (response returns before the pipeline finishes; `/health` stays responsive) | `pytest tests/api/test_run_backgrounded.py -x` | ❌ Wave 0 |
| PLAT-01 | Whole app via one `docker compose up` | **smoke — operator-run** | `docker compose up -d --wait && curl -fsS localhost:8000/health` | ❌ Wave 0 (script + runbook) |
| PLAT-03 | Every route carries the auth seam | route-introspection | `pytest tests/test_auth_seam.py -x` | ❌ Wave 0 |
| PLAT-04 | Limits/thresholds/engine are config, not constants | unit (settings override + a grep-style assertion) | `pytest tests/test_config.py -x` | ❌ Wave 0 |
| UI-07 | Assets vendored; no CDN | static scan of templates + a `static/vendor/` presence check | `pytest tests/test_no_cdn.py -x` | ❌ Wave 0 |
| **D-20 (item 6)** | Both dedup indexes exist (partial + unconditional) | schema contract | `pytest tests/db/test_migration_contract.py::test_dedup_indexes -x` | ❌ Wave 0 |
| **D-20 (items 2,3,4,5,7,8)** | `listing_events` append-only; `scores` decomposition; `cv_artifacts.verification_json` + blocked; `applications.cv_artifact_id`; `sources.capabilities_json`/`tos_audited_at`; `listings.blocking_key` indexed | schema contract | `pytest tests/db/test_migration_contract.py -x` | ❌ Wave 0 |
| **D-11** | The raw `/config/providers` response is never logged or persisted | unit + log-scan + DB-scan | `pytest tests/llm/test_discovery_redaction.py -x` | ❌ Wave 0 |
| **P8/M8** | PRAGMAs applied on every connection (WAL, FK ON, busy_timeout) | unit against a live temp DB | `pytest tests/db/test_pragmas.py -x` | ❌ Wave 0 |
| **Probe** | Each WARN/FAIL boundary fires at the right value | unit (fixture-driven, no network) | `pytest tests/probe/test_thresholds.py -x` | ❌ Wave 0 |

**Manual / non-automatable in this environment:** PLAT-01 (no Docker in the sandbox) and the **live probe verdict** (a measurement against hostile third-party sites, which must never be a CI test — P13). Both are explicit operator tasks, not gaps to be quietly dropped.

### Sampling Rate

- **Per task commit:** `pytest -q tests/domain tests/db tests/sources tests/test_import_discipline.py` — the fast, offline lane. Must stay **< 30 s**; it is the loop the implementer actually runs.
- **Per wave merge:** `pytest -q` — full suite including api/pipeline integration against a temp SQLite file.
- **Phase gate:** the full suite is green **plus** the two non-test gates: (a) the 9-item migration checklist asserted by `tests/db/test_migration_contract.py` and (b) the **dated probe verdict document committed to the repo**. A phase that cannot produce (b) is not complete, regardless of test colour.
- **Never in CI:** any test that contacts LinkedIn or Indeed. The live check is `pytest -q -m live`, run deliberately by the operator (P13).

### Wave 0 Gaps

- [ ] `pyproject.toml` — exact pins for the whole Standard Stack; `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` and a `live` marker; `[tool.ruff]` config
- [ ] `tests/conftest.py` — an async-Engine fixture backed by a **temp file** (not `:memory:` — WAL and FTS5 behaviour differ), applying the PRAGMAs, created by running **`alembic upgrade head`** so tests exercise the real schema rather than `create_all`
- [ ] `tests/db/test_migration_contract.py` — the 9-item checklist as assertions (the single highest-value test in the phase)
- [ ] `tests/fixtures/listings/*.json` — captured or hand-built raw payloads per source. **Capture them once via a single manual run, strip the `emails` field, and commit** — never fetch in CI
- [ ] `tests/sources/test_linkedin.py` / `test_indeed.py` — fixture-driven adapters; must include the negative cases (`id=None`, empty description, `country_indeed` regression guard)
- [ ] `tests/test_import_discipline.py` — AST walk asserting `app.domain.*` imports none of `httpx | sqlalchemy | jobspy | jinja2 | subprocess` (D-24)
- [ ] `tests/test_no_credentials.py`, `tests/test_no_cdn.py`, `tests/test_auth_seam.py` — the three static/introspection guards
- [ ] `tests/probe/test_thresholds.py` — one test per WARN/FAIL boundary in §Scraper-Survival Probe Design
- [ ] `static/vendor/` — the vendored `htmx.min.js` / `alpine.min.js` and the built `app.css`
- [ ] `scripts/compose-smoke.sh` + a runbook note — the operator-run PLAT-01 check that cannot run in CI here
- [ ] Framework install (`pytest`, `pytest-asyncio`, `ruff`) — required before any of the above can be written

## Security Domain

`workflow.security_enforcement` is `true` with `security_asvs_level: 1` and `security_block_on: "high"`, so this section is required. Phase 1 has **no LLM call and no authentication**, which *narrows* the applicable surface but does not remove it — the phase's own hazards are credential leakage from discovery and PII persistence from ingest.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture / threat modelling | **yes** | The trust boundary is explicit: job-board content is untrusted input, opencode is a privileged external service, the browser is read-only. The import-discipline test is the enforcement of the first boundary |
| V2 Authentication | **no** (deferred) | v1 has no authentication by explicit decision. The *seam* exists (`current_user()` on every route) so V2 can be added without touching route signatures. Do not claim an auth control that is not present |
| V3 Session Management | **no** (deferred) | No sessions, no cookies in Phase 1 |
| V4 Access Control | **partial** | Single local user; the control is (a) the `current_user` seam on every route and (b) **not exposing the app beyond the host** in v1. There is no per-object authorization to get wrong yet — and the phase must not imply otherwise |
| V5 Input Validation | **yes** | Untrusted listing text is sanitised at exactly one boundary (`domain/sanitize.py`); adapter output is Pydantic-validated; Jinja2 autoescape **on** with no `|safe` on listing fields; FTS5 `MATCH` terms are **bound parameters**, never string-interpolated into SQL |
| V6 Cryptography | **yes — never hand-roll** | No cryptography is implemented in Phase 1. Requirements: `content_hash` uses `hashlib` (SHA-256), never a bespoke hash; the opencode credential is consumed as an env-supplied value and passed to `httpx` basic auth, never stored, hashed, or derived |
| V7 Error Handling & Logging | **yes — highest-risk row for this phase** | Structured logs carry **IDs, counts and status codes — never credentials, never raw API responses, never CV or listing prose**. The `/config/providers` response is the concrete hazard (D-11) |
| V8 Data Protection | **yes** | Recruiter PII (emails/phones) is stripped at the ingest boundary and never persisted (SRC-10); `.env` is gitignored and the password is uncommitted (D-07); the `host.docker.internal` default keeps the LLM credential local |
| V12 Files & Resources | **no** in Phase 1 | No uploads, downloads or user-supplied paths. `StaticFiles` serves a fixed vendored directory only (the artifact path-traversal surface arrives with Phase 6) |
| V14 Configuration | **yes** | No hard-coded secrets (D-07); the opencode port is **not published** (M10); the app binds to the host only in v1; every threshold is config, which is also what makes the ban-risk envelope auditable (PLAT-04) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| **Discovery-response credential leak** — `GET /config/providers` contains the provider API key in plaintext; a stray `logger.debug(body)` or a cached raw response puts a live secret in logs or the DB | Information Disclosure | Parse into a model with only `provider.id`/`model.id`; never bind the raw body to a long-lived name; a test that runs discovery against a fixture with a sentinel key and scans `caplog` **and** every table for it (D-11). **This is the phase's most likely real-world security defect** |
| **PII persistence** — JobSpy literally provides `emails: list[str] \| None`; storing it is the cheapest GDPR mistake available | Information Disclosure | `RawListing` has no `emails` field at all (unrepresentable, not filtered); the sanitise stage strips emails/phones from `description`; a **negative schema test** asserts no column named `email`/`phone` exists on any table |
| **XSS via listing text** — a job description contains `<script>` or an `onerror=` attribute rendered into the queue | Tampering / Elevation | Jinja2 autoescape **on**; no `\|safe`, no `Markup`, no `innerHTML` in templates; sanitise reduces HTML to text at the boundary; a template test asserts no `\|safe` on listing fields |
| **SQL injection via search terms (Phase 2 surface, schema now)** — an FTS `MATCH` string built by concatenation | Tampering | Bound parameters everywhere; the `search` port takes a string and binds it. Establish the pattern in Phase 1's repository layer so Phase 2 cannot regress it. Never `LIKE '%' || :term || '%'` |
| **Path traversal / static file escape** | Information Disclosure | `StaticFiles` is mounted on one fixed directory; no user-controlled path segments in Phase 1 |
| **Container/LAN exposure** — the app has no auth; publishing it or the opencode port exposes CVs and a shell-capable agent surface | Information Disclosure / Elevation | App bound to the host only; the opencode port is never published and there is no `opencode` compose service (D-05/M10); no `--mdns`; a password is set even locally |
| **Server-side request forgery via `OPENCODE_BASE_URL`** | Tampering | It is operator-supplied config from env, not user input, and is not reachable from a request path. Document that it must stay out of any user-facing input |
| **Supply chain — a git-installed dependency** | Tampering | The JobSpy commit is pinned to a **full SHA** (`fda080a…`), not a branch or tag; MIT licence verified; the lock records resolved hashes; one consolidated human verification of the resolved set (§Package Legitimacy Audit) |
| **Scraping with a real session / credentials in source** | Tampering / Reputational | The credential path is architecturally absent; a static test asserts no `LINKEDIN_*`/`INDEED_*` credential read and no session-cookie store (P2/SRC-06) |
| **Unbounded request velocity against a hostile board** | (Availability / third-party harm) | `FetchBudget` ceilings in config; the documented 1-search/board, ≤50–100 results, once-per-day envelope; stop signals recorded, never escalated (P2/D-02) |
| **Prompt injection via listing text** | Elevation | **No LLM call happens in Phase 1**, so the exploit path does not exist yet. Phase 1's job is the *boundary*: sanitise records instruction-like text as a finding, and the schema keeps listing content out of any future system-prompt field. The full pattern catalogue is Phase 2; the enforcement (`tools=[]`, untrusted text in `parts`) is Phase 3 |

## Sources

### Primary (HIGH confidence — read this session, pinned revision)
- **JobSpy `jobspy/model.py`** @ `fda080a373e8226f3fd60635323f5da9af9892b1` — `JobPost` (incl. `id: str | None = None`, `emails: list[str] | None = None`), `Country.IRELAND = ("ireland", "ie", "ie")`, `Compensation`, `SalarySource`, `Site`, `ScraperInput` (`request_timeout=60`), `Location.display_location()`
- **JobSpy `jobspy/__init__.py`** @ same commit — the full `scrape_jobs()` signature and defaults; `desired_order`; the internal `ThreadPoolExecutor`; the USA-only `extract_salary` branch
- **JobSpy `jobspy/util.py`** @ same commit — `desired_order`, `extract_salary` (the `\$`-anchored regex), `extract_emails_from_text`, `create_session`/`TLSRotating` (the built-in TLS impersonation), `RequestsRotating` retry config
- **JobSpy `pyproject.toml`** @ same commit — the runtime dependency set and `requires-python`
- **JobSpy README** @ same commit — "LinkedIn is the most restrictive and usually rate limits around the 10th page with one ip. Proxies are a must basically."; "All the job board endpoints are capped at around 1000 jobs on a given search."; 429 = blocked
- **GitHub API** — `speedyapply/JobSpy`: HEAD `fda080a…` committed `2026-02-18T19:39:52Z`, message `fix(linkedin): add fallback for date parsing on new job listings (#343)`, stars 4,284, `license: MIT`, `archived: false`, `default_branch: main`
- **PyPI + npm registries** (`pip index versions`, `npm view`) — every version in the Standard Stack table, plus the negative finding that `python-jobspy` is at 1.1.82
- **`gsd-tools query package-legitimacy check`** — all verdicts in §Package Legitimacy Audit, with the PyPI download-signal caveat documented inline

### Primary — official documentation (MEDIUM — `[CITED]`)
- **SQLAlchemy 2.0 docs** (via Context7, `/websites/sqlalchemy_en_20`) — the `engine.sync_engine` connect-event target for async engines; the `PRAGMA foreign_keys=ON` autocommit requirement; `sqlite+aiosqlite:///` URL form
- **Alembic docs** (via Context7, `/websites/alembic_sqlalchemy`) — `batch_alter_table` semantics; `create_index` dialect-keyword form (`<dialectname>_<argname>` ⇒ `sqlite_where`); the unnamed-CHECK/UNIQUE drop caveat on SQLite table recreation
- **Tailwind CSS docs** (via Context7, `/websites/tailwindcss`) — the `@tailwindcss/cli` v4 CLI, `@import "tailwindcss";`, `@source`
- **SQLite FTS5 reference** (`sqlite.org/fts5.html`) — external-content `content=`/`content_rowid=`, the verbatim trigger DDL, `ORDER BY rank`, the delete-ordering rule, the `rebuild` remedy
- **htmx docs** (`htmx.org/docs`) — `hx-trigger="every Ns"` and the **HTTP 286** stop-polling protocol
- **Docker Compose networking docs** (`docs.docker.com/compose/how-tos/networking`) — `extra_hosts` / `host-gateway`, "On Linux, host-gateway resolves to the host's IP on the default bridge network"

### Secondary (MEDIUM — corroborating engineering sources)
- Scraper-health monitoring: `link.sc/blog/how-to-test-and-monitor-scrapers` (success rate per domain, field fill rate, schema drift); `shifter.io/blog/how-to-monitor-a-web-scraping-pipeline` (fill rate, freshness, cost per record, baseline-per-target); `promptcloud.com/blog/web-scraping-monitoring-challenges` (baseline and trend gaps); `dev.to` schema-drift write-up (**the ≥10-point fill-rate drop heuristic**); `spyderproxy.com/blog/data-quality-metrics` (per-field coverage vs rolling 7-day average); `context.dev/blog/scraper-monitoring-in-production` (schema validation + scheduled canaries)
- Count-regression lines: `apify.com/convenient_yarn/scraper-freshness-watchdog` (**25% row-count regression**); `github.com/kingerson/scraper-monitor` (expected count ± **5%** tolerance)
- Container migration practice: `stackoverflow.com/questions/79704400` (the `entrypoint.sh` → `alembic upgrade head` → `exec "$@"` idiom); the migration-race issue on multi-replica deployments (moot at `--workers 1`)

### Tertiary (LOW — directional only)
- Vendor-authored scraper/proxy content (SpyderProxy, PromptCloud, ScrapingBee-adjacent) — treated as directional; used only where independently corroborated by the primary sources above

### Inherited from the project's own research (authoritative for this repo, not re-derived)
- `.planning/research/STACK.md`, `ARCHITECTURE.md`, `PITFALLS.md`, `FEATURES.md`, `SUMMARY.md`, `RESUME-MATCHER-SPIKE.md` — all Phase-1-relevant findings are cited inline by their local IDs (`P#`/`M#`/`m#`, `§n`, `TS-*`/`DF-*`/`AF-*`, `D1`–`D10`)

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | **HIGH** | Every version confirmed against the correct registry this session; the JobSpy pin confirmed to a full SHA including its commit message; the JobSpy→our-pydantic compatibility checked explicitly rather than assumed |
| External contracts (JobSpy, FTS5, htmx, Docker, SQLAlchemy, Alembic, Tailwind) | **HIGH** | Read at a pinned revision or from official docs; the load-bearing values are quoted verbatim in §Verified External Contracts |
| Architecture / migration mechanics | **HIGH** | Derived from the project's own settled architecture plus the verified library mechanics; the two non-obvious traps (batch-mode constraint drop, `to_thread` non-cancellability) are documented upstream |
| Probe design — *instrument* | **MEDIUM-HIGH** | The signal families and their formulas are corroborated across independent sources; the WARN/FAIL thresholds are deliberately conservative settings, not constants |
| Probe design — *observed survival rate* | **LOW** | This is the measurement Phase 1 exists to take. No first-hand evidence exists and none was gathered (by design — no live scraping during research). Treat any survival claim as unknown until the verdict document exists |
| Pitfalls | **HIGH** on the data-model, dedup, blocking-call and PII pitfalls (verified mechanics); **MEDIUM** on the probe thresholds; **MEDIUM** on the compose/`host-gateway` path (Docker unavailable to the sandbox) |

**Research date:** 2026-09-15
**Valid until:** ~2026-10-15 for the library pins and migration mechanics (30 days — these are stable). **Re-verify the opencode contract (A2) immediately before writing the discovery parser**, and re-verify package versions at lock time.

**Deliberate omissions from this document, and why:**
- **Runtime State Inventory** — this is a greenfield phase (the repository contains no application code). There is no stored data, live-service config, OS-registered state, secret key or build artefact carrying a string that needs migrating. The only migration is schema 0001 against an empty database. (Included here explicitly rather than left blank, so a reader can distinguish "not applicable" from "not checked".)
- **No live scraping was performed**, per the phase instructions. Every survival claim in this document is a *design* for a measurement, not a measurement.

