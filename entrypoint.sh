#!/usr/bin/env sh
# Migrate, then hand off to the server. Alembic runs on the SYNC URL.
set -e

alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
