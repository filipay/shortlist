"""Strict model forms, local-only shared context, safe explicit discovery."""

import html
import json
import re

import pytest
from sqlalchemy import func, select

from app.db.models import LlmCall
from app.llm.base import DiscoveryResult, ProviderModel
from tests.conftest import OfflineLLMBackend
from tests.llm.test_model_selection import model_wire as model_wire

PAIR = '{"provider_id":"B","model_id":"X"}'


def option_values(body):
    return [html.unescape(value) for value in re.findall(r'<option value="([^"]*)"', body)]


async def stored(factory):
    from app.db.repositories import llm_config_repo
    async with factory() as session:
        return await llm_config_repo.read_selection(session)


async def seed(factory):
    from tests.llm.test_model_selection import save_pair
    await save_pair(factory)


@pytest.mark.parametrize("raw", [None, "{", "[]", "null", '{"provider_id":"B"}',
    '{"provider_id":"B","model_id":"X","key":"secret"}',
    '{"provider_id":false,"model_id":"X"}', '{"provider_id":" ","model_id":"X"}',
    pytest.param("x" * 20_000, id="oversized-input")])
async def test_malformed_input_never_changes_saved_pair(client, session_factory, raw):
    await seed(session_factory)
    response = await client.post(
        "/settings/llm-model", data={} if raw is None else {"model_selection": raw}
    )
    assert response.status_code == 422
    assert await stored(session_factory) == ProviderModel(provider_id="B", model_id="X")


@pytest.mark.parametrize("opening,closing,depth", [("[", "]", 8000), ('{"":', "}", 3200)])
async def test_deeply_nested_json_returns_422_and_preserves_saved_pair(
    client, session_factory, monkeypatch, opening, closing, depth
):
    await seed(session_factory)
    raw = opening * depth + "0" + closing * depth
    assert len(raw) < 16_384
    # Exercise the recursive stdlib fallback; C accelerators may parse iteratively.
    decoder = json.JSONDecoder()
    decoder.scan_once = json.scanner.py_make_scanner(decoder)
    monkeypatch.setattr(json, "_default_decoder", decoder)

    async def forbidden(*args):
        raise AssertionError("invalid input must not trigger discovery")

    monkeypatch.setattr(OfflineLLMBackend, "discover_models", forbidden)
    response = await client.post("/settings/llm-model", data={"model_selection": raw})
    assert response.status_code == 422
    assert PAIR in option_values(response.text)
    assert await stored(session_factory) == ProviderModel(provider_id="B", model_id="X")


async def test_unchanged_and_clear_work_offline_without_discovery(
    client, session_factory, monkeypatch
):
    await seed(session_factory)
    async def forbidden(*args):
        raise AssertionError("discovery must not run")
    monkeypatch.setattr(OfflineLLMBackend, "discover_models", forbidden)
    unchanged = await client.post("/settings/llm-model", data={"model_selection": PAIR})
    cleared = await client.post("/settings/llm-model", data={"model_selection": ""})
    assert unchanged.status_code == cleared.status_code == 200
    assert await stored(session_factory) is None


@pytest.mark.parametrize("cause,status", [("unreachable", 503), ("unauthenticated", 503),
    ("models_warming", 503), ("unknown", 422)])
async def test_unavailable_or_unknown_new_pair_preserves_saved_choice(
    client, session_factory, monkeypatch, cause, status
):
    await seed(session_factory)
    async def discover(self):
        return DiscoveryResult(reachable=cause in {"models_warming", "unknown"},
            error="SECRET-NOT-FOR-HTML", error_kind=None if cause == "unknown" else cause)
    monkeypatch.setattr(OfflineLLMBackend, "discover_models", discover)
    response = await client.post("/settings/llm-model", data={
        "model_selection": '{"provider_id":"A","model_id":"X"}'
    })
    assert response.status_code == status
    assert "SECRET-NOT-FOR-HTML" not in response.text
    assert PAIR in option_values(response.text)
    assert await stored(session_factory) == ProviderModel(provider_id="B", model_id="X")


async def test_local_get_and_unrelated_save_do_not_discover(client, session_factory, monkeypatch):
    await seed(session_factory)
    async def forbidden(*args):
        raise AssertionError("shared context must stay local")
    monkeypatch.setattr(OfflineLLMBackend, "discover_models", forbidden)
    for response in (
        await client.get("/settings"), await client.post("/settings/weights", data={})
    ):
        assert response.status_code == 200
        assert 'id="llm-model-selection"' in response.text
        assert PAIR in option_values(response.text)
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(LlmCall)) == 0


async def test_refresh_deduplicates_exact_pairs_escapes_and_keeps_saved_choice(
    client, session_factory, monkeypatch, caplog
):
    await seed(session_factory)
    unusual = ProviderModel(provider_id='提供/"<p>', model_id='x/"雪')
    async def discover(self):
        return DiscoveryResult(reachable=True, providers=[
            unusual, unusual, ProviderModel(provider_id="A", model_id="X")
        ])
    monkeypatch.setattr(OfflineLLMBackend, "discover_models", discover)
    response = await client.get("/settings/llm-models")
    value = json.dumps(unusual.model_dump(), separators=(",", ":"))
    assert response.status_code == 200
    assert option_values(response.text).count(value) == 1
    assert PAIR in option_values(response.text)
    assert "<p>" not in response.text.split('id="llm-model-selection"')[1].split("</select>")[0]
    assert "SECRET-NOT-FOR-HTML" not in response.text + caplog.text
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(LlmCall)) == 0


async def test_cross_origin_model_save_is_refused(client, session_factory):
    response = await client.post("/settings/llm-model", data={"model_selection": ""},
                                 headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert await stored(session_factory) is None


async def test_every_offered_bounded_unicode_identifier_can_be_saved(
    client, session_factory, monkeypatch
):
    pair = ProviderModel(provider_id="雪" * 512, model_id="🌨" * 512)
    async def discover(self):
        return DiscoveryResult(reachable=True, providers=[pair])
    monkeypatch.setattr(OfflineLLMBackend, "discover_models", discover)
    loaded = await client.get("/settings/llm-models")
    value = json.dumps(pair.model_dump(), separators=(",", ":"))
    assert value in option_values(loaded.text)
    saved = await client.post("/settings/llm-model", data={"model_selection": value})
    assert saved.status_code == 200
    assert await stored(session_factory) == pair


async def test_real_discovery_save_and_reload_keep_exact_escaped_identifiers_without_spending(
    client, session_factory, monkeypatch, model_wire
):
    import structlog

    from app import llm
    from app.db import session as session_module

    requests, state = model_wire
    pair = ProviderModel(provider_id='提供/"<p>', model_id='x/"雪')
    state["pairs"] = [(pair.provider_id, pair.model_id)]
    monkeypatch.setattr(session_module, "get_session_factory", lambda: session_factory)
    client._transport.app.dependency_overrides[llm.get_llm_backend] = llm.get_llm_backend
    with structlog.testing.capture_logs() as logs:
        loaded = await client.get("/settings/llm-models")
        value = json.dumps(pair.model_dump(), separators=(",", ":"))
        assert value in option_values(loaded.text)
        saved = await client.post("/settings/llm-model", data={"model_selection": value})
        reloaded = await client.get("/settings")
    assert saved.status_code == reloaded.status_code == 200
    assert value in option_values(reloaded.text)
    assert await stored(session_factory) == pair
    assert "SECRET-NOT-FOR-HTML" not in loaded.text + saved.text + reloaded.text + repr(logs)
    assert not [request for request in requests if request.method == "POST"]
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(LlmCall)) == 0
