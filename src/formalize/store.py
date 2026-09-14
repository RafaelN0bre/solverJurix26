"""Disk layout of the formalized cases under `data/translated/` and the
`index.json` the interface lists cases from. The transcription and re-run
scripts write through here; `cases.catalog` reads through here.
"""

"""Where formalized cases live on disk, and the index the interface reads.

The layout under `data/translated/` is one directory per case:

    data/translated/index.json                 catalog of every case
    data/translated/<case-id>/case.json        the canonical record
    data/translated/<case-id>/validation.json  checks + solver-vs-court table

`update_index` rebuilds `index.json` from whatever `case.json` files exist,
so the index can never disagree with the records on disk. The records
themselves are written by the transcription scripts
(`scripts/build_case003_final.py`) and re-checked by
`scripts/run_translated.py`; nothing else writes here.
"""
import json
import logging

from pathlib import Path

from cases.workspace import data_dir

from .schema import FormalizedCase

logger = logging.getLogger(__name__)

DEFAULT_OUT_DIR = data_dir() / "translated"


def update_index(out_dir: Path) -> None:
    """Rebuild `index.json` from whatever `case.json` files exist."""
    entries = []
    for case_file in sorted(out_dir.glob("*/case.json")):
        try:
            case = FormalizedCase.model_validate_json(case_file.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a broken record must not break the index
            logger.warning("Ignorando %s: não é um case.json válido", case_file)
            continue
        validation_file = case_file.parent / "validation.json"
        summary = {}
        if validation_file.is_file():
            try:
                summary = json.loads(validation_file.read_text(encoding="utf-8")).get("summary", {})
            except json.JSONDecodeError:
                summary = {}
        entries.append({
            "case_id": case.case.id,
            "title": case.case.title,
            "annotator": case.case.annotator,
            "path": str(case_file.relative_to(out_dir)),
            "run_id": case.provenance.run_id if case.provenance else "",
            "created_at": case.provenance.created_at if case.provenance else "",
            "model": case.provenance.model if case.provenance else "",
            "summary": summary,
        })
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
