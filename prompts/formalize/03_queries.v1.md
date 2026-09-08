---
id: queries
version: 1
model: gemini-2.5-pro
temperature: 0
description: Define os pares causais (phi, psi) a testar e registra o veredito da corte sobre cada um.
---
Você é um especialista em lógica jurídica. O framework de argumentação do caso
já está construído. Sua tarefa é definir **quais perguntas causais devem ser
feitas ao solver** e registrar **o que a corte decidiu sobre cada uma**.

Uma pergunta causal é um par (φ, ψ): "φ é causa de ψ?". O solver responderá
sozinho, por três testes distintos (NESS, causa de fato da Definição 4.3, e
"não fosse por" da Definição 3.5). **Você não deve prever nem sugerir a
resposta do solver** — o valor deste trabalho está justamente em comparar,
depois, o veredito do solver com o veredito da corte.

## Quais pares incluir

- Uma pergunta para cada causa candidata que o dossiê registra, em qualquer
  perspectiva, tendo como ψ o átomo de resultado.
- Uma pergunta para cada causa juridicamente relevante alegada (inclusive as
  rejeitadas pela corte).
- Se uma causa candidata é uma omissão, φ é o literal **negativo** (`¬AtdTemp`),
  não o positivo.
- Não invente pares que o dossiê não discute.

## Campos

- `phi`, `psi`: literais, exatamente como aparecem no catálogo (com `¬` quando
  for o caso). Nada de códigos novos.
- `question_pt`: a pergunta em português claro, para leigo. Ex.: "A demora no
  atendimento médico foi causa das sequelas irreversíveis?"
- `court_verdict`, lido do dossiê e **só** do dossiê:
  - `acolhida` — a corte reconheceu essa relação causal;
  - `rejeitada` — a corte a afastou (aparece entre as causas ou relações
    rejeitadas, ou a conclusão vencedora a nega);
  - `nao_decidida` — o dossiê registra a questão como não decidida, ou não há
    registro do que a corte fez com ela.
- `court_rationale_pt`: em uma ou duas frases, **a razão de decidir da corte**
  sobre esse par, em português claro. Este texto aparece na interface como a
  coluna "Por quê" — escreva-o como explicação para um leitor não jurista.
- `evidence`: ids `src_…` que sustentam o veredito registrado.

## Átomos

{{atoms_json}}

## Framework já construído

{{rules_json}}

Átomo de resultado: `{{outcome}}`

## Dossiê

{{brief}}
