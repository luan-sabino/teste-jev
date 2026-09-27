"""Metricas agregadas por tema (nomes, e-mails, carros, qualidade)."""

from __future__ import annotations

from typing import Any

import pandas as pd

QUAL_SCORE_LABELS = {
    0: "0 = inutilizavel",
    1: "1 = ruim",
    2: "2 = regular",
    3: "3 = bom",
    4: "4 = excelente",
}


def _value_counts(series: pd.Series, categoria: str) -> pd.DataFrame:
    counts = series.fillna("(sem resposta)").value_counts(dropna=False)
    total = max(1, int(counts.sum()))
    return pd.DataFrame(
        {
            "categoria": categoria,
            "valor": counts.index.astype(str),
            "n_leads": counts.values.astype(int),
            "pct": (counts.values / total * 100).round(2),
        }
    )


def _noul_rate(df: pd.DataFrame, column: str, categoria: str, limiar: float = 0.5) -> pd.DataFrame:
    if column not in df.columns:
        return pd.DataFrame(columns=["categoria", "valor", "n_leads", "pct"])
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    total = max(1, len(values))
    positivos = int((values >= limiar).sum())
    return pd.DataFrame(
        [
            {"categoria": categoria, "valor": "positivo", "n_leads": positivos, "pct": round(positivos / total * 100, 2)},
            {"categoria": categoria, "valor": "negativo", "n_leads": total - positivos, "pct": round((total - positivos) / total * 100, 2)},
        ]
    )


def metrics_nomes(df: pd.DataFrame) -> pd.DataFrame:
    parts = [
        _value_counts(df["q_nome_genero"], "nome_genero"),
        _value_counts(df["q_nome_caixa"], "nome_caixa"),
        _noul_rate(df, "q_nome_valido", "nome_valido"),
        _noul_rate(df, "q_nome_apelido", "nome_apelido"),
        _noul_rate(df, "q_nome_invalido", "nome_invalido"),
        _value_counts(df["baseline_nome_caixa"], "baseline_nome_caixa"),
    ]
    return pd.concat(parts, ignore_index=True)


def metrics_emails(df: pd.DataFrame) -> pd.DataFrame:
    parts = [
        _value_counts(df["q_email_provider"], "email_provider"),
        _value_counts(df["q_email_tipo"], "email_tipo"),
        _noul_rate(df, "q_email_typo", "email_typo"),
        _noul_rate(df, "q_email_bate_nome", "email_bate_nome"),
    ]
    return pd.concat(parts, ignore_index=True)


def metrics_carros(df: pd.DataFrame) -> pd.DataFrame:
    parts = [
        _value_counts(df["q_carro_marca"], "carro_marca"),
        _value_counts(df["q_carro_carroceria"], "carro_carroceria"),
        _value_counts(df["q_carro_cambio"], "carro_cambio"),
        _value_counts(df["q_carro_combustivel"], "carro_combustivel"),
        _value_counts(df["q_carro_cor"], "carro_cor"),
        _noul_rate(df, "q_carro_coerente", "carro_coerente"),
    ]
    return pd.concat(parts, ignore_index=True)


def score_distribution(df: pd.DataFrame, column: str = "q_qual_score") -> pd.DataFrame:
    if column not in df.columns:
        return pd.DataFrame(columns=["score_bucket", "label", "n_leads", "pct"])
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    buckets = values.round().clip(0, 4).astype(int)
    counts = buckets.value_counts().reindex([0, 1, 2, 3, 4], fill_value=0)
    total = max(1, int(counts.sum()))
    return pd.DataFrame(
        {
            "score_bucket": counts.index,
            "label": [QUAL_SCORE_LABELS[i] for i in counts.index],
            "n_leads": counts.values.astype(int),
            "pct": (counts.values / total * 100).round(2),
        }
    )


def mean_confidence(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for col in [c for c in df.columns if c.endswith("_confidence")]:
        values = pd.to_numeric(df[col], errors="coerce").dropna()
        if values.empty:
            continue
        rows.append(
            {
                "pergunta": col[len("q_") : -len("_confidence")],
                "confidence_media": round(float(values.mean()), 4),
                "n_respostas": int(len(values)),
            }
        )
    return pd.DataFrame(rows)


def metrics_qualidade(df: pd.DataFrame) -> pd.DataFrame:
    parts = [
        _noul_rate(df, "q_qual_bot", "qual_bot"),
        _noul_rate(df, "q_email_typo", "email_typo"),
        _noul_rate(df, "q_carro_coerente", "carro_coerente"),
    ]
    dist = score_distribution(df)
    if not dist.empty:
        dist_tidy = dist.rename(columns={"label": "valor"})
        dist_tidy["categoria"] = "qual_score"
        parts.append(dist_tidy[["categoria", "valor", "n_leads", "pct"]])
    conf = mean_confidence(df)
    if not conf.empty:
        conf_tidy = conf.rename(columns={"pergunta": "valor", "n_respostas": "n_leads"})
        conf_tidy["categoria"] = "confidence_media"
        conf_tidy["pct"] = conf_tidy["confidence_media"]
        parts.append(conf_tidy[["categoria", "valor", "n_leads", "pct"]])
    return pd.concat(parts, ignore_index=True)


def crosstab(df: pd.DataFrame, index_col: str, column_col: str, normalize: bool = True) -> pd.DataFrame:
    if index_col not in df.columns or column_col not in df.columns:
        return pd.DataFrame()
    table = pd.crosstab(df[index_col], df[column_col])
    if normalize:
        table = (table.div(table.sum(axis=1).replace(0, 1), axis=0) * 100).round(2)
    table.index.name = index_col
    table.columns.name = column_col
    return table


def metrics_cruzamentos(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    work = df.copy()
    if "q_qual_score" in work.columns:
        work["qual_score_bucket"] = (
            pd.to_numeric(work["q_qual_score"], errors="coerce").round().clip(0, 4).astype("Int64")
        )
    if "q_carro_tier" in work.columns:
        work["carro_tier_bucket"] = (
            pd.to_numeric(work["q_carro_tier"], errors="coerce").round().clip(0, 2).astype("Int64")
        )
    if "q_email_typo" in work.columns:
        typo = pd.to_numeric(work["q_email_typo"], errors="coerce")
        work["email_typo_bin"] = typo.map(
            lambda v: "positivo" if v is not None and v == v and v >= 0.5 else "negativo"
        )
    out: dict[str, pd.DataFrame] = {
        "carro_marca_x_tier": crosstab(work, "q_carro_marca", "carro_tier_bucket"),
        "qual_score_x_email_typo": crosstab(work, "qual_score_bucket", "email_typo_bin"),
        "nome_genero_x_carroceria": crosstab(work, "q_nome_genero", "q_carro_carroceria"),
    }
    return {k: v for k, v in out.items() if not v.empty}


def build_all_metrics(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "nomes": metrics_nomes(df),
        "emails": metrics_emails(df),
        "carros": metrics_carros(df),
        "qualidade": metrics_qualidade(df),
    }
