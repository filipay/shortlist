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


# Instructions the classic (non-BuildKit) builder understands. `docker compose
# build` falls back to it when buildx is absent, so every logical Dockerfile line
# must start with one of these.
_CLASSIC_INSTRUCTIONS = {
    "ADD",
    "ARG",
    "CMD",
    "COPY",
    "ENTRYPOINT",
    "ENV",
    "EXPOSE",
    "FROM",
    "HEALTHCHECK",
    "LABEL",
    "ONBUILD",
    "RUN",
    "SHELL",
    "STOPSIGNAL",
    "USER",
    "VOLUME",
    "WORKDIR",
}


def _dockerfile_logical_lines() -> list[str]:
    """Collapse the Dockerfile to logical lines, as the classic builder would."""
    logical: list[str] = []
    pending = ""
    for raw_line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            pending += line[:-1].rstrip() + " "
            continue
        logical.append((pending + line).strip())
        pending = ""
    if pending:
        logical.append(pending.strip())
    return logical


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


def test_dockerfile_has_no_heredoc_operator() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "<<" not in text, "BuildKit-only heredocs break the classic builder"


def test_dockerfile_is_valid_for_the_classic_builder() -> None:
    for logical in _dockerfile_logical_lines():
        keyword = logical.split(maxsplit=1)[0].upper()
        assert keyword in _CLASSIC_INSTRUCTIONS, (
            f"unknown instruction for the classic builder: {logical!r}"
        )


def _compose_database_url_keys() -> list[str]:
    app = _compose()["services"]["app"]
    environment = app.get("environment", [])
    if isinstance(environment, dict):
        return [
            str(key) for key in environment if str(key).startswith("DATABASE_URL")
        ]
    keys: list[str] = []
    for entry in environment:
        key = str(entry).split("=", 1)[0].strip()
        if key.startswith("DATABASE_URL"):
            keys.append(key)
    return keys


def test_compose_database_url_keys_are_real_settings_fields() -> None:
    """WR-02: every `DATABASE_URL*` env key must map to a real `Settings` field.

    `compose.yml` set `DATABASE_URL`, which maps to no field and is silently
    discarded (`extra="ignore"`), so editing it to relocate the database would
    have been a no-op that fell back to the default file.
    """
    from app.config import Settings

    fields = {name.upper() for name in Settings.model_fields}
    keys = _compose_database_url_keys()

    assert keys, "expected at least one DATABASE_URL* key in compose.yml"
    unknown = sorted(key for key in keys if key not in fields)
    assert unknown == [], (
        f"compose.yml sets DATABASE_URL* keys with no Settings field: {unknown}"
    )


def test_compose_sets_the_async_database_url_key() -> None:
    assert "DATABASE_URL_ASYNC" in _compose_database_url_keys()
    assert "DATABASE_URL" not in _compose_database_url_keys(), (
        "the bare DATABASE_URL key is dead configuration"
    )


# --- the Phase-4 engine surface (CV-05 / PLAT-04 / D-58) ----------------------

#: The engine keys that must be forwarded through compose.yml AND documented in
#: .env.example, or a host-side override silently loses to the in-code default.
ENGINE_PASSTHROUGH_KEYS = (
    "LATEX_ENGINE",
    "TECTONIC_BINARY",
    "TECTONIC_CACHE_DIR",
    "TECTONIC_OFFLINE",
    "TECTONIC_TIMEOUT_SECONDS",
    "LATEX_XELATEX_BINARY",
    "CV_DIR",
    "ARTIFACTS_DIR",
    "TEX_IMPORT_MAX_LINES",
    "TEX_IMPORT_MAX_DEPTH",
)


def _expected_compose_default(key: str) -> str:
    """The compose spelling of the declared `Settings` default, DERIVED not copied.

    Booleans render lowercase in compose (`true`), which pydantic-settings parses
    back to `True`; every other type renders as `str(default)`.
    """
    from app.config import Settings

    default = Settings.model_fields[key.lower()].default
    if isinstance(default, bool):
        return str(default).lower()
    return str(default)


def _passthrough_problems(compose_text: str, env_text: str) -> list[str]:
    """Every way the engine passthrough surface disagrees with `Settings`."""
    problems: list[str] = []
    for key in ENGINE_PASSTHROUGH_KEYS:
        pattern = re.escape(key) + r"=\$\{" + re.escape(key) + r":-([^}]*)\}"
        match = re.search(pattern, compose_text)
        if match is None:
            problems.append(f"{key} is missing from compose.yml `${{KEY:-default}}` form")
        else:
            expected = _expected_compose_default(key)
            if match.group(1) != expected:
                problems.append(
                    f"{key} compose default {match.group(1)!r} != declared "
                    f"Settings default {expected!r}"
                )
        if f"{key}=" not in env_text:
            problems.append(f"{key} is missing from .env.example")
    return problems


def test_compose_mounts_the_cv_and_artifacts_volumes() -> None:
    app = _compose()["services"]["app"]
    volumes = [str(volume) for volume in app.get("volumes", [])]

    assert any(volume.startswith("./cv:/cv") for volume in volumes), volumes
    assert any(volume.startswith("./artifacts:/artifacts") for volume in volumes), volumes


def test_compose_and_env_example_forward_every_engine_key() -> None:
    compose_text = (ROOT / "compose.yml").read_text(encoding="utf-8")
    env_text = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert _passthrough_problems(compose_text, env_text) == []


def test_the_engine_passthrough_guard_can_actually_fail() -> None:
    """A guard that cannot fail is not a guard."""
    compose_text = (ROOT / "compose.yml").read_text(encoding="utf-8")
    env_text = (ROOT / ".env.example").read_text(encoding="utf-8")
    doctored = compose_text.replace("LATEX_ENGINE=${LATEX_ENGINE:-tectonic}", "")

    problems = _passthrough_problems(doctored, env_text)

    assert any("LATEX_ENGINE" in problem for problem in problems), problems


if __name__ == "__main__":  # pragma: no cover
    sys.exit(0)
