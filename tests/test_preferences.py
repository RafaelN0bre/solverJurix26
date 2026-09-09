"""Weighing reasons, and what it costs not to.

`aspic.preferences` exists for one situation the paper's basic ordering cannot
report: two defeasible arguments concluding complementary literals, neither
undercutting the other. Under Definition 2.11 they are incomparable, both
attacks succeed, and the grounded extension leaves both UNDEC -- which is not
the answer a judgment that resolved the conflict gave.

These tests pin the three properties that make the module safe to have:

* it is **strictly additive** -- a framework with no model, or with a model
  that scores neither side, behaves exactly as it did before;
* it decides **only** what ASPIC+ lets a preference decide, which is rebutting
  and undermining, never undercutting (Definition 2.10);
* it is **auditable** -- the same conflict flips at a weight the module can
  name, so a reader who disagrees with a number can tell whether the
  disagreement changes anything.
"""
import pytest

from aspic import preferences as PR
from aspic.graph_export import argument_status
from aspic.solver import ArgumentationFramework

#: A head-on conflict of qualifications with no undercut on either side --
#: the shape of ⟨q0, q2⟩ in `docs/formalizacao-caso003.md`. `esp` concludes
#: the specific duty from the custody condition; `gen` derives the generic
#: duty from the lapse and the gang, and `exc` draws the consequence.
KB = {"premises": ["RegFechado", "LapsoTemp", "FormacaoQuad"], "axioms": []}
MODEL = {
    "strict_rules": [],
    "defeasible_rules": [
        "esp: RegFechado => DeverEspec",
        "gen: LapsoTemp AND FormacaoQuad => DeverGener",
        "exc: DeverGener => ¬DeverEspec",
    ],
}

DIMENSIONS = [
    PR.Dimension("dever_especifico", "especificidade do dever", 4.0),
    PR.Dimension("intervencao_causal", "intervenção causal", 5.0),
    PR.Dimension("autonomia", "autonomia do terceiro", 5.0),
]

#: Tudo o que aparece nos dois argumentos em conflito é classificado --
#: premissas e regras. A Definição 21 compara `Prem_p` **e** `DefRules`, e um
#: único elemento sem classificação torna o conjunto incomparável, o que
#: silencia a ordenação inteira. Não existe, sob essa definição, "regra
#: neutra que se pula": ou o caso ordena o que está em jogo, ou não ordena.
PROFILES = [
    PR.RuleProfile("RegFechado", {"dever_especifico": 1.0}),
    PR.RuleProfile("LapsoTemp", {"intervencao_causal": 1.0}),
    PR.RuleProfile("FormacaoQuad", {"autonomia": 1.0}),
    PR.RuleProfile("esp", {"dever_especifico": 1.0}),
    PR.RuleProfile("gen", {"intervencao_causal": 1.0, "autonomia": 1.0}),
    PR.RuleProfile("exc", {"intervencao_causal": 1.0, "autonomia": 1.0}),
]


def model(principle=PR.WEAKEST_LINK, comparator=PR.ELITIST, **weights):
    dimensions = [PR.Dimension(d.key, d.label_pt, weights.get(d.key, d.weight))
                  for d in DIMENSIONS]
    return PR.PreferenceModel(dimensions, PROFILES, principle=principle,
                              comparator=comparator)


def framework(preferences=None):
    return ArgumentationFramework(KB, MODEL, preferences=preferences)


def labels(af):
    """`{conclusão: rótulo}` for the arguments that used a rule."""
    extension, _ = af.compute_grounded_extension()
    status = argument_status(af, extension)
    return {argument.conclusion: status[argument.id]
            for argument in af.arguments.values() if argument.defeasible_rules}


# ----------------------------------------------------------------------
# The default is unchanged
# ----------------------------------------------------------------------
def test_without_a_model_a_mutual_rebut_leaves_both_sides_undecided():
    """The behaviour the whole module exists to change, pinned first: this is
    what every case in the repository that declares no weights still does."""
    assert labels(framework()) == {
        "DeverEspec": "UNDEC", "DeverGener": "IN", "¬DeverEspec": "UNDEC"}


def test_a_model_that_scores_neither_side_changes_nothing():
    """Additivity: an ordering is a refinement of the basic one, so a rule
    base it says nothing about has to come out exactly as before."""
    silent = PR.PreferenceModel(DIMENSIONS, [])
    assert labels(framework(silent)) == labels(framework())


def test_an_exact_tie_is_incomparability_again():
    """Two equal strengths are not "the first one wins": ASPIC+'s ordering is
    a preorder, and equal is incomparable. Reporting a winner here would be
    the module inventing a decision nobody made."""
    tied = model(dever_especifico=5.0)   # premissa 5 × 5, regra 5 × 10
    assert labels(framework(tied))["DeverEspec"] == "UNDEC"
    assert labels(framework(tied))["¬DeverEspec"] == "UNDEC"


