"""Deterministic normalization of an annotated dossier into a case brief.

The dossiers in `data/<annotator>/` are exports of an annotation tool: dozens
of fields, most of them empty for any given case, free-text values that are
really numbered lists, and a `source_links` table that connects passages of
the PDF to individual *fields* of individual records. Feeding that raw JSON to
an LLM wastes context on nulls and hides the evidence structure.

This module turns it into a markdown brief -- no LLM involved, so it is cheap,
diffable and testable -- that keeps only what is filled in, resolves every
`source_links` row into an inline evidence marker next to the field it
supports, and ends with a catalog of the passages so later stages can cite
them by id. The same brief is the input of every LLM stage, and it is written
to `runs/<run_id>/00_brief.md` as part of the run's provenance.
"""
import hashlib
import json

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

#: Bookkeeping columns present on every record; never interesting in the brief.
_BOILERPLATE = {
    "id", "case_id", "user_id", "assignment_id", "created_at", "updated_at",
    "version", "status", "document_hash", "bounding_boxes",
    "source_annotation_ids", "target_assertion_id", "target_connection_id",
    "causal_relation_json",
}

#: Values the annotation tool writes for "nothing here".
_EMPTY_VALUES = {"", "none", "null", "n/a", "-"}

_PERSPECTIVE_LABELS = {
    "recorrente": "Recorrente",
    "recorrido": "Recorrido",
    "relator": "Relator",
    "voto_convergente": "Voto convergente",
    "voto_divergente": "Voto divergente",
    "stf_final": "Posição final da corte",
}

#: Rendering order for perspectives: the adversarial pair first, then the
#: court, so the brief reads as the dispute does.
_PERSPECTIVE_ORDER = [
    "recorrente", "recorrido", "relator",
    "voto_convergente", "voto_divergente", "stf_final",
]

#: The annotation tool writes `convergente`/`divergente`; the pipeline's own
#: vocabulary spells them `voto_*`. Left unmapped, Fachin's reconstruction
#: renders in the brief as a bare "Convergente" and sorts after the court,
#: the prompts enumerate values the dossier never uses, and every later stage
#: has to guess. Aliasing at the boundary is cheaper than making the two
#: vocabularies agree by decree.
_PERSPECTIVE_ALIASES = {
    "convergente": "voto_convergente",
    "divergente": "voto_divergente",
    "voto convergente": "voto_convergente",
    "voto divergente": "voto_divergente",
    "voto_convergente_fundamento_proprio": "voto_convergente",
    "stf": "stf_final",
    "posicao_final": "stf_final",
}

