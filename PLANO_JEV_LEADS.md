# Plano de Desenvolvimento — JEV Leads Lab

> Projeto-laboratório, simples e monorepo, para rodar o **JEV** (TypeSafe / System One) via **OpenRouter** sobre o CSV de leads da Unidas Livre e exibir os resultados em um **dashboard**.
> Escopo funcional: **Ideias 1 (Nomes) + 2 (E-mails) + 4 (Carros) + 6 (Fraude/Qualidade)**.

---

## 0. Como usar este documento (retomada sem contexto)

Este plano foi escrito para ser **auto-suficiente**. Se você parar no meio de uma fase e voltar depois (ou outra pessoa assumir), siga esta rotina:

1. Leia a seção **1. Contexto e decisões fixas** — ela contém tudo que não muda.
2. Vá para a fase em andamento na seção **5. Fases**.
3. Cada fase tem: **Objetivo → Entregáveis → Tarefas → Checkpoint (critérios de aprovação) → Como validar**.
4. **Só avance de fase quando todos os itens do checkpoint estiverem marcados.** O checkpoint é o contrato entre fases.
5. Nunca dependa de memória de conversa: tudo relevante está em arquivos versionados no repo (`README.md`, `docs/`, `questions.yaml`, `outputs/`).

Regra de ouro: **cada checkpoint gera um artefato verificável** (arquivo, tabela ou comando que reproduz o resultado).

---

## 1. Contexto e decisões fixas

### 1.1 O que é o JEV e como consumir (OpenRouter)

- O JEV é um **modelo de decisão** (System One) da TypeSafe. Ele **não gera texto**: recebe um `state` (texto/objeto/array) e **perguntas tipadas**, e devolve respostas tipadas com probabilidades e confiança.
- **NÃO usar** `/chat/completions`. O JEV é servido pelo endpoint **System One** do OpenRouter:

```
POST https://openrouter.ai/api/v1/systemone
Authorization: Bearer $OPENROUTER_API_KEY
Content-Type: application/json
```

- **Request:** `{ "model": "typesafe/jev-1.13", "state": <string|object|array>, "questions": { ... } }`
- **Response:** `{ "id", "provider", "model", "answers": {...}, "usage": { "input_tokens", "output_tokens", "cost" } }`
- **Model ID:** fixar `typesafe/jev-1.13` (não usar alias) para que limiares fiquem estáveis. O alias é `~typesafe/jev-latest`.
- Pode-se também usar o SDK Python `typesafe_sdk` apontando `TYPESAFE_BASE_URL=https://openrouter.ai/api` e `TYPESAFE_API_KEY=<chave OpenRouter>`. **Decisão padrão do projeto: usar `httpx` direto no endpoint System One** (menos dependência, controle total do payload). O SDK fica como fallback documentado.

### 1.2 Tipos de pergunta do JEV

| Tipo | Uso | Retorno |
| --- | --- | --- |
| `noul` | Sim/não calibrado | `{ "type": "noul", "noul": 0.0–1.0 }` |
| `choice` | Escolher 1 entre N categorias (`criteria` obrigatório, objeto) | `{ "choice", "probabilities", "confidence" }` |
| `score` | Escala ordinal (`criteria` obrigatório, array ≥ 2, ordenado) | `{ "score", "legend", "probabilities", "confidence" }` |

### 1.3 Custo e limites (base para o orçamento de teste)

- Preço: **$0,042 por 1M tokens de input**; **output gratuito**.
- Estimativa do projeto: ~1.000 tokens/lead (state + definições de pergunta).
  - Amostra de 500 leads ≈ 0,5M tokens ≈ **~$0,02**.
  - Base completa (~50k leads únicos) ≈ 50M tokens ≈ **~$2,10**.
- Toda resposta traz `usage.cost` → somar e logar. Definir **teto de gasto** por fase (ver 5.4).

### 1.4 Dados de entrada (fatos já verificados)

Arquivo: `data/raw/Report Update - Salesforce - N8N Beta Prod - RD Api.csv` — **60.760 linhas, 17 colunas**.

