#!/usr/bin/env python3
"""Transcription script: converts `docs/formalizacao-caso003.md` into an
executable record under `data/translated/`. It starts the deterministic
pipeline: `formalize.build` executes its output and the interface reads it.
"""

"""Transcribes `docs/formalizacao-caso003.md` into an executable record.

    uv run python scripts/build_case003_final.py
    uv run python scripts/build_case003_final.py --check   # do not rewrite files

The document is a handwritten formalization of Case 003 with **five voices**
(two parties and three adjudicators). This script is its deterministic
transcription, the repository's sole producer of executable records.
No generative model participates: a person copied every atom, rule and
premise below from the document. The solver computes the `CaFa_*`/`ButFor_*`
bridge during assembly. `case.dossier_case_id` links the record to its source dossier.

Like any transcription, this file makes choices the document does not.
They are identified here:

**Codes.** `ATOM_CODE_RE` limits codes to 12 characters. Four document names
exceed this: `LapsoTemporal` becomes `LapsoTemp`, `OmissaoGenerica` becomes
`OmissaoGen`, `ProvidenciasCabiveis` becomes `ProvCabiveis`, and
`MeiosDisponiveis` becomes `MeiosDisp`. No other names were changed.

**Premises.** The document lists what each perspective takes as given.
The appellant takes `FugaPreso` and `Latrocinio` as given, while the others
*derive* them through r0/r1 and r2/r6. Global premises for both would
short-circuit everyone's causal chain: r3 (`Latrocinio ⇒ MorteVitima`) is
shared, so `analysis.perspectives.project` would give `Latrocinio` to every
theory, making the damage derivable without the omission. The global base
therefore contains only what nobody derives: `OmiEstatal`, `RegFechado`,
`LapsoTemp`, `FormacaoQuad`, `¬ProvCabiveis`, `¬MeiosDisp`. The appellant's
acceptance of the other two remains recorded in the atoms' `perspectives`
field, from which `project` reads each perspective's independent assertions.

**Shared rules.** Rules attributed to all five perspectives (r3, r4) use
`comum`: an undisputed rule is uncontroversial. Drawing it in the first
supporting party's lane would falsely attribute that move to that party.

**LRC identifiers.** `aspic.lrc.scheme_of` recognizes ICAIL 2026 schemes by
identifier prefix. The document's q0…q8 rules receive their scheme prefix
while retaining the original name as a suffix: `cf2lrc_q5`, `sc_q6`,
`suca_q4`. Two moves instantiate no paper scheme: they concern the *nature
of the duty to act*, represented there by enabling or disabling an `Obl`
premise. Hence `aspic.lrc` adds `dvesp`/`dvgen`/`dvpre`
(`EXTENSION_SCHEMES`). After separating voices, only `dvesp` and `dvpre`
have instances here; `dvgen` remains in the vocabulary, unused in this case.

**Evidence.** The document cites no passages. Atoms expressing exactly the
same proposition as an old `case-003` atom reuse that record's evidence
(`_EVIDENCE`). Without an unambiguous match the field stays empty, and the
validation view reports it as untraceable.

**Weights.** The tuple ⟨specific duty, causal intervention, autonomy⟩ =
⟨4, 5, 5⟩ enters as `FormalizedCase.preferences`. It was written to resolve
⟨q0, q2⟩, marked as “rebutting — sole active point”. Once voices are
separated, the LRC layer has no rebutting: no vote concludes `¬DeverEspec`.
The ordering decides nothing here. It remains because it classifies premises
and rules, as Modgil & Prakken Definition 21 requires for any comparison,
and because factual disagreement occurs in the CIF layer. See `aspic.preferences`.
"""
import argparse
import hashlib
import json
import logging
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from cases.workspace import docs_dir  # noqa: E402
from formalize import build  # noqa: E402
from formalize.schema import (  # noqa: E402
    AtomOut, CaseMeta, FormalizedCase, LRCBlock, LrcPremiseOut, LrcRuleOut,
    PreferenceBlock, PreferenceDimensionOut, Query, RuleMeta, RuleProfileOut,
)
from formalize.store import DEFAULT_OUT_DIR, update_index  # noqa: E402
from formalize.validate import print_report, validate_case  # noqa: E402

CASE_ID = "case-003-final"
DOSSIER_CASE_ID = "case-003"
SOURCE_DOC = docs_dir() / "formalizacao-caso003.md"

