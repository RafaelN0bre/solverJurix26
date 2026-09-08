"""The deterministic gate between the model and the solver.

Each check exists because a real modelling mistake would otherwise reach the
solver silently: a rule the parser rejects, a literal that was never declared,
an outcome asserted as a premise (making the causal test vacuous), or a legal
relevance claim resting on a cause in fact the solver never established.
"""
import pytest

from formalize.bridge import BridgeFacts, CausalFact
from formalize.schema import (
    AtomsStageOut, LrcStageOut, QueriesStageOut, RulesStageOut,
)
from formalize.validate import (
    check_atoms, check_lrc, check_queries, check_rules, parse_rule,
)


def codes(issues):
    return {issue.code for issue in issues}


def errors(issues):
    return [i for i in issues if i.severity == "error"]


# ----------------------------------------------------------------------
# Rule grammar
# ----------------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    ("r0: A AND B => C", (["A", "B"], "C", False)),
    ("r1: X -> Y", (["X"], "Y", True)),
    ("r2: P => ¬r0", (["P"], "¬r0", False)),
])
def test_parse_rule_accepts_the_solvers_grammar(text, expected):
    rule = parse_rule(text)
    assert (rule.antecedents, rule.consequent, rule.is_strict) == expected


@pytest.mark.parametrize("text, message", [
    ("sem dois pontos", "identificador"),
    ("r0: A, B => C", "vírgula"),
    ("r0: => C", "vazio"),
    ("r0: A B C", "seta"),
])
def test_parse_rule_rejects_what_the_solver_would(text, message):
    with pytest.raises(ValueError, match=message):
        parse_rule(text)


def test_undercutters_are_recognised_by_their_consequent():
    assert parse_rule("r2: P => ¬r0").is_undercutter
    assert parse_rule("r2: P => ¬r0").undercut_target == "r0"
    assert not parse_rule("r2: P => ¬Ca").is_undercutter


# ----------------------------------------------------------------------
# Atoms
# ----------------------------------------------------------------------
def atoms_out(sample_stage_outputs, **overrides):
    payload = {**sample_stage_outputs["atoms"], **overrides}
    return AtomsStageOut.model_validate(payload)


def test_valid_atoms_pass(sample_stage_outputs):
    valid_ids = {"src_fixture01", "src_fixture02", "synth_fixture01",
                 "divg_fixture01", "unit_fixture01"}
    assert errors(check_atoms(atoms_out(sample_stage_outputs), valid_ids)) == []


def test_outcome_must_exist_and_be_derived(sample_stage_outputs):
    payload = sample_stage_outputs["atoms"]
    assert "atoms.outcome_missing" in codes(
        check_atoms(atoms_out(sample_stage_outputs, outcome_code="Inexistente")))

    established_outcome = {**payload, "atoms": [
        {**a, "established": True} if a["code"] == "Morte" else a for a in payload["atoms"]
    ]}
    assert "atoms.outcome_premise" in codes(
        check_atoms(AtomsStageOut.model_validate(established_outcome)))


def test_atom_codes_must_be_camel_case_ascii(sample_stage_outputs):
    payload = sample_stage_outputs["atoms"]
    broken = {**payload, "atoms": [
        {**a, "code": "não-válido"} if a["code"] == "Leuc" else a for a in payload["atoms"]
    ]}
    assert "atoms.code" in codes(check_atoms(AtomsStageOut.model_validate(broken)))


def test_hallucinated_evidence_ids_are_rejected(sample_stage_outputs):
    issues = check_atoms(atoms_out(sample_stage_outputs), {"src_fixture01"})
    assert "atoms.unknown_ref" in codes(issues)


# ----------------------------------------------------------------------
# Rules
# ----------------------------------------------------------------------
def rules_out(sample_stage_outputs, **overrides):
    return RulesStageOut.model_validate({**sample_stage_outputs["rules"], **overrides})


ATOM_CODES = ["Leuc", "Consent", "Quimio", "Morte"]


def test_valid_rules_pass(sample_stage_outputs):
    assert errors(check_rules(rules_out(sample_stage_outputs), ATOM_CODES, "Morte")) == []


