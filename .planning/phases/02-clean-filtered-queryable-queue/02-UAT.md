---
status: complete
phase: 02-clean-filtered-queryable-queue
source: [02-VERIFICATION.md, 02-11-SUMMARY.md]
started: 2026-09-16T13:30:00Z
updated: 2026-09-17T15:30:00Z
---

## Note on result vocabulary (2026-09-17)

Items 1–5 were recorded on 2026-09-16 as `result: satisfied` — the word the first
pass used. The completion predicate (`phase uat-passed --require-verification`)
recognises only `pass` / `skipped` / `blocked`, so all five read back as blockers
(`02-UAT.md: test 1 (satisfied)`, …) and the phase could not advance. They are
relabelled `pass` here and **no result changed**: the dates, the evidence, the
operator quotes and the G1–G7 findings are untouched. Items 6–9 are new, for the
02-11 deliverables that post-date the original UAT.

## Current Test

[testing complete]

## Tests

### 1. Tune the dedup threshold θ against the first real corpus
expected: Run a real pipeline run against live LinkedIn/Indeed data, inspect the `listing_dupes` pairs and the merge rate on `/merges`, and record the chosen `Settings.dedup_fuzzy_threshold` (currently 88) and its justification in `docs/`.
why_human: No real corpus exists pre-run; θ is deliberately shipped as a setting with a tuning procedure (02-VALIDATION.md Manual-Only; ROADMAP Phase-2 Notes; D-31). Code and tests prove θ is a settings read with no hard-coded literal, not that 88 is the right value.
result: pass (2026-09-16) — θ assessed against the real corpus; 88 retained
evidence: 2 real runs triggered; latest run #6 fetched=100. **6 live (un-reverted) merges** at scores
  89.1 / 90.6 / 92.0 / 95.2 / 100.0 / 100.0 — the lowest correct merge is **89.1**, so θ=88 caught it by
  only 1.1. 44 unmerged near-miss pairs scored >=70 and the distributions **overlap heavily**: true
  duplicates span 89.1-100 while non-duplicates span 70-97.9 (`Senior Software Engineer <-> Software
  Engineer` = 93.2; `Software Eng II <-> Software Engineer` = 93.6; `Software Engineer <-> Software
  Engineer Intern, 2027` = 78.3). **No θ separates them.** The dangerous high-score `Senior X <-> X`
  pair is stopped by the grade guard, not by θ. **Conclusion: θ=88 is approximately correct and is NOT
  the discriminating lever on this corpus** — the blocking key (company+title+location) plus the grade
  guard do that work, as the ROADMAP note anticipated. Raising θ would merge different seniority levels;
  lowering it would miss the 89.1 pair. CAVEAT: the attempted override to 90 never took effect (defect
  G1 under item 2), so this corpus was scored at the in-code default 88.

### 2. Merge-rate band sanity check after a real run
expected: After a real run, compare the observed merge rate on `/merges` against the 10–15% band from research and record why the chosen θ is or is not adjusted.
why_human: The band comes from a different market/query shape; QUEUE-09 asks for the rate to be visible and windowed, which is machine-verified, but whether the observed rate is sane needs real data.
result: pass (2026-09-16) — band compared against the only defensible figure; G2(a) implemented
evidence: `merge_rate()` is windowed to the latest run, so the per-run figures are 6/100 = **6.0%** on
  run #5 (the run that did the merging) and 0/100 = **0.0%** on run #6 (steady state). Neither is a
  meaningful "how much merging is happening" number, because all three runs re-fetch the SAME ~100
  listings, so cross-source overlap is collapsed on the first run and every later run is structurally
  0%. The only defensible figure is **distinct un-reverted merges over the distinct corpus:
  6 / 104 = 5.8%** (7/104 = 6.7% once id=74 is absorbed by a post-fix rerun).
  **Against the research band of 10-15%, the observed rate is BELOW the band.** The band does not
  transfer to this market/query shape, which is exactly the caveat the research recorded (a different
  market and query shape). Contributing factor: LinkedIn's field fill-rate shows
  `description: 0.0`, so title/company carry nearly all the matching signal.
  Verdict: the band is **not** an applicable target, the observed rate is sane for this corpus, and θ is
  not the lever (see item 1). The page's per-run scope is now stated unmistakably (G2, decision (a)),
  so a 0% can no longer be misread as a broken deduper.

