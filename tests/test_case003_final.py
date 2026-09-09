"""The Caso 003 formalization by votes, end to end.

`docs/formalizacao-caso003.md` is the only case in the repository whose
outcome turns on a weighing rather than on an undercut, and the only one with
five perspectives and rules several of them hold on their own account. That
makes it the regression guard for three things at once -- the preference
ordering, multi-holder attribution, and the step-relative bridge -- and the
place where a change to any of them shows up as a different reading of a real
judgment rather than as a different number in a fixture.

What is asserted here is the *shape* of the result and the two turns of the
trace, not every literal: `test_translated_regression` already pins the
stored verdicts literal by literal for every case on disk.
"""
import pytest

from aspic import lrc as lrc_vocab
from aspic import perspectives as P
from aspic import preferences as PR
from aspic.catalog import DEFAULT_TRANSLATED_DIR
from aspic.graph_export import argument_status
from formalize import build
from formalize.schema import FormalizedCase

CASE_FILE = DEFAULT_TRANSLATED_DIR / "case-003-final" / "case.json"
pytestmark = pytest.mark.skipif(
    not CASE_FILE.is_file(),
    reason="rode scripts/build_case003_final.py para gravar o caso")

TARGET = "LeReCa_OmiEstatal_Danos"


@pytest.fixture
def record():
    return FormalizedCase.model_validate_json(CASE_FILE.read_text(encoding="utf-8"))


def labels(af):
    extension, _ = af.compute_grounded_extension()
    status = argument_status(af, extension)
    return {argument.conclusion: status[argument.id]
            for argument in af.arguments.values() if argument.defeasible_rules}


# ----------------------------------------------------------------------
# The tuple, and what it decides
# ----------------------------------------------------------------------
def test_the_case_declares_the_three_dimensions_with_the_given_weights(record):
    model = build.preference_model(record)
    assert model.weights == {"dever_especifico": 4.0,
                             "intervencao_causal": 5.0, "autonomia": 5.0}
    assert model.principle == PR.WEAKEST_LINK


def test_the_weighing_decides_the_duty_and_only_the_duty(record):
    """⟨q0, q2⟩ is the document's own "único ponto ativo", and it stays the
    only one: every other conflict in both layers is an undercut, which no
    preference touches."""
    lrc_af = build.lrc_framework(record)
    resolved = labels(lrc_af)
    assert resolved["¬DeverEspec"] == "IN"
    assert resolved["DeverEspec"] == "OUT"

    conflicts = PR.resolved_conflicts(lrc_af)
    assert {(row["attacker_conclusion"], row["target_conclusion"])
            for row in conflicts} == {("DeverEspec", "¬DeverEspec"),
                                      ("¬DeverEspec", "DeverEspec")}
    # The cause-in-fact layer is decided entirely by undercutting, exactly as
    # the document's "Pontos sensíveis a preferência: nenhum" says.
    assert PR.resolved_conflicts(build.cif_framework(record)) == []


def test_the_ordering_is_a_move_of_the_dissenting_vote(record):
    """Prakken §4.3: um argumento de prioridade é **movimento**, não fato.

    A ordenação injetada em toda projeção valia já no passo 0, onde nenhum
    adjudicador falou -- e ali uma preferência decidiria um rebate entre as
    partes por autoridade de ninguém. Agora o bloco nomeia quem a move, e uma
    projeção que ainda não o admitiu roda sob a ordenação básica.
    """
    assert record.preferences.perspective == "voto_divergente"
    ativa = {}
    admitidas = []
    for key in ("recorrente", "recorrido", "relator",
                "voto_convergente", "voto_divergente"):
        admitidas.append(key)
        ativa[key] = P.project_lrc(record, list(admitidas)).preferences is not None
    assert ativa == {"recorrente": False, "recorrido": False, "relator": False,
                     "voto_convergente": False, "voto_divergente": True}
    # E o caso inteiro, onde todas as vozes falaram, roda com ela.
    assert build.preference_model(record) is not None


def test_the_ordering_follows_definition_21(record):
    """Premissas **e** regras, conjuntamente -- e por isso as premissas do
    caso são classificadas nos mesmos três eixos dos átomos."""
    model = build.preference_model(record)
    assert model.principle == PR.WEAKEST_LINK
    assert model.comparator == PR.ELITIST
    ranked = {p.rule for p in record.preferences.profiles}
    assert {"RegFechado", "LapsoTemp", "FormacaoQuad"} <= ranked

    af = build.lrc_framework(record)
    esp = next(a for a in af.arguments.values() if a.conclusion == "DeverEspec")
    gen = next(a for a in af.arguments.values() if a.conclusion == "¬DeverEspec")
    assert model.precedes(sorted(esp.ordinary_premises),
                          sorted(gen.ordinary_premises)) is True
    assert model.precedes(list(esp.defeasible_rules),
                          list(gen.defeasible_rules)) is True

    # Só com as regras -- a versão anterior -- a Def. 21 fica muda.
    so_regras = PR.PreferenceModel(
        model.dimensions,
        [pr for pr in model.profiles.values()
         if pr.rule_id not in ("RegFechado", "LapsoTemp", "FormacaoQuad")])
    assert so_regras.is_weaker(esp, gen) is False


