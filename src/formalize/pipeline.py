"""Orchestration: dossier in, formalized case + run artifacts out.

The layout under `data/translated/` separates the *current* formalization from
the runs that produced it:

    data/translated/index.json                 catalog the interface reads
    data/translated/<case-id>/case.json        the canonical record
    data/translated/<case-id>/validation.json  checks + solver-vs-court table
    data/translated/<case-id>/runs/<run-id>/   everything one run produced

A run directory holds `00_brief.md` (the deterministic normalization every
stage saw), one JSON per stage with its prompt hash and its issues,
`trace.jsonl` with the full text of every model call, and `run.json` tying it
together. Editing a prompt and re-running therefore produces a new, comparable
run rather than overwriting the evidence for the previous one -- which is the
whole reason the prompts live in versioned files.
"""
import json
import logging

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from . import build
from .bridge import BridgeFacts
from .dossier import Dossier, load_dossier
from .gemini import GeminiClient
from .prompts import PromptSpec, load as load_prompt
from .schema import (
    SCHEMA_VERSION, CaseMeta, FormalizedCase, LRCBlock, PromptRef, Provenance,
    Query, RuleMeta,
)
from .stages import StageResult, run_atoms, run_lrc, run_queries, run_rules
from .validate import ValidationReport, validate_case

logger = logging.getLogger("formalize.pipeline")

DEFAULT_OUT_DIR = Path("data/translated")
STAGE_FILES = {"atoms": "01_atoms.json", "rules": "02_rules.json",
               "queries": "03_queries.json", "lrc": "04_lrc.json"}


@dataclass
class PipelineResult:
    case: Optional[FormalizedCase]
    report: Optional[ValidationReport]
    run_dir: Path
    stages: List[StageResult] = field(default_factory=list)
    dry_run: bool = False
    usage: Dict[str, int] = field(default_factory=dict)


def new_run_id(now: Optional[datetime] = None) -> str:
    return (now or datetime.now()).strftime("%Y%m%d-%H%M%S")


# ----------------------------------------------------------------------
def formalize_dossier(
    source,
    *,
    client: Optional[GeminiClient] = None,
    out_dir=DEFAULT_OUT_DIR,
    prompt_versions: Optional[Dict[str, int]] = None,
    prompts_dir: Optional[Path] = None,
    max_repairs: int = 2,
    run_id: Optional[str] = None,
    dry_run: bool = False,
) -> PipelineResult:
    """Run the full formalization for one dossier file."""
    dossier = load_dossier(source)
    out_dir = Path(out_dir)
    run_id = run_id or new_run_id()
    case_dir = out_dir / dossier.case_id
    run_dir = case_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    brief = dossier.brief()
    (run_dir / "00_brief.md").write_text(brief, encoding="utf-8")
    logger.info("Dossiê %s normalizado: %s", dossier.case_id, dossier.stats())

    versions = prompt_versions or {}
    if dry_run:
        _write_dry_run_prompts(run_dir, brief, dossier, versions, prompts_dir)
        logger.info("Dry-run: prompts renderizados em %s", run_dir / "prompts")
        return PipelineResult(case=None, report=None, run_dir=run_dir, dry_run=True)

    client = client or GeminiClient()
    client.set_trace_path(run_dir / "trace.jsonl")
    valid_ids = dossier.valid_ids()
    stage_kwargs = dict(max_repairs=max_repairs, prompts_dir=prompts_dir)

    atoms = run_atoms(client, brief=brief, valid_ids=valid_ids,
                      version=versions.get("atoms"), **stage_kwargs)
    _write_stage(run_dir, atoms)

    rules = run_rules(client, brief=brief, atoms=atoms.output, valid_ids=valid_ids,
                      version=versions.get("rules"), **stage_kwargs)
    _write_stage(run_dir, rules)

    queries = run_queries(client, brief=brief, atoms=atoms.output, rules=rules.output,
                          valid_ids=valid_ids, version=versions.get("queries"), **stage_kwargs)
    _write_stage(run_dir, queries)

    # The bridge runs the cause-in-fact solver *before* the legal-relevance
    # stage, so that stage reasons over facts rather than over guesses.
    partial = _assemble(dossier, atoms.output, rules.output, queries.output, lrc=None,
                        provenance=None)
    facts = build.bridge_facts(partial)
    (run_dir / "03b_bridge.json").write_text(
        json.dumps(facts.as_records(), ensure_ascii=False, indent=2), encoding="utf-8")

    lrc = run_lrc(client, brief=brief, atoms=atoms.output, rules=rules.output,
                  queries=queries.output, facts=facts, glosses=partial.atom_glosses(),
                  version=versions.get("lrc"), **stage_kwargs)
    _write_stage(run_dir, lrc)

    stages = [atoms, rules, queries, lrc]
    provenance = Provenance(
        run_id=run_id,
        created_at=datetime.now().isoformat(timespec="seconds"),
        model=client.model_override or client.default_model,
        prompts=[
            PromptRef(
                stage=stage.stage,
                path=stage.prompt.relative_path,
                sha256=stage.prompt.template_sha256,
                model=str(client.model_override or stage.prompt.model or client.default_model),
            )
            for stage in stages
        ],
        pipeline_version=SCHEMA_VERSION,
    )
    case = _assemble(dossier, atoms.output, rules.output, queries.output,
                     lrc=lrc.output, facts=facts, provenance=provenance)
    case = build.annotate(case)
    report = validate_case(case, valid_ids)

    _write_outputs(case_dir, run_dir, case, report, stages, dossier, client, run_id)
    _update_index(out_dir)
    return PipelineResult(case=case, report=report, run_dir=run_dir,
                          stages=stages, usage=client.usage_total())


