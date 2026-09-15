# Scraper-survival verdict — Phase 1

**Status: PROVISIONAL** — 0 probe runs recorded on 0 distinct days.

**Date opened:** 2026-09-15
**Instrument:** `app/probe/survival.py` (signals S1–S6), `tests/live/test_probe_live.py` (the run), `scripts/run-probe.sh` (the entry point)
**Runbook:** `docs/probes/README.md`
**Window:** target ≥3 runs on ≥3 distinct days; achieved **0 runs on 0 days**

---

## 1. Why this document is PROVISIONAL and not FINAL

The phase-gate measurement is live scraping against hostile third-party boards,
which the agent sandbox cannot perform (no network egress to the boards, and
PITFALLS P13 forbids a live scrape in CI). The instrument, the operator entry point
and every WARN/FAIL boundary are implemented and boundary-tested offline
(`tests/probe/test_thresholds.py`, 43 tests); the **measurement itself** is the
operator's run.

There are therefore **no per-source numbers to report**. Inventing one — or
presenting a single run as a measurement — is the measurement equivalent of a
fabricated CV claim, and this project's ethical line applies to its own evidence.
The document is committed now, in its empty state, so that:

- the phase cannot close with "the probe exists" but no recorded verdict;
- the next reader can see exactly which figures are missing and where they will
  come from (`§4 Derivation`);
- the Adzuna decision is explicitly deferred rather than silently defaulted.

**To make this FINAL:** run `bash scripts/run-probe.sh` once per day on ≥3 distinct
days, then replace §2 and §3 with the recorded figures and flip the marker.

## 2. Per-source raw numbers

| Source | Runs | `ok` | `partial` | `blocked` | `rate_limited` | `error` | Listings returned (last run) | Baseline recorded at |
|--------|------|------|-----------|-----------|----------------|---------|------------------------------|----------------------|
| linkedin | 0 | — | — | — | — | — | — | not yet |
| indeed | 0 | — | — | — | — | — | — | not yet |

_No `runs` or `source_request_log` rows exist yet (0 runs). `scripts/run-probe.sh`
prints this table from `runs.source_counts_json` after every run._

## 3. Signal-by-signal verdict

Each row names the `Settings` field the boundary comes from, so Phase 8 can
re-evaluate the condition by code rather than by re-reading this prose.

| Signal | What it answers | Threshold (setting = value) | Observed | Verdict |
|--------|-----------------|-----------------------------|----------|---------|
| **S1** status distribution | how often the board pushed back | `probe_promotion_blocked_runs` = 3 of `probe_promotion_window_runs` = 5 | not measured | **not armed** — no runs |
| **S2** fill-rate vs baseline | did a field's fill-rate collapse | `probe_fill_rate_warn_drop_points` = 10 (WARN) · `probe_fill_rate_fail_drop_points` = 25 (FAIL) | not measured | **not armed** — no baseline recorded |
| **S3** count delta | did output collapse vs the trailing mean | `probe_count_warn_drop_pct` = 25 (WARN) · `probe_count_fail_drop_pct` = 50 (FAIL); trailing `probe_count_trailing_runs` = 5; armed at `probe_min_runs_before_arming` = 2 | not measured | **not armed** — 0 prior runs |
| **S4** freshness | `ok` but nothing new | `probe_freshness_fail_runs` = 3 consecutive | not measured | **not armed** — no runs |
| **S5** block vs parse | which side failed | ledger `ok` + note (`source_request_log`) | no rows | **not armed** — no requests recorded |
| **S6** schema drift | did JobSpy's columns change | pinned `desired_order` (28 columns, `app/sources/_jobspy_mapping.py`) | not measured | **not armed** — no returned column set |

All six signals return `skip` when they are not armed, which is what makes an
honest PROVISIONAL verdict possible: a signal that cannot be computed says so
rather than reporting a fabricated pass.

## 4. Derivation — where every future figure comes from

The verdict must be derivable from the recorded rows. This is the mapping; it is
also the checklist for "is the instrumentation complete?".

