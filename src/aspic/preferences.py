"""Preference orderings between defeasible arguments, computed from a
declared tuple of doctrinal dimensions. Loaded from
`FormalizedCase.preferences` by `formalize.build` and passed into
`aspic.solver.ArgumentationFramework`, where it refines only the
preference-dependent defeats (rebut/undermine); `interface.preference_view`
renders its numbers.
"""

"""Preferences between defeasible arguments, computed from a tuple of
doctrinal dimensions.

The solver's default ordering is the paper's *basic* one
(`aspic.solver.ArgumentationFramework._is_weaker`, Definition 2.11): a
strict-and-firm argument is never weaker than anything, and two defeasible
arguments are **incomparable**. Incomparability is a deliberate choice, and
it has a consequence the interface has to keep saying out loud: a mutual
rebut leaves both sides UNDEC, so a judgment whose ratio is "this reason
prevails over that one" cannot be reproduced as a rebut -- only as an
undercut (see `docs/formalizacao.md`, "The modeling restriction that determines the
outcome").

That is the right default for the ICAIL cases, which are built exactly that
way. It is *not* enough for a judgment that resolves a head-on conflict of
qualifications by weighing reasons, which is what
`docs/formalizacao.md`'s Case 003 does at ⟨q0, q2⟩: the specific duty of
custody against the generic duty of public security, two rules concluding
complementary literals, with no undercut on either side. Somebody has to be
preferred, and ASPIC+ has the room for it: Definition 2.10 makes rebutting
and undermining defeat *preference-dependent*, and only undercutting
preference-independent.

This module supplies the missing preorder, following Modgil & Prakken, "A
general account of argumentation with preferences" (AIJ 195, 2013) --
Definition 19 for comparing two sets, Definition 20 for last-link and
Definition 21 for weakest-link. It computes the ranking from an explicit,
auditable tuple rather than from a bare number:

* a **dimension** is one doctrinal axis the judgment weighs (for Case 003:
  the specificity of the duty to act, the causal intervention of a later
  event, the autonomy of the third party who acted), each with the weight the
  reader assigns to it;
* a **profile** says which dimensions one element invokes -- a defeasible
  rule *or an ordinary premise*, both, because Definition 21 compares
  `Prem_p` and `DefRules` together;
* an element's **strength** is the weighted sum ``Σ_d weight_d · coefficient_d``.
  An element the case did not rank has no position in the preorder at all,
  and one such element is enough to make its whole set incomparable;
* the **ordering** is the set comparison, `elitist` by default (one element
  of the weaker set below every element of the stronger), which is ASPIC+'s
  default and the reference implementation's (`orderingComparator(elitist)`).

**What this module used to do, and why it was wrong.** It scored an argument
by aggregating its *defeasible rules only*, and compared the two scalars.
Definition 21 clause 3 requires `Prem_p(B) ◁ Prem_p(A)` **and**
`DefRules(B) ◁ DefRules(A)`; dropping a conjunct can only make a preference
hold in *more* cases, so the old reading declared orderings where canonical
ASPIC+ declares none. Modgil & Prakken call the premise-ignoring version "an
anomaly" they set out to correct. It also treated an unprofiled rule as
skippable, which is not conservative either -- skipping versus counting it
inverted the verdict of a three-rule theory.

A framework whose elements carry no profile behaves exactly as it did before
the module existed: nothing precedes anything, the basic ordering decides.
The preference model is strictly additive in that sense -- but *not* in the
sense of being free: a case that wants the weights to decide has to rank
everything the conflicting arguments are built from, premises included.

Nothing here inspects the *content* of a rule: the profile is data supplied
with the case (`FormalizedCase.preferences`), so the weighing is part of the
formalization the reader can audit and change, not a heuristic buried in the
solver. `sensitivity` exists for exactly that: it reports the weight at which
a given conflict would flip.

Who *moves* the ordering is `PreferenceBlock.perspective`, and
`analysis.perspectives` honours it: a projection that has not admitted that
voice runs under the basic ordering. In Prakken's adjudication model a
priority argument is a move of the decision phase, so an ordering that
applied from step 0 would let a preference settle a dispute between the
parties on nobody's authority.
"""
from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

