"""The determinism boundary between the two layers of the formalization.

The ICAIL 2026 legal-relevance module takes the *output* of the cause-in-fact
evaluation as its premises. Those premises are computed here, by running the
solver, and are never authored by the LLM: asking a model to restate which
literals turned out to be causes would let a formalization claim legal
relevance for something the counterfactual test never established, which is
precisely the failure mode this pipeline exists to rule out. The model only
supplies the doctrinal premises (`Om_*`, `Obl_*`, ...) and the instantiated
rule schemes; the `CaFa_*`/`ButFor_*` facts are the solver's word.

This mirrors how `tests/test_legally_relevant_causes_2026.py` hand-feeds
`CaFa_x_y` premises for the paper's worked examples -- same literals, same
naming convention (`aspic.lrc`), derived instead of typed.
"""
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set

from aspic import lrc
from aspic.solver import ArgumentationFramework


@dataclass(frozen=True)
class CausalFact:
    """Both notions' verdicts on one (phi, psi) pair, as the solver computed
    them, plus the LRC literals they license."""
    phi: str
    psi: str
    ness: bool
    but_for: bool

    @property
    def cafa_literal(self) -> str:
        return lrc.cafa(self.phi, self.psi)

    @property
    def but_for_literal(self) -> str:
        return lrc.but_for(self.phi, self.psi)


@dataclass
class BridgeFacts:
    """Everything the LRC layer inherits from the cause-in-fact layer."""
    facts: List[CausalFact] = field(default_factory=list)

    @property
    def causes(self) -> List[CausalFact]:
        """The pairs that are causes in fact -- i.e. NESS causes.

        NESS and not but-for: but-for is strictly stronger, so keying the
        bridge on it would drop every overdetermined cause (each asbestos
        exposure, Bush's shot) out of the legal-relevance layer entirely,
        which is the result Fairchild exists to reject.
        """
        return [f for f in self.facts if f.ness]

    def premises(self) -> List[str]:
        """The `CaFa_*` and `ButFor_*` literals, in a stable order."""
        literals: List[str] = []
        for fact in self.facts:
            if fact.ness:
                literals.append(fact.cafa_literal)
            if fact.but_for:
                literals.append(fact.but_for_literal)
        return list(dict.fromkeys(literals))

    def lereca_targets(self) -> List[str]:
        return list(dict.fromkeys(lrc.lereca(f.phi, f.psi) for f in self.causes))

    def as_records(self) -> List[Dict]:
        return [
            {
                "phi": f.phi, "psi": f.psi,
                "ness": f.ness, "but_for": f.but_for,
                "cafa_literal": f.cafa_literal if f.ness else None,
                "but_for_literal": f.but_for_literal if f.but_for else None,
            }
            for f in self.facts
        ]

    def render_for_prompt(self, glosses: Dict[str, str] = None) -> str:
        """The markdown block the LRC prompt sees: only established facts, with
        the plain-Portuguese gloss of each side so the model can match them to
        the judgment without re-deriving them."""
        glosses = glosses or {}
        if not self.causes:
            return (
                "Nenhuma causa de fato foi estabelecida pelo solver neste caso. "
                "Não há `CaFa_*` disponível, portanto não escreva nenhuma regra "
                "`cf2lrc_*` e devolva listas vazias."
            )
        lines = [
            "Literais já presentes na base de conhecimento da camada de relevância jurídica:",
            "",
        ]
        for fact in self.causes:
            phi_gloss = glosses.get(fact.phi, fact.phi)
            psi_gloss = glosses.get(fact.psi, fact.psi)
            lines.append(
                f"- `{fact.cafa_literal}` — “{phi_gloss}” é causa de fato de “{psi_gloss}”."
            )
            if fact.but_for:
                lines.append(
                    f"- `{fact.but_for_literal}` — e é também causa \"não fosse por\" "
                    "(sem ela o resultado não ocorreria de jeito nenhum)."
                )
        rejected = [f for f in self.facts if not f.ness]
        if rejected:
            lines += [
                "",
                "Pares testados que o solver **não** reconheceu como causa de fato "
                "(não existe `CaFa_*` para eles; não escreva regra que os use):",
                "",
            ]
            lines += [f"- {f.phi} → {f.psi}" for f in rejected]
        return "\n".join(lines)


#: Atom kinds that condition an inference without ever being a candidate
#: cause. A duty is what makes a conduct imputable, and a piece of evidence is
#: what lets a fact be held established -- asking whether "the duty of custody
#: caused the death" or "the expert report caused the injury" is a category
#: error, and it is one a conjunctive causal rule produces mechanically: with
#: `r0: Conduct AND Duty => Link`, every antecedent comes out of the solver as
#: a cause in fact, and the legal-relevance layer then has to write a
#: `cf2lrc_Duty` for it.
NON_CANDIDATE_KINDS = frozenset({"dever", "prova"})


def candidate_literals(knowledge_base: Dict, queries: Iterable,
                       exclude: Optional[Set[str]] = None) -> List[str]:
    """The phi side of every pair worth testing: the premises of the framework
    plus whatever the case's own causal questions ask about (an omission's
    `¬X` is a question even though only `X` may be a premise).

    `exclude` drops literals that are premises but not candidate causes --
    see `NON_CANDIDATE_KINDS`. A literal the case *asks about* is never
    dropped: if the dossier poses the question, it gets answered.
    """
    excluded = exclude or set()
    # Compared on the base literal: `exclude` names atom *codes*, and a
    # premise may be a negation of one. Asking whether "the State did not
    # take the appropriate measures caused the death" is the same category
    # error as asking it of the measures themselves.
    candidates = [c for c in knowledge_base.get("premises", [])
                  if (c[1:] if c.startswith("¬") else c) not in excluded]
    candidates += [getattr(q, "phi", None) or q["phi"] for q in queries]
    return list(dict.fromkeys(c for c in candidates if c))


def target_literals(effect: str, queries: Iterable) -> List[str]:
    targets = [effect] if effect else []
    targets += [getattr(q, "psi", None) or q["psi"] for q in queries]
    return list(dict.fromkeys(t for t in targets if t))


def evaluate(af: ArgumentationFramework, candidates: Sequence[str],
             targets: Sequence[str]) -> BridgeFacts:
    """Run the three cause-in-fact notions over every (candidate, target) pair.

    A literal is never tested against itself, and a target that is not
    justified in the first place is skipped -- `ness_cause` and `but_for` both
    return False there anyway, and listing those pairs would only add noise to
    the LRC prompt.
    """
    justified = af.justified_conclusions()
    facts: List[CausalFact] = []
    for psi in targets:
        if psi not in justified:
            continue
        for phi in candidates:
            if phi == psi:
                continue
            facts.append(CausalFact(
                phi=phi,
                psi=psi,
                ness=af.ness_cause(phi, psi),
                but_for=af.but_for(phi, psi),
            ))
    return BridgeFacts(facts=facts)
