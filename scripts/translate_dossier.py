#!/usr/bin/env python3
"""Formaliza um dossiê anotado (data/<anotador>/*.json) como framework ASPIC+.

    uv run python scripts/translate_dossier.py --input data/izabela-melo/case-005-dossie-2026-08-24.json
    uv run python scripts/translate_dossier.py --input <arquivo> --dry-run

Insere `src` no path pelo mesmo motivo que scripts/run_app.py: a instalação
editável não é importável de forma confiável fora do pytest nesta combinação
de uv/Python.
"""
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from formalize.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
