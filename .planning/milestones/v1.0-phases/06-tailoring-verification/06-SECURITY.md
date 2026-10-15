---
phase: "06"
slug: "tailoring-verification"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
security_block_on: high
created: "2026-09-25"
---

# Phase 06 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Verification depth: **ASVS L1** (grep-level presence, reinforced with the cited hermetic tests). The register was authored at plan time in the PLAN files of all nine plans (06-01…06-09), so per the secure-phase short-circuit (`threats_open: 0`, `register_authored_at_plan_time: true`, `asvs_level: 1`) L1 presence verification is sufficient. `security_block_on = high`.

**Scope audited:** the tailoring pipeline and its four routes (`app/pipeline/tailor.py`, `app/api/tailoring.py`), the typed patch engine (`app/domain/cv.py`), the LaTeX escaping choke point (`app/latex/env.py`), the artifact repository access control (`app/db/repositories/cv_artifact_repo.py`), the shared spend guard (`app/pipeline/rank.py` `_reserve`/`_release`, `app/db/repositories/llm_call_repo.py` `calls_since`), the verification package (`app/verify/{base,numbers,plan_checks,text_checks,grounding}.py`), the review/page templates (`app/web/templates/html/_tailoring_review.html`, `tailoring.html`), and the redaction of the raised-transport error path (06-09).

**Register hygiene note:** `T-06-SC` is declared once in each of the nine PLAN files with a per-plan scope; there are **42 unique numbered threats** (`T-06-01`…`T-06-42`) plus the nine `T-06-SC` occurrences — **51 declared rows, 43 unique threats**. The nine `T-06-SC` rows are merged into one row below (the 05 house convention).

