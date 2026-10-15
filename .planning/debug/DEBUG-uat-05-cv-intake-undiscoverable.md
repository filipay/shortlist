---
status: diagnosed
trigger: "also where on the page do i provide my own cv ? its not clear to me how that works"
created: 2026-09-23T00:00:00Z
updated: 2026-09-23T00:00:00Z
gap_id: G-05-2
phase: 05-ranking-core-value
truth: "The app tells the user a CV fact store is required for ranking and how to supply it."
mode: find_root_cause_only
bug_class: Bohrbug (deterministic product/discoverability omission; not in common-bug-patterns catalog)
audit_acknowledged:
  milestone: v1.0
  at: 2026-10-15
  status: diagnosed
---

## Current Focus

hypothesis: "CONFIRMED. The defect is (b) the app never communicates that ranking requires a
  host-placed CV fact store, nor the exact path it reads, nor how to supply one — NOT (a) the
  absence of an upload UI. Every user-visible surface is mute; the single CV string in the UI is
  gated on LLM unreachability and gives no supply path. A second, contributing condition: the
  external operator docs stop at a review draft and never state the promotion step to cv/cv.yaml."
test: "Full inventory of every surface a user could look at for CV config, with file:line + copy."
expecting: "Confirmed by inventory — see Evidence."
next_action: "Diagnosis complete. Return ROOT CAUSE FOUND. No fix (diagnose-only mode)."

## Symptoms

<!-- IMMUTABLE after gathering -->

expected: "A user opening the web UI can discover that ranking needs a CV fact store, learn the
  exact path the app looks for, and find how to supply one."
actual: "User cannot find any place on the page to provide their CV; the mechanism is entirely
  undisclosed in-app. Ranking silently skips (D-94) and the UI shows only a bare 'not ranked'
  badge / generic 'pass was skipped' copy with no cause and no path."
errors: "none surfaced to the user (silent omission). Server-side only: structlog
  pipeline.rank_skipped reason=fact_store_absent (app/pipeline/rank.py:381-387)."
reproduction: "Open the web UI as an operator with an empty cv/ dir. /settings, /, /listings/{id}
  and the health strip never reference a CV or fact store or how to supply one."
started: "Always — Phase 4 shipped the parser + store, no roadmap phase includes CV intake/disclosure."

## Eliminated

<!-- APPEND only -->

- hypothesis: "The defect is that the app has no CV upload UI."
  evidence: "The CV source is a host file by explicit design (D-58): compose.yml:13 bind-mounts
    ./cv:/cv; cv/ is gitignored; app/cv/factstore.py:50 reads a filesystem path. The requirement
    truth asks the app to *tell the user* a fact store is required and *how to supply it* — a
    disclosure requirement, not an intake requirement. An upload UI is a scope change, not this gap."
  timestamp: 2026-09-23
