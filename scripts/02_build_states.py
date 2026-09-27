"""Fase 2 - dedup + PII + state + baseline -> outputs/leads_unique.parquet.

Uso:  uv run python scripts/02_build_states.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jevlab.core.config import CSV_PATH, get_settings  # noqa: E402
from jevlab.pipeline.load import load_raw_csv  # noqa: E402
from jevlab.pipeline.normalize import (  # noqa: E402
    deduplicate,
    mask_digits,
    mask_email,
    mask_telefone,
    only_digits,
    strip_text,
)
from jevlab.pipeline.state_builder import (  # noqa: E402
    build_states_dataframe,
    parse_date_iso,
    parse_km,
    state_is_masked,
)

OUT_PATH = ROOT / "outputs" / "leads_unique.parquet"


def main() -> int:
    settings = get_settings()
    print(f"Lendo {CSV_PATH.name} ...")
    raw = load_raw_csv(CSV_PATH)
    print(f"  linhas brutas: {len(raw)}")

    dedup = deduplicate(raw)
    print(f"  leads unicos (dedup): {len(dedup)}")

    states_df = build_states_dataframe(dedup, mask_pii=settings.mask_pii)
    print(f"  states montados: {len(states_df)} (MASK_PII={settings.mask_pii})")

    # Colunas de exibicao (PII mascarada se MASK_PII=true) - sem CPF.
    email_col = dedup["E-mail do contato"]
    tel_col = dedup["Telefone do contato"]
    display = pd.DataFrame(
        {
            "lead_key": dedup["lead_key"],
            "nome": dedup["Nome do contato"].map(
                lambda n: mask_digits(strip_text(n)) if settings.mask_pii else strip_text(n)
            ),
            "email_display": [
                mask_email(e) if settings.mask_pii else strip_text(e).lower()
                for e in email_col
            ],
            "telefone_display": [
                mask_telefone(t) if settings.mask_pii else only_digits(t)
                for t in tel_col
            ],
            "carro": dedup["Carro"].map(strip_text),
            "km": dedup["KM"].map(parse_km),
            "data_lead": dedup["Data Lead"].map(parse_date_iso),
            "n_aparicoes": dedup["n_aparicoes"].astype(int),
            "state_json": states_df["state_json"],
        }
    )
    baseline_cols = [c for c in states_df.columns if c.startswith("baseline_")]
    display = pd.concat([display, states_df[baseline_cols]], axis=1)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    display.to_parquet(OUT_PATH, index=False)
    print(f"  salvo em {OUT_PATH}")

    # Validacoes do checkpoint 2
    parsed_ok = all(isinstance(json.loads(s), dict) for s in display["state_json"].head(200))
    masked_ok = all(state_is_masked(s) for s in display["state_json"])
    print(f"  state_json parseavel (amostra): {parsed_ok}")
    print(f"  nenhum PII de 11 digitos no state: {masked_ok}")
    print(f"  distribuicao n_aparicoes: max={display['n_aparicoes'].max()} "
          f"soma={int(display['n_aparicoes'].sum())}")
    if not (parsed_ok and masked_ok):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
