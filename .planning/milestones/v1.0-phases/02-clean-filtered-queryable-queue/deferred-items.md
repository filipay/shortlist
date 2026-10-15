# Phase 2 — Deferred Items (out-of-scope discoveries)

Items found during execution that are **not** produced by the current plan's own
changes (scope boundary: do not auto-fix unrelated pre-existing issues).

## From plan 02-01 (2026-09-16)

### `.venv-host` is unusable in this sandbox (pre-existing, environment)

- **Discovered during:** plan-level verification (task 1 onward).
- **What:** every console script under `.venv-host/bin/` carries the shebang
  `#!/mnt/data/docker/apps/opencode/workspace/job-search/.venv-host/bin/python3.14`
  — a build-time absolute path that does not exist in this checkout, so
  `.venv-host/bin/pytest` fails with `bad interpreter: No such file or directory`.
  Additionally, `.venv-host`'s compiled wheels are `x86_64-linux-gnu` tagged while
  the sandbox interpreter (`/usr/bin/python3.14`) reports
  `EXT_SUFFIX=.cpython-314-x86_64-linux-musl.so`, so `import pydantic_core`
  fails with `ModuleNotFoundError`.
- **Workaround used:** the sibling `.venv/` (same Python 3.14.7, same package
  versions) is intact and was used as `.venv/bin/python -m pytest`. Every plan
  `<verify>` command has an exact equivalent under that interpreter.
- **Why deferred:** pre-existing environment breakage, not caused by migration
  0002; rebuilding `.venv-host` is an operator action outside this plan's files.
  The phase-level `<verification>` commands text should be read as
  `.venv/bin/python -m pytest` in this sandbox.
  status: acknowledged

### Default `DATABASE_URL_SYNC` is not writable in this sandbox (pre-existing, environment)

- **What:** `Settings.database_url_sync` defaults to `sqlite:////data/jobsearch.db`
  and `/data` does not exist here, so a bare `python -m alembic upgrade head`
  fails with `sqlite3.OperationalError: unable to open database file` unless
  `DATABASE_URL_SYNC` is set (the test harness sets it, `tests/conftest.py:47-57`).
- **Workaround used:** ran the migration with
  `DATABASE_URL_SYNC="sqlite:///$(pwd)/data/<file>.db"`.
- **Why deferred:** matches the documented D-17 deployment assumption
  (`/data` is the container volume); not a code defect.
  status: acknowledged
