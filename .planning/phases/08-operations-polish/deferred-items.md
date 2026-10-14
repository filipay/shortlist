# Deferred items — phase 08

Out-of-scope discoveries during execution. Not fixed here; recorded for a later owner.

## Pre-existing test failure (unrelated to plan 08-01)

`tests/test_stylesheet_coverage.py::test_the_committed_stylesheet_is_the_build_of_its_source`
fails in this sandbox: `static/vendor/app.css` is not byte-identical to the build of
`assets/tailwind/input.css` produced by the Tailwind CLI available to the test (first diff
at byte 1364). None of the files this plan changed (`pyproject.toml`, `requirements.txt`,
`tests/test_dependency_pins.py`, `app/config.py`, `tests/test_config.py`, `compose.yml`,
`Dockerfile`, `entrypoint.sh`) touches CSS, templates or the stylesheet build, so this is a
pre-existing/environmental drift, not a regression from plan 08-01.

Arming/repair command (operator, needs the pinned CLI):
`./node_modules/.bin/tailwindcss -i ./assets/tailwind/input.css -o ./static/vendor/app.css --minify`

## Sandbox interpreter mismatch

The project venv (`.venv`) was created for Python 3.14.7 and its compiled extensions under
`.venv/lib/python3.14/site-packages` are **musl**-linked
(`_pydantic_core.cpython-314-x86_64-linux-musl.so`), while the only Python 3.14 in this
sandbox is glibc. `.venv/bin/python` also resolves via a stale symlink to the sandbox's
Python 3.11. Verifications were therefore run with a working Python 3.11 interpreter
(`/tmp/gsdvenv`) plus `PYTHONPATH`. No repo file depends on this; it only affects how the
executor runs the suite here.
