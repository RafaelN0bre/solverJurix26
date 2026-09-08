"""Live, single-page app for exploring and *evaluating* legal cases.

The page is a workbench with four views of the same case, chosen from a tab
bar, plus a panorama over the whole collection:

* **Panorama** (`aspic.overview`) -- every case at once: how many came from a
  dossier, how often the framework lands where the court landed, what is
  still waiting to be formalized.
* **Análise** (`aspic.didactic`) -- the plain-Portuguese walkthrough: what was
  concluded, which arguments were built, who contests what, the vocabulary of
  the case, and the causal comparison. The formal ASPIC+ notation (graph,
  NESS table, English causal table) stays behind a collapsed "ver
  representação técnica" toggle.
* **Dossiê** (`aspic.dossier_view`) -- the annotator's own reconstruction of
  the judgment, field by field, next to the passages that support it. Falls
  back to the run's normalized brief when the raw dossier is not on disk.
* **Formalização** (`aspic.formalization_view`) -- the ficha de formalização:
  every atom and every rule beside the passage of the judgment behind it,
  plus the model, prompts and hashes that produced them.
* **Conferência** (`aspic.evaluation`) -- solver versus court, how much of the
  dossier the formalization actually used, what is untraceable, and the
  deterministic checks.

Case rendering is shared with the static bundle
(`scripts/generate_graphs.py`) via `aspic.report`/`aspic.didactic` -- this
module only adds the HTTP layer around it. The static bundle keeps rendering
the English/technical view unchanged (`aspic.report.render_case`), since it
is the source for the paper's figures.

Run with:
    uv run python scripts/run_app.py
then open http://127.0.0.1:8000/

(`uv run uvicorn aspic.api:app --reload` also works once the project is
installed such that `aspic` is importable outside this repo's `src`-relative
scripts/tests -- see `scripts/run_app.py` for why that isn't reliable with
every uv/Python combination.)
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from .catalog import (
    case_by_id, dossier_by_id, formalization_by_id, full_listing, brief_by_id,
    validation_by_id,
)
from .didactic import render_case_didactic
from .dossier_view import render_dossier
from .evaluation import coverage_report, render_evaluation
from .explain import case_glossary
from .formalization_view import render_formalization_fiche
from .overview import render_overview
from .perspective_view import render_perspectives
from .preference_view import render_preferences
from .report import GRAPH_INTERACTIVITY_JS, PAGE_CSS

app = FastAPI(title="Explorador de Causalidade Jurídica (ASPIC+)")


def _record_or_404(case_id: str):
    record = formalization_by_id(case_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"O caso {case_id!r} não veio de um dossiê formalizado.",
        )
    return record


@app.get("/api/cases")
def list_cases() -> JSONResponse:
    """The sidebar's contents: every case's id, title, provenance and which
    of the four views it has (`has_case`, `has_record`, `has_dossier`,
    `has_brief`)."""
    return JSONResponse(full_listing())


@app.get("/api/overview", response_class=HTMLResponse)
def get_overview() -> HTMLResponse:
    """The panorama fragment: totals across the whole collection."""
    return HTMLResponse(render_overview())


@app.get("/api/cases/{case_id}", response_class=HTMLResponse)
def get_case(case_id: str) -> HTMLResponse:
    """The didactic `<section>` fragment for one case -- plain-language
    conclusion, argument cards, disputes, glossary, causal comparison, the
    legal-relevance layer when the case has one, and the technical toggle."""
    try:
        case = case_by_id(case_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such case: {case_id!r}")
    return HTMLResponse(render_case_didactic(case))


@app.get("/api/cases/{case_id}/glossary")
def get_glossary(case_id: str) -> JSONResponse:
    """`{símbolo: leitura em português}` for every token of both frameworks.

    The page uses it to turn each formal symbol on screen into something a
    lawyer can hover and read -- the symbols are unavoidable in the graph and
    in the technical notes, but nobody should have to memorise them.
    """
    try:
        case = case_by_id(case_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such case: {case_id!r}")
    return JSONResponse(case_glossary(case))


@app.get("/api/cases/{case_id}/dossier", response_class=HTMLResponse)
def get_dossier(case_id: str) -> HTMLResponse:
    """The annotated dossier behind a case -- or, when the raw file is not on
    disk, the normalized brief the model was given. 404 only when neither
    exists, which is the case for the hand-modelled paper examples."""
    if dossier_by_id(case_id) is None and brief_by_id(case_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Não há dossiê nem brief para o caso {case_id!r}.",
        )
    return HTMLResponse(render_dossier(case_id, formalization_by_id(case_id)))


@app.get("/api/cases/{case_id}/formalization", response_class=HTMLResponse)
def get_formalization(case_id: str) -> HTMLResponse:
    """The formalization fiche: atoms and rules next to the passages that
    support them, plus solver-vs-court. 404 for the paper cases, which were
    hand-modelled and have no formalization record."""
    record = _record_or_404(case_id)
    return HTMLResponse(render_formalization_fiche(record, validation_by_id(case_id)))


@app.get("/api/cases/{case_id}/perspectives", response_class=HTMLResponse)
def get_perspectives(case_id: str) -> HTMLResponse:
    """The adjudication view: the map of who moves what, the argumentation
    phase and the decision phase. 404 for the paper cases, which carry no
    perspective metadata."""
    record = _record_or_404(case_id)
    return HTMLResponse(render_perspectives(record, title=record.case.title))


@app.get("/api/cases/{case_id}/preferences", response_class=HTMLResponse)
def get_preferences(case_id: str) -> HTMLResponse:
    """The weighing: the tuple of dimensions, which rule invokes which, the
    conflicts the ordering decided, the same case without it, and the weight
    at which it would turn. 404 for the paper cases, which carry no record."""
    record = _record_or_404(case_id)
    return HTMLResponse(render_preferences(record))


@app.get("/api/cases/{case_id}/evaluation", response_class=HTMLResponse)
def get_evaluation(case_id: str) -> HTMLResponse:
    """The conference fragment: agreement with the court, dossier coverage,
    traceability, deterministic checks and the pipeline runs."""
    record = _record_or_404(case_id)
    return HTMLResponse(render_evaluation(record, validation_by_id(case_id), case_id))


@app.get("/api/cases/{case_id}/coverage")
def get_coverage(case_id: str) -> JSONResponse:
    """The conference's numbers as JSON, for auditing outside the browser.

    The resolved `Passage` objects are dropped: they are display detail, and
    the passages themselves are already served by the dossier view.
    """
    record = _record_or_404(case_id)
    report = coverage_report(record, case_id)
    report["passages"] = {k: v for k, v in report["passages"].items() if k != "objects"}
    return JSONResponse(report)


@app.get("/api/cases/{case_id}/raw")
def get_raw(case_id: str) -> JSONResponse:
    """The formalization record itself (`case.json`) plus its validation
    report -- the machine-readable form of the fiche, for auditing."""
    record = _record_or_404(case_id)
    return JSONResponse({
        "case": record.model_dump(),
        "validation": validation_by_id(case_id),
    })


# ----------------------------------------------------------------------
# The page shell
# ----------------------------------------------------------------------
#: Kept out of the f-string below so the JS can use braces freely, and raw so
#: that JavaScript's own escapes (`\n` in a tooltip, `\/` in a regex) survive
#: Python's string parsing on the way to the browser instead of being consumed
#: on import.
APP_JS = r"""
var PANORAMA = '__panorama__';

