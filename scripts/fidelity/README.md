# Fidelity harnesses

Preserved from the 2026-09-13 scratchpad session. Run from the solver
repository with Python 3.11+ (no additional dependencies):

```sh
python scripts/fidelity/run_oracles.py
python scripts/fidelity/run_fuzz.py
python scripts/fidelity/run_fuzz_completed.py
python scripts/fidelity/run_sweep.py
```

Imports resolve relative to the scripts, so these commands also work from
another directory using absolute script paths. The sweep uses
`cases.workspace.workspace_root()` to locate `data/translated/`, including
the `JURIX_WORKSPACE` override. Without translated records it only sweeps
the 11 built-in frameworks; the recorded run includes two translated ones.

`refclone.py` ports the causal operations of the authors' `CausalitySolver.kt`
from tuProlog/arg2p-kt. It shares our parser, argument construction and
grounded extension engine: this is a differential check of causal semantics,
not an independent reimplementation of the entire argumentation engine.
`completed.py` preserves the diagnostic argument-fixpoint implementation;
after the production fix, both fuzz runners give the same results.

The generator uses `random.Random(20260913)` and 366 theories. Outputs
reexecuted after the construction fix are in `results/20260913/`:

| Check | Result |
| --- | --- |
| Reference clone oracles | 40/40 NESS and intervention; 5/5 but-for |
| Our NESS against reference oracles | 15/18; all three differences are joint interventions (D3) |
| Full comparison, 16,504 pairs | 155 ours=True/reference=False; 53 reverse |
| Singleton comparison | 235 differences: 210 D1, 25 D2; none unclassified |
| Theories with different supports | 8/366 |
| Current cases, 13 frameworks | Zero differences; zero construction truncation effects |

D1 is the reference's requirement for an IN attacker; D2 is its broader
support traversal; D3 is its joint intervention generation. D3 contributes
83 pairs in the full comparison, overlapping the other categories; do not
add that count to the directional totals.

These runners print diagnostics. The oracle runner exits nonzero if the
reference clone misses an oracle; fuzz and sweep results require inspecting
the output. Intentional semantic differences are not test failures.
The historical pre-fix construction bug is protected by
`tests/test_argument_construction.py`; the fixed solver no longer reproduces
the three spurious pre-fix NESS verdicts.
