---
phase: 05-ranking-core-value
verified: 2026-09-24T11:04:20Z
status: passed
score: 55/55 observable truths verified (0 present-but-behavior-unverified; 1 human item outstanding — in-browser confirmation of the 05-12 detail Save/Hide fix)
covered_files:

  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - .planning/phases/05-ranking-core-value/05-01-PLAN.md
  - .planning/phases/05-ranking-core-value/05-01-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-02-PLAN.md
  - .planning/phases/05-ranking-core-value/05-02-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-03-PLAN.md
  - .planning/phases/05-ranking-core-value/05-03-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-04-PLAN.md
  - .planning/phases/05-ranking-core-value/05-04-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-05-PLAN.md
  - .planning/phases/05-ranking-core-value/05-05-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-06-PLAN.md
  - .planning/phases/05-ranking-core-value/05-06-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-07-PLAN.md
  - .planning/phases/05-ranking-core-value/05-07-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-08-PLAN.md
  - .planning/phases/05-ranking-core-value/05-08-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-09-PLAN.md
  - .planning/phases/05-ranking-core-value/05-09-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-10-PLAN.md
  - .planning/phases/05-ranking-core-value/05-10-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-11-PLAN.md
  - .planning/phases/05-ranking-core-value/05-11-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-12-PLAN.md
  - .planning/phases/05-ranking-core-value/05-12-SUMMARY.md
  - .planning/phases/05-ranking-core-value/05-UAT.md
  - .planning/phases/05-ranking-core-value/05-SECURITY.md
  - alembic/versions/0004_ranking_config.py
  - app/api/events.py
  - app/api/health.py
  - app/api/listings.py
  - app/api/settings.py
  - app/config.py
  - app/cv/factstore.py
  - app/db/models.py
  - app/db/repositories/llm_call_repo.py
  - app/db/repositories/queue_repo.py
  - app/db/repositories/ranking_config_repo.py
  - app/db/repositories/run_repo.py
  - app/db/repositories/score_repo.py
  - app/domain/rubric.py
  - app/domain/schemas/ranking.py
  - app/main.py
  - app/pipeline/rank.py
  - app/pipeline/run.py
  - app/web/routes.py
  - app/web/templates/html/_action_forms.html
  - app/web/templates/html/_detail_actions.html
  - app/web/templates/html/_health_strip.html
  - app/web/templates/html/_listing_row.html
  - app/web/templates/html/listing_detail.html
  - app/web/templates/html/queue.html
  - app/web/templates/html/queue_list.html
  - app/web/templates/html/settings.html
  - assets/tailwind/input.css
  - docs/probes/2026-09-21-cv-tex-spike.md
  - docs/probes/README.md
  - static/vendor/app.css
  - tests/api/test_health.py
  - tests/api/test_listing_detail.py
  - tests/api/test_listing_events.py
  - tests/api/test_queue_excluded.py
  - tests/api/test_queue_ranked.py
  - tests/api/test_settings_page.py
  - tests/cv/test_factstore.py
  - tests/db/test_queue_page.py
  - tests/pipeline/test_rank_optional.py
  - tests/test_cv_tex_spike_docs.py

covered_digest: "v1:sha256:2138d371e274761a5bf062ba958fd2b384f88ae84c0b80d25ca36f67cdbd4495"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 49/49 observable truths verified (2 human items outstanding)
  gaps_closed:
    - "G-05-8 (the detail page's Save/Hide silent no-op) — closed by plan 05-12. The two controls now have ONE definition in `_action_forms.html`; the detail section `_detail_actions.html` is its own swap root (`<section id=\"detail-actions\">`, included by `listing_detail.html`); the events route reads an allow-listed `surface` field and returns the detail section (with the inverse label and the projected badge) for `surface=detail`. The failure mode — `hx-target=\"#listing-row-{id}\"` naming an element the detail page never renders — is structurally impossible: `listing_detail.html` and `_detail_actions.html` contain zero `listing-row-` occurrences (grep). Seven new tests pin it; all pass."
    - "Human item (a) from the prior pass — the queue pager's in-browser behaviour — is now human-CONFIRMED, not merely code-verified. `05-UAT.md` test 7 (`result: pass`, recorded 2026-09-24T09:38:23Z in commit 0628a9a — AFTER the prior verification's 2026-09-23T16:45:29Z) records the user: \"yup going back and forth works, pass\", and accepts the two embedded audit decisions (no `show:top`; boundary controls omitted rather than disabled) as-is."
    - "The two documented 05-12 deviations are confirmed non-behavioural: (1) the Task-3 acceptance grep `|safe` == 0 was unsatisfiable because a pre-existing negative assertion (`assert \"|safe\" not in response.text`) already lived in the file the task forbade editing — the intent (no safe-marking filter ADDED) holds; (2) the plan named a `listing_detail.html` file-header sentence that did not exist, so one was added stating the inline-swap posture. Neither changes rendered output."
  gaps_remaining: []
  regressions:
    - "Carried (not new): round-2 WR-01 — `runs.html` still stringifies the nested `reason_counts['ranking']` marker as a raw Python dict repr on `/runs/{id}` (`runs.html:106-112`). Run detail is Phase 2's RUN-03/RUN-04 surface, so this remains a ⚠️ Warning, not a phase-5 gap."
    - "Carried (not new): round-2 WR-02 — `rank.ranking_skip_reason()` still catches only `(CvFactStoreError, OSError)` while its docstring claims totality. Exotic corrupt-input path; the run still completes. ⚠️ Warning."

