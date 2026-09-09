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

  <h3>Causal comparison: NESS cause vs but-for</h3>
  {causal_section}
"""


def render_case(case: CaseSpec, *, figures_dir=None) -> str:
    """Render one case's full `<section>` fragment.

    If `figures_dir` is given, also writes standalone `<id>.svg`/`<id>.pdf`
    figures there (for the static bundle / the paper's LaTeX); the live API
    never passes it, since a request shouldn't have file-system side effects.
    """
    af = ArgumentationFramework(case.knowledge_base, case.causal_model,
                                preferences=case.preferences)
    extension, _ = af.compute_grounded_extension()

    # Só etiqueta quando a página também mostra a camada de relevância; um
    # caso de camada única não tem ambiguidade e o prefixo seria ruído.
    layer_tag = "F" if case.lrc is not None else ""
    dot = to_dot(af, extension, title=case.title, layer_tag=layer_tag)
    if figures_dir is not None:
        render_to_file(dot, figures_dir / f"{case.id}.svg", fmt="svg")
        render_to_file(dot, figures_dir / f"{case.id}.pdf", fmt="pdf")
    graph_svg = render_to_string(dot, fmt="svg")

    justified = sorted(af.justified_conclusions())
    ness_table = ness_html_table(af, case.effect)
    causal_section = causal_comparison_section(af, case.queries, layer_tag)
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
.paths { font-size: .85rem; color: var(--muted); margin: .4rem 0 0; }
.tech-note { margin: .5rem 0 0; display: flex; flex-wrap: wrap; gap: .3rem; }
.tech-note code { font-size: .8rem; color: var(--muted); }
.tech-ref { color: var(--muted); font-weight: 400; font-size: .78rem; }
details.technical-toggle { margin-top: 1.5rem; border: 1px solid var(--border);
  border-radius: 8px; padding: .6rem .9rem; background: var(--card); }
details.technical-toggle summary { cursor: pointer; font-weight: 600; }

/* legal-relevance layer (ICAIL 2026) and the formalization fiche */
.lrc-intro { color: var(--muted); font-size: .9rem; }
.duty-basis { background: var(--card); border-left: 4px solid var(--accent);
  padding: .5rem .8rem; border-radius: 0 6px 6px 0; font-size: .9rem; }
.case-origin { display: inline-block; font-size: .72rem; font-weight: 700;
  letter-spacing: .04em; text-transform: uppercase; border-radius: 999px;
  padding: .1rem .55rem; margin-left: .5rem; vertical-align: middle;
  background: var(--card); border: 1px solid var(--border); color: var(--muted); }
.fiche h4 { margin: 1.4rem 0 .3rem; }
.fiche p.lead { color: var(--muted); font-size: .9rem; margin-top: .2rem; }
.fiche .passage { color: var(--muted); font-size: .8rem; display: block;
  margin-top: .25rem; font-style: italic; }
.fiche td.mono, .fiche th.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .8rem; white-space: nowrap; }
.agreement { font-weight: 700; text-align: center; }
.agreement.match { color: var(--accent); }
.agreement.mismatch { color: #c0392b; }
.agreement.indefinido { color: var(--muted); }
.provenance { font-size: .82rem; color: var(--muted); }
.provenance code { font-size: .78rem; }
.open-questions { font-size: .88rem; }

/* hover glossary (see annotateTerms/showTip in the page script) */
.term { border-bottom: 1px dotted currentColor; cursor: help; }
.term:focus { outline: 2px solid var(--accent); outline-offset: 1px; border-radius: 2px; }
#term-tip { position: absolute; z-index: 50; max-width: min(46ch, calc(100vw - 2rem));
  background: var(--card); color: var(--fg); border: 1px solid var(--border);
  border-left: 3px solid var(--accent); border-radius: 6px; padding: .45rem .7rem;
  font-size: .85rem; line-height: 1.4; box-shadow: 0 4px 14px rgba(0, 0, 0, .18);
  opacity: 0; visibility: hidden; transition: opacity .12s; pointer-events: none; }
#term-tip.visible { opacity: 1; visibility: visible; }

/* click-to-highlight (see bindGraphInteractivity in the page script) */
.graph-wrap.has-selection .argnode,
.graph-wrap.has-selection .argedge { opacity: .15; transition: opacity .15s; }
.graph-wrap.has-selection .argnode.hl-related,
.graph-wrap.has-selection .argedge.hl-related { opacity: 1; }
.argnode { cursor: pointer; }

/* ==================================================================
   The explorer shell: sidebar of cases, tabbed panels per case.
   Everything below is used only by `aspic.api`'s page; the static
   bundle keeps rendering as a plain document.
   ================================================================== */
.app { display: grid; grid-template-columns: minmax(230px, 300px) 1fr; gap: 2rem;
  align-items: start; }
@media (max-width: 900px) { .app { grid-template-columns: 1fr; } }

.sidebar { position: sticky; top: 1rem; border: 1px solid var(--border);
  border-radius: 10px; background: var(--card); padding: .8rem; max-height: calc(100vh - 2rem);
  overflow-y: auto; }
@media (max-width: 900px) { .sidebar { position: static; max-height: none; } }
.sidebar input[type="search"] { width: 100%; padding: .45rem .6rem; border-radius: 6px;
  border: 1px solid var(--border); background: var(--bg); color: var(--fg); font-size: .9rem; }
.group-label { font-size: .72rem; font-weight: 700; letter-spacing: .06em;
  text-transform: uppercase; color: var(--muted); margin: 1rem 0 .35rem; }
.case-list { list-style: none; margin: 0; padding: 0; display: flex;
  flex-direction: column; gap: .15rem; }
.case-list button { display: block; width: 100%; text-align: left; cursor: pointer;
  font: inherit; font-size: .88rem; line-height: 1.35; color: var(--fg);
  background: none; border: 0; border-left: 3px solid transparent; border-radius: 0 6px 6px 0;
  padding: .4rem .55rem; }
.case-list button:hover { background: var(--bg); }
.case-list button[aria-current="true"] { background: var(--bg); font-weight: 600;
  border-left-color: var(--accent); }
.case-list .case-sub { display: block; font-size: .74rem; color: var(--muted);
  font-weight: 400; }

details.how-to-read { margin: .5rem 0 1.5rem; font-size: .9rem; max-width: 78ch; }
details.how-to-read summary { cursor: pointer; color: var(--accent); }
details.how-to-read ul { margin: .6rem 0; padding-left: 1.2rem; }
details.how-to-read li { margin: .25rem 0; }

.tabs { display: flex; flex-wrap: wrap; gap: .3rem; border-bottom: 2px solid var(--border);
  margin: 0 0 1.2rem; }
.tabs button { font: inherit; font-size: .92rem; cursor: pointer; color: var(--muted);
  background: none; border: 0; border-bottom: 3px solid transparent;
  padding: .5rem .85rem; margin-bottom: -2px; border-radius: 6px 6px 0 0; }
.tabs button:hover { color: var(--fg); background: var(--card); }
.tabs button[aria-selected="true"] { color: var(--fg); font-weight: 650;
  border-bottom-color: var(--accent); }
.main { min-width: 0; }   /* let the grid column shrink so wide tables scroll */
.table-wrap { overflow-x: auto; margin: .75rem 0 1.25rem; }
.table-wrap table { margin: 0; }
.panel h3 { margin-top: 0; }
.panel h4 { margin: 1.8rem 0 .35rem; }
.panel h5 { margin: 1.1rem 0 .35rem; font-size: .95rem; }
.panel > section > p.lead:first-of-type { margin-top: .2rem; }
p.lead { color: var(--muted); font-size: .9rem; max-width: 68ch; }
.muted, .muted code { color: var(--muted); }

/* Score tiles and stat strips ------------------------------------- */
.score-row { display: flex; flex-wrap: wrap; gap: .7rem; margin: .9rem 0 1.4rem; }
.score { flex: 1 1 190px; border: 1px solid var(--border); border-left-width: 4px;
  border-radius: 8px; padding: .7rem .9rem; background: var(--card); }
.score-value { display: block; font-size: 1.7rem; font-weight: 700; line-height: 1.1; }
.score-label { display: block; font-size: .82rem; color: var(--muted); margin-top: .2rem; }
.score-detail { display: block; font-size: .75rem; color: var(--muted); margin-top: .3rem;
  font-style: italic; }
.score.good { border-left-color: var(--accent); }
.score.good .score-value { color: var(--accent); }
.score.warn { border-left-color: #d17a00; }
.score.warn .score-value { color: #d17a00; }
.score.bad { border-left-color: #c0392b; }
.score.bad .score-value { color: #c0392b; }
.score.neutral { border-left-color: var(--border); }

.stat-row { display: flex; flex-wrap: wrap; gap: 1.4rem; margin: .8rem 0 1.4rem;
  padding: .7rem .9rem; border: 1px solid var(--border); border-radius: 8px;
  background: var(--card); }
.stat-value { font-size: 1.2rem; font-weight: 700; margin-right: .35rem; }
.stat-label { font-size: .82rem; color: var(--muted); }

/* Notices ---------------------------------------------------------- */
.notice { font-size: .88rem; background: var(--card); border-left: 4px solid #d17a00;
  padding: .55rem .8rem; border-radius: 0 6px 6px 0; }
.ok-note { font-size: .88rem; background: var(--card); border-left: 4px solid var(--accent);
  padding: .55rem .8rem; border-radius: 0 6px 6px 0; }
ul.id-list { columns: 2 18rem; font-size: .84rem; }
ul.id-list code { font-size: .78rem; }
ul.issues { font-size: .86rem; }
ul.issues.errors li { color: #c0392b; }

/* Dossier ---------------------------------------------------------- */
.dossier-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: .9rem; margin: .8rem 0 1.4rem; }
.dossier-card { border: 1px solid var(--border); border-radius: 10px; padding: .8rem 1rem;
  background: var(--card); }
.dossier-card h5 { margin: 0 0 .6rem; font-size: 1rem; }
.card-index { display: inline-block; font-size: .72rem; font-weight: 700; color: var(--muted);
  border: 1px solid var(--border); border-radius: 4px; padding: 0 .3rem; margin-right: .4rem; }
.card-who { display: block; font-size: .8rem; font-weight: 400; color: var(--muted); }
.unit-status { display: inline-block; font-size: .72rem; text-transform: uppercase;
  letter-spacing: .04em; border: 1px solid var(--border); border-radius: 999px;
  padding: .05rem .5rem; margin-left: .5rem; color: var(--muted); }
.arrow { color: var(--muted); }
.dossier-field { margin: 0 0 .7rem; }
.field-label { font-size: .74rem; font-weight: 700; letter-spacing: .04em;
  text-transform: uppercase; color: var(--muted); }
.field-value p { margin: .2rem 0; }
.field-value ul { margin: .2rem 0; padding-left: 1.1rem; }
.flag { display: inline-block; font-size: .68rem; text-transform: uppercase;
  letter-spacing: .04em; background: var(--bg); border: 1px solid var(--border);
  border-radius: 999px; padding: 0 .4rem; margin-left: .3rem; color: var(--muted); }
table.sides { font-size: .85rem; margin: .2rem 0 .8rem; }
table.sides td:first-child { width: 38%; color: var(--muted); }

details.evidence { margin: .25rem 0 .5rem; }
details.evidence summary { cursor: pointer; font-size: .78rem; color: var(--accent); }
ul.passage-list { list-style: none; margin: .4rem 0; padding: 0; display: flex;
  flex-direction: column; gap: .5rem; }
ul.passage-list li { border-left: 3px solid var(--border); padding-left: .7rem; }
.passage-where { display: block; font-size: .72rem; color: var(--muted); }
.passage-text { display: block; font-size: .85rem; font-style: italic; }
.passage-meta { display: block; font-size: .72rem; color: var(--muted); margin-top: .2rem; }
.passage-uses { margin-left: .5rem; }
.passage-uses.none { color: #d17a00; }
.page-block { margin-bottom: 1.2rem; }
.brief h3 { font-size: 1.15rem; }
.brief h4 { margin: 1.4rem 0 .3rem; }
.brief h5 { margin: 1rem 0 .25rem; color: var(--muted); }
.brief p, .brief li { font-size: .9rem; }

/* Disputes, glossary ----------------------------------------------- */
table.disputes td:first-child { width: 34%; }
.dispute-why { display: block; font-size: .78rem; color: var(--muted); margin-top: .3rem; }
.dispute-outcome.kept strong { color: #c0392b; }
.dispute-outcome.failed strong { color: var(--muted); }
.dispute-note { display: block; font-size: .76rem; color: var(--muted); font-weight: 400;
  margin-top: .15rem; }
table.glossary td:first-child { width: 8rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .82rem; }
table.glossary td:last-child { width: 1%; }
.role-tag { display: inline-block; font-size: .72rem; border-radius: 999px;
  padding: .05rem .5rem; border: 1px solid var(--border); color: var(--muted);
  white-space: nowrap; }
.role-tag.effect { border-color: var(--accent); color: var(--accent); }

/* Adjudication ----------------------------------------------------- */
.turning { display: inline-block; font-size: .7rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .04em; border-radius: 999px;
  padding: .05rem .5rem; background: #f6d6d6; color: #7a1414; margin-left: .4rem; }
tr.turning-row td { background: color-mix(in srgb, #c0392b 7%, transparent); }
ul.delta { margin: 0; padding-left: 1.1rem; font-size: .8rem; }
ul.delta code { font-size: .75rem; }
.perspectives p.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .8rem; word-break: break-word; }

.factor { display: inline-block; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .76rem; border-radius: 4px; padding: .05rem .35rem; margin: .1rem .15rem .1rem 0;
  border: 1px solid var(--border); cursor: help; }
.factor.pro { border-color: var(--accent); color: var(--accent); }
.factor.contra { border-color: #c0392b; color: #c0392b; }
.factor.neutro { color: var(--muted); }
tr.case-row td { font-weight: 600; background: var(--card); }

/* Conference ------------------------------------------------------- */
.mismatch-card { border: 1px solid var(--border); border-left: 4px solid #c0392b;
  border-radius: 8px; padding: .7rem 1rem; background: var(--card); margin: .7rem 0; }
.mismatch-card h5 { margin: 0 0 .5rem; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 700px) { .two-col { grid-template-columns: 1fr; } }
.col-label { font-size: .72rem; font-weight: 700; letter-spacing: .04em;
  text-transform: uppercase; color: var(--muted); }
.two-col p { margin: .2rem 0; font-size: .88rem; }

/* Overview --------------------------------------------------------- */
table.overview-table { font-size: .86rem; }
table.overview-table td.num { text-align: center; }
button.case-link { font: inherit; font-weight: 600; color: var(--accent); background: none;
  border: 0; padding: 0; cursor: pointer; text-align: left; }
button.case-link:hover { text-decoration: underline; }
.bar { display: block; height: .4rem; border-radius: 999px; background: var(--border);
  overflow: hidden; margin-bottom: .2rem; }
.bar-fill { display: block; height: 100%; background: var(--muted); }
.bar-fill.good { background: var(--accent); }
.bar-fill.warn { background: #d17a00; }
.bar-fill.bad { background: #c0392b; }
.agreement-text { font-size: .78rem; color: var(--muted); }
td.verdict.warn { color: #d17a00; }
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
