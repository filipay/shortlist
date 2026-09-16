---
status: testing
phase: 02-clean-filtered-queryable-queue
source: [02-VERIFICATION.md]
started: 2026-09-16T13:30:00Z
updated: 2026-09-16T13:30:00Z
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
result: [pending]

### 2. Merge-rate band sanity check after a real run
expected: After a real run, compare the observed merge rate on `/merges` against the 10–15% band from research and record why the chosen θ is or is not adjusted.
why_human: The band comes from a different market/query shape; QUEUE-09 asks for the rate to be visible and windowed, which is machine-verified, but whether the observed rate is sane needs real data.
result: [pending]

### 3. Compose smoke of the running stack
expected: `docker compose up` and browse the queue; confirm the migration to `0002` applies, the queue renders, and the run trigger works end to end.
why_human: 02-VALIDATION.md lists this as a WINDOWS.md carry-over (open item #1); it needs Docker/network and a human browsing.
result: [pending]

### 4. Confirm the pinned rapidfuzz dependency was human-approved
expected: The approval (version 3.14.6, source repo `rapidfuzz/RapidFuzz`, pre-compiled musllinux wheel, no arbitrary build step) is recorded in 02-02-SUMMARY.md "Authentication Gates".
why_human: An out-of-band human sign-off cannot be machine-verified; recorded as discharged in-phase on 2026-09-16 during execution, re-listed for the end-of-phase human checkpoint.
result: [pending]

### 5. Judge whether the excluded-listing chip satisfies "which rule fired and why"
expected: Under `Show excluded`, each rejected listing shows a chip `rule.kind (count)` (e.g. `exclude_keyword (2)`). Confirm this is sufficient, or require the firing rule id and the matched `detail_json` term (e.g. `crypto`) to be surfaced.
why_human: The rule id and the persisted `listing_exclusions.detail_json` (the matched term/field) have no UI consumer; the chip names only the rule kind plus a per-rule count. This is a product-sufficiency judgment against SC2 / FILT-03 wording, not a machine-definable pass/fail.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