#: Aggregation principles. The first two are ASPIC+'s own (Modgil & Prakken,
#: "A general account of argumentation with preferences", §4); `sum` is not,
#: and is offered because a court that stacks three independent reasons
#: against one is doing something a min() cannot express.
WEAKEST_LINK = "weakest"
LAST_LINK = "last"
PRINCIPLES = (WEAKEST_LINK, LAST_LINK)

PRINCIPLE_LABELS = {
    WEAKEST_LINK: "elo mais fraco (weakest-link, Def. 21): compara as premissas "
                  "ordinárias E as regras derrotáveis dos dois argumentos",
    LAST_LINK: "último elo (last-link, Def. 20): compara as últimas regras "
               "derrotáveis aplicadas, e só cai nas premissas quando não há "
               "regra derrotável de nenhum dos lados",
}

#: Definition 19 set comparators. `elitist` is the ASPIC+ default and
#: the reference implementation's default (`orderingComparator(elitist)`).
ELITIST = "elitist"
DEMOCRAT = "democrat"
COMPARATORS = (ELITIST, DEMOCRAT)

COMPARATOR_LABELS = {
    ELITIST: "elitista: basta um elemento de B ser mais fraco que todos os de A",
    DEMOCRAT: "democrata: todo elemento de B tem de ser mais fraco que algum de A",
}


@dataclass(frozen=True)
class Dimension:
    """One axis on which the judgment weighs reasons."""
    key: str
    label_pt: str
    weight: float
    rationale_pt: str = ""


@dataclass(frozen=True)
class RuleProfile:
    """Which dimensions a rule invokes, and how strongly.

    `coefficients` maps a dimension key to a multiplier -- 0 or 1 in every
    case modelled so far, but nothing here requires that. A profile whose
    coefficients are all zero (or empty) is neutral, and the rule is skipped
    when aggregating: a step that merely draws out a consequence of what is
    already established adds no weight of its own to the argument.
    """
    rule_id: str
    coefficients: Dict[str, float]
    rationale_pt: str = ""

    @property
    def is_neutral(self) -> bool:
        return not any(self.coefficients.values())


@dataclass(frozen=True)
class Comparison:
    """The result of comparing two arguments, with everything the interface
    needs to say *why* -- including the rules that carried the weight."""
    left: Optional[float]
    right: Optional[float]
    verdict: str            # "left", "right" or "incomparable"
    left_rules: Tuple[str, ...] = ()
    right_rules: Tuple[str, ...] = ()

    @property
    def decided(self) -> bool:
        return self.verdict in ("left", "right")


