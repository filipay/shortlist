# Phase 3: LLM Port + Structured Output - Context

**Gathered:** 2026-09-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the existing `app/llm/` port capable of a real, schema-constrained completion through the
user-managed `opencode serve` backend, prove that path end to end from inside the app, and pin the
structured-output wire contract with a test that fails loudly when opencode's API changes. Includes
the `llm_calls` audit write path and the run-level LLM counters that Phase 1's schema already
provisioned but nothing writes.

**In scope (this phase):**

- `complete_structured` on the `LLMBackend` port + `OpenCodeServerBackend` implementation
  (session create → message send → structured output → validated typed result).
- An on-demand **LLM backend selftest** in the app UI that performs one real schema-constrained call
  and records it in `llm_calls`.
- The `/doc` contract test (default-lane snapshot assertion + operator-run live diff) that resolves
  and pins `format` vs `outputFormat`.
- The `llm_calls` repository / writer, and writing `runs.llm_calls`, `runs.llm_tokens`,
  `runs.ranked_count` where applicable.
- Reading `OPENCODE_MODEL` (currently dead config) and recording model + provider + agent per call
  (D-12 / PITFALLS M9).

**Explicitly out of scope (other phases):**

- Ranking logic and its output schema — **Phase 5 (Ranking — CORE VALUE)**. Phase 3 must not
  constrain the ranking schema or implement scoring.
- Tailoring, multiple CV variations, prompt templates per CV style, user-supplied custom prompts —
  **Phase 6**.
- Per-run LLM spend caps (RANK-08) — **Phase 5**; enforced before the call is made, and there is no
  budget/cost-cap field in Phase 3.
- A CLI (`subprocess`) fallback backend — not required by PLAT-02/PLAT-05. The port must *permit* it
  (nothing outside `llm/` may import `httpx` or `subprocess`), but Phase 3 ships the server backend
  only.
- Standing up a CI runner — see the `/doc` contract test decision below.

</domain>

<decisions>
## Implementation Decisions

### End-to-end proof surface

- **D-48:** The live schema-constrained call is performed by an **on-demand "Test LLM backend" action
  in the app UI** (settings/health surface), not by `run_pipeline()`. One call, on demand, from a
  route that goes through the `current_user` seam. — **Reversibility:** reversible — a route plus a
  bounded backend call; removing it touches no schema and no other caller.
- **D-49:** **No automatic per-run LLM stage in Phase 3.** Ranking — the first real LLM consumer — is
  Phase 5. A `narrate`-style run-explanation call was rejected because it would contradict **D-45**,
  which deliberately made the run's explanation deterministic and LLM-free. `run_pipeline()` is not
  modified to make LLM calls in this phase.
- **D-50:** The selftest is recorded **only in `llm_calls`**, with `run_id` NULL and
  `purpose='probe'`. **No synthetic `runs` row.** Selftests must never appear in `/runs` history and
  must never influence the Phase 2 run-reason logic or the last-run strip. — **Note:** this needs
  **zero migration** — `llm_calls.run_id` is already nullable (`app/db/models.py:446`) and
  `purpose='probe'` is already in `ck_llm_calls_purpose` (`app/db/models.py:461-464`).
- **D-51:** The selftest uses a small **purpose-built `ProbeResult` schema**, used only by the
  selftest. The prompt sends a **canned adversarial / instruction-like snippet in the user part**, so
  the live run proves both the constrained-output path and that the system prompt stays constant and
  clean. Phase 5's ranking schema stays completely unconstrained. (The canned snippet is fixed test
  content, **not** a real listing — no dependency on queue contents.)
- **D-52:** On failure the operator sees the **full cause and attempt count**, not just red/green:
  distinguish `unreachable` / `timeout` / `invalid after N attempts` / other error, and show attempt
  count, latency and the validation message. This detail is persisted on the `llm_calls` row and
  rendered where the test was run; it must not be reduced to a bare badge. (Related: WINDOWS.md #4
  already warns that a health badge is not a reliable proxy for the real call.) — **Reversibility:**
  reversible — a presentation choice over data that is already persisted.

### /doc contract test mechanics

