"""Testes de PII, state builder, flags e deduplicacao."""

from __future__ import annotations

import json

import pandas as pd

from jevlab.pipeline.normalize import (
    build_lead_key,
    cpf_valido,
    deduplicate,
    flag_email_typo_regex,
    flag_tel_invalido,
    mask_email,
    mask_telefone,
    nome_caixa_rule,
)
from jevlab.pipeline.state_builder import (
    build_state,
    build_states_dataframe,
    parse_date_iso,
    parse_km,
    state_is_masked,
)


def _row(**overrides: object) -> dict:
    base = {
        "Nome do contato": "João Marcelo Romano",
        "E-mail do contato": "joaomarceloromano@gmail.com",
        "Telefone do contato": "11983147562",
        "CPF": "11144477735",
        "Carro": "Volkswagen Tera Comfort 1.0 TSI AT Cinza Platinum",
        "KM": "1000",
        "Vigência": "",
        "Data Lead": "01/01/2026",
    }
    base.update(overrides)
    return base


def test_build_state_canonical_shape() -> None:
    state = build_state(_row())
    assert set(state) == {
        "nome",
        "email",
        "email_dominio",
        "telefone",
        "carro",
        "km",
        "vigencia",
        "data_lead",
    }
    assert state["km"] == 1000
    assert state["data_lead"] == "2026-01-01"
    assert state["vigencia"] is None


def test_build_state_masks_pii() -> None:
    state = build_state(_row(), mask_pii=True)
    assert state["email"] == "j***@gmail.com"
    assert state["email_dominio"] == "gmail.com"
    assert state["telefone"] == "(11) ****-7562"
    assert "11144477735" not in json.dumps(state)
    assert state_is_masked(json.dumps(state))


def test_build_state_masks_digits_embedded_in_name() -> None:
    row = _row(**{"Nome do contato": "AUDENISCE BORGE PEREIRA 17865354835"})
    state = build_state(row, mask_pii=True)
    assert state["nome"] == "AUDENISCE BORGE PEREIRA ###########"
    assert state_is_masked(json.dumps(state))


def test_build_state_without_mask_keeps_email_and_phone() -> None:
    state = build_state(_row(), mask_pii=False)
    assert state["email"] == "joaomarceloromano@gmail.com"
    assert state["telefone"] == "11983147562"


def test_mask_helpers() -> None:
    assert mask_email("joao@gmail.com") == "j***@gmail.com"
    assert mask_telefone("11983147562") == "(11) ****-7562"
    assert mask_telefone("") is None
    assert mask_email("") is None


def test_cpf_valido_checksum() -> None:
    assert cpf_valido("11144477735")
    assert not cpf_valido("11144477736")
    assert not cpf_valido("11111111111")
    assert not cpf_valido("123")


def test_flags_deterministicos() -> None:
    assert flag_tel_invalido("11111111111")
    assert flag_tel_invalido("123")
    assert not flag_tel_invalido("11983147562")
    assert flag_email_typo_regex("joao@gmial.com")
    assert not flag_email_typo_regex("joao@gmail.com")
    assert nome_caixa_rule("JOAO MARcelo") == "misto_anomalo"
    assert nome_caixa_rule("JOAO MARcelo".upper()) == "tudo_maiusculo"


def test_parse_helpers() -> None:
    assert parse_km("2.500") == 2500
    assert parse_km("") is None
    assert parse_date_iso("01/01/2026") == "2026-01-01"
    assert parse_date_iso("") is None
    assert parse_date_iso("31/02/2026") is None


def test_build_lead_key_priority() -> None:
    assert build_lead_key("11144477735", "a@b.com", "1199").startswith("cpf:")
    assert build_lead_key("123", "A@B.com", "1199").startswith("email:")
    assert build_lead_key("123", "", "11999999999").startswith("phone:")


def test_deduplicate_counts_appearances() -> None:
    df = pd.DataFrame(
        [
            {"CPF": "11144477735", "E-mail do contato": "a@b.com", "Telefone do contato": "11", "Nome do contato": "A"},
            {"CPF": "11144477735", "E-mail do contato": "outro@b.com", "Telefone do contato": "22", "Nome do contato": "A"},
            {"CPF": "", "E-mail do contato": "c@b.com", "Telefone do contato": "33", "Nome do contato": "C"},
        ]
    )
    dedup = deduplicate(df)
    assert len(dedup) == 2
    assert dedup["n_aparicoes"].max() == 2


def test_states_dataframe_has_no_full_pii() -> None:
    df = pd.DataFrame([_row()])
    out = build_states_dataframe(df, mask_pii=True)
    assert "state_json" in out.columns
    state = json.loads(out.loc[0, "state_json"])
    assert state["telefone"] == "(11) ****-7562"
    assert "11144477735" not in out.loc[0, "state_json"]
    assert bool(out.loc[0, "baseline_cpf_valido"]) is True
