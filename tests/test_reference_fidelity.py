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

Onde divergimos, a auditoria de `docs/auditoria-icail2025.md` mediu de que
lado está o artigo. Em dois pontos a *referência* é que se afasta do texto
(exigir atacante `in`; coletar suporte a partir de argumentos não
justificados) e nós seguimos o artigo; num terceiro a lacuna é nossa
(intervenções conjuntas). Nenhum dos três move veredito publicado neste
repositório -- 159 pares (φ,ψ) varridos, 3 divergências, todas em pares que
nenhum caso consulta.

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
    reason="Divergência conhecida: só implementamos a intervenção unitária, e "
           "estes oráculos precisam de intervenção conjunta. Ver o docstring.",
    strict=True,
)
@pytest.mark.parametrize("phi,psi,premises,rules", [
    # theory2: `{¬a, ¬b}` acorda r2, que undercuta r0.
    ("b", "c", ["a", "b", "T"],
     ["r0: T => c", "r1: ¬a => ¬r0", "r2: ¬a AND ¬b => ¬r0"]),
    # complex: `tx2 : d, e => undercut(r2)` -- a intervenção `{d, e}` acorda tx2.
    ("¬d", "¬b", ["a"], ["r2: a => ¬b", "tx2: d AND e => ¬r2"]),
    ("¬e", "¬b", ["a"], ["r2: a => ¬b", "tx2: d AND e => ¬r2"]),
])
def test_a_joint_intervention_is_needed_for_these(phi, psi, premises, rules):
    """A referência devolve True nos três; nós devolvemos False.

    **A divergência, e o seu tamanho exato.**

    `ness/3` dos autores não testa só a intervenção unitária `{¬φ}`: ele
    *procura* uma intervenção. `generate_interventions/3`
    (`CausalitySolver.kt`, cláusulas Prolog no fim do arquivo) gera três
    famílias de candidatas para a causa S:

        generate_interventions(_, S, [CS])            :- compl(S, CS).
        generate_interventions(_, S, [undercut(S)])   :- S \\= -_.
        generate_interventions(R, S, SUP)             :- compl(S, CS),
                                                         unused_premises(R, UP),
                                                         subsets(UP, SUP),
                                                         member(CS, SUP).

    Destas, **falta-nos só a terceira** — as intervenções conjuntas. A
    primeira é a nossa. E a segunda, o *undercut* de uma regra, já vem de
    graça na nossa notação: o literal de undercut de `r2` escreve-se `¬r2`,
    que é exatamente `compl("r2")`, então `ness_cause("r2", ψ)` já faz o que
    a família (b) faria. `test_a_rule_id_is_a_candidate_cause` fixa isso.

    A família (c) só se ativa quando `¬φ` é antecedente de uma regra que
    **não disparou**: é ela que a intervenção acorda. Nos casos deste
    repositório isso nunca acontece — os literais consultados ou já são
    premissas, ou o seu complemento não é antecedente de regra inerte — e por
    isso a lacuna hoje não move nenhum veredito publicado. É propriedade da
    modelagem dos casos, não garantia: uma formalização com regras adormecidas
    de dois antecedentes reabre a questão.
    """
    af = framework(premises, rules)
    assert af.ness_cause(phi, psi) is True


def test_a_rule_id_is_a_candidate_cause():
    """A família (b) da referência, que na nossa notação não é família nenhuma.

    `isNessCause(r2, -b, true)` em `causalityTestComplex`: intervir undercutando
    `r2` mata `¬b`, logo `r2` é causa de `¬b`. Para nós a intervenção é o axioma
    `¬r2`, que é o mesmo objeto -- daí acertarmos o oráculo sem código extra.
    """
    af = framework(["a"], ["r2: a => ¬b", "tx2: d AND e => ¬r2"])
    assert "¬b" in af.justified_conclusions()
    assert af.ness_cause("r2", "¬b") is True
    assert af.ness_cause("a", "¬b") is True
    assert af.ness_cause("d", "¬b") is False


def test_we_follow_the_paper_where_the_reference_is_stricter():
    """Def. 4.3 pede que a explicação saia da extensão. Só isso.

    `checkCausalityICAIL25` (`CausalitySolver.kt:190`) pede mais: que o
    argumento que derrubou o suporte esteja ele próprio rotulado `in`. Aqui a
    intervenção `{x}` cria um `¬e` que se rebate mutuamente com as duas rotas
    para `e`; o ciclo par deixa todos `und`, e nenhum atacante fica `in`. O
    suporte saiu da extensão, então pelo texto do artigo `¬x` é causa de `e`;
    a referência diz que não.

    Divergimos da implementação dos autores **a favor do artigo**, e de
    propósito. Em fuzzing sobre teorias aleatórias este é o padrão mais comum
    de divergência entre nós e eles; nos casos deste repositório não ocorre
    nenhuma vez.
    """
    af = framework(["p", "p2"], ["r1: p => e", "r6: p2 => e", "r2: x => ¬e"])
    assert "e" in af.justified_conclusions()
    # `x` não é premissa: quem o introduz é a intervenção, que é o que torna
    # `¬x` a causa candidata. Depois dela os três argumentos ficam UNDEC.
    assert af.ness_cause("¬x", "e") is True


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
