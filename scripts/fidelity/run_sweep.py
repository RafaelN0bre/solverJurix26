"""Compares causal verdicts over built-in and translated catalog cases.
Consumes executable frameworks and reports differences and construction effects.
"""

"""Deterministic sweep of all CURRENT repository frameworks, comparing
our ness_cause against full reference ness/3 for every literal phi and the
case's effect. Also checks published verdicts (declared queries) on both
sides and detects construction truncation from the former early break.
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

import json, logging
logging.disable(logging.INFO)

from aspic.solver import ArgumentationFramework, negate_literal
from completed import CompletedFramework
from refclone import ReferenceSolver, OursEval
from cases.examples import LEGAL_CASES
from cases.workspace import workspace_root

ROOT = workspace_root()


def literals_of(kb, model):
    atoms, rule_ids = set(), set()
    for r in model["defeasible_rules"] + model.get("strict_rules", []):
        rid = r.split(":")[0].strip()
        rule_ids.add(rid)
        body = r.split(":", 1)[1]
        parts = body.replace("->", "=>").split("=>")
        toks = [t.strip() for t in parts[0].split("AND")] + [parts[1].strip()]
        for t in toks:
            base = t[1:] if t.startswith("¬") else t
            atoms.add(base)
    for lit in kb["premises"] + kb.get("axioms", []):
        atoms.add(lit[1:] if lit.startswith("¬") else lit)
    atoms -= rule_ids
    return sorted(atoms), sorted(rule_ids)


def sweep_case(name, kb, model, effect, queries, preferences=None):
    af = ArgumentationFramework(kb, model, preferences=preferences)
    caf = CompletedFramework(kb, model, preferences=preferences)
    base_trunc = ({a.signature for a in caf.arguments.values()} !=
                  {a.signature for a in af.arguments.values()})

    ours, ref = OursEval(af), ReferenceSolver.from_framework(af)
    ours_c, ref_c = OursEval(caf), ReferenceSolver.from_framework(caf)

    atoms, rule_ids = literals_of(kb, model)
    phis = [l for a in atoms for l in (a, "¬" + a)] + rule_ids
    divs, trunc_flags = [], []
    for phi in phis:
        if phi == effect:
            continue
        o = ours.ness_cause(phi, effect)
        r, wit = ref.ness(phi, effect)
        oc = ours_c.ness_cause(phi, effect)
        rc, _ = ref_c.ness(phi, effect)
        if o != r:
            # Classify the difference.
            supp_d = ours.support_signatures(effect) != ref.base_supports(effect)
            r1 = ref.ness_singleton(phi, effect)
            if r and not r1:
                cls = "D3 (conjunta)"
            elif supp_d:
                cls = "D2 (Supp)"
            elif o == ref.check_causality_relaxed([negate_literal(phi)], effect):
                cls = "D1 (IN)"
            else:
                cls = "OUTRA"
            divs.append((phi, o, r, cls))
        if (o, r) != (oc, rc):
            trunc_flags.append((phi, (o, r), (oc, rc)))

    n = len(phis)
    status = f"{len(divs)} DIVs" if divs else "NO DIFFERENCE"
    print(f"===== {name:34s} {status}   ({n} literais)"
          + ("   [TRUNCAMENTO na construção-base!]" if base_trunc else ""))
    for phi, o, r, cls in divs:
        print(f"        ness({phi},{effect}): ours={o} ref={r}  -> {cls}")
    for phi, before, after in trunc_flags:
        print(f"        [truncamento muda par] ness({phi},{effect}): "
              f"as-is(ours,ref)={before} completado={after}")

    pub = []
    for q in queries:
        o = ours.ness_cause(q["phi"], q["psi"])
        r, _ = ref.ness(q["phi"], q["psi"])
        exp = q.get("expect_ness")
        ok = "OK " if (exp is None or (o == exp and r == exp)) else "XX "
        agree = "==" if o == r else "!="
        pub.append(f"        {ok}ness({q['phi']},{q['psi']}) ours={o} {agree} ref={r}"
                   + (f"  esperado={exp}" if exp is not None else ""))
    if pub:
        print("\n".join(pub))
    return len(divs), len(trunc_flags)


total_divs = total_trunc = 0
for spec in LEGAL_CASES:
    qs = [{"phi": q.phi, "psi": q.psi, "expect_ness": q.expect_ness}
          for q in spec.queries]
    d, tr = sweep_case(f"examples::{spec.id}", spec.knowledge_base,
                       spec.causal_model, spec.effect, qs, spec.preferences)
    total_divs += d; total_trunc += tr

for case_file in sorted((ROOT / "data/translated").glob("*/case.json")):
    doc = json.loads(case_file.read_text())
    qs = [{"phi": q["phi"], "psi": q["psi"], "expect_ness": q.get("expect_ness")}
          for q in doc.get("queries", [])]
    d, tr = sweep_case(f"translated::{case_file.parent.name}",
                       doc["knowledge_base"], doc["causal_model"],
                       doc["effect"], qs)
    total_divs += d; total_trunc += tr

print(f"\nTOTAL pares (phi,psi) divergentes na varredura: {total_divs}")
print(f"TOTAL pares afetados por truncamento de construção: {total_trunc}")
