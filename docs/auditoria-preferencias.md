# Auditoria — preferências × ASPIC+ e arg2p-kt

Data: 2026-09-08. Escopo: `src/aspic/preferences.py`, o gancho de ordenação em
`src/aspic/solver.py` e o efeito dos dois sobre `data/translated/case-003-final/`.
Nada de código foi alterado por esta auditoria; a suíte foi rodada no início e no
fim (`VIRTUAL_ENV= uv run pytest -q` → 286 passed / 1 xfailed no início, 289
passed / 3 xfailed no fim — a diferença vem de outras frentes que mexeram na
árvore durante o trabalho, e todos os números abaixo foram reconferidos contra o
estado final).

Fontes: a implementação de referência dos autores
(`~/.claude/knowledge/jurix26/repos/tuProlog--arg2p-kt/`, commit `2ca68fe`), os
PDFs de `docs/papers/`, e — obtido durante esta auditoria — o artigo primário
Modgil & Prakken, *A General Account of Argumentation with Preferences*
(arXiv:1804.06763, versão corrigida do AIJ 195 (2013) 361–397).

## Resumo

A nossa ordenação **não é** o weakest-link nem o last-link do ASPIC+. Ela é uma
terceira ordenação, construída sobre três escolhas que nenhuma das duas fontes
autoriza:

1. **ignora as premissas ordinárias** (`Prem_p`), que a Definição 21 de Modgil &
   Prakken exige comparar em conjunto com as regras, e que a referência dos
   autores implementa explicitamente (`superiorityRelation.pl:38-44`);
2. **remove da comparação as regras sem perfil**, em vez de deixá-las participar
   — e uma regra sem perfil, na semântica `sup` do arg2p, é justamente o que
   *bloqueia* a preferência;
3. no `last`, **anda para trás** até achar uma regra com peso, em vez de usar
   `LastDefRules(A)` como definido (`argumentationGraph.pl:113-114`).

As três, juntas, são exatamente o que faz `case-003-final` decidir. Rodando a
Definição 21 canônica sobre o mesmo `case.json`, a camada de relevância volta a
ficar **UNDEC**, isto é, ao mesmo resultado de não haver preferência nenhuma.
Rodando a política de regra neutra na leitura oposta (neutra = 0), o resultado
**inverte**. Ou seja: a decisão do caso principal não repousa nos pesos
⟨4, 5, 5⟩ escolhidos pelo leitor; repousa em três convenções de implementação
não documentadas como divergências.

O que **está** certo: preferência afeta rebut e undermine e nunca undercut; a
comparação é feita contra o sub-argumento atacado, não contra o argumento
inteiro; empate é incomparabilidade; a ordenação básica (Def. 2.11) tem
precedência sobre o modelo numérico; e o comparador que usamos, quando reduzido
a números, é o **elitist**, que é o padrão da referência.

## O que a referência dos autores faz

Todos os caminhos abaixo são relativos a
`~/.claude/knowledge/jurix26/repos/tuProlog--arg2p-kt/`.

### Onde a preferência entra no defeat

`core/src/jvmMain/resources/it/unibo/tuprolog/argumentation/core/core/graph/extensions/preferences.pl:11-15`
(extensão `standardPref`, "ASPIC+ static preferences"):

```prolog
standardPreferences(rebut, A, _, C)      :- \+ superiority::superiorArgument(C, A).
standardPreferences(undermine, A, _, C)  :- \+ superiority::superiorArgument(C, A).
standardPreferences(contrary_rebut, _, _, _).
standardPreferences(contrary_undermine, _, _, _).
standardPreferences(undercut, _, _, _).
```

`attack(T, A, B, C)` tem `A` = atacante, `B` = argumento atacado, `C` = o
sub-argumento em que o ataque cai. Só rebut e undermine consultam a
superioridade, e a comparação é **atacante × sub-argumento atacado** — não
atacante × argumento inteiro. Idêntico em
`.../graph/extensions/defPreferences.pl:28-29`.

### Os dois princípios

`core/src/jvmMain/resources/.../utils/superiorityRelation.pl:18-44`. Cada
argumento carrega a tripla `[LastDefRules, DefRules, DefPremises]`:

