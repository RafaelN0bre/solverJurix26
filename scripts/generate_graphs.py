#!/usr/bin/env python3
"""Entry-point script: renders the hardcoded paper cases
(`cases.examples`) into standalone figures under `docs/figures/` and one
static HTML report. The rendering comes from `interface.report`; this
script only supplies the shell and the file layout.
"""

"""Generate argument-graph figures and a static HTML report for the base
cases of the two papers (cases.examples.LEGAL_CASES): the six cause-in-fact
cases of ICAIL 2025 and the five legally-relevant-causation cases of ICAIL
2026, the latter with their LRC layer.

Outputs:
    docs/figures/<case_id>.svg   -- standalone figure, for the paper (LaTeX)
    docs/figures/<case_id>.pdf   -- same, as PDF
    docs/graphs/base-cases.html  -- one self-contained report with all cases
                                     stacked: graph + rules legend + NESS
                                     table + is_cause/but_for comparison

Case rendering itself (the `<section>` fragment, CSS, click-to-highlight
JS) lives in `interface.report` and is shared with the live API app
(`interface.api`) -- this script only supplies the "all cases on one page,
plus a table of contents" shell and the figure files.

Usage:
    uv run python scripts/generate_graphs.py

Requires the Graphviz `dot` executable on PATH (see interface.graph_export).
"""
import html
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from cases.examples import LEGAL_CASES  # noqa: E402
from cases.workspace import docs_dir  # noqa: E402
from interface.didactic import render_case_didactic  # noqa: E402
from interface.report import GRAPH_INTERACTIVITY_JS, PAGE_CSS  # noqa: E402

FIGURES_DIR = docs_dir() / "figures"
REPORT_PATH = docs_dir() / "graphs" / "base-cases.html"


#: Tabs in paper order. `leukaemia` belongs to both `papers` and is drawn
#: only once, in the 2025 tab where it originates. The 2026 tab links to it:
#: duplicate node ids would break graphs that number arguments independently.
TABS = [
    ("25", "icail2025", "ICAIL 2025 — causa de fato",
     "Os casos da Seção 5 de Pisano, Prakken, Sartor &amp; Liepina, "
     "<em>Modelling Cause-in-Fact in Legal Cases through Defeasible "
     "Argumentation</em>. Uma camada só: o mecanismo causal, com as duas noções "
     "(NESS e não-fosse-por) e o que as separa."),
    ("26", "icail2026", "ICAIL 2026 — relevância jurídica",
     "Os casos das Seções 5 e 6 de Pisano, Prakken &amp; Sartor, <em>From "
     "Cause-in-Fact to Legally Relevant Cause through Argumentation</em>. Duas "
     "camadas: o CIF resolve e cada <code>CaFa(φ,ψ)</code> justificado entra na "
     "camada de relevância como axioma (equação 1), onde os esquemas do artigo "
     "podem afastá-la."),
]

TAB_CSS = """
.tabs > input { position: absolute; opacity: 0; pointer-events: none; }
.tabbar { display: flex; flex-wrap: wrap; gap: .35rem; margin: 1.75rem 0 0;
  border-bottom: 1px solid var(--border); }
.tabbar label { padding: .55rem 1.1rem; cursor: pointer; font-weight: 600;
  color: var(--muted); border: 1px solid transparent; border-bottom: none;
  border-radius: 9px 9px 0 0; }
.tabbar label:hover { color: var(--fg); }
.tabpanel { display: none; padding-top: 1.25rem; }
#tab-25:checked ~ .tabbar label[for="tab-25"],
#tab-26:checked ~ .tabbar label[for="tab-26"] {
  color: var(--fg); background: var(--card); border-color: var(--border);
  margin-bottom: -1px; }
#tab-25:checked ~ .tabpanel-25, #tab-26:checked ~ .tabpanel-26 { display: block; }
.tab-lead { color: var(--muted); max-width: 62rem; }
"""

CROSS_REFERENCE = (
    '<p class="tab-lead"><strong>Também deste artigo:</strong> o caso da '
    'leucemia infantil, que o ICAIL 2026 reaproveita para o outro lado do '
    'esquema de omissão — ali havia dever de agir, e por isso a relevância '
    'jurídica se mantém. Está desenhado na aba <em>ICAIL 2025</em>, já com a '
    'camada de relevância: <a href="#leukaemia">ver o caso</a>.</p>'
)


def cases_of(tab_key: str, exclusive: bool = True) -> list:
    """Cases for one tab. `exclusive` excludes cases shown in the previous tab."""
    out = []
    for case in LEGAL_CASES:
        if tab_key not in case.papers:
            continue
        if exclusive and case.papers[0] != tab_key:
            continue
        out.append(case)
    return out


def build_report() -> str:
    panels, bar, inputs = [], [], []
    for index, (suffix, key, title, lead) in enumerate(TABS):
        cases = cases_of(key)
        checked = " checked" if index == 0 else ""
        inputs.append(f'<input type="radio" name="tab" id="tab-{suffix}"{checked}>')
        bar.append(f'<label for="tab-{suffix}">{title} ({len(cases)})</label>')
        toc = "\n".join(f'<a href="#{case.id}">{html.escape(case.title)}</a>'
                         for case in cases)
        # The same view used by dossier-case reports. `interface.report`
        # draws only cause in fact; ICAIL 2026 cases have a
        # relevance layer, which must also be shown.
        sections = "\n".join(
            f'<section id="{case.id}">{render_case_didactic(case)}</section>'
            for case in cases
        )
        extra = CROSS_REFERENCE if key == "icail2026" else ""
        panels.append(
            f'<div class="tabpanel tabpanel-{suffix}">'
            f'<p class="tab-lead">{lead}</p>{extra}'
            f'<nav class="toc">{toc}</nav>{sections}</div>'
        )

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Casos base — ICAIL 2025 e ICAIL 2026</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{PAGE_CSS}{TAB_CSS}</style>
</head>
<body>
<h1>Casos base — ICAIL 2025 e ICAIL 2026</h1>
<p>Os casos de referência dos dois artigos, gerados de
<code>cases.examples.LEGAL_CASES</code> por
<code>scripts/generate_graphs.py</code>: causa de fato no ICAIL 2025,
relevância jurídica no ICAIL 2026. Para trocar de caso sem regerar este
arquivo, rode <code>uv run python scripts/run_app.py</code>.</p>
<div class="tabs">
{chr(10).join(inputs)}
<div class="tabbar">{''.join(bar)}</div>
{''.join(panels)}
</div>
<script>{GRAPH_INTERACTIVITY_JS}
bindGraphInteractivity(document);</script>
</body>
</html>
"""


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report_html = build_report()
    REPORT_PATH.write_text(report_html, encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    for case in LEGAL_CASES:
        print(f"Wrote {FIGURES_DIR / (case.id + '.svg')}")
        print(f"Wrote {FIGURES_DIR / (case.id + '.pdf')}")


if __name__ == "__main__":
    main()
