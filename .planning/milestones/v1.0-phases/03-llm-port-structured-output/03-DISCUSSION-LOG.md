# Phase 3 Discussion Log: LLM Port + Structured Output

**Gathered:** 2026-09-17
**Areas presented:** End-to-end proof surface · /doc contract test mechanics · Schema-violation semantics · Port contract & trust boundary
**Areas discussed:** End-to-end proof surface · /doc contract test mechanics
**Areas not selected:** Schema-violation semantics · Port contract & trust boundary — governed by locked prior decisions (ARCHITECTURE.md §6.1–6.3, PITFALLS M1/M9, Phase 1 D-12); see 03-CONTEXT.md "Carried forward".

---

## Area 1 — End-to-end proof surface

### Q1. What should actually perform the live schema-constrained call in Phase 3?

The tension surfaced to the user: "end to end" plus "explicit, retried run outcome" imply production
code performs a live call and something records it against a run — but ranking (the first real LLM
consumer) is Phase 5, and a `narrate` stage would contradict D-45's deliberately deterministic,
LLM-free run explanation.

| Option | Description |
|---|---|
| **On-demand UI selftest** (chosen) | A real "Test LLM backend" action on the settings/health page: one schema-constrained call on demand, written to `llm_calls` (`purpose='probe'`), result + model + latency shown in the UI. Proves the full app path (route → `current_user` seam → backend → validation → persistence → render), costs nothing per run, gives the operator a live smoke check. |
| Operator-run live test only | Only a `@pytest.mark.live` test performs the real call; no production code path invokes the model. Cheapest, zero accidental spend — but "end to end" is proven by a test command and `llm_calls` persistence never runs against a real response in-app. |
| Per-run diagnostic stage | Every `run_pipeline()` makes one cheap structured diagnostic call and records `llm_calls` + `runs.llm_calls`/`llm_tokens`. Most literal reading of "run outcome", but adds LLM spend to every run and brushes against D-45. |
| Both live test and UI selftest | Belt and braces; more surface to build and test. |

**Selection:** On-demand UI selftest.

### Q2. How should the on-demand selftest be recorded?

| Option | Description |
|---|---|
| **`llm_calls` only, no run row** (chosen) | One row with `run_id` NULL, `purpose='probe'`, status/attempts/error/model/latency filled. **Zero migration** — `run_id` is already nullable and `purpose='probe'` is already in the CHECK constraint. Selftests never appear in `/runs` history and cannot pollute the run-reason logic. |
| Synthetic `runs` row | Visible alongside real runs in `/runs`, but needs a distinct trigger marker so run-reason logic and the last-run strip don't treat a selftest as a search run — more surface, risks confusing Phase 2 run-history semantics. |
| Response-only, no persistence | Simplest, but no audit trail at all — weakens criterion 2's "recorded outcome" and leaves the operator nothing to inspect afterwards. |

**Selection:** `llm_calls` only, no run row.

### Q3. What should the selftest actually ask the model for?

| Option | Description |
|---|---|
| **Generic probe schema** (chosen) | A small purpose-built `ProbeResult` used only by the selftest; the prompt ships a canned adversarial / instruction-like snippet in the user part, so the live run proves both the constrained-output path and that the system prompt stays constant — while leaving Phase 5's ranking schema unconstrained. |
| Reuse a Phase 5 ranking schema | Gives Phase 5 a head start, but commits to a ranking schema the roadmap explicitly defers — including batching/calibration questions still open. |
| Extraction over a real listing | Strongest live demonstration of the trust boundary, but starts building Phase 5's requirement extraction early and couples the selftest to queue contents. |

**Selection:** Generic probe schema.

### Q4. When the selftest fails, what should the operator see?

| Option | Description |
|---|---|
| **Full cause + attempts** (chosen) | Distinguish unreachable / timeout / invalid-after-N-attempts / other error, plus attempt count, latency and the validation message — persisted on the `llm_calls` row and rendered where the test was run. |
| Status only, details in DB | Less UI surface, but the operator must query SQLite to find out why the backend is unhappy. |
| Reuse health-strip badge | Established pattern, but WINDOWS.md #4 already flags that a badge can mislead when it is not a reliable proxy for the real call. |

**Selection:** Full cause + attempts.

---

## Area 2 — /doc contract test mechanics

Framing given to the user: success criterion 3 says a **CI** test reads the installed server's
`GET /doc`, but this repo has **no CI runner at all** (`.github/` absent, no `.gitlab-ci.yml`, no
`.circleci`) and pytest runs with `addopts="-m 'not live'"` — so a live-only test would never fire on
an upgrade.

### Q1. Where should the /doc contract test actually run?

