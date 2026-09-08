"""The weighing, on screen: which reasons prevailed, and at what price.

A number that decides a case has to be readable by whoever the case is about.
This tab renders `aspic.preferences` as five questions a jurist can check, in
the order they matter:

* **Que eixos o julgamento pesa, e quanto.** The tuple itself -- one row per
  dimension, with the weight and the reason it was given.
* **Qual regra invoca qual eixo.** The per-rule profile. A rule absent from
  the table is neutral, and the table says so rather than leaving the reader
  to infer it from silence.
* **Onde o peso decidiu.** Every rebut or undermine whose outcome the ordering
  settled, in both layers. Undercuts never appear: ASPIC+ makes them
  preference-independent, so listing them would credit the weights with work
  they did not do.
* **O que aconteceria sem os pesos.** The same case under the basic ordering.
  This is the control, and for a judgment that turns on a head-on conflict of
  qualifications it is usually the whole argument for having weights at all:
  without them the two sides come out UNDEC and the layer answers nothing.
* **A que altura o caso vira.** The weight at which the conflict flips. A
  reader who disagrees with "4" needs to know whether the disagreement
  matters, and this is the only honest way to tell them.

Nothing here decides anything: every number is read back off frameworks the
solver built, and the counterfactuals are re-runs, not estimates.
"""
import html

from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import lrc as lrc_vocab
from . import preferences as PR
from .graph_export import argument_status
from .solver import ArgumentationFramework

#: Where to probe when looking for the weight at which a dimension flips the
#: case. Fine enough to land on a tie (which is itself a finding: an exact tie
#: is incomparability again, so the conflict stays undecided) and short enough
#: that the whole table is a handful of solver runs.
_PROBE_STEPS = 24


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _num(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:g}"


# ----------------------------------------------------------------------
# Computation
# ----------------------------------------------------------------------
def layers(record) -> List[Tuple[str, ArgumentationFramework]]:
    """`(nome da camada, framework)` para as camadas que o caso tem."""
    from formalize import build

    out: List[Tuple[str, ArgumentationFramework]] = [
        ("causa de fato", build.cif_framework(record))]
    lrc_af = build.lrc_framework(record)
    if lrc_af is not None:
        out.append(("relevância jurídica", lrc_af))
    return out


def decided_conflicts(record) -> List[dict]:
    """Every conflict the ordering settled, across both layers."""
    rows: List[dict] = []
    for layer, af in layers(record):
        for row in PR.resolved_conflicts(af):
            rows.append({**row, "layer": layer})
    return rows


def _labelling(af: ArgumentationFramework) -> Dict[str, str]:
    extension, _ = af.compute_grounded_extension()
    return argument_status(af, extension)


def without_preferences(record) -> List[dict]:
    """The same conflicts, read under the basic ordering.

    Built by re-running each layer with the ordering removed and comparing
    the two labellings argument by argument. Only arguments whose label moved
    are reported: a case where nothing moves is a case whose weights are
    decoration, and that has to be visible too.
    """
    from formalize import build

    plain = record.model_copy(deep=True)
    plain.preferences = None
    rows: List[dict] = []
    for (layer, af), (_, bare) in zip(layers(record), layers(plain)):
        with_labels, bare_labels = _labelling(af), _labelling(bare)
        for arg_id, argument in af.arguments.items():
            if not argument.defeasible_rules:
                continue
            match = next(
                (other for other in bare.arguments.values()
                 if other.signature == argument.signature), None)
            if match is None:
                continue
            before, after = bare_labels[match.id], with_labels[arg_id]
            if before == after:
                continue
            rows.append({
                "layer": layer,
                "argument": arg_id,
                "conclusion": argument.conclusion,
                "rules": list(argument.defeasible_rules),
                "without": before,
                "with": after,
            })
    return rows


def flip_points(record, reading: Optional[Callable] = None) -> List[dict]:
    """For each dimension, the weight at which the case starts reading
    differently -- or None when it never does over the probed range.

    `reading` maps a record to whatever should be watched; the default is the
    pair of labels the case is about, which is the set of justified
    conclusions of both layers.
    """
    from formalize import build

    block = record.preferences
    if block is None or not block.dimensions:
        return []
    reading = reading or _default_reading

    baseline = reading(record)
    out: List[dict] = []
    for dimension in block.dimensions:
        ceiling = max(4.0 * (dimension.weight or 1.0), 20.0)
        probe = [round(ceiling * step / _PROBE_STEPS, 3)
                 for step in range(1, _PROBE_STEPS + 1)]
        flip = None
        for weight in probe:
            probed = record.model_copy(deep=True)
            for entry in probed.preferences.dimensions:
                if entry.key == dimension.key:
                    entry.weight = weight
            if reading(probed) != baseline:
                flip = weight
                break
        out.append({
            "key": dimension.key,
            "label_pt": dimension.label_pt,
            "weight": dimension.weight,
            "flip_at": flip,
            "probed_from": probe[0],
            "probed_up_to": probe[-1],
        })
    return out


