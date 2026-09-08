"""One framework per perspective, and the votes as adjudication moves.

The pipeline produces a single framework per case, and the grounded extension
of that framework reports the court's final position. What it cannot report is
the *disagreement*: `aspic.didactic` shows an argument as OUT without saying
that three of five perspectives sustained it and two knocked it down.

This module reads the perspective metadata the formalization already carries
-- `RuleMeta.perspective` on every rule, `AtomOut.perspectives` on every atom
-- and projects the record into one `ArgumentationFramework` per perspective,
following the three-player model of

    Prakken, H. "A Formal Model of Adjudication Dialogues." AI & Law, 2008
    (docs/papers/2008_Prakken_FormalModel_AILaw.pdf).

There, an adjudication dialogue has an *argumentation phase*, in which the
adversaries build the argument graph, and a *decision phase*, in which only
the adjudicator moves -- and moves only arguments: premise attacks,
undercutters (internal validity) and priority arguments (dialectical
validity), §4.3. Silence is itself a decision: an argument the adjudicator
does not attack is endorsed.

Two things follow for this codebase.

* A vote is not a label on the outcome; it is a **set of rules injected into
  the graph**. Projecting the record by `perspective` is therefore exactly the
  paper's move-by-player decomposition, done after the fact.
* A priority argument ("A > B, since ...") stops B from defeating A. Under
  the solver's default ordering there are no preferences between defeasible
  arguments (`aspic.solver._is_weaker`), so the only way to stop a defeat is
  to undercut the losing rule -- and a priority argument is then already
  expressible as an undercutter whose author is the adjudicator rather than a
  party. A case that instead declares weights (`aspic.preferences`) gets the
  other route as well: the priority becomes an ordering the whole framework
  carries, and `Theory` passes it into every projection so a perspective's
  own reading is weighed exactly as the case is.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set

from .graph_export import argument_status
from .solver import ArgumentationFramework

#: The two adversaries, then the votes, then the court's final position --
#: reading order of the dossier and, not by accident, the order in which an
#: adjudication dialogue unfolds.
ADVERSARIES = ("recorrente", "recorrido")
ADJUDICATORS = ("relator", "voto_convergente", "voto_divergente", "stf_final")

#: A rule nobody disputes belongs to every theory.
SHARED = "comum"


@dataclass(frozen=True)
class Theory:
    """One perspective's argumentation theory, ready for the solver."""
    key: str
    label: str
    premises: List[str]
    rules: List[str]
    rule_ids: List[str] = field(default_factory=list)
    #: The case's ordering between defeasible arguments, carried so that a
    #: projected theory is weighed exactly as the whole case is. A preference
    #: that only applied to the full framework would make every per-
    #: perspective reading here quietly disagree with the case it came from.
    preferences: Optional[object] = None

    @property
    def knowledge_base(self) -> dict:
        return {"premises": list(self.premises), "axioms": []}

    @property
    def causal_model(self) -> dict:
        return {"strict_rules": [], "defeasible_rules": list(self.rules)}

    def framework(self) -> ArgumentationFramework:
        return ArgumentationFramework(self.knowledge_base, self.causal_model,
                                      preferences=self.preferences)


def _label(key: str) -> str:
    from formalize.dossier import perspective_label
    return perspective_label(key)


def _canon(key: str) -> str:
    """The pipeline's spelling. The annotation tool writes `convergente`
    where the prompts say `voto_convergente`, and a perspective spelled two
    ways is two perspectives to every grouping in this module."""
    from formalize.dossier import canonical_perspective
    return canonical_perspective(key)


def _holders(entity) -> Set[str]:
    """Every perspective that holds a rule or premise, canonically spelled.

    `RuleMeta`/`LrcRuleOut`/`LrcPremiseOut` all answer `holders()`: the
    multi-holder list when the record fills it in, the single `perspective`
    otherwise. Reading holders rather than `perspective` is what lets a rule
    three voices assert on their own account belong to three theories instead
    of one -- which is the difference between a runnable theory and an empty
    one for everybody but the first holder.
    """
    getter = getattr(entity, "holders", None)
    if getter is not None:
        return {_canon(key) for key in getter() if key}
    return {_canon(entity.perspective)} if getattr(entity, "perspective", "") else set()


def _admits(selected: Set[str], held: Set[str]) -> bool:
    """Whether a rule belongs to the theory of `selected`.

    Unattributed (`held` empty) and undisputed (`comum`) rules belong to
    every theory; anything else belongs to the theories of its holders.
    """
    return not held or SHARED in held or bool(selected & held)


def _preferences(record):
    """The record's ordering, or None. Imported lazily: `formalize` imports
    `aspic`, so a module-level import here would close the cycle."""
    from formalize.build import preference_model
    return preference_model(record)


