"""Generates seeded theories and compares our causal verdicts with `refclone`.
Reports directional differences and their semantic classifications.
"""

"""Differential fuzzing: our ness_cause versus the reference clone on 366
random acyclic theories (random atoms, defeasible rules and knowledge bases;
fixed seed 20260913).

The original audit fuzz seed was not preserved, so its absolute counts
(115/58, 151/145) cannot be reproduced bit for bit. This harness checks the
phenomenon and its explanation:

1. Directional full comparison: our singleton versus reference ness/3.
2. Isolated singleton comparison, classifying each difference as D1
   (IN-attacker requirement), D2 (getSupports breadth), or other (expected: zero).
3. Count of theories where Supp itself differs (D2).
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

import logging
import random
from collections import Counter

logging.disable(logging.INFO)

from aspic.solver import negate_literal
from refclone import ReferenceSolver, OursEval

SEED = 20260913
N_THEORIES = 366


def random_theory(rng):
    n_atoms = rng.randint(3, 6)
    atoms = list("abcdef"[:n_atoms])
    n_rules = rng.randint(2, 6)
    rules = []
    for i in range(n_rules):
        rid = f"r{i}"
        prior = [f"r{j}" for j in range(i)]
        if prior and rng.random() < 0.2:
            cons = "¬" + rng.choice(prior)
            pool = atoms
        else:
            tgt = rng.randint(1, n_atoms - 1)
            cons = ("¬" if rng.random() < 0.4 else "") + atoms[tgt]
            pool = atoms[:tgt]
        k = rng.randint(1, min(2, len(pool)))
        ants = [("¬" if rng.random() < 0.35 else "") + a
                for a in rng.sample(pool, k)]
        rules.append(f"{rid}: {' AND '.join(ants)} => {cons}")

    premises = []
    for a in atoms:
        roll = rng.random()
        if roll < 0.45:
            premises.append(a)
        elif roll < 0.70:
            premises.append("¬" + a)
    if not premises:
        premises.append(atoms[0])
    return premises, rules, atoms, [f"r{j}" for j in range(n_rules)]


def main():
    rng = random.Random(SEED)
    pairs = 0
    full_ours_T = full_ours_F = 0          # ours=T/ref=F and the reverse (full comparison)
    iso_div = 0
    iso_direction = Counter()
    iso_class = Counter()
    supp_div_theories = 0
    d3_pairs = 0                            # Full reference=True only through a joint intervention.
    example_d1 = None

    for t in range(N_THEORIES):
        premises, rules, atoms, rule_ids = random_theory(rng)
        try:
            ref = ReferenceSolver(premises, rules)
        except Exception as e:
            print(f"  teoria {t} descartada: {e}")
            continue
        ours = OursEval(ref.base_af)

        concluded = {a.conclusion for a in ref.base_af.arguments.values()}
        effects = [lit for a in atoms for lit in (a, "¬" + a) if lit in concluded]
        causes = [lit for a in atoms for lit in (a, "¬" + a)] + rule_ids

        theory_supp_div = False
        for psi in effects:
            our_supp = ours.support_signatures(psi)
            ref_supp = ref.base_supports(psi)
            if our_supp != ref_supp:
                theory_supp_div = True
            for phi in causes:
                if phi == psi:
                    continue
                pairs += 1
                o = ours.ness_cause(phi, psi)
                r_single = ref.ness_singleton(phi, psi)
                r_full, _ = ref.ness(phi, psi)

                if o and not r_full:
                    full_ours_T += 1
                elif r_full and not o:
                    full_ours_F += 1

                if r_full and not r_single:
                    d3_pairs += 1

                if o != r_single:
                    iso_div += 1
                    iso_direction["ours=T/ref=F" if o else "ours=F/ref=T"] += 1
                    if our_supp != ref_supp:
                        iso_class["D2 (Supp difere)"] += 1
                    elif o == ref.check_causality_relaxed(
                            [negate_literal(phi)], psi):
                        iso_class["D1 (exigência de atacante IN)"] += 1
                        if example_d1 is None and o:
                            example_d1 = (premises, rules, phi, psi)
                    else:
                        iso_class["OUTRA (não explicada!)"] += 1
        if theory_supp_div:
            supp_div_theories += 1

    print(f"teorias: {N_THEORIES}  pares (phi,psi): {pairs}")
    print(f"\n[plena]  nosso x ness/3 completo da referência:")
    print(f"  nosso=T / ref=F : {full_ours_T}")
    print(f"  nosso=F / ref=T : {full_ours_F}")
    print(f"  (pares em que só a intervenção conjunta da referência "
          f"dá causa -- lacuna D3 nossa: {d3_pairs})")
    print(f"\n[isolada]  singleton dos dois lados:")
    print(f"  divergentes: {iso_div}  ({dict(iso_direction)})")
    for k, v in iso_class.most_common():
        print(f"    {k}: {v}")
    print(f"\nteorias em que Supp(psi) difere (D2): {supp_div_theories} de {N_THEORIES}")
    if example_d1:
        p, r, phi, psi = example_d1
        print(f"\nexemplo D1 -- Kp={p}; regras={r}; ness({phi},{psi}): "
              f"nosso=True, referência=False")
    return 0


if __name__ == "__main__":
    sys.exit(main())
