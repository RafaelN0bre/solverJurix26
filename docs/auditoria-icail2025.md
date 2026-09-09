# Auditoria — ICAIL 2025 × `src/aspic/solver.py`

Artigo auditado: Pisano, Prakken, Sartor & Liepina, *Modelling Cause-in-Fact in Legal
Cases through Defeasible Argumentation*, ICAIL 2025 (`docs/papers/ICAIL2025causation.pdf`,
lido integralmente, 10 páginas).

Implementação de referência dos autores:
`~/.claude/knowledge/jurix26/repos/tuProlog--arg2p-kt/causality-solver/src/commonMain/kotlin/it/unibo/tuprolog/argumentation/causality/libs/CausalitySolver.kt`
(daqui em diante `CausalitySolver.kt`) e os oráculos em
`causality-solver/src/commonTest/kotlin/it/unibo/tuprolog/argumentation/causality/BasicTest.kt`.

Nossa implementação: `src/aspic/solver.py`, `src/aspic/sufficiency.py`,
`src/aspic/preferences.py`.

**Método.** Além da leitura definição por definição, foi construída uma
reimplementação Python *fiel à referência* do `ness/3` completo — `supporters`/
`getSupports` com o guard `chain`, as três famílias de `generate_interventions/3`,
`checkIntervention` com a exigência de atacante IN, e a minimalidade de
`checkCausalityICAIL25` — rodando sobre o nosso próprio `ArgumentationFramework`.
Isso permite diferenciar *nós × referência* mantendo tudo o mais constante. Essa
reimplementação reproduz **100% dos oráculos de `BasicTest.kt`** — 40 asserções
portadas (18 `isNessCause` + 22 `isNessIntervention`, de
`causalityTestRefinedTheory1/2`, `causalityTestComplex`, `causalityTest`,
`asbestos`, `tobacco`, `doubleShooting`, `leukaemia`, `brakes`, `soldiers`) —, o
que dá confiança de que ela é de fato o comportamento dos autores.

Suíte do repositório no momento da auditoria: `286 passed, 1 xfailed`.

---

## Resumo

| | |
|---|---|
| Definições auditadas | 13 (Def. 2.2, 2.3, 2.4, 2.6, 2.8, 2.10, 2.11, 2.12, rotulagem fundamentada da §2.1, Def. 3.3, 4.2, 4.3 + Def. 3.5 do ICAIL 2026, usada como referência cruzada) |
| Fiéis ao artigo | 11 |
| Divergentes | 2 — Def. 3.3 (parcial: divergimos da *referência*, não do artigo) e Def. 4.3 (divergimos da *referência*, em duas direções opostas) |
| Divergências que mudam linha publicada no repositório | **0** |

O achado principal é duplo e não é o que estava documentado:

1. **A lacuna conhecida (famílias de intervenção) é menor do que o `xfail` afirma.**
   Das três famílias de `generate_interventions/3`, a família (b) — o *undercut* de
   uma regra — **não é uma lacuna nossa**: na nossa notação o literal de undercut de
   `r2` se escreve `¬r2`, que é exatamente `compl("r2")`, então a família (a) já a
   cobre. Rodamos o oráculo `isNessCause(r2, -b, true)` de `causalityTestComplex` e
   nós acertamos. Só a família (c) (intervenções conjuntas) falta.

2. **A afirmação "todo veredito positivo nosso é positivo na referência" é falsa.**
   Está escrita em `tests/test_reference_fidelity.py:122`. Em fuzzing sobre 366
   teorias acíclicas aleatórias, **115** pares (φ,ψ) têm `ours=True` e
   `ref=False`, contra 58 no sentido inverso. A causa é a exigência de atacante
   **IN** em `checkCausalityICAIL25` — e nesse ponto **nós estamos com o texto do
   artigo e a referência é mais estrita do que a própria Def. 4.3**.

Nenhuma das duas muda qualquer veredito publicado: nos 6 casos de
`src/aspic/examples.py` e nos 3 casos de `data/translated/*/case.json`, varrendo
**todos** os literais de cada teoria contra o efeito do caso (159 pares (φ,ψ)),
há **3 divergências**, todas em `case-003-final`, todas em pares *não publicados*,
e todas causadas por um terceiro ponto — a amplitude do `getSupports` da referência,
onde de novo o artigo está do nosso lado.

---

