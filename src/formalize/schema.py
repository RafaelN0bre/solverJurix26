"""Pydantic contracts for the dossier -> ASPIC+ formalization pipeline.

Two families of models live here:

* **Stage models** (`AtomsStageOut`, `RulesStageOut`, `QueriesStageOut`,
  `LrcStageOut`, `RepairStageOut`) are the JSON schemas handed to Gemini as
  `response_schema`. They are deliberately flat: Gemini's structured-output
  schema subset has no open-ended objects, so every "map" is a list of
  key/value records, and every field is required.

* **Record models** (`FormalizedCase` and friends) are what gets persisted to
  `data/translated/<case>/case.json`. That file is the single artifact the
  interface reads and the solver consumes -- `knowledge_base` and
  `causal_model` are already in `aspic.solver.ArgumentationFramework`'s exact
  input shape, so no adapter sits between the formalization and the solver.

Everything the LLM produces carries `evidence` (ids of `source_passages`) and
`dossier_refs` (ids of the dossier records it came from), so every literal and
every rule in the final framework can be traced back to a passage of the PDF.
"""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


def undercut_gloss(rule_gloss: str) -> str:
    """How to say "this rule does not apply here" in plain Portuguese.

    Shared by the cause-in-fact glossary below and by the legal-relevance
    one (`formalize.build.lrc_atom_glosses`) so both layers phrase an
    undercut the same way.
    """
    return f"não se sustenta o raciocínio: “{rule_gloss.strip().rstrip('.')}”"

AtomKind = Literal["fato", "intermediario", "resultado", "prova", "dever"]
#: Which side a factor favours, in the sense of CATO's `pFactor`/`dFactor`
#: (Aleven & Ashley; formalized in Prakken, Wyner, Bench-Capon & Atkinson,
#: "A formalization of argumentation schemes for legal case-based reasoning in
#: ASPIC+", JLC 2015). Named for the substantive question rather than for the
#: procedural position, because `recorrente`/`recorrido` swap depending on who
#: appealed while "does this fact push towards liability?" does not.
FactorSide = Literal["responsabilizacao", "exclusao", "neutro"]
AtomStatus = Literal["incontroverso", "controvertido", "rejeitado"]
RuleKind = Literal["causal", "excecao", "undercut", "rebut"]
CourtVerdict = Literal["acolhida", "rejeitada", "nao_decidida"]
#: Schemes 2-8 of ICAIL 2026, then the duty-qualification extensions of
#: `aspic.lrc.EXTENSION_SCHEMES`.
LrcScheme = Literal["cf2lrc", "nwo", "sc", "suca", "nofor", "rpl", "unom",
                    "dvesp", "dvgen", "dvpre"]


# ----------------------------------------------------------------------
# Stage 1 -- atoms
# ----------------------------------------------------------------------
class AtomOut(BaseModel):
    """One atom of the logical language, with its provenance in the dossier."""
    code: str = Field(description="Identificador CamelCase ASCII de 2 a 12 caracteres, sem acento e sem o sinal de negacao.")
    label_pt: str = Field(description="Glosa em portugues claro, na afirmativa, comecando em minuscula.")
    kind: AtomKind
    status: AtomStatus
    perspectives: List[str] = Field(description="Perspectivas que sustentam o atomo: recorrente, recorrido, relator, stf_final.")
    evidence: List[str] = Field(description="Ids de passagens de origem (src_*) que sustentam o atomo.")
    dossier_refs: List[str] = Field(description="Ids de registros do dossie (divg_*, unit_*, prec_*, synth_*) de onde o atomo foi extraido.")
    established: bool = Field(description="True se o atomo entra como premissa do framework (fato dado por posto, ainda que contestado por regra).")
    favors: FactorSide = Field(default="neutro", description="Para que lado o fato pesa: responsabilizacao, exclusao, ou neutro se nao pesa para nenhum.")
    abstract_factor: str = Field(default="", description="Codigo CamelCase do ponto abstrato que este fato instancia (ex.: DeverDeAgir, NexoCausal, Prova). Dois fatos de lados opostos sob o mesmo ponto abstrato se anulam.")


class AtomsStageOut(BaseModel):
    case_title: str
    narrative_pt: str
    central_question: str
    outcome_code: str = Field(description="Codigo do atomo que representa o resultado danoso a ser explicado.")
    atoms: List[AtomOut]
    open_questions: List[str]


