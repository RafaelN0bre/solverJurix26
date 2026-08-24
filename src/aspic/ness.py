"""NESS (Necessary Element of a Sufficient Set) causality.

The NESS test, introduced by Hart & Honoré and developed by Wright, says:

    A fact A is a cause of an effect E iff A is a necessary element of a
    set S of conditions which are jointly sufficient for E to be produced
    (S \\ {A} would not be sufficient to produce E).

This is the classical, purely deductive test that motivated the
argumentation-based `ArgumentationFramework.is_cause` in `solver.py`
(Definition 4.3 of the ICAIL 2025 paper). It is deliberately implemented
here as an *independent* algorithm -- forward-chaining sufficiency over the
rule base, with no reference to attacks, defeats or axiom-expansion -- so
that it can be cross-checked against the fuller argumentation-based notion.

The paper is explicit that its notion of a cause goes beyond plain NESS:
besides literals that are *positively* part of a sufficient set (captured
here), it also counts literals whose complement would enable a new
undercutting/rebutting/undermining counterargument (Definition 4.3, case 3
-- e.g. the Childhood Leukaemia example's "¬PaCo"). Plain NESS as
implemented in this module does not detect such cases; see
`tests/test_ness.py::test_leukaemia_beyond_ness` for a worked example of the
gap, and `ArgumentationFramework.is_cause` for the notion that closes it.
"""
from dataclasses import dataclass
from typing import FrozenSet, Iterable, List

from .solver import ArgumentationFramework, Rule


def deductive_closure(premises: FrozenSet[str], rules: Iterable[Rule]) -> FrozenSet[str]:
    """The set of literals derivable from `premises` by repeatedly firing
    rules (strict or defeasible alike) whose antecedents are satisfied.

    This is intentionally monotonic and defeat-agnostic: NESS sufficiency
    is a property of a causal theory T applied to a set of conditions, not
    of what survives dialectical attack (that is the solver's job).
    """
    rules = list(rules)
    closure = set(premises)
    changed = True
    while changed:
        changed = False
        for rule in rules:
            if rule.consequent in closure:
                continue
            if all(antecedent in closure for antecedent in rule.antecedents):
                closure.add(rule.consequent)
                changed = True
    return frozenset(closure)


def is_sufficient(premises: FrozenSet[str], psi: str, rules: Iterable[Rule]) -> bool:
    """Whether `premises`, alone, deductively entail psi via the rule base."""
    return psi in deductive_closure(premises, rules)


@dataclass(frozen=True)
class SufficientSet:
    """A NESS set S for some effect psi: the premises of one particular
    justified argument that concludes psi."""
    elements: FrozenSet[str]
    source_argument_id: str

    def __iter__(self):
        return iter(self.elements)

    def __len__(self) -> int:
        return len(self.elements)

    def __contains__(self, item: str) -> bool:
        return item in self.elements


def sufficient_sets(af: ArgumentationFramework, psi: str, *,
                     justified_only: bool = True) -> List[SufficientSet]:
    """All subset-minimal NESS sets S for effect `psi`.

    Each candidate S is the premise set (Prem(A)) of an argument A
    concluding psi. By default only arguments in the grounded extension are
    considered, matching the paper's framing ("Suppose psi is justified...")
    and correctly excluding causal chains that exist structurally but are
    defeated (e.g. Dlugash's shot in the Double Shooting case, or the brake
    malfunction in the Car Accident case).
    """
    rules = list(af.rules.values())

    if justified_only:
        extension, _ = af.compute_grounded_extension()
        arg_ids = [a for a in extension if af.arguments[a].conclusion == psi]
    else:
        arg_ids = [a for a, arg in af.arguments.items() if arg.conclusion == psi]

    candidates: List[SufficientSet] = []
    for arg_id in arg_ids:
        premises = af.arguments[arg_id].premises
        if is_sufficient(premises, psi, rules):
            candidates.append(SufficientSet(premises, arg_id))

    # Keep only subset-minimal sets (drop S if some other candidate is a
    # proper subset of it -- ASPIC+ arguments shouldn't carry redundant
    # premises in the first place, but this is a cheap independent check).
    minimal = [
        c for c in candidates
        if not any(other.elements < c.elements for other in candidates)
    ]

    seen: set = set()
    unique: List[SufficientSet] = []
    for c in minimal:
        if c.elements in seen:
            continue
        seen.add(c.elements)
        unique.append(c)
    return unique


def necessary_elements(S: SufficientSet, psi: str, rules: Iterable[Rule]) -> FrozenSet[str]:
    """The subset of S each of whose members is individually necessary,
    i.e. S \\ {element} is no longer sufficient for psi.

    For sets coming from `sufficient_sets` this should always equal S in
    full (ASPIC+ arguments carry no redundant premises, Definition 2.6),
    but it is computed independently here rather than assumed.
    """
    rules = list(rules)
    return frozenset(
        element for element in S.elements
        if not is_sufficient(S.elements - {element}, psi, rules)
    )


def is_ness_cause(af: ArgumentationFramework, phi: str, psi: str) -> bool:
    """phi is a NESS cause of psi iff phi is a necessary element of some
    (minimal, justified) sufficient set for psi."""
    rules = list(af.rules.values())
    for S in sufficient_sets(af, psi):
        if phi in S and phi in necessary_elements(S, psi, rules):
            return True
    return False


def ness_report(af: ArgumentationFramework, psi: str) -> str:
    """Human-readable NESS breakdown for psi: every sufficient set found
    and which of its elements are necessary within it."""
    rules = list(af.rules.values())
    sets = sufficient_sets(af, psi)
    if not sets:
        return f"No justified argument concludes '{psi}'."

    lines = [f"NESS analysis for '{psi}':"]
    for i, S in enumerate(sets, start=1):
        necessary = necessary_elements(S, psi, rules)
        lines.append(
            f"  S{i} = {{{', '.join(sorted(S.elements))}}} "
            f"(argument {S.source_argument_id}) -- "
            f"necessary: {{{', '.join(sorted(necessary))}}}"
        )
    return "\n".join(lines)
