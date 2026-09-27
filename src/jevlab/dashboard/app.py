"""Fase 5 - Dashboard Streamlit. Le parquet, nunca chama a API.

Rodar:  uv run streamlit run src/jevlab/dashboard/app.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUTS = REPO_ROOT / "outputs"

QUAL_SCORE_LABELS = {
    0: "0 inutilizavel",
    1: "1 ruim",
    2: "2 regular",
    3: "3 bom",
    4: "4 excelente",
}

DISPLAY_COLUMNS = [
    "nome",
    "email_display",
    "telefone_display",
    "carro",
    "km",
    "n_aparicoes",
    "q_nome_genero",
    "q_email_provider",
    "q_email_typo",
    "q_carro_marca",
    "q_carro_tier",
    "q_qual_bot",
    "q_qual_score",
]


def resolve_data_path() -> Path | None:
    env = os.environ.get("JEVLAB_DATA")
    if env and Path(env).exists():
        return Path(env)
    full = OUTPUTS / "enriched.parquet"
    if full.exists():
        return full
    sample = OUTPUTS / "enriched_sample.parquet"
    if sample.exists():
        return sample
    return None


@st.cache_data(show_spinner=False)
def load_data(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False)
def load_metrics() -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    metrics_dir = OUTPUTS / "metrics"
    if metrics_dir.exists():
        for path in sorted(metrics_dir.glob("*.parquet")):
            out[path.stem] = pd.read_parquet(path)
    return out


def has_col(df: pd.DataFrame, col: str) -> bool:
    return col in df.columns and df[col].notna().any()


def kpi(label: str, value: str) -> None:
    st.metric(label, value)


def bar(df: pd.DataFrame, col: str, title: str, top: int | None = None):
    if not has_col(df, col):
        st.info(f"Coluna `{col}` indisponivel (dados nao enriquecidos).")
        return
    counts = df[col].fillna("(sem resposta)").value_counts()
    if top:
        counts = counts.head(top)
    fig = px.bar(
        x=counts.index.astype(str),
        y=counts.values,
        labels={"x": col, "y": "leads"},
        title=title,
    )
    fig.update_layout(showlegend=False, height=340)
    st.plotly_chart(fig, use_container_width=True)


def noul_bar(df: pd.DataFrame, col: str, title: str, limiar: float = 0.5):
    if not has_col(df, col):
        st.info(f"Coluna `{col}` indisponivel.")
        return
    values = pd.to_numeric(df[col], errors="coerce").dropna()
    pos = int((values >= limiar).sum())
    neg = int((values < limiar).sum())
    fig = px.bar(
        x=["positivo", "negativo"],
        y=[pos, neg],
        labels={"x": col, "y": "leads"},
        title=f"{title} (limiar {limiar:.2f})",
    )
    fig.update_layout(showlegend=False, height=340)
    st.plotly_chart(fig, use_container_width=True)


def crosstab_heatmap(df: pd.DataFrame, row: str, col: str, title: str):
    if not (has_col(df, row) and has_col(df, col)):
        st.info(f"Cruzamento `{row}` x `{col}` indisponivel.")
        return
    work = df[[row, col]].dropna()
    if row == "q_qual_score":
        work[row] = pd.to_numeric(work[row], errors="coerce").round().clip(0, 4)
    elif col == "q_qual_score":
        work[col] = pd.to_numeric(work[col], errors="coerce").round().clip(0, 4)
    table = pd.crosstab(work[row], work[col])
    fig = px.imshow(table, text_auto=True, title=title, aspect="auto")
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)


def drilldown(df: pd.DataFrame) -> None:
    cols = [c for c in DISPLAY_COLUMNS if c in df.columns]
    st.dataframe(df[cols].head(500), use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="JEV Leads Lab", layout="wide")
    st.title("JEV Leads Lab - enriquecimento de leads")

    path = resolve_data_path()
    if path is None:
        st.warning(
            "Nenhum `enriched.parquet`/`enriched_sample.parquet` encontrado em outputs/. "
            "Rode o enriquecimento (scripts/03_enrich.py) primeiro."
        )
        return

    df = load_data(str(path))
    st.caption(f"Fonte: `{path.relative_to(REPO_ROOT)}` - {len(df)} leads")

    # ------------------------------------------------------------- filtros
    with st.sidebar:
        st.header("Filtros")
        filtered = df
        if has_col(df, "q_carro_marca"):
            marcas = sorted(df["q_carro_marca"].dropna().unique())
            sel = st.multiselect("Marca", marcas, default=[])
            if sel:
                filtered = filtered[filtered["q_carro_marca"].isin(sel)]
        if has_col(df, "q_carro_carroceria"):
            tipos = sorted(df["q_carro_carroceria"].dropna().unique())
            sel_t = st.multiselect("Carroceria", tipos, default=[])
            if sel_t:
                filtered = filtered[filtered["q_carro_carroceria"].isin(sel_t)]
        if has_col(df, "q_qual_score"):
            score = pd.to_numeric(df["q_qual_score"], errors="coerce")
            lo, hi = st.slider("Faixa de qual_score", 0.0, 4.0, (0.0, 4.0), 0.1)
            filtered = filtered[score.between(lo, hi).fillna(False)]
        if has_col(df, "q_qual_bot"):
            cap = st.slider("qual_bot maximo (prob. de bot)", 0.0, 1.0, 1.0, 0.05)
            bot = pd.to_numeric(filtered["q_qual_bot"], errors="coerce")
            filtered = filtered[bot <= cap]

    tabs = st.tabs(["Visao Geral", "Nomes", "E-mails", "Carros", "Qualidade/Risco"])

    with tabs[0]:
        total = len(filtered)
        typo = (
            (pd.to_numeric(filtered["q_email_typo"], errors="coerce") >= 0.5).mean() * 100
            if has_col(filtered, "q_email_typo")
            else 0
        )
        bot = (
            (pd.to_numeric(filtered["q_qual_bot"], errors="coerce") >= 0.5).mean() * 100
            if has_col(filtered, "q_qual_bot")
            else 0
        )
        score_cols = st.columns(4)
        with score_cols[0]:
            kpi("Leads", f"{total:,}")
        with score_cols[1]:
            kpi("% e-mail typo", f"{typo:.1f}%")
        with score_cols[2]:
            kpi("% possivel bot", f"{bot:.1f}%")
        with score_cols[3]:
            mean_score = (
                pd.to_numeric(filtered["q_qual_score"], errors="coerce").mean()
                if has_col(filtered, "q_qual_score")
                else float("nan")
            )
            kpi("qual_score medio", f"{mean_score:.2f}")
        c1, c2 = st.columns(2)
        with c1:
            bar(filtered, "q_email_provider", "Provedores de e-mail")
        with c2:
            dist = filtered.get("q_qual_score")
            if dist is not None:
                buckets = pd.to_numeric(dist, errors="coerce").round().clip(0, 4)
                counts = buckets.value_counts().reindex([0, 1, 2, 3, 4], fill_value=0)
                fig = px.bar(
                    x=[QUAL_SCORE_LABELS[i] for i in counts.index],
                    y=counts.values,
                    labels={"x": "qual_score", "y": "leads"},
                    title="Distribuicao de qual_score",
                )
                fig.update_layout(showlegend=False, height=340)
                st.plotly_chart(fig, use_container_width=True)
        drilldown(filtered)

    with tabs[1]:
        c1, c2 = st.columns(2)
        with c1:
            bar(filtered, "q_nome_genero", "Genero inferido")
        with c2:
            bar(filtered, "q_nome_caixa", "Capitalizacao do nome")
        c3, c4, c5 = st.columns(3)
        with c3:
            noul_bar(filtered, "q_nome_valido", "Nome valido")
        with c4:
            noul_bar(filtered, "q_nome_apelido", "Parece apelido")
        with c5:
            noul_bar(filtered, "q_nome_invalido", "Nome invalido")
        drilldown(filtered)

    with tabs[2]:
        c1, c2 = st.columns(2)
        with c1:
            bar(filtered, "q_email_provider", "Provedor")
        with c2:
            bar(filtered, "q_email_tipo", "Tipo (pessoal/corporativo)")
        c3, c4 = st.columns(2)
        with c3:
            noul_bar(filtered, "q_email_typo", "Possivel erro de digitacao")
        with c4:
            noul_bar(filtered, "q_email_bate_nome", "Bate com o nome")
        drilldown(filtered)

    with tabs[3]:
        c1, c2 = st.columns(2)
        with c1:
            bar(filtered, "q_carro_marca", "Marca")
        with c2:
            bar(filtered, "q_carro_carroceria", "Carroceria")
        c3, c4 = st.columns(2)
        with c3:
            bar(filtered, "q_carro_cambio", "Cambio")
        with c4:
            bar(filtered, "q_carro_combustivel", "Combustivel")
        c5, c6 = st.columns(2)
        with c5:
            bar(filtered, "q_carro_cor", "Cor")
        with c6:
            noul_bar(filtered, "q_carro_coerente", "Modelo coerente com a marca")
        if has_col(filtered, "q_carro_tier"):
            tier = pd.to_numeric(filtered["q_carro_tier"], errors="coerce").round().clip(0, 2)
            counts = tier.value_counts().reindex([0, 1, 2], fill_value=0)
            fig = px.bar(
                x=["entrada", "intermediario", "premium"],
                y=counts.values,
                labels={"x": "tier", "y": "leads"},
                title="Tier (posicionamento de valor)",
            )
            fig.update_layout(showlegend=False, height=340)
            st.plotly_chart(fig, use_container_width=True)
        drilldown(filtered)

    with tabs[4]:
        c1, c2 = st.columns(2)
        with c1:
            noul_bar(filtered, "q_qual_bot", "Possivel bot/teste")
        with c2:
            conf = load_metrics().get("confidence")
            if conf is not None and not conf.empty:
                fig = px.bar(
                    conf,
                    x="pergunta",
                    y="confidence_media",
                    title="Confianca media por pergunta",
                )
                fig.update_layout(height=340)
                st.plotly_chart(fig, use_container_width=True)
        crosstab_heatmap(
            filtered, "q_carro_marca", "q_qual_score",
            "qual_score por marca (bucket)",
        )
        crosstab_heatmap(
            filtered, "q_nome_genero", "q_carro_carroceria",
            "Carroceria por genero",
        )
        drilldown(filtered)


if __name__ == "__main__":
    main()
