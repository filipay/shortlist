#!/usr/bin/env bash
#
# The operator entry point for the Phase-1 scraper-survival probe.
#
# One run = one bounded search per enabled board, writing the rows the verdict
# document is derived from (a `runs` row, one `source_request_log` row per
# outbound request, and the S2 baseline on the first successful run).
#
# Run it ONCE PER DAY on at least three distinct days, then write/refresh
# docs/probes/YYYY-MM-DD-scraper-survival.md following docs/probes/README.md.
#
# This script REFUSES to run with the envelope raised above the documented
# personal-scale ceiling unless you pass --i-understand-the-ban-risk. The ceiling
# is the ban-risk line (PITFALLS P2): the response to a block is to record it and
# stop, never to ask for more.
#
# Usage:
#   bash scripts/run-probe.sh [--dry-run] [--i-understand-the-ban-risk]
#
#   --dry-run   Check the envelope and print the plan without issuing a request.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
PROBE_DB="${PROBE_DB:-$ROOT/data/probe.db}"
CONFIRM_FLAG="--i-understand-the-ban-risk"

# The documented personal-scale ceiling (RESEARCH §The config-driven envelope).
# Exceeding these is how personal-scope scraping becomes a ban risk.
CEILING_REQUESTS=2   # 1 search + at most 1 detail pass, per board
CEILING_RESULTS=100  # the documented <=50-100 ceiling
CEILING_DETAIL=1

DRY_RUN=0
CONFIRMED=0

usage() {
  sed -n '2,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    "$CONFIRM_FLAG") CONFIRMED=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "run-probe: unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if [ ! -x "$PYTHON" ]; then
  echo "run-probe: no interpreter at $PYTHON (set PYTHON=... or create .venv)" >&2
  exit 2
fi

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
# Keep the probe evidence in its own database so the verdict is reproducible and
# the operator's /data volume is untouched.
export DATABASE_URL_ASYNC="sqlite+aiosqlite:///$PROBE_DB"
export DATABASE_URL_SYNC="sqlite:///$PROBE_DB"
mkdir -p "$(dirname "$PROBE_DB")"

step() { printf '\n== %s\n' "$1"; }

step "effective envelope"
read -r MAX_REQUESTS MAX_RESULTS MAX_DETAIL <<EOF
$("$PYTHON" - <<'PY'
from app.config import settings

print(
    settings.probe_max_requests,
    settings.probe_max_results,
    settings.probe_max_detail_fetches,
)
PY
)
EOF
echo "probe_max_requests=$MAX_REQUESTS probe_max_results=$MAX_RESULTS probe_max_detail_fetches=$MAX_DETAIL"

if [ "$CONFIRMED" -ne 1 ]; then
  refusal=""
  if [ "$MAX_REQUESTS" -gt "$CEILING_REQUESTS" ]; then
    refusal="probe_max_requests=$MAX_REQUESTS > ceiling $CEILING_REQUESTS"
  elif [ "$MAX_RESULTS" -gt "$CEILING_RESULTS" ]; then
    refusal="probe_max_results=$MAX_RESULTS > ceiling $CEILING_RESULTS"
  elif [ "$MAX_DETAIL" -gt "$CEILING_DETAIL" ]; then
    refusal="probe_max_detail_fetches=$MAX_DETAIL > ceiling $CEILING_DETAIL"
  fi

  if [ -n "$refusal" ]; then
    echo "run-probe: REFUSING to run — $refusal" >&2
    echo "The documented envelope is 1 search per board, <=100 results, once per day." >&2
    echo "Lower it in app/config.py / the environment, or re-run with $CONFIRM_FLAG." >&2
    exit 3
  fi
fi

if [ "$DRY_RUN" -eq 1 ]; then
  step "dry run"
  echo "envelope within the documented ceiling; no request was issued."
  echo "would run: $PYTHON -m pytest -q -m live"
  echo "would write evidence to: $PROBE_DB"
  exit 0
fi

step "migrating the probe database"
"$PYTHON" -m alembic upgrade head >/dev/null
echo "database ready at $PROBE_DB"

step "running one bounded probe (live lane)"
"$PYTHON" -m pytest -q -m live

step "recorded evidence"
"$PYTHON" - <<'PY'
import asyncio
import json

from sqlalchemy import select

from app.db.models import Run, SourceRequestLog
from app.db.session import async_session_maker


async def main() -> None:
    async with async_session_maker() as session:
        runs = list((await session.execute(select(Run).order_by(Run.id))).scalars())
        ledger = list(
            (await session.execute(select(SourceRequestLog).order_by(SourceRequestLog.id)))
            .scalars()
        )

    days = sorted({run.started_at.date().isoformat() for run in runs if run.started_at})
    print(f"runs so far: {len(runs)} on {len(days)} distinct day(s): {', '.join(days) or 'none'}")
    for run in runs:
        print(f"  run {run.id} {run.trigger} {run.status} {json.dumps(run.source_counts_json)}")

    print(f"source_request_log rows: {len(ledger)}")
    for row in ledger:
        print(
            f"  {row.source} kind={row.kind} status_code={row.status_code} "
            f"ok={row.ok} note={row.note!r}"
        )

    if len(days) < 3:
        print(
            "\nPROVISIONAL: fewer than 3 distinct days recorded. Keep the envelope at its "
            "defaults and run again tomorrow; the verdict document must be marked PROVISIONAL "
            "with the actual run count until the window is met."
        )
    else:
        print("\nWindow met. Refresh docs/probes/YYYY-MM-DD-scraper-survival.md now.")


asyncio.run(main())
PY

step "next steps"
echo "1. Run this script once per day until at least 3 distinct days are recorded."
echo "2. Write or refresh docs/probes/YYYY-MM-DD-scraper-survival.md"
echo "   (see docs/probes/README.md for the required contents)."
echo "3. Mark it PROVISIONAL if the window is short, and leave the Adzuna decision to Phase 8."
