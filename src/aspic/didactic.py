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
from .lrc import relevance_report
from .report import technical_section_html
from .solver import Argument, ArgumentationFramework


def _conclusion_summary_html(case: CaseSpec, af: ArgumentationFramework) -> str:
    effect_text = capitalize_pt(gloss(case.atom_glosses, case.effect))
    lines = [f'<p class="conclusion-main">Conclusão principal: <strong>{html.escape(effect_text)}.</strong></p>']

    causes = [q for q in case.queries if q.expect_ness]
    non_causes = [q for q in case.queries if not q.expect_ness]
    if causes:
        items = "; ".join(gloss(case.atom_glosses, q.phi) for q in causes)
        lines.append(f'<p class="conclusion-causes">Reconhecidos como causa: {html.escape(items)}.</p>')
    if non_causes:
        items = "; ".join(gloss(case.atom_glosses, q.phi) for q in non_causes)
        lines.append(f'<p class="conclusion-non-causes">Não reconhecidos como causa: {html.escape(items)}.</p>')
    return "\n".join(lines)


#: Best-first, for picking the status of a conclusion reached by more than
#: one line of reasoning: if any path survives, the conclusion stands.
_STATUS_RANK = {"IN": 0, "UNDEC": 1, "OUT": 2}


def _argument_card_html(af: ArgumentationFramework, args: list, description: str,
                         status_map: dict, defeat_attack_ids: set,
                         atom_glosses: dict, rule_glosses: dict) -> str:
    """One card for one *conclusion-with-a-rationale*, not one card per
    argument object.

    The solver builds a separate `Argument` for every distinct derivation, so
    a conclusion reachable three ways yields three arguments that read
    identically -- and, worse, can carry different badges, since one path may
    survive while the others are defeated. Merging them into a single card
    keyed on the plain-language description is what a jurist actually needs:
    the conclusion holds if *some* line of reasoning holds, and the card says
    how many lines there were and how each fared.
    """
    statuses = [status_map[arg.id] for arg in args]
    status = min(statuses, key=lambda value: _STATUS_RANK.get(value, 3))
    status_text = status_label_pt(status)

    # target_id == arg.id (not target_subargument_id) picks the attack
    # recorded against this argument directly -- every attacked argument
    # gets exactly one such entry (from being its own target in
    # `_identify_attacks`'s outer loop), whereas target_subargument_id also
    # matches once more per larger argument built on top of this one,
    # which would otherwise duplicate the same explanation on this card.
    arg_ids = {arg.id for arg in args}
    incoming = [a for a in af.attacks if a.target_id in arg_ids and a.target_id == a.target_subargument_id]
    outgoing = [a for a in af.attacks if a.attacker_id in arg_ids]

    explanations = []
    for attack in incoming:
        text = describe_attack(af, attack, id(attack) in defeat_attack_ids,
                               atom_glosses, rule_glosses)
        if text not in explanations:
            explanations.append(text)

    body = ""
    if len(args) > 1:
        tally = []
        for label, key in (("aceito", "IN"), ("indeterminado", "UNDEC"), ("afastado", "OUT")):
            count = statuses.count(key)
            if count:
                tally.append(f"{count} {label}{'s' if count > 1 else ''}")
        body += (f'<p class="paths">{len(args)} caminhos de raciocínio levam a esta '
                 f'mesma conclusão: {html.escape(", ".join(tally))}.</p>')
    if explanations:
        items = "".join(f"<li>{html.escape(text)}</li>" for text in explanations)
        body += (
            f'<p class="why-heading">Por que este argumento está '
            f'{status_text.lower()}:</p><ul class="attack-list">{items}</ul>'
        )
    if outgoing:
        targets = ", ".join(sorted({af.arguments[a.target_id].conclusion for a in outgoing}))
        body += f'<p class="attacks-out">Este argumento também ataca conclusões que dependem de: <code>{html.escape(targets)}</code>.</p>'

    technical_note = '<p class="tech-note">' + "".join(
        f'<code>{html.escape(arg.id)}: '
        f'{html.escape(", ".join(sorted(arg.premises)) or "∅")} ⊢ {html.escape(arg.conclusion)}</code> '
        for arg in args
    ) + "</p>"
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


def _argument_cards_html(af: ArgumentationFramework, status_map: dict,
                          defeat_attack_ids: set, atom_glosses: dict,
                          rule_glosses: dict) -> str:
    """Every argument of a framework as cards, one per distinct reading."""
    groups: dict = {}
    for arg in af.arguments.values():
        description = describe_argument(arg, atom_glosses, rule_glosses)
        groups.setdefault(description, []).append(arg)
    return "\n".join(
        _argument_card_html(af, args, description, status_map, defeat_attack_ids,
                            atom_glosses, rule_glosses)
        for description, args in groups.items()
    )


ATTACK_KIND_PT = {
    "undercut": "ataque ao raciocínio",
    "rebut": "contradição direta",
    "undermine": "contestação do fato",
}


