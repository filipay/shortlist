#!/usr/bin/env sh
# Migrate, then hand off to the server. Alembic runs on the SYNC URL.
set -e

alembic upgrade head

# `--workers 1` is load-bearing for TWO reasons: the in-process ranking task set,
# and the Phase-8 APScheduler instance — N workers would each start their own
# scheduler, so the same nightly job would run N times (Pitfall 5 / PLAT-06).
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