## Tabela definição → implementação → veredito

| Definição (ICAIL 2025) | Nossa implementação | Referência | Veredito |
|---|---|---|---|
| Def. 2.2 — Argumentation System (`L`, `Rs`, `Rd`, `n`) | `solver.py:90-118` (`Rule`), `solver.py:299-330` (`_parse_rule`/`_parse_rules`); `n(r)` é o próprio id, `¬n(r)` é a string `"¬<id>"` | `RuleParserBase` + `undercut/1` | **Fiel**, com ressalva de notação (abaixo) |
| Def. 2.3 — Knowledge base (`Kn`, `Kp`) | `solver.py:262-263` (`self.premises` = Kp, `self.axioms` = Kn) | idem | **Fiel** |
| Def. 2.4 — Argumentation theory | `solver.py:246-297` (`__init__`) | `Arg2pSolverFactory.causality(theory)` | **Fiel** |
| Def. 2.6 — Arguments | `solver.py:334-427`; guard de aciclicidade em `solver.py:393-395` | motor Prolog do `core/` | **Fiel ao texto da Def. 2.6**, mais fraco que a exigência de grafo acíclico da §2.2 (ver Suspeitas) |
| Def. 2.8 — Attack (undercut/rebut/undermine) | `solver.py:463-511`: undercut `:473-480`, rebut `:482-489`, undermine `:491-499` | `core/.../attack.pl` | **Fiel** |
| Def. 2.10 — Defeat | `solver.py:513-540`; undercut sai antes de qualquer consulta a preferência (`:518-521`) | `checkIntervention` usa `graph.attacks` já resolvido | **Fiel** (verificado rodando) |
| Def. 2.11 — Basic argument ordering | `solver.py:433-455` (`_is_weaker`), refinada por `preferences.py:223` (`is_weaker`) → `preferences.py:210` (`compare`) | flags `orderingPrinciple/orderingComparator` | **Fiel**; as cláusulas básicas vêm primeiro e nunca são sobrescritas |
| Def. 2.12 — AF a partir do SAF | `solver.py:513-540` produz `self.defeats`, que é `D` | idem | **Fiel** |
| §2.1 — Rotulagem/extensão fundamentada | `solver.py:542-583` (`compute_grounded_extension`, `_is_defended`) | `core/.../labellings/argument/grounded` | **Fiel** (ponto fixo mínimo da função característica) |
| Def. 3.3 — Explanations, support sets | `solver.py:593-673` (`_subset_minimal`, `_minimal_explanations`, `support_set_for_argument`, `support_set`) | `CausalitySolver.kt:61-99` (`supporters`, `getSupports`) | **Fiel ao artigo; divergente da referência** — ver Divergência D2 |
| Def. 4.2 — Axiom-expansion `K+L` | `solver.py:675-683` (`axiom_expand`) | `CausalitySolver.kt:114` injeta `:->(fkN, X)` | **Fiel ao artigo** (Def. 4.2 manda `L` para `Kn`) e **equivalente na prática** à referência — ver Fidelidades confirmadas |
| Def. 4.3 — Cause (NESS) | `solver.py:685-722` (`ness_cause`) | `CausalitySolver.kt:182-198` (`checkCausalityICAIL25`) + `:137-159` (`getInterventions`) | **Divergente da referência em duas direções** — ver D1 e D3 |
| Def. 3.5 do ICAIL 2026 — but-for | `solver.py:724-750` (`but_for`) | `CausalitySolver.kt:202-214` (`checkButFor`) | **Fiel** (fora do escopo do ICAIL 2025, conferido por completude) |

Módulos auxiliares: `src/aspic/sufficiency.py` **não decide nada** — só decompõe
conjuntos suficientes por fecho dedutivo monotônico (`sufficiency.py:38-60`), e o
docstring diz isso explicitamente. Não há como ele divergir de nenhuma definição do
artigo, porque não implementa nenhuma.

---

## Divergências confirmadas

### D1 — Def. 4.3: a referência exige um atacante rotulado `in`; nós (e o artigo) não

**O que o artigo diz.** Def. 4.3: *φ é causa de ψ sse existe um conjunto
subset-minimal de literais `L` e uma explicação `E` de um argumento
`A ∈ G(AF_AT)` com `Conc(A) = ψ` tais que `¬φ ∈ L` e `E ⊄ G(AF_AT+L)`.* A condição
é **só** "algum membro da explicação saiu da extensão fundamentada". A prosa da §4
fala em "a non-overruled defeater" — e *overruled* no vocabulário do próprio artigo
(§2.1) é `out`; um derrotador `und` é não-overruled.

