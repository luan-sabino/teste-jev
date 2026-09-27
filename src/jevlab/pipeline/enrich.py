"""Orquestracao assincrona do enriquecimento (fan-out de perguntas por lead)."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Iterable

import pandas as pd

from ..core.jev_client import JevClient


def flatten_answers(answers: dict[str, Any]) -> dict[str, Any]:
    """Achata respostas tipadas em colunas: `q_<nome>` e `q_<nome>_confidence`."""
    flat: dict[str, Any] = {}
    for name, answer in answers.items():
        atype = answer.get("type")
        if atype == "noul":
            flat[f"q_{name}"] = answer.get("noul")
        elif atype == "choice":
            flat[f"q_{name}"] = answer.get("choice")
            flat[f"q_{name}_confidence"] = answer.get("confidence")
        elif atype == "score":
            flat[f"q_{name}"] = answer.get("score")
            flat[f"q_{name}_confidence"] = answer.get("confidence")
    return flat


async def enrich_rows(
    states: list[dict[str, Any]],
    client: JevClient,
    concurrency: int = 8,
    limit: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Enriquece uma lista de states, tolerando falhas por lead."""
    states = states[:limit] if limit is not None else states
    total = len(states)
    semaphore = asyncio.Semaphore(max(1, concurrency))
    results: list[dict[str, Any] | None] = [None] * total
    completed = 0

    async def worker(index: int, state: dict[str, Any]) -> None:
        nonlocal completed
        async with semaphore:
            try:
                response = await client.evaluate(state)
                row = {"enriquecido": True, "erro": None, **flatten_answers(response["answers"])}
                row["jev_answers_json"] = json.dumps(response["answers"], ensure_ascii=False)
                row["jev_model"] = response.get("model")
                row["jev_cached"] = response.get("cached", False)
            except Exception as exc:  # noqa: BLE001 - falha por lead nao derruba o lote
                row = {"enriquecido": False, "erro": f"{type(exc).__name__}: {exc}"}
        results[index] = row
        completed += 1
        if on_progress is not None:
            on_progress(completed, total)

    await asyncio.gather(*(worker(i, s) for i, s in enumerate(states)))
    return [r if r is not None else {"enriquecido": False, "erro": "sem resultado"} for r in results]


async def enrich_dataframe(
    df: pd.DataFrame,
    client: JevClient,
    concurrency: int = 8,
    limit: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """Le `state_json`, enriquece e devolve o dataframe com colunas derivadas."""
    target = df.head(limit).copy() if limit is not None else df.copy()
    states = [json.loads(s) for s in target["state_json"]]
    rows = await enrich_rows(states, client, concurrency=concurrency, on_progress=on_progress)
    derived = pd.DataFrame(rows, index=target.index)
    return pd.concat([target, derived], axis=1)


def enrichment_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("q_")]
