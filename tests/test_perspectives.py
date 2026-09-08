"""One framework per perspective, and the votes as adjudication moves.

`aspic.perspectives` implements the three-player decomposition of Prakken,
"A Formal Model of Adjudication Dialogues" (AI & Law 2008): the adversaries
build the graph in the argumentation phase, and the adjudicator moves
arguments -- undercutters and priority arguments -- in the decision phase.
These tests pin the two properties that make the decomposition worth having:
a perspective's theory is *runnable on its own*, and the trace names the
exact move at which a claim stops being justified.
"""
import pytest

from aspic import perspectives as P
from formalize.schema import (
    AtomOut, FormalizedCase, CaseMeta, LRCBlock, LrcPremiseOut, LrcRuleOut,
    Query, RuleMeta,
)


def atom(code, kind="fato", perspectives=(), established=True):
    return AtomOut(code=code, label_pt=f"o fato {code}", kind=kind,
                   status="controvertido", perspectives=list(perspectives),
                   evidence=[], dossier_refs=[], established=established)


@pytest.fixture
def record():
    """A miniature dispute with the shape of case-003: the parties build a
    causal chain, one vote adds a parallel route, and the doctrinal defence
    that decides the case lives in the legal-relevance layer."""
    return FormalizedCase(
        case=CaseMeta(id="case-mini", title="Mini", annotator="t",
                      source_file="", source_sha256=""),
        effect="Dano",
        atoms=[
            atom("Omis", perspectives=["recorrido", "relator"]),
            atom("Dever", kind="dever", perspectives=["recorrido"]),
            atom("Prova", kind="prova", perspectives=["relator"]),
            atom("Elo", kind="intermediario", established=False),
            atom("Dano", kind="resultado", established=False),
        ],
        knowledge_base={"premises": ["Omis", "Dever", "Prova"], "axioms": []},
        causal_model={"strict_rules": [], "defeasible_rules": [
            "r0: Omis AND Dever => Elo", "r1: Prova => Elo", "r2: Elo => Dano"]},
        rules_meta=[
            RuleMeta(id="r0", rule="r0: Omis AND Dever => Elo", kind="causal",
                     gloss_pt="a omissão leva ao elo", perspective="recorrido"),
            RuleMeta(id="r1", rule="r1: Prova => Elo", kind="causal",
                     gloss_pt="a falta de prova leva ao elo", perspective="relator"),
            RuleMeta(id="r2", rule="r2: Elo => Dano", kind="causal",
                     gloss_pt="o elo causa o dano", perspective="comum"),
        ],
        queries=[Query(phi="Omis", psi="Dano", question_pt="A omissão causou o dano?",
                       court_verdict="rejeitada", court_rationale_pt="—")],
        lrc=LRCBlock(
            bridged_premises=["CaFa_Omis_Dano", "ButFor_Omis_Dano"],
            doctrinal_premises=[
                LrcPremiseOut(literal="Om_Omis", label_pt="é omissão", evidence=[],
                              perspective="voto_divergente",
                              origin_perspective="recorrente"),
                LrcPremiseOut(literal="¬Obl_Agir", label_pt="não havia dever",
                              evidence=[], perspective="voto_divergente",
                              origin_perspective="recorrente"),
            ],
            scheme_rules=[
                LrcRuleOut(rule="cf2lrc_Omis: CaFa_Omis_Dano => LeReCa_Omis_Dano",
                           scheme="cf2lrc", gloss_pt="presunção", evidence=[],
                           perspective="comum"),
                LrcRuleOut(rule="unom_Omis: Om_Omis AND ¬Obl_Agir => ¬cf2lrc_Omis",
                           scheme="unom", gloss_pt="omissão sem dever", evidence=[],
                           perspective="voto_divergente",
                           origin_perspective="recorrente"),
            ],
            targets=["LeReCa_Omis_Dano"],
        ),
    )


# ----------------------------------------------------------------------
# Projection
# ----------------------------------------------------------------------
def test_a_theory_carries_its_own_rules_and_the_undisputed_ones(record):
    theory = P.project(record, ["recorrido"])
    assert theory.rule_ids == ["r0", "r2"]      # r1 is the relator's
    assert "Prova" not in theory.premises        # and so is its premise


def test_a_theory_is_runnable_on_its_own(record):
    """The point of the decomposition: each perspective's theory has to
    derive something, otherwise it reports nothing."""
    theory = P.project(record, ["recorrido"])
    af = theory.framework()
    af.compute_grounded_extension()
    assert "Dano" in af.justified_conclusions()


def test_premises_include_what_the_perspective_asserts(record):
    """`Dever` is read by r0, `Omis` is asserted by the relator too -- both
    belong to the relator's theory even though only one of its rules reads
    one of them."""
    theory = P.project(record, ["relator"])
    assert "Prova" in theory.premises            # read by r1
    assert "Omis" in theory.premises             # asserted by the relator


