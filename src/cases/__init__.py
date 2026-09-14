"""Package of case sources: the hardcoded paper examples, the unified
catalog, and workspace resolution. Everything that asks "which cases exist?"
-- tests, figure scripts, the interface -- loads them from here.
"""

"""The cases: executable specifications, the unified catalog, and where the
shared data lives.

Three modules, three provenances of a case:

* `examples` -- the eleven case theories of the ICAIL 2025/2026 papers,
  hardcoded as `CaseSpec`s; the single source both the test suite and the
  figure generator consume;
* `catalog` -- the unified catalog behind the interface: the hardcoded
  examples plus the cases formalized from annotated dossiers
  (`data/translated/`, laid out by `formalize.store`);
* `workspace` -- resolution of the workspace root, so `docs/` and `data/`
  (shared with the annotator project) are found one level above the repo.
"""
from .examples import CaseSpec, CausalQuery, LRCLayer, LEGAL_CASES, case_by_id

__all__ = ["CaseSpec", "CausalQuery", "LRCLayer", "LEGAL_CASES", "case_by_id"]
