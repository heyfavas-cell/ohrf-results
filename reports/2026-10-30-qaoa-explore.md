# QAOA explore track, 2026-10-28 to 2026-10-30

The track of `docs/plans/P0e-qaoa-explore.md` was run under the rule fixed by the tag `qaoa-prereg` (commit `1e6d9b1`, tag object `9a9d4ca`) and the search frozen by the tag `qaoa-freeze` (commit `68b0b1c`, tag object `37d53ee`). This file records the outcome, the numbers behind it, what it cost, and everything that differs from the tagged plan. Decision: open (see the end).

## Outcome

**Null.** The rule was applied once, on all 145 frozen held-out circuits, with `score.decide` through `heldout_report final`. Neither (Q) nor (T) holds, so (S) does not decide anything.

| Test | Ratio (geometric mean) | 95% interval | Passes? |
|---|---|---|---|
| (Q) candidate@300 s against GUOQ@300 s | 1.0324 | 1.0213 to 1.0428 | no: gain is -3.2%, lower bound -4.3% |
| (T) candidate@15 s against GUOQ@300 s | 1.0502 | 1.0403 to 1.0596 | no: ratio is above 1.00 and the upper bound is above 1.01 |
| (S) candidate against `S*`, 300 s | 0.9481 | 0.9327 to 0.9626 | yes, but see the note below |
| (S) candidate against `S*`, 15 s | 0.9645 | 0.9509 to 0.9772 | yes, but see the note below |
| `S*` against GUOQ@300 s (at either budget) | 1.0889 | 1.0790 to 1.0993 | no |

- The candidate has more CNOTs than GUOQ on 109 of 145 circuits at 300 s, ties on 11 and has fewer on 25.
- **(S) is met and does not matter.** `S*` is `q-1q-decompose` by the tie rule below, and on these circuits it leaves the CNOT count at the input's (ratio 1.0000 on every circuit). The candidate beats it by 5.2% at 300 s and 3.6% at 15 s, which is the candidate's gain over the input. GUOQ's is 8.2% at 300 s.
- **Sensitivity row.** On the 136 circuits where every arm is verified the outcome is also null: (Q) 1.0298 (1.0187 to 1.0405), (T) 1.0489 (1.0388 to 1.0587).
- **The 80% verified floor** is met on every arm, so it did not apply (shares below).

### Geometric-mean CNOT ratio to the input (an unverified output scores the input)

| Arm | All 145 |
|---|---|
| GUOQ 15 s | 0.9481 |
| GUOQ 300 s | 0.9184 |
| Candidate 15 s | 0.9645 |
| Candidate 300 s | 0.9481 |
| `S*` | 1.0000 |

| Size | n | GUOQ 15 s | GUOQ 300 s | Cand. 15 s | Cand. 300 s | Cand. 300 s / GUOQ 300 s | Cand. 15 s / GUOQ 300 s |
|---|---|---|---|---|---|---|---|
| 6 | 15 | 0.8617 | 0.8388 | 0.8145 | 0.7789 | 0.9286 | 0.9710 |
| 8 | 16 | 0.8931 | 0.8865 | 0.9266 | 0.8850 | 0.9983 | 1.0452 |
| 10 | 17 | 0.9489 | 0.9075 | 0.9601 | 0.9330 | 1.0281 | 1.0580 |
| 12 | 17 | 0.9540 | 0.9085 | 0.9869 | 0.9625 | 1.0594 | 1.0863 |
| 14 | 17 | 0.9736 | 0.9400 | 0.9990 | 0.9966 | 1.0603 | 1.0628 |
| 16 | 15 | 0.9657 | 0.9320 | 1.0000 | 0.9942 | 1.0667 | 1.0729 |
| 18 | 16 | 0.9750 | 0.9455 | 1.0000 | 0.9983 | 1.0559 | 1.0577 |
| 20 | 16 | 0.9836 | 0.9549 | 0.9992 | 0.9983 | 1.0454 | 1.0464 |
| 22 | 16 | 0.9784 | 0.9536 | 1.0000 | 1.0000 | 1.0486 | 1.0486 |

