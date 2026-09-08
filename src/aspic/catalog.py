"""The unified case catalog behind the interface.

Two sources of cases feed the same renderers:

* the five worked examples of the ICAIL papers, hardcoded in `aspic.examples`;
* the cases formalized from annotated dossiers, living as `case.json` records
  under `data/translated/` (see `formalize.pipeline`).

Both arrive here as `CaseSpec`, so `aspic.didactic` and `aspic.report` never
learn that a case came from a dossier -- the only difference visible to them
is `CaseSpec.origin` (used to tag the dropdown) and the optional `CaseSpec.lrc`
layer, which dossier cases carry and the paper cases do not.

Translated records are re-read from disk on every call rather than cached, so
re-running the pipeline while the app is up shows the new formalization on the
next request.
"""
import json
import logging
import os

from pathlib import Path
from typing import Dict, List, Optional

from .examples import LEGAL_CASES, CaseSpec

logger = logging.getLogger("aspic.catalog")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TRANSLATED_DIR = REPO_ROOT / "data" / "translated"

ORIGIN_LABELS = {"paper": "artigo", "dossie": "dossiê",
                 "dossie_bruto": "dossiê não formalizado"}


def translated_dir() -> Path:
    """Where formalized cases live. `ASPIC_TRANSLATED_DIR` overrides, which is
    what the tests use to point at a fixture directory."""
    override = os.environ.get("ASPIC_TRANSLATED_DIR")
    return Path(override) if override else DEFAULT_TRANSLATED_DIR