```prolog
superiorArgumentSupport(LastDefRulesA, _, DefPremisesA, LastDefRulesB, _, DefPremisesB, SupSet) :-
    orderingPrinciple(last),
    superior(LastDefRulesA, DefPremisesA, LastDefRulesB, DefPremisesB, SupSet).
superiorArgumentSupport(_, DefRulesA, DefPremisesA, _, DefRulesB, DefPremisesB, SupSet) :-
    orderingPrinciple(weakest),
    superior(DefRulesA, DefPremisesA, DefRulesB, DefPremisesB, SupSet).

superior([], PremisesA, [], PremisesB, SupSet) :-            % sem regras: só premissas
    weaker(PremisesB, PremisesA, SupSet).
superior(DefRulesA, _, DefRulesB, _, SupSet) :-              % last: premissas IGNORADAS
    orderingPrinciple(last), (DefRulesA \== []; DefRulesB \== []),
    weaker(DefRulesB, DefRulesA, SupSet).
superior(DefRulesA, [], DefRulesB, [], SupSet) :-            % weakest, ambos firmes
    orderingPrinciple(weakest), weaker(DefRulesB, DefRulesA, SupSet).
superior(DefRulesA, PremisesA, DefRulesB, PremisesB, SupSet) :-   % weakest: OS DOIS
    orderingPrinciple(weakest),
    (DefRulesA \== []; DefRulesB \== []), (PremisesA \== []; PremisesB \== []),
    weaker(DefRulesB, DefRulesA, SupSetA),
    weaker(PremisesB, PremisesA, SupSetB),
    utils::appendLists([SupSetA, SupSetB], SupSet).
```

A última cláusula é a resposta à pergunta 1(a): **sim, a referência compara as
premissas ordinárias sob weakest-link, e exige as duas comparações
conjuntamente**. Sob last-link as premissas só entram se os dois conjuntos de
últimas regras forem vazios.

### `LastDefRules` — não há walk-back

`core/src/jvmMain/resources/.../core/graph/argumentationGraph.pl:110-121`:

```prolog
defRules(Id, Def, Def)      :- parser::check_strict(Id), !.
defRules(Id, Def, [Id|Def]).
lastDefRules(Id, LDef, LDef) :- parser::check_strict(Id), !.
lastDefRules(Id, LDef, [Id])  :- Id \== none, \+ parser::check_strict(Id).
```

Se o topo é derrotável, `LastDefRules = [topo]` e **ponto**: não se olha para
trás. Se o topo é estrito, herda-se a união dos `LastDefRules` dos
sub-argumentos. É a Definição 5 do ASPIC+, literal. Resposta à pergunta 1(b):
**a referência não anda para trás**.

### Elitist e democrat

`superiorityRelation.pl:46-85`. `weaker(RulesA, RulesB)` = "A é mais fraco que B":

```prolog
weaker(RulesA, [], []) :- RulesA \== [].          % conjunto vazio é o mais forte

weaker(RulesA, RulesB, SupSet) :-                 % ELITIST
    orderingComparator(elitist),
    member(Rule, RulesA), allStronger(Rule, RulesB, SupSet), !.

weaker(RulesA, RulesB, SupSet) :-                 % DEMOCRAT
    orderingComparator(democrat), weakerDemo(RulesA, RulesB, SupSet).

weakerDemo([H|T], Rules, [Sup|SupSet]) :- singleStronger(H, Rules, Sup), weakerDemo(T, Rules, SupSet).
singleStronger(Target, Rules, sup(Rule, Target)) :- member(Rule, Rules), context_check(sup(Rule, Target)), !.
allStronger(Target, [Rule|Rules], [sup(Rule, Target)|SupSet]) :- context_check(sup(Rule, Target)), allStronger(Target, Rules, SupSet).
```

* **elitist** = `∃X ∈ Γ, ∀Y ∈ Γ′ : X < Y` — basta *um* elemento de Γ ser mais
  fraco que *todos* os de Γ′;
* **democrat** = `∀X ∈ Γ, ∃Y ∈ Γ′ : X < Y` — *todo* elemento de Γ tem alguém
  mais forte do outro lado.

Há um terceiro, `normal` (`superiorityRelation.pl:65-71`): basta existir um par
`sup(X, W)` com `W ∈ Γ`, `X ∈ Γ′`. É o mais permissivo dos três e não aparece na
literatura.

Os oráculos de `core/src/commonTest/.../unit/PreferencesTest.kt:110-200`
confirmam a leitura: com `sup(r3, r1)` só, `weakest`+`elitist` **não** decide
(`undResults`, 4 ataques); acrescentando `sup(r2, r1)` decide (`definedResults`,
2 ataques); e com `sup(r3, r0), sup(r2, r1)`, `elitist` não decide mas
`democrat` decide.

**Ponto decisivo para nós:** a relação de base é `sup(RuleX, RuleY)`, um fato
explícito e *parcial* sobre nomes de regras, não um número. Uma regra sobre a
qual não há nenhum `sup` é **incomparável**, e sob elitist ela *bloqueia* a
preferência quando está do lado forte (`allStronger` exige `sup` para todos os
elementos de Γ′).

### Defaults

`core/src/commonMain/kotlin/.../libs/utils/SuperiorityRelation.kt:38-52`:

```kotlin
object OrderingPrinciple  { fun default() = "last";    fun values() = listOf("last", "weakest") }
object OrderingComparator { fun default() = "elitist"; fun values() = listOf("elitist", "democrat", "normal") }
```

Confirmado em `core/src/commonMain/.../libs/basic/FlagsBuilder.kt:31-32,48-49`,
no `README.md:71-72` e em `doc/site/content/docs/predicate.md:65-75`. O
`predicate.md:65-67` também diz que `graphExtension(MODE)` é opcional e que **"if
absent, preference handling is disabled"** — ou seja, o comportamento de fábrica
do arg2p é o mesmo da nossa `preferences=None`.

