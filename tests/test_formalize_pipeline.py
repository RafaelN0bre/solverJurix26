"""The pipeline end to end, with a fake transport instead of Gemini.

Covers what only shows up when the stages are wired together: that each stage
receives the previous one's output verbatim, that the legal-relevance stage is
handed solver-computed facts rather than being asked to invent them, that the
record persisted to `data/translated/` is what the interface will read, and
that a run leaves behind enough provenance to reproduce it.
"""
import json

from formalize import build
from formalize.gemini import GeminiClient
from formalize.pipeline import formalize_dossier
from formalize.schema import FormalizedCase


def run(sample_dossier, fake_transport, tmp_path, **kwargs):
    client = GeminiClient(transport=fake_transport, use_cache=False,
                          model_override="modelo-de-teste")
    return formalize_dossier(sample_dossier, client=client,
                             out_dir=tmp_path / "translated", **kwargs)


def test_dry_run_writes_prompts_without_calling_the_model(sample_dossier, fake_transport, tmp_path):
    result = formalize_dossier(sample_dossier, out_dir=tmp_path / "translated", dry_run=True)
    assert result.dry_run and result.case is None
    assert (result.run_dir / "00_brief.md").is_file()
    rendered = sorted(p.name for p in (result.run_dir / "prompts").glob("*.txt"))
    assert rendered == ["01_atoms.txt", "02_rules.txt", "03_queries.txt", "04_lrc.txt"]
    assert "REGRA Nº 1" in (result.run_dir / "prompts" / "02_rules.txt").read_text(encoding="utf-8")
    assert fake_transport.prompts == []


def test_full_run_produces_a_valid_case(sample_dossier, fake_transport, tmp_path):
    result = run(sample_dossier, fake_transport, tmp_path)
    assert result.report.ok, result.report.render_errors()

    case = result.case
    assert case.case.id == "case-fixture"
    assert case.case.annotator == "anotador-teste"
    assert case.effect == "Morte"
    assert case.knowledge_base == {"premises": ["Leuc", "¬Consent"], "axioms": []}
    assert case.causal_model["defeasible_rules"] == [
        "r0: Leuc => Morte", "r1: Consent => Quimio", "r2: Quimio => ¬r0"]
    assert [m.id for m in case.rules_meta] == ["r0", "r1", "r2"]


def test_stages_run_in_order_and_see_the_previous_output(sample_dossier, fake_transport, tmp_path):
    run(sample_dossier, fake_transport, tmp_path)
    assert fake_transport.schema_names == [
        "AtomsStageOut", "RulesStageOut", "QueriesStageOut", "LrcStageOut"]

    rules_prompt, queries_prompt, lrc_prompt = fake_transport.prompts[1:]
    assert '"code": "Leuc"' in rules_prompt          # atoms handed over verbatim
    assert "r2: Quimio => ¬r0" in queries_prompt     # rules handed over verbatim
    assert "CaFa_notConsent_Morte" in lrc_prompt     # solver-derived, not model-invented


def test_solver_verdicts_are_written_back_into_the_record(sample_dossier, fake_transport, tmp_path):
    case = run(sample_dossier, fake_transport, tmp_path).case
    verdicts = {(q.phi, q.psi): q.solver for q in case.queries}
    # The omission is a NESS cause (Definition 4.3) even though it is not a
    # premise of any argument for the death -- the case the paper uses to show
    # that a purely deductive reading of NESS is too narrow.
    assert verdicts[("¬Consent", "Morte")].ness is True
    assert verdicts[("¬Consent", "Morte")].but_for is True
    assert verdicts[("Leuc", "Morte")].ness is True


def test_bridge_premises_are_recorded_and_come_from_the_solver(sample_dossier, fake_transport, tmp_path):
    case = run(sample_dossier, fake_transport, tmp_path).case
    assert "CaFa_notConsent_Morte" in case.lrc.bridged_premises
    assert "CaFa_Leuc_Morte" in case.lrc.bridged_premises
    # The model only supplied doctrinal premises.
    assert {p.literal for p in case.lrc.doctrinal_premises} == {"Om_notConsent", "Obl_Consent"}


def test_omission_stays_relevant_because_there_was_a_duty(sample_dossier, fake_transport, tmp_path):
    """ICAIL 2026 section 6: `unom` does not fire when `Obl_*` holds."""
    case = run(sample_dossier, fake_transport, tmp_path).case
    justified = {e["target"]: e["justified"] for e in case.lrc.relevance}
    assert justified == {"LeReCa_Leuc_Morte": True, "LeReCa_notConsent_Morte": True}
    assert all(q.legally_relevant for q in case.queries)


def test_comparison_confronts_solver_and_court(sample_dossier, fake_transport, tmp_path):
    report = run(sample_dossier, fake_transport, tmp_path).report
    assert {row["agreement"] for row in report.comparison} == {"match"}
    assert report.summary["agreement"] == {"match": 2, "mismatch": 0, "indefinido": 0}
    assert report.summary["agreement_rate"] == 1.0
    assert report.summary["has_lrc"] is True


