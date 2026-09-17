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

# --- servers / endpoints ------------------------------------------------------
DOC_PATH = "/doc"
SESSION_PATH = "/session"
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
#: `TextPartInput` requires `type` and `text`; `additionalProperties: false`.
TEXT_PART_FIELDS = ("type", "text")

__all__ = [
    "DOC_PATH",
    "FORMAT_FIELD",
    "FORMAT_INNER_KEYS",
    "FORMAT_JSON_SCHEMA_TYPE",
    "FORMAT_REQUIRED_KEYS",
    "FORMAT_RETRY_FIELD",
    "FORMAT_SCHEMA_FIELD",
    "FORMAT_TYPE_FIELD",
    "MESSAGE_DOC_PATH",
    "MESSAGE_MODEL_FIELDS",
    "MESSAGE_PATH",
    "MESSAGE_REQUIRED_FIELDS",
    "SESSION_ID_FIELD",
    "SESSION_ID_PREFIX",
    "SESSION_MODEL_FIELDS",
    "SESSION_PATH",
    "STRUCTURED_ERROR_MESSAGE_PATH",
    "STRUCTURED_ERROR_NAME",
    "STRUCTURED_ERROR_RETRIES_PATH",
    "STRUCTURED_RESPONSE_PATH",
    "TEXT_PART_FIELDS",
    "TEXT_PART_TYPE",
]
