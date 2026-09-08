"""Vocabulary and helpers for the legally-relevant-causation (LRC) layer of

    Pisano, Prakken & Sartor. "From Cause-in-Fact to Legally Relevant Cause
    through Argumentation." ICAIL 2026 (docs/papers/ICAIL2026causation.pdf).

The paper builds legal relevance as a *second* argumentation framework whose
knowledge base is the output of the cause-in-fact (CIF) evaluation: literals
`CaFa(phi, psi)` / `ButFor(phi, psi)` become premises, and rule schemes 2-8
derive `LeReCa(phi, psi)` or undercut it via one of the doctrinal defences.

`tests/test_legally_relevant_causes_2026.py` already hand-feeds exactly this
vocabulary for the paper's five worked examples; this module turns the naming
convention used there into code, so the formalization pipeline
(`formalize.bridge`) can derive the bridge premises from the solver instead of
asking an LLM to restate them.

Naming convention (taken verbatim from the tests): a literal becomes an
identifier fragment by dropping the negation sign and prefixing "not", so
`¬PaCo` -> `notPaCo` and `CaFa(¬PaCo, ChDi)` -> `CaFa_notPaCo_ChDi`.
"""
from typing import Dict, List, Optional, Set, Tuple

from .solver import ArgumentationFramework

#: Rule-id prefixes of the paper's schemes, mapped to a plain-Portuguese name.
SCHEMES: Dict[str, str] = {
    "cf2lrc": "Esquema geral (regra 2): uma causa de fato é, presumidamente, causa juridicamente relevante.",
    "nwo": "Exceção do \"não estaria melhor\" / no-worse-off (regra 3): existe uma causa paralela não ilícita que teria produzido o mesmo dano.",
    "sc": "Causa superveniente (regra 4): um evento posterior interrompe o nexo de relevância jurídica.",
    "suca": "Caracterização da causa superveniente (regra 5): evento posterior, necessário e inesperado.",
    "nofor": "Imprevisibilidade (regra 6): o efeito não era previsível a partir da causa.",
    "rpl": "Concretização do risco / risk playout (regra 7): o efeito é a realização de um risco previsível da causa, o que afasta a imprevisibilidade.",
    "unom": "Omissão sem dever de agir (regra 8): a conduta omitida não era juridicamente obrigatória.",
}

#: Schemes the paper does not have, added for judgments that dispute the
#: *nature of the duty to act* rather than the causal mechanism. The ICAIL
#: 2026 module has a single on/off `Obl` premise, which is enough for its own
#: examples and not enough for a case whose whole ratio is that a duty of
#: custody degraded into a generic duty of public security over three months:
#: there, whether `Obl` holds is itself the conclusion of an argument, and the
#: conflict between the two answers is a *rebut* with no undercut on either
#: side -- the one place a preference has to decide (`aspic.preferences`).
#:
#: They are numbered on from the paper's 2-8 so a reader can see at a glance
#: which schemes come from it and which do not.
EXTENSION_SCHEMES: Dict[str, str] = {
    "dvesp": "Dever específico (regra 9, extensão): a condição concreta da custódia gera dever específico de agir, e não mero dever genérico.",
    "dvgen": "Dever genérico (regra 10, extensão): o lapso temporal e a atuação autônoma de terceiros degradam o dever específico em dever genérico de segurança pública, afastando aquele.",
    "dvpre": "Prevalência do dever específico (regra 11, extensão): subsistindo o dever específico de custódia, a defesa do ato de terceiro não se sustenta.",
}
SCHEMES.update(EXTENSION_SCHEMES)

#: Defence schemes: those that (directly or indirectly) block legal relevance.
#: `dvgen` is one: it does not undercut `cf2lrc` itself, it removes the duty
#: that `unom` needs to be absent, which is the same blocking move one step
#: earlier.
DEFENCE_SCHEMES: Set[str] = {"nwo", "sc", "suca", "nofor", "unom", "dvgen"}

#: Predicates of the LRC language that take two arguments, e.g. `CaFa_X_Y`.
BINARY_PREDICATES: Tuple[str, ...] = (
    "CaFa", "ButFor", "LeReCa", "After", "Foreseeable", "ForeseeableRisk", "Playout",
)

#: Predicates of the LRC language that take one argument, e.g. `Om_X`.
UNARY_PREDICATES: Tuple[str, ...] = (
    "Om", "Obl", "Tortious", "Unexpected", "SupersedingCause",
)

#: The layer reasons over legal *qualifications*, and a judgment may qualify
#: a plain fact of the cause-in-fact layer directly ("the closed regime is
#: what makes the duty specific"). Such a premise carries no LRC predicate
#: and is not a vocabulary error; `is_lrc_literal` still reports False for it,
#: which is the honest answer, and callers that need a reading fall back to
#: the case's own atom glosses (`formalize.build.lrc_atom_glosses`).

ALL_PREDICATES: Tuple[str, ...] = BINARY_PREDICATES + UNARY_PREDICATES


def atom_token(literal: str) -> str:
    """Identifier fragment for `literal`: `¬PaCo` -> `notPaCo`, `PaCo` -> `PaCo`."""
    return f"not{literal[1:]}" if literal.startswith("¬") else literal


