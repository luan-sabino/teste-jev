#!/usr/bin/env bash
# Fase 5 - sobe o dashboard Streamlit (le parquet, nao chama a API).
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run streamlit run src/jevlab/dashboard/app.py "$@"
