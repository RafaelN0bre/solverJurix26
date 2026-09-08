"""Deterministic checks over a formalization, and the solver-vs-court table.

Everything here runs without a model. Two jobs:

1. **Gatekeeping.** Each LLM stage is checked against the rules the solver
   actually enforces -- rule grammar, literal vocabulary, undercut targets,
   the requirement that the outcome be *derived* rather than assumed, and the
   requirement that the legal-relevance layer only reason over cause-in-fact
   facts the solver really produced. Failures come back as `Issue`s and drive
   the repair prompt, so the model is corrected by the parser rather than by
   a human re-reading the JSON.

2. **The comparison.** `validate_case` builds the table the whole exercise is
   for: for every causal question, what the three solver notions concluded,
   what the legal-relevance layer concluded, what the court decided, and
   whether they agree.

Warnings are reported but never trigger a repair: a mutual rebut with no
undercut is usually a modelling mistake, but it is occasionally exactly what
the judgment says (the question was left open), so the call is the reader's.
"""
import re

from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from aspic import lrc as lrc_vocab
from aspic.solver import ArgumentationFramework, negate_literal

from .bridge import BridgeFacts
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
# Stage checks
# ----------------------------------------------------------------------
def check_atoms(atoms_out, valid_ids: Optional[Set[str]] = None) -> List[Issue]:
    issues: List[Issue] = []
    atoms = atoms_out.atoms
    if not atoms:
        return [_error("atoms.empty", "Nenhum átomo foi extraído.")]

    seen: Set[str] = set()
    for atom in atoms:
        where = f"átomo {atom.code}"
        if not ATOM_CODE_RE.match(atom.code):
            issues.append(_error(
                "atoms.code",
                f"código {atom.code!r} inválido: use CamelCase ASCII começando por "
                "letra maiúscula, 2 a 12 caracteres, sem acento, sem '¬' e sem espaço.",
                where,
            ))
        if atom.code in seen:
            issues.append(_error("atoms.duplicate", f"código {atom.code!r} repetido.", where))
        seen.add(atom.code)
        if not atom.label_pt.strip():
            issues.append(_error("atoms.label", "label_pt vazio.", where))
        if valid_ids is not None:
            for ref in [*atom.evidence, *atom.dossier_refs]:
                if ref not in valid_ids:
                    issues.append(_error(
                        "atoms.unknown_ref",
                        f"id {ref!r} não existe no dossiê; remova-o ou substitua "
                        "por um id da lista fornecida.",
                        where,
                    ))

    outcome = next((a for a in atoms if a.code == atoms_out.outcome_code), None)
    if outcome is None:
        issues.append(_error(
            "atoms.outcome_missing",
            f"outcome_code {atoms_out.outcome_code!r} não está entre os átomos.",
        ))
    else:
        if outcome.kind != "resultado":
            issues.append(_error(
                "atoms.outcome_kind",
                f"o átomo de resultado {outcome.code!r} precisa ter kind='resultado' "
                f"(está '{outcome.kind}').",
            ))
        if outcome.established:
            issues.append(_error(
                "atoms.outcome_premise",
                f"o átomo de resultado {outcome.code!r} não pode ter established=true: "
                "ele precisa ser derivado por regra, senão não há causalidade a testar.",
            ))

    results = [a.code for a in atoms if a.kind == "resultado"]
    if len(results) > 1:
        issues.append(_warning(
            "atoms.many_results",
            f"mais de um átomo com kind='resultado': {', '.join(results)}.",
        ))
    if not any(a.established for a in atoms):
        issues.append(_error("atoms.no_premise", "nenhum átomo com established=true."))
    return issues


