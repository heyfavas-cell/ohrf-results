# Open Horizon Research Foundry: results

Pre-registered, verified tests of quantum compilers. Each rule is fixed before the run, every compiler output is checked with an equivalence checker, and every outcome is published, including the ones where nothing wins.

| # | Study | Outcome | Record |
|---|---|---|---|
| 1 | Reordering existing passes against GUOQ on 145 fresh QAOA circuits | **Null**: the search did not beat GUOQ | [record](reports/2026-10-30-qaoa-explore.md) |
| 2 | Audit of Qiskit, pytket and PyZX for wrong outputs | **Fallback**: 172 differences found, none a new wrong output | [record](reports/2026-10-28-audit-spike.md) |
| 3 | Automated bug-triage test on the audit's findings | **Fail** under its own rule: the reports were not graded as registered | [record](reports/2026-11-02-model-triage.md) |

Check every result yourself with `python check_results.py` (Python 3 only). Cite: https://doi.org/10.5281/zenodo.23906909

## Result 1: reordering existing passes did not beat GUOQ on QAOA circuits

**Null.** A budgeted search over the existing passes of Qiskit 2.5.2, pytket 2.18.4 and PyZX 0.10.7 did not beat GUOQ on 145 fresh QAOA MaxCut circuits of 6 to 22 qubits. The rule was fixed in advance and applied once.

| Test | CNOT ratio, candidate over GUOQ | 95% interval | Passes? |
|---|---|---|---|
| Quality: candidate at 300 s against GUOQ at 300 s | 1.0324 | 1.0213 to 1.0428 | No |
| Time: candidate at 15 s against GUOQ at 300 s | 1.0502 | 1.0403 to 1.0596 | No |

A ratio above 1 means the candidate kept more CNOT gates. The whole interval sits on the losing side. GUOQ was `wisq` 0.2.7 at commit `97c12a5`, run 2026-10-29 to 2026-10-30. This result covers this pool of passes, this circuit family, these sizes and this GUOQ version only.

## Result 2: the audit found no new wrong output

**Fallback.** 1,472 fresh cases of 6 to 22 qubits went through Qiskit, pytket and PyZX in 4 configurations: 5,888 outputs in 30.01 of 30 compute hours. QCEC witnessed 172 differences, all from Qiskit. 170 duplicate the known issues Qiskit/qiskit#16864 and #17315, and the other 2 are within tolerance, so by the pre-registered rule none counts as a new wrong output and nothing was filed. Qiskit's maintainers treat the #16864 removals as within tolerance by design.

## Result 3: the automated bug-triage test failed on its own rule

**Fail.** Two model families each judged 29 audit cases, including 5 planted faults, as a known issue or a new one, and drafted a bug report for each. The rule required the founder to grade every report blind; the founder graded none, so the test is a Fail whatever the numbers. Reported beside the outcome: one family named the right issue on 29 of 29 cases with all 5 planted faults, the other on 24 of 29, because 5 of its calls ended with no reply. The record lists every departure from the plan.

## Check it yourself

```
python check_results.py
```

It recomputes every figure in result 1's table from `data/qaoa/results.csv` and applies its rule, applies the audit's rule to `data/audit/ledger.jsonl`, and checks the circuits, the frozen configuration and every file's hash.

| Folder | What it holds |
|---|---|
| `preregistrations/` | Each plan exactly as tagged before its run, and result 1's search frozen before any held-out circuit ran. See `TAGS.md` |
| `reports/` | The three records, and the timestamp proofs in `qaoa-explore-anchors/` and `p0d-anchors/` |
| `data/qaoa/` | Result 1: one row per circuit (`results.csv`), every observation, the run ledger, the 145 input circuits and GUOQ's output circuits |
| `data/audit/` | Result 2: one row per witnessed difference, with the flags the rule reads (`ledger.jsonl`) |
| `code/` | The code that ran results 1 and 2, with its tests |

## How to cite

All versions: https://doi.org/10.5281/zenodo.23906909. Release v1.0 (result 1): https://doi.org/10.5281/zenodo.23906910. Release v2.0 (results 2 and 3): https://doi.org/10.5281/zenodo.23909578. GitHub's "Cite this repository" button gives the same from `CITATION.cff`.

## What you cannot check here

- **The pre-registration dates rest partly on our word.** The tags were made in a private repository. The timestamp proofs show that each stamped text existed by a date, and that text names a commit you cannot see. Result 1's frozen search configuration is checkable, because its hash is inside a stamped text. The audit's tags have no timestamp proof at all.
- **Result 1's candidate circuits are not here.** The data holds their counts and verification results. Re-run `code/` to regenerate them; the search is seeded, but timed budgets can change what it reaches.
- **Result 3's cases, reports, planted faults and grades are not here.** They stay private, and the record gives the hashes of the files it read. Its code is not published either.
- **Deviations happened in every study.** Each record lists them.
- **Nobody outside the lab has reviewed this yet.** Corrections are welcome through an issue.

## Changes for publication

The records and the pre-registrations are unchanged. Paths in the records that start with `spikes/` are under `code/` here, and the audit ledger is at `data/audit/ledger.jsonl`. In `data/qaoa/`, the observations drop one local file-path field, and `runs.csv` leaves out the free-text note rows, whose content is in the record's deviations. Decision ids such as `D-089` and `OD-BI` refer to the lab's private log; each one that matters is explained where it is cited.

## Licence

Code: Apache-2.0 (`LICENSE`). Data and reports: CC-BY-4.0 (`LICENSE-DATA`).

The founder directed this work, used software tools including AI coding assistants, and is responsible for every result.