var TABS = [
  {key: 'analise', label: 'Análise',
   url: function (id) { return '/api/cases/' + encodeURIComponent(id); },
   when: function (c) { return c.has_case; },
   hint: 'O que a análise concluiu, e por quê.'},
  {key: 'dossie', label: 'Dossiê',
   url: function (id) { return '/api/cases/' + encodeURIComponent(id) + '/dossier'; },
   when: function (c) { return c.has_dossier || c.has_brief; },
   hint: 'A leitura do acórdão feita pelo anotador.'},
  {key: 'perspectivas', label: 'Perspectivas',
   url: function (id) { return '/api/cases/' + encodeURIComponent(id) + '/perspectives'; },
   when: function (c) { return c.has_record; },
   hint: 'Quem sustenta o quê, e onde o caso virou.'},
  {key: 'pesos', label: 'Pesos',
   url: function (id) { return '/api/cases/' + encodeURIComponent(id) + '/preferences'; },
   when: function (c) { return c.has_preferences; },
   hint: 'Que razões pesaram, e o que mudaria se pesassem outra coisa.'},
  {key: 'formalizacao', label: 'Formalização',
   url: function (id) { return '/api/cases/' + encodeURIComponent(id) + '/formalization'; },
   when: function (c) { return c.has_record; },
   hint: 'De qual trecho saiu cada literal e cada regra.'},
  {key: 'conferencia', label: 'Conferência',
   url: function (id) { return '/api/cases/' + encodeURIComponent(id) + '/evaluation'; },
   when: function (c) { return c.has_record; },
   hint: 'Quanto essa tradução merece confiança.'}
];