def test_perspectives_are_found_in_both_layers(record):
    """A court that decides the case entirely through doctrinal defences
    contributes no cause-in-fact rule; scanning only that layer would report
    that it took no part in the judgment."""
    found = P.perspectives_in(record)
    assert "voto_divergente" in found
    assert found.index("recorrido") < found.index("voto_divergente")


# ----------------------------------------------------------------------
# The two phases
# ----------------------------------------------------------------------
def test_argumentation_phase_reaches_the_outcome_without_any_vote(record):
    """Emergent soundness: the adversaries' own theories already justify the
    outcome, before any adjudicator moves."""
    trace = P.adjudication_trace(record)
    assert trace[0]["added"] is None
    assert trace[0]["outcome_justified"] is True


def test_a_parallel_route_removes_but_for_without_removing_the_cause(record):
    """A concurring vote with its own grounds can *weaken* the counterfactual
    case for the very conclusion it supports: with a second route to the same
    link, the omission stops being necessary while staying a NESS cause."""
    before = P.verdicts(P.project(record, ["recorrido"]), record.queries)
    after = P.verdicts(P.project(record, ["recorrido", "relator"]), record.queries)
    key = "Omis->Dano"
    assert before[key]["but_for"] is True
    assert after[key]["but_for"] is False
    assert after[key]["ness"] is True


def test_decision_phase_names_the_move_that_flips_the_label(record):
    """The question the single framework cannot answer: not whether the
    court's position wins, but at which move it starts to."""
    trace = P.decision_trace(record)
    assert trace[0]["relevance"]["LeReCa_Omis_Dano"] is True      # presumption
    flip = [step for step in trace if step["newly_blocked"]]
    assert len(flip) == 1
    assert flip[0]["added"] == "voto_divergente"
    assert flip[0]["newly_blocked"] == ["LeReCa_Omis_Dano"]


def test_the_general_presumption_is_never_attributed_to_a_party(record):
    """`cf2lrc` is the paper's own rule, held by nobody in particular, so it
    is admitted at step 0 -- otherwise nothing would be presumed relevant and
    every defence would have nothing to knock down."""
    assert P.project_lrc(record, []).rule_ids == ["cf2lrc_Omis"]


def test_unattributed_defences_are_reported(record):
    """A defence with no author is admitted at every step, so it can never
    appear as a move: the count is the honest measure of how much of the
    adjudication the trace cannot place."""
    assert P.unattributed_lrc_rules(record) == []
    record.lrc.scheme_rules[1].perspective = ""
    assert P.unattributed_lrc_rules(record) == ["unom_Omis"]
    assert P.decision_trace(record) == [] or all(
        not step["newly_blocked"] for step in P.decision_trace(record))


# ----------------------------------------------------------------------
# The map and the rendered view
# ----------------------------------------------------------------------
def test_the_map_puts_each_rule_in_its_author_lane(record):
    dot = P.to_adjudication_dot(record)
    assert 'label="ADJUDICADORES"' in dot
    assert 'label="VOTO DIVERGENTE"' in dot
    assert 'label="RECORRIDO"' in dot
    # the undercut crosses the lanes, drawn as an attack
    assert '"unom_Omis" -> "cf2lrc_Omis"' in dot
    # and the presumption it hits is drawn as defeated
    assert "cf2lrc_Omis" in P.defeated_rules(record)


def test_the_map_shows_support_as_well_as_attack(record):
    """`suca` derives what `sc` consumes; without the support edge the
    characterisation of a superseding cause looks unconnected."""
    record.lrc.scheme_rules.append(
        LrcRuleOut(rule="suca_Z: CaFa_Omis_Dano => SupersedingCause_Z",
                   scheme="suca", gloss_pt="caracteriza", evidence=[],
                   perspective="voto_divergente"))
    record.lrc.scheme_rules.append(
        LrcRuleOut(rule="sc_Omis: SupersedingCause_Z => ¬cf2lrc_Omis",
                   scheme="sc", gloss_pt="afasta", evidence=[],
                   perspective="voto_divergente"))
    dot = P.to_adjudication_dot(record)
    assert '"suca_Z" -> "sc_Omis"' in dot
    assert "support from-suca_Z" in dot


def test_long_literals_are_shortened_for_the_diagram(record):
    assert P.short_literal("CaFa_Omis_Dano") == "causa(Omis)"
    assert P.short_literal("¬Obl_Agir") == "¬dever(Agir)"
    assert P.short_literal("Desconhecido_X") == "Desconhecido_X"


def test_the_view_names_the_turning_point(record):
    from aspic.perspective_view import render_perspectives

    body = render_perspectives(record, title="Mini")
    assert "Fase de argumentação" in body
    assert "Fase de decisão" in body
    # The move is named, not merely highlighted: a reader has to be able to
    # see *which* vote turned the case without reading the colours.
    assert "a pretensão cai aqui" in body
    assert "Voto divergente" in body


