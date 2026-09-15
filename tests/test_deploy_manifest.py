import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _compose() -> dict:
    return yaml.safe_load((ROOT / "compose.yml").read_text(encoding="utf-8"))


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


if __name__ == "__main__":  # pragma: no cover
    sys.exit(0)