# ----------------------------------------------------------------------
# Stage 2 -- rules
# ----------------------------------------------------------------------
class RuleOut(BaseModel):
    rule: str = Field(description="Regra no formato 'rN: Ant1 AND Ant2 => Cons' (ou '->' para regra estrita).")
    kind: RuleKind
    gloss_pt: str
    perspective: str
    evidence: List[str]
    dossier_refs: List[str]


class RulesStageOut(BaseModel):
    premises: List[str]
    axioms: List[str]
    strict_rules: List[RuleOut]
    defeasible_rules: List[RuleOut]
    modelling_notes_pt: str


# ----------------------------------------------------------------------
# Stage 3 -- causal queries
# ----------------------------------------------------------------------
class QueryOut(BaseModel):
    phi: str = Field(description="Literal da causa candidata (pode vir com o sinal de negacao).")
    psi: str = Field(description="Literal do resultado examinado.")
    question_pt: str
    court_verdict: CourtVerdict
    court_rationale_pt: str
    evidence: List[str]


class QueriesStageOut(BaseModel):
    queries: List[QueryOut]


# ----------------------------------------------------------------------
# Stage 4 -- legally relevant causation (ICAIL 2026)
# ----------------------------------------------------------------------
class LrcPremiseOut(BaseModel):
    literal: str = Field(description="Premissa doutrinaria: Om_X, Obl_X, Unexpected_X, After_X_Y, ForeseeableRisk_X_R, Playout_R_Y, Tortious_X (ou sua negacao).")
    label_pt: str
    evidence: List[str]
    perspective: str = Field(default="", description="Quem DECIDE por esta premissa: o primeiro julgador (relator, voto_convergente, voto_divergente, stf_final) que a sustenta; ou comum.")
    origin_perspective: str = Field(default="", description="Quem primeiro levantou a tese: em geral uma parte (recorrente, recorrido).")
    perspectives: List[str] = Field(default_factory=list, description="Deixe vazio: e o refinamento de registro para premissas que varias perspectivas sustentam por conta propria.")

    def holders(self) -> List[str]:
        """Every perspective that holds this premise on its own account.

        A single `perspective` is what the stages emit and cannot express a
        thesis three voices assert independently; `perspectives`, filled in
        at record level, can. Empty means "just `perspective`", so records
        written before the field existed read exactly as they did.
        """
        return list(self.perspectives) or ([self.perspective] if self.perspective else [])


class LrcRuleOut(BaseModel):
    rule: str = Field(description="Regra instanciada de um esquema, no formato '<esquema>_<sufixo>: Ant AND Ant => Cons'.")
    scheme: LrcScheme
    gloss_pt: str
    evidence: List[str]
    perspective: str = Field(default="", description="Quem DECIDE por esta regra: o primeiro julgador (relator, voto_convergente, voto_divergente, stf_final) que a sustenta; comum para o esquema geral cf2lrc.")
    origin_perspective: str = Field(default="", description="Quem primeiro levantou a tese: em geral uma parte (recorrente, recorrido).")
    perspectives: List[str] = Field(default_factory=list, description="Deixe vazio: e o refinamento de registro para regras que varias perspectivas sustentam por conta propria.")

    def holders(self) -> List[str]:
        """See `LrcPremiseOut.holders`."""
        return list(self.perspectives) or ([self.perspective] if self.perspective else [])


class LrcStageOut(BaseModel):
    doctrinal_premises: List[LrcPremiseOut]
    scheme_rules: List[LrcRuleOut]
    targets: List[str] = Field(description="Literais LeReCa_* cuja aceitacao deve ser avaliada.")
    duty_basis_pt: str = Field(description="Fundamento normativo do dever de agir, quando houver.")


class RepairStageOut(BaseModel):
    """Correction of a previously rejected stage: the same payload, re-emitted."""
    corrected_json: str = Field(description="O JSON corrigido do estagio, como string, com o mesmo formato exigido originalmente.")
    changes_pt: List[str]


# ----------------------------------------------------------------------
# Persisted record: data/translated/<case>/case.json
# ----------------------------------------------------------------------
class CaseMeta(BaseModel):
    id: str
    title: str
    annotator: str
    source_file: str
    source_sha256: str
    session_id: str = ""
    dossier_case_id: str = Field(
        default="",
        description="Id do dossie de origem, quando difere do id do caso -- "
                    "duas formalizacoes do mesmo acordao. Vazio: usa `id`.")

    @property
    def dossier_id(self) -> str:
        return self.dossier_case_id or self.id