## O que a literatura exige

### Modgil & Prakken 2013 — obtido

Baixado em `https://arxiv.org/pdf/1804.06763v1` (53 páginas; versão corrigida do
AIJ 195 (2013) 361–397). **Não está em `docs/papers/`** — ver Recomendação R6.

Definição 19 (comparações de conjunto), p. 21:

> 1. If Γ = ∅ then Γ ⋪ₛ Γ′;
> 2. If Γ′ = ∅ and Γ ≠ ∅ then Γ ◁ₛ Γ′;
> 3. if s = Eli: Γ ◁_Eli Γ′ if ∃X ∈ Γ s.t. ∀Y ∈ Γ′, X < Y.
> 4. if s = Dem: Γ ◁_Dem Γ′ if ∀X ∈ Γ, ∃Y ∈ Γ′, X < Y.
> Then Γ ⊴ₛ Γ′ iff Γ ◁ₛ Γ′ or Γ′ = Γ.

Definição 20 (last-link), p. 21:

> B ≺ A under the last-link principle iff
> 1. LastDefRules(B) ◁ₛ LastDefRules(A); or
> 2. LastDefRules(B) = ∅, LastDefRules(A) = ∅, and Prem_p(B) ◁ₛ Prem_p(A)

Definição 21 (weakest-link), p. 21:

> B ≺ A under the weakest-link principle iff:
> 1. If both B and A are strict, then Prem_p(B) ◁ₛ Prem_p(A), else;
> 2. If both B and A are firm, then DefRules(B) ◁ₛ DefRules(A), else;
> 3. **Prem_p(B) ◁ₛ Prem_p(A) and DefRules(B) ◁ₛ DefRules(A)**

E o parágrafo seguinte diz por que a cláusula 3 é assim — é uma *correção*
deliberada do ASPIC+ de 2010:

> Notice that in this paper we correct an anomaly in [40]'s definition of the
> weakest link principle, in which if both B and A are strict (…) there is an
> asymmetry in the way that premises and defeasible rules are compared. In
> Definition 21 above, the weakest link is defined so that the defeasible rules
> and ordinary premises are treated in the same way.

Ou seja: ignorar `Prem_p` no weakest-link não é uma simplificação inocente — é
exatamente a anomalia que os autores da definição foram corrigir.