var GROUPS = [
  {label: 'Casos formalizados de dossiê', test: function (c) { return c.origin === 'dossie'; }},
  {label: 'Dossiês não formalizados', test: function (c) { return c.origin === 'dossie_bruto'; }},
  {label: 'Casos de referência do artigo', test: function (c) { return c.origin === 'paper'; }}
];

var cases = [];
var byId = {};
var cache = {};
var current = {id: PANORAMA, tab: null};

function el(tag, attrs, text) {
  var node = document.createElement(tag);
  Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, attrs[k]); });
  if (text !== undefined) node.textContent = text;
  return node;
}

function tabsFor(id) {
  if (id === PANORAMA) return [];
  var entry = byId[id];
  return entry ? TABS.filter(function (t) { return t.when(entry); }) : [];
}

function buildSidebar(filter) {
  var nav = document.getElementById('case-nav');
  nav.innerHTML = '';
  var needle = (filter || '').trim().toLowerCase();

  var panoramaList = el('ul', {'class': 'case-list'});
  var item = el('li');
  var button = el('button', {type: 'button', 'data-case': PANORAMA}, 'Panorama do acervo');
  button.appendChild(el('span', {'class': 'case-sub'}, 'todos os casos de uma vez'));
  item.appendChild(button);
  panoramaList.appendChild(item);
  nav.appendChild(panoramaList);

  GROUPS.forEach(function (group) {
    var matching = cases.filter(function (c) {
      if (!group.test(c)) return false;
      if (!needle) return true;
      return (c.title + ' ' + c.id).toLowerCase().indexOf(needle) >= 0;
    });
    if (!matching.length) return;
    nav.appendChild(el('div', {'class': 'group-label'}, group.label));
    var list = el('ul', {'class': 'case-list'});
    matching.forEach(function (c) {
      var li = el('li');
      var b = el('button', {type: 'button', 'data-case': c.id}, c.title);
      var views = tabsFor(c.id).map(function (t) { return t.label; }).join(' · ');
      b.appendChild(el('span', {'class': 'case-sub'}, views || 'sem visualização'));
      li.appendChild(b);
      list.appendChild(li);
    });
    nav.appendChild(list);
  });
  markCurrent();
}

function markCurrent() {
  document.querySelectorAll('#case-nav button').forEach(function (b) {
    b.setAttribute('aria-current', b.dataset.case === current.id ? 'true' : 'false');
  });
}

function buildTabs() {
  var bar = document.getElementById('tabs');
  bar.innerHTML = '';
  var available = tabsFor(current.id);
  if (!available.length) return;
  available.forEach(function (tab) {
    var b = el('button', {type: 'button', role: 'tab', 'data-tab': tab.key,
                          title: tab.hint}, tab.label);
    b.setAttribute('aria-selected', tab.key === current.tab ? 'true' : 'false');
    b.addEventListener('click', function () { go(current.id, tab.key); });
    bar.appendChild(b);
  });
}

function load() {
  var panel = document.getElementById('case-container');
  var url = current.id === PANORAMA ? '/api/overview'
    : (tabsFor(current.id).filter(function (t) { return t.key === current.tab; })[0] || {}).url;
  if (!url) {
    panel.innerHTML = '<p class="notice">Este caso não tem essa visualização.</p>';
    return;
  }
  var resolved = typeof url === 'function' ? url(current.id) : url;
  var key = current.id + '::' + current.tab;
  if (cache[key]) {
    panel.innerHTML = cache[key];
    afterRender(panel);
    return;
  }
  panel.innerHTML = '<p class="muted">Carregando&hellip;</p>';
  fetch(resolved).then(function (resp) {
    if (!resp.ok) throw new Error(resp.status);
    return resp.text();
  }).then(function (text) {
    cache[key] = text;
    panel.innerHTML = text;
    afterRender(panel);
  }).catch(function (err) {
    panel.innerHTML = '<p class="notice">Não foi possível carregar esta visualização ('
      + err.message + ').</p>';
  });
}

// ------------------------------------------------------------------
// Hover glossary: every formal symbol on screen explains itself.
// ------------------------------------------------------------------
var glossaries = {};

// A token as the two frameworks write them: an atom code (`CrimeLatroc`), a
// rule id (`r4`, `cf2lrc_FugaPreso`), an LRC literal (`CaFa_X_Y`), each
// optionally negated. Anything not in the case's glossary is left alone, so
// ordinary words in the same text node are never touched.
var TERM_RE = /¬?[A-Za-z][A-Za-z0-9_]*/g;

