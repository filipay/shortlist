"""T-01-29 / D-09 / D-11 / Pitfall 11 — the discovery redaction boundary.

`GET /config/providers` returns the provider API key in plaintext. One stray log
statement, one cached body, one `raw` field and a live credential is on disk
forever. This module proves the boundary four ways:

1. the returned objects carry only provider and model identifiers;
2. the sentinel appears in no captured log output (the real structlog payload, a
   stdlib-backed `caplog` bridge, and stdout);
3. the sentinel appears in no cell of any table in the migrated database;
4. the request goes to `/config/providers` and the full-catalogue path is not
   referenced anywhere in the module.

`httpx` is swapped for a recorder in every test here, so nothing touches the
network.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import types
from pathlib import Path
from typing import Any

import httpx
import pytest
import structlog

from app.llm import opencode_server
from app.llm.base import ProviderModel
from app.llm.opencode_server import (
    CONFIG_PROVIDERS_PATH,
    GLOBAL_HEALTH_PATH,
    OpenCodeServerBackend,
    parse_providers,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PROVIDERS_FIXTURE = FIXTURES / "opencode_providers.json"
SENTINEL = "SENTINEL-PROVIDER-CREDENTIAL-DO-NOT-LOG"

#: The full-catalogue endpoint D-09 forbids. Spelled here, not in production code.
FORBIDDEN_CATALOGUE_PATH = "/provider"


def _fixture_payload() -> dict[str, Any]:
    return json.loads(PROVIDERS_FIXTURE.read_text(encoding="utf-8"))


class Recorder:
    """A fake `httpx` module for `app.llm.opencode_server`, recording request paths."""

    def __init__(self) -> None:
        self.paths: list[str] = []
        self.client_kwargs: list[dict[str, Any]] = []

    def module(
        self,
        *,
        status_code: int = 200,
        body: Any = None,
        error: BaseException | None = None,
        json_error: BaseException | None = None,
    ) -> types.SimpleNamespace:
        recorder = self

        def _json() -> Any:
            if json_error is not None:
                raise json_error
            return body

        class FakeClient:
            def __init__(self, **kwargs: Any) -> None:
                recorder.client_kwargs.append(kwargs)

            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *exc: object) -> bool:
                return False

            async def get(self, url: str) -> Any:
                recorder.paths.append(url)
                if error is not None:
                    raise error
                return types.SimpleNamespace(status_code=status_code, json=_json)

        return types.SimpleNamespace(AsyncClient=FakeClient, BasicAuth=httpx.BasicAuth)


def _scan_every_table(db_path: Path) -> tuple[list[str], list[str]]:
    """`(tables_scanned, offending_tables)` — the DB half of the sentinel hunt."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        tables = [
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        ]
        offenders: list[str] = []
        for table in tables:
            # PRAGMA-free: the name comes from our own sqlite_master, never input.
            for row in connection.execute(f"SELECT * FROM {table}"):
                if SENTINEL in repr(tuple(row)):
                    offenders.append(table)
        return tables, sorted(set(offenders))
    finally:
        connection.close()


# --- 1. identifiers only ------------------------------------------------------


def test_discovery_returns_only_provider_and_model_identifiers() -> None:
    providers = parse_providers(_fixture_payload())

    assert providers == [
        ProviderModel(provider_id="opencode", model_id="deepseek-v4.1-flash"),
        ProviderModel(provider_id="opencode", model_id="qwen3-coder"),
    ]
    assert set(ProviderModel.model_fields) == {"provider_id", "model_id"}


def test_provider_model_cannot_carry_a_raw_provider_entry() -> None:
    """A raw entry (with `api_key`) must raise, not silently drop the secret."""
    with pytest.raises(ValueError):
        ProviderModel.model_validate({"id": "opencode", "api_key": SENTINEL})


def test_a_provider_without_models_yields_an_empty_list() -> None:
    payload = {"providers": [{"id": "empty-provider", "api_key": SENTINEL}]}

    assert parse_providers(payload) == []

    # The fixture's model-less provider contributes nothing either.
    ids = {entry.provider_id for entry in parse_providers(_fixture_payload())}
    assert "no-models-provider" not in ids


def test_a_model_without_an_id_is_skipped() -> None:
    payload = {
        "providers": [
            {"id": "p", "models": [{"name": "nameless"}, {"id": ""}, "not-a-mapping", 7]}
        ]
    }

    assert parse_providers(payload) == []


@pytest.mark.parametrize(
    "payload",
    [None, [], "text", 7, (), {"providers": "nope"}, {"providers": [None, 1, []]}],
)
def test_a_malformed_payload_is_tolerated(payload: object) -> None:
    assert parse_providers(payload) == []


# --- 2. the endpoint contract -------------------------------------------------


async def test_discovery_requests_config_providers_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()
    monkeypatch.setattr(opencode_server, "httpx", recorder.module(body=_fixture_payload()))

    result = await OpenCodeServerBackend().discover_models()

    assert result.reachable is True
    assert recorder.paths == [CONFIG_PROVIDERS_PATH]
    assert recorder.paths == ["/config/providers"]


