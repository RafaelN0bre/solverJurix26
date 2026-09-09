# Auditoria — Prakken 2008 e CATO/ASPIC+ 2015

Auditoria de fidelidade de `src/aspic/perspectives.py`, `src/aspic/perspective_view.py`
e `src/aspic/factors.py` contra os dois artigos que dizem implementar. Nenhum código
foi alterado por esta auditoria. Toda afirmação abaixo foi produzida rodando o
código sobre `case-003-final` (`data/translated/case-003-final/case.json`) ou sobre
um contraexemplo mínimo reproduzido no texto. Suíte no estado auditado:
`286 passed, 1 xfailed`.

**Estado auditado:** working tree em 2026-09-08 11:00–11:24, sobre
`perspectives.py` (1077 linhas, mtime 11:00:44) e `factors.py` (176 linhas, mtime
08-28 17:32). Durante a auditoria outra sessão adicionou o commit `e16ef35` e o
arquivo `tests/test_reference_fidelity.py` (11:22:57), que trata dos artigos ICAIL
de causação e não toca nos dois módulos auditados — a suíte passou a `288 passed,
3 xfailed` por essa razão. Todas as citações `arquivo:linha` foram reconferidas
contra o estado final e continuam válidas.

Referências:

- **Artigo A** — Prakken, H. *A Formal Model of Adjudication Dialogues*, AI & Law
  2008 (`docs/papers/2008_Prakken_FormalModel_AILaw.pdf`), lido integralmente
  (23 pp.). Citações por página do PDF.
- **Artigo B** — Prakken, Wyner, Bench-Capon & Atkinson, *A formalization of
  argumentation schemes for legal case-based reasoning in ASPIC+*, JLC 25(5),
  2015, pp. 1141–1166
  (`docs/papers/A_formalisation_of_argumentation_schemes_for_legal_case_based_reasoning_in_ASPIC_.pdf`),
  lido integralmente (27 pp.). Citações por número de definição e página da revista.

---

## Resumo

O repositório implementa **uma leitura do Artigo A, não o Artigo A**. O que existe
é uma *decomposição post hoc* de um grafo já pronto, projetado por titular de regra;
o artigo define um *protocolo de diálogo* com atos de fala, turnos, ônus e término.
Isso, por si, é adaptação legítima e declarada. O que não é legítimo são cinco
divergências confirmadas em que o código **afirma** fidelidade e o comportamento
observado a contradiz:

1. **A preferência não tem autor.** `PreferenceBlock`
   (`src/formalize/schema.py:256-267`) é o único objeto móvel do registro sem campo
   de titular, e a ordenação é injetada em *todos* os passos dos dois traços,
   inclusive na fase de argumentação. Contraexemplo 1 mostra a preferência
   decidindo um rebate **entre as partes**, sem nenhum adjudicador ter movido nada.
   No Artigo A o argumento de prioridade é um *movimento do adjudicador na fase de
   decisão* (§4.3, p. 13; α₂₄, p. 17). **Contradiz a estrutura de fases.**
2. **A ponte por passo retira premissas em vez de atacá-las.** `bridged_for`
   (`perspectives.py:342-367`) faz o conjunto de premissas *encolher* quando um
   voto entra: quatro literais `CaFa_*`/`ButFor_*` desaparecem do passo 4 para o 5.
   No Artigo A o adjudicador que não aceita uma premissa **move um contra-argumento
   de ataque a premissa** (§4.3, p. 13); retratar é ato de fala privativo de quem
   afirmou (Tabela 2, p. 12) e vedado ao adjudicador por R₈.
3. **O ponto de virada é artefato da ordem codificada.** Invertendo
   `ADJUDICATORS` (`perspectives.py:48`) o traço de decisão perde **os dois**
   eventos: nenhum `newly_relevant`, nenhum `newly_blocked`.
4. **A fase de decisão admite as partes.** `decision_trace` itera sobre
   `(*ADVERSARIES, *ADJUDICATORS)` (`perspectives.py:399-400`), e a interface
   rotula essas linhas sob o texto *"Só o adjudicador se move aqui"*
   (`perspective_view.py:401-402`). R₈ diz o contrário.
5. **"Sem movimento" mente.** A caixa vazia significa "não é o *primeiro* titular
   de nenhuma regra", não "não moveu nada" — e a legenda invoca Prakken para
   declarar que quem está ali endossou tudo (`perspective_view.py:62-66`).
   Contraexemplo 4: uma perspectiva que sustenta quatro regras é desenhada
   "sem movimento".

No Artigo B, `factors.py` é **honesto no que declara e omisso no que não declara**.
A declaração sobre CS1–CS4 e *distinguishing* é verdadeira. Mas o módulo omite três
divergências relevantes: `cancels` implementa `parentFactor` e não `ancestor`
(defs. 18 e 20 do artigo); `abstract_factor: str` não expressa múltiplos pais, que
o artigo exige explicitamente (p. 1149); e o módulo trata todo átomo como fator,
inclusive com polaridade `neutro`, que o Axioma 6 (p. 1147) proíbe. Há ainda uma
incoerência interna: `partitions` toma a **perspectiva** como caso, `cancellations`
toma o **registro inteiro** — e dois dos três cancelamentos encontrados em
`case-003-final` unem fatores que nenhuma perspectiva sustenta junto.

O que está fiel, e é substancial: a projeção por titular múltiplo; a leitura de
ataques pelos titulares e não pelas caixas; a distinção `derivable=False` vs.
verdicto negativo; a exclusão dos undercuts de `resolved_conflicts` (Def. 2.10 do
Artigo B); a álgebra de partições, que reproduz literalmente as defs. 12–17; e
`dvpre_q8`, que é um argumento de prioridade movido como undercutter por um
adjudicador na fase de decisão — exatamente a rota que o Artigo A prevê.

---

## Artigo A — modelo de adjudicação

### O que o modelo exige

**Papéis** (§4.2, p. 11): `Players = {π, δ, α}` — exatamente três. π e δ são os
adversários; α é *o* adjudicador, singular. A fase de decisão é explicitamente
"um monólogo, e o adjudicador pode responder aos próprios movimentos" (§4.3, p. 13).