_FIELD_LABELS = {
    "posicao_defendida": "Posição defendida",
    "fatos_relevantes": "Fatos relevantes",
    "causas_candidatas": "Causas candidatas",
    "causas_candidatas_rejeitadas": "Causas candidatas rejeitadas",
    "causas_juridicamente_relevantes": "Causas juridicamente relevantes",
    "causas_juridicamente_relevantes_rejeitadas": "Causas juridicamente relevantes rejeitadas",
    "relacoes_causais": "Relações causais afirmadas",
    "relacoes_causais_rejeitadas": "Relações causais rejeitadas",
    "fundamento_normativo": "Fundamento normativo (dever jurídico de agir)",
    "razoes_de_decidir": "Razões de decidir",
    "questoes_nao_decididas": "Questões não decididas",
    "conclusao": "Conclusão",
    # divergences
    "divergence_point": "Ponto de divergência",
    "perspective_1": "Perspectiva 1",
    "support_1": "Apoio da perspectiva 1",
    "perspective_2": "Perspectiva 2",
    "support_2": "Apoio da perspectiva 2",
    "reason": "Natureza da divergência",
    "effect_on_conclusion": "Efeito sobre a conclusão",
    "who_sustains": "Quem sustenta",
    "who_contests": "Quem contesta",
    "motive": "Motivo",
    "foundation": "Fundamento",
    "main_layer": "Camada principal",
    "additional_layers": "Camadas adicionais",
    "sides": "Lados",
    "origin_kind": "Origem",
    # causal units
    "candidate_cause": "Causa candidata",
    "result_examined": "Resultado examinado",
    "outcome": "Resultado",
    "alleged_mechanism": "Mecanismo alegado",
    "conditions": "Condições",
    "intermediate_events": "Eventos intermediários",
    "causal_relation": "Relação causal",
    "supported_conclusion": "Conclusão sustentada",
    "perspective_origin": "Perspectiva de origem",
    "perspective_conclusion": "Conclusão da perspectiva",
    "judgment_status": "Status no julgamento",
    "court_treatment": "Tratamento pela corte",
    "legally_relevant_cause": "Causa juridicamente relevante",
    "treatment": "Tratamento",
    "main_passages": "Passagens principais",
    "related_units": "Unidades relacionadas",
    # synthesis
    # perspective reconstructions of the concurring/dissenting votes
    "ponto_divergencia": "Ponto de divergência",
    "razao_divergencia": "Razão da divergência",
    "ponto_aproximacao": "Ponto de aproximação",
    "ponto_distincao": "Ponto de distinção",
    "argumentos_enfrentados": "Argumentos enfrentados",
    "razoes_rejeicao": "Razões da rejeição",
    "fundamento_proprio": "Fundamento próprio",
    "fundamentos": "Fundamentos",
    "perspective": "Perspectiva",
    # synthesis
    "central_question": "Questão central",
    "common_premises": "Premissas comuns",
    "disputed_premises": "Premissas controvertidas",
    "uncontroversial_premises_winning": "Premissas incontroversas acolhidas",
    "uncontroversial_premises_defeated": "Premissas incontroversas afastadas",
    "winning_premises": "Premissas vencedoras",
    "defeated_premises": "Premissas derrotadas",
    "winning_conclusion": "Conclusão vencedora",
    "defeated_conclusions": "Conclusões derrotadas",
    "ambiguities": "Ambiguidades",
    "undecided_questions": "Questões não decididas",
}

#: Collections rendered generically when the annotator filled them in. The
#: case-005 dossier leaves all of these empty, but other cases may not.
_EXTRA_COLLECTIONS = [
    ("annotations", "Anotações"),
    ("assertions", "Afirmações"),
    ("connections", "Conexões"),
    ("timeline", "Linha do tempo"),
    ("perspectives", "Perspectivas (registro livre)"),
    ("facts", "Fatos"),
    ("clarifications", "Esclarecimentos"),
    ("canonical_concepts", "Conceitos canônicos"),
    ("canonical_connections", "Conexões canônicas"),
]


def field_label(key: str) -> str:
    return _FIELD_LABELS.get(key, key.replace("_", " ").capitalize())


def canonical_perspective(perspective_type: str) -> str:
    """The pipeline's own spelling of a perspective the dossier may name
    differently. Unknown values come back untouched, so a vocabulary this
    table has not caught yet still travels intact instead of vanishing."""
    value = (perspective_type or "").strip().lower()
    return _PERSPECTIVE_ALIASES.get(value, value)


def perspective_label(perspective_type: str) -> str:
    """Human label for a `perspective_type` (`recorrente`, `stf_final`, ...).

    Public counterpart of `field_label`, so the interface layer
    (`aspic.dossier_view`) names perspectives exactly as the brief does
    instead of keeping a second, drifting copy of the table.
    """
    canonical = canonical_perspective(perspective_type)
    return _PERSPECTIVE_LABELS.get(canonical, perspective_type or "Perspectiva")


def perspective_sort_key(perspective_type: str) -> int:
    """Position of a perspective in the brief's reading order (the
    adversarial pair first, then the court); unknown types sort last."""
    canonical = canonical_perspective(perspective_type)
    if canonical in _PERSPECTIVE_ORDER:
        return _PERSPECTIVE_ORDER.index(canonical)
    return len(_PERSPECTIVE_ORDER)


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _EMPTY_VALUES
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _as_text(value) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {v}" for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value).strip()


@dataclass(frozen=True)
class Passage:
    """One quoted stretch of the source PDF, citable by id."""
    id: str
    page: Optional[int]
    text: str
    document_id: str = ""
    section: str = ""
    author: str = ""


