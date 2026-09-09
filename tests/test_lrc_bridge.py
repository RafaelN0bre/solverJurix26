"""The bridge between the two layers, and the LRC vocabulary it speaks.

`tests/test_legally_relevant_causes_2026.py` hand-feeds `CaFa_x_y` premises
for the paper's worked examples. This checks that `formalize.bridge` *derives*
the same literals from the solver, which is what stops a formalization from
claiming legal relevance for a cause the counterfactual test never accepted.
"""
from aspic import lrc
from aspic.solver import ArgumentationFramework
from formalize.bridge import candidate_literals, evaluate, target_literals


LEUKAEMIA_KB = {"premises": ["ChLe", "¬PaCo"], "axioms": []}
LEUKAEMIA_MODEL = {
    "strict_rules": [],
    "defeasible_rules": ["r0: ChLe => ChDi", "r1: PaCo => Chem", "r2: Chem => ¬r0"],
}


def test_atom_token_round_trip():
    assert lrc.atom_token("¬PaCo") == "notPaCo"
    assert lrc.atom_token("PaCo") == "PaCo"
    assert lrc.token_atom("notPaCo") == "¬PaCo"
    assert lrc.token_atom("PaCo") == "PaCo"


def test_predicate_builders_match_the_papers_notation():
    assert lrc.cafa("¬PaCo", "ChDi") == "CaFa_notPaCo_ChDi"
    assert lrc.but_for("Ga", "Ig") == "ButFor_Ga_Ig"
    assert lrc.lereca("¬YaHe", "BiDi") == "LeReCa_notYaHe_BiDi"


def test_longest_prefix_wins_when_predicates_share_a_stem():
    assert lrc.split_lrc_literal("ForeseeableRisk_PlSp_SpCo") == (
        "ForeseeableRisk", ["PlSp", "SpCo"])
    assert lrc.split_lrc_literal("¬Foreseeable_PlSp_In") == ("Foreseeable", ["PlSp", "In"])
    assert lrc.scheme_of("cf2lrc_DeFi") == "cf2lrc"
    assert lrc.scheme_of("cf2lrc") == "cf2lrc"
    assert lrc.scheme_of("r0") is None


def test_case_atoms_are_not_mistaken_for_lrc_literals():
    assert not lrc.is_lrc_literal("DemAt")
    assert lrc.split_lrc_literal("DemAt") is None
    assert lrc.is_lrc_literal("¬Tortious_UnFi")


def test_bridge_derives_the_papers_leukaemia_premises():
    """The omission is a NESS cause under Definition 4.3, and the bridge has
    to carry it: `¬PaCo` never appears as a premise of any argument for
    ChDi, so a bridge keyed on the sufficient-set decomposition alone would
    silently drop the very cause this case exists to make visible."""
    af = ArgumentationFramework(LEUKAEMIA_KB, LEUKAEMIA_MODEL)
    facts = evaluate(af, candidate_literals(LEUKAEMIA_KB, []), target_literals("ChDi", []))

    by_pair = {(f.phi, f.psi): f for f in facts.facts}
    assert by_pair[("¬PaCo", "ChDi")].ness is True
    assert by_pair[("¬PaCo", "ChDi")].but_for is True
    assert by_pair[("ChLe", "ChDi")].ness is True

    assert "CaFa_notPaCo_ChDi" in facts.premises()
    assert "CaFa_ChLe_ChDi" in facts.premises()
    assert facts.lereca_targets() == ["LeReCa_ChLe_ChDi", "LeReCa_notPaCo_ChDi"]


def test_bridge_omits_non_causes():
    """A pair the solver rejected must not appear as a `CaFa_*` premise."""
    kb = {"premises": ["BuSh", "DlSh"], "axioms": []}
    model = {"strict_rules": [], "defeasible_rules": [
        "r0: BuSh => BuKi", "r1: DlSh => DlKi", "r2: BuKi => GeDi",
        "r3: DlKi => GeDi", "r4: BuKi => ¬r1",
    ]}
    af = ArgumentationFramework(kb, model)
    facts = evaluate(af, candidate_literals(kb, []), target_literals("GeDi", []))
    assert "CaFa_BuSh_GeDi" in facts.premises()
    assert "CaFa_DlSh_GeDi" not in facts.premises()
    prompt_block = facts.render_for_prompt()
    assert "reconheceu como causa de fato" in prompt_block
    assert "- DlSh → GeDi" in prompt_block


def test_duties_and_evidence_are_not_candidate_causes():
    """A conjunctive causal rule makes *every* antecedent a cause in fact, so
    `r0: Conduta AND Dever => Elo` would otherwise hand the legal-relevance
    layer a `CaFa_Dever_Dano` and make it ask whether the duty of custody
    caused the death. The duty conditions the inference; it is not a cause."""
    kb = {"premises": ["Conduta", "Dever", "Laudo"], "axioms": []}
    model = {"strict_rules": [],
             "defeasible_rules": ["r0: Conduta AND Dever AND Laudo => Elo",
                                  "r1: Elo => Dano"]}
    af = ArgumentationFramework(kb, model)
    facts = evaluate(af, candidate_literals(kb, [], exclude={"Dever", "Laudo"}),
                     target_literals("Dano", []))
    assert "CaFa_Conduta_Dano" in facts.premises()
    assert "CaFa_Dever_Dano" not in facts.premises()
    assert "CaFa_Laudo_Dano" not in facts.premises()


