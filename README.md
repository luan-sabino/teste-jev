# JEV Leads Lab

Laboratorio para rodar o **JEV** (TypeSafe / System One) via **OpenRouter** sobre o
CSV de leads da Unidas Livre e visualizar os resultados num dashboard Streamlit.

Escopo funcional: **Ideias 1 (Nomes) + 2 (E-mails) + 4 (Carros) + 6 (Fraude/Qualidade)**.

O plano completo esta em [`PLANO_JEV_LEADS.md`](PLANO_JEV_LEADS.md) e o guia do
modelo em [`jev-typesafe.md`](jev-typesafe.md).

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Chave do OpenRouter (`OPENROUTER_API_KEY`)

## Quickstart (5 comandos)

```bash
# 1. ambiente + dependencias
uv sync

# 2. configuracao
cp .env.example .env          # edite e preencha OPENROUTER_API_KEY

# 3. perfil dos dados (Fase 0)
uv run python scripts/01_inspect.py

# 4. dedup + states (Fase 2)
uv run python scripts/02_build_states.py

# 5. smoke test do JEV (Fase 1)
uv run python scripts/00_smoke_jev.py
```

## Estrutura

```
src/jevlab/
  core/       # config, cliente JEV, questions.yaml, cache
  pipeline/   # load, normalize, state_builder, enrich, metrics
  dashboard/  # app.py (Streamlit)
scripts/      # 00_smoke_jev .. 05_dashboard
docs/         # perfil de dados, decisoes, relatorio de validacao
data/raw/     # CSV original (gitignored)
outputs/      # parquet, metricas, cache, fixtures
tests/        # testes offline (sem rede)
```

> Nota: adotamos a "variante simples" do plano (um unico `pyproject.toml` +
> pacote `src/jevlab/` com subpastas), em vez do workspace com 3 pacotes.

## Fases

| Fase | Comando | Entregavel |
| --- | --- | --- |
| 0 | `python scripts/01_inspect.py` | `docs/01-data-profile.md` |
| 1 | `python scripts/00_smoke_jev.py` | cliente + fixture + testes |
| 2 | `python scripts/02_build_states.py` | `outputs/leads_unique.parquet` |
| 3 | `python scripts/03_enrich.py --limit 300` | `outputs/enriched_sample.parquet` |
| 3 | `python scripts/06_manual_check.py --generate 20` | `outputs/manual_check.csv` |
| 4 | `python scripts/03_enrich.py --all` | `outputs/enriched.parquet` |
| 4 | `python scripts/04_metrics.py` | `outputs/metrics/*.parquet` |
| 5 | `python scripts/05_dashboard.sh` | dashboard Streamlit |
| 6 | `python scripts/07_validation_report.py` | `docs/03-validation-report.md` |

### Desenvolvimento offline (sem gastar token)

```bash
uv run python scripts/00_smoke_jev.py --fixture      # imprime o fixture
uv run python scripts/03_enrich.py --limit 50 --mock # enriquece com dados falsos
```

## Testes

```bash
uv run pytest
```

Os testes de cliente usam `outputs/fixtures/jev_response.json` e nao acessam a rede.

## Notas de ambiente

- Windows sem `make`: use os comandos `uv run` direto (a `Makefile` e conveniencia).
- `MASK_PII=true` por padrao: nada de CPF/telefone/e-mail cru no `state`.
  Detalhes em [`docs/02-decisions.md`](docs/02-decisions.md).
- O perfil dos dados gerado esta em [`docs/01-data-profile.md`](docs/01-data-profile.md).

## Endpoint usado

`POST https://openrouter.ai/api/alpha/decisions` (System One / Decisions API),
payload `{ "model", "state", "questions" }`. O endpoint e configuravel via
`OPENROUTER_BASE_URL` / `DECISIONS_PATH` no `.env`.