- **D-53:** The `/doc` contract test is a **committed snapshot fixture + an operator-run live diff**.
  A fixture holding the real spec slice is committed (e.g. `tests/llm/fixtures/opencode-doc.json`); a
  **default-lane** test asserts our client's expected structured-output names exist in the snapshot
  **and** that our request builder emits exactly those names — so a code-side rename fails with no
  server running. An operator-run `@pytest.mark.live` test refetches `/doc` and diffs against the
  snapshot, failing loudly on server drift. The runbook gains a "run the live lane, refresh the
  snapshot deliberately" step. — **Rationale:** the repo has **no CI runner at all** (`.github/` is
  absent; no `.gitlab-ci.yml`, no `.circleci`) and pytest runs with `addopts="-m 'not live'"`, so a
  live-only test would never fire on an upgrade. Standing up CI was rejected as out of scope for this
  phase. — **Reversibility:** costly — the fixture is a committed contract artefact that later phases
  and the runbook reference; replacing the approach means rewriting the test and the runbook step.
- **D-54:** **Pin one exact field name** (resolving the roadmap's `format` vs `outputFormat`
  ambiguity, expected to be `format`) as a **single constant**, asserted against both the snapshot and
  our request builder. Any other name fails the test. An "adaptive — accept either name" client was
  **explicitly rejected**: it would silently absorb a rename and defeat success criterion 3. The
  constant is the one place to change when opencode genuinely renames the field. — **Reversibility:**
  reversible — a single named constant.
- **D-55:** The committed snapshot covers **only the structured-output-relevant slice** of `/doc`:
  the message-send request-body schema (property names, the structured-output key) and the endpoint
  path. It is **not** a full `/doc` dump — unrelated OpenAPI churn must not fail the test.
- **D-56:** The contract test pins the **whole structured-output contract surface**, each with its own
  constant: the request field name (`format`), its inner keys (`type`, `json_schema`, `retryCount`),
  the **response location** (`info.structured_output`), and the message-send endpoint path. Both ends
  can drift; criterion 3 says "the structured-output contract", not just one key.
- **D-57:** The live `/doc` test does **spec fetch + diff only** — it does **not** also perform a live
  structured call. The real call lives solely in the in-app selftest (D-48). Chain of proof:
  builder == snapshot (default lane) → snapshot == live spec (live lane) → real call works (UI
  selftest).

### Carried forward — decided outside this discussion (do not re-litigate)

The following were **presented as gray areas but not selected**. They are governed by already-locked
prior decisions, and the researcher/planner must follow those rather than invent new ones:

