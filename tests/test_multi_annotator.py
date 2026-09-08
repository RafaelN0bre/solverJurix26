"""Três anotadores, um acórdão: qual leitura o pipeline usa, e como se sabe.

O caso 003 foi anotado por três pessoas. Os exports diferem em substância --
41, 28 e 18 trechos marcados, contagens diferentes de unidades causais e de
divergências -- e os ids de passagem são disjuntos entre eles.

Até aqui o pipeline escolhia *um* por acidente: `dossier_paths` varria
`data/*/*.json` em ordem alfabética e ficava com o primeiro, que é o da
Andressa. Só que o `case-003` foi formalizado a partir do dossiê da Izabela --
as 22 passagens que ele cita são todas dela. A aba Dossiê e a formalização
descreviam documentos diferentes, e nada dizia isso.

Estes testes fixam as três propriedades que impedem a volta desse estado: a
escolha do primário é declarada e não alfabética, as três anotações continuam
acessíveis, e a cobertura é medida contra tudo o que foi marcado.
"""
import pytest

from aspic import catalog
from aspic.evaluation import coverage_report

CASE = "case-003"
pytestmark = pytest.mark.skipif(
    len(catalog.dossier_paths_for(CASE)) < 2,
    reason="precisa de mais de um dossiê anotado em data/<anotador>/")


@pytest.fixture
def record():
    return catalog.formalization_by_id(CASE)


# ----------------------------------------------------------------------
# Qual dossiê é o primário
# ----------------------------------------------------------------------
def test_the_primary_dossier_is_the_one_the_record_names(record):
    """Não é o primeiro em ordem alfabética -- é o que o registro nomeia.

    `andressa-bissolotti` ordena antes de `izabela-melo`, então a regra
    antiga escolheria a Andressa. O registro diz Izabela, e é ela.
    """
    primary = catalog.dossier_path_by_id(CASE)
    assert primary is not None
    assert primary.parent.name == record.case.annotator == "izabela-melo"
    assert primary.parent.name != sorted(
        p.parent.name for p in catalog.dossier_paths_for(CASE))[0]


def test_the_primary_is_where_the_cited_passages_actually_live(record):
    """A prova de que o primário está certo não é o campo do registro: é que
    todas as passagens citadas resolvem dentro dele."""
    from formalize.dossier import load_dossier

    cited = {i for i in _cited(record) if i.startswith("src_")}
    assert cited
    primary = load_dossier(catalog.dossier_path_by_id(CASE)).passages()
    assert cited <= set(primary)


def test_every_annotator_stays_reachable():
    paths = catalog.dossier_paths_for(CASE)
    assert len(paths) == 3
    assert paths[0] == catalog.dossier_path_by_id(CASE)      # primário primeiro
    assert {p.parent.name for p in paths} == {
        "izabela-melo", "andressa-bissolotti", "vitor-melo"}


def test_passage_ids_are_disjoint_so_the_union_is_unambiguous():
    """Se dois anotadores usassem o mesmo id para trechos diferentes, unir os
    exports silenciaria um dos dois. Eles não usam -- e é isso que permite
    atribuir cada passagem ao seu autor."""
    seen: dict = {}
    for dossier in catalog.dossiers_by_id(CASE):
        for passage_id in dossier.passages():
            assert passage_id not in seen, (
                f"{passage_id} aparece em {seen.get(passage_id)} e em {dossier.annotator}")
            seen[passage_id] = dossier.annotator
    assert len(seen) == len(catalog.all_passages(CASE))


# ----------------------------------------------------------------------
# O rastreamento
# ----------------------------------------------------------------------
def test_coverage_is_measured_against_every_annotator(record):
    """O número que interessa -- quanto do que foi marcado virou modelo -- só
    é honesto sobre tudo o que foi marcado."""
    report = coverage_report(record, CASE)
    assert len(report["annotators"]) == 3
    assert report["passages"]["total"] == len(catalog.all_passages(CASE))
    assert report["passages"]["unresolved"] == []     # nada fica pendurado


def test_coverage_says_whose_work_went_unused(record):
    """O achado que o número agregado esconde: a formalização usou trechos de
    um anotador só, e os outros dois não entraram em lugar nenhum."""
    by_annotator = coverage_report(record, CASE)["passages"]["by_annotator"]
    used = {a for a, entry in by_annotator.items() if entry["cited"]}
    assert used == {"izabela-melo"}
    assert all(by_annotator[a]["total"] > 0 for a in by_annotator)


# ----------------------------------------------------------------------
# A consolidação canônica
# ----------------------------------------------------------------------
def test_the_consolidation_covers_every_cell_and_names_its_support():
    consolidation = catalog.consolidation(CASE)
    if consolidation is None:
        pytest.skip("rode scripts/build_consolidacao_main.py")
    cells = consolidation["celulas"]
    assert len(cells) == consolidation["resumo"]["celulas"]
    known = set(consolidation["anotadores"])
    for cell in cells:
        assert set(cell["sustentada_por"]) <= known
        # Uma célula com valor tem que dizer por que aquele valor.
        if cell["valor"].strip():
            assert cell["justificativa"].strip()


def test_the_consolidation_never_invents_content():
    """Célula vazia nas três propostas continua vazia: 'ninguém se pronunciou'
    é informação, e preenchê-la seria o modelo opinando sobre o acórdão."""
    consolidation = catalog.consolidation(CASE)
    if consolidation is None:
        pytest.skip("rode scripts/build_consolidacao_main.py")
    for cell in consolidation["celulas"]:
        if not any(v.strip() for v in cell["propostas"].values()):
            assert not cell["valor"].strip(), f"inventou em §{cell['secao_id']}"


# ----------------------------------------------------------------------
# A vista
# ----------------------------------------------------------------------
def test_the_dossier_view_shows_all_three_and_the_consolidation():
    from aspic.dossier_view import render_dossier

    body = render_dossier(CASE)
    assert "Consolidação canônica" in body
    assert body.count('<details class="dossier-other"') == 2
    for annotator in ("izabela-melo", "andressa-bissolotti", "vitor-melo"):
        assert annotator in body


def _cited(record):
    ids = set()
    for atom in record.atoms:
        ids |= set(atom.evidence)
    for meta in record.rules_meta:
        ids |= set(meta.evidence)
    for query in record.queries:
        ids |= set(query.evidence)
    return ids
