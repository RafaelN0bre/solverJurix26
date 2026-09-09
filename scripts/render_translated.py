#!/usr/bin/env python3
"""Gera um relatório estático, autocontido, de um caso formalizado.

    uv run python scripts/render_translated.py                    # todos
    uv run python scripts/render_translated.py case-003-final     # um caso

Escreve `docs/graphs/<caso>.html` — um arquivo só, sem servidor, sem rede,
com todas as visualizações do explorador empilhadas na mesma ordem das abas
(Análise, Dossiê, Perspectivas, Pesos, Formalização, Conferência) — e, em
`docs/figures/`, as figuras isoladas de que o artigo precisa:

    <caso>-cif.svg          grafo de argumentos da camada de causa de fato
    <caso>-lrc.svg          grafo de argumentos da camada de relevância
    <caso>-adjudicacao.svg  mapa de adjudicação (quem move o quê)
    <caso>-confrontos.svg   quem enfrenta quem, por perspectiva

`scripts/generate_graphs.py` faz o equivalente para os cinco casos de
referência do artigo, que são especificados à mão e não têm registro de
formalização; este faz para os que vieram de dossiê, que têm — e por isso
têm dossiê, ficha, conferência e, quando declaram pesos, a aba de
preferências.

O HTML é gerado pelos mesmos módulos que a aplicação viva serve
(`aspic.didactic`, `aspic.dossier_view`, `aspic.perspective_view`,
`aspic.preference_view`, `aspic.formalization_view`, `aspic.evaluation`), de
modo que o arquivo estático e a página não podem divergir.
"""
import argparse
import html
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from aspic import catalog  # noqa: E402
from aspic import perspectives as P  # noqa: E402
from aspic.didactic import render_case_didactic  # noqa: E402
from aspic.dossier_view import render_dossier  # noqa: E402
from aspic.evaluation import render_evaluation  # noqa: E402
from aspic.formalization_view import render_formalization_fiche  # noqa: E402
from aspic.graph_export import render_to_file, to_dot  # noqa: E402
from aspic.perspective_view import render_perspectives  # noqa: E402
from aspic.preference_view import render_preferences  # noqa: E402
from aspic.report import GRAPH_INTERACTIVITY_JS, PAGE_CSS  # noqa: E402
from formalize import build  # noqa: E402

FIGURES_DIR = REPO_ROOT / "docs" / "figures"
REPORT_DIR = REPO_ROOT / "docs" / "graphs"


def write_figures(record) -> list:
    """As figuras isoladas do caso, em SVG e PDF. Devolve os caminhos."""
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
    for fmt in ("svg", "pdf"):
        path = FIGURES_DIR / f"{record.case.id}-adjudicacao.{fmt}"
        render_to_file(dot, path, fmt=fmt)
        written.append(path)

    dot = P.to_confrontation_dot(
        record, title=f"{record.case.title} — quem enfrenta quem")
    for fmt in ("svg", "pdf"):
        path = FIGURES_DIR / f"{record.case.id}-confrontos.{fmt}"
        render_to_file(dot, path, fmt=fmt)
        written.append(path)
    return written


#: `(âncora, rótulo, como renderizar)`, na ordem das abas do explorador.
VIEWS = [
    ("analise", "Análise",
     lambda record: render_case_didactic(build.to_case_spec(record))),
    ("dossie", "Dossiê",
     lambda record: render_dossier(record.case.id, record)),
    ("perspectivas", "Perspectivas",
     lambda record: render_perspectives(record, title=record.case.title)),
    ("pesos", "Pesos",
     lambda record: render_preferences(record)),
    ("formalizacao", "Formalização",
     lambda record: render_formalization_fiche(
         record, catalog.validation_by_id(record.case.id))),
    ("conferencia", "Conferência",
     lambda record: render_evaluation(
         record, catalog.validation_by_id(record.case.id), record.case.id)),
]


def build_report(record) -> str:
    blocks, toc = [], []
    for anchor, label, render in VIEWS:
        try:
            body = render(record)
        except Exception as exc:  # noqa: BLE001 - uma vista quebrada não some com o resto
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
            print(f"Escrito {path.relative_to(REPO_ROOT)}")
        report = REPORT_DIR / f"{case_id}.html"
        report.write_text(build_report(record), encoding="utf-8")
        print(f"Escrito {report.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
