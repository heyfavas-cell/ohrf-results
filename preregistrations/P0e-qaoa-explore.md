# P0e QAOA explore track plan

This plan tests option (b) of the reshape decision (D-144), the fallback the audit's verdict activated (D-155): on fresh QAOA MaxCut circuits, can a search over the passes of existing tools match or beat GUOQ? It runs on the P0 harness beside P0d during the P2 hold (D-156), under a kill rule, a budget and a held-out set fixed before any run.

Status: draft

**Goal.** In at most 10 working days and 30 wall-clock compute hours, answer one question: on fresh `qaoa` circuits, does a search over existing tools' passes (the P0 portfolio plus pass ordering) beat GUOQ by at least 1% in geometric-mean CNOT ratio, with a bootstrap 95% confidence lower bound above 0, or match GUOQ's quality in less time, at time budgets declared below? The answer decides whether the benchmark-discovery pilot (D-089) has a live case on one family, or the null result is published beside the audit's.

**Why now.** D-155 kept the fallback as registered. The evidence for and against is thin. P0 gave the portfolio no gain on `qaoa` (all four circuits tied the baseline) while GUOQ at 300 s was 11% to 21% lower on three of them (123 against 144 at 12 qubits, 180 against 228 at 16, 48 against 56 at 8). One Qiskit pass closed GUOQ's `vqe_two_local` gap in about a second (D-144), so a single pass may do the same here, and the plan tests for that first. Odds at D-144: 10% to 15% for a verified win, about 30% for equal quality in less time (assumptions, replaced by measurement). The reason to run it anyway is cost: no platform code and no model spend, and a null is a published result the D-097 preprint already wants.

**Architecture.** A new package `spikes/qopt_qaoa/` imports the P0 harness (`run_text`, `strip_measurements`, `cx_count`), `normalise`, the QCEC hard-wall worker and the bootstrap in `portfolio.py` from `spikes/qopt_p0/`, and does not import `spikes/qopt_audit/` (P0c will change its oracle, and a frozen rule must not move with it; P0e keeps its own copy of the re-decide step, pinned by tests). A seeded generator writes the QAOA circuits; GUOQ runs in the P0 container at a declared wall-clock budget; the candidate is a budgeted search over a pool of named passes; the best single pass is the second baseline; every output is checked by QCEC; a pure function applies the rule to the results.

**Tech stack.** Python 3.12 to 3.13, qiskit 2.5.2, pytket 2.18.4, pyzx 0.10.7, mqt.qcec 3.10.2 (pinned in `spikes/qopt_p0/requirements.txt`), networkx (pinned at Task 1 to the installed release), numpy, psutil. GUOQ is `wisq` 0.2.7 at commit `97c12a5`, built by `spikes/qopt_p0/guoq/Dockerfile` (Docker, Linux container).

**Spec.** `docs/history/2026-10-14-reshape-decision.md` (option (b) and "Why (b) is weaker than it looks"), D-144, D-155 to D-158, `docs/history/2026-10-28-audit-spike.md`, `docs/plans/P0b-audit-spike.md` (style and oracle), `docs/plans/P0c-tolerance-repair.md` (the run changes adopted below), and the rule below.

**Estimate.** 3 to 5 founder hours (assumption, replaced by measurement): approving this plan, the frozen sets and the freeze, reading the result and the decision. The compute is unattended and goes on the compute line. No platform code, no model calls, no cloud spend: $0.

