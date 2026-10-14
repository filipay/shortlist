---
phase: "08"
slug: "operations-polish"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
security_block_on: high
created: "2026-10-14"
---

# Phase 08 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Verification depth: **ASVS L1** (grep-level presence, reinforced with the executed hermetic tests). The register was authored at plan time in the PLAN files of all five plans (08-01…08-05), so per the secure-phase short-circuit (`threats_open: 0`, register authored at plan time, `asvs_level: 1`) L1 presence verification is sufficient, with a full read of the five shipped source modules rather than grep alone. `security_block_on = high`.

**Scope audited:** the dependency pin and its two configuration knobs (`pyproject.toml`, `requirements.txt`, `app/config.py`, `compose.yml`, `Dockerfile`, `entrypoint.sh`, `tests/test_dependency_pins.py`, `tests/test_config.py`); the responsive reflow source and committed artefact (`assets/tailwind/input.css`, `static/vendor/app.css`, `tests/test_stylesheet_coverage.py`, `tests/test_no_cdn.py`, the journey/admin templates); the scheduler slice (`app/jobs/scheduler.py`, `app/db/repositories/operations_config_repo.py`, `app/db/repositories/run_repo.py`, `app/main.py`, `app/api/settings.py`, `alembic/versions/0008_operations_config.py`, `app/db/models.py`); the health surface (`app/api/health.py`, `app/api/health_page.py`, `app/db/repositories/source_repo.py`, `app/web/templates/html/health.html`, `app/web/templates/html/base.html`); and the retention/prune surface (`app/db/repositories/retention_repo.py`, `app/api/settings.py`'s two prune routes and the reused reset helpers, `app/web/templates/html/settings.html`).

**Register hygiene note:** `T-08-SC` is declared once in plan 08-01 and once in plan 08-03 with a per-plan scope; there are **31 unique numbered threats** (`T-08-01` … `T-08-31`) plus the two `T-08-SC` occurrences — **33 declared rows, 32 unique threats**. The two `T-08-SC` rows are merged into one row below (the 05/06/07 house convention). Every row across the five plans carries disposition `mitigate`; there are **no** `accept`- and no `transfer`-dispositioned rows. Severity spread: 15 high, 14 medium, 3 low, 0 critical.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| PyPI → the running interpreter and the container image | Third-party code is fetched and executed in-process; the phase's only new supply-chain surface | Pinned wheel/sdist |
| dependency manifests → the image build | `requirements.txt` is what the Dockerfile installs and `pyproject.toml` is the declared contract | Pin strings |
| host `.env` → the container | compose substitutes `${…}` and the image carries no `.env`, so an unforwarded knob silently reverts to the code default | Two schedule knobs |
| base image → the schedule's timezone arithmetic | `zoneinfo` reads the system tz database; if absent the trigger cannot be built and the failure surfaces at run time | tz data |
| HTML template → CSS rule set | A class used in a template but absent from the source stylesheet is an unstyled control | Class names |
| source stylesheet → committed build artefact | `static/vendor/app.css` is committed and served; a hand-edit diverges from a real rebuild | CSS source → artifact |
| rendered label text → assistive technology | `content: attr(data-label)` renders the phone label | Label text ↔ header text |
| the browser schedule form → the stored schedule document | `run_at` and `timezone` arrive from the browser | Untrusted form fields |
| the process → its own restart | The persisted schedule and fire time are the only thing that survives boot | Persisted job state |
| APScheduler's executor → the async pipeline | The callable and its arguments are serialised into a third-party table | Module ref + pickled args |
| a scheduled run → a concurrent manual run | Both write `runs` rows and spend LLM budget; only the database predicate sees both | Non-terminal run rows |
| the library's job store → our schema contract | The job store creates its own table outside Alembic | Third-party DDL |
| a page view → a job board | A view that contacts a board would be the scrape this project exists not to be (T-01-31) | None (DB-only page) |
| the database → the rendered page | Dependency failures expose the exception class name and a disclosed path only | Diagnostics |
| the scheduler object → the page | The scheduler may be absent, unstarted or paused; the accessor must be total | Optional datetime |
| the recorded verdict → the operator's decision | Evidence must not become an action | Verdict text |
| the browser prune form → the delete statements | A category and an age arrive from the browser and select what is destroyed | Untrusted form fields |
| the database rows → the filesystem | Stored artifact paths are unlinked | Stored paths |
| the transaction → the append-only invariant | The listing carve-out suspends a tamper-evidence trigger | Trigger DDL |
| the destructive route → a prefetch or link | Both prune steps must be POSTs | HTTP method |
| the retention floor → the readers downstream | The ledger and run floor protect spend ceilings and the health page's inputs | Guarded rows |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-08-01 | Tampering (supply chain) | `apscheduler` install | high | mitigate | A `checkpoint:human-verify gate="blocking-human"` task precedes the install and is never auto-approved (`08-01-PLAN.md:126-143`), resolved by a human at `approved: apscheduler=3.11.3` before any install or manifest edit (`08-01-SUMMARY.md:156`). The install is by exact pin with no range: `"apscheduler==3.11.3"` in `pyproject.toml:38` and `requirements.txt:31`, bound to the installed distribution by the `PINNED_PACKAGES` row `("apscheduler", "apscheduler==3.11.3", "3.11.3")` (`tests/test_dependency_pins.py:37`). | closed |
| T-08-02 | Tampering | manifest drift between `pyproject.toml` and `requirements.txt` | medium | mitigate | Both lines are the identical string `apscheduler==3.11.3` written in one task; `tests/test_dependency_pins.py` asserts the pin appears verbatim in both manifests and equals the installed version (6 passed). | closed |
| T-08-03 | Denial of Service (self-inflicted) | `ZoneInfo("Europe/Dublin")` with no tz database | medium | mitigate | `ENV TZ=Europe/Dublin` (`Dockerfile:58`) plus the build-time assertion `RUN python -c "from zoneinfo import ZoneInfo; ZoneInfo('Europe/Dublin')"` (`Dockerfile:59`), so a base image without tz data fails the image build rather than the morning run. The build itself is operator-run (Docker absent from the sandbox; `.planning/WINDOWS.md` #14) — the assertion is present and armed. | closed |
| T-08-04 | Tampering (configuration substitution) | an unforwarded `Settings` field | low | mitigate | Both knobs are forwarded through `compose.yml:72-73` (`SCHEDULE_TIMEZONE=${SCHEDULE_TIMEZONE:-Europe/Dublin}`, `SCHEDULE_MISFIRE_GRACE_SECONDS=${SCHEDULE_MISFIRE_GRACE_SECONDS:-3600}`); the config surface guard (`tests/test_config.py`) fails if either field disappears from `Settings` (29 passed). | closed |
| T-08-05 | Tampering | `static/vendor/app.css` hand-edited out of sync with its source | high | mitigate | The byte-identity guard `test_the_committed_stylesheet_is_the_build_of_its_source` (`tests/test_stylesheet_coverage.py:232-265`) re-builds from source with the pinned CLI and asserts byte-equality; it **ran and passed** (not skipped — all 10 tests green) after the phase's rebuild. The 07-13 failure mode is deliberately re-guarded. | closed |
| T-08-06 | Information Disclosure | a new external asset reference on a journey page | medium | mitigate | No asset reference is added; `tests/test_no_cdn.py` guards UI-07 and passed. | closed |
| T-08-07 | Spoofing (accessibility) | a `data-label` that disagrees with its column header | low | mitigate | `data-label` is present on all 8 queue-row cells (`_listing_row.html`), 6 tracker cells (`_application_row.html`) and 5 health-row cells (`_health_strip.html`), each equal to its desktop `<th>` text. | closed |
| T-08-08 | Denial of Service (usability) | a long unbroken value widening the phone page | low | mitigate | The reflow's block-display cells plus `overflow-wrap: anywhere` inside the `@variant max-md` block (`assets/tailwind/input.css:1964`) reach the committed build, so an unbroken source name or deep CV path wraps inside its card. | closed |
| T-08-09 | Tampering (gate evasion) | the coverage guard silently passing because the CLI is absent | medium | mitigate | The guard emits a visible `pytest.skip` naming the arming command when the CLI is absent (`tests/test_stylesheet_coverage.py:242-247`) — never a silent pass; each task's `fails_when` treats a skipped assertion as not-a-pass. In this audit the CLI was present and the assertion executed. | closed |
| T-08-10 | Tampering / DoS (self-inflicted) | the schedule form's `run_at` and `timezone` fields | high | mitigate | Validated at the storage boundary before any SQL: `_parse_schedule_form` requires exactly `HH:MM` with two digits, hour ≤ 23 and minute ≤ 59, and a timezone in the frozen `ALLOWED_TIMEZONES` (`app/api/settings.py:347-369`); `write_schedule` re-validates before SQL (`app/db/repositories/operations_config_repo.py:126-134`). An invalid submission writes nothing and re-renders with a 400 (`tests/api/test_schedule_settings.py`: junk time / unknown timezone cases pass). | closed |
| T-08-11 | Repudiation / DoS (self-inflicted) | a run cancelled by container shutdown leaves a non-terminal row | high | mitigate | Boot-time `reconcile_stale_runs` marks every non-terminal run as the terminal literal `partial` with the reason in the row's existing error storage, adds no column and no status value (`app/jobs/scheduler.py:191-227`); pinned by `test_stale_running_rows_are_reconciled_to_partial`. | closed |
| T-08-12 | Tampering | unconditional job re-registration at boot | high | mitigate | `reconcile` creates only when absent (`replace_existing=False`) and reschedules only on trigger drift, leaving a matching job untouched so a persisted past-due fire time survives (`app/jobs/scheduler.py:230-272`); pinned by `test_a_past_due_fire_time_is_not_clobbered` and `test_reconcile_is_idempotent`. | closed |
| T-08-13 | Denial of Service (self-inflicted) | a scheduled run overlapping a manual run, doubling spend | high | mitigate | One shared in-flight predicate `run_repo.running_run_id` — `Run.status.not_in(tuple(TERMINAL_STATUSES))` (`app/db/repositories/run_repo.py:306-317`) — consumed by both the reset guard (`app/api/settings.py:764-768` delegates) and the scheduled target (`app/jobs/scheduler.py:180-184`), which records the skip instead of starting a second pipeline. Pinned by `test_in_flight_run_is_skipped_not_overlapped`. | closed |
| T-08-14 | Elevation of Privilege | a new route without the identity seam | medium | mitigate | `save_schedule` declares `user: User = Depends(current_user)` (`app/api/settings.py:460`) and `/settings/schedule` is in `EXPECTED_SEAM_ROUTES` (`tests/test_auth_seam.py:68`); the dynamic route walk fails any leaf route without the seam (suite green). | closed |
| T-08-15 | Tampering (schema drift) | the job store's own table appearing outside Alembic | medium | mitigate | `_is_internal` exempts `apscheduler_jobs` **by name** with a comment naming the library as the DDL owner (`tests/db/test_orm_drift.py:57-64`); `tests/db/test_orm_drift.py` passes. | closed |
| T-08-16 | Denial of Service (boot) | a scheduler that cannot start taking the app down | medium | mitigate | `start_scheduler`/`stop_scheduler` are total — each wraps its work, logs the exception class name and returns a status, never raising (`app/jobs/scheduler.py:275-313`); the lifespan calls them inside their own non-fatal guard (`app/main.py:53-67`); pinned by `test_a_broken_jobstore_degrades_to_unavailable` and `test_start_stop_are_total`. | closed |
| T-08-17 | Reputational / legal (ban risk) | a page view issuing a board request | high | mitigate | `GET /status` reads the database only: `app/api/health_page.py` contains no reference to the live probe orchestration, the source badge comes from recorded rows, and the verdict builder is a pure read. Pinned by `test_the_page_issues_no_board_request` and `test_the_verdict_read_issues_no_board_request`. | closed |
| T-08-18 | Information Disclosure | raw upstream or diagnostic content echoed into the page | medium | mitigate | The shared dependency report exposes the exception **class name** only (`app/api/health.py:56,60,80`; `app/api/health_page.py:77-99`), and the page adds no compile log, listing text or exception message; the JSON endpoint's forbidden-body-keys scan stays green (`tests/api/test_health.py` passed unmodified). | closed |
| T-08-19 | Spoofing (operator authority) | the verdict presented as an action | medium | mitigate | The verdict region renders read-only evidence with its number and a single committed-path link (`app/web/templates/html/health.html:51-60`), and `test_the_verdict_region_offers_no_control` asserts no form, button or enabling control. | closed |
| T-08-20 | Denial of Service (page) | a total function made partial by a new read | medium | mitigate | Every read in `page_context` is individually guarded so one failure degrades one line (`app/api/health_page.py:176-191,222-355`); explicit totality tests cover a failing database read, a raising dependency probe and a raising scheduler (all pass). | closed |
| T-08-21 | Tampering (contract drift) | the shared builder silently changing the JSON key names | high | mitigate | `dependency_report` returns exactly `db`/`opencode`/`tectonic`/`cv` in the existing reading order (`app/api/health.py:124-131`) and the JSON route merges it with `**report` rather than restating keys (`:182-190`); `tests/api/test_health.py`'s 20 exact assertions passed **unmodified**. `GET /health` keeps its path and the page takes `/status`, so the 25 call sites are untouched. | closed |
| T-08-22 | Elevation of Privilege | the new page route without the identity seam | medium | mitigate | The `/status` route declares `user: User = Depends(current_user)` (`app/api/health_page.py:360`) and is in `EXPECTED_SEAM_ROUTES` (`tests/test_auth_seam.py:72`). | closed |
| T-08-23 | Tampering / Elevation of Privilege | path traversal via an artifact row's stored path | high | mitigate | Every path is resolved and asserted inside `artifacts_dir` both at the preview's `stat()` (`app/db/repositories/retention_repo.py:417-434`) and at the post-commit unlink, where a path outside is skipped and reported, never followed (`app/api/settings.py:952-983`). Pinned by `test_a_path_outside_the_artifacts_directory_is_skipped_and_reported`. | closed |
| T-08-24 | Tampering | SQL injection through the prune category | high | mitigate | The category is validated against the frozen `PRUNE_CATEGORIES` (`app/db/repositories/retention_repo.py:82-84,154-169`) and mapped to pre-built statements through a frozen `MappingProxyType`; no request-derived string is interpolated and the repository contains no f-string (asserted in the plan's gate). | closed |
| T-08-25 | Denial of Service (self-inflicted, data-destroying) | an unbounded delete from a mis-typed threshold | high | mitigate | `_validate` refuses a zero, negative or non-integer age rather than clamping (`app/db/repositories/retention_repo.py:154-169`); the preview is mandatory and shares the delete's predicate; the confirm re-derives the count and refuses at zero (`app/api/settings.py:1089-1099`); the most destructive category takes a snapshot first (`:1109-1130`). | closed |
| T-08-26 | Tampering (destructive action from a GET or prefetch) | the prune routes | high | mitigate | Both steps are `@router.post` routes (`app/api/settings.py:1029,1070`), the preview deletes nothing, and the confirm form renders only when the preview returned a non-zero count while the server re-derives it anyway. | closed |
| T-08-27 | Repudiation (silent destruction) | the audit trail of a prune | medium | mitigate | Every prune renders an audit line naming the count, the category, the threshold and the time, appends any skipped/outside paths and a snapshot note (`app/api/settings.py:1179-1195`), and logs a structured `prune.completed` event. | closed |
| T-08-28 | Tampering / Denial of Service | the suspended append-only trigger left down | high | mitigate | The suspension and the re-arm bracket the deletes inside the caller's one transaction (`app/api/settings.py:1139-1148`, reusing the reset's shipped `_suspend_append_only_trigger`/`_restore_append_only_trigger`); `test_the_listing_prune_leaves_the_append_only_trigger_armed_with_its_negative_control` reads `sqlite_master` after the commit and proves the assertion can fail. | closed |
| T-08-29 | Denial of Service (downstream correctness) | pruning the ledger, the run floor or the verdict's log inputs | high | mitigate | The four guards are conditions in the selections: the run floor reuses `RUN_HISTORY_LIMIT` (`app/db/repositories/retention_repo.py:178-180,248-253`), `llm_calls` rows survive with a nulled `run_id` (`:269`), application-linked artifacts and each listing's newest successful artifact are excluded (`:209-216`), and the source request log keeps rows belonging to retained runs (`:282-288`). Covered by four parametrized guard tests. | closed |
| T-08-30 | Tampering | artifact rows left pointing at deleted files, or files deleted with a rolled-back commit | medium | mitigate | The repository never commits and never unlinks (`app/db/repositories/retention_repo.py:479-504`); the route commits the row deletes first (`app/api/settings.py:1148`) and only then unlinks (`:1169`), so a rolled-back commit never leaves live rows without files and an unlink failure is reported. | closed |
| T-08-31 | Elevation of Privilege | a new destructive route without the identity seam | medium | mitigate | `preview_prune` and `confirm_prune` both declare `user: User = Depends(current_user)` (`app/api/settings.py:1032,1073`) and both paths are in `EXPECTED_SEAM_ROUTES` (`tests/test_auth_seam.py:76-77`); the dynamic walk passes. | closed |
| T-08-SC | Tampering (supply chain) | package installs across the phase (08-01…08-05) | high | mitigate | The phase adds exactly one runtime dependency behind a blocking human checkpoint (T-08-01); the diff of both manifests from 08-01's parent to HEAD shows only the `apscheduler==3.11.3` lines. Alembic 0008 is purely additive — one new table, no `alter_table`/`batch_alter_table`, `runs` untouched (`alembic/versions/0008_operations_config.py:43-52`). No npm/cargo/other install occurs. See also AR-08-01. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (`high`) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

No row in the register carries disposition `accept` or `transfer`. The items below are the residual risks each plan records in prose and accepts explicitly; they are logged here so a later run does not re-litigate them.

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-08-01 | T-08-01, T-08-SC | Installing a third-party wheel always confers trust in that project's maintainers. The blocking-human gate and the exact pin reduce the chance of an accidental slopsquat; they do not audit the library's source, which is out of ASVS L1 scope. | plan 08-01 | 2026-10-14 |
| AR-08-02 | T-08-15 | APScheduler's `apscheduler_jobs` is a third-party table whose schema we do not own, so a future library upgrade may change it without a migration of ours. The pinned version plus the named drift-guard exemption is the mitigation; auditing the library's internals is out of ASVS L1 scope. | plan 08-03 | 2026-10-14 |
| AR-08-03 | T-08-17, T-08-19 | The Adzuna promotion verdict is derived from a bounded run window, so a corpus with very few runs reads "no verdict recorded yet" rather than a number. That is the honest state (D-158), the same discipline the schedule line applies to a missing next-run time. | plan 08-04 | 2026-10-14 |
| AR-08-04 | T-08-05, T-08-08 | `display: block` on table elements degrades table semantics in some assistive technologies; the `data-label` pattern exists to compensate, and the plan states this rather than claiming an accessibility guarantee the CSS does not deliver (CONVENTIONS rule 6). | plan 08-02 | 2026-10-14 |
| AR-08-05 | T-08-28 | The stale-listing category is genuinely unrecoverable apart from the snapshot, and its accepted consequence (D-167) is that a re-posted job returns as a new listing with prior dismissals gone. This is a deliberate, documented, one-way trade-off recorded in the repository docstring and the UI copy. | plan 08-05 | 2026-10-14 |

*Accepted risks do not resurface in future audit runs.*

---

## Threat Flags

The `## Threat Flags` sections were read in all five SUMMARY files:

- **08-01**, **08-02**, **08-04** carry no `## Threat Flags` section, so they introduce no unregistered flag. **08-02** additionally states "None" in its Threats section (`08-02-SUMMARY.md:180-182`).
- **08-03** reports `threat_flag: new-scheduled-execution-path` (`app/jobs/scheduler.py`) — a new unattended execution path where a trigger calls `run_pipeline` with no user in the loop. This **maps to existing threats** `T-08-13` (the database in-flight guard), `T-08-16` (the non-fatal boot guard) and `T-08-10` (the allow-listed schedule inputs), and adds no new network endpoint or credential. It is therefore informational, not an unregistered flag.
- **08-05** reports "None — every file changed sits inside the plan's `<threat_model>`, and all nine threats (T-08-23 … T-08-31) are mitigated by code committed here" (`08-05-SUMMARY.md:216-218`).

No `unregistered_flag` was raised.

---

## Verification Notes (non-blocking)

Hermetic evidence (provisioned Python 3.13.16 interpreter, since the sandbox `.venv` is a broken 3.14 venv). Lane: `PYTHONPATH=/workspace/job-search:/workspace/job-search/.venv/lib/python3.11/site-packages /tmp/opencode/gsdvenv13/bin/python -m pytest`:

- `tests/jobs/test_scheduler.py tests/api/test_schedule_settings.py tests/api/test_health_page.py tests/db/test_retention_repo.py tests/api/test_settings_prune.py tests/test_auth_seam.py tests/test_dependency_pins.py tests/test_config.py` → **137 passed** (2026-10-14).
- `tests/api/test_health.py tests/test_stylesheet_coverage.py tests/test_no_cdn.py tests/db/test_orm_drift.py tests/db/test_migration_contract.py tests/db/test_no_pii_columns.py` → **67 passed** (2026-10-14).
- `tests/test_stylesheet_coverage.py -v -rs` re-run explicitly: **10 passed, 0 skipped** — the byte-identity assertion (T-08-05) was executed, not skipped. This is the strongest single piece of evidence in the phase: the committed artifact is the pinned CLI's build of its source.

Precise greps used to locate each declared mitigation:

- `grep -n 'apscheduler' pyproject.toml requirements.txt` → the pin in both manifests; `git diff 431a639~1 HEAD -- pyproject.toml requirements.txt` → only the `apscheduler` lines, proving T-08-SC.
- `grep -n 'ZoneInfo\|TZ=' Dockerfile` → `ENV TZ=Europe/Dublin` + the build-time `ZoneInfo('Europe/Dublin')` assertion (T-08-03).
- `grep -n 'running_run_id\|not_in(tuple(TERMINAL_STATUSES))' app/db/repositories/run_repo.py app/api/settings.py app/jobs/scheduler.py` → one predicate, two consumers (T-08-13).
- `grep -n 'probe_all\|app.probe.probe' app/api/health_page.py app/db/repositories/source_repo.py` → only `app.probe.survival` (pure functions); the live-probe orchestration is never imported (T-08-17).
- `grep -n 'max-md\|overflow-wrap\|attr(data-label)' assets/tailwind/input.css` → the reflow block, the wrap declaration and the label rule (T-08-07/T-08-08).

Operator-run checks remain unrun and are recorded in `.planning/WINDOWS.md` (Docker and a browser are absent from the sandbox); they do not affect a declared-mitigation verdict:

- **#14** — `docker compose build` proves the `ZoneInfo` assertion (T-08-03). The assertion is present and correct; only its execution is deferred.
- **#15** — the 320/375/768 responsive walk of `docs/runbook-responsive-ui.md` (T-08-07/T-08-08 rendered correctness; the static half is proven by the green byte-identity guard).
- **#16** — the schedule-persistence compose smoke (a second concurrent `schedule` run is the failure it catches; the in-flight guard is proven hermetically by T-08-13).

Non-blocking observation (no action required): the prune and reset refusal banners render the exception string into the settings danger-zone page (`app/api/settings.py:1125,1163` and the pre-existing reset path at `:898,930`) and log it. This is the **pre-existing house pattern** in the settings module, not surface introduced by phase 08, and the reader is the single local user viewing their own database's error — no upstream content, no listing text and no third-party data crosses. It is not a declared-mitigation gap for any threat in this register and was not raised as an `unregistered_flag`.

Implementation files were read-only during this audit; no file other than this SECURITY.md was written by the auditor.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-14 | 32 (33 declared rows across the five PLANs) | 32 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-14 (08-01…08-05; 31 numbered threats plus the merged `T-08-SC`)
