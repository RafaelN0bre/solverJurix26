"""Preferences between defeasible arguments, computed from a tuple of
doctrinal dimensions.

The solver's default ordering is the paper's *basic* one
(`aspic.solver.ArgumentationFramework._is_weaker`, Definition 2.11): a
strict-and-firm argument is never weaker than anything, and two defeasible
arguments are **incomparable**. Incomparability is a deliberate choice, and
it has a consequence the interface has to keep saying out loud: a mutual
rebut leaves both sides UNDEC, so a judgment whose ratio is "this reason
prevails over that one" cannot be reproduced as a rebut -- only as an
undercut (see `docs/formalizacao.md`, "A restrição de modelagem que decide o
resultado").

That is the right default for the ICAIL cases, which are built exactly that
way. It is *not* enough for a judgment that resolves a head-on conflict of
qualifications by weighing reasons, which is what
`docs/formalizacao.md`'s Caso 003 does at ⟨q0, q2⟩: the specific duty of
custody against the generic duty of public security, two rules concluding
complementary literals, with no undercut on either side. Somebody has to be
preferred, and ASPIC+ has the room for it: Definition 2.10 makes rebutting
and undermining defeat *preference-dependent*, and only undercutting
preference-independent.

This module supplies the missing preorder, and computes it from an explicit,
auditable tuple rather than from a bare number:

* a **dimension** is one doctrinal axis the judgment weighs (for Caso 003:
  the specificity of the duty to act, the causal intervention of a later
  event, the autonomy of the third party who acted), each with the weight the
  reader assigns to it;
* a **rule profile** says which dimensions a defeasible rule invokes, and how
  strongly (a coefficient, normally 0 or 1);
* a rule's **strength** is the weighted sum ``Σ_d weight_d · coefficient_d``.
  A rule that invokes no dimension is *neutral*: it carries no weight of its
  own and is skipped, which is what a purely inferential step should be;
* an **argument's** strength aggregates the strengths of the defeasible rules
  it uses, by one of the two principles ASPIC+ names -- weakest-link (the
  default) or last-link -- plus `sum`, for a reading in which reasons
  accumulate rather than bottleneck.

`A ≺ B` iff both arguments are scored and `strength(A) < strength(B)`. When
either is unscored the two stay incomparable and the basic ordering decides,
so a framework whose rules carry no profile behaves exactly as before -- the
preference model is strictly additive.

Nothing here inspects the *content* of a rule: the profile is data supplied
with the case (`FormalizedCase.preferences`), so the weighing is part of the
formalization the reader can audit and change, not a heuristic buried in the
solver. `sensitivity` exists for exactly that: it reports the weight at which
a given conflict would flip.
"""
from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

#: Aggregation principles. The first two are ASPIC+'s own (Modgil & Prakken,
#: "A general account of argumentation with preferences", §4); `sum` is not,
#: and is offered because a court that stacks three independent reasons
#: against one is doing something a min() cannot express.
WEAKEST_LINK = "weakest"
LAST_LINK = "last"
SUM = "sum"
PRINCIPLES = (WEAKEST_LINK, LAST_LINK, SUM)

