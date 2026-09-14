"""Checks complete, acyclic argument construction in `aspic.solver`.
Protects rule-order invariance and the causal results of axiom expansion.
"""

"""Regression tests for argument construction (Definition 2.6 + Section 2.2).

Construction must reach a fixpoint of *arguments*, not merely of
conclusions: an earlier stop on conclusion-set stability made the argument
set depend on rule order, and an axiom-expanded framework could silently
lack derivations its base framework had -- yielding spurious NESS verdicts
(the support "leaves" the extension because it was never built). Found by
differential fuzzing against the authors' reference implementation
(2026-09-13, 3 of 16,504 pairs; harness in `scripts/fidelity/`).
Termination on cyclic theories is the acyclic-chaining guard's job, not
the loop's: no argument may re-derive a conclusion already drawn inside
its own derivation.
"""
from aspic.solver import ArgumentationFramework

#: Fuzz theory 29 (seed 20260913), the minimal found counterexample of the
#: old conclusion-fixpoint stop.
KB = {"premises": ["a", "c", "e", "¬f"], "axioms": []}
RULES = ["r0: c AND ¬a => d", "r1: ¬d AND a => e", "r2: a AND b => d",
         "r3: c AND a => ¬d", "r4: ¬a => ¬b"]
#: The derivation of `e` that chains r1 on top of r3's ¬d.
TARGET = (frozenset({"a", "c"}), "e", ("r1", "r3"), ())


def model(rules):
    return {"strict_rules": [], "defeasible_rules": list(rules)}


def signatures(af):
    return {a.signature for a in af.arguments.values()}


def test_axiom_expansion_keeps_every_base_argument():
    """Axiom expansion only ever adds knowledge, so every argument of the
    base framework must still be constructible in the expanded one. Under
    the old stop it was not: with ¬d as an axiom, r1 fires from the axiom
    in the first pass, the pass adds no new *conclusion*, construction
    halts, and the (r1, r3) derivation of `e` was never built."""
    base = ArgumentationFramework(KB, model(RULES))
    expanded = base.axiom_expand(["¬d"])
    assert TARGET in signatures(base)
    assert signatures(base) <= signatures(expanded)


def test_construction_is_rule_order_invariant():
    """The same theory must build the same argument set no matter how its
    rules are ordered -- the declaration order carried semantics before."""
    reordered = [RULES[3], RULES[0], RULES[1], RULES[2], RULES[4]]
    assert signatures(ArgumentationFramework(KB, model(RULES))) == \
        signatures(ArgumentationFramework(KB, model(reordered)))


def test_no_spurious_ness_verdict_from_a_missing_derivation():
    """ness(d, e) is False here: intervening with ¬d leaves every support
    member of `e` justified (nothing can derive d, so both the premise
    argument and the r1+r3 chain stay in). The truncated construction
    answered True, because the r1+r3 chain vanished from the expanded
    framework and the support looked broken."""
    af = ArgumentationFramework(KB, model(RULES))
    assert af.ness_cause("d", "e") is False


def test_cyclic_theory_terminates_with_only_acyclic_arguments():
    """Section 2.2: inferences chain into *acyclic* graphs. On a two-rule
    cycle the construction must stop at the premise and one application of
    c1 -- and not build p-via-c1+c2, which re-derives its own conclusion."""
    af = ArgumentationFramework({"premises": ["p"], "axioms": []},
                                model(["c1: p => q", "c2: q => p"]))
    assert sorted((a.conclusion, tuple(sorted(a.defeasible_rules)))
                  for a in af.arguments.values()) == [("p", ()), ("q", ("c1",))]
