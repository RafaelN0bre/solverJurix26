"""Resolves the workspace root -- where `docs/` and `data/` live, one level
above the repository. Every read and write path of the pipeline (dossiers,
records under `data/translated/`, figures under `docs/figures/`) goes
through here.
"""

"""Where the documentation and the data live: in the workspace, not in the
project.

This repository and `anotadorJurix26` are two projects of a single work, and
the documentation and the data are shared between them — the dossier the
annotator produces is the solver's input, and the formalized judgment feeds
both. That is why `docs/` and `data/` live one level above, in the repository
that composes the two as submodules, and not duplicated inside each one.

The resolution has three steps, in this order:

1. `JURIX_WORKSPACE`, if declared — it is what the tests use to point at a
   temporary directory;
2. the parent directory, if it has `docs/` and `data/` — the normal case,
   with the project mounted as a submodule of the workspace;
3. the project's own root — for when it is cloned on its own, without the
   workspace around it, and still needs to run.
"""
import os

from pathlib import Path

#: This project's root (the directory that contains `src/`).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def workspace_root() -> Path:
    """The workspace root: where `docs/` and `data/` are."""
    override = os.environ.get("JURIX_WORKSPACE")
    if override:
        return Path(override).expanduser().resolve()
    parent = PROJECT_ROOT.parent
    if (parent / "docs").is_dir() and (parent / "data").is_dir():
        return parent
    return PROJECT_ROOT


def docs_dir() -> Path:
    return workspace_root() / "docs"


def data_dir() -> Path:
    return workspace_root() / "data"
