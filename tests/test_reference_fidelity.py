"""Nossos vereditos contra os dos autores.

`src/aspic/solver.py` reimplementa em Python o que Pisano, Prakken, Sartor &
Liepina implementaram em Kotlin/Prolog. A implementação deles está clonada em
`~/.claude/knowledge/jurix26/repos/tuProlog--arg2p-kt/`, e o módulo
`causality-solver/` traz uma bateria de teorias pequenas com o veredito
esperado de cada noção, escrita pelos próprios autores:

    causality-solver/src/commonTest/kotlin/.../causality/BasicTest.kt

Este arquivo porta esses oráculos. Não é um teste de regressão contra nós
mesmos — é o único ponto do repositório em que a nossa leitura dos artigos é
confrontada com a leitura de quem os escreveu. Um oráculo que passa a falhar
aqui significa que divergimos da referência, não que "mudou o resultado".

Notação: as teorias de origem estão em sintaxe arg2p (`f1 :=> a.` é regra
derrotável de corpo vazio concluindo `a`; `r0 : [] => c.` idem). Corpo vazio
não existe na nossa gramática, então uma regra dessas vira premissa, e a
`r0 : [] => c` da segunda teoria vira `r0: T => c` sobre uma premissa `T`
sempre presente — o que preserva o que interessa, que é `r0` ser uma regra
undercutável concluindo `c`.
"""
import pytest

from aspic.solver import ArgumentationFramework


def framework(premises, rules):
    return ArgumentationFramework({"premises": list(premises), "axioms": []},
                                  {"strict_rules": [], "defeasible_rules": list(rules)})


# ----------------------------------------------------------------------
# BasicTest.kt :: causalityTestRefinedTheory1
#
#   f1 :=> a.   f1 :=> b.
#   r1 : a => c.
#   r2 : a, b => c.
# ----------------------------------------------------------------------
@pytest.fixture
def theory1():
    return framework(["a", "b"], ["r1: a => c", "r2: a AND b => c"])


def test_theory1_both_premises_are_ness_causes(theory1):
    """`isNessCause(a, c, true)` e `isNessCause(b, c, true)`.

    `b` é causa NESS embora removê-lo não mate `c`: r1 continua de pé. NESS
    pede que a intervenção quebre *alguma* explicação, e a de r2 quebrou.
    """
    assert theory1.ness_cause("a", "c") is True
    assert theory1.ness_cause("b", "c") is True


def test_theory1_only_a_is_a_but_for_cause(theory1):
    """`isButForCause(a, c)` e `isButForCause(b, c, false)` — a assimetria
    que separa as duas noções, na teoria mínima que a produz."""
    assert theory1.but_for("a", "c") is True
    assert theory1.but_for("b", "c") is False


# ----------------------------------------------------------------------
# BasicTest.kt :: causalityTestRefinedTheory2
#
#   f1 :=> a.   f2 :=> b.
#   r0 : [] => c.
#   r1 : -a     => -r0.
#   r2 : -a, -b => -r0.
#
# É a teoria que separa o ICAIL 2024 do ICAIL 2025: lá `ness_original(b, c)`
# é falso e `ness(b, c)` é verdadeiro.
# ----------------------------------------------------------------------
@pytest.fixture
def theory2():
    return framework(["a", "b", "T"],
                     ["r0: T => c", "r1: ¬a => ¬r0", "r2: ¬a AND ¬b => ¬r0"])


def test_theory2_a_is_a_ness_cause(theory2):
    """`isNessCause(a, c, true)`: a intervenção `{¬a}` habilita r1, que
    undercuta r0, e `c` cai."""
    assert theory2.ness_cause("a", "c") is True


@pytest.mark.xfail(
    reason="Divergência conhecida com a referência: só implementamos a "
           "intervenção unitária. Ver o docstring abaixo e o relatório do "
           "agente de verificação.",
    strict=True,
)
def test_theory2_b_is_a_ness_cause_under_a_joint_intervention(theory2):
    """`isNessCause(b, c, true)` na referência; nós devolvemos False.

    **A divergência, e por que ela é substantiva.**

    `ness/3` dos autores não testa só a intervenção unitária `{¬φ}`: ele
    *procura* uma intervenção. `generate_interventions/3`
    (`CausalitySolver.kt`, cláusulas Prolog embutidas no fim do arquivo) gera
    três famílias de candidatas para a causa S:

        generate_interventions(_, S, [CS])            :- compl(S, CS).
        generate_interventions(_, S, [undercut(S)])   :- S \\= -_.
        generate_interventions(R, S, SUP)             :- compl(S, CS),
                                                         unused_premises(R, UP),
                                                         subsets(UP, SUP),
                                                         member(CS, SUP).

    1. o singleton `{¬S}` — a única que implementamos;
    2. o *undercut* da regra `S`, o que faz de um **identificador de regra**
       uma causa candidata (a bateria deles tem `isNessCause(r2, -b, true)`);
    3. qualquer subconjunto das premissas ainda não usadas que **contenha**
       `¬S` — ou seja, **intervenções conjuntas**.

    `checkCausalityICAIL25` então exige minimalidade: nenhum subconjunto
    próprio da intervenção pode produzir os mesmos atacantes IN.

    Aqui `b` só é causa pela família 3: `{¬a}` sozinho já derruba `c` via r1,
    mas `{¬a, ¬b}` derruba via r2, e r2 não é atacante de nenhum subconjunto
    próprio — logo `{¬a, ¬b}` é minimal e `b` é causa. Com intervenção
    unitária `{¬b}`, r2 não dispara (falta `¬a`) e nós dizemos False.

    Consequência prática: **nós sub-reportamos causas.** Todo veredito
    positivo nosso é positivo na referência; o inverso não vale.
    """
    assert theory2.ness_cause("b", "c") is True


# ----------------------------------------------------------------------
# O encaixe entre as duas noções, que a referência assume em toda parte
# ----------------------------------------------------------------------
@pytest.mark.parametrize("premises,rules,pairs", [
    (["a", "b"], ["r1: a => c", "r2: a AND b => c"], [("a", "c"), ("b", "c")]),
    (["a", "b", "T"], ["r0: T => c", "r1: ¬a => ¬r0", "r2: ¬a AND ¬b => ¬r0"],
     [("a", "c"), ("b", "c")]),
    (["Ex1", "Ex2", "Ex3"],
     ["r0: Ca => Di", "r1: Ex1 AND Ex2 => Ca", "r2: Ex2 AND Ex3 => Ca",
      "r3: Ex1 AND Ex3 => Ca"],
     [("Ex1", "Di"), ("Ex2", "Di"), ("Ex3", "Di"), ("Ca", "Di")]),
])
def test_every_but_for_cause_is_a_ness_cause(premises, rules, pairs):
    """but-for é estritamente mais forte, então nunca pode valer sozinho.

    Se isto falhar, uma das duas implementações está errada — e como a
    inclusão decorre das definições (quebrar *todas* as explicações é um caso
    particular de quebrar *alguma*), é a nossa.
    """
    af = framework(premises, rules)
    for phi, psi in pairs:
        if af.but_for(phi, psi):
            assert af.ness_cause(phi, psi) is True, f"but_for sem ness: {phi}->{psi}"
