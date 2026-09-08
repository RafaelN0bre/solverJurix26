"""The adjudication view: who moved what, and where the case turned.

Renders `aspic.perspectives` as the tab a jurist reads. Three pieces, in the
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

from . import factors as F
from . import perspectives as P
from .graph_export import render_to_string


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
    from . import catalog

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
  <p class="legend-note">Cada elipse é uma <strong>regra</strong>, dentro da
  caixa de quem a move. Caixa marcada <em>sem movimento</em>: essa perspectiva
  existe no dossiê e não move regra nenhuma — no modelo de Prakken isso é uma
  decisão, não uma lacuna (quem não ataca, endossa). Seta vermelha cheia: a regra <strong>afasta</strong> a
  regra apontada. Linha vermelha sem ponta: as duas regras
  <strong>se contradizem</strong> — concluem literais complementares, e o
  ataque corre nos dois sentidos, de modo que só uma preferência o resolve
  (aba <em>Pesos</em>). Seta cinza tracejada: a conclusão de uma regra
  <strong>alimenta</strong> o antecedente da outra. Elipse vermelha: regra que
  não sobreviveu — afastada por outra, ou com todos os seus argumentos
  derrotados. Marca <em>(N vozes)</em>: a regra é sustentada por N
  perspectivas por conta própria, e está desenhada na caixa da primeira.
  A última linha de cada elipse dá os <strong>argumentos</strong> que o solver
  construiu com aquela regra — <code>F·</code> na camada de causa de fato,
  <code>R·</code> na de relevância jurídica, porque as duas numeram por conta
  própria e um <code>A17</code> solto nomearia dois argumentos diferentes.
  <em>(sem argumento)</em> quer dizer que os antecedentes nunca foram
  satisfeitos, o que é diferente de a regra ter sido afastada. Passe o mouse
  para ver a regra completa, a sua leitura e a situação de cada argumento; as
  duas tabelas abaixo trazem tudo por extenso.</p>
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
    argument graph of the Análise tab, in `blocked_by.attacker` of the
    relevance report, and in the conflict table of the Pesos tab. The two
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
    `None`, and rendering that as "não" produces the nonsense this column used
    to print: `não → sim` for a step where the previous theory had not reached
    the damage and so had said nothing about what caused it. The word for
    `None` is "não avaliável", and the arrow says which of the three moved.
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


def _factor_chip(factor) -> str:
    side = "pro" if factor.side == "responsabilizacao" else (
        "contra" if factor.side == "exclusao" else "neutro")
    return (f'<span class="factor {side}" title="{_esc(factor.label)}">'
            f"{_esc(factor.code)}</span>")


def _cancellations_html(record) -> str:
    pairs = F.cancellations(record)
    if not pairs:
        return ('<p class="lead">Nenhum par de fatores se anula: não há dois '
                "fatos de lados opostos sob o mesmo ponto abstrato.</p>")
    rows = "".join(
        "<tr>"
        f"<td><strong>{_esc(abstract)}</strong></td>"
        f"<td>{_factor_chip(pro)} <span class='muted'>{_esc(pro.label)}</span></td>"
        f"<td>{_factor_chip(against)} <span class='muted'>{_esc(against.label)}</span></td>"
        "</tr>"
        for pro, against, abstract in pairs
    )
    return (
        '<p class="lead">Dois fatos de lados opostos sob o mesmo ponto abstrato '
        "se anulam — é o <code>cancels</code> do CATO. Cada linha aqui é uma "
        "questão que o acórdão disputou, com as duas respostas que recebeu: "
        "não são duas premissas soltas, é um ponto controvertido.</p>"
        "<table><thead><tr><th>Ponto abstrato</th>"
        "<th>Pesa pela responsabilização</th><th>Pesa pela exclusão</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def _balance_html(record) -> str:
    rows = []
    for key in [None, *P.perspectives_in(record)]:
        scale = F.balance(record, key)
        label = "O caso inteiro" if key is None else P._label(key)
        pro = " ".join(_factor_chip(f) for f in scale["pro"]) or "—"
        against = " ".join(_factor_chip(f) for f in scale["against"]) or "—"
        lean = {"responsabilizacao": "responsabilização", "exclusao": "exclusão",
                "empate": "empate"}[scale["lean"]]
        rows.append(
            f'<tr class="{"case-row" if key is None else ""}">'
            f"<td><strong>{_esc(label)}</strong></td>"
            f'<td class="num">{len(scale["pro"])}</td><td>{pro}</td>'
            f'<td class="num">{len(scale["against"])}</td><td>{against}</td>'
            f"<td>{_esc(lean)}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Leitura</th><th>#</th>"
        "<th>Fatores pela responsabilização</th><th>#</th>"
        "<th>Fatores pela exclusão</th><th>Pende para</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        '<p class="lead">Contagem, não peso: o CATO não soma fatores, e nem '
        "este quadro. Ele mostra de que material cada leitura dispõe — quem "
        "vence continua sendo decidido pelo solver, nas duas fases acima.</p>"
    )


def _factors_html(record) -> str:
    if not F.is_annotated(record):
        return (
            "<h4>Fatores</h4>"
            '<p class="notice">Este caso foi formalizado antes de os átomos '
            "receberem polaridade, então não há balança a mostrar. Reformalize "
            "para que cada fato declare para que lado pesa e que ponto abstrato "
            "instancia.</p>"
        )
    orphans = F.unclassified(record)
    neutral = {f.code for f in F.by_side(record)["neutro"]}
    unplaced = [code for code in orphans if code not in neutral]
    warning = ""
    if unplaced:
        items = ", ".join(f"<code>{_esc(c)}</code>" for c in unplaced)
        warning = (f'<p class="notice">{len(unplaced)} fator(es) sem ponto '
                   f"abstrato: {items}. Um fator sem ancestral não pode se "
                   "anular com nenhum outro, então a lista de pontos "
                   "controvertidos abaixo pode estar incompleta.</p>")
    return f"""
  <h4>Fatores em disputa</h4>
  <p class="lead">Cada fato do caso puxa a decisão para um lado — é a noção de
  <em>factor</em> do CATO (Aleven &amp; Ashley), formalizada em ASPIC+ por
  Prakken, Wyner, Bench-Capon e Atkinson (2015). Os esquemas de precedente
  daquele trabalho (CS1–CS4, distinguishing) não estão aqui: todos exigem um
  caso paradigma com resultado conhecido, e este acervo não tem corpus de
  precedentes.</p>
  {warning}
  <h5>Pontos controvertidos</h5>
  {_cancellations_html(record)}
  <h5>Balança de cada leitura</h5>
  {_balance_html(record)}
"""


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

  <h4>Legenda das regras</h4>
  {_rules_legend_html(record)}

  <h4>Os argumentos, um a um</h4>
  {_arguments_html(record)}

  {_argumentation_html(record)}
  {_decision_html(record)}
  {_unattributed_html(record)}
  {_factors_html(record)}

  <h4>A teoria de cada perspectiva</h4>
  <p class="lead">Cada perspectiva com as suas regras e as premissas de que
  elas precisam, mais as que ela própria afirma. Uma teoria que não deriva o
  resultado não é necessariamente errada — pode ser uma posição que só ataca,
  ou uma anotação incompleta.</p>
  {_theories_html(record)}
</section>
"""
