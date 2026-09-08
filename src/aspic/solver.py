"""ASPIC+ argumentation solver with cause-in-fact detection.

Ported and adapted from a TCC (UnB) project's standalone ASPIC+ solver, and
extended to reproduce the argumentation-theoretic notions of cause-in-fact
from:

    Pisano, Prakken, Sartor & Liepina. "Modelling Cause-in-Fact in Legal
    Cases through Defeasible Argumentation." ICAIL 2025.

Compared to the original solver, two things changed:

1. Defeat semantics. The original solver decided rebutting attacks using
   numeric rule preferences (weakest-link aggregation), which is specific to
   the BoardgameQA benchmark it was built for. This version instead
   implements the paper's "basic argument ordering" (Definition 2.11) as its
   default: a strict-and-firm argument is never weaker than anything, two
   defeasible/plausible arguments are incomparable (so any attack between
   them succeeds as a defeat), and undercutting always succeeds regardless
   of strength. A case that needs to weigh two defeasible reasons against
   each other can pass an `aspic.preferences.PreferenceModel`, which refines
   *only* the clause the basic ordering leaves open; with no model passed --
   the default for every case in this repository except the ones that
   declare weights -- the behaviour is exactly Definition 2.11's.
2. Cause-in-fact machinery. Added explanations/support sets (Definition 3.3,
   computed via the grounded-extension fixed point rather than by literally
   enumerating the dialectical game trees) and axiom-expansion (Definition
   4.2) to implement the paper's NESS cause (Definition 4.3).

Additionally ported `but_for` (Definition 3.5) from the ICAIL 2026
follow-up paper, "From Cause-in-Fact to Legally Relevant Cause through
Argumentation" (Pisano, Prakken & Sartor; docs/papers/ICAIL2026causation.pdf).
That paper renames Definition 4.3 "NESS Cause" (Definition 3.4) -- a purely
terminological refinement, with no behavioural change -- and adds the
strictly stronger but-for test alongside it.

**There are exactly two notions, and this file has exactly two methods.** The
authors' own implementation confirms it: `tuProlog/arg2p-kt`'s causality
module exposes `ness/3` and `but_for/2` and nothing else. An earlier version
of this file called the first one `is_cause` and carried a third,
home-grown deductive NESS test alongside it; both were removed, because the
name hid that `is_cause` *was* the NESS cause and the third test could not
answer for a derived literal at all. See `tests/test_legally_relevant_causes_2026.py` for the
paper's new legal-cause examples that build a further "legally relevant
causation" layer on top of cause-in-fact; that layer (Wright's no-worse-off,
superseding-cause and risk-playout defences) is out of scope for this file
and is instead modelled directly as a second, hand-fed ArgumentationFramework
in the tests, mirroring how the paper itself presents it.
"""
import json
import logging

from itertools import product
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ASPIC+")


def negate_literal(literal: str) -> str:
    """Return the complement of a literal string (Wright's '-phi' notation)."""
    return literal[1:] if literal.startswith("¬") else f"¬{literal}"


class Literal:
    """A literal in the logical language, can be positive or negative."""
    def __init__(self, name: str):
        self.name = name
        self.is_negative = name.startswith("¬")
        self.base_name = name[1:] if self.is_negative else name

    def negate(self) -> 'Literal':
        return Literal(negate_literal(self.name))

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"Literal({self.name!r})"

    def __eq__(self, other) -> bool:
        return isinstance(other, Literal) and self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


