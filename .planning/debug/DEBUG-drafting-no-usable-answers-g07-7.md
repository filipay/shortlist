---
status: diagnosed
trigger: "G-07-7 — drafting-no-usable-answers-g07-7"
created: 2026-10-12T00:00:00Z
updated: 2026-10-12T10:20:00Z
goal: find_root_cause_only
---

# G-07-7 — "The drafting call did not return a usable response"

## Gap

`POST /listings/109/apply/draft` (the **Draft answers** action on an apply package) returns
HTTP 502 `data-error="drafting_failed"` with _"The drafting call did not return a usable
response. Your existing drafts were kept."_ and writes no `screening_drafts` rows, so the
user has nothing to review or copy.

Truth that must hold: clicking **Draft answers** returns usable drafted answers the user can
review and copy.

## Root Cause

The model's structured payload reaches the app with `ScreeningAnswer.evidence_ids` — a
`list[str]` — encoded as a **single-key array-wrapper object `{"item": <value>}`**, and once
as the empty string `""`.

`_coerce_evidence_ids` (`app/domain/schemas/screening.py:37-53`) tolerates `None`, a `str`,
a `list` and a `tuple`, but **returns any `Mapping` untouched**. `{"item": [...]}` is a
`Mapping`, so it is passed straight to pydantic, which requires a list and raises
`list_type` → `"Input should be a valid list"` at loc `('answers', 0, 'evidence_ids')`
(the FIRST error in the response).

The rest of the chain then behaves exactly as designed:

1. `_salvage` (`app/llm/opencode_server.py:912-930`) catches the `ValidationError`;
   `list_type` is deliberately **not** in `TOLERATED_SCHEMA_ERRORS`
   (`opencode_server.py:93`) so it re-raises → `status="invalid"`,
   `error="validation failed: Input should be a valid list"`.
2. `result.ok` is `False`, so `draft_screening_answers` returns `None`
   (`app/pipeline/draft.py:212-213`).
3. `draft_answers` maps `None` to the 502 `drafting_failed` refusal
   (`app/api/apply.py:335-341`) — the exact copy the user reported. It writes no rows, so
   the previously stored drafts are (correctly) preserved — and empty.

**The pre-diagnosis in `07-UAT.md` is wrong.** It hypothesised `answers` itself arriving as a
scalar. `answers` was a **proper 4-element JSON array in every captured failure**. The defect
is one level deeper, in the nested `evidence_ids` field.

**Contributing factors (two categories — the AND-gate holds):**

- *provider/serializer (environment)* — opencode-go → minimax-m3 intermittently encodes a
  JSON array as `{"item": ...}` (and an empty array as `""`), and opencode's own
  `StructuredOutput` tool reported `state.status="completed"`, i.e. the server-side schema
  check did **not** reject the wrapped shape.
- *code* — the schema-boundary coercion has no branch for a `Mapping` in a `list[str]`
  position, so the only place that could absorb the artifact does not.

**It is a Bohrbug, not an intermittent one** — the "intermittence" is only whether the
provider emits the wrapper on a given call. Given the wrapper, the failure is deterministic.

## Evidence Summary

### The failing call, captured exactly

`llm_calls` (live `data/jobsearch.db`, read-only via `.venv/bin/python`):

| id | created_at (UTC) | purpose | status | attempts | latency_ms | model | server_version | error |
|----|------------------|---------|--------|----------|-----------|-------|----------------|-------|
| 55 | 2026-10-06T22:52:17 | tailor | **invalid** | 1 | 41335 | minimax-m3 | 1.18.33 | `validation failed: Input should be a valid list` |
| 52 | 2026-10-01T11:39:02 | tailor | invalid | 1 | 52054 | minimax-m3 | 1.18.33 | `validation failed: Input should be a valid list` |
| 51 | 2026-10-01T11:17:47 | tailor | invalid | 1 | 45702 | minimax-m3 | 1.18.33 | `validation failed: Input should be a valid list` |
| 50 | 2026-10-01T11:12:22 | tailor | ok | 1 | 115350 | minimax-m3 | 1.18.33 | — |

`llm_calls` stores no payload (P9 privacy rule; `tests/db/test_no_pii_columns.py`), so the
raw shape was recovered from the **opencode host's own store**,
`/home/opencode/.local/share/opencode/opencode.db` (read-only), where the drafting session
still exists:

- session `ses_eec95112fffesM3mxIMTW5scmO`, `time_created = 2026-10-06T22:52:17.489Z`
  — **+0.5 s** from the `llm_calls` id-55 row (the session IS that call).
- assistant message `msg_1136b148b001KdoS5UXS9WsJ51`, model `minimax-m3`,
  provider `opencode-go`, `finish="tool-calls"`.
- tool part `prt_1136b7588001Dcuq1W7cRYId6M`, `tool="StructuredOutput"`,
  `state.status="completed"`, `state.input` identical to `info.structured`.