def perspectives_in(record) -> List[str]:
    """Every perspective the record actually names, in reading order.

    Both layers are scanned: after the doctrinal defences moved to the
    legal-relevance layer, a court that decides the case may contribute no
    rule at all to the cause-in-fact one, and looking only there would report
    that it took no part in the judgment.
    """
    found: Set[str] = set()
    for meta in record.rules_meta:
        found |= _holders(meta)
    found |= {_canon(p) for atom in record.atoms for p in atom.perspectives}
    if record.lrc is not None:
        for rule in record.lrc.scheme_rules:
            found |= _holders(rule) | {_canon(getattr(rule, "origin_perspective", ""))}
        for premise in record.lrc.doctrinal_premises:
            found |= _holders(premise) | {_canon(getattr(premise, "origin_perspective", ""))}
    found.discard(SHARED)
    found.discard("")
    ordered = [p for p in (*ADVERSARIES, *ADJUDICATORS) if p in found]
    return ordered + sorted(found - set(ordered))


def project(record, keys: Sequence[str]) -> Theory:
    """The theory held by `keys` together (plus whatever nobody disputes).

    Premises are the record's premises that either (a) some selected rule
    reads, or (b) the perspective itself asserts. (a) is what keeps the
    theory *runnable* -- a rule whose antecedent is not a premise never fires,
    and a theory that derives nothing says nothing. (b) is what keeps it
    *honest*: a fact a perspective asserts belongs to its theory even when no
    rule of that perspective happens to use it.
    """
    from formalize.validate import base_literal, parse_rule

    selected = {_canon(key) for key in keys}
    rules = [meta for meta in record.rules_meta if _admits(selected, _holders(meta))]
    needed: Set[str] = set()
    for meta in rules:
        try:
            needed |= {base_literal(ant) for ant in parse_rule(meta.rule).antecedents}
        except ValueError:
            continue
    asserted = {atom.code for atom in record.atoms
                if selected & {_canon(p) for p in atom.perspectives}}

    declared = record.knowledge_base.get("premises", [])
    premises = [p for p in declared if base_literal(p) in needed | asserted]
    label = " + ".join(_label(key) for key in keys)
    return Theory(key="+".join(keys), label=label, premises=premises,
                  rules=[meta.rule for meta in rules],
                  rule_ids=[meta.id for meta in rules],
                  preferences=_preferences(record))


def verdicts(theory: Theory, queries: Sequence) -> Dict[str, dict]:
    """What this theory concludes about each of the case's causal questions.

    The same two notions the single-framework view reports, so a
    perspective's answer is comparable line by line with the court's.

    A question whose effect this theory does not even derive comes back with
    `derivable: False` and both verdicts `None` -- *not* `False`. The
    difference matters: "esta teoria não chega ao dano" is not the same
    statement as "chega ao dano e a omissão não o causou", and a trace that
    conflated them reported a perspective as denying causation when it had
    said nothing about it (see `perspective_view._verdict_delta`).
    """
    af = theory.framework()
    extension, _ = af.compute_grounded_extension()
    justified = af.justified_conclusions()
    out: Dict[str, dict] = {}
    for query in queries:
        key = f"{query.phi}->{query.psi}"
        if query.psi not in justified:
            out[key] = {"derivable": False, "ness": None, "but_for": None}
            continue
        out[key] = {
            "derivable": True,
            "ness": af.ness_cause(query.phi, query.psi),
            "but_for": af.but_for(query.phi, query.psi),
        }
    return out


def adjudication_trace(record) -> List[dict]:
    """The dispute rebuilt move by move, in the paper's two phases.

    Step 0 is the argumentation phase: both adversaries' theories together,
    with no vote yet. Each further step admits one adjudicator's rules, in
    procedural order, and reports what changed -- which conclusions became
    justified and which stopped being so.

    This is the measurement the single framework cannot give: not *whether*
    the court's position wins (it does, by construction), but **at which move
    it starts to win**, and on whose rules that turn depends.
    """
    present = perspectives_in(record)
    adversaries = [key for key in ADVERSARIES if key in present]
    votes = [key for key in ADJUDICATORS if key in present]

    steps: List[dict] = []
    admitted: List[str] = list(adversaries)
    previous: Optional[Set[str]] = None
    previous_rules: Set[str] = set()
    for index, added in enumerate([None, *votes]):
        if added is not None:
            admitted = [*admitted, added]
        theory = project(record, admitted)
        af = theory.framework()
        extension, _ = af.compute_grounded_extension()
        justified = af.justified_conclusions()
        steps.append({
            "step": index,
            "added": added,
            "added_label": _label(added) if added else "fase de argumentação",
            "admitted": list(admitted),
            "rules": theory.rule_ids,
            # What this move adds to the graph, not everything its author
            # holds: a rule three voices share is already in play when the
            # second one speaks, and reporting it again would make a vote
            # that changed nothing look like it moved.
            "new_rules": [rule_id for rule_id in theory.rule_ids
                          if rule_id not in previous_rules] if added else [],
            "justified": sorted(justified),
            "gained": sorted(justified - previous) if previous is not None else [],
            "lost": sorted(previous - justified) if previous is not None else [],
            "outcome_justified": record.effect in justified,
            "status": argument_status(af, extension),
            "verdicts": verdicts(theory, record.queries),
        })
        previous = set(justified)
        previous_rules = set(theory.rule_ids)
    return steps


