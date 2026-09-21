---
gsd_state_version: "1.0"
current_phase: 4
current_phase_name: CV Fact Store + LaTeX Compile Spike
status: planning
stopped_at: Phase 03 complete, ready to plan Phase 4
last_updated: "2026-09-21T11:09:11.122Z"
last_activity: 2026-09-21
last_activity_desc: Phase 03 complete, transitioned to Phase 4
state_head: 54ba87791ed14ebc58859ae83a7f211287cd8259
progress:
  total_phases: 8
  completed_phases: 1
  total_plans: 28
  completed_plans: 28
  percent: 13
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-15)

**Core value:** Every morning there is one ranked, explained, apply-ready queue of jobs worth considering — so the search→judge→tailor loop costs minutes instead of hours.
**Current focus:** Phase 03 — LLM Port + Structured Output

## Current Position

Phase: 4 — CV Fact Store + LaTeX Compile Spike
Plan: Not started
Status: Ready to plan
Last activity: 2026-09-21 — Phase 03 complete, transitioned to Phase 4

Progress: [█░░░░░░░░░] 13%

## Performance Metrics

**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 23 min | 3 tasks | 40 files |
| Phase 01 P02 | 5 min | 2 tasks | 3 files |
| Phase 01 P03 | 15 min | 3 tasks | 34 files |
| Phase 01 P04 | 8min | 2 tasks | 12 files |
| Phase 01 P05 | 22 min | 2 tasks | 11 files |
| Phase 01 P06 | 22 min | 3 tasks | 20 files |
| Phase 01 P07 | 22 min | 3 tasks | 35 files |
| Phase 02 P01 | 8 min | 3 tasks | 8 files |
| Phase 02 P02 | 4 min | 2 tasks | 3 files |
| Phase 02 P03 | 15 min | 3 tasks | 6 files |
| Phase 02 P04 | 15 min | 2 tasks | 7 files |
| Phase 02 P05 | 22 min | 3 tasks | 10 files |
| Phase 02 P06 | 15 min | 2 tasks | 5 files |
| Phase 02 P07 | 22 min | 3 tasks | 13 files |
| Phase 02 P08 | 32 min | 3 tasks | 10 files |
| Phase 02 P09 | 20 min | 2 tasks | 8 files |
| Phase 02 P10 | 17 min | 2 tasks | 7 files |
| Phase 02 P11 | 212 min | 8 tasks | 21 files |
| Phase 03 P01 | 21 min | 3 tasks | 18 files |
| Phase 03 P02 | 8 min | 2 tasks | 4 files |
| Phase 03 P03 | 9 min | 2 tasks | 3 files |
| Phase 03 P04 | 8 min | 3 tasks | 7 files |
| Phase 03 P05 | 5 min | 2 tasks | 3 files |
| Phase 03 P06 | 13 min | 3 tasks | 10 files |
| Phase 03 P07 | 10 min | 3 tasks | 8 files |
| Phase 03 P08 | 5 min | 3 tasks | 5 files |
| Phase 03 P09 | 13 min | 3 tasks | 6 files |
| Phase 03 P10 | 13 min | 3 tasks | 12 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Ranking (Phase 5) precedes tailoring (Phase 6) — tailoring consumes the requirement gaps ranking produces.
- [Roadmap]: Phase 4 (CV fact store + LaTeX spike) runs **in parallel** with Phases 2–3; it is a shared prerequisite and the largest unquantified cost.
- [Roadmap]: Scheduling is late (Phase 8) on purpose — a cron job over an unstable pipeline hides failures.
- Phases 01 and 02 decisions are archived in their phase SUMMARYs (`.planning/phases/01-*/01-*-SUMMARY.md`, `02-*`); this section now tracks Phase 03 only.
- [Phase 03]: 03-01: pin the opencode structured-output wire vocabulary in one no-I/O module (app/llm/contract.py); the request field is format and the live response field is info.structured, with no adaptive fallback (D-54/D-56).
- [Phase 03]: 03-01: parse_providers accepts the live dict shape AND the legacy list shape; OPENCODE_MODEL resolves through discovery and fails loud on a miss instead of silently omitting model.
- [Phase 03]: 03-01: the selftest is a plain full-page POST that writes exactly one llm_calls row (purpose='probe', run_id NULL) and no runs row; server_version is carried on the returned record but not persisted until migration 0003 (plan 03-04).
- [Phase 03]: 03-02: the /doc contract slice is indexed by MESSAGE_DOC_PATH (the OpenAPI path-template spelling) and never by MESSAGE_PATH; both constants are asserted present and distinct so a rename fails loudly rather than raising a bare KeyError.
- [Phase 03]: 03-02: the live lane diffs 22 named facts set-by-set and asserts the committed _meta.server_version matches GET /global/health, so a version-only upgrade still fails; it performs no model call (D-57) and a request hook asserts no POST occurred.
- [Phase 03]: 03-03: status stays inside the four legal llm_calls.status values; the operator cause lives in error_kind (unreachable/timeout/invalid/http_<code>/parse-exception), and ConnectTimeout is unreachable while ReadTimeout is timeout.
- [Phase 03]: 03-03: the client retry loop is bounded by the caller's retries argument (Settings supplies the default) and never retries a schema failure; attempts is the server's info.error.data.retries when supplied, else the issued-request count.
- [Phase 03]: 03-03: TOLERATED_SCHEMA_ERRORS is an explicit frozenset allow-list and _salvage is wired into complete_structured; the WrapValidator substitutes defaults by removing the offending field, so a default-less field re-raises instead of leaking a PydanticUseDefault marker (P11).
- [Phase 03]: 03-04: Task 1's one-way-door gate resolved to migration-0003 — a dedicated nullable llm_calls.server_version VARCHAR(32) (migration 0003), because backend/provider/error each have distinct meanings another surface relies on and error is NULL on the successful rows where the version matters most.
- [Phase 03]: 03-04: llm_call_repo.latest_probe and llm_totals_for_run are the shared reads (total over half-written rows, never commit); _settings_context reads through latest_probe, so D-52's detail has one read shape and server_version now survives a reload.
- [Phase 03]: 03-04: the migration + ORM mirror land together so test_orm_drift enforces the pair; four revision assertions (three in test_migration_contract, one in test_skeleton_boot) moved deliberately to 0003, and no JSON column was added so test_no_pii_columns is untouched.
- [Phase 03]: 03-05: the three Phase-3 opencode ceilings are asserted by the config guard and proven env-tunable; the completion timeout stays a separate Settings field from opencode_timeout_seconds (P4) and the LIMIT_FIELDS comment records why they must not be merged.
- [Phase 03]: 03-05: compose.yml forwards all four opencode keys with ${VAR:-default} defaults matching app/config.py exactly — the three new ceilings plus the previously unforwarded OPENCODE_TIMEOUT_SECONDS — and .env.example documents each, so a host .env override is no longer silently defeated.
- [Phase 03]: 03-05: probe_cache_ttl_seconds was a ceiling LIMIT_FIELDS covered but REQUIRED_SETTINGS_FIELDS omitted; it is now required, so every LIMIT_FIELDS entry is a required numeric ceiling.
- [Phase 03]: 03-06: tools are denied by default through the session-level permission ruleset (DEFAULT_DENY_RULES), not the deprecated message-level tools map; the message body sends no tools key by default and a wildcard '*' key raises ValueError naming the permission control.
- [Phase 03]: 03-06: the session model shape {id: modelID, providerID} is the deliberate inverse of the message shape {providerID, modelID}; both key order and values are asserted together because a wrong placement is a silent 400.
- [Phase 03]: 03-06: the deny is observed, not asserted — StructuredCallResult.part_types/info_keys carry part TYPE names and info KEY names only (logged and rendered on /settings, transient), and a scoped import guard enforces §6.5 with a proven app/sources exclusion.
- [Phase 03]: 03-07: instruction-like text is recorded as a counts-only finding (instruction_like bool + patterns_matched int) on listings.quality_signals_json; a clean listing passes None so the column stays NULL and a recorded signal is never clobbered, and no redaction step was added.
- [Phase 03]: 03-07: the queue row ships a conditional 'flagged' badge with its own .badge-flagged CSS rule — the plan's condition held (the three queue tests assert badges additively), so the guard was satisfied rather than weakened.
- [Phase 03]: 03-07: _finish gains llm_calls/llm_tokens, assigned only when supplied and never touching ranked_count; Phase 3 wires no caller so D-49 holds and run_pipeline still writes zero llm_calls rows.
- [Phase 03]: 03-08: both the port and the adapter declare `retries: int | None = None`, so the documented `settings.opencode_max_retries` fallback is the live default path (PLAT-04); a test patches the setting to 7 and observes 7 POSTs.
- [Phase 03]: 03-08: the port keeps `tools: Sequence[str] = ()` (03-CONTEXT locked) and the adapter converts a non-empty sequence to the builder's `{name: True}` map; an empty sequence stays None so the fail-closed default emits no message-level tools key.
- [Phase 03]: 03-08: the `except ValueError` parse-failure branch sits AFTER `except ValidationError` because ValidationError subclasses ValueError; a non-JSON info.structured becomes `invalid` with provider/model/agent and part_types/info_keys preserved.
- [Phase 03]: D-55 widened deliberately: the committed /doc slice now also pins the session deny-rule field names and the deny action, because the permission ruleset is the ENFORCED tool control; _meta.note records the widening
- [Phase 03]: The live projection follows the session permission array items.$ref (with a one-level wrapper follow and a PermissionRule-name fallback) so a renamed rule reports drift instead of resolving to an empty schema
- [Phase 03]: The raise branch records the attempt BEFORE replying and returns 500 (the reset route convention for an unexpected internal failure), rather than lying with a 200
- [Phase 03]: 03-10: DEFAULT_DENY_RULES is order-enforced — the catch-all deny stays first and the single StructuredOutput carve-out follows it, with a last-match-wins ruleset_allows_tool so reordering fails a default-lane test
- [Phase 03]: 03-10: opencode_model default moves to minimax-m3 with KNOWN_FORCED_TOOL_CHOICE_INCOMPATIBLE_MODELS guarding the shipped default; no validator rejects a configured model because an operator stays free to set any model
- [Phase 03]: 03-10: the structured-output differential travels on the persisted StructuredCallResult.error (llm_calls.error), so it survives a reload with no new field and no migration
- [Phase 03]: 03-10: the default change propagates through ONE mechanism — the shared _backend helper's stubbed discovery — rather than 24 call-site model= edits

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1] Blocking unknown #2 — scrape survival at personal scale is unmeasured; the Phase 1 probe answers it and re-ranks Adzuna from hedge to primary if LinkedIn/Indeed fail.
- [Phase 4] Blocking unknown #1 — the real `.tex` is **not in this repo**; `.tex → cv.yaml` import cost and Tectonic bundle coverage are unmeasured. Spike on one section is a hard gate before Phase 6 is estimated.
- [Phase 3] RESOLVED by 03-10: the `format` vs `outputFormat` contract is pinned in `app/llm/contract.py` (`format` / `info.structured`, no adaptive fallback) and confirmed by the live schema-constrained call; the deny-ruleset half needed a carve-out for the server-internal `StructuredOutput` tool, now shipped and guarded.
- [Phase 5] Ranking batching (one call per listing vs per K) and budget-cap semantics are unresolved; decide in the plan.
- [Phase 2] RESOLVED at the end-of-phase UAT (2026-09-17): θ=88 was assessed against the real corpus and retained, and the research 10–15% merge-rate band was judged non-transferable to this market — the blocking key plus the grade guard do the discriminating, which the cross-source-only merge rule then hardened. No longer a blocker for planning.

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-09-21T10:40:39.802Z
Stopped at: Phase 03 complete, ready to plan Phase 4
Resume file: None