Captured payload (types; prose/ids redacted to lengths — the app's own CV-derived text):

```
info.structured = {"answers": [ <4 objects> ]}          # top-level keys: ['answers']
  answers[0]  question=str(36)  answer=str(729)  evidence_ids = {"item": list[17] of str}
  answers[1]  question=str(27)  answer=str(220)  evidence_ids = {"item": "exp/self-employed-2026"}
  answers[2]  question=str(34)  answer=str(212)  evidence_ids = ""        # empty string
  answers[3]  question=str(47)  answer=str(487)  evidence_ids = {"item": list[3] of str}
```

`answers` is a valid array of 4 dicts with exactly the keys `question`/`answer`/`evidence_ids`.
The first pydantic error is therefore at `('answers', 0, 'evidence_ids')` → `list_type` →
`"Input should be a valid list"`, matching the stored `llm_calls.error` byte-for-byte.

### Why the earlier G-07-2 fix did not close it

- The G-07-2 coercion (`9521696`, 2026-10-05T22:39Z) added: `answers` as a single Mapping →
  one-element list; `evidence_ids` as a bare `str` → comma-split. The plan/summary call this
  the "recorded payload", but **no payload was ever recorded** — it was an inference from the
  error string alone. The real payload keeps `answers` as an array and defects in the
  **nested** `evidence_ids`.
- **The deployed code included that fix.** The reported copy was written only by commit
  `c993c7a` (2026-10-05T22:44Z); before it, a `None` result rendered the *old* text
  _"The drafting call returned no answers…"_ with reason `drafting_empty` (`git show
  9521696^:app/api/apply.py`). The user saw the **new** `drafting_failed` copy, so the running
  container had 9521696 + c993c7a — and call 55 still failed. The G-07-2 coercion provably
  does not cover the real shape.
- The G-07-2 prompt hardening (_"return each answer's evidence_ids as a JSON array of
  strings"*, `app/pipeline/draft.py:99-100`) was in force for call 55 and the model still
  wrapped the array. **Prompt tightening cannot be the fix.**

### The same class on the other schemas

- id 48 (2026-09-30T09:10:29, `invalid`, list_type) is a **tailoring** call, not a drafting
  one (payload keys `listing_id`/`ops`/`gaps`/`suggestions`; the drafting stage was committed
  later that day, 16:32–16:42). Its `gaps[0].evidence_ids` was `""` — the same
  "array-typed field arrives as a non-array" artifact, on a schema with no coercion branch at
  all. (Top-level lists inspected only; see "not captured".)
- id 51's payload carried a stray **top-level** `item` key alongside `answers`
  (`keys=['answers','item']`), i.e. the wrapper also reaches the outermost object level.
- ids 51/52 failed on `evidence_ids == ""` (pre-fix, now coerced to `[]`); id 55 failed on
  `{"item": ...}` (post-fix, still unhandled).

## Files Involved

| File | Line(s) | Involvement |
|------|---------|-------------|
| `app/domain/schemas/screening.py` | 37-53 | **`_coerce_evidence_ids` — the defect.** Handles `None`/`str`/`list`/`tuple`; a `Mapping` (`{"item": …}`) falls through untouched and fails `list[str]`. |
| `app/domain/schemas/screening.py` | 63-80 | `_coerce_answers` — the pre-diagnosis suspect; **not** the failing field on this payload, but symmetric unwrapping is wanted (the wrapper also appears at top level, as the stray `item` key in id 51). |
| `app/llm/opencode_server.py` | 93, 912-930 | `TOLERATED_SCHEMA_ERRORS` excludes `list_type` by design; `_salvage` re-raises → `status=invalid`. Correct as-is — do **not** widen it (the M1 hazard). |
| `app/pipeline/draft.py` | 176-185, 212-213 | Makes the one structured call; returns `None` on `not result.ok` → the route's unusable-response branch. |
| `app/api/apply.py` | 335-341 | Maps `None` → 502 `drafting_failed` with the reported copy; writes no rows (drafts preserved). Behaviour is correct given a `None`; the defect is upstream. |
| `app/domain/cv.py` | `GapFinding.evidence_ids`, `Suggestion.evidence_ids` | Same defect class (id 48's `gaps[].evidence_ids = ""`); candidate for the shared helper. |
| `tests/domain/test_screening_schema.py` | 85-88 | `test_a_scalar_answers_value_still_fails_loudly` — encodes the (wrong) pre-diagnosis assumption; must be kept as the fail-loud direction but the new wrapper case added. |
| `tests/llm/test_salvage.py` | 184-205 | Golden-payload test for the **inferred** shape; needs the real captured payload added. |

## Suggested Fix Direction (diagnosis only — no code changed)

1. **Minimal, root-cause fix.** In `_coerce_evidence_ids`, before the existing branches,
   unwrap a single-key array-wrapper `Mapping`: when the value is a `Mapping` whose sole value
   is itself a scalar/list/Mapping, unwrap to that value and re-apply the existing logic
   (loop, so `{"item": {"item": […]}}` also resolves). A `Mapping` is never a legal
   `list[str]`, so this only converts *invalid → valid*; every other shape must keep failing
   loudly (CONVENTIONS 1/2 — fail closed, visibly). Apply the same unwrap to `_coerce_answers`
   for the top-level stray-`item` case seen in id 51. **Do not** add `list_type` to
   `TOLERATED_SCHEMA_ERRORS` — that substitutes the field default and silently discards every
   drafted answer (the documented M1 hazard).
2. **Systemic fix (preferred shape).** The artifact is not screening-specific (tailoring's
   `gaps[].evidence_ids` hit the same class). Extract the coercion into **one** shared helper
   and use it for every list-typed field on the wire-adjacent schemas — at minimum
   `ScreeningAnswer.evidence_ids`, `ScreeningDraftResponse.answers`,
   `GapFinding.evidence_ids`, `Suggestion.evidence_ids`; consider
   `RankingResponse.requirements`. One helper, one behaviour.
3. **Do not rely on prompt/schema tightening.** The prompt already demanded a JSON array for
   `evidence_ids` (added by G-07-2) and the wrapper still arrived; opencode's own tool call
   reported `state.status="completed"`, so server-side schema validation is not enforcing the
   nested array type either.
4. **Diagnostic hardening (separate, optional).** Because the app deliberately stores no
   payload (P9), this failure was undiagnosable from `llm_calls` and had to be reconstructed
   from the opencode host's store. Persisting a **privacy-safe shape signature** alongside
   `error` (per-field JSON type names, e.g.
   `{"answers":"array","answers[].evidence_ids":"object/item"}`) would make this class
   self-diagnosing without storing model prose.

### Held-out test needed

- **The literal captured payload** (CONVENTIONS rule 3 — fixture carries the finding's repro),
  routed through the production `_salvage(ScreeningDraftResponse, payload)`: `answers` = the
  4 objects with `evidence_ids` = `{"item":[17 str]}`, `{"item":"exp/self-employed-2026"}`,
  `""`, `{"item":[3 str]}` → asserts `len(answers) == 4` and
  `answers[0].evidence_ids` has 17 entries, `answers[2].evidence_ids] == []`. **This test fails
  on today's code and must fail before the fix.**
- **The fail-loud direction must stay green** (CONVENTIONS rule 7 — asymmetric pressure):
  a scalar `answers`, an unknown key, and an unrecognised shape such as
  `evidence_ids={"nope": 1}` still raise `ValidationError`.
- **Test the class, not the instance** (CONVENTIONS rule 4): a parametrised case for the
  nested wrapper `{"item": {"item": [...]}}`.
- **Route/stage level**: with this payload the stage persists 4 rows and does **not** emit
  `drafting_failed`.
- **Idempotence with the stray top-level key** (id 51's `{'answers','item'}`): after the fix
  the wrapped top-level `item` must be absorbed without weakening `extra="forbid"`.

## What Was NOT Captured

1. **No live reproduction.** It was impossible in this sandbox: the opencode LLM API is not
   reachable as a JSON API (port 4096 on the LAN host serves the opencode SPA shell — every
   path returns HTML 200; `POST /session` → 405), and the app venvs are unusable
   (`pyvenv.cfg` pins `/usr/bin/python3.14`, which does not exist; `.venv/bin/python` is
   system Python 3.11 with no site-packages, so `import app.config` fails on
   `pydantic_settings`). The payload was therefore recovered **after the fact** from the
   opencode host's own store, not by re-running the app's client.
2. **The answer prose and the individual evidence-id strings are not reproduced here** —
   only their types and lengths. (Note for the record: the opencode host DB *does* retain the
   full drafting request/response, i.e. CV-derived prose, despite the app's P9 no-payload
   rule. That is a privacy observation, not a code defect in this gap.)
3. **Not exhaustively verified:** whether the `{"item": …}` wrapper also corrupts other fields
   in the same payloads (only `evidence_ids` was inspected per answer), and id 48's tailoring
   payload was inspected only at top level plus the first element of each list.
4. **Not verified:** whether ids 51/52's payloads *also* contained `{"item": …}` wrappers
   elsewhere (their recorded `list_type` is fully explained by `evidence_ids == ""`, which was
   unhandled at the time).
5. **Not verified:** that no other `llm_calls` caller (ranking, CV extraction) is exposed to
   the same wrapper — the systemic scope in the fix direction is inferred from one tailoring
   sample plus the mechanism, not from a full inventory.
6. **Not verified:** the exact provenance of the wrapper (whether `opencode-go`'s Go
   serialization or minimax-m3's tool-arg emission); the app cannot control it, so the fix is
   placed at the coercion boundary either way.
