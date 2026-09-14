"""Renders the Perspectivas tab: the adjudication map, the argumentation
phase and the decision phase. Pure rendering of `analysis.perspectives` --
the same structures the standalone adjudication figures are generated from.
"""

"""The adjudication view: who moved what, and where the case turned.

Renders `analysis.perspectives` as the tab a jurist reads. Three pieces, in the
order the dispute happens:

* the **map** -- every rule of both layers drawn inside its author's box, with
  the attacks crossing the lanes. It is the picture the single argument graph
  cannot draw, because there every rule belongs to one anonymous theory;
* the **argumentation phase** -- the adversaries' theories, then each vote
  admitted in turn, with what its rules changed in the causal verdicts;
* the **decision phase** -- the legal-relevance layer admitted one adjudicator
  at a time, with the move that first blocks a claim marked as the turning
  point.

Following Prakken, "A Formal Model of Adjudication Dialogues" (AI & Law 2008),
§4.3: in the decision phase the adjudicator decides by *moving arguments* --
undercutters and priority arguments -- and silence is a decision too.
"""
import html

from typing import List, Optional

from analysis import perspectives as P
from interface.graph_export import render_to_string


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _known_perspectives(record) -> list:
    """Everyone the *dossiers* reconstruct, not only whoever the formalization
    attributed a rule to. A vote an annotator wrote up and the formalization
    ignored has to show as an empty box, otherwise the map reports a judgment
    with fewer participants than it had.

    Across every annotator, not just the one the formalization came from: a
    perspective only the second annotator reconstructed is still a
    perspective of the case, and drawing the map from one export alone would
    lose it.
    """
    from cases import catalog

    found: list = []
    for dossier in catalog.dossiers_by_id(record.case.id):
        for key in dossier.perspective_types():
            if key not in found:
                found.append(key)
    return found


def _map_html(record, title: str) -> str:
    try:
        svg = render_to_string(
            P.to_adjudication_dot(record, title=title,
                                  known=_known_perspectives(record)), fmt="svg")
    except RuntimeError as exc:  # Graphviz missing: the tables still stand
        return f'<p class="notice">{_esc(exc)}</p>'
    return f"""
  <div class="graph-wrap">{svg}</div>
  <p class="legend-note">O mapa desenha só a <strong>estrutura principal de
  ataque</strong>: um nó por lance que ataca ou é atacado, dentro da caixa de
  quem o move — nenhum argumento individual. Os argumentos que o solver
  constrói são mais numerosos do que a figura comporta, e listá-los pela
  metade apresentaria como inteiro o que não é; os ataques, ao contrário,
  estão <strong>todos</strong> aqui, numerados, e a tabela-legenda ao pé do
  mapa dá, para cada um, quem o move, em que fase e o seu desfecho lido da
  extensão fundada. Sustentação sem ataque não vira nó: dobra-se no lance que
  alimenta, anotada no tooltip; a camada de causa de fato, que não contém
  ataque nenhum, colapsa num nó único, ligado à outra camada pela seta
  <em>ponte</em>. Caixa marcada <em>sem movimento</em>: essa perspectiva
  existe no dossiê e não move lance nenhum — no modelo de Prakken isso é uma
  decisão, não uma lacuna (quem não ataca, endossa).</p>
  <p class="legend-note">O estilo de cada seta vermelha é o seu desfecho:
  <strong>cheia</strong>, o ataque subsiste — a mais grossa é o lance
  decisivo; <strong>tracejada</strong>, o autor do ataque foi ele próprio
  afastado; <strong>pontilhada cinza</strong>, o ataque é inerte (nunca gerou
  argumento). Linha vermelha sem ponta: os dois lances se contradizem e o
  ataque corre nos dois sentidos (aba <em>Pesos</em>). Seta cinza tracejada:
  a conclusão de um lance <strong>alimenta</strong> o antecedente de outro.
  Elipse vermelha: lance afastado. Marca <em>(N vozes)</em>: sustentado por N
  perspectivas por conta própria, desenhado na caixa da primeira — e a seta
  vermelha que aponta para a <strong>borda</strong> de uma caixa diz que o
  lance atacado também é daquela perspectiva (ponta vazada: as duas pontas
  são adjudicadores). Para o embate sem os lances no meio, veja o grafo
  <em>Quem enfrenta quem</em>, mais abaixo.</p>
"""


