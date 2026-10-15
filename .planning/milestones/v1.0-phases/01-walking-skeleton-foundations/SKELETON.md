# Walking Skeleton — Job Search Copilot

**Phase:** 1
**Generated:** 2026-09-15
**Status:** contract for every later slice — not a scratchpad

## Capability Proven End-to-End

> An operator runs `docker compose up`, opens the queue UI, presses **Run search now**, and sees a
> real listing fetched from LinkedIn **and** Indeed persisted in SQLite, normalised into one shape,
> still present after a restart — with a per-source health strip that says whether each board is
> alive.

This is the smallest user-visible capability that exercises the full stack **and** the phase's
non-backfillable one-way commitment (migration 0001). It is deliberately bigger than a "hello
world" because the phase's second deliverable — a schema that describes the past — cannot be added
later.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | **FastAPI 0.141.1** on **uvicorn 0.53.0, `--workers 1`** | Async-first for fan-out I/O; Pydantic v2 native (Phase 3 structured output builds on it). One worker because SQLite has one writer and any future in-process scheduler must not multiply (AP13). |
| Runtime | **Python 3.13** (`python:3.13-slim`) | Locked (D-17). Not 3.14 — Playwright/`curl_cffi`/`lxml` wheel coverage is the risk. |
| Data layer | **SQLite (WAL) + SQLAlchemy 2.0.53 + Alembic 1.20.0 + aiosqlite 0.22.1** | Single-file, zero-ops, read-heavy. Async URL for the app; **sync** URL for Alembic (`app/db/session.py`). `alembic upgrade head` in the entrypoint. |
| Schema | **Migration 0001 is one-way** and carries all 9 ROADMAP acceptance items | These columns describe the past and cannot be backfilled (D-20 / P8). The migration doubles as the schema test (`tests/db/test_migration_contract.py`). |
| Acquisition | **JobSpy from git at pinned SHA `fda080a373e8226f3fd60635323f5da9af9892b1`, behind one adapter per board over one shared transport** | Never PyPI (stale 1.1.82); never a `site_name` list (AP16). `sources/_jobspy_transport.py` is the only module that imports `jobspy`. |
| Auth | **No auth; a `current_user()` FastAPI dependency on every route; no `user_id` columns** | The route seam is free; the data model is not (AR14). A test proves the seam is universal so a later route cannot omit it. |
| LLM backend | **External, user-managed `opencode serve` via config only — no compose service, no LLM call in Phase 1** | D-05/D-08: `docker compose up` must never depend on an LLM backend. `/health` reports it `unreachable` rather than crashing. |
| UI | **Jinja2 3.1.6 + HTMX 2.0.10 + Alpine 3.17.3, styled by Tailwind 4.3.3 CLI at image build — all vendored, no CDN** | Server-rendered HTML keeps listing text out of client templates (XSS surface) and the image free of a runtime Node toolchain (UI-07). |
| Deployment | **`docker compose up` of the `app` service only**; `extra_hosts: host.docker.internal:host-gateway`; opencode port never published | PLAT-01 + D-06 + M10. Local-only in v1; portable to a host later because the base URL is config. |
| Directory layout | `app/{config,api,web,domain,sources,ingest,pipeline,probe,llm,db}`, `tests/{domain,sources,db,pipeline,probe,api,llm,fixtures}`, `alembic/versions/`, `static/vendor/`, `docs/probes/`, `scripts/` | ARCHITECTURE §3. `domain/` is pure and its purity is enforced by an AST test. |
| Scheduling | **None** — manual trigger only | Scheduling is Phase 8 by roadmap intent; a cron over an untrustworthy pipeline hides failures. |
| Dedup | **Tier-1 only, two-key**: partial unique `(source, source_listing_id) WHERE source_listing_id IS NOT NULL` **plus** unconditional unique `(source, canonical_source_url)` | JobSpy's `id` may be `None`; a single `ON CONFLICT` would insert duplicates silently (AP7/m9). |

### Adapter identity — the second-source seam

The phase introduces the project's first pluralisation (one board → two). The resolution is locked
(D-18) and recorded here so later slices do not re-litigate it: **the registry is keyed by `name`,
resolved from the `sources` table at run start; there is one adapter per board; LinkedIn and Indeed
share `sources/_jobspy_transport.py` but are separate `JobSource` classes with separate
capabilities, budgets and health.** Adding a third board (Adzuna, SRC-11) is: implement `JobSource`,
register it, insert a `sources` row. No pipeline edit, no schema change.

## Stack Touched in Phase 1

- [x] Project scaffold — `pyproject.toml` exact pins, `[tool.pytest.ini_options]`, `[tool.ruff]`, Dockerfile, compose
- [x] Routing — real routes: `GET /` (queue), `POST /runs` (trigger), `GET /runs/{id}/status` (poll), `GET /health`
- [x] Database — real **write** (two-key Tier-1 upsert of a listing + its source row) **and** real **read** (queue list, count, health strip), via `alembic upgrade head`
- [x] UI — real interactive element: HTMX "Run search now" button + status poll that stops on HTTP 286
- [x] Deployment — `docker compose up` (operator-run; Docker is absent from the agent sandbox, so this is an explicit human-check deliverable, not a CI test)

