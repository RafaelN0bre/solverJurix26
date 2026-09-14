"""Runs seeded differential fuzzing with the diagnostic completed framework.
Consumes `completed`, `refclone` and the generator in `run_fuzz`.
"""

"""Runs the same fuzzing as run_fuzz.py with completed construction on both
sides. Expected: no OTHER cases; only D1/D2/D3 remain."""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

import logging, random
from collections import Counter
logging.disable(logging.INFO)
from aspic.solver import negate_literal
from completed import CompletedFramework
from refclone import ReferenceSolver, OursEval
from run_fuzz import random_theory, SEED, N_THEORIES

rng = random.Random(SEED)
pairs = full_T = full_F = iso_div = d3 = 0
iso_dir, iso_class = Counter(), Counter()
supp_div_theories = 0
for t in range(N_THEORIES):
    premises, rules, atoms, rule_ids = random_theory(rng)
    af = CompletedFramework({"premises": premises, "axioms": []},
                            {"strict_rules": [], "defeasible_rules": rules})
    ref = ReferenceSolver.from_framework(af)
    ours = OursEval(af)
    concluded = {a.conclusion for a in af.arguments.values()}
    effects = [lit for a in atoms for lit in (a, "¬" + a) if lit in concluded]
    causes = [lit for a in atoms for lit in (a, "¬" + a)] + rule_ids
    supp_div = False
    for psi in effects:
        our_supp = ours.support_signatures(psi)
        ref_supp = ref.base_supports(psi)
        if our_supp != ref_supp:
            supp_div = True
        for phi in causes:
            if phi == psi: continue
            pairs += 1
            o = ours.ness_cause(phi, psi)
            r1 = ref.ness_singleton(phi, psi)
            rF, _ = ref.ness(phi, psi)
            if o and not rF: full_T += 1
            elif rF and not o: full_F += 1
            if rF and not r1: d3 += 1
            if o != r1:
                iso_div += 1
                iso_dir["ours=T/ref=F" if o else "ours=F/ref=T"] += 1
                if our_supp != ref_supp:
                    iso_class["D2 (Supp difere)"] += 1
                elif o == ref.check_causality_relaxed([negate_literal(phi)], psi):
                    iso_class["D1 (exigência de atacante IN)"] += 1
                else:
                    iso_class["OUTRA (não explicada!)"] += 1
    if supp_div: supp_div_theories += 1

print(f"teorias: {N_THEORIES}  pares: {pairs}")
print(f"[plena] nosso=T/ref=F: {full_T}   nosso=F/ref=T: {full_F}   (D3: {d3})")
print(f"[isolada] divergentes: {iso_div}  {dict(iso_dir)}")
for k, v in iso_class.most_common(): print(f"    {k}: {v}")
print(f"teorias com Supp divergente (D2): {supp_div_theories}")
