"""Uma consolidação canônica a partir das três dos anotadores.

Cada anotador do caso 003 produziu, além do seu dossiê, um *documento de
consolidação*: as mesmas 8 seções × 5 perspectivas, com as três anotações lado
a lado e uma coluna "Consolidação" que ele próprio preencheu. São três
propostas independentes de consolidação do mesmo material —
`data/<anotador>/consolidacao.json` — e elas **divergem em 23 das 32 células**.

Antes disto, o pipeline resolvia essa divergência por acidente de ordenação:
`aspic.catalog.dossier_paths` varria `data/*/*.json` em ordem alfabética e
ficava com o primeiro dossiê que encontrava para o caso — o da Andressa,
porque `andressa-bissolotti` vem antes de `izabela-melo`. As outras duas
anotações não entravam em lugar nenhum, e nada na interface dizia isso.

Este módulo substitui o acidente por uma decisão registrada. Ele monta o
material das três (proposta de cada um **mais** as anotações cruas que cada
proposta resume), manda para o modelo com o comando e o vocabulário mínimo da
própria seção, e recebe de volta uma célula consolidada que carrega, além do
valor: quais anotadores a sustentam, se houve divergência substantiva (e não
apenas de redação), e por que a escolha foi essa. O resultado vai para
`data/consolidacao-main.json`.

Duas coisas que o desenho recusa a fazer:

* **Não resolve divergência por maioria.** Duas redações do mesmo conteúdo não
  são dois votos; e uma leitura minoritária pode ser a correta. O modelo
  escolhe e **justifica**, e `divergencia_substantiva` fica marcada para quem
  for revisar encontrar sem procurar.
* **Não inventa conteúdo.** Célula vazia nas três continua vazia. O prompt diz
  isso e `validate_consolidation` verifica depois, porque um prompt pedindo
  para não inventar não é garantia de nada.
"""
import json

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

from . import prompts
from .gemini import GeminiClient

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_ROOT = REPO_ROOT / "data"
DEFAULT_PROMPTS_DIR = REPO_ROOT / "prompts" / "consolidacao"
DEFAULT_OUTPUT = DEFAULT_DATA_ROOT / "consolidacao-main.json"

#: Nome do arquivo que cada anotador deixou na sua pasta.
CONSOLIDATION_FILE = "consolidacao.json"

#: Como o documento de consolidação nomeia as partes, e como o pipeline as
#: nomeia. A ponte existe porque o dossiê e o documento .docx foram escritos
#: por pessoas diferentes em momentos diferentes, e `aspic.perspectives` só
#: sabe falar a grafia canônica.
PERSPECTIVE_TO_PIPELINE = {
    "Recorrente": "recorrente",
    "Recorrido": "recorrido",
    "Marco Aurélio": "relator",
    "Edson Fachin": "voto_convergente",
    "Alexandre de Moraes": "voto_divergente",
}


# ----------------------------------------------------------------------
# O material
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Cell:
    """Uma célula a consolidar: um par (seção, perspectiva), ou uma seção
    inteira quando ela é de campo livre."""
    secao_id: str
    secao: str
    tipo: str
    perspectiva: Optional[str]
    comando: str
    vocabulario: List[str] = field(default_factory=list)
    orientacoes: List[str] = field(default_factory=list)
    #: `{anotador: a consolidação que ele propôs}`
    propostas: Dict[str, str] = field(default_factory=dict)
    #: `{anotador: as anotações cruas dele que a proposta resume}`
    anotacoes: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.secao_id}|{self.perspectiva or ''}"

    @property
    def divergem(self) -> bool:
        valores = {v.strip() for v in self.propostas.values() if v.strip()}
        return len(valores) > 1

    @property
    def vazia(self) -> bool:
        return not any(v.strip() for v in self.propostas.values())