class Rule:
    """A rule (strict or defeasible) in the argumentation system."""
    def __init__(self, id: str, antecedents: List[str], consequent: str,
                 is_strict: bool = False):
        """
        Args:
            id: Rule identifier (e.g., "r0").
            antecedents: List of literal strings that must hold for the rule to fire.
            consequent: The conclusion that follows from the antecedents.
            is_strict: True for '->' rules, False for defeasible '=>' rules.

        A rule is automatically treated as an undercutter (n(r) in the
        paper's notation) when its consequent has the form "¬<rule id>",
        e.g. "r4: BiSt => ¬r1" says r4 attacks the applicability of r1.
        There is no need for a separate "undercutter rule" list: any rule
        (strict or defeasible) whose consequent negates a rule id plays
        that role automatically.
        """
        self.id = id
        self.antecedents = antecedents
        self.consequent = consequent
        self.is_strict = is_strict
        self.is_undercutter = consequent.startswith("¬r")

    def __str__(self) -> str:
        ant_str = " AND ".join(self.antecedents)
        arrow = "->" if self.is_strict else "=>"
        return f"{self.id}: {ant_str} {arrow} {self.consequent}"

    def __repr__(self) -> str:
        return f"Rule({str(self)!r})"


class Argument:
    """An argument in the ASPIC+ framework (Definition 2.6)."""
    def __init__(self, id: str, conclusion: str,
                 ordinary_premises: FrozenSet[str], axiom_premises: FrozenSet[str],
                 strict_rules: List[str], defeasible_rules: List[str],
                 sub_arguments: Optional[List['Argument']] = None,
                 top_rule: Optional[Rule] = None):
        """
        Args:
            id: Unique identifier for the argument.
            conclusion: The final conclusion (Conc(A)).
            ordinary_premises: Cumulative Prem(A) ∩ Kp.
            axiom_premises: Cumulative Prem(A) ∩ Kn.
            strict_rules: Cumulative strict rule ids used (Rules(A) ∩ Rs).
            defeasible_rules: Cumulative defeasible rule ids used (DefRules(A)).
            sub_arguments: Direct immediate sub-arguments (A1, ..., An in Def. 2.6).
            top_rule: The rule applied at the last inference step, or None
                for atomic (premise/axiom) arguments.
        """
        self.id = id
        self.conclusion = conclusion
        self.ordinary_premises = ordinary_premises
        self.axiom_premises = axiom_premises
        self.strict_rules = strict_rules
        self.defeasible_rules = defeasible_rules
        self.sub_arguments = sub_arguments or []
        self.top_rule = top_rule

    @property
    def premises(self) -> FrozenSet[str]:
        """Prem(A) = Prem(A) ∩ Kp ∪ Prem(A) ∩ Kn."""
        return self.ordinary_premises | self.axiom_premises

    @property
    def is_atomic(self) -> bool:
        """True for base-case arguments consisting of a single premise/axiom."""
        return self.top_rule is None

    @property
    def is_strict(self) -> bool:
        """DefRules(A) = ∅."""
        return not self.defeasible_rules

    @property
    def is_firm(self) -> bool:
        """Prem_p(A) = ∅."""
        return not self.ordinary_premises

    @property
    def signature(self) -> Tuple:
        """Structural identity used to match arguments across frameworks
        that share rules but differ in knowledge base (see axiom_expand)."""
        return (
            self.premises,
            self.conclusion,
            tuple(sorted(self.defeasible_rules)),
            tuple(sorted(self.strict_rules)),
        )

    def all_subarguments(self) -> Dict[str, 'Argument']:
        """Sub(A): transitive closure of sub-arguments, including self."""
        result: Dict[str, 'Argument'] = {self.id: self}
        for sub in self.sub_arguments:
            if sub.id not in result:
                result.update(sub.all_subarguments())
        return result

    def __str__(self) -> str:
        return f"{self.id}: [{', '.join(sorted(self.premises))}] => {self.conclusion}"

    def __repr__(self) -> str:
        return f"Argument({str(self)!r})"


