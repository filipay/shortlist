"""T-01-29 / D-09 / D-11 / D-146 — the discovery redaction boundary.

Discovery now speaks the V2 surface (`GET /api/model` + `GET /api/provider`,
retargeted by D-146) alongside the retained V1 `GET /config/providers` (D-148).
Either response carries a credential-adjacent value in plaintext (`key` on a V2
provider entry; the same on a V1 provider), so one stray log statement, one
cached body, one `raw` field and a live credential is on disk forever. This
module proves the boundary four ways:

1. the returned objects carry only provider and model identifiers;
2. the sentinel appears in no captured log output (the real structlog payload, a
   stdlib-backed `caplog` bridge, and stdout);
3. the sentinel appears in no cell of any table in the migrated database;
4. the V2 request sequence is exactly `/api/model` then `/api/provider`, and the
   full-catalogue path is not referenced anywhere in the module.

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

from app.config import settings
from app.llm import opencode_server
from app.llm.base import DiscoveryResult, ProviderModel, StructuredCallResult
from app.llm.contract import (
    GLOBAL_HEALTH_PATH,
    INFO_PATH,
    V2_MODEL_PATH,
    V2_PROVIDER_PATH,
)
from app.llm.detection import detect_surface
from app.llm.opencode_server import (
    CONFIG_PROVIDERS_PATH,
    OpenCodeServerBackend,
    parse_providers,
    parse_v2_models,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PROVIDERS_FIXTURE = FIXTURES / "opencode_providers.json"
SENTINEL = "SENTINEL-PROVIDER-CREDENTIAL-DO-NOT-LOG"
V2_SERVER_VERSION = "2.0.26"

#: The full-catalogue endpoint D-09 forbids. Spelled here, not in production code.
FORBIDDEN_CATALOGUE_PATH = "/provider"


def _fixture() -> dict[str, Any]:
    return json.loads(PROVIDERS_FIXTURE.read_text(encoding="utf-8"))


def _model_payload() -> Any:
    return _fixture()["model"]


def _provider_payload() -> Any:
    return _fixture()["provider"]


class Recorder:
    """A fake `httpx` module for `app.llm.opencode_server`, recording request paths.

    `bodies` maps a path to its response body (or a list of bodies consumed in
    order, the last repeating) so the V2 discovery test can serve `/api/model` and
    `/api/provider` differently and a cold-start test can return empty then
    populated. `body` is the single-response fallback (transport-error / non-200).
    """

    def __init__(
        self,
        *,
        status_code: int = 200,
        body: Any = None,
        bodies: dict[str, Any] | None = None,
        statuses: dict[str, int] | None = None,
        error: BaseException | None = None,
        json_error: BaseException | None = None,
    ) -> None:
        self.paths: list[str] = []
        self.client_kwargs: list[dict[str, Any]] = []
        self._status_code = status_code
        self._body = body
        self._bodies = dict(bodies or {})
        self._statuses = dict(statuses or {})
        self._error = error
        self._json_error = json_error

    def _reply(self, url: str) -> Any:
        if url in self._bodies:
            entry = self._bodies[url]
            if isinstance(entry, list):
                return entry.pop(0) if len(entry) > 1 else entry[0]
            return entry
        return self._body

    def module(self) -> types.SimpleNamespace:
        recorder = self

        def _json_for(url: str) -> Any:
            if recorder._json_error is not None:
                raise recorder._json_error
            return recorder._reply(url)

        class FakeClient:
            def __init__(self, **kwargs: Any) -> None:
                recorder.client_kwargs.append(kwargs)

            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *exc: object) -> bool:
                return False

            async def get(self, url: str) -> Any:
                recorder.paths.append(url)
                if recorder._error is not None:
                    raise recorder._error
                return types.SimpleNamespace(
                    status_code=recorder._statuses.get(url, recorder._status_code),
                    json=lambda u=url: _json_for(u),
                )

        return types.SimpleNamespace(AsyncClient=FakeClient, BasicAuth=httpx.BasicAuth)


def _v2_recorder(*, model: Any = None) -> Recorder:
    """A recorder serving the V2 fixture per path (detection + both discovery GETs)."""
    return Recorder(
        bodies={
            INFO_PATH: {"version": V2_SERVER_VERSION},
            V2_MODEL_PATH: _model_payload() if model is None else model,
            V2_PROVIDER_PATH: _provider_payload(),
        }
    )


async def _prime_v2_verdict() -> None:
    """Cache a V2 verdict through the public probe, so discovery issues no probe.

    The endpoint test asserts the LITERAL discovery paths; priming the process
    cache keeps the `/api/info` probe out of the recorded sequence.
    """
    module = Recorder(bodies={INFO_PATH: {"version": V2_SERVER_VERSION}}).module()
    client = module.AsyncClient(
        base_url=settings.opencode_base_url, timeout=1.0, auth=None
    )
    await detect_surface(base_url=settings.opencode_base_url, client=client)


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
    """The FIXTURE is the live 2.0.26 `/api/model` shape; `data[]` rows carry the pair."""
    providers = parse_v2_models(_model_payload(), _provider_payload())

    assert providers == [
        ProviderModel(provider_id="opencode", model_id="claude-sonnet-4"),
        ProviderModel(provider_id="opencode-go", model_id="deepseek-v4.1-flash"),
        ProviderModel(provider_id="opencode-go", model_id="qwen3-coder"),
    ]
    assert set(ProviderModel.model_fields) == {"provider_id", "model_id"}


def test_parse_v2_models_never_reads_provider_payload_values() -> None:
    """Only the two model identifiers leave; the provider `key` is never touched."""
    model = {"data": [{"modelID": "m1", "providerID": "p", "compatibility": {}}]}
    provider = {"data": [{"id": "p", "key": SENTINEL, "options": {"secret": SENTINEL}}]}

    providers = parse_v2_models(model, provider)

    assert providers == [ProviderModel(provider_id="p", model_id="m1")]
    assert SENTINEL not in repr(providers)


def test_parse_v2_models_does_not_filter_by_the_provider_list() -> None:
    """A cold/empty `/api/provider` must not drop a model the model payload offers."""
    model = {"data": [{"modelID": "m1", "providerID": "p"}]}

    assert parse_v2_models(model, {"data": []}) == [
        ProviderModel(provider_id="p", model_id="m1")
    ]


def test_parse_v2_models_skips_a_model_missing_an_identifier() -> None:
    payload = {
        "data": [
            {"modelID": "m1", "providerID": "p"},
            {"modelID": "m2"},
            {"providerID": "p"},
            {"modelID": "", "providerID": "p"},
            {"modelID": "m3", "providerID": ""},
            "not-a-mapping",
        ]
    }

    assert parse_v2_models(payload, {"data": []}) == [
        ProviderModel(provider_id="p", model_id="m1")
    ]


@pytest.mark.parametrize(
    "payload",
    [None, [], "text", 7, (), {"data": "nope"}, {"data": [None, 1, []]}],
)
def test_parse_v2_models_tolerates_a_malformed_payload(payload: object) -> None:
    assert parse_v2_models(payload, {"data": []}) == []


def test_parse_providers_still_accepts_the_legacy_list_shape() -> None:
    """The retained V1 parse (D-148): the old `[{"id": …}]` shape keeps working."""
    payload = {
        "providers": [
            {"id": "legacy", "api_key": SENTINEL, "models": [{"id": "m2"}, {"id": "m1"}]}
        ]
    }

    assert parse_providers(payload) == [
        ProviderModel(provider_id="legacy", model_id="m1"),
        ProviderModel(provider_id="legacy", model_id="m2"),
    ]


def test_the_dict_shape_branch_is_actually_exercised() -> None:
    """A guard that cannot fail is not a guard (the repo's guard-can-fail convention).

    The same V1 model ids as an OBJECT yield two pairs; as a LIST of id-less entries
    they yield none. The lengths differ, which proves the dict branch does real
    work rather than walking a list that happens to be empty.
    """
    as_dict = {"providers": [{"id": "p", "models": {"m1": {}, "m2": {}}}]}
    as_list = {"providers": [{"id": "p", "models": [{}, {}]}]}

    assert len(parse_providers(as_dict)) == 2
    assert len(parse_providers(as_list)) == 0


def test_the_object_branch_never_copies_model_metadata_values() -> None:
    """Only the keys leave the V1 parser; per-model metadata is the secret's hiding place."""
    payload = {"providers": [{"id": "p", "models": {"m1": {"credential": SENTINEL}}}]}

    providers = parse_providers(payload)

    assert providers == [ProviderModel(provider_id="p", model_id="m1")]
    assert SENTINEL not in repr(providers)


def test_provider_model_cannot_carry_a_raw_provider_entry() -> None:
    """A raw entry (with `api_key`) must raise, not silently drop the secret."""
    with pytest.raises(ValueError):
        ProviderModel.model_validate({"id": "opencode", "api_key": SENTINEL})


# --- 2. the endpoint contract -------------------------------------------------


async def test_v2_discovery_requests_model_then_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _prime_v2_verdict()
    recorder = Recorder(
        bodies={
            V2_MODEL_PATH: _model_payload(),
            V2_PROVIDER_PATH: _provider_payload(),
        }
    )
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    result = await OpenCodeServerBackend().discover_models()

    assert result.reachable is True
    assert result.providers
    assert recorder.paths == ["/api/model", "/api/provider"]


@pytest.mark.parametrize("status_code", [404, 500, 503])
async def test_a_failing_api_provider_does_not_take_down_discovery(
    monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    """WR-02: `/api/provider` is never read, so its failure must not fail discovery.

    The authoritative pair source is `/api/model` (`parse_v2_models` ignores the
    provider payload), so a 5xx/404 on the provider endpoint must not take down
    model resolution — and, through `_resolve_model`, every completion.
    """
    await _prime_v2_verdict()
    recorder = Recorder(
        bodies={V2_MODEL_PATH: _model_payload(), V2_PROVIDER_PATH: None},
        statuses={V2_PROVIDER_PATH: status_code},
    )
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    result = await OpenCodeServerBackend().discover_models()

    assert result.reachable is True
    assert result.providers
    assert recorder.paths == [V2_MODEL_PATH, V2_PROVIDER_PATH]


def test_the_module_never_references_the_full_catalogue_endpoint() -> None:
    source = Path(opencode_server.__file__).read_text(encoding="utf-8")

    assert CONFIG_PROVIDERS_PATH in source
    assert not re.search(r"""["']/provider["']""", source), (
        "the 6 MB full-catalogue endpoint must not be referenced (D-09); "
        "`/api/provider` is a different literal and `/config/providers` is the "
        "user's actual entitlement"
    )


# --- 3. the sentinel never reaches a log or the database ----------------------


async def test_the_real_logger_never_carries_the_sentinel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert SENTINEL in PROVIDERS_FIXTURE.read_text(encoding="utf-8"), (
        "the fixture lost its sentinel — this suite would pass vacuously"
    )
    recorder = _v2_recorder()
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

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
    recorder = _v2_recorder()
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())
    backend = OpenCodeServerBackend()

    result = await backend.discover_models()

    assert V2_MODEL_PATH in recorder.paths and V2_PROVIDER_PATH in recorder.paths
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
    recorder = _v2_recorder()
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    await OpenCodeServerBackend().discover_models()

    captured = capsys.readouterr()
    assert SENTINEL not in captured.out + captured.err


# --- 4. failure is a value, never an exception --------------------------------


async def test_health_reports_the_server_version(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = Recorder(body={"version": "1.2.3"})
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    outcome = await OpenCodeServerBackend().health()

    assert outcome.reachable is True
    assert outcome.version == "1.2.3"
    # 07.1: health probes the V2 liveness path first (D-147); the V1 leg is reached
    # only when /api/info is not a JSON body carrying `version`.
    assert recorder.paths == [INFO_PATH]


async def test_health_is_unreachable_on_a_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder(error=RuntimeError("connect refused"))
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    outcome = await OpenCodeServerBackend().health()

    assert outcome.reachable is False
    assert outcome.error == "RuntimeError"


async def test_health_is_unreachable_on_a_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = Recorder(status_code=503)
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    outcome = await OpenCodeServerBackend().health()

    assert outcome.reachable is False
    assert "503" in (outcome.error or "")


async def test_health_rejects_a_non_json_200_as_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """07.1 / D-147: a non-JSON 200 is the SPA fallback, NOT a reachable server."""
    recorder = Recorder(json_error=ValueError("not json"))
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    outcome = await OpenCodeServerBackend().health()

    assert outcome.reachable is False
    assert outcome.version is None


async def test_discovery_is_unreachable_on_a_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder(error=RuntimeError("timed out"))
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    result = await OpenCodeServerBackend().discover_models()

    assert result.reachable is False
    assert result.providers == []
    assert result.error == "RuntimeError"


async def test_discovery_is_unreachable_on_a_non_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder(status_code=404)
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    result = await OpenCodeServerBackend().discover_models()

    assert result.reachable is False
    assert "404" in (result.error or "")


# --- 5. the server password is configuration, sent only when set --------------


async def test_the_server_password_is_used_only_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder(body={"healthy": True, "version": "1.0.0"})
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    await OpenCodeServerBackend(password="").health()
    await OpenCodeServerBackend(password="localhost-server-password").health()

    assert recorder.client_kwargs[0]["auth"] is None
    assert isinstance(recorder.client_kwargs[1]["auth"], httpx.BasicAuth)


# --- 6. model resolution is derived, and a miss fails loud --------------------


def _discovery(*pairs: tuple[str, str]) -> DiscoveryResult:
    return DiscoveryResult(
        reachable=True,
        providers=[
            ProviderModel(provider_id=provider_id, model_id=model_id)
            for provider_id, model_id in pairs
        ],
    )


async def test_resolve_model_returns_the_provider_and_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`OPENCODE_MODEL` is a bare id; the provider is DERIVED from discovery."""
    backend = OpenCodeServerBackend()

    async def _fake_discovery() -> DiscoveryResult:
        return _discovery(("opencode-go", settings.opencode_model))

    monkeypatch.setattr(backend, "discover_models", _fake_discovery)

    # No argument: this exercises the real default path, not a forced id.
    assert await backend._resolve_model() == ("opencode-go", settings.opencode_model)


async def test_resolve_model_fails_loud_on_a_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wrong OPENCODE_MODEL must be distinguishable from a call that worked."""
    backend = OpenCodeServerBackend()

    async def _fake_discovery() -> DiscoveryResult:
        return _discovery(("opencode", "qwen3-coder"))

    monkeypatch.setattr(backend, "discover_models", _fake_discovery)

    resolved = await backend._resolve_model()

    assert isinstance(resolved, StructuredCallResult)
    assert resolved.ok is False
    assert resolved.status == "error"
    assert settings.opencode_model in (resolved.error or "")


async def test_resolve_model_fails_loud_when_discovery_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = OpenCodeServerBackend()

    async def _fake_discovery() -> DiscoveryResult:
        return DiscoveryResult(reachable=False, error="ConnectError")

    monkeypatch.setattr(backend, "discover_models", _fake_discovery)

    resolved = await backend._resolve_model()

    assert isinstance(resolved, StructuredCallResult)
    assert resolved.ok is False
    assert resolved.error_kind == "unreachable"


async def test_resolve_model_is_deterministic_under_ambiguity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One model id under two providers resolves by sorted provider id."""
    backend = OpenCodeServerBackend()

    async def _fake_discovery() -> DiscoveryResult:
        return _discovery(
            ("z-provider", settings.opencode_model),
            ("a-provider", settings.opencode_model),
        )

    monkeypatch.setattr(backend, "discover_models", _fake_discovery)

    assert await backend._resolve_model() == ("a-provider", settings.opencode_model)


# --- 7. cold-start tolerance + the retained V1 branch -------------------------


async def test_a_cold_start_empty_api_model_is_retried_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pitfall P3: the registry warms up lazily; ONE re-probe, never a loop."""
    # The pause is asserted separately; keep it out of this test's wall time.
    monkeypatch.setattr(
        opencode_server.settings, "opencode_discovery_retry_delay_seconds", 0.0
    )
    recorder = Recorder(
        bodies={
            INFO_PATH: {"version": V2_SERVER_VERSION},
            V2_MODEL_PATH: [{"data": []}, _model_payload()],
            V2_PROVIDER_PATH: _provider_payload(),
        }
    )
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    with structlog.testing.capture_logs() as events:
        result = await OpenCodeServerBackend().discover_models()

    assert result.reachable is True
    assert result.providers == [
        ProviderModel(provider_id="opencode", model_id="claude-sonnet-4"),
        ProviderModel(provider_id="opencode-go", model_id="deepseek-v4.1-flash"),
        ProviderModel(provider_id="opencode-go", model_id="qwen3-coder"),
    ]
    assert recorder.paths.count(V2_MODEL_PATH) == 2
    assert any(event.get("retried") is True for event in events)
    # A registry that did warm is NOT reported as still warming.
    assert result.error_kind is None


async def test_a_cold_start_retry_pauses_before_the_single_reprobe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bounded re-probe waits a short configured pause, not zero (DEFECT 2).

    It is deliberately short — a couple of seconds — so a cold server is given a
    chance to publish its registry without pinning the request for the full ~32 s
    warm window. `asyncio.sleep` is replaced with a recorder so this test is instant
    and the delay VALUE is asserted, not merely that some pause occurred.
    """
    monkeypatch.setattr(
        opencode_server.settings, "opencode_discovery_retry_delay_seconds", 0.25
    )
    slept: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(opencode_server.asyncio, "sleep", _fake_sleep)
    recorder = Recorder(
        bodies={
            INFO_PATH: {"version": V2_SERVER_VERSION},
            V2_MODEL_PATH: [{"data": []}, _model_payload()],
            V2_PROVIDER_PATH: _provider_payload(),
        }
    )
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    result = await OpenCodeServerBackend().discover_models()

    assert result.providers
    assert slept == [0.25], "the single re-probe must pause for the configured delay"
    assert recorder.paths.count(V2_MODEL_PATH) == 2


async def test_a_permanently_empty_api_model_is_reported_as_warming(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reachable but empty registry is `models_warming`, not a silent empty result.

    No hard-coded provider papers over a genuinely empty registry (D-145), and the
    empty outcome is a DISTINCT cause so "still starting" is not reported as a
    generic failure (DEFECT 2). Iterating the pause keeps the test instant.
    """
    monkeypatch.setattr(
        opencode_server.settings, "opencode_discovery_retry_delay_seconds", 0.0
    )
    recorder = Recorder(
        bodies={
            INFO_PATH: {"version": V2_SERVER_VERSION},
            V2_MODEL_PATH: {"data": []},
            V2_PROVIDER_PATH: _provider_payload(),
        }
    )
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())
    backend = OpenCodeServerBackend()

    resolved = await backend._resolve_model()

    assert isinstance(resolved, StructuredCallResult)
    assert resolved.ok is False
    assert resolved.status == "error"
    assert resolved.error_kind == "models_warming"
    # One bounded retry per discovery; `_resolve_model` issued no completion.
    assert recorder.paths.count(V2_MODEL_PATH) == 2


async def test_an_empty_registry_is_reachable_but_flags_the_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`discover_models` itself carries the warming cause, not just `_resolve_model`."""
    monkeypatch.setattr(
        opencode_server.settings, "opencode_discovery_retry_delay_seconds", 0.0
    )
    recorder = Recorder(
        bodies={
            INFO_PATH: {"version": V2_SERVER_VERSION},
            V2_MODEL_PATH: {"data": []},
            V2_PROVIDER_PATH: _provider_payload(),
        }
    )
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    result = await OpenCodeServerBackend().discover_models()

    assert result.reachable is True
    assert result.providers == []
    assert result.error_kind == "models_warming"
    assert result.error is not None and "warm" in result.error


async def test_the_retained_v1_discovery_resolves_from_config_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-148: a V1 server still resolves `(provider_id, model_id)` from `/config/providers`."""
    v1_payload = {
        "providers": [
            {
                "id": "legacy",
                "api_key": SENTINEL,
                "models": {settings.opencode_model: {"name": "Legacy model"}},
            }
        ]
    }
    recorder = Recorder(
        bodies={
            INFO_PATH: None,  # non-V2: the SPA fallback / no version marker
            GLOBAL_HEALTH_PATH: {"healthy": True},
            CONFIG_PROVIDERS_PATH: v1_payload,
        }
    )
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())
    backend = OpenCodeServerBackend()

    discovery = await backend.discover_models()

    assert discovery.reachable is True
    assert discovery.providers == [
        ProviderModel(provider_id="legacy", model_id=settings.opencode_model)
    ]
    assert recorder.paths == [INFO_PATH, GLOBAL_HEALTH_PATH, CONFIG_PROVIDERS_PATH]
    assert await backend._resolve_model() == ("legacy", settings.opencode_model)



if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
