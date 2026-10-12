---
schema_version: 1
open_count: 7
waived_count: 1
fixed_count: 2
total_count: 10
last_updated: 2026-10-12T14:13:30.027Z
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
| 5 | 3 | unrun-verify |  |  | Operator-run live check of one real schema-constrained call from /settings (PLAT-02 success criterion 1) cannot run in the executor sandbox: it needs the user's opencode server with no second provider key configured (03-VALIDATION.md Manual-Only table). The default lane proves the port path with a fake transport; the live call plus confirmation of exactly one llm_calls row (purpose='probe', run_id NULL, no new runs row) remains for the operator. | open |  | 2026-09-17T20:07:07.720Z |  |
| 6 | 3 | unrun-verify | tests/llm/test_contract_live.py |  | Operator-run live /doc contract lane (PLAT-05) is deselected by addopts and cannot run in the executor sandbox. The projection logic was validated during execution against the live 1.18.31 spec (22 pointers, 0 diffs; GET /global/health version 1.18.31 matched the fixture), but the pytest -m live lane itself remains for the operator per docs/runbook-opencode-contract.md. | open |  | 2026-09-17T21:18:10.209Z |  |
| 7 | 3 | unrun-verify | tests/llm/test_trust_boundary.py |  | Operator-run live trust-boundary observation (success criterion 4): with the /settings selftest result page open on a real call, confirm the returned parts carry no tool invocation, the rendered system prompt is the module constant, and info_keys contains the structured payload key (closing Open Question Q1). The default lane proves the deny encoding with a fake transport; the live observation remains for the operator. | open |  | 2026-09-17T23:07:15.009Z |  |
| 8 | 06 | unrun-verify |  |  | Layer-2 checks against a real pypdf extraction of a Tectonic-compiled tailored CV are unrun in the hermetic lane (extraction is stubbed; container latex lane only) | open |  | 2026-09-24T16:55:25.904Z |  |
| 9 | 07 | unrun-verify | .planning/phases/07-assisted-apply-tracker/07-11-SUMMARY.md |  | 07-11 mandated rendered-rect human-check (button/date non-intersection at 1280px+375px) not performed: no layout engine in the repo; deferred to end-of-phase UAT | open |  | 2026-10-12T11:15:19.630Z |  |
| 10 | 07 | deviation | app/domain/schemas/_coerce.py |  | 07-14 Rule 3: Task 2's declared verify command includes the IN-01 TailoringPatch tests that only Task 3's wiring makes green; Task 2's gate was run with -k 'not tailoring_patch' and the full combined gate passed at Task 3 | fixed |  | 2026-10-12T14:13:08.268Z | 2026-10-12T14:13:30.027Z |

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
  },
  {
    "id": 5,
    "kind": "unrun-verify",
    "phase": "3",
    "file": "",
    "line": null,
    "description": "Operator-run live check of one real schema-constrained call from /settings (PLAT-02 success criterion 1) cannot run in the executor sandbox: it needs the user's opencode server with no second provider key configured (03-VALIDATION.md Manual-Only table). The default lane proves the port path with a fake transport; the live call plus confirmation of exactly one llm_calls row (purpose='probe', run_id NULL, no new runs row) remains for the operator.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-17T20:07:07.720Z",
    "resolved_at": null
  },
  {
    "id": 6,
    "kind": "unrun-verify",
    "phase": "3",
    "file": "tests/llm/test_contract_live.py",
    "line": null,
    "description": "Operator-run live /doc contract lane (PLAT-05) is deselected by addopts and cannot run in the executor sandbox. The projection logic was validated during execution against the live 1.18.31 spec (22 pointers, 0 diffs; GET /global/health version 1.18.31 matched the fixture), but the pytest -m live lane itself remains for the operator per docs/runbook-opencode-contract.md.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-17T21:18:10.209Z",
    "resolved_at": null
  },
  {
    "id": 7,
    "kind": "unrun-verify",
    "phase": "3",
    "file": "tests/llm/test_trust_boundary.py",
    "line": null,
    "description": "Operator-run live trust-boundary observation (success criterion 4): with the /settings selftest result page open on a real call, confirm the returned parts carry no tool invocation, the rendered system prompt is the module constant, and info_keys contains the structured payload key (closing Open Question Q1). The default lane proves the deny encoding with a fake transport; the live observation remains for the operator.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-17T23:07:15.009Z",
    "resolved_at": null
  },
  {
    "id": 8,
    "kind": "unrun-verify",
    "phase": "06",
    "file": "",
    "line": null,
    "description": "Layer-2 checks against a real pypdf extraction of a Tectonic-compiled tailored CV are unrun in the hermetic lane (extraction is stubbed; container latex lane only)",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-24T16:55:25.904Z",
    "resolved_at": null
  },
  {
    "id": 9,
    "kind": "unrun-verify",
    "phase": "07",
    "file": ".planning/phases/07-assisted-apply-tracker/07-11-SUMMARY.md",
    "line": null,
    "description": "07-11 mandated rendered-rect human-check (button/date non-intersection at 1280px+375px) not performed: no layout engine in the repo; deferred to end-of-phase UAT",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-10-12T11:15:19.630Z",
    "resolved_at": null
  },
  {
    "id": 10,
    "kind": "deviation",
    "phase": "07",
    "file": "app/domain/schemas/_coerce.py",
    "line": null,
    "description": "07-14 Rule 3: Task 2's declared verify command includes the IN-01 TailoringPatch tests that only Task 3's wiring makes green; Task 2's gate was run with -k 'not tailoring_patch' and the full combined gate passed at Task 3",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-10-12T14:13:08.268Z",
    "resolved_at": "2026-10-12T14:13:30.027Z"
  }
]
````
