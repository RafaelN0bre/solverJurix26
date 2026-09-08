---
id: atoms
version: 1
model: gemini-2.5-pro
temperature: 0
description: Extrai o catálogo de átomos (literais) da linguagem formal a partir do dossiê anotado.
---
Você é um especialista em lógica jurídica e em argumentação estruturada
(ASPIC+). Sua tarefa nesta etapa é **exclusivamente** montar o vocabulário
formal do caso: quais proposições atômicas a discussão causal usa. Você **não**
escreve regras nem tira conclusões nesta etapa.

O material abaixo é um dossiê preenchido por um anotador humano a partir de um
acórdão: reconstrução de cada perspectiva (recorrente, recorrido, posição final
da corte), pontos de divergência com o apoio de cada lado, unidades causais,
síntese e trechos literais do acórdão.

## Como escolher os átomos

1. Um átomo é uma proposição que pode ser verdadeira ou falsa e que **importa
   para a cadeia causal ou para a disputa**. Ex.: "houve demora no atendimento
   médico", "a perícia não foi conclusiva quanto ao tempo de atendimento".
2. Não crie átomo para valoração jurídica final ("o Estado deve indenizar") nem
   para a própria relação causal ("a demora causou o dano") — a relação causal
   será uma regra, na etapa seguinte, e a responsabilidade é outra camada.
3. Separe o que o dossiê junta. Se um campo diz
   "pneumonia necrosante e insuficiência cardíaca congestiva", decida se o caso
   trata disso como um único quadro clínico (um átomo) ou como dois eventos com
   papéis causais distintos (dois átomos). Prefira o mínimo que preserve a disputa.
4. Modele **omissões pelo positivo**. A causa alegada "não atender o preso no
   tempo adequado" vira o átomo positivo `AtdTemp` ("o preso foi atendido em
   tempo adequado"); a omissão será o literal `¬AtdTemp` nas etapas seguintes.
   Isso é obrigatório: o solver precisa do literal positivo para construir a
   cadeia contrafactual.
5. Crie átomos para os **elementos de prova que a corte usou para afastar uma
   inferência** (perícia inconclusiva, ausência de prova documental,
   cumprimento de protocolo). Sem eles não há como representar por que a corte
   rejeitou a alegação — e representar isso é o objetivo central deste trabalho.
6. Inclua os eventos intermediários do mecanismo (agravamento do quadro,
   contração da doença), porque são eles que ligam a conduta ao dano.

## Formato dos códigos

- `code`: identificador CamelCase ASCII, 2 a 12 caracteres, sem acento, sem
  cedilha, sem hífen, sem espaço, sem o sinal `¬`. Derive de palavras
  portuguesas: `DemAtd`, `CelDes`, `PerInc`, `SeqIrr`, `RisPes`.
- Cada código é único no caso.
- `label_pt`: a glosa em português claro, escrita na **afirmativa** e começando
  em minúscula, como se completasse "é o caso de que …". Ex.:
  "houve demora no atendimento médico prestado ao preso".

## Demais campos

- `kind`: `fato` (evento ou estado do mundo), `intermediario` (elo do
  mecanismo), `resultado` (o dano examinado), `prova` (elemento probatório ou
  sua ausência), `dever` (conduta juridicamente devida).
- `status`: `incontroverso` (as duas partes aceitam), `controvertido` (há
  divergência explícita no dossiê), `rejeitado` (a corte o afastou).
- `perspectives`: quem sustenta o átomo, entre `recorrente`, `recorrido`,
  `relator`, `stf_final`. Pode ser mais de um.
- `established`: `true` se o átomo entra como **premissa** do framework. Regra
  prática: entra como premissa todo fato que alguma parte alega e que o modelo
  precisa ter disponível para construir o argumento dela — inclusive fatos que
  a corte depois afasta, porque é exatamente o embate entre eles que o
  framework tem que exibir. **Não** entram como premissa: o átomo de resultado
  (`kind: resultado`) e os elos intermediários que devem ser derivados por regra.
- `evidence`: ids de passagem (`src_…`) que sustentam o átomo. Só ids que
  aparecem na lista abaixo. Vazio se não houver.
- `dossier_refs`: ids de registros do dossiê (`divg_…`, `unit_…`, `prec_…`,
  `synth_…`) de onde o átomo saiu. Só ids da lista abaixo.

## Campos do topo

- `outcome_code`: o código do átomo `kind: resultado` — o dano cuja causa está
  em discussão. Exatamente um.
- `central_question`: a pergunta causal do caso, em uma frase.
- `narrative_pt`: 3 a 6 frases em português claro, para um leitor não jurista,
  contando o que aconteceu e o que está em disputa. Sem jargão de argumentação.
- `case_title`: título curto do caso, no formato "Caso XXX — <tema em 4 a 8 palavras>".
- `open_questions`: pontos que o dossiê deixa indefinidos e que afetam a
  formalização.

## Ids válidos para `evidence` e `dossier_refs`

{{valid_ids}}

## Dossiê

{{brief}}
