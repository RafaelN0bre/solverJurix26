#!/usr/bin/env python3
"""Transcreve `docs/formalizacao-caso003.md` num registro executável.

    uv run python scripts/build_case003_final.py
    uv run python scripts/build_case003_final.py --check   # não regrava nada

O documento é uma formalização escrita à mão do Caso 003 com **cinco vozes**
(as duas partes e três julgadores), e não a saída do pipeline de LLM: o
`case-003` que já está em `data/translated/` veio do pipeline, tem quatro
perspectivas e outro vocabulário de átomos. Os dois convivem — este script
grava `case-003-final`, apontando para o mesmo dossiê pelo campo
`case.dossier_case_id`, de modo que as duas leituras do mesmo acórdão possam
ser comparadas lado a lado no explorador.

O que este arquivo é, então, é a transcrição — e como toda transcrição, ela
faz escolhas que o documento não faz. Elas estão todas aqui, nomeadas:

**Códigos.** `ATOM_CODE_RE` limita um código a 12 caracteres, e três nomes do
documento passam disso. `LapsoTemporal` vira `LapsoTemp`,
`ProvidenciasCabiveis` vira `ProvCabiveis`, `MeiosDisponiveis` vira
`MeiosDisp`. Nada mais foi renomeado.

**Premissas.** O documento lista, por perspectiva, o que cada uma toma por
posto — e o Recorrente toma por posto `FugaPreso` e `Latrocinio`, que as
outras *derivam* por r0/r1 e r2/r6. Declarar os dois como premissas globais
curto-circuitaria a cadeia causal de todo mundo: r3 (`Latrocinio ⇒
MorteVitima`) é regra de todos, então `aspic.perspectives.project` daria a
premissa `Latrocinio` a todas as teorias, e o dano passaria a ser derivável
sem passar pela omissão em nenhuma delas. A base global é, por isso, só o que
ninguém deriva: `OmiEstatal`, `RegFechado`, `LapsoTemp`, `FormacaoQuad`,
`¬ProvCabiveis`, `¬MeiosDisp`. Que o Recorrente conceda os outros dois
continua registrado — no campo `perspectives` dos átomos, que é de onde
`project` tira o que cada perspectiva afirma por conta própria.

**Regras de todos.** As regras que o documento atribui às cinco perspectivas
(r3, r4) entram como `comum`: uma regra que ninguém disputa é incontroversa, e
desenhá-la na raia da primeira parte que a sustenta faria o mapa de
adjudicação dizer que foi um movimento dela.

**Identificadores da camada LRC.** Os esquemas do ICAIL 2026 são reconhecidos
pelo prefixo do identificador (`aspic.lrc.scheme_of`), e as regras do
documento se chamam q0…q8. Cada uma recebe o prefixo do esquema de que é
instância, mantendo o nome do documento no sufixo: `cf2lrc_q5`, `sc_q6`,
`unom_q7`, `suca_q3`. Três movimentos do documento não instanciam esquema
nenhum do artigo — são sobre a *natureza do dever de agir*, que lá é uma
premissa `Obl` ligada ou desligada — e por isso `aspic.lrc` ganhou
`dvesp`/`dvgen`/`dvpre` (`EXTENSION_SCHEMES`).

**Evidência.** O documento não cita passagens. Para os átomos que são
literalmente a mesma proposição de um átomo do `case-003` do pipeline, a
evidência daquele registro é reaproveitada (`_CARRIED_EVIDENCE`); onde não há
correspondência inequívoca, o campo fica vazio, e a Conferência reporta isso
como não rastreável — que é o que é.

**Pesos.** A tupla ⟨dever específico, intervenção causal, autonomia⟩ =
⟨4, 5, 5⟩ entra como `FormalizedCase.preferences`. Ela existe porque o
documento marca ⟨q0, q2⟩ como "rebutting — único ponto ativo": duas regras
concluindo literais complementares, sem undercut de nenhum lado. Sob a
ordenação básica isso deixa os dois lados UNDEC e a camada inteira sem
resposta; com a tupla, `dvgen_q1` (5+5) prevalece sobre `dvesp_q0` (4) e a
camada decide. Ver `aspic.preferences`.
"""
import argparse
import hashlib
import json
import logging
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from formalize import build  # noqa: E402
from formalize.cli import print_report  # noqa: E402
from formalize.pipeline import DEFAULT_OUT_DIR, _update_index  # noqa: E402
from formalize.schema import (  # noqa: E402
    AtomOut, CaseMeta, FormalizedCase, LRCBlock, LrcPremiseOut, LrcRuleOut,
    PreferenceBlock, PreferenceDimensionOut, Query, RuleMeta, RuleProfileOut,
)
from formalize.validate import validate_case  # noqa: E402