def by_perspective(record) -> List[Theory]:
    """Each perspective's own theory, standing alone."""
    return [project(record, [key]) for key in perspectives_in(record)]


# ----------------------------------------------------------------------
# The decision phase: the legal-relevance layer, admitted vote by vote
# ----------------------------------------------------------------------
def project_lrc(record, keys: Sequence[str],
                bridged: Optional[Sequence[str]] = None) -> Optional[Theory]:
    """The legal-relevance theory held by `keys`, over the solver's facts.

    Three kinds of ingredient are separated here, and the separation is the
    whole point:

    * the **bridge premises** are solver output, not anybody's position, so
      they are always admitted;
    * the `cf2lrc` presumption is the paper's general rule, held by nobody in
      particular, so it is admitted too;
    * every **defence** (`nwo`, `sc`, `suca`, `nofor`, `unom`) is a move by a
      party or by the court, and is admitted only when its perspective is.

    An unattributed defence -- no holder at all, which is what records
    formalized before the field existed carry -- is admitted at every step.
    That keeps old records readable while making their flatness visible: a
    trace where nothing ever flips is a trace whose moves were never
    attributed.

    `bridged` overrides the record's stored bridge premises with the ones a
    particular set of cause-in-fact theories establishes -- see
    `bridged_for`. The stored list is what the *whole* case yields, which is
    the right answer for the record and the wrong one for a step: a claim
    that only becomes a cause in fact once one vote removes another's
    undercut has no `CaFa_*` before that vote, and pretending it does would
    show the legal-relevance layer deciding a question the facts had not yet
    posed.
    """
    from .lrc import scheme_of

    layer = record.lrc
    if layer is None or not layer.scheme_rules:
        return None
    selected = {_canon(key) for key in keys}

    def admitted(entity, scheme: Optional[str] = None) -> bool:
        if scheme == "cf2lrc":
            return True
        return _admits(selected, _holders(entity))

    rules = [rule for rule in layer.scheme_rules
             if admitted(rule, scheme_of(_rule_id(rule.rule)))]
    premises = [*(layer.bridged_premises if bridged is None else bridged)]
    premises += [p.literal for p in layer.doctrinal_premises if admitted(p)]
    label = " + ".join(_label(key) for key in keys) if keys else "sem votos"
    return Theory(key="+".join(keys) or "base", label=label,
                  premises=list(dict.fromkeys(premises)),
                  rules=[rule.rule for rule in rules],
                  rule_ids=[_rule_id(rule.rule) for rule in rules],
                  preferences=_preferences(record))


def _rule_id(rule: str) -> str:
    return rule.split(":", 1)[0].strip()


def cif_keys_for(record, admitted: Sequence[str]) -> List[str]:
    """The cause-in-fact theories standing behind a decision-phase step.

    Both adversaries, always -- the argumentation phase is over before the
    decision phase begins -- plus every adjudicator admitted so far. A party
    that only moves in the legal-relevance layer changes nothing here, which
    is correct: it took no position on what happened.
    """
    present = set(perspectives_in(record))
    parties = [key for key in ADVERSARIES if key in present]
    votes = [key for key in ADJUDICATORS
             if key in present and _canon(key) in {_canon(k) for k in admitted}]
    return [*parties, *votes]


def bridged_for(record, keys: Sequence[str], _cache: Optional[Dict] = None) -> List[str]:
    """The `CaFa_*`/`ButFor_*` literals the theories in `keys` establish.

    The same computation `formalize.bridge` runs for the whole case, run over
    a projection of it. This is the determinism boundary again -- the facts
    the legal-relevance layer reasons over are the solver's word, not
    anybody's claim -- only now it can answer the question the stored list
    cannot: *at which move* did this become a cause in fact?
    """
    from formalize.bridge import candidate_literals, evaluate, target_literals
    from formalize.build import non_candidate_codes

    signature = tuple(sorted(_canon(key) for key in keys))
    if _cache is not None and signature in _cache:
        return _cache[signature]
    theory = project(record, keys)
    facts = evaluate(
        theory.framework(),
        candidate_literals({"premises": theory.premises}, record.queries,
                           exclude=non_candidate_codes(record)),
        target_literals(record.effect, record.queries),
    )
    premises = facts.premises()
    if _cache is not None:
        _cache[signature] = premises
    return premises


