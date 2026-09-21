# The scraper-survival probe — operator runbook

This is the phase-gate measurement for Phase 1. The roadmap's blocking unknown #2
is *"does scraping survive at personal scale?"*, and it is retired only by a
**recorded verdict with an observation window** — never by "the probe exists".

Two instruments, deliberately kept apart:

| | `probe()` — liveness | The survival measurement — the verdict |
|---|---|---|
| Cost | 1 cheap request per board | One bounded search per board (the real ingest path) |
| Cadence | On `/health`, TTL-cached (`probe_cache_ttl_seconds`) | Once per day, operator-run |
| Output | `ok` / `degraded` / `unreachable` | The six signal families in `app/probe/survival.py` |
| Answers | "Is the board reachable right now?" | "Does scraping survive, and should Adzuna be promoted?" |

## The documented operating envelope (a policy statement, not a default)

> **1 search per board, ≤50–100 results, once per day, one IP, honest User-Agent.**

This is the ban-risk line. It is configuration (`app/config.py`, `probe_*`) so it can
be *lowered* without a code change, and `scripts/run-probe.sh` **refuses to run** with
it raised above the ceiling unless you explicitly pass
`--i-understand-the-ban-risk`.

The correct response to a block signal is to **record it and stop**. The transport
has no retry path for a `blocked`/`rate_limited` outcome (asserted by
`tests/probe/test_thresholds.py`): escalating from a block is how a maintenance
problem becomes an account ban.

**There is no target fill-rate for any field.** Every judgement is a *delta* against
the recorded baseline or a trailing average. JobSpy's description-salary extraction
is USA-only, so an Irish search is structurally low on `salary_*`; a target there
would fail forever and mean nothing.

## Precondition: the interpreter must match the host platform

> **The interpreter used for a probe run must have the project's dependencies
> compiled for the host platform.** A venv built inside a musl container (such as
> this sandbox) cannot be reused on a glibc host: native extensions fail to load,
> e.g. `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`.
> `scripts/run-probe.sh` fails fast with exit 2 and the underlying import error
> rather than running the live lane with an empty envelope.

Build the venv for the host you are running on, or point `PYTHON=` at an
interpreter that already has the dependencies:

```bash
python3.13 -m venv .venv && .venv/bin/pip install -e '.[dev]'
PYTHON=/path/to/such/python bash scripts/run-probe.sh
```

## The source allow-list is seeded automatically

The `sources` table is the run-time allow-list, and its rows are seeded from the
adapter registry (`app/sources/registry.py`) — **you never insert them by hand**:

- at app boot, the FastAPI lifespan inserts one row per registered adapter;
- `scripts/run-probe.sh` does the same after the migration and before the live
  lane, so the probe (which never boots the app) also has its rows.

Every registered adapter is inserted `enabled=True`, and the step is idempotent
(a second call inserts nothing). If the table were empty, every run would resolve
zero adapters and fetch nothing.

## Commands

```bash
# One bounded probe run. Run this ONCE PER DAY, on at least 3 distinct days.
bash scripts/run-probe.sh

# Check the envelope and print the plan without issuing a request:
bash scripts/run-probe.sh --dry-run

# The live lane directly (used by the script):
.venv/bin/python -m pytest -q -m live
```

The `live` marker is excluded from the default lane by
`addopts = "-m 'not live'"` in `pyproject.toml`: a live scrape against hostile
third-party boards must never be a CI test.

By default the script writes its evidence to `data/probe.db` (gitignored), so your
`/data` volume is untouched. Override with `PROBE_DB=/some/path.db`.

## What to capture after each run

Exactly three recording places feed the verdict:

1. **`runs`** — one row per run. `source_counts_json` carries the per-source
   `status`, `fetched`, `created`, `updated`, `failed` and `requests_used`.