- hypothesis: "The documented external procedure fully covers 'how to supply one' (evidence item 5
    claimed mv cv/cv.draft.yaml cv/cv.yaml is documented)."
  evidence: "Grep across docs/ and scripts/ finds NO promotion step. docs/probes/2026-09-21-cv-tex-spike.md:117-119
    and docs/probes/README.md:149-152 stop at 'review draft'; scripts/cv-tex-spike.sh:48-51 only names
    cv/base.tex -> cv/cv.draft.yaml. Nothing writes cv/cv.yaml (app/cv/factstore.py:10-11: 'no module
    writes it'). Evidence item 5 is unsupported — correction recorded."
  timestamp: 2026-09-23

## Evidence

<!-- APPEND only - facts discovered -->

- timestamp: 2026-09-23
  checked: "Whole-repo grep for CV/fact-store/upload strings in app/**/*.{py,html}."
  found: "Exactly ONE user-visible CV mention in the entire UI: app/web/templates/html/_health_strip.html:11
    'ranking and CV tailoring are unavailable until it is back' — conditional on the LLM backend being
    UNREACHABLE, not on the CV being absent, and gives no path. Every other match is a docstring/comment
    or server-side code. No upload/multipart/UploadFile/enctype anywhere (python-multipart is
    deliberately not a dependency: app/api/searches.py:83, app/api/events.py:90)."
  implication: "The app is mute about the CV. There is no intake surface AND no disclosure surface."

- timestamp: 2026-09-23
  checked: "/settings template + route (app/web/templates/html/settings.html; app/api/settings.py:135-226)."
  found: "Four cards: 'Queue data' (settings.html:16-27), 'LLM backend' (29-83), 'Ranking weights'
    (85-110), 'Danger zone' (112-135). NO CV card, NO cv/fact-store/upload string. _settings_context
    (settings.py:153-178) passes banner/counts/weights/factors/probe/system_prompt — no cv_dir, no cv path,
    no cv presence. The closest 'host file' analog is the Danger zone (settings.html:120-125): it names an
    exact path via <code>{{ backup_dir }}</code> and gives operator steps ('stop the container and replace
    the database file with that snapshot')."
  implication: "The settings page is the natural, currently-empty home for CV configuration. The exact
    markup pattern to reuse is the Danger-zone settings-note + <code>path</code> + operator-procedure shape."

- timestamp: 2026-09-23
  checked: "Queue empty/zero states (app/web/templates/html/queue_list.html:44-54)."
  found: "Filtered: 'No listings match these filters. Clear filters' (46-49). Unfiltered: 'No listings yet.
    Once a search runs, its normalised results appear here.' (51-53). No ranking/CV mention. There is NO
    separate 'listings present but none ranked' empty state — an all-unranked queue renders a normal table
    with per-row 'not ranked' badges."
  implication: "The queue's empty state addresses listings only; it is silent on the CV prerequisite."

- timestamp: 2026-09-23
  checked: "Queue ranking strip (app/web/templates/html/queue.html:130-143; app/web/routes.py:276-310)."
  found: "Renders 'Ranked {{ ranked }} of {{ candidates }}' (+ optional '— cap reached ({{ cap_reason }})')
    ONLY when ranking_strip.get('ranked') is not none (queue.html:139). ranked_count is written by the
    detached ranking task at rank.py:487. When the fact store is absent, run_ranking returns at rank.py:377-387
    BEFORE any run row update, so ranked_count stays NULL and the strip NEVER renders."
  implication: "The absence of the fact store structurally HIDES the ranking strip, so the UI cannot even
    show '0 ranked' — the skip is invisible by construction. This is the mechanism behind the user's
    'i cannot tell'."

- timestamp: 2026-09-23
  checked: "Per-row unranked badge (app/web/templates/html/_listing_row.html:45-50)."
  found: "When total_score is none: <span class='badge badge-unranked' id='listing-unranked-{id}'>not ranked</span>
    (line 48). No title attribute, no link, no cause."
  implication: "The most frequently seen unranked signal is a two-word badge with no explanation."

- timestamp: 2026-09-23
  checked: "Listing detail 'not yet ranked' copy (app/web/templates/html/listing_detail.html:64-69)."
  found: "'Not yet ranked. This listing has no score yet — ranking may still be running, or the pass was
    skipped. Refresh once it finishes.' It names a possible skip but never says why a pass is skipped,
    never mentions the CV/fact store, and offers no path."
  implication: "The app's closest acknowledgement that a skip exists is a dead end. It cannot distinguish
    'still running' from 'no CV configured' (that distinction is G-05-1's territory)."

- timestamp: 2026-09-23
  checked: "Health strip (app/web/templates/html/_health_strip.html:1-49) and its data source
    (app/web/routes.py:71-87)."
  found: "Two data sources only: per-source rows + LLM reachability/version. LLM-unreachable copy at line 9-12;
    LLM-reachable at 14-16; source table at 19-45; empty at 47. NO CV/fact-store row. _health_strip() returns
    (rows, reachable, version, error) — nothing about the CV."
  implication: "The queue page's status area is the natural second home for a CV/fact-store status line, but
    carries none today."

- timestamp: 2026-09-23
  checked: "GET /health JSON route (app/api/health.py:72-136)."
  found: "Response keys: status, db, opencode, tectonic, sources (health.py:127-136). NO cv/fact-store key.
    It already reports the LaTeX engine as a first-class sibling dependency via _tectonic_report (health.py:55-69)
    — 'available', 'version', 'error'. /health has NO UI consumer: the health strip is rendered by the queue
    route (routes.py:339) with its own context, not by fetching /health."
  implication: "A cv/fact-store report slots in exactly where tectonic already sits — a natural, cheap,
    consistent place for the operator/uptime path. It is not, however, a substitute for in-page disclosure
    because nothing in the UI reads /health."

- timestamp: 2026-09-23
  checked: "Navigation (app/web/templates/html/base.html:27-33)."
  found: "Five nav links: Queue, Searches, Merges, Runs, Settings. No 'CV'/'Profile'/'My CV' entry."
  implication: "There is no clickable place a user could even guess at for CV configuration."

- timestamp: 2026-09-23
  checked: "Other pages: /searches (criteria.html), /merges (merges.html), /runs (runs.html)."
  found: "Grep for cv/fact-store/tailor/upload across app/web/templates returned only _health_strip.html:11.
    These three pages carry no CV string."
  implication: "No additional surface to contradict the finding."

- timestamp: 2026-09-23
  checked: "The CV read path and failure semantics (app/pipeline/rank.py:74-75,377-387;
    app/cv/factstore.py:50-88; app/config.py:160)."
  found: "CV_FILENAME='cv.yaml' (rank.py:75); read at Path(settings.cv_dir)/CV_FILENAME (rank.py:379);
    cv_dir default '/cv' (config.py:160); compose.yml:13 mounts ./cv:/cv. load_facts raises a path-qualified
    CvFactStoreError 'no CV fact store at <resolved>' for missing/bad/unreadable/wrong-schema/duplicate.
    run_ranking catches (CvFactStoreError, OSError) and returns silently, logging only
    pipeline.rank_skipped reason=fact_store_absent (rank.py:380-387)."
  implication: "The exact path a fix must name is host ./cv/cv.yaml == container /cv/cv.yaml. The failure is
    deliberately silent to the user — loud only in the operator log."

- timestamp: 2026-09-23
  checked: "External operator docs (docs/probes/2026-09-21-cv-tex-spike.md:103-134;
    docs/probes/README.md:138-160; scripts/cv-tex-spike.sh; docs/runbook-latex-compile.md:31-38)."
  found: "Documented procedure: mkdir -p cv artifacts; place real LaTeX CV at cv/base.tex; run
    'bash scripts/cv-tex-spike.sh' (writes cv/cv.draft.yaml, never over cv.yaml); 'review' the draft.
    The docs then stop. NO step promotes cv/cv.draft.yaml to cv/cv.yaml, and no doc states that ranking
    reads /cv/cv.yaml. grep for 'mv'/'promote' across docs+scripts: no matches. factstore.py:10-11 confirms
    'no module writes' cv.yaml."
  implication: "Even the external escape hatch is incomplete — a user who found the docs still would not be
    told how to produce the file ranking actually loads. Any in-app copy pointing at these docs inherits the
    dead end unless the docs are completed too. This is the AND-gate's second contributing condition."

- timestamp: 2026-09-23
  checked: "Planning record (05-UAT.md:61-67; STATE.md Blockers/Concerns)."
  found: "G-05-2 recorded status failed, severity major, truth = 'The app tells the user a CV fact store is
    required for ranking and how to supply it.' STATE.md already carries '[Phase 4] Blocking unknown #1 —
    the real .tex is not in this repo' with the cv-tex-spike trigger. ROADMAP: 8 phases, none a CV-intake UI;
    Phase 4 = store+spike (complete), Phase 6 = tailoring, Phase 8 = operations+polish."
  implication: "The gap is a known, pre-registered truth failure — not a regression. The roadmap provides no
    phase for an upload UI, which supports the disclosure-only reading of the fix."

- timestamp: 2026-09-23
  checked: "cv/ directory and gitignore."
  found: "cv/ exists, is EMPTY, root-owned, and gitignored (.gitignore 'cv/' with !app/cv/ !tests/cv/
    !tests/fixtures/cv/ negations). tests/fixtures/cv/awesomecv_standin.yaml is the synthetic fixture."
  implication: "A fresh checkout guarantees the fact store is absent, so every fresh user hits the silent skip."

