"""Didactic (Portuguese, plain-language) rendering of a case for legal
professionals -- the HTML-assembly layer on top of `aspic.explain`'s
sentence templates. Used by the live API (`aspic.api`); the static bundle
(`scripts/generate_graphs.py`) keeps using `aspic.report.render_case`
unchanged, in English, for the paper's figures.
"""
import html

from .causal_report import causal_comparison_section, ness_html_table
from .examples import CaseSpec
from .explain import capitalize_pt, describe_argument, describe_attack, gloss, status_label_pt
from .graph_export import argument_status, render_to_string, to_dot
from .ness import is_ness_cause
from .report import technical_section_html
from .solver import Argument, ArgumentationFramework


def _conclusion_summary_html(case: CaseSpec, af: ArgumentationFramework) -> str:
    effect_text = capitalize_pt(gloss(case.atom_glosses, case.effect))
    lines = [f'<p class="conclusion-main">Conclusão principal: <strong>{html.escape(effect_text)}.</strong></p>']

    causes = [q for q in case.queries if q.expect_cause]
    non_causes = [q for q in case.queries if not q.expect_cause]
    if causes:
        items = "; ".join(gloss(case.atom_glosses, q.phi) for q in causes)
        lines.append(f'<p class="conclusion-causes">Reconhecidos como causa: {html.escape(items)}.</p>')
    if non_causes:
        items = "; ".join(gloss(case.atom_glosses, q.phi) for q in non_causes)
        lines.append(f'<p class="conclusion-non-causes">Não reconhecidos como causa: {html.escape(items)}.</p>')
    return "\n".join(lines)


def _argument_card_html(af: ArgumentationFramework, arg: Argument, status: str,
                         defeat_attack_ids: set, atom_glosses: dict, rule_glosses: dict) -> str:
    description = describe_argument(arg, atom_glosses, rule_glosses)
    status_text = status_label_pt(status)

    # target_id == arg.id (not target_subargument_id) picks the attack
    # recorded against this argument directly -- every attacked argument
    # gets exactly one such entry (from being its own target in
    # `_identify_attacks`'s outer loop), whereas target_subargument_id also
    # matches once more per larger argument built on top of this one,
    # which would otherwise duplicate the same explanation on this card.
    incoming_attacks = [a for a in af.attacks if a.target_id == arg.id]
    outgoing_attacks = [a for a in af.attacks if a.attacker_id == arg.id]

    attack_items = "".join(
        f"<li>{html.escape(describe_attack(af, attack, id(attack) in defeat_attack_ids, atom_glosses, rule_glosses))}</li>"
        for attack in incoming_attacks
    )
    body = ""
    if attack_items:
        body += (
            f'<p class="why-heading">Por que este argumento está '
            f'{status_text.lower()}:</p><ul class="attack-list">{attack_items}</ul>'
        )
    if outgoing_attacks:
        targets = ", ".join(sorted({af.arguments[a.target_id].conclusion for a in outgoing_attacks}))
        body += f'<p class="attacks-out">Este argumento também ataca conclusões que dependem de: <code>{html.escape(targets)}</code>.</p>'

    technical_note = (
        f'<p class="tech-note"><code>{html.escape(arg.id)}: '
        f'{html.escape(", ".join(sorted(arg.premises)) or "∅")} ⊢ {html.escape(arg.conclusion)}</code></p>'
    )
    badge = f'<span class="badge status-{status}">{status_text}</span>'

    if body:
        return (
            f'<details class="arg-card status-{status}">'
            f"<summary>{badge} {html.escape(description)}</summary>"
            f"{body}{technical_note}</details>"
        )
    return (
        f'<div class="arg-card status-{status} no-detail">'
        f"{badge} {html.escape(description)}{technical_note}</div>"
    )


def _verdict_cell_pt(value: bool) -> str:
    cls = "yes" if value else "no"
    glyph = "✓" if value else "✗"
    return f'<td class="verdict {cls}">{glyph}</td>'


def _causal_plain_table_html(case: CaseSpec, af: ArgumentationFramework) -> str:
    if not case.queries:
        return "<p>Nenhuma pergunta causal para este caso.</p>"

    rows = []
    for q in case.queries:
        ness = is_ness_cause(af, q.phi, q.psi)
        cause = af.is_cause(q.phi, q.psi)
        but_for = af.but_for(q.phi, q.psi)
        phi_text = capitalize_pt(gloss(case.atom_glosses, q.phi))
        rows.append(
            "<tr>"
            f"<td>{html.escape(phi_text)}</td>"
            f"{_verdict_cell_pt(ness)}{_verdict_cell_pt(cause)}{_verdict_cell_pt(but_for)}"
            f'<td class="note">{html.escape(q.note_pt or q.note)}</td>'
            "</tr>"
        )

    return (
        '<table class="causal-table">'
        "<thead><tr><th>Fato analisado</th>"
        "<th>Foi indispensável, junto com outros? <span class=\"tech-ref\">(teste NESS)</span></th>"
        "<th>É reconhecido como causa? <span class=\"tech-ref\">(Def. 4.3)</span></th>"
        "<th>O resultado não ocorreria de jeito nenhum sem ele? <span class=\"tech-ref\">(\"não fosse por\" / Def. 3.5)</span></th>"
        "<th>Por quê</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_case_didactic(case: CaseSpec) -> str:
    """The full didactic `<section>` for one case: plain-language summary,
    argument cards (each expandable into why it's accepted/rejected), the
    causal comparison reframed as plain questions, and a collapsed toggle
    holding the unchanged technical (English, ASPIC+-notation) view."""
    af = ArgumentationFramework(case.knowledge_base, case.causal_model)
    extension, _ = af.compute_grounded_extension()
    status = argument_status(af, extension)
    defeat_attack_ids = {id(d.attack) for d in af.defeats}

    summary_html = _conclusion_summary_html(case, af)
    cards_html = "\n".join(
        _argument_card_html(af, arg, status[arg.id], defeat_attack_ids, case.atom_glosses, case.rule_glosses)
        for arg in af.arguments.values()
    )
    causal_html = _causal_plain_table_html(case, af)

    dot = to_dot(af, extension, title=case.title)
    graph_svg = render_to_string(dot, fmt="svg")
    ness_table = ness_html_table(af, case.effect)
    causal_section_en = causal_comparison_section(af, case.queries)
    technical = technical_section_html(case, graph_svg, ness_table, causal_section_en)

    return f"""
<section class="case" id="{case.id}">
  <h2>{html.escape(case.title)}</h2>
  <p class="narrative">{html.escape(case.narrative_pt or case.narrative)}</p>

  <h3>O que a análise concluiu</h3>
  {summary_html}

  <h4>Argumentos construídos</h4>
  <div class="argument-cards">
    {cards_html}
  </div>

  <h3>Comparação causal</h3>
  {causal_html}

  <details class="technical-toggle">
    <summary>Ver representação técnica (notação ASPIC+, em inglês)</summary>
    {technical}
  </details>
</section>
"""
