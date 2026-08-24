"""Shared HTML rendering for a single case: the `<section>` fragment (graph
+ rules legend + NESS table + causal comparison), the page CSS, and the
click-to-highlight JS -- used by both the static multi-case bundle
(`scripts/generate_graphs.py`) and the live single-case API (`aspic.api`),
so the two entry points can never drift out of sync on how a case renders.
"""
import html

from .causal_report import causal_comparison_section, ness_html_table
from .examples import CaseSpec
from .graph_export import render_to_file, render_to_string, to_dot
from .solver import ArgumentationFramework


def technical_section_html(case: CaseSpec, graph_svg: str, ness_table: str,
                            causal_section: str) -> str:
    """The technical (English, ASPIC+-notation) markup shared by the static
    bundle and the live didactic view's collapsed "advanced" toggle: the
    graph, its legend, the NESS table and the causal-comparison table.
    Takes already-rendered pieces so callers control exactly how (and how
    often) the underlying framework gets built and the graph gets rendered.
    """
    return f"""
  <h3>Argument graph</h3>
  <div class="graph-wrap">{graph_svg}</div>
  <p class="legend-note">
    Node color: <span class="swatch in"></span> IN (grounded extension) &middot;
    <span class="swatch out"></span> OUT (defeated by an IN argument) &middot;
    <span class="swatch undec"></span> UNDEC.
    Edge style: <span class="swatch-line undercut"></span> undercut &middot;
    <span class="swatch-line rebut"></span> rebut &middot;
    <span class="swatch-line undermine"></span> undermine
    (bold = succeeded as a defeat, thin dotted grey = attack failed).
    Click a node to highlight its attackers/targets.
  </p>

  <h3>NESS analysis for <code>{html.escape(case.effect)}</code></h3>
  {ness_table}

  <h3>Causal comparison: NESS vs is_cause vs but_for</h3>
  {causal_section}
"""


def render_case(case: CaseSpec, *, figures_dir=None) -> str:
    """Render one case's full `<section>` fragment.

    If `figures_dir` is given, also writes standalone `<id>.svg`/`<id>.pdf`
    figures there (for the static bundle / the paper's LaTeX); the live API
    never passes it, since a request shouldn't have file-system side effects.
    """
    af = ArgumentationFramework(case.knowledge_base, case.causal_model)
    extension, _ = af.compute_grounded_extension()

    dot = to_dot(af, extension, title=case.title)
    if figures_dir is not None:
        render_to_file(dot, figures_dir / f"{case.id}.svg", fmt="svg")
        render_to_file(dot, figures_dir / f"{case.id}.pdf", fmt="pdf")
    graph_svg = render_to_string(dot, fmt="svg")

    justified = sorted(af.justified_conclusions())
    ness_table = ness_html_table(af, case.effect)
    causal_section = causal_comparison_section(af, case.queries)
    technical = technical_section_html(case, graph_svg, ness_table, causal_section)

    return f"""
<section class="case" id="{case.id}">
  <h2>{html.escape(case.title)}</h2>
  <p class="narrative">{html.escape(case.narrative)}</p>
  <p class="justified"><strong>Justified conclusions:</strong>
     {", ".join(f"<code>{html.escape(c)}</code>" for c in justified)}</p>
  {technical}
</section>
"""


