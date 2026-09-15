---
schema_version: 1
open_count: 4
waived_count: 0
fixed_count: 0
total_count: 4
last_updated: 2026-09-15T21:05:27.728Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 1 | unrun-verify |  |  | Operator-only compose smoke (docker compose up -d --wait && curl -fsS localhost:8000/health) could not run: Docker is absent from the agent sandbox. Deferred to plan 01-07. | open |  | 2026-09-15T17:16:52.438Z |  |
| 2 | 1 | unrun-verify |  |  | Dependency-legitimacy human-check (resolved version set vs the RESEARCH Package Legitimacy Audit; aiosqlite/structlog home-page check; JobSpy resolves to the full SHA) is collected at phase verification per workflow.human_verify_mode=end-of-phase. | open |  | 2026-09-15T17:17:00.804Z |  |
| 3 | 1 | unmet-truth | app/sources/indeed.py |  | Adapter probe() asserts status, minimum body length and stop-signal absence but not a POSITIVE structural marker (3 of the 4 RESEARCH signals) for must-have truth 5; deferred to plan 01-07 because choosing a marker needs a real known-stable page and a guessed one would cause false 'degraded' classifications. Recorded as human_judgment coverage entry D8 in 01-06-SUMMARY.md. | open |  | 2026-09-15T18:54:59.352Z |  |
| 4 | 1 | unmet-truth | app/api/health.py |  | probe() is not a reliable proxy for fetch(): in the same container session the /health probe reported indeed=unreachable and linkedin=degraded at 21:02:36 while runs.id=1 had just fetched 50 usable listings from EACH board at 21:02:01 (100 distinct content_hash, 0 blank titles). The survival verdict is unaffected (it derives from runs + source_request_log), but /health's per-source liveness badge can mislead, and promotion condition P-4 is unusable until resolved. Candidate human-verification item: is the fixed probe URL/classification wrong, was the difference a transient board challenge, or should the probe be re-pointed at the ingest path? Same family as entry #3. See docs/probes/2026-09-15-scraper-survival.md section 7. | open |  | 2026-09-15T21:05:27.728Z |  |

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
  },
  {
    "id": 3,
    "kind": "unmet-truth",
    "phase": "1",
    "file": "app/sources/indeed.py",
    "line": null,
    "description": "Adapter probe() asserts status, minimum body length and stop-signal absence but not a POSITIVE structural marker (3 of the 4 RESEARCH signals) for must-have truth 5; deferred to plan 01-07 because choosing a marker needs a real known-stable page and a guessed one would cause false 'degraded' classifications. Recorded as human_judgment coverage entry D8 in 01-06-SUMMARY.md.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-15T18:54:59.352Z",
    "resolved_at": null
  },
  {
    "id": 4,
    "kind": "unmet-truth",
    "phase": "1",
    "file": "app/api/health.py",
    "line": null,
    "description": "probe() is not a reliable proxy for fetch(): in the same container session the /health probe reported indeed=unreachable and linkedin=degraded at 21:02:36 while runs.id=1 had just fetched 50 usable listings from EACH board at 21:02:01 (100 distinct content_hash, 0 blank titles). The survival verdict is unaffected (it derives from runs + source_request_log), but /health's per-source liveness badge can mislead, and promotion condition P-4 is unusable until resolved. Candidate human-verification item: is the fixed probe URL/classification wrong, was the difference a transient board challenge, or should the probe be re-pointed at the ingest path? Same family as entry #3. See docs/probes/2026-09-15-scraper-survival.md section 7.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-15T21:05:27.728Z",
    "resolved_at": null
  }
]
````
