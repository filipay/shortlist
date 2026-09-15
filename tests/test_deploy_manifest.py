import re
import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _compose() -> dict:
    return yaml.safe_load((ROOT / "compose.yml").read_text(encoding="utf-8"))


def _requirements_jobspy_line() -> str:
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    refs = [line for line in lines if "git+" in line]
    assert len(refs) == 1, f"expected exactly one VCS reference, got {refs}"
    return refs[0]


def _pyproject_jobspy_ref() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    refs = [dep for dep in data["project"]["dependencies"] if "git+" in dep]
    assert len(refs) == 1, f"expected exactly one VCS dependency, got {refs}"
    return refs[0]


def _split_vcs_reference(ref: str) -> tuple[str, str, str]:
    """Return (distribution-name, repo-url, commit) for a PEP 508 direct ref."""
    name, _, target = ref.partition("@")
    url, _, commit = target.strip().rpartition("@")
    return name.strip(), url, commit


def test_compose_defines_exactly_one_service() -> None:
    services = _compose()["services"]
    assert list(services) == ["app"], f"expected only the app service, got {list(services)}"


def test_compose_grants_host_gateway_access_for_opencode() -> None:
    app = _compose()["services"]["app"]
    assert "host.docker.internal:host-gateway" in app["extra_hosts"]


def test_compose_publishes_no_4096_host_port() -> None:
    app = _compose()["services"]["app"]
    ports = [str(port) for port in app.get("ports", [])]
    assert ports == ["8000:8000"]
    assert all("4096" not in port for port in ports)


def test_compose_has_no_opencode_service_or_dependency() -> None:
    app = _compose()["services"]["app"]
    assert "opencode" not in app
    assert "depends_on" not in app


def test_entrypoint_migrates_then_execs_uvicorn() -> None:
    text = (ROOT / "entrypoint.sh").read_text(encoding="utf-8")
    assert "alembic upgrade head" in text
    assert "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1" in text


def test_dockerfile_pins_python_313_and_exercises_the_migration() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "python:3.13-slim" in text
    assert "alembic upgrade head" in text


def test_vendored_assets_are_committed() -> None:
    for name in ("htmx.min.js", "alpine.min.js", "app.css"):
        path = ROOT / "static" / "vendor" / name
        assert path.is_file(), f"missing vendored asset: {path}"
        assert path.stat().st_size > 0, f"empty vendored asset: {path}"


def test_requirements_names_python_jobspy_distribution() -> None:
    name, _, _ = _split_vcs_reference(_requirements_jobspy_line())
    assert name == "python-jobspy", f"wrong distribution named: {name!r}"


def test_requirements_pins_full_lowercase_sha() -> None:
    _, _, commit = _split_vcs_reference(_requirements_jobspy_line())
    assert re.fullmatch(r"[0-9a-f]{40}", commit), (
        f"VCS reference must pin a full 40-char lowercase SHA, got {commit!r}"
    )


def test_pyproject_and_requirements_agree_on_jobspy_pin() -> None:
    req_name, req_url, req_sha = _split_vcs_reference(_requirements_jobspy_line())
    py_name, py_url, py_sha = _split_vcs_reference(_pyproject_jobspy_ref())
    assert py_name == req_name == "python-jobspy"
    assert py_url == req_url, f"repo drift: {py_url!r} != {req_url!r}"
    assert py_sha == req_sha, f"SHA drift: {py_sha!r} != {req_sha!r}"


def test_dockerfile_asserts_pinned_jobspy_revision() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "direct_url.json" in text
    assert "commit_id" in text
    assert "python-jobspy" in text


if __name__ == "__main__":  # pragma: no cover
    sys.exit(0)
