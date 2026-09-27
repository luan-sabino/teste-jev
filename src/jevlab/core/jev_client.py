"""Cliente HTTP do JEV (System One / Decisions API) via OpenRouter.

Endpoint verificado na documentacao oficial:
    POST https://openrouter.ai/api/alpha/decisions
    body: { "model": "typesafe/jev-1.13", "state": ..., "questions": {...} }
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .cache import DiskCache, cache_key
from .config import Settings, get_settings
from .questions import get_questions, questions_version


class JevError(RuntimeError):
    """Erro nao recuperavel ao falar com o JEV."""


class JevRetryableError(JevError):
    """Erro transitorio (429/5xx/rede) - candidato a retry."""


class JevValidationError(JevError):
    """Resposta do JEV nao respeita o contrato do catalogo."""


def _extract_retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


def validate_answers(
    answers: dict[str, Any], questions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Valida e normaliza cada resposta conforme o tipo declarado na pergunta."""
    if not isinstance(answers, dict):
        raise JevValidationError(f"campo `answers` invalido: {type(answers)}")

    normalized: dict[str, Any] = {}
    for name, qdef in questions.items():
        qtype = qdef["type"]
        answer = answers.get(name)
        if not isinstance(answer, dict):
            raise JevValidationError(f"resposta ausente/invalida para `{name}`")

        if qtype == "noul":
            value = answer.get("noul")
            if not isinstance(value, (int, float)) or not (0.0 <= float(value) <= 1.0):
                raise JevValidationError(f"`{name}.noul` fora de [0,1]: {value!r}")
            normalized[name] = {"type": "noul", "noul": float(value)}

        elif qtype == "choice":
            choice = answer.get("choice")
            valid = list(qdef.get("criteria", {}))
            if choice not in valid:
                raise JevValidationError(
                    f"`{name}.choice`={choice!r} fora de {valid}"
                )
            probs = answer.get("probabilities") or {}
            normalized[name] = {
                "type": "choice",
                "choice": choice,
                "probabilities": {k: float(v) for k, v in probs.items()},
                "confidence": (
                    float(answer["confidence"])
                    if answer.get("confidence") is not None
                    else None
                ),
            }

        elif qtype == "score":
            score = answer.get("score")
            if not isinstance(score, (int, float)):
                raise JevValidationError(f"`{name}.score` nao numerico: {score!r}")
            probs = answer.get("probabilities") or {}
            normalized[name] = {
                "type": "score",
                "score": float(score),
                "legend": answer.get("legend") or {},
                "probabilities": {k: float(v) for k, v in probs.items()},
                "confidence": (
                    float(answer["confidence"])
                    if answer.get("confidence") is not None
                    else None
                ),
            }
        else:  # pragma: no cover - garantido pelo catalogo
            raise JevValidationError(f"tipo desconhecido `{qtype}` para `{name}`")

    return normalized


def append_cost_log(record: dict[str, Any], path: str | Path | None = None) -> None:
    target = Path(path) if path is not None else get_settings().cost_log_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_cost_log(path: str | Path | None = None) -> list[dict[str, Any]]:
    target = Path(path) if path is not None else get_settings().cost_log_path
    if not target.exists():
        return []
    records = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def total_cost(path: str | Path | None = None) -> float:
    return sum(float(r.get("cost") or 0.0) for r in read_cost_log(path))


class JevClient:
    """Cliente assincrono do JEV com cache em disco, retry e contabilizacao de custo."""

    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
        cache: DiskCache | None = None,
        log_cost: bool = True,
        max_attempts: int = 5,
    ) -> None:
        self.settings = settings or get_settings()
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            timeout=self.settings.request_timeout_s
        )
        self.cache = cache if cache is not None else DiskCache(self.settings.cache_dir)
        self.log_cost = log_cost
        self.max_attempts = max_attempts

    async def __aenter__(self) -> "JevClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ------------------------------------------------------------------ internos
    def build_payload(
        self,
        state: Any,
        questions: dict[str, dict[str, Any]],
        model: str,
    ) -> dict[str, Any]:
        return {"model": model, "state": state, "questions": questions}

    async def _post(self, payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
        api_key = self.settings.require_api_key()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        started = time.perf_counter()
        retrying = Retrying(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=20),
            retry=retry_if_exception_type(JevRetryableError),
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                try:
                    response = await self._client.post(
                        self.settings.decisions_url, headers=headers, json=payload
                    )
                except httpx.HTTPError as exc:  # erros de rede
                    raise JevRetryableError(f"falha de rede: {exc}") from exc

                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = _extract_retry_after(response)
                    if retry_after:
                        time.sleep(retry_after)
                    raise JevRetryableError(
                        f"HTTP {response.status_code}: {response.text[:200]}"
                    )
                if response.status_code >= 400:
                    raise JevError(
                        f"HTTP {response.status_code}: {response.text[:500]}"
                    )
                return response.json(), time.perf_counter() - started
        raise JevError("retry esgotado")  # pragma: no cover

    # -------------------------------------------------------------------- publico
    async def evaluate(
        self,
        state: Any,
        questions: dict[str, dict[str, Any]] | None = None,
        model: str | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Envia um `state` e o catalogo de perguntas; retorna respostas tipadas.

        Retorno: dict com `id`, `model`, `provider`, `answers`, `usage`,
        `cached` (bool) e `cache_key`.
        """
        model = model or self.settings.jev_model
        questions = questions or get_questions()
        version = questions_version()
        key = cache_key(state, questions, model, version)

        if use_cache:
            hit = self.cache.get(key)
            if hit is not None:
                hit["cached"] = True
                hit["cache_key"] = key
                return hit

        payload = self.build_payload(state, questions, model)
        data, elapsed = await self._post(payload)

        answers = validate_answers(data.get("answers", {}), questions)
        usage = data.get("usage") or {}
        result = {
            "id": data.get("id"),
            "model": data.get("model", model),
            "provider": data.get("provider"),
            "answers": answers,
            "usage": {
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "cost": usage.get("cost"),
            },
            "cached": False,
            "cache_key": key,
            "elapsed_s": elapsed,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.cache.set(key, result)

        if self.log_cost:
            append_cost_log(
                {
                    "created_at": result["created_at"],
                    "id": result["id"],
                    "model": result["model"],
                    "provider": result["provider"],
                    "input_tokens": result["usage"]["input_tokens"],
                    "output_tokens": result["usage"]["output_tokens"],
                    "cost": result["usage"]["cost"],
                    "cache_key": key,
                },
                self.settings.cost_log_path,
            )

        return result

    async def evaluate_batch(
        self,
        states: list[Any],
        questions: dict[str, dict[str, Any]] | None = None,
        model: str | None = None,
        on_result: Any = None,
    ) -> list[dict[str, Any]]:
        """Placeholder simples; o enriquecimento concorrente vive no pipeline."""
        results = []
        for state in states:
            result = await self.evaluate(state, questions=questions, model=model)
            results.append(result)
            if on_result is not None:
                on_result(result)
        return results