def relevance_of(theory: Theory, targets: Sequence[str]) -> Dict[str, bool]:
    from .lrc import relevance_report
    report = relevance_report(theory.framework(), list(targets))
    return {entry["target"]: entry["justified"] for entry in report}


def decision_trace(record) -> List[dict]:
    """The legal-relevance layer rebuilt one adjudicator at a time.

    Step 0 admits only the general presumption: every cause in fact is
    presumed legally relevant. Each further step admits one perspective's
    doctrinal defences and reports which `LeReCa_*` stopped being justified.

    This is the "breaking point" the single framework hides -- the exact move
    at which a claim that survived the facts stops surviving the law, and
    whose reasons that turn rests on.

    Each step also re-derives the cause-in-fact facts from the theories
    admitted *at that step* (`bridged_for`), so the two layers advance
    together. A claim can therefore turn twice in one trace: once when the
    facts start supporting it, and once when the law stops.
    """
    layer = record.lrc
    if layer is None or not layer.scheme_rules:
        return []
    present = perspectives_in(record)
    attributed: Set[str] = set()
    for rule in layer.scheme_rules:
        attributed |= _holders(rule)
    votes = [key for key in (*ADVERSARIES, *ADJUDICATORS)
             if key in present and key in attributed]

    steps: List[dict] = []
    admitted: List[str] = []
    previous: Optional[Dict[str, bool]] = None
    cache: Dict = {}
    for index, added in enumerate([None, *votes]):
        if added is not None:
            admitted = [*admitted, added]
        cif_keys = cif_keys_for(record, admitted)
        bridged = bridged_for(record, cif_keys, cache)
        theory = project_lrc(record, admitted, bridged=bridged)
        if theory is None:
            return []
        relevance = relevance_of(theory, layer.targets)
        steps.append({
            "step": index,
            "added": added,
            "added_label": _label(added) if added else "presunção geral (cf2lrc)",
            "admitted": list(admitted),
            "rules": theory.rule_ids,
            "cif_admitted": cif_keys,
            "bridged": list(bridged),
            "relevance": relevance,
            "blocked": sorted(t for t, ok in relevance.items() if not ok),
            "newly_blocked": sorted(
                t for t, ok in relevance.items()
                if not ok and previous is not None and previous.get(t)),
            "newly_relevant": sorted(
                t for t, ok in relevance.items()
                if ok and previous is not None and previous.get(t) is False),
        })
        previous = relevance
    return steps


def unattributed_lrc_rules(record) -> List[str]:
    """Defences whose author the record does not name.

    They are admitted at every step of `decision_trace`, so each one is a
    move the trace cannot place -- the honest measure of how much of the
    adjudication is still invisible.
    """
    from .lrc import scheme_of

    layer = record.lrc
    if layer is None:
        return []
    return [_rule_id(rule.rule) for rule in layer.scheme_rules
            if not _holders(rule) and scheme_of(_rule_id(rule.rule)) != "cf2lrc"]


# ----------------------------------------------------------------------
# The adjudication map: rules in their author's lane, attacks crossing them
# ----------------------------------------------------------------------
#: Lane grouping. The adjudicators sit above the parties because that is the
#: direction the attacks run: in the decision phase the court moves arguments
#: against what the parties built, never the reverse.
LANES = (
    ("ADJUDICADORES", ADJUDICATORS),
    ("PARTES", ADVERSARIES),
    ("INCONTROVERSO", (SHARED,)),
)

#: How the legal-relevance vocabulary reads on a diagram. The full literal is
#: precise and unreadable at node size (`CaFa_FugaPreso_MorteVitima`); the
#: effect is the same in every literal of a case, so dropping it loses nothing
#: a reader of *this* map needs. The untouched rule stays in the tooltip.
_SHORT = {
    "CaFa": "causa({0})", "ButFor": "só-por({0})", "LeReCa": "relevante({0})",
    "Om": "omissão({0})", "Obl": "dever({0})", "Tortious": "ilícito({0})",
    "Unexpected": "inesperado({0})", "SupersedingCause": "superveniente({0})",
    "After": "{0} após {1}", "Foreseeable": "previsível({0})",
    "ForeseeableRisk": "risco({0})", "Playout": "concretiza({0})",
}

#: Antecedents drawn before the node is cut short. `suca` takes five, and a
#: node listing all of them is a circle nobody reads.
_MAX_ANTECEDENTS = 3

_LANE_STYLE = {
    "cif": {"shape": "ellipse", "fill": "#ffffff"},
    "lrc": {"shape": "ellipse", "fill": "#f4f0fa"},
}


