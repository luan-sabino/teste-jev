"""Wrapper para deploy na Streamlit Cloud.

Aponta para o dashboard oficial em src/jevlab/dashboard/app.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Adiciona src/ ao PYTHONPATH para permitir import de jevlab
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from jevlab.dashboard.app import main  # noqa: E402

if __name__ == "__main__":
    main()