def test_the_module_never_references_the_full_catalogue_endpoint() -> None:
    source = Path(opencode_server.__file__).read_text(encoding="utf-8")

    assert CONFIG_PROVIDERS_PATH in source
    assert not re.search(r"""["']/provider["']""", source), (
        "the 6 MB full-catalogue endpoint must not be referenced (D-09); "
        "`/config/providers` is the user's actual entitlement"
    )


# --- 3. the sentinel never reaches a log or the database ----------------------


async def test_the_real_logger_never_carries_the_sentinel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert SENTINEL in PROVIDERS_FIXTURE.read_text(encoding="utf-8"), (
        "the fixture lost its sentinel — this suite would pass vacuously"
    )
    recorder = Recorder()
    monkeypatch.setattr(opencode_server, "httpx", recorder.module(body=_fixture_payload()))

    with structlog.testing.capture_logs() as events:
        result = await OpenCodeServerBackend().discover_models()

    # Non-vacuity: discovery ran, returned entries, and did emit a non-secret event.
    assert result.providers
    assert any(event.get("model_count", 0) > 0 for event in events)

    assert SENTINEL not in repr(events)
    assert SENTINEL not in repr(result)


async def test_the_sentinel_does_not_reach_captured_log_output(
    migrated_db: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caplog.set_level(logging.INFO, logger="app.llm.opencode_server")
    monkeypatch.setattr(
        opencode_server,
        "log",
        structlog.wrap_logger(logging.getLogger("app.llm.opencode_server")),
    )
    recorder = Recorder()
    monkeypatch.setattr(opencode_server, "httpx", recorder.module(body=_fixture_payload()))
    backend = OpenCodeServerBackend()

    result = await backend.discover_models()

    assert recorder.paths == [CONFIG_PROVIDERS_PATH]
    assert result.providers
    assert "llm.discovery" in caplog.text, "the stage did not log — assertion is vacuous"

    assert SENTINEL not in caplog.text
    assert SENTINEL not in repr(result)
    assert SENTINEL not in repr(vars(backend)), "the backend retained the raw response"

    tables, offenders = _scan_every_table(migrated_db)
    assert tables, "no tables were scanned — the persistence half is vacuous"
    assert offenders == [], f"the sentinel was persisted: {offenders}"


async def test_the_sentinel_does_not_reach_stdout(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()
    monkeypatch.setattr(opencode_server, "httpx", recorder.module(body=_fixture_payload()))

    await OpenCodeServerBackend().discover_models()

    captured = capsys.readouterr()
    assert SENTINEL not in captured.out + captured.err


# --- 4. failure is a value, never an exception --------------------------------


async def test_health_reports_the_server_version(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = Recorder()
    monkeypatch.setattr(
        opencode_server,
        "httpx",
        recorder.module(body={"healthy": True, "version": "1.2.3"}),
    )

    outcome = await OpenCodeServerBackend().health()

    assert outcome.reachable is True
    assert outcome.version == "1.2.3"
    assert recorder.paths == [GLOBAL_HEALTH_PATH]


async def test_health_is_unreachable_on_a_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()
    monkeypatch.setattr(
        opencode_server, "httpx", recorder.module(error=RuntimeError("connect refused"))
    )

    outcome = await OpenCodeServerBackend().health()

    assert outcome.reachable is False
    assert outcome.error == "RuntimeError"


async def test_health_is_unreachable_on_a_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = Recorder()
    monkeypatch.setattr(opencode_server, "httpx", recorder.module(status_code=503))

    outcome = await OpenCodeServerBackend().health()

    assert outcome.reachable is False
    assert "503" in (outcome.error or "")


async def test_health_tolerates_a_non_json_body(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = Recorder()
    monkeypatch.setattr(
        opencode_server,
        "httpx",
        recorder.module(json_error=ValueError("not json")),
    )

    outcome = await OpenCodeServerBackend().health()

    assert outcome.reachable is True
    assert outcome.version is None


async def test_discovery_is_unreachable_on_a_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()
    monkeypatch.setattr(
        opencode_server, "httpx", recorder.module(error=RuntimeError("timed out"))
    )

    result = await OpenCodeServerBackend().discover_models()

    assert result.reachable is False
    assert result.providers == []
    assert result.error == "RuntimeError"


async def test_discovery_is_unreachable_on_a_non_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()
    monkeypatch.setattr(opencode_server, "httpx", recorder.module(status_code=404))

    result = await OpenCodeServerBackend().discover_models()

    assert result.reachable is False
    assert "404" in (result.error or "")


# --- 5. the server password is configuration, sent only when set --------------


async def test_the_server_password_is_used_only_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()
    monkeypatch.setattr(
        opencode_server,
        "httpx",
        recorder.module(body={"healthy": True, "version": "1.0.0"}),
    )

    await OpenCodeServerBackend(password="").health()
    await OpenCodeServerBackend(password="localhost-server-password").health()

    assert recorder.client_kwargs[0]["auth"] is None
    assert isinstance(recorder.client_kwargs[1]["auth"], httpx.BasicAuth)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
