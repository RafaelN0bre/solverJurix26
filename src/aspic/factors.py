"""Factors: which side each fact pushes towards, and where they cancel out.

CATO (Aleven & Ashley) analyses a case as a set of *factors* -- stereotypical
fact patterns that predispose the decision towards one party -- organised in a
hierarchy of abstract factors. Prakken, Wyner, Bench-Capon & Atkinson,
"A formalization of argumentation schemes for legal case-based reasoning in
ASPIC+" (JLC 25(5), 2015; `docs/papers/`) turns that into ASPIC+ defeasible
rules: `pFactor(f)`/`dFactor(f)` for polarity, `parentFactor(f, abstract)` for
the hierarchy, and the partition functions `commonPfactors`, `currPfactors`,
`precPfactors` for comparing a case against a precedent.

**What this module implements, and what it deliberately does not.** Every one
of the paper's argumentation schemes -- CS1 and CS2 (deciding from a
precedent), U1.1 and U2.1 (distinguishing), CS3 and CS4 (emphasising
strengths) -- takes `outcome(prec)` or a `curr × prec` partition among its
premises. They need a case base. This repository has no precedent corpus: the
dossiers record no citations, and the formalized cases come from unrelated
domains. Those schemes are therefore *not* implemented; implementing them
against an empty case base would produce arguments that look like stare
decisis and are not.

Three pieces of the account need no precedent, and are implemented here:

* **polarity** -- `AtomOut.favors`, the `pFactor`/`dFactor` distinction;
* **the hierarchy** -- `AtomOut.abstract_factor`, the `parentFactor` relation;
* **cancellation** -- the paper's `cancels(f1, f2)`: two factors of opposite
  polarity sharing an ancestor, which "cancel each other out so as to remove
  the abstract factor from the case". Substitution is its sibling and *does*
  need two cases, so it is left out.

The partition algebra is applied here between **perspectives of one case**
rather than between a case and a precedent. That is an adaptation, not CATO:
there is no stare decisis in it, and nothing is inferred from another case's
outcome. What it buys is a factor-level reading of where two positions in the
same judgment actually part company.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

#: The polarity labels, and how they read on screen.
SIDE_LABELS = {
    "responsabilizacao": "pesa pela responsabilização",
    "exclusao": "pesa pela exclusão",
    "neutro": "não pesa para nenhum lado",
}

#: CATO's own names, for anyone reading the paper alongside the code.
CATO_SIDE = {"responsabilizacao": "pFactor", "exclusao": "dFactor"}

OPPOSITE = {"responsabilizacao": "exclusao", "exclusao": "responsabilizacao"}


@dataclass(frozen=True)
class Factor:
    code: str
    label: str
    side: str
    abstract: str
    perspectives: Tuple[str, ...]


def factors_of(record) -> List[Factor]:
    """Every atom of the case as a factor. Atoms with no polarity declared
    come back as neutral, which is how a record formalized before the field
    existed reads -- correctly, since nothing was claimed about them."""
    return [
        Factor(code=atom.code, label=atom.label_pt,
               side=getattr(atom, "favors", "neutro") or "neutro",
               abstract=getattr(atom, "abstract_factor", "") or "",
               perspectives=tuple(atom.perspectives))
        for atom in record.atoms
    ]


def is_annotated(record) -> bool:
    """Whether the record carries any polarity at all. A record without it is
    not a case where every fact is neutral -- it is a case nobody was asked
    about, and the interface has to say so rather than draw an empty balance."""
    return any(factor.side != "neutro" for factor in factors_of(record))


def by_side(record) -> Dict[str, List[Factor]]:
    grouped: Dict[str, List[Factor]] = {key: [] for key in SIDE_LABELS}
    for factor in factors_of(record):
        grouped[factor.side].append(factor)
    return grouped


def hierarchy(record) -> Dict[str, List[Factor]]:
    """`{abstract factor: the factors under it}`, skipping the unclassified."""
    tree: Dict[str, List[Factor]] = {}
    for factor in factors_of(record):
        if factor.abstract:
            tree.setdefault(factor.abstract, []).append(factor)
    return tree


def cancellations(record) -> List[Tuple[Factor, Factor, str]]:
    """Pairs of factors that cancel: opposite polarity, same abstract factor.

    The paper's `cancels(f1, f2)` (definition 20), restricted to what one case
    can support -- it is defined *within* a case, unlike `substitutes`, which
    compares a case with a precedent.

    A cancellation is where a dispute lives. `DevCustodia` and `DeverSegPub`
    under *the nature of the duty to act* is not two unrelated premises: it is
    one contested question with the two answers the judgment actually gave.
    """
    pairs: List[Tuple[Factor, Factor, str]] = []
    for abstract, group in hierarchy(record).items():
        for i, first in enumerate(group):
            for second in group[i + 1:]:
                if OPPOSITE.get(first.side) == second.side:
                    pro = first if first.side == "responsabilizacao" else second
                    against = second if pro is first else first
                    pairs.append((pro, against, abstract))
    return pairs


def balance(record, perspective: Optional[str] = None) -> Dict[str, object]:
    """The factor balance of the case, or of one perspective's reading of it.

    Restricted to a perspective, only the factors that perspective asserts are
    counted -- which is what makes the reading *its* reading and not the
    case's.
    """
    selected = [
        factor for factor in factors_of(record)
        if perspective is None or perspective in factor.perspectives
    ]
    pro = [f for f in selected if f.side == "responsabilizacao"]
    against = [f for f in selected if f.side == "exclusao"]
    return {
        "perspective": perspective,
        "pro": pro,
        "against": against,
        "neutral": [f for f in selected if f.side == "neutro"],
        "lean": ("responsabilizacao" if len(pro) > len(against)
                 else "exclusao" if len(against) > len(pro) else "empate"),
    }


# ----------------------------------------------------------------------
# The partition algebra, between perspectives
# ----------------------------------------------------------------------
def _codes(record, perspective: str, side: str) -> Set[str]:
    return {f.code for f in factors_of(record)
            if perspective in f.perspectives and f.side == side}


def partitions(record, left: str, right: str) -> Dict[str, List[str]]:
    """CATO's set operations, applied between two perspectives.

    `common*` is what both invoke; `left*`/`right*` is what only one does.
    The paper reads these against a precedent's outcome to argue a fortiori;
    here there is no outcome to read against, so they answer a narrower and
    more honest question: **on which facts do these two positions actually
    differ, and on which do they agree?**
    """
    out: Dict[str, List[str]] = {}
    for side, tag in (("responsabilizacao", "Pro"), ("exclusao", "Contra")):
        lhs, rhs = _codes(record, left, side), _codes(record, right, side)
        out[f"common{tag}"] = sorted(lhs & rhs)
        out[f"left{tag}"] = sorted(lhs - rhs)
        out[f"right{tag}"] = sorted(rhs - lhs)
    return out


def unclassified(record) -> List[str]:
    """Atoms with no abstract factor: the part of the hierarchy nobody built.

    Reported rather than hidden, because a hierarchy with holes silently
    under-reports cancellations -- two opposed factors can only cancel if
    somebody said they are about the same thing.
    """
    return sorted(f.code for f in factors_of(record) if not f.abstract)