Colunas: `Nome da Oportunidade, Nome da Organização, Nome do contato, Telefone do contato, E-mail do contato, Fonte da negociação, Campanha, Segmento do cliente, Responsável, Etapa, CPF, data Nascimento, cod mob, Data Lead, Carro, KM, Vigência`.

Fatos que guiam o design:

- **Colunas constantes (ignorar no enriquecimento):** `Nome da Organização`, `Fonte da negociação`, `Campanha`, `Segmento do cliente`, `Responsável`, `Etapa` (1 único valor cada).
- **Variáveis úteis:** nome, e-mail, telefone, CPF, `Carro`, `KM`, `Vigência`, datas, `cod mob`.
- **~50.087 pessoas únicas** para 60.760 linhas (repetição até 19x) → **deduplicar antes de enriquecer**.
- **Qualidade (medida):** 17.458 CPFs fora de 11 dígitos; 9.507 CPFs repetidos; 18 telefones só com dígito repetido; 73 e-mails padrão suspeito; 7.694 nomes em MAIÚSCULA; 1.472 em minúscula; 32 nomes com dígitos; `data Nascimento` vazia em 60.412.
- **Encoding:** UTF-8 com BOM (usar `utf-8-sig`).

### 1.5 Privacidade / LGPD (decisão obrigatória antes da Fase 2)

- O CSV contém **dados pessoais** (CPF, telefone, e-mail, nascimento). Mesmo com ZDR, o envio de PII crua a um terceiro é decisão de compliance.
- **Decisão padrão:** **mascarar** antes de montar o `state`:
  - CPF: enviar apenas os **3 primeiros dígitos** ou hash (ex.: `sha256[:8]`).
  - Telefone: enviar só **DDD + 4 últimos** ou hash.
  - E-mail: enviar **domínio** sempre; o local-part entra mascarado (`j***@gmail.com`) **ou** cru — configurável por flag `MASK_PII=true|false`.
- O objetivo é que o JEV avalie **texto/semântica** (nome, carro, e-mail) e não seja dependente de PII completa.

---

## 2. Escopo

### 2.1 Dentro do escopo

- ETL simples do CSV (dedup + montagem do `state`).
- Cliente JEV via OpenRouter com cache, retry e contabilização de custo.
- Enriquecimento das 4 ideias (seções 3.1–3.4), uma chamada por lead com fan-out de perguntas.
- Métricas agregadas.
- Dashboard Streamlit com 5 visões (Visão Geral, Nomes, E-mails, Carros, Qualidade/Risco).
- Testes dos builders e do parser de resposta; smoke test do cliente.

### 2.2 Fora do escopo

- Autenticação/usuários, deploy em nuvem, banco de dados, fila.
- Extração de campos por LLM (o JEV classifica/pontua, não extrai).
- Validação determinística “de verdade” de CPF/data (isso fica em Python puro e serve só de **baseline comparativo**).
- Tratamento de imagem/áudio/vídeo.

---

## 3. As 4 ideias → catálogo de perguntas JEV

> Este é o **contrato de enriquecimento**. Implementar em `packages/core/.../questions.yaml` e carregar via `pydantic`. Mudanças aqui exigem bump de versão do cache.

### 3.1 Ideia 1 — Nomes (`nome_*`)

| Chave | Tipo | Instructions (resumo) | Criteria |
| --- | --- | --- | --- |
| `nome_valido` | noul | É um nome plausível de pessoa física? | true/false |
| `nome_genero` | choice | Gênero provável pelo primeiro nome | `masculino`, `feminino`, `indeterminado` |
| `nome_apelido` | noul | Parece apelido/incompleto? | true/false |
| `nome_caixa` | choice | Estado de caixa do nome | `correto`, `tudo_maiusculo`, `tudo_minusculo`, `misto_anomalo` |
| `nome_invalido` | noul | Tem sinais de teste/placeholder? | true/false |

### 3.2 Ideia 2 — E-mails (`email_*`)

| Chave | Tipo | Instructions | Criteria |
| --- | --- | --- | --- |
| `email_provider` | choice | Provedor do e-mail | `gmail`, `outlook_hotmail`, `yahoo`, `corporativo`, `isp`, `descartavel`, `invalido` |
| `email_typo` | noul | Parece erro de digitação? | true/false |
| `email_bate_nome` | noul | Local-part é compatível com o nome? | true/false |
| `email_tipo` | choice | Pessoal vs corporativo | `pessoal`, `corporativo`, `indeterminado` |