class PreferenceModel:
    """A preorder on arguments, built from weighted dimensions and per-rule
    profiles. Immutable: `with_weights` returns a new model, which is what
    makes `sensitivity` cheap and side-effect free."""

    def __init__(self, dimensions: Sequence[Dimension],
                 profiles: Iterable[RuleProfile] = (),
                 principle: str = WEAKEST_LINK,
                 comparator: str = ELITIST):
        if principle not in PRINCIPLES:
            raise ValueError(
                f"princípio de agregação desconhecido: {principle!r} "
                f"(use um de {', '.join(PRINCIPLES)})")
        if comparator not in COMPARATORS:
            raise ValueError(
                f"comparador de conjuntos desconhecido: {comparator!r} "
                f"(use um de {', '.join(COMPARATORS)})")
        self.dimensions: Tuple[Dimension, ...] = tuple(dimensions)
        self.principle = principle
        self.comparator = comparator
        self.profiles: Dict[str, RuleProfile] = {p.rule_id: p for p in profiles}
        unknown = {
            key
            for profile in self.profiles.values()
            for key, coefficient in profile.coefficients.items()
            if coefficient and key not in {d.key for d in self.dimensions}
        }
        if unknown:
            raise ValueError(
                "perfil de regra cita dimensões que não existem: "
                f"{', '.join(sorted(unknown))}")

    # ------------------------------------------------------------------
    # Weights and strengths
    # ------------------------------------------------------------------
    @property
    def weights(self) -> Dict[str, float]:
        return {d.key: d.weight for d in self.dimensions}

    def tuple_for(self, rule_id: str) -> Tuple[float, ...]:
        """The rule's coefficients as a tuple, in dimension order -- the
        `⟨specific duty, causal intervention, autonomy⟩` a reader of the
        formalization sees written out."""
        profile = self.profiles.get(rule_id)
        if profile is None:
            return tuple(0.0 for _ in self.dimensions)
        return tuple(float(profile.coefficients.get(d.key, 0.0))
                     for d in self.dimensions)

    def rule_strength(self, rule_id: str) -> Optional[float]:
        """`Σ_d weight_d · coefficient_d`, or None for an unprofiled or
        neutral rule."""
        profile = self.profiles.get(rule_id)
        if profile is None or profile.is_neutral:
            return None
        weights = self.weights
        return float(sum(weights[key] * coefficient
                         for key, coefficient in profile.coefficients.items()
                         if coefficient))

    def contributing_rules(self, rule_ids: Sequence[str]) -> List[str]:
        """The elements of an argument that carry weight, in order."""
        return [rule_id for rule_id in rule_ids
                if self.rule_strength(rule_id) is not None]

    @staticmethod
    def last_defeasible_rules(argument) -> List[str]:
        """`LastDefRules(A)` (Modgil & Prakken, Def. 20).

        Empty for an atomic argument; `{top rule}` when the top rule is
        defeasible; the **union** of the sub-arguments' last defeasible rules
        when it is strict. A *set* -- never "the last item of a list", which
        is what this used to read and which made the answer depend on the
        order the antecedents happen to be written in.
        """
        if argument.top_rule is None:
            return []
        if not argument.top_rule.is_strict:
            return [argument.top_rule.id]
        out: List[str] = []
        for sub in argument.sub_arguments:
            for rule_id in PreferenceModel.last_defeasible_rules(sub):
                if rule_id not in out:
                    out.append(rule_id)
        return out

    def argument_strength(self, argument) -> Optional[float]:
        """An indicative scalar for the interface, **not** the ordering.

        The ordering is a comparison between *sets* (Def. 19), and a set does
        not collapse to a number without losing exactly the information the
        definition uses. This is the weakest carrying element, which is what a
        reader wants next to an argument in a table; `compare` is what decides.
        """
        keys = (self.last_defeasible_rules(argument)
                if self.principle == LAST_LINK
                else list(argument.defeasible_rules) + sorted(argument.ordinary_premises))
        scored = [self.rule_strength(key) for key in self.contributing_rules(keys)]
        return min(scored) if scored else None

    # ------------------------------------------------------------------
    # Definition 19: comparing two sets of elements
    # ------------------------------------------------------------------
    def precedes(self, left: Sequence[str], right: Sequence[str]) -> bool:
        """`Γ ◁ₛ Γ′` (Def. 19), over sets of rule ids and/or premise literals.

        Clauses 1 and 2 are the paper's: the empty set never precedes, and a
        non-empty set precedes the empty one. Then `elitist` asks for one
        element of `Γ` below *every* element of `Γ′`, `democrat` for every
        element of `Γ` below *some* element of `Γ′`.

        An element the case did not rank has no position in the preorder, so
        `X < Y` is false for every pair it appears in. One unranked element on
        the right is therefore enough to defeat the elitist clause -- which is
        the honest reading of "incomparable", and the reason a case that wants
        the weights to decide has to rank *everything* the conflicting
        arguments are built from, not only the rules that carry the doctrine.
        """
        if not left:
            return False
        if not right:
            return True
        lhs = [self.rule_strength(key) for key in left]
        rhs = [self.rule_strength(key) for key in right]

        def below(x: Optional[float], y: Optional[float]) -> bool:
            return x is not None and y is not None and x < y

        if self.comparator == ELITIST:
            return any(all(below(x, y) for y in rhs) for x in lhs)
        return all(any(below(x, y) for y in rhs) for x in lhs)

    # ------------------------------------------------------------------
    # The ordering
    # ------------------------------------------------------------------
    def _precedes_argument(self, weaker, stronger) -> bool:
        """`B ≺ A` under the declared principle (Def. 20 or Def. 21)."""
        prem_b = sorted(weaker.ordinary_premises)
        prem_a = sorted(stronger.ordinary_premises)

        if self.principle == LAST_LINK:
            last_b = self.last_defeasible_rules(weaker)
            last_a = self.last_defeasible_rules(stronger)
            if self.precedes(last_b, last_a):
                return True
            return not last_b and not last_a and self.precedes(prem_b, prem_a)

        # Definition 21, all three clauses.
        rules_b = list(weaker.defeasible_rules)
        rules_a = list(stronger.defeasible_rules)
        if not rules_b and not rules_a:              # both strict
            return self.precedes(prem_b, prem_a)
        if not prem_b and not prem_a:                # both firm
            return self.precedes(rules_b, rules_a)
        return self.precedes(prem_b, prem_a) and self.precedes(rules_b, rules_a)

    def compare(self, left, right) -> Comparison:
        """Compare two arguments. `verdict` is which side is *stronger*.

        The verdict comes from the set comparison, not from the scalars: the
        scalars are shown alongside because a table needs a number, but two
        arguments with different scalars can still be incomparable, and two
        with the same scalar can still be ordered.
        """
        left_weaker = self._precedes_argument(left, right)
        right_weaker = self._precedes_argument(right, left)
        if left_weaker and not right_weaker:
            verdict = "right"
        elif right_weaker and not left_weaker:
            verdict = "left"
        else:
            verdict = "incomparable"
        return Comparison(
            left=self.argument_strength(left), right=self.argument_strength(right),
            verdict=verdict,
            left_rules=tuple(self.contributing_rules(
                list(left.defeasible_rules) + sorted(left.ordinary_premises))),
            right_rules=tuple(self.contributing_rules(
                list(right.defeasible_rules) + sorted(right.ordinary_premises))))

    def is_weaker(self, a, b) -> bool:
        """`A ≺ B`, by Definition 20 or 21."""
        return self._precedes_argument(a, b) and not self._precedes_argument(b, a)

    def explain(self, a, b) -> str:
        """One line saying how the two compare, for a tooltip or a table."""
        comparison = self.compare(a, b)
        if comparison.verdict == "incomparable":
            if not comparison.left_rules or not comparison.right_rules:
                return ("sem preferência aplicável: ao menos um dos argumentos "
                        "não tem elemento classificado, então os dois seguem "
                        "incomparáveis")
            return ("incomparáveis: nenhum dos dois precede o outro sob a "
                    f"{PRINCIPLE_LABELS.get(self.principle, self.principle)}")
        stronger, weaker = ((a, b) if comparison.verdict == "left" else (b, a))
        high, low = ((comparison.left, comparison.right)
                     if comparison.verdict == "left"
                     else (comparison.right, comparison.left))
        detalhe = ""
        if high is not None and low is not None:
            detalhe = f" ({low:g} < {high:g} no elo mais fraco)"
        return (f"{stronger.id} prevalece sobre {weaker.id} por "
                f"{self.principle}/{self.comparator}{detalhe}")

    # ------------------------------------------------------------------
    # Sensitivity
    # ------------------------------------------------------------------
    def with_weights(self, **overrides: float) -> "PreferenceModel":
        """A copy with some dimension weights replaced."""
        dimensions = [replace(d, weight=float(overrides.get(d.key, d.weight)))
                      for d in self.dimensions]
        return PreferenceModel(dimensions, self.profiles.values(),
                               self.principle, self.comparator)

    def with_principle(self, principle: str) -> "PreferenceModel":
        return PreferenceModel(self.dimensions, self.profiles.values(), principle,
                               self.comparator)

    def with_comparator(self, comparator: str) -> "PreferenceModel":
        return PreferenceModel(self.dimensions, self.profiles.values(),
                               self.principle, comparator)

    def as_dict(self) -> Dict[str, object]:
        return {
            "principle": self.principle,
            "principle_pt": PRINCIPLE_LABELS.get(self.principle, self.principle),
            "comparator": self.comparator,
            "comparator_pt": COMPARATOR_LABELS.get(self.comparator, self.comparator),
            "dimensions": [
                {"key": d.key, "label_pt": d.label_pt, "weight": d.weight,
                 "rationale_pt": d.rationale_pt}
                for d in self.dimensions
            ],
            "profiles": [
                {"rule": profile.rule_id,
                 "coefficients": dict(profile.coefficients),
                 "tuple": list(self.tuple_for(profile.rule_id)),
                 "strength": self.rule_strength(profile.rule_id),
                 "rationale_pt": profile.rationale_pt}
                for profile in self.profiles.values()
            ],
        }


