"""Deterministic assembly: `FormalizedCase` -> solver frameworks -> `CaseSpec`.

Nothing here calls a model. Given the record produced by the LLM stages, this
module builds the two argumentation frameworks, runs them, writes the verdicts
back into the record, and adapts it to the `aspic.examples.CaseSpec` the
interface and the report renderers already consume -- so a case formalized
from a dossier renders through exactly the same code path as the five ICAIL
cases hardcoded in `aspic.examples`.

Two things worth knowing about the adaptation:

* `CausalQuery.expect_*` is filled with what the solver *did* compute, not
  with a prediction. Those fields drive no rendering (`aspic.didactic` and
  `aspic.causal_report` recompute the three notions live); they exist so a
  regression test can catch a solver change silently altering the verdicts of
  an already-published formalization.
* The `LeReCa_*`/`CaFa_*` literals of the LRC layer get their Portuguese
  glosses generated here from the case's own atom glosses, rather than being
  asked of the model -- the templates are fixed by the paper's vocabulary, so
  generating them is both cheaper and more consistent.
"""
from typing import Dict, List, Optional

from aspic import lrc as lrc_vocab
from aspic.examples import CaseSpec, CausalQuery, LRCLayer
from aspic.solver import ArgumentationFramework

from .bridge import (
    NON_CANDIDATE_KINDS, BridgeFacts, candidate_literals, evaluate, target_literals,
)
from .schema import FormalizedCase, Query, SolverVerdict, undercut_gloss

VERDICT_LABELS = {
    "acolhida": "a corte reconheceu essa relação causal",
    "rejeitada": "a corte afastou essa relação causal",
    "nao_decidida": "a corte não decidiu esse ponto",
}

#: `predicate -> (positive template, negative template)`, in terms of the
#: glossed arguments. Used to render the LRC layer in plain Portuguese.
_LRC_TEMPLATES = {
    "CaFa": ("{0} é causa de fato de {1}",
             "{0} não é causa de fato de {1}"),
    "ButFor": ("sem {0}, {1} não teria ocorrido de jeito nenhum",
               "mesmo sem {0}, {1} ainda teria ocorrido"),
    "LeReCa": ("{0} é causa juridicamente relevante de {1}",
               "{0} não é causa juridicamente relevante de {1}"),
    "Om": ("a conduta apontada é uma omissão: {0}",
           "a conduta apontada não é uma omissão: {0}"),
    "Obl": ("havia dever jurídico de agir: {0} era conduta obrigatória",
            "não havia dever jurídico de agir: {0} não era conduta obrigatória"),
    "Tortious": ("{0} é conduta ilícita", "{0} não é conduta ilícita"),
    "Unexpected": ("{0} era um evento altamente inesperado",
                   "{0} não era um evento inesperado"),
    "SupersedingCause": ("{0} é causa superveniente, que rompe o nexo anterior",
                         "{0} não é causa superveniente"),
    # Mesma leitura, com os três argumentos que o artigo escreve. A escolha é
    # por aridade, em `_render_lrc_literal`.
    "SupersedingCause/3": ("{0} é causa superveniente: rompe o nexo entre {1} e {2}",
                           "{0} não rompe o nexo entre {1} e {2}"),
    "After": ("{0} ocorreu depois de {1}", "{0} não ocorreu depois de {1}"),
    "Foreseeable": ("{1} era previsível a partir de {0}",
                    "{1} não era previsível a partir de {0}"),
    "ForeseeableRisk": ("{1} é um risco previsível de {0}",
                        "{1} não é um risco previsível de {0}"),
    "Playout": ("{1} é a concretização do risco {0}",
                "{1} não é a concretização do risco {0}"),
}


# ----------------------------------------------------------------------
# Frameworks
# ----------------------------------------------------------------------
def preference_model(case: FormalizedCase):
    """The case's ordering between defeasible arguments, or None.

    One model serves both layers: rule ids are disjoint across them, and a
    dimension the judgment weighs (say, the specificity of the duty to act)
    is the same dimension whichever layer names it.
    """
    return case.preferences.model() if case.preferences is not None else None


def cif_framework(case: FormalizedCase) -> ArgumentationFramework:
    """The cause-in-fact layer, straight from the record's own dicts."""
    return ArgumentationFramework(case.knowledge_base, case.causal_model,
                                  preferences=preference_model(case))


def lrc_framework(case: FormalizedCase) -> Optional[ArgumentationFramework]:
    """The legal-relevance layer, or None when the case has no LRC block."""
    if case.lrc is None or not case.lrc.scheme_rules:
        return None
    return lrc_vocab.build_framework(case.lrc.knowledge_base, case.lrc.causal_model,
                                     preferences=preference_model(case))


def bridge_facts(case: FormalizedCase,
                 af: Optional[ArgumentationFramework] = None) -> BridgeFacts:
    """The cause-in-fact verdicts that feed the LRC layer."""
    af = af or cif_framework(case)
    return evaluate(
        af,
        candidate_literals(case.knowledge_base, case.queries,
                           exclude=non_candidate_codes(case)),
        target_literals(case.effect, case.queries),
    )


def non_candidate_codes(case: FormalizedCase) -> set:
    """Atoms that condition an inference without being candidate causes --
    duties and pieces of evidence (`bridge.NON_CANDIDATE_KINDS`)."""
    return {atom.code for atom in case.atoms if atom.kind in NON_CANDIDATE_KINDS}


