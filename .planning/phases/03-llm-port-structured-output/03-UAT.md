---
status: testing
phase: 03-llm-port-structured-output
source: [03-VERIFICATION.md]
started: 2026-09-18T11:07:39Z
updated: 2026-09-18T11:22:10Z
---

## Current Test

number: 1
name: Live schema-constrained call from /settings
expected: |
  With `opencode serve` running, pressing "Test LLM backend" on /settings returns a
  schema-validated structured result, and exactly one `llm_calls` row is written
  (`run_id IS NULL`) with no `runs` row. No second provider key is configured.
awaiting: user response

## Tests

### 1. Live schema-constrained call from /settings
expected: Start `opencode serve`, press "Test LLM backend" on /settings; observe a validated structured result and exactly one `llm_calls` row (`run_id IS NULL`) with no `runs` row, using only the opencode backend (no second provider key).
result: [pending]

### 2. Operator live /doc drift lane
expected: `pytest -q -m live tests/llm/test_contract_live.py` reports 0 divergent pointers and `_meta.server_version` matching `GET /global/health`.
result: [x] passed — 2026-09-18, against `opencode serve` 1.18.31 via
  `OPENCODE_BASE_URL=http://127.0.0.1:4096 .venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py`
  → `1 passed in 0.11s` (exit 0), 0 divergent pointers, committed `_meta.server_version` 1.18.31 == `/global/health`.
  First run failed unconditionally on `permission_action_enum` (committed `{allow,ask,deny}` vs live `set()`):
  the live `PermissionRule.action` is a `$ref` to `PermissionAction`, which the projection helper did not follow.
  Fixed in commit `e63e901` by adding a cycle-safe `_resolve()` and reading all four projected enums through it;
  `tests/llm/test_contract_snapshot.py` 13 passed (unchanged), full default suite 834 passed / 3 deselected,
  ruff clean. The guard keeps its teeth (renamed target → `{}` → drift).
  NOTE: the host interpreter is `.venv-host/bin/python` (glibc); the container is `.venv/bin/python` (musl).
  The previous run used the container musl venv from the host, which fails to import `pydantic_core._pydantic_core`.
  Both the runbook and the live module docstring have been corrected.

### 3. Live trust-boundary observation
expected: A live returned response carries no tool invocation, the system prompt is the constant one (listing text is never in it), and `info_keys` contains `structured`.
result: [pending]

### 4. Close Open Question Q1 live
expected: The pinned `format` / `info.structured` structured-output fields are accepted by the installed server (the `format` vs `outputFormat` ambiguity is confirmed resolved against the real server).
result: [pending]

## Summary

total: 4
passed: 1
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

<!-- Populated by /gsd-verify-work if a test reports an issue. -->
