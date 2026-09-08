"""The conference desk: is this formalization worth trusting?

The didactic view says what the analysis concluded, the fiche says where the
framework came from, the dossier view says what the annotator wrote. This
module asks the question those three leave open -- **how good is the
translation between them?** -- and answers it with numbers a non-programmer
can read:

* **Solver × corte.** How many causal questions the framework answers the way
  the court did, and, for each divergence, the two readings side by side. A
  mismatch is the pipeline's most informative output, not a failure.
* **Cobertura do dossiê.** Which marked passages of the judgment ended up
  cited by some atom, rule or question -- and which were ignored. A
  formalization that uses three of forty passages is telling you something.
* **Rastreabilidade.** Which atoms and rules were written without pointing at
  any passage at all.
* **Checagens.** The deterministic validation report (`formalize.validate`)
  that gated publication.
* **Execução.** Model, prompts, retries and token cost of the run.

Everything here is computed from artifacts already on disk; nothing calls a
model and nothing re-runs the pipeline.
"""
import html

from typing import Dict, List, Optional, Set

from . import catalog
from .dossier_view import passages_for
from .formalization_view import COURT_VERDICT_LABELS


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


# ----------------------------------------------------------------------
# Computation
# ----------------------------------------------------------------------
#: Evidence ids are prefixed by kind in the annotation tool: `src_` for a
#: quoted passage of the PDF, `prec_`/`divg_`/`unit_`/`synth_` for a record of
#: the dossier. The stages are told to cite passages in `evidence` and records
#: in `dossier_refs`, but a record id in `evidence` is a citation, not an
#: error -- so the two families are separated here rather than counted as
#: dangling references.
PASSAGE_PREFIX = "src_"


def cited_evidence(record) -> Set[str]:
    """Every id the formalization cites as evidence, of either kind."""
    ids: Set[str] = set()
    for atom in record.atoms:
        ids.update(atom.evidence)
    for meta in record.rules_meta:
        ids.update(meta.evidence)
    for query in record.queries:
        ids.update(query.evidence)
    if record.lrc is not None:
        for premise in record.lrc.doctrinal_premises:
            ids.update(premise.evidence)
        for rule in record.lrc.scheme_rules:
            ids.update(rule.evidence)
    return ids


def referenced_records(record) -> Set[str]:
    """Every dossier record id (`divg_*`, `unit_*`, `prec_*`, `synth_*`) the
    formalization derived something from -- from `dossier_refs`, plus the
    record ids that turn up inside `evidence` fields."""
    ids: Set[str] = set()
    for atom in record.atoms:
        ids.update(atom.dossier_refs)
    for meta in record.rules_meta:
        ids.update(meta.dossier_refs)
    ids.update(i for i in cited_evidence(record) if not i.startswith(PASSAGE_PREFIX))
    return ids