def _holders_text(keys, origin: str = "") -> str:
    """Who sustains something, as the tables say it.

    `comum` is not a perspective, it is the absence of dispute; and a bridge
    premise is the solver's output, held by nobody. Printing either as a list
    of names would claim an agreement that was never asserted.
    """
    if origin == "ponte":
        return "ponte (saída do solver)"
    keys = list(keys)
    if not keys:
        return "—"
    if keys == [P.SHARED]:
        return "incontroverso (todas)"
    return ", ".join(P._label(key) for key in keys)


def _confrontation_graph_html(record) -> str:
    """Perspective confrontations as a graph, without intermediate rules."""
    try:
        svg = render_to_string(
            P.to_confrontation_dot(record, title="Quem enfrenta quem"), fmt="svg")
    except RuntimeError as exc:
        return f'<p class="notice">{_esc(exc)}</p>'
    return f"""
  <div class="graph-wrap">{svg}</div>
  <p class="legend-note">Um nó por perspectiva, uma aresta por confronto, lida
  pelos <strong>titulares</strong> das regras e não pelas caixas do mapa acima.
  Aresta vermelha cheia: confronto <strong>entre adjudicadores</strong> — é
  nele que a fase de decisão acontece, e é o que o mapa de regras não consegue
  desenhar, porque lá a regra atacada mora numa caixa só. Aresta cinza
  tracejada: confronto em que ao menos uma ponta é parte.</p>
"""


def _confrontations_html(record) -> str:
    """Who attacks whom, read through rule holders.

    The question the map does not answer. A node occupies one box, belonging
    to its first holder in reading order, where parties precede adjudicators.
    A rule shared by the reporting judge and respondent is therefore drawn
    in the respondent's box; a dissenting vote's attack against it *appears*
    to attack the party. In `case-003-final`, six of seven attacks are between
    adjudicators, yet none appears that way in the drawing.
    """
    rows_data = P.confrontations(record)
    if not rows_data:
        return ('<p class="notice">Nenhum ataque entre perspectivas: as regras '
                "deste caso não se atacam, ou nenhuma tem autor identificado.</p>")
    entre = [r for r in rows_data if r["between_adjudicators"]]
    rows = "".join(
        f'<tr class="{"turning-row" if row["between_adjudicators"] else ""}">'
        f'<td><strong>{_esc(P._label(row["source"]))}</strong></td>'
        f'<td>{_esc(P._label(row["target"]))}</td>'
        f'<td>{_esc(row["phase"])}</td>'
        f'<td class="mono">{_esc(", ".join(row["rules"]))}</td>'
        + ('<td><span class="turning">adjudicador × adjudicador</span></td>'
           if row["between_adjudicators"] else "<td></td>")
        + "</tr>"
        for row in rows_data
    )
    nota = (f'<p class="lead"><strong>{len(entre)}</strong> destes confrontos são '
            "entre adjudicadores — é neles que a fase de decisão acontece. No "
            "mapa acima eles estão desenhados com traço mais grosso, mas com uma "
            "parte numa das pontas: a regra atacada é sustentada também por ela, "
            "e o nó teve de ser posto em alguma caixa. É esta tabela, e não o "
            "desenho, que diz quem estava de cada lado.</p>"
            if entre else
            '<p class="lead">Nenhum confronto entre adjudicadores: a fase de '
            "decisão deste caso não tem juiz contra juiz.</p>")
    return (
        '<p class="lead">Cada par de perspectivas que se enfrenta, lido pelas '
        "regras que cada uma sustenta — não pelas caixas do mapa. Uma regra que "
        "três vozes sustentam produz três confrontos, e eles não são todos da "
        "mesma natureza: <code>dvesp_q0 ⤅ dvgen_q2</code> é o recorrido "
        "respondendo ao dissenso na fase de argumentação <em>e</em> o relator "
        "respondendo na fase de decisão, conforme o titular de que se lê.</p>"
        + nota +
        "<table><thead><tr><th>Ataca</th><th>Quem</th><th>Fase</th>"
        f"<th>Por quais regras</th><th></th></tr></thead><tbody>{rows}</tbody></table>"
    )