**As duas fases** (R₁₃, p. 12): a fase de argumentação é a que precede o movimento
`terminate`; a de decisão é o resto. R₈ separa os poderes: na argumentação α só move
`burden`, `illegal`, `pass` e `terminate`; na decisão α só move `argue` e `terminate`.

**Os movimentos do adjudicador na fase de decisão** (§4.3, p. 13) — quatro decisões,
cada uma com a sua forma:

| decisão | forma do movimento |
|---|---|
| se uma premissa não disputada e não atacada vale | contra-argumento de **ataque a premissa** (ou nada) |
| se um argumento é internamente válido | **undercutter** (ou nada) |
| se cabe mover contra-argumentos adicionais a argumentos internamente válidos | `argue` |
| se um argumento é dialeticamente válido | **argumento de prioridade** |

**Silêncio é decisão** (§4.3, p. 13, in fine): *"Note that all these decisions can be
made by either remaining silent or moving an argument."* E, no exemplo (§5.2, p. 17):
α₂₆ `terminate` "implicitamente julgando todos os argumentos restantes internamente
válidos por não mover undercutters, e dialeticamente válidos por não mover nenhum
outro contra-argumento".

### Tabela exigência → implementação → veredito

| # | Exigência do Artigo A | Implementação | Veredito |
|---|---|---|---|
| A1 | `Players = {π, δ, α}`, um único adjudicador (§4.2 p. 11) | `ADVERSARIES` + `ADJUDICATORS` de 4 elementos, `perspectives.py:47-48` | **Extensão não declarada.** Quatro adjudicadores; o artigo não tem confronto adjudicador × adjudicador |
| A2 | Fase de argumentação: adversários constroem o grafo | `adjudication_trace` passo 0 = ambos os adversários, `perspectives.py:231-234` | **Fiel** como decomposição post hoc |
| A3 | Fase de decisão: **só α move** (R₈, p. 12) | `decision_trace` itera `(*ADVERSARIES, *ADJUDICATORS)`, `perspectives.py:399-400`; passos 1 e 2 do traço real são `recorrente` e `recorrido` | **Divergência D4** |
| A4 | Ataque a premissa como movimento de α (§4.3) | Nenhum: `undermine=0` nas duas camadas; a rejeição de premissa é feita por *recomputação* em `bridged_for`, `perspectives.py:342-367` | **Divergência D2** |
| A5 | Undercutter como movimento de α (§4.3) | `sc_q6`, `unom_q7`, `dvpre_q8`, `r7`, `r8`; `mapped_rules` classifica pelo consequente negado, `perspectives.py:688-690` | **Fiel** |
| A6 | Argumento de prioridade como movimento de α (§4.3; α₂₄ p. 17) | Duas rotas: `dvpre_q8` (undercut autoral, **fiel**) e `aspic/preferences.py` via `Theory.preferences`, `perspectives.py:66,76-78,178,320` (**infiel**) | **Divergência D1** — ver seção própria |
| A7 | Silêncio de α = endosso (§4.3) | `SILENT_NOTE`, `perspectives.py:767-771`, emitido em `perspectives.py:988-991` | **Divergência D5** |
| A8 | Ordem dos movimentos determinada pelo diálogo (T₁–T₅, p. 13: turno vai ao *current loser*) | Ordem fixa em `ADJUDICATORS`, `perspectives.py:48`, e reutilizada em `perspectives_in`, `cif_keys_for`, `mapped_rules` | **Divergência D3** |
| A9 | Ônus de produção: ato de fala `burden(φ,p)`, alocado por α (R₁₀, R₁₁, p. 12) | Ausente do repositório (`grep -ril burden src/` → vazio) | **Não implementado** (não declarado como tal) |
| A10 | Ônus de persuasão: dado como entrada à fase de decisão (§4.1, p. 11) | Ausente | **Não implementado** |
| A11 | Admissibilidade de prova: `illegal m` (Tabela 2, p. 12; α₁₉ p. 17) | Ausente | **Não implementado** |
| A12 | `terminate`, `pass`, turntaking, *current winner/loser* (T₁–T₅, p. 13) | Ausentes | **Não implementado** |
| A13 | `retract φ` é ato do próprio falante; α não pode retratar (Tabela 2, R₈) | `bridged_for` retira premissas de terceiros ao admitir um voto | **Divergência D2** |
| A14 | Status dialético recalculado a cada movimento (§3.3, p. 7) | `argument_status(af, extension)` a cada passo, `perspectives.py:254` | **Fiel** |
| A15 | Grafo dialético só cresce (§3.3, p. 10) | `new_rules` é monotônico (`perspectives.py:248-249`), mas o conjunto de **premissas** da camada LRC não é | **Divergência D2** |

### Divergências confirmadas

#### D1 — O argumento de prioridade não tem autor e vale na fase de argumentação

Ver seção fundamentada abaixo.

#### D2 — A ponte por passo retrata premissas em vez de atacá-las

`decision_trace` recalcula os fatos causais a cada passo
(`perspectives.py:409-411`), delegando a `bridged_for` (`perspectives.py:342-367`).
Traço real:

```
step 3  added=relator            bridged = []
step 4  added=voto_convergente   bridged = ['CaFa_OmiEstatal_Danos', 'ButFor_OmiEstatal_Danos',
                                            'CaFa_RegFechado_Danos', 'CaFa_FugaPreso_Danos',
                                            'ButFor_FugaPreso_Danos', 'CaFa_Latrocinio_Danos',
                                            'ButFor_Latrocinio_Danos']
step 5  added=voto_divergente    bridged = ['CaFa_LapsoTemp_Danos', 'CaFa_FormacaoQuad_Danos',
                                            'CaFa_Latrocinio_Danos', 'ButFor_Latrocinio_Danos']
```

Do passo 4 para o 5, **cinco literais somem** — `CaFa_OmiEstatal_Danos`,
`ButFor_OmiEstatal_Danos`, `CaFa_RegFechado_Danos`, `CaFa_FugaPreso_Danos`,
`ButFor_FugaPreso_Danos` — e dois entram. `project_lrc` monta
`premises = [*bridged]` (`perspectives.py:313`), logo o literal não fica OUT: ele
**deixa de existir na base de conhecimento**. Não há argumento para ele, não há
ataque a ele, não há nada a inspecionar.

