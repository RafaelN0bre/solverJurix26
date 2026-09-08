"""The repair loop: the parser correcting the model.

When a stage's output fails a deterministic check, the model gets its own
output back plus the concrete errors and one chance (per configured attempt)
to fix them. This is what keeps a run from dying on a fixable slip like an
undercut pointed at a rule that does not exist -- and what keeps an
unfixable one from being silently written to `data/translated/`.
"""
import json

import pytest

from formalize.gemini import GeminiClient, RawResponse, Transport
from formalize.pipeline import formalize_dossier
from formalize.stages import StageError


class ScriptedTransport(Transport):
    """Serves stage payloads, corrupting `rules` for the first `n` calls."""

    def __init__(self, outputs, broken_rules_calls=1):
        self.outputs = outputs
        self.broken_rules_calls = broken_rules_calls
        self.rules_calls = 0
        self.schema_names = []
        self.repair_prompts = []

    def generate(self, *, model, prompt, schema, config):
        self.schema_names.append(schema.__name__)
        if schema.__name__ == "RepairStageOut":
            self.repair_prompts.append(prompt)
            return RawResponse(text=json.dumps({
                "corrected_json": json.dumps(self.outputs["rules"], ensure_ascii=False),
                "changes_pt": ["r2 voltou a atacar r0"],
            }, ensure_ascii=False))
        key = {"AtomsStageOut": "atoms", "RulesStageOut": "rules",
               "QueriesStageOut": "queries", "LrcStageOut": "lrc"}[schema.__name__]
        payload = self.outputs[key]
        if key == "rules":
            self.rules_calls += 1
            if self.rules_calls <= self.broken_rules_calls:
                payload = _break(payload)
        return RawResponse(text=json.dumps(payload, ensure_ascii=False))


def _break(rules_payload):
    """Point the undercutter at a rule that does not exist."""
    broken = json.loads(json.dumps(rules_payload))
    broken["defeasible_rules"][2]["rule"] = "r2: Quimio => ¬r7"
    return broken


def test_a_fixable_stage_is_repaired_and_the_run_completes(
        sample_dossier, sample_stage_outputs, tmp_path):
    transport = ScriptedTransport(sample_stage_outputs, broken_rules_calls=1)
    client = GeminiClient(transport=transport, use_cache=False)
    result = formalize_dossier(sample_dossier, client=client, out_dir=tmp_path / "out")

    assert result.report.ok
    assert "RepairStageOut" in transport.schema_names
    # The repair prompt carries the real parser error, not a vague hint.
    assert "não existe regra 'r7'" in transport.repair_prompts[0]
    assert "r2: Quimio => ¬r7" in transport.repair_prompts[0]

    rules_stage = next(s for s in result.stages if s.stage == "rules")
    assert rules_stage.attempts == 2
    assert rules_stage.repairs == [["r2 voltou a atacar r0"]]
    assert result.case.causal_model["defeasible_rules"][2] == "r2: Quimio => ¬r0"


def test_repair_attempts_are_bounded_and_failure_is_loud(
        sample_dossier, sample_stage_outputs, tmp_path):
    """A stage that never comes right must fail the run rather than persist a
    framework the solver would choke on."""
    transport = ScriptedTransport(sample_stage_outputs, broken_rules_calls=99)

    class NeverFixes(ScriptedTransport):
        def generate(self, *, model, prompt, schema, config):
            if schema.__name__ == "RepairStageOut":
                self.repair_prompts.append(prompt)
                return RawResponse(text=json.dumps({
                    "corrected_json": json.dumps(_break(self.outputs["rules"]),
                                                 ensure_ascii=False),
                    "changes_pt": ["nada mudou"],
                }, ensure_ascii=False))
            return ScriptedTransport.generate(self, model=model, prompt=prompt,
                                              schema=schema, config=config)

    transport = NeverFixes(sample_stage_outputs, broken_rules_calls=99)
    client = GeminiClient(transport=transport, use_cache=False)
    with pytest.raises(StageError) as excinfo:
        formalize_dossier(sample_dossier, client=client, out_dir=tmp_path / "out",
                          max_repairs=2)

    assert excinfo.value.stage == "rules"
    assert len(transport.repair_prompts) == 2
    assert "rules.unknown_undercut" in str(excinfo.value)
    # Nothing half-formalized was published.
    assert not (tmp_path / "out" / "case-fixture" / "case.json").exists()


def test_stage_artifacts_record_the_repair(sample_dossier, sample_stage_outputs, tmp_path):
    transport = ScriptedTransport(sample_stage_outputs, broken_rules_calls=1)
    client = GeminiClient(transport=transport, use_cache=False)
    result = formalize_dossier(sample_dossier, client=client, out_dir=tmp_path / "out")

    stage_file = json.loads((result.run_dir / "02_rules.json").read_text(encoding="utf-8"))
    assert stage_file["attempts"] == 2
    assert stage_file["repairs"] == [["r2 voltou a atacar r0"]]

    trace = [json.loads(line) for line in
             (result.run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    # The corrected payload comes back inside the repair call itself, so the
    # stage is not re-prompted from scratch.
    assert [entry["stage"] for entry in trace] == [
        "atoms", "rules", "rules:repair", "queries", "lrc"]


# ----------------------------------------------------------------------
# Transport failures must not be charged to the repair budget
# ----------------------------------------------------------------------
def test_a_dropped_response_is_retried_not_counted_as_a_bad_answer():
    """A connection that drops mid-response is a transport failure, and the
    transport layer is where retrying belongs. Letting it through would spend
    one of the stage's two repair attempts on a network blip -- which is how
    a run once died on a 13-character atom code it had already been told to
    fix."""
    from formalize.gemini import _is_retryable

    class RemoteProtocolError(Exception):
        pass

    assert _is_retryable(RemoteProtocolError(
        "Server disconnected without sending a response."))
    assert _is_retryable(ConnectionResetError("Connection reset by peer"))


def test_a_real_refusal_is_not_retried():
    class PermissionDenied(Exception):
        pass

    from formalize.gemini import _is_retryable

    assert not _is_retryable(PermissionDenied("API key not valid"))