class RuleMeta(BaseModel):
    """One rule of the cause-in-fact layer, with its author and provenance.

    `perspective` names *the* perspective a stage attributed the rule to, and
    stays the primary field: it is what the LLM stages emit and what every
    record formalized so far carries. `perspectives` is the record-level
    refinement -- a rule several voices hold on their own account, which a
    single string cannot say. A judgment where the reporting judge and two
    others each assert the same causal step is not one author and two
    silences, and reading it that way empties their theories.

    Left empty (the default, and what every earlier record has), the holders
    are just `[perspective]`, so nothing changes for records written before
    the field existed.
    """
    id: str
    rule: str
    kind: RuleKind
    gloss_pt: str
    perspective: str = ""
    perspectives: List[str] = Field(
        default_factory=list,
        description="Todas as perspectivas que sustentam a regra por conta "
                    "propria; vazio significa apenas `perspective`.")
    evidence: List[str] = Field(default_factory=list)
    dossier_refs: List[str] = Field(default_factory=list)

    def holders(self) -> List[str]:
        """Every perspective that holds this rule, never empty when the rule
        has an author at all."""
        return list(self.perspectives) or ([self.perspective] if self.perspective else [])


class SolverVerdict(BaseModel):
    """What the solver actually computed for a (phi, psi) pair.

    Two notions, which is all the papers define: `ness` is the NESS cause
    (ICAIL 2025 Def. 4.3 / ICAIL 2026 Def. 3.4), `but_for` is Def. 3.5.
    Every but-for cause is a NESS cause; the converse fails under
    overdetermination and preemption.
    """
    ness: bool
    but_for: bool


class Query(BaseModel):
    phi: str
    psi: str
    question_pt: str
    court_verdict: CourtVerdict
    court_rationale_pt: str
    evidence: List[str] = Field(default_factory=list)
    solver: Optional[SolverVerdict] = None
    legally_relevant: Optional[bool] = None


class PreferenceDimensionOut(BaseModel):
    """One doctrinal axis the judgment weighs, and the weight it gets."""
    key: str = Field(description="Chave em snake_case, ex.: dever_especifico.")
    label_pt: str
    weight: float
    rationale_pt: str = ""


class RuleProfileOut(BaseModel):
    """Which dimensions an element invokes. `coefficients` is normally 0/1.

    `rule` names a defeasible rule **or an ordinary premise literal**. Both
    are ranked, because Definition 21 of Modgil & Prakken compares
    `Prem_p(B) ◁ Prem_p(A)` *and* `DefRules(B) ◁ DefRules(A)`: an argument
    whose premises are unranked is incomparable no matter how its rules
    compare. Ranking only the rules -- which is what this repository used to
    do -- declares preferences where canonical ASPIC+ declares none, and the
    authors call the version that ignores premises "an anomaly" they went out
    of their way to correct.
    """
    rule: str
    coefficients: Dict[str, float] = Field(default_factory=dict)
    rationale_pt: str = ""


class PreferenceBlock(BaseModel):
    """The case's ordering between defeasible arguments, as data.

    Never authored by an LLM stage: the weights are somebody's reading of the
    judgment, and the point of writing them into the record is that another
    reader can disagree and re-run. Applies to both layers -- rule ids are
    disjoint across them -- and is silent about any element it does not rank.

    `perspective` is who moves the ordering. In Prakken's adjudication model
    a priority argument is a *move*, made by a player in the decision phase
    (§4.3), not a fact of the world: an ordering that applies before anybody
    argued for it would let a preference settle a dispute between the parties
    with no adjudicator present. Left empty, the ordering is treated as
    undisputed and applies from the first step -- which is the old behaviour,
    and honest only for a case where nobody contests the weighing.
    """
    principle: Literal["weakest", "last"] = "weakest"
    comparator: Literal["elitist", "democrat"] = "elitist"
    dimensions: List[PreferenceDimensionOut] = Field(default_factory=list)
    profiles: List[RuleProfileOut] = Field(default_factory=list)
    perspective: str = Field(
        default="",
        description="Quem move a ordenacao (relator, voto_divergente, ...). "
                    "Vazio: incontroversa, vale desde o primeiro passo.")
    notes_pt: str = ""

    def model(self):
        """The `aspic.preferences.PreferenceModel` this block describes, or
        None when the block declares no dimension."""
        from aspic.preferences import Dimension, PreferenceModel, RuleProfile

        if not self.dimensions:
            return None
        return PreferenceModel(
            [Dimension(key=d.key, label_pt=d.label_pt, weight=d.weight,
                       rationale_pt=d.rationale_pt) for d in self.dimensions],
            [RuleProfile(rule_id=p.rule, coefficients=dict(p.coefficients),
                         rationale_pt=p.rationale_pt) for p in self.profiles],
            principle=self.principle,
            comparator=self.comparator,
        )