# ----------------------------------------------------------------------
# What the weights decide
# ----------------------------------------------------------------------
def test_the_case_tuple_resolves_the_conflict_against_the_specific_duty():
    """⟨4, 5, 5⟩: the generic-duty argument scores 5 + 5 = 10 against 4, so it
    prevails -- and the argument it defeats stops being merely undecided and
    becomes OUT, which is a different statement about the judgment."""
    resolved = labels(framework(model()))
    assert resolved["¬DeverEspec"] == "IN"
    assert resolved["DeverEspec"] == "OUT"


def test_raising_the_weight_of_the_duty_flips_the_case():
    """The counterfactual a reader needs in order to disagree with a number.

    Sob a Def. 21 o eixo do dever levanta os dois lados da conjunção de uma
    vez -- a premissa `RegFechado` e a regra `esp` --, e é preciso passar dos
    dois: da premissa (5) e da regra (5 + 5).
    """
    flipped = labels(framework(model(dever_especifico=11.0)))
    assert flipped["DeverEspec"] == "IN"
    assert flipped["¬DeverEspec"] == "OUT"


def test_the_ordering_compares_premises_and_rules_together():
    """Definição 21, cláusula 3: `Prem_p(B) ◁ Prem_p(A)` **e**
    `DefRules(B) ◁ DefRules(A)`. As duas, conjuntamente.

    Este repositório comparava só as regras. Modgil & Prakken chamam a versão
    que ignora as premissas de "an anomaly" que foram corrigir -- e o efeito
    de ignorá-las não é conservador: retirar um conjuntivo faz a preferência
    valer em *mais* casos, declarando ordem onde o ASPIC+ canônico não declara
    nenhuma.
    """
    preferences = model()
    af = framework(preferences)
    esp = next(a for a in af.arguments.values() if a.conclusion == "DeverEspec")
    gen = next(a for a in af.arguments.values() if a.conclusion == "¬DeverEspec")

    assert preferences.precedes(sorted(esp.ordinary_premises),
                                sorted(gen.ordinary_premises)) is True
    assert preferences.precedes(list(esp.defeasible_rules),
                                list(gen.defeasible_rules)) is True
    assert preferences.is_weaker(esp, gen) is True

    # Basta uma das duas falhar para não haver preferência.
    so_regras = PR.PreferenceModel(
        DIMENSIONS, [p for p in PROFILES if p.rule_id in ("esp", "gen", "exc")])
    assert so_regras.is_weaker(esp, gen) is False


def test_last_link_is_the_top_rule_and_nothing_else():
    """`LastDefRules(A)` (Def. 20) é `{regra do topo}` quando o topo é
    derrotável -- não a regra que carrega o fundamento mais fundo na cadeia.

    Esta versão corrige a anterior, que fixava uma invenção minha: "andar para
    trás até achar uma regra com peso". A referência não anda
    (`argumentationGraph.pl`), e andar torna last-link uma terceira coisa que
    não é nem last nem weakest.
    """
    preferences = model(principle=PR.LAST_LINK)
    af = framework(preferences)
    gen = next(a for a in af.arguments.values() if a.conclusion == "¬DeverEspec")
    assert list(gen.defeasible_rules) == ["gen", "exc"]
    assert preferences.last_defeasible_rules(gen) == ["exc"]   # só o topo
    assert preferences.argument_strength(gen) == 10.0


def test_last_link_over_a_strict_top_rule_ignores_antecedent_order():
    """Com topo estrito, `LastDefRules` é a *união* das dos sub-argumentos --
    um conjunto, não "o último item de uma lista".

    Ler o último item fazia a força depender da ordem em que os antecedentes
    foram escritos: `s: X AND Y -> Z` dava 1 e `s: Y AND X -> Z` dava 9, para
    a mesma teoria. Reordenar antecedentes é irrelevante para o significado e
    invertia o veredito da ordenação.
    """
    dims = [PR.Dimension("d", "eixo", 1.0)]
    profiles = [PR.RuleProfile("a", {"d": 9.0}), PR.RuleProfile("b", {"d": 1.0})]
    forcas = set()
    for body in ("s: X AND Y -> Z", "s: Y AND X -> Z"):
        af = ArgumentationFramework(
            {"premises": ["p", "q"], "axioms": []},
            {"strict_rules": [body],
             "defeasible_rules": ["a: p => X", "b: q => Y"]},
            preferences=PR.PreferenceModel(dims, profiles, principle=PR.LAST_LINK))
        argument = next(x for x in af.arguments.values() if x.conclusion == "Z")
        assert set(af.preferences.last_defeasible_rules(argument)) == {"a", "b"}
        forcas.add(af.preferences.argument_strength(argument))
    assert forcas == {1.0}      # o elo mais fraco do conjunto, elitist


