"""Live, single-page app for exploring the ICAIL 2025 legal cases: pick a
case from a dropdown and see a plain-Portuguese, didactic walkthrough of the
framework's reasoning -- built for legal professionals, not just for people
with an argumentation-theory background. The formal ASPIC+ notation (graph,
NESS table, English causal-comparison table) stays available behind a
collapsed "ver representação técnica" toggle inside each case.

Case rendering is shared with the static bundle (`scripts/generate_graphs.py`)
via `aspic.report`/`aspic.didactic` -- this module only adds the HTTP layer
around it. The static bundle keeps rendering the English/technical view
unchanged (`aspic.report.render_case`), since it's the source for the
paper's figures; this app renders the didactic view
(`aspic.didactic.render_case_didactic`).

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

from .didactic import render_case_didactic
from .examples import LEGAL_CASES, case_by_id
from .report import GRAPH_INTERACTIVITY_JS, PAGE_CSS

app = FastAPI(title="Explorador de Causalidade Jurídica (ASPIC+)")


@app.get("/api/cases")
def list_cases() -> JSONResponse:
    """The dropdown's contents: every case's id and title, in catalog order."""
    return JSONResponse([{"id": case.id, "title": case.title} for case in LEGAL_CASES])


@app.get("/api/cases/{case_id}", response_class=HTMLResponse)
def get_case(case_id: str) -> HTMLResponse:
    """The didactic `<section>` fragment for one case -- plain-language
    conclusion, argument cards, causal comparison, technical toggle --
    ready to drop into `#case-container` via `innerHTML`."""
    try:
        case = case_by_id(case_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such case: {case_id!r}")
    return HTMLResponse(render_case_didactic(case))


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
<p>Selecione um caso para ver, em linguagem simples, como a análise chegou à
sua conclusão: quais fatos foram estabelecidos, quais argumentos foram
construídos a partir deles, quais argumentos foram contestados (e por quê),
e qual conclusão prevaleceu ao final — com base no arcabouço ASPIC+ e nos
casos da Seção 5 de Pisano, Prakken, Sartor &amp; Liepina (ICAIL 2025). A
notação técnica formal continua disponível dentro de cada caso, em
"Ver representação técnica". Para uma versão estática e imprimível de todos
os casos (em inglês, para o artigo), veja <code>docs/graphs/index.html</code>
(<code>uv run python scripts/generate_graphs.py</code>).</p>
<p><label for="case-select"><strong>Caso:</strong></label>
   <select id="case-select"></select></p>
<div id="case-container">Carregando&hellip;</div>
<script>{GRAPH_INTERACTIVITY_JS}
async function loadCase(id) {{
  const container = document.getElementById('case-container');
  container.innerHTML = 'Carregando&hellip;';
  const resp = await fetch('/api/cases/' + encodeURIComponent(id));
  if (!resp.ok) {{
    container.textContent = 'Falha ao carregar o caso ' + id + ' (' + resp.status + ')';
    return;
  }}
  container.innerHTML = await resp.text();
  bindGraphInteractivity(container);
}}

(async function init() {{
  const select = document.getElementById('case-select');
  const resp = await fetch('/api/cases');
  const cases = await resp.json();
  cases.forEach(function (c) {{
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.title;
    select.appendChild(opt);
  }});
  select.addEventListener('change', function () {{ loadCase(select.value); }});
  if (cases.length > 0) {{
    select.value = cases[0].id;
    loadCase(cases[0].id);
  }}
}})();
</script>
</body>
</html>
""")