def _rules_legend_html(record) -> str:
    """Every rule of both layers, written out.

    The map draws a rule as an ellipse with a shortened label -- antecedents
    capped at three, consequent dropped when it is an undercut, because a
    node that carries the whole rule is a node nobody reads. The cost is that
    the diagram alone never tells you what `dvgen_q1` actually says. This is
    where it says it.
    """
    rules = P.mapped_rules(record)
    if not rules:
        return '<p class="notice">Este caso não tem regras registradas.</p>'
    by_rule = P.arguments_by_rule(record)
    model = _preference_model(record)

    rows = []
    for layer in ("cif", "lrc"):
        do_layer = [rule for rule in rules if rule.layer == layer]
        if not do_layer:
            continue
        rows.append(
            f'<tr class="case-row"><td colspan="7"><strong>Camada de '
            f'{_esc(P.LAYER_LABELS.get(layer, layer))}</strong></td></tr>')
        for rule in do_layer:
            arguments = by_rule.get(rule.id, [])
            quem = _holders_text(rule.holders)
            forca = model.rule_strength(rule.id) if model is not None else None
            estado = ('<span class="badge status-OUT">não sobreviveu</span>'
                      if rule.defeated else
                      ('<span class="badge status-IN">de pé</span>' if arguments
                       else '<span class="badge status-UNDEC">não disparou</span>'))
            rows.append(
                "<tr>"
                f'<td class="mono">{_esc(rule.id)}</td>'
                f'<td class="mono">{_esc(rule.body.split(":", 1)[-1].strip())}</td>'
                f"<td>{_esc(rule.gloss)}</td>"
                f"<td>{_esc(quem)}</td>"
                f'<td class="mono">{_esc(", ".join(a.label for a in arguments)) or "—"}</td>'
                f'<td class="num">{"—" if forca is None else f"{forca:g}"}</td>'
                f"<td>{estado}</td></tr>"
            )
    return (
        '<p class="lead">O que cada elipse do mapa diz por extenso. '
        "<em>Argumentos</em> lista o que o solver de fato construiu com a "
        "regra — vazio quer dizer que os antecedentes nunca foram satisfeitos, "
        "que é diferente de a regra ter sido afastada. <em>Força</em> só "
        "aparece quando o caso declara pesos (aba <em>Pesos</em>).</p>"
        "<table><thead><tr><th>Regra</th><th>Corpo</th><th>Leitura</th>"
        "<th>Quem sustenta</th><th>Argumentos</th><th>Força</th>"
        f"<th>Situação</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _preference_model(record):
    from formalize import build

    return build.preference_model(record)


def _arguments_html(record) -> str:
    """Every argument of both layers, named and traced.

    The ids are the solver's own, and on purpose: `A7` here is `A7` in the
    argument graph of the Analysis tab, in `blocked_by.attacker` of the
    relevance report, and in the conflict table of the Weights tab. The two
    layers number independently, so the layer is part of the name.
    """
    arguments = P.mapped_arguments(record)
    if not arguments:
        return '<p class="notice">Nenhum argumento foi construído.</p>'
    model = _preference_model(record)

    rows = []
    for layer in ("cif", "lrc"):
        do_layer = [a for a in arguments if a.layer == layer]
        if not do_layer:
            continue
        rows.append(
            f'<tr class="case-row"><td colspan="7"><strong>Camada de '
            f'{_esc(P.LAYER_LABELS.get(layer, layer))}</strong></td></tr>')
        for argument in do_layer:
            quem = _holders_text(argument.holders, argument.origin)
            rows.append(
                "<tr>"
                f'<td class="mono">{_esc(argument.label)}</td>'
                f'<td><span class="badge status-{argument.status}">{argument.status}</span></td>'
                f'<td class="mono">{_esc(P.short_literal(argument.conclusion))}</td>'
                f'<td class="mono">{_esc(", ".join(argument.rules)) or "premissa"}</td>'
                f'<td class="mono">{_esc(", ".join(argument.premises)) or "—"}</td>'
                f"<td>{_esc(quem)}</td>"
                f'<td class="num">'
                f'{"—" if argument.strength is None else f"{argument.strength:g}"}</td>'
                "</tr>"
            )
    nota = ""
    if model is None:
        nota = ('<p class="lead">A coluna de força fica vazia porque este caso '
                "roda sob a ordenação básica, sem pesos declarados.</p>")
    return (
        '<p class="lead">Cada argumento que o solver construiu, com o nome que '
        "ele carrega em todo o resto do explorador. O prefixo diz a camada — "
        "<code>F·</code> para causa de fato, <code>R·</code> para relevância "
        "jurídica — porque as duas numeram por conta própria e um "
        "<code>A17</code> solto nomearia dois argumentos diferentes. O que vem "
        "depois do ponto é o id do próprio solver: <code>F·A7</code> é o "
        "<code>A7</code> do grafo da aba Análise, do relatório de relevância e "
        "da tabela de conflitos da aba Pesos. <strong>IN</strong> "
        "é aceito, <strong>OUT</strong> é derrotado por um argumento aceito, "
        "<strong>UNDEC</strong> é indecidido. <em>Quem sustenta</em> são as "
        "perspectivas que dispõem de todas as regras que ele usa — um "
        "argumento não é movido por ninguém, é o que uma teoria consegue "
        "construir.</p>" + nota +
        "<table><thead><tr><th>Argumento</th><th>Situação</th>"
        "<th>Conclusão</th><th>Regras</th><th>Premissas</th>"
        "<th>Quem sustenta</th><th>Força</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _theories_html(record) -> str:
    cards = []
    for theory in P.by_perspective(record):
        premises = ", ".join(theory.premises) or "nenhuma"
        rules = ", ".join(theory.rule_ids) or "nenhuma regra própria"
        af = theory.framework()
        af.compute_grounded_extension()
        derives = record.effect in af.justified_conclusions()
        badge = ('<span class="badge status-IN">deriva o resultado</span>' if derives
                 else '<span class="badge status-OUT">não deriva o resultado</span>')
        cards.append(
            f'<article class="dossier-card"><h5>{_esc(theory.label)} {badge}</h5>'
            f'<div class="dossier-field"><div class="field-label">Regras</div>'
            f'<div class="field-value"><p class="mono">{_esc(rules)}</p></div></div>'
            f'<div class="dossier-field"><div class="field-label">Premissas</div>'
            f'<div class="field-value"><p class="mono">{_esc(premises)}</p></div></div>'
            "</article>"
        )
    return f'<div class="dossier-cards">{"".join(cards)}</div>'


#: How a verdict reads on screen. `None` is not "no": it is the answer to a
#: question that could not be put, because the theory admitted so far does not
#: derive the effect at all.
_VERDICT_WORD = {True: "sim", False: "não", None: "não avaliável"}


def _verdict_delta(previous: Optional[dict], current: dict, record) -> str:
    """What admitting this perspective changed in the causal verdicts.

    The interesting case is not a conclusion appearing or vanishing -- it is a
    cause staying a cause while ceasing to be a but-for cause, which is what a
    concurring vote with its own grounds does when it opens a second route to
    the same link.

    Three states, not two. Before the effect is derivable at all, a verdict is
    `None`, and rendering that as "no" produces the nonsense this column used
    to print: `no → yes` for a step where the previous theory had not reached
    the damage and so had said nothing about what caused it. The word for
    `None` is "not evaluable", and the arrow says which of the three moved.
    """
    if previous is None:
        return '<span class="muted">—</span>'
    changes = []
    for key, now in current.items():
        before = previous.get(key, {})
        for notion, label in (("ness", "causa (NESS)"),
                              ("but_for", "não fosse por")):
            was, is_now = before.get(notion), now.get(notion)
            if was == is_now:
                continue
            arrow = f"{_VERDICT_WORD[was]} → {_VERDICT_WORD[is_now]}"
            changes.append(f"<li><code>{_esc(key)}</code> {label}: {arrow}</li>")
    return f"<ul class='delta'>{''.join(changes)}</ul>" if changes else (
        '<span class="muted">nada mudou</span>')


def _argumentation_html(record) -> str:
    trace = P.adjudication_trace(record)
    if not trace:
        return ""
    rows, previous = [], None
    for step in trace:
        new_rules = ", ".join(step["new_rules"]) or "—"
        rows.append(
            "<tr>"
            f'<td class="num">{step["step"]}</td>'
            f'<td><strong>{_esc(step["added_label"])}</strong></td>'
            f'<td class="mono">{_esc(new_rules)}</td>'
            f'<td class="verdict {"yes" if step["outcome_justified"] else "no"}">'
            f'{"✓" if step["outcome_justified"] else "✗"}</td>'
            f'<td>{_verdict_delta(previous, step["verdicts"], record)}</td>'
            "</tr>"
        )
        previous = step["verdicts"]
    return (
        "<h4>Fase de argumentação</h4>"
        '<p class="lead">As partes constroem o grafo; cada julgador entra em '
        "seguida, na ordem do processo. A coluna do resultado diz se o dano "
        "continua sendo derivado — nesta camada discute-se o que aconteceu, "
        "não a quem se imputa.</p>"
        "<table><thead><tr><th>#</th><th>Quem entra</th><th>Regras novas</th>"
        "<th>Resultado derivado</th><th>O que mudou nos vereditos causais</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _decision_html(record) -> str:
    trace = P.decision_trace(record)
    if not trace:
        return ('<h4>Fase de decisão</h4><p class="notice">Nenhuma defesa '
                "doutrinária tem autor identificado neste registro, então não "
                "há movimentos a ordenar. Reformalize o caso para atribuir "
                "cada defesa à perspectiva que a acolheu.</p>")
    targets = list(trace[0]["relevance"])
    head = "".join(f"<th>{_esc(P.short_literal(t))}</th>" for t in targets)
    rows = []
    for step in trace:
        blocked = bool(step["newly_blocked"])
        released = bool(step.get("newly_relevant"))
        cells = "".join(
            f'<td class="verdict {"yes" if step["relevance"][t] else "no"}">'
            f'{"✓" if step["relevance"][t] else "✗"}</td>'
            for t in targets
        )
        mark = ""
        if blocked:
            mark = '<span class="turning">a pretensão cai aqui</span>'
        elif released:
            mark = '<span class="turning">a pretensão passa a se sustentar aqui</span>'
        # How many cause-in-fact facts this step's theories establish. A claim
        # can fail here for two different reasons -- the law knocked it down,
        # or the facts never got it off the ground -- and without this column
        # a ✗ looks the same either way.
        facts = len([literal for literal in step.get("bridged", [])
                     if literal.startswith("CaFa_")])
        rows.append(
            f'<tr class="{"turning-row" if blocked or released else ""}">'
            f'<td class="num">{step["step"]}</td>'
            f'<td><strong>{_esc(step["added_label"])}</strong> {mark}</td>'
            f'<td class="num">{facts}</td>'
            f"{cells}</tr>"
        )
    return (
        "<h4>Fase de decisão</h4>"
        '<p class="lead">Só o adjudicador se move aqui, e move argumentos: a '
        "presunção geral entra primeiro, e cada julgador acrescenta as defesas "
        "que acolheu. A coluna <em>causas de fato</em> conta os "
        "<code>CaFa_*</code> que as teorias admitidas até ali estabelecem — "
        "porque a camada de relevância só pode presumir relevante o que a "
        "camada dos fatos já reconheceu como causa, e uma pretensão pode cair "
        "por qualquer dos dois motivos. ✓ é relevância jurídica reconhecida; "
        "✗ é afastada. As linhas destacadas são os movimentos em que a "
        "pretensão muda de sorte.</p>"
        f"<table><thead><tr><th>#</th><th>Quem decide</th>"
        f"<th>Causas de fato</th>{head}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _unattributed_html(record) -> str:
    orphans = P.unattributed_lrc_rules(record)
    if not orphans:
        return ('<p class="ok-note">Toda defesa doutrinária deste caso tem autor '
                "identificado, então cada uma aparece no traço como um "
                "movimento datado.</p>")
    items = "".join(f"<li><code>{_esc(rule)}</code></li>" for rule in orphans)
    return (
        f'<p class="notice">{len(orphans)} defesa(s) sem autor identificado. '
        "Elas entram em todos os passos, então nunca aparecem como movimento — "
        "e o traço fica mais liso do que o julgamento foi.</p>"
        f'<ul class="id-list">{items}</ul>'
    )


def render_perspectives(record, title: str = "") -> str:
    """The adjudication `<section>` for one formalized case."""
    return f"""
<section class="perspectives">
  <h3>Perspectivas e adjudicação</h3>
  <p class="lead">O mesmo caso lido como uma disputa entre teorias, e não como
  um resultado pronto. Cada parte e cada voto sustenta as suas próprias regras;
  o julgamento é o que acontece quando elas se encontram. A divisão em duas
  fases — as partes argumentam, o adjudicador decide movendo argumentos — segue
  Prakken, <em>A Formal Model of Adjudication Dialogues</em> (2008).</p>

  {_map_html(record, title)}

  <h4>Quem ataca quem</h4>
  {_confrontation_graph_html(record)}
  {_confrontations_html(record)}

  <h4>Legenda das regras</h4>
  {_rules_legend_html(record)}

  <h4>Os argumentos, um a um</h4>
  {_arguments_html(record)}

  {_argumentation_html(record)}
  {_decision_html(record)}
  {_unattributed_html(record)}

  <h4>A teoria de cada perspectiva</h4>
  <p class="lead">Cada perspectiva com as suas regras e as premissas de que
  elas precisam, mais as que ela própria afirma. Uma teoria que não deriva o
  resultado não é necessariamente errada — pode ser uma posição que só ataca,
  ou uma anotação incompleta.</p>
  {_theories_html(record)}
</section>
"""