# ----------------------------------------------------------------------
# Running the solver back into the record
# ----------------------------------------------------------------------
def annotate(case: FormalizedCase) -> FormalizedCase:
    """Return a copy of `case` with every solver-computed field filled in:
    per-query NESS/but-for, per-query legal relevance, and the LRC
    layer's relevance report."""
    annotated = case.model_copy(deep=True)
    af = cif_framework(annotated)

    for query in annotated.queries:
        query.solver = SolverVerdict(
            ness=af.ness_cause(query.phi, query.psi),
            but_for=af.but_for(query.phi, query.psi),
        )

    lrc_af = lrc_framework(annotated)
    if annotated.lrc is not None and lrc_af is not None:
        annotated.lrc.relevance = lrc_vocab.relevance_report(lrc_af, annotated.lrc.targets)
        justified = lrc_af.justified_conclusions()
        for query in annotated.queries:
            target = lrc_vocab.lereca(query.phi, query.psi)
            if target in annotated.lrc.targets:
                query.legally_relevant = target in justified

    return annotated


# ----------------------------------------------------------------------
# Glosses for the LRC layer
# ----------------------------------------------------------------------
def lrc_atom_glosses(case: FormalizedCase) -> Dict[str, str]:
    """Plain-Portuguese glosses for every literal of the LRC layer, generated
    from the case's own atom glosses plus the paper's fixed vocabulary."""
    if case.lrc is None:
        return {}
    base = case.atom_glosses()
    authored = {p.literal: p.label_pt for p in case.lrc.doctrinal_premises if p.label_pt}

    literals: List[str] = [
        *case.lrc.bridged_premises,
        *(p.literal for p in case.lrc.doctrinal_premises),
        *case.lrc.targets,
    ]
    for rule in case.lrc.scheme_rules:
        body = rule.rule.split(":", 1)[-1]
        head, _, consequent = body.partition("=>")
        literals += [part.strip() for part in head.split(" AND ")]
        literals.append(consequent.strip())

    glosses: Dict[str, str] = {}
    for literal in literals:
        literal = literal.strip()
        if not literal or literal in glosses:
            continue
        if literal in authored:
            glosses[literal] = authored[literal]
            continue
        rendered = _render_lrc_literal(literal, base)
        if rendered:
            glosses[literal] = rendered
        elif literal in base:
            # A qualification rule may read or conclude a plain atom of the
            # case ("regime fechado ⇒ dever específico"). It carries no LRC
            # predicate, so `_render_lrc_literal` declines it -- but the case
            # already says what it means, and repeating the code raw on
            # screen would be the only alternative.
            glosses[literal] = base[literal]

    # `¬<scheme rule>` is what a defence concludes when it undercuts, e.g.
    # `¬cf2lrc_AgrQuad`; `_render_lrc_literal` deliberately leaves those to us.
    for rule in case.lrc.scheme_rules:
        if rule.gloss_pt:
            glosses.setdefault(f"¬{_rule_id(rule.rule)}", undercut_gloss(rule.gloss_pt))
    return glosses


def _render_lrc_literal(literal: str, atom_glosses: Dict[str, str]) -> str:
    negated = literal.startswith("¬")
    split = lrc_vocab.split_lrc_literal(literal)
    if split is None:
        # `¬rN` (an undercut target) or a plain atom: leave to the caller.
        return ""
    predicate, arguments = split
    # Um predicado pode ter mais de uma aridade (`SupersedingCause`), e a
    # frase muda com ela: com um argumento só não há como nomear o nexo que
    # se rompe.
    templates = (_LRC_TEMPLATES.get(f"{predicate}/{len(arguments)}")
                 or _LRC_TEMPLATES.get(predicate))
    if not templates:
        return ""
    glossed = [f"“{atom_glosses.get(arg, arg)}”" for arg in arguments]
    template = templates[1] if negated else templates[0]
    try:
        return template.format(*glossed)
    except IndexError:
        return ""


# ----------------------------------------------------------------------
# Adaptation to CaseSpec
# ----------------------------------------------------------------------
def _query_note(query: Query) -> str:
    label = VERDICT_LABELS.get(query.court_verdict, query.court_verdict)
    rationale = query.court_rationale_pt.strip()
    return f"No acórdão, {label}. {rationale}".strip()


def to_case_spec(case: FormalizedCase) -> CaseSpec:
    """Adapt a formalization record to the shape the renderers already know.

    `case` should have been through `annotate` first; if it has not, the
    solver is run here so `expect_*` is never left guessing.
    """
    if any(q.solver is None for q in case.queries):
        case = annotate(case)

    queries = [
        CausalQuery(
            phi=q.phi, psi=q.psi,
            expect_ness=bool(q.solver and q.solver.ness),
            expect_but_for=bool(q.solver and q.solver.but_for),
            note=_query_note(q),
            note_pt=_query_note(q),
        )
        for q in case.queries
    ]

    preferences = preference_model(case)
    layer = None
    if case.lrc is not None and case.lrc.scheme_rules:
        layer = LRCLayer(
            knowledge_base=case.lrc.knowledge_base,
            causal_model=case.lrc.causal_model,
            targets=list(case.lrc.targets),
            atom_glosses=lrc_atom_glosses(case),
            rule_glosses={
                _rule_id(rule.rule): rule.gloss_pt for rule in case.lrc.scheme_rules
            },
            duty_basis_pt=case.lrc.duty_basis_pt,
        )

    return CaseSpec(
        preferences=preferences,
        id=case.case.id,
        title=case.case.title,
        narrative=case.narrative_pt,
        narrative_pt=case.narrative_pt,
        knowledge_base=case.knowledge_base,
        causal_model=case.causal_model,
        effect=case.effect,
        queries=queries,
        atom_glosses=case.atom_glosses(),
        rule_glosses=case.rule_glosses(),
        lrc=layer,
        origin="dossie",
    )


def _rule_id(rule: str) -> str:
    return rule.split(":", 1)[0].strip()