CASE_ID = "case-003-final"
DOSSIER_CASE_ID = "case-003"
SOURCE_DOC = REPO_ROOT / "docs" / "formalizacao-caso003.md"

#: `perspective` do documento -> a grafia canônica do pipeline.
#: Fachin acompanha o relator com fundamento próprio (r8 desfaz o undercut do
#: Recorrente); Moraes diverge (r6, r7 rompem a cadeia). O documento não traz
#: uma posição final da corte separada dos votos, então `stf_final` não
#: aparece: inventá-la seria atribuir ao colegiado uma tese que o documento
#: não escreve.
RTE, RDO = "recorrente", "recorrido"
MA, EF, AM = "relator", "voto_convergente", "voto_divergente"
TODOS = "comum"

#: Átomo daqui -> átomo do `case-003` do pipeline cuja evidência é reusável.
_CARRIED_EVIDENCE = {
    "FugaPreso": "FugaPreso",
    "MorteVitima": "MorteVitima",
    "FormacaoQuad": "FormacaoQuad",
    "Latrocinio": "Latrocinio",
    "RegFechado": "PresoRegFech",
    "LapsoTemp": "CrimeApos3M",
    "DeverEspec": "DeverEspec",
    "DeverGener": "DeverGener",
    "AtoTerceiro": "FatoDeTerc",
    "ProvCabiveis": "ProvaMedidas",
}


def carried_evidence(directory: Path) -> dict:
    """Evidência do registro `case-003` do pipeline, por átomo daqui."""
    source = directory / DOSSIER_CASE_ID / "case.json"
    if not source.is_file():
        return {}
    payload = json.loads(source.read_text(encoding="utf-8"))
    by_code = {atom["code"]: atom.get("evidence", []) for atom in payload["atoms"]}
    return {here: list(by_code.get(there, []))
            for here, there in _CARRIED_EVIDENCE.items()}