## Out of Scope (Deferred to Later Slices)

- Tier-2 fuzzy dedup / merge + revert (QUEUE-03/04) — **Phase 2**
- Criteria CRUD, filter compiler, exclusions UI (CRIT-01/02/03, FILT-01…04) — **Phase 2**
- FTS search queries, new/stale badges (QUEUE-06/07/08/09) — **Phase 2** (the FTS5 table + triggers ship in 0001; queries do not)
- `_INJECTION_PATTERNS`-style injection rule catalogue (Resume-Matcher, Apache-2.0 §4 attribution) — **Phase 2**
- Any LLM call, ranking, per-call model recording — **Phases 3 / 5**
- CV fact store, LaTeX render/compile/verify — **Phases 4 / 6**
- Tailoring, apply package, tracker — **Phases 6 / 7**
- Scheduling, source-health auto-escalation, responsive/phone layout (UI-06) — **Phase 8**
- Adzuna adapter (SRC-11) — **v2 / Phase 8**, gated on the Phase 1 probe verdict (D-04)
- Authentik OIDC, multi-user, MCP server — future milestone

### Recorded scoping conflict (D-16) — desktop-first

Phase 1 is built **desktop-first**. `PROJECT.md` Constraints and `REQUIREMENTS.md` Out-of-Scope both
state the opposite ("primary access is a phone" / desktop-first is out of scope). The user was shown
the conflict and confirmed desktop-first for Phase 1, with the phone-first layout pass at **Phase 8
(UI-06)**. This is a **scoping decision with a Phase 8 payoff**, not consistency with `PROJECT.md`.
Undo is `costly` (retrofitting responsive layout across all Phase 1–7 views is a cross-cutting
rework), so it is flagged, not gated.

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton **without altering its
architectural decisions**:

- **Phase 2:** the queue becomes deduped, deterministically filtered, searchable — every rejection explained
- **Phase 3:** any schema-constrained LLM call works end to end through the external opencode server, contract pinned by a `/doc` test
- **Phase 4:** `cv.yaml` reproduces the base CV fact-for-fact and Tectonic compiles the real `.tex` in-container (runs in parallel with 2–3)
- **Phase 5:** ranking — one ranked, explained queue with per-factor sub-scores and named gaps
- **Phase 6:** a tailored, verified CV PDF, previewable and downloadable
- **Phase 7:** assisted-apply package + tracker linked to the exact verified artefact
- **Phase 8:** scheduled runs, source health in the UI, responsive interface

---

## Assumptions & Flagged Probe Rows

The edge probe (`specless_probe_fallback`) could not classify several rows. Per the no-silent-drop
contract, every row appears either as a `must_haves.truths` acceptance criterion (with a `verification`
tier) or in this flagged list. **Unclassified rows are flagged, never auto-resolved.**

| Row | Requirement | Disposition |
|---|---|---|
| unclassified | SRC-01 | Flagged — requirement text is the criterion ("a LinkedIn search returns normalised listings"); plan 01-03 |
| unclassified | SRC-02 | Flagged — plan 01-04 |
| unclassified | SRC-04 | Flagged — plan 01-04 (registry-extensibility criterion) |
| unclassified | SRC-05 | Flagged — plan 01-03 (partial-result criterion) |
| unclassified | SRC-06 | Flagged — plan 01-05 (static no-credential scan) |
| unclassified | QUEUE-01 | Flagged — plan 01-01 (volume + persistence) |
| unclassified | QUEUE-02 | Flagged — plan 01-01 (idempotent two-key upsert) |
| unclassified | RUN-01 | Flagged — plan 01-03 |
| unclassified | RUN-02 | Flagged — plan 01-03 |
| unclassified | PLAT-01 | Flagged — plan 01-07 (operator-run compose smoke) |
| unclassified | PLAT-04 | Flagged — plan 01-05 (config-not-constants assertion) |

Typed probe rows (adjacency / empty / ordering / idempotency / concurrency / boundary / precision /
encoding) are authored as `must_haves.truths` in the owning plan, each as a plain string when
mechanically checkable or as a `{statement, verification: backstop}` marker when not.

Prohibitions recalled by the prohibition-probe (Stage 1 → Stage 2) live in the owning plans'
`must_haves.prohibitions` blocks, descriptor-less, and are surfaced as flagged-unverified.

Canon-referral breadcrumbs (not minted as prohibitions): prompt-injection rule catalogue →
`/gsd-secure-phase` + Phase 2; generic GDPR retention → `/gsd-secure-phase`; unattended-submission
bright line → Phase 7; CV fabrication → Phases 4/6.