The candidate is ahead of GUOQ only at 6 qubits (7.1% fewer CNOTs at 300 s, 2.9% at 15 s) and level at 8 qubits at 300 s. From 10 qubits up it is 3% to 7% behind at 300 s and is close to the input from 14 qubits up. The per-size ratios are descriptive, not a test.

## The sample and its power

- **`N_heldout` = 145**, fixed at `qaoa-freeze` before any held-out circuit ran. The development spread was `s` = 0.0663, which would call for 342 circuits for a 1% gain at 80% power; the pool has 324 and the cap allowed 145 (593.2 worker-seconds per circuit, 12 h on 2 workers), so the cap bound. The floor of 108 was met. The 145 circuits are the first 145 of the stratified, seeded order: 49 `regular4`, 48 `regular3` and 48 `erdos_renyi`, 15 to 17 per size.
- **Measured on the held-out sample:** `s` = 0.0639 (candidate against GUOQ at 300 s). **The smallest gain this sample could find was 1.48%** (1.53% was planned from the development set). A true gain of 1% would very likely not have reached a lower bound above 0, as the plan said. This does not matter for the result: the point estimate is a loss of 3.2%, and the whole interval lies on the loss side.
- A null with an interval entirely on the wrong side of zero is a null of this sample and of this candidate, with this pool. It is not a statement about every search over every pool.

## Verification

Every output was checked by QCEC 3.10.2 with the audit's re-decide step, and every verified GUOQ output was re-checked with QCEC 3.11.0 (all 288 agreed: 267 `equivalent_up_to_global_phase`, 21 `equivalent`). Each candidate proposal went through the same check (QCEC 3.10.2, then the 3.11.0 re-check); the search rows record whether the output verified, not the re-check answer.

| Arm | Verified |
|---|---|
| GUOQ 15 s | 144 of 145 (0.9931) |
| GUOQ 300 s | 144 of 145 (0.9931) |
| Candidate 15 s | 144 of 145 (0.9931) |
| Candidate 300 s | 137 of 145 (0.9448) |
| `S*` | 145 of 145 |

By size (verified of total):

| Size | GUOQ 15 s | GUOQ 300 s | Cand. 15 s | Cand. 300 s | `S*` |
|---|---|---|---|---|---|
| 6 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 |
| 8 | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 |
| 10 | 17/17 | 17/17 | 17/17 | 16/17 | 17/17 |
| 12 | 17/17 | 17/17 | 17/17 | 15/17 | 17/17 |
| 14 | 17/17 | 17/17 | 16/17 | 16/17 | 17/17 |
| 16 | 15/15 | 15/15 | 15/15 | 14/15 | 15/15 |
| 18 | 16/16 | 16/16 | 16/16 | 14/16 | 16/16 |
| 20 | 16/16 | 15/16 | 16/16 | 16/16 | 16/16 |
| 22 | 15/16 | 16/16 | 16/16 | 15/16 | 16/16 |

- **GUOQ's two unverified outputs.** `held_out-22-regular3-p4-r2` at 15 s (QCEC `hard_timeout`; the same kind and depth as the development circuit whose output also timed out) and `held_out-20-regular3-p3-r2` at 300 s (`no_information` after the alternating checker). Each scored its input's count.
- **The candidate's unverified outputs** are eight at 300 s and one at 15 s. In each case all five proposals went unverified, and none was a witnessed difference, so none is a lead. For example `held_out-10-regular4-p4-r0` had a best unverified count of 135 against an input of 160. The candidate's 300 s ratio would be lower if QCEC had decided them; the rule scores them as the input, for the candidate as for GUOQ.

## Development phase

All development results are on the 36 development circuits and decided nothing.

