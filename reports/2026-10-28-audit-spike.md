# Toolchain audit spike, 2026-10-14 to 2026-10-28

The spike of `docs/plans/P0b-audit-spike.md` was run under the rule fixed by the tag `audit-prereg` (commit `beb8897`), with the QCEC 3.11.0 re-check pre-declared under the tag `audit-addendum` (commit `b7717e6`, D-145 addendum). This file records the verdict, the numbers behind it, every finding, what it cost that triage stalled, and everything that differs from the tagged plan. Decision: D-155.

## Verdict

**Fallback.** The pre-registered rule gives it, and nothing here changes the rule.

```
ledger.verdict(findings, day0=date(2026, 10, 14), today=date(2026, 10, 28)) -> fallback
```

The ledger is `spikes/qopt_audit/findings/ledger.jsonl`: one row for every case whose triage found a witnessed difference (172), each with its true flags, so `ledger.verdict` alone applies the exclusions. Re-run it from the repo root with:

```
python -c "import json; from datetime import date; from spikes.qopt_audit.ledger import Finding, verdict; f = [Finding(**json.loads(l)) for l in open('spikes/qopt_audit/findings/ledger.jsonl')]; print(verdict(f, day0=date(2026, 10, 14), today=date(2026, 10, 28)))"
```

| Rows | Evidence conditions not met |
|---|---|
| 157 | duplicate of Qiskit/qiskit#16864 |
| 10 | within tolerance; does not reproduce on Qiskit 2.6.1; duplicate of #16864 |
| 1 | duplicate of Qiskit/qiskit#17315 (`boundary:qaoa-22:254:qiskit`) |
| 1 | within tolerance; does not reproduce on 2.6.1; duplicate of #17315 (`boundary:qaoa-14:452:qiskit`) |
| 1 | within tolerance; duplicate of #16864 |
| 1 | within tolerance (`random:random:680:qiskit`, no duplicate) |
| 1 | not proved twice; second opinion fails; within tolerance (`random:random:119:qiskit`, no duplicate) |
| **0** | **counts as a wrong output** |