class LRCBlock(BaseModel):
    """The ICAIL 2026 legal-relevance layer as a second framework.

    `bridged_premises` is computed by `formalize.bridge` from the cause-in-fact
    solver run and is never authored by the LLM -- the same determinism
    boundary that keeps the counterfactual test honest.
    """
    doctrinal_premises: List[LrcPremiseOut] = Field(default_factory=list)
    bridged_premises: List[str] = Field(default_factory=list)
    scheme_rules: List[LrcRuleOut] = Field(default_factory=list)
    targets: List[str] = Field(default_factory=list)
    duty_basis_pt: str = ""
    relevance: List[dict] = Field(default_factory=list, description="Saida de aspic.lrc.relevance_report.")

    @property
    def knowledge_base(self) -> Dict[str, List[str]]:
        return {
            "premises": list(dict.fromkeys(
                [*self.bridged_premises, *(p.literal for p in self.doctrinal_premises)]
            )),
            "axioms": [],
        }

    @property
    def causal_model(self) -> Dict[str, List[str]]:
        return {"strict_rules": [], "defeasible_rules": [r.rule for r in self.scheme_rules]}


class PromptRef(BaseModel):
    stage: str
    path: str
    sha256: str
    model: str


class Provenance(BaseModel):
    run_id: str
    created_at: str
    model: str
    prompts: List[PromptRef] = Field(default_factory=list)
    pipeline_version: str = SCHEMA_VERSION


class FormalizedCase(BaseModel):
    """The canonical formalization record. `knowledge_base` and `causal_model`
    are already `ArgumentationFramework`'s input shape."""
    schema_version: str = SCHEMA_VERSION
    case: CaseMeta
    narrative_pt: str = ""
    central_question: str = ""
    atoms: List[AtomOut] = Field(default_factory=list)
    knowledge_base: Dict[str, List[str]] = Field(default_factory=lambda: {"premises": [], "axioms": []})
    causal_model: Dict[str, List[str]] = Field(default_factory=lambda: {"strict_rules": [], "defeasible_rules": []})
    rules_meta: List[RuleMeta] = Field(default_factory=list)
    effect: str = ""
    queries: List[Query] = Field(default_factory=list)
    lrc: Optional[LRCBlock] = None
    preferences: Optional[PreferenceBlock] = None
    open_questions: List[str] = Field(default_factory=list)
    modelling_notes_pt: str = ""
    provenance: Optional[Provenance] = None

    def atom_glosses(self) -> Dict[str, str]:
        """Plain-Portuguese text for every literal that can turn up as an
        argument's conclusion.

        That is the atoms and their negations -- generated here rather than
        asked of the LLM -- **and** the rule negations `¬rN`, which is what an
        undercutting argument concludes. Without the latter the didactic view
        would print a bare `¬r0` in the middle of a sentence; with it, the
        card reads "conclui-se que não se sustenta o raciocínio: ...".
        """
        glosses: Dict[str, str] = {}
        for atom in self.atoms:
            glosses[atom.code] = atom.label_pt
            glosses.setdefault(f"¬{atom.code}", f"não é o caso de que {atom.label_pt}")
        for meta in self.rules_meta:
            if meta.gloss_pt:
                glosses.setdefault(f"¬{meta.id}", undercut_gloss(meta.gloss_pt))
        return glosses

    def rule_glosses(self) -> Dict[str, str]:
        return {meta.id: meta.gloss_pt for meta in self.rules_meta}

    def atom_by_code(self, code: str) -> Optional[AtomOut]:
        base = code[1:] if code.startswith("¬") else code
        return next((a for a in self.atoms if a.code == base), None)
