---
phase: 03-llm-port-structured-output
reviewed: 2026-09-21T12:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - app/config.py
  - app/llm/contract.py
  - app/llm/opencode_server.py
  - app/web/templates/html/settings.html
  - compose.yml
  - .env.example
  - docs/runbook-opencode-contract.md
  - tests/llm/test_complete_structured.py
  - tests/llm/test_contract_live.py
  - tests/llm/test_discovery_redaction.py
  - tests/llm/test_live_structured_call.py
  - tests/llm/test_trust_boundary.py
  - tests/test_config.py
findings:
  critical: 0
  warning: 3
  info: 5
  total: 8
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-09-21T12:00:00Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Reviewed the plan 03-10 blocker-closure set: the order-enforced session `permission`
ruleset with its `StructuredOutput` carve-out, the move of the shipped `opencode_model`
default to `minimax-m3`, the differential structured-failure cause on the persisted
`llm_calls.error`, and the operator live lane. The core of the change is sound and,
unusually, the ordering claim is backed by a test with real teeth rather than a comment:

- **The deny/carve-out precedence is genuine last-match-wins.** I re-ran the evaluator
  against the shipped tuple and a reordered one (`default → True`, `reordered → False`,
  `bash → False`), then ran a first-match evaluator against the shipped tuple
  (`default → False`). The shipped ruleset and a reordered one are therefore
  distinguishable, so `test_the_carve_out_must_follow_the_catch_all_deny` would fail on a
  first-match/reorder regression instead of passing vacuously.
- **The evaluator agrees with the emitted ruleset shape.** `ruleset_allows_tool` matches
  on `permission ∈ {*, tool_name}` AND `pattern == *`, which is exactly the shape
  `DEFAULT_DENY_RULES` emits; `to_session_body` copies each rule verbatim, preserving
  order. The carve-out grants only the server-internal tool name; every user-facing tool
  (`bash`/`read`/`write`) evaluates to denied.
- **The model default is consistent across all three operator surfaces** and the
  incompatibility guard is non-vacuous: `app/config.py:57` (`minimax-m3`),
  `compose.yml:19` (`${OPENCODE_MODEL:-minimax-m3}`), `.env.example:15`
  (`OPENCODE_MODEL=minimax-m3`), with `test_the_compose_model_default_agrees_with_the_declared_one`
  deriving the expected spelling from the declared default rather than hard-coding it.
- **The persisted error clause does not leak a credential.** `_structured_tool_note`
  returns fixed literals naming only the contract constants
  (`StructuredOutput`, `tool`); the discovery credential never enters this path, and
  `raw` stays `None` on every failure branch. (The pre-existing unbounded server-message
  feed is noted as IN-02, below.)
- **Test honesty holds.** Full default suite: **843 passed, 4 deselected** (matches the
  plan summary). `pytest --collect-only` on the two live modules reports `2 deselected`
  with the default `addopts = "-m 'not live'"`, and `-m live` collects both — the live
  lanes cannot reach the default gate. I could not execute the live lanes here (no
  `opencode serve` reachable); their pass status is taken from the plan summary, not
  re-verified.

No Critical/Blocker was found. The three Warnings below are the actionable defects: two
are pre-existing adapter attribution/taxonomy gaps that this plan did not touch (and that
the prior review at this path also raised), and one is a new diagnostic-accuracy risk in
the differential added by 03-10.

## Warnings

### WR-01: failures outside the retry loop discard the resolved D-12 identity and report `attempts=0`

**File:** `app/llm/opencode_server.py:560-587` (outer handlers), `:360-397` (`_create_session`)

**Issue:** `_resolve_model` succeeds first, so `provider_id`/`model_id` are known
(`:442-445`). `_create_session` then runs *outside* the per-attempt loop, and a
transport/timeout failure there escapes the loop to one of the outer handlers
(`:560-587`), all of which hard-code `attempts=0` and pass no `provider`/`model`/`agent`.
The non-200 session branch (`:379-385`) has the same gap. Reproduced in-process against a
stubbed transport:

```
session-create transport failure -> error unreachable attempts= 0 provider= None model= None
```

The message-send path is correctly attributed by the loop; the session handshake is not.
Consequence: the `llm_calls` audit row understates the attempt count and NULLs the
`provider`/`model` columns whose existence is the stated reason migration 0003 (D-12) was
written, even though both values were resolved moments earlier. No test exercises a
session-create transport failure, so the gap is invisible to the suite. Carried over from
the prior review at this path (its WR-01/IN-04), still unfixed.

