"""The panorama: every case in the repository, in one screen.

Before drilling into a single case, someone evaluating this work needs the
aggregate -- how many cases exist, how many came from an annotated dossier,
how often the framework lands where the court landed, and what is still
pending. The per-case views answer "is *this* formalization good?"; this one
answers "how is the whole thing going?".

It also surfaces the two asymmetries that are invisible from a case page: a
dossier that has been annotated but never formalized, and a formalization
whose source dossier is no longer on disk.
"""
import html

from typing import Dict, List

from . import catalog
from .evaluation import agreement_counts


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def overview_rows(directory=None) -> List[dict]:
    """One row per case in the catalog, with whatever the record and the
    validation report can tell us. Paper cases carry neither, and are
    reported as reference cases rather than padded with zeros."""
    records = catalog.formalized_records(directory)
    dossiers = catalog.dossier_paths()
    rows = []
    for entry in catalog.listing(directory):
        case_id = entry["id"]
        record = records.get(case_id)
        validation = catalog.validation_by_id(case_id, directory) if record else None
        comparison = (validation or {}).get("comparison") or []
        row = {
            **entry,
            "atoms": len(record.atoms) if record else None,
            "rules": len(record.rules_meta) if record else None,
            "queries": len(record.queries) if record else len(
                catalog.case_by_id(case_id, directory).queries),
            "agreement": agreement_counts(comparison) if comparison else None,
            "validation_ok": None if validation is None else validation.get("ok"),
            "issues": None if validation is None else (
                len(validation.get("errors") or []) + len(validation.get("warnings") or [])),
            "has_dossier": case_id in dossiers,
            "runs": len(catalog.run_summaries(case_id, directory)) if record else 0,
        }
        rows.append(row)
    return rows


def pending_dossiers(directory=None) -> List[dict]:
    """Dossiers on disk that no formalization has consumed yet."""
    formalized = set(catalog.formalized_records(directory))
    return [
        {"case_id": case_id, "path": str(path)}
        for case_id, path in catalog.dossier_paths().items()
        if case_id not in formalized
    ]


def _totals(rows: List[dict]) -> Dict[str, int]:
    match = sum((row["agreement"] or {}).get("match", 0) for row in rows)
    mismatch = sum((row["agreement"] or {}).get("mismatch", 0) for row in rows)
    undecided = sum((row["agreement"] or {}).get("indefinido", 0) for row in rows)
    return {
        "cases": len(rows),
        "paper": sum(1 for row in rows if row["origin"] == "paper"),
        "dossie": sum(1 for row in rows if row["origin"] != "paper"),
        "compared": match + mismatch + undecided,
        "match": match,
        "mismatch": mismatch,
    }


def _tile(value, label: str, tone: str = "neutral", detail: str = "") -> str:
    return (
        f'<div class="score {tone}"><span class="score-value">{_esc(value)}</span>'
        f'<span class="score-label">{_esc(label)}</span>'
        + (f'<span class="score-detail">{_esc(detail)}</span>' if detail else "")
        + "</div>"
    )


def _agreement_cell(row: dict) -> str:
    agreement = row["agreement"]
    if not agreement:
        return '<td class="muted">caso de referência do artigo</td>'
    total = sum(agreement.values())
    match = agreement.get("match", 0)
    tone = "good" if match == total else ("warn" if match else "bad")
    bar = f'<span class="bar"><span class="bar-fill {tone}" style="width:{round(100*match/total) if total else 0}%"></span></span>'
    return (f'<td class="agreement-cell">{bar}'
            f'<span class="agreement-text">{match} de {total} coincidem</span></td>')


def _validation_cell(row: dict) -> str:
    if row["validation_ok"] is None:
        return '<td class="muted">—</td>'
    if row["validation_ok"] and not row["issues"]:
        return '<td class="verdict yes">sem apontamentos</td>'
    if row["validation_ok"]:
        return f'<td class="verdict warn">{row["issues"]} aviso(s)</td>'
    return '<td class="verdict no">reprovado</td>'


def render_overview(directory=None) -> str:
    """The panorama `<section>`: totals, one row per case, and what is
    still waiting to be formalized."""
    rows = overview_rows(directory)
    totals = _totals(rows)
    pending = pending_dossiers(directory)

    rate = (f"{round(100 * totals['match'] / totals['compared'])}%"
            if totals["compared"] else "—")
    tiles = (
        _tile(totals["cases"], "casos no acervo", "neutral",
              f"{totals['paper']} do artigo · {totals['dossie']} de dossiê")
        + _tile(totals["compared"], "perguntas causais confrontadas com a corte")
        + _tile(rate, "das perguntas terminam como a corte decidiu",
                "good" if totals["compared"] and totals["match"] == totals["compared"]
                else ("warn" if totals["match"] else "bad"),
                f"{totals['mismatch']} divergência(s)")
        + _tile(len(pending), "dossiês anotados ainda não formalizados",
                "warn" if pending else "good")
    )

    body = "".join(
        f'<tr data-case="{_esc(row["id"])}">'
        f'<td><button class="case-link" data-case="{_esc(row["id"])}">{_esc(row["title"])}</button></td>'
        f'<td><span class="case-origin">{_esc(row["origin_label"])}</span></td>'
        f'<td class="num">{_esc(row["atoms"] if row["atoms"] is not None else "—")}</td>'
        f'<td class="num">{_esc(row["rules"] if row["rules"] is not None else "—")}</td>'
        f'<td class="num">{_esc(row["queries"])}</td>'
        f"{_agreement_cell(row)}"
        f'<td>{"sim" if row["has_lrc"] else "não"}</td>'
        f"{_validation_cell(row)}"
        f'<td>{"sim" if row["has_dossier"] else "não"}</td>'
        "</tr>"
        for row in rows
    )

    pending_block = ""
    if pending:
        items = "".join(
            f'<li><strong>{_esc(entry["case_id"])}</strong> — '
            f'<code>{_esc(entry["path"])}</code></li>' for entry in pending
        )
        pending_block = (
            "<h4>Dossiês à espera de formalização</h4>"
            '<p class="lead">Anotados por um especialista, mas ainda sem uma '
            "execução do pipeline. Podem ser lidos na aba <em>Dossiê</em> assim "
            "que aparecerem no acervo.</p>"
            f'<ul class="id-list">{items}</ul>'
        )

    return f"""
<section class="overview">
  <h3>Panorama</h3>
  <p class="lead">Todo o acervo de uma vez: os casos de referência do artigo,
  os casos formalizados a partir de dossiês anotados, e o quanto cada um
  coincide com o que a corte decidiu.</p>
  <div class="score-row">{tiles}</div>

  <table class="overview-table">
    <thead><tr><th>Caso</th><th>Origem</th><th>Átomos</th><th>Regras</th>
    <th>Perguntas</th><th>Solver × corte</th><th>Relevância jurídica</th>
    <th>Checagens</th><th>Dossiê no disco</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
  {pending_block}
</section>
"""