### 3. Compose smoke of the running stack
expected: `docker compose up` and browse the queue; confirm the migration to `0002` applies, the queue renders, and the run trigger works end to end.
why_human: 02-VALIDATION.md lists this as a WINDOWS.md carry-over (open item #1); it needs Docker/network and a human browsing.
result: pass (2026-09-16)
evidence: Operator ran `bash scripts/compose-smoke.sh` on the Phase-2 image → PASS (`up -d --wait`
  healthy, `/health` `db=ok`, a run completed, listings survived `restart`). Follow-up probes:
  revision `0002`, 104 listings preserved, `ck_runs_reason` present, `rapidfuzz 3.14.6`,
  and `/`, `/merges`, `/runs`, `/searches` all HTTP 200. `.planning/WINDOWS.md` item #1 closed.
  Caveat: the three later commits touch templates/CSS/tests only, so the smoked
  migration + pipeline contract still holds. Docker is absent from the agent sandbox, so this is
  operator-confirmed rather than independently reproducible by the agent.

### 4. Confirm the pinned rapidfuzz dependency was human-approved
expected: The approval (version 3.14.6, source repo `rapidfuzz/RapidFuzz`, pre-compiled musllinux wheel, no arbitrary build step) is recorded in 02-02-SUMMARY.md "Authentication Gates".
why_human: An out-of-band human sign-off cannot be machine-verified; recorded as discharged in-phase on 2026-09-16 during execution, re-listed for the end-of-phase human checkpoint.
result: pass (2026-09-16)
evidence: During plan 02-02 execution the human answered the `blocking-human` checkpoint with
  "approved", having been shown: `pip index versions rapidfuzz` → 3.14.6 with a release history
  back to 0.0.6; PyPI metadata homepage/repository `https://github.com/rapidfuzz/RapidFuzz`
  (matching the research citation, no slopsquat); and a pre-compiled
  `rapidfuzz-3.14.6-cp314-cp314-musllinux_1_2_x86_64.whl` (no arbitrary source build).
  Recorded in `02-02-SUMMARY.md`. Nothing about the pin changed since, so the approval stands.

### 5. Judge whether the excluded-listing chip satisfies "which rule fired and why"
expected: Under `Show excluded`, each rejected listing shows a chip `rule.kind (count)` (e.g. `exclude_keyword (2)`). Confirm this is sufficient, or require the firing rule id and the matched `detail_json` term (e.g. `crypto`) to be surfaced.
why_human: The rule id and the persisted `listing_exclusions.detail_json` (the matched term/field) have no UI consumer; the chip names only the rule kind plus a per-rule count. This is a product-sufficiency judgment against SC2 / FILT-03 wording, not a machine-definable pass/fail.
result: pass (2026-09-16) — kind + run-scoped count judged sufficient for now
evidence: User decision: *"I think it's enough for now, we can add more."* So the chip stays as
  `rule.kind (count)`. The underlying capability is present and tested — `detail_json` (the matched
  term/field) is persisted on every exclusion and `rule_id` is available on `QueueRule` — so enriching
  the chip later is a template + one repository read, not new plumbing. Note the count is deliberately
  run-scoped and pinned by `test_the_chip_count_is_grouped_over_the_run_not_per_row`.
  The related ask ("filter out specifics like remote: no or location: galway") is a different feature —
  an ad-hoc browse-time filter over listing attributes, not chip content — and is captured as
  **SEED-001** (`.planning/seeds/SEED-001-queue-filter-by-remote-and-location.md`) for a future phase.

### 6. A queue row links to its posting and to each source
expected: On `/`, each row's title links to the posting page in a new tab; a merged row shows one link per source (so both halves of a merge are visible); an `Apply` link to the employer/ATS page appears **only** when that URL genuinely differs from the board URL (Indeed usually differs, LinkedIn does not); a row with no usable URL renders as plain text rather than a dead link; and no `javascript:`/`data:` URL ever reaches an `href`.
why_human: The data path and the `http(s)` gate are machine-verified; whether the *right* links appear on real listings, and whether the "Apply only when different" rule reads correctly on the live corpus, needs a human looking at actual rows.
result: pass (2026-09-17) — operator confirmed on the live instance ("all pass")

### 7. Dismiss the whole queue with one action
expected: With the search box empty and no toggles selected, `Dismiss all queued listings` empties the queue, the returned page already shows the empty queue (no stale row left behind), the dismissal survives a reload, and `Unhide` restores exactly one row. Nothing already hidden, absorbed as a merge twin, or excluded by the latest run is touched, and one `hide` event per listing is recorded with `context.surface = queue_dismiss`.
why_human: The scope question — "everything" meaning the **default** queue, not the currently filtered view — is a product judgment, and the known above-ceiling edge (a refusal that htmx does not swap, so no visible feedback) can only be judged by eye.
result: pass (2026-09-17) — operator confirmed on the live instance ("all pass")

### 8. The settings page renders its danger zone
expected: `GET /settings` shows the per-table row counts, the confirm token, and a fifth `Settings` nav link that marks itself current. The danger zone is visually separated from ordinary settings, and the reset cannot be triggered without the exact token typed.
why_human: Visual hierarchy and affordance — whether the danger zone *reads* as dangerous and the token requirement is discoverable — is a design read, not a machine check.
result: pass (2026-09-17) — operator confirmed on the live instance ("all pass")

### 9. The guarded reset on the live database
expected: On the real container, `POST /settings/reset` with the correct token writes a snapshot to `<db_dir>/reset-backups/jobsearch-<UTC>Z.db`, empties the queue child-first in one transaction, keeps `searches` / `filter_rules` / `sources`, and reports the snapshot filename; the queue is still empty after a reload. A wrong token gives `400`, a run in flight `409`, tracked work present `409`, a snapshot failure `500` — each with the corpus untouched.
result: pass (2026-09-17) — operator confirmed on the live instance ("all pass")
evidence: **This is the case that failed with a bare `500` on the live database before `c16023a`.** The operator has since rebuilt the container and confirmed the reset now succeeds and the queue stays empty; the fix and its engine change were separately reviewed and recorded as a deliberate decision (`d436425`).

## Summary

total: 9
passed: 9
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

Findings surfaced by the real-corpus UAT (2026-09-16). These are new information: the automated
verification (54/54) and the security / UI / Nyquist audits could not have found them, because each
needs a live corpus or a real container.

### G1 — the θ override never reaches the container — FIXED
`echo 'DEDUP_FUZZY_THRESHOLD=90' >> .env` is silently ineffective, for two independent reasons:
1. `compose.yml` did not forward the variable. Compose uses `.env` only for `${...}` substitution,
   and there was no `${DEDUP_FUZZY_THRESHOLD}` expression anywhere in it.
2. The image contains no `.env` — the Dockerfile does not COPY it, and only `./data` is mounted — so
   pydantic-settings' `env_file=".env"` inside the container finds nothing.

Worse, `docker compose up -d` reported `Container ... Running 0.0s`: it did not recreate the
container, so nothing was applied at all. Two layers of silent no-op.

Fixed by forwarding the four Phase-2 knobs explicitly in `compose.yml`, with the in-code defaults as
fallbacks (`DEDUP_FUZZY_THRESHOLD:-88`, `DEDUP_POSTED_WINDOW_DAYS:-90`, `STALE_AFTER_DAYS:-14`,
`QUEUE_PAGE_SIZE:-25`) — fixing the whole class rather than one field.
`tests/test_deploy_manifest.py` stays green (15 passed). A host-side `.env` now takes effect, though
it still requires a container recreate (`docker compose up -d --force-recreate`) to apply.

### G2 — the merge rate reads 0% in steady state — DECISION REQUIRED
`dupe_repo.merge_rate()` is deliberately windowed to the LATEST run. That windowing is CR-01's fix and
it correctly removed an impossible 167% reading, but on repeat runs the latest run has nothing left to
merge, so a corpus holding **6 live merges displays 0.0%**. `runs.deduped_count=0` on run #6 shows the
same behaviour upstream. Internally consistent and individually true — but it fails SC1's purpose
("a merge rate … the user trusts"), and it is why UAT item 2 could not be answered. Options:
- keep the latest-run window and label it prominently as "this run" (cheapest, honest, still 0%);
- **recommended:** add a trailing window (last N runs, or the last `dedup_posted_window_days`) as the
  headline with the latest run as detail — the phase already established the trailing-window idiom;
- all-time un-reverted merges over all-time fetched, with the latest run beside it.

### G4 — Tier-2 over-merged: 6 of 7 merges were different jobs — FIXED
Found by the user reading the real merged output on `/merges`, i.e. by the human UAT step. **No
automated check could have caught it**: every merge was individually well-formed, audited, snapshot-backed
and reversible. Only a human who knows what "Lead SRE (DSS)" means could see they were different jobs.

**Measured precision: 4 of the 5 commented merges were wrong (~20%).** The 7 merges with both sides'
provenance:

| # | score | company | sources | user's verdict |
|---|---|---|---|---|
| 1 | 100.00 | dow jones | indeed / indeed | WRONG — different listings behind the links |
| 2 | 92.04 | jpmorganchase | indeed / indeed | user read as SAME (see note) |
| 3 | 95.24 | jpmorganchase | indeed / indeed | WRONG — `(DSS)` is a different role |
| 4 | 89.06 | jpmorganchase | indeed / indeed | WRONG — `(Backend, AWS)` vs `Backend` |
| 5 | 100.00 | mastercard | indeed / indeed | WRONG — different Indeed `jk` (`9814f9bf…` vs `e9764e77…`) |
| 6 | 90.57 | taktile | linkedin / linkedin | WRONG — "Platform team" vs "Team Agent" |
| 7 | 100.00 | mastercard | indeed / **linkedin** | CORRECT — the only cross-source pair |

**Root cause: Tier-2 merged listings that Tier-1 had already declared distinct.** Tier-1's identity
primitive is `uq_listing_sources_source_sid` — `UNIQUE (source, source_listing_id)`
(`app/db/models.py:178-184`) — and JobSpy supplies a stable board key (`in-<jk>`, `li-<id>`). Two
distinct listings sharing a source therefore necessarily have different job ids. **6 of 7 merges crossed
that boundary**, and a high fuzzy score overrode it.

**θ cannot fix it.** At θ=90 the pairs interleave: #2 (92.04, judged SAME) would be refused before #3
(95.24, judged WRONG). #5 has *identical titles* at score 100.0, so no threshold and no qualifier guard
can separate it — the distinguishing fact is the job id, not the text.

**The user proposed:** *"if the listing is from the same domain but has different listing ids, we should
consider them different jobs."* The conclusion was adopted, the **key was corrected**: `canonical_source_url`
prefers `direct_url`, so for these rows it holds the *employer's* URL (`dowjones.jobs`,
`contacthr.com`, an `appcast.io` redirect token), not a board id. The correct primitive is
`(source, source_listing_id)` — which also dissolves the `appcast.io` tracking-token concern.

