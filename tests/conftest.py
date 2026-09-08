"""Fixtures shared by the formalization tests.

`sample_stage_outputs` reproduces the childhood-leukaemia case of ICAIL 2025
(and its ICAIL 2026 legal-relevance reading) in the shape the four LLM stages
produce. Using a case whose expected verdicts are already asserted
independently in `test_legal_cases.py` and
`test_legally_relevant_causes_2026.py` means these tests check the *pipeline*
without also having to argue about whether the modelling is right.

The `FakeTransport` returns those outputs stage by stage, so the whole
pipeline -- prompts, checks, bridge, assembly, validation, artifacts -- runs
end to end with no API key and no network.
"""
import json

import pytest

from formalize.gemini import RawResponse, Transport


@pytest.fixture
def sample_dossier(tmp_path):
    """A small but structurally complete dossier, with linked passages.

    Written under an annotator directory (`<tmp>/anotador-teste/`) because
    that is the layout `aspic.catalog.dossier_paths` scans -- so a test that
    points `ASPIC_DOSSIER_ROOT` at `tmp_path` finds this dossier exactly as
    the app finds the real ones under `data/<annotator>/`.
    """
    payload = {
        "case_id": "case-fixture",
        "user_id": "anotador-teste",
        "case": {"id": "case-fixture", "title": "Caso Fixture",
                 "session_id": "testes", "phase": "evaluation"},
        "annotations": [], "assertions": [], "connections": [], "timeline": [],
        "perspectives": [], "clarifications": [], "canonical_concepts": [],
        "canonical_connections": [], "facts": [],
        "divergences": [{
            "id": "divg_fixture01",
            "divergence_point": "Recusa de consentimento",
            "perspective_1": "A recusa dos pais causou a morte",
            "perspective_2": "A doença causou a morte de qualquer modo",
            "support_1": "Laudo médico", "support_2": "Perícia",
            "reason": "Nexo causal",
            "effect_on_conclusion": "Muda o resultado",
            "who_sustains": None, "motive": None, "sides": None,
        }],
        "causal_units": [{
            "id": "unit_fixture01",
            "candidate_cause": "Recusa de consentimento para o tratamento",
            "outcome": "Morte da criança",
            "judgment_status": "Acolhida", "court_treatment": "Acolhida",
            "perspective_origin": "Acusação", "causal_relation": None,
        }],
        "perspective_reconstructions": [{
            "id": "prec_fixture01", "perspective_type": "recorrente",
            "person_or_body": None, "version": 1, "status": "draft",
            "fields_json": {
                "posicao_defendida": "Os pais recusaram o tratamento e a criança morreu.",
                "fatos_relevantes": "1. Leucemia diagnosticada\n2. Recusa de consentimento",
                "causas_candidatas": "1. Recusa de consentimento",
                "causas_juridicamente_relevantes": "1. NÃO CONSENTIR COM O TRATAMENTO",
                "fundamento_normativo": "Dever dos pais de zelar pela saúde do filho.",
            },
        }],
        "synthesis": {
            "id": "synth_fixture01",
            "central_question": "A recusa de consentimento causou a morte da criança?",
            "common_premises": "1. A criança tinha leucemia",
            "disputed_premises": "A recusa de consentimento",
            "winning_conclusion": "A recusa é causa da morte.",
            "ambiguities": None, "undecided_questions": None,
        },
        "source_passages": [
            {"id": "src_fixture01", "case_id": "case-fixture", "document_id": "doc",
             "pdf_page": 2, "text": "A criança foi diagnosticada com leucemia.",
             "bounding_boxes": [], "section": None, "vote_or_author": None},
            {"id": "src_fixture02", "case_id": "case-fixture", "document_id": "doc",
             "pdf_page": 5, "text": "Os pais recusaram o consentimento para a quimioterapia.",
             "bounding_boxes": [], "section": None, "vote_or_author": None},
        ],
        "source_links": [
            {"id": "fsl_01", "source_passage_id": "src_fixture02",
             "entity_type": "perspective_reconstruction", "entity_id": "prec_fixture01",
             "field_key": "posicao_defendida"},
        ],
    }
    directory = tmp_path / "anotador-teste"
    directory.mkdir(exist_ok=True)
    path = directory / "case-fixture-dossie.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def sample_stage_outputs():
    """Canned stage payloads: the leukaemia case, in the pipeline's own shape."""
    atoms = {
        "case_title": "Caso Fixture — recusa de tratamento",
        "narrative_pt": "A criança tinha leucemia e os pais recusaram o tratamento; ela morreu.",
        "central_question": "A recusa de consentimento causou a morte da criança?",
        "outcome_code": "Morte",
        "open_questions": ["Qual era o prognóstico com tratamento?"],
        "atoms": [
            {"code": "Leuc", "label_pt": "a criança tinha leucemia", "kind": "fato",
             "status": "incontroverso", "perspectives": ["recorrente"],
             "evidence": ["src_fixture01"], "dossier_refs": ["synth_fixture01"],
             "established": True},
            {"code": "Consent", "label_pt": "os pais consentiram com o tratamento",
             "kind": "fato", "status": "controvertido", "perspectives": ["recorrente"],
             "evidence": ["src_fixture02"], "dossier_refs": ["divg_fixture01"],
             "established": True},
            {"code": "Quimio", "label_pt": "a quimioterapia foi aplicada",
             "kind": "intermediario", "status": "controvertido", "perspectives": [],
             "evidence": [], "dossier_refs": [], "established": False},
            {"code": "Morte", "label_pt": "a criança morreu", "kind": "resultado",
             "status": "incontroverso", "perspectives": ["recorrente"],
             "evidence": [], "dossier_refs": ["unit_fixture01"], "established": False},
        ],
    }
    rules = {
        "premises": ["Leuc", "¬Consent"],
        "axioms": [],
        "strict_rules": [],
        "defeasible_rules": [
            {"rule": "r0: Leuc => Morte", "kind": "causal",
             "gloss_pt": "A leucemia, sem tratamento, leva presumidamente à morte.",
             "perspective": "comum", "evidence": ["src_fixture01"], "dossier_refs": []},
            {"rule": "r1: Consent => Quimio", "kind": "causal",
             "gloss_pt": "Se os pais consentissem, a quimioterapia teria sido aplicada.",
             "perspective": "recorrente", "evidence": ["src_fixture02"], "dossier_refs": []},
            {"rule": "r2: Quimio => ¬r0", "kind": "undercut",
             "gloss_pt": "A quimioterapia afastaria a conclusão de que a leucemia levaria à morte.",
             "perspective": "recorrente", "evidence": [], "dossier_refs": []},
        ],
        "modelling_notes_pt": "A omissão é modelada pelo literal positivo Consent.",
    }
    queries = {
        "queries": [
            {"phi": "Leuc", "psi": "Morte",
             "question_pt": "A leucemia foi causa da morte?",
             "court_verdict": "acolhida",
             "court_rationale_pt": "A doença é reconhecida como causa da morte.",
             "evidence": ["src_fixture01"]},
            {"phi": "¬Consent", "psi": "Morte",
             "question_pt": "A recusa de consentimento foi causa da morte?",
             "court_verdict": "acolhida",
             "court_rationale_pt": "A recusa impediu o tratamento que evitaria a morte.",
             "evidence": ["src_fixture02"]},
        ]
    }
    lrc = {
        "doctrinal_premises": [
            {"literal": "Om_notConsent",
             "label_pt": "a recusa de consentimento é uma omissão",
             "evidence": ["src_fixture02"]},
            {"literal": "Obl_Consent",
             "label_pt": "os pais tinham o dever jurídico de consentir com o tratamento",
             "evidence": []},
        ],
        "scheme_rules": [
            {"rule": "cf2lrc_Leuc: CaFa_Leuc_Morte => LeReCa_Leuc_Morte",
             "scheme": "cf2lrc",
             "gloss_pt": "Sendo causa de fato, a leucemia é presumidamente causa juridicamente relevante.",
             "evidence": []},
            {"rule": "cf2lrc_notConsent: CaFa_notConsent_Morte => LeReCa_notConsent_Morte",
             "scheme": "cf2lrc",
             "gloss_pt": "Sendo causa de fato, a recusa é presumidamente causa juridicamente relevante.",
             "evidence": []},
            {"rule": "unom_notConsent: Om_notConsent AND ¬Obl_Consent => ¬cf2lrc_notConsent",
             "scheme": "unom",
             "gloss_pt": "Uma omissão só deixa de ser juridicamente relevante se a conduta omitida não era obrigatória.",
             "evidence": []},
        ],
        "targets": ["LeReCa_Leuc_Morte", "LeReCa_notConsent_Morte"],
        "duty_basis_pt": "Dever dos pais de zelar pela saúde do filho.",
    }
    return {"atoms": atoms, "rules": rules, "queries": queries, "lrc": lrc}


class FakeTransport(Transport):
    """Returns canned stage payloads, dispatching on the requested schema."""

    def __init__(self, outputs):
        self.outputs = outputs
        self.prompts = []
        self.schema_names = []

    def generate(self, *, model, prompt, schema, config):
        self.prompts.append(prompt)
        self.schema_names.append(schema.__name__)
        key = {
            "AtomsStageOut": "atoms", "RulesStageOut": "rules",
            "QueriesStageOut": "queries", "LrcStageOut": "lrc",
        }.get(schema.__name__)
        if key is None:
            raise AssertionError(f"schema inesperado no teste: {schema.__name__}")
        return RawResponse(
            text=json.dumps(self.outputs[key], ensure_ascii=False),
            usage={"total_tokens": 100},
            model_version=model,
        )


@pytest.fixture
def fake_transport(sample_stage_outputs):
    return FakeTransport(sample_stage_outputs)
