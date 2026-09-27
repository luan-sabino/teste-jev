"""Configuracao central do laboratorio (env + defaults)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# src/jevlab/core/config.py -> core, jevlab, src, <repo raiz>
REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_MODEL = "typesafe/jev-1.13"
# Endpoint System One (Decisions API) do OpenRouter. Ver docs/02-decisions.md.
DEFAULT_BASE_URL = "https://openrouter.ai/api"
DEFAULT_DECISIONS_PATH = "/alpha/decisions"

CSV_PATH = REPO_ROOT / "data" / "raw" / "Report Update - Salesforce - N8N Beta Prod - RD Api.csv"


class Settings(BaseSettings):
    """Configuracao carregada de variaveis de ambiente / arquivo .env."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    openrouter_api_key: str = ""
    jev_model: str = DEFAULT_MODEL
    openrouter_base_url: str = DEFAULT_BASE_URL
    decisions_path: str = DEFAULT_DECISIONS_PATH

    mask_pii: bool = True
    max_concurrency: int = 8
    spend_cap_usd: float = 5.0
    request_timeout_s: float = 120.0

    @property
    def decisions_url(self) -> str:
        return self.openrouter_base_url.rstrip("/") + self.decisions_path

    @property
    def outputs_dir(self) -> Path:
        return REPO_ROOT / "outputs"

    @property
    def cache_dir(self) -> Path:
        return self.outputs_dir / "cache"

    @property
    def cost_log_path(self) -> Path:
        return self.outputs_dir / "cost_log.jsonl"

    def require_api_key(self) -> str:
        if not self.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY nao configurada. Copie .env.example para .env e preencha."
            )
        return self.openrouter_api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