def _glossary_html(case: CaseSpec) -> str:
    """The case's vocabulary in plain Portuguese.

    The formal literals are the one piece of notation a lawyer cannot avoid
    seeing (they label the graph nodes and the technical view), so the
    didactic view states, once and up front, what each one means. Negated
    forms are left out: `atom_glosses` carries a mechanical "não é o caso de
    que ..." entry for every atom, which would double the table without
    adding anything.
    """
    entries = [(code, text) for code, text in case.atom_glosses.items()
               if not code.startswith("¬")]
    if not entries:
        return ""
    premises = set(case.knowledge_base.get("premises", []))
    axioms = set(case.knowledge_base.get("axioms", []))
    rows = []
    for code, text in entries:
        if code in axioms:
            role, tone = "fato assentado", "axiom"
        elif code in premises:
            role, tone = "fato alegado", "premise"
        elif code == case.effect:
            role, tone = "resultado a explicar", "effect"
        else:
            role, tone = "conclusão derivada", "derived"
        rows.append(
            "<tr>"
            f'<td class="mono">{html.escape(code)}</td>'
            f"<td>{html.escape(capitalize_pt(text))}</td>"
            f'<td><span class="role-tag {tone}">{html.escape(role)}</span></td>'
            "</tr>"
        )
    return (
        '<table class="glossary"><thead><tr><th>Símbolo</th><th>Significa</th>'
        "<th>Papel no caso</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _attacker_text(attacker, atom_glosses: dict) -> str:
    """Who is doing the contesting, in facts rather than in symbols.

    An undercutting argument concludes `¬rN` -- a symbol with no gloss and no
    meaning to a lawyer. What carries the meaning is what that argument rests
    on, so a derived attacker is named by its immediate sub-arguments'
    conclusions ("o atendimento seguiu os protocolos") instead of by its own.
    """
    if attacker.is_atomic or not attacker.sub_arguments:
        return capitalize_pt(gloss(atom_glosses, attacker.conclusion))
    return capitalize_pt(" e ".join(
        gloss(atom_glosses, sub.conclusion) for sub in attacker.sub_arguments
    ))


def _disputes_html(af: ArgumentationFramework, atom_glosses: dict,
                    rule_glosses: dict) -> str:
    """Every contestation in the framework, as a row a jurist can read.

    Only *direct* attacks are listed: `af.attacks` records one entry per
    (attacker, target, attacked sub-argument), so an attack on a step also
    appears once for every larger argument built on top of it. Keeping the
    rows where the attacked sub-argument *is* the target argument lists each
    contestation exactly once -- the same filter the argument cards use.
    """
    defeat_ids = {id(d.attack) for d in af.defeats}
    rows = []
    seen = set()
    for attack in af.attacks:
        if attack.target_id != attack.target_subargument_id:
            continue
        attacker = af.arguments[attack.attacker_id]
        target = af.arguments[attack.target_id]
        is_defeat = id(attack) in defeat_ids

        if attack.attack_type == "undercut":
            # The gloss of the undercut rule *is* the reasoning under attack.
            challenged = rule_glosses.get(attack.rule_id) or (
                f"O raciocínio que leva a: {gloss(atom_glosses, target.conclusion)}")
        elif attack.attack_type == "rebut":
            challenged = f"A conclusão de que {gloss(atom_glosses, target.conclusion)}"
        else:
            challenged = f"O fato de que {gloss(atom_glosses, attack.attacked_literal)}"

        who = _attacker_text(attacker, atom_glosses)
        why = rule_glosses.get(attacker.top_rule.id, "") if attacker.top_rule else ""

        key = (challenged, who, attack.attack_type)
        if key in seen:
            continue
        seen.add(key)

        verdict, consequence = (
            ("Prevalece", "o argumento atacado é afastado") if is_defeat
            else ("Não prevalece", "o argumento atacado permanece de pé"))
        rows.append(
            "<tr>"
            f"<td>{html.escape(capitalize_pt(challenged))}</td>"
            f"<td>{html.escape(who)}"
            + (f'<span class="dispute-why">{html.escape(why)}</span>' if why else "")
            + "</td>"
            f"<td>{html.escape(ATTACK_KIND_PT.get(attack.attack_type, attack.attack_type))}</td>"
            f'<td class="dispute-outcome {"kept" if is_defeat else "failed"}">'
            f"<strong>{html.escape(verdict)}</strong>"
            f'<span class="dispute-note">{html.escape(consequence)}</span></td>'
            "</tr>"
        )
    if not rows:
        return ("<p>Nenhum argumento deste caso é contestado por outro: não há "
                "disputa a resolver.</p>")
    return (
        '<table class="disputes"><thead><tr><th>O que é contestado</th>'
        "<th>Quem contesta, e por quê</th><th>Tipo de ataque</th>"
        "<th>Resultado</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
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
        ness = af.ness_cause(q.phi, q.psi)
        but_for = af.but_for(q.phi, q.psi)
        phi_text = capitalize_pt(gloss(case.atom_glosses, q.phi))
        rows.append(
            "<tr>"
            f"<td>{html.escape(phi_text)}</td>"
            f"{_verdict_cell_pt(ness)}{_verdict_cell_pt(but_for)}"
            f'<td class="note">{html.escape(q.note_pt or q.note)}</td>'
            "</tr>"
        )

    return (
        '<table class="causal-table">'
        "<thead><tr><th>Fato analisado</th>"
        "<th>É causa do resultado? <span class=\"tech-ref\">(teste NESS — Def. 4.3 / 3.4)</span></th>"
        "<th>O resultado não ocorreria de jeito nenhum sem ele? <span class=\"tech-ref\">(\"não fosse por\" / Def. 3.5)</span></th>"
        "<th>Por quê</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )



def _lrc_section_html(case: CaseSpec) -> str:
    """The legal-relevance layer (ICAIL 2026) as its own didactic block.

    Cause in fact only gets a claimant halfway: the paper's second module asks
    whether a cause the counterfactual test accepted is one the law should
    care about, and lets doctrinal defences (no-worse-off, superseding cause,
    unforeseeability, omission without a duty to act) undercut that. Rendered
    only for cases that carry the layer -- the five ICAIL 2025 cases do not.
    """
    layer = case.lrc
    af = ArgumentationFramework(layer.knowledge_base, layer.causal_model,
                                preferences=case.preferences)
    extension, _ = af.compute_grounded_extension()
    status = argument_status(af, extension)
    defeat_attack_ids = {id(d.attack) for d in af.defeats}

    rows = []
    for entry in relevance_report(af, layer.targets):
        target_text = capitalize_pt(gloss(layer.atom_glosses, entry["target"]))
        if entry["justified"]:
            verdict = '<td class="verdict yes">✓</td>'
            reason = "Nenhuma defesa afastou a relevância jurídica."
        else:
            verdict = '<td class="verdict no">✗</td>'
            reasons = [b["scheme_pt"] for b in entry["blocked_by"] if b["scheme_pt"]]
            reason = " ".join(reasons) or (
                "A relevância jurídica não se sustenta neste framework."
            )
        rows.append(
            f"<tr><td>{html.escape(target_text)}</td>{verdict}"
            f'<td class="note">{html.escape(reason)}</td></tr>'
        )

    table = (
        '<table class="causal-table">'
        "<thead><tr><th>Afirmação de relevância jurídica</th>"
        "<th>Aceita? <span class=\"tech-ref\">(LeReCa)</span></th>"
        "<th>Por quê</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        if rows else "<p>Nenhuma afirmação de relevância jurídica a avaliar.</p>"
    )

    duty = ""
    if layer.duty_basis_pt:
        duty = (
            f'<p class="duty-basis"><strong>Dever jurídico de agir:</strong> '
            f"{html.escape(layer.duty_basis_pt)}</p>"
        )

    cards = _argument_cards_html(af, status, defeat_attack_ids,
                                 layer.atom_glosses, layer.rule_glosses)
    dot = to_dot(af, extension, title=f"{case.title} — relevância jurídica")

    return f"""
  <h3>Relevância jurídica <span class="tech-ref">(camada ICAIL 2026)</span></h3>
  <p class="lrc-intro">Ser causa de fato é condição necessária, mas não
  suficiente, da responsabilidade. Esta segunda camada parte das causas de fato
  que o solver reconheceu acima e verifica se alguma defesa doutrinária afasta
  a relevância jurídica de cada uma.</p>
  {duty}
  {table}

  <details class="technical-toggle lrc-toggle">
    <summary>Ver os argumentos e o grafo da camada de relevância jurídica</summary>
    <div class="argument-cards">
      {cards}
    </div>
    <div class="graph-wrap">{render_to_string(dot, fmt="svg")}</div>
  </details>
"""

def render_case_didactic(case: CaseSpec) -> str:
    """The full didactic `<section>` for one case: plain-language summary,
    argument cards (each expandable into why it's accepted/rejected), the
    causal comparison reframed as plain questions, and a collapsed toggle
    holding the unchanged technical (English, ASPIC+-notation) view."""
    af = ArgumentationFramework(case.knowledge_base, case.causal_model,
                                preferences=case.preferences)
    extension, _ = af.compute_grounded_extension()
    status = argument_status(af, extension)
    defeat_attack_ids = {id(d.attack) for d in af.defeats}

    summary_html = _conclusion_summary_html(case, af)
    cards_html = _argument_cards_html(af, status, defeat_attack_ids,
                                      case.atom_glosses, case.rule_glosses)
    causal_html = _causal_plain_table_html(case, af)
    disputes_html = _disputes_html(af, case.atom_glosses, case.rule_glosses)
    glossary_html = _glossary_html(case)
    lrc_html = _lrc_section_html(case) if case.lrc is not None else ""

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

  <h4>Disputas entre os argumentos</h4>
  <p class="lead">Quem contesta o quê, e se a contestação prevaleceu. É esta
  tabela, e não a ordem dos argumentos, que decide o resultado.</p>
  {disputes_html}

  <h4>Vocabulário do caso</h4>
  <p class="lead">O que cada símbolo do grafo e da tabela técnica significa.</p>
  {glossary_html}

  <h3>Comparação causal</h3>
  {causal_html}
  {lrc_html}

  <details class="technical-toggle">
    <summary>Ver representação técnica (notação ASPIC+, em inglês)</summary>
    {technical}
  </details>
</section>
"""