**Note on the user's #2 verdict.** #2 and #4 are structurally identical (same company, same domain,
different req id, one title carrying a trailing qualifier) yet were judged oppositely. The rule treats
them consistently by refusing both, so **#2's "same job" read is the probable outlier** — `153569403` and
`153557411` are different reqs. Worth the user's confirmation.

**Fix (`819bb9e`, oracle-designed): fuzzy merge is only attempted across DISJOINT source sets.** A shared
source refuses the pair as the *first* check in `score_pair`, before the grade guard
(`app/domain/dedup.py:162-173`). `CandidateFacts.sources` is populated by ONE indexed batch read (no
N+1). No threshold change, no migration, no new dependency. Empty source sets never refuse, so missing
provenance still falls through to grade/company/location/score. 14 new tests pin each false-merge shape
plus a cross-source **must-merge** control and an aggregate case asserting the real 7-pair corpus now
yields exactly **one** decision.

**Trade-off, stated honestly:** same-source *reposts* (the same role re-posted under a new job id) will no
longer collapse — they appear as visible duplicates. That is the safe direction: a refused duplicate is a
**visible** duplicate the user scrolls past; a wrong merge is an **invisible lost job**. Same-source was
also 6-for-6 wrong on this corpus, so its expected value was negative.

**Test corrected, not weakened:** `a51a133`'s reproduction test
(`test_a_three_way_duplicate_merges_both_twins_onto_the_first_seen`) asserted two *same-source* Indeed rows
merging — precisely the behaviour this feedback proved wrong. Replaced by
`test_a_shared_source_member_is_not_merged_but_the_cross_source_twin_is`; the `a51a133` location
regression it protected is preserved on the cross-source path.