**Fix:** capture the resolved identity before the completion client and thread it into
every outer `_failure(...)` (and the non-200 session return), e.g.
`attempts=issued, provider=provider_id, model=model_id, agent=agent`; add a test that fails
`_create_session` with `httpx.ConnectError` and asserts `attempts == 1` plus the resolved
identity survive.

### WR-02: the generic handler emits a raw exception class name as `error_kind`, outside the D-52 taxonomy

**File:** `app/llm/opencode_server.py:580-587` (`error_kind=type(exc).__name__` at `:583`)

**Issue:** `_failure`'s contract is that `status` stays one of the four legal
`llm_calls.status` values while `error_kind` carries the *specific cause* from the
documented namespace (`unreachable`, `timeout`, `invalid`, `model_not_found`,
`invalid_session`, `http_<code>`). The generic handler writes the implementation class
name directly. Demonstrated by passing the builder's forbidden wildcard:

```
tools=("*",) -> error ValueError attempts= 0 err= ValueError: the deprecated 'tools' map ...
```

Any operator/UI logic switching on the D-52 taxonomy cannot classify `ValueError`,
`JSONDecodeError`, or `TypeError`. The same taxonomy leak exists in the "other provider
error envelope" branch (`:886-896`), which persists the provider's raw `info.error.name`
as `error_kind`. Fail-closed (still a value), but it degrades the observability contract
this phase is built on. Carried over from the prior review (its WR-02). `attempts` also
drops to 0 here (same root as WR-01).

**Fix:** map unexpected exceptions to a stable label (e.g. `error_kind="internal_error"`,
keeping the class name in `error` only), and preserve `attempts`/identity as in WR-01.

### WR-03: the differential cause can assert a model refusal when the response only proves a missing tool part

**File:** `app/llm/opencode_server.py:727-752` (`_structured_tool_note`), `:819-822` (call site)

**Issue:** `_structured_tool_note` returns the model/provider cause
("…the model or provider did not honour the forced tool call…") whenever the grant is
present and no `tool` part was observed. That conflates two distinct failures: a model
that genuinely declined the forced call, and a schema-retry exhaustion where the server
returned `StructuredOutputError` with a parts list that happens not to contain a tool part.
The repository's own `_structured_error_body` fixture models the schema-failure case as
`parts: []` (`tests/llm/test_complete_structured.py:460-479`), so `parts == []` is a
plausible real shape — and under it the persisted `llm_calls.error` would tell the operator
to "check that the configured model accepts a required tool choice" when the model did call
the tool and the failure was schema validation. This directly targets the feature's
purpose (D3: make a structured failure name its cause). Separately, the branch order
returns the ruleset cause even when a `tool` part *is* present (`granted=False,
part_types=["tool"]` → "the tool was never available"), which contradicts the observation.
The exact server-side `parts` shape on a schema failure is not settled by the live lane
(which only asserts the success shape), so this cannot be fully confirmed without a live
failure capture — flagged rather than asserted.

**Fix:** only attach the model/provider clause when the observation positively excludes the
tool having run, e.g. treat `part_types in (None, [])` as "no parts observed" and return
`None`, and check `PART_TYPE_TOOL in part_types` before the `not granted` branch (or reword
the ruleset cause to "the session ruleset as evaluated does not grant …"). Capture a real
`StructuredOutputError` response in the live lane to settle the `[]`-vs-tool-part question.

## Info

### IN-01: `tools: Sequence[str]` accepts a bare `str` and expands it per character

**File:** `app/llm/opencode_server.py:472` (`tool_grant = {name: True for name in tools} if tools else None`)

**Issue:** A single `str` satisfies `Sequence[str]`, so `tools="read"` yields
`{"r": True, "e": True, "a": True, "d": True}` — a silent nonsense grant, no diagnostic
(confirmed in-process). The session `permission` deny backstops today, so it fails safe,
but a future caller passing one name gets an unexpected message-level grant. Pre-existing.

**Fix:** reject a bare `str` explicitly (`if isinstance(tools, str): raise TypeError(...)`)
or annotate the port to require a list/tuple.

### IN-02: unbounded server-derived text is persisted into `llm_calls.error`

**File:** `app/llm/opencode_server.py:860-872` (`StructuredOutputError` message), `:779-792` (bounded excerpt)

