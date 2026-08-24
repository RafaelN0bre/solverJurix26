#!/usr/bin/env python3
"""Generate argument-graph figures and a static HTML report for the five
ICAIL 2025 legal cases (aspic.examples.LEGAL_CASES).

Outputs:
    docs/figures/<case_id>.svg   -- standalone figure, for the paper (LaTeX)
    docs/figures/<case_id>.pdf   -- same, as PDF
    docs/graphs/index.html       -- one self-contained report with all cases
                                     stacked: graph + rules legend + NESS
                                     table + is_cause/but_for comparison

Case rendering itself (the `<section>` fragment, CSS, click-to-highlight
JS) lives in `aspic.report` and is shared with the live API app
(`aspic.api`) -- this script only supplies the "all cases on one page,
plus a table of contents" shell and the figure files.

Usage:
    uv run python scripts/generate_graphs.py

Requires the Graphviz `dot` executable on PATH (see aspic.graph_export).
"""
import html
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from aspic.examples import LEGAL_CASES  # noqa: E402
from aspic.report import GRAPH_INTERACTIVITY_JS, PAGE_CSS, render_case  # noqa: E402

FIGURES_DIR = REPO_ROOT / "docs" / "figures"
REPORT_PATH = REPO_ROOT / "docs" / "graphs" / "index.html"


def build_report() -> str:
    sections = "\n".join(
        render_case(case, figures_dir=FIGURES_DIR) for case in LEGAL_CASES
    )
    toc = "\n".join(
        f'<a href="#{case.id}">{html.escape(case.title)}</a>' for case in LEGAL_CASES
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ASPIC+ Cause-in-Fact — Argument Graphs</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{PAGE_CSS}</style>
</head>
<body>
<h1>ASPIC+ Cause-in-Fact — Argument Graphs</h1>
<p>Argument graphs and cause-in-fact analysis for the five legal cases of
Section 5, Pisano, Prakken, Sartor &amp; Liepina, "Modelling Cause-in-Fact in
Legal Cases through Defeasible Argumentation" (ICAIL 2025), generated from
<code>aspic.examples.LEGAL_CASES</code> by <code>scripts/generate_graphs.py</code>.
For a live version where you can switch cases without regenerating this
file, run <code>uv run python scripts/run_app.py</code>.</p>
<nav class="toc">{toc}</nav>
{sections}
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
    print(f"Wrote {REPORT_PATH.relative_to(REPO_ROOT)}")
    for case in LEGAL_CASES:
        print(f"Wrote {(FIGURES_DIR / (case.id + '.svg')).relative_to(REPO_ROOT)}")
        print(f"Wrote {(FIGURES_DIR / (case.id + '.pdf')).relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
