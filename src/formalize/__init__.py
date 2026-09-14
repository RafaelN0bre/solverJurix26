"""Package that turns the hand-transcribed formalization record into solver
input and keeps it honest: schema, normalization, bridge, assembly,
validation and storage. It is the stretch of the pipeline between the
annotated dossier and the frameworks `aspic` runs.
"""

"""Deterministic formalization of annotated legal dossiers into ASPIC+ input.

No generative model is involved anywhere in this package: the executable
record of the case study is hand-transcribed from the consolidated
formalization document (`docs/formalizacao-caso003.md`) by
`scripts/build_case003_final.py`, and everything here either assembles,
checks or stores that record. Submodules:

* `schema` -- the pydantic contract of `data/translated/<case>/case.json`;
* `dossier` -- deterministic normalization of an annotated dossier into a
  readable, diffable brief (display and audit only);
* `bridge` -- the cause-in-fact facts (`CaFa_*`/`ButFor_*`) that feed the
  legal-relevance layer, always computed by the solver, never authored;
* `build` -- record -> solver frameworks -> `cases.CaseSpec`;
* `validate` -- deterministic checks and the solver-vs-court table;
* `store` -- the `data/translated/` layout and its `index.json`.

An earlier version of this package formalized dossiers through a staged LLM
pipeline (Google Gemini); that machinery was removed on purpose, so that no
object in the theory is produced by generative AI.
"""
from .schema import SCHEMA_VERSION, FormalizedCase

__all__ = ["SCHEMA_VERSION", "FormalizedCase"]