# ----------------------------------------------------------------------
# Átomos
# ----------------------------------------------------------------------
#: `(código, glosa, tipo, status, perspectivas, é premissa, lado, ponto abstrato)`
#:
#: Os três pontos abstratos que o documento disputa são exatamente as três
#: dimensões da tupla de preferências, e recebem os mesmos nomes de propósito:
#: é o que faz a "balança de fatores" da aba Perspectivas e a resolução de
#: preferências falarem do mesmo desacordo em vez de dois parecidos.
ATOMS = [
    ("OmiEstatal", "o Estado foi omisso na custódia do preso", "fato",
     "incontroverso", [RDO, MA, EF, AM], True, "responsabilizacao", "CondutaEstatal"),
    ("RegFechado", "o preso cumpria regime prisional fechado", "fato",
     "incontroverso", [RDO, MA, EF], True, "responsabilizacao", "NaturezaDoDever"),
    ("FugaPreso", "o detento fugiu do sistema prisional", "intermediario",
     "incontroverso", [RTE, AM], False, "responsabilizacao", "CondutaEstatal"),
    ("LapsoTemp", "o crime foi praticado após três meses da fuga", "fato",
     "incontroverso", [RTE, AM], True, "exclusao", "IntervencaoCausal"),
    ("FormacaoQuad", "o crime foi praticado em concurso de agentes (quadrilha)",
     "fato", "incontroverso", [AM], True, "exclusao", "AutonomiaDeTerceiro"),
    ("Latrocinio", "a quadrilha praticou roubo seguido de morte contra a vítima",
     "intermediario", "incontroverso", [RTE], False, "neutro", ""),
    ("MorteVitima", "a vítima foi morta em decorrência de latrocínio",
     "intermediario", "incontroverso", [], False, "neutro", ""),
    ("Danos", "a família da vítima sofreu danos materiais e morais", "resultado",
     "incontroverso", [], False, "neutro", ""),
    ("ProvCabiveis", "o Estado adotou as providências cabíveis", "prova",
     "controvertido", [EF], False, "exclusao", "OnusDaProva"),
    ("MeiosDisp", "o Estado teve meios disponíveis para agir", "prova",
     "controvertido", [EF], False, "responsabilizacao", "OnusDaProva"),
    # Qualificações jurídicas: vivem na camada de relevância, e nenhuma é
    # premissa do framework de causa de fato.
    ("DeverEspec", "o Estado tinha um dever específico de custódia sobre o preso",
     "dever", "controvertido", [RDO, MA, EF], False, "responsabilizacao",
     "NaturezaDoDever"),
    ("DeverGener", "o Estado tinha um dever genérico de segurança pública",
     "dever", "controvertido", [AM], False, "exclusao", "NaturezaDoDever"),
    ("AtoTerceiro", "o crime praticado após a fuga é ato de terceiro",
     "intermediario", "controvertido", [RTE, AM], False, "exclusao",
     "AutonomiaDeTerceiro"),
]

#: Premissas da camada de causa de fato, na ordem do documento. `¬X` entra
#: como premissa negativa: é o que o voto de Fachin afirma.
PREMISES = ["OmiEstatal", "RegFechado", "LapsoTemp", "FormacaoQuad",
            "¬ProvCabiveis", "¬MeiosDisp"]


# ----------------------------------------------------------------------
# Camada CIF -- inventário de regras do documento
# ----------------------------------------------------------------------
#: `(id, regra, tipo, glosa, quem sustenta)`
CIF_RULES = [
    ("r0", "r0: OmiEstatal => FugaPreso", "causal",
     "A omissão do Estado na custódia levou à fuga do preso.", [RDO]),
    ("r1", "r1: OmiEstatal AND RegFechado => FugaPreso", "causal",
     "A omissão do Estado sobre quem cumpria regime fechado — e portanto sob "
     "custódia estrita — levou à fuga.", [MA, EF]),
    ("r2", "r2: FugaPreso => Latrocinio", "causal",
     "A fuga do detento levou ao latrocínio praticado contra a vítima.",
     [RDO, MA, EF]),
    ("r3", "r3: Latrocinio => MorteVitima", "causal",
     "O latrocínio resultou na morte da vítima.", [TODOS]),
    ("r4", "r4: MorteVitima => Danos", "causal",
     "A morte da vítima causou danos materiais e morais à sua família.", [TODOS]),
    ("r5", "r5: LapsoTemp => ¬r2", "undercut",
     "Passados três meses entre a fuga e o crime, não se sustenta o raciocínio "
     "que liga uma coisa à outra.", [RTE]),
    ("r6", "r6: LapsoTemp AND FormacaoQuad => Latrocinio", "causal",
     "O latrocínio se explica pelo lapso de três meses somado à formação de "
     "quadrilha: é a quadrilha, e não a fuga, que o produz.", [AM]),
    ("r7", "r7: LapsoTemp AND FormacaoQuad => ¬r2", "undercut",
     "Havendo lapso de três meses e concurso de agentes, não se sustenta o "
     "raciocínio que liga a fuga ao latrocínio.", [AM]),
    ("r8", "r8: ¬ProvCabiveis => ¬r5", "undercut",
     "Se o Estado não adotou as providências cabíveis, não se sustenta a "
     "objeção do lapso temporal: o decurso do tempo é consequência da própria "
     "inércia.", [EF]),
]


