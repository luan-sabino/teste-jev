"""Fase 4 - Metricas agregadas -> outputs/metrics/*.parquet.

Uso:
    uv run python scripts/04_metrics.py                 # usa enriched.parquet
    uv run python scripts/04_metrics.py --input outputs/enriched_sample.parquet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jevlab.pipeline.metrics import (  # noqa: E402
    build_all_metrics,
    mean_confidence,
    metrics_cruzamentos,
    score_distribution,
)

METRICS_DIR = ROOT / "outputs" / "metrics"
FULL_PATH = ROOT / "outputs" / "enriched.parquet"
SAMPLE_PATH = ROOT / "outputs" / "enriched_sample.parquet"


def main() -> int:
    parser = argparse.ArgumentParser(description="Metricas agregadas do enriquecimento")
    parser.add_argument("--input", type=Path, default=None)
    args = parser.parse_args()

    if args.input is not None:
        source = args.input
    elif FULL_PATH.exists():
        source = FULL_PATH
    elif SAMPLE_PATH.exists():
        source = SAMPLE_PATH
    else:
        print("ERRO: nenhum enriched*.parquet encontrado.", file=sys.stderr)
        return 2

    print(f"Lendo {source} ...")
    df = pd.read_parquet(source)
    if "enriquecido" in df.columns:
        enriched = df[df["enriquecido"] == True]  # noqa: E712
    else:
        enriched = df
    print(f"  linhas: {len(df)} | enriquecidas: {len(enriched)}")

    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    tables = build_all_metrics(enriched)
    for name, table in tables.items():
        path = METRICS_DIR / f"{name}.parquet"
        table.to_parquet(path, index=False)
        print(f"  {path.name}: {len(table)} linhas")

    score_distribution(enriched).to_parquet(METRICS_DIR / "qual_score.parquet", index=False)
    mean_confidence(enriched).to_parquet(METRICS_DIR / "confidence.parquet", index=False)

    for name, table in metrics_cruzamentos(enriched).items():
        path = METRICS_DIR / f"cruz_{name}.parquet"
        table.reset_index().to_parquet(path, index=False)
        print(f"  {path.name}: {table.shape[0]}x{table.shape[1]}")

    print(f"Metricas salvas em {METRICS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