function fetchGlossary(id) {
  if (glossaries[id]) return Promise.resolve(glossaries[id]);
  return fetch('/api/cases/' + encodeURIComponent(id) + '/glossary')
    .then(function (r) { return r.ok ? r.json() : {}; })
    .then(function (terms) { glossaries[id] = terms; return terms; })
    .catch(function () { return {}; });
}

function annotateTerms(root, terms) {
  // Only where symbols actually appear: inline code, the fiche's monospace
  // cells, and the technical note under each argument card. The glossary
  // table is skipped -- its own row already says what the symbol means.
  var hosts = root.querySelectorAll('code, td.mono, .tech-note');
  hosts.forEach(function (host) {
    if (host.closest('table.glossary') || host.dataset.glossed) return;
    host.dataset.glossed = '1';
    var walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);
    var texts = [];
    while (walker.nextNode()) texts.push(walker.currentNode);
    texts.forEach(function (node) {
      var text = node.nodeValue;
      if (!TERM_RE.test(text)) { TERM_RE.lastIndex = 0; return; }
      TERM_RE.lastIndex = 0;
      var frag = document.createDocumentFragment();
      var last = 0, match, found = false;
      while ((match = TERM_RE.exec(text)) !== null) {
        var gloss = terms[match[0]];
        if (!gloss) continue;
        found = true;
        if (match.index > last) {
          frag.appendChild(document.createTextNode(text.slice(last, match.index)));
        }
        var span = document.createElement('span');
        span.className = 'term';
        span.dataset.gloss = gloss;
        span.setAttribute('tabindex', '0');
        span.textContent = match[0];
        frag.appendChild(span);
        last = match.index + match[0].length;
      }
      if (!found) return;
      if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
      node.parentNode.replaceChild(frag, node);
    });
  });
}

function annotateGraphs(root, terms) {
  // Graphviz writes the node's technical label into `xlink:title`, which the
  // browser shows natively on hover. Append the reading of every symbol in
  // that label so the graph is legible without the glossary open.
  root.querySelectorAll('.graph-wrap a[*|title]').forEach(function (anchor) {
    if (anchor.dataset.glossed) return;
    anchor.dataset.glossed = '1';
    var title = anchor.getAttributeNS('http://www.w3.org/1999/xlink', 'title') || '';
    var seen = {}, lines = [];
    (title.match(TERM_RE) || []).forEach(function (token) {
      if (seen[token] || !terms[token]) return;
      seen[token] = true;
      lines.push(token + ' — ' + terms[token]);
    });
    if (!lines.length) return;
    anchor.setAttributeNS('http://www.w3.org/1999/xlink', 'title',
                          title + '\n\n' + lines.join('\n'));
  });
}

function tipElement() {
  var tip = document.getElementById('term-tip');
  if (!tip) {
    tip = document.createElement('div');
    tip.id = 'term-tip';
    tip.setAttribute('role', 'tooltip');
    document.body.appendChild(tip);
  }
  return tip;
}

function showTip(target) {
  var tip = tipElement();
  tip.textContent = target.dataset.gloss;
  tip.classList.add('visible');
  var box = target.getBoundingClientRect();
  var width = Math.min(tip.offsetWidth, window.innerWidth - 16);
  var left = Math.min(Math.max(8, box.left), window.innerWidth - width - 8);
  var above = box.top > tip.offsetHeight + 12;
  tip.style.left = left + 'px';
  tip.style.top = (above ? box.top - tip.offsetHeight - 8 : box.bottom + 8)
    + window.scrollY + 'px';
}

function hideTip() {
  var tip = document.getElementById('term-tip');
  if (tip) tip.classList.remove('visible');
}

function bindTips(root) {
  root.addEventListener('mouseover', function (evt) {
    var term = evt.target.closest('.term');
    if (term) showTip(term);
  });
  root.addEventListener('mouseout', function (evt) {
    if (evt.target.closest('.term')) hideTip();
  });
  root.addEventListener('focusin', function (evt) {
    var term = evt.target.closest('.term');
    if (term) showTip(term);
  });
  root.addEventListener('focusout', hideTip);
  window.addEventListener('scroll', hideTip, {passive: true});
  document.addEventListener('keydown', function (evt) {
    if (evt.key === 'Escape') hideTip();
  });
}