## Resolution

root_cause: >
  The app never discloses that ranking requires a host-placed CV fact store, nor the exact path it reads,
  nor how to supply one — a deterministic, in-app discoverability omission (b), not the absence of a CV
  intake UI (a). The CV is a host file by design (D-58; compose.yml:13 ./cv:/cv; config.py:160 cv_dir=/cv;
  rank.py:75,379 reads /cv/cv.yaml), and ranking silently skips when it is absent (rank.py:377-387, D-94),
  surfacing only a server log line. Every user-visible surface is mute: /settings has no CV card and no
  cv path in its context (settings.html:16-135; settings.py:153-178); the queue empty state is listings-only
  (queue_list.html:44-54); the ranking strip cannot render at all when the store is absent because
  ranked_count stays NULL (queue.html:139; rank.py:487); the row badge is a bare 'not ranked'
  (_listing_row.html:48); the detail page says only 'the pass was skipped' with no cause or path
  (listing_detail.html:64-69); the health strip has no CV row (routes.py:71-87; _health_strip.html);
  GET /health has no cv key (health.py:127-136); and nav has no CV entry (base.html:27-33). The single
  UI CV string (_health_strip.html:11) is gated on LLM unreachability and gives no path. A second,
  contributing condition (AND-gate) compounds it: the external operator docs stop at a review draft and
  never document the promotion step to cv/cv.yaml (spike §4:117-119; README:149-152; cv-tex-spike.sh:48-51;
  nothing writes cv.yaml), so even the escape hatch is incomplete.