**Not in scope.** No change to P3 or P4, whatever the outcome; the founder decides afterwards. No new rewrite rules and no model-written passes (that is P3's job): the candidate is built only from passes the pinned tools already ship. No problem-aware synthesis: the candidate sees the circuit, not the graph. Nothing is posted upstream and no upstream contact is made from here (D-157): a lead goes to the founder with a draft.

## Step 0: feasibility (done before this plan, on 2026-10-28)

GUOQ runs locally through the P0 container (`spikes/qopt_p0/guoq/`, image `ohrf-wisq:97c12a5`, built two weeks earlier) and its outputs go through the P0 verifier. Two throwaway circuits (seeded 3-regular graphs; they are in neither set), input CNOT counts from the textbook form:

| Circuit | Input | Qiskit L3 | GUOQ 5 s | GUOQ 15 s | GUOQ 60 s | GUOQ 300 s | QCEC on GUOQ 60 s |
|---|---|---|---|---|---|---|---|
| 10 qubits, `p` = 2 | 60 | 60 | 56 | 56 | 56 | 56 | `equivalent_up_to_global_phase`, 0.3 s |
| 22 qubits, `p` = 3 | 198 | 198 | 197 | 195 | 195 | 195 | `equivalent_up_to_global_phase`, 0.5 s |

What step 0 shows, and what it changed in this plan:

- **GUOQ runs here** and a run's wall-clock is its budget plus about 3 s. It uses one core (102% CPU) and 0.87 GB at 22 qubits. QCEC decides a 22-qubit output in half a second, so the large sizes are measurable (for these circuits).
- **GUOQ is converged by 15 s on these circuits.** Its 300 s result equals its 15 s result, so "quality in less time" against a 300 s GUOQ is a test of matching a converged tool, and `B_short` is 15 s, not 60 s. GUOQ's gain here is small (7% and 1.5%), against 11% to 21% on P0's `mqt.bench` `qaoa` circuits at 300 s: the fresh textbook circuits leave less room, which makes a 1% margin harder to resolve (see Power). Two circuits say little; the development set measures it.
- **One slow start.** The first call took 325 s for a 60 s budget: four minutes passed before the container started, cause not found (the other runs took the budget plus 3 s, and a rebuild check takes 2 s). The runner logs the start delay of every job.
- Step 0 used about 0.15 wall-clock hours of runs (counted against the 30). It ran before any tag and is disclosed as such.

## The rule (fixed before the run)

Day 0 is the day the tag `qaoa-prereg` is pushed. Day 10 (working days) decides. The held-out set is run once, after the tag `qaoa-freeze`.

For each held-out circuit `i` and each budget B, let `g(i, B)` be the CNOT count of GUOQ's output run for B seconds of wall-clock, and `c(i, B)` the candidate's, both counted by `harness.cx_count` after rebasing to `{cx, rz, sx, x}`. An output that is not verified (below) scores the circuit's input CNOT count, for GUOQ as for the candidate. The ratio is `c / g`; the **gain** is 1 minus the geometric mean of `c / g` over the held-out circuits, and its interval is the 95% percentile bootstrap of `portfolio.bootstrap_ci` (10,000 resamples of circuits, seed in `frozen.py`).

**Declared budgets.** `B_short` = 15 s and `B_long` = 300 s (P0 ran GUOQ at 300 s, `GUOQ_BUDGET_S`; step 0 found GUOQ converged by 15 s on two circuits), one worker each, the same CPU allowance (below).

**Pass** when, on the held-out set, at least one of:

- **(Q) Quality.** At `B_long`: gain at least 0.01 and the lower bound of the gain above 0.
- **(T) Time.** Candidate at `B_short` against GUOQ at `B_long`: the geometric-mean ratio at most 1.00 and the upper bound of the ratio at most 1.01 (not worse than GUOQ by more than 1% with 95% confidence, in one twentieth of the time).

and **(S)** in either case, the candidate beats the best single existing pass `S*` (chosen on the development set and frozen, below) at the same budget: the gain over `S*` has a lower bound above 0. This is the `vqe_two_local` lesson: a win that one existing pass already gives is not a result of the search.

**Outcomes.**

| Outcome | When | What the lab does |
|---|---|---|
| `pass` | (Q) or (T), and (S) | Report to the founder; no plan changes until the founder decides |
| `single-pass` | `S*` alone meets (Q) or (T) | Publish: an existing pass matches GUOQ here, and which one |
| `null` | otherwise | Publish beside the audit's null, in `docs/history/` |

An outcome is never decided on the development set. If fewer than 80% of held-out circuits have a verified output on either side, the record says so and adds the verified-only result as a sensitivity row; the rule above still decides.

### What counts as verified

An output is verified when QCEC 3.10.2 answers `equivalent` or `equivalent_up_to_global_phase` after `normalise` (D-082, D-113), with the audit's re-decide step: a default answer that is not decided is re-decided once by the alternating checker alone, and `hard_timeout`, `strict_parse`, `no_information` and `probably_*` answers are unverified and counted by size, as in P0b. Every verified output is also re-checked with QCEC 3.11.0 (the `audit-addendum` check); a contradiction by 3.11.0 makes the output unverified.

### Power

The held-out pool holds 324 circuits, all generated and hashed at `qaoa-prereg`. The number actually run, `N_heldout`, is fixed at `qaoa-freeze` from the development set, before any held-out circuit is run: `N_heldout = min(max(circuits_needed(s, 1%), 108), N_cap, 324)`. Here `s` is the standard deviation of the log ratio `c / g` at `B_long` over the development set (`reference.log_sd`, candidate against GUOQ), `circuits_needed` is the P0 formula for 80% power to find a true gain of 1% with the lower bound above 0, 108 is the floor, and `N_cap` is the number of circuits whose measured development cost (worker-seconds per circuit for GUOQ, the candidate, `S*` and verification, both budgets) fits `HELD_OUT_CAP_S` at `WORKERS_DEFAULT` workers. If `N_cap` is under 108 the floor cannot be met, `N_heldout = N_cap`, and the record says so. The circuits run are the first `N_heldout` of the pool in a stratified, seeded order, so the choice cannot depend on any held-out result and any first `N` is balanced: the 27 strata (size by graph kind, 12 circuits each) are ordered by a hash of `HELD_OUT_ORDER_SEED` and the stratum, the circuits inside each stratum by a hash of the seed and the circuit's name, and the order is round-robin over the strata (the first circuit of every stratum, then the second of every stratum, and so on). Any first `N` therefore holds counts per stratum that differ by at most 1. The rank is stored in `held_out.json`. With the floor alone (108), a true gain of 1% is found with 80% power only if `s` is at most about 0.036. P0's four `qaoa` rows (GUOQ against the baseline) have a log-ratio spread near 0.10, which would call for far more than the pool or the cap allow, so a true gain of 1% would very likely not reach the lower bound above 0; a gain of about 3% would. The 1% bar is the founder's (D-144) and is kept. The record reports the measured `s`, `N_heldout` and the smallest gain that sample could have found. A null with a wide interval is a null of this sample, not proof of no effect.

## Scope decisions

- **Circuits.** QAOA MaxCut, unweighted, on seeded graphs: random regular (degree 3 and 4) and Erdos-Renyi (mean degree 3.5, no isolated vertex), at 6 to 22 qubits (even sizes), depth `p` of 1 to 4, per-layer `gamma` and `beta` drawn uniformly from `[0.05, pi - 0.05]`. Each layer applies `cx, rz, cx` on every edge in sorted edge order, then `rx` on every qubit; the first step is `h` on every qubit. The text is lowered to `qelib1` gates by a level-0 transpile, as P0 did, on one register. A circuit is a pure function of `(set, size, kind, depth)`.
- **Two sets, frozen and hashed before any run.** Development: 36 circuits (4 per size). Held-out pool: 324 (36 per size: every kind at every depth, three replicates), of which `N_heldout` (at least 108) are run, chosen at `qaoa-freeze` (see Power). The two sets use different seeds and share no graph. Manifests `dev.json` and `held_out.json` hold the parameters and the sha256 of each stripped text (the hash the harness checks); the circuit files are committed.
- **GUOQ.** `wisq` 0.2.7, objective `TWO_Q`, gate set `IBMN`, input rebased to `{cx, rz, sx, x}` without optimising (`guoq_inputs.rebase`), `--opt_timeout` = the budget. One run per circuit and budget on the held-out set. Its variance is measured on the development set (three runs of `B_long` on 12 circuits) and reported.
- **Candidate.** A budgeted search over a pool of named passes (below). It may use any number of passes and any order up to the length limit, and may use tools in sequence through QASM. Its clock starts when the circuit is handed over and stops at the budget; verifying the finished output is outside the budget, and so is GUOQ's.
- **Baselines.** (1) GUOQ at both budgets. (2) `S*`, the best single pool entry, run compute-matched to the budget with extra seeds as in `matched_runs` where the pass takes a seed. (3) The P0 portfolio (the `CHAINS2` chains and PyZX) as context only.
- **Compute.** At most 30 wall-clock hours of runs in total (the sum of the batches' lengths in `runs.jsonl`, step 0 included), batches of at most 4 hours, no cloud spend, and no model calls. Planned: development at most 10 hours, the held-out run at most 12, a reserve of 8 for a rerun after a crash and the GUOQ repeats. Worker count is set under "Sharing the PC".
- **Time.** At most 10 working days from the tag. The development phase ends by day 6; if the search is not frozen then, what exists is frozen.
- **What a pass or null changes.** Nothing in P3 or P4 until the founder decides. A pass is evidence that a discovery test on `qaoa` is worth a plan; it is not a plan.

## The pass pool and the search

The pool is a list of named passes, fixed at the tag in `frozen.py` and checked against the pinned versions by a test (a name the pinned tool does not have is removed before the tag, not after). The offered pool:

- **Qiskit 2.5.2:** `Optimize1qGatesDecomposition`, `CommutativeCancellation`, `CommutativeInverseCancellation`, `InverseCancellation`, `Collect2qBlocks` with `ConsolidateBlocks` and `UnitarySynthesis`, `CollectLinearFunctions` with `HighLevelSynthesis` (the pass that won on `vqe_two_local`), and the level-3 transpile as one macro step.
- **pytket 2.18.4:** `FullPeepholeOptimise` (with and without swaps), `CliffordSimp`, `KAKDecomposition`, `CommuteThroughMultis`, `RemoveRedundancies`, `ZZPhaseToRz`, and the Pauli-gadget passes (`PauliSimp`, `GreedyPauliSimp`) where they accept the circuit.
- **PyZX 0.10.7:** `full_reduce`, `clifford_simp`, behind a 60 s wall per call (P0c, run change 3).

The search is a beam search over sequences of at most 6 steps (width 4) with random restarts, scoring by CNOT count and then total gate count, until the budget ends. Each step is a pass call on the QASM text of the best states. The width, length limit, restart rule and the order priors learned on the development set are written to `search_config.json` and hashed at `qaoa-freeze`. The finished search proposes its five best distinct states; the first one QCEC verifies, in order, is the output (none verified is a loss for that circuit). The search is allowed to find an unsound pass output: QCEC refuses it, and the case is a lead (below).

## Run changes adopted from P0c (rules fixed by the tag; code built after it)

The five changes P0c fixes for the audit's next run, applied here because the same failures can occur. As in the audit (tag `audit-prereg` froze the parameters and the tolerance table, the code followed), the tag fixes what each rule says: the text below and the values in `frozen.py`. Tasks 4 to 9 build and test each rule after the tag, test-first; a test pins a rule and never changes it.

1. **A witness with several states.** A candidate output that QCEC calls `not_equivalent` is a lead. Its witness is any of at least 3 seeded random product states or 2 computational-basis states (all zeros, and one fixed seeded bit string) with infidelity above `WITNESS_MIN` (1e-11, the audit's value); the record keeps every state's gap. The seeds are in `frozen.py`.
2. **Known mechanisms stop early.** A lead whose first breaking pass and reduced shape match an open known issue (Qiskit/qiskit#16864 through `TwoQubitPeepholeOptimization`, Qiskit/qiskit#17315 through `CommutativeCancellation`) is logged as a known duplicate and not reduced further. The match rule is P0c's, tested here on the audit's reproducers in the repository.
3. **A wall on PyZX.** 60 s per PyZX observation, in the search and in the baselines. Other tools keep the P0 limits.
4. **The second opinion.** For a `not_equivalent` answer, the second opinion is the ZX checker alone, where `not_equivalent` or `probably_not_equivalent` agrees (the audit's 20 disagreements were all `probably_not_equivalent` from ZX, in 60 of 60 calls at most 6.4 s). A test on a dropped `cu1(0.0001)` passes 15 of 15 full-suite runs before the tag. The answer feeds leads only: a disagreement is `oracle_disagreement`, and the output stays unverified either way.
5. **A stall alarm.** A heartbeat file records the time the last batch ended and the time triage last finished, in UTC. While a run is open, a check run hourly by the Windows task scheduler puts one line in the sessions board if either time is over 24 hours old (a scheduled task does not edit tracked files, so the line goes to the board and to the working notes, and the chat that sees it copies it into `docs/STATUS.md`). A test sets a heartbeat 25 hours old and checks that the line appears.

**Triage of every batch as it is logged (D-156).** Each batch is triaged the moment it is written, not at the end of the run. Every observation carries a UTC time. A lead that needs a person (a `not_equivalent` that is not a known duplicate, a crash of a tool on a valid input, an output QCEC 3.11.0 contradicts) is written to `attention.jsonl` with `seen_utc` and `due_by` 72 hours after, and a filing draft is ready by `due_by`. The founder files or declines under D-157. Leads never count toward the rule above.

## Sharing the PC

P0d runs at the same time, and D-149 sets 3 agent runs and 2 jobs. P0d's runs are model calls: little CPU and no containers. P0e's workers are jobs (a GUOQ container, a QCEC check or a search process). So that the two together stay within D-149:

- P0e runs **2 workers** by default and **3 only** when the check below finds the PC idle. It never runs a fourth.
- A guard, `slots.py`, runs before every job. It counts P0e's own live jobs (a registry of process ids and container names written at start, removed at exit, so a stray is visible), reads the sessions board for a P0d entry whose status is `running job`, and samples CPU for 30 seconds with `psutil`. It refuses a third job while P0d is running or the CPU is above 60% outside P0e's own jobs, and refuses any job when free memory is under 8 GB. Every refusal is logged with the time.
- Each worker gets a fixed allowance for both GUOQ and the candidate: 1 CPU (a container `--cpus 1`; the search process pinned to one logical CPU with `psutil` affinity) and 4 GB. Step 0 measured GUOQ at 102% CPU and 0.87 GB on a 22-qubit circuit, so it is a one-core program and the allowance does not handicap it. The two sides are compared at equal wall-clock and equal CPUs; the CPU seconds each used are logged as well.
- The PC stays awake during runs (the lab's keep-awake setting). After every background batch, list Python and container processes and kill strays (the P0 lesson, D-141).
- P0d's files (`.local/p0d`, `spike/p0d`) and `spikes/qopt_audit/` are never opened for writing by P0e.

## Frozen parameters

Fixed by the commit tagged `qaoa-prereg`. A test fails if this block and `spikes/qopt_qaoa/frozen.py` differ. A change after the tag voids the run, except the disclosed kind below.

```python
"""QAOA explore track parameters fixed before the run (tag `qaoa-prereg`). Changing one after the tag voids the run."""
import math

TOOL_PINS = {"qiskit": "2.5.2", "pytket": "2.18.4", "pyzx": "0.10.7", "mqt.qcec": "3.10.2", "networkx": "3.7", "psutil": "7.2.2"}
RECHECK_QCEC = "3.11.0"
GUOQ = {"wisq": "0.2.7", "commit": "97c12a5", "gateset": "IBMN", "objective": "TWO_Q"}
SIZES = (6, 8, 10, 12, 14, 16, 18, 20, 22)
GRAPH_KINDS = ("regular3", "regular4", "erdos_renyi")
ER_MEAN_DEGREE = 3.5
DEPTHS = (1, 2, 3, 4)
DEV_PER_SIZE = 4
HELD_OUT_POOL_PER_SIZE = 36  # 3 kinds x 4 depths x 3 replicates
HELD_OUT_MIN = 108
HELD_OUT_ORDER_SEED = 20261029
POWER_EFFECT = 0.01  # the gain the sample size is chosen to find with 80% power
ANGLE_RANGE = (0.05, math.pi - 0.05)
CIRCUIT_SEED = 20261028
BUDGETS_S = (15, 300)
B_SHORT_S, B_LONG_S = BUDGETS_S
GAIN_MIN = 0.01
GAIN_LOWER = 0.0
TIME_RATIO_MAX = 1.00
TIME_RATIO_UPPER_MAX = 1.01
BOOTSTRAP_N = 10000
BOOTSTRAP_SEED = 20261028
VERIFIED_FLOOR = 0.80
SEARCH_STEPS_MAX = 6
SEARCH_BEAM = 4
SEARCH_PROPOSALS = 5
GUOQ_REPEAT_CIRCUITS = 12
GUOQ_REPEATS = 3
QCEC_TIMEOUT_S = 60
QCEC_HARD_WALL_S = 120
PYZX_WALL_S = 60
CONFIRM_RUNS = 2
WITNESS_MIN = 1e-11
WITNESS_RANDOM_SEEDS = (11, 12, 13)
WITNESS_BASIS_SEED = 14
KNOWN_ISSUES = ("Qiskit/qiskit#16864", "Qiskit/qiskit#17315")
WORKERS_DEFAULT = 2
WORKERS_IDLE_MAX = 3
CPUS_PER_WORKER = 1
MEMORY_PER_WORKER_GB = 4
IDLE_CPU_PCT = 60
FREE_MEMORY_MIN_GB = 8
COMPUTE_CAP_S = 30 * 3600
RUN_CAP_S = 4 * 3600
DEV_CAP_S = 10 * 3600
HELD_OUT_CAP_S = 12 * 3600
WORKING_DAYS = 10
FREEZE_BY_DAY = 6
DUE_BY_HOURS = 72
STALL_HOURS = 24
```

`search_config.json` (the pool, `S*` and the search parameters learned on the development set) is frozen by the second tag, `qaoa-freeze`, before the held-out circuits are first run. The held-out circuits are hashed at `qaoa-prereg` but nothing about their results is seen before `qaoa-freeze`: GUOQ's held-out runs start after it.

**Disclosed changes after the tag.** Tasks 4 to 9 are written after the tag; they implement the rules in this plan and are listed in the record. A change that does not alter the rule, a parameter above, the pool or the generator's definition (a bug fix, a changed path, the version of a tool used only to check an output) is allowed and is listed in the record under "Changes after the tag".

## Conventions

- Code in `spikes/qopt_qaoa/`, tests in `spikes/qopt_qaoa/tests/`. Run with the P0 environment: `python -m pytest spikes/qopt_qaoa -q` from the repository root.
- Inputs are single-register OpenQASM 2.0 on the standard `qelib1.inc` gates, without measurements. Every run script has a `__main__` guard (QCEC's worker is spawned).
- Every circuit and every GUOQ and candidate output is written to disk beside the log, with its UTC start and end times.
- Only `equivalent` and `equivalent_up_to_global_phase` are verified (D-082). Every other outcome is unverified and counted by size.
- Hours are logged per batch in `runs.jsonl` and, for the founder's and the build's time, in the working notes.
- Each task ends with a subject-only commit by the lab's identity, no trailers. Pull requests are opened and never merged by the build; the founder reviews and merges as a merge commit.

## Files

| File | Purpose | Task |
|---|---|---|
| `spikes/qopt_qaoa/frozen.py` | The parameters above | 1 |
| `spikes/qopt_qaoa/make_qaoa.py`, `circuits/`, `dev.json`, `held_out.json` | The generator, the dev set, the held-out pool with its order, their hashes | 2 |
| `spikes/qopt_qaoa/sample.py` | `N_heldout` from the development set | 2 |
| `spikes/qopt_qaoa/oracle.py` | Verification: re-decide, QCEC 3.11.0 re-check, witness, second opinion | 4 |
| `spikes/qopt_qaoa/slots.py` | The PC-sharing guard and the job registry | 5 |
| `spikes/qopt_qaoa/guoq.py` | GUOQ in the container at a wall-clock budget, with its CPU allowance | 6 |
| `spikes/qopt_qaoa/passes.py`, `search.py` | The pool and the budgeted search | 7 |
| `spikes/qopt_qaoa/score.py` | The ratios, the bootstrap, the rule and its outcome | 8 |
| `spikes/qopt_qaoa/run.py`, `triage.py`, `heartbeat.py` | The batch runner, per-batch triage, the stall alarm | 9 |
| `spikes/qopt_qaoa/search_config.json` | The frozen search and `S*` | 11 |
| `docs/history/<date>-qaoa-explore.md` | The record of the result and the decision | 13 |

## Tasks

Each task: failing test, see it fail, implement, see it pass, subject-only commit. Tasks 1 and 2 come before the tag; Tasks 4 to 9 come after it and before the first run. No compute is run before the oracle, the PC guard and the runner pass their tests (step 0 excepted).

1. **Frozen parameters.** Write `frozen.py` as the block above; a test fails if the block in this plan and the file differ, and if a pin does not match the installed tool.
2. **The generator and the two sets** (a 324-circuit held-out pool with its seeded order, and the 36 development circuits). `make_qaoa.generate(set, size, kind, depth) -> str` is a pure function of its arguments and `CIRCUIT_SEED`; tests: the same call twice gives the same text, no two circuits share a graph, every qubit has an edge, every circuit parses in Qiskit and tket and PyZX's reader, dev and held-out share no hash. Write the circuits and the two manifests.
3. **Tag `qaoa-prereg`.** Commit the plan, the frozen parameters, the generator, both manifests and the held-out hashes (the pool and its stratified order); run the suite of Tasks 1 and 2; push the tag; anchor it with a third-party timestamp (a public archive record with a DOI, or an OpenTimestamps proof committed beside it). Record the decision. Day 0.
4. **The oracle.** Port the audit's re-decide step with tests that pin its behaviour; add the QCEC 3.11.0 re-check, the multi-state witness (run change 1) and the second opinion (run change 4, with the 15 of 15 test on a dropped `cu1(0.0001)`).
5. **The PC guard.** `slots.py` with the registry, the board read, the CPU and memory samples, and the refusal log; tests with fake samples for each refusal, and a test that a fourth job is never allowed.
6. **GUOQ at a budget.** Run the container for one circuit with `--cpus` and `--memory`, record UTC start and end, wall-clock and exit status; tests with a stub container; one real run at 10 s on a throwaway circuit.
7. **The pool and the search.** Check every pool name against the pinned versions; the PyZX wall (run change 3); the beam search with an injectable clock; tests that the search stops at its budget, never returns an unverified output as verified, and returns the five best distinct states.
8. **The score and the rule.** `score.py` computes ratios, gains and intervals with `portfolio.bootstrap_ci`, and returns the outcome; tests on fixed tables for each outcome, for the unverified-scores-the-input rule on both sides, and for the sensitivity row.
9. **The runner, triage and the stall alarm.** Batches write `runs.jsonl` (UTC, cost), triage runs after each batch (run changes 2 and 5, and the 72 hour `due_by`), the heartbeat and its hourly check; tests: a 25-hour-old heartbeat puts a line in a fake board; a lead gets `due_by` 72 hours after `seen_utc`; a known duplicate is not reduced.
10. **Development.** GUOQ at both budgets on the 36 development circuits; the GUOQ repeats; every pool entry alone (to choose `S*`); the search developed and tuned on this set only. Triage each batch as it lands.
11. **Freeze.** Compute `N_heldout` from the development set (`sample.n_heldout`) and write it with `search_config.json` (the pool, `S*`, the search parameters), hash it, commit, tag `qaoa-freeze`, push. By day 6.
12. **Held-out run.** GUOQ at both budgets, the candidate at both, and `S*` at both, on the `N_heldout` held-out circuits (first in the seeded order), once. A crash is rerun from the log; nothing is retuned.
13. **Record.** `docs/history/<date>-qaoa-explore.md` with every number: the outcome, the intervals, the spread `s` and the smallest gain the sample could find, the verified shares by size, the compute hours against 30, the founder's and the build's hours, the PC guard's refusals, every lead with its `seen_utc` and `due_by`, "Changes after the tag", and the decision.

## What would reverse this

If step 0 shows GUOQ cannot run here, the question changes and the founder decides before any plan. If the verified share of GUOQ's 18 to 22 qubit outputs is under half on the first development batch (QCEC cannot decide them), the sizes above 16 are not measurable, and the founder is asked before the tag whether to cut the sets at 16 qubits; that is a plan revision made before the tag, not a result. If a live chat or the founder moves P0d's load onto the PC so that two workers cannot run, the held-out cap in compute hours still binds and the work waits.

## Self-review

(Filled when the plan is approved.)
