"""Global configuration wins at the real adapter/wire boundary, without sockets."""

import json
from contextlib import asynccontextmanager

import httpx
import pytest

from app import llm
from app.db import session as session_module
from app.domain.schemas.probe import ProbeResult
from app.llm import opencode_server
from app.llm.base import DiscoveryResult, ProviderModel


@pytest.fixture
def model_wire(monkeypatch, request):
    from app.llm.detection import clear_cache
    clear_cache()
    request.addfinalizer(clear_cache)
    requests = []
    state = {"pairs": [("A", "X"), ("B", "X")], "status": 200, "v1": False}

    async def handle(request):
        requests.append(request)
        path = request.url.path
        if path == "/api/info":
            return httpx.Response(404 if state["v1"] else 200, json={"version": "2.0.26"})
        if path == "/global/health":
            return httpx.Response(200, json={"healthy": True, "version": "1.18.31"})
        if path == "/api/model":
            return httpx.Response(state["status"], json={"data": [
                {"providerID": p, "modelID": m} for p, m in state["pairs"]
            ]})
        if path == "/api/provider":
            return httpx.Response(200, json={"data": [{"key": "SECRET-NOT-FOR-HTML"}]})
        if path == "/config/providers":
            return httpx.Response(200, json={"providers": [
                {"id": p, "models": {m: {}}, "key": "SECRET-NOT-FOR-HTML"}
                for p, m in state["pairs"]
            ]})
        if path == "/api/session":
            hook = state.get("session_hook")
            if hook:
                await hook()
            return httpx.Response(200, json={"data": {"id": "ses_selection"}})
        if path == "/session":
            return httpx.Response(200, json={"id": "ses_selection"})
        payload = state.get("payload", {"acknowledged": True})
        if path.endswith("/generate"):
            hook = state.get("generate_hook")
            if hook:
                await hook()
            return httpx.Response(200, json={"data": {"text": json.dumps(payload)}})
        if path.endswith("/message"):
            return httpx.Response(200, json={"info": {"structured": payload}})
        raise AssertionError(f"unexpected HTTP path {path}")

    def client(self):
        return httpx.AsyncClient(base_url="http://wire", transport=httpx.MockTransport(handle))

    for name in ("_client", "_discovery_client", "_completion_client"):
        monkeypatch.setattr(opencode_server.OpenCodeServerBackend, name, client)
    monkeypatch.setattr(opencode_server.settings, "opencode_discovery_retry_delay_seconds", 0)
    return requests, state


async def save_pair(factory, provider="B", model="X"):
    from app.db.repositories import llm_config_repo
    async with factory() as session:
        await llm_config_repo.write_selection(
            session, ProviderModel(provider_id=provider, model_id=model)
        )
        await session.commit()


@pytest.mark.parametrize("v1", [False, True])
async def test_api_save_survives_fresh_backend_and_overrides_explicit_environment(
    client, session_factory, monkeypatch, model_wire, v1
):
    requests, state = model_wire
    state["v1"] = v1
    client._transport.app.dependency_overrides[llm.get_llm_backend] = llm.get_llm_backend
    monkeypatch.setattr(session_module, "get_session_factory", lambda: session_factory)
    response = await client.post("/settings/llm-model", data={
        "model_selection": '{"provider_id":"B","model_id":"X"}'
    })
    assert response.status_code == 200
    assert not [r for r in requests if r.method == "POST"]
    backend = llm.get_llm_backend()
    result = await backend.complete_structured(
        schema=ProbeResult, system="fixed", parts=["data"], model="old-environment"
    )
    assert result.ok
    posts = [r for r in requests if r.method == "POST"]
    assert json.loads(posts[0].content)["model"] == {"id": "X", "providerID": "B"}
    if v1:
        assert json.loads(posts[1].content)["model"] == {"modelID": "X", "providerID": "B"}
    else:
        assert result.provider is None
        assert result.model == "X"


