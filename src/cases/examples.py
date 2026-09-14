"""The eleven hardcoded case theories of the ICAIL 2025/2026 papers, as
executable `CaseSpec`s. Single source for the test suite
(`tests/test_legal_cases.py`), the figure generator
(`scripts/generate_graphs.py`) and, through `cases.catalog`, the interface.
"""

"""The executable case specifications: the eleven case theories of the two
ICAIL papers (2025's cause-in-fact cases, 2026's legal-relevance cases), as
the `CaseSpec`s the test suite, the figure generator and the interface consume.

The first block holds the five legal cases of Section 5, Pisano, Prakken,
Sartor & Liepina, "Modelling Cause-in-Fact in Legal Cases through Defeasible
Argumentation" (ICAIL 2025); the `LEGAL_CASES +=` block below appends the
ICAIL 2026 cases, each carrying its legal-relevance (LRC) layer.

This is the single source of truth for these cases' knowledge bases and rule
models -- both `tests/test_legal_cases.py` and `interface.graph_export` /
`scripts/generate_graphs.py` import from here, instead of each keeping its
own copy of the same five `kb`/`model` dicts.

The `expect_*` fields on `CausalQuery` are not illustrative guesses: they are
the actual outputs of `ArgumentationFramework.ness_cause` /
`ArgumentationFramework.but_for` for that (phi, psi) pair, and
`test_legal_cases.py` asserts them independently. Where the two notions
disagree, `note` spells out why -- these disagreements are the whole point of
walking through the cases (but-for's classic failure under overdetermination
and preemption).

`narrative_pt`, `atom_glosses`, `rule_glosses` and `note_pt` are the content
behind the didactic view (`interface.didactic`) aimed at legal professionals:
plain-Portuguese glosses for every literal/rule that actually appears in the
case's *base* framework (not the counterfactual axiom-expansions used by
`ness_cause`/`but_for` -- those stay inside the technical/English toggle,
which reuses `interface.report`'s existing English rendering unchanged).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CausalQuery:
    """One (phi, psi) causal question to run against a case's framework, and
    the two notions' verdicts on it: the NESS cause (ICAIL 2025 Definition
    4.3, renamed "NESS Cause" in ICAIL 2026 Definition 3.4) and `but_for`
    (ICAIL 2026 Definition 3.5)."""
    phi: str
    psi: str
    expect_ness: bool
    expect_but_for: bool
    note: str = ""
    note_pt: str = ""


@dataclass(frozen=True)
class LRCLayer:
    """The legally-relevant-causation module of the ICAIL 2026 follow-up paper
    ("From Cause-in-Fact to Legally Relevant Cause through Argumentation",
    Pisano, Prakken & Sartor), as a second argumentation framework layered on
    top of a case's cause-in-fact one.

    `knowledge_base` mixes premises of two very different provenances: the
    `CaFa_*`/`ButFor_*` literals, which are *computed* from the cause-in-fact
    framework (see `aspic.lrc` and `formalize.bridge`), and the doctrinal ones
    (`Om_*`, `Obl_*`, `Unexpected_*`, ...), which come from reading the
    judgment. `targets` lists the `LeReCa_*` conclusions worth asking about.

    The five ICAIL 2025 cases in `LEGAL_CASES` carry no LRC layer, so
    `CaseSpec.lrc` is None for them and they render exactly as before; the
    layer is populated for cases formalized from an annotated dossier.
    """
    knowledge_base: dict
    causal_model: dict
    targets: List[str] = field(default_factory=list)
    atom_glosses: Dict[str, str] = field(default_factory=dict)
    rule_glosses: Dict[str, str] = field(default_factory=dict)
    duty_basis_pt: str = ""


@dataclass(frozen=True)
class CaseSpec:
    """A full worked example: one ASPIC+ argumentation theory plus the
    causal questions to ask of it."""
    id: str
    title: str
    narrative: str
    knowledge_base: dict
    causal_model: dict
    effect: str
    queries: List[CausalQuery] = field(default_factory=list)
    narrative_pt: str = ""
    atom_glosses: Dict[str, str] = field(default_factory=dict)
    rule_glosses: Dict[str, str] = field(default_factory=dict)
    lrc: Optional[LRCLayer] = None
    #: The case's ordering between defeasible arguments
    #: (`aspic.preferences.PreferenceModel`), or None for the basic ordering
    #: of Definition 2.11 -- which is what all five paper cases use.
    preferences: Optional[object] = None
    origin: str = "paper"
    #: Papers to which the case belongs. `leukaemia` belongs to both: cause in
    #: fact in ICAIL 2025, reused in 2026 to show the
    #: other side of the omission scheme (there was a duty to act).
    papers: List[str] = field(default_factory=lambda: ["icail2025"])


LEGAL_CASES: List[CaseSpec] = [
    CaseSpec(
        id="asbestos",
        title="Fairchild v Glenhaven (2002) — Overdetermination",
        narrative=(
            "The claimant was exposed to asbestos at three employers (Ex1, Ex2, "
            "Ex3); any *two* of the three exposures are, on their own, sufficient "
            "to cause the cancer (Ca), which defeasibly causes death (Di). Since "
            "the three sufficient pairs overlap, no single exposure is "
            "individually necessary for Di -- yet the paper's cause-in-fact test "
            "still counts each Ex_i as a cause, unlike the stricter but-for test."
        ),
        narrative_pt=(
            "A vítima foi exposta ao amianto em três empregadores diferentes. "
            "Basta a exposição em quaisquer dois deles, isoladamente, para causar "
            "o câncer — que por sua vez leva à morte. Como os três pares de "
            "exposição se sobrepõem, nenhuma exposição isolada é \"indispensável\" "
            "no sentido estrito (é um caso de sobredeterminação causal), mas a "
            "análise ainda reconhece cada uma delas como causa da morte — "
            "diferente do teste do \"não fosse por\", que falha aqui."
        ),
        knowledge_base={"premises": ["Ex1", "Ex2", "Ex3"], "axioms": []},
        causal_model={
            "strict_rules": [],
            "defeasible_rules": [
                "r0: Ca => Di",
                "r1: Ex1 AND Ex2 => Ca",
                "r2: Ex2 AND Ex3 => Ca",
                "r3: Ex1 AND Ex3 => Ca",
            ],
        },
        effect="Di",
        atom_glosses={
            "Ex1": "a vítima foi exposta ao amianto no empregador 1",
            "Ex2": "a vítima foi exposta ao amianto no empregador 2",
            "Ex3": "a vítima foi exposta ao amianto no empregador 3",
            "Ca": "a vítima contraiu a doença (mesotelioma)",
            "Di": "a vítima morreu em decorrência da doença",
        },
        rule_glosses={
            "r0": "Contrair a doença leva, presumidamente, à morte.",
            "r1": "A exposição nos empregadores 1 e 2, por si só, já é suficiente para causar a doença — não é preciso mais nada.",
            "r2": "A exposição nos empregadores 2 e 3, por si só, também já é suficiente para causar a doença.",
            "r3": "A exposição nos empregadores 1 e 3, por si só, também já é suficiente para causar a doença.",
        },
        queries=[
            CausalQuery(
                "Ex1", "Di", expect_ness=True, expect_but_for=False,
                note="Overdetermination: removing Ex1 still leaves Ex2+Ex3 sufficient (r2), so but-for fails even though Ex1 is a NESS cause.",
                note_pt="Sobredeterminação: mesmo removendo hipoteticamente a exposição no empregador 1, a exposição nos empregadores 2 e 3 continua sendo suficiente para causar a doença — por isso o teste do \"não fosse por\" falha, mesmo a exposição 1 sendo reconhecida como causa.",
            ),
            CausalQuery(
                "Ex2", "Di", expect_ness=True, expect_but_for=False,
                note="Same overdetermination pattern via the other two sufficient pairs (r1, r3).",
                note_pt="Mesmo padrão de sobredeterminação, agora pelos pares empregador 1+2 e 1+3.",
            ),
            CausalQuery(
                "Ex3", "Di", expect_ness=True, expect_but_for=False,
                note="Same overdetermination pattern via the other two sufficient pairs (r1, r2).",
                note_pt="Mesmo padrão de sobredeterminação, agora pelos pares empregador 1+2 e 2+3.",
            ),
        ],
    ),
    CaseSpec(
        id="double_shooting",
        title="People v. Dlugash (1997) — Preemption",
        narrative=(
            "Bush (BuSh) and Dlugash (DlSh) both shoot the victim. Bush's shot "
            "kills first; because Geller was already dead, Dlugash's shot could "
            "not, as a matter of fact, have killed him -- r4 undercuts r1's "
            "applicability. Bush's shooting is a cause of Geller's death (GeDi); "
            "Dlugash's is not."
        ),
        narrative_pt=(
            "Bush e Dlugash atiraram na mesma vítima (Geller). O tiro de Bush "
            "matou primeiro; como a vítima já estava morta, o tiro de Dlugash não "
            "pode, de fato, tê-la matado — isso derruba a regra r1. O tiro de "
            "Bush é causa da morte de Geller; o de Dlugash não é."
        ),
        knowledge_base={"premises": ["BuSh", "DlSh"], "axioms": []},
        causal_model={
            "strict_rules": [],
            "defeasible_rules": [
                "r0: BuSh => BuKi",
                "r1: DlSh => DlKi",
                "r2: BuKi => GeDi",
                "r3: DlKi => GeDi",
                "r4: BuKi => ¬r1",
            ],
        },
        effect="GeDi",
        atom_glosses={
            "BuSh": "Bush atirou na vítima (Geller)",
            "DlSh": "Dlugash também atirou na vítima",
            "BuKi": "o tiro de Bush foi, por si só, letal",
            "DlKi": "o tiro de Dlugash foi, por si só, letal",
            "GeDi": "Geller morreu",
            "¬r1": "não é possível concluir, pela regra r1, que o tiro de Dlugash foi letal",
        },
        rule_glosses={
            "r0": "Quando alguém atira na vítima, presume-se que esse tiro, isoladamente, foi letal.",
            "r1": "O mesmo raciocínio se aplicaria, isoladamente, ao tiro de Dlugash.",
            "r2": "Um tiro letal de Bush é presumidamente a causa da morte de Geller.",
            "r3": "Um tiro letal de Dlugash seria, isoladamente, presumidamente a causa da morte de Geller.",
            "r4": "Como o tiro de Bush já havia matado a vítima, o tiro de Dlugash não pode, de fato, ter sido letal — não se mata quem já está morto. Por isso essa regra ataca diretamente a possibilidade de aplicar a regra r1.",
        },
        queries=[
            CausalQuery(
                "BuSh", "GeDi", expect_ness=True, expect_but_for=False,
                note="Classic preemption failure of but-for: axiom-expanding with ¬BuSh removes Bush's shot, which also removes r4's undercut, reviving Dlugash's r3 chain -- GeDi stays justified even though Bush's shot is the actual (NESS) cause.",
                note_pt="Caso clássico de falha do teste \"não fosse por\" (preempção): se, por hipótese, retirássemos o tiro de Bush, isso também removeria o ataque à regra r1, reabilitando a cadeia do tiro de Dlugash — a morte continuaria justificada mesmo assim. Ainda assim, o tiro de Bush é reconhecido como a causa real (pelo teste NESS e pela análise mais ampla).",
            ),
            CausalQuery(
                "DlSh", "GeDi", expect_ness=False, expect_but_for=False,
                note="Dlugash's chain is undercut by r4 and never justified in the first place, so it is not a cause under any of the three notions.",
                note_pt="A cadeia do tiro de Dlugash é bloqueada pela regra r4 e nunca chega a ser aceita — por isso não é causa em nenhum dos três testes.",
            ),
        ],
    ),
    CaseSpec(
        id="leukaemia",
        title="Cassazione penale (2023) — Omission",
        narrative=(
            "The child had leukaemia (ChLe) and the parents refused consent to "
            "chemotherapy (¬PaCo); the child died (ChDi). ChLe is a plain NESS "
            "cause (it is literally in the sufficient set). ¬PaCo is not -- it "
            "never appears as a premise of any argument for ChDi -- yet "
            "axiom-expanding with PaCo would enable Chem, which would undercut "
            "r0 (Definition 4.3, case 3), so the omission is still a cause under "
            "the paper's full notion."
        ),
        narrative_pt=(
            "A criança tinha leucemia e os pais recusaram consentimento para o "
            "tratamento; a criança morreu. A leucemia é uma causa evidente. Mas a "
            "recusa de consentimento também é uma causa: embora ela nunca "
            "apareça como premissa de nenhum argumento que conclui a morte, "
            "autorizar hipoteticamente o tratamento habilitaria a quimioterapia, "
            "que por sua vez derrubaria a regra que liga a leucemia à morte — "
            "evidenciando que a omissão dos pais também foi causalmente "
            "relevante, algo que o teste NESS clássico não enxerga."
        ),
        knowledge_base={"premises": ["ChLe", "¬PaCo"], "axioms": []},
        causal_model={
            "strict_rules": [],
            "defeasible_rules": [
                "r0: ChLe => ChDi",
                "r1: PaCo => Chem",
                "r2: Chem => ¬r0",
            ],
        },
        effect="ChDi",
        atom_glosses={
            "ChLe": "a criança tinha leucemia",
            "¬PaCo": "os pais recusaram (não deram) consentimento para o tratamento",
            "ChDi": "a criança morreu",
            "PaCo": "os pais consentiram com o tratamento",
            "Chem": "a quimioterapia foi administrada",
            "¬r0": "não é possível concluir, pela regra r0, que a leucemia levou à morte",
        },
        rule_glosses={
            "r0": "A leucemia, presumidamente, leva à morte se nada mais for feito.",
            "r1": "Havendo consentimento dos pais, presume-se que a quimioterapia seria administrada.",
            "r2": "Se a quimioterapia fosse administrada, isso derrubaria a regra r0 — ou seja, o tratamento teria interrompido o curso presumido da doença para a morte.",
        },
        queries=[
            CausalQuery(
                "ChLe", "ChDi", expect_ness=True, expect_but_for=True,
                note="Straightforward direct cause: ChLe is the only element of the only sufficient set, and removing it removes ChDi entirely.",
                note_pt="Causa direta e evidente: é o único elemento do único conjunto suficiente para a morte, e removê-lo remove a morte por completo — os três testes concordam.",
            ),
            CausalQuery(
                "¬PaCo", "ChDi", expect_ness=True, expect_but_for=True,
                note="A negatively relevant cause: ¬PaCo is not a premise of any argument for ChDi, so a purely deductive reading of NESS misses it. The argumentation-theoretic NESS of Definition 4.3 catches it via axiom-expansion -- PaCo would enable Chem, which would undercut r0.",
                note_pt="O teste NESS clássico não enxerga esta causa, pois a recusa de consentimento nunca aparece como premissa de nenhum argumento que leva à morte. A análise mais ampla identifica que, hipoteticamente, o consentimento habilitaria a quimioterapia, que derrubaria a regra que liga a leucemia à morte — por isso a omissão É reconhecida como causa nessa análise mais completa.",
            ),
        ],
        lrc=LRCLayer(
            knowledge_base={
                "premises": ["Om_notPaCo", "Obl_PaCo"],
                "axioms": ["CaFa_notPaCo_ChDi"],
            },
            causal_model={
                "strict_rules": [],
                "defeasible_rules": [
                    "cf2lrc: CaFa_notPaCo_ChDi => LeReCa_notPaCo_ChDi",
                    "unom: Om_notPaCo AND ¬Obl_PaCo => ¬cf2lrc",
                ],
            },
            targets=["LeReCa_notPaCo_ChDi"],
        ),
        papers=["icail2025", "icail2026"],
    ),
    CaseSpec(
        id="car_accident",
        title="Saunders v Adams (1928) — Preemptive negative causation",
        narrative=(
            "The brakes had a pre-existing malfunction (BrMa) and the driver did "
            "not push the brake pedal in time (¬DrPu); the accident happened "
            "(AcHa). The driver's omission also undercuts the malfunction's "
            "causal chain (r3: since the pedal was never pushed, whether the "
            "faulty brakes would have failed is never actually tested), so "
            "¬DrPu is a cause of AcHa but BrMa is not."
        ),
        narrative_pt=(
            "Os freios do carro tinham um defeito preexistente e o motorista "
            "também não pisou no freio a tempo. A omissão do motorista derruba a "
            "cadeia causal do defeito nos freios: como ele nunca chegou a pisar "
            "no freio, nunca se testou, de fato, se os freios com defeito "
            "falhariam. Por isso a omissão do motorista é causa do acidente; o "
            "defeito nos freios não é."
        ),
        knowledge_base={"premises": ["BrMa", "¬DrPu"], "axioms": []},
        causal_model={
            "strict_rules": [],
            "defeasible_rules": [
                "r0: BrFa => AcHa",
                "r1: ¬DrPu => AcHa",
                "r2: BrMa => BrFa",
                "r3: ¬DrPu => ¬r2",
            ],
        },
        effect="AcHa",
        atom_glosses={
            "BrMa": "os freios tinham um defeito preexistente",
            "¬DrPu": "o motorista não pisou no freio a tempo",
            "BrFa": "os freios de fato falharam",
            "AcHa": "o acidente aconteceu",
            "¬r2": "não é possível concluir, pela regra r2, que o defeito nos freios se traduziu em falha real",
        },
        rule_glosses={
            "r0": "Uma falha real dos freios, presumidamente, causa o acidente.",
            "r1": "A omissão do motorista em pisar no freio, presumidamente, causa o acidente diretamente, independente do estado dos freios.",
            "r2": "Um defeito nos freios, presumidamente, se traduz numa falha real dos freios.",
            "r3": "Como o motorista sequer chegou a pisar no freio, nunca se testou, de fato, se os freios defeituosos falhariam — por isso essa regra ataca diretamente a possibilidade de aplicar a regra r2.",
        },
        queries=[
            CausalQuery(
                "¬DrPu", "AcHa", expect_ness=True, expect_but_for=False,
                note="Same preemption pattern as the double-shooting case: axiom-expanding with DrPu removes r3's undercut, reviving the BrMa-via-BrFa chain, so AcHa stays justified even though ¬DrPu is the actual (NESS) cause.",
                note_pt="Mesmo padrão de preempção do caso Dlugash: se, por hipótese, o motorista tivesse pisado no freio, isso removeria o ataque à regra r2, reabilitando a cadeia do defeito nos freios — o acidente continuaria justificado mesmo assim. Ainda assim, a omissão do motorista é reconhecida como a causa real.",
            ),
            CausalQuery(
                "BrMa", "AcHa", expect_ness=False, expect_but_for=False,
                note="The malfunction's chain is undercut by r3 and never justified, so it is not a cause under any of the three notions.",
                note_pt="A cadeia do defeito nos freios é bloqueada pela regra r3 e nunca chega a ser aceita — por isso não é causa em nenhum dos três testes.",
            ),
        ],
    ),
    CaseSpec(
        id="war_crime_soldier_shoots",
        title="War Crime / Ennoblement — soldier shoots",
        narrative=(
            "A soldier is ordered to shoot a prisoner. If he shoots (SoSh), his "
            "shot causes the prisoner's death (PrDi) directly."
        ),
        narrative_pt=(
            "Um soldado recebe ordem de atirar em um prisioneiro. Se ele atira, "
            "seu tiro é causa direta da morte do prisioneiro."
        ),
        knowledge_base={"premises": ["SoSh"], "axioms": []},
        causal_model={
            "strict_rules": [],
            "defeasible_rules": [
                "r0: SoSh => PrDi",
                "r1: SeSh => PrDi",
                "r2: ¬SoSh => SeSh",
            ],
        },
        effect="PrDi",
        atom_glosses={
            "SoSh": "o soldado atirou no prisioneiro",
            "PrDi": "o prisioneiro morreu",
        },
        rule_glosses={
            "r0": "Se o soldado atira, presume-se que isso causa a morte do prisioneiro.",
            "r1": "Se o sargento atira, presume-se que isso causa a morte do prisioneiro.",
            "r2": "Se o soldado se recusa a atirar, presume-se que o sargento atira em seu lugar.",
        },
        queries=[
            CausalQuery(
                "SoSh", "PrDi", expect_ness=True, expect_but_for=False,
                note="Preemption again: axiom-expanding with ¬SoSh triggers r2, so the sergeant's shot (SeSh, via r1) reinstates PrDi -- but-for fails, NESS does not.",
                note_pt="Mesmo padrão de preempção: se, por hipótese, o soldado se recusasse a atirar, isso acionaria a regra que faz o sargento atirar em seu lugar, e a morte continuaria justificada — mesmo assim, o tiro do soldado é reconhecido como a causa real quando ele de fato atira.",
            ),
        ],
    ),
    CaseSpec(
        id="war_crime_soldier_refuses",
        title="War Crime / Ennoblement — soldier refuses",
        narrative=(
            "If the soldier refuses to shoot (¬SoSh), the sergeant shoots "
            "instead (SeSh, via r2), and his shot causes the prisoner's death "
            "(PrDi) instead -- both paths reach the same effect."
        ),
        narrative_pt=(
            "Se o soldado se recusa a atirar, o sargento atira em seu lugar, e é "
            "o tiro do sargento que causa a morte do prisioneiro — os dois "
            "caminhos possíveis levam ao mesmo resultado."
        ),
        knowledge_base={"premises": ["¬SoSh"], "axioms": []},
        causal_model={
            "strict_rules": [],
            "defeasible_rules": [
                "r0: SoSh => PrDi",
                "r1: SeSh => PrDi",
                "r2: ¬SoSh => SeSh",
            ],
        },
        effect="PrDi",
        atom_glosses={
            "¬SoSh": "o soldado se recusou a atirar",
            "SeSh": "o sargento atirou no lugar dele",
            "PrDi": "o prisioneiro morreu",
        },
        rule_glosses={
            "r0": "Se o soldado atira, presume-se que isso causa a morte do prisioneiro.",
            "r1": "Se o sargento atira, presume-se que isso causa a morte do prisioneiro.",
            "r2": "Se o soldado se recusa a atirar, presume-se que o sargento atira em seu lugar.",
        },
        queries=[
            CausalQuery(
                "¬SoSh", "PrDi", expect_ness=True, expect_but_for=False,
                note="Symmetric preemption: axiom-expanding with SoSh triggers r0 directly, reinstating PrDi via the soldier's own shot -- but-for fails here too.",
                note_pt="Preempção simétrica: se, por hipótese, o soldado tivesse atirado, a regra r0 seria acionada diretamente e a morte continuaria justificada pelo tiro dele — mesmo assim, a recusa do soldado (que aciona o tiro do sargento) é reconhecida como a causa real neste cenário.",
            ),
        ],
    ),
]


def case_by_id(case_id: str) -> CaseSpec:
    for case in LEGAL_CASES:
        if case.id == case_id:
            return case
    raise KeyError(f"No case with id {case_id!r}")

# ----------------------------------------------------------------------
# ICAIL 2026: cases exercising the legal-relevance layer.
# ----------------------------------------------------------------------
#: Pisano, Prakken & Sartor, "From Cause-in-Fact to Legally Relevant Cause
#: through Argumentation” (ICAIL 2026), Sections 5 and 6. Each exercises a
#: LRC scheme; all follow the paper's order: CIF resolves, then
#: `CaFa(φ,ψ)` enters LRC **as an axiom** (equation 1).
#:
#: Two transcription choices: the paper states conclusions through
#: schemes without a causal model. In `r_v_jordan` and `yania_bigan`, CIF
#: is the smallest model producing the `CaFa` literals consumed by LRC, using
#: the conjunctive form the paper itself uses in Watson.
LEGAL_CASES += [
    CaseSpec(
        id="kingston",
        title="Kingston v. Chicago & Northwestern Railway (1927) — No-worse-off",
        narrative=(
            "The defendant negligently set a fire (DeFi); an unrelated, "
            "non-tortious fire of unknown origin (UnFi) merged with it, and "
            "either alone sufficed to destroy the property (De). Both are "
            "causes-in-fact, but the defendant's fire is not a legally relevant "
            "cause: the harm would have happened anyway from the parallel "
            "non-tortious fire."
        ),
        narrative_pt=(
            "O réu provocou um incêndio por negligência. Um segundo incêndio, "
            "de origem desconhecida e sem ilicitude, juntou-se a ele, e "
            "qualquer um dos dois, isolado, já destruía a propriedade. Os dois "
            "são causa de fato — mas o do réu não é causa juridicamente "
            "relevante, porque o dano teria ocorrido de todo modo por força do "
            "incêndio paralelo lícito."
        ),
        knowledge_base={"premises": ["DeFi", "UnFi"], "axioms": []},
        causal_model={
            "strict_rules": [],
            "defeasible_rules": ["r0: Ig => De", "r1: DeFi => Ig", "r2: UnFi => Ig"],
        },
        effect="De",
        queries=[
            CausalQuery(phi="DeFi", psi="De", expect_ness=True, expect_but_for=False,
                        note_pt="O incêndio do réu é causa de fato, mas a LRC o afasta."),
            CausalQuery(phi="UnFi", psi="De", expect_ness=True, expect_but_for=False,
                        note_pt="O incêndio lícito é causa de fato e segue relevante."),
        ],
        atom_glosses={
            "DeFi": "o réu provocou um incêndio por negligência",
            "UnFi": "um segundo incêndio, lícito e de origem desconhecida, ocorreu",
            "Ig": "a propriedade pegou fogo",
            "De": "a propriedade foi destruída",
        },
        rule_glosses={
            "r0": "pegando fogo, a propriedade é destruída",
            "r1": "o incêndio do réu faz a propriedade pegar fogo",
            "r2": "o incêndio lícito faz a propriedade pegar fogo",
        },
        lrc=LRCLayer(
            knowledge_base={
                "premises": ["¬Tortious_UnFi"],
                "axioms": ["CaFa_DeFi_De", "CaFa_UnFi_De"],
            },
            causal_model={
                "strict_rules": [],
                "defeasible_rules": [
                    "cf2lrc_DeFi: CaFa_DeFi_De => LeReCa_DeFi_De",
                    "cf2lrc_UnFi: CaFa_UnFi_De => LeReCa_UnFi_De",
                    "nwo_DeFi: CaFa_UnFi_De AND ¬Tortious_UnFi => ¬cf2lrc_DeFi",
                ],
            },
            targets=["LeReCa_DeFi_De", "LeReCa_UnFi_De"],
        ),
        papers=["icail2026"],
    ),
    CaseSpec(
        id="watson",
        title="Watson v. Kentucky & Indiana Bridge & Railroad (1910) — Superseding cause",
        narrative=(
            "The defendant railroad spilled gasoline (Ga); three hours later "
            "Duerr dropped a match (Ma), igniting the vapours (Ig). Ma is a "
            "later, necessary and highly unexpected event, so it is a "
            "superseding cause that relieves the railroad -- even though Ga "
            "remains a cause-in-fact of Ig."
        ),
        narrative_pt=(
            "A ferrovia derramou gasolina. Três horas depois, um terceiro "
            "deixou cair um fósforo e os vapores explodiram. O fósforo é evento "
            "posterior, necessário e altamente inesperado: é causa "
            "superveniente, e exonera a ferrovia — ainda que o derramamento "
            "continue sendo causa de fato."
        ),
        knowledge_base={"premises": ["Ga", "Ma"], "axioms": []},
        causal_model={"strict_rules": [], "defeasible_rules": ["r0: Ga AND Ma => Ig"]},
        effect="Ig",
        queries=[
            CausalQuery(phi="Ga", psi="Ig", expect_ness=True, expect_but_for=True,
                        note_pt="O derramamento é causa de fato; a LRC o afasta pela causa superveniente."),
            CausalQuery(phi="Ma", psi="Ig", expect_ness=True, expect_but_for=True,
                        note_pt="O fósforo é causa de fato e segue relevante."),
        ],
        atom_glosses={
            "Ga": "a ferrovia derramou gasolina",
            "Ma": "um terceiro deixou cair um fósforo",
            "Ig": "os vapores de gasolina se inflamaram",
        },
        rule_glosses={"r0": "gasolina derramada mais fósforo produzem a ignição"},
        lrc=LRCLayer(
            knowledge_base={
                "premises": ["Unexpected_Ma", "After_Ma_Ga"],
                "axioms": ["CaFa_Ga_Ig", "CaFa_Ma_Ig", "ButFor_Ma_Ig"],
            },
            causal_model={
                "strict_rules": [],
                "defeasible_rules": [
                    "cf2lrc_Ga: CaFa_Ga_Ig => LeReCa_Ga_Ig",
                    "cf2lrc_Ma: CaFa_Ma_Ig => LeReCa_Ma_Ig",
                    "suca_Ma: CaFa_Ga_Ig AND CaFa_Ma_Ig AND After_Ma_Ga "
                    "AND Unexpected_Ma AND ButFor_Ma_Ig => SupersedingCause_Ma",
                    "sc_Ga: SupersedingCause_Ma => ¬cf2lrc_Ga",
                ],
            },
            targets=["LeReCa_Ga_Ig", "LeReCa_Ma_Ig"],
        ),
        papers=["icail2026"],
    ),
    CaseSpec(
        id="r_v_jordan",
        title="R v Jordan (1956) — Superseding cause (medical negligence)",
        narrative=(
            "Jordan stabbed the victim (JoSt), who was healing when hospital "
            "staff administered an antibiotic the victim was intolerant to "
            "(AdAn), causing death (ViDe). The negligent administration is a "
            "later, necessary and highly unexpected intervention: a superseding "
            "cause relieving Jordan."
        ),
        narrative_pt=(
            "Jordan esfaqueou a vítima, que se recuperava bem no hospital "
            "quando a equipe médica administrou um antibiótico a que ela era "
            "intolerante, causando a morte. A administração negligente é "
            "intervenção posterior, necessária e altamente inesperada: causa "
            "superveniente, que exonera Jordan."
        ),
        knowledge_base={"premises": ["JoSt", "AdAn"], "axioms": []},
        causal_model={"strict_rules": [], "defeasible_rules": ["r0: JoSt AND AdAn => ViDe"]},
        effect="ViDe",
        queries=[
            CausalQuery(phi="JoSt", psi="ViDe", expect_ness=True, expect_but_for=True,
                        note_pt="A facada é causa de fato; a LRC a afasta pela negligência médica superveniente."),
            CausalQuery(phi="AdAn", psi="ViDe", expect_ness=True, expect_but_for=True,
                        note_pt="A administração do antibiótico é causa de fato."),
        ],
        atom_glosses={
            "JoSt": "Jordan esfaqueou a vítima",
            "AdAn": "a equipe médica administrou antibiótico a que a vítima era intolerante",
            "ViDe": "a vítima morreu",
        },
        rule_glosses={"r0": "a facada somada à administração do antibiótico produz a morte"},
        lrc=LRCLayer(
            knowledge_base={
                "premises": ["Unexpected_AdAn", "After_AdAn_JoSt"],
                "axioms": ["CaFa_JoSt_ViDe", "CaFa_AdAn_ViDe", "ButFor_AdAn_ViDe"],
            },
            causal_model={
                "strict_rules": [],
                "defeasible_rules": [
                    "cf2lrc_JoSt: CaFa_JoSt_ViDe => LeReCa_JoSt_ViDe",
                    "suca_AdAn: CaFa_JoSt_ViDe AND CaFa_AdAn_ViDe AND After_AdAn_JoSt "
                    "AND Unexpected_AdAn AND ButFor_AdAn_ViDe => SupersedingCause_AdAn",
                    "sc_JoSt: SupersedingCause_AdAn => ¬cf2lrc_JoSt",
                ],
            },
            targets=["LeReCa_JoSt_ViDe"],
        ),
        papers=["icail2026"],
    ),
    CaseSpec(
        id="berry_sugar_notch",
        title="Berry v. Sugar Notch Borough (1899) — Risk playout",
        narrative=(
            "The plaintiff was speeding in violation of an ordinance (PlSp) "
            "when a tree fell on his car (TrFa), injuring him (In). Speeding is "
            "a cause-in-fact, but being hit by a falling tree is not among the "
            "foreseeable risks speeding creates, so it is not legally relevant."
        ),
        narrative_pt=(
            "O autor trafegava acima do limite quando uma árvore caiu sobre o "
            "carro e o feriu. O excesso de velocidade é causa de fato — mas ser "
            "atingido por uma árvore não está entre os riscos previsíveis que a "
            "velocidade cria, e por isso não é causa juridicamente relevante."
        ),
        knowledge_base={"premises": ["PlPr", "PlSp", "TrFa"], "axioms": []},
        causal_model={
            "strict_rules": [],
            "defeasible_rules": ["r0: PlPr AND PlSp => PlRo", "r1: TrFa AND PlRo => In"],
        },
        effect="In",
        queries=[
            CausalQuery(phi="PlSp", psi="In", expect_ness=True, expect_but_for=True,
                        note_pt="A velocidade é causa de fato; a LRC a afasta por imprevisibilidade."),
            CausalQuery(phi="TrFa", psi="In", expect_ness=True, expect_but_for=True,
                        note_pt="A queda da árvore é causa de fato e segue relevante."),
        ],
        atom_glosses={
            "PlPr": "o autor seguia viagem",
            "PlSp": "o autor trafegava acima do limite de velocidade",
            "PlRo": "o autor estava naquele ponto da estrada",
            "TrFa": "uma árvore caiu sobre o carro",
            "In": "o autor ficou ferido",
        },
        rule_glosses={
            "r0": "seguindo viagem acima do limite, o autor chega àquele ponto da estrada",
            "r1": "a árvore caindo sobre quem está na estrada produz o ferimento",
        },
        lrc=LRCLayer(
            knowledge_base={
                "premises": ["ForeseeableRisk_PlSp_SpCo", "¬Foreseeable_PlSp_In",
                             "¬Playout_SpCo_In"],
                "axioms": ["CaFa_PlSp_In", "CaFa_TrFa_In"],
            },
            causal_model={
                "strict_rules": [],
                "defeasible_rules": [
                    "cf2lrc_PlSp: CaFa_PlSp_In => LeReCa_PlSp_In",
                    "cf2lrc_TrFa: CaFa_TrFa_In => LeReCa_TrFa_In",
                    "nofor_PlSp: ¬Foreseeable_PlSp_In => ¬cf2lrc_PlSp",
                    "rpl_PlSp: ForeseeableRisk_PlSp_SpCo AND Playout_SpCo_In "
                    "=> ¬nofor_PlSp",
                ],
            },
            targets=["LeReCa_PlSp_In", "LeReCa_TrFa_In"],
        ),
        papers=["icail2026"],
    ),
    CaseSpec(
        id="yania_bigan",
        title="Yania v. Bigan (1959) — Omission without a duty to act",
        narrative=(
            "Yania did not help Bigan, who had fallen into a water pit and "
            "drowned. Under US law there is in general no duty to rescue, so "
            "the omission -- a cause-in-fact of the death -- is not a legally "
            "relevant cause."
        ),
        narrative_pt=(
            "Yania não socorreu Bigan, que caíra numa cava d'água e se afogou. "
            "Não havendo, em regra, dever jurídico de socorro, a omissão — que é "
            "causa de fato da morte — não é causa juridicamente relevante."
        ),
        knowledge_base={"premises": ["¬YaHe"], "axioms": []},
        causal_model={"strict_rules": [], "defeasible_rules": ["r0: ¬YaHe => BiDi"]},
        effect="BiDi",
        queries=[
            CausalQuery(phi="¬YaHe", psi="BiDi", expect_ness=True, expect_but_for=True,
                        note_pt="A omissão é causa de fato; sem dever de agir, a LRC a afasta."),
        ],
        atom_glosses={
            "YaHe": "Yania socorre Bigan",
            "BiDi": "Bigan morreu afogado",
        },
        rule_glosses={"r0": "não socorrido, Bigan morre"},
        lrc=LRCLayer(
            knowledge_base={
                "premises": ["Om_notYaHe", "¬Obl_YaHe"],
                "axioms": ["CaFa_notYaHe_BiDi"],
            },
            causal_model={
                "strict_rules": [],
                "defeasible_rules": [
                    "cf2lrc: CaFa_notYaHe_BiDi => LeReCa_notYaHe_BiDi",
                    "unom: Om_notYaHe AND ¬Obl_YaHe => ¬cf2lrc",
                ],
            },
            targets=["LeReCa_notYaHe_BiDi"],
        ),
        papers=["icail2026"],
    ),
]