**Still open for the operator:** the live corpus still holds the 6 wrong merges. They are **revertible
today** via `/merges` (that is what revert shipped for), and a rebuilt image is required before the guard
is active. See the step-by-step instructions in the session record.

### G3 — dedup gap on the phase's CENTRAL promise — ROOT CAUSE CONFIRMED AND FIXED
SC1 promises "the same job found on two sources appears once". A real-corpus case violated it.

**Root cause (confirmed, not hypothesised): the score gate contradicted the location gate.**
`app/domain/dedup.py::score_pair` scored a text built by `_pair_text` (`dedup.py:108-114`) that
concatenates `company + title + location`. So a listing with a NULL `location_norm` was **penalised in
the score for the very absence the location gate declares acceptable** — the module's own contract at
`dedup.py:134-135` / `151-156` is *"an unknown location is never a rejection reason"*.

The live pair:
| side | `_pair_text` | score |
|---|---|---|
| id=3 (indeed) | `'mastercard senior software engineer dublin, d, ie'` | — |
| id=74 (linkedin, NULL `location_norm`) | `'mastercard senior software engineer'` | **83.33** |

83.33 < θ=88, so `score_pair` returned `None` and `candidate_merges` never proposed the pair. The block
ordered `[3, 4, 74]`, so survivor 3 absorbed 4 (score 100.0) and dropped 74.

**The earlier hypothesis in this file was WRONG and is corrected here.** Candidate selection was not at
fault: `candidates_for_block` filters only `company_norm` + `is_active` (never "touched this run"), and
the persisted stage logs show `candidates: 102, proposed: 6` on both runs, with run #6 recording
`skipped_already_merged: 6`. id=74 was in the pool both times; the pair was simply never proposed.

**A second correction.** This file previously said Tier-2 is "cross-source by design". That is false in
this codebase: `listing_dupes` #2 (22←38) and #4 (39←43) are both **indeed↔indeed** merges. The
`jpmorganchase` id=23 vs id=44 case is refused by the dedicated location gate (`'dublin 1, d, ie'` vs
`'dublin 2, d, ie'`), a deliberate safety-bias refusal documented and unit-tested at
`tests/domain/test_dedup.py:122-136` — not a cross-source limitation. Whether "dublin 1" and "dublin 2"
should count as the same role is a separate **product** question.

**Impact was bounded:** a corpus-wide scan found the only title-identical pairs failing the score gate
are (3,74) and (4,74), both this exact mechanism. One bug, one mechanism.

**Fix:** `a51a133` — `_pair_text` gained a keyword-only `include_location: bool = True`; `score_pair`
now scores over `(company, title)` alone when **exactly one** side's location is unknown, and keeps the
full `(company, title, location)` tuple when both are known (so both-present scores are byte-identical
and the boundary assertion at `tests/domain/test_dedup.py:140-150` is untouched). Rejected alternative:
always dropping location, which would change both-present scores and break that boundary assertion.