# ----------------------------------------------------------------------
def _assemble(dossier: Dossier, atoms, rules, queries, lrc,
              facts: Optional[BridgeFacts] = None,
              provenance: Optional[Provenance] = None) -> FormalizedCase:
    """Stage outputs -> the persisted record. Purely mechanical: no stage
    output is reinterpreted here, only re-shaped."""
    rules_meta = [
        RuleMeta(
            id=entry.rule.partition(":")[0].strip(),
            rule=entry.rule, kind=entry.kind, gloss_pt=entry.gloss_pt,
            perspective=entry.perspective, evidence=entry.evidence,
            dossier_refs=entry.dossier_refs,
        )
        for entry in [*rules.strict_rules, *rules.defeasible_rules]
    ]
    lrc_block = None
    if lrc is not None:
        lrc_block = LRCBlock(
            doctrinal_premises=list(lrc.doctrinal_premises),
            bridged_premises=facts.premises() if facts else [],
            scheme_rules=list(lrc.scheme_rules),
            targets=list(lrc.targets),
            duty_basis_pt=lrc.duty_basis_pt,
        )
    return FormalizedCase(
        schema_version=SCHEMA_VERSION,
        case=CaseMeta(
            id=dossier.case_id,
            title=atoms.case_title or dossier.title,
            annotator=dossier.annotator,
            source_file=str(dossier.path) if dossier.path else "",
            source_sha256=dossier.sha256,
            session_id=dossier.session_id,
        ),
        narrative_pt=atoms.narrative_pt,
        central_question=atoms.central_question,
        atoms=list(atoms.atoms),
        knowledge_base={"premises": list(rules.premises), "axioms": list(rules.axioms)},
        causal_model={
            "strict_rules": [r.rule for r in rules.strict_rules],
            "defeasible_rules": [r.rule for r in rules.defeasible_rules],
        },
        rules_meta=rules_meta,
        effect=atoms.outcome_code,
        queries=[
            Query(
                phi=q.phi, psi=q.psi, question_pt=q.question_pt,
                court_verdict=q.court_verdict, court_rationale_pt=q.court_rationale_pt,
                evidence=q.evidence,
            )
            for q in queries.queries
        ],
        lrc=lrc_block,
        open_questions=list(atoms.open_questions),
        modelling_notes_pt=rules.modelling_notes_pt,
        provenance=provenance,
    )


