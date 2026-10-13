# Deferred Items — Phase 07.1

Out-of-scope discoveries logged during execution (not fixed; scope boundary).

| Item | File | Found during | Why out of scope |
|------|------|--------------|------------------|
| Pre-existing `ruff` F401: `INFO_PATH` imported but unused | `app/llm/opencode_server.py:63` | 07.1-04 Task 1 | Present at `HEAD` (682f06d) before this plan's edits, unrelated to the discovery retarget. The repo enforces no pre-commit hook; left untouched per the scope-boundary rule. One-line fix when an owner next touches the import block. |