**Proof:** the diagnosing lane's reproduction test
`tests/pipeline/test_dedup_merge.py::test_a_three_way_duplicate_merges_both_twins_onto_the_first_seen`
failed on the old code with `assert 1 == 2` and passes unmodified after the fix; three focused unit
tests pin the mechanism in `tests/domain/test_dedup.py`. Full suite 605 passed, `ruff` clean.

**Operational consequence:** the live corpus still holds the unmerged pair. A rerun will now absorb
id=74, taking that run's `deduped_count` from 6 to 7 (it is `count_merges_for_run`) and raising
`merge_rate()`'s numerator by 1 with `fetched_count` unchanged. `merge_rate()` itself is deliberately
untouched — see G2.

**Assessed and deliberately NOT changed:** a blank `title_norm` depresses the score by the same
mechanism, but the module declares no contract that an unknown *title* is acceptable, and refusing to
merge on a missing title is the safety-preserving direction (merging on company alone would collapse
distinct roles). A NULL `company_norm` is an explicit hard refusal, never silently scored, so no
contradiction exists there.

**Still invisible in the UI:** `/merges` lists only merged rows, so an unmerged duplicate cannot be
surfaced at all — finding this needed a hand-written corpus query.

### G5 — the browser rule form sent an empty body: "Add rule" / "Save rule" were dead — FIXED

Surfaced while reviewing the G3/UI layout screenshot. Not a layout defect and **not** findable by any
existing test: the rule routes were well covered, but every test posted the body directly rather than
going through the browser.

**Mechanism.** In `app/web/templates/html/criteria.html` the "Add rule" and "Save rule" buttons are
`<button type="button" hx-post="…">` living in a plain `<div>` (`<div class="rule-form">` /
`<div class="rule-edit">`), with their named inputs as siblings. There was **no enclosing `<form>` and
no `hx-include`/`hx-vals` anywhere**. htmx 2.0.10 (exactly pinned here) sends **zero parameters** in
that shape, per its own source:
- `getRelatedForm(elt)` (`src/htmx.js:2853`) = `elt.form || closest(elt, 'form')` → `null`.
- the non-GET branch of `getInputValues` (`:3602`, `~:3622`) passes that `null` into
  `processInputValue` (`:3521`), whose first line returns immediately on `null`;
- the element itself is rejected by `shouldInclude()` (`:3451`) — `type === 'button'` and no `name`;
- the button-value branch no-ops via `addValueToFormData` (`:3471`) when `name == null`.