### 3.3 Ideia 4 — Carros (`carro_*`)

| Chave | Tipo | Instructions | Criteria |
| --- | --- | --- | --- |
| `carro_marca` | choice | Marca do veículo | `fiat`, `volkswagen`, `renault`, `chevrolet`, `toyota`, `hyundai`, `jeep`, `outra` |
| `carro_carroceria` | choice | Tipo de carroceria | `hatch`, `sedan`, `suv`, `picape`, `outro` |
| `carro_cambio` | choice | Transmissão | `manual`, `automatico`, `indeterminado` |
| `carro_combustivel` | choice | Combustível | `flex`, `gasolina`, `diesel`, `eletrico`, `hibrido`, `indeterminado` |
| `carro_tier` | score | Posicionamento de valor | `entrada`, `intermediario`, `premium` |
| `carro_cor` | choice | Cor normalizada | `branco`, `preto`, `prata`, `cinza`, `azul`, `vermelho`, `outra` |
| `carro_coerente` | noul | Modelo coerente com a marca inferida? | true/false |

### 3.4 Ideia 6 — Fraude / Qualidade (`qual_*`)

| Chave | Tipo | Instructions | Criteria |
| --- | --- | --- | --- |
| `qual_bot` | noul | Parece submissão de teste/bot? | true/false |
| `qual_score` | score | Nota geral de qualidade do registro | `0=inutilizavel`, `1=ruim`, `2=regular`, `3=bom`, `4=excelente` |

> Nota: `qual_score` é `score` com 5 critérios; a probabilidade ponderada pode vir fracionária (ex.: 2.4) — tratar como contínuo no dashboard.

### 3.5 Montagem do `state` (formato canônico)

Enviar **um objeto** por lead (aproveita o fan-out: todas as perguntas veem o mesmo `state`):

```json
{
  "nome": "João Marcelo Romano",
  "email": "joaomarceloromano@gmail.com",
  "email_dominio": "gmail.com",
  "telefone": "***0480",
  "carro": "Volkswagen Tera Comfort 1.0 TSI AT Cinza Platinum",
  "km": 1000,
  "vigencia": null,
  "data_lead": "2026-01-01"
}
```

---

## 4. Arquitetura do monorepo (simples)

```
jev-leads-lab/
├── README.md                     # como rodar tudo (fonte da verdade)
├── PLANO_JEV_LEADS.md            # este documento
├── pyproject.toml                # workspace uv (raiz)
├── .env.example                  # OPENROUTER_API_KEY, JEV_MODEL, MASK_PII
├── Makefile                      # atalhos: make inspect / sample / review / all / dash
├── docs/
│   ├── 01-data-profile.md        # saída da Fase 0
│   ├── 02-decisions.md           # decisões (PII, modelo, limiares)
│   └── 03-validation-report.md   # saída da Fase 6
├── data/
│   ├── raw/                      # CSV original (gitignore)
│   └── interim/                  # parquet intermediário (gitignore)
├── packages/
│   ├── core/                     # cliente JEV, schemas, questions.yaml, cache
│   │   ├── pyproject.toml
│   │   └── src/jevlab_core/
│   │       ├── config.py         # env + settings (pydantic-settings)
│   │       ├── jev_client.py     # POST systemone, retry, custo
│   │       ├── questions.py      # carrega/valida questions.yaml
│   │       ├── cache.py          # cache em disco por hash
│   │       └── questions.yaml
│   ├── pipeline/                 # ETL + enriquecimento
│   │   ├── pyproject.toml
│   │   └── src/jevlab_pipeline/
│   │       ├── load.py           # leitura CSV (utf-8-sig)
│   │       ├── normalize.py      # dedup, flags determinísticos, PII
│   │       ├── state_builder.py  # linha -> state
│   │       ├── enrich.py         # orquestra chamadas (async, semáforo)
│   │       └── metrics.py        # tabelas agregadas
│   └── dashboard/                # Streamlit
│       ├── pyproject.toml
│       └── src/jevlab_dashboard/app.py
├── scripts/
│   ├── 00_smoke_jev.py           # 1 lead -> imprime answers
│   ├── 01_inspect.py             # perfil do CSV
│   ├── 02_build_states.py        # dedup + states
│   ├── 03_enrich.py              # --limit N | --all (com resume)
│   ├── 04_metrics.py             # gera tabelas
│   └── 05_dashboard.sh           # streamlit run
├── outputs/                      # results (gitignore os grandes)
│   ├── leads_unique.parquet
│   ├── enriched.parquet
│   ├── metrics/*.parquet
│   └── fixtures/jev_response.json
└── tests/
```

