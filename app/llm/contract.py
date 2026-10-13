"""Pinned opencode wire contract — the single home of every wire name (D-54/D-56).

**Verified against a live opencode server 1.18.31 on 2026-09-17** (`GET /doc` and
`GET /config/providers` fetched directly, plus a real schema-constrained call).
The server's own docs are unreliable on precisely the two fields that matter —
the docs say `outputFormat` and `structured_output`; the running server accepts
`format` and returns `structured`. The running server wins.

**Deliberate refresh:** when opencode genuinely renames one of these, change it
HERE and refresh `tests/llm/fixtures/opencode-doc.json` intentionally. That is the
whole point of having exactly one place to change (D-54); do NOT add an adaptive
"accept either name" fallback — it would silently absorb a rename and defeat the
contract test (success criterion 3).

This module imports nothing but `__future__`, so importing it needs no network
and cannot drag an I/O dependency into `app/domain`.
"""

from __future__ import annotations

# =============================================================================
# V1 contract (retained) — D-148
#
# Kept verbatim so a V1 server still works (D-147). Do NOT add V2 twins of the
# V1-only `FORMAT_*` / `STRUCTURED_*` / `PERMISSION_*` names: V2 has no
# server-side structured output, so those names have no V2 meaning.
# =============================================================================

# --- servers / endpoints ------------------------------------------------------
DOC_PATH = "/doc"
SESSION_PATH = "/session"
#: V1 liveness probe. Lives here (not in `opencode_server`) because this module is
#: the single home of every wire name (D-54) — and `detection.py` needs it without
#: importing `opencode_server` (which would be an import cycle).
GLOBAL_HEALTH_PATH = "/global/health"
#: The wire spelling WE build the message URL with.
MESSAGE_PATH = "/session/{session_id}/message"
#: The OpenAPI path-template spelling the installed spec serves — its path
#: parameter is literally `sessionID`. Used ONLY to index the committed `/doc`
#: fixture and the live spec. The two constants exist deliberately; do not
#: "fix" one into the other (see RESEARCH Pitfall P3 and the `/doc` slice).
MESSAGE_DOC_PATH = "/session/{sessionID}/message"

# --- the request-side structured-output contract (D-54/D-56) ------------------
#: The request field name. NOT "outputFormat" — `outputFormat` occurs 0 times in
#: the live 478,968-byte spec, and `format` is the property on the message body.
FORMAT_FIELD = "format"
FORMAT_TYPE_FIELD = "type"
FORMAT_SCHEMA_FIELD = "schema"
#: OPTIONAL on the wire: `required: ["type", "schema"]` excludes it.
FORMAT_RETRY_FIELD = "retryCount"
FORMAT_JSON_SCHEMA_TYPE = "json_schema"
#: Every key the inner object may carry.
FORMAT_INNER_KEYS = (FORMAT_TYPE_FIELD, FORMAT_SCHEMA_FIELD, FORMAT_RETRY_FIELD)
#: The keys the inner object MUST carry.
FORMAT_REQUIRED_KEYS = (FORMAT_TYPE_FIELD, FORMAT_SCHEMA_FIELD)

# --- the response-side structured-output contract ----------------------------
#: Live 1.18.31 truth: the validated payload is at `info.structured`. The docs
#: and older notes say `structured_output` — that spelling occurs 0 times in the
#: live spec and reading it yields None on every successful call (Pitfall P2).
STRUCTURED_RESPONSE_PATH = ("info", "structured")
STRUCTURED_ERROR_NAME = "StructuredOutputError"
#: `info.error` is an envelope: the attempt count and message are nested under
#: `data` (Pitfall P7).
STRUCTURED_ERROR_RETRIES_PATH = ("info", "error", "data", "retries")
STRUCTURED_ERROR_MESSAGE_PATH = ("info", "error", "data", "message")