def test_literals_outside_the_catalog_are_rejected(sample_stage_outputs):
    payload = sample_stage_outputs["rules"]
    broken = {**payload, "defeasible_rules": [
        {**payload["defeasible_rules"][0], "rule": "r0: Inventado => Morte"},
        *payload["defeasible_rules"][1:],
    ]}
    assert "rules.unknown_literal" in codes(
        check_rules(RulesStageOut.model_validate(broken), ATOM_CODES, "Morte"))


def test_undercut_of_a_nonexistent_rule_is_rejected(sample_stage_outputs):
    payload = sample_stage_outputs["rules"]
    broken = {**payload, "defeasible_rules": [
        *payload["defeasible_rules"][:2],
        {**payload["defeasible_rules"][2], "rule": "r2: Quimio => ¬r9"},
    ]}
    assert "rules.unknown_undercut" in codes(
        check_rules(RulesStageOut.model_validate(broken), ATOM_CODES, "Morte"))


def test_outcome_as_premise_is_rejected(sample_stage_outputs):
    broken = rules_out(sample_stage_outputs, premises=["Leuc", "¬Consent", "Morte"])
    assert "rules.outcome_premise" in codes(check_rules(broken, ATOM_CODES, "Morte"))


def test_outcome_must_survive_the_attacks(sample_stage_outputs):
    """A model where the outcome is defeated in the base framework has nothing
    left to explain causally -- usually an undercut aimed at the wrong rule."""
    payload = sample_stage_outputs["rules"]
    broken = {
        **payload,
        "premises": ["Leuc", "¬Consent", "Quimio"],
        "defeasible_rules": payload["defeasible_rules"],
    }
    issues = check_rules(RulesStageOut.model_validate(broken),
                         [*ATOM_CODES], "Morte")
    assert "rules.outcome_not_derived" in codes(issues)


def test_mutual_rebut_without_undercut_is_flagged():
    """The no-preferences ordering leaves both sides UNDEC, which almost never
    matches a judgment that actually decided the point."""
    payload = {
        "premises": ["A", "B"], "axioms": [],
        "strict_rules": [],
        "defeasible_rules": [
            {"rule": "r0: A => C", "kind": "causal", "gloss_pt": "g",
             "perspective": "x", "evidence": [], "dossier_refs": []},
            {"rule": "r1: B => ¬C", "kind": "rebut", "gloss_pt": "g",
             "perspective": "y", "evidence": [], "dossier_refs": []},
        ],
        "modelling_notes_pt": "",
    }
    issues = check_rules(RulesStageOut.model_validate(payload), ["A", "B", "C"], "")
    assert "rules.mutual_rebut" in codes(issues)
    assert all(i.severity == "warning" for i in issues if i.code == "rules.mutual_rebut")


def test_orphan_atoms_are_only_a_warning(sample_stage_outputs):
    issues = check_rules(rules_out(sample_stage_outputs),
                         [*ATOM_CODES, "NuncaUsado"], "Morte")
    orphan = [i for i in issues if i.code == "rules.orphan_atom"]
    assert orphan and orphan[0].severity == "warning"


# ----------------------------------------------------------------------
# Queries
# ----------------------------------------------------------------------
def test_valid_queries_pass(sample_stage_outputs):
    out = QueriesStageOut.model_validate(sample_stage_outputs["queries"])
    assert errors(check_queries(out, ATOM_CODES, "Morte")) == []


def test_queries_must_use_declared_literals(sample_stage_outputs):
    payload = sample_stage_outputs["queries"]
    broken = {"queries": [{**payload["queries"][0], "phi": "Inventado"}]}
    assert "queries.unknown_literal" in codes(
        check_queries(QueriesStageOut.model_validate(broken), ATOM_CODES, "Morte"))


# ----------------------------------------------------------------------
# Legal-relevance layer
# ----------------------------------------------------------------------
def leukaemia_facts():
    return BridgeFacts(facts=[
        CausalFact("Leuc", "Morte", ness=True, but_for=True),
        CausalFact("¬Consent", "Morte", ness=True, but_for=True),
    ])