**Variante simples (se o workspace uv incomodar):** um único `pyproject.toml` na raiz e um pacote `jevlab/` com subpastas `core/`, `pipeline/`, `dashboard/`. O plano não muda; muda só o empacotamento.

**Stack:** Python 3.11+, `httpx` (async), `pandas` + `pyarrow`, `pydantic` + `pydantic-settings`, `tenacity` (retry), `streamlit` + `plotly`, `pytest`, `python-dotenv`.

---

## 5. Fases

Cada fase tem checkpoint com critérios binários (passa/não passa) e um comando de validação.

---

### Fase 0 — Setup e reconhecimento dos dados

**Objetivo:** repo criado, ambiente reproduzível, e um perfil de dados confiável em disco.

**Entregáveis**
- [ ] Estrutura do monorepo criada (seção 4).
- [ ] `pyproject.toml` raiz + `.env.example` + `Makefile`.
- [ ] `scripts/01_inspect.py` que gera `docs/01-data-profile.md`.
- [ ] `README.md` com passos de instalação e execução.

**Tarefas**
1. Inicializar workspace uv e os 3 pacotes (editáveis).
2. `.env.example` com `OPENROUTER_API_KEY=`, `JEV_MODEL=typesafe/jev-1.13`, `MASK_PII=true`, `MAX_CONCURRENCY=8`, `SPEND_CAP_USD=5`.
3. `01_inspect.py`: ler CSV com `utf-8-sig`, reportar por coluna nº de distintos, top-valores, nulos, e as métricas de qualidade da seção 1.4 (CPF, telefone, e-mail, nomes).
4. Escrever o resultado em `docs/01-data-profile.md` (versionado).

**Checkpoint 0 — Aprovação**
- [ ] `make inspect` roda do zero e (re)gera `docs/01-data-profile.md` sem erro.
- [ ] Os números batem com a seção 1.4 (60.760 linhas; ~50.087 nomes distintos; 17.458 CPF inválidos; etc.).
- [ ] `.env` está no `.gitignore` e `data/raw` também.

**Como validar:** `make inspect && git diff --stat docs/01-data-profile.md` (segunda execução deve ser estável/near-zero diff).

---

### Fase 1 — Cliente JEV (OpenRouter) + contrato de perguntas

**Objetivo:** uma função confiável que envia `{model, state, questions}` ao endpoint System One e devolve as respostas tipadas.

**Entregáveis**
- [ ] `jevlab_core/jev_client.py` com `evaluate(state, questions, model) -> dict`.
- [ ] `questions.yaml` com as 18 perguntas das seções 3.1–3.4 e loader validado por pydantic.
- [ ] `cache.py` (cache em disco por `sha256(state + questions + model)`).
- [ ] `scripts/00_smoke_jev.py`.
- [ ] `outputs/fixtures/jev_response.json` (resposta real capturada para testes offline).
- [ ] `tests/test_jev_client.py` (usa o fixture; sem chamar a API).

**Tarefas**
1. Cliente HTTP com `httpx` para `POST https://openrouter.ai/api/v1/systemone`, header `Authorization: Bearer`.
2. Retry com backoff exponencial via `tenacity` (erros 429/5xx; respeitar `Retry-After`).
3. Capturar `usage.cost` e acumular em log/estrutura de custo.
4. Validação da resposta contra o schema de saída (campos por tipo).
5. Cache: antes de chamar, checar; se hit, não gastar token.
6. Smoke: 1 lead real, imprimir `answers` formatados e `usage`.

