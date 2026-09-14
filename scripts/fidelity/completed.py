"""Provides a diagnostic argument-fixpoint framework for fidelity runners.
It supplies the completed construction used in fuzzing and case sweeps.
"""

"""ArgumentationFramework with construction to an argument fixpoint.

The former conclusion-stability break truncated construction according to
rule order. This diagnostic implementation removes that break, and its
axiom expansions retain the diagnostic subclass. After the production fix,
it agrees with the normal framework. It shares the production acyclicity
guard; it is a construction diagnostic, not an independent solver.
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

import logging
logging.disable(logging.INFO)
from aspic.solver import ArgumentationFramework, Argument


class CompletedFramework(ArgumentationFramework):
    def _construct_arguments(self):
        for i, literal in enumerate(sorted({*self.premises, *self.axioms},
                                           key=lambda l: l.name)):
            is_axiom = literal in self.axioms
            sig = (frozenset([literal.name]), literal.name, tuple(), tuple())
            if sig in self._argument_signatures:
                continue
            arg_id = f"A{i}"
            self.arguments[arg_id] = Argument(
                id=arg_id, conclusion=literal.name,
                ordinary_premises=frozenset() if is_axiom else frozenset([literal.name]),
                axiom_premises=frozenset([literal.name]) if is_axiom else frozenset(),
                strict_rules=[], defeasible_rules=[])
            self._argument_signatures.add(sig)

        changed, it = True, 0
        while changed and it < 1000:
            it += 1
            changed = False
            for rule in list(self.rules.values()):
                if self._apply_rule(rule):
                    changed = True

    def axiom_expand(self, new_axioms):
        expanded_kb = {
            "premises": list(self._kb_raw["premises"]),
            "axioms": list(dict.fromkeys([*self._kb_raw["axioms"], *new_axioms])),
        }
        return CompletedFramework(expanded_kb, self._model_raw,
                                  preferences=self.preferences)