def _write_stage(run_dir: Path, stage: StageResult) -> None:
    (run_dir / STAGE_FILES[stage.stage]).write_text(
        json.dumps(stage.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _write_outputs(case_dir: Path, run_dir: Path, case: FormalizedCase,
                   report: ValidationReport, stages: List[StageResult],
                   dossier: Dossier, client: GeminiClient, run_id: str) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(case.model_dump(), ensure_ascii=False, indent=2)
    (case_dir / "case.json").write_text(payload, encoding="utf-8")
    (run_dir / "case.json").write_text(payload, encoding="utf-8")

    validation = json.dumps(report.as_dict(), ensure_ascii=False, indent=2)
    (case_dir / "validation.json").write_text(validation, encoding="utf-8")
    (run_dir / "validation.json").write_text(validation, encoding="utf-8")

    (run_dir / "run.json").write_text(json.dumps({
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "case_id": dossier.case_id,
        "annotator": dossier.annotator,
        "source_file": str(dossier.path) if dossier.path else "",
        "source_sha256": dossier.sha256,
        "dossier_stats": dossier.stats(),
        "model": client.model_override or client.default_model,
        "usage": client.usage_total(),
        "llm_calls": len(client.calls),
        "stages": [
            {
                "stage": stage.stage,
                "prompt": stage.prompt.relative_path,
                "prompt_version": stage.prompt.version,
                "template_sha256": stage.prompt.template_sha256,
                "attempts": stage.attempts,
                "warnings": len(stage.warnings),
            }
            for stage in stages
        ],
        "validation": report.summary,
        "ok": report.ok,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _update_index(out_dir: Path) -> None:
    """Rebuild `index.json` from whatever `case.json` files exist."""
    entries = []
    for case_file in sorted(out_dir.glob("*/case.json")):
        try:
            case = FormalizedCase.model_validate_json(case_file.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a broken record must not break the index
            logger.warning("Ignorando %s: não é um case.json válido", case_file)
            continue
        validation_file = case_file.parent / "validation.json"
        summary = {}
        if validation_file.is_file():
            try:
                summary = json.loads(validation_file.read_text(encoding="utf-8")).get("summary", {})
            except json.JSONDecodeError:
                summary = {}
        entries.append({
            "case_id": case.case.id,
            "title": case.case.title,
            "annotator": case.case.annotator,
            "path": str(case_file.relative_to(out_dir)),
            "run_id": case.provenance.run_id if case.provenance else "",
            "created_at": case.provenance.created_at if case.provenance else "",
            "model": case.provenance.model if case.provenance else "",
            "summary": summary,
        })
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_dry_run_prompts(run_dir: Path, brief: str, dossier: Dossier,
                           versions: Dict[str, int], prompts_dir: Optional[Path]) -> None:
    """Render every prompt without calling the model.

    Only the first stage can be rendered with real inputs; the later ones get
    an explicit placeholder where the previous stage's output would go, which
    is still enough to review the modelling manual and the includes.
    """
    placeholder = "«saída do estágio anterior (preenchida na execução real)»"
    variables = {
        "atoms": {
            "brief": brief,
            "valid_ids": "\n".join(f"- `{i}`" for i in sorted(dossier.valid_ids())),
        },
        "rules": {"brief": brief, "atoms_json": placeholder, "outcome": "«resultado»"},
        "queries": {"brief": brief, "atoms_json": placeholder,
                    "rules_json": placeholder, "outcome": "«resultado»"},
        "lrc": {"brief": brief, "atoms_json": placeholder, "rules_json": placeholder,
                "queries_json": placeholder, "bridge_facts": placeholder,
                "deferred_atoms": placeholder},
    }
    prompts_out = run_dir / "prompts"
    prompts_out.mkdir(parents=True, exist_ok=True)
    for order, (stage, values) in enumerate(variables.items(), start=1):
        spec: PromptSpec = load_prompt(stage, version=versions.get(stage),
                                       variables=values, prompts_dir=prompts_dir)
        (prompts_out / f"{order:02d}_{stage}.txt").write_text(
            f"# {spec.relative_path} (v{spec.version}, sha {spec.template_sha256[:12]})\n"
            f"# config: {spec.config}\n\n{spec.text}",
            encoding="utf-8",
        )