@dataclass(frozen=True)
class MappedRule:
    """One rule, placed in a lane and told whether it survived."""
    id: str
    body: str
    layer: str
    perspective: str
    gloss: str
    attacks: Optional[str]
    defeated: bool
    label: str = ""
    consequent: str = ""
    antecedents: List[str] = field(default_factory=list)
    #: Every perspective that holds the rule, in reading order. `perspective`
    #: is the lane the node is drawn in -- a node can only sit in one box --
    #: and this is what the tooltip says so the other holders are not lost.
    holders: List[str] = field(default_factory=list)


def defeated_rules(record) -> Set[str]:
    """Rule ids that did not survive, across both layers.

    Two ways to not survive, and the map has to show both:

    * some accepted argument **undercuts** the rule, i.e. concludes `¬<id>`;
    * every argument the rule tops is out of the grounded extension. That is
      what a lost **rebut** looks like, and until a case declared preferences
      it never happened -- two defeasible arguments were incomparable, so a
      mutual rebut left both UNDEC and neither was refuted. With an ordering
      one of them is now OUT, and a map that only drew undercuts would show
      the losing rule standing.

    A rule with no argument at all is *not* reported: its antecedents were
    never satisfied, which is a rule that did not fire, not one that fell.

    Read off the frameworks rather than off the record's own verdicts, so the
    map never claims a rule fell for a reason the solver does not produce.
    """
    from formalize import build

    out: Set[str] = set()
    for framework in (build.cif_framework(record), build.lrc_framework(record)):
        if framework is None:
            continue
        extension, _ = framework.compute_grounded_extension()
        topped: Dict[str, List[bool]] = {}
        for arg_id, argument in framework.arguments.items():
            if (argument.conclusion.startswith("¬")
                    and argument.conclusion[1:] in framework.rules
                    and arg_id in extension):
                out.add(argument.conclusion[1:])
            if argument.top_rule is not None:
                topped.setdefault(argument.top_rule.id, []).append(arg_id in extension)
        out |= {rule_id for rule_id, accepted in topped.items() if not any(accepted)}
    return out


#: How a layer reads on screen, and which framework builds it.
LAYER_LABELS = {"cif": "causa de fato", "lrc": "relevância jurídica"}

#: One-letter tag for an argument id. The two frameworks number independently
#: -- both start at A0 -- so on any surface that shows both layers at once, a
#: bare `A17` names two different arguments. The adjudication map is exactly
#: such a surface: it drew `A17` twice, once for the concurring vote's `r8`
#: and once for the reporting judge's `dvpre_q8`.
LAYER_TAGS = {"cif": "F", "lrc": "R"}


@dataclass(frozen=True)
class MappedArgument:
    """One argument of one layer, with everything needed to trace it back.

    The id is the solver's own (`A0`, `A1`, ...), deliberately: it is the
    same id the argument graph of the Análise tab draws, the same one
    `LRCBlock.relevance` names in `blocked_by.attacker`, and the same one
    `aspic.preferences.resolved_conflicts` reports. Renumbering per view
    would make each view internally tidy and mutually untraceable.

    Ids repeat across the two layers -- both frameworks number from A0 -- so
    `layer` is part of the identity and every rendering shows it.
    """
    id: str
    layer: str
    conclusion: str
    premises: List[str]
    rules: List[str]
    top_rule: Optional[str]
    status: str
    #: Perspectives able to build it: those holding *every* rule it uses.
    holders: List[str]
    strength: Optional[float] = None
    #: Where an atomic argument comes from. "ponte" marks the `CaFa_*` /
    #: `ButFor_*` premises the cause-in-fact solver produced: they are
    #: nobody's claim, and listing every perspective as holding them would
    #: read as unanimity where there was no assertion at all.
    origin: str = ""

    @property
    def label(self) -> str:
        """The id as every view prints it: `F·A17` in the cause-in-fact
        layer, `R·A17` in the legal-relevance one. What follows the dot is
        the solver's own id inside that layer, so it still matches the
        argument graph and the relevance report."""
        return f"{LAYER_TAGS.get(self.layer, self.layer)}·{self.id}"


def _rule_holders(record) -> Dict[str, Set[str]]:
    """`{rule id: perspectives that hold it}`, across both layers."""
    out: Dict[str, Set[str]] = {}
    for meta in record.rules_meta:
        out[meta.id] = _holders(meta)
    if record.lrc is not None:
        for rule in record.lrc.scheme_rules:
            out[_rule_id(rule.rule)] = _holders(rule)
    return out


