"""The ASPIC+ engine package: the solver, the causal tests, the
legal-relevance vocabulary and the preference orderings. Every other package
builds on it -- `formalize` assembles its input, `cases` and `analysis` run
it, `interface` renders what it computes.
"""

"""The ASPIC+ engine: argumentation solver, causal notions (NESS / but-for),
the legal-relevance vocabulary, and preferences between arguments.

This package is the reimplementation of the theory of the two papers --
Pisano, Prakken, Sartor & Liepina (ICAIL 2025) and Pisano, Prakken & Sartor
(ICAIL 2026) -- and nothing else: no case data (`cases`), no per-perspective
analysis (`analysis`), no rendering (`interface`), no formalization
machinery (`formalize`). Its four modules:

* `solver` -- the ASPIC+ framework proper: arguments, attacks, defeats, the
  grounded extension, and the two causal tests (`ness_cause`, `but_for`);
* `sufficiency` -- sufficient sets, the *why* behind a NESS verdict;
* `lrc` -- vocabulary and helpers for the legally-relevant-causation layer;
* `preferences` -- argument orderings refined from doctrinal dimensions.
"""
from .solver import (
    ArgumentationFramework,
    Argument,
    Attack,
    Defeat,
    Literal,
    Rule,
    negate_literal,
)
from .sufficiency import (
    SufficientSet,
    deductive_closure,
    is_sufficient,
    necessary_elements,
    sufficiency_report,
    sufficient_sets,
)
from .preferences import Dimension, PreferenceModel, RuleProfile, resolved_conflicts

__all__ = [
    "ArgumentationFramework",
    "Argument",
    "Attack",
    "Defeat",
    "Literal",
    "Rule",
    "negate_literal",
    "SufficientSet",
    "deductive_closure",
    "is_sufficient",
    "necessary_elements",
    "sufficiency_report",
    "sufficient_sets",
    "Dimension",
    "PreferenceModel",
    "RuleProfile",
    "resolved_conflicts",
]