def coverage_report(record, case_id: Optional[str] = None) -> dict:
    """How much of the dossier the formalization actually used.

    Passage coverage is computed whenever passages can be resolved at all
    (dossier or run brief); record coverage needs the raw dossier, since the
    brief does not enumerate record ids as a citable set, and is reported as
    `None` when unavailable rather than as a misleading zero.
    """
    case_id = case_id or record.case.id
    dossiers = catalog.dossiers_by_id(case_id)

    # Coverage is measured against **every** annotator's marked passages, not
    # only the one the formalization was built from. Two reasons. A citation
    # to another annotator's passage then resolves instead of being reported
    # as dangling; and the number that matters -- how much of what was marked
    # got used -- is only honest over everything that was marked.
    attributed = catalog.all_passages(case_id)
    if attributed:
        passages = {pid: passage for pid, (_, passage) in attributed.items()}
        source = ("dossiê anotado" if len(dossiers) == 1 else
                  f"{len(dossiers)} dossiês anotados")
    else:
        passages, source = passages_for(case_id, record)

    cited = {i for i in cited_evidence(record) if i.startswith(PASSAGE_PREFIX)}
    known = set(passages)
    referenced = referenced_records(record)

    # Which annotator each side of the count belongs to. The ids are disjoint
    # across exports, so this partition is exact.
    by_annotator: Dict[str, dict] = {}
    for pid, (annotator, _) in attributed.items():
        entry = by_annotator.setdefault(annotator, {"total": 0, "cited": 0})
        entry["total"] += 1
        if pid in cited:
            entry["cited"] += 1

    record_ids: Optional[Set[str]] = None
    if dossiers:
        record_ids = set()
        for dossier in dossiers:
            record_ids |= set(dossier.valid_ids()) - set(dossier.passages())

    return {
        "case_id": case_id,
        "passage_source": source,
        "annotators": sorted(d.annotator for d in dossiers),
        "passages": {
            "total": len(known),
            "cited": sorted(cited & known),
            "uncited": sorted(known - cited),
            "unresolved": sorted(cited - known) if known else sorted(cited),
            "by_annotator": by_annotator,
            "objects": passages,
        },
        "records": None if record_ids is None else {
            "total": len(record_ids),
            "referenced": sorted(referenced & record_ids),
            "unreferenced": sorted(record_ids - referenced),
            "unresolved": sorted(referenced - record_ids),
        },
        "untraced": {
            "atoms": [a.code for a in record.atoms if not a.evidence],
            "rules": [m.id for m in record.rules_meta if not m.evidence],
            "queries": [q.question_pt or f"{q.phi} → {q.psi}"
                        for q in record.queries if not q.evidence],
        },
    }


def agreement_counts(comparison: List[dict]) -> Dict[str, int]:
    counts = {"match": 0, "mismatch": 0, "indefinido": 0}
    for row in comparison:
        key = row.get("agreement", "indefinido")
        counts[key] = counts.get(key, 0) + 1
    return counts


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------
def _score_card(value: str, label: str, tone: str, detail: str = "") -> str:
    return (
        f'<div class="score {tone}"><span class="score-value">{_esc(value)}</span>'
        f'<span class="score-label">{_esc(label)}</span>'
        + (f'<span class="score-detail">{_esc(detail)}</span>' if detail else "")
        + "</div>"
    )


def _pair(row: dict) -> str:
    return f'{row.get("phi", "?")} → {row.get("psi", "?")}'


def _agreement_block(comparison: List[dict]) -> str:
    if not comparison:
        return "<p>Nenhuma pergunta causal foi avaliada neste caso.</p>"
    counts = agreement_counts(comparison)
    total = len(comparison)
    matches = counts["match"]
    tone = "good" if matches == total else ("warn" if matches else "bad")
    cards = (
        _score_card(f"{matches}/{total}", "perguntas em que solver e corte coincidem", tone)
        + _score_card(str(counts["mismatch"]), "divergências", "bad" if counts["mismatch"] else "good")
        + _score_card(str(counts["indefinido"]), "sem decisão da corte para comparar", "neutral")
    )

    divergences = [row for row in comparison if row.get("agreement") == "mismatch"]
    detail = ""
    if divergences:
        blocks = "".join(
            '<article class="mismatch-card">'
            f'<h5>{_esc(row.get("question_pt") or _pair(row))}</h5>'
            '<div class="two-col">'
            f'<div><span class="col-label">O framework concluiu</span>'
            f'<p>{_esc(row.get("solver_label_pt") or "—")}</p></div>'
            f'<div><span class="col-label">A corte decidiu</span>'
            f'<p>{_esc(COURT_VERDICT_LABELS.get(row.get("court_verdict"), row.get("court_verdict")))}'
            f' — {_esc(row.get("court_rationale_pt"))}</p></div>'
            "</div></article>"
            for row in divergences
        )
        detail = (
            "<h5>Onde os dois discordam</h5>"
            '<p class="lead">Cada divergência aponta para um trecho da '
            "formalização a revisar: uma regra que deveria ser um ataque à "
            "regra e virou contradição direta, uma premissa que a corte "
            "afastou e o modelo manteve, ou uma leitura do acórdão que merece "
            "outra discussão.</p>"
            f"{blocks}"
        )
    return f'<div class="score-row">{cards}</div>{detail}'