# ----------------------------------------------------------------------
# Naming and tracing the arguments
# ----------------------------------------------------------------------
def test_arguments_keep_the_solver_ids_so_the_views_agree(record):
    """The whole point of naming them: `A7` in the adjudication view has to
    be `A7` in the argument graph, in the relevance report and in the
    preference table. A view that renumbered for its own tidiness would make
    the four mutually untraceable."""
    from formalize import build

    mapped = {a.id for a in P.mapped_arguments(record) if a.layer == "cif"}
    assert mapped == set(build.cif_framework(record).arguments)


def test_an_argument_belongs_to_whoever_holds_every_rule_it_uses(record):
    """An argument is not moved by anyone -- it is what a theory can build.
    `r0` is the respondent's and `r2` is undisputed, so the chain through
    both is the respondent's alone; the relator's `r1` is not in it."""
    by_id = {a.id: a for a in P.mapped_arguments(record) if a.layer == "cif"}
    chain = next(a for a in by_id.values()
                 if a.conclusion == "Dano" and "r0" in a.rules)
    assert chain.holders == ["recorrido"]
    assert "relator" not in chain.holders


def test_a_bridge_premise_is_held_by_nobody(record):
    """`CaFa_*` is the cause-in-fact solver's output, not a party's claim.
    Listing every perspective as holding it would read as unanimity where
    nothing was asserted."""
    bridge = [a for a in P.mapped_arguments(record)
              if a.layer == "lrc" and a.origin == "ponte"]
    assert bridge
    assert all(a.holders == [] for a in bridge)


def test_every_rule_traces_to_the_arguments_it_topped(record):
    by_rule = P.arguments_by_rule(record)
    assert by_rule["r0"]
    assert all(a.top_rule == "r0" for a in by_rule["r0"])
    # A rule whose antecedents were never satisfied tops nothing, which is a
    # different statement from having been defeated.
    assert "r99" not in by_rule


def test_the_map_names_the_arguments_on_the_rule_nodes(record):
    dot = P.to_adjudication_dot(record)
    for argument in P.arguments_by_rule(record)["r0"]:
        assert argument.label in dot


def test_argument_labels_carry_their_layer(record):
    """The map draws both layers at once and they number independently, so a
    bare id names two arguments. It really happened: case-003-final drew
    `A17` twice, for the concurring vote's `r8` and the reporting judge's
    `dvpre_q8`."""
    by_layer = {}
    for argument in P.mapped_arguments(record):
        by_layer.setdefault(argument.layer, set()).add(argument.id)
    if len(by_layer) > 1:
        cif, lrc = by_layer["cif"], by_layer["lrc"]
        assert cif & lrc, "sem colisão de ids, o teste não prova nada"
    labels = [a.label for a in P.mapped_arguments(record)]
    assert len(labels) == len(set(labels))
    assert all(label[:2] in ("F·", "R·") for label in labels)


def test_the_view_carries_a_rules_legend_and_an_argument_table(record):
    from aspic.perspective_view import render_perspectives

    body = render_perspectives(record, title="Mini")
    assert "Legenda das regras" in body
    assert "Os argumentos, um a um" in body
    # The legend has to spell out the rule the map only abbreviates.
    assert "Omis AND Dever =&gt; Elo" in body or "Omis AND Dever => Elo" in body


# ----------------------------------------------------------------------
# Two vocabularies, one roll call
# ----------------------------------------------------------------------
def test_the_dossier_spelling_is_aliased_to_the_pipeline_one():
    """The annotation tool writes `convergente`; the prompts say
    `voto_convergente`. Unmapped, Fachin's reconstruction renders as a bare
    "Convergente" and sorts after the court."""
    from formalize.dossier import canonical_perspective, perspective_label, perspective_sort_key

    assert canonical_perspective("convergente") == "voto_convergente"
    assert perspective_label("divergente") == "Voto divergente"
    assert perspective_sort_key("convergente") < perspective_sort_key("stf_final")
    # anything the table has not caught still travels intact
    assert canonical_perspective("amicus_curiae") == "amicus_curiae"


def test_a_record_using_the_dossier_spelling_groups_with_the_canonical_one(record):
    record.lrc.scheme_rules[1].perspective = "divergente"
    assert "voto_divergente" in P.perspectives_in(record)
    assert "divergente" not in P.perspectives_in(record)
    flip = [s for s in P.decision_trace(record) if s["newly_blocked"]]
    assert flip and flip[0]["added"] == "voto_divergente"


def test_a_perspective_that_moved_nothing_still_gets_a_box(record):
    """Prakken's decision phase makes silence substantive: an adjudicator who
    moves no argument has endorsed what is there. A box that disappears
    reports a judgment with fewer participants than it had."""
    dot = P.to_adjudication_dot(record, known=["relator", "voto_convergente"])
    assert 'label="VOTO CONVERGENTE"' in dot
    assert 'label="RELATOR"' in dot
    assert P.SILENT_NOTE in dot
    assert '"silent_voto_convergente"' in dot