advisory:

  - finding: "The score-sort scan truncates at SCORE_SORT_SCAN_LIMIT=5000 rows; `page.total` (and the pager's `page_count`) under-reports past that, and `_DISMISS_LIMIT=10_000` can never trip."
    category: architectural
    reason: "User-visible only at >5 000 matching listings; explicitly accepted at personal scale. Pre-existing (unchanged by 05-11/05-12). 05-REVIEW.md round-3 CR-01; no failing named test."
    evidence_status: "none beyond source reading"
  - finding: "`?min_score=nan` (or `inf`) passes `_float_or_none`; `row.total_score >= nan` is False for every scored row, so all scored listings disappear."
    category: other
    reason: "Accepted-by-design known limitation, pinned by the strict-xfail sentinel tests/api/test_queue_ranking_adversarial.py::test_nan_min_score_degrades_to_no_threshold."
    evidence_status: "named xfail sentinel; excluded from the default lane by design"
  - finding: "`read_weights` accepts a stored negative weight."
    category: other
    reason: "Accepted-by-design, pinned by the strict-xfail sentinel tests/pipeline/test_rank_adversarial.py."
    evidence_status: "named xfail sentinel; excluded from the default lane by design"
  - finding: "`jobsearch.db` sits untracked at the repo root and is not gitignored."
    category: security
    reason: "Local SQLite DB that can contain CV-derived scores and rationales. Repo hygiene outside the phase file list."
    evidence_status: "`git status` shows `?? jobsearch.db`; no failing test"
  - finding: "The shipped default DB URL points at an absolute `/data/jobsearch.db`, so the app cannot boot from the repo root; the UI audits this phase were therefore code-only (no dev server/screenshots)."
    category: other
    reason: "Deployment environment default vs the Docker volume path; PLAT-01 (Docker Compose) is Phase 1 and unaffected. Not a phase-5 must-have, but it is why the UI evidence is code-only."
    evidence_status: "05-UI-REVIEW.md method note; no failing test"
  - finding: "Two user-deferred UAT follow-ups remain unimplemented: visa/work-authorisation signals when the JD states them, and rendering the Requirement-fit list as a table."
    category: other
    reason: "Explicitly deferred by the user in 05-UAT.md (`Deferred Follow-Ups`), not covered by any later phase's stated goal. Non-blocking."
    evidence_status: "deferred by user; no failing test"
human_verification:

  - test: "Confirm the 05-12 detail Save/Hide fix in a browser. Boot the app against a real DB, open any job detail page, click Save, then click Hide."
    expected: "The `#detail-actions` section re-renders in place on the click: the button flips to its inverse label (Save→Unsave, Hide→Unhide), the `★ saved` / `hidden` badge appears, no full-page reload occurs, and no `htmx:targetError` is logged in the browser console. The `View saved jobs` link is present and goes to `/?saved=1`."
    why_human: "Every operative clause is test-pinned — the page renders the `#detail-actions` target (`test_detail_action_forms_target_the_detail_section`), the route returns the detail section with `Unsave` for `surface=detail` (`test_a_detail_surface_save_swaps_the_detail_actions_fragment`), the saved badge renders (`test_detail_saved_listing_shows_the_saved_badge`), and htmx is loaded (`base.html`). But the actual DOM swap is a browser-level behaviour that no automated test exercises (the project has no browser test harness), and the project's own 05-12-SUMMARY marks coverage item D2 `human_judgment: true`, routing \"the browser-level visual swap ... to end-of-phase UAT\". UAT test 8 has not been re-run since the fix. The root cause is closed by automated evidence; this is the residual 10-second visual confirmation."
---

# Phase 5: Ranking — CORE VALUE — Verification Report

**Phase Goal:** One ranked, explained queue: every surviving listing scored against the user's CV with named factors, stored sub-scores, a grounded rationale, and named gaps.
**Verified:** 2026-09-24T11:04:20Z
**Status:** human_needed
**Re-verification:** Yes — round 4, after gap-closure plan 05-12 (gap G-05-8; rounds 1–3 and the round-3 review fix are prior evidence)

## Goal Achievement

### Success Criteria (the ROADMAP contract)