class Attack:
    """Represents an attack between arguments (Definition 2.8)."""
    def __init__(self, attacker_id: str, target_id: str,
                 attack_type: str, target_subargument_id: str,
                 rule_id: Optional[str] = None,
                 attacked_literal: Optional[str] = None):
        """
        Args:
            attacker_id: Id of the attacking argument.
            target_id: Id of the attacked argument.
            attack_type: One of "rebut", "undercut", or "undermine".
            target_subargument_id: Id of the specific sub-argument B' of the
                target that is attacked -- needed both to decide defeat
                (the ordering compares the attacker against B', not against
                the whole target) and to compute explanations.
            rule_id: Id of the undercut rule (for undercut attacks).
            attacked_literal: The literal being attacked (for rebut/undermine).
        """
        self.attacker_id = attacker_id
        self.target_id = target_id
        self.attack_type = attack_type
        self.target_subargument_id = target_subargument_id
        self.rule_id = rule_id
        self.attacked_literal = attacked_literal

    def __str__(self) -> str:
        if self.attack_type == "undercut":
            return f"{self.attacker_id} undercuts {self.target_id} on rule {self.rule_id}"
        elif self.attack_type == "rebut":
            return f"{self.attacker_id} rebuts {self.target_id} on {self.attacked_literal}"
        else:
            return f"{self.attacker_id} undermines {self.target_id} on {self.attacked_literal}"


class Defeat:
    """A successful attack (Definition 2.10)."""
    def __init__(self, attack: Attack, reason: str):
        self.attack = attack
        self.reason = reason

    def get_explanation(self) -> str:
        base = str(self.attack)
        if self.attack.attack_type == "undercut":
            return f"{base} (undercutting always succeeds as a defeat)"
        return f"{base} ({self.reason})"


