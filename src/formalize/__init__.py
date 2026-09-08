"""LLM-assisted formalization of annotated legal dossiers into ASPIC+ input.

Reads the dossiers under `data/<annotator>/`, turns them into executable
argumentation frameworks with Google Gemini, and writes the result to
`data/translated/` for `aspic.catalog` (and therefore the interface) to load.

Submodules, in pipeline order: `dossier` (deterministic normalization),
`prompts` (versioned prompt files), `gemini` (the model client), `stages` (the
four LLM calls plus repair), `bridge` (cause-in-fact facts feeding the
legal-relevance layer), `build` (record -> frameworks -> `CaseSpec`),
`validate` (checks and the solver-vs-court table), `pipeline` (orchestration)
and `cli`.

Importing this package pulls in nothing heavier than pydantic; the Gemini SDK
is imported lazily inside `formalize.gemini`, so `formalize.build` can be used
from `aspic.catalog` without an API key or a network dependency.
"""
from .schema import SCHEMA_VERSION, FormalizedCase

__all__ = ["SCHEMA_VERSION", "FormalizedCase"]