| # | Success criterion | Status | Evidence (independently checked) |
| --- | --- | --- | --- |
| 1 | Browse ranked jobs; every listing scored against the CV using named, inspectable factors; per-factor sub-scores stored; total computed in code | ✓ VERIFIED | Runtime: `rubric.FACTORS == ('skills','seniority','domain','location','evidence','compensation')`, `RUBRIC_VERSION == 'v1'`; `score_repo._factor_payload({'skills':0.0}) == {'skills':0.0}`, `{'skills':-1.0} == {}` (present zero ≠ absent); `weighted_total({}, equal) → None`, all-zero weights → `None`, `{'skills':1.0,'domain':0.0} → 0.5`. Queue total computed at read time in `queue_repo._enrich` via `rubric.weighted_total`. |
| 2 | Re-running ranking gives the same listing a stable, absolute score — never a relative ranking of a batch | ✓ VERIFIED | One `complete_structured` call per listing (`rank.py`); `tests/pipeline/test_rank_stage.py::test_prompt_contains_exactly_one_listing` and `::test_absolute_score_is_stable_across_runs` pass (38 focused rank tests green). |
| 3 | User can adjust factor weights from the UI and see rankings re-derive without a new LLM call | ✓ VERIFIED | `POST /settings/weights`; read-time recompute; `tests/api/test_ranking_weights.py::test_weight_change_writes_zero_llm_calls` passes. |
| 4 | Opening a job detail shows a rationale grounded in stored evidence plus a requirement-by-requirement fit breakdown with named gaps | ✓ VERIFIED | `GET /listings/{id}` renders `score.rationale`, the factor table, and `req-met`/`req-partial`/`req-gap`; the grounding filter drops fabricated ids (`test_rationale_ids_are_cv_fact_ids`). |
| 5 | Once the per-run or per-day LLM spend cap is reached, further calls are refused before the call is made | ✓ VERIFIED | `rank._reserve`/`_cap_hit` gate before `rank_listing` (`rank.py:347-451`); `tests/pipeline/test_rank_caps.py::test_cap_refuses_before_the_call` and `::test_rolling_24h_cap_is_enforced` pass. |

### Observable Truths

The prior pass verified 49 observable truths (rounds 1–3). This round re-verified them at the level of: full default-lane suite green (`1093 passed, 14 deselected, 2 xfailed`), targeted runtime checks of the core rubric/score/cap invariants, and confirmation that the 05-12 diff is isolated to the detail-action path (it touches no ranking, rubric, schema, persistence, cap, queue-ordering or pager file — see `git diff --stat 1cc6171 HEAD`). Truths 1–49 stand; the 05-12 delta adds truths 50–55.

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1–49 | Prior-pass observable truths (rubric identity; `weighted_total` totality; schema bounds; stored sub-scores incl. present-zero convention; grounding filter; one-call-per-listing isolation; cap refusal; D-94 skip paths; single-flight lifecycle; migration 0004 / head 0004; detail-page render; queue score ordering; unranked badge; `min_score`; weights save; strip one-population + honest degrade; five-state strip; `_finish` sole writer of the ranking marker; non-UTF-8 fact store; 05-10 CV disclosure trio; 05-11 two-way pager + position line + server-fixed limit + predicate reset + accessor totality + no new plumbing) | ✓ VERIFIED | Re-verified this round: full suite green; runtime rubric/score checks above; `alembic heads` → `0004 (head)`; targeted suites `tests/pipeline/test_rank_caps.py test_rank_stage.py test_ranking_weights.py test_rank_optional.py tests/cv/test_factstore.py` → 38 passed; `tests/test_stylesheet_coverage.py` → 5 passed. No 05-12 file overlaps any of them. |
| 50 | 05-12: Clicking Save/Hide on the detail page produces a visible change in place — controls re-render with the inverse label, the saved/hidden indicator appears, no `htmx:targetError`, no silent no-op, no manual reload | ✓ VERIFIED | `test_a_detail_surface_save_swaps_the_detail_actions_fragment` (POST `surface=detail` → 200, body has `<section id="detail-actions"`, has `Unsave`, no queue row, one `save` event with `context_json == {"surface":"detail"}`); `test_detail_saved_listing_shows_the_saved_badge` (`#detail-saved-badge` + `badge-saved`); htmx loaded via `base.html:9`. Browser-level DOM swap → the one human item. |
| 51 | 05-12: Every detail Save/Hide control resolves its htmx target inside the detail page's own markup (`#detail-actions`), never the queue-only row id; the queue row still targets its own `listing-row-{id}` and its swap is unchanged | ✓ VERIFIED | `_detail_actions.html:25` sets `target_id = "detail-actions"`; `listing_detail.html`/`_detail_actions.html` contain 0 `listing-row-` occurrences; `_listing_row.html:72` sets `target_id = "listing-row-" ~ row.id`; `test_detail_action_forms_target_the_detail_section` + `test_a_detail_surface_save_is_visible_on_the_queue` (queue row target preserved) pass. |
| 52 | 05-12: The two controls have exactly ONE definition, shared by both surfaces, so a target/field/label change cannot drift | ✓ VERIFIED | `grep -c 'include "html/_action_forms.html"'` → 1 in each of `_listing_row.html` and `_detail_actions.html`; both files carry 0 inline `<form>`; `_action_forms.html` holds `name="surface"` ×2 and `hx-target="#{{ target_id }}"` ×2. |
| 53 | 05-12: The detail page tells the user where saved jobs live — a link to the existing saved view (`GET /?saved=1`) rendered on the page | ✓ VERIFIED | `_detail_actions.html` renders `id="detail-saved-link" href="/?saved=1"` + `View saved jobs`; `test_detail_offers_the_saved_jobs_affordance` passes. |
| 54 | 05-12: Both surfaces post one event vocabulary to the one append-only endpoint; the origin is an allow-listed machine fact (`surface` = `queue`/`detail`), and any other value falls back to `queue` rather than selecting an unknown template or reaching the audit log | ✓ VERIFIED | `events.py`: `ACTION_SURFACES = ("queue","detail")`, `DEFAULT_SURFACE = "queue"`, normalisation before any branch, `context={"surface": surface}`; `test_an_unknown_surface_falls_back_to_the_queue_row` (surface=`evil` → queue row, `context_json == {"surface":"queue"}`) passes. |
| 55 | 05-12: The interaction posture is deliberate — inline htmx swap through the same endpoint, with no new route, endpoint, JS, polling/SSE, CDN asset, history integration or safe-marking filter | ✓ VERIFIED | `events.py` has exactly 1 route decorator (the existing POST); `git diff --name-only 1cc6171 HEAD` has no `.js`; 0 `hx-push-url`/`hx-history`/`hx-boost` in `app/`; 0 `|safe` added; `test_no_cdn.py` + `test_stylesheet_coverage.py` pass. |

