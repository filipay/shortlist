---
schema_version: 1
open_count: 2
waived_count: 1
fixed_count: 1
total_count: 4
last_updated: 2026-09-16T14:45:41.388Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 1 | unrun-verify |  |  | Operator-only compose smoke (docker compose up -d --wait && curl -fsS localhost:8000/health) could not run: Docker is absent from the agent sandbox. Deferred to plan 01-07. | fixed |  | 2026-09-15T17:16:52.438Z | 2026-09-16T14:45:41.388Z |
| 2 | 1 | unrun-verify |  |  | Dependency-legitimacy human-check (resolved version set vs the RESEARCH Package Legitimacy Audit; aiosqlite/structlog home-page check; JobSpy resolves to the full SHA) is collected at phase verification per workflow.human_verify_mode=end-of-phase. | open |  | 2026-09-15T17:17:00.804Z |  |
| 3 | 1 | unmet-truth | app/sources/indeed.py |  | Adapter probe() asserts status, minimum body length and stop-signal absence but not a POSITIVE structural marker (3 of the 4 RESEARCH signals) for must-have truth 5; deferred to plan 01-07 because choosing a marker needs a real known-stable page and a guessed one would cause false 'degraded' classifications. Recorded as human_judgment coverage entry D8 in 01-06-SUMMARY.md. | waived | Waived by human decision at phase-01 verification (operator, 2026-09-15): accept the probe's 3-of-4 signal set and waive the missing positive structural marker. The probe asserts HTTP status, minimum body length and stop-signal absence; choosing a marker needs a real known-stable page and a guessed marker would cause FALSE degraded classifications. The recorded survival verdict does not depend on the marker (it derives from runs + source_request_log). Recorded as 2 overrides in 01-VERIFICATION.md; re-open by implementing a marker once a real board page has been observed. | 2026-09-15T18:54:59.352Z | 2026-09-15T22:23:44.053Z |
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
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-15T17:16:52.438Z",
    "resolved_at": "2026-09-16T14:45:41.388Z"
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
    "status": "waived",
    "reason": "Waived by human decision at phase-01 verification (operator, 2026-09-15): accept the probe's 3-of-4 signal set and waive the missing positive structural marker. The probe asserts HTTP status, minimum body length and stop-signal absence; choosing a marker needs a real known-stable page and a guessed marker would cause FALSE degraded classifications. The recorded survival verdict does not depend on the marker (it derives from runs + source_request_log). Recorded as 2 overrides in 01-VERIFICATION.md; re-open by implementing a marker once a real board page has been observed.",
    "recorded_at": "2026-09-15T18:54:59.352Z",
    "resolved_at": "2026-09-15T22:23:44.053Z"
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
