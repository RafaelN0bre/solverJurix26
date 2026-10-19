"""Checks the transcribed Case 003 record and its pipeline results.
Exercises layer ordering, legal-relevance resolution and architecture rendering.
"""

"""Case 003, validated against `docs/formalizacao-caso003.md`.

The document is the hand-written formalization of RE 608.880/MT with five
voices (the two parties and three adjudicators);
`scripts/build_case003_final.py` transcribes it into
`data/translated/case-003-final/case.json`. This file enforces two things:

1. **Alignment** — every rule of the document exists in the record, with the
   same antecedent, the same consequent and the same voices. It is the test
   that keeps the document and the executable from diverging in silence,
   which has happened before.
2. **Resolution** — the record, when run, arrives where the judgment
   arrived, and arrives along the path the winning vote takes.

The layer order is the paper's, `CIF → LRC`: the cause-in-fact layer runs
first and its verdicts enter the legal-relevance layer as axioms (eq. 1).
"""
import re

import pytest

from cases import catalog
from cases.workspace import docs_dir
from formalize import build

DOC = docs_dir() / "formalizacao-caso003.md"
TARGET = "LeReCa_OmiEstatal_Danos"

#: Long name in the document -> record code (`ATOM_CODE_RE` caps it at 12).
RENAME = {"LapsoTemporal": "LapsoTemp", "ProvidenciasCabiveis": "ProvCabiveis",
          "MeiosDisponiveis": "MeiosDisp", "OmissaoGenerica": "OmissaoGen"}
#: Document abbreviation -> record perspective.
VOICES = {"RTE_": "recorrente", "RDO_": "recorrido", "MA_": "relator",
          "EF_": "voto_convergente", "AM_": "voto_divergente"}
ALL_VOICES = set(VOICES.values())


@pytest.fixture(scope="module")
def record():
    return catalog.formalized_records()["case-003-final"]


@pytest.fixture(scope="module")
def document():
    return DOC.read_text(encoding="utf-8")


def parse(document, prefix):
    """The document's rules: `id -> (antecedent, consequent, voices)`."""
    out = {}
    pattern = r"^(" + prefix + r"[\w]*)\s*:\s*(.+?)\s+⇒\s+(.+?)\s+\[(.+?)\]\s*$"
    for match in re.finditer(pattern, document, re.M):
        rule_id, antecedent, consequent, voices = match.groups()

        def rename(text):
            for long, short in RENAME.items():
                text = text.replace(long, short)
            return text.replace(" ∧ ", " AND ")

        out[rule_id] = (rename(antecedent), rename(consequent),
                        {VOICES[v.strip()] for v in voices.split(",")})
    return out


def rules_of(record, layer):
    """The record's rules: `id -> (antecedent, consequent, voices)`."""
    if layer == "cif":
        entries = [(m.id, m.rule, set(m.perspectives) or {m.perspective})
                   for m in record.rules_meta]
    else:
        entries = [(r.rule.split(":", 1)[0].strip(), r.rule,
                    set(r.perspectives) or {r.perspective}) for r in record.lrc.scheme_rules]
    out = {}
    for rule_id, rule, voices in entries:
        antecedent, _, consequent = rule.split(":", 1)[1].partition(" => ")
        out[rule_id] = (antecedent.strip(), consequent.strip(),
                        ALL_VOICES if voices == {"comum"} else voices)
    return out


# ----------------------------------------------------------------------
# 1. Document-to-record alignment
# ----------------------------------------------------------------------
def test_the_cause_in_fact_rules_are_the_documents(record, document):
    doc_rules, rec_rules = parse(document, "r"), rules_of(record, "cif")
    assert set(doc_rules) == set(rec_rules)
    for rule_id, (antecedent, consequent, voices) in doc_rules.items():
        assert rec_rules[rule_id][0] == antecedent, rule_id
        assert rec_rules[rule_id][1] == consequent, rule_id
        assert rec_rules[rule_id][2] == voices, rule_id


def test_the_legal_relevance_rules_are_the_documents(record, document):
    """Document ids receive scheme prefixes in the record (`q4` ->
    `suca_q4`), so matching uses the suffix."""
    doc_rules = parse(document, "q") | parse(document, "u_") | parse(document, "dvesp") \
        | parse(document, "suca") | parse(document, "cf2lrc") | parse(document, "sc_") \
        | parse(document, "dvpre") | parse(document, "og_")
    rec_rules = rules_of(record, "lrc")
    by_suffix = {rule_id.split("_")[-1]: rule_id for rule_id in rec_rules}
    assert len(doc_rules) == len(rec_rules)
    for doc_id, (antecedent, consequent, voices) in doc_rules.items():
        rec_id = by_suffix[doc_id.split("_")[-1]]
        rec_antecedent, rec_consequent, rec_voices = rec_rules[rec_id]
        assert rec_antecedent == antecedent, doc_id
        # The document's `¬q5` is `¬cf2lrc_q5` in the record.
        expected = re.sub(r"^¬(\w+)$",
                          lambda m: "¬" + by_suffix.get(m.group(1).split("_")[-1],
                                                        m.group(1)), consequent)
        assert rec_consequent == expected, doc_id
        assert rec_voices == voices, doc_id


