"""Reliability tests for the material that is NEW in the ICAIL 2026
follow-up paper (docs/papers/ICAIL2026causation.pdf), "From Cause-in-Fact
to Legally Relevant Cause through Argumentation" (Pisano, Prakken & Sartor),
compared to the ICAIL 2025 paper already covered by test_legal_cases.py and
test_ness.py ("Modelling Cause-in-Fact in Legal Cases through Defeasible
Argumentation", Pisano, Prakken, Sartor & Liepina).

Comparing the two papers (docs/papers/ICAIL2025causation.pdf vs.
docs/papers/ICAIL2026causation.pdf):

1. Cause-in-fact itself is essentially unchanged. 2026's Definition 3.4
   "NESS Cause" is a terminological/presentational refinement of 2025's
   Definition 4.3 "Cause" (same explanation-breaking-under-axiom-expansion
   idea, now phrased directly in terms of explanations and attacks rather
   than the old three-case enumeration) -- it has no behavioural difference
   for this solver, and `ArgumentationFramework.is_cause` already implements
   it. The Asbestos/Fairchild v Glenhaven example is reused verbatim in
   both papers (see test_legal_cases.py::test_asbestos_overdetermination).

2. 2026 adds a genuinely NEW, strictly stronger notion: "But-for Cause"
   (Definition 3.5) -- phi is a but-for cause of psi iff psi loses *all*
   justified arguments (not just one explanation) once phi is counterfactually
   removed. The paper uses this to sharpen the Asbestos case: each Ex_i is a
   NESS cause of Di, but *not* a but-for cause of it, since the other two
   exposures alone remain sufficient. See `test_asbestos_ness_but_not_but_for`
   below, and `ArgumentationFramework.but_for` in src/aspic/solver.py.

3. 2026's main contribution is an entirely new layer that 2025 does not
   have at all: "legally relevant causation" (module LRC), built via modular
   argumentation (Prakken & Sartor 2023) on top of the cause-in-fact module
   (CIF). The LRC layer formalises R.W. Wright's doctrine, under which
   cause-in-fact is only a *necessary* condition for legal responsibility;
   it can be defeated by three defences, each illustrated with a NEW legal
   case not present in the 2025 paper:
     - No-Worse-Off: Kingston v. Chicago & Northwestern Railway Co. (1927)
     - Superseding cause / actus novus interveniens:
       Watson v. Kentucky & Indiana Bridge & Railroad Co. (1910), and
       R v Jordan (1956)
     - Risk-playout limitation: Berry v. Sugar Notch Borough (1899)
   Section 6 of the 2026 paper further extends the LRC layer to omissions
   (a new case, Yania v. Bigan (1959), showing legal relevance is denied
   when there is no legal duty to act -- contrasted with the childhood
   leukaemia Cassazione Penale case already in test_legal_cases.py, which
   2026 reuses to show the omission defence does NOT apply when a duty to
   act does exist). 2026 also gestures at "adequate/proximate causality"
   and "increase in probability" doctrines and reframes the War Crime /
   ennoblement example from 2025 as a legal-relevance question rather than
   a cause-in-fact one -- but gives no concrete rule/knowledge-base
   instantiation for any of these three, only prose sketches deferring the
   predicates (CausesNormally, IncreasesProbability) to "a further
   reasoning module"; they are therefore not reproducible as solver tests
   and are omitted here.

This solver has no built-in notion of "modules" or output-input bridge
rules (Prakken & Sartor 2023's modular argumentation), so each LRC test
below follows the paper's own presentation: it hand-feeds the cause-in-fact
facts (CaFa_x_y literals) as premises of a *second*, independent
ArgumentationFramework representing the LRC module -- exactly as the paper
itself does when it writes "let us now assume a second framework ...
containing the following knowledge base resulting from the cause-in-fact
evaluation" for each of its worked examples.
"""
from aspic.solver import ArgumentationFramework


def test_asbestos_ness_but_not_but_for():
    """ICAIL 2026, Section 3: the same Fairchild v Glenhaven asbestos case
    as test_legal_cases.py::test_asbestos_overdetermination, now used to
    illustrate the paper's new But-for Cause (Definition 3.5), which is
    strictly stronger than NESS Cause (Definition 3.4, i.e. `is_cause`).

    Since exposure at any *two* of the three employers suffices to cause
    the cancer, removing any single Ex_i still leaves a sufficient pair of
    the other two -- so no Ex_i is individually necessary (but-for) for the
    death, even though each one is a NESS cause (each is part of some
    minimal sufficient explanation)."""
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

    assert af.is_cause("Ex1", "Di") is True
    assert af.is_cause("Ex2", "Di") is True
    assert af.is_cause("Ex3", "Di") is True

    assert af.but_for("Ex1", "Di") is False
    assert af.but_for("Ex2", "Di") is False
    assert af.but_for("Ex3", "Di") is False


