"""The evaluation-facing views: dossier, conference and panorama.

The didactic view and the fiche already had tests; these cover the three
pieces added so a case can be *judged*, not just read -- the annotator's raw
dossier (`aspic.dossier_view`), the conference that measures the translation
(`aspic.evaluation`), and the collection-wide panorama (`aspic.overview`) --
plus the two didactic fixes they depend on: no bare `¬rN` in prose, and one
card per reading rather than one per `Argument` object.
"""
import json
import shutil

import pytest

from fastapi.testclient import TestClient

from aspic import catalog, dossier_view, evaluation, overview
from aspic.api import app
from aspic.didactic import _argument_cards_html, _disputes_html, render_case_didactic
from aspic.graph_export import argument_status
from aspic.solver import ArgumentationFramework
from formalize.gemini import GeminiClient
from formalize.pipeline import formalize_dossier


@pytest.fixture
def translated_dir(sample_dossier, fake_transport, tmp_path, monkeypatch):
    out_dir = tmp_path / "translated"
    client = GeminiClient(transport=fake_transport, use_cache=False)
    formalize_dossier(sample_dossier, client=client, out_dir=out_dir, run_id="run-teste")
    monkeypatch.setenv("ASPIC_TRANSLATED_DIR", str(out_dir))
    monkeypatch.setenv("ASPIC_DOSSIER_ROOT", str(tmp_path))
    return out_dir


@pytest.fixture
def client(translated_dir):
    return TestClient(app)


# ----------------------------------------------------------------------
# Catalog: dossiers and runs
# ----------------------------------------------------------------------
def test_dossier_is_found_by_case_id(translated_dir, sample_dossier):
    assert catalog.dossier_path_by_id("case-fixture") == sample_dossier
    assert catalog.dossier_by_id("case-fixture").title == "Caso Fixture"
    assert catalog.dossier_by_id("asbestos") is None


def test_translated_index_json_is_not_mistaken_for_a_dossier(translated_dir, tmp_path,
                                                             monkeypatch):
    """`data/translated/index.json` sits at the exact depth the dossier glob
    walks; it must never enter the catalog as a case."""
    monkeypatch.setenv("ASPIC_DOSSIER_ROOT", str(tmp_path))
    assert set(catalog.dossier_paths()) == {"case-fixture"}


def test_runs_and_brief_are_readable(translated_dir):
    runs = catalog.run_summaries("case-fixture")
    assert [r["run_id"] for r in runs] == ["run-teste"]
    assert runs[0]["complete"] is True
    brief = catalog.brief_by_id("case-fixture")
    assert brief["run_id"] == "run-teste"
    assert "Passagens de origem" in brief["markdown"]


def test_dossier_only_cases_are_listed_apart(translated_dir, sample_dossier, tmp_path,
                                             monkeypatch):
    """A dossier nobody formalized still has to be reachable."""
    monkeypatch.setenv("ASPIC_TRANSLATED_DIR", str(tmp_path / "vazio"))
    entries = {e["id"]: e for e in catalog.full_listing()}
    assert entries["case-fixture"]["origin"] == "dossie_bruto"
    assert entries["case-fixture"]["has_case"] is False
    assert entries["case-fixture"]["has_dossier"] is True


# ----------------------------------------------------------------------
# Dossier view
# ----------------------------------------------------------------------
def test_dossier_view_shows_the_annotators_own_reading(translated_dir):
    body = dossier_view.render_dossier("case-fixture")
    assert "Dossiê anotado — Caso Fixture" in body
    # synthesis, perspective, divergence, causal unit
    assert "A recusa de consentimento causou a morte da criança?" in body
    assert "Recorrente" in body
    assert "Recusa de consentimento" in body
    assert "Morte da criança" in body
    # the passage catalog, and the field-level evidence link
    assert "Os pais recusaram o consentimento para a quimioterapia." in body
    assert "1 trecho do acórdão" in body


def test_unlinked_passages_are_flagged(translated_dir):
    """A marked passage tied to no field is a gap in the annotation, and the
    view says so rather than listing it silently."""
    body = dossier_view.render_dossier("case-fixture")
    assert "não vinculada a nenhum campo" in body


def test_dossier_view_falls_back_to_the_run_brief(translated_dir, sample_dossier):
    """With the source dossier gone, the run's normalized brief still tells
    the reader what the model was given."""
    sample_dossier.unlink()
    record = catalog.formalization_by_id("case-fixture")
    body = dossier_view.render_dossier("case-fixture", record)
    assert "brief da execução run-teste" in body
    assert "não está neste repositório" in body
    assert "A recusa de consentimento causou a morte da criança?" in body


def test_parse_brief_passages_recovers_id_page_and_text(translated_dir):
    brief = catalog.brief_by_id("case-fixture")["markdown"]
    passages = dossier_view.parse_brief_passages(brief)
    assert passages["src_fixture02"].page == 5
    assert passages["src_fixture02"].text.startswith("Os pais recusaram")