async def test_unsaved_legacy_model_keeps_sorted_provider_tie_break(
    session_factory, model_wire
):
    requests, _ = model_wire
    backend = opencode_server.OpenCodeServerBackend(selection_session_factory=session_factory)
    result = await backend.complete_structured(schema=ProbeResult, system="s", parts=[], model="X")
    assert result.ok
    assert json.loads(next(r for r in requests if r.method == "POST").content)["model"] == {
        "id": "X", "providerID": "A"
    }


@pytest.mark.parametrize("cause", ["missing", "offline", "auth", "warming", "corrupt", "db"])
async def test_saved_selection_fails_closed_before_any_spending(
    session_factory, model_wire, monkeypatch, cause
):
    from app.db.repositories import llm_config_repo
    requests, state = model_wire
    await save_pair(session_factory)
    backend = opencode_server.OpenCodeServerBackend(selection_session_factory=session_factory)
    expected = {
        "missing": "model_not_found", "offline": "unreachable", "auth": "unauthenticated",
        "warming": "models_warming", "corrupt": "selection_unavailable",
        "db": "selection_unavailable",
    }
    if cause == "missing":
        state["pairs"] = [("A", "X")]
    elif cause in {"offline", "auth", "warming"}:
        async def discover():
            return DiscoveryResult(reachable=cause == "warming", error="SECRET-NOT-FOR-HTML",
                                   error_kind=expected[cause])
        monkeypatch.setattr(backend, "discover_models", discover)
    elif cause in {"corrupt", "db"}:
        async def broken(session):
            raise (ValueError if cause == "corrupt" else RuntimeError)("SECRET-NOT-FOR-HTML")
        monkeypatch.setattr(llm_config_repo, "read_selection", broken)
    result = await backend.complete_structured(schema=ProbeResult, system="s", parts=[], model="X")
    assert not result.ok and result.attempts == 0
    assert result.error_kind == expected[cause]
    assert "SECRET-NOT-FOR-HTML" not in repr(result)
    assert not [r for r in requests if r.method == "POST"]


async def test_selection_session_closes_before_network_and_retry_identity_is_frozen(
    session_factory, model_wire, monkeypatch
):
    requests, state = model_wire
    await save_pair(session_factory)
    opened = False

    @asynccontextmanager
    async def factory():
        nonlocal opened
        opened = True
        async with session_factory() as session:
            yield session
        opened = False

    backend = opencode_server.OpenCodeServerBackend(selection_session_factory=factory)
    original = backend.discover_models
    async def discover():
        assert not opened
        return await original()
    monkeypatch.setattr(backend, "discover_models", discover)
    monkeypatch.setattr(opencode_server.settings, "opencode_structured_retry_count", 1)
    state["payload"] = {"acknowledged": []}
    async def change_selection():
        assert not opened
        await save_pair(session_factory, "A", "X")
        state["payload"] = {"acknowledged": True}
    state["generate_hook"] = change_selection
    result = await backend.complete_structured(schema=ProbeResult, system="s", parts=[], model="X")
    assert result.ok and result.attempts == 2
    assert result.model == "X" and result.provider is None
    sessions = [json.loads(r.content) for r in requests if r.url.path == "/api/session"]
    assert len(sessions) == 1 and sessions[0]["model"]["providerID"] == "B"


async def test_session_transport_retry_keeps_snapshot_after_global_choice_changes(
    session_factory, model_wire
):
    requests, state = model_wire
    await save_pair(session_factory)
    backend = opencode_server.OpenCodeServerBackend(selection_session_factory=session_factory)
    async def change_selection():
        state["session_hook"] = None
        await save_pair(session_factory, "A", "new-model")
        raise httpx.ReadTimeout("test timeout")
    state["session_hook"] = change_selection
    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=[], model="environment", retries=2
    )
    assert result.ok
    attempts = [json.loads(r.content)["model"] for r in requests if r.url.path == "/api/session"]
    assert attempts == [{"id": "X", "providerID": "B"}] * 2
    assert len([r for r in requests if r.url.path.endswith("/generate")]) == 1
