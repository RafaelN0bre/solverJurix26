## Linguagem formal (ASPIC+) — contrato obrigatório

O destino desta formalização é um solver ASPIC+ real. Qualquer desvio de formato
faz a regra ser rejeitada pelo parser.

### Formato das regras

- Regra derrotável (o caso normal): `rN: Ant1 AND Ant2 => Cons`
- Regra estrita (raríssima, ver abaixo): `rN: Ant1 AND Ant2 -> Cons`
- Os antecedentes são separados **exclusivamente** por ` AND ` em maiúsculas.
  Nunca use vírgula, `&`, `e`, `+` ou quebra de linha para separar antecedentes.
- Uma regra tem **exatamente um** consequente.
- Os identificadores de regra são `r0`, `r1`, `r2`, … em sequência, sem buracos.
- Negação é o prefixo `¬` colado ao código: `¬DemAtd`. Não existe `not`, `~` ou `-`.
- Nada de espaços dentro de um código. Nada de acento, cedilha ou hífen nos códigos.

### Undercutter (ataque à aplicabilidade de uma regra)

Uma regra cujo consequente é `¬rN` **derruba a aplicabilidade da regra rN**.
Não existe lista separada de undercutters: basta escrever a regra normalmente.

```
r7: PerInc => ¬r2      # a perícia inconclusiva derruba a aplicação da regra r2
```

### ⚠️ REGRA Nº 1 — use undercut, não rebut, para fazer um lado vencer

Este solver **não tem preferências numéricas entre regras**. Ele usa a ordenação
básica do artigo: dois argumentos derrotáveis são **incomparáveis**.

A consequência é decisiva para a modelagem:

- Se você escrever `r2: DemAtd => Agrav` e `r7: ProtOk => ¬Agrav`, os dois
  argumentos se atacam mutuamente (rebut) e **nenhum dos dois vence** — ambos
  ficam UNDEC (indecididos). Isso quase nunca é o que o acórdão diz.
- Se você escrever `r2: DemAtd => Agrav` e `r7: ProtOk => ¬r2`, o argumento de
  `r7` **derrota** o de `r2` de forma assimétrica. `Agrav` cai. Isso, sim,
  reproduz "a corte afastou a alegação".

Portanto: **sempre que uma perspectiva prevalece sobre a outra no acórdão,
modele a prevalência como undercut (`=> ¬rN`)**, atacando a regra do lado
derrotado. Use rebut (`=> ¬Literal`) apenas quando o acórdão realmente deixa a
questão em aberto, isto é, quando o resultado desejado é o impasse.

### Regras estritas

Use `->` apenas para passos indefectíveis, que nenhuma prova poderia afastar
(por exemplo, uma definição legal fechada). Na dúvida, use `=>`. Uma regra
estrita não pode ser derrotada por undercut e costuma tornar o modelo rígido
demais para representar um litígio.

### Literais

- Use **somente** os códigos do catálogo de átomos que já foi extraído.
  Nunca invente um código novo, nunca traduza um código, nunca renomeie.
- Um literal negativo `¬X` só pode aparecer se `X` estiver no catálogo.
- O código do resultado danoso **não pode** ser premissa: ele tem que ser
  derivado por alguma regra, senão não há nada a explicar causalmente.

### Padrões de modelagem

Os códigos abaixo (`Doe`, `Con`, `Trat`, `Mor`, `Peric`, `Ris`, `Agrav`) são
**fictícios, só para ilustrar a forma**. Nunca os use numa formalização real.

**(a) Cadeia causal simples.** Fato → mecanismo intermediário → resultado.

```
r0: Doe => Agrav
r1: Agrav => Mor
```

**(b) Omissão (a causa alegada é um fato negativo `¬X`).** O literal `¬X`
**não aparece em regra nenhuma**. Modele em três passos:
(i) a regra que deriva o resultado do estado de fato;
(ii) a cadeia que parte do literal **positivo** `X`;
(iii) o undercutter em que essa cadeia derruba (i).

```
premissas: ["Doe", "¬Con"]
r0: Doe => Mor          # (i) sem tratamento, a doença leva à morte
r1: Con => Trat         # (ii) se houvesse consentimento, haveria tratamento
r2: Trat => ¬r0         # (iii) o tratamento derrubaria a regra r0
```

Está **errado** escrever `r2: Trat => ¬Mor`: a omissão tem que atacar a
*aplicabilidade* da regra, não concluir a negação do resultado. É esse desenho
que faz o teste contrafactual (expandir o framework com o literal oposto)
reconhecer a omissão como causa.

**(c) Prova insuficiente / laudo inconclusivo.** A corte não afirma o
contrário do fato: ela diz que a prova não sustenta a inferência. Isso é
undercut da regra que a prova sustentaria, nunca rebut do fato.

```
r2: DemAtd => Agrav     # a demora agravaria o quadro
r6: PerInc => ¬r2       # mas a perícia é inconclusiva: a inferência não se aplica
```

**(d) Excludente / conduta conforme o protocolo.** Mesmo desenho: o
cumprimento do protocolo derruba a regra que imputa o agravamento à conduta.

```
r7: ProtOk => ¬r2
```

**(e) Causa concorrente ou alternativa.** Um fator pessoal que produz o mesmo
resultado por outra via é uma **cadeia paralela**, não um ataque:

```
r8: Ris => Agrav
```

Só acrescente um undercut (`r9: Ris => ¬r2`) se o acórdão realmente disser que
o fator pessoal **rompe** o nexo, e não apenas que concorre com ele.

**(f) Preempção.** Quando uma causa se antecipa e torna a outra faticamente
impossível, a que chegou antes derruba a regra da outra:

```
r3: PriEve => ¬r1
```