**O que a referência faz.** `CausalitySolver.kt:117-121`, dentro de
`checkIntervention`: entre os membros do suporte que ficaram `out`/`und`, coleta
`attackers(...).filter { b -> b.label == "in" }`, e `checkCausalityICAIL25`
(`:190`) exige `attackers.isNotEmpty()`. Ou seja: só conta se o argumento que
derrubou o suporte estiver ele próprio `in`.

**O que nós fazemos.** `solver.py:713-722`: comparamos as assinaturas do suporte
original com as assinaturas presentes na nova extensão. Basta sair.

**Contraexemplo mínimo (3 regras), rodado:**

```
Kp = {p, p2};   r1: p => e ;   r6: p2 => e ;   r2: x => ¬e
consulta: ness('¬x', 'e')   →   intervenção {x}
```

```
  [base] ext-conclusions=['e', 'e', 'p', 'p2']
   base Supp(e) = ['A2', 'A3']
   after intervention {x}: IN args = [('A0', 'p'), ('A1', 'p2'), ('A2', 'x')]
     A3 concl=e rules=['r1'] in=False
     A4 concl=e rules=['r6'] in=False
     A5 concl=¬e rules=['r2'] in=False
   ours ness('¬x','e') = True
   ref  ness('¬x','e') = (False, None)
```

`A5` (o `¬e` habilitado pela intervenção) e os dois argumentos para `e` se rebatem
mutuamente: ciclo par, todos ficam `und`. O suporte saiu da extensão — o artigo diz
"é causa"; a referência diz "não é", porque o derrotador não está `in`.

**Impacto medido.**
- Fuzzing, 366 teorias acíclicas aleatórias, intervenção *singleton* nos dois lados
  (para isolar esta questão das famílias de intervenção): **151 pares divergentes,
  145 deles `ours=True` / `ref=False`** — todos por este motivo.
- **Nos casos do repositório: 0.** Nenhum dos 159 pares (φ,ψ) varridos nos 9
  frameworks do repositório cai nesse padrão.

**Quem está certo:** nós, em relação ao texto da Def. 4.3. Vale registrar no
código que a divergência é *deliberada e a favor do artigo*, e não uma lacuna.

---

### D2 — Def. 3.3: a referência coleta suporte também a partir de argumentos não justificados

**O que o artigo diz.** Def. 3.3: uma *explanation* é o conjunto de argumentos do
proponente numa estratégia vencedora **mínima** para `A` estar na extensão
fundamentada; `Supp(A,E)` é a união das explicações de `A`; e
`Supp(ψ,E) = ∪ { Supp(A,E) : A ∈ E, Conc(A) = ψ }`. Um argumento fora de `E` não
tem estratégia vencedora, logo não tem explicação, logo não contribui.

**O que a referência faz.** `CausalitySolver.kt:91-99`, `getSupports`:
`graph.labellings.filter { equalTerms(it.argument.conclusion, effect) }` — **sem
filtro de rótulo**. Um argumento `out` para o efeito entra na recursão; `supporters`
(`:61-76`) devolve `[]` para a cabeça não-`in`, mas **continua descendo** por
`attackers(attackers(x))`, e recolhe lá embaixo qualquer argumento `in`. Assim,
defensores de argumentos *derrotados* para o efeito acabam no conjunto-suporte.

**O que nós fazemos.** `solver.py:661-673` (`support_set`) itera só sobre
`arg_id in extension` com `conclusion == formula`.

**Contraexemplo rodado — e ele está no repositório**, `case-003-final`:

```
--- arguments concluding Danos ---
  A12 in=False rules=['r0', 'r2', 'r3', 'r4'] prem=['OmiEstatal']
  A13 in=False rules=['r1', 'r2', 'r3', 'r4'] prem=['OmiEstatal', 'RegFechado']
  A19 in=True  rules=['r6', 'r3', 'r4'] prem=['FormacaoQuad', 'LapsoTemp']

--- our Supp(Danos) (Def 3.3, justified args only) ---
  A19: Danos  rules=['r6', 'r3', 'r4'] prem=['FormacaoQuad', 'LapsoTemp']

--- reference getSupports(Danos) (no label filter on the head) ---
  A17: ¬r5  rules=['r8'] prem=['¬ProvCabiveis']
  A19: Danos  rules=['r6', 'r3', 'r4'] prem=['FormacaoQuad', 'LapsoTemp']

  extra in reference: ['A17']
```