PAGE_CSS = """
:root {
  --bg: #ffffff; --fg: #1a1a1a; --muted: #666666; --border: #dddddd;
  --card: #fafafa; --accent: #2e7d32;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #1a1a1a; --fg: #eaeaea; --muted: #aaaaaa; --border: #3a3a3a;
          --card: #242424; --accent: #66bb6a; }
}
:root[data-theme="dark"] { --bg: #1a1a1a; --fg: #eaeaea; --muted: #aaaaaa;
  --border: #3a3a3a; --card: #242424; --accent: #66bb6a; }
:root[data-theme="light"] { --bg: #ffffff; --fg: #1a1a1a; --muted: #666666;
  --border: #dddddd; --card: #fafafa; --accent: #2e7d32; }

* { box-sizing: border-box; }
body {
  margin: 0; padding: 2rem clamp(1rem, 4vw, 3rem); background: var(--bg);
  color: var(--fg); font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  line-height: 1.5;
}
h1 { margin-top: 0; }
h2 { border-bottom: 2px solid var(--border); padding-bottom: .3rem; }
nav.toc { display: flex; flex-wrap: wrap; gap: .5rem 1rem; margin: 1.5rem 0;
  padding: 1rem; background: var(--card); border: 1px solid var(--border); border-radius: 8px; }
nav.toc a { color: var(--accent); text-decoration: none; }
nav.toc a:hover { text-decoration: underline; }
select#case-select { font-size: 1rem; padding: .4rem .6rem; border-radius: 6px;
  border: 1px solid var(--border); background: var(--card); color: var(--fg); }
section.case { margin: 3rem 0; padding-bottom: 1rem; }
.graph-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 8px;
  padding: .5rem; background: var(--card); }
.graph-wrap svg { max-width: 100%; height: auto; display: block; margin: 0 auto; }
.legend-note { color: var(--muted); font-size: .85rem; }
.swatch, .swatch-line { display: inline-block; width: .9rem; height: .9rem; vertical-align: middle;
  border-radius: 3px; margin: 0 .15rem; }
.swatch.in { background: #d9f2d9; border: 1px solid #2e7d32; }
.swatch.out { background: #f6d6d6; border: 1px solid #b71c1c; }
.swatch.undec { background: #eeeeee; border: 1px solid #757575; }
.swatch-line { width: 1.4rem; height: 0; border-top: 3px solid; background: none; }
.swatch-line.undercut { border-color: #d17a00; border-top-style: dashed; }
.swatch-line.rebut { border-color: #c0392b; }
.swatch-line.undermine { border-color: #7030a0; border-top-style: dotted; }

table { border-collapse: collapse; width: 100%; margin: .75rem 0 1.25rem; }
th, td { border: 1px solid var(--border); padding: .4rem .6rem; text-align: left; font-size: .9rem; }
th { background: var(--card); }
td.verdict { text-align: center; font-weight: bold; }
td.verdict.yes { color: var(--accent); }
td.verdict.no { color: #c0392b; }
td.note { color: var(--muted); font-size: .82rem; }

details.counterfactual { margin: .5rem 0 1.25rem; border: 1px dashed var(--border);
  border-radius: 8px; padding: .5rem .75rem; background: var(--card); }
details.counterfactual summary { cursor: pointer; font-weight: 600; }
details.counterfactual .graph-wrap { margin-top: .5rem; }

code { background: var(--card); border: 1px solid var(--border); border-radius: 4px;
  padding: 0 .25rem; }

/* didactic view: conclusion summary, argument cards, technical toggle */
.conclusion-main { font-size: 1.05rem; }
.conclusion-causes { color: var(--accent); }
.conclusion-non-causes { color: #c0392b; }
.argument-cards { display: flex; flex-direction: column; gap: .6rem; margin: .75rem 0 1.5rem; }
.arg-card { border: 1px solid var(--border); border-radius: 8px; padding: .6rem .9rem;
  background: var(--card); border-left: 4px solid var(--border); }
.arg-card.status-IN { border-left-color: #2e7d32; }
.arg-card.status-OUT { border-left-color: #b71c1c; }
.arg-card.status-UNDEC { border-left-color: #757575; }
details.arg-card summary { cursor: pointer; }
.arg-card.no-detail { cursor: default; }
.badge { display: inline-block; font-size: .78rem; font-weight: 700; border-radius: 999px;
  padding: .1rem .6rem; margin-right: .4rem; }
.badge.status-IN { background: #d9f2d9; color: #205625; }
.badge.status-OUT { background: #f6d6d6; color: #7a1414; }
.badge.status-UNDEC { background: #eeeeee; color: #444444; }
.why-heading { font-weight: 600; margin: .6rem 0 .2rem; }
.attack-list { margin: 0 0 .4rem; padding-left: 1.2rem; }
.attack-list li { margin: .3rem 0; }
.attacks-out { color: var(--muted); font-size: .85rem; }
.tech-note { margin: .5rem 0 0; }
.tech-note code { font-size: .8rem; color: var(--muted); }
.tech-ref { color: var(--muted); font-weight: 400; font-size: .78rem; }
details.technical-toggle { margin-top: 1.5rem; border: 1px solid var(--border);
  border-radius: 8px; padding: .6rem .9rem; background: var(--card); }
details.technical-toggle summary { cursor: pointer; font-weight: 600; }

/* click-to-highlight (see bindGraphInteractivity in the page script) */
.graph-wrap.has-selection .argnode,
.graph-wrap.has-selection .argedge { opacity: .15; transition: opacity .15s; }
.graph-wrap.has-selection .argnode.hl-related,
.graph-wrap.has-selection .argedge.hl-related { opacity: 1; }
.argnode { cursor: pointer; }
"""

# `bindGraphInteractivity(root)` wires up click-to-highlight for every
# argument graph under `root`. It is idempotent and side-effect-free on
# nodes it isn't called on, so callers can invoke it as many times as they
# swap in new graph markup (the static bundle calls it once over `document`
# after building the whole page; the live API calls it again after every
# case swap, since replacing `innerHTML` drops the previous listeners along
# with the old nodes).
GRAPH_INTERACTIVITY_JS = """
function bindGraphInteractivity(root) {
  root.querySelectorAll('.graph-wrap svg').forEach(function (svg) {
    var wrap = svg.closest('.graph-wrap');
    svg.querySelectorAll('.argnode').forEach(function (node) {
      node.addEventListener('click', function (evt) {
        evt.stopPropagation();
        var argClass = Array.from(node.classList).find(function (c) { return c.indexOf('arg-') === 0; });
        if (!argClass) return;
        var argId = argClass.slice(4);
        var alreadySelected = wrap.classList.contains('has-selection') && node.classList.contains('hl-related');
        svg.querySelectorAll('.hl-related').forEach(function (el) { el.classList.remove('hl-related'); });
        if (alreadySelected) {
          wrap.classList.remove('has-selection');
          return;
        }
        wrap.classList.add('has-selection');
        node.classList.add('hl-related');
        svg.querySelectorAll('.argedge.from-' + argId + ', .argedge.to-' + argId).forEach(function (edge) {
          edge.classList.add('hl-related');
          var from = Array.from(edge.classList).find(function (c) { return c.indexOf('from-') === 0; });
          var to = Array.from(edge.classList).find(function (c) { return c.indexOf('to-') === 0; });
          [from, to].forEach(function (tok) {
            if (!tok) return;
            var otherId = tok.slice(tok.indexOf('-') + 1);
            var otherNode = svg.querySelector('.argnode.arg-' + otherId);
            if (otherNode) otherNode.classList.add('hl-related');
          });
        });
      });
    });
    svg.addEventListener('click', function () {
      wrap.classList.remove('has-selection');
      svg.querySelectorAll('.hl-related').forEach(function (el) { el.classList.remove('hl-related'); });
    });
  });
}
"""