# ----------------------------------------------------------------------
# Camada LRC -- q0..q8, com o prefixo do esquema de que cada uma é instância
# ----------------------------------------------------------------------
#: `(id, regra, esquema, glosa, quem sustenta)`
LRC_RULES = [
    ("dvesp_q0", "dvesp_q0: RegFechado => DeverEspec", "dvesp",
     "Cumprindo o preso regime fechado, o dever do Estado sobre ele é "
     "específico de custódia, e não o dever difuso de segurança pública.",
     [RDO, MA, EF]),
    ("dvgen_q1", "dvgen_q1: LapsoTemp AND FormacaoQuad => DeverGener", "dvgen",
     "Decorridos três meses e tendo o crime sido praticado em quadrilha, o que "
     "restava era o dever genérico de segurança pública.", [AM]),
    ("dvgen_q2", "dvgen_q2: DeverGener => ¬DeverEspec", "dvgen",
     "Sendo genérico o dever, não há dever específico de custódia a imputar.",
     [AM]),
    ("suca_q3", "suca_q3: Latrocinio AND LapsoTemp => AtoTerceiro", "suca",
     "O latrocínio, praticado três meses depois, é ato de terceiro.", [RTE]),
    ("suca_q4", "suca_q4: Latrocinio AND LapsoTemp AND FormacaoQuad => AtoTerceiro",
     "suca",
     "O latrocínio, praticado três meses depois e em concurso de agentes, é ato "
     "autônomo de terceiro.", [AM]),
    ("cf2lrc_q5", "cf2lrc_q5: CaFa_OmiEstatal_Danos => LeReCa_OmiEstatal_Danos",
     "cf2lrc",
     "Sendo a omissão estatal causa de fato dos danos, presume-se que seja "
     "causa juridicamente relevante deles.", [RDO, MA, EF]),
    ("sc_q6", "sc_q6: AtoTerceiro => ¬cf2lrc_q5", "sc",
     "Sendo o crime ato de terceiro, rompe-se o nexo de relevância jurídica "
     "entre a omissão e os danos.", [RTE, AM]),
    ("unom_q7", "unom_q7: OmiEstatal AND ¬DeverEspec => ¬cf2lrc_q5", "unom",
     "Sem dever específico de agir, a omissão do Estado não é juridicamente "
     "imputável como causa dos danos.", [AM]),
    ("dvpre_q8", "dvpre_q8: DeverEspec => ¬sc_q6", "dvpre",
     "Subsistindo o dever específico de custódia, não se sustenta a defesa do "
     "ato de terceiro: o risco que se concretizou é exatamente o que o dever "
     "existia para conter.", [MA]),
]

#: Premissas da camada LRC que não vêm da ponte. Aqui elas são fatos da camada
#: de causa de fato que as regras de qualificação leem: o documento qualifica
#: o fato diretamente ("regime fechado ⇒ dever específico") em vez de passar
#: por um predicado `Obl`/`Om` intermediário. Não pertencem ao vocabulário
#: `aspic.lrc`, e é por isso que `check_lrc` — que só roda como porteiro dos
#: estágios de LLM — recusaria o campo: o registro é escrito à mão, e a
#: checagem que vale para ele é `validate_case`.
LRC_PREMISES = [
    ("OmiEstatal", "o Estado foi omisso na custódia do preso", [RDO, MA, EF, AM]),
    ("RegFechado", "o preso cumpria regime prisional fechado", [RDO, MA, EF]),
    ("LapsoTemp", "o crime foi praticado após três meses da fuga", [RTE, AM]),
    ("FormacaoQuad", "o crime foi praticado em concurso de agentes", [AM]),
    ("Latrocinio", "a quadrilha praticou roubo seguido de morte contra a vítima",
     [TODOS]),
]

