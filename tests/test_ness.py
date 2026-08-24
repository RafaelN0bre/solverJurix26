"""Reliability test for the classical NESS module (aspic/ness.py) against
the same five legal cases from Section 5 of Pisano, Prakken, Sartor &
Liepina (ICAIL 2025), and an explicit demonstration of where plain NESS
falls short of the paper's full argumentation-based cause (Definition 4.3)
-- which is exactly the gap the paper's own contribution closes.
"""
from aspic.ness import is_ness_cause, sufficient_sets
from aspic.solver import ArgumentationFramework


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
    assert is_ness_cause(af, "Ex1", "Di") is True
    assert is_ness_cause(af, "Ex2", "Di") is True
    assert is_ness_cause(af, "Ex3", "Di") is True


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
    assert is_ness_cause(af, "BuSh", "GeDi") is True
    assert is_ness_cause(af, "DlSh", "GeDi") is False


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
    assert is_ness_cause(af, "¬DrPu", "AcHa") is True
    assert is_ness_cause(af, "BrMa", "AcHa") is False


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
    assert is_ness_cause(soldier_shoots, "SoSh", "PrDi") is True

    soldier_refuses = ArgumentationFramework({"premises": ["¬SoSh"], "axioms": []}, model)
    assert is_ness_cause(soldier_refuses, "¬SoSh", "PrDi") is True


def test_leukaemia_beyond_ness():
    """Childhood Leukaemia (omission): ChLe is a plain NESS cause of ChDi
    (it is literally in the sufficient set). ¬PaCo is NOT -- it never
    appears as a premise of any argument for ChDi, so classical NESS
    sufficiency/necessity cannot detect it. The paper's Definition 4.3
    catches it anyway (already covered by test_legal_cases.py) via
    axiom-expansion: adding PaCo would *enable* a new undercutting
    counterargument, which is a form of relevance NESS was never designed
    to express. This test pins down that gap explicitly.
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

    assert is_ness_cause(af, "ChLe", "ChDi") is True
    assert is_ness_cause(af, "¬PaCo", "ChDi") is False  # plain NESS misses it

    assert af.is_cause("¬PaCo", "ChDi") is True  # Definition 4.3 catches it