#: document `perspective` -> canonical record spelling.
#: Fachin concurs with the reporting judge on independent grounds (r8 defeats the
#: appellant's undercut); Moraes dissents (r6, r7 break the chain). The document has
#: no final court position separate from the votes, so `stf_final` does not
#: appear: inventing it would attribute a thesis to the panel that the document
#: never states.
RTE, RDO = "recorrente", "recorrido"
MA, EF, AM = "relator", "voto_convergente", "voto_divergente"
TODOS = "comum"

#: Per-atom evidence: `src_*` judgment passage ids, collected from
#: Izabela Melo's annotation (`data/izabela-melo/case-003-dossie-2026-08-24.json`,
#: referenced by `case.dossier_case_id`). Frozen here because the
#: intermediate record was removed; the ids remain valid, and the
#: validation view can still trace every atom to its page.
_EVIDENCE = {
    "AtoTerceiro": ["src_aa174d74858e40d2", "src_463968192f4c4384", "src_b08f1a1374b84354"],
    "DeverEspec": ["src_4621720adee3413a", "src_c9ac4600e7a84a96", "src_d4430da819554298", "src_72ea31d850704795"],
    "FormacaoQuad": ["src_f2b9e027898b482e"],
    "FugaPreso": ["src_3bfb96a17abe4056", "src_e18ee49b97864ccf"],
    "LapsoTemp": ["src_2cc2964892904cf2", "src_f2b9e027898b482e"],
    "Latrocinio": ["src_a5b5c7f3a9ca4d80", "src_7adf43487cee456e"],
    "MorteVitima": ["src_a5b5c7f3a9ca4d80", "src_d27a4d0db9954fe8"],
    "ProvCabiveis": ["src_e78c7d363e2f4c61"],
    "RegFechado": ["src_4de553dc86c34273", "src_c9ac4600e7a84a96", "src_03d379dcbe9d4160"],
}


def carried_evidence(directory: Path) -> dict:
    """Per-atom evidence. `directory` is ignored: the mapping is literal."""
    return {code: list(ids) for code, ids in _EVIDENCE.items()}


# ----------------------------------------------------------------------
# Atoms
# ----------------------------------------------------------------------
#: `(code, gloss, type, status, perspectives, is premise, side, abstract point)`
#:
#: The document's three disputed abstract points are exactly the three
#: preference-tuple dimensions, deliberately given the same names:
#: the perspective tab's factor balance and preference resolution thereby
#: describe the same disagreement rather than two similar ones.
ATOMS = [
    # ------------------------------------------------------------------
    # CIF layer: the factual causal mechanism. Entirely naturalistic:
    # all controversy moved to LRC; there are no attacks here.
    # ------------------------------------------------------------------
    ("OmiEstatal", "o Estado foi omisso na custódia do preso", "fato",
     "incontroverso", [RDO, MA, EF, AM], True, "responsabilizacao", "CondutaEstatal"),
    ("RegFechado", "o preso cumpria regime prisional fechado", "fato",
     "incontroverso", [RDO, MA, EF], True, "responsabilizacao", "NaturezaDoDever"),
    ("FugaPreso", "o detento fugiu do sistema prisional", "intermediario",
     "incontroverso", [RTE, AM], False, "responsabilizacao", "CondutaEstatal"),
    ("Latrocinio", "o foragido praticou roubo seguido de morte contra a vítima",
     "intermediario", "incontroverso", [RTE], False, "neutro", ""),
    ("MorteVitima", "a vítima foi morta em decorrência de latrocínio",
     "intermediario", "incontroverso", [], False, "neutro", ""),
    ("Danos", "a família da vítima sofreu danos materiais e morais", "resultado",
     "incontroverso", [], False, "neutro", ""),
    # ------------------------------------------------------------------
    # LRC layer: legal qualifications and attribution. Elapsed time and
    # joint action are facts, but operate only here: in CIF they
    # short-circuited the bridge, preventing `caFa` from ever arising.
    # ------------------------------------------------------------------
    ("LapsoTemp", "o crime foi praticado após três meses da fuga", "fato",
     "incontroverso", [RTE, AM], True, "exclusao", "IntervencaoCausal"),
    ("FormacaoQuad", "o crime foi praticado em concurso de agentes (quadrilha)",
     "fato", "incontroverso", [AM], True, "exclusao", "AutonomiaDeTerceiro"),
    ("DeverEspec", "o Estado tinha um dever específico de custódia sobre o preso",
     "dever", "controvertido", [RDO, MA, EF], False, "responsabilizacao",
     "NaturezaDoDever"),
    ("OmissaoGen", "a omissão estatal qualifica-se como genérica diante do tempo "
     "e do concurso", "dever", "controvertido", [AM], False, "exclusao",
     "NaturezaDoDever"),
    ("AtoTerceiro", "o crime praticado após a fuga é ato de terceiro (causa "
     "superveniente independente)", "intermediario", "controvertido", [RTE, AM],
     False, "exclusao", "AutonomiaDeTerceiro"),
    # `PremedAlvo` and `SeqImediata` distinguish RE 136.247: they remain in the
    # vocabulary because the judgment's theory uses them, but outside the factual base
    # because they did not occur in this case. Hence `q_reab` stays inert,
    # demonstrating a general rule rather than a rule tailored to this case.
    ("PremedAlvo", "o crime contra alvo específico foi premeditado antes da fuga "
     "(RE 136.247)", "fato", "controvertido", [], False, "responsabilizacao",
     "IntervencaoCausal"),
    ("SeqImediata", "houve sequência lógica e imediata entre a fuga e o crime "
     "(RE 136.247)", "fato", "controvertido", [], False, "responsabilizacao",
     "IntervencaoCausal"),
    ("ProvCabiveis", "o Estado adotou as providências cabíveis para evitar a fuga",
     "prova", "controvertido", [EF], False, "exclusao", "OnusDaProva"),
    ("MeiosDisp", "o Estado teve meios materiais disponíveis para agir", "prova",
     "controvertido", [EF], False, "responsabilizacao", "OnusDaProva"),
]

