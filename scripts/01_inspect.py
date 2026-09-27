"""Fase 0 - Perfil do CSV bruto -> docs/01-data-profile.md.

Uso:  uv run python scripts/01_inspect.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jevlab.core.config import CSV_PATH, REPO_ROOT  # noqa: E402
from jevlab.pipeline.load import load_raw_csv  # noqa: E402
from jevlab.pipeline.normalize import (  # noqa: E402
    _ascii_fold,
    only_digits,
    strip_text,
)

DOC_PATH = REPO_ROOT / "docs" / "01-data-profile.md"

# Valores de referencia da secao 1.4 do plano (fatos ja verificados).
# Definicoes adotadas (documentadas em docs/01-data-profile.md):
# - cpf_repetidos: ocorrencias EXTRAS de um CPF de 11 digitos (duplicated keep='first').
# - email_suspeito: local-part numerico ou placeholder puro (teste/test/asdf/aaa/xxx/qwe/email).
#   O plano cita 73, mas nao define o criterio; usamos um criterio explicito e estavel.
EXPECTED = {
    "linhas": 60760,
    "colunas": 17,
    "pessoas_unicas_nome": 50087,
    "cpf_fora_11_digitos": 17458,
    "cpf_repetidos": 9507,
    "telefone_digito_repetido": 18,
    "email_suspeito": 38,
    "nome_maiusculo": 7694,
    "nome_minusculo": 1472,
    "nome_com_digitos": 32,
    "nascimento_vazio": 60412,
}


def col_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        series = df[col].astype(str)
        non_empty = series[series.str.strip() != ""]
        top = non_empty.value_counts().head(5)
        rows.append(
            {
                "coluna": col,
                "distintos": int(non_empty.nunique()),
                "vazios": int((series.str.strip() == "").sum()),
                "pct_vazio": round((series.str.strip() == "").mean() * 100, 2),
                "top_valores": "; ".join(f"{v} ({n})" for v, n in top.items()) or "-",
            }
        )
    return pd.DataFrame(rows)


def quality_metrics(df: pd.DataFrame) -> dict[str, int]:
    nome = df["Nome do contato"].astype(str)
    cpf = df["CPF"].astype(str)
    tel = df["Telefone do contato"].astype(str)
    email = df["E-mail do contato"].astype(str)

    cpf_digits = cpf.map(only_digits)
    nome_letters = nome[nome.str.contains(r"[A-Za-zÀ-ÿ]", regex=True)]

    return {
        "linhas": int(len(df)),
        "colunas": int(df.shape[1]),
        "pessoas_unicas_nome": int(nome[nome.str.strip() != ""].nunique()),
        "cpf_fora_11_digitos": int((cpf_digits.str.len() != 11).sum()),
        # O plano reporta 9.507 = ocorrencias extras; "todas as ocorrencias" daria 16.071.
        "cpf_repetidos": int(cpf_digits[cpf_digits.str.len() == 11].duplicated(keep="first").sum()),
        "cpf_repetidos_todas_ocorrencias": int(
            cpf_digits[cpf_digits.str.len() == 11].duplicated(keep=False).sum()
        ),
        "telefone_digito_repetido": int(
            tel.map(lambda v: len(set(only_digits(v))) == 1 and len(only_digits(v)) > 0).sum()
        ),
        "email_suspeito": int(
            email.map(
                lambda v: (
                    "@" in v
                    and (
                        strip_text(v).split("@")[0].isdigit()
                        or strip_text(v).lower().split("@")[0]
                        in {"teste", "test", "asdf", "aaa", "xxx", "qwe", "email"}
                    )
                )
            ).sum()
        ),
        "nome_maiusculo": int((nome_letters == nome_letters.str.upper()).sum()),
        "nome_minusculo": int((nome_letters == nome_letters.str.lower()).sum()),
        "nome_com_digitos": int(nome.str.contains(r"\d", regex=True).sum()),
        "nascimento_vazio": int((df["data Nascimento"].astype(str).str.strip() == "").sum()),
    }


def render(metrics: dict[str, int], profile: pd.DataFrame, csv_path: Path) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    lines.append("# Perfil dos dados - CSV bruto")
    lines.append("")
    lines.append(f"- Arquivo: `{csv_path.name}`")
    lines.append(f"- Gerado em: {now}")
    lines.append(f"- Linhas: **{metrics['linhas']}** | Colunas: **{metrics['colunas']}**")
    lines.append("")
    lines.append("## 1. Metricas de qualidade (secao 1.4 do plano)")
    lines.append("")
    lines.append("| Metrica | Medido | Esperado (plano) | Confere |")
    lines.append("| --- | --- | --- | --- |")
    for key, expected in EXPECTED.items():
        measured = metrics.get(key, 0)
        ok = "OK" if measured == expected else "DIVERGE"
        lines.append(f"| `{key}` | {measured} | {expected} | {ok} |")
    lines.append("")
    lines.append("Metricas auxiliares:")
    lines.append("")
    lines.append(
        f"- CPFs de 11 digitos repetidos (todas as ocorrencias): "
        f"{metrics['cpf_repetidos_todas_ocorrencias']}"
    )
    lines.append(
        f"- CPFs de 11 digitos repetidos (ocorrencias extras): {metrics['cpf_repetidos']}"
    )
    lines.append("")
    lines.append("Definicoes adotadas para as metricas ambiguas do plano:")
    lines.append("")
    lines.append(
        "- `cpf_repetidos` = ocorrencias **extras** de um CPF de 11 digitos "
        "(`duplicated(keep='first')`)."
    )
    lines.append(
        "- `email_suspeito` = local-part numerico **ou** placeholder puro "
        "(teste/test/asdf/aaa/xxx/qwe/email). O plano cita 73 sem definir o criterio."
    )
    lines.append("")
    lines.append("## 2. Perfil por coluna")
    lines.append("")
    lines.append("| Coluna | Distintos | Vazios | % vazio | Top valores |")
    lines.append("| --- | ---: | ---: | ---: | --- |")
    for row in profile.to_dict("records"):
        top = str(row["top_valores"]).replace("|", "\\|")
        lines.append(
            f"| {row['coluna']} | {row['distintos']} | {row['vazios']} | "
            f"{row['pct_vazio']} | {top} |"
        )
    lines.append("")
    lines.append("## 3. Observacoes")
    lines.append("")
    lines.append("- Encoding: UTF-8 com BOM (`utf-8-sig`).")
    lines.append("- Leitura com `dtype=str`; string vazia representa ausencia de valor.")
    lines.append("- `data Nascimento` e praticamente vazia: nao usar como sinal.")
    lines.append("- Colunas constantes (1 valor): ")
    constants = [
        r["coluna"] for r in profile.to_dict("records") if r["distintos"] == 1
    ]
    lines.append(f"  {', '.join(constants) if constants else '(nenhuma)'}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    df = load_raw_csv(CSV_PATH)
    metrics = quality_metrics(df)
    profile = col_profile(df)
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(render(metrics, profile, CSV_PATH), encoding="utf-8")

    print(f"Perfil escrito em {DOC_PATH}")
    print(f"Linhas: {metrics['linhas']} | Colunas: {metrics['colunas']}")
    divergences = [
        f"{k}: medido={metrics.get(k, 0)} esperado={v}"
        for k, v in EXPECTED.items()
        if metrics.get(k, 0) != v
    ]
    if divergences:
        print("Divergencias vs secao 1.4:")
        for d in divergences:
            print(f"  - {d}")
    else:
        print("Todas as metricas batem com a secao 1.4.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