2. **`source_request_log`** — one row per outbound request: `source`, `run_id`,
   `occurred_at`, `kind` (`search`/`detail`), `status_code`, `ok`, and a `note`
   classifying **fetch-side** (403/429/stop signal) versus **parse-side** (a valid
   page with no matching rows). The two need opposite fixes and both look like
   empty data.
3. **`sources.field_fill_baseline_json` + `baseline_recorded_at`** — the fill-rate
   baseline, written once on the first successful run per source and never
   overwritten, so drift is measurable.

`scripts/run-probe.sh` prints all three at the end of every run. Copy that output;
it is the raw material for the verdict document.

## The observation window

- Target: **≥3 runs on ≥3 distinct days** (the roadmap's count-delta and fill-rate
  signals need a baseline *and* at least one prior run).
- If the window cannot be met, the verdict is written **PROVISIONAL** with the
  actual run count, and the Adzuna decision stays deferred to Phase 8 (which the
  roadmap already provides for).
- **A single run is not a measurement.** Presenting one as a verdict is the
  measurement equivalent of a fabricated CV claim — the project's ethical line
  applies to its own evidence too.

## Writing the verdict document

Create `docs/probes/YYYY-MM-DD-scraper-survival.md` dated with the **first** run's
date. It must contain:

- the per-source raw numbers (from `runs.source_counts_json`);
- the baseline used and when it was recorded;
- each signal's observed value **against its named threshold**, with an explicit
  PASS/FAIL (or `not armed` with the reason);
- the observation window and the actual run count;
- an explicit **PROVISIONAL** or **FINAL** marker;
- a paragraph naming which board (if any) failed — "scraping failed" is not a
  decision;
- the Adzuna promotion condition **P-1…P-5 reproduced by name**, with the current
  verdict against it and the note that the promote/keep decision is taken at
  Phase 8.

Every figure must be traceable to a `runs` or `source_request_log` row. If a number
is not in those rows, the instrumentation is incomplete — fix the instrumentation,
do not write the number.

**Never paste listing text into the document.** Counts, status codes and fill-rates
only: the document is committed, and listing content can carry recruiter PII.

## The second probe: the LaTeX CV decomposition spike (Phase 4)

`docs/probes/` now holds **two** probes, with two different instruments and two
different cadences:

| | Scraper survival (Phase 1) | LaTeX CV decomposition (Phase 4) |
|---|---|---|
| Instrument | `app/probe/survival.py` + `scripts/run-probe.sh` | `app/cv/import_tex.py` + `scripts/cv-tex-spike.sh` |
| Cadence | once per day, target ≥3 distinct days | once against the real document, re-runnable whenever the CV changes |
| Verdict | `docs/probes/2026-09-15-scraper-survival.md` | `docs/probes/2026-09-21-cv-tex-spike.md` |

The LaTeX spike turns the human's `cv/base.tex` into a **review draft** fact store
plus a report of everything the bounded parser could not resolve. Nothing is
guessed, and the draft is written to a separate path — never back over the source
and never over `cv.yaml`. It is **re-runnable whenever the real CV changes**.

- Verdict: `docs/probes/2026-09-21-cv-tex-spike.md` — status `PARTIAL` until the
  real document is measured, with an `UNRESOLVED` section naming the exact trigger.
- Command: `bash scripts/cv-tex-spike.sh`.
- Container compile lane and the engine switch: `docs/runbook-latex-compile.md`.

**Never paste CV text or personal detail into either document.** Counts, package
names, versions, commands and unit-suffixed durations only.

## Closing WINDOWS.md #3 (the deferred structural marker)

`probe()` currently asserts HTTP status, a minimum body length and the absence of
stop signals — three of the four signals RESEARCH specifies. The fourth, a
**positive structural marker** (an element known to appear on a healthy page), was
deferred because no live page was ever read and a guessed marker would cause *false*
`degraded` classifications.

A probe run is the opportunity to close it: while inspecting the raw pages, note one
stable element per board, implement it in that adapter's `probe()`, and mark
ledger entry #3 fixed. Until then the gap is recorded, not claimed.
