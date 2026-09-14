#!/usr/bin/env python3
"""Entry-point script: runs the live case explorer (`interface.api:app`)
under uvicorn with auto-reload. The interactive way into the pipeline's
outputs; the static equivalents are `generate_graphs.py` and
`render_translated.py`.
"""

"""Run the live case-explorer app (interface.api:app) with auto-reload.

Runs uvicorn programmatically (rather than via `uv run uvicorn interface.api:app`)
because this uv/Python combination leaves the editable install's `.pth` file
flagged hidden on macOS, which CPython 3.13's site module skips -- so `aspic`
isn't reliably importable outside of pytest (which sets `pythonpath` itself
via pyproject.toml). Inserting `src` directly here sidesteps that, matching
how `scripts/generate_graphs.py` already does it.

Usage:
    uv run python scripts/run_app.py
then open http://127.0.0.1:8000/

Set `ASPIC_APP_PORT` to run somewhere else, which is what you want when
another service already holds 8000.
"""
import os
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("ASPIC_APP_PORT", "8000"))
    uvicorn.run("interface.api:app", host="127.0.0.1", port=port, reload=True,
                reload_dirs=[str(REPO_ROOT / "src")])
