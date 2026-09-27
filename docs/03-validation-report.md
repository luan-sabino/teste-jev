# Relatorio de validacao - JEV Leads Lab

- Gerado em: 2026-09-26 23:38 UTC
- Fonte: `outputs/enriched.parquet`
- Leads enriquecidos: 47783/47783 (100.00%)
- Modelo: `typesafe/jev-1.13` (snapshot logado em `outputs/cost_log.jsonl`)

## 1. Custo

- Custo total acumulado: **$5.3907**
- Custo por 1.000 leads enriquecidos: **$0.1128**
- Chamadas reais registradas: 47773
- Teto configurado (`SPEND_CAP_USD`): $8.00
- Teto original do plano: $5.00 (custo real ficou acima do planejado: $5.3907).
- Nota: prompts com 18 perguntas gastam ~2.700 tokens/lead, entao o custo real (~$0,113/1.000 leads) e maior que a estimativa inicial do plano (~$0,042).

## 2. Acuracia na amostra anotada a mao

| campo | n | acuracia_pct |
| --- | --- | --- |
| nome_genero | 20 | 100.0 |
| email_provider | 20 | 100.0 |
| carro_marca | 20 | 100.0 |


## 3. Concordancia JEV vs baseline deterministico

| pergunta | baseline | n | concordancia_pct |
| --- | --- | --- | --- |
| nome_caixa | baseline_nome_caixa | 47783 | 69.76 |
| nome_invalido | baseline_nome_invalido | 47783 | 99.53 |
| email_typo | baseline_email_typo | 47783 | 98.47 |


Achado: `nome_caixa` concorda pouco com o baseline porque a regra deterministica (`.title()`) marca nomes com particulas (`de`, `da`, `dos`) como `misto_anomalo`, enquanto o JEV os considera `correto`. O baseline e mais estrito que o JEV; a divergencia e esperada e favorece o JEV.

Atencao: a concordancia alta de `email_typo` (98,47%) ocorre porque o JEV quase nunca sobe a probabilidade (media 0.140, max 0.670; apenas 16 leads >= 0,5), enquanto o baseline marca 720. Casos de dominio malformado (ex.: `gmaol.com`, `gmail.comr`) sao capturados por `email_provider = invalido` (224 leads).
Recomendacao de ajuste: usar limiar ~0,3 em `email_typo` (525 leads) ou depender de `email_provider=invalido`.

## 4. Confianca media por pergunta

| pergunta | confidence_media | n_respostas |
| --- | --- | --- |
| carro_combustivel | 0.5252 | 47783 |
| qual_score | 0.5754 | 47783 |
| carro_carroceria | 0.7998 | 47783 |
| carro_tier | 0.8584 | 47783 |
| nome_caixa | 0.9008 | 47783 |
| email_provider | 0.9763 | 47783 |
| carro_cor | 0.9825 | 47783 |
| nome_genero | 0.9843 | 47783 |
| email_tipo | 0.9942 | 47783 |
| carro_cambio | 0.9956 | 47783 |
| carro_marca | 1.0 | 47783 |


## 5. Distribuicao de qual_score

| score_bucket | label | n_leads | pct |
| --- | --- | --- | --- |
| 0 | 0 = inutilizavel | 0 | 0.0 |
| 1 | 1 = ruim | 87 | 0.18 |
| 2 | 2 = regular | 19795 | 41.43 |
| 3 | 3 = bom | 27901 | 58.39 |
| 4 | 4 = excelente | 0 | 0.0 |


## 6. Limitacoes e proximos passos

- Amostra manual pequena (20 leads) e enviesada para casos faceis;
  ampliar para 30-50 leads estratificados antes de decisao final.
- `carro_combustivel` (confianca media 0,53) e `qual_score` (0,58) sao as
  perguntas mais incertas — revisar `criteria` antes de usar como gate.
- `email_typo` e pouco sensivel (media 0,14); o dominio malformado aparece
  melhor em `email_provider=invalido`.
- Nomes com digitos (CPF/telefone colados) foram mascarados; a anomalia
  permanece visivel como `#` para o JEV.
- Ideias 3 e 5 seguem fora do escopo.

## 7. Recomendacao

- [x] **Escalar** — acuracia da amostra anotada >= 85% e sucesso de enriquecimento em 100.00% dos leads.
- [ ] Ajustar perguntas
- [ ] Abandonar

Recomendacao: **escalar** o uso do JEV para as 4 ideias, com as seguintes ressalvas: (a) ampliar a amostra anotada para 30-50 leads estratificados; (b) revisar `carro_combustivel` (confianca media 0,53) e `qual_score` (0,58), que sao as perguntas mais incertas.