def test_an_excluded_kind_still_gets_tested_when_the_case_asks_about_it():
    """The filter drops premises nobody asked about; a pair the dossier
    actually poses is always answered."""
    kb = {"premises": ["Conduta", "Dever"], "axioms": []}
    model = {"strict_rules": [], "defeasible_rules": ["r0: Conduta AND Dever => Dano"]}
    queries = [{"phi": "Dever", "psi": "Dano"}]
    assert "Dever" in candidate_literals(kb, queries, exclude={"Dever"})


def test_unjustified_targets_are_skipped():
    af = ArgumentationFramework({"premises": ["A"], "axioms": []},
                                {"strict_rules": [], "defeasible_rules": ["r0: A => B"]})
    assert evaluate(af, ["A"], ["Inexistente"]).facts == []


def test_relevance_report_names_the_defence_that_blocked_the_target():
    """Kingston v. Chicago (ICAIL 2026, no-worse-off): the defendant's fire is
    a cause in fact but not a legally relevant cause."""
    af = lrc.build_framework(
        {"premises": ["CaFa_DeFi_De", "CaFa_UnFi_De", "¬Tortious_UnFi"], "axioms": []},
        {"strict_rules": [], "defeasible_rules": [
            "cf2lrc_DeFi: CaFa_DeFi_De => LeReCa_DeFi_De",
            "cf2lrc_UnFi: CaFa_UnFi_De => LeReCa_UnFi_De",
            "nwo_DeFi: CaFa_UnFi_De AND ¬Tortious_UnFi => ¬cf2lrc_DeFi",
        ]},
    )
    report = {entry["target"]: entry for entry in
              lrc.relevance_report(af, ["LeReCa_DeFi_De", "LeReCa_UnFi_De"])}
    assert report["LeReCa_UnFi_De"]["justified"] is True
    assert report["LeReCa_DeFi_De"]["justified"] is False
    assert report["LeReCa_DeFi_De"]["blocked_by"][0]["scheme"] == "nwo"
    assert "no-worse-off" in report["LeReCa_DeFi_De"]["blocked_by"][0]["scheme_pt"]


def test_omission_scheme_does_not_fire_when_there_is_a_duty_to_act():
    """The ICAIL 2026 contrast: same `unom` rule in both cases; what changes is
    whether `Obl_*` or `¬Obl_*` is a premise."""
    model = {"strict_rules": [], "defeasible_rules": [
        "cf2lrc: CaFa_notPaCo_ChDi => LeReCa_notPaCo_ChDi",
        "unom: Om_notPaCo AND ¬Obl_PaCo => ¬cf2lrc",
    ]}
    with_duty = lrc.build_framework(
        {"premises": ["CaFa_notPaCo_ChDi", "Om_notPaCo", "Obl_PaCo"], "axioms": []}, model)
    without_duty = lrc.build_framework(
        {"premises": ["CaFa_notPaCo_ChDi", "Om_notPaCo", "¬Obl_PaCo"], "axioms": []}, model)

    assert lrc.relevance_report(with_duty, ["LeReCa_notPaCo_ChDi"])[0]["justified"] is True
    blocked = lrc.relevance_report(without_duty, ["LeReCa_notPaCo_ChDi"])[0]
    assert blocked["justified"] is False
    assert blocked["blocked_by"][0]["scheme"] == "unom"


# ----------------------------------------------------------------------
# O vocabulário, e a tabela que o explica
# ----------------------------------------------------------------------
def test_the_predicate_families_are_derived_from_one_registry():
    """`BINARY_PREDICATES` e companhia saem de `PREDICATES`, não de listas
    paralelas. Duas listas que dizem a mesma coisa são duas listas que
    divergem."""
    assert set(lrc.ALL_PREDICATES) == {p.name for p in lrc.PREDICATES}
    assert set(lrc.BINARY_PREDICATES) == {p.name for p in lrc.PREDICATES if p.arity == 2}
    assert set(lrc.UNARY_PREDICATES) == {p.name for p in lrc.PREDICATES if p.arity == 1}
    assert lrc.TERNARY_PREDICATES == ("SupersedingCause",)


def test_superseding_cause_parses_in_both_arities():
    """O artigo escreve `SupersedingCause(χ, φ, ψ)` (eqs. 4 e 5); este
    repositório sempre escreveu a forma abreviada, deixando φ e ψ implícitos
    na regra que consome o literal. As duas têm de ser lidas -- e a ternária
    era mal-parseada como um argumento só chamado `Ma_Ga_Ig`."""
    assert lrc.split_lrc_literal("SupersedingCause_Ma_Ga_Ig") == (
        "SupersedingCause", ["Ma", "Ga", "Ig"])
    assert lrc.split_lrc_literal("SupersedingCause_Ma") == ("SupersedingCause", ["Ma"])


def test_every_predicate_documents_its_roles_and_source():
    """A referência é gerada do registro, então cada predicado tem de trazer
    o que a tabela mostra: forma, leitura, o que afirma e onde está no
    artigo."""
    for entrada in lrc.predicate_reference():
        assert entrada["shape"].startswith(entrada["name"] + "_")
        assert len(entrada["roles"]) == entrada["arity"]
        assert entrada["label_pt"] and entrada["reading_pt"]
        assert entrada["source"]
        assert entrada["kind"] in ("factual", "doutrinario", "derivado", "conclusao")


def test_the_reference_reaches_the_page():
    from aspic import catalog
    from aspic.didactic import _predicate_reference_html

    body = _predicate_reference_html()
    for predicate in lrc.PREDICATES:
        assert f"{predicate.name}_" in body
    # a marcação da fonte vira HTML, e não texto literal
    assert "**" not in body
    assert "<strong>" in body and "<code>" in body
