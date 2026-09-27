"""Fase 3/6 - Amostra anotada a mao + calculo de acuracia.

Uso:
    uv run python scripts/06_manual_check.py --generate 20
    # edite outputs/manual_check.csv preenchendo as colunas manual_*
    uv run python scripts/06_manual_check.py --score
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SAMPLE_PATH = ROOT / "outputs" / "enriched_sample.parquet"
FULL_PATH = ROOT / "outputs" / "enriched.parquet"
CHECK_PATH = ROOT / "outputs" / "manual_check.csv"

FIELDS = ["nome_genero", "email_provider", "carro_marca"]


def source_path() -> Path:
    return FULL_PATH if FULL_PATH.exists() else SAMPLE_PATH


def generate(n: int) -> int:
    path = source_path()
    if not path.exists():
        print("ERRO: nenhum enriched*.parquet encontrado.", file=sys.stderr)
        return 2
    df = pd.read_parquet(path)
    if "enriquecido" in df.columns:
        df = df[df["enriquecido"] == True]  # noqa: E712
    sample = df.head(n).copy()
    out = pd.DataFrame(
        {
            "lead_key": sample.get("lead_key"),
            "nome": sample.get("nome"),
            "email_display": sample.get("email_display"),
            "carro": sample.get("carro"),
            "pred_nome_genero": sample.get("q_nome_genero"),
            "pred_email_provider": sample.get("q_email_provider"),
            "pred_carro_marca": sample.get("q_carro_marca"),
            "manual_nome_genero": "",
            "manual_email_provider": "",
            "manual_carro_marca": "",
        }
    )
    out.to_csv(CHECK_PATH, index=False)
    print(f"Anotacoes geradas em {CHECK_PATH} ({len(out)} leads).")
    print("Preencha as colunas manual_* e rode --score.")


def score() -> int:
    if not CHECK_PATH.exists():
        print(f"ERRO: {CHECK_PATH} nao existe. Rode --generate primeiro.", file=sys.stderr)
        return 2
    df = pd.read_csv(CHECK_PATH, dtype=str, keep_default_na=False)
    rows = []
    for label in FIELDS:
        manual = df.get(f"manual_{label}", pd.Series("", index=df.index)).str.strip().str.lower()
        pred = df.get(f"pred_{label}", pd.Series("", index=df.index)).str.strip().str.lower()
        answered = manual != ""
        n = int(answered.sum())
        if n == 0:
            rows.append({"campo": label, "n_anotado": 0, "acertos": 0, "acuracia_pct": None})
            continue
        acertos = int((manual[answered] == pred[answered]).sum())
        rows.append(
            {
                "campo": label,
                "n_anotado": n,
                "acertos": acertos,
                "acuracia_pct": round(acertos / n * 100, 2),
            }
        )
    result = pd.DataFrame(rows)
    print(result.to_string(index=False))
    valid = result[result["acuracia_pct"].notna()]
    if len(valid) == 0:
        print("Nenhuma anotacao encontrada nas colunas manual_*.")
        return 2
    abaixo = valid[valid["acuracia_pct"] < 85]
    if len(abaixo):
        print("AVISO: campos abaixo de 85%:", ", ".join(abaixo["campo"]))
        return 1
    print("Todos os campos anotados estao >= 85%.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Amostra anotada e acuracia")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--generate", type=int, metavar="N")
    group.add_argument("--score", action="store_true")
    args = parser.parse_args()
    if args.score:
        return score()
    return generate(args.generate)


if __name__ == "__main__":
    raise SystemExit(main())