O Artigo A prevê a decisão sobre premissas (§4.3, p. 13, primeiro item), mas prevê
a *forma*: "o adjudicador move um contra-argumento de ataque a premissa". A retirada
silenciosa é `retract`, que na Tabela 2 (p. 12) é resposta de rendição do próprio
falante a um `why`, e que R₈ veda ao adjudicador. Em `case-003-final` quem "retrata"
`CaFa_OmiEstatal_Danos` é o voto divergente, sobre uma premissa que ele nunca
afirmou.

**Veredito: não é extensão, é contradição** — o modelo do artigo é monotônico em
premissas e resolve discordância sobre premissa por ataque; aqui a discordância
apaga a premissa.

**Além disso, o passo 5 é sobredeterminado e o traço não diz por quê.** 2×2 isolando
ponte e votos:

```
bridge@4 x votos@4: LeReCa=True   | DeverEspec=True  ¬DeverEspec=False ¬cf2lrc_q5=False
bridge@4 x votos@5: LeReCa=False  | DeverEspec=False ¬DeverEspec=True  ¬cf2lrc_q5=True
bridge@5 x votos@4: LeReCa=False  | DeverEspec=True  ¬DeverEspec=False ¬cf2lrc_q5=False
bridge@5 x votos@5: LeReCa=False  | DeverEspec=False ¬DeverEspec=True  ¬cf2lrc_q5=True
```

A ponte do passo 5 **sozinha** bloqueia a pretensão; as defesas do passo 5
**sozinhas** também. O `newly_blocked` do passo 5 relata um evento onde há dois,
de naturezas diferentes: um fato deixou de ser causa, e uma defesa doutrinária
entrou. A coluna "causas de fato" da interface (`perspective_view.py:392-395`)
foi feita para essa distinção, mas conta `CaFa_*` sem separar as duas causas de ✗.

**Contrafactual: sem `bridged_for` o traço é plano.** Usando a ponte global
armazenada (`r.lrc.bridged_premises`), que é o que `project_lrc` faz com
`bridged=None`:

```
bridge_global x votos@4: LeReCa=False
bridge_global x votos@5: LeReCa=False
```

Ou seja, **o único ponto de virada positivo do traço (passo 4, `newly_relevant`)
existe só por causa da ponte por passo**. Isso é mérito real da invenção — ela
mostra algo que o registro global esconde. E é também o motivo pelo qual ela não
pode ser apresentada como leitura do Artigo A: o artigo não tem duas camadas, não
tem premissas derivadas de outra camada, e não tem recomputação de base de
conhecimento entre movimentos.

#### D3 — A ordem de admissão não tem respaldo no artigo e determina o resultado

`ADJUDICATORS = ("relator", "voto_convergente", "voto_divergente", "stf_final")`
(`perspectives.py:48`) é convenção nossa. O Artigo A não tem ordem de papéis: tem
regras de turno (T₁–T₅, p. 13) em que o turno vai ao *current loser* — quem move a
seguir depende do estado dialético, não de um cargo. E, com um único α, a questão
nem se põe.

Teste (substituindo `P.ADJUDICATORS` em memória):

```
ORIGINAL ('relator','voto_convergente','voto_divergente','stf_final')
   relevancia por passo : [False, False, False, False, True, False]
   newly_relevant em    : [4] | newly_blocked em: [5]
   1o passo com Danos justificado (cif): 2

INVERTIDA ('stf_final','voto_divergente','voto_convergente','relator')
   relevancia por passo : [False, False, False, False, False, False]
   newly_relevant em    : []  | newly_blocked em: []
   1o passo com Danos justificado (cif): 1

DIVERGENTE PRIMEIRO ('voto_divergente','relator','voto_convergente','stf_final')
   relevancia por passo : [False, False, False, False, False, False]
   newly_relevant em    : []  | newly_blocked em: []
   1o passo com Danos justificado (cif): 1
```

**O resultado depende inteiramente da ordem.** Não é que o ponto de virada se
desloque: ele **desaparece**. Admitido o dissenso primeiro, a pretensão nunca se
sustenta e o traço não relata evento nenhum — a interface renderiza uma tabela sem
nenhuma `turning-row`. Na camada de causa de fato o efeito é mais suave mas real:
o passo em que `Danos` passa a ser derivado vai de 2 para 1.

A ordem é defensável como *ordem processual do acórdão* (relator, depois votos,
depois a decisão do órgão). Mas então é uma tese sobre o processo brasileiro, não
uma leitura de Prakken, e a afirmação de `perspectives.py:45-46` — "a ordem em que
um diálogo de adjudicação se desenrola" — atribui ao artigo uma ordem que ele não
tem.

#### D4 — A fase de decisão admite movimentos das partes

`decision_trace` monta `votes` a partir de `(*ADVERSARIES, *ADJUDICATORS)`
(`perspectives.py:399-400`). Traço real: os passos 1 e 2 admitem `recorrente` e
`recorrido`, com as regras `suca_q3`, `sc_q6` e `dvesp_q0`. R₈ (p. 12) é explícito:
na fase de decisão o adjudicador só move `argue` e `terminate` — e só ele move.

Três agravantes:

- O docstring do próprio `decision_trace` diz "a camada de relevância jurídica
  reconstruída **um adjudicador por vez**" (`perspectives.py:377`), o que o código
  não faz.
- `cif_keys_for` afirma o oposto no seu docstring — "ambos os adversários, sempre:
  a fase de argumentação acabou antes de a fase de decisão começar"
  (`perspectives.py:330-332`) — e o implementa corretamente para a camada de causa
  de fato. As duas camadas do mesmo módulo usam noções de fase incompatíveis.
- A interface renderiza essas linhas sob o cabeçalho `Quem decide` e o texto
  *"Só o adjudicador se move aqui, e move argumentos"*
  (`perspective_view.py:401-402`). O leitor vê "recorrente" na coluna "quem decide".

#### D5 — "Sem movimento" não significa "não moveu"

`mapped_rules` desenha cada regra na caixa do **primeiro** titular na ordem
`(*ADVERSARIES, *ADJUDICATORS)` (`perspectives.py:679-681`), e
`to_adjudication_dot` emite o nó `SILENT_NOTE` quando a caixa fica vazia
(`perspectives.py:988-991`). A legenda declara, invocando Prakken, que isso é
"uma decisão, não uma lacuna (quem não ataca, endossa)"
(`perspective_view.py:62-66`).