#: Cause-in-fact premises in document order. `¬X` enters
#: as a negative premise: this is what Fachin's vote asserts.
#: The CIF base contains only what the causal mechanism reads. Elapsed time,
#: joint action and evidence of precautions moved to LRC, where they enter
#: through `LRC_PREMISES`: in CIF they short-circuited the bridge.
PREMISES = ["OmiEstatal", "RegFechado"]


# ----------------------------------------------------------------------
# CIF layer: the document's rule inventory.
# ----------------------------------------------------------------------
#: `(id, rule, type, gloss, holders)`
CIF_RULES = [
    ("r0", "r0: OmiEstatal => FugaPreso", "causal",
     "A omissão do Estado na custódia levou à fuga do preso.", [RDO]),
    ("r1", "r1: OmiEstatal AND RegFechado => FugaPreso", "causal",
     "A omissão do Estado sobre quem cumpria regime fechado — e portanto sob "
     "custódia estrita — levou à fuga.", [MA, EF, AM]),
    ("r2", "r2: FugaPreso => Latrocinio", "causal",
     "A fuga do detento levou ao latrocínio praticado contra a vítima.", [TODOS]),
    ("r3", "r3: Latrocinio => MorteVitima", "causal",
     "O latrocínio resultou na morte da vítima.", [TODOS]),
    ("r4", "r4: MorteVitima => Danos", "causal",
     "A morte da vítima causou danos materiais e morais à sua família.", [TODOS]),
]