def test_passages_prefer_the_dossier_then_the_brief(translated_dir, sample_dossier):
    _, source = dossier_view.passages_for("case-fixture",
                                          catalog.formalization_by_id("case-fixture"))
    assert source == "dossiê de origem"
    sample_dossier.unlink()
    passages, source = dossier_view.passages_for("case-fixture",
                                                 catalog.formalization_by_id("case-fixture"))
    assert source == "brief da execução run-teste"
    assert set(passages) == {"src_fixture01", "src_fixture02"}


def test_brief_markdown_renders_without_mangling_ids():
    """The underscore-italic rule must not fire inside a code span, which is
    where every `src_*` id lives."""
    html_out = dossier_view.render_brief_html(
        "## Título\n\n- `src_a1_b2` (p. 1): “texto” _(evidência: `x_y`)_\n")
    assert "<code>src_a1_b2</code>" in html_out
    assert "<em>(evidência: <code>x_y</code>)</em>" in html_out


# ----------------------------------------------------------------------
# Conference
# ----------------------------------------------------------------------
def test_coverage_report_separates_passages_from_records(translated_dir):
    record = catalog.formalization_by_id("case-fixture")
    report = evaluation.coverage_report(record)
    assert report["passages"]["total"] == 2
    assert report["passages"]["cited"] == ["src_fixture01", "src_fixture02"]
    assert report["passages"]["uncited"] == []
    # `prec_*`/`divg_*` ids are dossier records, not dangling passage citations
    assert report["passages"]["unresolved"] == []
    assert report["records"]["unreferenced"] == ["prec_fixture01"]


def test_coverage_report_names_what_cannot_be_traced(translated_dir):
    record = catalog.formalization_by_id("case-fixture")
    untraced = evaluation.coverage_report(record)["untraced"]
    assert untraced["atoms"] == ["Quimio", "Morte"]
    assert "r2" in untraced["rules"]


def test_uncited_passages_are_reported(translated_dir, sample_dossier):
    """The number that matters when judging a formalization: what the
    annotator marked and the model ignored."""
    payload = json.loads(sample_dossier.read_text(encoding="utf-8"))
    payload["source_passages"].append(
        {"id": "src_fixture03", "case_id": "case-fixture", "document_id": "doc",
         "pdf_page": 9, "text": "Trecho que a formalização nunca citou.",
         "bounding_boxes": [], "section": None, "vote_or_author": None})
    sample_dossier.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    record = catalog.formalization_by_id("case-fixture")
    report = evaluation.coverage_report(record)
    assert report["passages"]["uncited"] == ["src_fixture03"]
    html_out = evaluation.render_evaluation(record, catalog.validation_by_id("case-fixture"))
    assert "Trecho que a formalização nunca citou." in html_out


def test_evaluation_html_scores_solver_against_court(translated_dir):
    record = catalog.formalization_by_id("case-fixture")
    html_out = evaluation.render_evaluation(record, catalog.validation_by_id("case-fixture"))
    assert "O framework chegou onde a corte chegou?" in html_out
    assert "2/2" in html_out  # both questions agree in the fixture
    assert "Execuções do pipeline" in html_out
    assert "run-teste" in html_out


# ----------------------------------------------------------------------
# Panorama
# ----------------------------------------------------------------------
def test_overview_rows_cover_paper_and_dossier_cases(translated_dir):
    rows = {row["id"]: row for row in overview.overview_rows()}
    assert rows["asbestos"]["atoms"] is None          # hand-modelled, no record
    assert rows["case-fixture"]["atoms"] == 4
    assert rows["case-fixture"]["agreement"]["match"] == 2
    assert rows["case-fixture"]["runs"] == 1