**Contraexemplo 4** — removendo `r8` (a única regra em que `voto_convergente` é o
primeiro titular) do registro em memória:

```
voto_convergente ainda sustenta: ['cf2lrc_q5', 'dvesp_q0', 'r1', 'r2']
mas o mapa desenha: "silent_voto_convergente" [... label="sem movimento"]
```

Uma perspectiva que sustenta **quatro regras**, incluindo a presunção geral e a tese
do dever específico, é desenhada como silente — e a legenda afirma, em nome do
artigo, que ela endossou o que está no grafo. Em `case-003-final` isso não ocorre
por sorte (`r8` existe); o predicado que governa o nó é "não é o primeiro titular
de nada", não "não moveu nada".

Um segundo desvio, mais fino: no artigo o silêncio que endossa é o de **α, na fase
de decisão, sobre um argumento determinado**, e o que o torna decisão é o
`terminate` que o segue. Aqui o silêncio é atribuído também às **partes**
(`LANES`, `perspectives.py:458-462`, dá caixa a `recorrente` e `recorrido`), e
parte silente no Artigo A não endossa nada — apenas passa, e pode perder pelo ônus
tático (§5.1, p. 14).

**Veredito parcialmente fiel:** a proposição "silêncio do adjudicador é decisão" é
lida corretamente do artigo; a condição que o código usa para detectar silêncio não
é silêncio, e a proposição é estendida a quem o artigo não cobre.

### O argumento de prioridade e as nossas preferências: veredito fundamentado

**O que o artigo diz.** O argumento de prioridade é, no Artigo A, um objeto com
quatro propriedades inseparáveis:

1. **É um argumento** — `argue A`, na linguagem de comunicação (Tabela 2, p. 12),
   sujeito a todas as regras que valem para argumentos. R₇.2 (p. 10) o define pela
   função: "A é um argumento de prioridade que impede B de derrotar C".
2. **Tem alvo** — responde a um movimento (`t(m)`). No exemplo: `α₂₄[δ₁₂]`, isto é,
   responde a δ₁₂ (p. 17).
3. **Tem autor, e é o adjudicador** — na fase de decisão, R₈ (p. 12) restringe
   `argue` a α, e §4.1 (p. 11) diz que "na fase de decisão só o adjudicador pode
   mover e, até o término, só pode mover argumentos, inclusive contra-argumentos e
   argumentos de prioridade".
4. **Tem fundamento explícito e atacável** — α₂₄ é `π₁₁ > δ₁₂ since convinced by π₁₁`
   (p. 17). O "since" é premissa, e o próprio artigo observa que o formalismo *não*
   permite ao adjudicador expressar as razões da alocação do ônus (p. 16, sobre
   α₁₀), contrastando com o argumento de prioridade, que as expressa.

**O que nós temos.** Duas coisas distintas, e é preciso separá-las.

**Rota 1 — `dvpre_q8`. Fiel.** A regra `dvpre_q8: DeverEspec => ¬sc_q6`, do
`relator`, é um undercut sobre `sc_q6`. Ele impede que a defesa de ato de terceiro
derrote a tese do dever específico. Tem autor (um adjudicador), tem alvo, tem
antecedente explícito e atacável, e entra no traço no passo em que o relator entra.
É exatamente o que `perspectives.py:30-33` descreve, e é exatamente a rota que o
artigo prevê: um argumento de prioridade expresso como undercutter, movido por α.
`confrontations` classifica-o corretamente:
`relator -> recorrente | decisão | dvpre_q8 ⇏ sc_q6`.

**Rota 2 — `aspic/preferences.py`. Infiel, e é ela que decide o conflito ⟨q0,q2⟩.**

*Quem move?* Ninguém. `PreferenceBlock` (`src/formalize/schema.py:256-267`) tem
`principle`, `dimensions`, `profiles`, `notes_pt` — e **nenhum campo de titular**.
É o único objeto móvel do registro nessa situação: `RuleMeta` (`schema.py:204-215`),
`LrcRuleOut` (`schema.py:143-149`), `LrcPremiseOut` (`schema.py:123-135`) e
`AtomOut` (`schema.py:63`) todos têm `perspective`/`perspectives`/`holders()`.
`_holders` (`perspectives.py:94-107`) não tem o que ler num `PreferenceBlock`.
O docstring do próprio bloco responde à pergunta: *"os pesos são do leitor"*
(`schema.py:259-261`). O autor da prioridade é **o leitor da formalização** — um
quarto agente, fora de `Players = {π, δ, α}`.

*Ela decide?* Sim, o conflito central. Rodando `resolved_conflicts` sobre o
framework LRC completo:

```
A11 (¬DeverEspec, dvgen_q1, força 10) prevalece sobre A9 (DeverEspec, dvesp_q0, força 4) por weakest
   type=rebut  attack_succeeded=True
```

E o efeito nas conclusões justificadas da camada LRC:

```
COM pref -> [... 'DeverGener', ..., '¬DeverEspec', '¬cf2lrc_q5']
SEM pref -> [... 'DeverGener', ...]                     (sem ¬DeverEspec, sem ¬cf2lrc_q5)
```

Sem a preferência, o rebate ⟨`dvesp_q0`, `dvgen_q1`⟩ deixa os dois lados UNDEC e
`¬cf2lrc_q5` não é justificado. **A preferência é o que faz o dissenso vencer a
questão do dever.**

*Quando ela vale?* Sempre. `Theory.preferences` (`perspectives.py:66`) é passada ao
framework em `Theory.framework()` (`perspectives.py:76-78`), e `project`
(`perspectives.py:178`) e `project_lrc` (`perspectives.py:320`) a preenchem
incondicionalmente com `_preferences(record)`. Isso inclui o **passo 0** de
`adjudication_trace`, que o docstring chama de "a fase de argumentação"
(`perspectives.py:214-216`).

**Contraexemplo 1 — a preferência decide um rebate entre as partes, na fase de
argumentação:**

```python
kb = {'premises': ['A','B'], 'axioms': []}
cm = {'strict_rules': [], 'defeasible_rules': ['pA: A => X', 'pB: B => ¬X']}
pm = PreferenceModel([Dimension('d','peso',1.0)],
                     [RuleProfile('pA', {'d': 1.0}), RuleProfile('pB', {'d': 9.0})])
```

