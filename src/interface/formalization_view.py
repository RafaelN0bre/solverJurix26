"""Renders the Formalization tab: the fiche that traces every atom and rule
of a record to its evidence, closing with the solver-vs-court table. Reads
the `FormalizedCase` record and its validation; only dossier cases have
one.
"""

"""The "formalization sheet": how a dossier case became a framework.

The didactic view answers *what the analysis concluded*. This one answers the
question a reader of the article will ask next -- **where did this framework
come from?** Every atom is shown next to the passage of the judgment that
supports it, every rule next to its plain-Portuguese rationale and its
evidence, the legal-relevance layer next to the cause-in-fact facts it was
handed, and the whole thing next to the model, the prompt files and their
hashes that produced it.

It closes with the table that motivates the pipeline: for each causal
question, what the solver concluded versus what the court decided, and whether
they agree. A mismatch is a finding, not a crash -- it points at a prompt to
iterate on, and the fiche is what makes it possible to see *which* one.

Rendered only for cases loaded from `data/translated/`; paper cases have no
formalization record.
"""
import html
import logging

from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("interface.formalization_view")

ATOM_KIND_LABELS = {
    "fato": "fato", "intermediario": "elo intermediário", "resultado": "resultado",
    "prova": "prova", "dever": "dever",
}
ATOM_STATUS_LABELS = {
    "incontroverso": "incontroverso", "controvertido": "controvertido",
    "rejeitado": "rejeitado pela corte",
}
RULE_KIND_LABELS = {
    "causal": "elo causal", "excecao": "exceção", "undercut": "ataque à regra",
    "rebut": "contradição direta",
}
COURT_VERDICT_LABELS = {
    "acolhida": "acolhida", "rejeitada": "rejeitada", "nao_decidida": "não decidida",
}
AGREEMENT_LABELS = {"match": "coincide", "mismatch": "diverge", "indefinido": "—"}


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _passages(record) -> Tuple[Dict[str, object], str]:
    """Passage id -> passage, resolved by `interface.dossier_view.passages_for`:
    the file the record names, then any dossier for the same case id, then
    the run's brief.

    Best effort: the fiche degrades to bare ids if none of the three is
    available, rather than refusing to render.
    """
    from interface.dossier_view import passages_for

    passages, source = passages_for(record.case.id, record)
    if not passages:
        logger.info("Nenhuma fonte de trechos para a ficha de %s", record.case.id)
    return passages, source


def _evidence_html(ids: List[str], passages: Dict[str, object]) -> str:
    if not ids:
        return '<span class="passage">sem trecho vinculado</span>'
    parts = []
    for passage_id in ids:
        passage = passages.get(passage_id)
        if passage is None:
            parts.append(f"<code>{_esc(passage_id)}</code>")
            continue
        page = f"p. {passage.page}" if passage.page else "página não informada"
        text = " ".join(passage.text.split())
        parts.append(
            f"<code>{_esc(passage_id)}</code>"
            f'<span class="passage">{_esc(page)} — “{_esc(text)}”</span>'
        )
    return "".join(parts)


def _source_note(passages: Dict[str, object], source: str) -> str:
    """Where the quoted passages in this fiche came from.

    Worth stating: the record names one dossier file, but the fiche happily
    falls back to another copy of the same case or to the run's brief, and a
    reader auditing a citation needs to know which document they are reading.
    """
    if not passages:
        return ('<p class="notice">Os trechos do acórdão não puderam ser '
                "carregados: nem o dossiê de origem nem o brief de uma execução "
                "estão disponíveis. Abaixo aparecem apenas os identificadores.</p>")
    if source and source != "dossiê de origem":
        return (f'<p class="notice">Trechos recuperados do <strong>{_esc(source)}</strong>, '
                "porque o dossiê que o registro nomeia não está no disco.</p>")
    return ""


