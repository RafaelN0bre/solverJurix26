"""Renders the Dossier tab: the annotator's reconstruction of the judgment,
field by field, beside its supporting passages. Reads the raw dossier (or
the normalized brief from `formalize.dossier`) so a formalization can be
audited against its input.
"""

"""The dossier side of the interface: what the annotator actually wrote.

`interface.didactic` shows what the analysis concluded and
`interface.formalization_view` shows how the framework was built; neither shows
the *input* -- the annotated dossier itself. For someone evaluating this
pipeline (a lawyer, not a programmer) that is the missing half: you cannot
judge whether a formalization is faithful without reading the reconstruction
it was made from.

This module renders that dossier the way a jurist reads a case -- synthesis,
each perspective's reconstruction, the points of divergence with what each
side sustains, the causal units, and the quoted passages of the judgment --
with every field shown next to the passages that support it.

Two fallbacks keep it useful when the raw dossier is not on disk:

* passages are looked for in the record's own `source_file` first, then in
  any dossier found under `data/` by case id, and finally in the run's
  `00_brief.md` -- the normalized text the model actually read, which is
  committed alongside the formalization and therefore always available;
* when there is no dossier at all, the brief is rendered directly, flagged
  as the derived (not raw) document that it is.
"""
import html
import re

from pathlib import Path
from typing import Dict, List, Tuple

from cases import catalog

#: Fields of a dossier record that are bookkeeping, never content.
_SKIP_FIELDS = {
    "id", "case_id", "user_id", "assignment_id", "created_at", "updated_at",
    "version", "status", "document_hash", "bounding_boxes", "document_id",
    "source_annotation_ids", "origin_refs", "sides", "target_assertion_id",
    "target_connection_id", "perspective_1", "perspective_2", "support_1",
    "support_2",
}

#: `- `src_x` (p. 3, Section, Author): “text”` -- one line of the brief's
#: passage catalog, as `formalize.dossier.Dossier._passages_block` writes it.
_BRIEF_PASSAGE_RE = re.compile(
    r"^-\s+`(?P<id>[^`]+)`\s+\((?P<where>.*?)\):\s+[“\"](?P<text>.*)[”\"]\s*$"
)


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


# ----------------------------------------------------------------------
# Where the quoted passages come from
# ----------------------------------------------------------------------
def parse_brief_passages(markdown: str) -> Dict[str, object]:
    """Recover the passage catalog from a run's `00_brief.md`.

    The brief is generated, not hand-written, so this parses a format this
    repo controls (`Dossier._passages_block`). It is a fallback, not the
    source of truth: it recovers the id, the page and the quoted text, which
    is everything the interface displays, and drops the bounding boxes and
    document ids it never shows.
    """
    from formalize.dossier import Passage

    passages: Dict[str, object] = {}
    for line in markdown.splitlines():
        match = _BRIEF_PASSAGE_RE.match(line.strip())
        if not match:
            continue
        where = match.group("where")
        page_match = re.search(r"p\.\s*(\d+)", where)
        extras = [part.strip() for part in where.split(",")[1:] if part.strip()]
        passages[match.group("id")] = Passage(
            id=match.group("id"),
            page=int(page_match.group(1)) if page_match else None,
            text=match.group("text").strip(),
            section=extras[0] if extras else "",
            author=extras[1] if len(extras) > 1 else "",
        )
    return passages


def passages_for(case_id: str, record=None) -> Tuple[Dict[str, object], str]:
    """`(passages, where they came from)` for a case, best effort.

    Tried in order of fidelity: the exact file the record names, any dossier
    for the same case id under `data/`, then the run's brief. The label is
    shown in the interface so a reader always knows which of the three they
    are looking at.
    """
    if record is not None:
        source = getattr(record.case, "source_file", "")
        if source:
            path = Path(source)
            if not path.is_absolute():
                path = catalog.REPO_ROOT / path
            if path.is_file():
                from formalize.dossier import load_dossier
                try:
                    return load_dossier(path).passages(), "dossiê de origem"
                except Exception:  # noqa: BLE001 - fall through to the next source
                    pass

    dossier = catalog.dossier_by_id(case_id)
    if dossier is not None:
        return dossier.passages(), "dossiê anotado"

    brief = catalog.brief_by_id(case_id)
    if brief:
        return (parse_brief_passages(brief["markdown"]),
                f"brief da execução {brief['run_id']}")
    return {}, ""