# ----------------------------------------------------------------------
# Reading the ordering off a framework
# ----------------------------------------------------------------------
def resolved_conflicts(af) -> List[Dict[str, object]]:
    """Every rebut/undermine of `af` whose outcome a preference decided.

    Undercuts are excluded on purpose: ASPIC+ Definition 2.10 makes them
    preference-independent, so listing them here would suggest the weights do
    work they do not do. What is reported is exactly the set of attacks whose
    success or failure would change if the weights changed -- which is the
    honest answer to "where did these numbers matter?".
    """
    model = getattr(af, "preferences", None)
    if model is None:
        return []
    succeeded = {id(defeat.attack) for defeat in af.defeats}
    rows: List[Dict[str, object]] = []
    # One row per (attacker, attacked sub-argument, kind): an attack on a
    # compound argument is registered once against the whole and once against
    # the sub-argument it lands on, and both readings compare exactly the same
    # pair of arguments -- listing them twice would double every conflict.
    seen: Set[Tuple[str, str, str]] = set()
    for attack in af.attacks:
        if attack.attack_type == "undercut":
            continue
        attacker = af.arguments[attack.attacker_id]
        target = af.arguments[attack.target_subargument_id]
        key = (attacker.id, target.id, attack.attack_type)
        if key in seen:
            continue
        comparison = model.compare(attacker, target)
        if not comparison.decided:
            continue
        seen.add(key)
        rows.append({
            "attacker": attacker.id,
            "attacker_conclusion": attacker.conclusion,
            "attacker_rules": list(comparison.left_rules),
            "attacker_strength": comparison.left,
            "target": target.id,
            "target_conclusion": target.conclusion,
            "target_rules": list(comparison.right_rules),
            "target_strength": comparison.right,
            "type": attack.attack_type,
            "attack_succeeded": id(attack) in succeeded,
            "explanation_pt": model.explain(attacker, target),
        })
    return rows


def sensitivity(build_framework, model: PreferenceModel, dimension: str,
                probe: Sequence[float], reading) -> List[Dict[str, object]]:
    """How the case reads as one dimension's weight moves.

    `build_framework(model)` returns a framework built under a given
    preference model, and `reading(af)` extracts whatever the caller wants to
    watch (a justified literal, a relevance verdict, a whole labelling). The
    table this produces is the answer to the only question a reader has about
    a number somebody chose: *what would have to be different for the case to
    come out the other way?*
    """
    rows = []
    for weight in probe:
        probed = model.with_weights(**{dimension: weight})
        rows.append({
            "dimension": dimension,
            "weight": weight,
            "reading": reading(build_framework(probed)),
        })
    return rows


def flip_point(rows: Sequence[Dict[str, object]]) -> Optional[Dict[str, object]]:
    """The first row of a `sensitivity` table whose reading differs from the
    first row's -- the weight at which the case turns, or None if it never
    does over the probed range."""
    if not rows:
        return None
    baseline = rows[0]["reading"]
    for row in rows[1:]:
        if row["reading"] != baseline:
            return row
    return None