**Score:** 55/55 observable truths verified (0 present-but-behavior-unverified; 1 human item outstanding — see Human Verification Required).

### Deferred Items

None. No later milestone phase's goal or success criteria covers a leftover must-have. The two UAT follow-ups (visa signals, Requirement-list-as-table) are explicitly user-deferred, not roadmap-deferred (recorded under Advisory).

### Advisory (New Scope, Unevidenced)

Re-verification scan. Carried-forward or new non-blocking findings with no deterministic failing test; none is a must-have truth.

| # | Finding | Category | Why Advisory |
| --- | ------- | -------- | ------------ |
| 1 | Score-sort scan cap 5000 truncates the default queue; `page.total` under-reports; `_DISMISS_LIMIT=10 000` unreachable (05-REVIEW.md CR-01) | architectural | Pre-existing; explicitly accepted at personal scale; no failing named test. |
| 2 | `?min_score=nan`/`inf` hides every scored listing | other | Accepted-by-design: strict-xfail sentinel excluded from the default lane. |
| 3 | `read_weights` accepts a negative stored weight | other | Accepted-by-design: strict-xfail sentinel. |
| 4 | `jobsearch.db` untracked and not gitignored | security | Repo hygiene outside the phase file list; no failing test. |
| 5 | Default DB URL is absolute `/data/...`, so the app cannot boot from the repo root; UI evidence is code-only | other | Deployment-env default vs Docker volume; PLAT-01 unaffected; not a phase-5 truth. |
| 6 | Two user-deferred UAT follow-ups: visa/work-authorisation signals; Requirement-fit list as a table | other | Explicitly deferred by the user; not covered by a later phase's goal. |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/domain/rubric.py` | pure six-factor rubric + code-side total | ✓ VERIFIED | `FACTORS` six in order; `RUBRIC_VERSION="v1"`; `weighted_total` runtime-checked |
| `app/domain/schemas/ranking.py` | top-level-scalar response, no total | ✓ VERIFIED | six bounded scalars + `RequirementFit` |
| `app/db/models.py` `RankingConfig` | singleton weights row | ✓ VERIFIED | `id=1` CHECK |
| `alembic/versions/0004_ranking_config.py` | additive `ranking_config`, head 0004 | ✓ VERIFIED | `alembic heads` → `0004 (head)` |
| `app/db/repositories/score_repo.py` | the `scores` writer | ✓ VERIFIED | zero/absent convention runtime-checked |
| `app/db/repositories/run_repo.py` | `RunSummary` + `_ranking_marker` + `ranking_state` | ✓ VERIFIED | `_optional_int` positive-only; `_ranking_marker` total |
| `app/db/repositories/queue_repo.py` | score ordering + threshold + four derived page accessors | ✓ VERIFIED | `tests/db/test_queue_page.py`; untouched by 05-12 |
| `app/pipeline/rank.py` | `RANK_SKIP_*` + `ranking_skip_reason` + `ranking_in_progress` + `start_ranking_task` | ✓ VERIFIED | all present; `ranking_skip_reason` totality is a Warning (WR-02) |
| `app/cv/factstore.py` | total `fact_store_report(path)` | ✓ VERIFIED | class-name-only error |
| `app/api/events.py` | `ACTION_SURFACES`/`DEFAULT_SURFACE`, `DETAIL_ACTIONS_TEMPLATE`, allow-listed `surface` read, detail-fragment return, surface-aware error fragment | ✓ VERIFIED | present; 1 route decorator only; `ACTION_CONTEXT` gone |
| `app/web/templates/html/_action_forms.html` | the single Save/Hide form definition (new) | ✓ VERIFIED | `name="surface"` ×2, `hx-target="#{{ target_id }}"` ×2, no new class token |
| `app/web/templates/html/_detail_actions.html` | `#detail-actions` swap root + badges + saved link (new) | ✓ VERIFIED | `target_id = "detail-actions"`, 3 badge/link ids, 0 `listing-row-`, 0 `class="detail-"` |
| `app/web/templates/html/listing_detail.html` | includes `_detail_actions.html`; no inline forms | ✓ VERIFIED | 0 `<form>`; 0 `listing-row-`; inline-swap header paragraph added (deviation 2) |
| `app/web/templates/html/_listing_row.html` | includes `_action_forms.html` with queue target/surface | ✓ VERIFIED | `target_id = "listing-row-" ~ row.id` preserved |
| `app/web/templates/html/queue_list.html` + `queue.html` | 05-11 pager + five-state strip | ✓ VERIFIED | untouched by 05-12 |
| `app/web/templates/html/settings.html` + `_health_strip.html` | 05-10 CV disclosure | ✓ VERIFIED | untouched by 05-12 |
| `docs/probes/*` | promotion step + container path | ✓ VERIFIED | pinned by `tests/test_cv_tex_spike_docs.py` |
| `static/vendor/app.css` + `assets/tailwind/input.css` | pager rules (05-11) | ✓ VERIFIED | NOT modified by 05-12 (prohibition held) |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `_detail_actions.html` `hx-post` | `POST /listings/{id}/events` → `event_repo.append_event` → `read_row` → `_detail_actions.html` re-render → `#detail-actions` outerHTML swap | `surface=detail` allow-listed branch | ✓ WIRED | `test_a_detail_surface_save_swaps_the_detail_actions_fragment` |
| `_detail_actions.html` saved-view link | `GET /?saved=1` → `parse_queue_query(saved=True)` → `read_queue` `saved_predicate()` | existing queue filter | ✓ WIRED | `test_detail_offers_the_saved_jobs_affordance` |
| `surface` form field | `ACTION_SURFACES` → returned template AND `listing_events.context_json` | allow-list normalisation | ✓ WIRED | `test_an_unknown_surface_falls_back_to_the_queue_row` |
| `_action_forms.html` | included by `_listing_row.html` (queue) and `_detail_actions.html` (detail) | one definition, two surfaces | ✓ WIRED | grep ×1 each; queue target preserved |
| `app/pipeline/rank.py` grounding filter | `score_repo.upsert_score` | `iter_fact_ids` check before persist | ✓ WIRED | `test_rationale_ids_are_cv_fact_ids` |
| `QueuePage.offset/limit/total` | pager accessors → `queue_list.html` | pure derivation → rendered control/URL | ✓ WIRED | `tests/db/test_queue_page.py` |
| `queue_repo._enrich` | `ranking_config_repo.read_weights` + `rubric.weighted_total` | read-time total | ✓ WIRED | weights read once per page |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `_detail_actions.html` badges | `row.saved` / `row.hidden` | `listing_events` fold via `read_row` (the same projection the queue uses) | Yes | ✓ FLOWING |
| `_detail_actions.html` action URL | `action_url` | route `row.id` + `queue_query` predicate set | Yes | ✓ FLOWING |
| `_listing_row.html` score badge | `row.total_score` | newest `scores.factor_scores_json` → `weighted_total` under live weights | Yes | ✓ FLOWING |
| `listing_detail.html` factor table / requirements | `row.factor_scores` / `score.requirements` | stored score row + `ranking_config`; CV-grounded `gaps_json` | Yes | ✓ FLOWING |
| `queue_list.html` pager | `page.has_prev`/`prev_offset`/`page_index`/`page_count` | `read_queue`'s `offset`/`limit`/`total`/`rows` | Yes | ✓ FLOWING |
| `_health_strip.html` / `settings.html` / `/health` `cv` | `cv.available`/`cv.path` | `fact_store_report` over `settings.cv_dir`/`CV_FILENAME` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full hermetic default lane | `.venv/bin/python -m pytest -q` | **1093 passed, 14 deselected, 2 xfailed** (199.13s) | ✓ PASS |
| 05-12 targeted suites | `pytest -q tests/api/test_listing_events.py tests/api/test_listing_detail.py tests/test_stylesheet_coverage.py tests/test_no_cdn.py` | **39 passed** (40.85s) | ✓ PASS |
| Core ranking suites | `pytest -q tests/pipeline/test_rank_caps.py tests/pipeline/test_rank_stage.py tests/api/test_ranking_weights.py tests/pipeline/test_rank_optional.py tests/cv/test_factstore.py` | **38 passed** | ✓ PASS |
| 05-12 acceptance greps | `include "html/_action_forms.html"` ×1 each; `target_id = "detail-actions"` ×1; `name="surface"` ×2; `hx-target="#{{ target_id }}"` ×2; `<form>` 0 in both detail files; `ACTION_CONTEXT` 0 | as expected | ✓ PASS |
| Detail target isolation | `grep -c "listing-row-" listing_detail.html _detail_actions.html` | 0 / 0 | ✓ PASS |
| Queue target preserved | `grep -c 'target_id = "listing-row-" ~ row.id' _listing_row.html` | 1 | ✓ PASS |
| Migration head | `.venv/bin/python -m alembic heads` | `0004 (head)` | ✓ PASS |
| Rubric identity + totality | inline python | `FACTORS` six in D-82 order, `v1`; `{} → None`, all-zero weights → `None`, partial → `0.5` | ✓ PASS |
| Score zero/absent convention | inline python | `{'skills':0.0}` / `{}` | ✓ PASS |
| Debt markers | `grep -rn "TBD\|FIXME\|XXX" app/ tests/ alembic/ assets/` | 0 matches | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED — `find scripts -path '*/tests/probe-*.sh'` returns 0 files, and no PLAN/SUMMARY declares a probe contract for this phase. `scripts/run-probe.sh` is not a phase probe.