# ----------------------------------------------------------------------
# Rendering values of dossier fields
# ----------------------------------------------------------------------
def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "none", "null", "n/a", "-"}
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _flags_html(payload: dict) -> str:
    """Boolean annotations on a dossier entry (`is_damage`, ...) as chips."""
    chips = [
        f'<span class="flag">{_esc(key.replace("is_", "").replace("_", " "))}</span>'
        for key, value in payload.items()
        if key != "text" and value is True
    ]
    return "".join(chips)


def _item_html(item) -> str:
    if isinstance(item, dict):
        text = item.get("text") or item.get("entry") or ""
        if text:
            return f"{_esc(text)} {_flags_html(item)}"
        return " · ".join(
            f"<strong>{_esc(k)}</strong>: {_esc(v)}"
            for k, v in item.items() if not _is_empty(v)
        )
    return _esc(item)


def _text_html(text: str) -> str:
    """A free-text field. Annotators habitually type numbered or dashed
    lists into single text fields, so those are turned back into real lists;
    anything else keeps its line breaks."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) > 1 and all(re.match(r"^(-|\*|\d+[.)])\s+", line) for line in lines):
        items = "".join(
            f"<li>{_esc(re.sub(r'^(-|\*|\d+[.)])\s+', '', line))}</li>" for line in lines
        )
        return f"<ul>{items}</ul>"
    return "<p>" + "<br>".join(_esc(line) for line in lines) + "</p>"


def _value_html(value) -> str:
    if _is_empty(value):
        return ""
    if isinstance(value, list):
        return "<ul>" + "".join(f"<li>{_item_html(i)}</li>" for i in value) + "</ul>"
    if isinstance(value, dict):
        return f"<p>{_item_html(value)}</p>"
    return _text_html(str(value))


def _evidence_details(passage_ids: List[str], passages: Dict[str, object]) -> str:
    """The passages backing one field, collapsed -- the fields matter more
    than their citations, but the citation is the whole point of auditing."""
    ids = [p for p in passage_ids if p]
    if not ids:
        return ""
    quotes = []
    for passage_id in ids:
        passage = passages.get(passage_id)
        if passage is None:
            quotes.append(f'<li><code>{_esc(passage_id)}</code> — trecho não localizado</li>')
            continue
        page = f"p. {passage.page}" if passage.page else "página não informada"
        quotes.append(
            f'<li><span class="passage-where">{_esc(page)}</span>'
            f'<span class="passage-text">“{_esc(" ".join(passage.text.split()))}”</span></li>'
        )
    plural = "s" if len(ids) > 1 else ""
    return (
        f'<details class="evidence"><summary>{len(ids)} trecho{plural} do acórdão</summary>'
        f'<ul class="passage-list">{"".join(quotes)}</ul></details>'
    )


def _field_html(entity_id: str, key: str, value, evidence, passages) -> str:
    from formalize.dossier import field_label

    body = _value_html(value)
    if not body:
        return ""
    return (
        '<div class="dossier-field">'
        f'<div class="field-label">{_esc(field_label(key))}</div>'
        f'<div class="field-value">{body}</div>'
        f"{_evidence_details(evidence.get((entity_id, key), []), passages)}"
        "</div>"
    )


def _fields_html(entity_id: str, fields: dict, evidence, passages) -> str:
    return "".join(
        _field_html(entity_id, key, value, evidence, passages)
        for key, value in fields.items()
        if key not in _SKIP_FIELDS
    )


# ----------------------------------------------------------------------
# Sections
# ----------------------------------------------------------------------
def _synthesis_html(dossier, evidence, passages) -> str:
    synthesis = dossier.raw.get("synthesis") or {}
    body = _fields_html(synthesis.get("id", ""), synthesis, evidence, passages)
    if not body:
        return ""
    return (
        '<h4>Síntese do caso</h4>'
        '<p class="lead">O quadro geral que o anotador extraiu do acórdão: a '
        'questão central, o que ficou incontroverso, o que foi disputado e o '
        'que prevaleceu.</p>'
        f'<div class="dossier-card">{body}</div>'
    )


def _perspectives_html(dossier, evidence, passages) -> str:
    from formalize.dossier import perspective_label, perspective_sort_key

    records = dossier.raw.get("perspective_reconstructions") or []
    if not records:
        return ""
    ordered = sorted(records, key=lambda r: (perspective_sort_key(r.get("perspective_type", "")),
                                             r.get("perspective_type", "")))
    cards = []
    for record in ordered:
        ptype = record.get("perspective_type", "")
        who = record.get("person_or_body")
        subtitle = f'<span class="card-who">{_esc(who)}</span>' if who else ""
        body = _fields_html(record.get("id", ""), record.get("fields_json") or {},
                            evidence, passages)
        cards.append(
            f'<article class="dossier-card perspective perspective-{_esc(ptype)}">'
            f'<h5>{_esc(perspective_label(ptype))}{subtitle}</h5>'
            f'{body or "<p class=\'muted\'>Nada preenchido nesta perspectiva.</p>"}'
            "</article>"
        )
    return (
        "<h4>Como cada parte reconstruiu o caso</h4>"
        '<p class="lead">A mesma controvérsia contada por quem a sustentou: '
        'recorrente, recorrido, cada voto e a posição final da corte.</p>'
        f'<div class="dossier-cards">{"".join(cards)}</div>'
    )


def _sides_html(sides) -> str:
    if not sides:
        return ""
    rows = "".join(
        "<tr>"
        f'<td>{_esc(side.get("perspective_label") or side.get("perspective_id"))}</td>'
        f'<td>{_esc(side.get("support"))}</td>'
        "</tr>"
        for side in sides if isinstance(side, dict)
    )
    if not rows:
        return ""
    return ("<table class=\"sides\"><thead><tr><th>Quem</th>"
            f"<th>Sustenta que</th></tr></thead><tbody>{rows}</tbody></table>")


def _divergences_html(dossier, evidence, passages) -> str:
    records = dossier.raw.get("divergences") or []
    if not records:
        return ""
    cards = []
    for i, record in enumerate(records, start=1):
        point = record.get("divergence_point") or f"Divergência {i}"
        body = _fields_html(record.get("id", ""),
                            {k: v for k, v in record.items() if k != "divergence_point"},
                            evidence, passages)
        cards.append(
            '<article class="dossier-card divergence">'
            f'<h5><span class="card-index">D{i}</span> {_esc(point)}</h5>'
            f"{_sides_html(record.get('sides'))}{body}"
            "</article>"
        )
    return (
        "<h4>Pontos de divergência</h4>"
        '<p class="lead">Onde as perspectivas se chocam. É daqui que saem os '
        'ataques entre argumentos na formalização.</p>'
        f'<div class="dossier-cards">{"".join(cards)}</div>'
    )


def _origin_refs_html(refs) -> str:
    if not refs:
        return ""
    items = "".join(
        f'<li><strong>{_esc(ref.get("perspective_label"))}</strong> — '
        f'{_esc(ref.get("field_label") or ref.get("field_key"))}: {_esc(ref.get("entry"))}</li>'
        for ref in refs if isinstance(ref, dict)
    )
    if not items:
        return ""
    return (f'<details class="evidence"><summary>De onde esta unidade foi derivada</summary>'
            f"<ul>{items}</ul></details>")


def _causal_units_html(dossier, evidence, passages) -> str:
    records = dossier.raw.get("causal_units") or []
    if not records:
        return ""
    cards = []
    for i, record in enumerate(records, start=1):
        cause = (record.get("candidate_cause") or f"unidade {i}").replace("\n", " / ")
        outcome = record.get("outcome") or record.get("result_examined") or ""
        status = record.get("judgment_status") or record.get("court_treatment") or ""
        badge = f'<span class="unit-status">{_esc(status)}</span>' if status else ""
        head = _esc(cause) + (f' <span class="arrow">→</span> {_esc(outcome)}' if outcome else "")
        body = _fields_html(
            record.get("id", ""),
            {k: v for k, v in record.items()
             if k not in ("candidate_cause", "outcome", "judgment_status")},
            evidence, passages,
        )
        cards.append(
            '<article class="dossier-card unit">'
            f'<h5><span class="card-index">U{i}</span> {head}{badge}</h5>'
            f"{body}{_origin_refs_html(record.get('origin_refs'))}"
            "</article>"
        )
    return (
        "<h4>Unidades causais</h4>"
        '<p class="lead">Cada par "causa candidata → resultado" que o anotador '
        'isolou, com o mecanismo alegado e o tratamento que a corte lhe deu.</p>'
        f'<div class="dossier-cards">{"".join(cards)}</div>'
    )


def _passages_html(passages: Dict[str, object], evidence) -> str:
    if not passages:
        return ""
    used: Dict[str, int] = {}
    for (_, _), ids in evidence.items():
        for passage_id in ids:
            used[passage_id] = used.get(passage_id, 0) + 1

    by_page: Dict[object, List[object]] = {}
    for passage in sorted(passages.values(), key=lambda p: (p.page or 0, p.id)):
        by_page.setdefault(passage.page, []).append(passage)

    blocks = []
    for page, group in by_page.items():
        label = f"Página {page}" if page else "Página não informada"
        items = []
        for passage in group:
            count = used.get(passage.id, 0)
            tag = (f'<span class="passage-uses">citada em {count} campo'
                   f'{"s" if count > 1 else ""}</span>' if count
                   else '<span class="passage-uses none">não vinculada a nenhum campo</span>')
            items.append(
                f'<li><span class="passage-text">“{_esc(" ".join(passage.text.split()))}”</span>'
                f'<span class="passage-meta"><code>{_esc(passage.id)}</code>{tag}</span></li>'
            )
        blocks.append(f'<div class="page-block"><h5>{_esc(label)}</h5>'
                      f'<ul class="passage-list">{"".join(items)}</ul></div>')
    return (
        "<h4>Trechos do acórdão</h4>"
        '<p class="lead">Os recortes literais que o anotador marcou no PDF. '
        'São eles que a formalização cita como evidência.</p>'
        f'{"".join(blocks)}'
    )


def _stats_html(dossier) -> str:
    labels = {
        "perspective_reconstructions": "perspectivas",
        "divergences": "divergências",
        "causal_units": "unidades causais",
        "source_passages": "trechos marcados",
        "source_links": "vínculos trecho↔campo",
    }
    stats = dossier.stats()
    chips = "".join(
        f'<div class="stat"><span class="stat-value">{stats.get(key, 0)}</span>'
        f'<span class="stat-label">{_esc(label)}</span></div>'
        for key, label in labels.items()
    )
    return f'<div class="stat-row">{chips}</div>'


# ----------------------------------------------------------------------
# The brief, when there is no raw dossier
# ----------------------------------------------------------------------
def render_brief_html(markdown: str) -> str:
    """The run's normalized brief as HTML.

    A deliberately small Markdown subset -- headings, bullets, `code`,
    **bold**, _italic_ -- because the brief is machine-generated by
    `formalize.dossier` and uses nothing else. Code spans are extracted
    before the inline passes so ids like `src_9a…` never get mangled by the
    underscore-italic rule.
    """
    out: List[str] = []
    bullets: List[str] = []

    def flush() -> None:
        if bullets:
            out.append("<ul>" + "".join(f"<li>{item}</li>" for item in bullets) + "</ul>")
            bullets.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            flush()
            continue
        if line.startswith("### "):
            flush()
            out.append(f"<h5>{_inline(line[4:])}</h5>")
        elif line.startswith("## "):
            flush()
            out.append(f"<h4>{_inline(line[3:])}</h4>")
        elif line.startswith("# "):
            flush()
            out.append(f"<h3>{_inline(line[2:])}</h3>")
        elif line.lstrip().startswith("- "):
            bullets.append(_inline(line.lstrip()[2:]))
        else:
            flush()
            out.append(f"<p>{_inline(line)}</p>")
    flush()
    return f'<div class="brief">{"".join(out)}</div>'


def _inline(text: str) -> str:
    escaped = _esc(text)
    spans: List[str] = []

    def stash(match: "re.Match") -> str:
        spans.append(match.group(1))
        return f"\x00{len(spans) - 1}\x00"

    escaped = re.sub(r"`([^`]+)`", stash, escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"_([^_]+)_", r"<em>\1</em>", escaped)
    for index, span in enumerate(spans):
        escaped = escaped.replace(f"\x00{index}\x00", f"<code>{span}</code>")
    return escaped


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
def _dossier_body(dossier) -> str:
    """One annotator's dossier, field by field."""
    passages = dossier.passages()
    evidence = dossier.evidence_index()
    header = (
        f'<p class="provenance">Anotador <code>{_esc(dossier.annotator)}</code> · '
        f'sessão <code>{_esc(dossier.session_id or "—")}</code> · arquivo '
        f'<code>{_esc(dossier.path.name if dossier.path else "")}</code> '
        f'(sha256 <code>{_esc(dossier.sha256[:16])}…</code>)</p>'
    )
    return (header + _stats_html(dossier)
            + _synthesis_html(dossier, evidence, passages)
            + _perspectives_html(dossier, evidence, passages)
            + _divergences_html(dossier, evidence, passages)
            + _causal_units_html(dossier, evidence, passages)
            + _passages_html(passages, evidence))


