# P0b Toolchain audit spike implementation plan

**Goal.** In two weeks, test whether fuzzing Qiskit, pytket and PyZX with large and boundary-angle circuits, and proving every output with QCEC, finds a wrong output or an upstream-accepted wrong-output issue that earlier compiler fuzzers did not. The answer decides whether the toolchain audit (D-100, D-144) can carry the lab's first project or the fallback, option (b) on `qaoa`, is added. Decision D-145.

**Why now.** D-144 chose the audit as the first project on odds taken from assumption (15% to 20% for a real wrong-output bug). Before any P3 or P4 plan is rewritten around it, two weeks of cheap fuzzing on the P0 harness measure whether those odds hold. The prior art (`docs/history/2026-10-14-audit-prior-art.md`) found gaps in what published fuzzers tried, not evidence of a bug; P0 proved no output wrong in 10,421.

**Architecture.** A new package `spikes/qopt_audit/` imports the P0 harness (`run_text`, `strip_measurements`), `normalise` and the QCEC hard-wall worker from `spikes/qopt_p0/`. A seeded schedule of circuits goes through the four tool runs; each output is checked by QCEC; every `not_equivalent` is confirmed twice, given a second opinion by a different checker, measured against the tool's recorded tolerance, and reduced to a minimal reproducer. A pure function applies the kill rule to the findings ledger.

**Tech stack.** Python 3.12 to 3.13, qiskit 2.5.2, pytket 2.18.4, pyzx 0.10.7, mqt.qcec 3.10.2 (pinned in `spikes/qopt_p0/requirements.txt`), mqt.bench 2.3.0 only to write the base circuits once, numpy.

**Spec.** `docs/history/2026-10-14-reshape-decision.md` (D-144), `docs/history/2026-10-14-audit-prior-art.md`, and the rule below.

**Estimate.** 3 to 6 founder hours (assumption, replaced by measurement): approving each filing, reading findings, the decision. The 30 hours of compute are unattended and go on the compute line, as in P0. No platform code, no P3 or P4 change.

## The kill rule (fixed before the run)

Day 0 is the day the tag `audit-prereg` is pushed. Day 14 decides.

**Pass** when, by day 14, at least one of:

- **(i)** One new **wrong output**: an output QCEC proves not equivalent that meets every condition in "Evidence for a wrong output" below and has a reproducer of at most 50 gates.
- **(ii)** Two **upstream-accepted wrong-output issues**: each meets the same evidence conditions (the 50-gate limit does not apply), was filed by day 10, and by day 14 the maintainers have confirmed it as a bug, labelled it a bug, or fixed it.

**Fallback** otherwise: add option (b), narrow to `qaoa` and beat GUOQ on fresh circuits, as an explore track on the same harness (D-144). No P3 or P4 change follows from either outcome in this spike; the founder takes that decision afterwards.

What does not count toward (i) or (ii): crashes, reader or parser errors and documentation issues (earlier fuzzers find these routinely, and they do not show what this audit claims to add, which is proving outputs wrong). They are still logged and, when real, reported upstream. Also not counted: the four P0 leads (PyZX scientific-notation reader, pytket register reorder, the undecided `qft-16` output, the 641 `no_information` outputs), and any issue whose search found a duplicate.

### Evidence for a wrong output

All of these, recorded in the ledger (`ledger.py`):

1. The input QASM is accepted by the tool's reader and the output passes `normalise` (no `// o`, no hidden layout).
2. QCEC answers `not_equivalent` on two runs in fresh worker processes (default configuration).
3. A second opinion agrees: QCEC with the alternating checker alone returns `not_equivalent`, and for 10 qubits or fewer a dense operator comparison (global phase removed) also shows a difference. A disagreement is recorded as `oracle_disagreement`, never as a wrong output; it is a lead on QCEC itself.
4. **Tolerance rule.** The phase-optimised operator-norm distance D between input and output, computed on the reduced reproducer, exceeds `G * TOLERANCE[tool]`, where G is the reproducer's gate count and `TOLERANCE` is the table below, measured at the pinned versions (Task 2). A rotation dropped within the tool's recorded tolerance is documented behaviour and is recorded as `within_tolerance`, never as a wrong output. A reproducer over 10 qubits has no computed D and is not counted until it is reduced below 11 qubits.
5. The reproducer is deterministic: it reproduces with the same seed, in a fresh process, and on the latest released version of the tool. The result on the tool's main branch is recorded.
6. For (ii), before filing, the tool's tracker has been searched for duplicates and the search link is recorded in the ledger. An issue without that link does not count.

## Scope decisions (D-145)

- **Tools.** Qiskit 2.5.2 at level 3 (seed 1), pytket 2.18.4 `FullPeepholeOptimise` with and without swaps, PyZX 0.10.7, exactly as P0's `run_text`, checked by QCEC 3.10.2.
- **Generator.** Structured plus boundary angles. 40 base circuits (the 8 P0 families at 6, 10, 14, 18 and 22 qubits, from `mqt.bench` 2.3.0, committed with hashes) with boundary-angle variants, interleaved one for one with seeded random circuits of 6 to 20 qubits and 50 to 600 gates. Cases are drawn in a fixed order until the cap is reached.
- **Compute cap.** 30 wall-clock hours in total, runs of at most 4 hours, at most 3 worker processes, local only, no cloud spend, QCEC hard wall 120 s.
- **Kill rule.** As above.