### Test Quality Audit

| Test File | Linked Req | Active | Skipped | Circular | Assertion Level | Verdict |
|-----------|-----------|--------|---------|----------|-----------------|---------|
| `tests/api/test_listing_events.py` | UI-02 | 22 | 0 | No | Behavioral (detail-surface swap, allow-list fallback with exact `context_json`, predicate-set preservation, queue invariance) | ✓ |
| `tests/api/test_listing_detail.py` | UI-02 | 15 | 0 | No | Value/Behavioral (target resolution, saved-view affordance, saved badge, state sentences) | ✓ |
| `tests/db/test_queue_page.py` | UI-01 | 14 | 0 | No | Value (exact accessors for first/middle/last/empty/zero/negative) | ✓ |
| `tests/api/test_queue_excluded.py` | UI-01 | 27 | 0 | No | Behavioral (rendered `hx-get` offsets, position text, boundary controls, server-fixed limit) | ✓ |
| `tests/pipeline/test_rank_caps.py` + `test_rank_stage.py` | RANK-07/08 | 38 | 0 | No | Behavioral (refusal before call, rolling-24h, one-listing-per-prompt, stability) | ✓ |
| `tests/api/test_ranking_weights.py` | RANK-04 | — | 0 | No | Value (`test_weight_change_writes_zero_llm_calls`) | ✓ |
| `tests/api/test_queue_ranking_adversarial.py` | RANK-08 | 0 | 1 xfail | No | — | accepted sentinel (`?min_score=nan`) |
| `tests/pipeline/test_rank_adversarial.py` | RANK-08 | 0 | 1 xfail | No | — | accepted sentinel (`read_weights` negative) |