| Reported figure | Derived from | Produced by |
|-----------------|--------------|-------------|
| Per-source run status counts (S1) | `runs.source_counts_json[source]["status"]` across runs | `run_pipeline()` |
| Listings returned (S3 input) | `runs.source_counts_json[source]["fetched"]` | `_persist_result()` |
| New listings written (S4 input) | `runs.source_counts_json[source]["created"]` | `_persist_result()` |
| Fill-rate per field (S2 input) | the normalised `listings` rows of a run, via `compute_fill_rates()` | `_persist_result()` + `app/probe/survival.py` |
| Baseline (S2 reference) | `sources.field_fill_baseline_json`, `sources.baseline_recorded_at` | `record_baseline()` on the first successful run |
| Fetch-side vs parse-side (S5) | `source_request_log.kind` / `.status_code` / `.ok` / `.note` | `record_fetch_outcome()` per outbound request |
| Probe liveness (P-4) | `sources.health` / `sources.last_probe_at`, or `/health`'s `sources[].probe` | `probe_all()` |
| Schema drift (S6) | the returned column set vs `DESIRED_ORDER` | `detect_schema_drift()` |
| Requests used (envelope) | `runs.source_counts_json[source]["requests_used"]` | `_persist_result()` |

If a number in §2 or §3 cannot be traced through this table, the instrumentation is
incomplete and the number must not be written.

## 5. Which board failed

**Not yet determinable.** With 0 runs there is no evidence for or against either
board. This paragraph must name the board(s) — "scraping failed" is not a decision —
once the window is met.

## 6. The Adzuna promotion condition (D-04 / P-1 … P-5)

Reproduced here **by name**, with the same settings keys `app/probe/survival.py`
reads, so Phase 8 can re-evaluate it by code. Promote Adzuna from hedge to primary
at Phase 8 if **any** of the following holds on the Phase-1 probe evidence:

| # | Condition | Signal | Setting(s) | Current verdict |
|---|-----------|--------|------------|-----------------|
| **P-1** | a board returns `blocked` or `rate_limited` on ≥3 of 5 probe runs in the window | S1 | `probe_promotion_blocked_runs` = 3, `probe_promotion_window_runs` = 5 | not armed (0 runs) |
| **P-2** | a board's `title`, `company_name` or `location_raw` fill-rate drops ≥25 points below baseline on ≥2 consecutive runs | S2 | `probe_fill_rate_fail_drop_points` = 25, `probe_promotion_consecutive_runs` = 2 | not armed (no baseline) |
| **P-3** | a board's output count falls below the trailing average by ≥25% on ≥2 consecutive runs | S3 | `probe_count_warn_drop_pct` = 25, `probe_promotion_consecutive_runs` = 2 | not armed (0 prior runs) |
| **P-4** | `probe()` reports `unreachable` on ≥2 consecutive days | `probe()` | `probe_promotion_consecutive_runs` = 2 | not armed (no probes) |
| **P-5** | a board returns `ok` with zero new listings for ≥3 consecutive runs (the S4 contradiction) | S4 | `probe_freshness_fail_runs` = 3 | not armed (0 runs) |

**Keep as hedge while:** both boards return `ok`/`partial`, the `title` /
`company_name` / `location_raw` fill-rate stays within 25 points of baseline, and
output stays within 25% of the trailing average.

**Current recommendation: keep Adzuna as hedge, decision deferred to Phase 8.**
No condition can be evaluated yet, and structural conditions such as these must not
be resolved on absent evidence.

Note on P-3's wording: RESEARCH phrases it as "output count falls ≤25% of the
trailing average", while S3's boundary is a ≤ −25% delta. This document — and the
code — use the **S3 boundary** (`probe_count_warn_drop_pct`, a 25% drop), so the
document and the implementation agree. If the stricter "falls *to* 25%" reading was
intended, it is a one-setting change and Phase 8 should decide.

## 7. What is already verified (offline)

- Every WARN/FAIL boundary fires exactly at its configured value and not one step
  earlier, and each P-condition triggers on its own constructed evidence
  (`tests/probe/test_thresholds.py`, 43 tests).
- Every threshold is read from `Settings`; no numeric threshold literal appears in
  `app/probe/` (`tests/test_config.py` scans it).
- The transport has no retry or escalation path for a block (asserted on the AST).
- A run writes exactly one `source_request_log` row per outbound request and
  records the fill-rate baseline once, on the first successful run.
- The `live` lane is excluded from the default test lane.

---

*Phase: 01-walking-skeleton-foundations · Plan: 01-07*
*Opened: 2026-09-15 · Marker: PROVISIONAL (0 runs on 0 days)*