## Frozen parameters

Fixed by the commit tagged `audit-prereg`. A test fails if this block and `spikes/qopt_audit/frozen.py` differ. A change after the tag voids the run, except the disclosed kind below.

```python
"""Audit spike parameters fixed before the run (tag `audit-prereg`). Changing one after the tag voids the run."""
import math

TOOL_PINS = {"qiskit": "2.5.2", "pytket": "2.18.4", "pyzx": "0.10.7", "mqt.qcec": "3.10.2", "mqt.bench": "2.3.0"}
TOOLS = ("qiskit", "tket-swaps", "tket-noswaps", "pyzx")
QISKIT_SEED = 1
BASE_FAMILIES = ("qft", "qpeexact", "qaoa", "vqe_two_local", "graphstate", "wstate", "dj", "qnn")
BASE_SIZES = (6, 10, 14, 18, 22)
BOUNDARY_RATE = 0.5
BOUNDARY_ANGLES = tuple(
    [1e-12, 1e-9, 9.6e-05, 1e-05, 1e-04, math.pi / 4, math.pi / 2, math.pi, 3 * math.pi / 2, 2 * math.pi]
    + [2 * math.pi / 2 ** k for k in range(3, 13)]
    + [math.pi / 2 + 1e-9, math.pi / 2 - 1e-9, math.pi + 1e-9, math.pi - 1e-9]
)
RANDOM_QUBITS = (6, 20)
RANDOM_GATES = (50, 600)
SCHEDULE_SEED = 20261014
COMPUTE_CAP_S = 30 * 3600
RUN_CAP_S = 4 * 3600
WORKERS = 3
QCEC_TIMEOUT_S = 60
QCEC_HARD_WALL_S = 120
CONFIRM_RUNS = 2
DENSE_MAX_QUBITS = 10
REDUCED_MAX_GATES = 50
REDUCE_MAX_CALLS = 300
TOLERANCE = {"qiskit": 1e-05, "tket-swaps": 1e-04, "tket-noswaps": 1e-04, "pyzx": 1e-09}
FILE_BY_DAY = 10
DECIDE_DAY = 14
```

`TOLERANCE` is ten times the largest rotation each tool dropped in exact mode when measured on 2026-10-14 (Qiskit about 1e-6 on a controlled phase, 1e-8 on `rz`; tket 1e-5 on `rz` and `rx`; PyZX none, with a floor of 1e-9 for rounding), rounded to a power of ten. Task 2 re-measures it and fails if a pinned tool now drops more than the table says.

**Disclosed changes after the tag.** A change that does not alter the rule, a parameter above, the schedule order or the generator's definition (a bug fix, a changed path, the version of a tool used only to check a reproducer) is allowed and is listed in the report under "Changes after the tag".

## Conventions

- Code in `spikes/qopt_audit/`, tests in `spikes/qopt_audit/tests/`. Run with the P0 environment: `python -m pytest spikes/qopt_audit -q` from the repository root.
- Inputs are single-register OpenQASM 2.0 on the standard `qelib1.inc` gates only (tket cannot read others), without measurements.
- Every circuit is a pure function of its `Case` (kind, name, seed), so every finding replays from three values. The run writes each circuit it uses to disk beside its log.
- Only `equivalent` and `equivalent_up_to_global_phase` are verified (D-082). Every other QCEC outcome, `hard_timeout` and `strict_parse` are unverified and are counted, by size, in the report: the share QCEC cannot decide is itself a result.
- After every background batch, list Python processes and kill strays (the P0 lesson, D-141). Keep the PC awake during a batch.
- Each task ends with a subject-only commit.

## Files

| File | Purpose | Task |
|---|---|---|
| `spikes/qopt_p0/verify.py` | `_Worker.stop` fix for a worker that never started | 1 |
| `spikes/qopt_audit/frozen.py` | The parameters above | 2 |
| `spikes/qopt_audit/tolerance.py` | Re-measures the drop threshold of each tool | 2 |
| `spikes/qopt_audit/bases.py`, `bases/`, `bases.json` | The 40 base circuits, their generator and hashes | 3 |
| `spikes/qopt_audit/generate.py` | Random and boundary-angle circuits, the schedule | 3 |
| `spikes/qopt_audit/oracle.py` | Run a tool, check the output, confirm, classify | 4 |
| `spikes/qopt_audit/reduce.py` | Gate-level reduction of a reproducer | 5 |
| `spikes/qopt_audit/ledger.py` | The findings ledger and the kill rule | 6 |
| `spikes/qopt_audit/run.py` | The batch runner, the log, the report | 7 |
| `spikes/qopt_audit/findings/<id>/` | One folder per finding: input, command, versions, search link | 8 |
| `docs/history/<date>-audit-spike.md` | The record of the result and the decision | 8 |

## Tasks

### Task 1: Fix `_Worker.stop` for a worker that never started

`_start` builds the process before it starts it, so a failed start, or the `atexit` call, can find an unstarted `Process`; `kill()` then raises `AttributeError`. Done on the branch before the tag.