**Disabled tests on requirements:** 0 → none blocking (the two strict xfails are accepted-by-design known limitations).
**Circular patterns detected:** 0.
**Insufficient assertions:** 0.

### Decision Coverage

All trackable CONTEXT.md decisions are honored by shipped artifacts. The 05-12 delta is consistent with the one-rendering-path rule (T-02-38/T-05-16), the append-only event log (D-41), and the saved-view-is-a-queue-filter posture; it touches no persisted shape and changes no decision.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| RANK-01 | 05-01 | Scored against CV using named, inspectable factors | ✓ SATISFIED | `rubric.FACTORS`, `rank_listing`, queue/detail surfaces |
| RANK-02 | 05-01 | Per-factor sub-scores stored, not just a total | ✓ SATISFIED | `factor_scores_json`; `RankingResponse` has no total |
| RANK-03 | 05-01 | Total computed in code from stored sub-scores and weights | ✓ SATISFIED | `rubric.weighted_total` at read time |
| RANK-04 | 05-04 | Adjust factor weights and see rankings re-derive | ✓ SATISFIED | `/settings/weights`; zero-LLM reorder test |
| RANK-05 | 05-01 | Rationale grounded in stored evidence | ✓ SATISFIED (mechanically) | Grounding filter + detail page; prose quality UAT-passed (test 1) |
| RANK-06 | 05-01 | Requirement-by-requirement fit breakdown with named gaps | ✓ SATISFIED | `gaps_json` + detail requirement list; presentation UAT-passed (test 3) |
| RANK-07 | 05-01 | Absolute per-listing score, stable across runs | ✓ SATISFIED | one-listing-per-call; stability test; live tolerance UAT-passed (test 2) |
| RANK-08 | 05-02, 05-05…05-10 | LLM spend capped per run and per day, before the call; unreadable fact store is an optional-ranking skip; the skip is a persisted, named outcome; the CV prerequisite is disclosed | ✓ SATISFIED | refusal-before-call tests; non-UTF-8 clean-skip tests; `_assert_skipped`; five-state strip; `fact_store_report` + `/health` `cv` |
| UI-01 | 05-04, 05-05, 05-07, 05-08, 05-10, 05-11 | Browse ranked jobs in a list; the strip reports one run's population and the five states; the CV prerequisite is stated; the queue is two-way pageable with a position line | ✓ SATISFIED | score-ordered queue + sort/min_score; one-population + five-state tests; CV status line; `#queue-pager` + accessor tests; **browser-confirmed** by UAT test 7 |
| UI-02 | 05-03, 05-09, **05-12** | Job detail with fit breakdown and rationale; the unscored state names the last run's real cause; **the Save/Hide action is a real inline swap with a saved affordance** | ✓ SATISFIED (code) | `GET /listings/{id}` + tests; three 05-09 state-branch tests; **05-12: 7 new tests pin the detail target, the surface split, the allow-list fallback, the badge and the saved-view link**. Browser-level confirmation → the one human item. |
| UI-03 | 05-04 | Edit search criteria and ranking weights | ✓ SATISFIED | weights card on settings; criteria editor pre-existing |

