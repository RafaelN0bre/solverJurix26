"""Regression guard over the formalizations actually committed to the repo.

`case.json` stores what the solver concluded at the time the case was
formalized. Re-running the solver here turns any change to `aspic.solver`,
`aspic.ness` or `formalize.bridge` that would silently alter a published
formalization into a failing test, instead of into a quietly different figure
in the article.

Skipped when `data/translated/` is empty, so a fresh clone is not red before
the pipeline has ever been run.
"""
import json

import pytest

from formalize import build
from formalize.schema import FormalizedCase
from formalize.validate import validate_case

from aspic.catalog import DEFAULT_TRANSLATED_DIR

CASE_FILES = sorted(DEFAULT_TRANSLATED_DIR.glob("*/case.json"))
pytestmark = pytest.mark.skipif(
    not CASE_FILES, reason="nenhum caso formalizado em data/translated")


def load(path):
    return FormalizedCase.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case_file", CASE_FILES, ids=lambda p: p.parent.name)
def test_stored_solver_verdicts_still_hold(case_file):
    stored = load(case_file)
    recomputed = build.annotate(stored)
    for before, after in zip(stored.queries, recomputed.queries):
        assert before.solver is not None, "case.json sem vereditos gravados"
        assert before.solver.model_dump() == after.solver.model_dump(), (
            f"veredito mudou para ({before.phi} → {before.psi})")
        assert before.legally_relevant == after.legally_relevant


@pytest.mark.parametrize("case_file", CASE_FILES, ids=lambda p: p.parent.name)
def test_record_still_validates(case_file):
    report = validate_case(load(case_file))
    assert report.ok, report.render_errors()


@pytest.mark.parametrize("case_file", CASE_FILES, ids=lambda p: p.parent.name)
def test_record_renders(case_file):
    """The adapter must keep producing a CaseSpec the renderers accept."""
    from aspic.didactic import render_case_didactic
    from aspic.formalization_view import render_formalization_fiche

    record = load(case_file)
    spec = build.to_case_spec(record)
    assert spec.origin == "dossie"
    assert spec.effect in spec.atom_glosses
    assert render_case_didactic(spec).lstrip().startswith("<section")
    assert "Ficha de formalização" in render_formalization_fiche(record)


@pytest.mark.parametrize("case_file", CASE_FILES, ids=lambda p: p.parent.name)
def test_stored_validation_matches_the_record(case_file):
    validation_file = case_file.parent / "validation.json"
    if not validation_file.is_file():
        pytest.skip("sem validation.json")
    stored = json.loads(validation_file.read_text(encoding="utf-8"))
    recomputed = validate_case(build.annotate(load(case_file)))
    assert stored["summary"]["agreement"] == recomputed.summary["agreement"]