So the POST went out urlencoded with an empty body; `create_rule_route`
(`app/api/searches.py:486-507`) read `kind` from that body, found nothing, and returned a **400**. The
rule was never created. The docs state the rule exactly (https://htmx.org/docs/#parameters), and
https://htmx.org/quirks/ documents the same lookup.

**Blast radius (audited, all templates, every mutating htmx element).** Exactly two interactions were
broken — both the browser half of CRIT-03:

| Route | Trigger | Body needed? | Verdict |
|---|---|---|---|
| `POST /searches` (`searches.py:453`) | `<form class="search-create">` | yes | OK (real form) |
| `POST /searches/{id}` (`:553`) | `<form class="search-edit">` | yes | OK (real form) |
| `POST /searches/{id}/rules` (`:486`) | `<button hx-post>` in `<div class="rule-form">` | yes | **BROKEN — fixed** |
| `POST /searches/{id}/rules/{rule_id}` (`:621`) | `<button hx-post>` in `<div class="rule-edit">` | yes | **BROKEN — fixed** |
| `…/toggle`, `…/delete`, `…/run`, rule toggle/delete, `POST /listings/{id}/events` | id in path / real form | no | OK |

**Fix:** `edcbe68` — `hx-include="closest .rule-form"` on the Add button, `hx-include="closest .rule-edit"`
on the Save button. Zero structural change, deliberately avoiding a markup change to the recent
`9d30e23` layout commit; no CSS touched (`app.css` unchanged, sha256 `676cf6dd…`). This is the
mechanism htmx's own docs prescribe for inputs outside a form
(https://htmx.org/attributes/hx-include/).

**Why it matters for the phase:** CRIT-03 / plan 02-08 task 1 is "create a named search with a typed
rule **from the browser**". The API half was correct and tested; the browser half was unreachable. It
also explains why a real corpus carried no exclusion rules.

**Regression guard:** new `tests/api/test_rule_form_payloads.py` (7 tests) reimplements htmx 2.0.10's
payload lookup in stdlib `html.parser` — for every mutating element on `/searches` it computes the
payload htmx would actually send and asserts a non-empty body containing the fields that route reads,
plus a route-coverage table so a future un-audited mutating element fails the test. Fail-first proven:
with only the template fix reverted, the test fails with
`AssertionError: htmx would send an empty body for post /searches/1/rules/1`. Six further tests POST
the exact rendered payload for each of the six rule kinds and assert a 200 plus unchanged
`params_json` on the edit path. Full suite 626 passed, `ruff` clean.

### G6 — the global Run ignored saved searches — FIXED

Real-corpus UAT against the live DB (`data/jobsearch.db`, 108 listings) produced this gap together with
G7. The user had created exactly one saved search, `Dublin Junior` (`searches.id=1`, `enabled=1`,
`version=2`), whose `criteria_json` is
`{"keywords": "java, ruby, backend, softwarem, engineer", "location": "Dublin", "seniority": ["junior"]}`,
and one exclusion rule (`filter_rules.id=1`, `kind="location"`,
`params_json={"allow": ["Dublin"], "mode": "substring"}`, `position=0`). They pressed the queue's global
**Run** and reported "it found nothing new".

Run row `runs.id=9` (21:11:26→21:11:56, ~30 s, `errors_json=NULL`): `search_id=NULL`, `trigger=manual`,
`status=done`, `reason=nothing_new`, `fetched_count=100`, `deduped_count=0`, `filtered_count=16`.
`reason_counts_json`: `adapters_resolved=2`; `sources.indeed = sources.linkedin = {status: ok, fetched:
50, created: 0, updated: 50, failed: 0, requests_used: 1}`; `excluded_by_rule={"1": 16}`;
`survivors=83`; `duplicates_already_seen=100`; `new_since_watermark=0`; `capability_warnings=[]`.
`stage_log_json` (5 entries): `criteria_compile {warnings: 0}`; `persist:indeed`; `persist:linkedin`;
`dedup {candidates: 102, proposed: 1, skipped_already_merged: 1}`; `filter {enabled_searches: 1,
rules_loaded: 1, candidates: 99, survivors: 83, excluded_listings: 16, exclusions: 16}`.

**"Nothing new" was CORRECT and expected.** All 100 fetched listings already existed — `created: 0` on
both boards, `updated: 50` each, `duplicates_already_seen: 100`, `new_since_watermark: 0` — so no new
listing entered the queue. Fetching is idempotent by design; a re-run of the same corpus keeps reporting
`nothing_new` until a board publishes something new. `app/domain/run_reason.py::compute_empty_reason`
has a fixed precedence (`no_sources_enabled`, `all_sources_failed`, `zero_fetched`, `all_filtered` which
needs `survivors <= 0`, `nothing_new` which needs `survivors > 0` and `new_since_watermark == 0`, then
`mixed`), and run 9 satisfied `nothing_new` exactly. This is the answer to the user's question, recorded
plainly — **not** a defect.

**Root cause: the global Run ignored the saved search's criteria; only the searches' exclusion rules were
unioned.** `app/pipeline/run.py::_resolve_fetch_query` was:

```python
if query is not None:
    return query
if search_id is not None:
    return search_query_from(record.criteria_json)
return default_query()
```

`POST /runs` passes `search_id=None`, so it always used `default_query()` — keywords
`"software engineer"`, `location=settings.probe_query_location` (which is `"Ireland"`),
`results_wanted=50`. Three signals in run 9 corroborate it: `search_id=NULL`; the search's `last_run_at`
stayed `NULL`; and `criteria_compile` reported **0** capability warnings even though the criteria carried
`seniority: ["junior"]` — a filter both adapters declare unsupported (`supports_seniority=False`;
`compile_query_for_source` drops it with a `CapabilityWarning`), so a real compile would have warned.
`searches.is_default` existed but **no code path ever read it** for query resolution.

**The user's decision.** Asked which behaviour they wanted, they chose **"Union of all enabled
searches"**, rejecting both "use the `is_default` search" and "keep and document `default_query()`".
Meaning: fetch each enabled search's criteria, one fetch per search, and union the results into the
queue — mirroring how the exclusion rules already union.

**Fix** (`d222588` `fix(02): the global run fetches the union of enabled searches`, `38c3b23`
`test(02): pin the union-fetch fan-out, merge and dedupe behaviour`):

- `_resolve_fetch_query` was replaced by
  `async def _resolve_fetch_queries(session_factory, query, search_id) -> list[tuple[int | None, SearchQuery]]`:
  an explicit `query` wins (single entry); a scoped `search_id` uses that search's criteria (missing
  search → `[(None, default_query())]`); a global run gets one entry per enabled search ordered by
  `searches.id`; **zero enabled searches → `[(None, default_query())]`** so `POST /runs` and
  `scripts/compose-smoke.sh` still work unconfigured.
- Fetch is sequential across searches and `asyncio.gather`-concurrent within one search; a dedupe set
  keyed `(adapter.name, query)` means identical criteria fetch once.
- New helpers `_FETCH_STATUS_SEVERITY` / `_FETCH_STATUS_RANK` / `_worst_fetch_status` /
  `_merge_source_counts`: per-source counts are summed and status is the worst. Shapes are preserved —
  one `source_counts` entry and exactly one `persist:<source>` stage entry per source;
  `criteria_compile` shape unchanged; capability warnings deduped; watermark, `reason_counts_json`, the
  reason enum and `_write_criteria_snapshot` untouched.
- New `tests/pipeline/test_union_fetch.py`, 8 tests (order, per-search criteria, per-search run
  isolation, same-source merge with worst status, fetch dedupe, warning dedupe, zero-enabled fallback,
  determinism).

### G7 — an Irish county code broke the location rule — FIXED

Same run 9, same corpus as G6. The user's location allow-rule `allow=["Dublin"], mode="substring"`
wrongly excluded two Dublin listings. Boards normalise Irish locations as `<area>, <county>, <country>`
where the middle segment is a **vehicle-registration plate code**, not a county name: the corpus
contains `blanchardstown, d, ie` and `cloghran, d, ie`, neither of which contains the substring
`dublin`. Of the 16 exclusions in run 9, 12 were clearly correct (Cork ×5, Galway ×4, Limerick, Sligo,
Kilcoole/Wicklow), 2 were `remote, ie`, and **2 were the wrongly-excluded Dublin ones** — `listing_id`
49 "KERNEL SOFTWARE DEVELOPER" at `blanchardstown, d, ie`, and `listing_id` 103 "CRM Developer" at
`cloghran, d, ie`. `normalise_location` was just `normalise_text`, and **no county mapping existed
anywhere in the repo**.

The distinct second-segment codes actually present in the corpus:

| second segment | notes |
|---|---|
| `county dublin` ×45 | spelled-out form |
| `d` ×44 | Dublin plate code |
| `c` ×4 | Cork plate code (divergent — see the review) |
| `wd` ×3 | Waterford, plate == ISO |
| `county galway` ×3 | spelled-out form |
| `ie` ×2 | country leaked into the county slot (`remote, ie`) |
| `lk` | Limerick, plate code |
| `so` | Sligo, plate == ISO |
| `ww` | Wicklow, plate == ISO |
| `ireland` | country leaked into the county slot |
| `county cork` | spelled-out form |

The corpus also contains both `dublin 1, d, ie` and `dublin 2, d, ie` — a **separate** dedup gate treats
those as different jobs, so the location mode must not blur them (see G3).

**The user's decision.** Asked how a location allow-rule should treat these, they chose **"Add a
county-aware match mode"**, rejecting "match the county code inside substring mode" and "leave it to a
wider allow list".

**Fix** (`7d0bff5` `fix(02): a county-aware location rule mode so Irish suburbs are not excluded`,
`7ddd62e` `fix(ui): let the criteria forms choose the location rule mode`):

- `app/domain/filter.py`: added `IE_COUNTY_NAME_BY_CODE` (all 26 ISO 3166-2:IE code→name) and
  `LOCATION_MODES = ("substring", "county")`, and taught `_eval_location` the mode logic — when
  `mode == "county"` a term matches if it is a casefolded substring of the haystack **or** equals the
  resolved county name **or** equals the resolved county code; otherwise the original substring rule
  runs. Strictly add-only: absent / `"substring"` / unrecognised mode → substring. A falsy
  `location_norm` still returns `None`. The exclusion `detail` dict is unchanged (a test pins the exact
  key set).
- `app/db/repositories/search_repo.py`: `validate_rule_params` rejects a present `mode` not in
  `LOCATION_MODES`.
- `app/web/templates/html/criteria.html`: the create form's mode select gained
  `county (Irish counties)`; the edit form's hidden `location_mode` input became a visible labelled
  select with the stored mode preselected (so a rule can be switched without delete/recreate). No new
  CSS classes → no stylesheet rebuild.
- 14 new tests, no existing assertion modified.

**No migration was needed:** `mode` is stored in free-form `params_json` and the CHECK constraint is on
`kind`, so a new mode **value** required no schema change.

#### Review findings and fixes

An independent reviewer (the project's @oracle) reviewed both lanes and found two defects that had to be
fixed before closing, plus three follow-ups. All five are recorded here, split FIXED / FOLLOW-UP.

**FIXED NOW** (`f01ae1c`, `eb4806f`, `87ff974`):

- **`f01ae1c` — the county map was keyed to ISO codes but the boards emit plate codes.** Cork is the
  divergent case: the board emits `c`, the ISO code is `co`, and the map only had `"co"`, so
  `midleton, c, ie` resolved to no county and `allow=["cork"]` still wrongly **excluded** a Cork suburb
  whose town name does not literally contain "cork". Most other counties coincidentally have
  plate == ISO (`d`=Dublin, `g`=Galway, `wd`=Waterford, `ww`=Wicklow, `so`=Sligo, `lk`=Limerick),
  which is why Dublin appeared to work. Also affected: Tipperary (plate `t`, older `tn`/`ts`, ISO `ta`)
  and Limerick (plate `l`). Fix: added `IE_COUNTY_PLATE_CODE_BY_NAME` for the divergent plate codes,
  built `_COUNTY_NAME_BY_ANY_CODE` as a disjoint superset of the ISO table (strictly add-only; no ISO
  key removed or re-keyed), and made `_county_from_location` resolve the combined table, match a bare
  county name, and strip a leading `county ` before name lookup, so the `county <name>` second-segment
  form (e.g. `swords, county dublin, ireland`) resolves too. `IE_COUNTY_NAME_BY_CODE` and
  `_COUNTY_CODE_BY_NAME` remain the ISO reference/inverse.
  - The most important detail: the original Cork test passed **only via the substring branch**
    (`"cork"` appears literally in `"cork, c, ie"`), so it never exercised code resolution for a
    non-Dublin county and gave false confidence. The new regression
    `tests/domain/test_filter.py::test_location_county_mode_accepts_a_cork_plate_code_suburb` was proven
    to FAIL on the unmodified code (verbatim:
    `assert [RuleOutcome(... 'location_norm': 'midleton, c, ie', 'allowed': ['cork'])] == []`) and pass
    after.
  - Residual limitation: a bare *plate* term (e.g. `allow=["c"]`) does not match the county-name branch,
    but it still matches the raw location string through the always-evaluated substring branch.
- **`eb4806f` — a false `all_sources_failed` reason.** The union run stores the **merged worst**
  per-source status (`_worst_fetch_status`), and `compute_empty_reason` fired `all_sources_failed` on
  `all(status != "ok")` with **no `fetched` guard**. So two enabled searches on one board, one `ok`
  (fetching listings) and one `blocked`, produced the reason `all_sources_failed` and a stored sentence
  claiming all sources failed and nothing was fetched — factually false, since listings were fetched and
  survived. (The run-level `status` badge was unaffected, because it uses the raw `results` list.)
  Fix: branch 2 of `compute_empty_reason` now also requires `fetched <= 0`. Chosen over passing pre-merge
  statuses in, because it is the smaller change and keeps the pure enum a function of `RunCounts`
  alone. Precedence order and `reason_sentence` unchanged. New tests:
  `tests/domain/test_run_reason.py::test_all_sources_failed_does_not_fire_when_listings_were_fetched`,
  `...::test_all_sources_failed_still_fires_when_every_source_failed_and_nothing_was_fetched`, and
  `tests/pipeline/test_union_fetch.py::test_one_ok_one_blocked_search_does_not_claim_all_sources_failed`.
- **`87ff974` — a union run never stamped per-search `last_run_at`.** `_stamp_last_run` ran only when
  `search_id is not None`, so after the union change the global run fetched each enabled search's
  criteria while leaving every search's "last run" line blank on `/searches` — the very confusing signal
  that started the investigation. Fix: `_stamp_last_run(session_factory, search_ids, now)` now takes a
  sequence and stamps every search the union actually fetched (the ids from `_resolve_fetch_queries`),
  all with one shared timestamp; the explicit-`query` path and the zero-enabled `default_query()`
  fallback stamp nothing, since neither is attributable to a saved search.
  `tests/pipeline/test_single_search_run.py::test_the_union_run_still_unions_every_enabled_search` had
  its closing block changed from asserting both searches' `last_run_at is None` to `is not None` — **a
  deliberate relabel, not a weakened assertion**: the old assertion pinned the pre-`d222588` premise that
  a global run used `default_query()` and was attributable to no search, and that premise changed. The
  replacement asserts more, and new tests `test_a_union_run_stamps_every_search_it_fetched` (also
  asserts one shared timestamp), `test_a_union_run_with_no_enabled_searches_stamps_nothing` and
  `test_an_explicit_query_run_stamps_no_search` were added.

**FOLLOW-UPS** (deliberately NOT fixed — open, non-blocking):

- `fetched_count` now sums fetch **events** across searches, so a listing returned by two searches is
  counted twice; `merge_rate()` in `app/db/repositories/dupe_repo.py` divides `merged` by that
  `fetched_count`, so its numerator and denominator are no longer in the same units. Latent (only
  manifests with 2+ enabled searches hitting the same board). Needs a semantics decision: is
  `fetched_count` fetch events or unique listings?
- `searches.is_default` is now **dead** — no consumer reads it for query resolution, and the union design
  removes the "default search" concept. Either give it a consumer or remove the column/field/param.
- The fetch dedupe key uses the **uncompiled** query, so two searches whose criteria compile to the same
  board query both fetch. Safe direction (over-fetch, never under-fetch), so "identical criteria fetch
  once" is narrower than "identical effective query fetch once".
- `errors_json` can now carry multiple entries per source (one per failed fetch) where it previously had
  one. Renders fine; noted in case a consumer assumes one-per-source.

**Verification.** Full suite after all three fixes: **660 passed, 2 deselected** (was 648 before the
review fixes; 648 was itself 634 + the 14 G7 tests; 634 was 626 + the 8 G6 tests). `ruff check app tests`
clean. `git status --porcelain data` empty throughout — `data/` was never written.

#### Operator step still outstanding

On the host: rebuild (`docker compose down && docker compose up -d --build --wait`) — the running image
predates `d222588`, `38c3b23`, `7d0bff5`, `7ddd62e`, `f01ae1c`, `eb4806f`, `87ff974`; revert the 6 wrong
merges on `/merges`; switch the `Dublin Junior` location rule to `mode = county` using the new select on
`/searches`; add a `seniority` exclusion rule to enforce "junior" locally, because both boards declare
`supports_seniority=False` and cannot filter on it; and optionally fix the `softwarem` keyword, which is
probably a typo for `software`.