**Orphaned requirements:** None. All 11 IDs mapped to Phase 5 appear in a plan's `requirements_addressed` (05-01: RANK-01/02/03/05/06/07; 05-02: RANK-08; 05-03: UI-02; 05-04: RANK-04/UI-01/UI-03; 05-05: UI-01/RANK-08; 05-06: RANK-08; 05-07: UI-01/RANK-08; 05-08: UI-01/RANK-08; 05-09: UI-02/RANK-08; 05-10: RANK-08/UI-01; 05-11: UI-01; **05-12: UI-02**).

**Traceability note:** `REQUIREMENTS.md`'s Traceability table still marks RANK-01…RANK-07 and UI-03 as `Gaps Found` (stale from the round-1 verification) and does not list 05-12. All of those requirements are `✓ SATISFIED` above; the orchestrator/ship step should flip them to `Complete`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/web/templates/html/runs.html` | 106-112 | Generic `reason_counts` loop stringifies the nested `ranking` marker as a Python dict repr | ⚠️ Warning (carried) | User-visible on `/runs/{id}` for skipped/not-attempted runs. Run detail is Phase 2's RUN-03/04, not a phase-5 must-have. |
| `app/pipeline/rank.py` | 100-112 | `ranking_skip_reason()` docstring claims totality but catches only `(CvFactStoreError, OSError)` | ⚠️ Warning (carried) | Mislabeled skip cause for an exotic corrupt store; the run still completes. |
| `app/web/templates/html/queue_list.html` | 88-90, 98-100 | Pager swaps use `hx-swap="innerHTML"` with no `show:top` | ⚠️ Warning (05-11; accepted by user in UAT test 7) | Viewport stays scrolled to the pager after a swap; user explicitly accepted. |
| `app/web/templates/html/queue_list.html` | 85-103 | Boundary controls omitted, not disabled | ⚠️ Warning (05-11; accepted by user in UAT test 7) | Visual instability; user explicitly accepted. |
| `app/db/repositories/queue_repo.py` | ~111, 454-477 | Score-path scan truncates at 5000; `page.total` under-reports | ⚠️ Warning | CR-01 — accepted at personal scale (advisory 1) |
| `app/web/routes.py` | 109-116 | `_float_or_none` accepts `nan`/`inf` | ⚠️ Warning | Accepted-by-design (strict xfail) |
| `app/db/repositories/ranking_config_repo.py` | 48-64 | `read_weights` accepts a negative stored weight | ⚠️ Warning | Accepted-by-design (strict xfail) |
| `app/pipeline/rank.py` | 417-424, 486-489 | The cap-refusal row is counted as spend | ⚠️ Warning | WR-04 prior |
| `app/config.py` | 126 | Stale comment naming the deleted "Load more" control | ℹ️ Info (IN-04) | Cosmetic drift |
| `app/web/routes.py` | 150 | `parse_queue_query` clamps `offset` to 0 but does not snap to a `limit` multiple | ℹ️ Info (IN-01) | No UI path produces it |
| `app/db/repositories/queue_repo.py` | 289-291 | `prev_offset` omits the `max(1, limit)` guard | ℹ️ Info (IN-02) | Never negative; unreachable from `read_queue` |
| `app/cv/factstore.py` | 104-110 | Redundant first `except` clause | ℹ️ Info | Cosmetic |
| `app/pipeline/run.py` | 510, 529-530, 537, 550 | Bookkeeping-failure path persists a fabricated `survivors: 0` | ℹ️ Info | No longer user-visible via the strip |