`A12` (Danos pela cadeia `r2`) está `out`, undercutado pelos argumentos `¬r2`
(`r5`, `r7`); um desses `¬r2` é por sua vez atacado por `A17` (`¬r5`, via `r8`, da
premissa `¬ProvCabiveis`), que está `in`. A referência puxa `A17` para o suporte de
`Danos` a partir de um argumento que nunca esteve justificado.

**Consequência direta, também rodada:**

```
### ness('¬ProvCabiveis', 'Danos'): ours=False ref=(True, ('a', ('ProvCabiveis',)))
### ness('r8',            'Danos'): ours=False ref=(True, ('a', ('¬r8',)))
### ness('¬r5',           'Danos'): ours=False ref=(True, ('a', ('r5',)))
```

**Impacto medido.** Estes **3 pares são as únicas divergências ours × referência em
todo o repositório**. Nenhum deles é uma consulta publicada: as consultas de
`case-003-final` são `(OmiEstatal, Danos)`, `(FugaPreso, Danos)` e
`(Latrocinio, Danos)`, e nas três nós e a referência concordamos
(`False/False/True`). No fuzzing, `Supp` diverge em 3 de 366 teorias.

**Quem está certo:** nós, de novo em relação ao texto da Def. 3.3.

---

### D3 — Def. 4.3: só implementamos uma das famílias de intervenção (e é uma, não duas)

