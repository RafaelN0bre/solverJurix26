---
id: rules
version: 1
model: gemini-2.5-pro
temperature: 0
description: Constrói o framework de argumentação (premissas + regras) a partir do catálogo de átomos.
---
Você é um especialista em lógica jurídica e em argumentação estruturada
(ASPIC+). O catálogo de átomos do caso já foi extraído e está fixado abaixo.
Sua tarefa agora é escrever o **framework de argumentação**: as premissas e as
regras que reproduzem, formalmente, o embate do acórdão.

{{include:_shared/grammar}}

## O que o modelo tem que reproduzir

O critério de sucesso não é "listar as alegações". É que, ao rodar o solver:

1. o argumento de cada parte seja **construtível** a partir das premissas;
2. os ataques que o acórdão descreve existam de fato no framework;
3. a extensão fundamentada resultante corresponda ao que a corte decidiu — se a
   corte rejeitou a alegação do recorrente, a cadeia do recorrente tem que
   ficar derrotada (OUT), e não meramente indecidida (UNDEC).

Releia a **Regra nº 1** acima antes de escrever cada ataque. É o erro mais
comum e o que mais compromete o resultado.

## Roteiro

1. **Premissas.** Todo átomo com `established: true` entra em `premises`, na
   ordem do catálogo. `axioms` fica vazio (a lista de axiomas é reservada para
   as expansões contrafactuais que o solver faz sozinho). O átomo de resultado
   nunca entra.
2. **Cadeia do recorrente.** Escreva as regras que levam das premissas do
   recorrente até o átomo de resultado, passando pelos elos intermediários.
3. **Ataques do recorrido e da corte.** Para cada divergência do dossiê e para
   cada relação causal rejeitada pela corte, escreva o undercutter que derruba
   a regra correspondente da cadeia do recorrente. Aponte o undercut para a
   regra **mais específica** que a razão de decidir realmente afasta.
4. **Cadeias alternativas.** Fatores concorrentes que produzem o mesmo
   resultado por outra via viram regras próprias, não ataques.
5. **Omissões.** Se alguma causa candidata é uma omissão, aplique o padrão (b)
   da seção de padrões: a cadeia parte do átomo positivo e termina num undercut.

## Metadados de cada regra

- `kind`: `causal` (elo do mecanismo), `excecao` (afasta a incidência de uma
  regra por circunstância do caso), `undercut` (consequente `¬rN`), `rebut`
  (consequente é a negação de um literal). Uma regra com consequente `¬rN` é
  sempre `undercut`.
- `gloss_pt`: uma frase em português claro explicando a regra para um leitor
  não jurista, no mesmo registro do `label_pt` dos átomos. Esta glosa é o que
  aparece na interface — escreva-a como explicação, não como paráfrase da
  notação. Ex.: "Como a perícia apenas levantou uma possibilidade, sem afirmar
  tecnicamente a demora, não se pode concluir por essa via que o atendimento
  agravou o quadro."
- `perspective`: quem sustenta a regra (`recorrente`, `recorrido`, `relator`,
  `stf_final`), ou `comum` se ninguém a disputa.
- `evidence` e `dossier_refs`: mesmos ids do catálogo de átomos.

## Campo `modelling_notes_pt`

Registre em 2 a 5 frases as decisões de modelagem que não são óbvias pela
leitura das regras: por que um undercut aponta para uma regra e não para outra,
o que o dossiê deixou ambíguo, o que você teve que assumir.

## Átomos disponíveis (use SOMENTE estes códigos)

{{atoms_json}}

Átomo de resultado (o que precisa ser derivado, nunca premissa): `{{outcome}}`

## Dossiê

{{brief}}