def test_without_the_weights_the_layer_answers_nothing(record):
    """The control. Under the basic ordering the mutual rebut leaves both
    qualifications UNDEC, and with them the exception (`dvpre_q8`) and the
    defence that needs the duty absent (`unom_q7`) -- so the layer reports no
    relevance for a reason that is not a decision."""
    plain = record.model_copy(deep=True)
    plain.preferences = None
    resolved = labels(build.lrc_framework(plain))
    assert resolved["DeverEspec"] == "UNDEC"
    assert resolved["¬DeverEspec"] == "UNDEC"
    assert resolved["¬cf2lrc_q5"] == "UNDEC"


def test_the_case_turns_when_the_duty_outweighs_the_other_two(record):
    """4 against 5 + 5 loses; above 10 it wins. Anyone who wants to defend a
    different number needs to know that this is where it would matter."""
    def duty_wins(weight):
        probed = record.model_copy(deep=True)
        for dimension in probed.preferences.dimensions:
            if dimension.key == "dever_especifico":
                dimension.weight = weight
        return labels(build.lrc_framework(probed))["DeverEspec"] == "IN"

    assert not duty_wins(4.0)
    assert not duty_wins(10.0)       # exact tie: incomparable again
    assert duty_wins(10.5)


# ----------------------------------------------------------------------
# The two layers, and where each one decides
# ----------------------------------------------------------------------
def test_the_cause_in_fact_layer_already_denies_the_omission(record):
    """The document puts the divergence's break in both layers (r7 undercuts
    r2; q6/q7 undercut q5). In the full framework the first one is enough:
    with r2 out, the damage is still derived -- through r6 -- but no longer
    through the State's omission.
    """
    af = build.cif_framework(record)
    assert "Danos" in af.justified_conclusions()
    assert af.ness_cause("OmiEstatal", "Danos") is False
    assert af.ness_cause("Latrocinio", "Danos") is True
    assert lrc_vocab.cafa("OmiEstatal", "Danos") not in record.lrc.bridged_premises


def test_the_claim_was_never_formulated_not_defeated(record):
    """A distinção que o registro publicava errada.

    `LeReCa_OmiEstatal_Danos` não é conclusão de argumento nenhum: sem
    `CaFa_OmiEstatal_Danos`, `cf2lrc_q5` não tem antecedente e a presunção
    nunca dispara. As defesas `sc` e `unom` estão no framework e teriam
    bloqueado a pretensão -- só que não chegaram a fazê-lo. Dizer que a
    bloquearam credita ao direito um resultado que os fatos já produziram.
    """
    entry = next(e for e in record.lrc.relevance if e["target"] == TARGET)
    assert entry["justified"] is False
    assert entry["derivable"] is False
    assert entry["status"] == "nao_formulada"
    assert entry["blocked_by"] == []


def test_a_defence_that_wins_by_rebutting_is_reported_too(record):
    """`relevance_report` lia só undercuts, e undercut é justamente o que
    uma preferência não decide -- então a camada ficava cega onde os pesos
    trabalham. Agora os bloqueios saem dos defeats do framework."""
    from aspic.solver import ArgumentationFramework

    kb = {"premises": ["CaFa_A_B", "Forte"], "axioms": []}
    rules = {"strict_rules": [], "defeasible_rules": [
        "cf2lrc_A: CaFa_A_B => LeReCa_A_B",
        "nwo_A: Forte => ¬LeReCa_A_B"]}

    # Sem preferência o rebut é mútuo, os dois ficam UNDEC e nada *aceito*
    # bloqueia: a pretensão não é reconhecida nem afastada.
    plain = lrc_vocab.relevance_report(ArgumentationFramework(kb, rules),
                                       ["LeReCa_A_B"])[0]
    assert plain["derivable"] is True
    assert plain["blocked_by"] == []

    # Com a defesa preferida, ela vence por rebut -- e é este o caso que a
    # versão anterior de `relevance_report`, que só lia undercuts, não via.
    # Premissas e regras, porque a Def. 21 compara as duas.
    model = PR.PreferenceModel(
        [PR.Dimension("d", "eixo", 5.0)],
        [PR.RuleProfile("CaFa_A_B", {"d": 0.2}), PR.RuleProfile("Forte", {"d": 1.0}),
         PR.RuleProfile("cf2lrc_A", {"d": 0.2}), PR.RuleProfile("nwo_A", {"d": 1.0})])
    entry = lrc_vocab.relevance_report(
        ArgumentationFramework(kb, rules, preferences=model), ["LeReCa_A_B"])[0]
    assert entry["status"] == "afastada"
    assert {b["attack_type"] for b in entry["blocked_by"]} == {"rebut"}
    assert {b["scheme"] for b in entry["blocked_by"]} == {"nwo"}