- **GUOQ** (wisq 0.2.7, `97c12a5`): 300 s geometric-mean ratio to input 0.9254 (36 of 36 verified), 15 s 0.9511 (35 of 36). Three runs of 300 s on 12 circuits had a pooled log standard deviation of 0.0097, and 7 of the 12 circuits differed between runs.
- **Pool passes alone.** 13 of the 18 pool passes never change the CNOT count of a QAOA circuit; of the other five, only `t-greedy-pauli` beats the input on some circuits (small sizes), and it loses overall (gain -0.169, 78% verified). `q-linear-functions`, the pass that won on `vqe_two_local`, gains nothing here. The two PyZX passes make circuits far worse (gain -1.7 and -1.8). Passes verified 82 of 88 at 22 qubits and 85 to 88 of 88 elsewhere.
- **`S*` is a tie.** Thirteen passes score gain +0.000 at both budgets. The plan had no tie rule; at the freeze the founder chose "first by name", which gives `q-1q-decompose` at both budgets (OD-AQ). Since every tied pass leaves the circuit unchanged, any choice gives the same scores.
- **The search** (config `wide`: beam 8, 10 steps, 5 proposals, seed 1): at 15 s the base, prior, wide, wider and widest configurations scored 0.9644, 0.9644, 0.9557, 0.9557 and 0.9557 on the first 32 circuits, so the beam and the step limit were saturated and the pool was the limit. On all 36 development circuits, `wide` against GUOQ at 300 s gave (Q) 1.0270 (1.0040 to 1.0477) and (T) 1.0380 (1.0185 to 1.0555), which the held-out run then confirmed in sign and size.
- **Exploratory passes outside the pool** (never counted, never in the pool): `x-greedy-reduce` 5 wins, 20 ties, 4 worse and 3 unverified on the circuits tried; `x-pauli-individual-star` and `x-pauli-pairwise-tree` no wins. The best of the three alone reached 0.9758 of the input. Their 1266 s are counted on the compute line as development.

## Held-out blocks

The run order was the frozen order in six blocks (blocks 1 to 4: 26 circuits, block 5: 25, block 6: 16, all of size 22). Each block was triaged when it landed. All figures are descriptive; the rule was applied once, after block 6.

| Block | Circuits | Wall-clock | Memory waits (jobs, refusals, seconds, longest) | Leads |
|---|---|---|---|---|
| 1 | 26 | 7610 s | 8, 40, 1410 s, 390 s | 0 |
| 2 | 26 | 6222 s | 0 | 0 |
| 3 | 26 | 10312 s | 21, 370, 11311 s, 2010 s | 0 |
| 4 | 26 | 7290 s | 3, 3, 180 s, 60 s | 0 |
| 5 | 25 | 6091 s | 0 | 0 |
| 6 | 16 | 7200 s + 7200 s + 8562 s + 9982 s | 11, 53, 1590 s, 960 s (last attempt) | 0 |

In every block GUOQ had no timeouts and no bad exits, the candidate had no search errors and its largest overrun of the budget was 3.06 s.

Block 6 needed three restarts of the same jobs; see the deviations below.

## Compute

Wall-clock hours of runs, as logged in `runs.jsonl` (32 rows), against the 30:

| Phase | Hours |
|---|---|
| Development (including the aborted and stopped batches and the exploratory side run) | 7.457 |
| Held-out | 19.575 |
| **Total logged** | **27.032 of 30** (19.575 held-out + 7.457 development) |

**The final report's "compute" line shows `held_out` 19.575 and `total` 19.575.** That line sums the held-out rows only, because `heldout_report final` is given the held-out batches; it is not the total for the track. The total is 27.032 h, from all 32 rows of `runs.jsonl`.

Step 0, run before the tag (about 0.15 h, in the plan), is not in `runs.jsonl`, so the total with it is about 27.2 h. The 30 h total cap, the 4 h run cap and the 10 h development cap held. The held-out phase passed its planned 12 h by 7.575 h, inside the 8 h reserve, through the allowance in deviation 3 below. Roughly half of the held-out time was memory waiting: 3.6 h of logged waits in blocks 1 to 5, the two aborted attempts at block 6 (4.0 h, all waiting), most of the stopped third attempt (2.4 h) and 0.4 h in the last. The blocks with no waiting (2 and 5) took 1.7 h each.

**The founder's and the build's hours were not logged**, so this record has no figure for them. The plan's estimate of 3 to 5 founder hours is therefore neither confirmed nor refuted here.

## The PC guard's refusals