def test_panorama_flags_dossiers_still_waiting(translated_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("ASPIC_TRANSLATED_DIR", str(tmp_path / "vazio"))
    pending = overview.pending_dossiers()
    assert [entry["case_id"] for entry in pending] == ["case-fixture"]
    assert "Dossiês à espera de formalização" in overview.render_overview()


# ----------------------------------------------------------------------
# Didactic fixes the evaluation views depend on
# ----------------------------------------------------------------------
#: Two ways to reach X, one of them undercut: enough to exercise both the
#: disputes table and the merging of readings, which the fixture case cannot
#: (its `Quimio` branch is unreachable, so nothing ever attacks anything).
_TWO_PATHS = {
    "knowledge_base": {"premises": ["A", "B"], "axioms": []},
    "causal_model": {"strict_rules": [],
                     "defeasible_rules": ["r0: A => X", "r1: B => X", "r2: X => Y",
                                          "r3: A => ¬r0"]},
    "atom_glosses": {"A": "o fato A", "B": "o fato B", "X": "o elo X",
                     "Y": "o resultado Y",
                     "¬r0": "não se sustenta o raciocínio: “de A vem X”"},
    "rule_glosses": {"r0": "de A vem X", "r1": "de B vem X", "r2": "de X vem Y",
                     "r3": "o fato A afasta a regra r0"},
}


def _two_path_framework():
    af = ArgumentationFramework(_TWO_PATHS["knowledge_base"], _TWO_PATHS["causal_model"])
    extension, _ = af.compute_grounded_extension()
    return af, argument_status(af, extension), {id(d.attack) for d in af.defeats}


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz 'dot' not installed")
def test_rule_negations_read_as_portuguese_not_as_symbols(translated_dir):
    """`¬r0` is what an undercutting argument concludes; a lawyer must never
    see the symbol in the middle of a sentence."""
    case = catalog.case_by_id("case-fixture")
    assert case.atom_glosses["¬r0"].startswith("não se sustenta o raciocínio")
    assert "`¬r0`" not in render_case_didactic(case)

    af, status, defeats = _two_path_framework()
    cards = _argument_cards_html(af, status, defeats, _TWO_PATHS["atom_glosses"],
                                 _TWO_PATHS["rule_glosses"])
    assert "não se sustenta o raciocínio" in cards


def test_disputes_table_names_the_contesting_fact():
    af, _, _ = _two_path_framework()
    table = _disputes_html(af, _TWO_PATHS["atom_glosses"], _TWO_PATHS["rule_glosses"])
    assert "De A vem X" in table                      # what is contested
    assert "O fato A" in table                        # who contests it
    assert "o fato A afasta a regra r0" in table      # and on what grounds
    assert "ataque ao raciocínio" in table


def test_one_card_per_reading_not_per_argument_object():
    """Two derivations of the same conclusion read identically; merging them
    keeps the badge honest (the conclusion stands if any path stands)."""
    af, status, defeats = _two_path_framework()
    cards = _argument_cards_html(af, status, defeats, _TWO_PATHS["atom_glosses"],
                                 _TWO_PATHS["rule_glosses"])
    assert cards.count("conclui-se que o resultado Y") == 1
    assert "2 caminhos de raciocínio levam a esta mesma conclusão" in cards


# ----------------------------------------------------------------------
# HTTP -- none of these views renders a graph, so Graphviz is not needed
# ----------------------------------------------------------------------
def test_dossier_endpoint_serves_the_annotation(client):
    resp = client.get("/api/cases/case-fixture/dossier")
    assert resp.status_code == 200
    assert "Dossiê anotado" in resp.text


def test_dossier_endpoint_is_404_without_dossier_or_brief(client):
    assert client.get("/api/cases/asbestos/dossier").status_code == 404


def test_evaluation_endpoint_and_its_json_twin(client):
    assert "Conferência" in client.get("/api/cases/case-fixture/evaluation").text
    payload = client.get("/api/cases/case-fixture/coverage").json()
    assert payload["passages"]["total"] == 2
    assert "objects" not in payload["passages"]   # display detail, not data
    assert client.get("/api/cases/asbestos/evaluation").status_code == 404
    assert client.get("/api/cases/asbestos/coverage").status_code == 404


def test_glossary_endpoint_covers_both_frameworks(client):
    """What the hover tooltips read from: every symbol a reader can meet on
    screen, from the cause-in-fact layer and the legal-relevance one."""
    terms = client.get("/api/cases/case-fixture/glossary").json()
    assert terms["Leuc"] == "a criança tinha leucemia"
    assert terms["¬Consent"].startswith("não é o caso de que")
    assert terms["r0"].startswith("A leucemia")
    assert terms["¬r0"].startswith("não se sustenta o raciocínio")
    # the LRC layer's own vocabulary
    assert "CaFa_Leuc_Morte" in terms
    assert "cf2lrc_Leuc" in terms
    assert client.get("/api/cases/inexistente/glossary").status_code == 404


def test_paper_cases_have_a_glossary_too(client):
    terms = client.get("/api/cases/double_shooting/glossary").json()
    assert terms["BuSh"] and terms["r0"]


def test_page_script_keeps_its_javascript_escapes(client):
    """`APP_JS` is a raw string, so JavaScript's own escapes reach the
    browser intact. Letting Python consume them on import -- or
    double-escaping them to compensate -- is a syntax error that blanks the
    whole page, and it only surfaces in a console no test suite reads.
    """
    body = client.get("/").text
    assert r"replace(/^#\//, '')" in body       # not `\\/`, which breaks the regex
    assert r"title + '\n\n' + lines.join('\n')" in body
    assert "annotateTerms" in body and "term-tip" in body


def test_perspectives_endpoint(client):
    body = client.get("/api/cases/case-fixture/perspectives").text
    assert "Perspectivas e adjudicação" in body
    assert client.get("/api/cases/asbestos/perspectives").status_code == 404


def test_overview_endpoint_lists_the_whole_collection(client):
    body = client.get("/api/overview").text
    assert "Panorama" in body
    assert "Caso Fixture" in body
    assert "Fairchild v Glenhaven" in body


def test_listing_says_which_views_each_case_has(client):
    entries = {e["id"]: e for e in client.get("/api/cases").json()}
    assert entries["asbestos"]["has_record"] is False
    assert entries["case-fixture"]["has_record"] is True
    assert entries["case-fixture"]["has_dossier"] is True