function afterRender(panel) {
  bindGraphInteractivity(panel);
  hideTip();
  if (current.id !== PANORAMA) {
    fetchGlossary(current.id).then(function (terms) {
      annotateTerms(panel, terms);
      annotateGraphs(panel, terms);
    });
  }
  // Several tables (the fiche's solver-vs-court one above all) are wider
  // than the column. Each gets its own scroller so the page itself never
  // scrolls sideways.
  panel.querySelectorAll('table').forEach(function (table) {
    if (table.parentElement && table.parentElement.classList.contains('table-wrap')) return;
    var wrap = document.createElement('div');
    wrap.className = 'table-wrap';
    table.parentNode.insertBefore(wrap, table);
    wrap.appendChild(table);
  });
  panel.querySelectorAll('button.case-link').forEach(function (b) {
    b.addEventListener('click', function () { go(b.dataset.case, null); });
  });
  window.scrollTo({top: 0, behavior: 'smooth'});
}

function go(id, tab) {
  var available = tabsFor(id);
  var chosen = tab;
  if (id !== PANORAMA) {
    var valid = available.some(function (t) { return t.key === chosen; });
    if (!valid) chosen = available.length ? available[0].key : null;
  } else {
    chosen = null;
  }
  current = {id: id, tab: chosen};
  location.hash = '#/' + encodeURIComponent(id) + (chosen ? '/' + chosen : '');
  markCurrent();
  buildTabs();
  load();
}

function fromHash() {
  var parts = (location.hash || '').replace(/^#\//, '').split('/');
  var id = parts[0] ? decodeURIComponent(parts[0]) : PANORAMA;
  if (id !== PANORAMA && !byId[id]) id = PANORAMA;
  return {id: id, tab: parts[1] || null};
}

(function init() {
  fetch('/api/cases').then(function (r) { return r.json(); }).then(function (payload) {
    cases = payload;
    byId = {};
    cases.forEach(function (c) { byId[c.id] = c; });
    buildSidebar('');

    bindTips(document.getElementById('case-container'));
    document.getElementById('case-nav').addEventListener('click', function (evt) {
      var button = evt.target.closest('button[data-case]');
      if (button) go(button.dataset.case, null);
    });
    document.getElementById('case-filter').addEventListener('input', function (evt) {
      buildSidebar(evt.target.value);
    });
    window.addEventListener('hashchange', function () {
      var target = fromHash();
      if (target.id !== current.id || target.tab !== current.tab) go(target.id, target.tab);
    });

    var start = fromHash();
    go(start.id, start.tab);
  });
})();
"""


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Explorador de Causalidade Jurídica (ASPIC+)</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{PAGE_CSS}</style>
</head>
<body>
<h1>Explorador de Causalidade Jurídica</h1>
<p class="lead">Uma bancada para ler e conferir, em linguagem jurídica, como
cada caso foi analisado — do dossiê anotado ao veredito do solver.</p>
<details class="how-to-read">
  <summary>Como ler esta página</summary>
  <ul>
    <li><strong>Panorama</strong> — o acervo inteiro de uma vez: quantos casos
    existem, quanto cada um coincide com a decisão da corte, e o que ainda
    não foi formalizado.</li>
    <li><strong>Análise</strong> — o que se concluiu e por quê: os argumentos
    construídos, quem contesta o quê, e a comparação causal.</li>
    <li><strong>Dossiê</strong> — a leitura do acórdão feita pelo anotador,
    campo a campo, ao lado dos trechos que a sustentam.</li>
    <li><strong>Perspectivas</strong> — o julgamento como disputa: as regras de
    cada parte e de cada voto, e o movimento exato em que a pretensão deixa de
    se sustentar.</li>
    <li><strong>Pesos</strong> — quando o caso se resolve pesando razões e
    não por undercut: os eixos que o julgamento pondera, o que cada regra
    invoca, e a que altura o resultado viraria.</li>
    <li><strong>Formalização</strong> — a ficha de formalização: de qual
    trecho do acórdão saiu cada literal e cada regra.</li>
    <li><strong>Conferência</strong> — o quanto essa tradução merece
    confiança: solver × corte, cobertura do dossiê e checagens automáticas.</li>
  </ul>
  <p>A notação técnica (ASPIC+, em inglês) continua disponível dentro da
  Análise, em "Ver representação técnica". Para a versão estática e imprimível
  de todos os casos, veja <code>docs/graphs/index.html</code>
  (<code>uv run python scripts/generate_graphs.py</code>).</p>
</details>

<div class="app">
  <aside class="sidebar">
    <label class="group-label" for="case-filter">Buscar caso</label>
    <input type="search" id="case-filter" placeholder="filtrar por título…"
           autocomplete="off">
    <nav id="case-nav" aria-label="Casos"></nav>
  </aside>
  <main class="main">
    <div class="tabs" id="tabs" role="tablist"></div>
    <div class="panel" id="case-container">Carregando&hellip;</div>
  </main>
</div>

<script>{GRAPH_INTERACTIVITY_JS}{APP_JS}</script>
</body>
</html>
""")
