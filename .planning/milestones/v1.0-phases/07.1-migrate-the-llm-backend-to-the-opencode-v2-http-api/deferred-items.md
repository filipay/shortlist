# Deferred Items — Phase 07.1

Out-of-scope discoveries logged during execution (not fixed; scope boundary).

## 07.1-04 Task 1

- **Pre-existing `ruff` F401: `INFO_PATH` imported but unused** (`app/llm/opencode_server.py:63`) — Present at `HEAD` (682f06d) before this plan's edits, unrelated to the discovery retarget. The repo enforces no pre-commit hook; left untouched per the scope-boundary rule. One-line fix when an owner next touches the import block.
  status: acknowledged

## 07.1-05 Task 1

- **Committed V2 slice is not a byte-accurate projection: `paths["/api/session"].post.request_body_properties` omits `id`, and `components.schemas["Model.Ref"].properties` omits the optional `variant`** (`tests/llm/fixtures/opencode-doc.json`) — The fixture is owned by plan 07.1-03 (hand-written slice) and is outside this plan's `files_modified` scope. Harmless under the operator lane's committed-subset diff (a committed fact is honoured when its members are present in the live spec), but the slice carries fewer members than the live 2.0.26 `/openapi.json`. Fix by refreshing the slice deliberately via `docs/runbook-opencode-contract.md` if a byte-accurate pin is wanted.
  status: acknowledged