# --- the request body shape ---------------------------------------------------
#: `required` on the message-send body is `["parts"]` only.
MESSAGE_REQUIRED_FIELDS = ("parts",)
#: The MESSAGE body's model shape. NOT the session shape below (Pitfall P3).
MESSAGE_MODEL_FIELDS = ("providerID", "modelID")
#: `POST /session`'s model shape — a DIFFERENT object from `MESSAGE_MODEL_FIELDS`.
SESSION_MODEL_FIELDS = ("id", "providerID")
SESSION_ID_FIELD = "id"
#: `Session.id` has `pattern: "^ses"`.
SESSION_ID_PREFIX = "ses"
TEXT_PART_TYPE = "text"
#: The `parts[].type` discriminator: used to BUILD a text part and to OBSERVE the
#: returned part types. This phase emits and accepts text parts only.
PART_TYPE_FIELD = "type"
#: `TextPartInput` requires `type` and `text`; `additionalProperties: false`.
TEXT_PART_FIELDS = (PART_TYPE_FIELD, "text")

# --- the tool-deny control surface (success criterion 4 / Pitfall P5) ---------
#
#: `POST /session` accepts a `permission` ruleset (`PermissionRuleset`): an array of
#: `PermissionRule` objects, each requiring ALL THREE of `permission`, `pattern` and
#: `action` (verified against the live 1.18.31 `/doc`, 2026-09-17). This is the
#: DOCUMENTED, non-deprecated tool control; the message-level `tools` map is
#: deprecated and its wildcard semantics are undocumented (A2), so `permission` is
#: where the enforced deny lives.
PERMISSION_FIELD = "permission"
PERMISSION_RULE_FIELDS = ("permission", "pattern", "action")
#: The fail-closed action. `ask` is never sent. `allow` is emitted for exactly ONE
#: rule — the server-internal structured-output carve-out (`PERMISSION_ALLOW_ACTION`
#: below) — because opencode 1.18.31 implements structured output through a tool it
#: injects into the session, and a catch-all deny that suppresses that tool makes
#: every schema-constrained call fail (RESEARCH Pitfall P5 item 4).
PERMISSION_DENY_ACTION = "deny"
#: The one non-deny action this phase emits: the structured-output carve-out's
#: action. Order-sensitive — see `opencode_server.DEFAULT_DENY_RULES`.
PERMISSION_ALLOW_ACTION = "allow"
#: A bare `"*"` is legal as a `permission` key/pattern. It is deliberately NOT
#: legal in the deprecated `tools` map — hence no `TOOLS_WILDCARD` constant exists.
PERMISSION_WILDCARD = "*"
#: The synthetic tool opencode 1.18.31 injects into the session when the message
#: body carries `format`: the server forces the tool choice to `required` and
#: captures the structured payload only inside that tool's `execute()`. Our
#: session ruleset must therefore grant exactly this name (and nothing else), or
#: every schema-constrained call fails with `StructuredOutputError` while the
#: default lane stays green (Pitfall P5 item 4).
STRUCTURED_OUTPUT_TOOL_NAME = "StructuredOutput"
#: The `parts[].type` value of a tool invocation. Used by the differential cause
#: to tell a model that declined the forced tool call from a ruleset that stripped
#: the tool — a TYPE NAME only, never the part's text.
PART_TYPE_TOOL = "tool"
#: The deprecated message-level `tools` field: a name→boolean map of explicit
#: per-name GRANTS. Never a bare `"*"`, and never an empty map (an undocumented
#: empty map is not a deny).
MESSAGE_TOOLS_FIELD = "tools"

# =============================================================================
# V2 contract (opencode 2.0.x) — D-147/D-148
#
# Added alongside the retained V1 group so neither spelling can silently absorb
# the other. V2 has NO server-side structured output: the schema travels in the
# generate prompt and validation is client-side (`opencode_server`). There are
# therefore deliberately no V2 `FORMAT_*`/`STRUCTURED_*`/`PERMISSION_*` twins.
# =============================================================================