```
sem preferencia    justificados = ['A', 'B']
com preferencia    justificados = ['A', 'B', '¬X']
```

`pA` do recorrente, `pB` do recorrido, nenhum adjudicador moveu nada, e a validade
dialética já está decidida. No Artigo A isso é impossível: a validade dialética é
a quarta decisão de §4.3, privativa da fase de decisão, e o único movimento que a
expressa é um `argue` de α.

**Veredito.**

> A rota `dvpre_q8` é **fiel**. A rota `preferences.py` **contradiz a estrutura de
> fases** do Artigo A em dois pontos independentes, cada um suficiente: (i) a
> ordenação vale desde o passo 0, decidindo validade dialética antes de a fase de
> decisão existir — contraexemplo 1; (ii) a ordenação não é atribuível a ninguém,
> quando no artigo o argumento de prioridade é definido *pelo* fato de ser um
> movimento de α com alvo e fundamento — `PreferenceBlock` não tem campo de titular.

Não é "extensão legítima" no sentido em que a multi-titularidade ou a ponte por
passo o são, porque não acrescenta um objeto novo ao lado do modelo: **substitui**
um objeto do modelo (o movimento de prioridade) por um artefato de outra natureza
(uma ordenação global do framework, do Artigo B, Def. 2.2), e o faz de modo que a
distinção de fases deixa de ter consequência sobre ele. É extensão do **ASPIC+**
— legítima e bem construída ali, com `resolved_conflicts` corretamente excluindo
undercuts por Def. 2.10 — apresentada como se fosse leitura do **Artigo A**.

O reparo é pequeno e estrutural, e vale registrar porque a auditoria não deve
apenas condenar: bastaria `PreferenceBlock` carregar `perspective`/`perspectives`
como todo o resto do registro, e `project`/`project_lrc` filtrarem os `profiles`
pelos titulares admitidos no passo. A preferência voltaria a ser um movimento, com
autor e com momento, e o traço passaria a poder mostrar *em que voto* a prioridade
entrou. Hoje não pode.

---

## Artigo B — fatores

### Tabela definição → implementação → veredito

| # | Definição do Artigo B | Implementação | Veredito |
|---|---|---|---|
| B1 | `pFactor(f)` / `dFactor(f)` (p. 1147) | `SIDE_LABELS`, `CATO_SIDE`, `factors.py:41-48`; `Factor.side`, `factors.py:57` | **Fiel na correspondência**, com um terceiro valor a mais (B3) |
| B2 | Axioma 6: `∀f ¬(pFactor(f) ∧ dFactor(f))` (p. 1147) | `Factor.side` é escalar → exclusividade por construção | **Fiel** |
| B3 | Um fator *predispõe* a decisão a um lado (§3.1, p. 1145); não existe fator neutro | `favors` default `"neutro"`, `factors.py:69`; `factors_of` converte **todo átomo** em `Factor`, `factors.py:62-72` | **Divergência D6** |
| B4 | `parentFactor(f, abstract)` (p. 1148), com **múltiplos pais obrigatórios** (p. 1149) | `abstract_factor: str`, `src/formalize/schema.py:68`; `hierarchy` agrupa por string única, `factors.py:89-95` | **Divergência D7** |
| B5 | Def. 18 (p. 1150): `ancestor` = fecho transitivo de `parentFactor` | Inexistente | **Divergência D8** |
| B6 | Def. 20 (p. 1150): `cancels(f₁,f₂)` ≡ polaridades opostas ∧ `∃f₃(ancestor(f₁,f₃) ∧ ancestor(f₂,f₃))` | `cancellations`, `factors.py:98-117` — polaridades opostas ∧ **mesmo pai direto** | **Parcialmente fiel** — D7, D8 |
| B7 | `cancels` aplica-se *dentro* de um caso; `substitutes` *entre* casos (p. 1150) | `cancellations` opera sobre o registro inteiro; `substitutes` corretamente ausente (`factors.py:28-29`) | **Divergência D9** (incoerência com B9) |
| B8 | Def. 19: `substitutes` (p. 1150) | Deliberadamente ausente, declarado em `factors.py:28-29` | **Omissão honesta** |
| B9 | Defs. 12–17 (p. 1149): `commonPfactors = pFactors(curr) ∩ pFactors(prec)`; `currPfactors = pFactors(curr) \ commonPfactors`; `precPfactors = pFactors(prec) \ commonPfactors`, e as três duais em `d` | `partitions`, `factors.py:151-166` | **Fiel na álgebra**, adaptado no domínio (D9) |
| B10 | `outcome(prec) ∈ {plaintiff, defendant}` (p. 1148) | Ausente | **Omissão honesta**, `factors.py:12-20` |
| B11 | CS1, CS2 (p. 1151, 1153) | Ausentes | **Omissão honesta** |
| B12 | U1.1, U1.1.1, U1.1.2, U2.1, U2.1.1, U2.1.2 (pp. 1152–1154) | Ausentes | **Omissão honesta** |
| B13 | CS3, CS4 (p. 1155) | Ausentes | **Omissão honesta** |
| B14 | `preferred(factorSet1, factorSet2)` (p. 1150) | Ausente do módulo. Existe algo de nome parecido em `preferences.py`, mas é ordenação de **argumentos** (Def. 2.2), não de conjuntos de fatores | **Omissão honesta**; sem confusão no código |
| B15 | Def. 2.3/2.4: derrota por undercut é independente de preferências | `resolved_conflicts` exclui undercuts, `preferences.py:298-299`, com a Def. 2.10 citada no docstring, `preferences.py:283-285` | **Fiel** |
| B16 | §4.2 (p. 1161): a passagem de **fatos** para **fatores** exige esquemas próprios, não fornecidos | `factors_of` faz a passagem implicitamente, tratando átomo como fator | **Divergência D6** |

### Divergências confirmadas

#### D6 — Todo átomo vira fator, e existe fator "neutro"

`factors_of` (`factors.py:62-72`) devolve um `Factor` para **cada átomo do
registro**. Em `case-003-final`:

```
fatores com side='neutro': ['Latrocinio', 'MorteVitima', 'Danos']
```