fix: >
  NOT APPLIED — diagnose-only. Recommended minimal fix surface (in-app disclosure only; no upload UI):
  (1) settings.html + app/api/settings.py _settings_context — add one CV fact-store settings-card modeled on
  the Danger-zone markup (<p class="settings-note"> naming <code>{{ cv_path }}</code>), passing cv_path
  (settings.cv_dir + rank.CV_FILENAME), a cv_present bool and the load error.
  (2) _health_strip.html + app/web/routes.py queue() — add an unconditional CV/fact-store status line beside
  the LLM line, so the queue page is not mute.
  (3) app/api/health.py — add a 'cv' key mirroring 'tectonic' (available/version/error), for the operator path.
  (4) listing_detail.html:64-69 and the queue empty/row unranked copy — when the reason is a missing fact
  store, name the CV and the path instead of the generic 'may still be running'; requires a render-time
  load_facts(cv_path) probe (no new persistence) — overlaps G-05-1.
  (5) docs/probes/2026-09-21-cv-tex-spike.md §4 + docs/probes/README.md:145-156 — document the promotion step
  (curated cv/cv.draft.yaml -> cv/cv.yaml) and state that ranking reads /cv/cv.yaml, so in-app copy does not
  inherit the dead end.
  An upload UI is explicitly OUT of scope for phase 05 (scope change, new trust boundary/dependency; truth
  asks to disclose+instruct, not to accept a file).

verification: >
  Not performed (diagnose-only). Verification should assert, for each surface, that with cv/cv.yaml absent the
  rendered page names the CV fact store AND the exact path AND a supply path; and that with cv.yaml present
  the notice disappears. Existing pinned copy to preserve: 'No listings yet' (tests/db/test_skeleton_boot.py:125;
  tests/api/test_run_trigger.py:167 and siblings), 'Not yet ranked' (tests/api/test_listing_detail.py:208).

files_changed: []