def _default_reading(record):
    from formalize import build

    frameworks = [build.cif_framework(record), build.lrc_framework(record)]
    return tuple(
        tuple(sorted(af.justified_conclusions())) if af is not None else ()
        for af in frameworks
    )


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------
def _tuple_block(model: PR.PreferenceModel, block) -> str:
    rows = "".join(
        "<tr>"
        f'<td class="mono">{_esc(dimension.key)}</td>'
        f"<td><strong>{_esc(dimension.label_pt)}</strong></td>"
        f'<td class="num">{_num(dimension.weight)}</td>'
        f'<td class="muted">{_esc(dimension.rationale_pt)}</td>'
        "</tr>"
        for dimension in block.dimensions
    )
    signature = ", ".join(f"{d.label_pt} = {d.weight:g}" for d in block.dimensions)
    return (
        f'<p class="lead">A ordenação deste caso é a tupla ⟨{_esc(signature)}⟩, '
        f"agregada por <strong>{_esc(PR.PRINCIPLE_LABELS.get(model.principle, model.principle))}</strong>. "
        "A força de uma regra é a soma dos pesos dos eixos que ela invoca; a "
        "de um argumento, a agregação das forças das regras que ele usa. "
        "Ataques por <em>undercut</em> não entram nessa conta em momento "
        "algum — no ASPIC+ eles independem de preferência.</p>"
        "<table><thead><tr><th>Eixo</th><th>Do que se trata</th><th>Peso</th>"
        f"<th>Por quê</th></tr></thead><tbody>{rows}</tbody></table>"
    )