# ----------------------------------------------------------------------
# LRC layer: q0..q8, prefixed by the scheme each instantiates.
# ----------------------------------------------------------------------
#: `(id, rule, scheme, gloss, holders)`
LRC_RULES = [
    ("dvesp_q0", "dvesp_q0: RegFechado => DeverEspec", "dvesp",
     "Cumprindo o preso regime fechado, o dever do Estado sobre ele é "
     "específico de custódia, e não o dever difuso de segurança pública.",
     [RDO, MA, EF]),
    ("suca_q3", "suca_q3: LapsoTemp => AtoTerceiro", "suca",
     "Alegação de parte: decorridos três meses, o crime é ato de terceiro. "
     "Vence na fase preliminar por default dialético — falta de réplica "
     "eficaz —, não por mérito dogmático.", [RTE]),
    ("u_corte", "u_corte: LapsoTemp => ¬suca_q3", "u_corte",
     "A corte recusa expressamente a tese de que o tempo isolado rompe a "
     "causalidade: o mero lapso não autoriza, por si só, a caracterização do "
     "ato de terceiro.", [AM]),
    ("suca_q4", "suca_q4: Latrocinio AND LapsoTemp AND FormacaoQuad => AtoTerceiro",
     "suca",
     "Ratio decidendi: o lapso temporal somado ao concurso de agentes "
     "superveniente e independente constitui ato de terceiro.", [AM]),
    ("q_reab", "q_reab: PremedAlvo AND SeqImediata => ¬suca_q4", "q_reab",
     "Distinguishing do RE 136.247: houvesse premeditação contra alvo certo e "
     "sequência imediata entre a fuga e o crime, a caracterização do ato de "
     "terceiro não se sustentaria.", [AM]),
    ("cf2lrc_q5", "cf2lrc_q5: CaFa_OmiEstatal_Danos => LeReCa_OmiEstatal_Danos",
     "cf2lrc",
     "Sendo a omissão estatal causa de fato dos danos, presume-se que seja "
     "causa juridicamente relevante deles.", [RDO, MA, EF]),
    ("sc_q6", "sc_q6: AtoTerceiro => ¬cf2lrc_q5", "sc",
     "Sendo o crime ato de terceiro, rompe-se o nexo de relevância jurídica "
     "entre a omissão e os danos.", [RTE, AM]),
    ("dvpre_q8", "dvpre_q8: DeverEspec => ¬sc_q6", "dvpre",
     "Subsistindo o dever específico de custódia, não se sustenta a defesa do "
     "ato de terceiro: o risco que se concretizou é exatamente o que o dever "
     "existia para conter.", [MA, EF]),
    ("og_q9", "og_q9: OmiEstatal AND LapsoTemp AND FormacaoQuad => OmissaoGen",
     "og",
     "Decorrido o tempo e interposta a deliberação autônoma da quadrilha, a "
     "omissão estatal já não é específica àquele resultado: qualifica-se como "
     "genérica.", [AM]),
    ("og_q10", "og_q10: OmissaoGen => ¬cf2lrc_q5", "og",
     "Omissão genérica não é liame necessário nem determinante do resultado: "
     "não sustenta a presunção de relevância jurídica.", [AM]),
    ("q11", "q11: ¬ProvCabiveis => ¬suca_q3", "q11",
     "Não tendo o Estado demonstrado as providências cabíveis, não se sustenta "
     "a alegação de ato de terceiro deduzida por ele.", [EF]),
]

#: LRC premises not supplied by the bridge. These are cause-in-fact facts
#: read by qualification rules: the document qualifies
#: the fact directly (“closed regime ⇒ specific duty”), rather than using
#: an intermediate `Obl`/`Om` predicate. They are outside the
#: `aspic.lrc` vocabulary: this record is handwritten, and its applicable check is
#: `validate_case`.
LRC_PREMISES = [
    ("OmiEstatal", "o Estado foi omisso na custódia do preso", [RDO, MA, EF, AM]),
    ("RegFechado", "o preso cumpria regime prisional fechado", [RDO, MA, EF]),
    ("LapsoTemp", "o crime foi praticado após três meses da fuga", [RTE, AM]),
    ("FormacaoQuad", "o crime foi praticado em concurso de agentes", [AM]),
    ("Latrocinio", "o foragido praticou roubo seguido de morte contra a vítima",
     [TODOS]),
    ("¬ProvCabiveis", "o Estado não demonstrou as providências cabíveis", [EF]),
]

LRC_TARGETS = ["LeReCa_OmiEstatal_Danos"]


# ----------------------------------------------------------------------
# Assembly
# ----------------------------------------------------------------------
NARRATIVE = (
    "Um detento em regime fechado foge do sistema prisional por omissão do "
    "Estado na custódia. Três meses depois, em concurso com outros agentes, "
    "pratica roubo seguido de morte contra a vítima, cuja família sofre danos "
    "materiais e morais e pede reparação. O Estado recorre. A disputa não é "
    "sobre o que aconteceu — ninguém nega a fuga nem o crime — mas sobre duas "
    "questões encadeadas: se a fuga ainda explica o crime três meses depois e "
    "em quadrilha, e se o dever que o Estado tinha sobre aquele preso era o "
    "dever específico de custódia ou o dever genérico de segurança pública "
    "que ele deve a todos."
)