**Checkpoint 1 — Aprovação**
- [ ] `make smoke` faz 1 chamada e imprime respostas dos 3 tipos (`noul`, `choice`, `score`) com valores plausíveis.
- [ ] Rodar `make smoke` de novo retorna do **cache** (custo incremental $0) — provar via log.
- [ ] `pytest tests/test_jev_client.py` passa 100% **sem rede**.
- [ ] Resposta contém `model`, `answers`, `usage.input_tokens`, `usage.cost`.

**Como validar:** `make smoke && make smoke && pytest -q` e conferir no log “cache hit” na 2ª execução.

**Gate de risco:** se 429 persistir, reduzir `MAX_CONCURRENCY` e confirmar backoff antes de seguir.

---

### Fase 2 — Preparação de dados (dedup, PII, state, baseline determinístico)

**Objetivo:** transformar 60.760 linhas em uma tabela de leads únicos com `state` pronto e flags determinísticas de baseline.

**Entregáveis**
- [ ] `load.py` (leitura robusta), `normalize.py`, `state_builder.py`.
- [ ] `scripts/02_build_states.py` → `outputs/leads_unique.parquet`.
- [ ] `docs/02-decisions.md` registrando: regra de PII, chave de dedup, normalizações.
- [ ] `tests/test_state_builder.py`.
- [ ] Baseline em Python puro: `flag_email_typo_regex`, `flag_tel_invalido`, `cpf_valido` (checksum), `nome_caixa_rule`.

**Tarefas**
1. Dedup por prioridade: **CPF válido → e-mail normalizado → telefone**. Guardar `n_aparicoes` e `lead_key`.
2. Aplicar máscara de PII conforme `MASK_PII` (seção 1.5) — **antes** de gerar o `state`.
3. `state_builder` produz o objeto canônico da seção 3.5.
4. Flags determinísticas (para comparar com o JEV na Fase 6).
5. Salvar parquet com: `lead_key`, `state_json`, `n_aparicoes`, flags baseline, e colunas originais não-PII para o dashboard.

**Checkpoint 2 — Aprovação**
- [ ] `make states` gera `leads_unique.parquet` com ~50k linhas e coluna `state_json` válida (parseável).
- [ ] Nenhum CPF/telefone completo presente no `state_json` quando `MASK_PII=true` (teste automatizado).
- [ ] `pytest tests/test_state_builder.py` passa.
- [ ] `docs/02-decisions.md` descreve a regra de dedup e a de PII.

**Como validar:** `make states && python -c "import pandas as pd;d=pd.read_parquet('outputs/leads_unique.parquet');print(len(d));d.head()"` + `pytest -q`.

---

### Fase 3 — Enriquecimento em amostra (prova de valor)

**Objetivo:** rodar as 18 perguntas em 200–500 leads e provar que o enriquecimento é útil e barato, **antes** de escalar.

**Entregáveis**
- [ ] `enrich.py` com `asyncio` + `Semaphore(MAX_CONCURRENCY)` e resume/cache.
- [ ] `scripts/03_enrich.py --limit 300`.
- [ ] `outputs/enriched_sample.parquet`.
- [ ] `outputs/cost_log.jsonl` (uma linha por chamada com tokens e custo).
- [ ] Amostra anotada à mão de ~20 leads (`outputs/manual_check.csv`) para medir acerto.

**Tarefas**
1. Para cada lead: montar `questions` (todas as 18) e chamar `evaluate`.
2. Achatar respostas em colunas: `nome_genero`, `email_provider`, `email_typo`, `carro_marca`, `carro_tier`, `qual_bot`, `qual_score`, e as respectivas `confidence`/`noul`.
3. Tratar falhas por lead sem derrubar o lote (registrar `erro`).
4. Acumular custo; abortar se passar do cap.
5. Medir acurácia da amostra anotada.

**Checkpoint 3 — Aprovação**
- [ ] `make enrich SAMPLE=300` completa com **≥ 98%** de leads enriquecidos (falhas registradas).
- [ ] `enriched_sample.parquet` tem todas as colunas derivadas esperadas e tipos corretos.
- [ ] Custo total da amostra **< $0,10** (ver `cost_log.jsonl`).
- [ ] Acurácia na amostra manual **≥ 85%** em `email_provider`, `carro_marca` e `nome_genero`.
- [ ] Rodar de novo finaliza instantâneo (cache).