def token_atom(token: str) -> str:
    """Inverse of `atom_token`: `notPaCo` -> `¬PaCo`, `PaCo` -> `PaCo`."""
    return f"¬{token[3:]}" if token.startswith("not") and len(token) > 3 else token


def cafa(phi: str, psi: str) -> str:
    """`CaFa(phi, psi)`: phi is a cause in fact (NESS cause) of psi."""
    return f"CaFa_{atom_token(phi)}_{atom_token(psi)}"


def but_for(phi: str, psi: str) -> str:
    """`ButFor(phi, psi)`: phi is a but-for cause of psi (Definition 3.5)."""
    return f"ButFor_{atom_token(phi)}_{atom_token(psi)}"


def lereca(phi: str, psi: str) -> str:
    """`LeReCa(phi, psi)`: phi is a legally relevant cause of psi."""
    return f"LeReCa_{atom_token(phi)}_{atom_token(psi)}"


def scheme_of(rule_id: str) -> Optional[str]:
    """The scheme a rule id belongs to, e.g. `cf2lrc_notAtTe` -> `cf2lrc`.

    Longest-prefix match, so `cf2lrc` is never mistaken for `cf` and the
    bare ids used in the paper's own examples (`cf2lrc`, `unom`) also match.
    """
    for scheme in sorted(SCHEMES, key=len, reverse=True):
        if rule_id == scheme or rule_id.startswith(f"{scheme}_"):
            return scheme
    return None


def is_lrc_literal(literal: str) -> bool:
    """True for literals of the LRC language (ignoring any negation sign)."""
    base = literal[1:] if literal.startswith("¬") else literal
    return any(base.startswith(f"{p}_") for p in ALL_PREDICATES)


def split_lrc_literal(literal: str) -> Optional[Tuple[str, List[str]]]:
    """`CaFa_notPaCo_ChDi` -> `("CaFa", ["¬PaCo", "ChDi"])`, or None if the
    literal is not in the LRC language. Longest-prefix match again, so
    `ForeseeableRisk_X_Y` never parses as `Foreseeable` + `Risk_X`."""
    base = literal[1:] if literal.startswith("¬") else literal
    for predicate in sorted(ALL_PREDICATES, key=len, reverse=True):
        prefix = f"{predicate}_"
        if not base.startswith(prefix):
            continue
        rest = base[len(prefix):]
        arity = 2 if predicate in BINARY_PREDICATES else 1
        parts = rest.split("_", arity - 1) if arity > 1 else [rest]
        if len(parts) != arity or any(not p for p in parts):
            return None
        return predicate, [token_atom(p) for p in parts]
    return None


def build_framework(knowledge_base: Dict, causal_model: Dict,
                    preferences=None) -> ArgumentationFramework:
    """The LRC module as an ordinary ASPIC+ framework. Kept as a named
    function so callers read as the paper does ("a second framework whose
    knowledge base results from the cause-in-fact evaluation") rather than
    constructing a bare `ArgumentationFramework` and leaving the reader to
    infer which layer it belongs to.

    `preferences` is the same optional `aspic.preferences.PreferenceModel`
    the cause-in-fact layer takes. It matters more here: the paper's own
    schemes conflict by undercutting, which no preference touches, but a
    layer that also decides *which qualification holds* conflicts by
    rebutting, and there the ordering is what settles it."""
    return ArgumentationFramework(knowledge_base, causal_model,
                                  preferences=preferences)


def relevance_report(af: ArgumentationFramework, targets: List[str]) -> List[Dict]:
    """For each `LeReCa_*` target: whether it survives in the LRC framework
    and, when it does not, which defence scheme knocked it out.

    "Knocked it out" is read off the framework's own defeats: an accepted
    argument whose conclusion is `¬<rule id>` where that rule is the
    `cf2lrc_*` step deriving the target (or, one level up, the `nofor_*`
    step that the `rpl_*` scheme itself undercuts).
    """
    extension, _ = af.compute_grounded_extension()
    justified = af.justified_conclusions()

    # rule id -> the conclusion it derives, so a defeat on `¬rN` can be
    # reported against the target rN was supposed to establish.
    accepted_undercuts: Dict[str, List[str]] = {}
    for arg_id in extension:
        conclusion = af.arguments[arg_id].conclusion
        if conclusion.startswith("¬") and conclusion[1:] in af.rules:
            accepted_undercuts.setdefault(conclusion[1:], []).append(arg_id)

    report = []
    for target in targets:
        blockers = []
        for rule_id, rule in af.rules.items():
            if rule.consequent != target or rule_id not in accepted_undercuts:
                continue
            for attacker_id in accepted_undercuts[rule_id]:
                attacker = af.arguments[attacker_id]
                scheme = None
                for used in attacker.defeasible_rules + attacker.strict_rules:
                    scheme = scheme_of(used) or scheme
                blockers.append({
                    "undercut_rule": rule_id,
                    "attacker": attacker_id,
                    "attacker_rules": sorted(attacker.defeasible_rules + attacker.strict_rules),
                    "scheme": scheme,
                    "scheme_pt": SCHEMES.get(scheme, "") if scheme else "",
                })
        report.append({
            "target": target,
            "justified": target in justified,
            "blocked_by": blockers,
        })
    return report
