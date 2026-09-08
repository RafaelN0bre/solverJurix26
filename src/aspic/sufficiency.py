"""Sufficient sets: *why* a NESS verdict came out the way it did.

The NESS test -- Hart & Honoré's, developed by Wright -- says:

    A fact A is a cause of an effect E iff A is a necessary element of a
    set S of conditions which are jointly sufficient for E to be produced
    (S \\ {A} would not be sufficient to produce E).

The **verdict** lives in `ArgumentationFramework.ness_cause`, which is the
papers' own reading of that test over a defeasible theory (Definition 4.3 of
ICAIL 2025 / Definition 3.4 of ICAIL 2026, and `ness/3` in the authors'
implementation). This module does not re-decide it. What it supplies is the
*decomposition* the verdict is silent about: which sets of conditions are in
fact sufficient for the effect, and which members of each are individually
necessary. That is what makes a NESS answer readable -- "é causa" is a
verdict, "porque {Ex1, Ex2} basta e sem Ex1 não basta" is an explanation.

Everything here is forward-chaining over the rule base: monotonic,
defeat-agnostic, and deliberately independent of attacks and axiom-expansion.
Sufficiency is a property of a causal theory applied to a set of conditions,
not of what survives dialectical attack -- that is the solver's job.

**Historical note.** This module used to export `is_ness_cause`, a third
causal verdict standing beside `is_cause` and `but_for`. It was removed, for
two reasons. It was not in the papers -- the authors' implementation
(`tuProlog/arg2p-kt`) has `ness/3` and `but_for/2` and nothing else, and
their `ness/3` is what this repository used to call `is_cause`. And it could
not answer at all for a *derived* literal: it looked for phi inside an
argument's premise set, so `Latrocinio` -- a conclusion, not a premise --
came back "not a cause" when the honest answer was "this test does not
apply". A verdict that says "no" when it means "I cannot tell" is worse than
no verdict.
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


def sufficiency_report(af: ArgumentationFramework, psi: str) -> str:
    """Human-readable breakdown for psi: every sufficient set found and
    which of its elements are necessary within it.

    Explanatory only. Whether a literal *is* a cause is
    `ArgumentationFramework.ness_cause`'s answer, not this one's.
    """
    rules = list(af.rules.values())
    sets = sufficient_sets(af, psi)
    if not sets:
        return f"No justified argument concludes '{psi}'."

    lines = [f"Sufficient sets for '{psi}':"]
    for i, S in enumerate(sets, start=1):
        necessary = necessary_elements(S, psi, rules)
        lines.append(
            f"  S{i} = {{{', '.join(sorted(S.elements))}}} "
            f"(argument {S.source_argument_id}) -- "
            f"necessary: {{{', '.join(sorted(necessary))}}}"
        )
    return "\n".join(lines)