**Gap-closure re-audit (2026-09-25):** the register was first written against plans 06-01…06-07. Plans **06-08** (CR-01 + CR-02, `gap_closure: true`) and **06-09** (WR-01, `gap_closure: true`) subsequently landed and declared `T-06-34`…`T-06-38` and `T-06-39`…`T-06-42` plus a per-plan `T-06-SC`. Those rows are appended below; the pre-existing rows are preserved unchanged and were not re-litigated. The 06-09 delta is the audit's specific focus: the raised-transport path writes exactly one class-only audit row, releases the shared budget slot, and becomes a typed 502 (T-06-39/T-06-40/T-06-41/T-06-42).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| listing text → LLM prompt | Untrusted job-board text (title, company, description) crosses into the model's user turn | Untrusted listing text |
| CV facts → LLM prompt | The user's private CV content crosses into the model's user turn | Private CV content (ids + prose) |
| LLM response → `apply_patch` | Model-produced ids cross into the patch engine before any write | Model output, untrusted-shaped |
| request form (`patch_json`) → compile route | Client-controlled JSON crosses into the patch engine | Untrusted JSON |
| `GET …/cv/pdf` → filesystem | A request selects which artifact's file is served | Integer ids → file path |
| verification findings → `verification_json` | Findings cross into a persisted JSON column | Ids, statuses, hashes |
| compiled PDF → extracted text → checks | Lossy, untrusted extraction crosses into the containment predicates | Extracted text |
| opencode backend → `complete_structured` | A transport failure (raise) crosses into the pipeline | Exception object |
| raised exception → `llm_calls.error` and the log | An exception class name crosses into a persisted row and a log line | Exception class name |
| pipeline failure → generate route | A transport failure decides the HTTP response the client sees | Value / typed refusal |
| operator configuration → route guards | `Settings.tailoring_enabled` decides whether new work happens | Boolean setting |
| `RenderPlan` + patch reasons → HTML preview | Audit/model text crosses back into rendered HTML | Text → HTML |
| `cv_artifact_repo` → Phase 7 attach query | The `ok`-only contract is consumed across a phase boundary | Artifact row |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-06-01 | Tampering | `build_tailoring_parts` / `complete_structured` | high | mitigate | `TAILOR_SYSTEM_PROMPT` is a frozen plain literal with no f-string/`%`/concat (`app/pipeline/tailor.py:108-129`); listing + CV prose travel only in `parts` (`build_tailoring_parts`, `:164-178`) and `system=TAILOR_SYSTEM_PROMPT` is passed verbatim (`:227`); `tools=()` (`:230`); the patch carries ids only. Pinned by the parts-membership / frozen-prompt tests. | closed |
| T-06-02 | Tampering | `apply_patch` | high | mitigate | All-or-nothing validation raises before any plan is built: unknown id per family, duplicate target, cross-entry move, emptied section (`app/domain/cv.py:601-683`), invoked by `apply_patch` (`:813-826`); every emitted bullet is a carried-through source object — `Bullet.text` is never rebuilt (`:699`, `:813-826`). No partial-apply or repair branch exists. | closed |
| T-06-03 | Tampering | LaTeX injection via CV content | high | mitigate | Single `finalize` choke point escapes every interpolated plain `str` exactly once, `Markup` is the only opt-out and the HTML escape filters are removed (`app/latex/env.py:53-85`); no shell-escape is enabled — the engine is invoked with `--untrusted` / `-no-shell-escape` (`app/latex/compile.py:45,246,259`); no `\|safe` use anywhere in `app/web/templates/`. | closed |
| T-06-04 | Tampering | `patch_json` hidden field | high | mitigate | Re-parsed with Pydantic `extra="forbid"` (`app/api/tailoring.py:445`; `TailoringPatch` `app/domain/cv.py:480-492`) and re-grounded by `apply_patch` at compile (`app/pipeline/tailor.py:298`); the schema has no text field that becomes PDF text (`app/domain/cv.py:392-395,480-492`). | closed |
| T-06-05 | Tampering / Information Disclosure | `GET /listings/{id}/cv/pdf` | high | mitigate | Route applies `ok_only=True` (`app/api/tailoring.py:512`) and the `compile_status == "ok"` predicate is applied IN SQL (`app/db/repositories/cv_artifact_repo.py:163-177`); the path is the stored `pdf_path`, resolved and confined under `Settings.artifacts_dir` (`app/api/tailoring.py:516-524`); no request text contributes. | closed |
| T-06-06 | Denial of Service | unbounded LLM spend | high | mitigate | `_reserve` runs BEFORE the request against the purpose-aware rolling-24h read (`app/pipeline/tailor.py:206-221`; `llm_call_repo.calls_since` `app/db/repositories/llm_call_repo.py:221-246`); the shared lock/counter lives in `app/pipeline/rank.py:361-379`; a refusal writes one `budget_exceeded` row and returns without calling (`app/pipeline/tailor.py:212-221`). | closed |
| T-06-07 | Information Disclosure | `verification_json` / logs | medium | mitigate | `extra="forbid"` on `CheckResult`/`VerificationResult` is the type-level redaction control (`app/verify/base.py:31,42`); findings carry ids/status/counts/reasons only — a finding's requirement is never persisted, an offending token is the index form `gap[i]` (`app/verify/plan_checks.py:177,195`); extracted text is a sha256 hash only (`app/verify/text_checks.py:199`); the raised path logs the class name only (`app/pipeline/tailor.py:251,255`). | closed |
| T-06-08 | Tampering | extracted-text containment | high | mitigate | Region-scoped containment excludes each entry's OWN date-like cores, page-number lines physically in the region, and region-local structured strings; every remaining candidate must appear in that region's source facts (`app/verify/numbers.py:232-285`, `app/verify/text_checks.py:82-98`). Pinned by the mutation fixtures. | closed |
| T-06-09 | Tampering | injection residue | high | mitigate | Check 7 reuses the single `INJECTION_PATTERNS` list imported from `app/domain/sanitize.py` (no second list minted); a match is a hard `fail` (`app/verify/text_checks.py:39,101-113`). | closed |
| T-06-10 | Repudiation | blocked-row provenance | medium | mitigate | `verification_json` persists the whole `VerificationResult` plus `verifier_version` and the captured `facts_hash` (`app/pipeline/tailor.py:321-324,407`); `VERIFIER_VERSION` is bumped on every check change (`app/verify/base.py:21-22`). | closed |
| T-06-11 | Information Disclosure | `verification_json` / `compile_log` | medium | mitigate | The extracted text is stored as `extracted_text_hash` only, never as text (`app/verify/text_checks.py:198-199`); `extra="forbid"` on the result types (`app/verify/base.py:31,42`); offending tokens are region ids + digit cores only (`app/verify/numbers.py:275`, `app/verify/text_checks.py:91`). | closed |
| T-06-12 | Denial of Service | `asyncio.to_thread(extract_pdf_text)` | medium | mitigate | The single blocking PDF read runs in a worker thread (`app/pipeline/tailor.py:372`), so a multi-page extraction cannot stall the single worker; an unreadable PDF is a caught value, never a raise (`:373-389`). | closed |
| T-06-13 | Tampering | forged/edited hidden `patch_json` | high | mitigate | Re-parsed with `extra="forbid"` (`app/api/tailoring.py:445`) and re-grounded by `apply_patch` (`app/pipeline/tailor.py:298`); the schema has no text field (`app/domain/cv.py:480-492`), so a forged patch can only reorder/reweight/demote/drop/re-order. | closed |
| T-06-14 | Tampering | stale-patch TOCTOU | high | mitigate | `verify_original_matches` recomputes the semantic `facts_hash` from the loaded store and compares `cv_repo.current_version()` fresh (`app/domain/cv.py:544-561`; `app/api/tailoring.py:460-475`); a mismatch is a 409 refusal that writes no artifact (`:467-475`). | closed |
| T-06-15 | Tampering | forged guard fields | medium | mitigate | The hash is recomputed from the just-loaded facts and the version read fresh, so a forged `base_cv_version_id`/`fact_store_hash` can only make the guard MORE likely to refuse (`app/domain/cv.py:557-560`; `app/api/tailoring.py:460-466`). | closed |
| T-06-16 | Tampering | HTML preview / change log | medium | mitigate | Jinja autoescape only; nothing is marked safe (zero `\|safe` in `app/web/templates/`); bullet text and reasons render as text. | closed |
| T-06-17 | Information Disclosure | the review fragment | low | accept | The fragment renders the user's own CV content and model reasons to the single local user; no third party sees it (PROJECT.md privacy constraint). See AR-06-01. | closed |
| T-06-18 | Information Disclosure / Integrity | blocked-artifact download | high | mitigate | The `ok`-only predicate is applied IN SQL by every download/link accessor (`app/db/repositories/cv_artifact_repo.py:163-177,180-194`), and the route refuses a non-`ok`/absent selection with a 404 (`app/api/tailoring.py:512-524`). A blocked row cannot be served even by artifact id. Pinned by the failure-path suite. | closed |
| T-06-19 | Tampering | PDF path traversal | high | mitigate | The served path is the stored `pdf_path` (or `Settings.artifacts_dir` + integer ids), resolved and `relative_to(root)`-checked; the response filename is built from the two integer ids (`app/api/tailoring.py:516-529`); no path/filename/query parameter contributes. | closed |
| T-06-20 | Tampering | findings fragment | low | mitigate | `_parse_findings` degrades an unparseable blob to `[]` rather than raising (`app/api/tailoring.py:140-167`); `_findings_fragment` `html.escape`s every value (`:272-288`); Jinja autoescape for the page. | closed |
| T-06-21 | Repudiation | artifact history | low | mitigate | Every compile inserts a NEW row (`app/pipeline/tailor.py:443-461`; `app/db/repositories/cv_artifact_repo.py:104-160`); `history_for_listing` returns every row including blocked/failed (`:197-210`) and the page renders it (`app/api/tailoring.py:321,335`), so "which CV was sent" stays answerable. | closed |
| T-06-22 | Denial of Service | oversized/missing PDF file | low | accept | A missing file is a 404, never a 500 (`app/api/tailoring.py:522-524`); the file is served by `FileResponse` without loading it into memory (`:530-534`). Accepted at single-user scale. See AR-06-02. | closed |
| T-06-23 | Tampering | `region_token_report` allow/exclude sets | high | mitigate | Non-entry structured content is excused only in the region whose explicit text physically contains it (`app/verify/numbers.py:211-229,269-274`); exclusions stay region-local, so a novel metric inside an entry region remains a candidate and still fails. Pinned by the `Python 3.12` negative control and `test_a_foreign_date_core_is_not_excluded_in_another_region`. | closed |
| T-06-24 | Denial of Service | check 4 false positive | high | mitigate | The fix removes the fail-closed dead end for ordinary CV content (`AWS S3`, `Python 3`, `ISO 27001`) by excusing region-local structured strings (`app/verify/numbers.py:211-229`) instead of a document-wide union; the metric-containment check still hard-fails on a genuine surplus (`app/verify/text_checks.py:82-98`). | closed |
| T-06-25 | Repudiation | `verifier_version` | low | mitigate | `VERIFIER_VERSION` was bumped to `1.0.1` for this check revision (now `1.0.2` after 06-08) so a persisted outcome traces to the revision that produced it (`app/verify/base.py:21-22`). | closed |
| T-06-26 | Information Disclosure | `verification_json` / `CheckResult.offending` | low | mitigate | `offending` carries region ids and digit cores only (`app/verify/numbers.py:275`, `app/verify/text_checks.py:91`); the extracted text remains a sha256 hash, never stored (`app/verify/text_checks.py:199`). | closed |
| T-06-27 | Spoofing / Repudiation | `ChangeRecord` provenance | high | mitigate | `_validate_patch` grounds op ids against the op family's own id set (bullet ops vs `bullet_ids`, section ops vs `section_ids`, gap/suggestion refs vs the full fact set) before `_build_plan` (`app/domain/cv.py:612-644`), so a change-log entry can only name a real source fact at that family's locus. Pinned by `tests/domain/test_patch_ops.py::test_every_change_record_describes_an_effect_at_the_right_locus`. | closed |
| T-06-28 | Tampering | `patch_json` round trip | medium | mitigate | The compile route re-parses with `extra="forbid"` and re-validates; the tightened per-family grounding makes a forged non-bullet id raise `UnknownIdError` instead of silently no-opping into the persisted `change_log_json` (`app/domain/cv.py:621-644`). | closed |
| T-06-29 | Information Disclosure | `change_log_json` `detail` | low | accept | `detail` carries the model's reason/weight text and is audit/UI-only; no op field becomes PDF text (`app/domain/cv.py:738-751`, pinned by `tests/verify/test_no_free_text_path.py`), so the disclosure surface is the user's own CV audit. See AR-06-03. | closed |
| T-06-30 | Elevation of Privilege / Integrity | `compile_tailored_cv` bypass | high | mitigate | The compile route checks `settings.tailoring_enabled` AFTER the listing check and BEFORE `load_facts`/render/engine/insert (`app/api/tailoring.py:432-455`), so a round-tripped patch POSTed straight at the route cannot bypass the operator off switch. Pinned by `test_the_compile_route_refuses_when_tailoring_is_disabled`. | closed |
| T-06-31 | Tampering | `patch_json` reaching the renderer | high | mitigate | `TailoringPatch` has no field that becomes PDF text (`app/domain/cv.py:392-395,480-492`); 06-06's per-family grounding rejects a non-bullet id (`:621-644`); the generate route re-grounds too (`app/api/tailoring.py:394-401`). | closed |
| T-06-32 | Information Disclosure | refusal fragment | low | mitigate | The refusal is built from the shared skip vocabulary via `_error_fragment`, which `html.escape`s both the reason and the message; no request or fact-store text is echoed (`app/api/tailoring.py:223-229,365,369,375`). | closed |
| T-06-33 | Denial of Service | gating an existing verified download | low | accept | `GET …/cv/pdf` is deliberately NOT gated so turning new work off cannot strand an already-verified artifact; recorded as an explicit prohibition in the route docstring (`app/api/tailoring.py:503-505`). See AR-06-04. | closed |
| T-06-34 | Tampering | `_allowed_for_entry` allowed set | high | mitigate | The entry's location digit cores join only that entry's OWN allowed set, never the excluded set (`app/verify/numbers.py:163-181` at `:175-176`); every exclusion stays region-local, so a fabricated digit in another region remains a candidate. Pinned by the `Python 3.12` negative control and `test_a_foreign_date_core_is_not_excluded_in_another_region`. | closed |
| T-06-35 | Tampering | `_entry_lines` region anchoring | high | mitigate | A region starts only on a line containing BOTH the entry's org AND its title (`app/verify/numbers.py:120-160` at `:147-159`), so a bullet naming a later employer cannot start that employer's region. Pinned by `test_a_bullet_naming_a_later_employer_does_not_bleed_into_its_region` and `test_a_split_header_entry_is_reported_not_found_not_mislocated`. | closed |
| T-06-36 | Denial of Service | check 4 false positive | high | mitigate | The two fixes remove the fail-closed dead end (a digit-bearing location; a bullet naming a later employer) whose only recovery was a fresh tailor that re-ran the same predicate (`app/verify/numbers.py:147-160,175-176`). | closed |
| T-06-37 | Repudiation | `verifier_version` | low | mitigate | `VERIFIER_VERSION` is bumped once to `1.0.2` for the combined CR-01 + CR-02 change (`app/verify/base.py:21-22`), so a persisted outcome traces to the check revision that produced it. | closed |
| T-06-38 | Information Disclosure | `verification_json` / `CheckResult.offending` | low | mitigate | `offending` still carries region ids and digit cores only; the extracted text remains a sha256 hash, never stored (`app/verify/numbers.py:275`, `app/verify/text_checks.py:199`). | closed |
| T-06-39 | Repudiation | `tailor_listing` audit row | high | mitigate | The `except` clause writes exactly one `purpose="tailor"`, `status="error"`, `run_id=None` row for the attempted call before returning `None` (`app/pipeline/tailor.py:243-256`). Pinned by `tests/pipeline/test_tailor_stage.py::test_a_raised_backend_error_still_writes_one_tailor_row_and_returns_none` and `tests/api/test_tailoring_generate.py::test_generate_returns_a_typed_error_and_one_audit_row_when_the_backend_raises`. | closed |
| T-06-40 | Information Disclosure | exception message → `llm_calls.error` / logs | high | mitigate | Only `type(exc).__name__` is recorded and logged — `error=type(exc).__name__` (`app/pipeline/tailor.py:251`) and `log.warning("pipeline.tailor_transport_error", error=type(exc).__name__)` (`:255`); `str(exc)` is never used. Pinned by the route test's `error == "RuntimeError"` assertion (`tests/api/test_tailoring_generate.py:249`). | closed |
| T-06-41 | Integrity / Availability | generate route 500 | high | mitigate | The pipeline returns a value instead of raising (`app/pipeline/tailor.py:256`), so the route reaches its typed 502 `data-error="tailoring_failed"` branch (`app/api/tailoring.py:387-392`); no request becomes a bare 500. Pinned by the route test asserting 502 and the `data-error` value (`tests/api/test_tailoring_generate.py:240-241`). | closed |
| T-06-42 | Denial of Service | leaked in-flight budget slot | medium | mitigate | `finally: await _release()` is retained on the exception path (`app/pipeline/tailor.py:257-258`; `_release` `app/pipeline/rank.py:375-379`), so a transport failure cannot wedge the shared budget. Pinned by the pipeline test's `_in_flight == 0` assertion. | closed |
| T-06-SC | Tampering (supply chain) | npm/pip/cargo installs (06-01…06-09) | high | mitigate | No package installed by any part of this phase: `pyproject.toml` is unchanged across every phase-6 commit (its most recent change is the phase-04 `320e2e2`; `rapidfuzz`/`pypdf`/`pyyaml` predate this phase), no lockfile/manifest edit appears in the phase-6 history, and the Alembic head stays `0004` (`alembic/versions/0004_ranking_config.py`; no `0005` exists). Every plan's `T-06-SC` row declares "this plan installs no package". | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (`high`) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-06-01 | T-06-17 | The review fragment renders the user's own CV content and model reasons — no third party sees it (PROJECT.md privacy constraint; v1 is single-user local, no auth by design). | plan 06-03 | 2026-09-24 |
| AR-06-02 | T-06-22 | A missing/oversized PDF is a 404 (never a 500) and `FileResponse` streams it without loading it into memory; accepted at single-user scale. | plan 06-04 | 2026-09-24 |
| AR-06-03 | T-06-29 | `change_log_json.detail` carries the model's reason/weight text but is audit/UI-only; no op field becomes PDF text, so the disclosure surface is the user's own CV audit. | plan 06-06 | 2026-09-24 |
| AR-06-04 | T-06-33 | The PDF download route is deliberately not gated by `tailoring_enabled` so disabling new work cannot strand an already-verified artifact; it serves only a stored `ok` row. | plan 06-07 | 2026-09-24 |

