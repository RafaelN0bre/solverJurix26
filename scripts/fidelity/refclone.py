"""Ports the reference causal operations over our argumentation framework.
Consumed by the oracle, differential fuzzing and case-sweep runners.
"""

"""Python clone of the authors' reference implementation.

Ports `CausalitySolver.kt` from tuProlog/arg2p-kt
(`causality-solver/src/commonMain/.../CausalitySolver.kt`), running on our
`aspic.solver.ArgumentationFramework` to hold the parser and grounded
extension engine constant across both sides:

- `supporters`/`getSupports` (kt:61-99): a head is included only if `in`, but
  recursion traverses attackers of attackers WITHOUT a head-label filter
  (the breadth called D2 in the audit).
- `checkIntervention` (kt:109-123): support members labelled out/und in the
  expanded graph, collecting attackers labelled `in` (requirement D1).
- `checkCausalityICAIL25` (kt:182-198): nonempty attackers plus minimality:
  no proper subset reproduces all the same attackers.
- `generate_interventions/3` (kt:346-356): family (a), singleton complements,
  and family (c), antecedent subsets of unfired rules containing the
  complement. Family (b), `undercut(S)`, coincides with (a) in our notation:
  compl(r) = “¬r” IS already the undercut literal for r.
- `checkButFor` (kt:202-214).

Structural identity between graphs (Kotlin's `termRepresentation`) uses our
solver's `Argument.signature`, exactly as `ness_cause` does.

Interventions use `axiom_expand` (Def. 4.2). The reference injects a strict
rule with an empty body; the audit verified equivalence
(“axiom-expansion vs strict-empty-body-rule: 0 divergent pairs”).
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from itertools import combinations

from aspic.solver import ArgumentationFramework, negate_literal


class RefGraph:
    """Grounded in/out/und labelling over an ArgumentationFramework."""

    def __init__(self, af: ArgumentationFramework):
        self.af = af
        extension, _ = af.compute_grounded_extension()
        self.in_set = extension
        self.defeaters_of = {}
        for d in af.defeats:
            self.defeaters_of.setdefault(d.attack.target_id, set()).add(
                d.attack.attacker_id)
        self.label = {}
        for aid in af.arguments:
            if aid in extension:
                self.label[aid] = "in"
            elif any(att in extension for att in self.defeaters_of.get(aid, ())):
                self.label[aid] = "out"
            else:
                self.label[aid] = "und"

    def attackers(self, aid):
        return sorted(self.defeaters_of.get(aid, ()))

    def supporters(self, aid, chain):
        # kt:61-76: filter the head by “in”; always recurse.
        if aid in chain:
            return []
        result = [aid] if self.label[aid] == "in" else []
        for att in self.attackers(aid):
            for att2 in self.attackers(att):
                if att2 == aid:
                    continue
                result.extend(self.supporters(att2, chain + [aid]))
        return result

    def get_supports(self, effect):
        # kt:91-99: iterate over EVERY argument concluding effect,
        # with no label filter (D2).
        out = []
        for aid, arg in self.af.arguments.items():
            if arg.conclusion == effect:
                out.extend(self.supporters(aid, []))
        return out

    def signatures(self, aids):
        return {self.af.arguments[a].signature for a in aids}


class ReferenceSolver:
    """Reference ness/3, ness_intervention/2 and but_for/2."""

    def __init__(self, premises, rules, axioms=(), preferences=None):
        self.base_af = ArgumentationFramework(
            {"premises": list(premises), "axioms": list(axioms)},
            {"strict_rules": [], "defeasible_rules": list(rules)},
            preferences=preferences)
        self.base_graph = RefGraph(self.base_af)
        self._expanded = {}
        self._supports = {}

    @classmethod
    def from_framework(cls, af: ArgumentationFramework):
        self = cls.__new__(cls)
        self.base_af = af
        self.base_graph = RefGraph(af)
        self._expanded = {}
        self._supports = {}
        return self

    def _graph_for(self, intervention):
        key = frozenset(intervention)
        if key not in self._expanded:
            self._expanded[key] = RefGraph(self.base_af.axiom_expand(sorted(key)))
        return self._expanded[key]

    def base_supports(self, effect):
        # checkBaseTheory (kt:101-106)
        if effect not in self._supports:
            self._supports[effect] = self.base_graph.signatures(
                self.base_graph.get_supports(effect))
        return self._supports[effect]

    def check_intervention(self, intervention, supports, effect):
        # kt:109-123: IN attackers of out/und support members.
        g = self._graph_for(intervention)
        attackers = set()
        for aid, lab in g.label.items():
            if lab in ("out", "und") and g.af.arguments[aid].signature in supports:
                for att in g.attackers(aid):
                    if g.label[att] == "in":
                        attackers.add(g.af.arguments[att].signature)
        return attackers

    def check_causality_icail25(self, intervention, effect):
        # kt:182-198
        supports = self.base_supports(effect)
        if not supports:
            return False
        attackers = self.check_intervention(intervention, supports, effect)
        if not attackers:
            return False
        if len(intervention) <= 1:
            return True
        for r in range(1, len(intervention)):
            for sub in combinations(intervention, r):
                n = self.check_intervention(list(sub), supports, effect)
                if attackers.issubset(n):
                    return False
        return True

    def check_causality_relaxed(self, intervention, effect):
        """Diagnostic ICAIL25 variant without the IN-attacker requirement.
        The published Def. 4.3 condition only requires support to leave.
        Used solely to classify differences as D1."""
        supports = self.base_supports(effect)
        if not supports:
            return False
        g = self._graph_for(intervention)
        return any(
            lab in ("out", "und") and g.af.arguments[aid].signature in supports
            for aid, lab in g.label.items())

    def _unused_antecedents(self):
        # unused_premises/2 (kt:361-364): antecedents of rules whose id is not
        # the topRule of any base-graph argument. Deduplicate: a
        # subset with repeated literals never satisfies minimality.
        fired = {a.top_rule.id for a in self.base_af.arguments.values()
                 if a.top_rule is not None}
        up = []
        for rid, rule in self.base_af.rules.items():
            if rid not in fired:
                for ant in rule.antecedents:
                    if ant not in up:
                        up.append(ant)
        return up

    def generate_interventions(self, cause):
        # kt:346-356. Family (b) is omitted: it coincides with (a) in our notation.
        cs = negate_literal(cause)
        yield [cs]
        up = self._unused_antecedents()
        if cs in up:
            others = [x for x in up if x != cs]
            for r in range(1, len(others) + 1):
                for combo in combinations(others, r):
                    yield [cs, *combo]

    def ness(self, cause, effect):
        # ness/3: the first generated intervention that passes the check.
        for iv in self.generate_interventions(cause):
            if self.check_causality_icail25(iv, effect):
                return True, tuple(iv)
        return False, None

    def ness_singleton(self, cause, effect):
        """Family (a) only: isolates D1/D2 from the joint-intervention gap."""
        return self.check_causality_icail25([negate_literal(cause)], effect)

    def but_for(self, cause, effect):
        # kt:202-214
        base_in = any(
            self.base_graph.label[aid] == "in" and arg.conclusion == effect
            for aid, arg in self.base_af.arguments.items())
        if not base_in:
            return False
        g = self._graph_for([negate_literal(cause)])
        return not any(
            g.label[aid] == "in" and arg.conclusion == effect
            for aid, arg in g.af.arguments.items())


class OursEval:
    """Our solver's `ness_cause`/`but_for`, caching expansions for the sweep.
    Replicates solver.py:685-744 and :746-773 literally."""

    def __init__(self, af: ArgumentationFramework):
        self.af = af
        self._support_sigs = {}
        self._expanded_sigs = {}
        self._expanded_concl = {}
        self._base_concl = None

    def support_signatures(self, psi):
        if psi not in self._support_sigs:
            support = self.af.support_set(psi)
            self._support_sigs[psi] = {
                self.af.arguments[a].signature for a in support} if support else set()
        return self._support_sigs[psi]

    def _expansion(self, phi):
        lit = negate_literal(phi)
        if lit not in self._expanded_sigs:
            expanded = self.af.axiom_expand([lit])
            ext, _ = expanded.compute_grounded_extension()
            self._expanded_sigs[lit] = {expanded.arguments[a].signature for a in ext}
            self._expanded_concl[lit] = {expanded.arguments[a].conclusion for a in ext}
        return self._expanded_sigs[lit], self._expanded_concl[lit]

    def ness_cause(self, phi, psi):
        original = self.support_signatures(psi)
        if not original:
            return False
        new_sigs, _ = self._expansion(phi)
        return not original.issubset(new_sigs)

    def but_for(self, phi, psi):
        if self._base_concl is None:
            self._base_concl = self.af.justified_conclusions()
        if psi not in self._base_concl:
            return False
        _, new_concl = self._expansion(phi)
        return psi not in new_concl
