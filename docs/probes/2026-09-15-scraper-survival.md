# Scraper-survival verdict — Phase 1

**Status: PROVISIONAL** — 1 probe run recorded on 1 distinct day (2026-09-15).
The ≥3-distinct-day window is **not yet met**, so this is not a measurement.

**Date opened:** 2026-09-15
**Instrument:** `app/probe/survival.py` (signals S1–S6), `tests/live/test_probe_live.py` (the run), `scripts/run-probe.sh` (the entry point)
**Runbook:** `docs/probes/README.md`
**Window:** target ≥3 runs on ≥3 distinct days; achieved **1 run on 1 day** (`runs.id = 1`, 2026-09-15)
**Evidence DB:** `data/probe.db` (gitignored; every figure below was read from it)

---

## 1. Why this document is PROVISIONAL and not FINAL

The phase-gate measurement needs an observation window: the count-delta and
fill-rate signals require a baseline **and** at least one prior run, and a single
sample cannot distinguish "the board is fine" from "the board happened to answer
once". Presenting one run as a measurement is the measurement equivalent of a
fabricated CV claim, and this project's ethical line applies to its own evidence.

The operator has run the probe once and will keep running it daily; the verdict is
refreshed per run until the window is met. **This document will be flipped to FINAL
only when ≥3 distinct days are recorded**, at which point §2 and §3 are replaced
with the accumulated figures.

One run *is* enough to prove the instrumentation works end to end: real rows were
produced in all three recording places, and both signals that do not need a window
(S1, S5) evaluate cleanly. That is a different claim from "scraping survives", and
this document keeps the two apart.

## 2. Per-source raw numbers

Source: `runs.source_counts_json` for `runs.id = 1` (`trigger=manual`, `status=done`,
`started_at=2026-09-15 20:23:40`).

| Source | Runs | `ok` | other statuses | `fetched` | `created` | `updated` | `failed` | `requests_used` | Baseline recorded |
|--------|------|------|----------------|-----------|-----------|-----------|----------|-----------------|-------------------|
| indeed | 1 | 1 | — | 34 | 1 | 33 | 0 | 1 | yes (2026-09-15) |
| linkedin | 1 | 1 | — | 34 | 1 | 33 | 0 | 1 | yes (2026-09-15) |

`source_request_log`: **2 rows**, one per board, all `kind=search`,
`ok=True`, `status_code=NULL`, note
`ok: no observable status returned 34 rows`.
`status_code` is NULL by design: JobSpy does not surface the HTTP status, so the
ledger records what was actually observable and says so in the note.

