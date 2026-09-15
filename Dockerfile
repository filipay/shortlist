# syntax=docker/dockerfile:1
#
# Two stages: the asset builder (Node, image-build only) and the runtime.
# The built CSS + vendored JS are committed under static/vendor/ so the repo
# runs without Node; the builder keeps the image build reproducible (D-14/D-15,
# RESEARCH Open Question 7).

# --- Stage 1: vendor HTMX/Alpine and build Tailwind --------------------------
FROM node:24-slim AS assets
WORKDIR /app
RUN npm install --no-save --no-audit --no-fund \
    htmx.org@2.0.10 \
    alpinejs@3.17.3 \
    tailwindcss@4.3.3 \
    @tailwindcss/cli@4.3.3
COPY assets/tailwind/input.css ./assets/tailwind/input.css
COPY app/web/templates ./app/web/templates
RUN mkdir -p ./static/vendor \
    && ./node_modules/.bin/tailwindcss -i ./assets/tailwind/input.css -o ./static/vendor/app.css --minify \
    && cp ./node_modules/htmx.org/dist/htmx.min.js ./static/vendor/htmx.min.js \
    && cp ./node_modules/alpinejs/dist/cdn.min.js ./static/vendor/alpine.min.js

# --- Stage 2: runtime --------------------------------------------------------
# Python 3.13 — never 3.14 (Playwright/curl_cffi/lxml wheel coverage, D-17).
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# `git` is required to install JobSpy from its pinned git commit.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY entrypoint.sh ./
RUN chmod +x ./entrypoint.sh

# Vendored assets produced by the builder stage.
COPY --from=assets /app/static/vendor ./static/vendor

# Acceptance item 9: exercise `alembic upgrade head` against a throwaway file so
# the migration is proven to apply to a clean database at image build time.
RUN DATABASE_URL_SYNC=sqlite:////tmp/migration-smoke.db alembic upgrade head \
    && rm -f /tmp/migration-smoke.db /tmp/migration-smoke.db-wal /tmp/migration-smoke.db-shm

EXPOSE 8000

CMD ["./entrypoint.sh"]