*Accepted risks do not resurface in future audit runs.*

---

## Threat Flags

The `## Threat Flags` sections of `06-08-SUMMARY.md` and `06-09-SUMMARY.md` both report **"None — no new security-relevant surface."** The SUMMARY files for 06-01…06-07 carry no `## Threat Flags` section (verified by grep: 0 matches each), so they introduce no unregistered flag either. No `unregistered_flag` was raised.

The two most recent gap-closure deltas were checked against the register directly:
- **06-08** (`app/verify/numbers.py`, `app/verify/base.py`): the region-local structured exclusions and the org+title header anchor map onto `T-06-34`/`T-06-35` (and the DoS variants `T-06-36`, provenance `T-06-37`, disclosure `T-06-38`). No new surface.
- **06-09** (`app/pipeline/tailor.py`, `app/api/tailoring.py`): the raised-transport except clause, class-only logging, retained `finally` release and typed 502 map onto `T-06-39`/`T-06-40`/`T-06-41`/`T-06-42`. No table, column, Settings field or migration touched; Alembic head stays `0004`.

---

## Verification Notes (non-blocking)

Hermetic evidence command: `.venv/bin/python -m pytest -q tests/pipeline/test_tailor_stage.py tests/api/test_tailoring_generate.py tests/api/test_tailoring_review.py tests/verify/test_numbers.py tests/verify/test_no_free_text_path.py tests/domain/test_patch_ops.py` → **86 passed** (2026-09-25). This includes the two WR-01 pins (`test_generate_returns_a_typed_error_and_one_audit_row_when_the_backend_raises`, `test_a_raised_backend_error_still_writes_one_tailor_row_and_returns_none`), the CR-01/CR-02 region pins, and `test_no_free_text_path`.