CENTRAL_QUESTION = (
    "A omissão do Estado na custódia do preso é causa juridicamente relevante "
    "dos danos sofridos pela família da vítima?"
)

QUERIES = [
    ("OmiEstatal", "Danos",
     "A omissão do Estado na custódia do preso causou os danos sofridos pela "
     "família da vítima?", "rejeitada",
     "A tese vencedora entendeu que o lapso de três meses e a execução do "
     "crime em concurso de agentes rompem o nexo: o que restava ao Estado era "
     "o dever genérico de segurança pública."),
    ("FugaPreso", "Danos",
     "A fuga do detento causou os danos sofridos pela família da vítima?",
     "rejeitada",
     "Mesma razão de decidir: o crime praticado três meses depois, por "
     "quadrilha, é ato de terceiro."),
    ("Latrocinio", "Danos",
     "O latrocínio praticado pela quadrilha causou os danos sofridos pela "
     "família da vítima?", "acolhida",
     "Ponto incontroverso: é o crime que produz a morte e, com ela, os danos."),
]

MODELLING_NOTES = (
    "Transcrição de `docs/formalizacao-caso003.md`, com as escolhas de "
    "transcrição documentadas em `scripts/build_case003_final.py`. Três delas "
    "mudam o que se lê no resultado.\n\n"
    "Primeiro, `FugaPreso` e `Latrocinio` não entram como premissas globais, "
    "embora o Recorrente os tome por postos: como r3 é regra de todos, "
    "declará-los daria a premissa `Latrocinio` a todas as teorias e o dano "
    "passaria a ser derivável sem passar pela omissão em nenhuma delas.\n\n"
    "Segundo, a camada de causa de fato é puramente mecânica: r0–r4, sem "
    "ataque nenhum. O lapso temporal e o concurso de agentes deixaram de "
    "atacar a cadeia causal e passaram inteiros à camada de relevância. "
    "Enquanto atacavam nas duas, o CIF resolvia o caso sozinho — com r2 "
    "afastada, `OmiEstatal` deixava de ser causa de fato e `cf2lrc_q5` ficava "
    "sem antecedente, de modo que a relevância decidia sobre uma pretensão "
    "que os fatos já haviam derrubado. Agora `caFa(OmiEstatal, Danos)` sai "
    "verdadeira e a imputação é decidida onde se decide imputação.\n\n"
    "Terceiro, este registro corre na ordem invertida, `lrc_first`: as dez "
    "regras de qualificação da LRC — dever, ato de terceiro, omissão "
    "genérica, ônus das cautelas — não leem nenhum literal de ponte, então "
    "correm antes e entregam `DeverEspec`, `AtoTerceiro` e `OmissaoGen` ao "
    "CIF como axiomas. Só `cf2lrc_q5`, que lê `CaFa`, espera os fatos. Os "
    "casos do ICAIL 2025/2026 ficam na ordem do artigo, `cif_first`. Ver o "
    "bloco \"Ordem das camadas\" adiante."
)


#: `order -> (id suffix, variant name)`. The same document is
#: transcribed twice, changing only the order of the layers, so
#: both readings can be compared side by side. This is the sole difference
#: between records; any difference in results is an effect of the
#: execution order alone.
ORDERS = {
    "lrc_first": ("", "qualificação antes dos fatos: LRC → CIF → LRC"),
    "cif_first": ("-cif", "a ordem do ICAIL 2026: CIF → LRC"),
}