def mapped_arguments(record) -> List[MappedArgument]:
    """Every argument of both layers, named and attributed.

    Attribution is the interesting part. A perspective can build an argument
    exactly when it holds every defeasible rule the argument uses -- an
    argument is not "moved" by anyone, it is what a theory can construct. A
    rule nobody disputes (`comum`) or nobody claimed belongs to all theories,
    so it never narrows the set.

    Atomic arguments (a bare premise) use no rule and are therefore available
    to every perspective that asserts the premise; they are reported with the
    perspectives the record's atoms attribute the premise to.
    """
    from formalize import build

    holders_of = _rule_holders(record)
    present = perspectives_in(record)
    asserted: Dict[str, Set[str]] = {}
    for atom in record.atoms:
        asserted[atom.code] = {_canon(p) for p in atom.perspectives}

    preferences = _preferences(record)
    bridged = set(record.lrc.bridged_premises) if record.lrc is not None else set()
    out: List[MappedArgument] = []
    for layer, af in (("cif", build.cif_framework(record)),
                      ("lrc", build.lrc_framework(record))):
        if af is None:
            continue
        extension, _ = af.compute_grounded_extension()
        status = argument_status(af, extension)
        for argument in af.arguments.values():
            used = list(argument.defeasible_rules) + list(argument.strict_rules)
            if used:
                holders = set(present)
                for rule_id in used:
                    held = holders_of.get(rule_id, set())
                    if held and SHARED not in held:
                        holders &= held
            else:
                base = argument.conclusion.lstrip("¬")
                holders = asserted.get(base, set()) or set(present)
            origin = ""
            if not used and layer == "lrc" and argument.conclusion in bridged:
                origin, holders = "ponte", set()
            out.append(MappedArgument(
                id=argument.id, layer=layer, conclusion=argument.conclusion,
                premises=sorted(argument.premises), rules=used,
                top_rule=argument.top_rule.id if argument.top_rule else None,
                status=status[argument.id],
                holders=[k for k in present if k in holders],
                strength=(preferences.argument_strength(argument)
                          if preferences is not None else None),
                origin=origin,
            ))
    return out


def arguments_by_rule(record) -> Dict[str, List[MappedArgument]]:
    """`{rule id: the arguments it tops}` -- the trace from the map's nodes,
    which are rules, to the arguments the solver actually built with them."""
    out: Dict[str, List[MappedArgument]] = {}
    for argument in mapped_arguments(record):
        if argument.top_rule:
            out.setdefault(argument.top_rule, []).append(argument)
    return out


def mapped_rules(record) -> List[MappedRule]:
    """Every rule of both layers, with its author and its fate."""
    from formalize.validate import parse_rule

    fallen = defeated_rules(record)
    rules: List[MappedRule] = []

    def add(rule_text: str, layer: str, entity, gloss: str) -> None:
        held = _holders(entity)
        ordered = [key for key in (*ADVERSARIES, *ADJUDICATORS) if key in held]
        ordered += sorted(held - set(ordered))
        perspective = ordered[0] if ordered else SHARED
        try:
            parsed = parse_rule(rule_text)
        except ValueError:
            return
        # `ParsedRule.is_undercutter` only recognises `¬r…`; the
        # legal-relevance layer undercuts named schemes (`¬cf2lrc_X`), so any
        # negated consequent that names a rule is an undercut here.
        target = (parsed.consequent[1:]
                  if parsed.consequent.startswith("¬") else None)
        parsed_rules.append((parsed, layer, perspective or SHARED, gloss, target,
                             rule_text, ordered))

    parsed_rules = []
    for meta in record.rules_meta:
        add(meta.rule, "cif", meta, meta.gloss_pt)
    if record.lrc is not None:
        for rule in record.lrc.scheme_rules:
            add(rule.rule, "lrc", rule, rule.gloss_pt)

    known = {parsed.id for parsed, *_ in parsed_rules}
    for parsed, layer, perspective, gloss, target, rule_text, held in parsed_rules:
        rules.append(MappedRule(
            id=parsed.id, body=rule_text, layer=layer,
            perspective=_canon(perspective) or SHARED,
            gloss=gloss, attacks=target if target in known else None,
            defeated=parsed.id in fallen, label=_rule_label(parsed, known),
            consequent=parsed.consequent, antecedents=list(parsed.antecedents),
            holders=list(held),
        ))
    return rules


def short_literal(literal: str) -> str:
    """A legal-relevance literal at a size a diagram can carry."""
    from .lrc import split_lrc_literal

    negated = literal.startswith("¬")
    body = literal[1:] if negated else literal
    split = split_lrc_literal(body)
    if split is None:
        return literal
    predicate, arguments = split
    template = _SHORT.get(predicate)
    if not template:
        return literal
    try:
        rendered = template.format(*arguments)
    except IndexError:
        return literal
    return f"¬{rendered}" if negated else rendered


