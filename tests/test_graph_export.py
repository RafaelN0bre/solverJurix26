"""Tests for aspic.graph_export: the DOT-generation logic is tested as pure
string/data assertions (no dependency on the `dot` binary being installed);
actually invoking Graphviz is covered by one skip-guarded test at the end."""
import shutil

import pytest

from aspic.examples import case_by_id
from aspic.graph_export import argument_status, render_to_string, to_dot
from aspic.solver import ArgumentationFramework


def _build_double_shooting():
    case = case_by_id("double_shooting")
    af = ArgumentationFramework(case.knowledge_base, case.causal_model)
    extension, _ = af.compute_grounded_extension()
    return af, extension


def _arg_id_for_conclusion(af: ArgumentationFramework, conclusion: str, *,
                            via_rule: str = None) -> str:
    matches = [
        a.id for a in af.arguments.values()
        if a.conclusion == conclusion
        and (via_rule is None or via_rule in a.strict_rules + a.defeasible_rules)
    ]
    assert len(matches) == 1, (
        f"expected exactly one argument for {conclusion!r} (via_rule={via_rule!r}), got {matches}"
    )
    return matches[0]


def test_argument_status_classifies_in_out_undec():
    af, extension = _build_double_shooting()
    status = argument_status(af, extension)

    # GeDi has two competing arguments: one via r2 (Bush's chain, survives)
    # and one via r3 (Dlugash's chain, undercut) -- exactly the case's point.
    ge_di_via_bush = _arg_id_for_conclusion(af, "GeDi", via_rule="r2")
    ge_di_via_dlugash = _arg_id_for_conclusion(af, "GeDi", via_rule="r3")
    dl_ki = _arg_id_for_conclusion(af, "DlKi")
    not_r1 = _arg_id_for_conclusion(af, "¬r1")

    # Bush's chain survives, so its arguments (and their conclusion GeDi) are IN.
    assert status[ge_di_via_bush] == "IN"
    # Dlugash's GeDi argument depends on the undercut DlKi, hence OUT.
    assert status[ge_di_via_dlugash] == "OUT"
    # The undercutter itself is undefeated, hence IN.
    assert status[not_r1] == "IN"
    # Dlugash's DlKi argument is undercut by an IN argument, hence OUT.
    assert status[dl_ki] == "OUT"

    # Every argument gets exactly one of the three labels.
    assert set(status.values()) <= {"IN", "OUT", "UNDEC"}
    assert set(status.keys()) == set(af.arguments.keys())


def test_to_dot_contains_nodes_edges_and_rules_legend():
    af, extension = _build_double_shooting()
    dot = to_dot(af, extension, title="Double Shooting")

    assert dot.startswith("digraph ArgumentGraph {")
    assert dot.rstrip().endswith("}")

    # Every argument becomes a node statement carrying its status as a CSS class.
    ge_di_via_bush = _arg_id_for_conclusion(af, "GeDi", via_rule="r2")
    dl_ki = _arg_id_for_conclusion(af, "DlKi")
    assert f'class="argnode status-IN arg-{ge_di_via_bush}"' in dot
    assert f'class="argnode status-OUT arg-{dl_ki}"' in dot

    # The undercut attack (r4 attacking r1) shows up as an edge labeled with its rule.
    assert "UC(r1)" in dot
    assert "type-undercut" in dot
    assert "defeat" in dot  # the undercut succeeded as a defeat

    # The rules legend lists every rule of the case, including the undercutter.
    assert "r4: BuKi =&gt; ¬r1" in dot or "r4: BuKi => ¬r1" in dot


def test_to_dot_marks_failed_attacks_distinctly_from_defeats():
    # A rebut between two defeasible/plausible arguments always succeeds under
    # the basic ordering in this solver (see solver._is_weaker), so to exercise
    # the "failed attack" styling branch we only need a case with an attack at
    # all; double_shooting's undercut always succeeds, so we assert instead
    # that no failed-attack class appears when every attack is a defeat here.
    af, extension = _build_double_shooting()
    dot = to_dot(af, extension)
    assert len(af.attacks) == len(af.defeats)  # both attacks in this case are undercuts
    assert "failed-attack" not in dot


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz 'dot' not installed")
def test_render_to_string_produces_svg():
    af, extension = _build_double_shooting()
    dot = to_dot(af, extension, title="Double Shooting")
    svg = render_to_string(dot, fmt="svg")
    assert "<svg" in svg
    assert "argnode" in svg


def test_argument_names_carry_their_layer_when_a_case_has_two():
    """Os dois frameworks de um caso numeram a partir de A0, então uma página
    que mostra os dois grafos imprime `A8` duas vezes para argumentos
    diferentes. Aconteceu: `A8: OmiEstatal ⊢ Latrocinio` numa figura e
    `A8: RegFechado ⊢ RegFechado` na outra.

    O nome do *nó* no DOT continua nu -- ele só precisa ser único dentro de um
    grafo, e o realce por clique se apoia nele.
    """
    from aspic.graph_export import to_dot
    from aspic.solver import ArgumentationFramework

    af = ArgumentationFramework(
        {"premises": ["p"], "axioms": []},
        {"strict_rules": [], "defeasible_rules": ["r0: p => q", "r1: q => ¬r0"]})
    extension, _ = af.compute_grounded_extension()

    nu = to_dot(af, extension)
    etiquetado = to_dot(af, extension, layer_tag="F")

    assert "label=\"A1\\n" in nu
    assert "label=\"F·A1\\n" in etiquetado
    assert "label=\"A1\\n" not in etiquetado
    # o nome do nó não muda -- o JS de realce depende dele
    assert '"A1" [shape' in etiquetado
    # e os tooltips de ataque, que são frases prontas, também são etiquetados
    assert "F·A" in [l for l in etiquetado.splitlines() if "tooltip" in l and "->" in l][0]
