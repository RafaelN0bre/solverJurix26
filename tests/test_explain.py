"""Tests for aspic.explain's plain-Portuguese sentence templates."""
from aspic.examples import case_by_id
from aspic.explain import (
    capitalize_pt,
    describe_argument,
    describe_attack,
    gloss,
    status_label_pt,
)
from aspic.solver import ArgumentationFramework


def test_gloss_falls_back_to_backtick_symbol_when_missing():
    assert gloss({"X": "o fato X"}, "X") == "o fato X"
    assert gloss({}, "Y") == "`Y`"


def test_capitalize_pt():
    assert capitalize_pt("bush atirou") == "Bush atirou"
    assert capitalize_pt("") == ""


def test_status_label_pt_known_and_unknown():
    assert status_label_pt("IN") == "Aceito"
    assert status_label_pt("OUT") == "Rejeitado"
    assert status_label_pt("UNDEC") == "Indeterminado"
    assert status_label_pt("WHATEVER") == "WHATEVER"


def _build_double_shooting():
    case = case_by_id("double_shooting")
    af = ArgumentationFramework(case.knowledge_base, case.causal_model)
    return case, af


def _arg_for(af, conclusion, *, via_rule=None):
    matches = [
        a for a in af.arguments.values()
        if a.conclusion == conclusion
        and (via_rule is None or via_rule in a.strict_rules + a.defeasible_rules)
    ]
    assert len(matches) == 1
    return matches[0]


def test_describe_argument_atomic_premise():
    case, af = _build_double_shooting()
    arg = _arg_for(af, "BuSh")
    text = describe_argument(arg, case.atom_glosses, case.rule_glosses)
    assert text == "Fato do caso: Bush atirou na vítima (Geller)."


def test_describe_argument_derived_includes_rule_rationale():
    case, af = _build_double_shooting()
    arg = _arg_for(af, "BuKi")
    text = describe_argument(arg, case.atom_glosses, case.rule_glosses)
    assert text.startswith("Considerando que Bush atirou na vítima (Geller), conclui-se que")
    assert "o tiro de Bush foi, por si só, letal" in text
    # the top rule's gloss is appended as the rationale, in parentheses
    assert case.rule_glosses["r0"] in text


def test_describe_attack_undercut_mentions_rule_rationale_and_defeat_status():
    case, af = _build_double_shooting()
    attack = next(a for a in af.attacks if a.attack_type == "undercut" and a.target_id == _arg_for(af, "DlKi").id)
    text = describe_attack(af, attack, is_defeat=True, atom_glosses=case.atom_glosses, rule_glosses=case.rule_glosses)
    assert case.rule_glosses["r4"] in text
    assert text.endswith("Esse ataque foi aceito e afasta o argumento atacado.")


def test_describe_attack_reports_failed_attack_when_not_a_defeat():
    case, af = _build_double_shooting()
    attack = next(a for a in af.attacks if a.attack_type == "undercut" and a.target_id == _arg_for(af, "DlKi").id)
    text = describe_attack(af, attack, is_defeat=False, atom_glosses=case.atom_glosses, rule_glosses=case.rule_glosses)
    assert text.endswith("Esse ataque não foi suficiente para afastar o argumento atacado.")
