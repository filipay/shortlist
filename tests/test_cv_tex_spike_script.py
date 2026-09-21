"""04-05-02 — the `cv-tex-spike.sh` contract, in the hermetic lane.

The script is the D-60 measurement entry point, but its behaviours were verified
only by ad-hoc shell one-liners at execution time (`bash -n`, `--dry-run`, a
missing source). These tests put the same contract into the sampled suite so a
regression is caught on every run rather than only when someone remembers to
re-run the command.

No engine, no Docker and no network are required: the script is a thin wrapper
over `app/cv/import_tex.py` and the committed fixture. `PYTHON` is pointed at the
interpreter running the suite, so the test is independent of the default venv
path.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "cv-tex-spike.sh"
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.tex"


def _run(*args: object) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHON": sys.executable}
    env.pop("PYTEST_ADDOPTS", None)
    return subprocess.run(
        ["bash", str(SCRIPT), *(str(argument) for argument in args)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def test_the_script_is_syntactically_valid() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr


def test_dry_run_names_the_default_source_and_a_review_draft_that_is_not_canonical() -> None:
    result = _run("--dry-run")

    assert result.returncode == 0, result.stderr
    assert "dry run" in result.stdout

    lines = result.stdout.splitlines()
    source_line = next(line for line in lines if line.strip().startswith("source:"))
    draft_line = next(line for line in lines if line.strip().startswith("draft:"))

    assert source_line.strip().endswith("cv/base.tex"), source_line
    # A SEPARATE review path, deliberately never the machine-canonical cv.yaml.
    assert draft_line.strip().endswith("cv/cv.draft.yaml"), draft_line
    assert not draft_line.strip().endswith("cv/cv.yaml"), draft_line


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    draft = tmp_path / "never.yaml"

    result = _run("--dry-run", FIXTURE, draft)

    assert result.returncode == 0, result.stderr
    assert not draft.exists()


def test_a_missing_source_exits_3_and_names_the_path(tmp_path: Path) -> None:
    missing = tmp_path / "absent.tex"

    result = _run(missing, tmp_path / "draft.yaml")

    output = result.stdout + result.stderr
    assert result.returncode == 3, output
    assert str(missing) in output


def test_an_unknown_option_exits_2() -> None:
    result = _run("--not-an-option")

    assert result.returncode == 2


def test_a_real_run_writes_a_draft_that_loads_and_leaves_the_source_untouched(
    tmp_path: Path,
) -> None:
    """The whole D-60 path: preflight, parse, write, then the fact store's gate."""
    from app.cv.factstore import load_facts

    draft = tmp_path / "spike-draft.yaml"
    before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()

    result = _run(FIXTURE, draft)

    assert result.returncode == 0, result.stdout + result.stderr
    assert draft.exists()

    facts = load_facts(draft)
    assert facts.sections
    assert facts.all_entries()

    # The importer never writes back over the document it read.
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == before


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
