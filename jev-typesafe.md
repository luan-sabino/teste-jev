# Guia de uso — `typesafe/jev` (Cloudflare Workers AI)

**Jev** é o modelo de *avaliação estruturada* (structured evaluation) da TypeSafe. Em vez de gerar texto livre, ele **avalia um único estado (`state`) contra perguntas tipadas** e devolve respostas calibradas, com probabilidades e confiança.

- **Modelo:** `typesafe/jev` (versão reportada na resposta: `jev-1.13.0`)
- **Endpoint Cloudflare:** `https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/ai/run`
- **Janela de contexto:** 32.000 tokens
- **Retenção de dados:** zero (zero data retention)
- **Licença / termos:** https://docs.typesafe.ai/legal.md
- **Docs do modelo:** https://docs.typesafe.ai/models.md

## Preços

| Item | Preço por 1M tokens |
| --- | --- |
| Input | $0,042 |
| Output | $0,00 (grátis) |
| Input em cache | $0,00 |

Cobrança é feita **somente sobre os tokens de entrada**. Saídas são gratuitas.

---

## Conceito: como o Jev funciona

Você envia duas coisas:

1. **`state`** — o material a ser avaliado (string, objeto JSON ou array). É o contexto/registro/documento.
2. **`questions`** — um objeto com uma ou mais perguntas tipadas. Cada pergunta tem um `type`, `instructions` e, opcionalmente, `criteria`.

O Jev lê o `state` **uma vez** e avalia todas as perguntas em paralelo. A resposta traz uma entrada em `answers` para cada pergunta, sempre com o mesmo nome (chave) que você definiu.

> **Observação importante:** o `state` e todas as perguntas combinadas precisam caber em ~64k tokens no total (a Cloudflare documenta janela de 32k). Prefira muitas perguntas atômicas em um único request ("fan-out").

---

## Os três tipos de pergunta

### 1. `noul` — booleano calibrado

Responde "sim/não" devolvendo um **número entre 0 e 1** (não um booleano). Quanto mais perto de 1, mais provável o "sim".

```json
{
  "is_urgent": {
    "type": "noul",
    "instructions": "Does this convey urgency?",
    "criteria": {
      "true": "Explicitly time-sensitive",
      "false": "No urgency expressed"
    }
  }
}
```

- `criteria` é **opcional** no `noul`, mas definir `true`/`false` melhora a consistência.
- Retorno: `{ "type": "noul", "noul": 0.95 }`

### 2. `choice` — escolha entre categorias

Escolhe **uma** entre várias opções nomeadas. `criteria` é **obrigatório** e é um objeto `chave -> descrição`.

```json
{
  "department": {
    "type": "choice",
    "instructions": "Which team should handle this?",
    "criteria": {
      "billing": "Payments, invoicing, refunds",
      "technical": "Bugs, outages, integrations",
      "sales": "Pricing, upgrades, new accounts"
    }
  }
}
```

- Retorno:
```json
{
  "type": "choice",
  "choice": "billing",
  "confidence": 0.8,
  "probabilities": { "billing": 0.87, "sales": 0, "technical": 0.13 }
}
```
- `choice` é a opção vencedora; `probabilities` traz a distribuição completa.

### 3. `score` — escala ordinal

Avalia em uma **escala ordenada**. `criteria` é **obrigatório** e é um **array** (mínimo de 2 itens), do menor para o maior.

```json
{
  "frustration": {
    "type": "score",
    "instructions": "How frustrated is the customer?",
    "criteria": ["Calm", "Frustrated", "Very angry"]
  }
}
```

- Retorno:
```json
{
  "type": "score",
  "score": 1.04,
  "confidence": 0.94,
  "legend": { "0": "Calm", "1": "Frustrated", "2": "Very angry" },
  "probabilities": { "0": 0, "1": 0.96, "2": 0.04 }
}
```
- `score` é um **número fracionário** (não precisa ser inteiro): 1.04 indica "levemente acima de Frustrated".
- `legend` mapeia o índice numérico de volta para o texto do critério.

---

## Referência de schema

### Entrada (`input`)

| Campo | Obrigatório | Tipo | Descrição |
| --- | --- | --- | --- |
| `state` | Sim | string \| object \| array \| null | Material a ser avaliado |
| `questions` | Sim | object | Mapa `nomeDaPergunta -> definição` (chaves com mín. 1 caractere) |

