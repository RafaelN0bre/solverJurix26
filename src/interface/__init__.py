"""The rendering package: everything that turns computed structures into
graphs, HTML and text for humans. End of the pipeline -- it consumes
`aspic`, `cases`, `analysis` and `formalize`, and decides nothing.
"""

"""Everything that renders for humans: graphs, HTML views, plain-language
text, and the live web app.

No causal or argumentation logic is decided here -- these modules only
present structures computed by `aspic`, `cases`, `analysis` and `formalize`:

* building blocks -- `graph_export` (Graphviz DOT/SVG), `report` (shared
  case section + CSS/JS), `causal_report` (NESS vs but-for panel),
  `explain` (plain-Portuguese sentences);
* the tabs of the case workbench -- `didactic`, `formalization_view`,
  `dossier_view`, `evaluation`, `perspective_view`, `preference_view`,
  `architecture_view`, and the collection-wide `overview`;
* `api` -- the FastAPI app that serves the workbench
  (`scripts/run_app.py`); the static bundle is `scripts/generate_graphs.py`
  and `scripts/render_translated.py` over the same renderers.
"""