**Files:** Modify `spikes/qopt_p0/verify.py`; Test `spikes/qopt_p0/tests/test_verify.py`.

- [x] **Failing test** (`test_stopping_a_worker_that_never_started_does_not_raise`): create a spawn `Process`, assign it to `worker._proc` without starting it, call `stop()`, assert `_proc` and `_conn` are `None`; a fresh `_Worker().stop()` must also pass.
- [x] **Run:** fails with `AttributeError: 'NoneType' object has no attribute 'kill'`.
- [x] **Fix:** in `stop`, act only when `self._proc.pid is not None` (the pid stays `None` until the process has started).
- [x] **Run:** `python -m pytest spikes/qopt_p0/tests/test_verify.py -q`, 9 passed.
- [x] **Commit:** `Make _Worker.stop safe when the worker never started`.

### Task 2: Frozen parameters and the tolerance table

**Files:** Create `spikes/qopt_audit/__init__.py`, `frozen.py`, `tolerance.py`; Test `spikes/qopt_audit/tests/test_frozen.py`.

**Interfaces.** Produces `frozen.*` as in the block above, and `tolerance.largest_drop(tool: str) -> float`: the largest rotation angle, on a grid of 1e-1 to 1e-16, that the tool's output changes by more than half the angle (rotations `rz`, `rx` and `cu1` between Hadamards, measured by the phase-optimised operator-norm distance); 0.0 if none; tools whose reader raises at an angle skip it.

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from spikes.qopt_audit import frozen
from spikes.qopt_audit.tolerance import largest_drop

HERE = Path(__file__).resolve().parents[1]
PLAN = HERE.parents[1] / "docs" / "plans" / "P0b-audit-spike.md"