- **Port shape, prompt assembly, trust boundary** — follow `ARCHITECTURE.md` §6.1–6.3:
  `StructuredCallResult` (`ok`, `data`, `error`, `raw`, `attempts`, `provider_tokens`) and
  `complete_structured(*, schema, system, parts, model=None, agent=None, tools=(), retries=2)`.
  Untrusted content goes in `parts` (user turn) **never** `system`; `tools` defaults to **empty**
  (deny, don't allow). Prompt assembly lives outside `llm/`; `llm/` exposes no `system`-from-data
  path. Nothing outside `llm/` may import `httpx` or `subprocess` (§6.5).
- **Schema-violation semantics** — follow `PITFALLS.md` M1 and `ARCHITECTURE.md` §6.2: validation is a
  boundary concern in `llm/`, the domain never sees an unvalidated dict; a validation failure is a
  **run outcome, not a crash** — record `status='invalid'` in `llm_calls`, retry a bounded number of
  times, then surface. `attempts` and the `invalid` status already exist in the shipped schema.
  `tenacity` is pinned but currently unused; `pydantic_core.from_json(..., allow_partial=True)` plus a
  `WrapValidator`/`PydanticUseDefault` is the documented salvage approach — tolerated error types
  only.
- **Per-call telemetry** — **D-12** requires recording model + version per call (PITFALLS M9).
  `llm_calls` already carries `backend`, `provider`, `model`, `agent`, `attempts`. The **opencode
  server version has no column**; whether Phase 3 adds migration 0003 (or records the version into an
  existing text field) is left to the planner as an open implementation question, not a new decision.
- **Injection flag persistence** — `SanitizeReport.instruction_like` / `patterns_matched` are
  currently discarded in `run.py` `_persist_result`; §6.3 says instruction-like text is a **finding to
  record**, not an instruction. Plumbing that flag through is required by §6.3 but the *shape* of the
  change is a planning question, not re-litigated here.

### the agent's Discretion

- Exact placement of the "Test LLM backend" action in the existing settings/health surface.
- Whether the selftest route is rate-limited / confirm-gated (it does spend tokens).
- The concrete `ProbeResult` field set (kept small; Phase 5 owns the ranking schema).
- Fixture file naming/location within `tests/llm/fixtures/`, and the constant's module location.
- Whether the operator-run live diff compares raw JSON or a normalised projection.
- Whether the opencode server version is recorded via migration 0003 or an existing text column.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

> Note: `ROADMAP.md` contains **no `Canonical refs:` line** for Phase 3 (verified — the string does
> not appear in the file). This list was therefore accumulated from REQUIREMENTS.md, PROJECT.md, the
> research documents and the two prior CONTEXT files. That absence is recorded here rather than
> papered over.

### Phase definition and requirements

- `.planning/ROADMAP.md` §Phase 3 (L118–133) — goal, the two requirements, and the four success
  criteria; also the "Research flag" that mandates resolving `format` vs `outputFormat` against the
  running server.
- `.planning/REQUIREMENTS.md` — **PLAT-02** (LLM reached through opencode as a sibling service, no
  second provider key) and **PLAT-05** (structured-output contract covered by a test that fails loudly
  on upgrade). Also PLAT-04 (limits/thresholds are configuration, shipped in Phase 1) which constrains
  any new Settings fields.
- `.planning/PROJECT.md` — the "opencode as the LLM backend / no second provider key" constraint and
  the out-of-scope list.

### Architecture and design contract (Phase 3's primary spec)

- `.planning/research/ARCHITECTURE.md` §6 (L530–607) — **the Phase 3 design contract.** §6.1 the port
  sketch; §6.2 "schema in `domain/schemas/`, validation in `llm/`"; §6.3 the untrusted-input boundary
  table (user turn, `tools=[]`, schema as blast-radius limiter); §6.4 model/agent as a per-call
  parameter, not a global; §6.5 nothing outside `llm/` imports `httpx`/`subprocess`.
- `.planning/research/PITFALLS.md` **M1** (L428–448) — Pydantic/structured-output handling that
  crashes instead of degrading; the canonical prevention list and the warning signs.
- `.planning/research/PITFALLS.md` **M9** (L592–604) — model/version drift; pin the server version and
  run the `/doc` contract test.
- `.planning/research/PITFALLS.md` **m5** (L641–642) — never put job descriptions in the system
  prompt; tools denied by default; instruction-like text is a finding to record.
- `.planning/research/PITFALLS.md` **M10** (L611–623) — the opencode server as an RCE surface if
  exposed; context for why D-05/D-06 keep it external and unpublished.
- `.planning/research/STACK.md` §Q7 — the opencode HTTP endpoint table (`/global/health`, `/session`,
  `/session/:id/message`, `/prompt_async`, `/event`, `/doc`, `/provider`, `/agent`), the
  `format`/`outputFormat` inconsistency, and the prompt-injection boundary.

### Prior phase decisions that still bind

- `.planning/phases/01-walking-skeleton-foundations/01-CONTEXT.md` — **D-05** (opencode is external and
  user-managed; no compose service), **D-06** (`OPENCODE_BASE_URL`), **D-07**
  (`OPENCODE_SERVER_PASSWORD`), **D-08** (degraded-tolerant health), **D-09** (`/config/providers` for
  discovery, never `/provider`), **D-10** (`OPENCODE_MODEL`), **D-11** (never persist/log raw provider
  payloads), **D-12** (Phase 3 must record model + version per call).
- `.planning/phases/02-clean-filtered-queryable-queue/02-CONTEXT.md` — **D-45** (the run explanation is
  deterministic and LLM-free — the reason D-49 rejects a `narrate` stage), plus the repository/stage
  patterns Phase 3 code follows.

### Repository governance and operational notes

- `AGENTS.md` — the stack constraints and the "what NOT to use" list (`format` vs `outputFormat`
  ambiguity is called out there too; the `/doc` contract test is required).
- `docs/probes/2026-09-15-scraper-survival.md` — origin of the "badge is not a reliable proxy for the
  real call" lesson referenced by D-52; also documents how the live server was probed (the pattern the
  live `/doc` test follows).
- `.planning/WINDOWS.md` — #2/#4 open items; #4 is the health-badge-vs-real-call gap informing D-52.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `app/llm/base.py` — `LLMBackend` `@runtime_checkable Protocol` with `health()` +
  `discover_models()`. Its docstring **explicitly reserves** "Phase 3 adds `complete_structured`".
  `ProviderModel` / `DiscoveryResult` / `ProbeOutcome` are the redaction-first typed models to imitate.