> **Caveat — the `created`/`updated` split in this first run is NOT representative.**
> `runs.id = 1` predates commit `489422d` ("convert a scraped DataFrame to rows, not
> column labels"). Before that fix, `list(frame)` iterated the DataFrame's **column
> labels**, so all 34 rows mapped to one blank listing — which is exactly the
> `created 1 / updated 33` signature above. After the fix, the compose run in §7
> shows the healthy signature (`fetched 50, created 50, updated 0` per board, 100
> distinct `content_hash` values). Read this column as "the instrumentation ran",
> not as a result about either board; the next daily run will replace it.

## 3. Signal-by-signal verdict

Each row names the `Settings` field the boundary comes from, so Phase 8 can
re-evaluate the condition by code rather than by re-reading this prose.

| Signal | What it answers | Threshold (setting = value) | Observed (1 run) | Verdict |
|--------|-----------------|-----------------------------|------------------|---------|
| **S1** status distribution | how often the board pushed back | `probe_promotion_blocked_runs` = 3 of `probe_promotion_window_runs` = 5 | 0 blocked / 0 rate-limited across 2 source-runs | **PASS**, window not full (1 of 5 runs) |
| **S2** fill-rate vs baseline | did a field's fill-rate collapse | `probe_fill_rate_warn_drop_points` = 10 (WARN) · `probe_fill_rate_fail_drop_points` = 25 (FAIL) | baselines recorded for both boards; no second run to compare | **not armed** — a drift needs a subsequent run |
| **S3** count delta | did output collapse vs the trailing mean | `probe_count_warn_drop_pct` = 25 (WARN) · `probe_count_fail_drop_pct` = 50 (FAIL); trailing `probe_count_trailing_runs` = 5; armed at `probe_min_runs_before_arming` = 2 | 0 prior runs | **not armed** — needs ≥2 prior runs |
| **S4** freshness | `ok` but nothing new | `probe_freshness_fail_runs` = 3 consecutive | 1 run | **not armed** — needs 3 consecutive runs |
| **S5** block vs parse | which side failed | ledger `ok` + note (`source_request_log`) | 2/2 rows `ok`, note classifies as healthy | **PASS** — no fetch-side or parse-side failure recorded |
| **S6** schema drift | did JobSpy's columns change | pinned `desired_order` (`app/sources/_jobspy_mapping.py`) | the live lane records no column set | **not measured** — see `tests/probe/test_thresholds.py` for the offline contract |

A signal that cannot be computed reports `skip`/`not armed` rather than a
fabricated pass. With one run, four of the six are in that state by construction.

## 4. Derivation — where every figure comes from

| Reported figure | Derived from | Produced by |
|-----------------|--------------|-------------|
| Per-source run status counts (S1) | `runs.source_counts_json[source]["status"]` | `run_pipeline()` |
| Listings returned (S3 input) | `runs.source_counts_json[source]["fetched"]` | `_persist_result()` |
| New listings written (S4 input) | `runs.source_counts_json[source]["created"]` | `_persist_result()` |
| Fill-rate per field (S2 input) | the normalised `listings` rows of a run, via `compute_fill_rates()` | `_persist_result()` + `app/probe/survival.py` |
| Baseline (S2 reference) | `sources.field_fill_baseline_json`, `sources.baseline_recorded_at` | `record_baseline()` on the first successful run |
| Fetch-side vs parse-side (S5) | `source_request_log.kind` / `.status_code` / `.ok` / `.note` | `record_fetch_outcome()` per outbound request |
| Probe liveness (P-4) | `sources.health` / `sources.last_probe_at`, or `/health`'s `sources[].probe` | `probe_all()` |
| Schema drift (S6) | the returned column set vs `DESIRED_ORDER` | `detect_schema_drift()` |
| Requests used (envelope) | `runs.source_counts_json[source]["requests_used"]` | `_persist_result()` |

Every figure in §2 and §3 was read from these rows. What the instrumentation
cannot yet show is the one thing a window is for: how a board behaves *across* runs.

## 5. Which board failed

**Neither board failed — and that is not yet a verdict.** Both returned
`status=ok`, 34 rows each, and one clean ledger row each; nothing in the recorded
rows shows a block, a rate limit or a parse-side miss.

With one run this says only "both boards answered once". The signals that detect
*silent* degradation (S2 drift, S3 count collapse, S4 freshness) are all
window-dependent and therefore all unarmed. This paragraph must name the failing
board(s) — "scraping failed" is not a decision — if and when a condition fires.

## 6. The Adzuna promotion condition (D-04 / P-1 … P-5)

Reproduced here **by name**, with the same settings keys `app/probe/survival.py`
reads, so Phase 8 can re-evaluate it by code. Promote Adzuna from hedge to primary
at Phase 8 if **any** of the following holds on the Phase-1 probe evidence:

| # | Condition | Signal | Setting(s) | Current verdict |
|---|-----------|--------|------------|-----------------|
| **P-1** | a board returns `blocked` or `rate_limited` on ≥3 of 5 probe runs in the window | S1 | `probe_promotion_blocked_runs` = 3, `probe_promotion_window_runs` = 5 | not fired (0 blocked), window not full |
| **P-2** | a board's `title`, `company_name` or `location_raw` fill-rate drops ≥25 points below baseline on ≥2 consecutive runs | S2 | `probe_fill_rate_fail_drop_points` = 25, `probe_promotion_consecutive_runs` = 2 | not armed (no second run) |
| **P-3** | a board's output count falls below the trailing average by ≥25% on ≥2 consecutive runs | S3 | `probe_count_warn_drop_pct` = 25, `probe_promotion_consecutive_runs` = 2 | not armed (0 prior runs) |
| **P-4** | `probe()` reports `unreachable` on ≥2 consecutive days | `probe()` | `probe_promotion_consecutive_runs` = 2 | not armed (the live lane does not call `probe()`) — **see §7's caveat** |
| **P-5** | a board returns `ok` with zero new listings for ≥3 consecutive runs (the S4 contradiction) | S4 | `probe_freshness_fail_runs` = 3 | not armed (1 run) |

**Keep as hedge while:** both boards return `ok`/`partial`, the `title` /
`company_name` / `location_raw` fill-rate stays within 25 points of baseline, and
output stays within 25% of the trailing average.

**Current recommendation: keep Adzuna as hedge, decision deferred to Phase 8.**
No condition is evaluable on one run, and a structural condition must not be
resolved on absent evidence.

Note on P-3's wording: RESEARCH phrases it as "output count falls ≤25% of the
trailing average", while S3's boundary is a ≤ −25% delta. This document — and the
code — use the **S3 boundary** (`probe_count_warn_drop_pct`, a 25% drop), so the
document and the implementation agree. If the stricter "falls *to* 25%" reading was
intended, it is a one-setting change and Phase 8 should decide.

## 7. Open limitation — `probe()` is not a reliable proxy for `fetch()`

Recorded with the evidence, because it is a genuine hole in the instrumentation
rather than a cosmetic one. Also logged as `.planning/WINDOWS.md` entry #4.

During the compose smoke, in the **same container session**:

| Observation | Value |
|---|---|
| `sources.health` written by `/health` at 21:02:36 | `indeed: unreachable`, `linkedin: degraded` |
| `runs.id = 1` (`data/jobsearch.db`) at 21:02:01 | `indeed: ok, fetched 50` · `linkedin: ok, fetched 50`, 100 distinct `content_hash`, 0 blank titles |

So `probe()` — a plain `httpx` GET of one fixed public URL, classified by status /
body length / stop signals — reported both boards unhealthy roughly **35 seconds
after** `fetch()` had pulled 50 usable listings from each. The two instruments use
different request paths (the probe's own client vs JobSpy's), so the probe's
classification is **not** a reliable proxy for ingest success.

Consequences, stated plainly:

- **The survival verdict is unaffected**, because it is derived from `runs` and
  `source_request_log` (both healthy), not from `probe()`. §2/§3 stand.
- **`/health`'s per-source liveness badge is optimistic-to-misleading**: it can show
  a board as degraded or unreachable while ingestion is working. A user reading the
  health strip would draw the wrong conclusion even though the queue fills.
- **P-4 is not usable as written** until this is resolved: it is the one promotion
  condition that reads `probe()` rather than the ledger.
- This is the same family as `.planning/WINDOWS.md` #3 (the deferred *positive*
  structural marker): `probe()` asserts a known answer on a request path that is
  not the one ingestion uses.

**Candidate human-verification item for phase verification:** decide whether
`probe()`'s fixed URL / classification is wrong, whether the board genuinely served
a challenge page to the probe's client while serving JobSpy normally, or whether the
probe should be re-pointed at (or corroborated by) the ingest path. Until that
decision, treat `/health`'s probe badge as advisory and the ledger as authoritative.

## 8. What is already verified (offline)

- Every WARN/FAIL boundary fires exactly at its configured value and not one step
  earlier, and each P-condition triggers on its own constructed evidence
  (`tests/probe/test_thresholds.py`, 43 tests).
- Every threshold is read from `Settings`; no numeric threshold literal appears in
  `app/probe/` (`tests/test_config.py` scans it).
- The transport has no retry or escalation path for a block (asserted on the AST).
- A run writes exactly one `source_request_log` row per outbound request and
  records the fill-rate baseline once, on the first successful run.
- The DataFrame→rows contract is pinned by real-DataFrame regression tests, so the
  blank-collapse bug cannot return silently.
- The `live` lane is excluded from the default test lane.

---

*Phase: 01-walking-skeleton-foundations · Plan: 01-07*
*Opened: 2026-09-15 · Marker: PROVISIONAL (1 run on 1 day; window target ≥3 days)*