**O que o artigo diz.** Def. 4.3 quantifica sobre "um conjunto subset-minimal de
literais `L`" com `¬φ ∈ L` — **`L` não precisa ser unitário**. A §4 dá os três modos
em que φ pode ser causa, e o modo (3) ("`¬φ` habilita ou defende um novo argumento
`B` que derrota `C ∈ E`") é exatamente o que exige `L` conjunto.

**O que a referência faz.** `CausalitySolver.kt:346-356`,
`generate_interventions/3`, três famílias:

```prolog
generate_interventions(_, S, [CS])          :- compl(S, CS).
generate_interventions(_, S, [undercut(S)]) :- S \= -_.
generate_interventions(R, S, SUP)           :- compl(S, CS), unused_premises(R, UP),
                                               subsets(UP, SUP), member(CS, SUP).
```

com `unused_premises/2` (`:361-364`) = os antecedentes das regras que não dispararam.

**O que nós fazemos.** `solver.py:711` — apenas `axiom_expand([negate_literal(phi)])`,
o singleton.

**Correção ao que está documentado.** O docstring de
`tests/test_reference_fidelity.py:91-124` afirma que faltam as famílias (b) e (c).
**Falta só a (c).** Na nossa notação o literal de undercut da regra `r` é `¬r`, que é
literalmente `compl(r)`; `_identify_attacks` (`solver.py:473-480`) casa
`attacker.conclusion == f"¬{sub.top_rule.id}"`. Logo a família (a) já produz a
intervenção da família (b). Rodado, sobre a teoria de `causalityTestComplex`:

```
OK ours=True  OK ref=True  exp=True   ness('r2','¬b')  [complex]  witness=('a', ('¬r2',))
```

**Oráculos da referência que reprovamos, todos por falta da família (c):**

```
XX ours=False OK ref=True  exp=True   ness('b','c')   [theory2]  witness=('c', ('¬a', '¬b'))
XX ours=False OK ref=True  exp=True   ness('¬d','¬b') [complex]  witness=('c', ('d', 'e'))
XX ours=False OK ref=True  exp=True   ness('¬e','¬b') [complex]  witness=('c', ('d', 'e'))
```

(o primeiro é o `xfail` de `tests/test_reference_fidelity.py:85-125`; os outros dois
não estão portados hoje e valeria portá-los.)

**Impacto medido nos casos do repositório: 0 linha muda.**

```
===== examples.py::asbestos            NO DIFFERENCE   (14 literais)
===== examples.py::double_shooting     NO DIFFERENCE   (16 literais)
===== examples.py::leukaemia           NO DIFFERENCE   (12 literais)
===== examples.py::car_accident        NO DIFFERENCE   (13 literais)
===== examples.py::war_crime_soldier_shoots    NO DIFFERENCE  (9 literais)
===== examples.py::war_crime_soldier_refuses   NO DIFFERENCE  (9 literais)
===== data/translated/case-003-final   3 DIFFs, todas por D2, nenhuma publicada
===== data/translated/case-003         NO DIFFERENCE   (23 literais)
===== data/translated/case-005         NO DIFFERENCE   (32 literais)

TOTAL DIVERGENT (phi,psi) PAIRS ACROSS REPO: 3
```

E as consultas publicadas, com veredito nosso, veredito da referência completa e
`but_for`:

```
asbestos:        ness(Ex1,Di)=T/T bf=F ; ness(Ex2,Di)=T/T bf=F ; ness(Ex3,Di)=T/T bf=F
double_shooting: ness(BuSh,GeDi)=T/T bf=F ; ness(DlSh,GeDi)=F/F bf=F
leukaemia:       ness(ChLe,ChDi)=T/T bf=T ; ness(¬PaCo,ChDi)=T/T bf=T
car_accident:    ness(¬DrPu,AcHa)=T/T bf=F ; ness(BrMa,AcHa)=F/F bf=F
soldier_shoots:  ness(SoSh,PrDi)=T/T bf=F
soldier_refuses: ness(¬SoSh,PrDi)=T/T bf=F
case-003-final:  ness(OmiEstatal,Danos)=F/F ; ness(FugaPreso,Danos)=F/F ; ness(Latrocinio,Danos)=T/T bf=T
case-003:        ness(FugaPreso,MorteVitima)=T/T bf=T ; ness(Latrocinio,MorteVitima)=T/T bf=T
case-005:        ness(¬AtdTemp,SeqIrr)=F/F ; ness(¬CelHum,SeqIrr)=F/F ;
                 ness(FatRisc,SeqIrr)=T/T bf=T ; ness(AgrQuad,SeqIrr)=T/T bf=T
```

**Por que o impacto é zero.** A família (c) só se ativa quando `¬φ` aparece como
antecedente de uma regra que **não disparou** (`member(CS, SUP)`, `SUP ⊆ UP`). Nos
casos do repositório, os literais consultados como causa ou já são premissas (logo
suas regras dispararam), ou seu complemento não é antecedente de nenhuma regra
inerte. É uma propriedade da modelagem dos casos, não uma garantia: uma
formalização futura com regras "adormecidas" de dois antecedentes reabre a lacuna.

**Nota lateral sobre a minimalidade.** Mesmo implementando (c), a nossa
minimalidade não deveria copiar a da referência: Def. 4.3 pede `L`
*subset-minimal*, enquanto `checkCausalityICAIL25:192-196` pede "nenhum subconjunto
próprio reproduz **todos os mesmos atacantes**" — condição diferente e não
equivalente. Para `L` unitário as duas são vacuamente satisfeitas, então hoje isso
não nos afeta.

---

## Suspeitas não confirmadas

### S1 — `in_progress` (nosso) × `chain` (referência) em Def. 3.3 — NÃO CONFIRMADA

Suspeitava-se que o guard `in_progress` de `solver.py:605-651` (adicionado antes da
recursão, `:626`, descartado depois, `:641`) não fosse equivalente ao `chain`
posicional de `CausalitySolver.kt:66`. **Não consegui construir contraexemplo, e há
razão estrutural para não existir**: em semântica fundamentada, todo argumento em
`E` entra numa rodada finita da função característica, e todo defensor entra numa
rodada estritamente anterior; logo a relação "X aparece na explicação de Y" é bem
fundada e nenhum ciclo de defesa entre membros de `E` é possível. Como
`_minimal_explanations` só desce para contra-atacantes filtrados por
`in grounded_extension` (`:634-637`), o guard nunca dispara num caminho legítimo.

O que foi rodado: o guard foi instrumentado e as 366 teorias acíclicas do fuzz
foram varridas. Ele dispara 14 vezes — sempre em ramos que já não contribuíam — e
`Supp` diverge da referência 3 vezes, **todas** explicadas por D2 (a amplitude do
`getSupports`), nenhuma pelo guard.

### S2 — Poluição do memo entre contextos de `in_progress` — NÃO CONFIRMADA

`_minimal_explanations` consulta `memo` (`:621`) **antes** de `in_progress` (`:623`),
e `memo` é compartilhado entre todos os argumentos de mesma conclusão dentro de
`support_set` (`:664-671`). Em tese isso permite cachear um resultado calculado sob
supressão e reusá-lo fora dela — dependência de ordem. **Não reproduzi**: pelo mesmo
argumento de boa fundamentação de S1, o valor cacheado sob supressão nunca difere do
valor sem supressão. Rodado: `support_set` com memo compartilhado × memo novo por
argumento, sobre as 366 teorias e todas as suas conclusões — **0 divergências**.

```
in_progress guard fired (non-memoised): 14
support_set order/memo dependence (shared vs fresh memo): 0
```

Ainda assim é uma fragilidade latente: a correção depende de uma propriedade da
semântica fundamentada, não do código. Se algum dia o solver ganhar outra semântica,
esse memo passa a ser um bug. Vale um comentário, não uma mudança.

### S3 — Def. 2.6, aciclicidade — divergência real, impacto nulo, NÃO ACIONÁVEL HOJE

O guard de `solver.py:393-395` é **literalmente** o que a Def. 2.6 escreve
(`ψ ∉ Conc({A1,…,An})`, só os antecedentes diretos), mas a §2.2 exige mais:
"arguments are constructed … by chaining inferences over `L` into **acyclic
graphs**". Numa teoria com ciclo isso produz argumentos que reentram no ciclo.
Rodado:

```
C. Def 2.6 acyclicity guard on a 2-cycle:  Kp={p}; c1: p => q; c2: q => p
     A0: p  rules=[]
     A1: q  rules=['c1']
     A2: p  rules=['c1', 'c2']
     A3: q  rules=['c1', 'c2', 'c1']
     A4: p  rules=['c1', 'c2', 'c1', 'c2']
```

`A2`, `A3` e `A4` não são argumentos ASPIC+ válidos (grafo cíclico). A terminação
não vem do guard, e sim do corte por ponto fixo do conjunto de conclusões
(`solver.py:373-375`) e do `MAX_ITER` (`solver.py:355`). **Impacto medido: zero** —
varridos os 9 frameworks do repositório, `arguments with a repeated conclusion in
Sub(A): 0`. Nenhuma formalização do repositório tem ciclo de literais. Marco como
não acionável, mas é a fragilidade estrutural mais séria do construtor: uma
formalização futura com ciclo produz silenciosamente um conjunto de argumentos
arbitrário (dependente de quando o ponto fixo de conclusões para), não um erro.

### S4 — Precedência de `n(r)` na notação — NÃO CONFIRMADA, mas anotada

`Rule.is_undercutter` (`solver.py:112`) usa `consequent.startswith("¬r")`, o que
classificaria `¬rico` como undercutter. **É código morto no solver**: o ataque real
(`solver.py:476`) casa contra o id concreto da regra, `f"¬{sub.top_rule.id}"`. O
único risco remanescente é um átomo do domínio homônimo de um id de regra — nenhum
caso do repositório tem isso.

---

## O que está fiel e vale registrar

**Def. 2.10/2.11 — preferência nunca toca undercut.** `_compute_defeats`
(`solver.py:513-540`) trata undercut e faz `continue` (`:518-521`) *antes* de
qualquer consulta a `_is_weaker`; e `_is_weaker` (`solver.py:433-455`) só delega ao
`PreferenceModel` (`preferences.py:223`) depois de esgotar as cláusulas básicas —
argumento estrito-e-firme nunca é mais fraco (`:447-448`), qualquer coisa
derrotável é mais fraca que estrito-e-firme (`:449-450`). Rodado com um modelo em
que o undercutter vale 1.0 e o alvo vale 100.0:

```
  [basic ordering]      defeats: rebut=2; undercut=1   undercut presente: True
  [preference-refined]  defeats: rebut=1; undercut=1   undercut presente: True
     rebut defeats: [('A3', 'e', 'A5')]     (o rebut fraco 1.0 → 100.0 caiu)
     justified (nos dois): ['p', 'q', 'u', '¬e', '¬rP']
```

A preferência derruba um rebut e **não** derruba o undercut. É exatamente Def. 2.10.

**Def. 4.2 — axioma × regra estrita de corpo vazio: equivalentes na prática.** O
artigo (Def. 4.2) manda `L` para `Kn`, que é literalmente o nosso `axiom_expand`
(`solver.py:675-683`); a referência injeta `:->(fkN, X)`
(`CausalitySolver.kt:114`), o que é um desvio *dela* em relação ao artigo. Testei a
equivalência construindo a variante por regra estrita (`fkN: ⊤ -> L`, com `⊤`
axioma) e comparando `ness_cause` em todos os literais de 12 teorias (os 6 casos de
`examples.py`, os 3 dossiês, e as 3 teorias de `BasicTest.kt`):

```
   axiom-expansion vs strict-empty-body-rule: 0 divergent pair(s) over 12 theories
```

**Def. 4.3 — o uso do conjunto-suporte no lugar da quantificação sobre explicações
está correto.** `ness_cause` (`solver.py:713-722`) checa se *alguma* assinatura de
`Supp(ψ)` saiu da extensão expandida. Como `Supp(ψ) = ∪ E`, "algum membro da união
saiu" ⟺ "∃E. E ⊄ G(AF+L)", que é exatamente o existencial da Def. 4.3. O docstring
já argumenta isso; confirmo.

**Def. 3.5 (ICAIL 2026) — `but_for` bate com `checkButFor`.** `solver.py:724-750`
faz "ψ justificado antes, ψ não justificado depois", que é
`CausalitySolver.kt:202-214`. Além dos oráculos de `BasicTest.kt` (theory1:
`but_for(a,c)=True`, `but_for(b,c)=False`; asbestos: os três `False`), verifiquei a
inclusão `but_for ⊆ ness` em todos os literais das 9 teorias do repositório:

```
   26 but-for causes checked, 0 violations
```

**Def. 2.8 — os três ataques estão certos, inclusive as condições laterais.** Rebut
e undercut só contra sub-argumentos com **regra de topo derrotável**
(`solver.py:474`, `:483`); undermine só contra premissa ordinária, axioma nunca
(`solver.py:465`, `:492`). O alvo do ataque é registrado no sub-argumento
(`Attack.target_subargument_id`, `solver.py:181-190`), que é o que Def. 2.10 compara
na ordenação — e é o que `_compute_defeats:523-524` de fato usa.

**Os oráculos dos autores que hoje passam.** Das 18 asserções `isNessCause` de
`BasicTest.kt` portadas para o nosso `ness_cause`, acertamos **15**; as 3 que
erramos são exatamente as da família (c) listadas em D3. As 22 asserções
`isNessIntervention` não têm contrapartida na nossa API pública (não expomos o
teste da intervenção separado da busca pela intervenção). Vale ampliar
`tests/test_reference_fidelity.py`, que hoje porta 6 asserções.

**`src/aspic/sufficiency.py` é honesto.** Não decide causa, só decompõe (fecho
dedutivo monotônico, `sufficiency.py:38-60`), e o docstring explica por que o antigo
`is_ness_cause` foi removido. Não há terceira noção causal escondida no repositório:
`ness_cause` e `but_for` são as duas, como em `ness/3` e `but_for/2`.

---

## Ações sugeridas (nenhuma aplicada — esta auditoria não alterou código)

1. Corrigir o docstring de `tests/test_reference_fidelity.py:91-124`: falta só a
   família (c), não (b) e (c); e a frase "todo veredito positivo nosso é positivo na
   referência" (`:122`) está invertida — medimos 115 casos `ours=True/ref=False`
   contra 58 no outro sentido.
2. Registrar D1 e D2 como divergências **deliberadas a favor do artigo**, não como
   dívida. Hoje não há nada no código dizendo isso.
3. Portar os oráculos `isNessCause` restantes de `BasicTest.kt`
   (`causalityTestComplex`, `causalityTest`, `tobacco`) — 12 asserções a mais, 2
   delas `xfail` pela família (c) — e, se `but_for` ganhar cobertura, os de
   `asbestos`.
4. Se a família (c) for implementada, usar a minimalidade da Def. 4.3
   (`L` subset-minimal), não a de `checkCausalityICAIL25`.
5. Considerar um guard de aciclicidade de verdade em `_apply_rule`
   (`ψ ∉ Conc(Sub(A_i))`, não só dos antecedentes diretos) — hoje inofensivo, mas é
   a única parte do solver que pode falhar em silêncio.