class ArgumentationFramework:
    """Constructs arguments, attacks and defeats, and computes the grounded
    extension and cause-in-fact relation for an ASPIC+ argumentation theory."""

    def __init__(self, knowledge_base: Dict, causal_model: Dict,
                 preferences=None):
        """
        Args:
            knowledge_base: {"premises": [...], "axioms": [...]} -- Kp and Kn.
            causal_model: {"strict_rules": [...], "defeasible_rules": [...]}
                Rule strings look like "r1: SuDe => SuTh" (defeasible) or
                "r1: SuDe -> SuTh" (strict). Undercutters are ordinary rules
                whose consequent is "¬<rule id>"; no separate list needed.
            preferences: an optional `aspic.preferences.PreferenceModel`,
                refining the basic ordering between two defeasible arguments.
                Left None -- the default everywhere in this repository except
                where a case explicitly declares weights -- the ordering is
                exactly Definition 2.11's and two defeasible arguments stay
                incomparable, so every existing framework behaves unchanged.
        """
        logger.info("Initializing ArgumentationFramework...")
        self.preferences = preferences

        # Keep raw specs (deep-ish copy) so axiom_expand() can rebuild a
        # sibling framework with an extended axiom set.
        self._kb_raw = {
            "premises": list(knowledge_base.get("premises", [])),
            "axioms": list(knowledge_base.get("axioms", [])),
        }
        self._model_raw = {
            "strict_rules": list(causal_model.get("strict_rules", [])),
            "defeasible_rules": list(causal_model.get("defeasible_rules", [])),
        }

        self.premises = {Literal(p) for p in self._kb_raw["premises"]}  # Kp
        self.axioms = {Literal(a) for a in self._kb_raw["axioms"]}      # Kn
        logger.info(f"Loaded knowledge base: {len(self.premises)} premises, {len(self.axioms)} axioms")

        self.rules: Dict[str, Rule] = {}
        self.strict_rules: Dict[str, Rule] = {}     # Rs
        self.defeasible_rules: Dict[str, Rule] = {} # Rd

        self.arguments: Dict[str, Argument] = {}
        self.attacks: List[Attack] = []
        self.defeats: List[Defeat] = []
        self._argument_signatures: Set[Tuple] = set()

        self._parse_rules(self._model_raw)
        self._construct_arguments()
        self._identify_attacks()
        self._compute_defeats()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def _parse_rule(self, rule_str: str) -> Tuple[List[str], str]:
        rule_body = rule_str.split(":", 1)[1].strip()
        parts = rule_body.split("=>")
        if len(parts) == 1:
            parts = rule_body.split("->")
        if len(parts) != 2:
            raise ValueError(f"Invalid rule format: {rule_str}")
        antecedents = [ant.strip() for ant in parts[0].split("AND")]
        consequent = parts[1].strip()
        return antecedents, consequent

    def _parse_rules(self, causal_model: Dict):
        logger.info("Parsing rules from causal model...")
        for r_str in causal_model.get("strict_rules", []):
            rule_id = r_str.split(":")[0].strip()
            ants, cons = self._parse_rule(r_str)
            rule = Rule(rule_id, ants, cons, is_strict=True)
            self.strict_rules[rule_id] = rule
            self.rules[rule_id] = rule

        for r_str in causal_model.get("defeasible_rules", []):
            rule_id = r_str.split(":")[0].strip()
            ants, cons = self._parse_rule(r_str)
            rule = Rule(rule_id, ants, cons, is_strict=False)
            self.defeasible_rules[rule_id] = rule
            self.rules[rule_id] = rule

        logger.info(
            f"Found {len(self.strict_rules)} strict rules, "
            f"{len(self.defeasible_rules)} defeasible rules"
        )

    # ------------------------------------------------------------------
    # Argument construction (Definition 2.6)
    # ------------------------------------------------------------------
    def _construct_arguments(self):
        logger.info("Starting argument construction...")

        for i, literal in enumerate(sorted({*self.premises, *self.axioms}, key=lambda literal_: literal_.name)):
            is_axiom = literal in self.axioms
            sig = (frozenset([literal.name]), literal.name, tuple(), tuple())
            if sig in self._argument_signatures:
                continue
            arg_id = f"A{i}"
            self.arguments[arg_id] = Argument(
                id=arg_id,
                conclusion=literal.name,
                ordinary_premises=frozenset() if is_axiom else frozenset([literal.name]),
                axiom_premises=frozenset([literal.name]) if is_axiom else frozenset(),
                strict_rules=[],
                defeasible_rules=[],
            )
            self._argument_signatures.add(sig)

        all_rules = list(self.rules.values())
        logger.info(f"Loaded {len(all_rules)} rules total")

        MAX_ITER = 1000
        changed = True
        iteration = 0
        while changed and iteration < MAX_ITER:
            iteration += 1
            changed = False
            previous_conclusions = {a.conclusion for a in self.arguments.values()}

            for rule in all_rules:
                try:
                    if self._apply_rule(rule):
                        changed = True
                except Exception as e:
                    logger.error(f"Error applying rule {rule.id}: {e}")

            new_conclusions = {a.conclusion for a in self.arguments.values()}
            if new_conclusions == previous_conclusions:
                break

        if iteration >= MAX_ITER:
            logger.warning("Argument construction stopped after reaching MAX_ITER limit")

        logger.info(
            "Argument construction complete: %d arguments built | conclusions: %s",
            len(self.arguments), sorted({a.conclusion for a in self.arguments.values()}),
        )

    def _apply_rule(self, rule: Rule) -> bool:
        antecedent_args = []
        for ant in rule.antecedents:
            ant_args = [arg for arg in self.arguments.values() if arg.conclusion == ant]
            if not ant_args:
                return False
            antecedent_args.append(ant_args)

        created = False
        for combo in product(*antecedent_args):
            # Def. 2.6 step 2 acyclicity guard: psi must not already be a
            # conclusion among the antecedent arguments themselves.
            if rule.consequent in {a.conclusion for a in combo}:
                continue

            ordinary = frozenset().union(*(a.ordinary_premises for a in combo)) if combo else frozenset()
            axiom = frozenset().union(*(a.axiom_premises for a in combo)) if combo else frozenset()
            strict_rules, defeasible_rules = [], []
            for a in combo:
                strict_rules.extend(a.strict_rules)
                defeasible_rules.extend(a.defeasible_rules)
            if rule.is_strict:
                strict_rules = strict_rules + [rule.id]
            else:
                defeasible_rules = defeasible_rules + [rule.id]

            signature = (ordinary | axiom, rule.consequent,
                         tuple(sorted(defeasible_rules)), tuple(sorted(strict_rules)))
            if signature in self._argument_signatures:
                continue
            self._argument_signatures.add(signature)

            new_id = f"A{len(self.arguments)}"
            self.arguments[new_id] = Argument(
                id=new_id,
                conclusion=rule.consequent,
                ordinary_premises=ordinary,
                axiom_premises=axiom,
                strict_rules=strict_rules,
                defeasible_rules=defeasible_rules,
                sub_arguments=list(combo),
                top_rule=rule,
            )
            created = True

        return created

    # ------------------------------------------------------------------
    # Attacks (Definition 2.8) and defeats (Definition 2.10/2.11)
    # ------------------------------------------------------------------
    def _is_weaker(self, a: Argument, b: Argument) -> bool:
        """Argument ordering: Definition 2.11's basic one, refined by the
        case's declared preferences when it has any.

        The basic clauses come first and are never overridden -- a
        strict-and-firm argument is weaker than nothing, and everything
        defeasible-or-plausible is weaker than a strict-and-firm one. Only
        the case the basic ordering leaves open (two defeasible arguments,
        incomparable by default) is handed to the preference model, and only
        when one exists. This is the ASPIC+ shape: Definition 2.10 makes
        rebutting and undermining defeat preference-dependent, so refining
        the preorder here is where a weighing of reasons belongs.
        """
        a_defeasible_or_plausible = not (a.is_strict and a.is_firm)
        b_strict_and_firm = b.is_strict and b.is_firm
        if not a_defeasible_or_plausible:
            return False
        if b_strict_and_firm:
            return True
        if self.preferences is None:
            return False
        return self.preferences.is_weaker(a, b)

    def strength(self, arg_id: str) -> Optional[float]:
        """The argument's strength under the case's preference model, or None
        when the case declares none (or the argument invokes no dimension)."""
        if self.preferences is None:
            return None
        return self.preferences.argument_strength(self.arguments[arg_id])

    def _identify_attacks(self):
        logger.info("Identifying attacks among %d arguments...", len(self.arguments))
        axiom_names = {a.name for a in self.axioms}

        for attacker in self.arguments.values():
            for target in self.arguments.values():
                if attacker.id == target.id:
                    continue

                for sub in target.all_subarguments().values():
                    # Undercut: sub's top rule is defeasible and attacker
                    # concludes ¬n(rule), i.e. "¬<rule id>".
                    if sub.top_rule is not None and not sub.top_rule.is_strict:
                        if attacker.conclusion == f"¬{sub.top_rule.id}":
                            self.attacks.append(Attack(
                                attacker.id, target.id, "undercut",
                                target_subargument_id=sub.id, rule_id=sub.top_rule.id,
                            ))

                    # Rebut: sub was derived via a defeasible top rule and
                    # attacker concludes the complement of sub's conclusion.
                    if sub.top_rule is not None and not sub.top_rule.is_strict:
                        if attacker.conclusion == negate_literal(sub.conclusion):
                            self.attacks.append(Attack(
                                attacker.id, target.id, "rebut",
                                target_subargument_id=sub.id, attacked_literal=sub.conclusion,
                            ))

                    # Undermine: sub is an atomic ordinary-premise argument
                    # (axioms cannot be undermined) and attacker concludes
                    # its complement.
                    if sub.is_atomic and sub.conclusion not in axiom_names:
                        if attacker.conclusion == negate_literal(sub.conclusion):
                            self.attacks.append(Attack(
                                attacker.id, target.id, "undermine",
                                target_subargument_id=sub.id, attacked_literal=sub.conclusion,
                            ))

        by_type = {"undermine": 0, "undercut": 0, "rebut": 0}
        for att in self.attacks:
            by_type[att.attack_type] += 1
        logger.info(
            "Attacks identified: %d total | undermine=%d, undercut=%d, rebut=%d",
            len(self.attacks), by_type["undermine"], by_type["undercut"], by_type["rebut"],
        )

    @property
    def _ordering_name(self) -> str:
        return "basic" if self.preferences is None else "preference-refined"

    def _compute_defeats(self):
        logger.info("Computing defeats from %d attacks...", len(self.attacks))
        self.defeats.clear()
        for attack in self.attacks:
            attacker = self.arguments[attack.attacker_id]

            if attack.attack_type == "undercut":
                self.defeats.append(Defeat(attack, "undercutting always succeeds"))
                continue

            target_sub = self.arguments[attack.target_subargument_id]
            if not self._is_weaker(attacker, target_sub):
                reason = (
                    "succeeds: attacker is not weaker than the attacked sub-argument "
                    f"under the {self._ordering_name} ordering"
                )
                if self.preferences is not None:
                    reason += f" -- {self.preferences.explain(attacker, target_sub)}"
                self.defeats.append(Defeat(attack, reason))
            elif self.preferences is not None:
                logger.debug(
                    "attack %s failed on preference: %s",
                    attack, self.preferences.explain(attacker, target_sub))

        logger.info("Defeats computed: %d out of %d attacks succeeded", len(self.defeats), len(self.attacks))

    # ------------------------------------------------------------------
    # Grounded extension (Section 2.1)
    # ------------------------------------------------------------------
    def compute_grounded_extension(self) -> Tuple[Set[str], List[Defeat]]:
        """The grounded extension (least fixed point of the defense
        function) and the framework's defeats. Per-argument explanations
        are deliberately not computed here -- they're not needed to get the
        extension itself, and are potentially expensive; call
        `support_set_for_argument` lazily for the specific arguments you
        care about instead.
        """
        extension: Set[str] = set()

        logger.info(
            "Computing grounded extension: %d arguments, %d defeats",
            len(self.arguments), len(self.defeats),
        )

        while True:
            defended = {
                arg.id for arg in self.arguments.values()
                if self._is_defended(arg.id, extension)
            }
            new_extension = extension | defended
            if new_extension == extension:
                break
            extension = new_extension

        logger.info(
            "Grounded extension computed: %d argument(s) accepted | conclusions: %s",
            len(extension), sorted({self.arguments[a].conclusion for a in extension}),
        )
        return extension, self.defeats

    def _is_defended(self, arg_id: str, defenders: Set[str]) -> bool:
        defeats_against = [d for d in self.defeats if d.attack.target_id == arg_id]
        for defeat in defeats_against:
            attacker_defeated = any(
                d.attack.attacker_id == defender_id and d.attack.target_id == defeat.attack.attacker_id
                for defender_id in defenders
                for d in self.defeats
            )
            if not attacker_defeated:
                return False
        return True

    def justified_conclusions(self) -> Set[str]:
        extension, _ = self.compute_grounded_extension()
        return {self.arguments[a].conclusion for a in extension}

    # ------------------------------------------------------------------
    # Explanations & support sets (Definition 3.3)
    # ------------------------------------------------------------------
    @staticmethod
    def _subset_minimal(sets: List[FrozenSet[str]]) -> List[FrozenSet[str]]:
        """Keep only the subset-minimal frozensets in `sets` (drop any set
        that properly contains another set already present), deduplicated."""
        minimal = [s for s in sets if not any(other < s for other in sets)]
        seen: Set[FrozenSet[str]] = set()
        unique: List[FrozenSet[str]] = []
        for s in minimal:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        return unique

    def _minimal_explanations(self, arg_id: str, grounded_extension: Set[str],
                               memo: Dict[str, Set[FrozenSet[str]]],
                               in_progress: Set[str]) -> Set[FrozenSet[str]]:
        """All subset-minimal explanations for `arg_id` (Definition 3.3):
        each explanation is one minimal winning strategy's set of proponent
        arguments.

        For every defeater D of arg_id, a strategy must pick *one* justified
        (in E) counter-attacker of D; different picks yield different
        strategies, so this recurses per defeater, keeps only the
        subset-minimal option *for that defeater* (an option that is a
        strict superset of another valid option can never be part of a
        minimal overall strategy), then combines one option per defeater
        (cartesian product) and filters the combined results for minimality
        again. `in_progress` guards against an argument being used
        (even transitively) to defend itself, mirroring strong admissibility's
        "defended by some S' ⊆ S \\ {A}" (Caminada 2014).
        """
        if arg_id in memo:
            return memo[arg_id]
        if arg_id in in_progress:
            return set()  # arg_id cannot be used to (transitively) defend itself

        in_progress.add(arg_id)
        defeaters = sorted({d.attack.attacker_id for d in self.defeats if d.attack.target_id == arg_id})

        per_defeater_options: List[List[FrozenSet[str]]] = []
        for defeater_id in defeaters:
            counters = sorted({
                d.attack.attacker_id for d in self.defeats
                if d.attack.target_id == defeater_id and d.attack.attacker_id in grounded_extension
            })
            options: List[FrozenSet[str]] = []
            for counter_id in counters:
                options.extend(self._minimal_explanations(counter_id, grounded_extension, memo, in_progress))
            per_defeater_options.append(self._subset_minimal(options))

        in_progress.discard(arg_id)

        combined: Set[FrozenSet[str]] = set()
        for combo in product(*per_defeater_options) if per_defeater_options else [()]:
            explanation = frozenset({arg_id}).union(*combo) if combo else frozenset({arg_id})
            combined.add(explanation)

        result = set(self._subset_minimal(list(combined)))
        memo[arg_id] = result
        return result

    def support_set_for_argument(self, arg_id: str, grounded_extension: Set[str],
                                  _memo: Optional[Dict[str, Set[FrozenSet[str]]]] = None) -> Set[str]:
        """Supp(A, E): union of all (minimal) explanations for A being in
        the grounded extension."""
        memo = _memo if _memo is not None else {}
        explanations = self._minimal_explanations(arg_id, grounded_extension, memo, set())
        return set().union(*explanations) if explanations else {arg_id}

    def support_set(self, formula: str) -> Set[str]:
        """Supp(psi, E): union of Supp(A, E) for every justified argument A
        with conclusion psi (Definition 3.3)."""
        extension, _ = self.compute_grounded_extension()
        memo: Dict[str, Set[FrozenSet[str]]] = {}
        result: Set[str] = set()
        for arg_id in extension:
            if self.arguments[arg_id].conclusion == formula:
                result |= self.support_set_for_argument(arg_id, extension, memo)
        return result

    # ------------------------------------------------------------------
    # Axiom-expansion (Definition 4.2) & cause-in-fact (Definition 4.3)
    # ------------------------------------------------------------------
    def axiom_expand(self, new_axioms: List[str]) -> 'ArgumentationFramework':
        """K + L: build a sibling framework whose axioms are extended with
        L, leaving Kp and the rule base untouched."""
        expanded_kb = {
            "premises": list(self._kb_raw["premises"]),
            "axioms": list(dict.fromkeys([*self._kb_raw["axioms"], *new_axioms])),
        }
        return ArgumentationFramework(expanded_kb, self._model_raw,
                                     preferences=self.preferences)

    def ness_cause(self, phi: str, psi: str) -> bool:
        """The **NESS cause**: phi is a cause in fact of psi.

        Definition 4.3 of ICAIL 2025, renamed "NESS Cause" in Definition 3.4
        of ICAIL 2026 -- the same notion under two names, and the one the
        authors' own implementation exposes as the Prolog primitive `ness/3`
        (`causality-solver/.../CausalitySolver.kt` in `tuProlog/arg2p-kt`;
        see `~/.claude/knowledge/jurix26/maps/tuProlog--arg2p-kt.md`).

        phi is a NESS cause of psi iff -phi ∈ L for a (here: singleton)
        axiom-expansion L such that some explanation E of a justified
        argument for psi is no longer a subset of the grounded extension of
        the expanded framework.

        Implemented via the support set: Supp(psi, E) is the union of all
        explanations of psi, so checking whether the expansion drops *any*
        support-set member out of the new grounded extension is equivalent
        to checking whether it breaks *some* explanation -- exactly the
        existential in Definition 4.3.

        "NESS" is Wright's *Necessary Element of a Sufficient Set*, and the
        argumentation-theoretic reading above is what makes it computable
        over a defeasible theory rather than over a bare set of conditions.
        It is strictly weaker than `but_for`: it asks whether the
        intervention breaks *some* route to psi, where but-for asks whether
        it breaks *every* one. See `aspic.sufficiency` for the set-of-
        conditions decomposition that explains a given verdict.
        """
        original_support = self.support_set(psi)
        if not original_support:
            return False
        original_signatures = {self.arguments[a].signature for a in original_support}

        expanded = self.axiom_expand([negate_literal(phi)])
        new_extension, _ = expanded.compute_grounded_extension()
        new_signatures_in_extension = {expanded.arguments[a].signature for a in new_extension}

        return not original_signatures.issubset(new_signatures_in_extension)

    def but_for(self, phi: str, psi: str) -> bool:
        """Definition 3.5 of the ICAIL 2026 follow-up paper ("From
        Cause-in-Fact to Legally Relevant Cause through Argumentation",
        Pisano, Prakken & Sartor): phi is a but-for cause of psi iff psi is
        justified in this framework, and psi is no longer the conclusion of
        any justified argument once the framework is axiom-expanded with
        the singleton intervention {-phi}.

        This is strictly stronger than `ness_cause`: NESS only requires that
        the intervention break *one* explanation of psi, whereas `but_for`
        requires that psi lose *all* justified arguments, i.e. that no
        alternative explanation survives. Consequently every but-for cause
        is a NESS cause, but not conversely, and the two are the only
        notions the papers define (the authors' implementation exposes
        exactly `ness/3` and `but_for/2`).

        Overdetermination and preemption are the textbook counterexamples.
        Asbestos/Fairchild: each Ex_i is a NESS cause of Di, but none is a
        but-for cause, since the other two exposures alone still suffice.
        Double Shooting: removing Bush's shot kills the only justified route
        to the death -- yet the death survives, because the undercut that
        Bush's kill placed on Dlugash's chain goes with it and a suppressed
        route wakes up.
        """
        if psi not in self.justified_conclusions():
            return False
        expanded = self.axiom_expand([negate_literal(phi)])
        return psi not in expanded.justified_conclusions()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_json(self) -> str:
        return json.dumps({
            "ordering": (None if self.preferences is None
                         else self.preferences.as_dict()),
            "knowledge": {
                "axioms": sorted(a.name for a in self.axioms),
                "premises": sorted(p.name for p in self.premises),
                "rules": {
                    "strict": [str(r) for r in self.strict_rules.values()],
                    "defeasible": [str(r) for r in self.defeasible_rules.values()],
                },
            },
            "arguments": [
                {
                    "id": arg.id,
                    "premises": sorted(arg.premises),
                    "rules": sorted(arg.strict_rules + arg.defeasible_rules),
                    "conclusion": arg.conclusion,
                }
                for arg in self.arguments.values()
            ],
            "attacks": [
                {
                    "attacker": att.attacker_id,
                    "target": att.target_id,
                    "type": att.attack_type,
                    "rule": att.rule_id,
                }
                for att in self.attacks
            ],
            "defeats": [
                {
                    "defeater": d.attack.attacker_id,
                    "defeated": d.attack.target_id,
                    "type": d.attack.attack_type,
                    "explanation": d.get_explanation(),
                }
                for d in self.defeats
            ],
        }, indent=2)