def test_the_two_comparators_of_definition_19_can_disagree():
    """`elitist` e `democrat` são os dois comparadores de conjunto da Def. 19,
    e a escolha é substantiva, não formalidade.

    `elitist` pede um elemento de B abaixo de *todos* os de A; `democrat` pede
    que *todo* elemento de B esteja abaixo de *algum* de A. Aqui as regras de
    A são ⟨5, 20⟩ e a de B é ⟨10⟩: nenhum elemento de B fica abaixo de todos
    os de A (falha o elitista), mas o único que há fica abaixo de algum
    (passa o democrata).
    """
    dims = [PR.Dimension("d", "eixo", 1.0)]
    profiles = [PR.RuleProfile("pb", {"d": 1.0}), PR.RuleProfile("pa", {"d": 2.0}),
                PR.RuleProfile("b1", {"d": 10.0}),
                PR.RuleProfile("a1", {"d": 5.0}), PR.RuleProfile("a2", {"d": 20.0})]
    kb = {"premises": ["pb", "pa"], "axioms": []}
    rules = {"strict_rules": [], "defeasible_rules": [
        "b1: pb => X", "a1: pa => Y", "a2: Y => ¬X"]}

    def verdict(comparator):
        af = ArgumentationFramework(kb, rules, preferences=PR.PreferenceModel(
            dims, profiles, comparator=comparator))
        return labels(af)["X"]

    assert verdict(PR.ELITIST) == "UNDEC"      # ninguém precede ninguém
    assert verdict(PR.DEMOCRAT) == "OUT"       # X é mais fraco, e cai


def test_an_unranked_element_silences_the_ordering():
    """Um único elemento sem classificação torna o conjunto incomparável.

    É a razão de o caso ter de classificar premissas *e* regras: era isto que
    fazia a ordenação do case-003 ser inerte sob a Def. 21 enquanto só as
    regras estavam classificadas.
    """
    incompleto = PR.PreferenceModel(
        DIMENSIONS,
        [p for p in PROFILES if p.rule_id not in ("RegFechado", "LapsoTemp",
                                                  "FormacaoQuad")])
    assert labels(framework(incompleto)) == labels(framework())


# ----------------------------------------------------------------------
# What the weights must never decide
# ----------------------------------------------------------------------
def test_undercutting_ignores_preferences_entirely():
    """Definition 2.10: undercutting defeat is preference-independent. A
    weak undercutter still knocks out a strong rule, and pretending otherwise
    would let a number override the claim that a rule does not apply."""
    kb = {"premises": ["Fraco", "Forte"], "axioms": []}
    rules = {"strict_rules": [], "defeasible_rules": [
        "forte: Forte => Conclusao",
        "fraco: Fraco => ¬forte",
    ]}
    preferences = PR.PreferenceModel(
        DIMENSIONS,
        [PR.RuleProfile("forte", {"autonomia": 1.0}),        # 5
         PR.RuleProfile("fraco", {"dever_especifico": 0.25})],  # 1
    )
    af = ArgumentationFramework(kb, rules, preferences=preferences)
    assert "¬forte" in af.justified_conclusions()
    assert "Conclusao" not in af.justified_conclusions()


def test_a_strict_and_firm_argument_is_never_made_weaker_by_a_number():
    """The basic clauses come first and are not negotiable: a preference
    refines only the case Definition 2.11 leaves open."""
    kb = {"premises": [], "axioms": ["Axioma"]}
    rules = {"strict_rules": ["forte: Axioma -> Conclusao"], "defeasible_rules": [
        "fraco: Axioma => ¬Conclusao"]}
    af = ArgumentationFramework(kb, rules, preferences=model())
    assert "Conclusao" in af.justified_conclusions()
    assert "¬Conclusao" not in af.justified_conclusions()


def test_the_counterfactual_frameworks_are_weighed_the_same_way():
    """`ness_cause` and `but_for` compare the framework against an
    axiom-expanded sibling. If the sibling dropped the ordering, the
    counterfactual would be run under a different logic than the case."""
    af = framework(model())
    expanded = af.axiom_expand(["¬RegFechado"])
    assert expanded.preferences is af.preferences


# ----------------------------------------------------------------------
# Sanity of the declaration itself
# ----------------------------------------------------------------------
def test_a_profile_citing_an_unknown_dimension_is_refused():
    """A typo in a dimension key would otherwise silently score zero, and a
    rule the author believed carried weight would quietly stop carrying it."""
    with pytest.raises(ValueError, match="dimensões que não existem"):
        PR.PreferenceModel(DIMENSIONS, [PR.RuleProfile("esp", {"dever_espcifico": 1.0})])


def test_an_unknown_aggregation_principle_is_refused():
    with pytest.raises(ValueError, match="princípio de agregação"):
        PR.PreferenceModel(DIMENSIONS, PROFILES, principle="média")


def test_resolved_conflicts_reports_each_pair_once_and_skips_undercuts():
    rows = PR.resolved_conflicts(framework(model()))
    pairs = {(row["attacker"], row["target"]) for row in rows}
    assert len(rows) == len(pairs)
    assert all(row["type"] in ("rebut", "undermine") for row in rows)
    # Both directions of the mutual rebut are reported, with opposite outcomes:
    # that asymmetry *is* the resolution.
    assert {row["attack_succeeded"] for row in rows} == {True, False}


def test_a_framework_without_a_model_reports_no_resolved_conflicts():
    assert PR.resolved_conflicts(framework()) == []
