#!/usr/bin/env python3
"""Run the live case-explorer app (aspic.api:app) with auto-reload.

Runs uvicorn programmatically (rather than via `uv run uvicorn aspic.api:app`)
because this uv/Python combination leaves the editable install's `.pth` file
flagged hidden on macOS, which CPython 3.13's site module skips -- so `aspic`
isn't reliably importable outside of pytest (which sets `pythonpath` itself
via pyproject.toml). Inserting `src` directly here sidesteps that, matching
how `scripts/generate_graphs.py` already does it.

Usage:
    uv run python scripts/run_app.py
then open http://127.0.0.1:8000/
"""
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("aspic.api:app", host="127.0.0.1", port=8000, reload=True,
                reload_dirs=[str(REPO_ROOT / "src")])