def test_prompt_front_matter_picks_the_model_unless_overridden(
        sample_dossier, fake_transport, tmp_path):
    """Switching one stage to a cheaper model is a prompt edit; `--model`
    still forces a single model across every stage when asked."""
    client = GeminiClient(transport=fake_transport, use_cache=False)
    result = formalize_dossier(sample_dossier, client=client,
                               out_dir=tmp_path / "translated")
    assert {p.model for p in result.case.provenance.prompts} == {"gemini-2.5-pro"}
    assert {call["model"] for call in client.calls} == {"gemini-2.5-pro"}


def test_run_artifacts_are_complete(sample_dossier, fake_transport, tmp_path):
    result = run(sample_dossier, fake_transport, tmp_path)
    run_dir = result.run_dir
    for name in ("00_brief.md", "01_atoms.json", "02_rules.json", "03_queries.json",
                 "03b_bridge.json", "04_lrc.json", "trace.jsonl", "run.json",
                 "case.json", "validation.json"):
        assert (run_dir / name).is_file(), name

    trace = [json.loads(line) for line in
             (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [entry["stage"] for entry in trace] == ["atoms", "rules", "queries", "lrc"]
    for entry in trace:
        assert entry["prompt_text"] and entry["raw_response"]
        assert len(entry["prompt_template_sha256"]) == 64
        assert entry["model"] == "modelo-de-teste"

    manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert manifest["ok"] is True
    assert manifest["source_sha256"] == result.case.case.source_sha256
    assert {s["stage"] for s in manifest["stages"]} == {"atoms", "rules", "queries", "lrc"}


def test_canonical_record_and_index_are_written(sample_dossier, fake_transport, tmp_path):
    run(sample_dossier, fake_transport, tmp_path)
    out_dir = tmp_path / "translated"
    stored = FormalizedCase.model_validate_json(
        (out_dir / "case-fixture" / "case.json").read_text(encoding="utf-8"))
    assert stored.case.id == "case-fixture"
    assert stored.provenance.model == "modelo-de-teste"
    assert {p.stage for p in stored.provenance.prompts} == {"atoms", "rules", "queries", "lrc"}
    assert all(len(p.sha256) == 64 for p in stored.provenance.prompts)

    index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
    assert [entry["case_id"] for entry in index] == ["case-fixture"]
    assert index[0]["summary"]["agreement"]["match"] == 2


def test_reruns_do_not_overwrite_previous_runs(sample_dossier, fake_transport, tmp_path):
    first = run(sample_dossier, fake_transport, tmp_path, run_id="run-a")
    second = run(sample_dossier, fake_transport, tmp_path, run_id="run-b")
    runs = sorted(p.name for p in (tmp_path / "translated" / "case-fixture" / "runs").iterdir())
    assert runs == ["run-a", "run-b"]
    assert first.run_dir != second.run_dir


def test_cache_avoids_a_second_call(sample_dossier, fake_transport, tmp_path):
    client = GeminiClient(transport=fake_transport, cache_dir=tmp_path / "cache",
                          model_override="modelo-de-teste")
    formalize_dossier(sample_dossier, client=client, out_dir=tmp_path / "translated",
                      run_id="run-a")
    assert len(fake_transport.prompts) == 4

    client = GeminiClient(transport=fake_transport, cache_dir=tmp_path / "cache",
                          model_override="modelo-de-teste")
    result = formalize_dossier(sample_dossier, client=client,
                               out_dir=tmp_path / "translated", run_id="run-b")
    assert len(fake_transport.prompts) == 4  # no new calls
    assert all(call["cache_hit"] for call in client.calls)
    assert result.report.ok


def test_case_spec_adapter_feeds_the_renderers(sample_dossier, fake_transport, tmp_path):
    case = run(sample_dossier, fake_transport, tmp_path).case
    spec = build.to_case_spec(case)
    assert spec.id == "case-fixture"
    assert spec.origin == "dossie"
    assert spec.effect == "Morte"
    assert spec.atom_glosses["Leuc"] == "a criança tinha leucemia"
    assert spec.atom_glosses["¬Consent"].startswith("não é o caso de que")
    assert spec.rule_glosses["r2"].startswith("A quimioterapia")
    # expect_* records what the solver computed, so a solver change is caught.
    assert [q.expect_ness for q in spec.queries] == [True, True]
    assert [q.expect_but_for for q in spec.queries] == [True, True]
    assert "No acórdão, a corte reconheceu" in spec.queries[0].note_pt

    assert spec.lrc is not None
    assert spec.lrc.targets == ["LeReCa_Leuc_Morte", "LeReCa_notConsent_Morte"]
    assert spec.lrc.duty_basis_pt.startswith("Dever dos pais")
    # LRC glosses are generated from the case's own atom glosses.
    assert spec.lrc.atom_glosses["CaFa_notConsent_Morte"] == (
        "“não é o caso de que os pais consentiram com o tratamento” é causa de fato "
        "de “a criança morreu”")
    assert spec.lrc.atom_glosses["Obl_Consent"].startswith("os pais tinham o dever")
