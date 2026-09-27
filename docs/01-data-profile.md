# Perfil dos dados - CSV bruto

- Arquivo: `Report Update - Salesforce - N8N Beta Prod - RD Api.csv`
- Gerado em: 2026-09-26 23:08 UTC
- Linhas: **60760** | Colunas: **17**

## 1. Metricas de qualidade (secao 1.4 do plano)

| Metrica | Medido | Esperado (plano) | Confere |
| --- | --- | --- | --- |
| `linhas` | 60760 | 60760 | OK |
| `colunas` | 17 | 17 | OK |
| `pessoas_unicas_nome` | 50087 | 50087 | OK |
| `cpf_fora_11_digitos` | 17458 | 17458 | OK |
| `cpf_repetidos` | 9507 | 9507 | OK |
| `telefone_digito_repetido` | 18 | 18 | OK |
| `email_suspeito` | 38 | 38 | OK |
| `nome_maiusculo` | 7694 | 7694 | OK |
| `nome_minusculo` | 1472 | 1472 | OK |
| `nome_com_digitos` | 32 | 32 | OK |
| `nascimento_vazio` | 60412 | 60412 | OK |

Metricas auxiliares:

- CPFs de 11 digitos repetidos (todas as ocorrencias): 16071
- CPFs de 11 digitos repetidos (ocorrencias extras): 9507

Definicoes adotadas para as metricas ambiguas do plano:

- `cpf_repetidos` = ocorrencias **extras** de um CPF de 11 digitos (`duplicated(keep='first')`).
- `email_suspeito` = local-part numerico **ou** placeholder puro (teste/test/asdf/aaa/xxx/qwe/email). O plano cita 73 sem definir o criterio.

## 2. Perfil por coluna

| Coluna | Distintos | Vazios | % vazio | Top valores |
| --- | ---: | ---: | ---: | --- |
| Nome da Oportunidade | 50087 | 0 | 0.0 | Cleverson Andrade (19); Odair Soares (18); CACILDA BARRETO NOBRE (15); Eduardo de sousa Teixeira (14); Pedro Henrique (13) |
| Nome da Organização | 1 | 0 | 0.0 | Unidas Livre (60760) |
| Nome do contato | 50087 | 0 | 0.0 | Cleverson Andrade (19); Odair Soares (18); CACILDA BARRETO NOBRE (15); Eduardo de sousa Teixeira (14); Pedro Henrique (13) |
| Telefone do contato | 48295 | 0 | 0.0 | 11959219995 (19); 31983529000 (16); 11995007725 (14); 18991509816 (14); 55555555555 (14) |
| E-mail do contato | 48226 | 0 | 0.0 | acleverson127@gmail.com (19); odairsoares674@gmail.com (18); edukellytri@gmail.com (14); cacildabarretonobre@7gmail.com (14); guilhermecarvalho010203@gmail.com (13) |
| Fonte da negociação | 1 | 0 | 0.0 | api@livre.com.br (60760) |
| Campanha | 1 | 0 | 0.0 | api@livre.com.br (60760) |
| Segmento do cliente | 1 | 0 | 0.0 | Carro Por Assinatura (60760) |
| Responsável | 0 | 60760 | 100.0 | - |
| Etapa | 1 | 0 | 0.0 | Novo Lead (60760) |
| CPF | 47547 | 0 | 0.0 | 37510933897 (19); 49531700672 (18); 15882839840 (15); 5024523822 (14); 48162961828 (13) |
| data Nascimento | 304 | 60412 | 99.43 | 02/03/1960 (4); 29/04/1986 (4); 31/10/1998 (3); 11/11/1980 (3); 31/03/1995 (3) |
| cod mob | 60429 | 0 | 0.0 | 00QU600000bVSKV (2); 00QU600000bVgu2 (2); 00QU600000bVzEs (2); 00QU600000bW2J9 (2); 00QU600000bW6Q3 (2) |
| Data Lead | 268 | 0 | 0.0 | 04/01/2026 (1008); 08/01/2026 (969); 2026-05-27 (669); 07/01/2026 (579); 05/01/2026 (518) |
| Carro | 254 | 67 | 0.11 | Volkswagen Polo Highline 1.0 170 TSI AT Preto Ninja (4494); Renault Kwid Intense 1.0 MT Branco Glacier (3847); Volkswagen Polo Robust 1.0 MT Branco Cristal (3797); Volkswagen Tera Comfort 1.0 TSI AT Preto Ninja (2878); Volkswagen Polo Track MT 5P Preto Ninja (2641) |
| KM | 4 | 67 | 0.11 | 1000 (41762); 2500 (7162); 1500 (7045); 2000 (4724) |
| Vigência | 3 | 55241 | 90.92 | 36 (3211); 12 (1615); 24 (693) |

## 3. Observacoes

- Encoding: UTF-8 com BOM (`utf-8-sig`).
- Leitura com `dtype=str`; string vazia representa ausencia de valor.
- `data Nascimento` e praticamente vazia: nao usar como sinal.
- Colunas constantes (1 valor): 
  Nome da Organização, Fonte da negociação, Campanha, Segmento do cliente, Etapa
