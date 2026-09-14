"""Dossier discovery after the shared data-directory cleanup."""
import json

from cases.catalog import dossier_paths_all


def test_discovers_all_annotators_in_shared_layout_and_legacy_exports(tmp_path):
    for relative in (
        "annotations/andressa/case.json",
        "annotations/izabela/case.json",
        "annotations/vitor/case.json",
        "legacy-annotator/case.json",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"case_id": "case-003", "perspective_reconstructions": [{}]}))
    generated = tmp_path / "annotations/translated/index.json"
    generated.parent.mkdir(parents=True)
    generated.write_text(json.dumps({"cases": ["case-003"]}))

    found = dossier_paths_all(tmp_path)

    assert set(found) == {"case-003"}
    assert len(found["case-003"]) == 4
    assert generated not in found["case-003"]
