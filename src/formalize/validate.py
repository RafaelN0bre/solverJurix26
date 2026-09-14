"""Deterministic validation of a formalization record, plus the
solver-vs-court comparison table. Runs after assembly (`formalize.build`)
and gates publication: `scripts/run_translated.py` writes its output to
`validation.json`, and the Validation tab renders it.
"""

"""Deterministic checks over a formalization record, and the solver-vs-court
comparison table.

Everything here runs without a model. Two jobs:

1. **Checking.** `validate_case` holds a record against the rules the solver
   actually enforces -- rule grammar, literal vocabulary, the requirement
   that the outcome be *derived* rather than assumed, and the requirement
   that the bridged premises of the legal-relevance layer match exactly what
   the solver produces (`case.bridge_drift`). Since the records are
   hand-transcribed (`scripts/build_case003_final.py`), failures point at the
   transcription, and the transcriber is a person reading the report.

2. **The comparison.** `validate_case` also builds the table the whole
   exercise is for: for every causal question, what the solver notions
   concluded, what the legal-relevance layer concluded, what the court
   decided, and whether they agree. `print_report` is its terminal rendering.

Warnings are reported but are not errors: a mutual rebut with no undercut is
usually a modelling mistake, but it is occasionally exactly what the judgment
says (the question was left open), so the call is the reader's.
"""
import re
import sys

from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .schema import FormalizedCase

ATOM_CODE_RE = re.compile(r"^[A-Z][A-Za-z0-9]{1,11}$")
RULE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    where: str = ""
    severity: str = "error"

    def render(self) -> str:
        location = f" [{self.where}]" if self.where else ""
        return f"- ({self.code}){location} {self.message}"


@dataclass
class ValidationReport:
    issues: List[Issue] = field(default_factory=list)
    comparison: List[dict] = field(default_factory=list)
    summary: Dict[str, object] = field(default_factory=dict)

    @property
    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def render_errors(self) -> str:
        return "\n".join(issue.render() for issue in self.errors) or "- (nenhum)"

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": [asdict(i) for i in self.errors],
            "warnings": [asdict(i) for i in self.warnings],
            "comparison": self.comparison,
            "summary": self.summary,
        }


def _error(code: str, message: str, where: str = "") -> Issue:
    return Issue(code, message, where, "error")


def _warning(code: str, message: str, where: str = "") -> Issue:
    return Issue(code, message, where, "warning")


# ----------------------------------------------------------------------
# Rule grammar (mirrors ArgumentationFramework._parse_rule exactly)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ParsedRule:
    id: str
    antecedents: List[str]
    consequent: str
    is_strict: bool

    @property
    def is_undercutter(self) -> bool:
        return self.consequent.startswith("¬r")

    @property
    def undercut_target(self) -> Optional[str]:
        return self.consequent[1:] if self.consequent.startswith("¬") else None

    @property
    def literals(self) -> List[str]:
        return [*self.antecedents, self.consequent]


def parse_rule(rule_str: str) -> ParsedRule:
    """Parse `rN: A AND B => C`, raising ValueError on anything the solver
    would also reject."""
    if ":" not in rule_str:
        raise ValueError("falta o identificador seguido de ':' (ex.: 'r0: A => B')")
    rule_id, _, body = rule_str.partition(":")
    rule_id = rule_id.strip()
    body = body.strip()
    if not RULE_ID_RE.match(rule_id):
        raise ValueError(f"identificador de regra inválido: {rule_id!r}")

    is_strict = False
    parts = body.split("=>")
    if len(parts) == 1:
        parts = body.split("->")
        is_strict = len(parts) == 2
    if len(parts) != 2:
        raise ValueError("a regra precisa ter exatamente uma seta '=>' (ou '->')")

    antecedents = [ant.strip() for ant in parts[0].split("AND")]
    consequent = parts[1].strip()
    if not consequent:
        raise ValueError("consequente vazio")
    if any(not ant for ant in antecedents):
        raise ValueError("antecedente vazio (verifique o separador ' AND ')")
    for ant in antecedents:
        if "," in ant or " " in ant:
            raise ValueError(
                f"antecedente {ant!r} contém vírgula ou espaço; separe os "
                "antecedentes apenas com ' AND '"
            )
    return ParsedRule(rule_id, antecedents, consequent, is_strict)


