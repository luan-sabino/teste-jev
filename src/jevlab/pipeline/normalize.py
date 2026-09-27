"""Normalizacoes, flags deterministicas (baseline) e mascara de PII."""

from __future__ import annotations

import hashlib
import re
import unicodedata

import pandas as pd

from .load import is_blank

# ------------------------------------------------------------------ utilitarios
_DIGITS_RE = re.compile(r"\D")


def only_digits(value: object) -> str:
    return _DIGITS_RE.sub("", str(value or ""))


def strip_text(value: object) -> str:
    return str(value or "").strip()


def _ascii_fold(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


# ----------------------------------------------------------------------- CPF
def cpf_valido(cpf: object) -> bool:
    """Valida CPF pelo checksum (11 digitos, nao repetido)."""
    digits = only_digits(cpf)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    nums = [int(d) for d in digits]
    for size in (9, 10):
        total = sum(nums[i] * (size + 1 - i) for i in range(size))
        check = (total * 10) % 11
        if check == 10:
            check = 0
        if check != nums[size]:
            return False
    return True


# -------------------------------------------------------------------- telefone
def flag_tel_invalido(telefone: object) -> bool:
    """True quando vazio, curto/longo demais ou so com digito repetido."""
    digits = only_digits(telefone)
    if len(digits) < 10 or len(digits) > 11:
        return True
    return len(set(digits)) == 1


# ---------------------------------------------------------------------- e-mail
def normalize_email(email: object) -> str:
    return strip_text(email).lower().replace(" ", "")


_DOMAIN_TYPOS = ("gmial", "gmai.", "gmal", "hotmial", "homail", "outlok", "yaho.")


def flag_email_typo_regex(email: object, nome: object = "") -> bool:
    """Heuristica simples de typo (baseline deterministico)."""
    value = normalize_email(email)
    if not value or "@" not in value or value.count("@") != 1:
        return True
    local, _, domain = value.partition("@")
    if not local or "." not in domain:
        return True
    if any(typo in domain for typo in _DOMAIN_TYPOS):
        return True
    if re.search(r"(.)\1{2,}", local):  # 3+ chars repetidos
        return True
    if ".." in local or local.startswith(".") or local.endswith("."):
        return True
    # local-part sem nenhuma vogal (exceto quando tem digitos)
    if not re.search(r"[aeiou]", _ascii_fold(local)) and not any(c.isdigit() for c in local):
        return True
    return False


def email_domain(email: object) -> str:
    value = normalize_email(email)
    return value.partition("@")[2] if "@" in value else ""


# ------------------------------------------------------------------------- nome
def nome_caixa_rule(nome: object) -> str:
    """Classifica a capitalizacao do nome em Python puro (baseline)."""
    value = strip_text(nome)
    if not value:
        return "misto_anomalo"
    if value == value.upper():
        return "tudo_maiusculo"
    if value == value.lower():
        return "tudo_minusculo"
    if value == value.title():
        return "correto"
    return "misto_anomalo"


def flag_nome_invalido_regex(nome: object) -> bool:
    value = strip_text(nome)
    if len(value) < 3 or any(ch.isdigit() for ch in value):
        return True
    tokens = [_ascii_fold(t) for t in value.split() if t]
    placeholders = {"teste", "test", "asdf", "xxx", "aaa", "nao informado", "n/a", "cliente"}
    return any(t in placeholders for t in tokens)


# ------------------------------------------------------------------------ PII
def mask_digits(value: object) -> str:
    """Troca cada digito por '#' (preserva o sinal de anomalia sem a PII)."""
    return re.sub(r"\d", "#", str(value or ""))


def hash_value(value: object, size: int = 8) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:size]


def mask_cpf(cpf: object, mode: str = "digits3") -> str | None:
    digits = only_digits(cpf)
    if not digits:
        return None
    if mode == "hash":
        return f"h:{hash_value(digits)}"
    return f"{digits[:3]}******" if len(digits) >= 3 else "***"


def mask_telefone(telefone: object, mode: str = "ddd_last4") -> str | None:
    digits = only_digits(telefone)
    if not digits:
        return None
    if mode == "hash":
        return f"h:{hash_value(digits)}"
    ddd = digits[:2]
    last4 = digits[-4:]
    return f"({ddd}) ****-{last4}" if len(digits) >= 6 else "****"


def mask_email(email: object, keep_domain: bool = True) -> str | None:
    """Mascara o local-part preservando (por padrao) o dominio."""
    value = normalize_email(email)
    if not value or "@" not in value:
        return None
    local, _, domain = value.partition("@")
    masked_local = (local[0] + "***") if local else "***"
    return f"{masked_local}@{domain}" if keep_domain else masked_local


# ------------------------------------------------------------------ deduplicacao
def build_lead_key(cpf: object, email: object, telefone: object) -> str:
    """Chave de dedup por prioridade: CPF valido > e-mail > telefone."""
    if cpf_valido(cpf):
        return f"cpf:{only_digits(cpf)}"
    email_norm = normalize_email(email)
    if email_norm and "@" in email_norm:
        return f"email:{email_norm}"
    digits = only_digits(telefone)
    if digits:
        return f"phone:{digits}"
    return ""


def _column_or_blank(df: pd.DataFrame, name: str) -> pd.Series:
    if name in df.columns:
        return df[name]
    return pd.Series("", index=df.index, dtype=object)


def compute_lead_keys(df: pd.DataFrame) -> pd.Series:
    cpf_col = _column_or_blank(df, "CPF")
    email_col = _column_or_blank(df, "E-mail do contato")
    tel_col = _column_or_blank(df, "Telefone do contato")
    return pd.Series(
        (
            build_lead_key(cpf, email, tel)
            for cpf, email, tel in zip(cpf_col, email_col, tel_col)
        ),
        index=df.index,
    )


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplica por lead_key, guardando n_aparicoes e mantendo o registro mais completo."""
    out = df.copy()
    out["lead_key"] = compute_lead_keys(out)
    sem_chave = out["lead_key"].eq("")
    # registros sem chave nao devem colapsar entre si
    out.loc[sem_chave, "lead_key"] = [f"row:{i}" for i in out.index[sem_chave]]

    completeness = pd.Series(0, index=out.index)
    for col in out.columns:
        if col == "lead_key":
            continue
        completeness += out[col].map(lambda v: 0 if is_blank(v) else 1)
    out["_completeness"] = completeness

    counts = out["lead_key"].value_counts()
    out["n_aparicoes"] = out["lead_key"].map(counts).astype(int)

    out = (
        out.sort_values(["lead_key", "_completeness"], ascending=[True, False])
        .drop_duplicates("lead_key", keep="first")
        .drop(columns=["_completeness"])
        .reset_index(drop=True)
    )
    return out
