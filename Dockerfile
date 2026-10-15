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

# `git` is required to install JobSpy from its pinned git commit; `curl` is
# required by the Tectonic install RUN below (the slim base ships no curl).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Fail the build unless JobSpy came from the pinned git commit. Without this a
# wrong-revision or non-VCS install could pass silently; the `jobspy` vs
# `python-jobspy` name collision previously surfaced as a misleading pip error
# (candidate discarded as metadata-inconsistent, reported as "(unavailable)").
# This is deliberately a SINGLE-LINE `python -c` and NOT a heredoc script:
# heredocs are BuildKit-only, and `docker compose build` falls back to the classic
# builder when buildx is absent, which would choke on the script body as if it
# were Dockerfile instructions ("unknown instruction: ..."). Keep it a one-liner.
ARG JOBSPY_SHA=1fffbcd4c1d822740157459fe527a916d3ce7a43
RUN JOBSPY_SHA="$JOBSPY_SHA" python -c "import importlib.metadata as md, json, os; vcs = json.loads(md.distribution('python-jobspy').read_text('direct_url.json')).get('vcs_info', {}); assert vcs.get('vcs') == 'git', 'python-jobspy is not a VCS install: %r' % (vcs,); assert vcs.get('commit_id') == os.environ['JOBSPY_SHA'], 'wrong revision: %r != %r' % (vcs.get('commit_id'), os.environ['JOBSPY_SHA']); print('python-jobspy pinned at', os.environ['JOBSPY_SHA'])"

# Prove the image's zoneinfo database resolves at BUILD time (T-08-03 / RESEARCH
# Pitfall 7, assumption A1): APScheduler builds the nightly trigger with
# `ZoneInfo("Europe/Dublin")`, and a base image carrying no tz database would fail
# only at the first scheduled run. `tzdata` is the remedy if this ever fails. Same
# shape as the JobSpy and Tectonic build-time proofs above.
ENV TZ=Europe/Dublin
RUN python -c "from zoneinfo import ZoneInfo; ZoneInfo('Europe/Dublin')"

# --- Tectonic, the LaTeX engine (CV-05 / D-73/D-74) --------------------------
# Install the pinned Tectonic binary and verify it in the SAME RUN that fetches it.
# Mirrors the JobSpy assertion above: a checksum in a separate layer can be reused
# by the cache while the download changed underneath it. The musl build is static,
# so it adds no runtime library dependency. The two ARGs make the pin greppable;
# TECTONIC_SHA256 was re-derived from the release metadata at implementation time
# (GitHub Releases API, tag tectonic@0.17.0, verified against a real download).
# Deliberately single-line shell, no heredoc, for the same classic-builder-fallback
# reason the JobSpy assertion gives. Ends with --version so a binary that cannot
# execute fails the BUILD rather than becoming a runtime mystery.
ARG TECTONIC_VERSION=0.17.0
ARG TECTONIC_SHA256=8533d07f9ccbd7a65824b9e0459041bca34af1eb33daba48f59215593753a3b7
RUN cd /tmp \
    && curl -fsSL -o tectonic.tar.gz "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
    && echo "${TECTONIC_SHA256}  tectonic.tar.gz" | sha256sum -c - \
    && tar -xzf tectonic.tar.gz -C /usr/local/bin tectonic \
    && rm -f tectonic.tar.gz \
    && tectonic --version

# D-75 requires the cached-only flag and the untrusted-mode option to be confirmed
# against the INSTALLED binary, not carried from documentation. This puts the
# binary's own option list in the build log beside the pinned version.
RUN tectonic --help

# Deterministic, HOME-independent cache location; set BEFORE the prime (Pitfall 2/
# T-04-09). This path must equal settings.tectonic_cache_dir and compose.yml's
# default for TECTONIC_CACHE_DIR, or a runtime compile looks in a cache the build
# never primed. TECTONIC_UNTRUSTED_MODE is the belt to the argv's braces: a future
# argv edit cannot quietly undo the sandbox (T-04-05).
ENV TECTONIC_CACHE_DIR=/opt/tectonic-cache \
    TECTONIC_UNTRUSTED_MODE=1

# The `latex` lane (D-69) must be literally runnable inside the image:
# `docker compose run --rm app pytest -m latex`. The runtime stage deliberately
# installs no dev tooling from requirements.txt, so the two test-only pins are
# added explicitly here. They need only pyproject.toml, NOT the test tree — so the
# test tree is copied at the very bottom of this file, where an edit to a test
# invalidates one cheap layer instead of re-priming the LaTeX cache below.
COPY pyproject.toml ./
RUN pip install --no-cache-dir pytest==9.1.1 pytest-asyncio==1.4.0

# Prime the package cache AND prove the engine works, at build time (D-74). This
# layer is the reason the runtime can pass --only-cached, and it is the build-time
# proof the engine actually runs — the same shape as the migration smoke below.
# The `test -f` turns "the command exited 0" into "the engine produced an
# artefact"; the primed set is exactly this fixture's package set. Tectonic does
# NOT create its --outdir (it fails with "output directory does not exist"), and
# the runtime path never hits this because the caller stages a real workdir.
# Only this fixture is copied ahead of the prime — not the whole test tree. It is
# self-contained (no \input/\include), so the prime does not need its siblings.
COPY tests/fixtures/cv/awesomecv_standin.tex ./tests/fixtures/cv/
RUN mkdir -p /tmp/prime \
    && tectonic --outdir /tmp/prime tests/fixtures/cv/awesomecv_standin.tex \
    && test -f /tmp/prime/awesomecv_standin.pdf \
    && rm -rf /tmp/prime

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

# The full test tree, deliberately last: an edit to any test then invalidates only
# this layer. `docker compose run --rm app pytest` needs it; nothing above does.
COPY tests ./tests

EXPOSE 8000

CMD ["./entrypoint.sh"]