`Danos` é o efeito do caso; `MorteVitima` e `Latrocinio` são eventos. No Artigo B
um fator é, por definição, "uma situação fática prototípica que predispõe a decisão
em favor de uma das partes" (§3.1, p. 1145), e o Axioma 6 (p. 1147) faz da
polaridade uma dicotomia. Um fator sem lado não é um fator neutro: não é fator.

O artigo é explícito sobre por que isso importa. §4.2 (p. 1161) trata exatamente da
lacuna: "os casos não chegam empacotados como conjuntos de fatores, e sim como
coleções desordenadas de fatos"; a passagem fato → fator "exige que os casos sejam
representados não só em termos de fatores, mas em termos dos fatos subjacentes que
sustentam a atribuição do fator", e os autores dizem não fornecer esses esquemas.
`factors_of` faz essa passagem por identidade — todo fato é um fator — que é
precisamente o passo que o artigo diz não estar resolvido.

O `is_annotated` (`factors.py:75-79`) mitiga o efeito na interface (case-005 vem
`anotado: False` e a balança não é desenhada), e o docstring de `factors_of`
justifica o default. Mas a declaração do módulo (`factors.py:22-29`) lista três
peças implementadas — polaridade, hierarquia, cancelamento — e **não menciona** que
o universo sobre o qual as três operam é o conjunto de átomos, não o conjunto de
fatores.

#### D7 — Um pai só

`abstract_factor: str` (`src/formalize/schema.py:68`). O artigo, na p. 1149, é
categórico: *"se desejado, podem ser acrescentados axiomas a `K_n` para excluir
ciclos na hierarquia de fatores, mas **múltiplos pais têm de ser permitidos** para
representar a hierarquia de [1]"*. E o próprio exemplo o exige:
`parentFactor(F4, F102)` **e** `parentFactor(F4, F115)` (p. 1149). Sob o nosso
esquema, `F4` só pode estar sob um dos dois, e a substituição `substitutes(F4, F6)`
via `F102` e a relação com `F21` via `F115` não podem coexistir.

#### D8 — `parentFactor` no lugar de `ancestor`

`cancellations` (`factors.py:110`) itera sobre `hierarchy(record)`, que agrupa por
igualdade exata de `factor.abstract` (`factors.py:92-94`). Isso é
`parentFactor(f₁,a) ∧ parentFactor(f₂,a)`. A Def. 20 pede
`∃f₃(ancestor(f₁,f₃) ∧ ancestor(f₂,f₃))`, com `ancestor` definido na Def. 18 como
fecho transitivo. A nossa relação é estritamente mais fraca.

**Contraexemplo 2** (registro sintético, dois fatores netos do mesmo abstrato):

```
f1 (responsabilizacao) sob DeverConcreto, f2 (exclusao) sob DeverDifuso,
ambos filhos de NaturezaDoDever

cancellations() -> []
artigo (Def. 20, ancestor transitivo) -> cancels(f1, f2) VERDADEIRO
```

`unclassified` (`factors.py:169-176`) documenta corretamente que uma hierarquia com
buracos sub-relata cancelamentos, mas o buraco aqui não é de anotação: é de
profundidade. Uma hierarquia bem anotada **com dois níveis** já sub-relata.

Em `case-003-final` o efeito é nulo porque a hierarquia é rasa (todo `abstract` é
raiz), então isto é uma divergência de definição sem consequência observada *neste
caso* — mas com consequência garantida em qualquer hierarquia de dois níveis, que é
justamente a que CATO tem.

#### D9 — "Caso" significa duas coisas diferentes dentro do mesmo módulo

`partitions` (`factors.py:151-166`) toma a **perspectiva** como caso: `_codes`
(`factors.py:146-148`) filtra por `perspective in f.perspectives`. `cancellations`
(`factors.py:98-117`) toma o **registro inteiro** como caso: não filtra por
perspectiva nenhuma. O artigo diz que cancelamentos aplicam-se *dentro* de um caso
(p. 1150). Sob a adaptação de `partitions`, "dentro de um caso" deveria significar
"dentro de uma perspectiva".

Consequência medida em `case-003-final`:

```
RegFechado(recorrido, relator, voto_convergente) x DeverGener(voto_divergente)
    sob NaturezaDoDever -> perspectivas em comum: NENHUMA
DeverEspec(recorrido, relator, voto_convergente) x DeverGener(voto_divergente)
    sob NaturezaDoDever -> perspectivas em comum: NENHUMA
MeiosDisp(voto_convergente) x ProvCabiveis(voto_convergente)
    sob OnusDaProva -> perspectivas em comum: ['voto_convergente']
```

**Dois dos três cancelamentos unem fatores que nenhuma perspectiva sustenta
junto.** Sob a semântica de `partitions`, esses dois pares nunca estão no mesmo
"caso" e não poderiam cancelar-se. Só o terceiro é um cancelamento no sentido do
artigo — e é, aliás, o mais interessante: `voto_convergente` sustenta, sob o mesmo
ponto abstrato `OnusDaProva`, um fator pró e um contra.

