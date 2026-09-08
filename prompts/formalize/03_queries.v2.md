---
id: queries
version: 2
model: gemini-2.5-pro
temperature: 0
description: Define os pares causais (phi, psi) a testar e registra o veredito da corte sobre cada um, separando causa de fato de tese acolhida.
---
Você é um especialista em lógica jurídica. O framework de argumentação do caso
já está construído. Sua tarefa é definir **quais perguntas causais devem ser
feitas ao solver** e registrar **o que a corte decidiu sobre cada uma**.

Uma pergunta causal é um par (φ, ψ): "φ é causa de ψ?". O solver responderá
sozinho, por três testes distintos (NESS, causa de fato da Definição 4.3, e
"não fosse por" da Definição 3.5). **Você não deve prever nem sugerir a
resposta do solver** — o valor deste trabalho está justamente em comparar,
depois, o veredito do solver com o veredito da corte.

## ⚠️ A pergunta é sobre causa, não sobre quem ganhou

`court_verdict` responde a **uma** coisa: *a corte reconheceu φ como causa
de ψ?* Não responde se a corte deu ganho de causa ao lado que invocou φ.

A confusão entre as duas é o erro mais frequente desta etapa, e ela aparece
sempre da mesma forma. O acórdão diz que um fato **rompe o nexo causal**, e a
tese de quem o invocou vence; então parece natural marcar `acolhida`. Mas
"romper o nexo" é justamente **negar** que aquele fato explique o dano por uma
cadeia causal — ou é afirmar que *outro* fato o explica. Nos dois casos, a
resposta à pergunta causal não é `acolhida`.

Teste antes de escrever cada `court_verdict`: **a razão de decidir afirma que
φ produziu ψ?**

- Sim, φ produziu ψ → `acolhida`.
- Não; a corte diz que φ não produziu ψ, ou que só o produziria se não
  houvesse outra causa → `rejeitada`.
- A corte não enfrentou a questão → `nao_decidida`.

Repare que `court_rationale_pt` e `court_verdict` **não podem se contradizer**:
se você escrever "a corte considerou o lapso de três meses um fator para romper
o nexo", o veredito daquela linha não pode ser `acolhida`.

Circunstâncias que **qualificam** um evento — o tempo decorrido, o concurso de
agentes, o regime de cumprimento de pena — em geral não são causas por si:
elas sustentam a caracterização de outro fato como causa (ou como causa
superveniente). Prefira perguntar pelo **evento**, não pelo qualificador.

## Quais pares incluir

- Uma pergunta para **cada causa candidata que o dossiê registra, em qualquer
  perspectiva**, tendo como ψ o átomo de resultado — inclusive as que a
  perspectiva vencida sustentava e a corte afastou. Uma causa candidata que o
  dossiê registra e você não pergunta é uma lacuna: ninguém saberá o que o
  solver teria dito sobre ela.
- Uma pergunta para cada causa juridicamente relevante alegada, inclusive as
  rejeitadas pela corte.
- Se uma causa candidata é uma omissão, φ é o literal **negativo** (`¬AtdTemp`),
  não o positivo.
- Não invente pares que o dossiê não discute.

O framework abaixo é a camada de **causa de fato**, e ela pode ser mais enxuta
do que o dossiê: defesas doutrinárias (fato de terceiro, ausência de dever,
imprevisibilidade) foram deixadas para o estágio seguinte. Isso **não** reduz
as perguntas: use o dossiê, e não o tamanho do framework, para decidir o que
perguntar.

## Campos

- `phi`, `psi`: literais, exatamente como aparecem no catálogo (com `¬` quando
  for o caso). Nada de códigos novos.
- `question_pt`: a pergunta em português claro, para leigo. Ex.: "A demora no
  atendimento médico foi causa das sequelas irreversíveis?"
- `court_verdict`, lido do dossiê e **só** do dossiê, aplicando o teste acima:
  - `acolhida` — a corte reconheceu essa relação causal;
  - `rejeitada` — a corte a afastou (aparece entre as causas ou relações
    rejeitadas, a conclusão vencedora a nega, ou a corte disse que outro fato
    rompeu o nexo);
  - `nao_decidida` — o dossiê registra a questão como não decidida, ou não há
    registro do que a corte fez com ela.
- `court_rationale_pt`: em uma ou duas frases, **a razão de decidir da corte**
  sobre esse par, em português claro. Este texto aparece na interface como a
  coluna "Por quê" — escreva-o como explicação para um leitor não jurista, e
  coerente com o veredito que você registrou na mesma linha.
- `evidence`: ids `src_…` que sustentam o veredito registrado.

## Átomos

{{atoms_json}}

## Framework já construído (camada de causa de fato)

{{rules_json}}

Átomo de resultado: `{{outcome}}`

## Dossiê

{{brief}}
