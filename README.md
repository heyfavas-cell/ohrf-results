# Open Horizon Research Foundry: results

Open Horizon Research Foundry is a small independent lab. It tests quantum compilers on fresh circuits, fixes the rule before each run, checks every output with an equivalence checker, and publishes the result even when nothing wins.

## Result 1: reordering existing passes did not beat GUOQ on QAOA circuits

**Null.** A budgeted search over the existing passes of Qiskit 2.5.2, pytket 2.18.4 and PyZX 0.10.7 did not beat GUOQ on 145 fresh QAOA MaxCut circuits of 6 to 22 qubits. The rule was fixed in advance and applied once.

| Test | CNOT ratio, candidate over GUOQ | 95% interval | Passes? |
|---|---|---|---|
| Quality: candidate at 300 s against GUOQ at 300 s | 1.0324 | 1.0213 to 1.0428 | No |
| Time: candidate at 15 s against GUOQ at 300 s | 1.0502 | 1.0403 to 1.0596 | No |

A ratio above 1 means the candidate kept more CNOT gates. The whole interval sits on the losing side. GUOQ was `wisq` 0.2.7 at commit `97c12a5`, run 2026-10-29 to 2026-10-30. This result covers this pool of passes, this circuit family, these sizes and this GUOQ version only.

**Read next:** [the full record](reports/2026-10-30-qaoa-explore.md), with every number, cost and deviation.

## Check it yourself

```
python check_results.py
```

It needs Python 3 only. It recomputes every figure in the table from `data/qaoa/results.csv`, applies the rule, and checks the circuits, the frozen configuration and every file's hash.

| Folder | What it holds |
|---|---|
| `preregistrations/` | The plan exactly as tagged before the run, and the search frozen before any held-out circuit ran. See `TAGS.md` |
| `reports/` | The record, and the timestamp proofs in `qaoa-explore-anchors/` |
| `data/qaoa/` | One row per circuit (`results.csv`), every observation, the run ledger, the 145 input circuits and GUOQ's output circuits |
| `code/` | The code that ran the study, with its tests |

## What you cannot check here

- **The pre-registration date rests partly on our word.** The tags were made in a private repository. The timestamp proofs show that each stamped text existed by a date, and that text names a commit you cannot see. The frozen search configuration is checkable: its hash is inside the stamped text. The plan's link to its commit is not.
- **The candidate's output circuits are not here.** The published data holds their counts and verification results, not the circuits. Re-run `code/` to regenerate them; the search is seeded, but timed budgets can change what it reaches.
- **Deviations happened.** The record lists them, including a third attempt and a lowered memory margin on the last block. The founder decided those after seeing that the candidate was behind in earlier blocks and before the rule was applied.
- **The size pattern in the record is not a claim.** It was found after the rule was applied.
- **Nobody outside the lab has reviewed this yet.** Corrections are welcome through an issue.

## Changes for publication

The record and the pre-registration are unchanged. In `data/qaoa/`, the observations drop one local file-path field, and `runs.csv` leaves out the free-text note rows, whose content is in the record's deviations. Decision ids such as `D-089` and `OD-BI` refer to the lab's private log; each one that matters is explained where it is cited.

## How this was made

AI models did much of the coding, running and analysis, under the founder's direction. The founder set the questions, took the decisions listed in the record, and is responsible for what is published here.

## Licence

Code: Apache-2.0 (`LICENSE`). Data and reports: CC-BY-4.0 (`LICENSE-DATA`).