def base_literal(literal: str) -> str:
    return literal[1:] if literal.startswith("¬") else literal


# ----------------------------------------------------------------------
# Whole-case validation and the solver-vs-court comparison
# ----------------------------------------------------------------------
def _solver_conclusion(query, has_lrc: bool) -> Tuple[str, Optional[str]]:
    """`(readable label, comparable verdict)` for a resolved question."""
    solver = query.solver
    if solver is None:
        return "não avaliada", None
    if not solver.ness:
        return "não é causa de fato", "rejeitada"
    if has_lrc and query.legally_relevant is False:
        return "é causa de fato, mas não juridicamente relevante", "rejeitada"
    if has_lrc and query.legally_relevant is True:
        return "é causa de fato e juridicamente relevante", "acolhida"
    return "é causa de fato", "acolhida"


def build_comparison(case: FormalizedCase) -> List[dict]:
    """Per causal question: the three notions, the legal-relevance verdict,
    the court's own verdict, and whether they agree."""
    has_lrc = case.lrc is not None and bool(case.lrc.scheme_rules)
    rows = []
    for query in case.queries:
        label, solver_verdict = _solver_conclusion(query, has_lrc)
        if query.court_verdict == "nao_decidida" or solver_verdict is None:
            agreement = "indefinido"
        else:
            agreement = "match" if solver_verdict == query.court_verdict else "mismatch"
        rows.append({
            "phi": query.phi,
            "psi": query.psi,
            "question_pt": query.question_pt,
            "ness": query.solver.ness if query.solver else None,
            "but_for": query.solver.but_for if query.solver else None,
            "legally_relevant": query.legally_relevant,
            "solver_label_pt": label,
            "solver_verdict": solver_verdict,
            "court_verdict": query.court_verdict,
            "court_rationale_pt": query.court_rationale_pt,
            "agreement": agreement,
        })
    return rows


def _inert_premises(case: FormalizedCase) -> List[Issue]:
    """Premises no rule ever reads, on an already-assembled record.

    Reported as a warning rather than an error: `ValidationReport.ok` means
    "the record passed its checks when it was produced", and re-reading a
    stored case should surface the problem in the interface without
    retroactively invalidating it.
    """
    issues: List[Issue] = []
    consumed: Set[str] = set()
    for meta in case.rules_meta:
        try:
            consumed |= {base_literal(ant) for ant in parse_rule(meta.rule).antecedents}
        except ValueError:
            continue  # already reported as case.rule_syntax
    duties = {atom.code for atom in case.atoms if atom.kind == "dever"}
    premises = {base_literal(p) for p in case.knowledge_base.get("premises", [])}
    for premise in sorted(premises - consumed):
        if premise in duties:
            issues.append(_warning(
                "case.duty_not_used",
                f"o átomo de dever {premise} é premissa mas nenhuma regra o lê: "
                "o dever não condiciona nenhuma inferência e, portanto, não faz "
                "trabalho no framework.", premise))
        else:
            issues.append(_warning(
                "case.inert_premise",
                f"a premissa {premise} não é antecedente de nenhuma regra.", premise))
    return issues


