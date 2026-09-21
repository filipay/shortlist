# Runbook — the opencode structured-output contract (PLAT-05)

Phase 3 success criterion 3: *"the structured-output contract is covered by a
test that fails loudly when opencode's API changes."*

The repo has **no CI runner** by design (D-53), so a live-only test would never
fire on an upgrade. The mechanism is therefore a **committed snapshot slice**
plus this deliberate operator procedure:

```
builder == snapshot    tests/llm/test_contract_snapshot.py   (default lane, no server)
snapshot == live spec  tests/llm/test_contract_live.py       (this runbook, operator)
the real call works    POST /settings/llm-test               (plan 03-01's selftest)
```

The live lane does **spec fetch + diff only** — it never makes a model call
(D-57): one `GET /doc` plus one `GET /global/health`, and it asserts no `POST`
occurred.

## Prerequisites

- **The interpreter must match the platform you run on.** A venv built inside a
  musl container cannot load its native extensions on a glibc host
  (`ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`). Run the
  live lane **on the host** with the host venv `.venv-host/bin/python`; run it
  **inside the container** with the container venv `.venv/bin/python`. See
  `docs/probes/README.md` — "the interpreter must match the host platform".
- **`opencode serve` must be running and reachable from where you run the test.**
  The live lane runs **on the host**, so the server's default
  `--hostname 127.0.0.1` is fine for this test. (The *container* reaches it via
  `host.docker.internal`, which only works if you launched
  `opencode serve --hostname 0.0.0.0`.) A bare "connection refused" here usually
  means the server bound to `127.0.0.1` and you are testing from somewhere that
  is not the host — it is **not** evidence that the contract drifted.

## Procedure

1. **Confirm the default lane is green.** The snapshot test must pass before any
   live run, so a live failure is unambiguously server drift:

   ```bash
   .venv-host/bin/python -m pytest -q      # on the host
   # .venv/bin/python -m pytest -q         # inside the container
   ```

2. **Export the host environment.** Run the live lane on the **host** with the
   loopback base URL; the in-container value is the *container's* view of the
   host and will not resolve from the host:

   ```bash
   export OPENCODE_BASE_URL=http://127.0.0.1:4096
   # only if your server sets a password:
   # export OPENCODE_SERVER_PASSWORD=...
   ```

3. **Run the live lane.** It prints nothing on success and names the divergent
   pointers on drift:

   ```bash
   .venv-host/bin/python -m pytest -q -m live tests/llm/test_contract_live.py   # on the host
   # .venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py      # inside the container
   ```

   A pass also asserts the committed `_meta.server_version` matches the running
   server's `GET /global/health` version — an upgrade that changes only the
   version still fails here, deliberately.

4. **If it reports drift, confirm the drift is real — then refresh deliberately.**
   Read the printed pointer and compare it against the live spec
   (`curl -s "$OPENCODE_BASE_URL/doc" | python3 -m json.tool` at that pointer).
   Decide whether it is a genuine rename of the structured-output surface or
   unrelated churn. Then, and only then:

   - edit `tests/llm/fixtures/opencode-doc.json` to the **observed** server facts;
   - record the new `GET /global/health` version in `_meta.server_version`;
   - re-run step 1 and step 3.

   **Never edit the slice to match a guess.** Refreshing the fixture is a
   deliberate, reviewed act; an automatic re-dump would destroy the guard it
   exists to be (D-53/T-3-13).

## Why the response field is `structured`

The live opencode 1.18.31 spec exposes the validated payload as
`AssistantMessage.structured`. The published docs and older notes spell it
`structured_output`, and the SDK sample shows `structured_output` — but that
spelling occurs **zero times** in the 478,968-byte live spec, and reading it
yields `None` on every successful call. `app/llm/contract.py` pins
`STRUCTURED_RESPONSE_PATH = ("info", "structured")` for exactly that reason.

Do **not** "correct" the constant back to the docs' spelling, and do not add an
adaptive client that accepts either name: absorbing a rename silently is the
failure mode this whole runbook exists to prevent (D-54).

## Choosing a model that can satisfy a forced tool call

A schema-constrained call is not a plain chat completion. opencode implements
`format` structured output through a tool it injects into the session, and it sets
the tool choice to **`required`** on every such call. The configured model must
therefore accept a forced tool call; a model that refuses one makes every
schema-constrained call fail at the provider, with an error that does not obviously
name the model as the cause.

The previously shipped default, `deepseek-v4.1-flash`, is one such model. Against a
running 1.18.31 server it is rejected upstream with:

```
HTTP 400 invalid_request_error: Thinking mode does not support this tool_choice
```

The rejection is independent of the agent, the variant and the permission shape, and
the provider's whole model set is reasoning-capable — so "choose a non-reasoning
model" is not an available mitigation. The remedy is to select a model that honours
the forced tool call and confirm it: `minimax-m3` is the evidenced-capable shipped
default, and the `/settings` **Test LLM backend** button runs exactly the
schema-constrained call that exercises this requirement.

`format.retryCount` cannot rescue an incapable model. In 1.18.31 the field is
accepted on the wire but unused — the server's own retry counter is effectively
hardcoded to zero — so a provider-side `tool_choice` rejection is returned on the
first attempt with `retries: 0` and no `structured` key, however high the configured
retry count is.

`app/config.py` records the known-incompatible model in
`KNOWN_FORCED_TOOL_CHOICE_INCOMPATIBLE_MODELS`, and `tests/test_config.py` guards the
shipped default against it.

## Recording the evidence

Paste the live lane's output into the phase verification notes and keep:

- the exact command and the exit status;
- the observed `GET /global/health` version;
- on drift, the divergent pointers verbatim and the refreshed `_meta` values.

The docs gate in `03-VALIDATION.md` requires the committed
`_meta.server_version` to match what the live lane observed.
