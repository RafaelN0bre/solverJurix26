"""HTML rendering of the NESS test and the causal-comparison panel (plain
NESS vs `is_cause` vs `but_for`) shown below each case's argument graph.

This module formats output from `aspic.ness` (plain NESS sufficiency and
necessity) and `ArgumentationFramework.is_cause` / `.but_for` (solver.py);
it does not implement any new causal-reasoning logic of its own.
"""
import html as _html

from typing import List

from .examples import CausalQuery
from .graph_export import render_to_string, to_dot
from .ness import is_ness_cause, necessary_elements, sufficient_sets
from .solver import ArgumentationFramework, negate_literal


def ness_html_table(af: ArgumentationFramework, psi: str) -> str:
    """HTML rendering of what `aspic.ness.ness_report` prints as text: every
    subset-minimal sufficient set for psi, and which of its elements are
    individually necessary within that set."""
    rules = list(af.rules.values())
    sets = sufficient_sets(af, psi)
    if not sets:
        return f'<p class="ness-empty">No justified argument concludes <code>{_html.escape(psi)}</code>.</p>'

    rows = []
    for i, s in enumerate(sets, start=1):
        necessary = necessary_elements(s, psi, rules)
        elems = ", ".join(sorted(s.elements))
        necessary_str = ", ".join(sorted(necessary)) or "—"
        rows.append(
            "<tr>"
            f"<td>S{i}</td>"
            f"<td>{{{_html.escape(elems)}}}</td>"
            f"<td>{_html.escape(s.source_argument_id)}</td>"
            f"<td>{{{_html.escape(necessary_str)}}}</td>"
            "</tr>"
        )
    return (
        '<table class="ness-table">'
        "<thead><tr><th>Set</th><th>Elements</th><th>Argument</th><th>Necessary within set</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _verdict_cell(value: bool) -> str:
    cls = "yes" if value else "no"
    glyph = "✓" if value else "✗"
    return f'<td class="verdict {cls}">{glyph}</td>'


def causal_comparison_section(af: ArgumentationFramework, queries: List[CausalQuery]) -> str:
    """Table comparing plain NESS, `is_cause` (Definition 4.3) and
    `but_for` (Definition 3.5) for each (phi, psi) query, followed by one
    collapsed counterfactual graph per query -- the axiom-expanded
    framework `is_cause`/`but_for` actually reason over -- so a reader can
    see, not just read, why the three notions agree or disagree."""
    if not queries:
        return "<p>No causal queries for this case.</p>"

    rows = []
    details = []
    for q in queries:
        ness = is_ness_cause(af, q.phi, q.psi)
        cause = af.is_cause(q.phi, q.psi)
        but_for = af.but_for(q.phi, q.psi)
        rows.append(
            "<tr>"
            f"<td><code>{_html.escape(q.phi)}</code></td>"
            f"<td><code>{_html.escape(q.psi)}</code></td>"
            f"{_verdict_cell(ness)}{_verdict_cell(cause)}{_verdict_cell(but_for)}"
            f'<td class="note">{_html.escape(q.note)}</td>'
            "</tr>"
        )
        details.append(_counterfactual_detail(af, q))

    table = (
        '<table class="causal-table">'
        "<thead><tr><th>&phi;</th><th>&psi;</th><th>NESS</th>"
        "<th>is_cause (Def. 4.3)</th><th>but_for (Def. 3.5)</th><th>Why</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return table + "\n" + "\n".join(details)


def _counterfactual_detail(af: ArgumentationFramework, q: CausalQuery) -> str:
    not_phi = negate_literal(q.phi)
    expanded = af.axiom_expand([not_phi])
    ext, _ = expanded.compute_grounded_extension()
    dot = to_dot(expanded, ext, title=f"Counterfactual: axiom-expanded with {not_phi}")
    svg = render_to_string(dot, "svg")
    still_justified = q.psi in expanded.justified_conclusions()
    verdict = (
        f"<code>{_html.escape(q.psi)}</code> is "
        f"{'still' if still_justified else 'no longer'} justified after adding "
        f"<code>{_html.escape(not_phi)}</code> as an axiom."
    )
    return (
        f'<details class="counterfactual"><summary>Counterfactual graph for '
        f"&phi;=<code>{_html.escape(q.phi)}</code>, &psi;=<code>{_html.escape(q.psi)}</code></summary>"
        f"<p>{verdict}</p>{svg}</details>"
    )
