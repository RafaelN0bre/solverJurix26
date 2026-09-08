"""Factors: polarity, the abstraction hierarchy, and cancellation.

`aspic.factors` implements the part of CATO (Aleven & Ashley; formalized in
Prakken, Wyner, Bench-Capon & Atkinson, JLC 2015) that a single case can
support. The precedent-driven schemes -- CS1, CS2, U1.1, U2.1, CS3, CS4 -- are
deliberately absent: each takes `outcome(prec)` or a `curr × prec` partition
among its premises, and this repository has no case base. These tests pin the
three pieces that are present, and the honesty checks around them.
"""
import pytest

from aspic import factors as F
from formalize.schema import AtomOut, CaseMeta, FormalizedCase, Query, RuleMeta


def atom(code, favors="neutro", abstract="", perspectives=()):
    return AtomOut(code=code, label_pt=f"o fato {code}", kind="fato",
                   status="controvertido", perspectives=list(perspectives),
                   evidence=[], dossier_refs=[], established=True,
                   favors=favors, abstract_factor=abstract)


@pytest.fixture
def record():
    """The shape of case-003's core dispute: two duties, opposite polarity,
    one abstract factor."""
    return FormalizedCase(
        case=CaseMeta(id="c", title="t", annotator="a", source_file="",
                      source_sha256=""),
        effect="Dano",
        atoms=[
            atom("DeverEspec", "responsabilizacao", "NaturezaDoDever", ["recorrido"]),
            atom("DeverGener", "exclusao", "NaturezaDoDever", ["recorrente"]),
            atom("Fuga", "responsabilizacao", "Conduta", ["recorrente", "recorrido"]),
            atom("TresMeses", "exclusao", "NexoCausal", ["recorrente"]),
            atom("Dano", "neutro", "", ["recorrente", "recorrido"]),
        ],
        knowledge_base={"premises": ["DeverEspec", "DeverGener", "Fuga",
                                     "TresMeses"], "axioms": []},
        causal_model={"strict_rules": [], "defeasible_rules": ["r0: Fuga => Dano"]},
        rules_meta=[RuleMeta(id="r0", rule="r0: Fuga => Dano", kind="causal",
                             gloss_pt="g", perspective="comum")],
        queries=[Query(phi="Fuga", psi="Dano", question_pt="?",
                       court_verdict="rejeitada", court_rationale_pt="—")],
    )


def test_opposite_factors_under_one_abstract_point_cancel(record):
    """The CATO device that turns two loose premises into one contested
    question -- and the thing a case-based reading buys that a plain
    premise list does not."""
    pairs = F.cancellations(record)
    assert len(pairs) == 1
    pro, against, abstract = pairs[0]
    assert (pro.code, against.code, abstract) == ("DeverEspec", "DeverGener",
                                                  "NaturezaDoDever")


def test_factors_of_the_same_side_do_not_cancel(record):
    """`cancels` needs opposite polarity; two pro-liability factors under one
    point reinforce each other, they do not annul it."""
    record.atoms[1].favors = "responsabilizacao"
    assert F.cancellations(record) == []


def test_a_factor_without_an_abstract_point_can_never_cancel(record):
    record.atoms[1].abstract_factor = ""
    assert F.cancellations(record) == []
    assert "DeverGener" in F.unclassified(record)


def test_balance_is_per_perspective_not_per_case(record):
    """A perspective's balance counts only what that perspective asserts --
    that is what makes it *its* reading rather than the case's."""
    whole = F.balance(record)
    assert len(whole["pro"]) == 2 and len(whole["against"]) == 2
    assert whole["lean"] == "empate"

    recorrido = F.balance(record, "recorrido")
    assert [f.code for f in recorrido["pro"]] == ["DeverEspec", "Fuga"]
    assert recorrido["against"] == []
    assert recorrido["lean"] == "responsabilizacao"


def test_partitions_say_where_two_positions_part_company(record):
    parts = F.partitions(record, "recorrido", "recorrente")
    assert parts["commonPro"] == ["Fuga"]
    assert parts["leftPro"] == ["DeverEspec"]
    assert parts["rightContra"] == ["DeverGener", "TresMeses"]


def test_a_record_without_polarity_is_reported_as_unannotated(record):
    """Not the same as a case where every fact is neutral: it is a case
    nobody was asked about, and the interface has to say so instead of
    drawing an empty balance."""
    assert F.is_annotated(record)
    for a in record.atoms:
        a.favors = "neutro"
    assert not F.is_annotated(record)


def test_the_view_shows_the_contested_points(record):
    from aspic.perspective_view import render_perspectives

    body = render_perspectives(record)
    assert "Fatores em disputa" in body
    assert "NaturezaDoDever" in body
    assert "não estão aqui" in body   # the precedent schemes, stated as absent