def load_consolidations(root: Optional[Path] = None) -> Dict[str, dict]:
    """`{anotador: documento}` para cada `data/<anotador>/consolidacao.json`.

    A chave é o nome da pasta, que é o mesmo identificador que
    `CaseMeta.annotator` usa -- de modo que uma célula consolidada possa ser
    rastreada até a pessoa e, dela, até o dossiê dela.
    """
    root = Path(root or DEFAULT_DATA_ROOT)
    found: Dict[str, dict] = {}
    for path in sorted(root.glob(f"*/{CONSOLIDATION_FILE}")):
        try:
            found[path.parent.name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return found


def _display_name(document: dict, annotator: str) -> str:
    """Como o documento chama este anotador ("Izabela") a partir do nome da
    pasta ("izabela-melo"), casando pelo primeiro nome."""
    first = annotator.split("-")[0].lower()
    for name in document.get("anotadores", []):
        if name.lower().startswith(first[:4]):
            return name
    return annotator


def cells(consolidations: Dict[str, dict]) -> List[Cell]:
    """Todas as células a consolidar, na ordem do documento.

    A estrutura das seções é lida do primeiro documento: os três saíram do
    mesmo modelo .docx, então as seções e as perspectivas coincidem; o que
    difere é o que cada um escreveu na coluna Consolidação.
    """
    if not consolidations:
        return []
    base = next(iter(consolidations.values()))
    perspectivas = base.get("perspectivas", [])
    display = {a: _display_name(d, a) for a, d in consolidations.items()}

    def section_of(document: dict, secao_id: str) -> dict:
        return next((s for s in document.get("secoes", []) if s["id"] == secao_id), {})

    out: List[Cell] = []
    for secao in base.get("secoes", []):
        secao_id = secao["id"]
        comando = secao.get("comando", "")
        vocabulario = list(secao.get("vocabulario_minimo", []))
        orientacoes = list(secao.get("orientacoes", []))

        if secao.get("tipo") == "tabela_por_perspectiva":
            for perspectiva in perspectivas:
                propostas, anotacoes = {}, {}
                for annotator, document in consolidations.items():
                    other = section_of(document, secao_id)
                    propostas[annotator] = (
                        other.get("consolidacao_por_perspectiva", {}).get(perspectiva, "") or "")
                    raw = other.get("anotacoes_por_perspectiva", {}).get(perspectiva, {})
                    anotacoes[annotator] = list(raw.get(display[annotator], []))
                out.append(Cell(secao_id, secao["titulo"], secao["tipo"], perspectiva,
                                comando, vocabulario, orientacoes, propostas, anotacoes))
        else:
            propostas = {
                annotator: (section_of(document, secao_id).get("resposta_consolidada", "") or "")
                for annotator, document in consolidations.items()
            }
            out.append(Cell(secao_id, secao["titulo"], secao.get("tipo", "campo_livre"),
                            None, comando, vocabulario, orientacoes, propostas, {}))
    return out


# ----------------------------------------------------------------------
# O que o modelo devolve
# ----------------------------------------------------------------------
class ConsolidatedCell(BaseModel):
    """Uma célula consolidada, com a sua própria justificação."""
    secao_id: str = Field(description="Id da secao, exatamente como veio (ex.: '1', '7.2').")
    perspectiva: str = Field(description="Perspectiva da linha, ou string vazia em secao de campo livre.")
    valor: str = Field(description="O texto consolidado. Vazio se as tres propostas estiverem vazias.")
    itens: List[str] = Field(description="O mesmo valor quebrado em itens, quando for lista; senao, lista vazia.")
    sustentada_por: List[str] = Field(description="Anotadores cuja proposta a consolidacao adota, no todo ou em substancia.")
    divergencia_substantiva: bool = Field(description="True quando as propostas discordam sobre o CONTEUDO, nao apenas sobre a redacao.")
    justificativa: str = Field(description="Uma ou duas frases: por que este valor, e o que foi descartado das outras propostas.")


class ConsolidationStageOut(BaseModel):
    celulas: List[ConsolidatedCell]
    notas_gerais: str = Field(description="Observacoes sobre o conjunto: padroes de divergencia, secoes fracas, o que ficou em aberto.")


# ----------------------------------------------------------------------
# O prompt
# ----------------------------------------------------------------------
def render_material(cells_: Sequence[Cell]) -> str:
    """O bloco de markdown que o prompt recebe: uma célula por bloco, com as
    três propostas e as anotações cruas que cada uma resume."""
    linhas: List[str] = []
    for cell in cells_:
        titulo = f"### §{cell.secao_id} {cell.secao}"
        if cell.perspectiva:
            titulo += f" — {cell.perspectiva}"
        linhas += ["", titulo, ""]
        linhas.append(f"- **comando da seção**: {cell.comando}")
        if cell.vocabulario:
            linhas.append("- **vocabulário mínimo**: "
                          + ", ".join(f"`{v}`" for v in cell.vocabulario))
        for orientacao in cell.orientacoes:
            linhas.append(f"- **orientação**: {orientacao}")
        linhas.append("")
        linhas.append("Propostas de consolidação:")
        for annotator, proposta in sorted(cell.propostas.items()):
            linhas.append(f"  - `{annotator}`: {proposta.strip() or '(vazio)'}")
        cruas = {a: v for a, v in cell.anotacoes.items() if v}
        if cruas:
            linhas.append("")
            linhas.append("Anotações que essas propostas resumem:")
            for annotator, notas in sorted(cruas.items()):
                for nota in notas:
                    linhas.append(f"  - `{annotator}`: {nota}")
    return "\n".join(linhas).strip()


def build_prompt(cells_: Sequence[Cell], *, version: Optional[int] = None,
                 prompts_dir: Optional[Path] = None):
    return prompts.load(
        "main",
        version=version,
        prompts_dir=Path(prompts_dir or DEFAULT_PROMPTS_DIR),
        variables={
            "material": render_material(cells_),
            "total_celulas": str(len(cells_)),
            "anotadores": ", ".join(sorted({a for c in cells_ for a in c.propostas})),
        },
    )


# ----------------------------------------------------------------------
# Checagem determinística do que voltou
# ----------------------------------------------------------------------
def validate_consolidation(cells_: Sequence[Cell],
                           out: ConsolidationStageOut) -> List[str]:
    """Erros de forma no que o modelo devolveu.

    Determinístico e desconfiado por desenho: o prompt pede para não inventar
    conteúdo e para cobrir todas as células, e nenhuma das duas coisas um
    prompt garante.
    """
    problemas: List[str] = []
    esperadas = {c.key: c for c in cells_}
    vistas = set()

    for entrada in out.celulas:
        key = f"{entrada.secao_id}|{entrada.perspectiva or ''}"
        cell = esperadas.get(key)
        if cell is None:
            problemas.append(f"célula inexistente no material: §{entrada.secao_id} "
                             f"/ {entrada.perspectiva or '(campo livre)'}")
            continue
        if key in vistas:
            problemas.append(f"célula repetida: §{entrada.secao_id} / {entrada.perspectiva}")
        vistas.add(key)

        if cell.vazia and entrada.valor.strip():
            problemas.append(
                f"§{entrada.secao_id}/{entrada.perspectiva or '—'}: as três propostas "
                "estavam vazias e a consolidação inventou conteúdo.")
        if not cell.vazia and not entrada.valor.strip():
            problemas.append(
                f"§{entrada.secao_id}/{entrada.perspectiva or '—'}: havia proposta e "
                "a consolidação veio vazia.")
        desconhecidos = set(entrada.sustentada_por) - set(cell.propostas)
        if desconhecidos:
            problemas.append(
                f"§{entrada.secao_id}/{entrada.perspectiva or '—'}: cita anotador "
                f"inexistente ({', '.join(sorted(desconhecidos))}).")
        if entrada.valor.strip() and not entrada.justificativa.strip():
            problemas.append(
                f"§{entrada.secao_id}/{entrada.perspectiva or '—'}: sem justificativa.")

    for key, cell in esperadas.items():
        if key not in vistas:
            problemas.append(f"célula não consolidada: §{cell.secao_id} "
                             f"/ {cell.perspectiva or '(campo livre)'}")
    return problemas


# ----------------------------------------------------------------------
# O artefato
# ----------------------------------------------------------------------
def to_record(cells_: Sequence[Cell], out: ConsolidationStageOut,
              consolidations: Dict[str, dict], prompt) -> dict:
    """O `consolidacao-main.json`: o valor consolidado de cada célula, o que
    cada anotador havia proposto, e a proveniência da execução."""
    por_key = {f"{e.secao_id}|{e.perspectiva or ''}": e for e in out.celulas}
    registros = []
    for cell in cells_:
        entrada = por_key.get(cell.key)
        registros.append({
            "secao_id": cell.secao_id,
            "secao": cell.secao,
            "tipo": cell.tipo,
            "perspectiva": cell.perspectiva,
            "perspectiva_pipeline": PERSPECTIVE_TO_PIPELINE.get(cell.perspectiva or ""),
            "valor": entrada.valor if entrada else "",
            "itens": list(entrada.itens) if entrada else [],
            "sustentada_por": list(entrada.sustentada_por) if entrada else [],
            "divergencia_substantiva": bool(entrada.divergencia_substantiva) if entrada else False,
            "justificativa": entrada.justificativa if entrada else "",
            "propostas": dict(cell.propostas),
        })
    substantivas = [r for r in registros if r["divergencia_substantiva"]]
    return {
        "case_id": "case-003",
        "anotadores": sorted(consolidations),
        "perspectivas": next(iter(consolidations.values())).get("perspectivas", []),
        "resumo": {
            "celulas": len(registros),
            "divergiam_nas_propostas": sum(1 for c in cells_ if c.divergem),
            "divergencia_substantiva": len(substantivas),
            "vazias": sum(1 for c in cells_ if c.vazia),
        },
        "notas_gerais": out.notas_gerais,
        "celulas": registros,
        "proveniencia": {
            "prompt": prompt.relative_path,
            "prompt_versao": prompt.version,
            "template_sha256": prompt.template_sha256,
            "rendered_sha256": prompt.rendered_sha256,
        },
    }


def build(client: GeminiClient, *, root: Optional[Path] = None,
          prompts_dir: Optional[Path] = None,
          version: Optional[int] = None) -> tuple:
    """`(registro, problemas)` -- roda o prompt e checa o que voltou."""
    consolidations = load_consolidations(root)
    if not consolidations:
        raise FileNotFoundError(
            f"Nenhum {CONSOLIDATION_FILE} em {Path(root or DEFAULT_DATA_ROOT)}/*/")
    material = cells(consolidations)
    prompt = build_prompt(material, version=version, prompts_dir=prompts_dir)
    out = client.generate(prompt, ConsolidationStageOut, stage="consolidacao_main")
    return to_record(material, out, consolidations, prompt), validate_consolidation(material, out)
