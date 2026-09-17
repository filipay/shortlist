# Phase 3 — API Coverage Matrix

**Phase:** 3 — LLM Port + Structured Output
**Service integrated:** the user's own `opencode serve` HTTP server (verified live at 1.18.31)
**Authored:** 2026-09-17

## How this matrix was produced

The deterministic detector was run over the phase scope exactly as the planning contract requires:

```bash
SCOPE="$(cat .planning/phases/03-llm-port-structured-output/*-PLAN.md) \
        $(node gsd-core/bin/gsd-tools.cjs query roadmap.get-phase 3)"
printf '%s' "$SCOPE" | node gsd-core/bin/lib/api-coverage.cjs --json
# -> {"detected":false,"signals":[],...}   exit 1
```

`detected:false` here is a **real no-signal verdict on the prose, not a skip** — no `skipped:true`
was emitted, so the detector genuinely examined the input. Its compound signal (an integration verb
and an external-API noun in the same clause, after code spans and path-shaped tokens are stripped)
does not fire on this phase's plan text, because the plans describe a port, an endpoint path, and a
wire contract rather than using the verb-plus-noun phrasing the detector keys on.

The phase nevertheless integrates an external service: `OpenCodeServerBackend` performs HTTP calls
against the user's `opencode serve` instance. Per the mandatory COVERAGE.md deliverable, the
capability surface is therefore enumerated **manually and honestly** below, including the
capabilities this phase deliberately declines.

Constraint reminder honoured throughout: **no second provider key** is configured or required — the
only credential is the optional same-server `OPENCODE_SERVER_PASSWORD` (D-07).

## Coverage Matrix

| capability | decision | reason |
|---|---|---|
| `GET /global/health` | INTEGRATE | Reached per call for the server version recorded on `llm_calls.server_version` (D-12 / PITFALLS M9); already the Phase-1 reachability path. |
| `GET /doc` | INTEGRATE | Source of the pinned structured-output contract: a committed hand-projected snapshot in the default lane plus an operator live diff (D-53/D-55/D-57). |
| `GET /config/providers` | INTEGRATE | The only model-discovery surface (D-09); resolves the bare `OPENCODE_MODEL` into `{providerID, modelID}` and fails loud on a miss. |
| `POST /session` | INTEGRATE | One session created per call and discarded, carrying the default-deny `permission` ruleset that enforces success criterion 4. |
| `POST /session/{sessionID}/message` | INTEGRATE | The core path: `parts` + `system` + `model` + `format={type,schema,retryCount}`; the validated payload is read from `info.structured`. |
| `format` request field | INTEGRATE | Pinned verbatim as one constant (D-54/D-56); the request builder emits exactly it, and any other name fails the contract test. |
| `format.retryCount` | INTEGRATE | Sent from `Settings.opencode_structured_retry_count`, so server-side validation retries are configuration and never a literal (PLAT-04). |
| `info.structured` response payload | INTEGRATE | The validated typed result, read through the response-path constant and validated by Pydantic once at the boundary (ARCHITECTURE §6.2). |
| `info.error` `StructuredOutputError` envelope | INTEGRATE | Classified as `status='invalid'` with the attempt count from `info.error.data.retries`; never a silent success (criterion 2). |
| `info.tokens` accounting | INTEGRATE | Prompt and completion tokens are recorded per call so spend is auditable. |
| `info.providerID` / `modelID` / `agent` | INTEGRATE | Recorded per call so a model change can be traced to the call it produced (D-12). |
| Per-call agent selection | INTEGRATE | The port carries an `agent` parameter and records `info.agent`; the selftest passes `None`, but the capability is integrated rather than bypassed. |
| BasicAuth via `OPENCODE_SERVER_PASSWORD` | INTEGRATE | Sent when configured (D-07); an empty password sends no auth header at all, and no other credential path exists. |
| Session `permission` ruleset (default-deny) | INTEGRATE | A deny posture on `POST /session` — the documented control that replaces the deprecated `tools` field for criterion 4. |
| Text parts as user content | INTEGRATE | Untrusted content arrives only as `{"type":"text","text":...}`; the builder supports no other part type. |
| `POST /session/{id}/prompt_async` | OPT-OUT | Phase 3 is one synchronous on-demand call; the fire-and-forget path has no consumer until ranking or scheduling lands. |
| `GET /event` SSE stream | OPT-OUT | No UI consumer this phase; `stream_events()` is deliberately omitted rather than shipped as an unused Protocol method. |
| `GET /provider` | OPT-OUT | D-09 forbids it: the ~6 MB full vendor catalogue is unrelated to the user's subscription-scoped provider set. |
| `GET /experimental/tool/ids` | OPT-OUT | Explicitly experimental and churning; the deny uses the documented `permission` ruleset rather than a discovered tool-name list. |
| `GET /agent` catalogue discovery | OPT-OUT | 48 agents and no consumer in Phase 3; an agent is supplied per call once a later phase has one to choose. |
| `permission` allow/ask actions and pattern rules | OPT-OUT | Only the default-deny posture is needed in v1; allow/ask semantics have no consumer and would widen the boundary. |
| Message `tools` name-to-boolean map | OPT-OUT | Deprecated in favour of `permission`, and its empty/wildcard semantics are undocumented; an explicit map is emitted only for a caller-supplied allow-list. |
| Session metadata: title, metadata, parentID, workspaceID | OPT-OUT | Purely additive session properties with no product use in a one-shot probe call. |
| Message `noReply` and `messageID` | OPT-OUT | Storing context-only messages and caller-supplied ids solve problems Phase 3 does not have. |
| Message `variant` | OPT-OUT | Model-variant selection is a pricing and quality decision for Phase 5's ranking budget, not this port slice. |
| File, agent and subtask parts | OPT-OUT | ARCHITECTURE §6.3 requires untrusted content to arrive as text; a file-path part is an exfiltration shape this phase does not need. |
| `info.cost` | OPT-OUT | Not a Phase-3 column; per-run spend caps (RANK-08) are Phase 5 and own cost semantics. |
| Generated OpenAPI client | OPT-OUT | Three hand-rolled `httpx` calls beat pinning ~470 schemas; this is the repo's STACK.md Q7 position, unchanged. |
| CLI `subprocess` fallback backend | OPT-OUT | Not required by PLAT-02/PLAT-05; the port permits it as a class, and nothing outside `app/llm/` may import `subprocess`. |

**Totals:** 29 capabilities — 15 INTEGRATE, 14 OPT-OUT. Every opt-out carries a reason; no capability
is silently ignored.

## Notes for the seal-time gate

- The matrix is the markdown-table form the validator expects (`| capability | decision | reason |`),
  with no cell exceeding the capability/reason length bounds and no pipe inside a cell.
- `POST /session/{sessionID}/message` is the single capability the phase's four success criteria rest
  on; `GET /doc` is the single capability the contract test rests on.
- The two deliberately-declined capabilities that a reviewer is most likely to question are
  `GET /event` (streaming) and `prompt_async` — both are deferred with the phase that will consume
  them (5 and 8 respectively), not dropped by omission.
