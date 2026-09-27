"""Carrega e valida o catalogo de perguntas do JEV (questions.yaml)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

QuestionType = Literal["noul", "choice", "score"]

DEFAULT_QUESTIONS_PATH = Path(__file__).with_name("questions.yaml")


class QuestionDef(BaseModel):
    """Definicao de uma pergunta tipada enviada ao JEV."""

    type: QuestionType
    instructions: Any = Field(..., description="String ou estrutura com a pergunta.")
    criteria: Any | None = None

    @model_validator(mode="after")
    def _validate_criteria(self) -> "QuestionDef":
        if self.type == "choice":
            if not isinstance(self.criteria, dict) or not self.criteria:
                raise ValueError("choice exige `criteria` como objeto nao vazio")
        elif self.type == "score":
            if not isinstance(self.criteria, list) or len(self.criteria) < 2:
                raise ValueError("score exige `criteria` como array com >= 2 itens")
        elif self.type == "noul":
            if self.criteria is not None and not isinstance(self.criteria, dict):
                raise ValueError("criteria de noul, quando presente, deve ser objeto")
        return self


class QuestionsCatalog(BaseModel):
    version: int = 1
    language: str = "pt-BR"
    description: str = ""
    questions: dict[str, QuestionDef]

    def question_names(self) -> list[str]:
        return list(self.questions)


def load_catalog(path: str | Path | None = None) -> QuestionsCatalog:
    """Le e valida o questions.yaml. `path=None` usa o arquivo do pacote."""
    qpath = Path(path) if path is not None else DEFAULT_QUESTIONS_PATH
    raw = yaml.safe_load(qpath.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "questions" not in raw:
        raise ValueError(f"questions.yaml invalido: {qpath}")
    return QuestionsCatalog.model_validate(raw)


@lru_cache(maxsize=4)
def _cached_catalog(path: str | None) -> QuestionsCatalog:
    return load_catalog(path)


def get_catalog(path: str | Path | None = None) -> QuestionsCatalog:
    return _cached_catalog(str(path) if path is not None else None)


def get_questions(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Retorna o dict `questions` pronto para o payload (sem wrapper pydantic)."""
    catalog = get_catalog(path)
    return {
        name: qdef.model_dump(exclude_none=True)
        for name, qdef in catalog.questions.items()
    }


def questions_version(path: str | Path | None = None) -> str:
    catalog = get_catalog(path)
    return f"v{catalog.version}-{catalog.language}"