def build_record(directory: Path, layer_order: str = "lrc_first") -> FormalizedCase:
    evidence = carried_evidence(directory)

    atoms = [
        AtomOut(code=code, label_pt=label, kind=kind, status=status,
                perspectives=list(perspectives), evidence=evidence.get(code, []),
                dossier_refs=[], established=established, favors=favors,
                abstract_factor=abstract)
        for code, label, kind, status, perspectives, established, favors, abstract
        in ATOMS
    ]

    rules_meta = [
        RuleMeta(id=rule_id, rule=rule, kind=kind, gloss_pt=gloss,
                 perspective=(TODOS if holders == [TODOS] else holders[0]),
                 perspectives=([] if holders == [TODOS] else list(holders)),
                 evidence=[], dossier_refs=[])
        for rule_id, rule, kind, gloss, holders in CIF_RULES
    ]

    lrc = LRCBlock(
        doctrinal_premises=[
            LrcPremiseOut(literal=literal, label_pt=label, evidence=[],
                          perspective=(TODOS if holders == [TODOS] else holders[0]),
                          perspectives=([] if holders == [TODOS] else list(holders)))
            for literal, label, holders in LRC_PREMISES
        ],
        bridged_premises=[],          # Filled by the bridge below.
        scheme_rules=[
            LrcRuleOut(rule=rule, scheme=scheme, gloss_pt=gloss, evidence=[],
                       perspective=(TODOS if holders == [TODOS] else holders[0]),
                       perspectives=([] if holders == [TODOS] else list(holders)))
            for _, rule, scheme, gloss, holders in LRC_RULES
        ],
        targets=list(LRC_TARGETS),
        duty_basis_pt=(
            "Art. 37, § 6º, da Constituição Federal, lido junto ao dever de "
            "custódia sobre quem cumpre pena em regime fechado. A controvérsia "
            "é exatamente sobre a natureza desse dever. O vocabulário — dever "
            "específico, dever geral, omissão própria — é inteiro do voto "
            "convergente (EF_), que firma o dever específico e afasta o geral. "
            "Nenhum outro voto o usa: o divergente decide por ruptura do nexo, "
            "não por natureza do dever."
        ),
    )

    #: The spec theory has no weights: every LRC attack is
    #: undercutting, leaving no complementary conclusions to order.
    preferences = None

    record = FormalizedCase(
        case=CaseMeta(
            id=CASE_ID + ORDERS[layer_order][0],
            title="Caso 003 — Responsabilidade do Estado por crime de foragido "
                  "(formalização final, por votos; "
                  + ORDERS[layer_order][1] + ")",
            annotator="izabela-melo",
            source_file=SOURCE_DOC.name,
            source_sha256=hashlib.sha256(SOURCE_DOC.read_bytes()).hexdigest(),
            session_id="formalizacao-manual-2026-09-07",
            dossier_case_id=DOSSIER_CASE_ID,
        ),
        narrative_pt=NARRATIVE,
        central_question=CENTRAL_QUESTION,
        atoms=atoms,
        knowledge_base={"premises": list(PREMISES), "axioms": []},
        causal_model={"strict_rules": [],
                      "defeasible_rules": [rule for _, rule, _, _, _ in CIF_RULES]},
        rules_meta=rules_meta,
        effect="Danos",
        queries=[Query(phi=phi, psi=psi, question_pt=question,
                       court_verdict=verdict, court_rationale_pt=rationale,
                       evidence=[])
                 for phi, psi, question, verdict, rationale in QUERIES],
        lrc=lrc,
        preferences=preferences,
        layer_order=layer_order,
        open_questions=[
            "O documento não traz uma posição final da corte separada dos "
            "votos, então o registro não a inventa: `stf_final` não aparece "
            "como perspectiva.",
            "`¬MeiosDisp` é premissa do voto convergente e nenhuma regra a lê "
            "— a validação a reporta como premissa inerte.",
        ],
        modelling_notes_pt=MODELLING_NOTES,
    )

    # The bridge is deterministic and never handwritten: the solver determines
    # which `CaFa_*`/`ButFor_*` literals exist (`formalize.bridge`).
    record.lrc.bridged_premises = build.bridge_facts(record).premises()
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--check", action="store_true",
                        help="Não regrava nada; sai com 1 se houver erro.")
    parser.add_argument("--order", choices=sorted(ORDERS),
                        help="Gera só uma das variantes (padrão: as duas).")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("ASPIC+").setLevel(logging.WARNING)

    ok = True
    for layer_order, (suffix, label) in ORDERS.items():
        if args.order and layer_order != args.order:
            continue
        record = build.annotate(build_record(args.dir, layer_order))
        report = validate_case(record)
        print(f"=== {record.case.id} — {label} ===")
        print_report(report)
        ok = ok and report.ok

        if not args.check:
            out = args.dir / (CASE_ID + suffix)
            out.mkdir(parents=True, exist_ok=True)
            (out / "case.json").write_text(
                json.dumps(record.model_dump(), ensure_ascii=False, indent=2),
                encoding="utf-8")
            (out / "validation.json").write_text(
                json.dumps(report.as_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8")
            print(f"Gravado em {out}\n")
    if not args.check:
        update_index(args.dir)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