def _profiles_block(model: PR.PreferenceModel, record) -> str:
    from formalize import build

    heads = "".join(f"<th>{_esc(d.label_pt)}</th>" for d in model.dimensions)
    known = {meta.id for meta in record.rules_meta}
    if record.lrc is not None:
        known |= {rule.rule.split(":", 1)[0].strip()
                  for rule in record.lrc.scheme_rules}
    glosses = {meta.id: meta.gloss_pt for meta in record.rules_meta}
    if record.lrc is not None:
        glosses.update({rule.rule.split(":", 1)[0].strip(): rule.gloss_pt
                        for rule in record.lrc.scheme_rules})

    rows = []
    for rule_id in sorted(known, key=lambda r: (r not in model.profiles, r)):
        strength = model.rule_strength(rule_id)
        coefficients = "".join(
            f'<td class="num">{_num(c) if c else "·"}</td>'
            for c in model.tuple_for(rule_id))
        profile = model.profiles.get(rule_id)
        rows.append(
            f'<tr class="{"" if strength is not None else "muted"}">'
            f'<td class="mono">{_esc(rule_id)}</td>'
            f"{coefficients}"
            f'<td class="num"><strong>{_num(strength)}</strong></td>'
            f'<td class="muted">{_esc(profile.rationale_pt if profile else "")}</td>'
            "</tr>"
        )
    neutral = sum(1 for r in known if model.rule_strength(r) is None)
    return (
        '<p class="lead">Cada regra declara que eixos invoca. As '
        f"<strong>{neutral}</strong> regras sem força são neutras — passos que "
        "apenas encadeiam o que já está posto, e que por isso não entram na "
        "agregação: se entrassem, o fundamento seria contado duas vezes e o "
        "elo mais fraco passaria a medir o encadeamento em lugar da razão.</p>"
        f"<table><thead><tr><th>Regra</th>{heads}<th>Força</th><th>Por quê</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _conflicts_block(record) -> str:
    rows = decided_conflicts(record)
    if not rows:
        return ('<p class="notice">Nenhum conflito deste caso foi decidido por '
                "preferência. Ou não há rebut nem undermine entre argumentos "
                "pontuados, ou os que há empatam — em qualquer dos dois casos, "
                "os pesos não fizeram trabalho nenhum aqui.</p>")
    body = "".join(
        "<tr>"
        f'<td>{_esc(row["layer"])}</td>'
        f'<td class="mono">{_esc(row["attacker"])} → {_esc(row["target"])}</td>'
        f'<td class="mono">{_esc(row["attacker_conclusion"])}</td>'
        f'<td class="num">{_num(row["attacker_strength"])}</td>'
        f'<td class="mono">{_esc(row["target_conclusion"])}</td>'
        f'<td class="num">{_num(row["target_strength"])}</td>'
        f'<td class="verdict {"yes" if row["attack_succeeded"] else "no"}">'
        f'{"prevalece" if row["attack_succeeded"] else "não prevalece"}</td>'
        "</tr>"
        for row in rows
    )
    return (
        '<p class="lead">Cada linha é um ataque cuja sorte a tupla decidiu. '
        "Um ataque <em>prevalece</em> quando o atacante não é mais fraco que a "
        "parte atacada; quando é, o ataque existe e não derrota — que é "
        "exatamente o que o ASPIC+ chama de ataque sem defeat.</p>"
        "<table><thead><tr><th>Camada</th><th>Ataque</th>"
        "<th>Conclusão do atacante</th><th>Força</th>"
        "<th>Conclusão atacada</th><th>Força</th><th>Resultado</th>"
        f"</tr></thead><tbody>{body}</tbody></table>"
    )


def _control_block(record) -> str:
    rows = without_preferences(record)
    if not rows:
        return ('<p class="ok-note">Retirar os pesos não muda o rótulo de '
                "nenhum argumento: neste caso a ordenação básica já bastava, e "
                "a tupla é descritiva, não decisória.</p>")
    body = "".join(
        "<tr>"
        f'<td>{_esc(row["layer"])}</td>'
        f'<td class="mono">{_esc(row["argument"])}</td>'
        f'<td class="mono">{_esc(", ".join(row["rules"]))}</td>'
        f'<td class="mono">{_esc(row["conclusion"])}</td>'
        f'<td><span class="badge status-{_esc(row["without"])}">{_esc(row["without"])}</span></td>'
        f'<td><span class="badge status-{_esc(row["with"])}">{_esc(row["with"])}</span></td>'
        "</tr>"
        for row in rows
    )
    undecided = sum(1 for row in rows if row["without"] == "UNDEC")
    note = ""
    if undecided:
        note = (f'<p class="lead">{undecided} argumento(s) ficavam '
                "<strong>UNDEC</strong> sem os pesos. É o desfecho que a "
                "ordenação básica dá a um rebut mútuo: ninguém vence, e a "
                "camada deixa de responder a pergunta que lhe foi feita. Não é "
                "um empate no sentido jurídico — é a ausência de uma decisão "
                "que o acórdão tomou.</p>")
    return (
        note +
        "<table><thead><tr><th>Camada</th><th>Argumento</th><th>Regras</th>"
        "<th>Conclusão</th><th>Sem pesos</th><th>Com pesos</th>"
        f"</tr></thead><tbody>{body}</tbody></table>"
    )


def _sensitivity_block(record) -> str:
    points = flip_points(record)
    if not points:
        return ""
    rows = "".join(
        "<tr>"
        f"<td><strong>{_esc(point['label_pt'])}</strong></td>"
        f'<td class="num">{_num(point["weight"])}</td>'
        + (f'<td class="num turning">{_num(point["flip_at"])}</td>'
           if point["flip_at"] is not None
           else '<td class="muted">não vira em peso nenhum entre '
                f'{_num(point["probed_from"])} e {_num(point["probed_up_to"])}</td>')
        + "</tr>"
        for point in points
    )
    return (
        '<p class="lead">O peso a partir do qual o caso passa a ser lido de '
        "outro jeito. É a única resposta honesta a quem discorda de um dos "
        "números: discordar de 4 só importa se o resultado mudasse em algum "
        "valor que o leitor esteja disposto a defender.</p>"
        "<table><thead><tr><th>Eixo</th><th>Peso adotado</th>"
        f"<th>Vira em</th></tr></thead><tbody>{rows}</tbody></table>"
    )


def render_preferences(record) -> str:
    """The `<section>` for one case's ordering, or a notice when it has none."""
    from formalize import build

    block = record.preferences
    model = build.preference_model(record)
    if model is None or block is None:
        return """
<section class="preferences">
  <h3>Pesos e preferências</h3>
  <p class="notice">Este caso roda sob a ordenação básica do ASPIC+ (Definição
  2.11): dois argumentos derrotáveis são incomparáveis, e todo ataque entre
  eles derrota. Não há tupla de pesos a mostrar — e, enquanto não houver, um
  rebut mútuo deste caso deixaria os dois lados indecididos.</p>
</section>
"""
    notes = (f'<p class="dispute-note">{_esc(block.notes_pt)}</p>'
             if block.notes_pt else "")
    return f"""
<section class="preferences">
  <h3>Pesos e preferências</h3>
  <p class="lead">O solver não decide um choque frontal de qualificações
  sozinho: na ordenação básica do ASPIC+ dois argumentos derrotáveis são
  incomparáveis, e quando cada lado ataca o outro os dois saem indecididos.
  Um acórdão que resolve esse choque o resolve <em>pesando razões</em>, e é
  isso que esta aba mostra — que razões, com que peso, e o que mudaria se os
  pesos fossem outros.</p>

  <h4>Os eixos e os seus pesos</h4>
  {_tuple_block(model, block)}
  {notes}

  <h4>Que regra invoca que eixo</h4>
  {_profiles_block(model, record)}

  <h4>Onde o peso decidiu</h4>
  {_conflicts_block(record)}

  <h4>O que aconteceria sem os pesos</h4>
  {_control_block(record)}

  <h4>A que altura o caso vira</h4>
  {_sensitivity_block(record)}
</section>
"""