LRC_TARGETS = ["LeReCa_OmiEstatal_Danos"]


# ----------------------------------------------------------------------
# Preferências: a tupla ⟨dever específico, intervenção causal, autonomia⟩
# ----------------------------------------------------------------------
DIMENSIONS = [
    PreferenceDimensionOut(
        key="dever_especifico", weight=4.0,
        label_pt="especificidade no dever de agir",
        rationale_pt="Quanto pesa a tese de que o Estado devia àquele preso um "
                     "dever concreto de custódia, e não o dever difuso de "
                     "segurança pública que deve a todos."),
    PreferenceDimensionOut(
        key="intervencao_causal", weight=5.0,
        label_pt="intervenção causal",
        rationale_pt="Quanto pesa o evento interposto entre a conduta e o dano "
                     "— aqui, os três meses decorridos entre a fuga e o crime."),
    PreferenceDimensionOut(
        key="autonomia", weight=5.0,
        label_pt="autonomia do terceiro",
        rationale_pt="Quanto pesa a deliberação própria de quem praticou o "
                     "crime — aqui, a formação de quadrilha, que é decisão de "
                     "terceiros e não desdobramento da fuga."),
]

#: `id da regra -> (coeficientes, por quê)`. Uma regra ausente daqui é neutra:
#: não invoca nenhuma dimensão e não entra na agregação. É o caso das regras
#: que apenas encadeiam o que já está posto — `dvgen_q2` tira a consequência
#: de `dvgen_q1`, `sc_q6` aplica a caracterização de `suca_*` — e o é por
#: desenho: fossem elas pontuadas, o peso do fundamento seria contado duas
#: vezes e o elo mais fraco passaria a medir o encadeamento, não a razão.
PROFILES = {
    "r1": ({"dever_especifico": 1.0},
           "Lê o regime fechado, que é o que torna o dever específico."),
    "r5": ({"intervencao_causal": 1.0},
           "Opõe o lapso temporal ao elo entre fuga e crime."),
    "r6": ({"intervencao_causal": 1.0, "autonomia": 1.0},
           "Explica o crime pelo lapso somado à deliberação da quadrilha."),
    "r7": ({"intervencao_causal": 1.0, "autonomia": 1.0},
           "Mesmo fundamento de r6, na forma de undercut."),
    "dvesp_q0": ({"dever_especifico": 1.0},
                 "É a tese da especificidade do dever, e o único lado dela no "
                 "conflito ⟨q0, q2⟩."),
    "dvgen_q1": ({"intervencao_causal": 1.0, "autonomia": 1.0},
                 "É o outro lado de ⟨q0, q2⟩, e se apoia nas duas outras "
                 "dimensões ao mesmo tempo."),
    "suca_q3": ({"intervencao_causal": 1.0},
                "Caracteriza o ato de terceiro só pelo lapso."),
    "suca_q4": ({"intervencao_causal": 1.0, "autonomia": 1.0},
                "Caracteriza o ato de terceiro pelo lapso e pela quadrilha."),
    "dvpre_q8": ({"dever_especifico": 1.0},
                 "Faz o dever específico prevalecer sobre a defesa do ato de "
                 "terceiro."),
}

PREFERENCE_NOTES = (
    "A ordenação básica do ASPIC+ (Definição 2.11) deixa dois argumentos "
    "derrotáveis incomparáveis, e o documento marca ⟨q0, q2⟩ como o único "
    "ataque ativo por rebutting da formalização: `dvesp_q0` conclui "
    "DeverEspec, `dvgen_q2` conclui ¬DeverEspec, e nenhum dos dois undercuta "
    "o outro. Sem preferência, os dois ficam UNDEC, `unom_q7` e `dvpre_q8` "
    "deixam ambos de disparar, e a camada de relevância não responde nada. "
    "Com a tupla ⟨4, 5, 5⟩ e agregação pelo elo mais fraco, o argumento por "
    "¬DeverEspec vale 10 (5 + 5, por `dvgen_q1`) contra 4 do argumento por "
    "DeverEspec (`dvesp_q0`), e a camada decide. O ponto de virada está em "
    "10: com peso maior que esse para a especificidade do dever, é o dever "
    "específico que prevalece e a pretensão se sustenta."
)


