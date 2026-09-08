"""Tests for the live case-explorer API (aspic.api). Uses FastAPI's
TestClient, so no real server/socket is needed; graph rendering still
shells out to the real `dot` binary, matching how the app behaves live."""
import shutil

import pytest
from fastapi.testclient import TestClient

from aspic.api import app
from aspic.examples import LEGAL_CASES

pytestmark = pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz 'dot' not installed")

client = TestClient(app)


def test_index_serves_html_shell():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "case-nav" in resp.text       # the case picker
    assert "case-container" in resp.text  # where a view is injected


def test_list_cases_returns_all_catalog_entries():
    """The dropdown leads with the paper cases, in catalog order, and may be
    followed by whatever has been formalized into `data/translated/` -- see
    `test_catalog_api.py` for the dossier side, which pins its own directory
    instead of depending on what happens to be committed."""
    resp = client.get("/api/cases")
    assert resp.status_code == 200
    payload = resp.json()
    paper_ids = [entry["id"] for entry in payload if entry["origin"] == "paper"]
    assert paper_ids == [case.id for case in LEGAL_CASES]
    assert payload[:len(LEGAL_CASES)] == [entry for entry in payload
                                          if entry["origin"] == "paper"]
    assert all("title" in entry for entry in payload)


@pytest.mark.parametrize("case", LEGAL_CASES, ids=[c.id for c in LEGAL_CASES])
def test_get_case_returns_matching_fragment(case):
    resp = client.get(f"/api/cases/{case.id}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert f'id="{case.id}"' in resp.text
    assert "<svg" in resp.text


def test_get_unknown_case_returns_404():
    resp = client.get("/api/cases/not-a-real-case")
    assert resp.status_code == 404
