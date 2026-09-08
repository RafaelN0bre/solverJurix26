"""The catalog and the HTTP layer, with a formalized case on disk.

The point of the catalog is that a case formalized from a dossier reaches the
same renderers as the five hand-modelled ICAIL cases. These tests check that
both kinds coexist in one dropdown, that the dossier case additionally renders
the legal-relevance layer and the formalization fiche, and that the fiche
really carries the traceability it claims to -- atom to passage, rule to
rationale, verdict to court.
"""
import pytest

from fastapi.testclient import TestClient

from aspic import catalog
from aspic.api import app
from aspic.examples import LEGAL_CASES
from formalize.gemini import GeminiClient
from formalize.pipeline import formalize_dossier


@pytest.fixture
def translated_dir(sample_dossier, fake_transport, tmp_path, monkeypatch):
    out_dir = tmp_path / "translated"
    client = GeminiClient(transport=fake_transport, use_cache=False)
    formalize_dossier(sample_dossier, client=client, out_dir=out_dir, run_id="run-teste")
    monkeypatch.setenv("ASPIC_TRANSLATED_DIR", str(out_dir))
    # Point the dossier scan at the fixture tree too, so these tests never
    # depend on which dossiers happen to be committed under `data/`.
    monkeypatch.setenv("ASPIC_DOSSIER_ROOT", str(tmp_path))
    return out_dir


@pytest.fixture
def client(translated_dir):
    return TestClient(app)


# ----------------------------------------------------------------------
# Catalog
# ----------------------------------------------------------------------
def test_paper_cases_are_listed_even_without_translated_cases(monkeypatch, tmp_path):
    monkeypatch.setenv("ASPIC_TRANSLATED_DIR", str(tmp_path / "vazio"))
    assert [c["id"] for c in catalog.listing()] == [c.id for c in LEGAL_CASES]


def test_translated_cases_join_the_paper_ones(translated_dir):
    entries = {entry["id"]: entry for entry in catalog.listing()}
    assert entries["asbestos"]["origin"] == "paper"
    assert entries["asbestos"]["has_lrc"] is False
    assert entries["case-fixture"]["origin"] == "dossie"
    assert entries["case-fixture"]["origin_label"] == "dossiê"
    assert entries["case-fixture"]["has_lrc"] is True


def test_case_by_id_reaches_both_kinds(translated_dir):
    assert catalog.case_by_id("leukaemia").origin == "paper"
    assert catalog.case_by_id("case-fixture").effect == "Morte"
    with pytest.raises(KeyError):
        catalog.case_by_id("inexistente")


def test_formalization_record_only_exists_for_dossier_cases(translated_dir):
    assert catalog.formalization_by_id("asbestos") is None
    record = catalog.formalization_by_id("case-fixture")
    assert record.case.annotator == "anotador-teste"
    assert catalog.validation_by_id("case-fixture")["summary"]["has_lrc"] is True


def test_a_corrupt_record_does_not_empty_the_catalog(translated_dir):
    (translated_dir / "quebrado").mkdir()
    (translated_dir / "quebrado" / "case.json").write_text("{isso não é json", encoding="utf-8")
    assert "case-fixture" in {entry["id"] for entry in catalog.listing()}


def test_catalog_rereads_from_disk(translated_dir):
    record = catalog.formalization_by_id("case-fixture")
    path = translated_dir / "case-fixture" / "case.json"
    path.write_text(
        record.model_dump_json(indent=2).replace("Caso Fixture", "Título Novo"),
        encoding="utf-8")
    assert catalog.case_by_id("case-fixture").title.startswith("Título Novo")


# ----------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------
def test_index_mentions_both_kinds_of_case(client):
    body = client.get("/").text
    assert body.startswith("<!doctype html>")
    assert "ficha de formalização" in body
    # the four per-case views the shell offers
    for label in ("Análise", "Dossiê", "Perspectivas", "Formalização",
                  "Conferência"):
        assert label in body


def test_list_endpoint(client):
    payload = client.get("/api/cases").json()
    assert {"id", "title", "origin", "origin_label", "has_lrc"} <= set(payload[0])
    assert any(entry["origin"] == "dossie" for entry in payload)


def test_paper_cases_still_render(client):
    for case in LEGAL_CASES:
        response = client.get(f"/api/cases/{case.id}")
        assert response.status_code == 200
        assert "Relevância jurídica" not in response.text


def test_dossier_case_renders_didactic_view_plus_lrc_layer(client):
    body = client.get("/api/cases/case-fixture").text
    assert "a criança tinha leucemia" in body
    assert "Relevância jurídica" in body
    assert "camada ICAIL 2026" in body
    assert "Dever jurídico de agir" in body
    assert "<svg" in body  # both graphs rendered


def test_unknown_case_is_404(client):
    assert client.get("/api/cases/inexistente").status_code == 404


def test_fiche_shows_the_evidence_behind_each_atom_and_rule(client):
    body = client.get("/api/cases/case-fixture/formalization").text
    assert "Ficha de formalização" in body
    # atom -> passage of the judgment
    assert "src_fixture02" in body
    assert "Os pais recusaram o consentimento para a quimioterapia." in body
    # rule -> plain-language rationale
    assert "r2: Quimio =&gt; ¬r0" in body
    assert "A quimioterapia afastaria a conclusão" in body
    # bridge premises flagged as solver output, not model output
    assert "CaFa_notConsent_Morte" in body
    assert "não foram escritas pelo modelo" in body


def test_fiche_confronts_solver_and_court(client):
    body = client.get("/api/cases/case-fixture/formalization").text
    assert "Solver × decisão da corte" in body
    assert "A recusa de consentimento foi causa da morte?" in body
    assert "coincide" in body


def test_fiche_records_provenance(client):
    """Which prompt file produced the case, whichever version is current --
    pinning `v1` here would just break every time a prompt is iterated."""
    import re

    body = client.get("/api/cases/case-fixture/formalization").text
    assert re.search(r"prompts/formalize/02_rules\.v\d+\.md", body)
    assert "run-teste" in body
    assert "gemini-2.5-pro" in body


def test_fiche_is_404_for_paper_cases(client):
    assert client.get("/api/cases/asbestos/formalization").status_code == 404
    assert client.get("/api/cases/asbestos/raw").status_code == 404


def test_raw_endpoint_returns_the_record_and_its_validation(client):
    payload = client.get("/api/cases/case-fixture/raw").json()
    assert payload["case"]["effect"] == "Morte"
    assert payload["case"]["lrc"]["bridged_premises"]
    assert payload["validation"]["summary"]["agreement"]["match"] == 2
