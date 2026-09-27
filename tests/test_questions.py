"""Testes do catalogo de perguntas (questions.yaml)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jevlab.core.questions import (
    QuestionDef,
    get_catalog,
    get_questions,
    questions_version,
)

EXPECTED_QUESTIONS = {
    "nome_valido",
    "nome_genero",
    "nome_apelido",
    "nome_caixa",
    "nome_invalido",
    "email_provider",
    "email_typo",
    "email_bate_nome",
    "email_tipo",
    "carro_marca",
    "carro_carroceria",
    "carro_cambio",
    "carro_combustivel",
    "carro_tier",
    "carro_cor",
    "carro_coerente",
    "qual_bot",
    "qual_score",
}


def test_catalog_has_18_questions() -> None:
    catalog = get_catalog()
    assert len(catalog.questions) == 18
    assert set(catalog.question_names()) == EXPECTED_QUESTIONS
    assert catalog.version >= 1


def test_questions_payload_excludes_none() -> None:
    questions = get_questions()
    assert len(questions) == 18
    for qdef in questions.values():
        assert "type" in qdef and "instructions" in qdef
        assert None not in qdef.values()


def test_choice_requires_object_criteria() -> None:
    with pytest.raises(ValidationError):
        QuestionDef(type="choice", instructions="x", criteria=["a", "b"])


def test_score_requires_list_of_two() -> None:
    with pytest.raises(ValidationError):
        QuestionDef(type="score", instructions="x", criteria=["a"])
    ok = QuestionDef(type="score", instructions="x", criteria=["a", "b"])
    assert ok.type == "score"


def test_noul_criteria_optional() -> None:
    assert QuestionDef(type="noul", instructions="x").criteria is None


def test_questions_version_is_stable() -> None:
    assert questions_version() == questions_version()
    assert questions_version().startswith("v")
