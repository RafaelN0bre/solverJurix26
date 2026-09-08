"""Pins the `expect_ness` / `expect_but_for` fields on every `CausalQuery` in
`aspic.examples.LEGAL_CASES` to what the solver actually computes -- these
fields are what `scripts/generate_graphs.py` renders in each case's
causal-comparison table, so they must never silently drift from reality."""
import pytest

from aspic.examples import LEGAL_CASES
from aspic.solver import ArgumentationFramework

CASES_AND_QUERIES = [
    (case, query) for case in LEGAL_CASES for query in case.queries
]


@pytest.mark.parametrize(
    "case,query", CASES_AND_QUERIES,
    ids=[f"{case.id}:{query.phi}->{query.psi}" for case, query in CASES_AND_QUERIES],
)
def test_causal_query_expectations_match_solver(case, query):
    af = ArgumentationFramework(case.knowledge_base, case.causal_model)

    assert af.ness_cause(query.phi, query.psi) is query.expect_ness
    assert af.but_for(query.phi, query.psi) is query.expect_but_for
