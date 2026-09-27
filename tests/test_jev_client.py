"""Testes offline do cliente JEV (MockTransport, sem rede)."""

from __future__ import annotations

import json

import httpx
import pytest

from jevlab.core.cache import DiskCache, cache_key
from jevlab.core.config import REPO_ROOT, Settings
from jevlab.core.jev_client import JevClient, JevValidationError, validate_answers
from jevlab.core.questions import get_questions

FIXTURE = REPO_ROOT / "outputs" / "fixtures" / "jev_response.json"


@pytest.fixture()
def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture()
def sample_state() -> dict:
    return {
        "nome": "Oslano Amorim Barbosa",
        "email": "l***@yahoo.com.br",
        "email_dominio": "yahoo.com.br",
        "telefone": "(11) ****-7562",
        "carro": "Fiat Argo Drive 1.0 MT Cinza Silverstone",
        "km": 2500,
        "vigencia": None,
        "data_lead": "2026-01-01",
    }


def _client(tmp_path, fixture, calls: list[httpx.Request]) -> JevClient:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=fixture)

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    settings = Settings(
        openrouter_api_key="test-key",
        jev_model="typesafe/jev-1.13",
        mask_pii=True,
    )
    cache = DiskCache(tmp_path / "cache")
    return JevClient(settings=settings, http_client=http, cache=cache, log_cost=False)


async def test_evaluate_returns_typed_answers(tmp_path, fixture, sample_state) -> None:
    calls: list[httpx.Request] = []
    client = _client(tmp_path, fixture, calls)
    async with client:
        result = await client.evaluate(sample_state)

    assert result["cached"] is False
    assert result["model"].startswith("typesafe/jev-1.13")
    assert (
        result["answers"]["nome_genero"]["choice"]
        == fixture["answers"]["nome_genero"]["choice"]
    )
    assert result["answers"]["nome_valido"]["noul"] == pytest.approx(
        fixture["answers"]["nome_valido"]["noul"]
    )
    assert isinstance(result["answers"]["qual_score"]["score"], float)
    assert result["usage"]["input_tokens"] == fixture["usage"]["input_tokens"]
    assert result["usage"]["cost"] == pytest.approx(fixture["usage"]["cost"])

    sent = json.loads(calls[0].content)
    assert sent["model"] == "typesafe/jev-1.13"
    assert sent["state"] == sample_state
    assert len(sent["questions"]) == 18
    assert calls[0].headers["authorization"] == "Bearer test-key"
    assert calls[0].url.path.endswith("/alpha/decisions")


async def test_second_call_is_served_from_cache(tmp_path, fixture, sample_state) -> None:
    calls: list[httpx.Request] = []
    client = _client(tmp_path, fixture, calls)
    async with client:
        first = await client.evaluate(sample_state)
        second = await client.evaluate(sample_state)

    assert first["cached"] is False
    assert second["cached"] is True
    assert second["answers"] == first["answers"]
    assert len(calls) == 1  # segunda chamada nao gastou token


def test_cache_key_is_stable_and_sensitive() -> None:
    questions = get_questions()
    state = {"nome": "Ana"}
    key1 = cache_key(state, questions, "typesafe/jev-1.13", "v1")
    key2 = cache_key({"nome": "Ana"}, questions, "typesafe/jev-1.13", "v1")
    key3 = cache_key({"nome": "Bruno"}, questions, "typesafe/jev-1.13", "v1")
    assert key1 == key2
    assert key1 != key3


def test_validate_answers_rejects_bad_noul() -> None:
    questions = {"x": {"type": "noul"}}
    with pytest.raises(JevValidationError):
        validate_answers({"x": {"type": "noul", "noul": 1.5}}, questions)


def test_validate_answers_rejects_unknown_choice() -> None:
    questions = {"x": {"type": "choice", "criteria": {"a": "A", "b": "B"}}}
    with pytest.raises(JevValidationError):
        validate_answers(
            {"x": {"type": "choice", "choice": "c", "probabilities": {}}}, questions
        )


async def test_api_error_is_not_retried(tmp_path, sample_state) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(401, json={"error": "unauthorized"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(openrouter_api_key="bad")
    client = JevClient(
        settings=settings,
        http_client=http,
        cache=DiskCache(tmp_path / "cache"),
        log_cost=False,
    )
    with pytest.raises(Exception):
        await client.evaluate(sample_state)
    assert len(calls) == 1