def test_kingston_no_worse_off():
    """No-Worse-Off exception (ICAIL 2026, Section 5): Kingston v. Chicago
    & Northwestern Railway Co. (1927). The defendant negligently set a
    fire (DeFi); an unrelated, non-tortious fire of unknown origin (UnFi)
    merged with it; either fire alone sufficed to destroy the property
    (De). Both are causes-in-fact (overdetermination), but the defendant's
    fire is not a *legally relevant* cause, since the harm would have
    occurred anyway from the parallel non-tortious fire.

    Atoms: defendant sets fire (DeFi); unknown second fire (UnFi);
    property ignites (Ig); property destroyed (De)."""
    cif_kb = {"premises": ["DeFi", "UnFi"], "axioms": []}
    cif_model = {
        "strict_rules": [],
        "defeasible_rules": [
            "r0: Ig => De",
            "r1: DeFi => Ig",
            "r2: UnFi => Ig",
        ],
    }
    cif = ArgumentationFramework(cif_kb, cif_model)
    assert cif.is_cause("DeFi", "De") is True
    assert cif.is_cause("UnFi", "De") is True

    # Legally-relevant-causation layer: CaFa_x_y below are the (hand-fed)
    # outputs of the cause-in-fact evaluation above.
    lrc_kb = {
        "premises": ["CaFa_DeFi_De", "CaFa_UnFi_De", "¬Tortious_UnFi"],
        "axioms": [],
    }
    lrc_model = {
        "strict_rules": [],
        "defeasible_rules": [
            # General scheme (rule 2 in the paper): a cause-in-fact is
            # presumably a legally relevant cause.
            "cf2lrc_DeFi: CaFa_DeFi_De => LeReCa_DeFi_De",
            "cf2lrc_UnFi: CaFa_UnFi_De => LeReCa_UnFi_De",
            # No-Worse-Off exception (rule 3): a parallel non-tortious
            # cause-in-fact undercuts the general scheme for DeFi.
            "nwo_DeFi: CaFa_UnFi_De AND ¬Tortious_UnFi => ¬cf2lrc_DeFi",
        ],
    }
    lrc = ArgumentationFramework(lrc_kb, lrc_model)

    assert "LeReCa_UnFi_De" in lrc.justified_conclusions()
    assert "LeReCa_DeFi_De" not in lrc.justified_conclusions()


def test_watson_superseding_cause_match_drop():
    """Superseding-cause exception (ICAIL 2026, Section 5): Watson v.
    Kentucky & Indiana Bridge & Railroad Co. (1910). The defendant railroad
    spilled gasoline (Ga); three hours later Duerr dropped a match (Ma),
    igniting the vapours (Ig). Since Ma was a necessary (but-for), highly
    unexpected event that intervened after Ga, it is a superseding cause
    that relieves the railroad of legal responsibility -- even though Ga
    remains a cause-in-fact (indeed a but-for cause) of Ig.

    Atoms: defendant spills gasoline (Ga); Duerr drops match (Ma); vapours
    ignite (Ig)."""
    cif_kb = {"premises": ["Ga", "Ma"], "axioms": []}
    cif_model = {
        "strict_rules": [],
        "defeasible_rules": ["r0: Ga AND Ma => Ig"],
    }
    cif = ArgumentationFramework(cif_kb, cif_model)
    assert cif.is_cause("Ga", "Ig") is True
    assert cif.is_cause("Ma", "Ig") is True
    # Unlike the overdetermination cases, this rule is conjunctive, so
    # both antecedents are individually necessary: But-for Cause holds too.
    assert cif.but_for("Ga", "Ig") is True
    assert cif.but_for("Ma", "Ig") is True

    lrc_kb = {
        "premises": [
            "CaFa_Ga_Ig", "CaFa_Ma_Ig", "ButFor_Ma_Ig",
            "Unexpected_Ma", "After_Ma_Ga",
        ],
        "axioms": [],
    }
    lrc_model = {
        "strict_rules": [],
        "defeasible_rules": [
            "cf2lrc_Ga: CaFa_Ga_Ig => LeReCa_Ga_Ig",
            "cf2lrc_Ma: CaFa_Ma_Ig => LeReCa_Ma_Ig",
            # SuCa scheme (rule 5): Ma is characterised as a superseding
            # cause since it is a later, necessary, unexpected event.
            "suca_Ma: CaFa_Ga_Ig AND CaFa_Ma_Ig AND After_Ma_Ga "
            "AND Unexpected_Ma AND ButFor_Ma_Ig => SupersedingCause_Ma",
            # SC scheme (rule 4): a superseding cause undercuts the
            # general scheme for the earlier cause, Ga.
            "sc_Ga: SupersedingCause_Ma => ¬cf2lrc_Ga",
        ],
    }
    lrc = ArgumentationFramework(lrc_kb, lrc_model)

    assert "LeReCa_Ma_Ig" in lrc.justified_conclusions()
    assert "LeReCa_Ga_Ig" not in lrc.justified_conclusions()


