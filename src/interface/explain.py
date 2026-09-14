"""Generates the plain-Portuguese sentences of the didactic view -- strings
only, no HTML. Consumes a case's glosses and the solver's
`Argument`/`Attack` structures; `interface.didactic` assembles the output
into the page.
"""

"""Plain-Portuguese text generation for the didactic view (`interface.didactic`).

Pure functions only -- no HTML here, just strings -- built from a case's
`atom_glosses`/`rule_glosses` (see `cases.examples.CaseSpec`) plus the
already-computed `Argument`/`Attack` structure from `aspic.solver`. Kept
separate from `interface.didactic` (the HTML-assembly layer) so the sentence
templates can be unit-tested without touching rendering.
"""
from typing import Dict

from aspic.solver import Argument, ArgumentationFramework, Attack

STATUS_LABELS_PT = {
    "IN": "Aceito",
    "OUT": "Rejeitado",
    "UNDEC": "Indeterminado",
}


def status_label_pt(status: str) -> str:
    return STATUS_LABELS_PT.get(status, status)


def gloss(glosses: Dict[str, str], key: str) -> str:
    """A literal's plain-Portuguese gloss, falling back to the raw symbol
    (in backticks, so it's visually flagged as untranslated) if the case's
    glossary doesn't cover it -- this should only happen for literals that
    only appear in counterfactual/axiom-expanded frameworks, which the
    didactic view never renders as argument cards."""
    return glosses.get(key, f"`{key}`")


def case_glossary(case) -> Dict[str, str]:
    """Every symbol a reader can meet on screen, mapped to its reading.

    The interface shows formal tokens in three places a lawyer cannot avoid --
    the argument graph, the technical note under each card, and the fiche's
    tables -- so the page needs one lookup covering *both* frameworks at once:
    the cause-in-fact literals and rules, plus the legal-relevance layer's
    `CaFa_*`/`LeReCa_*` literals and scheme rules when the case has one.

    Kept here, next to the sentence templates, because it is the same
    question they answer ("how do I say this symbol in Portuguese?") and it
    stays a pure function of the `CaseSpec`.
    """
    glossary: Dict[str, str] = {**case.atom_glosses, **case.rule_glosses}
    if getattr(case, "lrc", None) is not None:
        glossary.update(case.lrc.atom_glosses)
        glossary.update(case.lrc.rule_glosses)
    return {code: text for code, text in glossary.items() if text}


def capitalize_pt(sentence: str) -> str:
    return sentence[0].upper() + sentence[1:] if sentence else sentence


def describe_argument(arg: Argument, atom_glosses: Dict[str, str],
                       rule_glosses: Dict[str, str]) -> str:
    """A plain-Portuguese paragraph describing how `arg` was derived.

    Atomic (premise) arguments are just the underlying fact. Derived
    arguments are phrased as "considering that <immediate sub-arguments'
    conclusions>, it follows that <conclusion>", followed by the top rule's
    gloss as the legal/causal rationale in parentheses.
    """
    if arg.is_atomic:
        return f"Fato do caso: {capitalize_pt(gloss(atom_glosses, arg.conclusion))}."

    premises_text = " e ".join(
        gloss(atom_glosses, sub.conclusion) for sub in arg.sub_arguments
    )
    conclusion_text = gloss(atom_glosses, arg.conclusion)
    sentence = f"Considerando que {premises_text}, conclui-se que {conclusion_text}."

    rule_id = arg.top_rule.id if arg.top_rule else None
    rationale = rule_glosses.get(rule_id, "") if rule_id else ""
    if rationale:
        sentence += f" ({rationale})"
    return sentence


def _defeat_status_sentence(is_defeat: bool) -> str:
    if is_defeat:
        return "Esse ataque foi aceito e afasta o argumento atacado."
    return "Esse ataque não foi suficiente para afastar o argumento atacado."


def describe_attack(af: ArgumentationFramework, attack: Attack, is_defeat: bool,
                     atom_glosses: Dict[str, str], rule_glosses: Dict[str, str]) -> str:
    """A plain-Portuguese paragraph describing one attack: what the
    attacking argument establishes, why that challenges the target, the
    underlying rationale (for undercuts, the attacking rule's gloss), and
    whether the attack actually succeeded as a defeat."""
    attacker = af.arguments[attack.attacker_id]
    target_sub = af.arguments[attack.target_subargument_id]

    if attack.attack_type == "undercut":
        sentence = capitalize_pt(gloss(atom_glosses, attacker.conclusion)) + "."
        rule_id = attacker.top_rule.id if attacker.top_rule else None
        rationale = rule_glosses.get(rule_id, "") if rule_id else ""
        if rationale:
            sentence += f" {rationale}"
    elif attack.attack_type == "rebut":
        sentence = (
            f"Este argumento conclui que {gloss(atom_glosses, attacker.conclusion)}, "
            f"o que contradiz diretamente a conclusão de que "
            f"{gloss(atom_glosses, target_sub.conclusion)}."
        )
    else:  # undermine
        sentence = (
            f"Este argumento estabelece que {gloss(atom_glosses, attacker.conclusion)}, "
            f"o que contesta diretamente o fato de que "
            f"{gloss(atom_glosses, attack.attacked_literal)}."
        )

    return f"{sentence} {_defeat_status_sentence(is_defeat)}"
