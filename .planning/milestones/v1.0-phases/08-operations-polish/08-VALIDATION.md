---
phase: "08"
slug: "operations-polish"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-10-14"
validated: "2026-10-14"
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `08-RESEARCH.md` §Validation Architecture (L751-801), reconciled with the
> five executed `08-0*-PLAN.md` / `08-0*-SUMMARY.md` pairs. Every `Automated Command`
> below was run green on 2026-10-14 after the two gap-closure tests in
> §Validation Audit were added.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest==9.1.1` + `pytest-asyncio==1.4.0` (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `addopts = "-m 'not live and not latex'"`) |
| **Quick run command** | `.venv/bin/python -m pytest -q tests/jobs/ tests/api/test_schedule_settings.py tests/api/test_health_page.py tests/api/test_settings_prune.py tests/db/test_retention_repo.py tests/test_responsive_contract.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest -q` (the default lane is hermetic: offline LLM stub, temp migrated DB, no Docker, no socket) |
| **CSS/build guard (needs node)** | `.venv/bin/python -m pytest -q tests/test_stylesheet_coverage.py -x` — byte-identity of `static/vendor/app.css` against a fresh pinned-CLI build |
| **Estimated runtime** | phase lane ~110 s; full suite ~5–8 min in the audit sandbox |

> **Sandbox note.** The project `.venv` is unusable in the agent sandbox (stale symlink to a
> Python 3.11 with no `pytest`; the venv was built for 3.14.7 with musl-linked extensions).
> Every command in this document was executed through the documented working lane:
> `PYTHONPATH=/workspace/job-search:/workspace/job-search/.venv/lib/python3.11/site-packages /tmp/opencode/gsdvenv13/bin/python -m pytest`
> (Python 3.13.16, pytest 9.1.1). Only the interpreter path differs from the canonical command.

---

## Sampling Rate

- **After every task commit:** run the touched test file(s) with `-x` (the phase lane listed above)
- **After every plan wave:** run the full hermetic suite (`.venv/bin/python -m pytest -q`)
- **Before `/gsd-verify-work`:** the full default lane must be green
- **Max feedback latency:** the narrow `-x` run (seconds), not the full suite
- **Not a gate for this phase:** the `latex` lane — Phase 8 changes nothing in the LaTeX path (D-69 keeps it operator-run)
- **Operator gates:** the two runbooks (`docs/runbook-compose-smoke.md`, `docs/runbook-responsive-ui.md`) and the prune walk, all recorded as open `unrun-verify` items in `.planning/WINDOWS.md` (#14–#17)

---

## Per-Task Verification Map

Task IDs follow the executed plan: `08-0N-TM` is Task M of `08-0N-PLAN.md`. `❌ W0` is
retained only where a file was created in Wave 0; every row below now exists and is green.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-T1 | 08-01 | 1 | RUN-05 | T-08-01 / T-08-SC | The `[SUS]` package is admitted only on a human's explicit exact-pin approval before any install or manifest edit | human gate (checkpoint:human-verify, blocking) | no command — resolved by the human (`approved: apscheduler=3.11.3`; see 08-01-SUMMARY) | N/A | ✅ green |
| 08-01-T2 | 08-01 | 1 | RUN-05 | T-08-01/02/03/04 | `apscheduler==3.11.3` pinned verbatim in both manifests and bound to the installed distribution; the two schedule knobs are `Settings` fields forwarded through compose; the image proves its tz data at build time | unit + static | `.venv/bin/python -m pytest -q tests/test_dependency_pins.py tests/test_config.py tests/test_deploy_manifest.py -x` | ✅ | ✅ green |
| 08-02-T1 | 08-02 | 1 | UI-06 | T-08-05/06/07/08/09 | The queue journey table reflows to label:value cards below 48rem with every desktop column still labelled; the reflow is authored in `input.css`, built byte-identically, and wraps unbroken values; no JS, no CDN | integration + static/build | `.venv/bin/python -m pytest -q tests/test_responsive_contract.py tests/test_stylesheet_coverage.py tests/test_no_cdn.py -x` | ✅ (new) | ✅ green |
| 08-02-T2 | 08-02 | 1 | UI-06 | T-08-07/08 | The tracker and health rows restack every desktop column as labelled cells, and every compact journey control carries the 44x44 floor | integration + static | `.venv/bin/python -m pytest -q tests/test_responsive_contract.py tests/test_stylesheet_coverage.py -x` | ✅ (new) | ✅ green |
| 08-02-T3 | 08-02 | 1 | UI-06 | T-08-06 | The merges / run-history / fit-breakdown tables keep their markup inside a keyboard-reachable, labelled scroll region; the operator checklist ships | static + operator-run | `.venv/bin/python -m pytest -q tests/test_responsive_contract.py -x` (+ `docs/runbook-responsive-ui.md`, WINDOWS #15) | ✅ (new) | ✅ green |
| 08-03-T1 | 08-03 | 2 | RUN-05 | T-08-10/12/14/15 | Saving the schedule form persists an allow-listed time/timezone, leaves exactly one APScheduler job, refuses junk with a 400 and writes nothing; the migration creates only the singleton row; the route carries the identity seam | integration + migration contract | `.venv/bin/python -m pytest -q tests/api/test_schedule_settings.py tests/db/test_migration_contract.py tests/db/test_orm_drift.py tests/db/test_no_pii_columns.py tests/test_auth_seam.py -x` | ✅ | ✅ green |
| 08-03-T2 | 08-03 | 2 | PLAT-06 | T-08-11/13/16 | A scheduled fire runs the existing pipeline exactly once (`trigger='schedule'`, null search id) and refuses to overlap a run already in flight, recording the skip; stale non-terminal runs reconcile to `partial`; start/stop are total | integration | `.venv/bin/python -m pytest -q tests/jobs/test_scheduler.py -x` | ✅ | ✅ green |
| 08-03-T3 | 08-03 | 2 | PLAT-06 | T-08-12 | Reconcile creates the job only when absent, is idempotent, honours an enabled/disabled flip, and never clobbers a persisted past-due fire time; `next_run_at()` is total | integration + operator-run | `.venv/bin/python -m pytest -q tests/jobs/test_scheduler.py -k "past_due or idempotent or next_run or reconc" -v` (+ `docs/runbook-compose-smoke.md`, WINDOWS #16) | ✅ | ✅ green |
| 08-04-T1 | 08-04 | 3 | RUN-07 | T-08-17/18/20/21/22 | `/status` renders the four dependency rows from the one shared builder; `GET /health` keeps its JSON contract; the page and the JSON cannot disagree about opencode reachability or `auth_configured`; a page view issues no board request; every failure degrades to a 200 | integration | `.venv/bin/python -m pytest -q tests/api/test_health_page.py tests/api/test_health.py tests/test_auth_seam.py -x` | ✅ | ✅ green |
| 08-04-T2 | 08-04 | 3 | RUN-06 | T-08-20 | The next-run line renders the scheduled time plus a countdown for a registered job; a disabled schedule reads `Scheduling off`; an enabled-but-unregistered schedule fabricates no time; a recorded missed/in-flight skip renders its own wording | integration | `.venv/bin/python -m pytest -q tests/api/test_health_page.py -k "next_run or missed or last_run or notice" -v` | ✅ | ✅ green |
| 08-04-T3 | 08-04 | 3 | RUN-07 | T-08-19 | The Adzuna promotion verdict shows as read-only evidence with its recorded number and the probe-document link; a short window prints no number; the region offers no control | integration | `.venv/bin/python -m pytest -q tests/api/test_health_page.py -k "adzuna or verdict" -v` | ✅ | ✅ green |
| 08-04-T1 (nav) | 08-04 | 3 | RUN-07 | T-08-22 | The health surface is reached from the UI: the nav carries the `Health` → `/status` entry and marks it current on the page (a route with no nav entry is unreachable without typing the URL) | integration | `.venv/bin/python -m pytest -q tests/api/test_health_page.py -k nav -v` | ✅ (new) | ✅ green |
| 08-05-T1 | 08-05 | 4 | RUN-07 | T-08-23/24/25/26/27/30/31 | The artifact prune previews then deletes rows and their `.tex`/`.pdf` files with the application-link and newest-successful guards holding; every path is resolved inside `artifacts_dir` before the unlink; the unlink follows the commit | unit + route | `.venv/bin/python -m pytest -q tests/db/test_retention_repo.py tests/api/test_settings_prune.py -x` | ✅ | ✅ green |
| 08-05-T2 | 08-05 | 4 | RUN-07 | T-08-25/29 | Runs and the source request log prune at a chosen age while the retained-run floor, the `llm_calls` ledger and the verdict's log inputs survive, with no foreign-key failure and preview == delete | unit | `.venv/bin/python -m pytest -q tests/db/test_retention_repo.py -k "floor or ledger or source_log or ordering or preview_and_delete" -v` | ✅ | ✅ green |
| 08-05-T3 | 08-05 | 4 | RUN-07 | T-08-25/28/29 | The stale-listing hard delete is foreign-key safe, takes a snapshot first, and re-arms the append-only trigger inside the same transaction (asserted from `sqlite_master`, with a negative control) | unit + route + operator-run | `.venv/bin/python -m pytest -q tests/db/test_retention_repo.py -k "listing or trigger or guard" -v` (+ WINDOWS #17) | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Requirement coverage: **RUN-05** (08-01-T1/T2, 08-03-T1), **RUN-06** (08-04-T2),
**RUN-07** (08-04-T1/T1-nav/T3, 08-05-T1/T2/T3), **PLAT-06** (08-03-T2/T3),
**UI-06** (08-02-T1/T2/T3) — all five requirement IDs represented.

---

## Wave 0 Requirements

- [x] `tests/jobs/test_scheduler.py` — the scheduler contract on a real temp-file `SQLAlchemyJobStore` (target, in-flight guard, missed fire, totality, stale-run reconciliation, past-due preservation, create-if-absent, idempotence, enabled/disabled flip, total `next_run_at`)
- [x] `tests/db/test_retention_repo.py` — the four categories, the four guards as a parametrized failure class, the runs ordering/ledger/floor, the listing carve-out with its trigger re-arm assertion and negative control
- [x] `tests/api/test_health_page.py` — the `/status` lane (four rows, page/JSON agreement, no-board-request sentinel, three totality cases, three next-run cases, three skip-notice cases, two last-run cases, two badge cases, four verdict cases, the nav surfacing)
- [x] `tests/api/test_schedule_settings.py` — the form round-trip, both refusals, register/reschedule/remove, the scheduled-path refusal
- [x] `tests/api/test_settings_prune.py` — preview→confirm round-trip, the refusals, preview-equals-delete, the post-commit unlink + containment skip, the audit line, threshold persistence, the snapshot-collision refusal
- [x] `tests/test_responsive_contract.py` — **added by this audit**: the D-160/D-162 reflow contract on the rendered queue/tracker/health rows, the authored reflow block, the admin scroll regions, and the tap floor (see §Validation Audit)
- [x] `tests/db/test_migration_contract.py`, `tests/db/test_orm_drift.py`, `tests/db/test_no_pii_columns.py`, `tests/db/test_skeleton_boot.py`, `tests/test_config.py`, `tests/test_dependency_pins.py`, `tests/test_auth_seam.py` — the guards updated for migration 0008, the three JSON columns, the job-store exemption, the two schedule knobs, the `apscheduler` pin and the four new routes
- [x] `docs/runbook-responsive-ui.md` (new) and the `docs/runbook-compose-smoke.md` schedule step (extended) — the operator checklists
- [x] Framework install: none — the lane already exists

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `ZoneInfo("Europe/Dublin")` resolves in the runtime image, so the scheduler can build its trigger | RUN-05 / PLAT-06 / T-08-03 | Docker is absent from the agent sandbox; the assertion only runs at image build time | `docker compose build` — the build fails on the `RUN python -c "…ZoneInfo('Europe/Dublin')…"` line if the base image ships no tz database; `tzdata` is the documented remedy. Recorded as `.planning/WINDOWS.md` #14 |
| The 320 / 375 / 768 responsive walk of the journey pages | UI-06 / D-161 | A browser and a layout engine do not ship in the repo; the *rendered* geometry and the reflow are only observable there | Walk `docs/runbook-responsive-ui.md`: at 320/375 the queue, tracker and health tables read as label:value cards with no horizontal scroll and every control finger-sized; at 768 the desktop table appears inside its scroll region; a long unbroken value wraps inside its card. Recorded as `.planning/WINDOWS.md` #15 |
| The schedule survives `docker compose restart` and fires exactly once (never two) | PLAT-06 | Docker Compose is absent from the sandbox; the multi-process behaviour is only observable on real containers | `docs/runbook-compose-smoke.md`'s schedule-persistence step: set a daily time, `docker compose restart`, confirm the stored schedule survives and exactly one run with `trigger='schedule'` fires. Recorded as `.planning/WINDOWS.md` #16 |
| The prune control read end to end in a browser (preview counts, protected line, confirm, audit banner) | RUN-07 / D-166 | A browser is absent; the data behaviour and the rendered markup are asserted, but only a person can confirm the surface reads honestly | With the stack up, walk one pass per category: pick a category and an age, read the preview counts and the protected line, confirm, verify the audit banner. Recorded as `.planning/WINDOWS.md` #17 |

*None of the four is rounded up to a pass: each is an open `unrun-verify` item in the broken-windows ledger and is surfaced as unverified in the phase verification, never as a silent pass (CONVENTIONS rule 2). While they are open, `workflow.windows_enforce` blocks `/gsd-ship`.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (the one exception is 08-01-T1, a `checkpoint:human-verify gate="blocking-human"` task with no command by design; it was cleared by a human before the install)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < the narrow `-x` run
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated — 2026-10-14 (gsd-nyquist-auditor)

---

## Validation Audit 2026-10-14

| Metric | Count |
|--------|-------|
| Gaps found | 2 |
| Resolved | 2 |
| Escalated | 0 |
| Manual-only (unchanged, already in WINDOWS.md) | 4 |

**Verification of record.** Full hermetic suite
(`PYTHONPATH=… /tmp/opencode/gsdvenv13/bin/python -m pytest -q`, Python 3.13.16, pytest 9.1.1)
→ **1918 passed, 15 deselected, 2 xfailed, 0 failed**. Phase lane (the nine files in the
Quick-run command plus the guards) → **134 passed**. The two gap-closure tests add 15 to the
suite (1903 → 1918) and each was proven non-vacuous by a mutation run that made it fail
(see below).

### Gap 1 — UI-06's reflow contract was verified only by shell greps (resolved)

Every task in `08-02-PLAN.md` verified the responsive work with ad-hoc one-liners
(`grep -c 'data-label' …`, a `python -c` attribute check). Those die with the session, so the
suite would stay green if a `data-label` were dropped, a `<th>` reworded, an admin scroll
region removed, or the reflow's `overflow-wrap` deleted — a phone would silently show an
unlabelled or mis-headered value. The SUMMARY's own coverage entry for this cited a plain
full-suite pass, which does not exercise the contract.

`tests/test_responsive_contract.py` (new, 14 tests) commits the contract as tests. It renders
the real pages offline and asserts, per journey table, that **a rendered row's cell labels
equal its table's header texts in order** — the failure class is a label that is absent or no
longer matches its column header (D-162). It also pins the authored reflow block (both journey
tables, `attr(data-label)`, `overflow-wrap`) in both source and byte-identical build, the
three labelled keyboard scroll regions, and the tap-floor class on the compact controls.

Negativity: each assertion was shown to fail under a mutation, then the tree was restored —
dropped/misnamed queue label (fail), dropped health label (fail), reworded tracker label
(fail), removed `overflow-wrap` from the reflow (fail), removed `role="region"` (fail),
removed a nav `touch-target` (fail).

### Gap 2 — nothing asserted that `/status` is reachable from the UI (resolved)

RUN-07 requires the health surface to be *surfaced in the UI*. The nav carried the `Health` →
`/status` entry but no test referenced it, so removing the entry would leave the page reachable
only by typing the URL — a RUN-07 regression the route's own 200 cannot catch.
`tests/api/test_health_page.py::test_the_health_page_is_surfaced_in_the_nav` asserts the entry
on `/` and its `nav-current` / `aria-current="page"` state on `/status`. It fails when the nav
line is removed.

### Not Nyquist gaps

`08-REVIEW.md` (a separate code review over the same phase) carries CR-01 / WR-01 / WR-02 /
WR-03 and five info items. Those are implementation and prose defects (a CSRF claim the code
does not deliver, a prune field that does not pre-fill, a `str(CronTrigger)` drift check that
cannot see a timezone change, a `repr()`-anchored stop-signal parse). They are remediation work
for `/gsd-code-review 08 --fix`, **not** missing coverage, and they do not affect
`nyquist_compliant`. The implementation files were not modified by this audit.
