---
phase: "02"
slug: "clean-filtered-queryable-queue"
status: verified
threats_total: 45
threats_open: 0
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (high)
asvs_level: 1
created: "2026-09-16"
---

# Phase 02 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register authored at plan time across the `02-01..02-10-PLAN.md` `<threat_model>`
> blocks (45 STRIDE threats). Audited against the implemented code, not against the
> plan prose. `security_block_on=high`, `security_asvs_level=1`.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| migration → live database | DDL runs once against accumulated real data; a wrong statement is not undoable without a restore | schema/DDL |
| schema → application | Column names/types are the contract the PII + migration guards read | schema metadata |
| PyPI → the running container | Third-party code fetched and executed in-process (the phase's only new supply-chain surface) | executable code |
| dependency manifests → the build | `requirements.txt` is what the Dockerfile installs; `pyproject.toml` is the declared contract | pinned versions |
| listing text (untrusted) → rule evaluation / HTML | job-board descriptions flow into matching and into autoescaped markup — never executed, never persisted as evidence, no CDN | listing prose (untrusted) |
| criteria + rule params (user-supplied) → evaluators | `params` mappings are attacker-influenceable if a criteria import path is added; treated as data | user config |
| HTTP client → mutations | POSTs change persisted listing/search/merge state | state changes |
| run → persisted JSON (exclusions, stage log, reason counts, errors) | evidence must carry terms/field names/counts/board+filter names only | counters, names (no prose/PII) |
| board capabilities → the user's belief about filters | a filter a board cannot honour, recorded nowhere, would be mistaken for applied | capability warnings |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-02-01 | Tampering | `alembic/versions/0002_*.py` | medium | mitigate | Purely additive migration; `op.add_column` nullable only; batch path used only for named `ck_runs_reason`; pre-existing named CHECKs survive (`alembic/versions/0002_queue_filter_and_run_reason.py:62-114`; `tests/db/test_migration_contract.py:373-413`) | closed |
| T-02-02 | Information Disclosure | new JSON columns (`filter_rules.params_json`, `runs.reason_counts_json/stage_log_json/criteria_snapshot_json`) | high | mitigate | Each deliberately added to `EXPECTED_JSON_COLUMNS`; no PII-shaped column name (`tests/db/test_no_pii_columns.py:30-70,86-130`; `app/db/models.py:81,300-303`); content contract enforced at write sites (T-02-07/T-02-17) | closed |
| T-02-03 | Repudiation | schema guard loosened by "testing" | medium | mitigate | Guard edits are additions only (`git diff f5cf20a..HEAD -- tests/db/test_migration_contract.py tests/db/test_no_pii_columns.py`: +193/-14, removals are the 0001→0002 revision bump); append-only/FTS assertions intact (`tests/db/test_migration_contract.py:107-129`) | closed |
| T-02-04 | Tampering (supply chain) | `rapidfuzz==3.14.6` install | high | mitigate | Exact pin, no range (`pyproject.toml:26`, `requirements.txt:18`); blocking human checkpoint recorded approved (`02-02-SUMMARY.md:88,149`); pin asserted (`tests/test_dependency_pins.py:40-59`) | closed |
| T-02-SC | Tampering | pip/uv installs this phase | high | mitigate | Exactly one new runtime dependency in the phase diff (`git diff f5cf20a..HEAD -- pyproject.toml requirements.txt`); unpinned entry fails the guard (`tests/test_dependency_pins.py:49-51`) | closed |
| T-02-05 | Tampering | manifest drift (`pyproject.toml` ↔ `requirements.txt`) | medium | mitigate | Pin added to both files and asserted (`tests/test_dependency_pins.py:40-45`); `tests/test_deploy_manifest.py` green | closed |
| T-02-06 | Tampering | `filter.evaluate` over `params` | medium | mitigate | Total function: non-mapping/missing/wrong-typed/unknown-kind → skipped, never raises (`app/domain/filter.py:373-392`); no eval/exec/import; `getattr` only over `LISTING_FACT_FIELDS` (`app/domain/filter.py:60-71,220-223`) | closed |
| T-02-07 | Information Disclosure | `RuleOutcome.detail` | high | mitigate | Detail vocabulary is terms/field-names/counts/numbers (`app/domain/filter.py:190-234`); exact key-set equality per kind (`tests/domain/test_filter.py:401`, `:175,208,255`); description prose absent from stored evidence (`tests/db/test_exclusions.py:282-311`) | closed |
| T-02-08 | Tampering | `INJECTION_PATTERNS` / `looks_like_instructions` | medium | mitigate | Flag-and-count only; `count_injection_patterns` returns a count and no `re.sub` mutates stored text (`app/domain/sanitize.py:169-192,222-233`); `tests/domain/test_injection_patterns.py` | closed |
| T-02-09 | Tampering | skipped rule treated as applied | medium | mitigate | `evaluate` emits no outcome for a skip; the stage counts `rules_skipped` into the stage log (`app/pipeline/filter_stage.py:88-90`; `app/domain/filter.py:28-30,386-392`) | closed |
| T-02-10 | Tampering (data loss) | `apply_merge` field fills | high | mitigate | Fill-blanks-only over `_LISTING_FIELDS`; `""`/`None` count as blank; twin never deleted/deactivated (`app/db/repositories/dupe_repo.py:195-224`; `tests/db/test_dupes.py:154-213,242-266`). **WARNING W-02**: register says `company_id` is not in the tuple, but it is (`app/db/repositories/listing_repo.py:40`) — residual impact negligible (same `company_norm` block). Primary control present. | closed |
| T-02-11 | Repudiation | merge audit trail | high | mitigate | Exactly one `ListingDupe` per merge, same transaction, always carrying `method`/`score`/`merged_at`/`snapshot_json`; INSERT-only on this path (`app/db/repositories/dupe_repo.py:212-224`; `tests/db/test_dupes.py:216-238`) | closed |
| T-02-12 | Denial of Service (self) | unbounded fuzzy candidate set | medium | mitigate | Indexed `company_norm` equality block first; group-of-one dropped; no all-pairs comparison (`app/pipeline/dedup_stage.py:74-103`; `app/db/repositories/dupe_repo.py:67-99`) | closed |
| T-02-13 | Tampering | revert undone by next run (D-28) | high | mitigate | `reverted_pairs` reads both orientations and the stage filters them before scoring (`app/db/repositories/dupe_repo.py:102-131`; `app/pipeline/dedup_stage.py:112,119-121`; `tests/db/test_dupes.py:124-153`) | closed |
| T-02-14 | Tampering | FTS drift after merge fill | medium | mitigate | Fills go through the ORM row so `listings_au` fires (`app/db/repositories/dupe_repo.py:203-210`); merge-then-search proven (`tests/db/test_dupes.py:270-295`) | closed |
| T-02-15 | Repudiation | disabled/unknown rule silently treated as applied (merge path) | low | accept | Out of plan scope; recorded as accepted risk AR-01 | closed |
| T-02-16 | Tampering | DB-loaded rules evaluated | medium | mitigate | Pure `evaluate`; ORM row mapped to `RuleSpec` before the pure layer; all SQL bound via ORM; deterministic `(search_id, position, id)` order (`app/pipeline/filter_stage.py:81-82,93`; `app/db/repositories/search_repo.py:215-236`; `app/domain/criteria.py`) | closed |
| T-02-17 | Information Disclosure | `listing_exclusions.detail_json`, `runs.stage_log_json/reason_counts_json/errors_json` | high | mitigate | `detail_json` comes straight from the pure evaluator (terms/field-names/counts); stage log/reason counts/errors carry stage names, counts, board+filter names, error-type strings — no description slice, no removed PII value (`app/db/repositories/exclusion_repo.py:70-83`; `app/pipeline/filter_stage.py:98-145`; `app/pipeline/run.py:148-176,277-330,465-482`; `tests/db/test_exclusions.py:282-311`; `tests/pipeline/test_filter_stage.py:199-200`) | closed |
| T-02-18 | Denial of Service (self) | one malformed rule/Run abort | high | mitigate | `evaluate` total; per-listing and per-write failures caught and counted; stage log bounded at write time (`app/pipeline/filter_stage.py:98-145`; `app/pipeline/run.py:273-274,737`) | closed |
| T-02-19 | Repudiation | capability drop recorded nowhere | high | mitigate | Warnings stay in `errors_json` extended with "(enforced locally…)" AND land in `stage_log_json` under `criteria_compile` as structured triples (`app/pipeline/run.py:148-176,632-638,708-716`; `tests/pipeline/test_capability_surface.py:140-232`) | closed |
| T-02-20 | Tampering | criteria edit rewriting a completed run | medium | mitigate | Snapshot written before the fetch and never rewritten by `_finish` (`app/pipeline/run.py:333-352,619`); `tests/pipeline/test_criteria_snapshot.py` | closed |
| T-02-21 | Tampering (destructive revert) | `revert_merge` | high | mitigate | UPDATE-only: sets `reverted_at`/`reverted_by`, reads `snapshot_json`, never clears; no `DELETE` on `listing_dupes` anywhere in `app/`; `listing_sources` untouched (`app/db/repositories/dupe_repo.py:501-563`; `tests/db/test_dupes.py:242-266`) | closed |
| T-02-22 | Tampering | revert undone by next run | high | mitigate | Negative-memory pre-check + real second run asserts zero new dupe rows (`app/pipeline/dedup_stage.py:112,119-121`; `tests/pipeline/test_dedup_revert.py:158-201`) | closed |
| T-02-23 | Tampering (XSS) | `merges.html` | high | mitigate | Jinja autoescape, no `|safe` (only a comment mentions it); no remote asset (`tests/api/test_merges_view.py:31-32,258-264`; `tests/test_no_cdn.py`) | closed |
| T-02-24 | Information Disclosure | Merges page snapshot value | medium | mitigate | `UNRENDERED_SNAPSHOT_FIELDS` excludes `source_extras_json`/`quality_signals_json` from the page while revert still restores them (`app/db/repositories/dupe_repo.py:43,425-430`) | closed |
| T-02-25 | Repudiation | incorrect merge hidden behind rate | medium | mitigate | Rate renders with both integers, the window named, reverted count separate, and the rows newest-first on the same page (`app/db/repositories/dupe_repo.py:449-499`; `tests/api/test_merges_view.py:160-198`) | closed |
| T-02-26 | Tampering / DoS | FTS5 `MATCH` from user text | high | mitigate | Every token quoted; `None` for empty query; `MATCH` takes only the bound `:match_expression` (`app/domain/search_query.py:47-75`; `app/db/repositories/queue_repo.py:114,300,334`; `tests/domain/test_search_query.py`) | closed |
| T-02-27 | Tampering (stored XSS) | `queue_list.html` / `_listing_row.html` | high | mitigate | Autoescape, no `|safe`; badges server-rendered; no CDN; the shared row partial is XSS-tested (`tests/api/test_listing_events.py:269-275`; `tests/test_no_cdn.py`) | closed |
| T-02-28 | Denial of Service (self) | page size / paging | low | mitigate | `limit` from `settings.queue_page_size`, never the request; `offset` clamped ≥0; predicate change resets offset; FTS ordered by `bm25` with unique tie-break (`app/web/routes.py:91-106`; `app/db/repositories/queue_repo.py:298-342`) | closed |
| T-02-29 | Repudiation | new-since watermark | medium | mitigate | Single DB row, advanced only by `GET /` and `Mark all as seen`, never backwards (`app/db/repositories/state_repo.py:55-89`; `app/web/routes.py:198`; `tests/db/test_queue_state.py:61-77`) | closed |
| T-02-30 | Information Disclosure | `Show excluded` reveals withheld listings | low | accept | Intentional product feature for a single local user; recorded as accepted risk AR-02 | closed |
| T-02-31 | Tampering | rule parameters from the UI | high | mitigate | `validate_rule_params` rejects per kind before any insert (non-int/negative amount, empty terms, unrecognised `fields`, unknown kind) (`app/db/repositories/search_repo.py:417-479,638-640`; `app/api/searches.py:505`); DB `ck_filter_rules_kind` CHECK (`alembic/versions/0002_queue_filter_and_run_reason.py:74`) | closed |
| T-02-32 | Repudiation | silent capability drop | high | mitigate | Every enabled search compiled against every enabled adapter's capabilities at render time; registry walk degrades to no warnings, not a 500 (`app/domain/criteria.py`; `tests/api/test_criteria_capabilities.py:93-134`) | closed |
| T-02-33 | Tampering | version churn | medium | mitigate | `version` bumps only on a real stored-field change; enable/disable deliberately does not bump; rule CRUD bumps the owner (`app/db/repositories/search_repo.py:482-488,524-560,575-579,654,701,717`; `tests/api/test_searches_crud.py`) | closed |
| T-02-34 | Tampering (destructive delete) | `delete_search` | medium | mitigate | Deletes the search + its rules only; listings/exclusions/merges untouched; runs row survives with its snapshot (only nullable `runs.search_id` pointer cleared) (`app/db/repositories/search_repo.py:594-618`) | closed |
| T-02-35 | Tampering (XSS) | search names / rule terms rendered back | high | mitigate | Boundary sanitisation + autoescape, no `|safe`; tag-bearing name escaped (`tests/api/test_searches_crud.py:18-21,218-240`; `app/web/templates/html/criteria.html`) | closed |
| T-02-36 | Tampering | forging a listing's state via the event log | high | mitigate | DB triggers abort UPDATE/DELETE (`alembic/versions/0001_initial_schema.py:344-349`); repository INSERT-only; statement-counting test; state projected, not stored (`app/db/repositories/event_repo.py`; `tests/db/test_listing_events.py:127-186`; `tests/db/test_migration_contract.py:107-129`) | closed |
| T-02-37 | Tampering | attacker-chosen `event_type` / `occurred_at` | medium | mitigate | Route validates against `event_repo.EVENT_TYPES`, 422 before write; `occurred_at` server-side only (`app/api/events.py:93-101,114-120`; `app/db/repositories/event_repo.py:60,170-173`) | closed |
| T-02-38 | Tampering (XSS) | re-rendered row fragment | high | mitigate | Same `_listing_row.html` partial, autoescape, no `|safe`; tag-bearing title seeded (`app/api/events.py:49-51,148-156`; `tests/api/test_listing_events.py:269-275`) | closed |
| T-02-39 | Repudiation | save/hide conflated | medium | mitigate | Two distinct event types and controls; projection tracks them independently (`app/api/events.py:1-11`; `app/db/repositories/event_repo.py:60-66,109-145`; `tests/api/test_listing_events.py`) | closed |
| T-02-40 | Denial of Service (self) | unbounded event growth | low | accept | One row per deliberate click on one person's corpus; pruning deferred to Phase 8; recorded as accepted risk AR-03 | closed |
| T-02-41 | Information Disclosure | history page renders `errors_json`/`stage_log_json`/`reason_counts_json` | medium | mitigate | Columns carry counts/names only; read model defaults nullable JSON to empty mapping/list and bounds the stage log; escaped (`app/db/repositories/run_repo.py:55-62,183-198,201-221`; `tests/api/test_run_history.py:37-38,371-380`) | closed |
| T-02-42 | Tampering | mutation reachable from history page | low | mitigate | History routes are `GET` only (`app/api/runs.py:125,142`); `POST /runs` unchanged; every leaf route carries `current_user` (`tests/test_auth_seam.py`) | closed |
| T-02-43 | Repudiation | partial/failed run rendered as clean success | high | mitigate | `runs.status` carried verbatim, never recomputed; reason + sentence shown for every run; in-flight run has no duration (`app/db/repositories/run_repo.py:112-120,205-208`; `tests/api/test_run_history.py`) | closed |
| T-02-44 | Denial of Service (self) | unbounded history / stage log | low | mitigate | `list_runs` takes an explicit bound; stage log bounded at write and read time; detail expansion is a separate request (`app/db/repositories/run_repo.py:45,183-198,224-238`) | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `security_block_on=high` count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

**Tally:** 45 threats — 42 mitigate, 3 accept (T-02-15, T-02-30, T-02-40), 0 transfer.
21 high / 18 medium / 6 low. No open threat at or above the `high` threshold ⇒ `threats_open: 0`.

---

## Findings / Warnings (not counted toward `threats_open`)

### W-01 — Deployment-image integrity is unregistered and unasserted
The Phase-2 supply-chain threats (T-02-04 / T-02-SC / T-02-05) are mitigated at the
**manifest** layer only. `Dockerfile:38-39` installs `requirements.txt`, and the sole
post-install assertion (`Dockerfile:49-50`) validates the `python-jobspy` VCS pin — it
does **not** assert that `rapidfuzz==3.14.6` (or any other pin) is present in the built
image. `tests/test_dependency_pins.py:54-59` imports `rapidfuzz` from the *test*
environment (not the image), and `tests/test_deploy_manifest.py` checks only that
`pyproject.toml` and `requirements.txt` agree with each other. A real deployment was
reported running a stale Phase-1 image where `rapidfuzz` was absent. Therefore the
declared mitigation covers "the two files agree", **not** "the image contains the pinned
dependency". No threat ID maps to this hazard → recorded as an unregistered flag.
Recommend: add a Dockerfile post-install assertion alongside the JobSpy one, e.g.
`RUN python -c "import rapidfuzz; assert rapidfuzz.__version__ == '3.14.6'"`, and/or a
deploy-manifest test that every `requirements.txt` pin is importable in the image.

### W-02 — T-02-10 register text overclaims `_LISTING_FIELDS` membership
The T-02-10 mitigation states `company_id` is not in `_LISTING_FIELDS` and is
"structurally unreachable"; `company_id` **is** in the tuple
(`app/db/repositories/listing_repo.py:40`), so `apply_merge` can fill it. The primary
control (fill-blanks-only) and the never-delete-twin control are present, and both
endpoints share a `company_norm` block, so the residual impact is negligible — the
threat is closed. Recommend either removing `company_id` from the fill set or correcting
the register wording. (`title`, `canonical_url`, `first_seen_at`, `content_hash` are
indeed absent, as claimed.)

### Deferred Info findings (code review, not security blockers)
`02-REVIEW.md` IN-05 already records that `filter.py`'s docstring ("never an excerpt of
the listing's own text") is stronger than the code: the `location` / `seniority` /
`company_blocklist` evaluators copy the listing's own *location/seniority/company* value
into `detail_json` (`app/domain/filter.py:261,303/312/319,358`). None is description
prose and none is PII, so the privacy bar of T-02-02/T-02-07/T-02-17 (no description
text, no removed PII value) is met; this remains a consciously deferred documentation
fix, not an open threat. IN-13 (no CSRF token) is likewise consistent with the project's
explicit "Auth: none in v1" decision and every route carries the `current_user` seam.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | T-02-15 | Disabled/unknown rule on the merge path is out of plan 02-04's scope; the equivalent merge control is the audited `listing_dupes` row, and rules themselves are handled by 02-05/02-08 | Phase-2 plan register (02-04-PLAN.md) | 2026-09-16 |
| AR-02 | T-02-30 | `Show excluded` is an intentional product feature (D-35); v1 is a single local user with no auth by design, and excluded listings are out of future LLM spend | Phase-2 plan register (02-07-PLAN.md) | 2026-09-16 |
| AR-03 | T-02-40 | One `listing_events` row per deliberate user click on one person's corpus; retention/pruning is a Phase-8 operations item | Phase-2 plan register (02-09-PLAN.md) | 2026-09-16 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-16 | 45 | 45 | 0 | gsd-security-auditor (verify:post hook, capId `security`) |

**Evidence base:** threat registers in `02-01..02-10-PLAN.md` `<threat_model>` blocks;
implementation greps with file:line; targeted test execution of the security lanes
(`tests/test_no_credentials.py`, `tests/test_auth_seam.py`, `tests/test_dependency_pins.py`,
`tests/test_deploy_manifest.py`, `tests/db/test_no_pii_columns.py`,
`tests/db/test_migration_contract.py`, `tests/db/test_listing_events.py`,
`tests/db/test_dupes.py`, `tests/db/test_exclusions.py`, `tests/test_no_cdn.py`,
`tests/pipeline/test_capability_surface.py`, `tests/pipeline/test_dedup_revert.py`,
`tests/pipeline/test_criteria_snapshot.py`, `tests/pipeline/test_filter_stage.py`,
`tests/domain/test_filter.py`, `tests/domain/test_injection_patterns.py`,
`tests/api/test_run_history.py`, `tests/api/test_merges_view.py`,
`tests/api/test_searches_crud.py`, `tests/api/test_listing_events.py`,
`tests/db/test_queue_state.py`, `tests/db/test_fts_triggers.py` — 207 passed, 0 failed).
Nested mitigations were re-derived from the write paths, not from the tests alone;
non-vacuity of the credential, auth-seam, XSS, append-only, description-absence and
manifest guards was checked by reading the assertions.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-16