def _atoms_table(record, passages) -> str:
    rows = []
    premises = set(record.knowledge_base.get("premises", []))
    axioms = {a.lstrip("¬") for a in record.knowledge_base.get("axioms", [])}
    for atom in record.atoms:
        # “CIF axiom”: the literal is an LRC conclusion entering the cause-in-fact
        # layer as an axiom. “Axiom” alone would suggest nobody
        # derived it anywhere.
        role = ("axioma do CIF" if atom.code in axioms else
                "premissa" if atom.code in premises else
                "resultado" if atom.code == record.effect else "derivado")
        rows.append(
            "<tr>"
            f'<td class="mono">{_esc(atom.code)}</td>'
            f"<td>{_esc(atom.label_pt)}</td>"
            f"<td>{_esc(ATOM_KIND_LABELS.get(atom.kind, atom.kind))}</td>"
            f"<td>{_esc(ATOM_STATUS_LABELS.get(atom.status, atom.status))}</td>"
            f"<td>{_esc(role)}</td>"
            f"<td>{_esc(', '.join(atom.perspectives))}</td>"
            f"<td>{_evidence_html(atom.evidence, passages)}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Código</th><th>Significado</th><th>Tipo</th>"
        "<th>Status</th><th>Papel</th><th>Sustentado por</th>"
        "<th>Trecho do acórdão</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _rules_table(record, passages) -> str:
    rows = []
    for meta in record.rules_meta:
        rows.append(
            "<tr>"
            f'<td class="mono">{_esc(meta.rule)}</td>'
            f"<td>{_esc(meta.gloss_pt)}</td>"
            f"<td>{_esc(RULE_KIND_LABELS.get(meta.kind, meta.kind))}</td>"
            f"<td>{_esc(meta.perspective)}</td>"
            f"<td>{_evidence_html(meta.evidence, passages)}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Regra</th><th>Leitura</th><th>Papel</th>"
        "<th>Sustentada por</th><th>Trecho do acórdão</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


ORDER_LABELS = {
    "cif_first": ("CIF → LRC", "a ordem do ICAIL 2026: o CIF resolve primeiro, e "
                  "cada <code>CaFa(φ,ψ)</code> justificado entra na LRC como "
                  "axioma (equação 1). Nada corre no sentido inverso."),
    "lrc_first": ("LRC → CIF → LRC", "as regras de qualificação da LRC correm "
                  "antes e entregam o quadro jurídico ao CIF como axioma; só a "
                  "ponte <code>cf2lrc</code>, que lê <code>CaFa</code>, espera "
                  "os fatos."),
}


def _order_block(record) -> str:
    """Layer execution order and the axioms received by each layer."""
    label, explain = ORDER_LABELS.get(record.layer_order, (record.layer_order, ""))
    cif_axioms = list(record.knowledge_base.get("axioms", []))
    lrc_axioms = list(record.lrc.knowledge_base.get("axioms", [])) if record.lrc else []

    def items(literals):
        return "".join(f"<li><code>{_esc(x)}</code></li>" for x in literals) or "<li>nenhum</li>"

    return f"""
  <h4>Ordem das camadas</h4>
  <p class="lead"><strong>{_esc(label)}</strong> — {explain}</p>
  <p><strong>Axiomas do CIF</strong> (o que a camada de relevância entregou):</p>
  <ul class="mono">{items(cif_axioms)}</ul>
  <p><strong>Axiomas da LRC</strong> (o que a camada de causa de fato entregou):</p>
  <ul class="mono">{items(lrc_axioms)}</ul>
"""


def _lrc_block(record, passages) -> str:
    layer = record.lrc
    if layer is None or not layer.scheme_rules:
        return ""
    bridged = "".join(
        f"<li><code>{_esc(literal)}</code></li>" for literal in layer.bridged_premises
    ) or "<li>nenhuma</li>"
    doctrinal = "".join(
        f"<li><code>{_esc(premise.literal)}</code> — {_esc(premise.label_pt)} "
        f"{_evidence_html(premise.evidence, passages)}</li>"
        for premise in layer.doctrinal_premises
    ) or "<li>nenhuma</li>"
    rules = "".join(
        "<tr>"
        f'<td class="mono">{_esc(rule.rule)}</td>'
        f"<td>{_esc(rule.scheme)}</td>"
        f"<td>{_esc(rule.gloss_pt)}</td>"
        f"<td>{_evidence_html(rule.evidence, passages)}</td>"
        "</tr>"
        for rule in layer.scheme_rules
    )
    duty = (f"<p><strong>Fundamento do dever de agir:</strong> {_esc(layer.duty_basis_pt)}</p>"
            if layer.duty_basis_pt else "")
    return f"""
  <h4>Camada de relevância jurídica</h4>
  <p class="lead">As premissas de ponte não foram escritas pelo modelo: são a
  saída do solver da camada de causa de fato, inseridas por código. Só as
  premissas doutrinárias e os esquemas vieram da leitura do acórdão.</p>
  {duty}
  <p><strong>Ponte, vinda do CIF como axioma (calculada pelo solver):</strong></p>
  <ul class="mono">{bridged}</ul>
  <p><strong>Premissas doutrinárias (extraídas do acórdão):</strong></p>
  <ul>{doctrinal}</ul>
  <table><thead><tr><th>Regra</th><th>Esquema</th><th>Leitura</th>
  <th>Trecho do acórdão</th></tr></thead><tbody>{rules}</tbody></table>
"""


def _comparison_table(comparison: List[dict], record) -> str:
    if not comparison:
        return "<p>Nenhuma pergunta causal avaliada.</p>"
    glosses = record.atom_glosses()
    rows = []
    for row in comparison:
        def cell(value):
            if value is None:
                return '<td class="verdict">—</td>'
            css, glyph = ("yes", "✓") if value else ("no", "✗")
            return f'<td class="verdict {css}">{glyph}</td>'

        agreement = row.get("agreement", "indefinido")
        question = row.get("question_pt") or glosses.get(row["phi"], row["phi"])
        rows.append(
            "<tr>"
            f"<td>{_esc(question)}</td>"
            f"{cell(row.get('ness'))}{cell(row.get('but_for'))}"
            f"{cell(row.get('legally_relevant'))}"
            f"<td>{_esc(COURT_VERDICT_LABELS.get(row.get('court_verdict'), row.get('court_verdict')))}</td>"
            f'<td class="agreement {_esc(agreement)}">{_esc(AGREEMENT_LABELS.get(agreement, agreement))}</td>'
            f'<td class="note">{_esc(row.get("court_rationale_pt"))}</td>'
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Pergunta causal</th>"
        '<th>NESS</th><th>Causa <span class="tech-ref">(Def. 4.3)</span></th>'
        '<th>Não fosse por <span class="tech-ref">(Def. 3.5)</span></th>'
        "<th>Juridicamente relevante</th><th>Decisão da corte</th>"
        "<th>Confere?</th><th>Razão de decidir</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _provenance_block(record) -> str:
    provenance = record.provenance
    if provenance is None:
        return ""
    prompts = "".join(
        f"<li><code>{_esc(p.path)}</code> — modelo <code>{_esc(p.model)}</code>, "
        f"sha256 <code>{_esc(p.sha256[:16])}…</code></li>"
        for p in provenance.prompts
    )
    return f"""
  <h4>Proveniência</h4>
  <p class="provenance">
    Dossiê de origem: <code>{_esc(record.case.source_file)}</code>
    (sha256 <code>{_esc(record.case.source_sha256[:16])}…</code>, anotador
    <code>{_esc(record.case.annotator)}</code>).<br>
    Execução <code>{_esc(provenance.run_id)}</code> em
    {_esc(provenance.created_at)}, modelo <code>{_esc(provenance.model)}</code>,
    schema <code>{_esc(record.schema_version)}</code>.
  </p>
  <p class="provenance"><strong>Prompts utilizados:</strong></p>
  <ul class="provenance">{prompts}</ul>
"""


def _issues_block(validation: Optional[dict]) -> str:
    if not validation:
        return ""
    warnings = validation.get("warnings") or []
    errors = validation.get("errors") or []
    if not warnings and not errors:
        return '<p class="lead">A validação determinística não apontou nenhum problema.</p>'
    def render(items, label):
        if not items:
            return ""
        entries = "".join(
            f"<li><code>{_esc(i.get('code'))}</code> {_esc(i.get('message'))}</li>"
            for i in items
        )
        return f"<p><strong>{label}:</strong></p><ul>{entries}</ul>"
    return f'<div class="open-questions">{render(errors, "Erros")}{render(warnings, "Avisos")}</div>'


def render_formalization_fiche(record, validation: Optional[dict] = None) -> str:
    """The full fiche for one formalized case."""
    from formalize.validate import build_comparison

    passages, passage_source = _passages(record)
    comparison = (validation or {}).get("comparison") or build_comparison(record)

    notes = (f'<h4>Notas de modelagem</h4><p class="open-questions">'
             f"{_esc(record.modelling_notes_pt)}</p>" if record.modelling_notes_pt else "")
    open_questions = ""
    if record.open_questions:
        items = "".join(f"<li>{_esc(q)}</li>" for q in record.open_questions)
        open_questions = (f"<h4>Pontos em aberto no dossiê</h4>"
                          f'<ul class="open-questions">{items}</ul>')

    return f"""
<section class="fiche">
  <h3>Ficha de formalização</h3>
  <p class="lead">Como o dossiê anotado virou este framework: cada literal e
  cada regra ao lado do trecho do acórdão que os sustenta, e o confronto entre
  o que o solver concluiu e o que a corte decidiu.</p>

  <h4>Solver × decisão da corte</h4>
  {_comparison_table(comparison, record)}
  {_issues_block(validation)}

  <h4>Átomos da linguagem</h4>
  {_source_note(passages, passage_source)}
  {_atoms_table(record, passages)}

  <h4>Regras do framework</h4>
  {_rules_table(record, passages)}
  {_lrc_block(record, passages)}
  {_order_block(record)}
  {notes}
  {open_questions}
  {_provenance_block(record)}
</section>
"""