# --- servers / endpoints ------------------------------------------------------
#: The V2 OpenAPI document (auth required) — the operator lane's spec source.
OPENAPI_PATH = "/openapi.json"
#: V2 liveness/identity probe. Probed V2-FIRST: its JSON carries `version`. The
#: SPA fallback serves HTML on every legacy path, so a bare HTTP 200 is never
#: enough (Pitfall P4).
INFO_PATH = "/api/info"
V2_MODEL_PATH = "/api/model"
V2_PROVIDER_PATH = "/api/provider"
V2_SESSION_PATH = "/api/session"
#: The wire spelling WE build the generate URL with.
GENERATE_PATH = "/api/session/{session_id}/generate"
#: The OpenAPI path-template spelling the installed spec serves — its path
#: parameter is literally `sessionID`. Used ONLY to index the committed V2 slice
#: and the live spec; mirrors `MESSAGE_DOC_PATH` (do not "fix" one into the other).
GENERATE_DOC_PATH = "/api/session/{sessionID}/generate"
#: `POST /api/session/{id}/generate`'s one body property (`required: ["prompt"]`).
GENERATE_PROMPT_FIELD = "prompt"
#: The generated text lives at `{"data": {"text": "…"}}`.
GENERATE_RESPONSE_PATH = ("data", "text")
#: V2 wraps the session in `{"data": {…}}`, so the id is NOT at the top level
#: (Pitfall P2); kept beside V1's `SESSION_ID_FIELD`.
V2_SESSION_RESPONSE_PATH = ("data", "id")
#: `Model.Ref` = `{id, providerID, variant?}` — an OBJECT with
#: `additionalProperties: false`, never a bare string (a bare string is a 400;
#: Pitfall P1).
MODEL_REF_FIELDS = ("id", "providerID")
#: The server-version field on `GET /api/info` (D-150).
SERVER_INFO_VERSION_FIELD = "version"
#: The reachability marker on the V1 `/global/health` body.
HEALTH_HEALTHY_FIELD = "healthy"

__all__ = [
    "DOC_PATH",
    "FORMAT_FIELD",
    "FORMAT_INNER_KEYS",
    "FORMAT_JSON_SCHEMA_TYPE",
    "FORMAT_REQUIRED_KEYS",
    "FORMAT_RETRY_FIELD",
    "FORMAT_SCHEMA_FIELD",
    "FORMAT_TYPE_FIELD",
    "GENERATE_DOC_PATH",
    "GENERATE_PATH",
    "GENERATE_PROMPT_FIELD",
    "GENERATE_RESPONSE_PATH",
    "GLOBAL_HEALTH_PATH",
    "HEALTH_HEALTHY_FIELD",
    "INFO_PATH",
    "MESSAGE_DOC_PATH",
    "MESSAGE_MODEL_FIELDS",
    "MESSAGE_PATH",
    "MESSAGE_REQUIRED_FIELDS",
    "MESSAGE_TOOLS_FIELD",
    "MODEL_REF_FIELDS",
    "OPENAPI_PATH",
    "PART_TYPE_FIELD",
    "PART_TYPE_TOOL",
    "PERMISSION_ALLOW_ACTION",
    "PERMISSION_DENY_ACTION",
    "PERMISSION_FIELD",
    "PERMISSION_RULE_FIELDS",
    "PERMISSION_WILDCARD",
    "SERVER_INFO_VERSION_FIELD",
    "SESSION_ID_FIELD",
    "SESSION_ID_PREFIX",
    "SESSION_MODEL_FIELDS",
    "SESSION_PATH",
    "STRUCTURED_ERROR_MESSAGE_PATH",
    "STRUCTURED_ERROR_NAME",
    "STRUCTURED_ERROR_RETRIES_PATH",
    "STRUCTURED_OUTPUT_TOOL_NAME",
    "STRUCTURED_RESPONSE_PATH",
    "TEXT_PART_FIELDS",
    "TEXT_PART_TYPE",
    "V2_MODEL_PATH",
    "V2_PROVIDER_PATH",
    "V2_SESSION_PATH",
    "V2_SESSION_RESPONSE_PATH",
]