PRINCIPLE_LABELS = {
    WEAKEST_LINK: "elo mais fraco (weakest-link): a força de um argumento é a "
                  "da regra mais fraca que ele usa",
    LAST_LINK: "último elo (last-link): vale a força da última regra aplicada, "
               "que é a que responde diretamente pela conclusão",
    SUM: "soma: as razões se acumulam, e um argumento apoiado em dois eixos "
         "pesa mais do que um apoiado em um só",
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
                 principle: str = WEAKEST_LINK):
        if principle not in PRINCIPLES:
            raise ValueError(
                f"princípio de agregação desconhecido: {principle!r} "
                f"(use um de {', '.join(PRINCIPLES)})")
        self.dimensions: Tuple[Dimension, ...] = tuple(dimensions)
        self.principle = principle
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
        `⟨dever específico, intervenção causal, autonomia⟩` a reader of the
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
        """The rules of an argument that actually carry weight, in the order
        they were applied."""
        return [rule_id for rule_id in rule_ids
                if self.rule_strength(rule_id) is not None]

    def strength_of_rules(self, rule_ids: Sequence[str]) -> Optional[float]:
        """Aggregate strength of a set of defeasible rules under this
        model's principle, or None when none of them carries weight.

        Under `last`, the *last* weight-carrying rule decides. The last rule
        applied may itself be neutral -- `q2: DeverGener ⇒ ¬DeverEspec` is a
        pure inference step -- and refusing to score the argument at all in
        that case would make last-link strictly less informative than
        weakest-link for no reason, so the scan walks backwards to the
        nearest rule that does carry weight.
        """
        scored = [self.rule_strength(rule_id)
                  for rule_id in self.contributing_rules(rule_ids)]
        if not scored:
            return None
        if self.principle == WEAKEST_LINK:
            return min(scored)
        if self.principle == LAST_LINK:
            return scored[-1]
        return float(sum(scored))

    def argument_strength(self, argument) -> Optional[float]:
        """Strength of an `aspic.solver.Argument`.

        Strict rules never enter: they are not defeasible, so no preference
        attaches to them, and an argument that uses only strict rules over
        premises is already handled by the basic ordering.
        """
        return self.strength_of_rules(argument.defeasible_rules)

    # ------------------------------------------------------------------
    # The ordering
    # ------------------------------------------------------------------
    def compare(self, left, right) -> Comparison:
        """Compare two arguments. `verdict` is which side is *stronger*."""
        left_score = self.argument_strength(left)
        right_score = self.argument_strength(right)
        left_rules = tuple(self.contributing_rules(left.defeasible_rules))
        right_rules = tuple(self.contributing_rules(right.defeasible_rules))
        if left_score is None or right_score is None or left_score == right_score:
            verdict = "incomparable"
        else:
            verdict = "left" if left_score > right_score else "right"
        return Comparison(left=left_score, right=right_score, verdict=verdict,
                          left_rules=left_rules, right_rules=right_rules)

    def is_weaker(self, a, b) -> bool:
        """`A ≺ B`: both scored, and A scores strictly lower."""
        return self.compare(a, b).verdict == "right"

    def explain(self, a, b) -> str:
        """One line saying how the two compare, for a tooltip or a table."""
        comparison = self.compare(a, b)
        if comparison.left is None or comparison.right is None:
            return ("sem preferência aplicável: ao menos um dos argumentos não "
                    "invoca nenhuma dimensão, então os dois seguem incomparáveis")
        if comparison.verdict == "incomparable":
            return (f"empate de força ({comparison.left:g} × {comparison.right:g}): "
                    "os dois seguem incomparáveis")
        stronger, weaker = ((a, b) if comparison.verdict == "left" else (b, a))
        high, low = ((comparison.left, comparison.right)
                     if comparison.verdict == "left"
                     else (comparison.right, comparison.left))
        return (f"{stronger.id} ({high:g}) prevalece sobre {weaker.id} ({low:g}) "
                f"por {self.principle}")

    # ------------------------------------------------------------------
    # Sensitivity
    # ------------------------------------------------------------------
    def with_weights(self, **overrides: float) -> "PreferenceModel":
        """A copy with some dimension weights replaced."""
        dimensions = [replace(d, weight=float(overrides.get(d.key, d.weight)))
                      for d in self.dimensions]
        return PreferenceModel(dimensions, self.profiles.values(), self.principle)

    def with_principle(self, principle: str) -> "PreferenceModel":
        return PreferenceModel(self.dimensions, self.profiles.values(), principle)

    def as_dict(self) -> Dict[str, object]:
        return {
            "principle": self.principle,
            "principle_pt": PRINCIPLE_LABELS.get(self.principle, self.principle),
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
