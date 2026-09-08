"""The persisted record's contract.

`case.json` is read by three different consumers -- the interface, the
regression tests and whoever audits the article -- so its shape has to survive
a round trip and its solver-facing fields have to be exactly what
`ArgumentationFramework` expects, with no adapter in between.
"""
from aspic.solver import ArgumentationFramework
from formalize.schema import (
    SCHEMA_VERSION, CaseMeta, FormalizedCase, LRCBlock, LrcPremiseOut, LrcRuleOut,
)


def minimal_case() -> FormalizedCase:
    return FormalizedCase(
        case=CaseMeta(id="c", title="C", annotator="a", source_file="f", source_sha256="h"),
        knowledge_base={"premises": ["Leuc", "¬Consent"], "axioms": []},
        causal_model={"strict_rules": [],
                      "defeasible_rules": ["r0: Leuc => Morte", "r1: Consent => Quimio",
                                           "r2: Quimio => ¬r0"]},
        effect="Morte",
    )


def test_round_trips_through_json():
    case = minimal_case()
    again = FormalizedCase.model_validate_json(case.model_dump_json())
    assert again.model_dump() == case.model_dump()
    assert again.schema_version == SCHEMA_VERSION


def test_solver_consumes_the_record_directly():
    """No adapter between the persisted dicts and the solver -- that is the
    whole point of the intermediate format."""
    case = minimal_case()
    af = ArgumentationFramework(case.knowledge_base, case.causal_model)
    assert "Morte" in af.justified_conclusions()


def test_lrc_block_assembles_its_own_framework_input():
    block = LRCBlock(
        bridged_premises=["CaFa_Leuc_Morte"],
        doctrinal_premises=[LrcPremiseOut(literal="Obl_Consent", label_pt="dever", evidence=[])],
        scheme_rules=[LrcRuleOut(rule="cf2lrc_Leuc: CaFa_Leuc_Morte => LeReCa_Leuc_Morte",
                                 scheme="cf2lrc", gloss_pt="g", evidence=[])],
        targets=["LeReCa_Leuc_Morte"],
    )
    assert block.knowledge_base == {"premises": ["CaFa_Leuc_Morte", "Obl_Consent"], "axioms": []}
    af = ArgumentationFramework(block.knowledge_base, block.causal_model)
    assert "LeReCa_Leuc_Morte" in af.justified_conclusions()


def test_negated_atoms_get_a_gloss_for_free():
    """Omissions appear as `¬X` in rules and queries; the didactic view needs a
    Portuguese reading for them without the model having to enumerate it."""
    from formalize.schema import AtomOut

    case = minimal_case()
    case.atoms = [AtomOut(code="Consent", label_pt="os pais consentiram", kind="fato",
                          status="controvertido", perspectives=[], evidence=[],
                          dossier_refs=[], established=True)]
    glosses = case.atom_glosses()
    assert glosses["Consent"] == "os pais consentiram"
    assert glosses["¬Consent"] == "não é o caso de que os pais consentiram"
    assert case.atom_by_code("¬Consent").code == "Consent"