| Flag (of 172 rows) | True |
|---|---|
| `proved_twice` | 171 |
| `second_opinion_ok` | 171 |
| `tolerance_ok` | 158 |
| `reproduces_latest` | 161 |
| `duplicate_of` set | 170 (168 #16864, 2 #17315) |
| counts as a wrong output | 0 |
| of those, at most 50 gates | 0 |
| filed | 0 |

- **Rule (i)**, one new wrong output meeting evidence conditions 2 to 5 with a reproducer of at most 50 gates: not met.
- **Rule (ii)**, two wrong-output issues filed by day 10 (2026-10-24) and accepted by day 14: nothing was filed. After the stall below, (ii) could no longer be met.
- Triage of every candidate finished on 2026-10-28 at 03:41 and the ledger was built at 03:46, both inside day 14.

## The stall and what it cost

The spike stopped after batch 4 on 2026-10-19, with triage at 413 of 728 candidates, and resumed on 2026-10-27, eight days later. Batches 5 to 8 and the rest of triage all ran on 2026-10-27 and 2026-10-28.

**The stall cost the pass.** `boundary:qaoa-22:254:qiskit` was logged before 2026-10-19 17:34. Its reproducer is three gates on two qubits (`cu1(-20.8211) q0,q1; rz(10.4105) q0; rz(9.6e-05) q0`, D = 4.8e-05). It meets every evidence condition except the duplicate check: proved not equivalent twice, the second opinion agrees, D is above the frozen tolerance (3 × 1e-5), and it reproduces on Qiskit 2.6.1. Qiskit's `CommutativeCancellation` merges two large `rz` rotations and drops their small sum. Qiskit/qiskit#17315 ("CommutativeCancellation drops small rotations"), the same mechanism, was opened by another reporter on 2026-10-25 and labelled a bug; fix PR #17321 was opened on 2026-10-26. The lab triaged the case on 2026-10-27. Triaged and searched before 2026-10-25, it would have counted under (i), and the verdict would have been pass.

The rule counts a case whose search finds a duplicate as a duplicate, whatever delayed the search. The founder kept that ruling as written. The case was also missed by the automatic duplicate rule (its #16864 test needs every angle tiny, and this reduction keeps two large ones), so the mechanism was found by hand.

The stall also made rule (ii) impossible: no issue could be filed by day 10.

## The run

| Batch | Date | Cases | Wall-clock hours (cumulative) |
|---|---|---|---|
| calibration (discarded, hours counted) | 10-14 | | 0.44 (0.44) |
| 1 to 3 | 10-14 to 10-19 | 527 | 10.61 (11.05) |
| 4 | 10-19 13:29 to 17:34 | 215 | 4.08 (15.13) |
| 5 | 10-27 09:14 to 13:17 | 146 | 4.05 (19.19) |
| 6 | 10-27 13:17 to 17:26 | 218 | 4.15 (23.34) |
| 7 | 10-27 17:26 to 21:28 | 220 | 4.04 (27.37) |
| 8 | 10-27 21:28 to 10-28 00:07 | 146 | 2.64 (30.01) |

- 1,472 cases (736 random, 736 boundary-angle), 6 to 22 qubits, each through 4 tool configurations: 5,888 outputs.
- Compute: 30.01 of 30 wall-clock hours on 3 workers. The runner checks the budget only before starting a case, so cases in flight overrun each batch by up to about 9 minutes; in total the cap is exceeded by 30 seconds. Busy time across workers: 85.5 hours.
- Throughput: about 49 cases (196 outputs) per wall-clock hour. Verified outputs per busy hour: tket 69 to 70, Qiskit 56, PyZX 17. PyZX took 41% of the busy time for 25% of the outputs.

| Tool | Verified | Undecided | Oracle disagreement | Within tolerance | Wrong output |
|---|---|---|---|---|---|
| Qiskit | 1,008 | 430 | 20 | 13 | 1 |
| tket, swaps | 1,124 | 348 | 0 | 0 | 0 |
| tket, no swaps | 1,122 | 350 | 0 | 0 | 0 |
| PyZX | 585 | 887 | 0 | 0 | 0 |
| **Total** | **3,839** | **2,015** | **20** | **13** | **1** |

No crash in the final log. Batch 1 logged 92 PyZX reader crashes on scientific-notation angles (the known lead); those 92 outputs were run again after the decimal rewrite (change 6) and replaced in the log. The original batch 1 log is kept privately.

**How far the oracle sees.** Undecided share (QCEC `no_information` 1,257, hard-wall timeout 758):

| Qubits | Undecided, all tools | Decided: Qiskit | tket swaps / no swaps | PyZX |
|---|---|---|---|---|
| 6 to 10 | 15.7% of 2,192 | 89% | 92% / 93% | 63% |
| 11 to 14 | 44.0% of 1,292 | 61% | 68% / 68% | 27% |
| 15 to 18 | 46.2% of 1,404 | 59% | 68% / 66% | 22% |
| 19 to 22 | 45.5% of 1,000 | 60% | 64% / 65% | 29% |

Above 10 qubits nearly half the outputs rest on triage's witness check alone: one seeded random product state, which cannot rule out an error that shows only on other inputs.

## Findings

Every witnessed wrong output is one Qiskit behaviour: a small rotation dropped at optimization level 3. It reaches the output through two passes.

| Mechanism | Rows | Issue |
|---|---|---|
| `TwoQubitPeepholeOptimization` drops controlled phases near pi/2^15 and smaller, even at `approximation_degree=1.0` | 168 | Qiskit/qiskit#16864 (open, not ours) |
| `CommutativeCancellation` merges rotations and drops a small sum | 2 | Qiskit/qiskit#17315 (open, not ours) |
| none named (see below) | 2 | |

Nothing turned up in tket, PyZX or QCEC. The largest reproducer is 9 gates on 4 qubits (`boundary:qaoa-14:132:qiskit`, within tolerance).

- **Triage.** All 2,049 candidates were triaged (2,015 undecided, 20 oracle disagreements, 13 within tolerance, 1 direct wrong output). 172 showed a witnessed difference (infidelity above 1e-11); the other 1,877 did not.
- **The one direct wrong output**, `random:random:680:qiskit` (12 qubits), reduces to 5 gates on 4 qubits. Its last gate is `cu3(0.683, 0.14348, 6.13973)`, whose phi + lambda is 2 pi + 2.4e-5. D = 5.6e-6, under the tolerance of the reduced reproducer, so it is within tolerance.
- **`random:random:119:qiskit`** reduces to 5 gates with `crz(6.2786)`. QCEC answers `equivalent_up_to_global_phase` although the witness gap is 1.4e-9, so it is not proved twice. This is a QCEC tolerance observation, not a finding.
- **The two rows with no duplicate** (680 and 119) are excluded by their flags. A first-breaking-pass probe names `ElidePermutations` for both, but their reproducers contain a `swap` and the probe does not account for layout, so that label is unresolved, not a mechanism. It changes no count.
- **Within-tolerance rows.** Triage skips full-circuit `within_tolerance` rows by design; they were triaged after the tag (change 14). Several reduce to one gate with D of about 2.4e-5 to 2.5e-5, above tolerance once reduced; their mechanism is #16864. `boundary:qaoa-6:495` and `boundary:qaoa-6:735` have no witness. `boundary:qaoa-10:651` reduces to an oracle disagreement.
- **Not reproduced on Qiskit 2.6.1** (11 rows, each within tolerance, so the result changes no count): `qaoa-10:571`, `qaoa-14:132`, `qaoa-14:452`, `qaoa-18:413`, `qaoa-22:654`, `qft-14:457`, `qft-18:218`, `qft-22:379`, `qpeexact-18:308`, `qpeexact-22:269`, `qpeexact-22:589`, all boundary cases through Qiskit.
- **The 20 oracle disagreements** are all Qiskit on boundary `qft` and `qpeexact` at 18 and 22 qubits: QCEC proves a difference twice and the second opinion does not see it. The likely cause, not checked case by case, is QCEC's default-checker race (change 2). On a tiny `cu1` drop the default configuration answers `no_information` in about 1 call in 6 to 10 (11 and 6 of 60 in two probes), so the case is re-decided by the alternating checker, and the second opinion becomes the random single-qubit simulation. The simulation never sees a drop this small: it answered `probably_equivalent` on a dropped `cu1(0.0001)` in 40 of 40 unseeded calls and with each of 12 seeds. A ZX-only check answered `probably_not_equivalent` 20 of 20 times on the same pair.
- **Condition 5 (latest release, and the main-branch result recorded).** Reproduction was tested on the latest Qiskit release, 2.6.1. The result on Qiskit's main branch was not run (it needs a Rust build, and fix PR #17321 is not merged). This is recorded as not run.

Unfiled reproducers stay in the founder's private folder until filed. The #16864 comment and a PyZX reader report (scientific-notation angles) are on hold; neither would count toward the rule.

## The QCEC 3.11.0 re-check (D-145 addendum)

Every verified output was regenerated by the pinned tools and re-decided by QCEC 3.11.0, logged apart from the 30-hour cap (3.94 busy hours, 2026-10-28 03:46 to 06:11). All 3,839 pairs regenerated.

| Tool | Confirmed | Contradicted | Unconfirmed |
|---|---|---|---|
| PyZX | 585 | 0 | 0 |
| Qiskit | 1,001 | 0 | 7 |
| tket, no swaps | 1,115 | 0 | 7 |
| tket, swaps | 1,120 | 0 | 4 |
| **Total** | **3,821** | **0** | **18** |

The 18 unconfirmed pairs (all `no_information`, 9 to 20 qubits) got the witness check the addendum requires: the largest gap over three seeded states is 8.4e-15, the same float noise as six confirmed control pairs (0 to 5.1e-15). No contradicted pair, so no rerun with QCEC 3.10.2 was needed. The re-check finds nothing.

## Changes after the tag

None alters the kill rule, a frozen parameter, the schedule order or the generator.

1. `verify.outcome` and `_Worker.check` take an optional QCEC configuration.
2. `oracle._decide` re-decides an undecided default QCEC answer (not a hard-wall timeout) with the alternating checker alone: the default configuration answered `no_information` on a phase-only difference 4 times in 12 identical calls (its ZX and simulation checkers race).
3. The second opinion is the random single-qubit simulation when the decision came from the alternating checker, and the alternating checker otherwise. Tolerance is tested before it.
4. `tools.run_tool("qiskit")`: at levels 2 and 3 `ElidePermutations` records swaps only in layout metadata, so the final permutation is appended explicitly. The calibration run gave 7 false wrong outputs from this; it was discarded and its 0.44 hours stay counted.
5. The tolerance table was mismeasured: `tolerance.largest_drop` tested "changed by more than half the angle", which a complete drop meets exactly. Re-measured: Qiskit drops controlled phases near 1e-4 and `rz` near 1e-6, tket about 1e-5, PyZX none. The frozen table (Qiskit 1e-5) was left as tagged; P0c redefines the condition for later runs.
6. PyZX inputs get plain decimal angles from batch 2 on (batch 1 logged 92 reader crashes on exponent notation; those outputs were run again).
7. `triage.py`: a statevector witness (infidelity above 1e-11 on a seeded random product state) for undecided outputs, ddmin reduction on the witness, then the oracle on the reduced reproducer. A witness is a lead; counting needs the evidence conditions.
8. Tests: the planted-fault test asserts on log rows; `test_tools` and `test_triage` added.
9. Latest releases on 2026-10-14: Qiskit 2.5.2 (pinned), pytket 2.18.5 (pinned 2.18.4), PyZX 0.10.7 (pinned), QCEC 3.11.0 (pinned 3.10.2).
10. `verify._Worker.check` returns `worker_died` (unverified) and replaces a worker that dies mid-check.
11. Batch 2 was cut short when the PC entered standby at about 19:27 on 10-14 and rebooted. Its 2.37 counted hours include about 49 minutes asleep; batch 3 lost about 22 minutes to standby cycles before the no-sleep hold worked. About 1 to 1.5 of the 30 hours are overstated; the cap ledger keeps the larger figure.
12. The QCEC 3.11.0 re-check of every verified output, declared before it ran (D-145 addendum, tag `audit-addendum`). It started after batch 8 rather than after batch 7, because the stall moved batches 5 to 8 to 10-27.
13. Batch 8 ran to the cap (2.64 hours); its triage finished inside day 14.
14. Full-circuit `within_tolerance` rows, which `triage.py` skips by design, were triaged after the tag with the same witness, reduction and record format.
15. The ledger was built by a script outside the repo: one row per witnessed case; `proved_twice` from two fresh-worker QCEC decisions on the reduced reproducer; `second_opinion_ok` from the alternating checker plus a dense distance for at most 10 qubits; `tolerance_ok` as D above G × tolerance on the reduced reproducer; `reproduces_latest` from the witness at the pins and on Qiskit 2.6.1; `duplicate_of` from the first pass after which the operator differs (`TwoQubitPeepholeOptimization` gives #16864, `CommutativeCancellation` #17315), with the tracker search URL.
16. The latest-release check used a separate Qiskit 2.6.1 environment, which runs the same Qiskit pipeline as `run_tool`.
17. The runner prints each shard's last index in completion order, not shard order, so the per-batch split of case kinds is ambiguous; case totals are exact. Batch 6's boundaries were corrected from the triage coverage.
18. Not in this record: `737701d` (UTC times on every observation and batch, triage of each batch as soon as it is logged, the attention list with its 72-hour filing clock) follows in its own pull request after the verdict. With it applied, `test_a_tiny_drop_is_reduced_to_one_gate_and_filed_as_the_known_qiskit_issue` failed in 4 of 15 full-suite runs (0 of 10 on main without it). The cause is QCEC's default-checker race, not the simulation's seed: when the default answers `no_information`, the case is re-decided by the alternating checker, and the simulation second opinion cannot see the drop, so the reduced case is classed an oracle disagreement. That pull request pins the test's default answer to the exact checker's and leaves the oracle as the audit ran it.

## What follows

D-155 keeps the registered fallback: option (b) on `qaoa` (D-144) becomes an explore track on the same harness, starting from a plan (`docs/plans/P0e-qaoa-explore.md`) and running alongside P0d during the six-week P2 hold. P0c is deferred until the audit runs again. No P3 or P4 change follows from the spike.

## Analysis added after the verdict

Added 2026-10-28, after D-155. Nothing above this section is changed. None of it changes the verdict, a count or the oracle the verdict used, and none of it counts toward any rule. The code is in `spikes/qopt_audit/` with tests; the private logs and reproducers stay private.

### The null result as bounds

"Nothing turned up" means 0 wrong outputs among the outputs QCEC decided. For N decided outputs with 0 wrong, the one-sided 95% upper bound on the wrong-output rate is about 3/N (the rule of three; the exact bound 1 − 0.05^(1/N) agrees to two decimal places here). The bound holds for inputs drawn the way the audit drew them, and it trusts QCEC's decisions: the QCEC 3.11.0 re-check confirmed 3,821 of the 3,839 and contradicted none. For Qiskit the bound is on mechanisms other than the known small-angle drops (#16864 and #17315), and it counts only the 1,008 verified outputs. The 34 outputs QCEC proved different are left out. Of those, 30 reduce to the #16864 pass under the ledger's rule, and 2 (`random:680`, `random:119`) reduce to the passes of the two issues under the layout-aware probe below. The other 2 (`boundary:qaoa-6:495` and `boundary:qaoa-6:735`, D about 2.5e-6 and within tolerance) have no witness, and no mechanism was named for them.

| Tool | Decided, 0 wrong | 95% bound | 6 to 10 qubits | 11 to 14 | 15 to 18 | 19 to 22 | Undecided, not covered |
|---|---|---|---|---|---|---|---|
| tket, swaps | 1,124 | 0.27% | 504: 0.60% | 220: 1.4% | 239: 1.3% | 161: 1.9% | 348 |
| tket, no swaps | 1,122 | 0.27% | 508: 0.59% | 221: 1.4% | 231: 1.3% | 162: 1.9% | 350 |
| PyZX | 585 | 0.51% | 347: 0.86% | 87: 3.4% | 78: 3.8% | 73: 4.1% | 887 |
| Qiskit, other mechanisms | 1,008 | 0.30% | 476: 0.63% | 195: 1.5% | 203: 1.5% | 134: 2.2% | 430 |

Each band cell gives the decided outputs in that band and their bound. The 2,015 undecided outputs, 60% of PyZX's (887 of 1,472), are not covered by any of these bounds. They had only triage's witness, one seeded random product state, and the run measured no bound for that check. Above 10 qubits the bounds widen to 1.3% to 4.1%, because fewer outputs were decided there.

### The 20 oracle disagreements, case by case

`spikes/qopt_audit/disagreements.py` regenerated each disagreement's output with the pinned Qiskit and put each pair to QCEC 3.10.2 again, each call in a fresh worker. The default configuration ran 10 times, then the alternating checker alone, the random single-qubit simulation alone, and the ZX checker alone 3 times (0.97 QCEC busy hours on 2026-10-28). Each case is classed by the path the run log shows it took:

- **`race`**: a proof failed (1 of 2 confirmations). The default sometimes proves the difference and sometimes gives an answer `oracle._decide` re-decides, and the alternating checker alone cannot decide in 60 seconds, so a raced decision ends undecided.
- **`second_opinion_timeout`**: proved twice, with a second opinion of `no_information`. The alternating checker alone cannot decide in 60 seconds.

| Class | Cases | Logged | Default, 10 calls each | Alternating alone | ZX alone |
|---|---|---|---|---|---|
| `race` | 4: `qft-18:218`, `qft-22:379`, `qpeexact-18:228`, `qpeexact-18:348` | 1 proof | proved in 2 to 6 of 10 calls; otherwise `no_information` or `probably_not_equivalent` | `no_information` (60 to 80 s) | `probably_not_equivalent` |
| `second_opinion_timeout` | 16: `qft-18:538`, `qft-18:658` and 14 `qft-22` cases | 2 proofs, second opinion `no_information` | proved in 8 to 10 of 10 calls | `no_information` (61 to 67 s) | `probably_not_equivalent` |

All 20 are Qiskit outputs of boundary cases, and all 20 reduce to the #16864 pass. Nothing falls outside the two classes.

- **This corrects the likely cause given above.** It is the default-checker race for 4 of the 20, the 4 whose proof failed. For the other 16 it is not the race and not the simulation's blindness. Both proofs held, and the second opinion was the alternating checker, which runs out of time at 18 and 22 qubits. The simulation would have missed most of them too: alone, it answered `probably_equivalent` on 14 of the 20 pairs.
- **The ZX checker alone saw every difference.** It answered `probably_not_equivalent` in 60 of 60 calls, each in at most 6.4 seconds. This supports the second-opinion rule P0c fixes before its tag (the ZX checker, with `probably_not_equivalent` accepted as agreement).
- **One change to the rule while classifying.** The first version looked only for `no_information` from the default, and it put `qpeexact-18:348` (6 proofs and 4 `probably_not_equivalent` in 10 calls) in `other`. `oracle._decide` re-decides `probably_not_equivalent` exactly as it does `no_information`, so the rule now counts either, and 348 is `race`. No other case moved.

### The ledger builder

The ledger was built by a script outside the repo (change 15). It is now `spikes/qopt_audit/build_ledger.py`, with a test. It has two steps. `collect` measures each witnessed case into a notes file: two QCEC decisions in fresh workers, the alternating checker, the first pass after which the operator differs (blind to the layout, as the verdict's ledger was built), the dense distance, and the witness at the pins and on Qiskit 2.6.1. `build` turns the triage records and the notes into the ledger and runs no tool.

- From the original notes, the build gives `ledger.jsonl` byte for byte. The original notes did not keep three measured fields (the dense distance of `random:119`, and the witness at the pins and on 2.6.1), so `collect` measured those again and kept everything else.
- From empty notes, with every field measured again on 2026-10-28, the build also gives `ledger.jsonl` byte for byte. That includes the 344 decisions behind `proved_twice`, the 172 alternating-checker answers and the 172 pass labels. Every answer matched the original notes.
- **A correction to "Not reproduced on Qiskit 2.6.1".** For the 11 rows with `reproduces_latest` false, the witness on the reduced reproducer is below the 1e-11 floor on both versions, and it is identical on the pinned Qiskit 2.5.2 and on 2.6.1 (1.4e-13 to 6.9e-12). The flag is false because the reduced reproducer's witness falls under the floor, not because 2.6.1 behaves differently. All 11 are within tolerance, so no count changes.

### The mechanism probe, aware of the layout

`spikes/qopt_audit/passes.py` runs the audit's Qiskit pipeline and compares the operator after every pass with the input's. In its layout-aware form it first appends the permutation that `ElidePermutations` records in `virtual_permutation_layout`. The blind form reproduces all 172 pass labels in the ledger.

| Case | Blind probe (the ledger's label) | Layout-aware probe | D after that pass, and in the final output |
|---|---|---|---|
| `random:random:680:qiskit` | `ElidePermutations` | `CommutativeCancellation` | 5.6e-6, 5.6e-6 |
| `random:random:119:qiskit` | `ElidePermutations` | `TwoQubitPeepholeOptimization` | 3.8e-5, 3.8e-5 |

Both labels are now resolved to a pass: the same passes as #17315 and #16864. Under the ledger's pass-to-issue rule, 680 would be a duplicate of #17315 and 119 of #16864. Whether each is the same mechanism as its issue, beyond the pass that first changes the operator, was not checked. Both rows were already excluded by their flags, so no count changes.

### Condition 5 on Qiskit's main branch

Measured on 2026-10-28, after the verdict. It changes no count and no flag in the ledger.

Qiskit was built from source in a throwaway container at two points: the merge base of fix PR [Qiskit/qiskit#17321](https://github.com/Qiskit/qiskit/pull/17321) on main (`73aa14d`), and the PR's head (`dd1b4c3`, merged on 2026-10-28 as the fix). Both builds report 2.7.0.dev0. Each ran the audit's Qiskit pipeline (`tools.run_tool`) with QCEC 3.10.2 on the reduced reproducers and the full inputs of the two #17315 rows and 10 of the #16864 rows.

| Cases | Merge base `73aa14d` | Head `dd1b4c3` (the fix) |
|---|---|---|
| The 2 #17315 reduced cases | `not_equivalent` (D 4.8e-5 and 5.0e-6), as on 2.5.2 | `equivalent_up_to_global_phase` (D below 1e-15) |
| The 10 #16864 reduced cases | `not_equivalent` (D 2.4e-5 to 2.5e-5), as on 2.5.2 | unchanged, the same figures |
| The 2 #17315 full circuits | witness 5.9e-9 and 7.3e-9; QCEC `no_information` | the same witnesses; QCEC `no_information` |

Main before the fix reproduces both #17315 cases and all 10 #16864 cases. The fix removes the #17315 drop and changes nothing else measured here. The full circuits of the two #17315 rows still differ after the fix. For `boundary:qaoa-14:452` the whole remaining full-circuit gap appears at `TwoQubitPeepholeOptimization` (the #16864 pass), and `CommutativeCancellation` adds nothing above 1e-11. For `boundary:qaoa-22:254` the full-circuit witness is unchanged by the fix (5.9e-9). A per-pass trace run to completion on 2026-10-28 puts the whole gap at `TwoQubitPeepholeOptimization` (the #16864 pass), from 1.3e-15 to 5.9e-9, and `CommutativeCancellation` adds nothing above 1e-11. For `boundary:qaoa-14:452` the reduced witness is 1.4e-13 at every version, below the ledger's 1e-11 floor, so its reproduction rests on QCEC's proof alone. That is why its `reproduces_latest` is false.

### What upstream has said

On [Qiskit/qiskit#16864](https://github.com/Qiskit/qiskit/issues/16864) a Qiskit maintainer answered on 2026-08-30 that the behaviour is not a bug: `approximation_degree=1.0` means no approximation "up to numerical tolerance". The issue is still open and still labelled a bug. Even so, upstream treats the 168 #16864 rows as tolerance behaviour by design, not as wrong outputs. That strengthens the case for P0c. A wrong output has to be defined from what each tool documents and how its maintainers judge it, not from a measured table, and #16864 is the first case that definition must cover through Qiskit's documentation. Both real leads the run held were reported by others during the stall (2026-10-19 to 2026-10-27), within days of the lab having them. [Qiskit/qiskit#17315](https://github.com/Qiskit/qiskit/issues/17315) was opened on 2026-10-25, about six days after `boundary:qaoa-22:254` was logged. The PyZX reader's rejection of exponent-notation angles became [zxcalc/pyzx#558](https://github.com/zxcalc/pyzx/issues/558), opened on 2026-10-21, a week after batch 1 logged the reader crashes on 2026-10-14. The fix for #17315, [Qiskit/qiskit#17321](https://github.com/Qiskit/qiskit/pull/17321), was merged on 2026-10-28 and closed the issue as completed.