Targeted 06-09 redaction re-check (the audit's stated focus):
- `grep -n "str(exc)\|{exc}\|% exc\|exc!r\|repr(exc)" app/pipeline/tailor.py app/api/tailoring.py` → **no live interpolation**; the sole match is the explanatory comment at `app/pipeline/tailor.py:245`. The exception class name is the only value written to `llm_calls.error` and the log line.
- The 502 refusal body is a fixed sentence (`app/api/tailoring.py:388-392`) — no exception text, no request echo.
- No `|safe`/`Markup` in `_tailoring_review.html` or `tailoring.html`; `Jinja2Templates` defaults to autoescape for HTML (`app/web/template_env.py:17-22`).

Code-review item relevant to an audited surface: `06-REVIEW.md` (2026-09-24) `issues_found` on the 06-05 delta — **not an absent declared mitigation**; the declared controls (T-06-23…T-06-26) are present in the shipped code. The 06-08 and 06-09 gap-closure plans were specifically authored to close CR-01/CR-02 and WR-01 respectively.

Implementation files were read-only during this audit; no file other than this SECURITY.md was written by the auditor.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-25 | 43 (51 declared rows across the nine PLANs) | 43 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-25 (06-01…06-09, including the 06-08 CR-01/CR-02 and 06-09 WR-01 gap-closure rows)
