"""Leitura robusta do CSV bruto (UTF-8 com BOM)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..core.config import CSV_PATH

EXPECTED_COLUMNS = [
    "Nome da Oportunidade",
    "Nome da Organização",
    "Nome do contato",
    "Telefone do contato",
    "E-mail do contato",
    "Fonte da negociação",
    "Campanha",
    "Segmento do cliente",
    "Responsável",
    "Etapa",
    "CPF",
    "data Nascimento",
    "cod mob",
    "Data Lead",
    "Carro",
    "KM",
    "Vigência",
]


def load_raw_csv(path: str | Path | None = None) -> pd.DataFrame:
    """Le o CSV preservando strings (sem inferencia de tipos / sem NaN)."""
    csv_path = Path(path) if path is not None else CSV_PATH
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV nao encontrado: {csv_path}")

    df = pd.read_csv(
        csv_path,
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
        na_filter=False,
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def is_blank(value: object) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == ""