Isto não invalida a leitura que o docstring propõe ("onde duas posições se separam
de fato"): a discordância entre `DeverEspec` e `DeverGener` é real e é o cerne do
caso. Mas ela é uma **divergência entre perspectivas**, que é o que `partitions`
mede; chamá-la de "cancelamento" importa do artigo uma palavra cuja definição diz
outra coisa — no artigo, cancelar é *remover o fator abstrato do caso*, o que
pressupõe que os dois fatores estejam no mesmo caso.

### Sobre a honestidade da declaração (pergunta 6)

A declaração de `factors.py:12-35` é **verdadeira e verificável no que afirma**:
CS1–CS4, U1.1.x e U2.1.x não estão implementados; `outcome(prec)` não existe;
`substitutes` está ausente e a razão dada (precisa de dois casos) é a do artigo
(p. 1150); a aplicação das partições entre perspectivas é explicitamente marcada
como "adaptação, não CATO", com a ressalva correta de que não há stare decisis nela.
Não encontrei nenhuma afirmação falsa. Não há esquema implementado às escondidas,
nem base de precedentes disfarçada.

Mas é **incompleta em três pontos**, todos confirmados acima e nenhum mencionado:
que o universo de fatores é o de átomos, inclusive neutros, contra o Axioma 6 e
contra §4.2 (D6); que `cancels` usa pai direto e não ancestral, contra as Defs. 18
e 20 (D8); e que a hierarquia é de pai único, contra a exigência expressa da p. 1149
(D7). A quarta — que `cancellations` e `partitions` usam noções de "caso"
diferentes (D9) — é uma incoerência interna, não uma omissão sobre o artigo.

### Sobre `cancels` (pergunta 7) — comparação literal

**Artigo, Def. 20 (p. 1150):**

```
∀f₁,f₂. cancels(f₁,f₂) ≡
    ((pFactor(f₁) ∧ dFactor(f₂)) ∨ (dFactor(f₁) ∧ pFactor(f₂)))
  ∧ ∃f₃ (ancestor(f₁,f₃) ∧ ancestor(f₂,f₃))
```

com, Def. 18 (p. 1150):

```
∀f₁,f₂. ancestor(f₁,f₂) ≡ parentFactor(f₁,f₂) ∨ ∃f₃(ancestor(f₁,f₃) ∧ parentFactor(f₃,f₂))
```

**Nosso, `factors.py:98-117`:** para cada `abstract` e cada par `(first, second)`
em `hierarchy(record)[abstract]`, emite o par se `OPPOSITE[first.side] == second.side`.
Desdobrado:

```
cancels_nosso(f₁,f₂) ≡
    ((pFactor(f₁) ∧ dFactor(f₂)) ∨ (dFactor(f₁) ∧ pFactor(f₂)))
  ∧ f₁.abstract ≠ "" ∧ f₁.abstract = f₂.abstract
```

Comparação cláusula a cláusula:

| cláusula | artigo | nosso | veredito |
|---|---|---|---|
| polaridade oposta | `(p∧d) ∨ (d∧p)` | `OPPOSITE.get(first.side) == second.side`, `factors.py:113` | **idêntico** (e `neutro` não tem oposto, logo nunca cancela — coerente) |
| ancestral comum | `∃f₃(ancestor(f₁,f₃) ∧ ancestor(f₂,f₃))`, transitivo, múltiplos pais | igualdade de uma string de pai único | **estritamente mais fraco** |
| simetria | simétrica (as duas disjunções) | par não ordenado emitido uma vez, normalizado `(pro, against)`, `factors.py:114-116` | **equivalente** |
| escopo | relação em `K_n` sobre fatores; a restrição ao caso vem das premissas dos esquemas | sobre os átomos do registro, sem restrição de perspectiva | **fiel à Def. 20 isolada**; incoerente com a adaptação de `partitions` (D9) |

**Veredito: não é a mesma definição.** É a Def. 20 com `ancestor` substituído por
`parentFactor` e com a hierarquia restrita a pai único. Coincide com o artigo
exatamente quando a hierarquia tem um nível e cada fator um pai — que é o caso de
`case-003-final`, e não é o caso de CATO.

### Sobre a álgebra de partições entre perspectivas (pergunta 8)

**A álgebra está correta.** Verificação direta contra as Defs. 12–17, com
`left = relator`, `right = voto_divergente`:

```
commonPro      ['OmiEstatal']
leftPro        ['DeverEspec', 'RegFechado']
rightPro       ['FugaPreso']
commonContra   []
leftContra     []
rightContra    ['AtoTerceiro', 'DeverGener', 'FormacaoQuad', 'LapsoTemp']

check commonPfactors = pF(L) ∩ pF(R):    True
check currPfactors   = pF(L) \ common:   True
check precPfactors   = pF(R) \ common:   True
```

As seis funções do artigo (12–17) correspondem uma a uma às seis chaves de
`partitions`: `common{Pro,Contra}` ↔ `common{P,D}factors`, `left{Pro,Contra}` ↔
`curr{P,D}factors`, `right{Pro,Contra}` ↔ `prec{P,D}factors`. As operações de
conjunto são as do artigo, e o `sorted` é apresentação.

**Veredito: adaptação legítima, e o docstring já sabe por quê.** O argumento decisivo
é que as Defs. 12–17 são operações puramente conjuntistas sobre `pFactors(·)` e
`dFactors(·)`. Nada nelas depende de o argumento ser um precedente: `outcome` não
aparece; a assinatura `currentcases × precedents → 2^factors` (p. 1149) é uma
restrição de tipo, não de conteúdo. Toda a carga de stare decisis está nos
**esquemas** que consomem as partições — CS1 e CS2 exigem `outcome(prec) = Plaintiff`
(pp. 1151, 1153), U1.1 e U2.1 exigem uma partição não vazia para distinguir
(pp. 1152, 1154) — e **nenhum desses esquemas está implementado**. Aplicar as
partições entre perspectivas, sem os esquemas, não pode inferir nada de nenhum
precedente, porque não há inferência alguma: é uma medida descritiva.

O que a adaptação **perde**, e o docstring diz corretamente (`factors.py:33-35`):
a assimetria. No artigo `curr` e `prec` não são intercambiáveis — `currPfactors`
*fortalece* a posição do autor e `precPfactors` a *enfraquece* (p. 1150), e a
direção depende de qual caso foi decidido. Entre perspectivas do mesmo caso não há
essa direção: `partitions(a,b)` e `partitions(b,a)` diferem só por troca de rótulos.
É por isso que `left`/`right` é a nomenclatura certa e `curr`/`prec` seria enganosa
— e o código usa `left`/`right`.

O que a adaptação **não perde**: nada da álgebra. Não distorce o que o artigo
define, porque não usa as partições para nada que o artigo defina com elas.

Uma ressalva, já registrada como D9: essa mesma adaptação — perspectiva = caso —
não foi aplicada a `cancellations`, que continua tomando o registro inteiro como
caso. As duas funções do mesmo módulo respondem a perguntas sobre unidades
diferentes.

---

## Suspeitas não confirmadas

**NÃO CONFIRMADA — "as preferências decidem o caso 003" no sentido do veredito
final.** A hipótese de trabalho era que a ordenação de `preferences.py` determina o
resultado do caso. Desligando `_preferences` e refazendo `decision_trace`, o traço é
**idêntico**:

```
SEM preferencias: relevancia por passo = [False, False, False, False, True, False]
COM preferencias: relevancia por passo = [False, False, False, False, True, False]
newly_blocked em [5] nos dois casos.
```

O que a preferência decide é o **conflito ⟨`dvesp_q0`, `dvgen_q1`⟩** — sem ela
`¬DeverEspec` e `¬cf2lrc_q5` não são justificados — mas o bloqueio final de
`LeReCa_OmiEstatal_Danos` é sobredeterminado: a ponte do passo 5 já o bloqueia
sozinha (2×2 em D2). A afirmação correta é "as preferências decidem a questão do
dever, e não decidem o resultado do traço"; a afirmação forte não se reproduz.
Isso **não** enfraquece o veredito de D1, que é sobre a estrutura (autoria e fase),
não sobre a magnitude do efeito.

**NÃO CONFIRMADA — `SILENT_NOTE` produzindo falso silêncio em `case-003-final`.**
Nenhum nó `sem movimento` é desenhado no caso real: `stf_final` não está em
`perspectives_in(record)` e só aparece se vier por `known` (o que
`_known_perspectives`, `perspective_view.py:32`, pode fazer a partir dos dossiês).
O defeito de D5 é estrutural e reproduzido no contraexemplo 4, mas **não se
manifesta no caso principal como ele está hoje**.

**NÃO CONFIRMADA — inconsistência prática entre `MappedAttack.phase` e
`confrontations`.** `MappedAttack.phase` (`perspectives.py:816-823`) devolve
"argumentação" para `sc_q6 ⇏ cf2lrc_q5` (porque `recorrente` está entre os
titulares), enquanto `confrontations` (`perspectives.py:861-866`) classifica a mesma
regra como "decisão" na linha cujo `source` é `voto_divergente`. As duas APIs dão
respostas diferentes para o mesmo ataque. O comentário de `perspectives.py:857-860`
declara isso deliberado e a leitura é defensável; não encontrei surface da interface
em que as duas apareçam lado a lado gerando contradição visível. Fica registrado
como risco, não como defeito.

**NÃO CONFIRMADA — impacto de D8 (pai direto vs. ancestral) em caso real.** A
hierarquia de `case-003-final` e de `case-003` é rasa: todo `abstract_factor` é
raiz, nenhum é filho de outro. Nenhum cancelamento é perdido nos dados atuais. A
divergência de definição está provada (contraexemplo 2); a consequência prática
não se observa no corpus existente.

---

## O que está fiel

Registro em separado o que a auditoria confirmou como correto, porque é substancial
e porque uma auditoria que só lista defeitos não é uma medida.

**Artigo A:**

- **Atribuição multi-titular.** `_holders` (`perspectives.py:94-107`) e `_admits`
  (`perspectives.py:110-116`) fazem uma regra sustentada por três vozes pertencer às
  três teorias. Sem isso, projetar por `perspective` daria teoria vazia para todos
  menos o primeiro titular. É o pré-requisito para que a decomposição por jogador
  signifique alguma coisa, e está correto.
- **Ataques lidos pelos titulares, não pelas caixas.** `MappedAttack`
  (`perspectives.py:778-823`) e `confrontations` (`perspectives.py:843-879`)
  corrigem uma distorção real: seis dos sete ataques de `case-003-final` são
  substantivamente entre adjudicadores e o diagrama mostrava uma parte numa das
  pontas. O `docstring` de `perspectives.py:781-792` descreve o problema com
  precisão e a solução funciona — a saída de `confrontations` marca corretamente
  `between_adjudicators=True` em três pares.
- **`derivable: False` distinto de verdicto negativo.** `verdicts`
  (`perspectives.py:181-208`) devolve `None` para uma tese que a teoria nem deriva,
  em vez de `False`. É uma distinção que o Artigo A também faz — status dialético
  tem três valores (§3.2, p. 6: justificado, derrotado, defensável) — e que a
  maioria das implementações perde.
- **`dvpre_q8`.** Argumento de prioridade movido como undercutter por um
  adjudicador, com alvo e fundamento explícitos, entrando no traço no passo do seu
  autor. É a leitura correta de §4.3 e funciona.
- **`new_rules` não repete regra já em jogo** (`perspectives.py:246-249`): um voto
  que só ecoa o que já estava lá não aparece como tendo movido. Correto, e é
  precisamente a leitura de "movimento" do artigo.
- **Recomputação do status a cada passo** (`perspectives.py:254`), que é o que §3.3
  (p. 7) descreve para o grafo dialético.
- **`unattributed_lrc_rules`** (`perspectives.py:436-449`): declara quanto da
  adjudicação o traço não consegue situar. Em `case-003-final` devolve `[]` — toda
  defesa tem autor. É a medida certa de honestidade e o caso passa nela.

**Artigo B:**

- **A álgebra de partições** reproduz as Defs. 12–17 literalmente (verificado acima),
  e a adaptação de domínio é declarada e defensável.
- **A cláusula de polaridade de `cancels`** é idêntica à Def. 20, e `neutro` não tem
  oposto em `OPPOSITE` (`factors.py:50`), logo nunca cancela — o que é a decisão
  certa dado D6.
- **A ausência de CS1–CS4, U1.1.x, U2.1.x, `substitutes`, `outcome` e `preferred`**
  é real, deliberada e declarada, com a razão correta: não há corpus de precedentes.
  Implementá-los sobre base vazia produziria argumentos com forma de stare decisis
  e sem conteúdo, e o módulo diz exatamente isso (`factors.py:17-20`).
- **`is_annotated`** (`factors.py:75-79`) e **`unclassified`**
  (`factors.py:169-176`): as duas existem para impedir que a interface leia ausência
  de anotação como afirmação sobre o caso. `case-005` volta `anotado: False` e não
  desenha balança nenhuma. É o comportamento certo.
- **`resolved_conflicts` exclui undercuts** (`preferences.py:298-299`, justificado em
  `preferences.py:283-285`) citando a Def. 2.10: undercut é independente de
  preferência. Correto, e é o tipo de detalhe que costuma passar batido.

---

*Auditoria conduzida em 2026-09-08 sobre `main` @ `130b3f6` + working tree.
Evidência: `case-003-final`, `case-003`, `case-005` e quatro contraexemplos
mínimos, todos reproduzidos no texto.*