def test_r_v_jordan_superseding_medical_negligence():
    """Superseding-cause exception, second example (ICAIL 2026, Section 5):
    R v Jordan (1956). Jordan stabbed the victim (JoSt), who was healing
    well in hospital when medical staff administered an antibiotic the
    victim was intolerant to (AdAn), causing death. The negligent
    administration -- a later, necessary, highly unexpected medical
    intervention -- is a superseding cause (actus novus interveniens) that
    relieves Jordan of legal responsibility for the death.

    Atoms: Jordan stabs the victim (JoSt); antibiotic administered (AdAn);
    victim dies (ViDe). Following the paper's prose (which states the
    conclusion via the SuCa/SC schemes without spelling out every
    antecedent), CaFa_AdAn_ViDe and ButFor_AdAn_ViDe are added as premises
    since the SuCa scheme (rule 5) requires them to fire."""
    lrc_kb = {
        "premises": [
            "CaFa_JoSt_ViDe", "CaFa_AdAn_ViDe", "ButFor_AdAn_ViDe",
            "Unexpected_AdAn", "After_AdAn_JoSt",
        ],
        "axioms": [],
    }
    lrc_model = {
        "strict_rules": [],
        "defeasible_rules": [
            "cf2lrc_JoSt: CaFa_JoSt_ViDe => LeReCa_JoSt_ViDe",
            "suca_AdAn: CaFa_JoSt_ViDe AND CaFa_AdAn_ViDe AND After_AdAn_JoSt "
            "AND Unexpected_AdAn AND ButFor_AdAn_ViDe => SupersedingCause_AdAn",
            "sc_JoSt: SupersedingCause_AdAn => ¬cf2lrc_JoSt",
        ],
    }
    lrc = ArgumentationFramework(lrc_kb, lrc_model)

    assert "LeReCa_JoSt_ViDe" not in lrc.justified_conclusions()


def test_berry_v_sugar_notch_risk_playout():
    """Risk-playout limitation (ICAIL 2026, Section 5): Berry v. Sugar
    Notch Borough (1899). The plaintiff was speeding in violation of a
    local ordinance (PlSp) when a tree fell on his car (TrFa), injuring him
    (In). Speeding is a cause-in-fact of the injury, but it is not
    legally relevant: being hit by a falling tree is not among the
    foreseeable risks that speeding creates (loss of control, being unable
    to stop in time), so the harm did not result from the "playing out" of
    any risk the speeding ordinance was meant to guard against.

    Atoms: plaintiff proceeds (PlPr); plaintiff speeds (PlSp); plaintiff is
    on the road (PlRo); tree falls (TrFa); plaintiff injured (In)."""
    cif_kb = {"premises": ["PlPr", "PlSp", "TrFa"], "axioms": []}
    cif_model = {
        "strict_rules": [],
        "defeasible_rules": [
            "r0: PlPr AND PlSp => PlRo",
            "r1: TrFa AND PlRo => In",
        ],
    }
    cif = ArgumentationFramework(cif_kb, cif_model)
    assert cif.is_cause("PlSp", "In") is True
    assert cif.is_cause("TrFa", "In") is True

    lrc_kb = {
        "premises": [
            "CaFa_PlSp_In", "CaFa_TrFa_In",
            "ForeseeableRisk_PlSp_SpCo", "¬Foreseeable_PlSp_In",
            "¬Playout_SpCo_In",
        ],
        "axioms": [],
    }
    lrc_model = {
        "strict_rules": [],
        "defeasible_rules": [
            "cf2lrc_PlSp: CaFa_PlSp_In => LeReCa_PlSp_In",
            "cf2lrc_TrFa: CaFa_TrFa_In => LeReCa_TrFa_In",
            # NoFor scheme (rule 6): non-foreseeability of the effect
            # generally undercuts legal relevance.
            "nofor_PlSp: ¬Foreseeable_PlSp_In => ¬cf2lrc_PlSp",
            # RPL scheme (rule 7): NoFor is itself undercut if the effect
            # is within the playout of a *foreseeable risk* of the cause --
            # which does not hold here (¬Playout_SpCo_In), so nofor_PlSp
            # stands and PlSp's legal relevance stays undercut.
            "rpl_PlSp: ForeseeableRisk_PlSp_SpCo AND Playout_SpCo_In "
            "=> ¬nofor_PlSp",
        ],
    }
    lrc = ArgumentationFramework(lrc_kb, lrc_model)

    assert "LeReCa_TrFa_In" in lrc.justified_conclusions()
    assert "LeReCa_PlSp_In" not in lrc.justified_conclusions()