def test_the_plan_carries_the_frozen_parameters_verbatim():
    text = (HERE / "frozen.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert text.strip() in PLAN.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_the_compute_and_worker_caps_are_the_registered_ones():
    assert frozen.COMPUTE_CAP_S == 30 * 3600 and frozen.RUN_CAP_S == 4 * 3600 and frozen.WORKERS == 3
    assert frozen.DECIDE_DAY == 14 and frozen.FILE_BY_DAY == 10 and frozen.REDUCED_MAX_GATES == 50


def test_the_installed_tools_are_the_pinned_ones():
    from importlib.metadata import PackageNotFoundError, version
    for name, pin in frozen.TOOL_PINS.items():
        try:
            assert version(name) == pin, name
        except PackageNotFoundError:
            assert name == "mqt.bench", name  # only needed to write the base circuits once


def test_no_pinned_tool_drops_more_than_its_recorded_tolerance():
    for tool in frozen.TOOLS:
        assert largest_drop(tool) <= frozen.TOLERANCE[tool], tool


def test_the_boundary_angles_cover_tiny_quarter_turn_and_binary_fraction_values():
    values = set(frozen.BOUNDARY_ANGLES)
    assert 9.6e-05 in values and 1e-12 in values
    assert any(abs(v - 3.141592653589793 / 2) < 1e-15 for v in values)
    assert any(abs(v - 2 * 3.141592653589793 / 4096) < 1e-18 for v in values)
```

- [ ] **Step 2: Run to verify failure**: `python -m pytest spikes/qopt_audit/tests/test_frozen.py -q`. Expected: `ModuleNotFoundError: spikes.qopt_audit`.
- [ ] **Step 3: Implement** `frozen.py` as the block above, byte for byte, and `tolerance.py`:

```python
"""Re-measure how small a rotation each pinned tool drops in exact mode (the table in frozen.TOLERANCE)."""
from __future__ import annotations

import numpy as np

from spikes.qopt_p0.harness import run_text


def _case(kind: str, eps: float):
    from qiskit import QuantumCircuit
    q = QuantumCircuit(2)
    q.h(0)
    {"rz": lambda: q.rz(eps, 0), "rx": lambda: q.rx(eps, 0), "cu1": lambda: q.append(_cu1(eps), [0, 1])}[kind]()
    q.h(0)
    return q


def _cu1(eps: float):
    from qiskit.circuit.library import CU1Gate
    return CU1Gate(eps)


def phase_distance(a, b) -> float:
    """Operator-norm distance between two circuits after removing the best global phase."""
    from qiskit.quantum_info import Operator
    u, v = Operator(a).data, Operator(b).data
    phase = np.angle(np.trace(u.conj().T @ v))
    return float(np.linalg.norm(u - np.exp(-1j * phase) * v, 2))


def largest_drop(tool: str) -> float:
    from qiskit import QuantumCircuit, qasm2, transpile
    biggest = 0.0
    for kind in ("rz", "rx", "cu1"):
        for exponent in range(1, 17):
            eps = 10.0 ** -exponent
            source = _case(kind, eps)
            text = qasm2.dumps(transpile(source, basis_gates=["u1", "u2", "u3", "cx", "h", "cu1", "rx", "rz"],
                                         optimization_level=0))
            try:
                out = QuantumCircuit.from_qasm_str(run_text(tool, text, seed=1))
            except Exception:  # a reader that rejects the angle drops nothing
                continue
            if phase_distance(source, out) > 0.5 * eps:
                biggest = max(biggest, eps)
    return biggest
```

- [ ] **Step 4: Run to verify pass.** If `largest_drop` exceeds the table for a tool, the table is wrong: stop, and re-register before the tag.
- [ ] **Step 5: Commit:** `Freeze the audit parameters and re-measure the tool tolerances`.

### Task 3: The circuit generator and the schedule

**Files:** Create `bases.py`, `bases/`, `bases.json`, `generate.py`; Test `tests/test_generate.py`.

**Interfaces.** Produces:

- `generate.Case(kind: str, name: str, seed: int, base: str | None)` (frozen dataclass; `kind` is `"random"` or `"boundary"`).
- `generate.random_circuit(seed: int) -> str`, `generate.boundary_variant(base_text: str, seed: int) -> str`.
- `generate.schedule(start: int = 0) -> Iterator[Case]`: case `i` is random with seed `i // 2 + 1` when `i` is even, and boundary with seed `i // 2 + 1` over base `bases[(i // 2) % 40]` (sorted names) when `i` is odd.
- `generate.build(case: Case, bases: dict[str, str]) -> str`.
- `bases.load_bases(folder: Path) -> dict[str, str]` (name to text, measurements stripped) and `bases.generate(folder)` (run once with `mqt.bench` 2.3.0, writing `<family>-<n>.qasm`, one register, `qelib1` gates only, as P0's `make_circuits`).

- [ ] **Step 1: Write the failing tests**

```python
import re
from pathlib import Path

from qiskit import QuantumCircuit

from spikes.qopt_audit import frozen
from spikes.qopt_audit.bases import load_bases
from spikes.qopt_audit.generate import boundary_variant, build, random_circuit, schedule

BASES = Path(__file__).resolve().parents[1] / "bases"


def test_a_random_circuit_is_a_pure_function_of_its_seed():
    assert random_circuit(7) == random_circuit(7)
    assert random_circuit(7) != random_circuit(8)


def test_random_circuits_parse_and_stay_in_the_registered_bounds():
    for seed in range(1, 40):
        text = random_circuit(seed)
        qc = QuantumCircuit.from_qasm_str(text)
        assert frozen.RANDOM_QUBITS[0] <= qc.num_qubits <= frozen.RANDOM_QUBITS[1]
        assert frozen.RANDOM_GATES[0] <= qc.size() <= frozen.RANDOM_GATES[1] + 5
        assert text.count("\nqreg ") == 1 and "measure" not in text and "creg" not in text


def test_random_circuits_use_only_standard_gates():
    allowed = {"u1", "u2", "u3", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "cx", "cz", "cy",
               "ch", "swap", "ccx", "crz", "cu1", "cu3"}
    for seed in range(1, 20):
        ops = {m.group(1) for m in re.finditer(r"^([a-z0-9]+)[ (]", random_circuit(seed), re.M)}
        assert ops - allowed <= {"OPENQASM", "include", "qreg"}


def test_the_forty_base_circuits_are_the_registered_grid():
    bases = load_bases(BASES)
    assert set(bases) == {f"{f}-{n}" for f in frozen.BASE_FAMILIES for n in frozen.BASE_SIZES}


def test_a_boundary_variant_keeps_the_gate_skeleton_and_moves_some_angles_to_boundary_values():
    base = load_bases(BASES)["qft-6"]
    changed = 0
    for seed in range(1, 30):
        variant = boundary_variant(base, seed)
        assert [re.sub(r"\([^)]*\)", "()", l) for l in variant.splitlines()] == \
               [re.sub(r"\([^)]*\)", "()", l) for l in base.splitlines()]
        changed += variant != base
    assert changed > 20
    assert "e-05" in "".join(boundary_variant(base, s) for s in range(1, 200))  # the PyZX lead's format appears


def test_the_schedule_alternates_is_deterministic_and_never_repeats():
    first = [c for _, c in zip(range(400), schedule())]
    assert first == [c for _, c in zip(range(400), schedule())]
    assert [c.kind for c in first[:4]] == ["random", "boundary", "random", "boundary"]
    assert len({(c.kind, c.name, c.seed) for c in first}) == 400
    assert [c for _, c in zip(range(10), schedule(start=390))] != first[:10]


def test_building_a_case_needs_nothing_but_the_case_and_the_bases():
    bases = load_bases(BASES)
    for case in [c for _, c in zip(range(8), schedule())]:
        assert build(case, bases) == build(case, bases)
```

- [ ] **Step 2: Run to verify failure** (`ModuleNotFoundError: spikes.qopt_audit.generate`).
- [ ] **Step 3: Implement.** `random_circuit`: `rng = random.Random(frozen.SCHEDULE_SEED + seed)`; draw `n` and `g` in range; each gate drawn from the allowed set (weights: 60% one-qubit, 35% two-qubit, 5% `ccx` when `n >= 3`); parameterised gates take uniform angles in [0, 2pi) written with `repr(float)`. `boundary_variant`: parse the header and gate lines of the base; in each parameterised gate replace each argument, with probability `BOUNDARY_RATE`, by a value drawn from `BOUNDARY_ANGLES` (optionally negated), written with `repr(float)`, using `random.Random(frozen.SCHEDULE_SEED + seed)`. `bases.generate` copies `make_circuits.generate` with `BASE_FAMILIES` and `BASE_SIZES`; run it once in the `mqt.bench` environment and write `bases.json` with the sha256 of each stripped text.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit:** `Add the seeded circuit generator and schedule for the audit`.

### Task 4: Run a tool, check the output, classify

**Files:** Create `oracle.py`; Test `tests/test_oracle.py`.

**Interfaces.** Consumes `spikes.qopt_p0.verify.outcome`, `normalise`, `frozen.*`, `tolerance.phase_distance`. Produces:

- `oracle.Observation` (frozen dataclass): `kind`, `tool`, `qcec` (first QCEC outcome name or `""`), `confirmations: int`, `second_opinion: str`, `distance: float | None`, `signature: str`.
- `kind` is one of `verified`, `unverified`, `wrong_output`, `within_tolerance`, `oracle_disagreement`, `crash`.
- `oracle.observe(original: str, tool: str, fn: Callable[[str], str], *, workdir: Path, gates: int | None = None) -> Observation`. `fn` is the tool call (production: `lambda t: run_text(tool, t, seed=frozen.QISKIT_SEED)`), so tests can pass a faulty tool. `gates` is the reproducer's gate count for the tolerance rule; `None` means count the lines of the input.
- `oracle.crash_signature(tool: str, exc: Exception) -> str` is `"<tool>:<ExceptionType>:<message with digit runs replaced by #>"`, at most 120 characters.

- [ ] **Step 1: Write the failing tests**

```python
from spikes.qopt_audit import frozen
from spikes.qopt_audit.oracle import crash_signature, observe

A = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];
rz(0.5) q[1];
cx q[0],q[1];
"""


def test_a_faithful_tool_is_verified(tmp_path):
    assert observe(A, "qiskit", lambda t: t, workdir=tmp_path).kind == "verified"


def test_a_tool_that_drops_a_rotation_is_a_wrong_output_confirmed_by_a_second_checker(tmp_path):
    obs = observe(A, "qiskit", lambda t: t.replace("rz(0.5) q[1];\n", ""), workdir=tmp_path)
    assert obs.kind == "wrong_output"
    assert obs.confirmations == frozen.CONFIRM_RUNS and obs.second_opinion == "not_equivalent"
    assert obs.distance is not None and obs.distance > 0.1


def test_a_tiny_rotation_dropped_within_the_recorded_tolerance_does_not_count(tmp_path):
    source = A.replace("rz(0.5)", "rz(1e-07)")
    obs = observe(source, "qiskit", lambda t: t.replace("rz(1e-07) q[1];\n", ""), workdir=tmp_path)
    assert obs.kind == "within_tolerance"  # QCEC says not_equivalent, but 1e-7 is under 4 gates * 1e-5


def test_the_same_drop_above_the_tolerance_does_count(tmp_path):
    source = A.replace("rz(0.5)", "rz(0.001)")
    obs = observe(source, "qiskit", lambda t: t.replace("rz(0.001) q[1];\n", ""), workdir=tmp_path)
    assert obs.kind == "wrong_output"


def test_a_tool_that_raises_is_a_crash_with_a_stable_signature(tmp_path):
    def boom(text):
        raise ValueError("bad angle 9.6e-05 at line 12")
    obs = observe(A, "pyzx", boom, workdir=tmp_path)
    assert obs.kind == "crash" and obs.signature == "pyzx:ValueError:bad angle #.#e-# at line #"
    assert crash_signature("pyzx", ValueError("x" * 500)).__len__() <= 120


def test_a_hidden_output_permutation_is_unverified_not_wrong(tmp_path):
    hidden = A.replace("h q[0];", "// o 1 0\nh q[0];")
    assert observe(A, "tket-swaps", lambda t: hidden, workdir=tmp_path).kind == "unverified"


def test_an_output_qcec_cannot_decide_is_unverified(tmp_path, monkeypatch):
    monkeypatch.setattr("spikes.qopt_audit.oracle.outcome", lambda *a, **k: "no_information")
    assert observe(A, "qiskit", lambda t: t, workdir=tmp_path).kind == "unverified"


def test_a_checker_disagreement_is_never_a_wrong_output(tmp_path, monkeypatch):
    calls = iter(["not_equivalent", "not_equivalent"])
    monkeypatch.setattr("spikes.qopt_audit.oracle.outcome", lambda *a, **k: next(calls))
    monkeypatch.setattr("spikes.qopt_audit.oracle._alternating", lambda *a, **k: "equivalent")
    assert observe(A, "qiskit", lambda t: t, workdir=tmp_path).kind == "oracle_disagreement"
```

(The last test feeds exactly the first QCEC call and the one confirmation call, then the alternating checker disagrees; the implementation must call `outcome` at most `CONFIRM_RUNS` times.)

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement.** `observe`: run `fn` inside try; on exception return `crash`. Check with `outcome(original, out, workdir=..., timeout_s=QCEC_TIMEOUT_S, hard_wall_s=QCEC_HARD_WALL_S)`. `verified` if in `VERIFIED`; `unverified` if not `not_equivalent`. On `not_equivalent`, repeat `CONFIRM_RUNS - 1` more times (each call goes through the shared worker; the worker is stopped and restarted between runs so each is a fresh process); if any run differs, `oracle_disagreement`. Second opinion: `_alternating(original, out)` runs QCEC with `run_construction_checker=False, run_zx_checker=False, run_simulation_checker=False, run_alternating_checker=True` inside the same hard-wall worker (extend `_serve` with an optional configuration dict, as a disclosed post-tag change if needed); if the input has at most `DENSE_MAX_QUBITS` qubits also require `phase_distance > 1e-9`; any disagreement is `oracle_disagreement`. Tolerance: `distance` from `phase_distance` when the qubit count is at most `DENSE_MAX_QUBITS`, else `None`; `within_tolerance` when `distance <= gates * TOLERANCE[tool]`; a `None` distance keeps `wrong_output` with `distance=None` (not counted until reduced).
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit:** `Add the audit oracle: run, verify, confirm and classify`.

### Task 5: Reduce a reproducer

**Files:** Create `reduce.py`; Test `tests/test_reduce.py`.

**Interfaces.** Produces `reduce.ddmin_gates(qasm: str, predicate: Callable[[str], bool], *, max_calls: int = frozen.REDUCE_MAX_CALLS) -> str`: the smallest gate subset (the three header lines `OPENQASM`, `include` and `qreg` are kept, then gate lines are removed in the delta-debugging order) for which `predicate` still holds, or the input if it does not hold on the input. `reduce.gate_count(qasm: str) -> int`. After removal of gates, qubits are not renumbered; unused qubits are dropped only by `reduce.compact(qasm: str) -> str`, which relabels the used qubits and rewrites the `qreg` line (so a 22-qubit failure can fall under the 10-qubit limit of Task 4).

- [ ] **Step 1: Write the failing tests**

```python
from spikes.qopt_audit import oracle
from spikes.qopt_audit.reduce import compact, ddmin_gates, gate_count

BIG = "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[12];\n" + "".join(
    f"h q[{i % 12}];\ncx q[{i % 12}],q[{(i + 1) % 12}];\n" + ("rz(0.7) q[5];\n" if i == 20 else "") for i in range(40))


def drops_rz(text):  # a faulty tool that removes every rz
    return "\n".join(l for l in text.splitlines() if not l.startswith("rz")) + "\n"


def test_reduction_keeps_the_failure_and_ends_with_few_gates(tmp_path):
    fails = lambda t: oracle.observe(t, "qiskit", drops_rz, workdir=tmp_path).kind == "wrong_output"
    small = ddmin_gates(BIG, fails)
    assert fails(small) and gate_count(small) <= 3 and gate_count(BIG) > 70


def test_a_predicate_that_does_not_hold_returns_the_input_unchanged():
    assert ddmin_gates(BIG, lambda t: False) == BIG


def test_the_call_budget_is_respected():
    calls = []
    def never_shrinks(t):
        calls.append(1)
        return t == BIG
    ddmin_gates(BIG, never_shrinks, max_calls=25)
    assert len(calls) <= 26


def test_compact_relabels_used_qubits_and_shrinks_the_register():
    text = compact("OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[22];\nh q[3];\ncx q[3],q[17];\n")
    assert "qreg q[2];" in text and "cx q[0],q[1];" in text
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** a standard `ddmin` over the gate-line list with a call counter (the check on the input counts as one call), and `compact`.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit:** `Add gate-level reproducer reduction for the audit`.

### Task 6: The findings ledger and the kill rule

**Files:** Create `ledger.py`; Test `tests/test_ledger.py`.

**Interfaces.** Produces:

- `ledger.Finding` (frozen dataclass): `id: str`, `cls: str` (`wrong_output`, `crash`, `reader`, `verifier`, `docs`), `tool: str`, `reproducer_gates: int`, `reproducer_qubits: int`, `distance: float | None`, `tolerance_ok: bool`, `proved_twice: bool`, `second_opinion_ok: bool`, `reproduces_latest: bool`, `lead: bool`, `duplicate_of: str | None`, `search_url: str | None`, `filed: date | None`, `accepted: date | None`, `url: str | None`.
- `ledger.counts_as_wrong_output(f: Finding) -> bool`: `cls == "wrong_output"`, evidence conditions 2 to 5 above all true (`proved_twice`, `second_opinion_ok`, `tolerance_ok`, `reproduces_latest`), not `lead`, no `duplicate_of`.
- `ledger.verdict(findings: list[Finding], *, day0: date, today: date) -> str`: `"pass"` when (i) at least one finding counts and has `reproducer_gates <= REDUCED_MAX_GATES`, or (ii) at least two counting findings have a `search_url`, `filed <= day0 + FILE_BY_DAY`, and `accepted` set and `<= day0 + DECIDE_DAY`; `"open"` when not passed, `today < day0 + DECIDE_DAY` and the pass is still reachable (reachable means: (i) cannot be ruled out, which is always true before day 14); `"fallback"` otherwise.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

from spikes.qopt_audit.ledger import Finding, counts_as_wrong_output, verdict

D0 = date(2026, 10, 14)


def f(**kw):
    base = dict(id="x", cls="wrong_output", tool="qiskit", reproducer_gates=12, reproducer_qubits=3, distance=0.3,
                tolerance_ok=True, proved_twice=True, second_opinion_ok=True, reproduces_latest=True, lead=False,
                duplicate_of=None, search_url=None, filed=None, accepted=None, url=None)
    base.update(kw)
    return Finding(**base)


def test_one_clean_small_wrong_output_passes_alone():
    assert verdict([f()], day0=D0, today=date(2026, 10, 20)) == "pass"


def test_a_tiny_rotation_dropped_within_tolerance_never_passes():
    assert verdict([f(tolerance_ok=False)], day0=D0, today=date(2026, 10, 28)) == "fallback"


def test_a_wrong_output_over_fifty_gates_does_not_pass_by_itself():
    assert verdict([f(reproducer_gates=51)], day0=D0, today=date(2026, 10, 28)) == "fallback"


def test_two_accepted_wrong_output_issues_pass_even_when_large():
    a = dict(reproducer_gates=90, search_url="u", filed=date(2026, 10, 20), accepted=date(2026, 10, 27))
    assert verdict([f(id="a", **a), f(id="b", **a)], day0=D0, today=date(2026, 10, 28)) == "pass"


def test_crash_and_reader_issues_never_count_however_many_are_accepted():
    a = dict(search_url="u", filed=date(2026, 10, 20), accepted=date(2026, 10, 27))
    crashes = [f(id=str(i), cls=c, **a) for i, c in enumerate(["crash", "reader", "crash"])]
    assert verdict(crashes, day0=D0, today=date(2026, 10, 28)) == "fallback"


def test_an_issue_filed_after_day_ten_or_without_a_search_link_does_not_count():
    late = dict(search_url="u", filed=date(2026, 10, 25), accepted=date(2026, 10, 27), reproducer_gates=90)
    nolink = dict(search_url=None, filed=date(2026, 10, 20), accepted=date(2026, 10, 27), reproducer_gates=90)
    assert verdict([f(id="a", **late), f(id="b", **nolink)], day0=D0, today=date(2026, 10, 28)) == "fallback"


def test_a_lead_a_duplicate_or_an_unreproduced_finding_does_not_count():
    assert not counts_as_wrong_output(f(lead=True))
    assert not counts_as_wrong_output(f(duplicate_of="qiskit#123"))
    assert not counts_as_wrong_output(f(reproduces_latest=False))
    assert not counts_as_wrong_output(f(proved_twice=False))
    assert not counts_as_wrong_output(f(second_opinion_ok=False))


def test_before_day_fourteen_an_unmet_rule_is_open_and_after_it_is_a_fallback():
    assert verdict([], day0=D0, today=date(2026, 10, 20)) == "open"
    assert verdict([], day0=D0, today=date(2026, 10, 28)) == "fallback"
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** the dataclass and the two functions exactly as specified; the ledger is stored as `spikes/qopt_audit/findings/ledger.jsonl` with `Finding` fields (dates as ISO strings), loaded by `ledger.load(path)`.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit:** `Add the audit findings ledger and the pre-registered kill rule`.

### Task 7: The batch runner, the log and the report

**Files:** Create `run.py`; Test `tests/test_run.py`.

**Interfaces.** Produces:

- `run.run_batch(cases: Iterable[Case], bases: dict[str, str], *, out: Path, budget_s: float, workers: int = frozen.WORKERS, tools: dict[str, Callable] | None = None) -> dict`: for each case, build it, write the QASM to `out/circuits/<kind>-<name>-<seed>.qasm`, run every tool in `tools` (default: the four of `frozen.TOOLS` through `run_text`), classify with `oracle.observe`, append one JSON line per (case, tool) to `out/log.jsonl`, and stop when the next case would pass `budget_s` of wall-clock time. Skips (case, tool) pairs already in the log, so a batch resumes. Returns `{"cases": n, "stopped": "budget"|"exhausted", "last_index": i}`. Always stops the QCEC worker before returning.
- `run.report(log: Path) -> str`: counts by `kind` and tool, the unverified share by qubit bucket (6 to 10, 11 to 14, 15 to 18, 19 to 22, 23 and over), the distinct crash signatures with counts, the `oracle_disagreement` cases, and every `wrong_output` with its case.
- Command: `python -m spikes.qopt_audit.run <out> --budget-hours 4 [--start N]`, which also refuses to start when the elapsed total of earlier logs plus this budget exceeds `COMPUTE_CAP_S`.

- [ ] **Step 1: Write the failing tests**

```python
import json
import multiprocessing as mp
from pathlib import Path

from spikes.qopt_audit.bases import load_bases
from spikes.qopt_audit.generate import schedule
from spikes.qopt_audit.run import report, run_batch

BASES = load_bases(Path(__file__).resolve().parents[1] / "bases")
IDENTITY = {"qiskit": lambda t: t}


def test_a_batch_logs_one_line_per_case_and_tool_and_writes_the_circuits(tmp_path):
    cases = [c for _, c in zip(range(3), schedule())]
    summary = run_batch(cases, BASES, out=tmp_path, budget_s=600, tools=IDENTITY)
    lines = [json.loads(l) for l in (tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert summary["cases"] == 3 and summary["stopped"] == "exhausted" and len(lines) == 3
    assert {l["kind"] for l in lines} <= {"verified", "unverified"}
    assert len(list((tmp_path / "circuits").glob("*.qasm"))) == 3


def test_a_second_batch_resumes_and_does_not_repeat_work(tmp_path):
    cases = [c for _, c in zip(range(2), schedule())]
    run_batch(cases, BASES, out=tmp_path, budget_s=600, tools=IDENTITY)
    run_batch(cases, BASES, out=tmp_path, budget_s=600, tools=IDENTITY)
    assert len((tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_the_budget_stops_the_batch_and_no_worker_is_left_behind(tmp_path):
    cases = [c for _, c in zip(range(50), schedule())]
    summary = run_batch(cases, BASES, out=tmp_path, budget_s=0.001, tools=IDENTITY)
    assert summary["stopped"] == "budget" and summary["cases"] < 50
    assert mp.active_children() == []


def test_a_planted_fault_appears_in_the_report_as_a_wrong_output(tmp_path):
    drop_rz = {"qiskit": lambda t: "\n".join(l for l in t.splitlines() if not l.startswith("rz")) + "\n"}
    cases = [c for _, c in zip(range(40), schedule()) if c.kind == "boundary"][:3]
    run_batch(cases, BASES, out=tmp_path, budget_s=1200, tools=drop_rz)
    text = report(tmp_path / "log.jsonl")
    assert "wrong_output" in text and "unverified share" in text
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement.** Sequential loop first; use a `multiprocessing` pool of `workers` processes (spawn) over cases only if the sequential throughput measured by a 20-minute calibration run is under 5 cases a minute; each pool process has its own QCEC worker. A tool call is wrapped so that an exception is a `crash` observation.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit:** `Add the audit batch runner, log and report`.

### Task 8: Run it, triage, file, decide

No new code. These steps are the run protocol, in order. The tag comes before step 2.

- [ ] **Step 1: Tag.** With Tasks 1 and 2 of this plan done and this file committed: `git tag audit-prereg && git push origin audit-prereg`. Day 0 is the date of the push. The tag fixes the rule, the parameters, the tolerance table, the generator definition and the schedule order.
- [ ] **Step 2: Build Tasks 3 to 7** test-first as written above. Anything that differs from this plan is listed in the report under "Changes after the tag".
- [ ] **Step 3: Calibrate.** One 20-minute batch; record cases per minute and the unverified share. Do not change a parameter because of it.
- [ ] **Step 4: Run** in batches of at most 4 hours until `COMPUTE_CAP_S` is spent or the rule passes; after each batch list Python processes and kill strays. Do not stop a run early because it passed: the cap and the record matter, and a pass is reported at the end.
- [ ] **Step 5: Triage** every `wrong_output`, `oracle_disagreement` and each distinct `crash` signature. For each `wrong_output`: reduce (`ddmin_gates`, then `compact`), re-run the oracle on the reduced input for `gates` and `distance`, re-run in a fresh process and with the latest released version of the tool in a separate environment, and run it on the tool's main branch if it is on GitHub; write the folder `spikes/qopt_audit/findings/<id>/` with `input.qasm`, `command.txt` (tool, version, seed, the one-line call), `versions.txt` and `NOTES.md`. Add it to `ledger.jsonl`.
- [ ] **Step 6: Search for duplicates** in the tracker of each tool (Qiskit, tket, PyZX; QCEC for a `verifier` finding) and record the search link in the ledger. A duplicate is recorded with `duplicate_of` and not filed again.
- [ ] **Step 7: File** only with the founder's yes for each issue (filing is public). Wrong-output issues by day 10 (they are the ones that can count); crashes and reader errors are filed too and are logged as not counted. Record `filed` and the issue URL.
- [ ] **Step 8: Decide.** `ledger.verdict(...)` on day 14 (or earlier when it already passes). Write `docs/history/<date>-audit-spike.md`: the verdict and the numbers behind it, the throughput, the unverified share by size, every finding with its reproducer path, changes after the tag, and what the founder must decide next. Update `docs/STATUS.md` and the decision log (D-145 result), commit, push the branch, open the pull request.
- [ ] **Step 9: Stop.** No P3 or P4 change in this spike; the founder decides what follows.

## Self-review

- **Rule coverage:** the pass conditions (i) and (ii), the tolerance rule and the wrong-output-only count are in the kill rule section and in Task 6's tests; the exclusion of crashes, leads, duplicates and unsearched issues is tested.
- **Frozen block:** Task 2's test fails if this plan and `frozen.py` differ.
- **Failure modes the tests pin:** a dropped tiny rotation (`within_tolerance`), a hidden permutation (`unverified`), a checker disagreement (`oracle_disagreement`), a planted fault found end to end (Task 7), a tool crash (signature), a worker never started (Task 1), a resumed batch, a budget stop leaving no worker, a unified schedule that never repeats a case.
- **Not covered, on purpose:** controls and measurement circuits (QCEC checks unitaries), layout and permutation metadata (`normalise` rejects `// o`), and simulators; the prior-art page lists them as outside the audit.
- **Known weakness:** (ii) depends on how fast maintainers reply; the rule counts acceptance by day 14 only, so a late reply can turn a real finding into a fallback. The report lists such cases separately.