def check_rules(rules_out, atom_codes: Sequence[str], outcome: str,
                valid_ids: Optional[Set[str]] = None,
                duty_codes: Optional[Set[str]] = None) -> List[Issue]:
    issues: List[Issue] = []
    codes = set(atom_codes)
    all_rules = [*rules_out.strict_rules, *rules_out.defeasible_rules]
    if not all_rules:
        return [_error("rules.empty", "Nenhuma regra foi produzida.")]

    parsed: Dict[str, ParsedRule] = {}
    for entry in all_rules:
        try:
            rule = parse_rule(entry.rule)
        except ValueError as exc:
            issues.append(_error("rules.syntax", f"{entry.rule!r}: {exc}", entry.rule))
            continue
        if rule.id in parsed:
            issues.append(_error("rules.duplicate_id", f"identificador {rule.id!r} repetido.", entry.rule))
        parsed[rule.id] = rule

    for entry in all_rules:
        rule = parsed.get(entry.rule.partition(":")[0].strip())
        if rule is None:
            continue
        where = entry.rule
        for literal in rule.literals:
            base = base_literal(literal)
            if base in codes:
                continue
            if literal.startswith("¬") and base in parsed:
                if base == rule.id:
                    issues.append(_error(
                        "rules.self_undercut", f"a regra {rule.id} ataca a si mesma.", where))
                continue
            if literal.startswith("¬") and base.startswith("r") and base not in parsed:
                issues.append(_error(
                    "rules.unknown_undercut",
                    f"a regra ataca {literal!r}, mas não existe regra {base!r}.", where))
                continue
            issues.append(_error(
                "rules.unknown_literal",
                f"literal {literal!r} não está no catálogo de átomos; use apenas "
                "os códigos fornecidos (ou '¬<id de regra>' para undercut).",
                where,
            ))
        if rule.is_undercutter and entry.kind != "undercut":
            issues.append(_warning(
                "rules.kind", f"a regra {rule.id} conclui {rule.consequent!r}, "
                f"então kind deveria ser 'undercut' (está '{entry.kind}').", where))
        if not entry.gloss_pt.strip():
            issues.append(_error("rules.gloss", f"a regra {rule.id} está sem gloss_pt.", where))
        if valid_ids is not None:
            for ref in [*entry.evidence, *entry.dossier_refs]:
                if ref not in valid_ids:
                    issues.append(_error(
                        "rules.unknown_ref", f"id {ref!r} não existe no dossiê.", where))

    for premise in rules_out.premises:
        if base_literal(premise) not in codes:
            issues.append(_error(
                "rules.unknown_premise",
                f"premissa {premise!r} não está no catálogo de átomos.", "premises"))
    if outcome in rules_out.premises:
        issues.append(_error(
            "rules.outcome_premise",
            f"o resultado {outcome!r} não pode ser premissa: ele tem que ser "
            "derivado por regra.", "premises"))
    if rules_out.axioms:
        issues.append(_warning(
            "rules.axioms",
            "axioms deve ficar vazio: os axiomas são reservados às expansões "
            "contrafactuais que o solver faz sozinho.", "axioms"))

    if not issues or all(i.severity == "warning" for i in issues):
        issues += _check_framework(rules_out, parsed, outcome, codes, duty_codes or set())
    return issues


def _check_framework(rules_out, parsed: Dict[str, ParsedRule], outcome: str,
                     codes: Set[str], duty_codes: Set[str]) -> List[Issue]:
    """Checks that need the framework actually built and solved."""
    issues: List[Issue] = []
    knowledge_base = {"premises": list(rules_out.premises), "axioms": list(rules_out.axioms)}
    causal_model = {
        "strict_rules": [r.rule for r in rules_out.strict_rules],
        "defeasible_rules": [r.rule for r in rules_out.defeasible_rules],
    }
    try:
        af = ArgumentationFramework(knowledge_base, causal_model)
    except Exception as exc:  # noqa: BLE001 - surfaced to the repair prompt
        return [_error("rules.framework", f"o solver rejeitou o framework: {exc}")]

    if outcome and outcome not in af.justified_conclusions():
        conclusions = sorted({a.conclusion for a in af.arguments.values()})
        derivable = outcome in conclusions
        issues.append(_error(
            "rules.outcome_not_derived",
            f"o resultado {outcome!r} "
            + ("é construível mas não sobrevive aos ataques"
               if derivable else "não é sequer derivável a partir das premissas")
            + ". Sem um argumento justificado para o resultado não há causa a testar: "
              "revise a cadeia causal (e verifique se algum undercut está atacando a "
              "regra errada).",
        ))

    used_rules = {r for arg in af.arguments.values()
                  for r in arg.strict_rules + arg.defeasible_rules}
    for rule_id in parsed:
        if rule_id not in used_rules:
            issues.append(_warning(
                "rules.never_fires",
                f"a regra {rule_id} nunca dispara: algum antecedente não é premissa "
                "nem é derivável.", rule_id))

    used_literals = {base_literal(lit) for rule in parsed.values() for lit in rule.literals}
    used_literals |= {base_literal(p) for p in rules_out.premises}
    for code in sorted(codes - used_literals):
        issues.append(_warning(
            "rules.orphan_atom",
            f"o átomo {code} não aparece em nenhuma premissa nem regra.", code))

    # A premise no rule ever reads is inert: it is declared, it is displayed,
    # and it changes nothing the solver computes. For an ordinary fact that is
    # sloppy; for an atom of kind `dever` it is a modelling failure, because
    # the duty is precisely what makes a conduct imputable -- so it has to
    # appear in the antecedent of the causal rule it enables.
    consumed = {base_literal(ant) for rule in parsed.values() for ant in rule.antecedents}
    for premise in sorted({base_literal(p) for p in rules_out.premises} - consumed):
        if premise in duty_codes:
            issues.append(_error(
                "rules.duty_not_used",
                f"o átomo de dever {premise} é premissa mas nenhuma regra o lê: "
                "um dever que não condiciona nenhuma inferência não faz trabalho "
                "no framework. Ou ele entra como antecedente da regra causal que "
                "habilita (rN: <conduta> AND " + premise + " => <elo>), ou ele é "
                "premissa doutrinária da camada de relevância jurídica e não "
                "deve ser premissa aqui.", premise))
        else:
            issues.append(_warning(
                "rules.inert_premise",
                f"a premissa {premise} não é antecedente de nenhuma regra: está "
                "declarada, mas não altera nada do que o solver calcula.", premise))

    undercut_targets = {r.undercut_target for r in parsed.values() if r.is_undercutter}
    by_consequent: Dict[str, List[str]] = {}
    for rule in parsed.values():
        if not rule.is_undercutter:
            by_consequent.setdefault(rule.consequent, []).append(rule.id)
    for consequent, rule_ids in by_consequent.items():
        opposing = by_consequent.get(negate_literal(consequent))
        if not opposing:
            continue
        if not (set(rule_ids) | set(opposing)) & undercut_targets:
            issues.append(_warning(
                "rules.mutual_rebut",
                f"{', '.join(sorted(rule_ids))} e {', '.join(sorted(opposing))} se "
                f"atacam mutuamente sobre {consequent!r} sem que nenhuma seja "
                "derrubada por undercut: os dois lados ficam indecididos (UNDEC). "
                "Se o acórdão decidiu a questão, modele a prevalência como undercut.",
            ))
    return issues