Vale também a Definição 18 (p. 16), "reasonable argument orderings", que a
Definição 2.2 do artigo de fatores exige explicitamente ("The argument ordering
is reasonable as defined in [20, 21]"), e a Proposição 30 (p. 26), que vale para
`◁_Eli` e **não** para `◁_Dem`. Nossas três agregações (min, last, sum) com pesos
não negativos satisfazem 18-1-iii e 18-2 — a continuação estrita não altera o
conjunto de regras derrotáveis, e `∀i: Σ_{j≠i} s_j < s_i` é impossível para
n ≥ 2 com pesos ≥ 0. Não é aí que está o problema.

### ICAIL 2025 / ICAIL 2026

`docs/papers/ICAIL2025causation.pdf`, §2, Definições 2.10 e 2.11:

> Undercutting attacks succeed as defeats independently of preferences over
> arguments, since they express exceptions to defeasible rules. Rebutting and
> undermining attacks succeed only if the attacked argument is not stronger
> than the attacking argument (…). Below we assume the so-called **basic
> argument ordering** (…). For present purposes this is all we need.
>
> **Definition 2.10 [Defeat]** Argument A defeats argument B iff either A
> undercuts B; or A rebuts B on B′ and A ⊀ B′.
>
> **Definition 2.11 [SAF]** (…) ⪯ **is the basic ordering** on A, i.e., A ≺ B
> iff A is defeasible or plausible and B is strict and firm (…).

Dois pontos: (i) a Def. 2.11 **fixa** ⪯ como a ordenação básica — os artigos não
oferecem nenhuma máquina de preferências, então qualquer coisa que façamos aqui
é extensão nossa, e o `preferences.py` já diz isso; (ii) a Def. 2.10, como
impressa, menciona só o rebut, embora o parágrafo anterior fale de rebut *e*
undermine — a nossa leitura (undermine também depende de preferência) segue a
prosa e a referência, e é a certa.

`docs/papers/ICAIL2026causation.pdf` **não contém as palavras "ordering" nem
"basic"**, e "preferen" aparece uma única vez, na referência bibliográfica a
Modgil & Prakken. O artigo de 2026 não diz nada sobre ordenação.

### O artigo de fatores (Prakken, Wyner, Bench-Capon & Atkinson 2015)

`docs/papers/A_formalisation_of_argumentation_schemes_for_legal_case_based_reasoning_in_ASPIC_.pdf`
é relevante — mas na direção contrária à nossa. Def. 2.4:

> A successfully rebuts B if A rebuts B on B′ and A ⊀ B′. A successfully
> undermines B if A undermines B on φ and A ⊀ φ. A defeats B iff A undercuts or
> successfully rebuts or successfully undermines B.

(Note o `A ⊀ φ`: no undermine a comparação é contra a **premissa**, tratada como
argumento atômico — que é o que o nosso solver faz.) E, sobre a ordenação:

> Above we used an argument ordering in which all strict-and-firm arguments are
> preferred over all other arguments and **all non-strict-and-firm arguments
> have equal strength**.

Isto é, o artigo que mais precisa pesar razões (a preferência entre conjuntos de
fatores CATO) **mantém a ordenação plana** e põe a preferência na **linguagem
objeto**: `preferred(factorSet1, factorSet2)` é a conclusão de um esquema
derrotável (CS2), com rebuttals (R2.1) e undercutters próprios. É a alternativa
de modelagem que o nosso `case-003` já tem meio construída — `dvpre_q8:
DeverEspec => ¬sc_q6` é literalmente uma regra de preferência na linguagem
objeto — e é a que os autores usam. Ver Recomendação R5.

## Tabela: exigência → nossa implementação → veredito

| # | Exigência (fonte) | Nossa implementação | Veredito |
|---|---|---|---|
| 1 | Preferência afeta rebut e undermine, nunca undercut (ICAIL25 Def. 2.10; `preferences.pl:11-15`) | `solver.py:513-541` (`_compute_defeats`: `if attack.attack_type == "undercut": defeats.append(...)` incondicional) | **Confere** (contraexemplo C1) |
| 2 | A comparação é atacante × **sub-argumento atacado** (M&P §6; `preferences.pl:11`; fatores Def. 2.4) | `solver.py:521,524` (`target_sub = self.arguments[attack.target_subargument_id]`) | **Confere** |
| 3 | Estrito-e-firme nunca é mais fraco; tudo o mais é mais fraco que ele (M&P Def. 18-1; ICAIL25 Def. 2.11) | `solver.py:447-452` (cláusulas básicas antes do modelo) | **Confere** |
| 4 | Comparador `Eli` = `∃X ∀Y : X < Y` (M&P Def. 19.3; `superiorityRelation.pl:49-54`) | `preferences.py:192-193,216-219` (`min` + `<` numérico) — equivale a `Eli` **sobre o subconjunto perfilado** | **Confere no comparador, com ressalva** (ver #7) |
| 5 | Weakest-link compara **`DefRules` e `Prem_p`** conjuntamente (M&P Def. 21.3; `superiorityRelation.pl:38-44`) | `preferences.py:198-205` (`argument_strength` só olha `argument.defeasible_rules`); `Argument.ordinary_premises` (`solver.py:144`) nunca é consultado | **Diverge — D1** |
| 6 | Last-link usa `LastDefRules(A)`, sem olhar para trás (M&P Def. 20; `argumentationGraph.pl:113-114`) | `preferences.py:177-196` (`scored[-1]` sobre `contributing_rules(defeasible_rules)` — anda para trás e ignora a semântica de topo estrito) | **Diverge — D2** |
| 7 | Regra sem `sup` participa da comparação e pode bloqueá-la (`allStronger`, `superiorityRelation.pl:82-85`) | `preferences.py:164` (`profile is None or profile.is_neutral → None`) + `171-175` (`contributing_rules` filtra) | **Diverge — D3** |
| 8 | Empate/incomparabilidade ⇒ nenhum lado é preferido ⇒ os dois ataques são derrotas (M&P Def. 19-21, `⊴` só quando os conjuntos são idênticos) | `preferences.py:216-217` (`left_score == right_score → "incomparable"`) | **Confere** (contraexemplo C2) |
| 9 | Princípio padrão da referência: `last` (`SuperiorityRelation.kt:41`) | `preferences.py:124`, `schema.py:264` — padrão `weakest` | **Divergência de default, benigna** (ver S1) |
| 10 | `sum` não existe no ASPIC+ | `preferences.py:61,196` — já documentado como não-canônico em `preferences.py:55-58` | **Confere (declarado)** |
| 11 | O framework contrafactual deve diferir do original só pelo axioma acrescentado (ICAIL25 Def. 4.2) | `solver.py:675-683` (`axiom_expand` passa `preferences=self.preferences`) | **Confere** (contraexemplo C5) |

## Divergências confirmadas

Todas as saídas abaixo foram produzidas rodando; os scripts ficaram em
`/tmp/audit_pref.py` e `/tmp/audit_pref2.py`.

### D1 — o weakest-link ignora as premissas ordinárias, e é isso que decide o caso

`preferences.py:198-205` agrega só `argument.defeasible_rules`. A Definição 21.3
exige `Prem_p(B) ◁ₛ Prem_p(A) **and** DefRules(B) ◁ₛ DefRules(A)` sempre que os
dois argumentos tiverem regras **e** premissas — que é o caso de todos os
argumentos das duas camadas do `case-003` (`case.json` declara 6 premissas
ordinárias na camada CIF e 9 na LRC; `axioms: []` nas duas).

Como não há preordem declarada sobre `K_p`, ela é plana, e `Prem_p(B) ◁ₛ
Prem_p(A)` **nunca** vale para dois conjuntos não vazios. Logo, sob a Definição
21 canônica, nenhuma preferência se estabelece.

Rodado sobre `data/translated/case-003-final/case.json`, camada LRC:

```
V0 NOSSA (weakest, neutra pulada, premissas ignoradas)
    LRC: {'DeverEspec': 'OUT', '¬DeverEspec': 'IN', 'DeverGener': 'IN',
          'AtoTerceiro': 'IN', '¬cf2lrc_q5': 'IN', '¬sc_q6': 'OUT'}

V1 sem preferência nenhuma (ordenação básica, Def. 2.11)
    LRC: {'DeverEspec': 'UNDEC', '¬DeverEspec': 'UNDEC', 'DeverGener': 'IN',
          'AtoTerceiro': 'IN', '¬cf2lrc_q5': 'UNDEC', '¬sc_q6': 'UNDEC'}

V2 CANÔNICA Def. 21 (weakest + Prem_p, Eli, não-perfilada incomparável)
    LRC: {'DeverEspec': 'UNDEC', '¬DeverEspec': 'UNDEC', 'DeverGener': 'IN',
          'AtoTerceiro': 'IN', '¬cf2lrc_q5': 'UNDEC', '¬sc_q6': 'UNDEC'}
```

**V2 ≡ V1.** Sob a Definição 21 tal como publicada, o modelo de preferências do
`case-003` é inerte: a camada de relevância volta inteira para UNDEC.

*Impacto na tabela publicada:* nenhum, e isso merece ser dito. As três linhas de
`scripts/run_translated.py case-003-final` (NESS/but-for/relevância × corte)
saem idênticas nas seis variantes testadas, porque a relevância de
`OmiEstatal → Danos` já é `False` pela camada cause-in-fact (`CaFa_OmiEstatal_Danos`
não é premissa da camada LRC — `ness(OmiEstatal, Danos) = False`), e não pelo
conflito ⟨q0, q2⟩. O que muda é o **rótulo** e, portanto, a *razão* que a
formalização dá: OUT/IN ("a corte pesou e o dever genérico prevaleceu") contra
UNDEC ("a formalização não resolve o conflito"). É a diferença entre reproduzir
o voto e reproduzir só o dispositivo.

*Direção do erro:* **não é conservadora.** Retirar um conjuntivo de uma
conjunção só pode fazer a preferência valer em mais casos, nunca em menos. Nós
declaramos preferências onde o ASPIC+ canônico não declara nenhuma.

### D2 — o last-link anda para trás, e o `LastDefRules` de topo estrito está errado

`preferences.py:177-196` documenta o walk-back e o justifica. Nem a Definição 20
nem `argumentationGraph.pl:113-114` fazem isso: se a última regra é derrotável,
`LastDefRules = {ela}`, e se ela não tem `sup`, não há preferência.

Contraexemplo mínimo (`KB = {p, q}`, `a: p ⇒ X` com peso 4, `b: q ⇒ Y` com peso
10, `c: Y ⇒ ¬X` **sem perfil** — a forma exata de ⟨q0, q2⟩):

```
argumento ¬X: defeasible_rules = ['b', 'c'] | top_rule = c
LastDefRules canônico = [c] (regra neutra) -> sem preferência
nosso strength_of_rules  = 10.0            (anda de trás pra frente até b=10)
labels com o nosso last-link: {'X': 'OUT', 'Y': 'IN', '¬X': 'IN'}
```

E no `case-003`:

```
V6 last-link CANÔNICO (LastDefRules, sem walk-back)
    LRC: {'DeverEspec': 'UNDEC', '¬DeverEspec': 'UNDEC', ...}
V7 NOSSO last-link (walk-back)
    LRC: {'DeverEspec': 'OUT', '¬DeverEspec': 'IN', ...}
```

**Segundo defeito, mais grave, no mesmo método:** quando o topo é *estrito*,
`LastDefRules(A)` é a **união** dos `LastDefRules` dos sub-argumentos, e o
comparador `Eli` roda sobre esse conjunto. Nós pegamos `scored[-1]` da lista
cumulativa `defeasible_rules`, isto é, **um** elemento arbitrário da união — e
qual elemento depende da **ordem textual dos antecedentes da regra estrita**:

```
s: X AND Y -> Z  -> def_rules ['a', 'b'] | nosso last = 9.0
s: Y AND X -> Z  -> def_rules ['b', 'a'] | nosso last = 1.0
```

Trocar `X AND Y` por `Y AND X` — uma reescrita semanticamente vazia — muda a
força do argumento de 9 para 1. E o veredito da ordenação chega a inverter:

```
teoria: KB={p,q,r}; s: X AND Y -> Z (estrita); a: p=>X (1), b: q=>Y (9), z: r=>¬Z (5)
C4b NOSSO last-link   : {'Z': 'IN',  '¬Z': 'OUT'}   (last = 9 > 5 -> Z mais forte)
C4b CANÔNICO last+Eli : {'Z': 'IN',  '¬Z': 'IN' }   ({a=1,b=9} ◁_Eli {z=5} -> Z mais fraco)
```

`case-003` não tem regra estrita, então isso não a atinge hoje; atinge qualquer
caso futuro que tenha, e atinge as cinco formalizações de `aspic/examples.py` no
dia em que alguém lhes der um `PreferenceBlock` com `principle: "last"`.

### D3 — a política de regra neutra pode **inverter** um resultado

`preferences.py:164` faz `rule_strength` devolver `None` para regra sem perfil, e
`171-175` a remove antes de agregar. A justificativa em `preferences.py:33-35` e
`177-186` é "um passo de encadeamento não deve contar duas vezes". **Não há
respaldo em nenhuma das fontes**: na referência, a ausência de `sup` não remove a
regra do conjunto — ela a torna incomparável, e sob `elitist` uma regra
incomparável do lado forte *impede* a preferência (`allStronger` exige
`context_check(sup(Rule, Target))` para **todo** elemento,
`superiorityRelation.pl:82-85`).

Três leituras da mesma teoria mínima (`a: p ⇒ X` peso 4, `b: q ⇒ Y` peso 10,
`c: Y ⇒ ¬X` sem perfil):

```
nossa (pula neutra)                      -> {'X': 'OUT',   '¬X': 'IN'}
neutra = 0                               -> {'X': 'IN',    '¬X': 'OUT'}
neutra incomparável (Eli, como o arg2p)  -> {'X': 'UNDEC', '¬X': 'UNDEC'}
```

Três vereditos diferentes para os mesmos pesos. E no `case-003`:

```
V0 nossa (pula)          : DeverEspec OUT   | ¬DeverEspec IN     (força 4 x 10)
V3 incomparável (arg2p)  : DeverEspec UNDEC | ¬DeverEspec UNDEC
V4 neutra = 0            : DeverEspec IN    | ¬DeverEspec OUT
```

**A política não é conservadora: ela inverte o resultado.** Sob "neutra = 0" —
uma leitura ao menos tão natural quanto a nossa, já que uma regra sem eixo
doutrinário é uma regra que não sustenta nada — `dvgen_q2` puxa a força do
argumento por `¬DeverEspec` para 0, e é o **dever específico** que prevalece,
que é o oposto do que a nossa formalização publica.

Note ainda o efeito colateral: como só as regras perfiladas entram na agregação,
o nosso "weakest-link" no `case-003` degenera em "a força da única regra
perfilada do ramo", que sob `dvgen_q1 = 10` é indistinguível de `sum` e de
`last` — as variantes V0, V5, V7, V8 e V9 (democrat) dão todas o mesmo rótulo.
Isto é, no caso principal os três princípios de agregação **não são
distinguíveis**, e a escolha `principle: "weakest"` registrada em
`case.json:596` não está fazendo trabalho nenhum.

### O ponto de virada, medido

`preferences.sensitivity` / `flip_point` (`preferences.py:325-357`) informam
corretamente onde o caso vira, e a nota em `case.json` ("o ponto de virada está
em 10") está certa:

```
peso dever_especifico=  9 -> dvesp_q0=9.0  x dvgen_q1=10.0 | DeverEspec OUT   ¬DeverEspec IN
peso dever_especifico= 10 -> dvesp_q0=10.0 x dvgen_q1=10.0 | DeverEspec UNDEC ¬DeverEspec UNDEC
peso dever_especifico= 11 -> dvesp_q0=11.0 x dvgen_q1=10.0 | DeverEspec IN    ¬DeverEspec OUT
```

O empate em 10 produzindo UNDEC (pergunta 4) **é o comportamento correto**: pela
Definição 19, `Γ ⊴ₛ Γ′` só quando `Γ ◁ₛ Γ′` ou `Γ′ = Γ` (identidade de
conjuntos), então força igual com conjuntos diferentes é genuína
incomparabilidade — nem `≺`, nem `≈`. A mensagem de `explain()`
(`preferences.py:234-235`, "os dois seguem incomparáveis") está tecnicamente
correta.

### Verificações que passaram

**C1 — undercut é imune a preferência.** `KB = {p, q}`, `forte: p ⇒ x` com peso
100, `fraco: q ⇒ ¬forte` com peso 1:

```
força(forte) = 100.0   força(fraco) = 1.0
defeat undercut A3 -> A2 | undercutting always succeeds
labels: {'x': 'OUT', '¬forte': 'IN'}
resolved_conflicts (deve ignorar undercut): []
```

O undercut 100× mais fraco derrota. Trocando `¬forte` por `¬x` (mesmo conflito
como rebut), a preferência decide e `x` fica IN. Bate com
`preferences.pl:11-15` e com a Def. 2.10.

**C2 — empate.** Com `forte` e `fraco` ambos com peso 7, os rótulos e a contagem
de derrotas (2 de 2) são idênticos aos do framework sem modelo nenhum.

**C5 — propagação para o contrafactual (pergunta 6).** É **necessária**, não só
correta. Sem propagar, o framework expandido perde a ordenação e conflitos que
estavam resolvidos voltam a UNDEC, o que quebra o suporte por um motivo que nada
tem a ver com a intervenção:

```
teoria: a: p=>X (10), b: q=>¬X (4), d: X=>W;  intervenção sobre 's' (irrelevante)
base labels:                    {'W': 'IN', 'X': 'IN', '¬X': 'OUT'}
ness(s, W) COM propagação    :  False        <- correto
ness(s, W) SEM propagação    :  True         <- falso positivo
labels do expandido sem prop :  {'W': 'UNDEC', 'X': 'UNDEC', '¬X': 'UNDEC'}
```

A ICAIL 2025 Def. 4.2 define a expansão como `K + L` — só a base de
conhecimento muda; a teoria de argumentação, incluindo ⪯, é a mesma. E a
referência faz o equivalente: `checkIntervention` injeta a intervenção como
regra estrita sem corpo no *mesmo* contexto, com as mesmas flags
(`causality-solver/src/commonMain/.../CausalitySolver.kt`). O argumento *contra*
que se poderia levantar — "os pesos foram calibrados no caso, não no
contrafactual" — não procede, porque a ordenação é sobre **regras**, não sobre
argumentos, e o conjunto de regras é idêntico nos dois frameworks
(`solver.py:678-683` reusa `self._model_raw`).

**C6 — a camada cause-in-fact do `case-003` não usa preferência nenhuma.**
Apesar de `r1`, `r5`, `r6` e `r7` terem perfil:

```
ataques: 13 | derrotas: 13
conflitos decididos por preferência na CIF: NENHUM
derrotas sem preferência: 13 | extensões iguais? True
```

Os quatro conflitos da camada CIF são todos **undercuts** (`r5`, `r7`, `r8`), que
por definição ignoram preferência; `r0`/`r1` e `r2`/`r6` concluem o *mesmo*
literal, e portanto não se atacam. Os perfis de `r1`, `r5`, `r6` e `r7` em
`case.json:617-685` são **decorativos**: eles descrevem uma ponderação que a
formalização não usa. É honesto documentá-los, mas a interface não deveria
sugerir que decidiram algo.

## Suspeitas não confirmadas

**S1 — "estamos usando um comparador alternativo sem dizer".** **NÃO
CONFIRMADA.** Reduzido a números, `A ≺ B ⟺ força(A) < força(B)` com agregação
`min` é exatamente `◁_Eli`: para uma preordem total, `∃X ∈ Γ ∀Y ∈ Γ′ : X < Y`
equivale a `min Γ < min Γ′`. E `Eli` é o **padrão** da referência
(`SuperiorityRelation.kt:49`) e a comparação para a qual valem a Proposição 30 e
o Teorema 34 de Modgil & Prakken. `democrat` corresponderia a comparar
**máximos**, não mínimos; rodado sobre o `case-003` (variante V9), dá o mesmo
rótulo que a nossa, porque cada ramo tem uma única regra perfilada. A ressalva é
a de D3: a equivalência com `Eli` só vale sobre o subconjunto perfilado.

**S2 — "o default `weakest` diverge do default `last` da referência".**
**CONFIRMADA COMO FATO, NÃO COMO ERRO.** `SuperiorityRelation.kt:41` tem
`default() = "last"`; `preferences.py:124` e `schema.py:264` têm `weakest`. Os
dois princípios são igualmente canônicos (M&P Defs. 20 e 21) e o `PreferenceBlock`
deixa escolher. Vale registrar a diferença de default na documentação, não
mudá-la.

**S3 — "o `sum` viola as ordenações razoáveis (M&P Def. 18)".** **NÃO
CONFIRMADA.** Com pesos não negativos, `sum` satisfaz 18-1-iii (continuação
estrita não muda o conjunto de regras derrotáveis) e 18-2 (`∀i: Σ_{j≠i} s_j <
s_i` somaria a `nS < 2S`, impossível para `n ≥ 2`). Com coeficiente negativo em
algum perfil — que o `RuleProfile` permite (`preferences.py:87-91`, "nothing here
requires that") — a garantia cai. Não há coeficiente negativo em nenhum caso do
repositório hoje.

**S4 — "a ordem das regras torna o `last` não determinístico".** **PARCIALMENTE
CONFIRMADA.** Reordenar a lista `defeasible_rules` da teoria não mudou nada nos
testes rodados; o que muda o resultado é a ordem dos **antecedentes de uma regra
estrita** (ver D2), porque é ela que determina em que ordem
`_construct_arguments` concatena os `defeasible_rules` dos sub-argumentos
(`solver.py:398-406`). Não é não-determinismo — é sensibilidade a uma escolha
sintática irrelevante.

**S5 — "`resolved_conflicts` e `_compute_defeats` podem discordar".** **NÃO
CONFIRMADA.** Os dois passam pelo mesmo `PreferenceModel.compare`
(`preferences.py:210-225`, `solver.py:452-454`), e `resolved_conflicts` reporta
`attack_succeeded` a partir da lista de derrotas real
(`preferences.py:290,319`). Não há caminho para divergirem.

## Recomendações

**R1 (bloqueante para o artigo). Implementar a Definição 21 inteira, ou declarar
a divergência no texto.** Hoje `preferences.py:198-205` implementa "weakest-link
sobre `DefRules`", que o próprio Modgil & Prakken chama de anomalia corrigida. Ou
(a) acrescentar a comparação de `Prem_p` — o que exige uma preordem sobre `K_p`
no `PreferenceBlock`, hoje inexistente (`schema.py:256-266`), e que sem ela
tornaria o `case-003` inerte —, ou (b) renomear o princípio para algo como
`weakest_rules` e escrever em `docs/formalizacao-caso003.md` que a ordenação
usada não é a do ASPIC+. A opção (b) é honesta e barata; a (a) é fiel e muda o
resultado publicado. **O que não dá é continuar chamando de `weakest`.**

**R2. Corrigir o `last-link`.** Duas correções independentes: usar
`LastDefRules(A)` de verdade (topo derrotável ⇒ `{topo}`; topo estrito ⇒ união
recursiva dos sub-argumentos, como `argumentationGraph.pl:113-114`), e comparar
os conjuntos por `Eli` em vez de reduzi-los a `scored[-1]`. Isso elimina de uma
vez o walk-back (D2) e a sensibilidade à ordem dos antecedentes. Um
`Argument.last_defeasible_rules` calculado em `_construct_arguments`
(`solver.py:398-422`) resolve.

**R3. Tornar a política de regra neutra explícita e testada nas três leituras.**
Ela é invenção nossa e pode inverter o caso principal. No mínimo: um campo no
`PreferenceBlock` (`neutral: "skip" | "zero" | "incomparable"`, padrão
`"incomparable"` para bater com o arg2p), um teste que fixe as três saídas do
contraexemplo mínimo de D3, e uma linha em `preferences.py:33-35` dizendo que a
política **não é conservadora**. Melhor ainda: dar perfil a `dvgen_q2` no
`case.json` e eliminar a dependência — se o leitor acha que o passo `DeverGener
⇒ ¬DeverEspec` carrega as duas dimensões de `dvgen_q1`, que ele escreva isso.

**R4. Parar de anunciar preferência onde não há.** Os perfis de `r1`, `r5`, `r6`
e `r7` (`case.json:617-685`) não decidem nada (C6). `resolved_conflicts` já os
omite corretamente, mas as views (`src/aspic/perspective_view.py`,
`src/aspic/formalization_view.py`) devem deixar claro quais eixos foram
efetivamente usados — a diferença entre "o leitor ponderou" e "a ponderação
mudou o grafo".

**R5. Considerar a modelagem dos autores em vez da nossa.** Prakken, Wyner,
Bench-Capon & Atkinson resolvem exatamente o nosso problema — preferência entre
razões concorrentes — **sem tocar em ⪯**: `preferred(p, d)` é conclusão de um
esquema derrotável, atacável e undercutável. O `case-003` já tem `dvpre_q8:
DeverEspec ⇒ ¬sc_q6`, que é isso. Se ⟨q0, q2⟩ virasse um undercut ou um
`preferred/2` explícito, a camada decidiria sob a ordenação básica da Def. 2.11,
sem nenhuma máquina numérica e sem nenhuma das três divergências acima. Vale um
`case-003-esquema/` lado a lado com o atual, como controle.

**R6. Ingerir Modgil & Prakken 2013 na base de conhecimento.** O artigo é citado
em `preferences.py:56-57` e não está em `docs/papers/`. Obtido nesta auditoria em
`https://arxiv.org/pdf/1804.06763v1` (versão corrigida, 53 pp.). Pela regra
permanente de `~/.claude/knowledge/jurix26/index.md`, ele deve entrar por
`/consume`, e o repositório que o acompanha já está clonado (`tuProlog/arg2p-kt`).
Enquanto não entrar, todo argumento de fidelidade sobre ordenação neste
repositório depende de um PDF em `/tmp`.

**R7. Portar `PreferencesTest.kt` como oráculo.**
`core/src/commonTest/.../unit/PreferencesTest.kt:11-200` traz uma teoria de 6
regras (`r0..r5`) com o veredito esperado de cada combinação
`{last, weakest} × {elitist, democrat, normal}` e a contagem de ataques
sobreviventes. É a forma mais barata de fixar a nossa ordenação contra a dos
autores — e a única que teria pego D1, D2 e D3 antes de `case-003-final` ser
publicado. `tests/test_preferences.py` tem hoje 15 testes, todos escritos contra
a nossa própria semântica.