Cada pergunta tem `type` (`"noul"` \| `"choice"` \| `"score"`), `instructions` (obrigatório, string ou estrutura) e `criteria` (obrigatório para `choice` e `score`; opcional para `noul`).

> `instructions` e `criteria` também aceitam objetos/arrays além de strings — útil para regras estruturadas avançadas.

### Saída (`output`)

| Campo | Descrição |
| --- | --- |
| `model` | ID versionado que respondeu (ex.: `jev-1.13.0`) — use para logging/reprodutibilidade |
| `answers` | Mapa com o mesmo nome das perguntas enviadas |
| `usage` | `{ input_tokens, output_tokens }` |

Formatos por tipo:

```jsonc
// noul
{ "type": "noul", "noul": 0.95 }

// choice
{ "type": "choice", "choice": "billing", "probabilities": {...}, "confidence": 0.8 }

// score
{ "type": "score", "score": 1.04, "legend": {...}, "probabilities": {...}, "confidence": 0.94 }
```

---

## Uso via Workers AI (JavaScript)

```js
const response = await env.AI.run(
  'typesafe/jev',
  {
    state: 'Help! My payouts have been failing for 3 days.',
    questions: {
      is_urgent: {
        type: 'noul',
        instructions: 'Does this convey urgency?',
        criteria: { true: 'Explicitly time-sensitive', false: 'No urgency expressed' },
      },
      department: {
        type: 'choice',
        instructions: 'Which team should handle this?',
        criteria: {
          billing: 'Payments, invoicing, refunds',
          technical: 'Bugs, outages, integrations',
          sales: 'Pricing, upgrades, new accounts',
        },
      },
      frustration: {
        type: 'score',
        instructions: 'How frustrated is the customer?',
        criteria: ['Calm', 'Frustrated', 'Very angry'],
      },
    },
  },
)
console.log(response)
```

## Uso via API HTTP (cURL)

No endpoint HTTP, o payload vai dentro de `input`:

```bash
curl https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/ai/run \
  --header "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
  "model": "typesafe/jev",
  "input": {
    "state": "Help! My payouts have been failing for 3 days.",
    "questions": {
      "is_urgent": {
        "type": "noul",
        "instructions": "Does this convey urgency?",
        "criteria": { "true": "Explicitly time-sensitive", "false": "No urgency expressed" }
      },
      "department": {
        "type": "choice",
        "instructions": "Which team should handle this?",
        "criteria": {
          "billing": "Payments, invoicing, refunds",
          "technical": "Bugs, outages, integrations",
          "sales": "Pricing, upgrades, new accounts"
        }
      },
      "frustration": {
        "type": "score",
        "instructions": "How frustrated is the customer?",
        "criteria": [ "Calm", "Frustrated", "Very angry" ]
      }
    }
  }
}'
```

Resposta de exemplo:

```json
{
  "model": "jev-1.13.0",
  "answers": {
    "is_urgent": { "type": "noul", "noul": 0.95 },
    "department": {
      "type": "choice",
      "choice": "billing",
      "confidence": 0.8,
      "probabilities": { "billing": 0.87, "sales": 0, "technical": 0.13 }
    },
    "frustration": {
      "type": "score",
      "score": 1.04,
      "confidence": 0.94,
      "legend": { "0": "Calm", "1": "Frustrated", "2": "Very angry" },
      "probabilities": { "0": 0, "1": 0.96, "2": 0.04 }
    }
  },
  "usage": { "input_tokens": 426, "output_tokens": 73 }
}
```

---

## Exemplos práticos

### Revisão de reembolso (state estruturado + múltiplas perguntas)

`state` como objeto e `instructions` referenciando caminhos do JSON com crases:

```js
const response = await env.AI.run('typesafe/jev', {
  state: {
    ticket: {
      subject: 'Duplicate charge',
      message: 'I was charged twice for order A-104. Please refund the duplicate.',
    },
    order: {
      id: 'A-104',
      charges: [
        { amount_usd: 49, status: 'captured' },
        { amount_usd: 49, status: 'captured' },
      ],
    },
    refund_policy: 'Duplicate charges are eligible for a refund.',
  },
  questions: {
    refund_requested: { type: 'noul', instructions: 'Does `ticket.message` request a refund?' },
    policy_supports_refund: {
      type: 'noul',
      instructions:
        'Does `refund_policy` support the refund requested in `ticket.message`, given `order.charges`?',
    },
  },
})
```

