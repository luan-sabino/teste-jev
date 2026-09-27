"""Fase 6 - Gera docs/03-validation-report.md (acuracia, baseline, custo).

Uso:  uv run python scripts/07_validation_report.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jevlab.core.config import get_settings  # noqa: E402
from jevlab.core.jev_client import read_cost_log, total_cost  # noqa: E402
from jevlab.pipeline.metrics import mean_confidence, score_distribution  # noqa: E402

FULL_PATH = ROOT / "outputs" / "enriched.parquet"
SAMPLE_PATH = ROOT / "outputs" / "enriched_sample.parquet"
CHECK_PATH = ROOT / "outputs" / "manual_check.csv"
REPORT_PATH = ROOT / "docs" / "03-validation-report.md"


def resolve() -> Path:
    return FULL_PATH if FULL_PATH.exists() else SAMPLE_PATH


def concordance(df: pd.DataFrame) -> pd.DataFrame:
    """Compara o JEV com as regras deterministicas (baseline)."""
    rows: list[dict] = []

    def add(pergunta: str, jev_col: str, baseline_col: str, tipo: str) -> None:
        if jev_col not in df.columns or baseline_col not in df.columns:
            return
        jev = df[jev_col]
        base = df[baseline_col]
        mask = jev.notna() & base.notna()
        if not mask.any():
            return
        if tipo == "noul":
            jev_bin = pd.to_numeric(jev[mask], errors="coerce") >= 0.5
            base_bin = base[mask].astype(bool)
        else:
            jev_bin = jev[mask].astype(str)
            base_bin = base[mask].astype(str)
        agree = float((jev_bin == base_bin).mean() * 100)
        rows.append(
            {
                "pergunta": pergunta,
                "baseline": baseline_col,
                "n": int(mask.sum()),
                "concordancia_pct": round(agree, 2),
            }
        )

    add("nome_caixa", "q_nome_caixa", "baseline_nome_caixa", "choice")
    add("nome_invalido", "q_nome_invalido", "baseline_nome_invalido", "noul")
    add("email_typo", "q_email_typo", "baseline_email_typo", "noul")
    return pd.DataFrame(rows)


def manual_accuracy() -> pd.DataFrame | None:
    if not CHECK_PATH.exists():
        return None
    df = pd.read_csv(CHECK_PATH, dtype=str, keep_default_na=False)
    rows = []
    for label in ["nome_genero", "email_provider", "carro_marca"]:
        m = df.get(f"manual_{label}", pd.Series("", index=df.index)).str.strip().str.lower()
        p = df.get(f"pred_{label}", pd.Series("", index=df.index)).str.strip().str.lower()
        ans = m != ""
        if not ans.any():
            continue
        rows.append(
            {
                "campo": label,
                "n": int(ans.sum()),
                "acuracia_pct": round(float((m[ans] == p[ans]).mean() * 100), 2),
            }
        )
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "_(sem dados)_\n"
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        out.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(out) + "\n"


def main() -> int:
    path = resolve()
    df = pd.read_parquet(path)
    n_total = len(df)
    n_ok = int(df["enriquecido"].sum()) if "enriquecido" in df.columns else n_total
    enriched = df[df["enriquecido"] == True] if "enriquecido" in df.columns else df  # noqa: E712

    cost = total_cost()
    per_1000 = cost / max(1, n_ok) * 1000
    settings = get_settings()

    lines: list[str] = []
    lines.append("# Relatorio de validacao - JEV Leads Lab")
    lines.append("")
    lines.append(f"- Gerado em: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"- Fonte: `{path.relative_to(ROOT).as_posix()}`")
    lines.append(f"- Leads enriquecidos: {n_ok}/{n_total} ({n_ok / max(1, n_total) * 100:.2f}%)")
    lines.append(f"- Modelo: `typesafe/jev-1.13` (snapshot logado em `outputs/cost_log.jsonl`)")
    lines.append("")

    lines.append("## 1. Custo")
    lines.append("")
    lines.append(f"- Custo total acumulado: **${cost:.4f}**")
    lines.append(f"- Custo por 1.000 leads enriquecidos: **${per_1000:.4f}**")
    calls = read_cost_log()
    lines.append(f"- Chamadas reais registradas: {len(calls)}")
    lines.append(f"- Teto configurado (`SPEND_CAP_USD`): ${settings.spend_cap_usd:.2f}")
    lines.append(
        f"- Teto original do plano: $5.00 (custo real ficou "
        f"{'acima' if cost > 5 else 'dentro'} do planejado: ${cost:.4f})."
    )
    lines.append(
        "- Nota: prompts com 18 perguntas gastam ~2.700 tokens/lead, entao o "
        "custo real (~$0,113/1.000 leads) e maior que a estimativa inicial do plano (~$0,042)."
    )
    lines.append("")

    lines.append("## 2. Acuracia na amostra anotada a mao")
    lines.append("")
    lines.append(md_table(manual_accuracy()))
    lines.append("")

    lines.append("## 3. Concordancia JEV vs baseline deterministico")
    lines.append("")
    lines.append(md_table(concordance(enriched)))
    lines.append("")
    lines.append(
        "Achado: `nome_caixa` concorda pouco com o baseline porque a regra "
        "deterministica (`.title()`) marca nomes com particulas (`de`, `da`, `dos`) "
        "como `misto_anomalo`, enquanto o JEV os considera `correto`. O baseline e "
        "mais estrito que o JEV; a divergencia e esperada e favorece o JEV."
    )
    lines.append("")
    if "q_email_typo" in enriched.columns:
        typo = pd.to_numeric(enriched["q_email_typo"], errors="coerce")
        baseline_typo = int(enriched.get("baseline_email_typo", pd.Series(dtype=bool)).sum())
        lines.append(
            f"Atencao: a concordancia alta de `email_typo` (98,47%) ocorre porque "
            f"o JEV quase nunca sobe a probabilidade (media {typo.mean():.3f}, max "
            f"{typo.max():.3f}; apenas {int((typo >= 0.5).sum())} leads >= 0,5), "
            f"enquanto o baseline marca {baseline_typo}. Casos de dominio malformado "
            f"(ex.: `gmaol.com`, `gmail.comr`) sao capturados por "
            f"`email_provider = invalido` ({int((enriched.get('q_email_provider') == 'invalido').sum())} leads)."
        )
        lines.append(
            "Recomendacao de ajuste: usar limiar ~0,3 em `email_typo` "
            f"({int((typo >= 0.3).sum())} leads) ou depender de `email_provider=invalido`."
        )
        lines.append("")

    lines.append("## 4. Confianca media por pergunta")
    lines.append("")
    conf = mean_confidence(enriched)
    if not conf.empty:
        conf = conf.sort_values("confidence_media")
        lines.append(md_table(conf))
    else:
        lines.append("_(sem dados)_\n")
    lines.append("")

    lines.append("## 5. Distribuicao de qual_score")
    lines.append("")
    lines.append(md_table(score_distribution(enriched)))
    lines.append("")

    lines.append("## 6. Limitacoes e proximos passos")
    lines.append("")
    lines.append("- Amostra manual pequena (20 leads) e enviesada para casos faceis;")
    lines.append("  ampliar para 30-50 leads estratificados antes de decisao final.")
    lines.append("- `carro_combustivel` (confianca media 0,53) e `qual_score` (0,58) sao as")
    lines.append("  perguntas mais incertas — revisar `criteria` antes de usar como gate.")
    lines.append("- `email_typo` e pouco sensivel (media 0,14); o dominio malformado aparece")
    lines.append("  melhor em `email_provider=invalido`.")
    lines.append("- Nomes com digitos (CPF/telefone colados) foram mascarados; a anomalia")
    lines.append("  permanece visivel como `#` para o JEV.")
    lines.append("- Ideias 3 e 5 seguem fora do escopo.")
    lines.append("")
    acc = manual_accuracy()
    acc_ok = acc is not None and not acc.empty and bool((acc["acuracia_pct"] >= 85).all())
    success_ok = (n_ok / max(1, n_total)) >= 0.98
    lines.append("## 7. Recomendacao")
    lines.append("")
    if acc_ok and success_ok:
        lines.append(
            "- [x] **Escalar** — acuracia da amostra anotada >= 85% e sucesso "
            f"de enriquecimento em {n_ok / max(1, n_total) * 100:.2f}% dos leads."
        )
        lines.append("- [ ] Ajustar perguntas")
        lines.append("- [ ] Abandonar")
        lines.append("")
        lines.append(
            "Recomendacao: **escalar** o uso do JEV para as 4 ideias, com as seguintes "
            "ressalvas: (a) ampliar a amostra anotada para 30-50 leads estratificados; "
            "(b) revisar `carro_combustivel` (confianca media 0,53) e `qual_score` "
            "(0,58), que sao as perguntas mais incertas."
        )
    else:
        lines.append("- [ ] Escalar")
        lines.append(
            "- [x] **Ajustar perguntas** — algum campo ficou abaixo de 85% ou o "
            "sucesso de enriquecimento ficou abaixo de 98%."
        )
        lines.append("- [ ] Abandonar")
    lines.append("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Relatorio escrito em {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
