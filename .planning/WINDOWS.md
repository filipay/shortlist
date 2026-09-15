---
schema_version: 1
open_count: 2
waived_count: 0
fixed_count: 0
total_count: 2
last_updated: 2026-09-15T17:17:00.804Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 1 | unrun-verify |  |  | Operator-only compose smoke (docker compose up -d --wait && curl -fsS localhost:8000/health) could not run: Docker is absent from the agent sandbox. Deferred to plan 01-07. | open |  | 2026-09-15T17:16:52.438Z |  |
| 2 | 1 | unrun-verify |  |  | Dependency-legitimacy human-check (resolved version set vs the RESEARCH Package Legitimacy Audit; aiosqlite/structlog home-page check; JobSpy resolves to the full SHA) is collected at phase verification per workflow.human_verify_mode=end-of-phase. | open |  | 2026-09-15T17:17:00.804Z |  |

````json
[
  {
    "id": 1,
    "kind": "unrun-verify",
    "phase": "1",
    "file": "",
    "line": null,
    "description": "Operator-only compose smoke (docker compose up -d --wait && curl -fsS localhost:8000/health) could not run: Docker is absent from the agent sandbox. Deferred to plan 01-07.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-15T17:16:52.438Z",
    "resolved_at": null
  },
  {
    "id": 2,
    "kind": "unrun-verify",
    "phase": "1",
    "file": "",
    "line": null,
    "description": "Dependency-legitimacy human-check (resolved version set vs the RESEARCH Package Legitimacy Audit; aiosqlite/structlog home-page check; JobSpy resolves to the full SHA) is collected at phase verification per workflow.human_verify_mode=end-of-phase.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-15T17:17:00.804Z",
    "resolved_at": null
  }
]
````