def test_every_atom_of_the_document_exists_in_the_record(record, document):
    block = document[document.index("## Atoms"):document.index("## CIF")]
    codes = {RENAME.get(m, m) for m in re.findall(r"^([A-Z][A-Za-z]+)\s{2,}\S",
                                                  block, re.M)}
    assert codes == {atom.code for atom in record.atoms}


# ----------------------------------------------------------------------
# 2. Layer execution order
# ----------------------------------------------------------------------
def test_nothing_flows_from_relevance_to_cause_in_fact(record):
    """The CIF runs first: its knowledge base is the case's own, with no
    axiom handed down by the LRC."""
    assert record.knowledge_base["axioms"] == []
    assert not {str(a) for a in build.cif_framework(record).axioms}


def test_the_bridge_enters_the_relevance_layer_as_an_axiom(record):
    """Equation (1): the bridge is an LRC axiom, not an attackable premise."""
    axioms = record.lrc.knowledge_base["axioms"]
    assert "CaFa_OmiEstatal_Danos" in axioms
    assert not [p for p in record.lrc.knowledge_base["premises"]
                if p.startswith(("CaFa_", "ButFor_"))]


# ----------------------------------------------------------------------
# 3. Resolution
# ----------------------------------------------------------------------
def test_the_grounded_extension_follows_the_votes(record):
    """Winning-vote steps in order: Fachin's specific duty becomes `in` and
    defeats the third-party-act defence; the ex officio undercut cancels the
    party's claim; generic omission defeats the relevance presumption."""
    af = build.lrc_framework(record)
    justified = set(af.justified_conclusions())
    for literal in ("DeverEspec", "¬sc_q6", "¬suca_q3", "OmissaoGen", "¬cf2lrc_q5"):
        assert literal in justified, literal
    assert TARGET not in justified


def test_the_claim_is_defeated_not_unformulated(record):
    """The presumption fired and was defeated. If “not formulated”, the right
    outcome would have arisen for the wrong reason."""
    report = {r["target"]: r for r in record.lrc.relevance}
    entry = report[TARGET]
    assert entry["derivable"] is True
    assert entry["status"] == "afastada"
    assert [b["scheme"] for b in entry["blocked_by"]] == ["og"]


def test_the_rehabilitation_rule_stays_inert(record):
    """`q_reab` distinguishes RE 136.247. Its premises are outside the factual
    base, so no argument uses it: this demonstrates a general rule rather
    than a rule tailored to this case."""
    af = build.lrc_framework(record)
    used = {rule for argument in af.arguments.values()
            for rule in argument.defeasible_rules}
    assert "q_reab" not in used
    assert "q_reab" in {r.rule.split(":", 1)[0].strip() for r in record.lrc.scheme_rules}


def test_the_theory_needs_no_preferences(record):
    """All disagreement is undercutting: no complementary conclusions need
    ordering, and the record declares no weights."""
    assert record.preferences is None
    af = build.lrc_framework(record)
    assert not [a for a in af.attacks if "rebut" in str(getattr(a, "attack_type", ""))]


def test_the_state_is_not_liable(record):
    """The case asks whether state omission is a legally relevant cause of
    the damage. The majority judgment and the framework both answer no."""
    query = next(q for q in record.queries
                 if (q.phi, q.psi) == ("OmiEstatal", "Danos"))
    assert query.solver.ness is True and query.solver.but_for is True
    assert query.legally_relevant is False
    assert query.court_verdict == "rejeitada"


# ----------------------------------------------------------------------
# 4. Architecture section
# ----------------------------------------------------------------------
def test_the_architecture_section_is_drawn_from_the_record(record):
    """The high-level diagram is generated from the record: its two blocks,
    the boundary output and the verdict all come from `case.json`. This
    prevents the diagram from becoming stale."""
    from interface.architecture_view import render_architecture

    html = render_architecture(record)
    assert "Arquitetura — CIF → LRC" in html
    assert "1. CIF — causa de fato" in html
    assert "2. LRC — ponte e imputação" in html
    assert "qualificação" not in html
    # What the boundary delivers, and where the bridge crosses.
    for literal in ("CaFa_OmiEstatal_Danos", "cf2lrc_q5"):
        assert literal in html, literal
    assert "afastada" in html