def _passage_list(ids: List[str], passages: Dict[str, object], limit: int = 12) -> str:
    items = []
    for passage_id in ids[:limit]:
        passage = passages.get(passage_id)
        if passage is None:
            items.append(f"<li><code>{_esc(passage_id)}</code></li>")
            continue
        page = f"p. {passage.page}" if passage.page else "página não informada"
        items.append(
            f'<li><span class="passage-where">{_esc(page)}</span>'
            f'<span class="passage-text">“{_esc(" ".join(passage.text.split()))}”</span></li>'
        )
    rest = len(ids) - limit
    more = f'<li class="muted">e mais {rest}…</li>' if rest > 0 else ""
    return f'<ul class="passage-list">{"".join(items)}{more}</ul>'


def _coverage_block(report: dict) -> str:
    passages = report["passages"]
    total = passages["total"]
    cited = len(passages["cited"])
    if not total:
        source_note = ('<p class="notice">Não foi possível localizar os trechos '
                       "do acórdão, então a cobertura não pôde ser medida.</p>")
        return source_note

    pct = round(100 * cited / total)
    tone = "good" if pct >= 70 else ("warn" if pct >= 40 else "bad")
    cards = _score_card(f"{cited}/{total}", "trechos marcados que a formalização cita", tone,
                        f"{pct}% do que o anotador destacou")
    records = report["records"]
    if records:
        used = len(records["referenced"])
        rtotal = records["total"]
        rpct = round(100 * used / rtotal) if rtotal else 0
        cards += _score_card(f"{used}/{rtotal}", "registros do dossiê aproveitados",
                             "good" if rpct >= 70 else ("warn" if rpct >= 40 else "bad"),
                             "perspectivas, divergências, unidades e síntese")
    unresolved = passages["unresolved"]
    if unresolved:
        cards += _score_card(str(len(unresolved)), "citações a trechos inexistentes", "bad",
                             "o modelo citou um id que não está no dossiê")

    sections = [f'<div class="score-row">{cards}</div>']
    by_annotator = passages.get("by_annotator") or {}
    if len(by_annotator) > 1:
        rows = "".join(
            f"<tr><td><code>{_esc(annotator)}</code></td>"
            f'<td class="num">{entry["total"]}</td>'
            f'<td class="num">{entry["cited"]}</td>'
            f'<td class="num">{round(100 * entry["cited"] / entry["total"]) if entry["total"] else 0}%</td></tr>'
            for annotator, entry in sorted(by_annotator.items())
        )
        sections.append(
            "<h5>De quem são os trechos que a formalização usou</h5>"
            '<p class="lead">O caso foi anotado por mais de uma pessoa, e a '
            "formalização saiu de um dos dossiês. Esta tabela diz de qual — e "
            "quanto do trabalho dos outros ficou de fora.</p>"
            "<table><thead><tr><th>Anotador</th><th>Trechos marcados</th>"
            "<th>Citados</th><th>%</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>")
    if passages["uncited"]:
        sections.append(
            "<h5>Trechos marcados que a formalização não usou</h5>"
            '<p class="lead">Nem todo trecho precisa virar átomo ou regra — mas '
            "se algo decisivo aparece aqui, faltou modelagem.</p>"
            + _passage_list(passages["uncited"], passages["objects"])
        )
    if unresolved:
        ids = "".join(f"<li><code>{_esc(i)}</code></li>" for i in unresolved)
        sections.append("<h5>Citações que não correspondem a nenhum trecho</h5>"
                        f"<ul>{ids}</ul>")
    if records and records["unreferenced"]:
        ids = "".join(f"<li><code>{_esc(i)}</code></li>" for i in records["unreferenced"])
        sections.append(
            "<h5>Registros do dossiê que nenhum átomo ou regra invocou</h5>"
            f"<ul class=\"id-list\">{ids}</ul>")
    return "".join(sections)


