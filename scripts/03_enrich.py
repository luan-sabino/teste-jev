"""Fases 3/4 - Enriquecimento JEV (amostra ou base completa), com resume.

Uso:
    uv run python scripts/03_enrich.py --limit 300     # amostra -> enriched_sample.parquet
    uv run python scripts/03_enrich.py --all           # base   -> enriched.parquet
    uv run python scripts/03_enrich.py --all --no-resume

Reexecutar e barato: o cache em disco evita novas chamadas; o resume pula
leads ja enriquecidos.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jevlab.core.config import get_settings  # noqa: E402
from jevlab.core.jev_client import JevClient, total_cost  # noqa: E402
from jevlab.pipeline.enrich import enrich_rows  # noqa: E402

LEADS_PATH = ROOT / "outputs" / "leads_unique.parquet"
SAMPLE_PATH = ROOT / "outputs" / "enriched_sample.parquet"
FULL_PATH = ROOT / "outputs" / "enriched.parquet"
FIXTURE_PATH = ROOT / "outputs" / "fixtures" / "jev_response.json"


class MockJevClient:
    """Cliente falso para validar o pipeline/dashboard offline (--mock)."""

    def __init__(self, fixture: dict, cost_per_call: float = 0.00003) -> None:
        self.fixture = fixture
        self.cost_per_call = cost_per_call

    async def evaluate(self, state: dict, **_: object) -> dict:  # noqa: D401
        return {
            "id": "mock",
            "model": self.fixture.get("model", "mock"),
            "provider": "mock",
            "answers": self.fixture["answers"],
            "usage": {"input_tokens": 800, "output_tokens": 100, "cost": self.cost_per_call},
            "cached": False,
        }

    async def aclose(self) -> None:
        return None


class _MockContext:
    def __init__(self) -> None:
        self.client: MockJevClient | None = None

    async def __aenter__(self) -> MockJevClient:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.client = MockJevClient(fixture)
        return self.client

    async def __aexit__(self, *exc: object) -> None:
        return None


def _mock_context() -> _MockContext:
    return _MockContext()


def load_done_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        df = pd.read_parquet(path, columns=["lead_key", "enriquecido"])
    except Exception:
        return set()
    return set(df.loc[df["enriquecido"] == True, "lead_key"])  # noqa: E712


def write_parquet(frames: list[pd.DataFrame], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    combined = pd.concat(frames, ignore_index=True)
    if "lead_key" in combined.columns:
        combined = combined.drop_duplicates("lead_key", keep="last")
    combined.to_parquet(path, index=False)


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    if not args.mock and not settings.openrouter_api_key:
        print(
            "ERRO: OPENROUTER_API_KEY nao configurada. Copie .env.example para .env "
            "(ou use --mock para validar offline).",
            file=sys.stderr,
        )
        return 2

    if not LEADS_PATH.exists():
        print(f"ERRO: {LEADS_PATH} nao existe. Rode scripts/02_build_states.py.", file=sys.stderr)
        return 2

    out_path = FULL_PATH if args.all else SAMPLE_PATH
    leads = pd.read_parquet(LEADS_PATH)
    target = leads if args.all else leads.head(args.limit or 300)
    print(f"Leads disponiveis: {len(leads)} | alvo desta execucao: {len(target)}")

    frames: list[pd.DataFrame] = []
    done_keys: set[str] = set()
    if not args.no_resume:
        done_keys = load_done_keys(out_path)
        if done_keys:
            existing = pd.read_parquet(out_path)
            frames.append(existing)
            print(f"Resume: {len(done_keys)} leads ja enriquecidos em {out_path.name}")

    todo = target[~target["lead_key"].isin(done_keys)].reset_index(drop=True)
    print(f"Pendentes: {len(todo)}")

    start_cost = total_cost()
    print(f"Custo acumulado antes: ${start_cost:.6f} (cap ${settings.spend_cap_usd})")
    if start_cost >= settings.spend_cap_usd:
        print("ERRO: cap de gasto ja atingido.", file=sys.stderr)
        return 3

    if todo.empty:
        print("Nada a fazer.")
        return 0

    concurrency = args.concurrency or settings.max_concurrency
    chunk_size = max(concurrency, args.checkpoint_every)

    client_ctx = (
        _mock_context() if args.mock else JevClient(settings=settings)
    )
    async with client_ctx as client:
        for start in range(0, len(todo), chunk_size):
            chunk = todo.iloc[start : start + chunk_size]
            states = [json.loads(s) for s in chunk["state_json"]]
            print(f"  processando {start + 1}-{start + len(chunk)} de {len(todo)} ...")

            rows = await enrich_rows(
                states,
                client,
                concurrency=concurrency,
                on_progress=lambda done, total: (
                    print(f"    {done}/{total}", end="\r", flush=True)
                    if done % 25 == 0 or done == total
                    else None
                ),
            )
            print()
            chunk_full = pd.concat(
                [chunk.drop(columns=["state_json"]).reset_index(drop=True), pd.DataFrame(rows)],
                axis=1,
            )
            frames.append(chunk_full)
            if args.checkpoint and (start + len(chunk)) < len(todo):
                write_parquet(frames, out_path)
                print(f"    checkpoint salvo ({out_path.name})")

            spent = total_cost()
            if spent >= settings.spend_cap_usd:
                print(f"    CAP atingido (${spent:.6f}); interrompendo.")
                break

    write_parquet(frames, out_path)

    result = pd.concat(frames, ignore_index=True)
    ok = int(result["enriquecido"].sum()) if "enriquecido" in result else 0
    total_n = len(result)
    spent = total_cost() - start_cost
    print(f"Salvo em {out_path}")
    print(f"Enriquecidos: {ok}/{total_n} ({ok / max(1, total_n) * 100:.2f}%)")
    print(f"Custo desta execucao: ${spent:.6f} | total acumulado: ${total_cost():.6f}")
    if ok / max(1, total_n) < 0.98:
        print("AVISO: sucesso abaixo de 98% (checkpoint exige >= 98%).")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Enriquecimento JEV")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="processa a base completa")
    group.add_argument("--limit", type=int, default=None, help="processa uma amostra")
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--checkpoint-every", type=int, default=100)
    parser.add_argument(
        "--mock",
        action="store_true",
        help="nao chama a API: usa o fixture (validacao offline do pipeline)",
    )
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--no-checkpoint", dest="checkpoint", action="store_false", default=True)
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
