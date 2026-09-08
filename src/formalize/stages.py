"""The four LLM stages, each guarded by the deterministic checks.

Splitting the formalization into stages is the point, not an implementation
detail: asking one call to invent a vocabulary, write rules over it, pick the
causal questions *and* build the legal-relevance layer produces rules that
reference literals the model forgot it had introduced. Here each stage
receives the previous stage's output verbatim and is forbidden from adding to
it, which is what makes the vocabulary checks in `formalize.validate`
enforceable at all.

Every stage runs through `run_stage`, which is a small loop: render the
prompt, call the model, run the stage's checks, and -- if the checks find hard
errors -- hand the model its own output plus the error list through the repair
prompt and try again. The checks run the real parser and the real solver, so
the corrections the model gets are facts, not style notes.
"""
import json
import logging

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Type

from pydantic import BaseModel, ValidationError

from . import prompts as prompt_loader
from .bridge import BridgeFacts
from .gemini import GeminiClient, LLMError, try_parse_json
from .prompts import PromptSpec
from .schema import (
    AtomsStageOut, LrcStageOut, QueriesStageOut, RepairStageOut, RulesStageOut,
)
from .validate import Issue, check_atoms, check_lrc, check_queries, check_rules, render_issues

logger = logging.getLogger("formalize.stages")

Checker = Callable[[BaseModel], List[Issue]]


@dataclass
class StageResult:
    stage: str
    output: BaseModel
    prompt: PromptSpec
    issues: List[Issue] = field(default_factory=list)
    attempts: int = 1
    repairs: List[List[str]] = field(default_factory=list)

    @property
    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    def as_dict(self) -> dict:
        return {
            "stage": self.stage,
            "prompt": {
                "path": self.prompt.relative_path,
                "version": self.prompt.version,
                "template_sha256": self.prompt.template_sha256,
                "rendered_sha256": self.prompt.rendered_sha256,
                "config": self.prompt.config,
                "includes": self.prompt.includes,
            },
            "attempts": self.attempts,
            "repairs": self.repairs,
            "issues": [
                {"code": i.code, "severity": i.severity, "where": i.where, "message": i.message}
                for i in self.issues
            ],
            "output": self.output.model_dump(),
        }


class StageError(RuntimeError):
    """A stage whose output still fails the hard checks after every repair."""

    def __init__(self, stage: str, issues: List[Issue], output: Optional[BaseModel] = None):
        self.stage = stage
        self.issues = issues
        self.output = output
        super().__init__(
            f"Estágio {stage} não passou na validação após as tentativas de "
            f"reparo:\n{render_issues(issues)}"
        )


def run_stage(client: GeminiClient, *, stage: str, schema: Type[BaseModel],
              variables: Dict[str, str], check: Checker,
              version: Optional[int] = None, max_repairs: int = 2,
              prompts_dir: Optional[Path] = None) -> StageResult:
    """Render, call, check, and repair until the hard checks pass."""
    prompt = prompt_loader.load(stage, version=version, variables=variables,
                                prompts_dir=prompts_dir)
    output = client.generate(prompt, schema, stage=stage)
    issues = check(output)
    result = StageResult(stage=stage, output=output, prompt=prompt, issues=issues)

    for attempt in range(max_repairs):
        errors = [i for i in issues if i.severity == "error"]
        if not errors:
            break
        logger.warning("Estágio %s: %d erro(s); reparo %d/%d",
                       stage, len(errors), attempt + 1, max_repairs)
        repaired = _repair(client, stage=stage, schema=schema, original=prompt,
                           previous=output, errors=errors, attempt=attempt + 1,
                           prompts_dir=prompts_dir)
        if repaired is None:
            break
        output, changes = repaired
        result.repairs.append(changes)
        issues = check(output)
        result.output, result.issues, result.attempts = output, issues, attempt + 2

    result.issues = issues
    if result.errors:
        raise StageError(stage, result.errors, output)
    return result