def validate_case(case: FormalizedCase,
                  valid_ids: Optional[Set[str]] = None) -> ValidationReport:
    """Full check of a formalization record, plus the comparison table.

    Assumes `case` already went through `formalize.build.annotate`, so the
    solver verdicts are present.
    """
    from . import build as build_module

    issues: List[Issue] = []
    codes = [atom.code for atom in case.atoms]

    try:
        af = build_module.cif_framework(case)
    except Exception as exc:  # noqa: BLE001
        issues.append(_error("case.framework", f"o solver rejeitou o framework: {exc}"))
        return ValidationReport(issues=issues)

    if case.effect not in af.justified_conclusions():
        issues.append(_error(
            "case.outcome_not_justified",
            f"o resultado {case.effect!r} não é conclusão justificada do framework."))
    for atom in case.atoms:
        if not ATOM_CODE_RE.match(atom.code):
            issues.append(_error("case.atom_code", f"código inválido: {atom.code!r}", atom.code))
    for meta in case.rules_meta:
        try:
            parse_rule(meta.rule)
        except ValueError as exc:
            issues.append(_error("case.rule_syntax", f"{meta.rule!r}: {exc}", meta.id))
    for query in case.queries:
        for literal in (query.phi, query.psi):
            if base_literal(literal) not in codes:
                issues.append(_error(
                    "case.query_literal", f"literal {literal!r} fora do catálogo.",
                    f"{query.phi}->{query.psi}"))

    issues += _inert_premises(case)

    if case.lrc is not None and case.lrc.scheme_rules:
        facts = build_module.bridge_facts(case, af)
        available = set(facts.premises())
        recorded = set(case.lrc.bridged_premises)
        if recorded != available:
            issues.append(_error(
                "case.bridge_drift",
                "as premissas de ponte gravadas não batem com o que o solver "
                f"produz agora (faltando: {sorted(available - recorded)}; "
                f"sobrando: {sorted(recorded - available)}).", "lrc"))
        try:
            build_module.lrc_framework(case)
        except Exception as exc:  # noqa: BLE001
            issues.append(_error("case.lrc_framework", f"o solver rejeitou a camada LRC: {exc}", "lrc"))

    comparison = build_comparison(case)
    counts = {key: sum(1 for row in comparison if row["agreement"] == key)
              for key in ("match", "mismatch", "indefinido")}
    decided = counts["match"] + counts["mismatch"]
    summary = {
        "case_id": case.case.id,
        "atoms": len(case.atoms),
        "premises": len(case.knowledge_base.get("premises", [])),
        "rules": len(case.rules_meta),
        "queries": len(case.queries),
        "has_lrc": case.lrc is not None and bool(case.lrc.scheme_rules),
        "agreement": counts,
        "agreement_rate": round(counts["match"] / decided, 3) if decided else None,
    }
    return ValidationReport(issues=issues, comparison=comparison, summary=summary)


def render_issues(issues: Iterable[Issue]) -> str:
    listed = [issue.render() for issue in issues]
    return "\n".join(listed) if listed else "- (nenhum)"


# ----------------------------------------------------------------------
# Terminal rendering of a report (moved here from the removed pipeline CLI)
# ----------------------------------------------------------------------
AGREEMENT_GLYPH = {"match": "OK ", "mismatch": "DIV", "indefinido": " ? "}


def print_comparison(report: ValidationReport, stream=sys.stdout) -> None:
    """The solver-vs-court table, as the terminal version of what the
    interface shows in the formalization fiche."""
    if not report.comparison:
        print("Nenhuma pergunta causal avaliada.", file=stream)
        return
    print("\nSolver × decisão da corte", file=stream)
    print(f"{'':4} {'φ':<14} {'ψ':<14} {'NESS':<5} {'but-for':<8} "
          f"{'relev.':<7} {'corte':<13}", file=stream)
    for row in report.comparison:
        def mark(value):
            return "—" if value is None else ("sim" if value else "não")
        print(
            f"{AGREEMENT_GLYPH.get(row['agreement'], '   '):4} "
            f"{row['phi']:<14} {row['psi']:<14} {mark(row['ness']):<5} "
            f"{mark(row['but_for']):<8} "
            f"{mark(row['legally_relevant']):<7} {row['court_verdict']:<13}",
            file=stream,
        )
    counts = report.summary.get("agreement", {})
    rate = report.summary.get("agreement_rate")
    print(
        f"\nConcordância: {counts.get('match', 0)} de "
        f"{counts.get('match', 0) + counts.get('mismatch', 0)} perguntas decididas"
        + (f" ({rate:.0%})" if rate is not None else "")
        + f"; {counts.get('indefinido', 0)} não decidida(s) pela corte.",
        file=stream,
    )


def print_report(report: ValidationReport, stream=sys.stdout) -> None:
    for warning in report.warnings:
        print(f"aviso  {warning.render()[2:]}", file=stream)
    for error in report.errors:
        print(f"ERRO   {error.render()[2:]}", file=stream)
    print_comparison(report, stream)
