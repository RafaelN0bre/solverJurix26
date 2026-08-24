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
    assert "case-select" in resp.text
    assert "case-container" in resp.text


def test_list_cases_returns_all_catalog_entries():
    resp = client.get("/api/cases")
    assert resp.status_code == 200
    payload = resp.json()
    assert [entry["id"] for entry in payload] == [case.id for case in LEGAL_CASES]
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
