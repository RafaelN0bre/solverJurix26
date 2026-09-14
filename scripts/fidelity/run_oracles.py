"""Checks reference causal operations against the published test oracles.
Consumes `refclone` and prints clone validation and expected solver differences.
"""

"""Validates the reference clone against 40 BasicTest.kt oracles
(22 isNessIntervention and 18 isNessCause, ICAIL 2025), plus 5 but_for oracles.

Ported notation: `-x` -> `¬x`; `f :=> a` / `r :=> a` -> premise `a`;
`r0 : [] => c` -> always-present premise `T` plus rule `r0: T => c`;
`undercut(r2)` -> `¬r2` (compl(r2) is already undercutting in our grammar).

Also runs the 18 isNessCause oracles against OUR ness_cause: expected 15/18,
with exactly three differences, all joint-intervention oracles (D3).
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

import logging

logging.disable(logging.INFO)

from refclone import ReferenceSolver, OursEval

THEORIES = {
    "theory1": (["a", "b"], ["r1: a => c", "r2: a AND b => c"]),
    "theory2": (["a", "b", "T"],
                ["r0: T => c", "r1: ¬a => ¬r0", "r2: ¬a AND ¬b => ¬r0"]),
    "complex": (["a"], ["tx2: d AND e => ¬r2", "r2: a => ¬b"]),
    "causalityTest": (["a"], ["tx2: d => ¬r2", "r2: a => ¬b"]),
    "asbestos": (["ex_1", "ex_2", "ex_3"],
                 ["r_0: ca => di", "r_1: ex_1 AND ex_2 => ca",
                  "r_2: ex_2 AND ex_3 => ca", "r_3: ex_1 AND ex_3 => ca"]),
    "tobacco": (["ge_di"], ["r_0: ge_di => lu_ca", "r_1: ge_di => sm_to"]),
    "doubleShooting": (["bu_sh", "dl_sh"],
                       ["r_0: bu_sh => bu_ki", "r_1: dl_sh => du_ki",
                        "r_2: bu_ki => ge_di", "r_3: du_ki => ge_di",
                        "r_4: bu_ki => ¬r_1"]),
    "leukaemia": (["ch_le", "¬pa_co"],
                  ["r_0: ch_le => ch_di", "r_1: pa_co => chem",
                   "r_2: chem => ¬r_0"]),
    "brakes": (["br_ma", "¬dr_pu"],
               ["r_0: ¬dr_pu => ac_ha", "r_1: br_ma => br_fa",
                "r_2: br_fa => ac_ha", "r_3: ¬dr_pu => ¬r_1"]),
    "soldiers_shoots": (["so_sh"],
                        ["r_0: so_sh => pr_di", "r_1: se_sh => pr_di",
                         "r_2: ¬so_sh => se_sh"]),
    "soldiers_refuses": (["¬so_sh"],
                         ["r_0: so_sh => pr_di", "r_1: se_sh => pr_di",
                          "r_2: ¬so_sh => se_sh"]),
}

# (theory, intervention, effect, expected) -- isNessIntervention / ness_intervention
INTERVENTION_ORACLES = [
    ("complex", ["d"], "¬b", False),
    ("complex", ["d", "e"], "¬b", True),
    ("complex", ["d", "e", "c"], "¬b", False),
    ("causalityTest", ["¬a"], "¬b", True),
    ("causalityTest", ["¬b"], "a", False),
    ("causalityTest", ["¬d"], "¬b", False),
    ("causalityTest", ["d"], "¬b", True),
    ("asbestos", ["¬ex_1"], "di", True),
    ("asbestos", ["¬ex_2"], "di", True),
    ("asbestos", ["¬ex_3"], "di", True),
    ("tobacco", ["¬sm_to"], "lu_ca", False),
    ("tobacco", ["¬ge_di"], "lu_ca", True),
    ("doubleShooting", ["¬bu_sh"], "ge_di", True),
    ("doubleShooting", ["¬dl_sh"], "ge_di", False),
    ("leukaemia", ["¬ch_le"], "ch_di", True),
    ("leukaemia", ["pa_co"], "ch_di", True),
    ("brakes", ["dr_pu"], "ac_ha", True),
    ("brakes", ["¬br_ma"], "ac_ha", False),
    ("soldiers_shoots", ["¬so_sh"], "pr_di", True),
    ("soldiers_shoots", ["¬se_sh"], "pr_di", False),
    ("soldiers_refuses", ["so_sh"], "pr_di", True),
    ("soldiers_refuses", ["¬se_sh"], "pr_di", True),
]

# (theory, cause, effect, expected) -- isNessCause / ness/3
NESS_ORACLES = [
    ("theory1", "a", "c", True),
    ("theory1", "b", "c", True),
    ("theory2", "a", "c", True),
    ("theory2", "b", "c", True),          # Requires a joint intervention (family c).
    ("complex", "¬d", "¬b", True),        # Same joint-intervention requirement.
    ("complex", "b", "a", False),
    ("complex", "d", "¬b", False),
    ("complex", "¬e", "¬b", True),        # Same joint-intervention requirement.
    ("complex", "a", "¬b", True),
    ("complex", "r2", "¬b", True),        # Family (b) == (a) in our notation.
    ("causalityTest", "a", "¬b", True),
    ("causalityTest", "b", "a", False),
    ("causalityTest", "d", "¬b", False),
    ("causalityTest", "¬d", "¬b", True),
    ("asbestos", "ex_1", "di", True),
    ("asbestos", "ex_2", "di", True),
    ("asbestos", "ex_3", "di", True),
    ("tobacco", "ge_di", "lu_ca", True),
]

JOINT_ONLY = {("theory2", "b", "c"), ("complex", "¬d", "¬b"), ("complex", "¬e", "¬b")}

BUTFOR_ORACLES = [
    ("theory1", "a", "c", True),
    ("theory1", "b", "c", False),
    ("asbestos", "ex_1", "di", False),
    ("asbestos", "ex_2", "di", False),
    ("asbestos", "ex_3", "di", False),
]


def main():
    solvers = {name: ReferenceSolver(p, r) for name, (p, r) in THEORIES.items()}
    ours = {name: OursEval(solvers[name].base_af) for name in THEORIES}

    ok = bad = 0
    print("== clone x oráculos: ness_intervention (22) ==")
    for th, iv, eff, exp in INTERVENTION_ORACLES:
        got = solvers[th].check_causality_icail25(iv, eff)
        mark = "OK" if got == exp else "XX"
        ok, bad = (ok + 1, bad) if got == exp else (ok, bad + 1)
        if mark == "XX":
            print(f"  {mark} {th}: intervention({iv}, {eff}) = {got}, esperado {exp}")
    print(f"  {ok} ok, {bad} falhas")

    ok2 = bad2 = 0
    print("== clone x oráculos: ness/3 (18) ==")
    for th, cause, eff, exp in NESS_ORACLES:
        got, witness = solvers[th].ness(cause, eff)
        mark = "OK" if got == exp else "XX"
        ok2, bad2 = (ok2 + 1, bad2) if got == exp else (ok2, bad2 + 1)
        if mark == "XX":
            print(f"  {mark} {th}: ness({cause}, {eff}) = {got}, esperado {exp}")
    print(f"  {ok2} ok, {bad2} falhas")

    ok3 = bad3 = 0
    print("== clone x oráculos: but_for (5) ==")
    for th, cause, eff, exp in BUTFOR_ORACLES:
        got = solvers[th].but_for(cause, eff)
        ok3, bad3 = (ok3 + 1, bad3) if got == exp else (ok3, bad3 + 1)
        if got != exp:
            print(f"  XX {th}: but_for({cause}, {eff}) = {got}, esperado {exp}")
    print(f"  {ok3} ok, {bad3} falhas")

    print("== NOSSO ness_cause x os mesmos 18 oráculos ==")
    ok4 = 0
    fails = []
    for th, cause, eff, exp in NESS_ORACLES:
        got = ours[th].ness_cause(cause, eff)
        if got == exp:
            ok4 += 1
        else:
            fails.append((th, cause, eff))
            joint = "conjunta (D3, esperada)" if (th, cause, eff) in JOINT_ONLY \
                else "INESPERADA"
            print(f"  XX {th}: ness_cause({cause}, {eff}) = {got}, "
                  f"esperado {exp} -- {joint}")
    print(f"  {ok4}/18 ok; falhas: {len(fails)} "
          f"({'todas' if set(fails) == JOINT_ONLY else 'NEM TODAS'} são os "
          f"oráculos de intervenção conjunta)")

    total_ref = ok + ok2
    print(f"\nRESULTADO: clone reproduz {total_ref}/40 oráculos ICAIL25 "
          f"(+{ok3}/5 but_for)")
    return 0 if (bad == bad2 == bad3 == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
