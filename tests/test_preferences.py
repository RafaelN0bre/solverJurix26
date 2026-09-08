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

#: `exc` carries no weight: it only draws out what `gen` established. Scoring
#: it would count the same ground twice and let the weakest link measure the
#: chaining instead of the reason.
PROFILES = [
    PR.RuleProfile("esp", {"dever_especifico": 1.0}),
    PR.RuleProfile("gen", {"intervencao_causal": 1.0, "autonomia": 1.0}),
]


def model(principle=PR.WEAKEST_LINK, **weights):
    dimensions = [PR.Dimension(d.key, d.label_pt, weights.get(d.key, d.weight))
                  for d in DIMENSIONS]
    return PR.PreferenceModel(dimensions, PROFILES, principle=principle)


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
    tied = model(dever_especifico=10.0)   # 10 against gen's 5 + 5
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
    """The counterfactual a reader needs in order to disagree with a number."""
    flipped = labels(framework(model(dever_especifico=11.0)))
    assert flipped["DeverEspec"] == "IN"
    assert flipped["¬DeverEspec"] == "OUT"


def test_the_neutral_step_carries_no_weight_of_its_own():
    """`exc` chains `gen`; the argument's strength is `gen`'s, not something
    the chaining diluted or doubled."""
    preferences = model()
    af = framework(preferences)
    argument = next(a for a in af.arguments.values() if a.conclusion == "¬DeverEspec")
    assert preferences.rule_strength("exc") is None
    assert preferences.argument_strength(argument) == 10.0
    assert preferences.contributing_rules(argument.defeasible_rules) == ["gen"]


def test_last_link_reads_the_last_rule_that_carries_weight():
    """Last-link is meant to ask what the final inference rests on. When that
    inference is itself neutral, refusing to score the argument would make
    last-link strictly less informative than weakest-link for no reason."""
    preferences = model(principle=PR.LAST_LINK)
    af = framework(preferences)
    argument = next(a for a in af.arguments.values() if a.conclusion == "¬DeverEspec")
    assert argument.defeasible_rules[-1] == "exc"      # neutral
    assert preferences.argument_strength(argument) == 10.0


def test_sum_and_weakest_link_can_disagree():
    """They only coincide because each argument here has one weight-carrying
    rule; the principle is a real choice, not a formality."""
    stacked = PR.PreferenceModel(
        DIMENSIONS,
        [PR.RuleProfile("esp", {"dever_especifico": 1.0}),
         PR.RuleProfile("gen", {"intervencao_causal": 1.0}),
         PR.RuleProfile("exc", {"autonomia": 1.0})],
        principle=PR.SUM,
    )
    af = framework(stacked)
    argument = next(a for a in af.arguments.values() if a.conclusion == "¬DeverEspec")
    assert stacked.argument_strength(argument) == 10.0          # 5 + 5
    assert stacked.with_principle(PR.WEAKEST_LINK).argument_strength(argument) == 5.0


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
