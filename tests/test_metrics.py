"""Testes das metricas e do achatamento de respostas."""

from __future__ import annotations

import pandas as pd

from jevlab.pipeline.enrich import flatten_answers
from jevlab.pipeline.metrics import (
    build_all_metrics,
    mean_confidence,
    metrics_cruzamentos,
    score_distribution,
)


def _enriched_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "lead_key": "cpf:1",
                "q_nome_genero": "masculino",
                "q_nome_caixa": "correto",
                "q_nome_valido": 0.9,
                "q_nome_apelido": 0.1,
                "q_nome_invalido": 0.05,
                "q_email_provider": "gmail",
                "q_email_tipo": "pessoal",
                "q_email_typo": 0.2,
                "q_email_bate_nome": 0.8,
                "q_carro_marca": "fiat",
                "q_carro_carroceria": "hatch",
                "q_carro_cambio": "manual",
                "q_carro_combustivel": "flex",
                "q_carro_cor": "cinza",
                "q_carro_coerente": 0.95,
                "q_carro_tier": 0.1,
                "q_qual_bot": 0.02,
                "q_qual_score": 3.4,
                "q_nome_genero_confidence": 0.9,
                "q_qual_score_confidence": 0.8,
                "baseline_nome_caixa": "correto",
            },
            {
                "lead_key": "cpf:2",
                "q_nome_genero": "feminino",
                "q_nome_caixa": "tudo_maiusculo",
                "q_nome_valido": 0.7,
                "q_nome_apelido": 0.3,
                "q_nome_invalido": 0.4,
                "q_email_provider": "yahoo",
                "q_email_tipo": "pessoal",
                "q_email_typo": 0.7,
                "q_email_bate_nome": 0.3,
                "q_carro_marca": "fiat",
                "q_carro_carroceria": "suv",
                "q_carro_cambio": "automatico",
                "q_carro_combustivel": "flex",
                "q_carro_cor": "preto",
                "q_carro_coerente": 0.6,
                "q_carro_tier": 2.0,
                "q_qual_bot": 0.8,
                "q_qual_score": 1.2,
                "q_nome_genero_confidence": 0.7,
                "q_qual_score_confidence": 0.6,
                "baseline_nome_caixa": "tudo_maiusculo",
            },
        ]
    )


def test_flatten_answers() -> None:
    answers = {
        "a": {"type": "noul", "noul": 0.9},
        "b": {"type": "choice", "choice": "x", "confidence": 0.8, "probabilities": {}},
        "c": {"type": "score", "score": 1.5, "confidence": 0.7, "legend": {}, "probabilities": {}},
    }
    flat = flatten_answers(answers)
    assert flat["q_a"] == 0.9
    assert flat["q_b"] == "x" and flat["q_b_confidence"] == 0.8
    assert flat["q_c"] == 1.5 and flat["q_c_confidence"] == 0.7


def test_build_all_metrics_keys() -> None:
    tables = build_all_metrics(_enriched_df())
    assert set(tables) == {"nomes", "emails", "carros", "qualidade"}
    nomes = tables["nomes"]
    assert set(nomes.columns) == {"categoria", "valor", "n_leads", "pct"}


def test_score_distribution_totals() -> None:
    dist = score_distribution(_enriched_df())
    assert int(dist["n_leads"].sum()) == 2
    assert list(dist["score_bucket"]) == [0, 1, 2, 3, 4]


def test_mean_confidence() -> None:
    conf = mean_confidence(_enriched_df())
    assert "nome_genero" in set(conf["pergunta"])
    assert conf["confidence_media"].between(0, 1).all()


def test_cruzamentos() -> None:
    tables = metrics_cruzamentos(_enriched_df())
    assert "carro_marca_x_tier" in tables
    assert "qual_score_x_email_typo" in tables