def _traceability_block(report: dict) -> str:
    untraced = report["untraced"]
    parts = []
    for key, label in (("atoms", "átomos"), ("rules", "regras"),
                       ("queries", "perguntas causais")):
        items = untraced[key]
        if not items:
            continue
        entries = "".join(f"<li>{_esc(i)}</li>" for i in items)
        parts.append(f"<p><strong>{len(items)} {label} sem trecho vinculado:</strong></p>"
                     f'<ul class="id-list">{entries}</ul>')
    if not parts:
        return ('<p class="ok-note">Todo átomo, toda regra e toda pergunta causal '
                "aponta para ao menos um trecho do acórdão.</p>")
    return ('<p class="lead">Estes elementos entraram no framework sem citar o '
            "acórdão. Podem ser legítimos (um dever normativo, um elo causal "
            "óbvio), mas não são auditáveis pelo texto.</p>" + "".join(parts))


def _checks_block(validation: Optional[dict]) -> str:
    if not validation:
        return ('<p class="notice">Este caso não tem relatório de validação '
                "gravado.</p>")
    errors = validation.get("errors") or []
    warnings = validation.get("warnings") or []
    if not errors and not warnings:
        return ('<p class="ok-note">As checagens determinísticas — gramática das '
                "regras, códigos dos átomos, literais existentes, rebuts mútuos "
                "sem undercut, coerência da camada de relevância — não apontaram "
                "nenhum problema.</p>")

    def render(items, label, css):
        if not items:
            return ""
        entries = "".join(
            f'<li><code>{_esc(i.get("code"))}</code> {_esc(i.get("message"))}'
            + (f' <span class="muted">({_esc(i.get("where"))})</span>' if i.get("where") else "")
            + "</li>"
            for i in items
        )
        return f'<p><strong>{label}:</strong></p><ul class="{css}">{entries}</ul>'

    return render(errors, "Erros", "issues errors") + render(warnings, "Avisos", "issues warnings")


def _runs_block(case_id: str) -> str:
    runs = catalog.run_summaries(case_id)
    if not runs:
        return ""
    rows = []
    for run in runs:
        usage = run.get("usage") or {}
        stages = run.get("stages") or []
        attempts = sum(stage.get("attempts", 0) for stage in stages)
        retries = attempts - len(stages) if stages else 0
        status = "concluída" if run.get("ok") else ("incompleta" if not run.get("complete")
                                                    else "falhou")
        rows.append(
            "<tr>"
            f'<td class="mono">{_esc(run["run_id"])}</td>'
            f'<td>{_esc(run.get("created_at", "—"))}</td>'
            f'<td>{_esc(run.get("model", "—"))}</td>'
            f'<td>{_esc(run.get("llm_calls", "—"))}</td>'
            f"<td>{_esc(retries) if stages else '—'}</td>"
            f'<td>{_esc(usage.get("total_tokens", "—"))}</td>'
            f"<td>{_esc(status)}</td>"
            "</tr>"
        )
    return (
        "<h4>Execuções do pipeline</h4>"
        '<p class="lead">Cada tentativa de formalizar este dossiê. "Reparos" '
        "conta quantas vezes uma etapa teve de ser reenviada ao modelo depois "
        "de reprovar nas checagens — quanto mais, mais frágil o prompt.</p>"
        "<table><thead><tr><th>Execução</th><th>Quando</th><th>Modelo</th>"
        "<th>Chamadas</th><th>Reparos</th><th>Tokens</th><th>Situação</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def render_evaluation(record, validation: Optional[dict] = None,
                      case_id: Optional[str] = None) -> str:
    """The conference `<section>` for one formalized case."""
    from formalize.validate import build_comparison

    case_id = case_id or record.case.id
    comparison = (validation or {}).get("comparison") or build_comparison(record)
    report = coverage_report(record, case_id)

    return f"""
<section class="evaluation">
  <h3>Conferência</h3>
  <p class="lead">Quatro perguntas sobre a qualidade desta tradução: ela chega
  ao mesmo resultado da corte? usa o que o anotador marcou? cita o acórdão?
  passa nas checagens automáticas?</p>

  <h4>O framework chegou onde a corte chegou?</h4>
  {_agreement_block(comparison)}

  <h4>A formalização usou o dossiê?</h4>
  {_coverage_block(report)}

  <h4>Dá para rastrear tudo até o acórdão?</h4>
  {_traceability_block(report)}

  <h4>Checagens automáticas</h4>
  {_checks_block(validation)}

  {_runs_block(case_id)}
</section>
"""