**Como validar:** `make enrich SAMPLE=300 && python -c "...soma cost_log..."` + revisar `manual_check.csv`.

**Gate de decisão:** se a acurácia ficar abaixo do alvo, ajustar `instructions`/`criteria` em `questions.yaml` (bump de versão) **antes** da Fase 4.

---

### Fase 4 — Execução completa + métricas

**Objetivo:** rodar a base inteira de forma retomável e consolidar métricas.

**Entregáveis**
- [ ] `scripts/03_enrich.py --all` com **checkpoint em parquet incremental** e resume.
- [ ] `outputs/enriched.parquet`.
- [ ] `metrics.py` + `scripts/04_metrics.py` → `outputs/metrics/*.parquet` (tabelas por tema).
- [ ] Relatório de custo consolidado.

**Tarefas**
1. Execução completa com gravação a cada N leads; ao reiniciar, pular os já processados.
2. Tabelas de métricas:
   - Nomes: contagem por `nome_genero`, `nome_caixa`, taxa `nome_invalido`.
   - E-mails: por `email_provider`, `email_tipo`, taxa `email_typo`.
   - Carros: por `carro_marca`, `carro_carroceria`, `carro_cambio`, `carro_combustivel`, distribuição `carro_tier`, top `carro_cor`.
   - Qualidade: distribuição `qual_score`, taxa `qual_bot`, média de `confidence` por pergunta.
3. Cruzamentos: `carro_marca × carro_tier`, `qual_score × email_typo`, `note_genero × carro_carroceria` (se fizer sentido).
4. Registrar custo total.

**Checkpoint 4 — Aprovação**
- [ ] `make all` processa 100% dos leads únicos com **≥ 98%** de sucesso.
- [ ] Teste de resume: interromper no meio, rodar de novo, e terminar sem reprocessar (custo incremental ~0 para os já feitos).
- [ ] Custo total **< $5** (teto).
- [ ] Todos os arquivos em `outputs/metrics/` existem e somam o total de leads únicos.

**Como validar:** `make all` → `Ctrl+C` → `make all` (deve retomar) → `make metrics` → conferir somas.

---

### Fase 5 — Dashboard (Streamlit)

**Objetivo:** visualizar as 4 ideias. O dashboard **lê parquet**, nunca chama a API.

**Entregáveis**
- [ ] `packages/dashboard/.../app.py` com 5 páginas: **Visão Geral, Nomes, E-mails, Carros, Qualidade/Risco**.
- [ ] Gráficos Plotly (barras, pizza, histograma de `qual_score`, heatmap de cruzamentos).
- [ ] Filtros globais: marca, tier, faixa de `qual_score`, flag bot.
- [ ] Tabela drill-down por lead (sem PII crua quando `MASK_PII=true`).
- [ ] `scripts/05_dashboard.sh` (`streamlit run`).

**Tarefas**
1. Carregar `enriched.parquet` + `metrics/*.parquet` com `@st.cache_data`.
2. KPI cards no topo: total leads, % e-mail typo, % bot, média `qual_score`.
3. Cada aba com seus gráficos e a tabela-fonte correspondente.
4. Mostrar **confiança média** por pergunta (transparência do JEV).
5. Comparativo opcional JEV vs baseline determinístico (coerência).

**Checkpoint 5 — Aprovação**
- [ ] `make dash` abre o dashboard e **todas as 5 abas** renderizam sem erro.
- [ ] Os números dos KPIs **batem** com `outputs/metrics/*.parquet` (conferência manual em 3 métricas).
- [ ] Dashboard funciona **offline** (sem rede) — prova de que não chama a API.
- [ ] Nenhuma PII crua aparece na UI com `MASK_PII=true`.

**Como validar:** desligar rede → `make dash` → navegar as abas.

---

### Fase 6 — Validação, comparação e encerramento

**Objetivo:** medir o valor real do JEV e documentar para decisão de continuidade.

**Entregáveis**
- [ ] `docs/03-validation-report.md`.
- [ ] Tabela de acurácia JEV vs baseline determinístico.
- [ ] Relatório de custo x benefício (custo real por 1.000 leads enriquecidos).
- [ ] `README.md` final com “quickstart” de 5 comandos.

