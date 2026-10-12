---
phase: "07"
slug: "assisted-apply-tracker"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
security_block_on: high
created: "2026-10-12"
---

# Phase 07 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Verification depth: **ASVS L1** (grep-level presence, reinforced with the cited hermetic tests). The register was authored at plan time in the PLAN files of all fourteen plans (07-01…07-14), so per the secure-phase short-circuit (`threats_open: 0`, `register_authored_at_plan_time: true`, `asvs_level: 1`) L1 presence verification is sufficient. `security_block_on = high`.

**Scope audited:** the assisted-apply tracker and its routes (`app/api/applications.py`, `app/api/apply.py`, `app/api/tailoring.py`'s CV-PDF route), the append-only application repository (`app/db/repositories/application_repo.py`), the ok-only artifact access control (`app/db/repositories/cv_artifact_repo.py`), the screening-drafting stage (`app/pipeline/draft.py`), the deterministic grounding checker (`app/verify/screening.py`), the wire-adjacent schema and coercion boundary (`app/domain/schemas/screening.py`, `app/domain/schemas/_coerce.py`, `app/llm/opencode_server.py`), the append-only migration (`alembic/versions/0006_screening_drafts.py`, `0007_screening_draft_warnings.py`), the apply/tracker templates (`app/web/templates/html/apply.html`, `_screening_drafts.html`, `_application_row.html`, `applications_list.html`, `_application_history.html`), the stylesheet source of truth and its guards (`assets/tailwind/input.css`, `static/vendor/app.css`, `tests/test_stylesheet_coverage.py`), and the no-PII JSON allow-list (`tests/db/test_no_pii_columns.py`).

**Register hygiene note:** `T-07-SC` is declared once in each of the fourteen PLAN files with a per-plan scope; there are **47 unique numbered threats** (`T-07-01-01` … `T-07-14-05`) plus the fourteen `T-07-SC` occurrences — **61 declared rows, 48 unique threats**. The fourteen `T-07-SC` rows are merged into one row below (the 05/06 house convention). All fourteen `T-07-SC` rows carry disposition `accept` (the 07 plans do not claim an SC mitigation; the only package use is the already-pinned Tailwind CLI, T-07-13-04).

**Gap-closure re-audit (2026-10-12):** the register was first written against plans 07-01…07-12. Plans **07-13** (Tailwind source/stylesheet reconciliation, `gap_closure: true`) and **07-14** (pure-domain wrapper-unwrap restriction, `gap_closure: true`) subsequently landed and declared `T-07-13-01`…`T-07-13-04`/`T-07-13-SC` and `T-07-14-01`…`T-07-14-05`/`T-07-14-SC`. Those rows are appended below; the pre-existing rows are preserved unchanged and were not re-litigated. Both deltas are low new security surface: 07-13 is a build-artifact/source reconciliation (guards, no runtime path), and 07-14 narrows an existing coercion helper (`"item"`-only) in pure `app/domain` code.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| browser → `/applications/*` | An untrusted form supplies a stage, an artefact id, a note and a next-action date | Untrusted form fields |
| application_repo → `application_events` | The history table is append-only; the repository is the only writer | Event rows (insert only) |
| listing data → apply page | `listing.apply_url` and description are untrusted board text rendered into the page | Untrusted board text |
| model answer → DOM | Model-produced free text is rendered per answer | Model prose |
| clipboard handler → user's browser | The copy button reads rendered answer text | Model prose |
| listing text + CV facts → model | Untrusted board text must reach the model only as user content | Untrusted listing text + private CV content |
| model → stored drafts | Model-produced free text crosses into persisted state and the DOM | Model output, untrusted-shaped |
| query string → tracker read | `stage`, `q`, `view`, `offset` are untrusted; `q` is free text | Untrusted query text |
| request query → artifact selection | `artifact_id` is an untrusted integer choosing which stored row to serve | Integer id → file path |
| listing URL → other listing's artifact | The listing id in the path must scope the selection | Path id vs stored row |
| model response → stored drafts | The model's `answers` list selects which stored rows a write path touches | Untrusted variable-length list |
| model payload → pydantic schema | Untrusted, variable-shape JSON crosses into the wire-adjacent models | Untrusted JSON |
| coercion → grounding | Unwrapped evidence ids remain an unverified claim until re-grounded | Claim → re-grounded ids |
| source stylesheet → committed build artifact | Author-controlled CSS is compiled by a third-party tool into a committed artifact | CSS source → served artifact |
| build toolchain → image | `npm install --no-save` pulls pinned packages at image build | Pinned npm packages |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-07-01-01 | Spoofing | `app/api/applications.py` transition/record | high | mitigate | `applied_at`/`occurred_at` are `datetime.now(UTC)` server-side — the route passes `now=datetime.now(UTC)` (`app/api/applications.py:196,262,306`) and the repository stamps `occurred_at`/`applied_at` from it (`app/db/repositories/application_repo.py:480,494,547,553`); no form field is read for a clock. | closed |
| T-07-01-02 | Tampering | `application_events` triggers | high | mitigate | BEFORE UPDATE/DELETE triggers `RAISE(ABORT, 'application_events is append-only')` (`alembic/versions/0006_screening_drafts.py:72-79`); `application_repo` exposes no update/delete for the table (only `record_application`/`transition_application` insert one event in the same `begin_nested()`). | closed |
| T-07-01-03 | Tampering | `applied` gate | high | mitigate | `read_for_download(ok_only=True)` applies `compile_status == "ok"` IN SQL (`app/db/repositories/cv_artifact_repo.py:190-194`); a blocked/failed artefact returns `None` and the write is refused (`app/db/repositories/application_repo.py:465-474,532-539`). | closed |
| T-07-01-04 | Tampering | status vocabulary | medium | mitigate | `status` validated against `APPLICATION_STATUSES` before any SQL (`app/api/applications.py:186,242`; `app/db/repositories/application_repo.py:456-459,519-522`). | closed |
| T-07-02-01 | Spoofing / Elevation | outbound link | high | mitigate | Plain `<a target="_blank" rel="noopener noreferrer">` (`app/web/templates/html/apply.html:41`); no form POST to a portal; pinned by `tests/api/test_apply_package.py::test_no_submit_surface`. | closed |
| T-07-02-02 | Tampering | untrusted answer/DOM text | medium | mitigate | Jinja autoescape is the one choke point (`app/web/template_env.py:17-22`; `Jinja2Templates` autoescapes HTML); no `|safe` in any phase-07 template. | closed |
| T-07-02-03 | Information disclosure | blocked CV | high | mitigate | The ready block is reachable only when `latest_for_listing(ok_only=True)` returns a record (`app/api/apply.py:211-221`; `app/db/repositories/cv_artifact_repo.py:163-177`). | closed |
| T-07-03-01 | Tampering | `app/pipeline/draft.py` prompt | high | mitigate | `DRAFT_SYSTEM_PROMPT` is a frozen module constant with no f-string/`%`/concat (`app/pipeline/draft.py:83-101`); facts/listing/questions travel only in `parts` (`build_screening_parts`, `:112-126`); `tools=()` (`:183`). | closed |
| T-07-03-02 | Tampering / Repudiation | fabricated screening claims | high | mitigate | `ground_screening_answers` flags unknown evidence ids and novel digit cores (`app/verify/screening.py:102-145`); the warnings are persisted on the row (`app/api/apply.py:372`) and surfaced (`_screening_drafts.html:36-41`). | closed |
| T-07-03-03 | Information disclosure | `evidence_json` / answer text | medium | mitigate | `evidence_json` holds fact/listing ids only and is in the no-PII JSON allow-list (`tests/db/test_no_pii_columns.py:77`); Jinja autoescape for the DOM. | closed |
| T-07-03-04 | Denial of service | unbounded spend | medium | mitigate | Reserve-then-call on the shared rolling-24h ceiling (`app/pipeline/draft.py:149-168`); a refusal writes one row and returns without calling. | closed |
| T-07-04-01 | Injection | `stage` / `view` / `q` | medium | mitigate | `stage`/`view` validated against allow-lists before SQL (`app/db/repositories/application_repo.py:309-314`); `q` is a Python-side casefold substring over ORM-fetched rows, never string-interpolated (`:344-350`). | closed |
| T-07-04-02 | Tampering | derived `overdue` state | low | mitigate | `overdue` is derived at read time from `next_action_at` (`app/db/repositories/application_repo.py:222-226`), never persisted. | closed |
| T-07-04-03 | Information disclosure | rendered free text | medium | mitigate | Jinja autoescape; the full note travels escaped in both the cell text and the `title` attribute (`_application_row.html:21`). | closed |
| T-07-05-01 | XSS | `_screening_drafts.html` | high | mitigate | The answer renders as text in `<p class="answer-text">` (`app/web/templates/html/_screening_drafts.html:32`); no `|safe`, no Python-built HTML, never an input value. | closed |
| T-07-05-02 | Elevation / legal | copy + outbound path | high | mitigate | Copy-only button reads the adjacent `.answer-text` (`_screening_drafts.html:46-49`); no auto-insert; no submit route (`tests/api/test_apply_package.py::test_no_submit_surface`). | closed |
| T-07-05-03 | Tampering | `apply_drafting_enabled` off switch | medium | mitigate | The draft route refuses before any model call when the switch is off (`app/api/apply.py:290-292` via `drafting_skip_reason`; `app/pipeline/draft.py:69-70`; setting `app/config.py:225`). | closed |
| T-07-06-01 | Tampering | `_salvage` / `TOLERATED_SCHEMA_ERRORS` | high | mitigate | Exact allow-list `frozenset({"missing", "int_parsing"})` (`app/llm/opencode_server.py:93`); `_tolerant_validator` substitutes a default only for those types and re-raises otherwise (`:673-687`); pinned by `tests/llm/test_salvage.py`. | closed |
| T-07-06-02 | Denial of service | repeated drafting calls | medium | mitigate | Coercion at the schema boundary prevents the repeat-failure loop that burned a real call per attempt (`app/domain/schemas/screening.py:59-70`; `app/domain/schemas/_coerce.py`). | closed |
| T-07-06-03 | Spoofing / Injection | `DRAFT_SYSTEM_PROMPT` | high | mitigate | The prompt stays a plain literal (`app/pipeline/draft.py:83-101`); untrusted content still travels only in `parts`. | closed |
| T-07-07-01 | XSS | `_screening_drafts.html` | high | mitigate | Warnings render as escaped text (`app/web/templates/html/_screening_drafts.html:37-40`); no `|safe`, no Python-built HTML. | closed |
| T-07-07-02 | Information disclosure | `screening_drafts.warnings_json` | low | accept | The sentences hold fact ids and digit tokens only, never recruiter PII; the JSON allow-list test pins it (`tests/db/test_no_pii_columns.py:77`). See AR-07-01. | closed |
| T-07-07-03 | Repudiation | advisory band wording | medium | mitigate | The band is labelled advisory and never flips `unsupported` (`app/verify/screening.py:137-143`; `_screening_drafts.html:42-44`); it cannot read as a pass/fail guarantee. | closed |
| T-07-08-01 | Open redirect | `RedirectResponse` location | medium | mitigate | The location is the fixed literal `/applications` (`app/api/applications.py:205`); no request-derived value is placed in it. | closed |
| T-07-08-02 | Integrity | refusal branches | high | mitigate | The ok-only applied gate and the no-write refusal behavior are untouched (`app/db/repositories/application_repo.py:462-474`; `app/api/applications.py:198-203`); a refused applied record writes nothing. | closed |
| T-07-08-03 | Tampering | form clock | medium | mitigate | `applied_at` remains stamped server-side (`app/api/applications.py:196`); this route reads no form clock. | closed |
| T-07-09-01 | Broken access control | `read_for_download` by id | high | mitigate | The `ok_only` SQL predicate stays on and `record.listing_id == listing_id` refuses a foreign id as a 404 (`app/api/tailoring.py:676-678`). | closed |
| T-07-09-02 | Path traversal | served `pdf_path` | medium | mitigate | The served path remains the selected row's stored `pdf_path`, resolved and confined under `artifacts_dir` (`app/api/tailoring.py:680-685`); the id only selects a row. | closed |
| T-07-09-03 | Information disclosure | cross-listing download | high | mitigate | The ownership check (`record.listing_id != listing_id`) makes another listing's PDF unreachable through this URL (`app/api/tailoring.py:677`). | closed |
| T-07-10-01 | Tampering / data destruction | `app/api/apply.py::draft_answers` partial path | high | mitigate | The `len(verdicts) < len(questions)` guard returns `drafting_partial` BEFORE `replace_for_listing` (`app/api/apply.py:356-362`), so the listing's DELETE is never reached. | closed |
| T-07-10-02 | Information destruction | `screening_draft_repo.replace_for_listing` | high | mitigate | Unchanged; it is now reachable only on a complete response — the guard sits upstream (`app/api/apply.py:356-364`). | closed |
| T-07-10-03 | Information loss (ad-hoc question text) | `screening_drafts.question_text` | high | mitigate | Ad-hoc rows are seeded by `add_question` (`app/api/apply.py:417-422`) and preserved by the partial guard (`:356-362`). | closed |
| T-07-11-01 | Tampering (XSS) | `_application_row.html` note `<td>`/`title` | low | accept | Jinja autoescape remains the only escaping; no `|safe` is introduced, and the full note stays escaped in both the cell text and the `title` attribute (`app/web/templates/html/_application_row.html:21`). See AR-07-02. | closed |
| T-07-11-02 | Denial of service (layout) | `.tracker-note` / `.tracker-actions` | low | mitigate | A bounded column `max-width` plus `overflow-wrap:anywhere` (`assets/tailwind/input.css:719-729`) stops a long unbroken token from forcing unbounded column width. | closed |
| T-07-12-01 | Tampering / schema laundering | `TOLERATED_SCHEMA_ERRORS` (`app/llm/opencode_server.py:93`) | high | mitigate | Left byte-unchanged: `frozenset({"missing", "int_parsing"})` — no `list_type` (`app/llm/opencode_server.py:93`). | closed |
| T-07-12-02 | Data integrity (fabricated evidence) | `ScreeningAnswer.evidence_ids` coercion | medium | accept | The unwrap admits only a *shape*, never a value; `app/verify/screening.py` still re-grounds every id byte-exact against `iter_fact_ids` (`:112-119`). See AR-07-03. | closed |
| T-07-12-03 | Availability | `POST /listings/{id}/apply/draft` | low | mitigate | The fix turns a deterministic 502 into a persisted result; no new write path or bypass — the CR-01 partial guard is untouched (`app/api/apply.py:356-362`). | closed |
| T-07-12-04 | Spoofing (contract weakening) | `extra="forbid"` on `ScreeningDraftResponse` / `ScreeningAnswer` | high | mitigate | `extra="forbid"` on both models (`app/domain/schemas/screening.py:32,55`); only a single-key `"item"` wrapper Mapping is unwrapped — a multi-key mapping, an unknown key and a scalar still raise (`app/domain/schemas/_coerce.py:38-45`). | closed |
| T-07-13-01 | Tampering (unstyled/incorrect UI shipped) | `Dockerfile:19` build vs committed `static/vendor/app.css` | high | mitigate | The byte-identity guard `test_the_committed_stylesheet_is_the_build_of_its_source` (`tests/test_stylesheet_coverage.py:232-265`) plus the Node-free source-coverage guard (`:170-189`); both green (10 passed, not skipped). | closed |
| T-07-13-02 | Tampering (artifact hand-edit masquerading as source) | `static/vendor/app.css` | high | mitigate | The byte-identity guard makes any hand-edit a test failure (`tests/test_stylesheet_coverage.py:260-265`); the source-coverage guard fails when a rule is dropped from `input.css`. | closed |
| T-07-13-03 | Repudiation (silently weakened verification) | `tests/test_stylesheet_coverage.py` | medium | mitigate | Fail-closed: it emits a visible `pytest.skip` naming the arming command when it cannot build (`:242-247`), never a silent pass; the Node-free source guard runs in both environments (`:170-189`). | closed |
| T-07-13-04 | Supply chain (package install) | `npm install --no-save tailwindcss@4.3.3 @tailwindcss/cli@4.3.3` | high | accept | Already the Dockerfile-pinned build dependencies (`Dockerfile:14-15`); no manifest/lockfile created; `node_modules/` gitignored. See AR-07-04. | closed |
| T-07-14-01 | Spoofing (contract weakening) | `unwrap_single_key_mapping` — accepting any single key | high | mitigate | Unwrap restricted to the literal `WRAPPER_KEY` (`"item"`); a Mapping with any other key is refused (`app/domain/schemas/_coerce.py:38-45`). | closed |
| T-07-14-02 | Tampering (schema laundering) | `TOLERATED_SCHEMA_ERRORS` (`app/llm/opencode_server.py:93`) | high | mitigate | Left byte-unchanged (`app/llm/opencode_server.py:93`); the fix is placed at the coercion boundary instead. | closed |
| T-07-14-03 | Denial of service | `unwrap_single_key_mapping` loop | low | mitigate | Bound by `inner is value`, so a self-referential Mapping terminates (`app/domain/schemas/_coerce.py:42-43`). | closed |
| T-07-14-04 | Data integrity (fabricated evidence) | coerced `evidence_ids` on `ScreeningAnswer` / `GapFinding` / `Suggestion` | medium | accept | The helper admits only a *shape*, never a value; `app/verify/screening.py` re-grounds every id byte-exact (`:112-119`). See AR-07-03. | closed |
| T-07-14-05 | Repudiation (false prose guarantee) | `_coerce.py` / `screening.py` / `cv.py` docstrings | medium | mitigate | The `_coerce.py` module docstring states both failure routes (`app/domain/schemas/_coerce.py:9-12`) and `coerce_mapping_list`'s docstring states its `extra="forbid"` route (`:72-74`). | closed |
| T-07-SC | Tampering (supply chain) | package installs (07-01…07-14) | high | accept | No package installed by any part of this phase: `pyproject.toml`/`requirements` are untouched and the Alembic head is `0007` (07-07's additive column migration). The only install is the already-pinned Tailwind CLI at image build (T-07-13-04). See AR-07-04. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (`high`) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-07-01 | T-07-07-02 | `screening_drafts.warnings_json` holds the checker's human sentences — fact ids and digit tokens only, never recruiter PII; allow-listed in `tests/db/test_no_pii_columns.py:77`. | plan 07-07 | 2026-10-06 |
| AR-07-02 | T-07-11-01 | The tracker note is the user's own stored/listing text rendered through the one autoescape choke point; no `|safe` is introduced, so the residual risk is the single local user reading their own data. | plan 07-11 | 2026-10-12 |
| AR-07-03 | T-07-12-02, T-07-14-04 | The single-key wrapper unwrap admits only a *shape*, never a value; `app/verify/screening.py:112-119` still re-grounds every evidence id byte-exact, so a wrapped fabricated id is dropped/flagged exactly as before. | plans 07-12 / 07-14 | 2026-10-12 |
| AR-07-04 | T-07-13-04, T-07-SC | Only the already-pinned Tailwind CLI (`tailwindcss@4.3.3`, `@tailwindcss/cli@4.3.3`) is used at image build with `--no-save`; no manifest or lockfile is created and no runtime dependency is added. | plans 07-11 / 07-13 | 2026-10-12 |

*Accepted risks do not resurface in future audit runs.*

---

## Threat Flags

The `## Threat Flags` sections of `07-06-SUMMARY.md`, `07-07-SUMMARY.md` and `07-09-SUMMARY.md` each report **"None — no new security-relevant surface."** The SUMMARY files for 07-01…07-05, 07-08, 07-10…07-14 carry no `## Threat Flags` section (verified by grep: 0 matches each), so they introduce no unregistered flag either. No `unregistered_flag` was raised.

The two most recent gap-closure deltas were checked against the register directly:
- **07-13** (`assets/tailwind/input.css`, `static/vendor/app.css`, `tests/test_stylesheet_coverage.py`): the source/artifact reconciliation and its byte-identity + source-coverage guards map onto `T-07-13-01`/`T-07-13-02`/`T-07-13-03` and the supply-chain `T-07-13-04`/`T-07-13-SC`. No table, column, Settings field or migration touched; Alembic head stays `0007`.
- **07-14** (`app/domain/schemas/_coerce.py`, `screening.py`, `cv.py`): the literal-key-only unwrap and the bounded loop map onto `T-07-14-01`/`T-07-14-03`, the untouched allow-list onto `T-07-14-02`, and the re-grounding onto `T-07-14-04`. Pure-domain, stdlib-only (no I/O, `tests/test_import_discipline.py` green); no runtime endpoint added.

---

## Verification Notes (non-blocking)

Hermetic evidence command (provisioned Python 3.13.16 interpreter, since the sandbox `.venv` is a broken 3.14 venv):

`.venv/bin/python -m pytest -q tests/db/test_application_events.py tests/api/test_applications_tracker.py tests/api/test_apply_package.py tests/api/test_cv_pdf_route.py tests/api/test_apply_package_warnings.py tests/api/test_apply_draft_errors.py tests/verify/test_screening.py tests/llm/test_salvage.py tests/db/test_no_pii_columns.py tests/test_import_discipline.py tests/domain/test_coerce.py tests/pipeline/test_draft_stage.py tests/test_stylesheet_coverage.py` → **156 passed** (2026-10-12).

- `tests/test_stylesheet_coverage.py` was re-run with `-v` and all 10 tests **passed** (not skipped): `node` and the pinned Tailwind CLI are present, so the byte-identity guard (T-07-13-01/02) is genuinely armed and green.
- `grep -n "|safe" app/web/templates/html/{apply,_screening_drafts,_application_row,applications_list,_application_history}.html` → **no live `|safe`** in any phase-07 template. The only `|safe` in the tree is `tailoring.html:47` on `draft_review_html` — server-rendered finished HTML from a validated patch, a Phase 6 surface outside this register (documented in the 06-SECURITY.md scope).
- The apply/tracker/CV-PDF routes all declare the identity seam (`user: User = Depends(current_user)`) and `tests/test_auth_seam.py` is green.

Implementation files were read-only during this audit; no file other than this SECURITY.md was written by the auditor.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-12 | 48 (61 declared rows across the fourteen PLANs) | 48 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-12 (07-01…07-14, including the 07-13 Tailwind source/artifact and 07-14 wrapper-unwrap gap-closure rows)