def test_valid_lrc_passes(sample_stage_outputs):
    out = LrcStageOut.model_validate(sample_stage_outputs["lrc"])
    assert errors(check_lrc(out, leukaemia_facts())) == []


def test_duty_premise_may_be_declared_in_either_polarity(sample_stage_outputs):
    """`unom` is always written with `¬Obl_A`; declaring `Obl_A` instead is how
    the paper says "there *was* a duty, so the defence does not fire"."""
    out = LrcStageOut.model_validate(sample_stage_outputs["lrc"])
    assert {p.literal for p in out.doctrinal_premises} == {"Om_notConsent", "Obl_Consent"}
    assert "lrc.missing_premise" not in codes(check_lrc(out, leukaemia_facts()))


def test_a_scheme_may_consume_what_another_scheme_derives(sample_stage_outputs):
    """Rule 5 feeds rule 4: `suca_Z` derives `SupersedingCause_Z` and `sc_X`
    consumes it. Demanding it in `doctrinal_premises` would force the model to
    *assert* the superseding-cause characterisation instead of deriving it --
    an unconditional assumption where the paper has a defeasible conclusion."""
    payload = sample_stage_outputs["lrc"]
    chained = {**payload, "scheme_rules": [
        *payload["scheme_rules"],
        {"rule": "suca_Leuc: CaFa_Leuc_Morte AND CaFa_notConsent_Morte AND "
                 "After_Leuc_notConsent AND Unexpected_Leuc AND ButFor_Leuc_Morte "
                 "=> SupersedingCause_Leuc",
         "scheme": "suca", "gloss_pt": "A doença é causa superveniente.", "evidence": []},
        {"rule": "sc_notConsent: SupersedingCause_Leuc => ¬cf2lrc_notConsent",
         "scheme": "sc", "gloss_pt": "A causa superveniente afasta a recusa.",
         "evidence": []},
    ], "doctrinal_premises": [
        *payload["doctrinal_premises"],
        {"literal": "After_Leuc_notConsent", "label_pt": "a doença veio depois", "evidence": []},
        {"literal": "Unexpected_Leuc", "label_pt": "a doença era inesperada", "evidence": []},
    ]}
    issues = check_lrc(LrcStageOut.model_validate(chained), leukaemia_facts())
    assert "lrc.missing_premise" not in codes(issues), [i.message for i in issues]


def test_relevance_cannot_rest_on_a_cause_the_solver_rejected(sample_stage_outputs):
    """The check that keeps the two layers honest."""
    facts = BridgeFacts(facts=[CausalFact("Leuc", "Morte", True, True)])
    out = LrcStageOut.model_validate(sample_stage_outputs["lrc"])
    issues = check_lrc(out, facts)
    assert "lrc.unavailable_fact" in codes(issues)
    assert any("CaFa_notConsent_Morte" in i.message for i in issues)


def test_scheme_id_must_match_the_declared_scheme(sample_stage_outputs):
    payload = sample_stage_outputs["lrc"]
    broken = {**payload, "scheme_rules": [
        {**payload["scheme_rules"][0], "scheme": "unom"}, *payload["scheme_rules"][1:]]}
    assert "lrc.scheme_mismatch" in codes(
        check_lrc(LrcStageOut.model_validate(broken), leukaemia_facts()))


def test_targets_must_be_derivable(sample_stage_outputs):
    payload = sample_stage_outputs["lrc"]
    broken = {**payload, "targets": [*payload["targets"], "LeReCa_Inventado_Morte"]}
    assert "lrc.target_underived" in codes(
        check_lrc(LrcStageOut.model_validate(broken), leukaemia_facts()))


def test_premises_must_belong_to_the_lrc_vocabulary(sample_stage_outputs):
    payload = sample_stage_outputs["lrc"]
    broken = {**payload, "doctrinal_premises": [
        *payload["doctrinal_premises"],
        {"literal": "AlgoQualquer", "label_pt": "x", "evidence": []},
    ]}
    assert "lrc.premise_vocabulary" in codes(
        check_lrc(LrcStageOut.model_validate(broken), leukaemia_facts()))