**Debt markers:** None. No `TBD`/`FIXME`/`XXX` in any phase-modified implementation or test file.

### Human Verification Required

1. **Confirm the 05-12 detail Save/Hide fix in a browser.**
   - **Test:** Boot the app against a real DB, open any job detail page, click **Save**, then click **Hide**.
   - **Expected:** The `#detail-actions` section re-renders in place on the click — the button flips to its inverse label (Save→Unsave, Hide→Unhide), the `★ saved` / `hidden` badge appears, there is no full-page reload, and no `htmx:targetError` appears in the browser console. The `View saved jobs` link is present and points at `/?saved=1`.
   - **Why human:** The root cause is closed by automated evidence — the page renders the `#detail-actions` target (`test_detail_action_forms_target_the_detail_section`), the route returns the detail section carrying `Unsave` for `surface=detail` (`test_a_detail_surface_save_swaps_the_detail_actions_fragment`), the saved badge renders (`test_detail_saved_listing_shows_the_saved_badge`), and htmx is loaded (`base.html:9`). But the actual DOM swap is browser-level behaviour that no automated test exercises (the project has no browser test harness), and the project's own 05-12-SUMMARY marks coverage item D2 `human_judgment: true`, routing "the browser-level visual swap … to end-of-phase UAT". UAT test 8 has not been re-run since the fix (05-UAT.md still shows it `result: issue`, `status: diagnosed`). This is the residual 10-second visual confirmation, not a fix.

> **Closed since the prior pass:** the pager human item (a). `05-UAT.md` test 7 (`result: pass`, recorded 2026-09-24T09:38:23Z) records the user's in-browser confirmation ("yup going back and forth works, pass") and accepts the two embedded UI-audit decisions as-is. It no longer routes to human verification.

### Gaps Summary

No must-have truth failed, no artifact is missing or a stub, every key link is wired, no debt marker exists, and the hermetic suite is green (1093 passed, 14 deselected, 2 xfailed). **05-12 is real and independently confirmed — not taken from the SUMMARY:**

1. **G-05-8's root cause is structurally eliminated.** The detail page's controls now target `#detail-actions`, an element the detail page itself renders (`listing_detail.html` and `_detail_actions.html` contain zero `listing-row-` occurrences; `_listing_row.html` still sets `target_id = "listing-row-" ~ row.id`). One shared `_action_forms.html` defines both controls for both surfaces — the exact drift that shipped the defect is impossible.
2. **The route's surface split is allow-listed and safe.** `ACTION_SURFACES = ("queue","detail")` with `DEFAULT_SURFACE = "queue"`; the normalisation happens before any branch; an unlisted value returns the queue row and records `context_json == {"surface":"queue"}`. One route decorator only.
3. **The feedback and discoverability facets are both present and tested.** The returned detail fragment carries the inverse label and the projected badge; the page carries the `View saved jobs` link to the existing `/?saved=1` view. Seven new tests pass.
4. **All 05-12 prohibitions held.** No new route/endpoint, no JS, no `hx-push-url`/`hx-history`/`hx-boost`, no polling/SSE, no CDN asset, no safe-marking filter, no schema/migration/setting; Alembic head stays `0004`; `static/vendor/app.css` and `app/db/repositories/*` are unmodified (`git diff --stat 1cc6171 HEAD`).
5. **The prior pass's truths remain closed** (full suite green; the 05-12 diff touches no ranking/rubric/schema/persistence/cap/pager file), and **the pager human item is now human-confirmed** by UAT test 7.

What keeps this phase out of a clean `passed` is a single **human verification item**: the detail page's primary Save/Hide action is a browser-level interaction that no automated test exercises, and the project's own coverage metadata routes its visual confirmation to end-of-phase UAT. Every requirement and every success criterion is verified with automated evidence; only the 10-second in-browser confirmation of the 05-12 fix remains.

Two **reproducible warnings** carried from round 2 remain unfixed and are recorded rather than silently passed: **WR-01** (`/runs/{id}` renders the nested `ranking` marker as a raw Python dict repr) and **WR-02** (`ranking_skip_reason()` is not total). Neither fails a phase must-have (run detail is Phase 2's RUN-03/04; the mislabel is a rare corrupt-input path that still completes the run).

**MVP-mode note:** ROADMAP marks Phase 5 `mode: mvp`, but its goal ("One ranked, explained queue: …") is not a User Story — `gsd-tools user-story validate` returns `valid: false`. No per-phase user story is set, so the MVP user-flow-coverage section is not applicable and this report uses the standard goal-backward methodology. To opt in, set a User Story goal via `/gsd mvp-phase 5`.

---

_Verified: 2026-09-24T11:04:20Z_
_Verifier: the agent (gsd-verifier)_
