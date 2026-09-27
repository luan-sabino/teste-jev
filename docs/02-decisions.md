# Decisoes do projeto

Registro das decisoes fixas do laboratorio (versionado).

## D1 - Empacotamento: variante simples

Em vez do workspace `uv` com 3 pacotes (`core`, `pipeline`, `dashboard`),
adotamos a **variante simples** prevista no plano: um unico `pyproject.toml`
na raiz e o pacote `src/jevlab/` com subpastas `core/`, `pipeline/`,
`dashboard/`. O plano nao muda; muda so o empacotamento.

## D2 - Endpoint do JEV

O plano (secao 1.1) citava `POST https://openrouter.ai/api/v1/systemone`.
A documentacao oficial do OpenRouter (verificada em 2026-09) usa o endpoint
**Decisions API**:

```
POST https://openrouter.ai/api/alpha/decisions
{ "model": "typesafe/jev-1.13", "state": ..., "questions": { ... } }
```

Payload top-level identico ao planejado. O endpoint fica configuravel via
`OPENROUTER_BASE_URL` + `DECISIONS_PATH` no `.env`, com default
`https://openrouter.ai/api` + `/alpha/decisions`.

## D3 - Modelo fixado

`typesafe/jev-1.13` (nunca o alias `~typesafe/jev-latest`), para manter
limiares estaveis. O `model` devolvido na resposta (ex.: `jev-1.13-20260917`)
e logado para reprodutibilidade.

## D4 - PII / LGPD

`MASK_PII=true` por padrao. Antes de montar o `state`:

- **CPF**: nao entra no `state` (nenhum campo). As colunas de exibicao nao
  guardam CPF.
- **Telefone**: `(DD) ****-LLLL` (DDD + 4 ultimos digitos).
- **E-mail**: local-part mascarado (`j***@dominio`); o dominio completo e
  preservado (e util para as perguntas de provedor).
- **Nome**: enviado sem mascara de letras (e o objeto central da avaliacao
  semantica), mas **digitos embutidos sao mascarados** (`#`). Achado da Fase 0:
  alguns nomes contem CPF/telefone completos colados ao nome
  (ex.: `AUDENISCE BORGE PEREIRA 17865354835`).

`MASK_PII=false` envia e-mail e telefone crus (apenas para experimentos).
Quando `MASK_PII=true`, o parquet nao contem CPF e o dashboard nao exibe PII crua.

Teste automatizado garante que nenhum `state_json` contem sequencia de 11
digitos (`pipeline/state_builder.py::state_is_masked`).

Colunas de exibicao (`nome`, `email_display`, `telefone_display`, `carro`)
nao contem PII crua. A coluna interna `lead_key` pode conter CPF/e-mail
(necessaria para dedup/resume), fica apenas em parquet local (gitignored)
e **nunca** e exibida no dashboard.

## D5 - Chave de deduplicacao

Prioridade: **CPF valido (checksum) > e-mail normalizado > telefone**.
Registros sem nenhuma das chaves nao colapsam entre si (`row:<indice>`).
Mantemos o registro mais completo (`n_aparicoes` registra o total e a soma
bate com as 60.760 linhas brutas).

## D6 - Normalizacoes do `state`

- `nome`: texto cru (trim).
- `email`: normalizado (trim + lowercase) e mascarado se `MASK_PII`.
- `email_dominio`: dominio do e-mail original.
- `telefone`: mascarado (DDD + 4 ultimos).
- `carro`: texto cru do modelo.
- `km`: inteiro (digitos) ou `null`.
- `vigencia`, `data_lead`: ISO `YYYY-MM-DD` ou `null` (`data Nascimento`
  praticamente vazia foi descartada).

## D7 - Cache

Cache em disco por `sha256(model + state + questions + versao_do_catalogo)` em
`outputs/cache/`. Rodar de novo o mesmo lead nao gasta token. Mudanca no
`questions.yaml` exige bump de `version` (invalida o cache).

## D8 - Custo

Teto `SPEND_CAP_USD=5`. Toda chamada real escreve uma linha em
`outputs/cost_log.jsonl` com `input_tokens`, `output_tokens` e `cost`.