def check_queries(queries_out, atom_codes: Sequence[str], outcome: str,
                  valid_ids: Optional[Set[str]] = None) -> List[Issue]:
    issues: List[Issue] = []
    codes = set(atom_codes)
    if not queries_out.queries:
        return [_error("queries.empty", "Nenhuma pergunta causal foi produzida.")]
    seen: Set[Tuple[str, str]] = set()
    for query in queries_out.queries:
        where = f"{query.phi} -> {query.psi}"
        for literal, label in ((query.phi, "phi"), (query.psi, "psi")):
            if base_literal(literal) not in codes:
                issues.append(_error(
                    "queries.unknown_literal",
                    f"{label}={literal!r} não está no catálogo de átomos.", where))
        if (query.phi, query.psi) in seen:
            issues.append(_warning("queries.duplicate", "par repetido.", where))
        seen.add((query.phi, query.psi))
        if not query.court_rationale_pt.strip():
            issues.append(_error("queries.rationale", "court_rationale_pt vazio.", where))
        if valid_ids is not None:
            for ref in query.evidence:
                if ref not in valid_ids:
                    issues.append(_error("queries.unknown_ref", f"id {ref!r} não existe no dossiê.", where))
    if outcome and not any(q.psi == outcome for q in queries_out.queries):
        issues.append(_warning(
            "queries.no_outcome",
            f"nenhuma pergunta tem o resultado {outcome!r} como psi."))
    return issues


