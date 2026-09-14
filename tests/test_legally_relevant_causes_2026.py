"""Checks both pipeline layers for the built-in ICAIL 2026 cases.
Verifies the causal bridge, relevance targets and declared case verdicts.
"""

"""Solver pipeline over ICAIL 2026 cases, with both layers.

Pisano, Prakken & Sartor, “From Cause-in-Fact to Legally Relevant Cause
through Argumentation” (ICAIL 2026). Each case exercises a legal-relevance
scheme, and all follow the paper's order:

    CIF → CaFa(φ,ψ) as an LRC axiom (equation 1) → LRC

Cases live in `cases.examples.LEGAL_CASES`, alongside ICAIL 2025 cases:
the same source rendered by `scripts/generate_graphs.py`. This file does
not build frameworks by hand: it loads a case, runs both layers and checks
both sides of the bridge.
"""
import pytest

from aspic import lrc as lrc_vocab
from cases.examples import LEGAL_CASES, case_by_id
from aspic.solver import ArgumentationFramework

#: `case -> {target: legally relevant?}`, following the paper's conclusions.
PAPER_VERDICTS = {
    "kingston": {"LeReCa_DeFi_De": False, "LeReCa_UnFi_De": True},
    "watson": {"LeReCa_Ga_Ig": False, "LeReCa_Ma_Ig": True},
    "r_v_jordan": {"LeReCa_JoSt_ViDe": False},
    "berry_sugar_notch": {"LeReCa_PlSp_In": False, "LeReCa_TrFa_In": True},
    "yania_bigan": {"LeReCa_notYaHe_BiDi": False},
    "leukaemia": {"LeReCa_notPaCo_ChDi": True},
}

LRC_CASES = sorted(PAPER_VERDICTS)


def cif_of(case):
    return ArgumentationFramework(case.knowledge_base, case.causal_model)


def lrc_of(case):
    return lrc_vocab.build_framework(case.lrc.knowledge_base, case.lrc.causal_model)


@pytest.mark.parametrize("case_id", LRC_CASES)
def test_the_layer_verdicts_are_the_papers(case_id):
    """Each target's relevance verdict matches the paper's conclusion."""
    case = case_by_id(case_id)
    report = {r["target"]: r["justified"]
              for r in lrc_vocab.relevance_report(lrc_of(case), case.lrc.targets)}
    assert report == PAPER_VERDICTS[case_id]


@pytest.mark.parametrize("case_id", LRC_CASES)
def test_the_bridge_is_confirmed_by_the_cause_in_fact_layer(case_id):
    """Every `CaFa`/`ButFor` LRC axiom matches CIF output. This checks the
    bridge: the upper layer cannot assume a cause in fact that the lower
    layer does not establish."""
    case = case_by_id(case_id)
    af = cif_of(case)
    checked = 0
    for axiom in case.lrc.knowledge_base.get("axioms", []):
        predicate, _, rest = axiom.partition("_")
        if predicate not in ("CaFa", "ButFor"):
            continue
        phi, _, psi = rest.rpartition("_")
        phi = "¬" + phi[3:] if phi.startswith("not") else phi
        answer = (af.ness_cause(phi, psi) if predicate == "CaFa"
                  else af.but_for(phi, psi))
        assert answer is True, f"{axiom}: o CIF de {case_id} não confirma"
        checked += 1
    assert checked, f"{case_id} não declara nenhuma premissa de ponte"


@pytest.mark.parametrize("case_id", LRC_CASES)
def test_the_bridge_enters_as_an_axiom_not_a_premise(case_id):
    """Equation (1): `CaFa(φ,ψ)` enters LRC in K𝑛, not K𝑝. Axioms cannot be
    undermined, preventing legal relevance from relitigating cause in fact."""
    layer = case_by_id(case_id).lrc
    bridged = [l for l in layer.knowledge_base["axioms"]
               if l.startswith(("CaFa_", "ButFor_"))]
    assert bridged, f"{case_id}: nenhuma ponte entre os axiomas"
    assert not [l for l in layer.knowledge_base.get("premises", [])
                if l.startswith(("CaFa_", "ButFor_"))]


@pytest.mark.parametrize("case_id", LRC_CASES)
def test_every_scheme_id_names_a_scheme_of_the_paper(case_id):
    """`aspic.lrc.scheme_of` classifies rules by id prefix. Without a scheme,
    the report cannot explain the rule."""
    layer = case_by_id(case_id).lrc
    for rule in layer.causal_model["defeasible_rules"]:
        rule_id = rule.split(":", 1)[0].strip()
        assert lrc_vocab.scheme_of(rule_id) is not None, rule_id


def test_the_whole_catalogue_runs_both_layers():
    """Every LRC case has a target and every target has an answer: the
    base-case report depends on this."""
    with_layer = [c for c in LEGAL_CASES if c.lrc is not None]
    assert {c.id for c in with_layer} == set(LRC_CASES)
    for case in with_layer:
        assert case.lrc.targets
        report = lrc_vocab.relevance_report(lrc_of(case), case.lrc.targets)
        assert len(report) == len(case.lrc.targets)
        assert all(r["status"] in ("reconhecida", "afastada") for r in report)


@pytest.mark.parametrize("case_id", LRC_CASES)
def test_the_cause_in_fact_verdicts_match_what_the_case_declares(case_id):
    """Both causal notions match case declarations: the same contract
    `test_legal_cases.py` checks for the 2025 cases."""
    case = case_by_id(case_id)
    af = cif_of(case)
    for query in case.queries:
        assert af.ness_cause(query.phi, query.psi) is query.expect_ness
        assert af.but_for(query.phi, query.psi) is query.expect_but_for
