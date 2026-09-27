"""Monta o `state` canonico por lead e as flags deterministicas (baseline)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Mapping

import pandas as pd

from .load import is_blank
from .normalize import (
    cpf_valido,
    email_domain,
    flag_email_typo_regex,
    flag_nome_invalido_regex,
    flag_tel_invalido,
    mask_digits,
    mask_email,
    mask_telefone,
    nome_caixa_rule,
    normalize_email,
    only_digits,
    strip_text,
)

_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d")


def parse_date_iso(value: object) -> str | None:
    text = strip_text(value)
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_km(value: object) -> int | None:
    text = only_digits(value) if strip_text(value) else ""
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def build_state(row: Mapping[str, Any], mask_pii: bool = True) -> dict[str, Any]:
    """Constroi o objeto `state` da secao 3.5 do plano."""
    nome = strip_text(row.get("Nome do contato"))
    # nomes com digitos frequentemente carregam CPF/telefone embutidos (PII).
    if mask_pii:
        nome = mask_digits(nome)
    email_raw = strip_text(row.get("E-mail do contato"))
    email = mask_email(email_raw) if mask_pii else normalize_email(email_raw)
    telefone = mask_telefone(row.get("Telefone do contato")) if mask_pii else only_digits(
        row.get("Telefone do contato")
    )

    return {
        "nome": nome or None,
        "email": email,
        "email_dominio": email_domain(email_raw) or None,
        "telefone": telefone or None,
        "carro": strip_text(row.get("Carro")) or None,
        "km": parse_km(row.get("KM")),
        "vigencia": parse_date_iso(row.get("Vigência")),
        "data_lead": parse_date_iso(row.get("Data Lead")),
    }


def state_to_json(state: Mapping[str, Any]) -> str:
    return json.dumps(state, ensure_ascii=False, sort_keys=True)


def add_baseline_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona as flags deterministicas usadas para comparar com o JEV."""
    out = df.copy()
    nome_col = out.get("Nome do contato", pd.Series("", index=out.index))
    cpf_col = out.get("CPF", pd.Series("", index=out.index))
    email_col = out.get("E-mail do contato", pd.Series("", index=out.index))
    tel_col = out.get("Telefone do contato", pd.Series("", index=out.index))

    out["baseline_cpf_valido"] = cpf_col.map(cpf_valido)
    out["baseline_email_typo"] = [
        flag_email_typo_regex(e, n) for e, n in zip(email_col, nome_col)
    ]
    out["baseline_tel_invalido"] = tel_col.map(flag_tel_invalido)
    out["baseline_nome_caixa"] = nome_col.map(nome_caixa_rule)
    out["baseline_nome_invalido"] = nome_col.map(flag_nome_invalido_regex)
    return out


def build_states_dataframe(df: pd.DataFrame, mask_pii: bool = True) -> pd.DataFrame:
    """Gera colunas `state_json` + flags baseline a partir de leads deduplicados."""
    out = add_baseline_flags(df)
    out["state_json"] = [state_to_json(build_state(row, mask_pii=mask_pii)) for row in out.to_dict("records")]
    return out


def state_is_masked(state_json: str) -> bool:
    """True se o state nao contem 11 digitos seguidos (heuristica anti-PII crua)."""
    import re

    return re.search(r"\d{11}", state_json) is None


__all__ = [
    "build_state",
    "state_to_json",
    "build_states_dataframe",
    "add_baseline_flags",
    "parse_date_iso",
    "parse_km",
    "state_is_masked",
    "is_blank",
]
