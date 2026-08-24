"""Reliability test: reproduce the cause-in-fact conclusions of Section 5
of Pisano, Prakken, Sartor & Liepina, "Modelling Cause-in-Fact in Legal
Cases through Defeasible Argumentation" (ICAIL 2025), against the ported
and adapted ASPIC+ solver.

Each test builds the argumentation theory exactly as given in the paper
(atoms, rules, knowledge base) and checks two things per case:
1. The grounded extension matches the paper's stated justified conclusions.
2. is_cause(phi, psi) matches the paper's explicit cause / non-cause claims.

The five cases' knowledge bases/rule models live in `aspic.examples` --
the same source `scripts/generate_graphs.py` uses to render their argument
graphs -- so this file only wires them up to the solver and its assertions.

Section 6 (Event Calculus reformulation with time points and first-order
rule instantiation) is out of scope: the solver is propositional.
"""
from aspic.examples import case_by_id
from aspic.solver import ArgumentationFramework


def test_asbestos_overdetermination():
    """Fairchild v Glenhaven (2002): exposure at any two of the three
    companies is sufficient for cancer, and each Ex_i is a cause of Di --
    overdetermination should not make any of them 'not a cause'."""
    case = case_by_id("asbestos")
    af = ArgumentationFramework(case.knowledge_base, case.causal_model)

    assert "Di" in af.justified_conclusions()
    assert af.is_cause("Ex1", "Di") is True
    assert af.is_cause("Ex2", "Di") is True
    assert af.is_cause("Ex3", "Di") is True


def test_double_shooting_preemption():
    """People v. Dlugash (1997): Bush's fatal shot preempts Dlugash's
    (already-dead-victim) shot. Bush's shooting is a cause of Geller's
    death; Dlugash's is not, since r4 undercuts r1."""
    case = case_by_id("double_shooting")
    af = ArgumentationFramework(case.knowledge_base, case.causal_model)

    assert "GeDi" in af.justified_conclusions()
    # Dlugash's argument chain is undercut, so DlKi should not be justified.
    assert "DlKi" not in af.justified_conclusions()

    assert af.is_cause("BuSh", "GeDi") is True
    assert af.is_cause("DlSh", "GeDi") is False


def test_childhood_leukaemia_omission():
    """Cassazione penale (2023): the child's leukaemia is a cause of death,
    but the parents' refusal of consent (an omission) is also a cause,
    detected via axiom-expansion enabling a new undercutting counterfactual
    argument (Definition 4.3, case 3)."""
    case = case_by_id("leukaemia")
    af = ArgumentationFramework(case.knowledge_base, case.causal_model)

    assert "ChDi" in af.justified_conclusions()
    assert af.is_cause("ChLe", "ChDi") is True
    assert af.is_cause("¬PaCo", "ChDi") is True


def test_car_accident_preemptive_negative_causation():
    """Saunders v Adams (1928): the driver's omission to brake is a cause
    of the accident; the brake malfunction is not, since the driver's
    omission also undercuts the malfunction's causal chain (r3)."""
    case = case_by_id("car_accident")
    af = ArgumentationFramework(case.knowledge_base, case.causal_model)

    assert "AcHa" in af.justified_conclusions()
    assert af.is_cause("¬DrPu", "AcHa") is True
    assert af.is_cause("BrMa", "AcHa") is False


def test_war_crime_ennoblement():
    """Ennoblement: the soldier's shooting causes the prisoner's death when
    he shoots; when he doesn't, the sergeant's shot (triggered by the
    soldier's omission) causes it instead -- both paths reach PrDi."""
    shoots = case_by_id("war_crime_soldier_shoots")
    soldier_shoots = ArgumentationFramework(shoots.knowledge_base, shoots.causal_model)
    assert "PrDi" in soldier_shoots.justified_conclusions()
    assert soldier_shoots.is_cause("SoSh", "PrDi") is True

    refuses = case_by_id("war_crime_soldier_refuses")
    soldier_refuses = ArgumentationFramework(refuses.knowledge_base, refuses.causal_model)
    assert "SeSh" in soldier_refuses.justified_conclusions()
    assert "PrDi" in soldier_refuses.justified_conclusions()
    assert soldier_refuses.is_cause("¬SoSh", "PrDi") is True