> **Dica:** referencie campos do `state` com crases (`` `ticket.message` ``) nas `instructions` para tornar a pergunta inequívoca.

### Roteamento de suporte (apenas `choice`)

```js
const response = await env.AI.run('typesafe/jev', {
  state: 'I cannot log in after changing my password, and the reset email never arrives.',
  questions: {
    department: {
      type: 'choice',
      instructions: 'Which team should handle this support request?',
      criteria: {
        account: 'Login, password, profile, or security issues',
        billing: 'Charges, invoices, refunds, or subscriptions',
        technical: 'Product bugs, outages, or integrations',
        other: 'Requests that do not fit the other departments',
      },
    },
  },
})
```

### Risco de conta (`score` + `noul` combinados)

```js
const response = await env.AI.run('typesafe/jev', {
  state: {
    account_age_days: 12,
    recent_events: [
      'Five failed login attempts',
      'Password reset requested from a new country',
      'Successful login from the usual device',
    ],
    account_verified: true,
  },
  questions: {
    risk_level: {
      type: 'score',
      instructions: 'How risky does this account activity appear?',
      criteria: [
        'Low risk: activity is consistent with the account history',
        'Moderate risk: some unusual activity needs monitoring',
        'High risk: multiple strong indicators of account compromise',
      ],
    },
    escalate: {
      type: 'noul',
      instructions: 'Should this account be escalated for manual security review?',
      criteria: {
        true: 'The activity warrants immediate human review',
        false: 'The activity can be handled with normal automated controls',
      },
    },
  },
})
```
Resposta: `risk_level.score = 1.84` (confidence 0.77) e `escalate.noul = 0.81`.

---

## Boas práticas

1. **Decomponha julgamentos amplos em perguntas atômicas.** Em vez de "classifique o ticket", faça `noul` de urgência + `choice` de departamento + `score` de frustração, e combine no seu código.
2. **Codifique regras de domínio em `instructions`/`criteria`.** Não há fine-tuning por cliente — você molda o comportamento via request.
3. **Cole dados proprietários no `state`.** O modelo não é treinado com seus dados (ZDR).
4. **Use as probabilidades/confiança para roteamento.** Decida por limiar (ex.: só automatizar quando `confidence >= 0.9`); as distribuições permitem treinar um modelo clássico downstream.
5. **Verifique `probabilities` no `choice`** para detectar casos ambíguos (ex.: 0.5/0.5).
6. **Referencie campos do `state` com crases** para perguntas sem ambiguidade.
7. **Registre o campo `model`** (ex.: `jev-1.13.0`) para reprodutibilidade; se você calibrou limiares para uma versão, fixe o ID versionado em vez de usar aliases.
8. **Inglês tem melhor acurácia.** Outros idiomas (inclusive CJK) funcionam, mas teste com seu próprio conteúdo antes de confiar.
9. **Entrada é só texto.** Pré-processe imagens/áudio/vídeo/binários para texto ou campos estruturados antes de enviar como `state`.

## Limitações e cuidados

- **Somente texto:** sem entrada de imagem, áudio ou vídeo.
- **Contexto:** ~32k tokens (o `state` + a pergunta mais longa devem caber; o total `state` + todas as perguntas também tem limite). Estados muito longos degradam a acurácia.
- **Aliases podem mudar:** em outros SDKs, `jev-latest`/`jev-preview` movem entre versões. Ao usar a API HTTP, envie `"model": "typesafe/jev"`.
- **Rate limits** (na API original TypeSafe) podem mudar dinamicamente; requisições acima do limite retornam `429`.

## Links úteis

- Página do modelo na Cloudflare: https://developers.cloudflare.com/ai/models/typesafe/jev/
- Schema de entrada: https://developers.cloudflare.com/ai/models/typesafe/jev/schema-input.json
- Schema de saída: https://developers.cloudflare.com/ai/models/typesafe/jev/schema-output.json
- Documentação TypeSafe: https://docs.typesafe.ai/models.md