def _rule_label(parsed, known_rules: Set[str]) -> str:
    """The rule as the map draws it: short literals, capped antecedents, and
    no consequent for an undercut -- the arrow already says what it hits."""
    antecedents = [short_literal(ant) for ant in parsed.antecedents]
    if len(antecedents) > _MAX_ANTECEDENTS:
        hidden = len(antecedents) - _MAX_ANTECEDENTS
        antecedents = antecedents[:_MAX_ANTECEDENTS] + [f"(+{hidden})"]
    head = " AND ".join(antecedents)
    consequent = parsed.consequent
    if consequent.startswith("¬") and consequent[1:] in known_rules:
        return f"{head}\n⇒ afasta"
    return f"{head}\n⇒ {short_literal(consequent)}"


def _wrap_label(text: str, width: int = 26) -> str:
    """Fold only the lines that are too long; the label already carries its
    own break between antecedents and consequent."""
    return "\\n".join(_wrap(line, width) for line in text.split("\\n"))


def _wrap(text: str, width: int = 24) -> str:
    words, lines, current = text.split(" "), [], ""
    for word in words:
        if current and len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return "\\n".join(lines)


#: What a lane shows when its owner moved nothing. Prakken's decision phase
#: makes this a substantive statement, not a gap: an adjudicator who moves no
#: argument has endorsed what is already there (§4.3, "all these decisions can
#: be made by either remaining silent or moving an argument").
SILENT_NOTE = "sem movimento"


#: Argument ids drawn on a rule node before the list is cut short.
_MAX_ARGUMENT_IDS = 3


def _argument_note(arguments: Sequence[MappedArgument]) -> str:
    """The argument ids a rule produced, as the node draws them."""
    if not arguments:
        return ""
    ids = [a.label for a in arguments]
    if len(ids) > _MAX_ARGUMENT_IDS:
        ids = ids[:_MAX_ARGUMENT_IDS] + [f"+{len(arguments) - _MAX_ARGUMENT_IDS}"]
    return ", ".join(ids)


