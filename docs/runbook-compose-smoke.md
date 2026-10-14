# Runbook — the `docker compose` smoke check (PLAT-01)

Phase 1 success criterion 1: *"User can start the whole stack with one
`docker compose up`, open the queue UI in a browser, and see listings that persist
across a restart."*

Docker is absent from the agent sandbox, so this is an **operator-run** check, not
an automated test. It is recorded in `.planning/WINDOWS.md` as an unrun verify
rather than being silently dropped.

## Prerequisites

- Docker Engine **≥20.10** with **Compose v2** (`docker compose`, not
  `docker-compose`). `host-gateway` for the default `OPENCODE_BASE_URL` needs 20.10.
- Port **8000** free on the host.
- The repository checked out with `compose.yml`, `Dockerfile` and `entrypoint.sh`.
- Optional: an uncommitted `.env` containing `OPENCODE_SERVER_PASSWORD` if your
  opencode server requires auth. **This is not required for the smoke to pass** —
  see "opencode absent" below.

## Commands

```bash
# The whole check, start to finish:
bash scripts/compose-smoke.sh

# Or step by step:
docker compose up -d --wait
curl -fsS localhost:8000/health | python3 -m json.tool
curl -fsS -X POST localhost:8000/runs          # trigger one run
# open http://localhost:8000 and confirm the listings render
docker compose restart
# reload http://localhost:8000 and confirm the SAME listings are still there
```

Override the target with `BASE_URL=http://host:port` and the wait budget with
`HEALTH_TIMEOUT_SECONDS` / `RUN_TIMEOUT_SECONDS` if your machine is slow.

## What a pass looks like

1. `docker compose up -d --wait` reaches a healthy state.
2. `GET /health` returns **HTTP 200** with:
   - `"db": "ok"` — the database is reachable;
   - an `"opencode"` object — either `{"reachable": true, ...}` or
     `{"reachable": false, "error": ...}`. **Both are acceptable**: the app must boot
     and serve without the LLM backend (D-08). A non-200 here is the failure.
   - a `"sources"` map; each enabled source may carry `probe`, `last_success_at`,
     `listings_returned` and `field_fill_rate`.
3. After `POST /runs`, the run reaches a terminal state and the queue page
   (http://localhost:8000/) renders listing rows.
4. After `docker compose restart`, `/health` is 200 again and **the same listings**
   are present. This is the persistence half of the criterion: the SQLite file lives
   in the `./data` volume, so a restart must not lose it.
5. The stack starts and serves with the opencode server **not running**.
6. The **daily schedule** survives a restart and fires exactly once (PLAT-06). See
   "The schedule persistence step" below.

## The schedule persistence step (PLAT-06)

Phase 8's schedule lives in a new singleton row and is re-configured at boot by the
scheduler's create-if-absent reconcile. This step is the operator half of PLAT-06:
single-worker safe and persistent across a restart. It is **recorded as an unrun
verify** in `.planning/WINDOWS.md` until an operator signs it off — Docker is
absent from the agent sandbox.

```bash
# 1. Set a daily time on the Settings page, e.g. a couple of minutes ahead:
#    open http://localhost:8000/settings, tick "Run once a day", pick the time,
#    choose Europe/Dublin and press "Save schedule".
#    Confirm the page reports "Schedule saved." and that a next run is shown.

# 2. Restart the containers:
docker compose restart

# 3. After the restart, reload http://localhost:8000/settings and confirm the
#    schedule is still set — the same time, the same timezone, still enabled.

# 4. Wait for the scheduled minute to pass, then count the runs for that trigger:
curl -fsS 'localhost:8000/health' >/dev/null      # app is up
#    open http://localhost:8000/runs and confirm EXACTLY ONE run whose trigger is
#    `schedule` appeared after the scheduled minute — never two.
```

**A second concurrent run is the failure this step exists to catch.** The
single-worker pin (`--workers 1`) is what stops N schedulers each running the same
job, and the database in-flight guard is what stops a scheduled run overlapping an
already-running one. Two `runs` rows with trigger `schedule` in the same minute, or
one `schedule` run plus a second in-flight run, is a failure — record it verbatim,
do not interpret it as a scheduling coincidence.

**What a pass looks like:** the schedule document survives the restart; the
settings page still shows it; and exactly one run row with trigger `schedule`
appears for the scheduled firing.

## Failure modes and what they mean

| Symptom | Meaning |
|---|---|
| `/health` non-200 | The app itself is down — check `docker compose logs app` |
| `"db": "unreachable"` | The SQLite file/volume is not writable; check the `./data` mount and its permissions |
| Queue empty after a run | No enabled sources ran, or the sources returned no matching listings. Both are *results*, not a compose failure. A run that resolved no sources reports `status: partial` with the `no enabled sources` reason in `runs.errors_json`; a blocked board reports `partial` naming the degraded board. Check `runs.source_counts_json` and `source_request_log`. Scrape survival is measured by `scripts/run-probe.sh`, not by this smoke |
| Listings gone after `docker compose restart` | Persistence is broken: the volume is not the configured one, or the backup/restore lost the WAL sidecar (M8) |
| App fails to start with opencode stopped | D-08 regression: nothing in `docker compose up` may depend on an LLM backend |

## opencode absent — the expected behaviour

Stop the opencode server (or simply do not start one: `compose.yml` defines no
opencode service by design, D-05) and bring the stack up:

```bash
docker compose up -d --wait
curl -fsS localhost:8000/health   # still HTTP 200
```

`/health` must still return 200, with `"opencode": {"reachable": false, ...}`, and
the queue page must render an "LLM backend unreachable" indicator instead of
failing. Phase 1 makes no LLM call, so nothing else changes.

## Recording the evidence

Paste the smoke output into the phase summary (or the phase's UAT notes) and keep:

- the `docker compose up` result line;
- the `/health` body (both with opencode running and with it stopped);
- the listing count before and after the restart;
- any failure message verbatim.

This closes `.planning/WINDOWS.md` entry #1 (the unrun compose smoke) and is the
only evidence for PLAT-01, since Docker is unavailable to the agent.