def _consolidation_html(consolidation: dict) -> str:
    """The canonical consolidation, and where the three annotators parted.

    The interesting column is not the value -- it is `sustentada_por` and
    `divergencia_substantiva`: the first says whose reading survived, the
    second separates a disagreement about wording from a disagreement about
    what the judgment says.
    """
    if not consolidation:
        return ('<p class="notice">Não há consolidação canônica gravada. Rode '
                "<code>uv run python scripts/build_consolidacao_main.py</code> "
                "para produzi-la a partir das propostas dos anotadores.</p>")
    resumo = consolidation.get("resumo", {})
    cards = (
        f'<div class="score-row">'
        f'<div class="score neutral"><span class="score-value">{resumo.get("celulas", 0)}</span>'
        f'<span class="score-label">células consolidadas</span></div>'
        f'<div class="score warn"><span class="score-value">{resumo.get("divergiam_nas_propostas", 0)}</span>'
        f'<span class="score-label">em que as três propostas divergiam</span></div>'
        f'<div class="score bad"><span class="score-value">{resumo.get("divergencia_substantiva", 0)}</span>'
        f'<span class="score-label">divergências de conteúdo, não de redação</span></div>'
        f'<div class="score neutral"><span class="score-value">{resumo.get("vazias", 0)}</span>'
        f'<span class="score-label">que ninguém preencheu</span></div></div>'
    )
    rows = []
    for cell in consolidation.get("celulas", []):
        onde = f'§{cell["secao_id"]} {cell["secao"]}'
        apoio = ", ".join(cell.get("sustentada_por") or []) or "—"
        marca = ('<span class="turning">divergência de conteúdo</span>'
                 if cell.get("divergencia_substantiva") else "")
        rows.append(
            f'<tr class="{"turning-row" if cell.get("divergencia_substantiva") else ""}">'
            f"<td>{_esc(onde)}</td>"
            f'<td>{_esc(cell.get("perspectiva") or "—")}</td>'
            f'<td>{_esc(cell.get("valor") or "—")} {marca}</td>'
            f'<td class="muted">{_esc(apoio)}</td>'
            f'<td class="muted">{_esc(cell.get("justificativa") or "")}</td></tr>'
        )
    notas = consolidation.get("notas_gerais", "")
    return (
        '<p class="lead">As três anotações foram consolidadas numa leitura só, '
        "célula a célula. <em>Sustentada por</em> diz de quem é o conteúdo "
        "adotado; a linha destacada é onde a discordância era sobre o que o "
        "acórdão diz, e não sobre como dizê-lo.</p>"
        + cards
        + (f'<p class="dispute-note">{_esc(notas)}</p>' if notas else "")
        + "<table><thead><tr><th>Seção</th><th>Perspectiva</th>"
        "<th>Consolidação</th><th>Sustentada por</th><th>Por quê</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def render_dossier(case_id: str, record=None) -> str:
    """The dossier `<section>` for one case.

    Every annotator's dossier, not one of them. The case was annotated by
    three people whose exports differ in substance -- 41, 28 and 18 marked
    passages, disjoint id spaces -- and this view used to show whichever
    directory sorted first. The primary is now the one the formalization
    actually came from, the other two are here, and above both sits the
    consolidation that says which reading became the case's.
    """
    dossiers = catalog.dossiers_by_id(case_id)
    if not dossiers:
        return _render_without_dossier(case_id, record)

    primary, others = dossiers[0], dossiers[1:]
    consolidation = catalog.consolidation(case_id)
    quem = ", ".join(f"<code>{_esc(d.annotator)}</code>" for d in dossiers)
    outras = "".join(
        f'<details class="dossier-other"><summary>Anotação de '
        f"<strong>{_esc(d.annotator)}</strong> — {len(d.passages())} trechos "
        f"marcados</summary>{_dossier_body(d)}</details>"
        for d in others
    )
    return f"""
<section class="dossier">
  <h3>Dossiê anotado — {_esc(primary.title)}</h3>
  <p class="lead">A leitura humana do acórdão, antes de qualquer formalização.
  Cada campo aparece com os trechos do acórdão que o anotador vinculou a ele.
  Este caso foi anotado por {len(dossiers)} pessoa(s): {quem}.</p>

  <h4>Consolidação canônica</h4>
  {_consolidation_html(consolidation)}

  <h4>Anotação de origem da formalização — {_esc(primary.annotator)}</h4>
  <p class="lead">É desta que a formalização saiu: é o arquivo que o registro
  nomeia em <code>case.source_file</code>, e é dela que vêm os trechos citados
  por cada átomo e cada regra.</p>
  {_dossier_body(primary)}

  {'<h4>As outras anotações do mesmo acórdão</h4>' if others else ''}
  {'<p class="lead">Mesmo acórdão, outra leitura. Nenhuma delas alimentou a formalização; estão aqui porque a divergência entre anotadores é dado do caso, não ruído a esconder.</p>' if others else ''}
  {outras}
</section>
"""


def _render_without_dossier(case_id: str, record=None) -> str:
    brief = catalog.brief_by_id(case_id)
    named = getattr(getattr(record, "case", None), "source_file", "") if record else ""
    missing = (f'<p class="notice">O dossiê de origem '
               f'(<code>{_esc(named)}</code>) não está neste repositório.'
               if named else '<p class="notice">Não há dossiê anotado para este caso.')
    if brief is None:
        return (f'<section class="dossier">{missing} Sem ele e sem o brief de '
                "uma execução, não há como exibir a anotação de origem.</p></section>")
    return f"""
<section class="dossier">
  <h3>Dossiê normalizado (brief da execução {_esc(brief['run_id'])})</h3>
  {missing} O que aparece abaixo é o <strong>brief</strong> daquela execução: o
  dossiê já normalizado, que é exatamente o texto que o modelo leu para
  formalizar o caso.</p>
  {render_brief_html(brief['markdown'])}
</section>
"""
