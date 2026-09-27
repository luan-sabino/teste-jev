"""Cache em disco por hash de (model, state, questions, versao do catalogo)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .config import get_settings


def cache_key(
    state: Any,
    questions: dict[str, Any],
    model: str,
    questions_version: str = "",
) -> str:
    """Hash estavel do payload. Mesmo state+questions+modelo => mesmo hash."""
    blob = json.dumps(
        {
            "model": model,
            "state": state,
            "questions": questions,
            "questions_version": questions_version,
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class DiskCache:
    """Cache JSON simples: um arquivo por chave em `directory`."""

    def __init__(self, directory: str | Path | None = None) -> None:
        self.directory = Path(directory) if directory is not None else get_settings().cache_dir
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, key: str, value: dict[str, Any]) -> Path:
        path = self._path(key)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(path)
        return path

    def has(self, key: str) -> bool:
        return self._path(key).exists()

    def count(self) -> int:
        return sum(1 for _ in self.directory.glob("*.json"))