def _repair(client: GeminiClient, *, stage: str, schema: Type[BaseModel],
            original: PromptSpec, previous: BaseModel, errors: List[Issue],
            attempt: int, prompts_dir: Optional[Path]):
    """One correction round. Returns `(output, changes)` or None if the model
    could not produce a parsable correction (the caller then gives up and
    surfaces the original errors, which are more informative)."""
    repair_prompt = prompt_loader.load(
        "repair",
        variables={
            "stage": stage,
            "errors": render_issues(errors),
            "previous_output": json.dumps(previous.model_dump(), ensure_ascii=False, indent=2),
            "original_prompt": original.text,
        },
        prompts_dir=prompts_dir,
    )
    try:
        correction = client.generate(repair_prompt, RepairStageOut,
                                     stage=f"{stage}:repair", attempt=attempt)
    except LLMError as exc:
        logger.warning("Reparo do estágio %s falhou: %s", stage, exc)
        return None

    payload = try_parse_json(correction.corrected_json)
    if payload is None:
        logger.warning("Reparo do estágio %s devolveu corrected_json ilegível.", stage)
        return None
    try:
        return schema.model_validate(payload), list(correction.changes_pt)
    except ValidationError as exc:
        logger.warning("Reparo do estágio %s fora do schema: %s", stage, exc)
        return None


# ----------------------------------------------------------------------
# The four stages
# ----------------------------------------------------------------------
def run_atoms(client: GeminiClient, *, brief: str, valid_ids, **kwargs) -> StageResult:
    ids = sorted(valid_ids)
    return run_stage(
        client,
        stage="atoms",
        schema=AtomsStageOut,
        variables={
            "brief": brief,
            "valid_ids": "\n".join(f"- `{i}`" for i in ids) or "- (nenhum)",
        },
        check=lambda out: check_atoms(out, set(ids)),
        **kwargs,
    )


def run_rules(client: GeminiClient, *, brief: str, atoms: AtomsStageOut,
              valid_ids, **kwargs) -> StageResult:
    codes = [a.code for a in atoms.atoms]
    return run_stage(
        client,
        stage="rules",
        schema=RulesStageOut,
        variables={
            "brief": brief,
            "atoms_json": _dump(atoms),
            "outcome": atoms.outcome_code,
        },
        check=lambda out: check_rules(out, codes, atoms.outcome_code, set(valid_ids),
                                      duty_codes={a.code for a in atoms.atoms
                                                  if a.kind == "dever"}),
        **kwargs,
    )


def run_queries(client: GeminiClient, *, brief: str, atoms: AtomsStageOut,
                rules: RulesStageOut, valid_ids, **kwargs) -> StageResult:
    codes = [a.code for a in atoms.atoms]
    return run_stage(
        client,
        stage="queries",
        schema=QueriesStageOut,
        variables={
            "brief": brief,
            "atoms_json": _dump(atoms),
            "rules_json": _dump(rules),
            "outcome": atoms.outcome_code,
        },
        check=lambda out: check_queries(out, codes, atoms.outcome_code, set(valid_ids)),
        **kwargs,
    )


def run_lrc(client: GeminiClient, *, brief: str, atoms: AtomsStageOut,
            rules: RulesStageOut, queries: QueriesStageOut,
            facts: BridgeFacts, glosses: Dict[str, str], **kwargs) -> StageResult:
    return run_stage(
        client,
        stage="lrc",
        schema=LrcStageOut,
        variables={
            "brief": brief,
            "atoms_json": _dump(atoms),
            "rules_json": _dump(rules),
            "queries_json": _dump(queries),
            "bridge_facts": facts.render_for_prompt(glosses),
            "deferred_atoms": _deferred_atoms(atoms, rules),
        },
        check=lambda out: check_lrc(out, facts),
        **kwargs,
    )


def _deferred_atoms(atoms: AtomsStageOut, rules: RulesStageOut) -> str:
    """Atoms stage 2 deliberately left out of the framework.

    An established atom that did not become a premise is one stage 2 judged to
    be about *imputation* rather than about what happened -- the third-party
    act, the generic duty. Handing the list to stage 4 explicitly is what
    stops those facts from disappearing between the layers: stage 2 is told to
    defer them, so stage 4 has to be told to expect them.
    """
    declared = {p.lstrip("¬") for p in rules.premises}
    deferred = [a for a in atoms.atoms if a.established and a.code not in declared]
    if not deferred:
        return "Nenhum: todos os átomos estabelecidos entraram no framework."
    return "\n".join(f"- `{a.code}` ({a.kind}) — {a.label_pt}" for a in deferred)


def _dump(model: BaseModel) -> str:
    return json.dumps(model.model_dump(), ensure_ascii=False, indent=2)