**Tarefas**
1. Anotar à mão uma amostra estratificada de 30–50 leads (todas as classes relevantes).
2. Calcular acurácia/precisão por pergunta e a **concordância** com as regras determinísticas.
3. Analisar casos de baixa `confidence` — onde o JEV hesita e por quê.
4. Consolidar custo total e custo/lead.
5. Documentar limitações e próximos passos (ex.: ideias 3 e 5 descartadas, dedup semântico).

**Checkpoint 6 — Aprovação**
- [ ] Relatório publicado com números de acurácia e custo reais.
- [ ] Recomendação explícita: **escalar / ajustar perguntas / abandonar**.
- [ ] `README.md` permite que outra pessoa rode o pipeline do zero em < 15 min.

**Como validar:** seguir o quickstart do `README.md` em ambiente limpo.

---

## 6. Resumo dos checkpoints

| Fase | Entregável-chave | Critério de aprovação (resumo) |
| --- | --- | --- |
| 0 | `docs/01-data-profile.md` | Perfil reproduzível e números batem com seção 1.4 |
| 1 | Cliente + fixture + `questions.yaml` | Smoke OK, 2ª chamada do cache, testes offline passam |
| 2 | `leads_unique.parquet` | ~50k únicos, `state_json` válido, sem PII no state |
| 3 | `enriched_sample.parquet` | ≥98% sucesso, custo <$0,10, acurácia ≥85% |
| 4 | `enriched.parquet` + metrics | 100% com resume, custo <$5, somas consistentes |
| 5 | Dashboard | 5 abas OK, números batem, roda offline |
| 6 | `docs/03-validation-report.md` | Acurácia + custo reais e recomendação |

---

## 7. Riscos e mitigação

| Risco | Prob. | Impacto | Mitigação |
| --- | --- | --- | --- |
| 429 / rate limit do OpenRouter | Média | Alto | Semáforo + backoff (tenacity) + cache; rodar fora de pico |
| Respostas instáveis entre versões | Baixa | Médio | Fixar `typesafe/jev-1.13`; nunca usar alias; logar `model` |
| PII enviada por engano | Média | Alto | Máscara por padrão + teste automatizado no checkpoint 2 |
| Acurácia baixa em português | Média | Médio | Medir na Fase 3; ajustar `criteria`; inglês melhor se necessário |
| Custo descontrolado | Baixa | Médio | Cache + cap de gasto + sample antes do full |
| Dashboard lento com 50k linhas | Baixa | Baixo | Ler parquet + `st.cache_data` + agregações pré-computadas |
| Dedup errado (merge indevido) | Média | Médio | Priorizar CPF válido; logar `n_aparicoes`; revisar amostra |

---

## 8. Glossário rápido

- **System One:** família de modelos de decisão da TypeSafe (JEV é o primeiro).
- **`state`:** o material avaliado (aqui, um objeto JSON por lead).
- **`noul`:** pergunta sim/não que retorna probabilidade.
- **`choice`:** escolha entre opções nomeadas, com distribuição de probabilidades.
- **`score`:** posição em escala ordinal, com legenda e probabilidades.
- **`confidence`:** concentração da distribuição entre as alternativas (não é “segurança do fluxo”).
- **`fan-out`:** enviar várias perguntas independentes na mesma chamada.
- **Baseline determinístico:** regras em Python puro usadas como comparação ao JEV.

---

## 9. Referências

- Jev no OpenRouter (hub): https://openrouter.ai/docs/guides/community/jev
- Tutorial Jev (System One / Decisions API): https://openrouter.ai/docs/guides/community/jev-tutorial
- SDK TypeSafe apontando para OpenRouter: https://openrouter.ai/docs/guides/community/typesafe-sdk
- Página do modelo: https://openrouter.ai/typesafe/jev-1.13
- Cloudflare Workers AI (alternativa de runtime): https://developers.cloudflare.com/ai/models/typesafe/jev/
- Docs de conceitos/primitivos TypeSafe: https://docs.typesafe.ai
- Guia interno: `jev-typesafe.md` (nesta pasta)