def formalized_records(directory: Optional[Path] = None) -> Dict[str, "object"]:
    """`{case_id: FormalizedCase}` for every readable record on disk."""
    from formalize.schema import FormalizedCase

    directory = Path(directory) if directory else translated_dir()
    records: Dict[str, object] = {}
    if not directory.is_dir():
        return records
    for case_file in sorted(directory.glob("*/case.json")):
        try:
            record = FormalizedCase.model_validate_json(case_file.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - one broken record must not empty the catalog
            logger.warning("Ignorando %s: %s", case_file, exc)
            continue
        records[record.case.id] = record
    return records


def translated_cases(directory: Optional[Path] = None) -> List[CaseSpec]:
    from formalize.build import to_case_spec

    return [to_case_spec(record) for record in formalized_records(directory).values()]


def all_cases(directory: Optional[Path] = None) -> List[CaseSpec]:
    """Paper cases first, then formalized ones, each group in catalog order."""
    return [*LEGAL_CASES, *translated_cases(directory)]


def case_by_id(case_id: str, directory: Optional[Path] = None) -> CaseSpec:
    for case in all_cases(directory):
        if case.id == case_id:
            return case
    raise KeyError(f"No such case: {case_id!r}")


def formalization_by_id(case_id: str, directory: Optional[Path] = None):
    """The full formalization record for a dossier case, or None for a paper case."""
    return formalized_records(directory).get(case_id)


def validation_by_id(case_id: str, directory: Optional[Path] = None) -> Optional[dict]:
    """The stored `validation.json` (checks + solver-vs-court table), if any."""
    directory = Path(directory) if directory else translated_dir()
    path = directory / case_id / "validation.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("validation.json inválido para %s: %s", case_id, exc)
        return None


def listing(directory: Optional[Path] = None) -> List[dict]:
    """Every case the renderers can build: id, title, provenance, and which
    views exist for it (`has_record` gates the fiche and the conference,
    `has_dossier` the raw-annotation view)."""
    records = formalized_records(directory)
    dossiers = dossier_paths_all()
    return [
        {
            "id": case.id,
            "title": case.title,
            "origin": case.origin,
            "origin_label": ORIGIN_LABELS.get(case.origin, case.origin),
            "has_lrc": case.lrc is not None,
            "has_preferences": bool(
                case.id in records and records[case.id].preferences is not None
                and records[case.id].preferences.dimensions),
            "has_case": True,
            "has_record": case.id in records,
            "has_dossier": case.id in dossiers or (
                records[case.id].case.dossier_id in dossiers
                if case.id in records else False),
            "has_brief": bool(brief_by_id(case.id, directory=directory)),
        }
        for case in all_cases(directory)
    ]


# ----------------------------------------------------------------------
# The other half of the picture: the annotator's raw dossiers, and the
# pipeline runs that turned them into formalizations.
# ----------------------------------------------------------------------
#: Where the annotated dossiers live: `data/<annotator>/<case>-dossie-*.json`.
DEFAULT_DOSSIER_ROOT = REPO_ROOT / "data"

#: `path -> (mtime, size, case_id)`. Dossiers are hundreds of kilobytes and
#: every request needs the id-to-path map, so the *identification* pass is
#: cached on the file's stat; the parse itself is not, matching how
#: `formalized_records` re-reads from disk each time.
_DOSSIER_IDS: Dict[Path, tuple] = {}


def dossier_root() -> Optional[Path]:
    """Root under which dossiers are looked for. `ASPIC_DOSSIER_ROOT`
    overrides, which is what the tests use to point at a fixture directory."""
    override = os.environ.get("ASPIC_DOSSIER_ROOT")
    return Path(override) if override else DEFAULT_DOSSIER_ROOT


def _dossier_case_id(path: Path) -> Optional[str]:
    """`case_id` of a dossier export, or None if the file is not one.

    A dossier is recognised by carrying at least one of the annotation
    collections -- `data/` also holds `translated/index.json` and whatever
    else an annotator drops there, and neither should end up in the catalog.
    """
    try:
        stat = path.stat()
    except OSError:
        return None
    cached = _DOSSIER_IDS.get(path)
    if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
        return cached[2]
    case_id = None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Ignorando %s como dossiê: %s", path, exc)
        payload = None
    if isinstance(payload, dict) and any(
        key in payload for key in ("source_passages", "perspective_reconstructions",
                                   "causal_units", "divergences")
    ):
        case_id = payload.get("case_id") or (payload.get("case") or {}).get("id")
    _DOSSIER_IDS[path] = (stat.st_mtime, stat.st_size, case_id)
    return case_id


def dossier_paths_all(root: Optional[Path] = None) -> Dict[str, List[Path]]:
    """`{case_id: [path, ...]}` -- **every** annotator's dossier for a case.

    A case annotated by three people has three dossiers, and for case-003 they
    are genuinely different documents: 41, 28 and 18 marked passages, with
    disjoint passage ids and different counts of causal units and
    divergences. Collapsing them to one throws two thirds of the annotation
    away, and picking which one to keep by directory name -- which is what
    this module used to do -- picks it by accident.

    The formalization output directory is skipped explicitly: its own
    `index.json` sits at exactly the depth this glob walks.
    """
    root = Path(root) if root else dossier_root()
    if root is None or not root.is_dir():
        return {}
    skip = translated_dir().resolve()
    found: Dict[str, List[Path]] = {}
    for path in sorted(root.glob("*/*.json")):
        if path.parent.resolve() == skip:
            continue
        case_id = _dossier_case_id(path)
        if case_id:
            found.setdefault(case_id, []).append(path)
    return found


def dossier_paths(root: Optional[Path] = None) -> Dict[str, Path]:
    """`{case_id: path}` for the **primary** dossier of each case.

    Kept for callers that genuinely need one file. Which one is primary is
    decided by `primary_dossier_path`, not by sort order.
    """
    return {case_id: primary_dossier_path(case_id, paths)
            for case_id, paths in dossier_paths_all(root).items()}


def primary_dossier_path(case_id: str, paths: Optional[List[Path]] = None,
                         directory: Optional[Path] = None) -> Optional[Path]:
    """Which annotator's dossier a formalization actually came from.

    In order: the file the record names in `case.source_file`; failing that,
    the directory matching `case.annotator`; failing that, the first in sort
    order, which is the old behaviour and is now the last resort rather than
    the rule.

    This mattered more than it looks. `case-003` was formalized from Izabela's
    dossier -- all 22 passages it cites are hers -- while the Dossiê tab was
    showing Andressa's, because `andressa-bissolotti` sorts first. The tab and
    the formalization were describing different documents.
    """
    if paths is None:
        paths = dossier_paths_all().get(case_id, [])
    if not paths:
        return None
    record = formalized_records(directory).get(case_id)
    if record is not None:
        named = getattr(record.case, "source_file", "")
        if named:
            target = Path(named)
            if not target.is_absolute():
                target = REPO_ROOT / target
            for path in paths:
                if path.resolve() == target.resolve():
                    return path
        annotator = getattr(record.case, "annotator", "")
        if annotator:
            for path in paths:
                if path.parent.name == annotator:
                    return path
    return paths[0]


def dossier_source_id(case_id: str, directory: Optional[Path] = None) -> str:
    """Which dossier a case reads from.

    Normally its own id. A record may instead declare `case.dossier_case_id`,
    which is how two formalizations of the *same* judgment -- a second pass
    that models the votes separately, say -- both reach the annotator's one
    dossier instead of the second one silently losing its evidence, its
    coverage numbers and its dossier tab.
    """
    record = formalized_records(directory).get(case_id)
    if record is None:
        return case_id
    return record.case.dossier_id


def dossier_path_by_id(case_id: str, root: Optional[Path] = None) -> Optional[Path]:
    """The primary dossier of a case, following `case.dossier_case_id` when
    the record points at another case's annotation."""
    every = dossier_paths_all(root)
    for key in (case_id, dossier_source_id(case_id)):
        if key in every:
            return primary_dossier_path(key, every[key])
    return None


def dossier_paths_for(case_id: str, root: Optional[Path] = None) -> List[Path]:
    """Every annotator's dossier for a case, primary first."""
    every = dossier_paths_all(root)
    for key in (case_id, dossier_source_id(case_id)):
        if key in every:
            paths = list(every[key])
            primary = primary_dossier_path(key, paths)
            if primary in paths:
                paths.remove(primary)
                paths.insert(0, primary)
            return paths
    return []


def dossiers_by_id(case_id: str, root: Optional[Path] = None) -> List:
    """Every annotator's parsed `formalize.dossier.Dossier`, primary first.

    A broken dossier is skipped with a warning rather than emptying the list:
    one annotator's malformed export must not hide the other two.
    """
    from formalize.dossier import load_dossier

    out = []
    for path in dossier_paths_for(case_id, root):
        try:
            out.append(load_dossier(path))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Não foi possível ler o dossiê %s: %s", path, exc)
    return out


def all_passages(case_id: str, root: Optional[Path] = None) -> Dict[str, tuple]:
    """`{passage_id: (annotator, Passage)}` across every annotator of a case.

    The three exports use disjoint id spaces, so the union is unambiguous and
    each passage still knows whose it is. This is what lets a citation be
    resolved -- and attributed -- no matter which annotator marked it.
    """
    found: Dict[str, tuple] = {}
    for dossier in dossiers_by_id(case_id, root):
        for passage_id, passage in dossier.passages().items():
            found.setdefault(passage_id, (dossier.annotator, passage))
    return found


# ----------------------------------------------------------------------
# The consolidation the annotators agreed on
# ----------------------------------------------------------------------
def consolidation_path(root: Optional[Path] = None) -> Path:
    return (Path(root) if root else dossier_root()) / "consolidacao-main.json"


def consolidation(case_id: str, root: Optional[Path] = None) -> Optional[dict]:
    """The canonical consolidation of the annotators' three proposals, or None.

    Produced by `scripts/build_consolidacao_main.py` from every
    `data/<annotator>/consolidacao.json`. It is the answer to "which reading
    is the case's", which picking one annotator's dossier by sort order
    silently pretended not to need.
    """
    path = consolidation_path(root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("consolidacao-main.json inválido: %s", exc)
        return None
    wanted = {case_id, dossier_source_id(case_id)}
    return payload if payload.get("case_id") in wanted else None


def dossier_by_id(case_id: str, root: Optional[Path] = None):
    """The parsed `formalize.dossier.Dossier` for a case, or None when no
    dossier for it is on disk (the paper cases never have one, and a
    formalized case may have been produced from a file since moved away)."""
    path = dossier_path_by_id(case_id, root)
    if path is None:
        return None
    from formalize.dossier import load_dossier
    try:
        return load_dossier(path)
    except Exception as exc:  # noqa: BLE001 - a broken dossier must not 500 the app
        logger.warning("Não foi possível ler o dossiê %s: %s", path, exc)
        return None


def run_dirs(case_id: str, directory: Optional[Path] = None) -> List[Path]:
    """Every `runs/<run_id>/` directory of a formalized case, newest first
    (run ids are timestamps, so lexicographic order is chronological)."""
    directory = Path(directory) if directory else translated_dir()
    runs = directory / case_id / "runs"
    if not runs.is_dir():
        return []
    return sorted((d for d in runs.iterdir() if d.is_dir()), reverse=True)


def run_summaries(case_id: str, directory: Optional[Path] = None) -> List[dict]:
    """`run.json` of every run of a case, newest first, each augmented with
    `run_id` and whether the run kept a brief. Runs that never finished have
    no `run.json`; they still show up, flagged as incomplete."""
    summaries: List[dict] = []
    for run_dir in run_dirs(case_id, directory):
        entry: dict = {"run_id": run_dir.name, "complete": False,
                       "has_brief": (run_dir / "00_brief.md").is_file()}
        run_file = run_dir / "run.json"
        if run_file.is_file():
            try:
                entry.update(json.loads(run_file.read_text(encoding="utf-8")))
                entry["complete"] = True
            except json.JSONDecodeError as exc:
                logger.warning("run.json inválido em %s: %s", run_dir, exc)
        entry["run_id"] = run_dir.name
        summaries.append(entry)
    return summaries


def brief_by_id(case_id: str, run_id: Optional[str] = None,
                directory: Optional[Path] = None) -> Optional[dict]:
    """The normalized dossier brief a run fed to the model, as
    `{"run_id": ..., "markdown": ...}` -- the newest one that has a brief
    unless `run_id` names another. None when the case has no run with one.

    This is what makes a formalization auditable even after its source
    dossier has moved: the brief is the exact text the model read.
    """
    for run_dir in run_dirs(case_id, directory):
        if run_id is not None and run_dir.name != run_id:
            continue
        path = run_dir / "00_brief.md"
        if path.is_file():
            return {"run_id": run_dir.name, "markdown": path.read_text(encoding="utf-8")}
    return None


def dossier_only_listing(directory: Optional[Path] = None) -> List[dict]:
    """Cases that exist as an annotated dossier but were never formalized.

    They have no `CaseSpec` and therefore no analysis, no fiche and no
    conference -- only the dossier view. Listing them anyway is the point:
    an annotated case nobody has run the pipeline on is exactly the kind of
    thing that otherwise stays invisible.
    """
    known = {case.id for case in all_cases(directory)}
    entries = []
    for case_id, paths in dossier_paths_all().items():
        path = paths[0]
        if case_id in known:
            continue
        dossier = dossier_by_id(case_id)
        entries.append({
            "id": case_id,
            "title": (dossier.title if dossier else case_id),
            "origin": "dossie_bruto",
            "origin_label": ORIGIN_LABELS["dossie_bruto"],
            "has_lrc": False,
            "has_case": False,
            "has_record": False,
            "has_dossier": True,
            "has_brief": False,
            "has_preferences": False,
            "path": str(path),
        })
    return sorted(entries, key=lambda entry: entry["id"])


def full_listing(directory: Optional[Path] = None) -> List[dict]:
    """Everything the interface can show, formalized cases first."""
    return [*listing(directory), *dossier_only_listing(directory)]
