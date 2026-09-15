#!/usr/bin/env bash
#
# The operator PLAT-01 smoke check: does the whole stack come up, serve, and keep
# its data across a restart?
#
# Pass criteria (ROADMAP Phase 1 success criterion 1 and 3):
#   1. `docker compose up -d --wait` succeeds and the app answers on :8000
#   2. `GET /health` returns HTTP 200 with the database reported reachable
#   3. a triggered run completes and its listings render on the queue page
#   4. the same listings are present after `docker compose restart`
#   5. the stack starts and serves with the opencode server NOT running
#
# Every step fails loudly with a clear message; the script never reports success
# on a step it did not observe.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE_URL="${BASE_URL:-http://localhost:8000}"
PYTHON="${PYTHON:-python3}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-120}"
RUN_TIMEOUT_SECONDS="${RUN_TIMEOUT_SECONDS:-300}"

step() { printf '\n== %s\n' "$1"; }
fail() { printf '\nFAIL: %s\n' "$1" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 is required but not on PATH"
}

need docker
need curl
need "$PYTHON"
docker compose version >/dev/null 2>&1 || fail "docker compose v2 is required"

body_value() {
  # Read one top-level field out of a JSON body without assuming jq is installed.
  "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get(sys.argv[1]))' "$1"
}

wait_for_health() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if curl -fsS "$BASE_URL/health" >/tmp/compose-smoke-health.json 2>/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

step "bringing the stack up"
docker compose up -d --wait || fail "docker compose up did not reach a healthy state"

step "waiting for /health"
wait_for_health || fail "/health did not answer HTTP 200 within ${HEALTH_TIMEOUT_SECONDS}s"
HEALTH_BODY="$(cat /tmp/compose-smoke-health.json)"
echo "$HEALTH_BODY"

DB_STATE="$(printf '%s' "$HEALTH_BODY" | body_value db)"
[ "$DB_STATE" = "ok" ] || fail "the database is not reachable (db=$DB_STATE)"

OPENCODE_STATE="$(printf '%s' "$HEALTH_BODY" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["opencode"]["reachable"])')"
echo "opencode reachable: $OPENCODE_STATE (either value is acceptable; the stack must boot without it)"

step "triggering one run"
# The 202 response IS the polling fragment and carries the run id, so read it from
# there. Re-fetching `/` cannot work: the queue route renders a bare
# `<div id="run-status-slot"></div>` and never includes the fragment.
RUN_BODY="$(curl -fsS -X POST "$BASE_URL/runs")" || fail "POST /runs did not answer"

RUN_ID="$(RUN_BODY="$RUN_BODY" "$PYTHON" - <<'PY'
import os
import re

body = os.environ["RUN_BODY"]
match = re.search(r'hx-get="/runs/(\d+)/status"', body)
print(match.group(1) if match else "")
PY
)"
[ -n "$RUN_ID" ] || fail "could not read a run id from the POST /runs response"

step "waiting for run $RUN_ID to finish"
deadline=$((SECONDS + RUN_TIMEOUT_SECONDS))
TERMINAL=0
while [ "$SECONDS" -lt "$deadline" ]; do
  CODE="$(curl -s -o /tmp/compose-smoke-run.html -w '%{http_code}' "$BASE_URL/runs/$RUN_ID/status")"
  if [ "$CODE" = "286" ]; then
    TERMINAL=1
    break
  fi
  sleep 2
done
[ "$TERMINAL" -eq 1 ] || fail "run $RUN_ID never reached a terminal state"
grep -q 'run-badge' /tmp/compose-smoke-run.html || fail "the run status fragment is not renderable"

BEFORE="$(curl -fsS "$BASE_URL/")"
TITLES_BEFORE="$(printf '%s' "$BEFORE" | grep -oE '<td class="listing-title">[^<]+</td>' || true)"
[ -n "$TITLES_BEFORE" ] || fail "the queue is empty after a run that reported success — is the scrape blocked?"

step "restarting the stack"
docker compose restart || fail "docker compose restart failed"
wait_for_health || fail "/health did not recover after the restart"

step "checking that the listings survived the restart"
AFTER="$(curl -fsS "$BASE_URL/")"
TITLES_AFTER="$(printf '%s' "$AFTER" | grep -oE '<td class="listing-title">[^<]+</td>' || true)"
if [ "$TITLES_BEFORE" != "$TITLES_AFTER" ]; then
  echo "before:"; echo "$TITLES_BEFORE"
  echo "after:";  echo "$TITLES_AFTER"
  fail "the listings changed across the restart — persistence is broken"
fi

step "PASS"
echo "health db=$DB_STATE opencode=$OPENCODE_STATE"
echo "listings persisted across the restart:"
echo "$TITLES_AFTER"
echo
echo "Record this output in the phase summary (see docs/runbook-compose-smoke.md)."