def to_adjudication_dot(record, title: str = "", known: Sequence[str] = ()) -> str:
    """The adjudication map as Graphviz DOT.

    One box per perspective, grouped into an adjudicators lane and a parties
    lane; one node per rule, inside its author's box; one edge per undercut,
    crossing the lanes. It is the picture the single argument graph cannot
    draw, because there every rule belongs to the same anonymous theory.
    """
    from .graph_export import _dot_escape

    rules = mapped_rules(record)
    by_rule = arguments_by_rule(record)
    moved = {rule.perspective for rule in rules}
    # Everyone the case knows about, whether or not they moved a rule: a
    # silent adjudicator is a finding, and an invisible one is a bug.
    present = moved | {_canon(key) for key in known} | set(perspectives_in(record))
    by_perspective: Dict[str, List[MappedRule]] = {}
    for rule in rules:
        by_perspective.setdefault(rule.perspective, []).append(rule)

    # Transparent canvas so the card's background shows through in either
    # theme; lane and title text in a mid grey that reads on both, node text
    # left dark because the fills are light by design (a defeated rule has to
    # look defeated, and that is carried by colour).
    lines = ["digraph Adjudicacao {", "  compound=true;", '  rankdir="TB";',
             '  bgcolor="transparent";', '  fontname="Helvetica";',
             '  fontcolor="#8a8a8a";',
             '  node [fontname="Helvetica", fontsize=10, fontcolor="#222222"];',
             '  edge [fontname="Helvetica", fontsize=9, fontcolor="#8a8a8a"];',
             "  nodesep=0.4;", "  ranksep=0.8;"]
    if title:
        lines.append(f'  labelloc="t"; label="{_dot_escape(title)}"; fontsize=15;')

    def node(rule: MappedRule) -> str:
        style = _LANE_STYLE[rule.layer]
        fill = "#fdecea" if rule.defeated else style["fill"]
        color = "#c0392b" if rule.defeated else "#444444"
        pen = 1.8 if rule.defeated else 1.0
        arguments = by_rule.get(rule.id, [])
        tip = f"{rule.id}: {rule.body}"
        if rule.gloss:
            tip += f"\n\n{rule.gloss}"
        others = [key for key in rule.holders if key != rule.perspective]
        if others:
            tip += ("\n\nSustentada também por: "
                    + ", ".join(_label(key) for key in others))
        # The rule is the node; the arguments are what the solver built with
        # it. Naming them here is what lets a reader carry a node of this map
        # over to the argument graph, to the relevance report and to the
        # preference table, all of which speak in `A<n>`.
        if arguments:
            tip += "\n\nArgumentos: " + ", ".join(
                f"{a.label} ({a.status})" for a in arguments)
        else:
            tip += "\n\nNão produziu argumento: os antecedentes nunca foram satisfeitos."
        css = (f"argnode rulenode arg-{rule.id} layer-{rule.layer} "
               f'{"defeated" if rule.defeated else "standing"}')
        # A rule several voices hold on their own account is drawn in the
        # first holder's box -- a node sits in one box or none -- so the
        # count goes on the node itself. Without it the map reads as one
        # perspective's move, which is precisely what it is not.
        label = _wrap_label(rule.label)
        if len(rule.holders) > 1:
            label += f"\\n({len(rule.holders)} vozes)"
        note = _argument_note(arguments)
        label += f"\\n{note}" if note else "\\n(sem argumento)"
        return (f'    "{rule.id}" [shape={style["shape"]}, style="filled", '
                f'fillcolor="{fill}", color="{color}", penwidth={pen}, '
                f'label="{_dot_escape(label)}", '
                f'tooltip="{_dot_escape(tip)}", class="{css}"];')

    for lane_label, keys in LANES:
        members = [key for key in keys if key in present]
        if not members:
            continue
        if keys == (SHARED,):
            # Nobody's move: one box, no inner lane for a single perspective.
            lines.append('  subgraph "cluster_lane_comum" {')
            lines.append(f'    label="{lane_label}"; fontsize=12; '
                         'color="#bbbbbb"; fontcolor="#8a8a8a"; style="dotted"; '
                         'labeljust="l";')
            for rule in by_perspective.get(SHARED, []):
                lines.append("  " + node(rule))
            lines.append("  }")
            continue
        lines.append(f'  subgraph "cluster_lane_{lane_label}" {{')
        lines.append(f'    label="{lane_label}"; fontsize=13; color="#999999"; '
                     'fontcolor="#8a8a8a"; style="dashed"; labeljust="l";')
        for key in members:
            lines.append(f'    subgraph "cluster_p_{key}" {{')
            lines.append(f'      label="{_dot_escape(_label(key).upper())}"; '
                         'fontsize=11; color="#bbbbbb"; fontcolor="#8a8a8a"; '
                         'style="dashed";')
            members_rules = by_perspective.get(key, [])
            for rule in members_rules:
                lines.append("  " + node(rule))
            if not members_rules:
                lines.append(
                    f'      "silent_{key}" [shape=plaintext, fontsize=9, '
                    f'fontcolor="#8a8a8a", label="{SILENT_NOTE}"];')
            lines.append("    }")
        lines.append("  }")

    anchors = [(by_perspective[key][0].id if by_perspective.get(key)
                else f"silent_{key}")
               for _, keys in LANES
               for key in keys
               if key in present]
    for upper, lower in zip(anchors, anchors[1:]):
        lines.append(f'  "{upper}" -> "{lower}" [style=invis, weight=10];')

    # Support: one rule's conclusion feeding another's antecedent. Drawn
    # faintly, because it is the plumbing -- but without it `suca` looks
    # unconnected when it is precisely what makes the `sc` defences fire.
    for source in rules:
        if not source.consequent or source.consequent.startswith("¬"):
            continue
        for target in rules:
            if target.id == source.id or source.consequent not in target.antecedents:
                continue
            lines.append(
                f'  "{source.id}" -> "{target.id}" [color="#b0b0b0", '
                'style="dashed", penwidth=1.0, arrowsize=0.6, '
                f'tooltip="{_dot_escape(source.id + " sustenta " + target.id)}", '
                f'class="argedge support from-{source.id} to-{target.id}"];')

    for rule in rules:
        if rule.attacks:
            lines.append(
                f'  "{rule.id}" -> "{rule.attacks}" [color="#c0392b", '
                f'style="solid", penwidth=1.8, arrowsize=0.8, '
                f'tooltip="{_dot_escape(rule.id + " afasta " + rule.attacks)}", '
                f'class="argedge defeat from-{rule.id} to-{rule.attacks}"];')

    # Head-on contradiction: two rules concluding complementary literals.
    # Drawn without an arrowhead because it runs both ways -- which is
    # precisely why it needs a preference to settle, and why the case that
    # has one is the case that needed `aspic.preferences`.
    for source, target in _rebutting_pairs(rules):
        lines.append(
            f'  "{source.id}" -> "{target.id}" [color="#c0392b", '
            'style="solid", penwidth=1.6, dir="none", constraint=false, '
            f'tooltip="{_dot_escape(source.id + " contradiz " + target.id + " -- rebut mutuo")}", '
            f'class="argedge rebut from-{source.id} to-{target.id}"];')

    lines.append("}")
    return "\n".join(lines)


def _rebutting_pairs(rules: Sequence[MappedRule]):
    """Unordered pairs of rules whose consequents are complementary."""
    from .solver import negate_literal

    seen = set()
    for source in rules:
        for target in rules:
            if source.id == target.id or not source.consequent:
                continue
            if target.consequent != negate_literal(source.consequent):
                continue
            key = tuple(sorted((source.id, target.id)))
            if key in seen:
                continue
            seen.add(key)
            yield source, target