def check_lrc(lrc_out, facts: BridgeFacts) -> List[Issue]:
    issues: List[Issue] = []
    available = set(facts.premises())
    declared = {p.literal for p in lrc_out.doctrinal_premises}

    parsed: Dict[str, ParsedRule] = {}
    for entry in lrc_out.scheme_rules:
        try:
            rule = parse_rule(entry.rule)
        except ValueError as exc:
            issues.append(_error("lrc.syntax", f"{entry.rule!r}: {exc}", entry.rule))
            continue
        scheme = lrc_vocab.scheme_of(rule.id)
        if scheme is None:
            issues.append(_error(
                "lrc.scheme_id",
                f"o identificador {rule.id!r} não começa por um nome de esquema "
                f"({', '.join(sorted(lrc_vocab.SCHEMES))}).", entry.rule))
        elif scheme != entry.scheme:
            issues.append(_error(
                "lrc.scheme_mismatch",
                f"o identificador {rule.id!r} é do esquema {scheme!r}, mas o campo "
                f"scheme diz {entry.scheme!r}.", entry.rule))
        parsed[rule.id] = rule

    # Literals another scheme concludes are available to the ones downstream:
    # the paper chains rule 5 into rule 4, with `suca_Z` deriving
    # `SupersedingCause_Z` and `sc_X` consuming it. Treating those as missing
    # premises would push the model into *declaring* the characterisation
    # instead of deriving it -- turning a defeasible conclusion into an
    # unconditional assumption, which is a strictly weaker model.
    derived = {rule.consequent for rule in parsed.values()}

    for entry in lrc_out.scheme_rules:
        rule = parsed.get(entry.rule.partition(":")[0].strip())
        if rule is None:
            continue
        where = entry.rule
        for literal in rule.antecedents:
            base = base_literal(literal)
            if base.startswith(("CaFa_", "ButFor_")):
                if literal not in available:
                    issues.append(_error(
                        "lrc.unavailable_fact",
                        f"{literal!r} não foi produzido pelo solver, então não existe "
                        "na base de conhecimento. Use apenas os fatos fornecidos.", where))
                continue
            # A scheme antecedent may be *deliberately* unsatisfied: the
            # omission scheme is always written with `¬Obl_A`, and declaring
            # `Obl_A` instead is exactly how the paper models "there was a
            # duty to act, so the defence does not fire". So the premise
            # counts as declared when either polarity is present.
            if literal in declared or negate_literal(literal) in declared:
                continue
            if literal in derived:
                continue
            issues.append(_error(
                "lrc.missing_premise",
                f"nem {literal!r} nem sua negação estão entre as premissas "
                "doutrinárias declaradas; inclua uma das duas em "
                "doctrinal_premises ou remova a regra.", where))
        if rule.is_undercutter or rule.consequent.startswith("¬"):
            target = rule.undercut_target
            if target and target not in parsed and not lrc_vocab.is_lrc_literal(target):
                issues.append(_error(
                    "lrc.unknown_undercut",
                    f"a regra ataca {rule.consequent!r}, mas não existe regra {target!r}.", where))
        if lrc_vocab.scheme_of(rule.id) == "cf2lrc" and not rule.consequent.startswith("LeReCa_"):
            issues.append(_error(
                "lrc.cf2lrc_consequent",
                f"uma regra cf2lrc tem que concluir um literal LeReCa_*, não "
                f"{rule.consequent!r}.", where))
        if not entry.gloss_pt.strip():
            issues.append(_error("lrc.gloss", f"a regra {rule.id} está sem gloss_pt.", where))

    consequents = {r.consequent for r in parsed.values()}
    for target in lrc_out.targets:
        if not target.startswith("LeReCa_"):
            issues.append(_error("lrc.target_shape", f"{target!r} não é um literal LeReCa_*.", target))
        elif target not in consequents:
            issues.append(_error(
                "lrc.target_underived",
                f"{target!r} está em targets mas nenhuma regra o conclui.", target))

    used = {base_literal(lit) for rule in parsed.values() for lit in rule.literals}
    for premise in lrc_out.doctrinal_premises:
        if not lrc_vocab.is_lrc_literal(premise.literal):
            issues.append(_error(
                "lrc.premise_vocabulary",
                f"{premise.literal!r} não pertence ao vocabulário da camada "
                "(Om_, Obl_, Tortious_, Unexpected_, After_, Foreseeable_, "
                "ForeseeableRisk_, Playout_).", premise.literal))
        elif base_literal(premise.literal) not in used:
            issues.append(_warning(
                "lrc.unused_premise",
                f"{premise.literal!r} não é usada por nenhuma regra.", premise.literal))

    if not issues or all(i.severity == "warning" for i in issues):
        knowledge_base = {
            "premises": list(dict.fromkeys([*facts.premises(), *declared])),
            "axioms": [],
        }
        try:
            lrc_vocab.build_framework(
                knowledge_base,
                {"strict_rules": [], "defeasible_rules": [e.rule for e in lrc_out.scheme_rules]},
            )
        except Exception as exc:  # noqa: BLE001
            issues.append(_error("lrc.framework", f"o solver rejeitou a camada LRC: {exc}"))
    return issues


# ----------------------------------------------------------------------
# Whole-case validation and the solver-vs-court comparison
# ----------------------------------------------------------------------
def _solver_conclusion(query, has_lrc: bool) -> Tuple[str, Optional[str]]:
    """`(rótulo legível, veredito comparável)` para uma pergunta já resolvida."""
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

    Same condition `_check_framework` raises during stage 2, reported here as
    a warning rather than an error: at this point the model is no longer in
    the loop, `ValidationReport.ok` means "the publication gate passed when
    this record was produced", and re-reading a stored case should surface the
    problem in the interface without retroactively invalidating it.
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
