"""The deterministic half of the ingestion: dossier JSON -> case brief.

No LLM is involved, so these assertions are exact. What matters is that the
brief keeps everything an annotator filled in, drops the tool's boilerplate
and its dozens of empty columns, and -- the part the later stages depend on --
attaches each passage of the judgment to the field it was linked to.
"""
import json

from formalize.dossier import Dossier, field_label, load_dossier


def test_loads_identity_and_hash(sample_dossier):
    dossier = load_dossier(sample_dossier)
    assert dossier.case_id == "case-fixture"
    assert dossier.annotator == "anotador-teste"
    assert dossier.title == "Caso Fixture"
    assert dossier.session_id == "testes"
    assert len(dossier.sha256) == 64


def test_hash_tracks_the_file(sample_dossier, tmp_path):
    first = load_dossier(sample_dossier).sha256
    payload = json.loads(sample_dossier.read_text(encoding="utf-8"))
    payload["case"]["title"] = "Outro título"
    sample_dossier.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert load_dossier(sample_dossier).sha256 != first


def test_valid_ids_cover_every_citable_record(sample_dossier):
    ids = load_dossier(sample_dossier).valid_ids()
    assert ids == {
        "src_fixture01", "src_fixture02", "divg_fixture01",
        "unit_fixture01", "prec_fixture01", "synth_fixture01",
    }


def test_brief_keeps_content_and_drops_boilerplate(sample_dossier):
    brief = load_dossier(sample_dossier).brief()
    # Annotator content survives, with Portuguese field labels.
    assert "Questão central" in brief
    assert "A recusa de consentimento causou a morte da criança?" in brief
    assert "Fundamento normativo (dever jurídico de agir)" in brief
    # Bookkeeping columns and empty fields do not.
    assert "assignment_id" not in brief
    assert "bounding_boxes" not in brief
    assert "Motivo" not in brief  # `motive` was null


def test_brief_links_passages_to_the_field_they_support(sample_dossier):
    brief = load_dossier(sample_dossier).brief()
    position = brief.index("**Posição defendida**")
    marker = brief.index("`src_fixture02`", position)
    # The evidence marker sits on the very field `source_links` points at.
    assert marker - position < 120
    # And every passage is listed once at the end, citable by id.
    assert "## Passagens de origem (cite pelo id)" in brief
    assert "Os pais recusaram o consentimento para a quimioterapia." in brief


def test_brief_is_stable(sample_dossier):
    dossier = load_dossier(sample_dossier)
    assert dossier.brief() == load_dossier(sample_dossier).brief()


def test_empty_collections_produce_no_headings(sample_dossier):
    brief = load_dossier(sample_dossier).brief()
    for heading in ("## Anotações", "## Linha do tempo", "## Conceitos canônicos"):
        assert heading not in brief


def test_field_label_falls_back_readably():
    assert field_label("posicao_defendida") == "Posição defendida"
    assert field_label("campo_desconhecido") == "Campo desconhecido"


def test_dossier_without_optional_sections_still_renders():
    dossier = Dossier({"case_id": "vazio", "case": {"id": "vazio", "title": "Vazio"}})
    brief = dossier.brief()
    assert "# Dossiê — Vazio (`vazio`)" in brief
    assert dossier.valid_ids() == set()