def test_yania_v_bigan_omission_without_legal_duty():
    """Omission defence (ICAIL 2026, Section 6): Yania v. Bigan (1959).
    Miner Yania did not help his colleague Bigan, who had fallen into a
    water pit and drowned. Under US law there is (in general) no legal
    duty to rescue, so even though Yania's failure to help is a
    cause-in-fact of Bigan's death, it is not a legally relevant cause: the
    omission defence (UnOm) undercuts legal relevance whenever the omitted
    action was not itself legally obligatory.

    Atoms: Yania helps Bigan (YaHe); Bigan dies (BiDi). The omission is
    ¬YaHe; CaFa_notYaHe_BiDi below stands for CaFa(¬YaHe, BiDi)."""
    lrc_kb = {
        "premises": ["CaFa_notYaHe_BiDi", "Om_notYaHe", "¬Obl_YaHe"],
        "axioms": [],
    }
    lrc_model = {
        "strict_rules": [],
        "defeasible_rules": [
            "cf2lrc: CaFa_notYaHe_BiDi => LeReCa_notYaHe_BiDi",
            # UnOm scheme (rule 8): an omission undercuts legal relevance
            # if the omitted action was not itself obligatory.
            "unom: Om_notYaHe AND ¬Obl_YaHe => ¬cf2lrc",
        ],
    }
    lrc = ArgumentationFramework(lrc_kb, lrc_model)

    assert "LeReCa_notYaHe_BiDi" not in lrc.justified_conclusions()


def test_leukaemia_omission_with_legal_duty_stays_relevant():
    """Omission defence, contrasting case (ICAIL 2026, Section 6): the
    Cassazione Penale (2023) childhood-leukaemia case already modelled at
    the cause-in-fact level in
    test_legal_cases.py::test_childhood_leukaemia_omission. 2026 reuses it
    to show the OTHER side of the UnOm scheme (Definition 8): here parents
    were under a legal obligation to consent to treatment, so the omission
    defence's second antecedent (¬Obl_PaCo) is not satisfied, UnOm does not
    fire, and the parents' refusal of consent remains a legally relevant
    cause of the child's death.

    Atoms: parents consent (PaCo); child dies (ChDi); CaFa_notPaCo_ChDi
    stands for CaFa(¬PaCo, ChDi); Obl_PaCo stands for the parents being
    under a legal obligation to consent to treatment (which holds here,
    unlike in Yania v. Bigan above)."""
    lrc_kb = {
        "premises": ["CaFa_notPaCo_ChDi", "Om_notPaCo", "Obl_PaCo"],
        "axioms": [],
    }
    lrc_model = {
        "strict_rules": [],
        "defeasible_rules": [
            "cf2lrc: CaFa_notPaCo_ChDi => LeReCa_notPaCo_ChDi",
            "unom: Om_notPaCo AND ¬Obl_PaCo => ¬cf2lrc",
        ],
    }
    lrc = ArgumentationFramework(lrc_kb, lrc_model)

    assert "LeReCa_notPaCo_ChDi" in lrc.justified_conclusions()