| Option | Description |
|---|---|
| **Snapshot fixture + live diff** (chosen) | Commit the real spec slice as a fixture; a default-lane test asserts our client's expected key exists in the snapshot AND that our request builder emits exactly that key (code-side rename fails with no server). An operator-run `@pytest.mark.live` test refetches `/doc` and diffs, failing loudly on server drift; the runbook gains a "run the live lane, refresh the snapshot deliberately" step. Zero CI infrastructure. |
| Live-only test | Closest to "reads the installed server" in spirit, nothing to maintain — but the default lane never runs it, so an upgrade is caught only if an operator remembers; it does not really "fail loudly on an upgrade". |
| Stand up real CI now | Most literal reading of criterion 3, but the repo has no CI today, so Phase 3 would also stand up the runner, secrets and workflow — larger scope than the phase and not required by PLAT-02 or PLAT-05. |

**Selection:** Snapshot fixture + live diff.

### Q2. How strictly should the structured-output field name be pinned?

| Option | Description |
|---|---|
| **Pin one exact key** (chosen) | An operator step probes the running server; the real name (likely `format`) is recorded as a single constant; the test asserts exactly that key in the snapshot and the request builder. Any other name fails. The constant is the one place to change on a genuine rename. |
| Adaptive: accept either name | Client accepts `format` or `outputFormat`, picking whichever `/doc` advertises. More resilient, but **directly defeats criterion 3** — a rename would be silently absorbed — and behaviour would differ between server versions with no test signal. |
| Probe both keys on the wire | Send both and see which is honoured. Thorough, but doubles the live probing surface and bakes a workaround into the client instead of pinning a contract. |

**Selection:** Pin one exact key. (A **scope-creep** answer arrived first on this question — see
"Deferred ideas" below — and the question was re-asked after noting the deferral.)

### Q3. What should the committed /doc snapshot cover?

| Option | Description |
|---|---|
| **Snapshot the relevant slice** (chosen) | Only the structured-output-relevant portion: the message-send request-body schema (property names, the structured-output key) and the endpoint path. Small and readable; failures point at the actual contract rather than unrelated OpenAPI churn. |
| Full /doc snapshot | Most literal reading of "reads GET /doc", but any unrelated opencode change (new endpoint, description tweak) fails the test for reasons that do not affect us — false alarms erode trust. |
| No snapshot, expectation dict only | Smallest fixture, but the offline lane then proves nothing about the real server's shape. |

**Selection:** Snapshot the relevant slice.

### Q4. What else should the /doc contract test pin, beyond the request field name?

| Option | Description |
|---|---|
| **Whole contract surface** (chosen) | The request field name (`format`), its inner keys (`type`, `json_schema`, `retryCount`), the response location (`info.structured_output`), and the message-send endpoint path — each asserted against the committed slice with its own constant. Both ends can drift; criterion 3 says "the structured-output contract", not just one key. |
| Request field name only | Narrowest reading, least brittle, but a rename of the response path or inner retry key still breaks the client silently — the exact failure mode this test exists to prevent. |
| Request + response names only | Middle ground; leaves `retryCount` unpinned even though retry behaviour is a criterion-2 concern. |

**Selection:** Whole contract surface.

### Q5. Should the live /doc contract test also perform a real structured call?

| Option | Description |
|---|---|
| **Spec fetch + diff only** (chosen) | The real schema-constrained call lives solely in the in-app selftest, so there is one implementation of the wire call and criterion 3 stays a pure contract-drift test. Chain of proof: builder == snapshot (default lane), snapshot == live spec (live lane), real call works (UI selftest). |
| Also make a live structured call | Strongest single-command proof of criteria 1 and 3 together, but duplicates the wire call the UI selftest already exercises, giving two paths that can drift from each other. |

**Selection:** Spec fetch + diff only.

---

## Deferred ideas (scope creep captured and redirected)

On the "/doc field" question the user instead raised a tailoring-capability idea: offering the user a
choice of how many results they'd like (up to ~3 CV variations), prompt templates for different CV
styles, different CV designs, and user-supplied custom prompts passed to the LLM. This was noted as a
**Phase 6 (Tailoring + Verification)** capability, not Phase 3 plumbing, and the question was re-asked.
All three ideas are recorded in `03-CONTEXT.md` under Deferred Ideas.

---

## Areas presented but not selected

- **Schema-violation semantics** — attempt count; who retries (opencode `format.retryCount` vs a
  client-side tenacity loop vs both); per-attempt vs final persistence; whether one failed call fails
  the run or records `status='invalid'` and continues; partial-JSON salvage before retrying.
- **Port contract & trust boundary** — the `complete_structured` signature and `StructuredCallResult`
  shape per §6.1; where prompts are assembled (`pipeline/*` vs `llm/*`); how "listing text only in user
  parts + `tools=[]` by default" is structurally enforced and test-pinned; telemetry — the opencode
  server version has no `llm_calls` column, so does Phase 3 need migration 0003; and whether to persist
  the injection flag ingest currently discards.

These remain governed by locked prior decisions (ARCHITECTURE.md §6.1–6.3, PITFALLS M1/M9, Phase 1
D-12). See the "Carried forward" subsection of `03-CONTEXT.md`.
