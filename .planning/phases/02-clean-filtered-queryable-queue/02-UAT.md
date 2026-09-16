---
status: testing
phase: 02-clean-filtered-queryable-queue
source: [02-VERIFICATION.md]
started: 2026-09-16T13:30:00Z
updated: 2026-09-16T17:07:19Z
---

## Current Test

number: 1
name: Tune the dedup threshold θ against the first real corpus
expected: |
  Run a real pipeline run against live LinkedIn/Indeed data, inspect the
  listing_dupes pairs and the merge rate on /merges, and record the chosen
  Settings.dedup_fuzzy_threshold (currently 88) and its justification in docs/.
awaiting: user response

## Tests

### 1. Tune the dedup threshold θ against the first real corpus
expected: Run a real pipeline run against live LinkedIn/Indeed data, inspect the `listing_dupes` pairs and the merge rate on `/merges`, and record the chosen `Settings.dedup_fuzzy_threshold` (currently 88) and its justification in `docs/`.
why_human: No real corpus exists pre-run; θ is deliberately shipped as a setting with a tuning procedure (02-VALIDATION.md Manual-Only; ROADMAP Phase-2 Notes; D-31). Code and tests prove θ is a settings read with no hard-coded literal, not that 88 is the right value.
result: satisfied (2026-09-16) — θ assessed against the real corpus; 88 retained
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
result: investigated (2026-09-16) — the band comparison is NOT answerable from the current display; see G2
evidence: `/merges` reports **0.0%** (latest run #6: 0 merges in its window / 100 fetched) while the
  corpus holds **6 live merges**. A 0% headline for a corpus with six real merges cannot be compared
  against a 10-15% band, so QUEUE-09's "visible, windowed merge rate" is *internally consistent* but
  *unusable as a headline* in steady state. Root cause and the decision needed are recorded as G2.

### 3. Compose smoke of the running stack
expected: `docker compose up` and browse the queue; confirm the migration to `0002` applies, the queue renders, and the run trigger works end to end.
why_human: 02-VALIDATION.md lists this as a WINDOWS.md carry-over (open item #1); it needs Docker/network and a human browsing.
result: satisfied (2026-09-16)
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
result: satisfied (2026-09-16)
evidence: During plan 02-02 execution the human answered the `blocking-human` checkpoint with
  "approved", having been shown: `pip index versions rapidfuzz` → 3.14.6 with a release history
  back to 0.0.6; PyPI metadata homepage/repository `https://github.com/rapidfuzz/RapidFuzz`
  (matching the research citation, no slopsquat); and a pre-compiled
  `rapidfuzz-3.14.6-cp314-cp314-musllinux_1_2_x86_64.whl` (no arbitrary source build).
  Recorded in `02-02-SUMMARY.md`. Nothing about the pin changed since, so the approval stands.

### 5. Judge whether the excluded-listing chip satisfies "which rule fired and why"
expected: Under `Show excluded`, each rejected listing shows a chip `rule.kind (count)` (e.g. `exclude_keyword (2)`). Confirm this is sufficient, or require the firing rule id and the matched `detail_json` term (e.g. `crypto`) to be surfaced.
why_human: The rule id and the persisted `listing_exclusions.detail_json` (the matched term/field) have no UI consumer; the chip names only the rule kind plus a per-rule count. This is a product-sufficiency judgment against SC2 / FILT-03 wording, not a machine-definable pass/fail.
result: [pending]

## Summary

total: 5
passed: 3
issues: 1
pending: 1
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

### G3 — residual dedup gap: identical company+title pairs left unmerged — INVESTIGATE
After 6 merges, groups with identical normalised company AND identical normalised title still hold
more than one un-absorbed listing:
- `mastercard | senior software engineer` — id=3 (indeed) + id=74 (linkedin), the SAME `blocking_key`
  (`mastercard|engineer senior software`). This is the exact cross-source case Tier-2 exists for, so it
  reads as a genuine miss rather than a design limit.
- `jpmorganchase | director of software engineering` — id=23 + id=44, BOTH `indeed`, same
  `blocking_key`. Explainable: Tier-1 cannot catch a repost carrying a new `source_listing_id`, and
  Tier-2 is cross-source by design. Worth documenting as a known same-source-repost limitation.

A plausible mechanism for the cross-source case is a bridge/transitive one — two separate merge chains
never joined, leaving both survivors visible. That is a hypothesis, not a diagnosis, and needs
investigation before any fix. Note also that the UI cannot surface a MISS at all: `/merges` lists only
merged rows, so an unmerged duplicate is invisible by construction.