**Issue:** The non-200 body excerpt *is* bounded (`NON_200_BODY_EXCERPT_CHARS = 200`), but
the `StructuredOutputError` `data.message` (`:868-871`) and the raise-path text in
`app/api/settings.py:430` are persisted to the unbounded `Text` column and rendered. Today
every writer is a canned selftest body or a library exception, so the exposure is
theoretical; once Phase 5 routes CV/listing content through this port, a server/proxy error
message could persist personal data into a column `tests/db/test_no_pii_columns.py` does not
treat as PII. Pre-existing (prior review IN-04); 03-10's clause itself is fixed-literal and
does not widen it.

**Fix:** before the LLM path carries real content, cap and redact every persisted `error`
(excerpt + exception class only) and document the decision where
`NON_200_BODY_EXCERPT_CHARS` lives.

### IN-03: `settings.html` says the Cause line always names which side is at fault

**File:** `app/web/templates/html/settings.html:71-73`

**Issue:** "When a structured call fails, the Cause line above names which side is at
fault: a ruleset that stripped the internal tool, or a model that declined the forced tool
call." The persisted cause only carries a side-clause when `_structured_tool_note` returns
one (it returns `None` when no parts were observed, and when the server's other error
envelopes are returned). The copy over-claims.

**Fix:** soften to "when the response shape allows, the Cause line names which side is at
fault".

### IN-04: a default-assertion test reads `Settings()` instead of the declared default

**File:** `tests/llm/test_complete_structured.py:873-877`

**Issue:** `test_the_new_phase_three_ceilings_are_settings_fields` asserts
`Settings().opencode_completion_timeout_seconds == 120.0` etc. Because `Settings` reads
`.env` and ambient env vars, this flakes under an override; the file's neighbour and
`tests/test_config.py:test_documented_defaults` deliberately use
`Settings.model_fields[name].default` for exactly this reason. The repo's own `.env` only
sets `DEDUP_FUZZY_THRESHOLD`, so it passes today — but it is an inconsistent, avoidable
coupling.

**Fix:** assert against `Settings.model_fields["opencode_completion_timeout_seconds"].default`
(and the two siblings), matching the documented convention.

### IN-05: stale model example in the `_resolve_model` docstring

**File:** `app/llm/opencode_server.py:325`

**Issue:** The docstring still uses ``deepseek-v4.1-flash`` as the example bare model id
for `OPENCODE_MODEL`, now the documented *incompatible* model. Reads as if it were the
default.

**Fix:** use `minimax-m3` (or a generic `example-model`) in the example.

## Verified clean (selected focus areas)

- **Order-dependent security logic:** `ruleset_allows_tool` evaluates rules in order and
  returns the LAST matching rule's action; it deliberately avoids `any()`/first-match/
  presence-only semantics. Behaviour verified: shipped `→ True`, reordered `→ False`,
  unmentioned/user-facing names `→ False`. The carve-out is scoped to the single
  server-internal tool name and cannot grant a user-facing tool. `to_session_body` copies
  rules verbatim in order, so the enforced request matches the evaluated tuple.
- **Model-default propagation:** `app/config.py:57`, `compose.yml:19` and `.env.example:15`
  are `minimax-m3`; the compose/.env agreement test derives the expected value from the
  declared default, so any single-surface drift fails. The incompatibility guard
  (`KNOWN_FORCED_TOOL_CHOICE_INCOMPATIBLE_MODELS`) is non-empty and the declared default is
  not a member; no other source surface bakes in the old default (Dockerfile/entrypoint
  carry no `OPENCODE` references).
- **Error-path legibility / leakage:** the new clause is assembled from fixed module-level
  literals plus contract constants only, appended with `"; "`; no part text, payload value,
  or credential reaches it. The template autoescapes. `raw` remains `None` on every failure
  branch, and the sentinel tests in `test_complete_structured.py`/`test_trust_boundary.py`
  cover the no-leak property.
- **Test honesty:** the reordering guard fails under a first-match evaluator (proved);
  `test_the_default_deny_ruleset_stays_fail_closed_with_one_carve_out` pins the catch-all
  as rule 0 and enforces a single allow rule; the config guards derive rather than
  hard-code; the two `pytestmark = pytest.mark.live` modules are deselected by the default
  `addopts` and collected only with `-m live`.
- **Live lane (not executed here):** `tests/llm/test_live_structured_call.py` overrides
  `get_llm_backend` with the callable backend class (correct for FastAPI DI), asserts
  reachability before the route, asserts exactly one `probe` row with `run_id IS NULL` and
  zero `runs` rows. Pass status is per the plan summary; no `opencode serve` was reachable
  in this review environment, so it is not independently verified.

---

_Reviewed: 2026-09-21T12:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