class Dossier:
    """An annotated dossier, plus the derived views the pipeline needs."""

    def __init__(self, raw: dict, *, path: Optional[Path] = None, sha256: str = ""):
        self.raw = raw
        self.path = path
        self.sha256 = sha256

    # -- identity ------------------------------------------------------
    @property
    def case_id(self) -> str:
        return self.raw.get("case_id") or self.raw.get("case", {}).get("id", "caso")

    @property
    def annotator(self) -> str:
        return self.raw.get("user_id", "")

    @property
    def title(self) -> str:
        return self.raw.get("case", {}).get("title") or self.case_id

    @property
    def session_id(self) -> str:
        return self.raw.get("case", {}).get("session_id", "")

    # -- evidence ------------------------------------------------------
    def passages(self) -> Dict[str, Passage]:
        result: Dict[str, Passage] = {}
        for row in self.raw.get("source_passages", []):
            result[row["id"]] = Passage(
                id=row["id"],
                page=row.get("pdf_page"),
                text=(row.get("text") or "").strip(),
                document_id=row.get("document_id") or "",
                section=row.get("section") or "",
                author=row.get("vote_or_author") or "",
            )
        return result

    def evidence_index(self) -> Dict[Tuple[str, str], List[str]]:
        """`(entity_id, field_key) -> [passage ids]`, from `source_links`.

        Keyed on the entity id alone (not the type) because ids are already
        globally unique and prefixed by kind (`prec_`, `divg_`, ...).
        """
        index: Dict[Tuple[str, str], List[str]] = {}
        for link in self.raw.get("source_links", []):
            key = (link.get("entity_id", ""), link.get("field_key", ""))
            index.setdefault(key, []).append(link.get("source_passage_id", ""))
        return index

    def valid_ids(self) -> Set[str]:
        """Every id a later stage is allowed to cite as evidence or ref."""
        ids: Set[str] = set(self.passages())
        for key in ("divergences", "causal_units", "perspective_reconstructions",
                    *[name for name, _ in _EXTRA_COLLECTIONS]):
            for row in self.raw.get(key, []) or []:
                if isinstance(row, dict) and row.get("id"):
                    ids.add(row["id"])
        synthesis = self.raw.get("synthesis") or {}
        if synthesis.get("id"):
            ids.add(synthesis["id"])
        return ids

    # -- brief ---------------------------------------------------------
    def brief(self) -> str:
        ev = self.evidence_index()
        passages = self.passages()
        out: List[str] = [
            f"# Dossiê — {self.title} (`{self.case_id}`)",
            "",
            f"Anotador: `{self.annotator}` · Sessão: `{self.session_id or '—'}`",
            "",
        ]
        out += self._synthesis_block(ev)
        out += self._perspectives_block(ev)
        out += self._divergences_block(ev)
        out += self._causal_units_block(ev)
        out += self._extra_collections_block(ev)
        out += self._passages_block(passages)
        return "\n".join(out).rstrip() + "\n"

    # -- brief sections ------------------------------------------------
    def _field_lines(self, entity_id: str, key: str, value, ev) -> List[str]:
        if _is_empty(value):
            return []
        marker = self._evidence_marker(ev.get((entity_id, key), []))
        text = _as_text(value)
        head = f"**{field_label(key)}**{marker}"
        if "\n" in text:
            return [head, "", text, ""]
        return [f"{head}: {text}", ""]

    @staticmethod
    def _evidence_marker(passage_ids: Iterable[str]) -> str:
        ids = [p for p in passage_ids if p]
        return f" _(evidência: {', '.join(f'`{p}`' for p in ids)})_" if ids else ""

    def _synthesis_block(self, ev) -> List[str]:
        synthesis = self.raw.get("synthesis") or {}
        if not synthesis:
            return []
        lines = [f"## Síntese do caso  `{synthesis.get('id', '')}`", ""]
        body: List[str] = []
        for key, value in synthesis.items():
            if key in _BOILERPLATE:
                continue
            body += self._field_lines(synthesis.get("id", ""), key, value, ev)
        return lines + body if body else []

    def _perspectives_block(self, ev) -> List[str]:
        records = self.raw.get("perspective_reconstructions") or []
        if not records:
            return []
        ordered = sorted(
            records,
            key=lambda r: (
                _PERSPECTIVE_ORDER.index(r.get("perspective_type", ""))
                if r.get("perspective_type") in _PERSPECTIVE_ORDER else len(_PERSPECTIVE_ORDER),
                r.get("perspective_type", ""),
            ),
        )
        lines = ["## Reconstrução por perspectiva", ""]
        for record in ordered:
            ptype = record.get("perspective_type", "")
            label = perspective_label(ptype)
            who = record.get("person_or_body")
            suffix = f" — {who}" if who else ""
            lines += [f"### {label}{suffix}  `{record.get('id', '')}` (`{ptype}`)", ""]
            for key, value in (record.get("fields_json") or {}).items():
                lines += self._field_lines(record.get("id", ""), key, value, ev)
        return lines

    def _divergences_block(self, ev) -> List[str]:
        records = self.raw.get("divergences") or []
        if not records:
            return []
        lines = ["## Divergências", ""]
        for i, record in enumerate(records, start=1):
            point = record.get("divergence_point") or f"divergência {i}"
            lines += [f"### D{i} — {point}  `{record.get('id', '')}`", ""]
            for key, value in record.items():
                if key in _BOILERPLATE or key == "divergence_point":
                    continue
                lines += self._field_lines(record.get("id", ""), key, value, ev)
        return lines

    def _causal_units_block(self, ev) -> List[str]:
        records = self.raw.get("causal_units") or []
        if not records:
            return []
        lines = ["## Unidades causais", ""]
        for i, record in enumerate(records, start=1):
            cause = (record.get("candidate_cause") or f"unidade {i}").replace("\n", " / ")
            lines += [f"### U{i} — {cause}  `{record.get('id', '')}`", ""]
            for key, value in record.items():
                if key in _BOILERPLATE or key == "candidate_cause":
                    continue
                lines += self._field_lines(record.get("id", ""), key, value, ev)
        return lines

    def _extra_collections_block(self, ev) -> List[str]:
        lines: List[str] = []
        for name, label in _EXTRA_COLLECTIONS:
            records = self.raw.get(name) or []
            if not records:
                continue
            lines += [f"## {label}", ""]
            for i, record in enumerate(records, start=1):
                if not isinstance(record, dict):
                    lines += [f"- {record}", ""]
                    continue
                lines += [f"### {label[:-1] if label.endswith('s') else label} {i}  `{record.get('id', '')}`", ""]
                for key, value in record.items():
                    if key in _BOILERPLATE:
                        continue
                    lines += self._field_lines(record.get("id", ""), key, value, ev)
        return lines

    def _passages_block(self, passages: Dict[str, Passage]) -> List[str]:
        if not passages:
            return []
        lines = [
            "## Passagens de origem (cite pelo id)",
            "",
            "Trechos literais do acórdão. Use estes ids no campo `evidence`.",
            "",
        ]
        for passage in sorted(passages.values(), key=lambda p: (p.page or 0, p.id)):
            where = f"p. {passage.page}" if passage.page else "página não informada"
            extra = f", {passage.section}" if passage.section else ""
            author = f", {passage.author}" if passage.author else ""
            text = " ".join(passage.text.split())
            lines += [f"- `{passage.id}` ({where}{extra}{author}): “{text}”"]
        lines.append("")
        return lines

    # -- misc ----------------------------------------------------------
    def perspective_types(self) -> List[str]:
        """Every perspective the dossier reconstructs, canonicalized and in
        reading order. This is the roll call of who took part -- including
        whoever the formalization ended up attributing nothing to."""
        found = {
            canonical_perspective(record.get("perspective_type", ""))
            for record in (self.raw.get("perspective_reconstructions") or [])
            if record.get("perspective_type")
        }
        return sorted(found, key=perspective_sort_key)

    def stats(self) -> Dict[str, int]:
        counts = {
            name: len(self.raw.get(name) or [])
            for name in ("divergences", "causal_units", "perspective_reconstructions",
                         "source_passages", "source_links", *[n for n, _ in _EXTRA_COLLECTIONS])
        }
        counts["synthesis"] = 1 if self.raw.get("synthesis") else 0
        return counts


def load_dossier(path) -> Dossier:
    path = Path(path)
    payload = path.read_bytes()
    return Dossier(
        json.loads(payload.decode("utf-8")),
        path=path,
        sha256=hashlib.sha256(payload).hexdigest(),
    )