# ----------------------------------------------------------------------
# Montagem
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
    "transcrição documentadas em `scripts/build_case003_final.py`. Duas delas "
    "mudam o que se lê no resultado. Primeiro, `FugaPreso` e `Latrocinio` não "
    "entram como premissas globais, embora o Recorrente os tome por postos: "
    "como r3 é regra de todos, declará-los daria a premissa `Latrocinio` a "
    "todas as teorias e o dano passaria a ser derivável sem passar pela "
    "omissão em nenhuma delas. Segundo, o documento põe a ruptura do voto "
    "divergente nas duas camadas ao mesmo tempo — r7 undercuta r2 na camada "
    "de causa de fato, e q6/q7 undercutam q5 na de relevância. A consequência "
    "é que, no framework completo, a camada de causa de fato já resolve o "
    "caso sozinha: com r2 afastada, `OmiEstatal` deixa de ser causa de fato "
    "de `Danos`, não há `CaFa_OmiEstatal_Danos`, e `cf2lrc_q5` fica sem "
    "antecedente. A camada de relevância continua decidindo o conflito de "
    "qualificações ⟨q0, q2⟩ — é ali que os pesos operam — mas o faz sobre uma "
    "pretensão que os fatos já haviam derrubado. O traço da fase de decisão "
    "(aba Perspectivas) mostra a janela em que ela esteve viva: entre o voto "
    "convergente, que desfaz o undercut do Recorrente, e o divergente."
)


def build_record(directory: Path) -> FormalizedCase:
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
        bridged_premises=[],          # preenchido pela ponte, abaixo
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
            "é exatamente sobre a natureza desse dever: específico de custódia "
            "(RDO_, MA_, EF_) ou genérico de segurança pública (AM_)."
        ),
    )

    preferences = PreferenceBlock(
        principle="weakest",
        dimensions=list(DIMENSIONS),
        profiles=[RuleProfileOut(rule=rule_id, coefficients=dict(coefficients),
                                 rationale_pt=why)
                  for rule_id, (coefficients, why) in PROFILES.items()],
        notes_pt=PREFERENCE_NOTES,
    )

    record = FormalizedCase(
        case=CaseMeta(
            id=CASE_ID,
            title="Caso 003 — Responsabilidade do Estado por crime de foragido "
                  "(formalização final, por votos)",
            annotator="izabela-melo",
            source_file=str(SOURCE_DOC.relative_to(REPO_ROOT)),
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
        open_questions=[
            "O documento não traz uma posição final da corte separada dos "
            "votos, então o registro não a inventa: `stf_final` não aparece "
            "como perspectiva.",
            "`¬MeiosDisp` é premissa do voto convergente e nenhuma regra a lê "
            "— a validação a reporta como premissa inerte.",
        ],
        modelling_notes_pt=MODELLING_NOTES,
    )

    # A ponte é determinística e nunca é escrita à mão: é o solver que diz
    # quais `CaFa_*`/`ButFor_*` existem (`formalize.bridge`).
    record.lrc.bridged_premises = build.bridge_facts(record).premises()
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--check", action="store_true",
                        help="Não regrava nada; sai com 1 se houver erro.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("ASPIC+").setLevel(logging.WARNING)

    record = build.annotate(build_record(args.dir))
    report = validate_case(record)
    print(f"=== {record.case.id} — {record.case.title} ===")
    print_report(report)

    if not args.check:
        out = args.dir / CASE_ID
        out.mkdir(parents=True, exist_ok=True)
        (out / "case.json").write_text(
            json.dumps(record.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8")
        (out / "validation.json").write_text(
            json.dumps(report.as_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8")
        _update_index(args.dir)
        print(f"\nGravado em {out}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