- `app/llm/opencode_server.py` — `OpenCodeServerBackend(*, base_url=None, password=None, timeout=None)`
  with `_auth()` (BasicAuth only when a password is set) and a bounded `httpx.AsyncClient`; path
  constants `GLOBAL_HEALTH_PATH`, `CONFIG_PROVIDERS_PATH`; tolerant `parse_providers()`. This is where
  the session/message/`/doc` HTTP lives.
- `app/llm/__init__.py` — `get_llm_backend()` DI factory, overridden in tests.
- `app/db/models.py` — `LlmCall` (L440-469) is **already provisioned**: `run_id` nullable,
  `purpose IN ('rank','narrate','tailor','extract','probe')`, `status IN ('ok','invalid','timeout','error')`,
  `attempts`, `provider`/`model`/`agent`/`backend`, token + latency columns. `Run` (L279-319) already
  has `llm_calls`, `llm_tokens`, `ranked_count` — **none ever written**.
- `app/pipeline/stages.py` — `Stage` Protocol, `StageCounts` (`.bump()`, `.fail()`), `StageResult`.
- `app/domain/sanitize.py` — pure `sanitize_text`, `looks_like_instructions`,
  `count_injection_patterns`, `INSTRUCTION_MARKERS`, `INJECTION_PATTERNS`, `SanitizeReport`
  (counts only — cannot carry matched text or PII).

### Established Patterns

- **Port + adapter + DI factory + test override** — `Protocol` in `base.py`, concrete backend,
  `get_llm_backend()`, `app.dependency_overrides[get_llm_backend]`.
- **Redaction as a type property** — Pydantic models with `extra="forbid"` carrying identifiers only;
  raw payloads are never assigned to `self`, logged, or cached. A completion response parser must
  follow the same discipline (holding a raw response body on `self` would be a redaction leak).
- **Total functions / failure-as-value** — `health()` and `discover_models()` return
  `reachable=False` on any exception; `docker compose up` must never depend on opencode (D-08).
- **Every ceiling is a Settings field** — `tests/test_config.py` AST-scans `app/probe` and
  `app/pipeline` for distinctive integer literals and fails on hard-coded limits (PLAT-04). Any new
  timeout/retry ceiling belongs in `Settings`.
- **Repositories are the only place SQL lives** — they take `AsyncSession` explicitly and **never
  commit**; the caller owns the commit.
- **`app.domain.*` is pure** — no `httpx | sqlalchemy | jobspy | jinja2 | subprocess | fastapi`.

### Integration Points

- **New route:** the selftest endpoint must carry the `current_user` seam — `tests/test_auth_seam.py`
  walks every route and pins `EXPECTED_SEAM_ROUTES`.
- **Health surface:** `app/api/health.py` `_opencode_report()` + `app/web/routes.py`
  `_health_strip(session, backend)` — the natural home for the "Test LLM backend" action (and the
  place the opencode `unreachable` message already renders).
- **New DB writer:** no `llm_call_repo` exists; `LlmCall` is currently constructed only in tests. A
  repository is needed for the selftest + Phase 5 to share.
- **`_finish()`** in `app/pipeline/run.py` is where `runs.llm_calls` / `llm_tokens` / `ranked_count`
  must eventually be written; Phase 3 provides the writer, Phase 5 provides the caller.
- **Run-history rendering:** `run_repo.RunSummary` / `RunDetail` read `errors_json` / `stage_log_json`;
  new counters need adding there to be visible (constrained by `tests/api/test_run_history.py`).

</code_context>

<specifics>
## Specific Ideas

- The wire contract to probe and pin is exactly:
  `format={"type": "json_schema", "schema": ..., "retryCount": 2}` in the message-send request body,
  and the validated payload arriving at `info["structured_output"]` in the response.
- The selftest's user part intentionally carries an instruction-like snippet — the same class of
  content `looks_like_instructions()` flags — making the live run double as a trust-boundary
  demonstration.
- The proof chain the user approved: **builder == snapshot** (default lane, no server) →
  **snapshot == live spec** (operator live lane) → **real call works** (UI selftest).

</specifics>

<deferred>
## Deferred Ideas

- **Multiple CV variations per job** — offer the user a choice of how many results they'd like, up to
  ~3 variations. Belongs in **Phase 6 (Tailoring + Verification)**.
- **Prompt templates for different CV styles, and different CV designs** — same phase 6.
- **User-supplied custom prompts passed to the LLM** — Phase 6; also needs its own trust/validation
  decision there (a user-supplied prompt is a different injection surface from a listing).

</deferred>

---

*Phase: 3-LLM Port + Structured Output*
*Context gathered: 2026-09-17*