3,221 refusals in all, each logged with its time and reason (`refusals.jsonl`): 656 in development and 2,565 in the held-out run. In the held-out run, 413 came in blocks 1 to 5 (370 in block 3 alone) and 2,152 in block 6, of which 1,440 were in the two attempts that aborted. 3,207 were memory refusals (free memory under the margin plus the QCEC reserve) and 14 were CPU refusals (more than 60% CPU outside P0e's jobs); none was for P0d. The cause was the 22-qubit jobs: QCEC needs a measured 8.06 GB at the peak, so a size-22 job is admitted only with 8 GB plus 8.1 GB free (16.1 GB), which a PC in daily use rarely had.

## Leads

None. No batch, in development or on the held-out set, produced a lead (no witnessed `not_equivalent` output, no tool crash on a valid input, no 3.11.0 contradiction), so `attention.jsonl` was never created and no `due_by` ran. Nothing was drafted for filing and nothing was posted or contacted upstream (D-157).

## The anchors

Both tags are stamped with OpenTimestamps, and both stamped files and proofs are committed in `qaoa-explore-anchors/`.

| Anchor | Stamped text (sha256 of the file) | Proof (sha256) | Actual status |
|---|---|---|---|
| `qaoa-prereg` | `qaoa-prereg.txt` `991653dc...70b7` | `qaoa-prereg.txt.ots` `8c2f03bb...a88f` (4,090 bytes) | Complete: three Bitcoin block header attestations (blocks 973556, 973564, 973580, from three calendars). A fourth calendar's branch (alice) still shows only a pending attestation. The upgrade was run by the founder with the OpenTimestamps client; this record repeats its output and does not re-verify it against a Bitcoin node. |
| `qaoa-freeze` | `qaoa-freeze.txt` `c8f6326a...d62d` | `qaoa-freeze.txt.ots` `de46f892...5fe31` (1,981 bytes) | One Bitcoin block header attestation (block 973658), read by parsing the proof's attestation records; the proof also still lists four calendar branches as pending. The calendar of the confirmed branch was not read, and the attestation was not checked against a Bitcoin node here. |

Both stamped files are unchanged from when they were stamped. `qaoa-prereg.txt` names tag object `9a9d4ca` and commit `1e6d9b1`; `qaoa-freeze.txt` names tag object `37d53ee`, commit `68b0b1c` and the sha256 of `search_config.json`, `c2e6b5d6...2736`. The freeze proof shows one Bitcoin attestation and still lists four calendar branches as pending beside it; the calendar of the confirmed branch was not read. **The held-out run started (2026-10-29 07:42 UTC) after the prereg anchor was complete and before the freeze proof was upgraded** (that happened at 09:28 UTC, during block 1). Nothing in the run depends on the freeze proof; the freeze commit and tag existed and were pushed before any held-out circuit ran.

## Deviations from the tagged plan

All were decided by the founder or are listed as the plan's own allowed kind, before the rule was applied (the outcome was decided only after block 6). OD-BB 1 and OD-BI 2 were decided after the block 1 to 5 summaries, which showed the candidate behind GUOQ, had been seen; they changed only whether and how jobs were admitted. None changes the rule, a frozen parameter, the pool or the generator. `frozen.py` is byte-identical to the tagged file throughout (sha256 `bc6fde2d...ed1ed`).

1. **`S*` tie rule (OD-AQ).** Thirteen passes tie as the best single pass; the plan had no rule. "First by name" was chosen at the freeze, before any held-out run. It does not change any score (above).
2. **Pool as built (OD-AQ).** The pool is the 18 passes `passes.py` builds; plan line 83 governs and `search_config.json` records it.
3. **Held-out cap allowance (OD-AS).** Memory waits count toward `HELD_OUT_CAP_S` (12 h), and `N_heldout` had been sized for no waiting. Before any held-out outcome was seen, the founder decided that the held-out phase may run into the 8 h reserve; the 30 h total and the 4 h run cap stay hard. It is implemented as a recorded allowance file read by `run.allowance_s`, not a change to `frozen.py`, and each batch started on it is logged in `allowances.jsonl`. It was used by the two last attempts at block 6.
4. **Third attempt at block 6 (OD-BB 1).** Block 6 aborted twice ("never admitted" after 120 refusal rounds, 720 each; 14,400 s booked by hand since aborted batches write no row). The rule was to stop and write up after a block fails twice. The founder decided, after both aborts and before any block 6 outcome, to allow a third attempt after a restart of the PC (the Windows kernel nonpaged pool was 3.1 GB, a leak, which stopped free memory from reaching 16.1 GB). It was stopped by hand at 19 of 80 block-6 results (see 5) and logged by hand at 8,562 s.
5. **Free-memory margin 8 to 5 GB for block 6 (OD-BI 2).** Free memory in work hours topped out near 13.5 GB. For block 6 only, the founder lowered the base margin from 8 GB to 5 GB (a size-22 job then needs 13.1 GB), kept the 8.1 GB QCEC reserve, and ran one job at a time. It was implemented as a recorded run-time override (`guard_override.json`, read by `run.guard_override`), with a note row in `runs.jsonl` and a line in `guard_overrides.jsonl`, not by editing `frozen.py`. The founder decided after 19 of 80 block-6 results; the stopped batch had no live job when it was stopped, and the 61 remaining jobs ran as batch `held-6-resume-3` (started 07:46 UTC, ended 10:32 UTC). The override was removed after block 6. It is an operational change (admission of jobs), not a change to a job, a budget, a verification step or the scoring.
6. **A borrowed interpreter.** QCEC 3.11.0 (the re-check) runs in a separate environment that the toolchain audit's worktree holds; `QCEC_LATEST_PYTHON` names it and the driver refuses to start without it. A note row records it.

## Changes after the tag

Code and files added after `qaoa-prereg`, all test-first, none altering the rule, a frozen parameter, the pool or the generator (the tagged circuits and manifests are identical, and `frozen.py` is unchanged; `make_qaoa.py` changed in two lines only, to use the folder helper):

- **Tasks 4 to 9, as the plan lists them:** the oracle (re-decide, 3.11.0 re-check, multi-state witness, ZX second opinion; `892a772`), the PC guard (`141b770`), GUOQ at a budget (`d68d3c3`), the pass pool, the PyZX wall and the budgeted beam search (`e2b18bb`), the score (`52506ea`), and the runner with per-batch triage and the stall alarm (`ad1a49c`).
- **Guard registry lock** (`3008219`): a Windows read-against-write race failed 13 of 15 suite runs; with the lock 15 of 15 pass.
- **Development driver** (`b7b394e`) and two bugs the first development batch found: the QCEC work folder was not made and results were written only at the end of a batch, so the first batch lost its three results (`8d2e72f`). That batch was stopped by hand and booked at 990 s.
- **Interpreter guard** (`fb5d9e0`): refuse to start a development run without the QCEC 3.11.0 interpreter.
- **QCEC peak memory** (`7a0231e`, `6fe7ba9`, `851aeb2`): a per-size peak table (`qcec_peak.json`; 22 qubits 8.06 GB, every other output 1.0 to 1.4 GB) and a guard reserve of that size on top of the 8 GB minimum.
- **One helper for folders** (`0b3ed25`), with a test that no script makes its own.
- **Pass and search jobs in worker processes, and `GreedyPauliSimp` given a gate set it accepts** (`a6d60f6`): the pass raised on every input in the pool basis because it rejects `sx`; it now rebases to CX, Rz and H first.
- **Development report** (`f013cb1`), **`--only` for the passes batch** (`131e75f`), the **freeze module with the exploratory passes and the `S*` tie rule** (`cd38f16`), and the **freeze** (`68b0b1c`).
- **Held-out driver and reports** (`c53c708`): the gate (anchor complete, config hash, tag), the blocks of the frozen order with size 22 last, `--resume` and the held-out reports.
- **The allowance and the per-batch memory-wait and hours report** (`413ab42`), and **the guard override** (`02ee5a9`).
- **Operational decisions (OD-AS, OD-BB 1, OD-BI 2), also in the deviations above.** The held-out cap allowance (OD-AS, `allowance.json`, `run.allowance_s`, `run.may_start`; commit `413ab42`); the third attempt at block 6 (OD-BB 1); and the free-memory margin of 5 GB for block 6 (OD-BI 2), decided after 19 of 80 block-6 results, with one worker in that batch (`guard_override.json`, `run.guard_override`, `slots.Guard(min_free_gb=...)`; commit `02ee5a9`). The held-out driver and reports are `c53c708`.
- **Hand-logged rows and a repaired log.** The two aborted block-6 attempts (7,200.4 s and 7,200.5 s) and the stopped third attempt wrote no `runs.jsonl` row, so each was logged by hand with a note. The third's first hand row said 8,310 s, which was wrong; it was corrected to 8,562 s (05:21:49 to 07:44:31 UTC). Writing a row with PowerShell 5.1 `Set-Content -Encoding utf8` added a byte-order mark to `runs.jsonl`, which broke reading the first line; the file was rewritten as UTF-8 without it, and later rows were appended without one. No row's content changed other than the corrected 8,310 s.
- **Other disclosed operations:** the 300 s development batch was split (the first part stopped by hand at 24 of 36 with size 22 deferred, booked at 5,648 s) because three workers waited on size-22 jobs and blocked smaller ones; size 22 was run later when memory had been freed. The wall-clock of the aborted and stopped batches was logged by hand (990, 5,648, 7,200, 7,200 and 8,562 s). A first hand row for the last was wrong (8,310 s) and was corrected from the logs.
- **Environment facts, not changes:** the audit's reproducers are private, so the known-issue match is tested on synthetic tiny-angle circuits; running Python scripts from stdin (`python -`) breaks the spawned workers on this PC.
- **Suite:** 140 tests pass with the real QCEC 3.11.0 interpreter, one deselected (the 10 s real GUOQ test, run once per full run).

## What this does and does not show

**Scope of the null.** It covers one thing: reordering and combining the existing passes of Qiskit 2.5.2, pytket 2.18.4 and PyZX 0.10.7 (the 18-pass pool, a beam search of up to 10 steps, width 8) on unweighted QAOA MaxCut circuits of 6 to 22 qubits (even sizes), depth 1 to 4, on random regular and Erdos-Renyi graphs, against GUOQ as pinned: `wisq` 0.2.7 at commit `97c12a5`, objective `TWO_Q`, gate set `IBMN`, run between 2026-10-29 and 2026-10-30. It says nothing about other circuit families, other graphs or sizes, other pools, new rewrite rules, problem-aware synthesis, other GUOQ versions or settings, or other time budgets than 15 s and 300 s.

**The size pattern (found after the rule was applied; not a claim and not part of the rule).** Looking at the results by size, the candidate does better at 6 qubits (ratio to GUOQ at 300 s 0.929; fewer CNOTs on 11 of 15 circuits) and is level at 8 (0.998; fewer on 8 of 16), and from 14 qubits up it has fewer CNOTs than GUOQ on none of 80 circuits (74 worse, 6 tied at 300 s; none better at 15 s either). Sizes were chosen as strata before the run, but this split by size is a description made after seeing the outcome. It was not tested, it carries no interval here, and a rule fixed in advance would be needed to claim it.

- On fresh textbook QAOA MaxCut circuits of 6 to 22 qubits, a budgeted beam search over the passes of Qiskit 2.5.2, pytket 2.18.4 and PyZX 0.10.7 did not match GUOQ at either budget, and the shortfall grows up to about size 16, then levels off. It found real savings only on small circuits.
- The existing passes by themselves do almost nothing here: thirteen of eighteen never change the count. The candidate's gain over the input (5.2%) is the search's, but GUOQ gets 8.2%, and the search was saturated by the second beam width: at 15 s on the development set, widening the beam stopped helping, while more time still helped on the held-out set (0.9645 at 15 s, 0.9481 at 300 s). Whether the pool is the limit was not tested.
- The 15 s time test failed by more than the 300 s quality test, so the plan's second route (matching a converged GUOQ in a twentieth of the time) is not close.
- This is a result on one family, one pool and one search design. A search over a different pool (for example passes that exploit the QAOA structure) is a different test and was outside this plan (no problem-aware synthesis, no new rewrite rules).
- The candidate's 300 s outputs went unverified on 8 of 145 circuits; the larger worry would be a search that finds unsound outputs, and none was found.

## Decision

Per the plan, a null is published beside the audit's null in `docs/history/`, and nothing in P3 or P4 changes until the founder decides. The decision is the founder's and is open: it would take the next free D-number in `docs/decisions/decision-log.md` and state the outcome above, the reading of what it does and does not show, and whether the benchmark-discovery pilot (D-089) keeps a live case on this family. This record does not decide it.