def test_the_solver_lands_where_the_court_landed(record):
    from formalize.validate import build_comparison

    agreements = {row["agreement"] for row in build_comparison(record)}
    assert agreements == {"match"}


# ----------------------------------------------------------------------
# Multi-holder attribution
# ----------------------------------------------------------------------
def test_a_rule_three_voices_hold_belongs_to_three_theories(record):
    """r2 is the chain's central step, held by the respondent and by two
    justices. Read through a single `perspective` it would belong to one of
    them, and the other two would have a theory that derives nothing."""
    for key in ("recorrido", "relator", "voto_convergente"):
        assert "r2" in P.project(record, [key]).rule_ids
    assert "r2" not in P.project(record, ["recorrente"]).rule_ids


def test_every_voice_of_the_document_is_on_the_roll_call(record):
    assert P.perspectives_in(record) == [
        "recorrente", "recorrido", "relator", "voto_convergente", "voto_divergente"]


def test_a_move_counts_only_what_it_adds_to_the_graph(record):
    """The concurring vote holds r1 and r2 as well, but both are already in
    play when it speaks; its move is r8 alone."""
    trace = P.adjudication_trace(record)
    by_vote = {step["added"]: step["new_rules"] for step in trace}
    assert by_vote["voto_convergente"] == ["r8"]
    assert by_vote["voto_divergente"] == ["r6", "r7"]


# ----------------------------------------------------------------------
# The step-relative bridge
# ----------------------------------------------------------------------
def test_the_claim_lives_in_exactly_one_window_of_the_decision_phase(record):
    """The whole point of re-deriving the bridge per step: the claim is not
    dead from the start and alive at the end, it is alive between the
    concurring vote -- which removes the appellant's undercut and lets the
    omission become a cause in fact -- and the dissent."""
    trace = P.decision_trace(record)
    relevant = [step["added"] for step in trace if step["relevance"][TARGET]]
    assert relevant == ["voto_convergente"]

    released = [step["added"] for step in trace if step["newly_relevant"]]
    blocked = [step["added"] for step in trace if step["newly_blocked"]]
    assert released == ["voto_convergente"]
    assert blocked == ["voto_divergente"]


def test_the_bridge_of_a_step_is_the_solvers_word_for_that_step(record):
    """Before the concurring vote there is no `CaFa_OmiEstatal_Danos` to
    presume relevant, and the stored (whole-case) list does not have one
    either -- but for the one step in between, it does."""
    trace = {step["added"]: step["bridged"] for step in P.decision_trace(record)}
    cafa = lrc_vocab.cafa("OmiEstatal", "Danos")
    assert cafa not in trace["relator"]
    assert cafa in trace["voto_convergente"]
    assert cafa not in trace["voto_divergente"]


def test_the_parties_alone_establish_no_cause_in_fact(record):
    """The argumentation phase ends with the appellant's undercut unanswered,
    so the graph the parties hand over derives no damage at all. That is
    Prakken's point: the adjudicator has something left to decide."""
    assert P.bridged_for(record, ["recorrente", "recorrido"]) == []


# ----------------------------------------------------------------------
# The view
# ----------------------------------------------------------------------
def test_the_weights_view_shows_the_tuple_the_conflict_and_the_control(record):
    from aspic.preference_view import render_preferences

    body = render_preferences(record)
    assert "especificidade no dever de agir" in body
    assert "dvgen_q1" in body
    assert "UNDEC" in body            # the control run, without the weights
    assert "Vira em" in body          # the sensitivity table


def test_the_map_draws_the_contradiction_and_marks_the_rule_that_lost(record):
    """A rebut settled by preference has to be visible: the losing rule is
    not undercut by anything, so a map that only drew undercuts would show
    it standing while the solver has it OUT."""
    dot = P.to_adjudication_dot(record)
    assert '"dvgen_q2" -> "dvesp_q0"' in dot or '"dvesp_q0" -> "dvgen_q2"' in dot
    assert "rebut from-" in dot
    fallen = P.defeated_rules(record)
    assert {"dvesp_q0", "dvpre_q8"} <= fallen      # lost the weighing
    assert {"r2", "r5"} <= fallen                  # undercut
    assert "dvgen_q2" not in fallen


def test_the_dossier_of_the_original_formalization_is_reachable(record):
    """Two formalizations of one judgment; the second must not lose the
    annotator's evidence just because it has a different case id."""
    from aspic import catalog

    assert record.case.dossier_id == "case-003"
    assert catalog.dossier_by_id("case-003-final") is not None
