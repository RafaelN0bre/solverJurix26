"""The sufficient-set decomposition (`aspic/sufficiency.py`) over the five
legal cases of Section 5, Pisano, Prakken, Sartor & Liepina (ICAIL 2025).

This module explains a NESS verdict; it does not pronounce one. So what is
pinned here is the *material*: which sets of conditions are jointly
sufficient for the effect, and which of their members are individually
necessary. The verdicts themselves live in `test_legal_cases.py`.

The last test is the one worth reading twice: it shows the case where a
purely deductive reading of NESS -- sufficiency and necessity over premise
sets, which is all this module computes -- cannot see a cause that the
argumentation-theoretic NESS of Definition 4.3 does see. That gap is why the
verdict is not computed from these sets.
"""
from aspic.solver import ArgumentationFramework
from aspic.sufficiency import necessary_elements, sufficient_sets


def test_asbestos_ness_sufficient_sets():
    """Fairchild v Glenhaven: any two of the three exposures form a NESS
    sufficient set for Di -- there should be exactly three, matching the
    'at least two of three companies' fact pattern."""
    kb = {"premises": ["Ex1", "Ex2", "Ex3"], "axioms": []}
    model = {
        "strict_rules": [],
        "defeasible_rules": [
            "r0: Ca => Di",
            "r1: Ex1 AND Ex2 => Ca",
            "r2: Ex2 AND Ex3 => Ca",
            "r3: Ex1 AND Ex3 => Ca",
        ],
    }
    af = ArgumentationFramework(kb, model)

    sets = {frozenset(s.elements) for s in sufficient_sets(af, "Di")}
    assert sets == {
        frozenset({"Ex1", "Ex2"}),
        frozenset({"Ex2", "Ex3"}),
        frozenset({"Ex1", "Ex3"}),
    }
    assert af.ness_cause("Ex1", "Di") is True
    assert af.ness_cause("Ex2", "Di") is True
    assert af.ness_cause("Ex3", "Di") is True


def test_double_shooting_ness_preemption():
    """Only Bush's (undefeated) causal chain forms a NESS sufficient set
    for Geller's death; Dlugash's is preempted, so it must not appear."""
    kb = {"premises": ["BuSh", "DlSh"], "axioms": []}
    model = {
        "strict_rules": [],
        "defeasible_rules": [
            "r0: BuSh => BuKi",
            "r1: DlSh => DlKi",
            "r2: BuKi => GeDi",
            "r3: DlKi => GeDi",
            "r4: BuKi => ¬r1",
        ],
    }
    af = ArgumentationFramework(kb, model)

    sets = {frozenset(s.elements) for s in sufficient_sets(af, "GeDi")}
    assert sets == {frozenset({"BuSh"})}
    assert af.ness_cause("BuSh", "GeDi") is True
    assert af.ness_cause("DlSh", "GeDi") is False


def test_car_accident_ness_preemptive_negative_causation():
    """The driver's omission forms the (only) NESS sufficient set for the
    accident; the brake malfunction's chain is undercut, so it must not
    contribute a sufficient set of its own."""
    kb = {"premises": ["BrMa", "¬DrPu"], "axioms": []}
    model = {
        "strict_rules": [],
        "defeasible_rules": [
            "r0: BrFa => AcHa",
            "r1: ¬DrPu => AcHa",
            "r2: BrMa => BrFa",
            "r3: ¬DrPu => ¬r2",
        ],
    }
    af = ArgumentationFramework(kb, model)

    sets = {frozenset(s.elements) for s in sufficient_sets(af, "AcHa")}
    assert sets == {frozenset({"¬DrPu"})}
    assert af.ness_cause("¬DrPu", "AcHa") is True
    assert af.ness_cause("BrMa", "AcHa") is False


def test_war_crime_ness_ennoblement():
    model = {
        "strict_rules": [],
        "defeasible_rules": [
            "r0: SoSh => PrDi",
            "r1: SeSh => PrDi",
            "r2: ¬SoSh => SeSh",
        ],
    }

    soldier_shoots = ArgumentationFramework({"premises": ["SoSh"], "axioms": []}, model)
    assert soldier_shoots.ness_cause("SoSh", "PrDi") is True

    soldier_refuses = ArgumentationFramework({"premises": ["¬SoSh"], "axioms": []}, model)
    assert soldier_refuses.ness_cause("¬SoSh", "PrDi") is True


def test_leukaemia_is_why_the_verdict_is_not_read_off_the_sets():
    """Childhood Leukaemia (omission), and the reason this module explains
    rather than decides.

    ChLe is literally in the one sufficient set for ChDi. `¬PaCo` is not --
    it never appears as a premise of any argument for ChDi, so no amount of
    sufficiency-and-necessity over these sets can reach it. Definition 4.3
    reaches it through axiom-expansion: asserting PaCo would *enable* a new
    undercutting counterargument, which is a form of relevance a deductive
    closure cannot express.

    A verdict computed from the sets would therefore have to answer "no"
    here, and "no" would be wrong. Hence `ness_cause` on the framework.
    """
    kb = {"premises": ["ChLe", "¬PaCo"], "axioms": []}
    model = {
        "strict_rules": [],
        "defeasible_rules": [
            "r0: ChLe => ChDi",
            "r1: PaCo => Chem",
            "r2: Chem => ¬r0",
        ],
    }
    af = ArgumentationFramework(kb, model)

    sets = {frozenset(s.elements) for s in sufficient_sets(af, "ChDi")}
    assert sets == {frozenset({"ChLe"})}

    # The sets reach ChLe and stop there...
    assert any("ChLe" in S.elements and "ChLe" in necessary_elements(
        S, "ChDi", list(af.rules.values())) for S in sufficient_sets(af, "ChDi"))
    assert not any("¬PaCo" in S.elements for S in sufficient_sets(af, "ChDi"))

    # ...while the verdict reaches both.
    assert af.ness_cause("ChLe", "ChDi") is True
    assert af.ness_cause("¬PaCo", "ChDi") is True
