#!/usr/bin/env python3
"""Pipeline output script: writes each catalog formalization's static report
under `docs/graphs/<case>.html` and standalone figures under `docs/figures/`.
Uses the same `interface` modules as the live application.
"""

"""Generates a self-contained static report for a formalized case.

    uv run python scripts/render_translated.py                    # all cases
    uv run python scripts/render_translated.py case-003-final     # one case

Writes `docs/graphs/<case>.html`: a single file with no server or network,
stacking explorer views in tab order (Analysis, Dossier, Perspectives,
Weights, Formalization, Validation). Also writes the paper's standalone figures:

    <case>-cif.svg            cause-in-fact argument graph
    <case>-lrc.svg            legal-relevance argument graph
    <case>-adjudication.svg   numbered attack structure with phase/outcome legend
    <case>-confrontation.svg  perspective-to-perspective confrontations

`scripts/generate_graphs.py` does the equivalent for the paper's five
reference cases, specified by hand without formalization records. This
script handles dossier cases, which have records and hence dossier,
formalization and validation views, plus preferences when weights are declared.

The HTML uses the live application's rendering modules
(`interface.didactic`, `interface.dossier_view`, `interface.perspective_view`,
`interface.preference_view`, `interface.formalization_view`, `interface.evaluation`),
keeping static files and live pages consistent.

Requires Graphviz (`dot`) and librsvg (`rsvg-convert`) for the standalone
adjudication PDF, whose vector legend is embedded in the SVG before export.
"""
import argparse
import html
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from cases import catalog  # noqa: E402
from cases.workspace import docs_dir, workspace_root  # noqa: E402
from analysis import perspectives as P  # noqa: E402
from interface.architecture_view import render_architecture  # noqa: E402
from interface.didactic import render_case_didactic  # noqa: E402
from interface.dossier_view import render_dossier  # noqa: E402
from interface.evaluation import render_evaluation  # noqa: E402
from interface.formalization_view import render_formalization_fiche  # noqa: E402
from interface.graph_export import render_to_file, to_dot  # noqa: E402
from interface.perspective_view import render_perspectives  # noqa: E402
from interface.preference_view import render_preferences  # noqa: E402
from interface.report import GRAPH_INTERACTIVITY_JS, PAGE_CSS  # noqa: E402
from formalize import build  # noqa: E402

FIGURES_DIR = docs_dir() / "figures"
REPORT_DIR = docs_dir() / "graphs"


def _short(path) -> str:
    """Path relative to the workspace, where `docs/` now lives."""
    try:
        return str(path.relative_to(workspace_root()))
    except ValueError:
        return str(path)


def write_figures(record) -> list:
    """Standalone case figures in SVG and PDF. Returns their paths."""
    written = []
    frameworks = [("cif", "F", build.cif_framework(record), "Camada de causa de fato"),
                  ("lrc", "R", build.lrc_framework(record), "Camada de relevância jurídica")]
    for suffix, tag, af, title in frameworks:
        if af is None:
            continue
        extension, _ = af.compute_grounded_extension()
        dot = to_dot(af, extension, title=f"{record.case.title} — {title}",
                     layer_tag=tag)
        for fmt in ("svg", "pdf"):
            path = FIGURES_DIR / f"{record.case.id}-{suffix}.{fmt}"
            render_to_file(dot, path, fmt=fmt)
            written.append(path)

    dot = P.to_adjudication_dot(
        record, title=f"{record.case.title} — adjudicação",
        known=P.perspectives_in(record))
    from interface.adjudication_translation import translate_adjudication_dot

    dot = translate_adjudication_dot(dot)
    for fmt in ("svg", "pdf"):
        path = FIGURES_DIR / f"{record.case.id}-adjudication.{fmt}"
        render_to_file(dot, path, fmt=fmt)
        written.append(path)

    dot = P.to_confrontation_dot(
        record, title=f"{record.case.title} — quem enfrenta quem")
    for fmt in ("svg", "pdf"):
        path = FIGURES_DIR / f"{record.case.id}-confrontation.{fmt}"
        render_to_file(dot, path, fmt=fmt)
        written.append(path)
    return written


#: `(anchor, label, renderer, always?)`. The report is a reading of the
#: case: it keeps what answers “what was decided and
#: why”: analysis, moves, formalization and validation. The annotated dossier
#: is raw input and alone accounted for 38% of the file; weights
#: appear only when declared. Both remain available in the live application
#: (`scripts/run_app.py`), where readers can consult the source.
VIEWS = [
    ("arquitetura", "Arquitetura",
     lambda record: render_architecture(record), True),
    ("analise", "Análise",
     lambda record: render_case_didactic(build.to_case_spec(record)), True),
    ("perspectivas", "Perspectivas",
     lambda record: render_perspectives(record, title=record.case.title), True),
    ("pesos", "Pesos",
     lambda record: render_preferences(record), False),
    ("formalizacao", "Formalização",
     lambda record: render_formalization_fiche(
         record, catalog.validation_by_id(record.case.id)), True),
    ("conferencia", "Conferência",
     lambda record: render_evaluation(
         record, catalog.validation_by_id(record.case.id), record.case.id), True),
]


def build_report(record) -> str:
    blocks, toc = [], []
    for anchor, label, render, always in VIEWS:
        if not always and record.preferences is None:
            continue
        try:
            body = render(record)
        except Exception as exc:  # noqa: BLE001 - a broken view must not suppress the rest
            body = (f'<section><h3>{html.escape(label)}</h3>'
                    f'<p class="notice">Esta vista não pôde ser gerada: '
                    f'{html.escape(str(exc))}</p></section>')
        blocks.append(f'<div id="{anchor}">{body}</div>')
        toc.append(f'<a href="#{anchor}">{html.escape(label)}</a>')

    title = html.escape(record.case.title)
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{PAGE_CSS}</style>
</head>
<body>
<h1>{title}</h1>
<p class="lead">Todas as visualizações do explorador, empilhadas num arquivo
só. Gerado por <code>scripts/render_translated.py</code> a partir de
<code>data/translated/{html.escape(record.case.id)}/case.json</code>. Para a
versão viva, com abas e glossário ao passar o mouse, rode
<code>uv run python scripts/run_app.py</code>.</p>
<nav class="toc">{" ".join(toc)}</nav>
{"".join(blocks)}
<script>{GRAPH_INTERACTIVITY_JS}
bindGraphInteractivity(document);</script>
</body>
</html>
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("case_id", nargs="*", help="Ids de caso (padrão: todos).")
    args = parser.parse_args(argv)

    records = catalog.formalized_records()
    if args.case_id:
        records = {k: v for k, v in records.items() if k in set(args.case_id)}
    if not records:
        print("Nenhum caso formalizado encontrado.", file=sys.stderr)
        return 1

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for case_id, record in records.items():
        for path in write_figures(record):
            print(f"Escrito {_short(path)}")
        report = REPORT_DIR / f"{case_id}.html"
        report.write_text(build_report(record), encoding="utf-8")
        print(f"Escrito {_short(report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
