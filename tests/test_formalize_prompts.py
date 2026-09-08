"""The prompt loader: versioning, includes, variables and hashes.

Prompts are the part of this pipeline meant to be edited constantly, so the
loader has to make two things impossible: silently sending a prompt with an
unfilled placeholder, and losing track of which prompt text produced a run.
"""
import pytest

from formalize import prompts


@pytest.fixture
def prompt_dir(tmp_path):
    shared = tmp_path / "_shared"
    shared.mkdir()
    (shared / "grammar.md").write_text("REGRA COMPARTILHADA\n", encoding="utf-8")
    (tmp_path / "01_demo.v1.md").write_text(
        "---\nid: demo\nversion: 1\nmodel: gemini-2.5-flash\ntemperature: 0\n"
        "max_output_tokens: 4096\n---\n"
        "{{include:_shared/grammar}}\n\nCaso: {{brief}}\n",
        encoding="utf-8",
    )
    (tmp_path / "01_demo.v2.md").write_text(
        "---\nid: demo\nversion: 2\nmodel: gemini-2.5-pro\n---\nv2: {{brief}}\n",
        encoding="utf-8",
    )
    return tmp_path


def test_defaults_to_the_highest_version(prompt_dir):
    spec = prompts.load("demo", variables={"brief": "X"}, prompts_dir=prompt_dir)
    assert spec.version == 2
    assert spec.text.strip() == "v2: X"
    assert prompts.available_versions("demo", prompt_dir) == [1, 2]


def test_pinning_an_older_version_keeps_it_runnable(prompt_dir):
    spec = prompts.load("demo", version=1, variables={"brief": "X"}, prompts_dir=prompt_dir)
    assert spec.version == 1
    assert "REGRA COMPARTILHADA" in spec.text
    assert spec.includes == ["_shared/grammar"]


def test_front_matter_configures_the_model_per_stage(prompt_dir):
    spec = prompts.load("demo", version=1, variables={"brief": "X"}, prompts_dir=prompt_dir)
    assert spec.config == {"model": "gemini-2.5-flash", "temperature": 0,
                           "max_output_tokens": 4096}
    assert spec.model == "gemini-2.5-flash"


def test_unfilled_variable_is_an_error(prompt_dir):
    with pytest.raises(prompts.PromptError, match="brief"):
        prompts.load("demo", prompts_dir=prompt_dir)


def test_unknown_stage_and_version_are_errors(prompt_dir):
    with pytest.raises(prompts.PromptError, match="inexistente|Nenhum prompt"):
        prompts.load("naoexiste", prompts_dir=prompt_dir)
    with pytest.raises(prompts.PromptError, match="v9"):
        prompts.load("demo", version=9, variables={"brief": "X"}, prompts_dir=prompt_dir)


def test_missing_include_is_an_error(tmp_path):
    (tmp_path / "01_x.v1.md").write_text("---\nid: x\n---\n{{include:_shared/ausente}}\n",
                                         encoding="utf-8")
    with pytest.raises(prompts.PromptError, match="Include inexistente"):
        prompts.load("x", prompts_dir=tmp_path)


def test_substituted_content_is_not_rescanned(prompt_dir):
    """Annotator text may contain braces; it must never be re-expanded."""
    spec = prompts.load("demo", version=2, variables={"brief": "{{brief}}"},
                        prompts_dir=prompt_dir)
    assert spec.text.strip() == "v2: {{brief}}"


def test_template_hash_is_stable_while_rendered_hash_tracks_the_case(prompt_dir):
    first = prompts.load("demo", version=2, variables={"brief": "A"}, prompts_dir=prompt_dir)
    second = prompts.load("demo", version=2, variables={"brief": "B"}, prompts_dir=prompt_dir)
    assert first.template_sha256 == second.template_sha256
    assert first.rendered_sha256 != second.rendered_sha256


def test_include_changes_move_the_template_hash(prompt_dir):
    before = prompts.load("demo", version=1, variables={"brief": "A"}, prompts_dir=prompt_dir)
    (prompt_dir / "_shared" / "grammar.md").write_text("OUTRA REGRA\n", encoding="utf-8")
    after = prompts.load("demo", version=1, variables={"brief": "A"}, prompts_dir=prompt_dir)
    assert before.template_sha256 != after.template_sha256


def test_shipped_prompts_all_load():
    """Every stage the pipeline calls must have a loadable prompt."""
    placeholder = "…"
    variables = {
        "atoms": {"brief": placeholder, "valid_ids": placeholder},
        "rules": {"brief": placeholder, "atoms_json": placeholder, "outcome": "Res"},
        "queries": {"brief": placeholder, "atoms_json": placeholder,
                    "rules_json": placeholder, "outcome": "Res"},
        "lrc": {"brief": placeholder, "atoms_json": placeholder, "rules_json": placeholder,
                "queries_json": placeholder, "bridge_facts": placeholder,
                "deferred_atoms": placeholder},
        "repair": {"stage": "rules", "errors": placeholder,
                   "previous_output": placeholder, "original_prompt": placeholder},
    }
    for stage, values in variables.items():
        spec = prompts.load(stage, variables=values)
        assert spec.text.strip()
        assert "{{" not in spec.text


def test_rules_prompt_carries_the_undercut_constraint():
    """The no-preferences constraint is what makes the modelling reproduce a
    judgment's outcome instead of leaving both sides undecided; if it ever
    falls out of the prompt, the formalizations quietly degrade."""
    spec = prompts.load("rules", variables={"brief": "b", "atoms_json": "a", "outcome": "R"})
    assert "REGRA Nº 1" in spec.text
    assert "undercut" in spec.text and "rebut" in spec.text
    assert "não tem preferências numéricas" in spec.text
