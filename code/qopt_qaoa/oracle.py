"""Verification of an output (plan, "What counts as verified") and the triage of a lead.

The re-decide step is the audit's, written out here so that changes to the audit's oracle (P0c) cannot move this rule.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from spikes.qopt_p0 import verify
from spikes.qopt_p0.verify import VERIFIED, outcome
from spikes.qopt_qaoa import frozen

ALTERNATING = {"run_construction_checker": False, "run_zx_checker": False, "run_simulation_checker": False,
               "run_alternating_checker": True}
ZX = {"run_construction_checker": False, "run_zx_checker": True, "run_simulation_checker": False,
      "run_alternating_checker": False}
ZX_AGREES = ("not_equivalent", "probably_not_equivalent")
Outcome = Callable[..., str]


def decide(original: str, candidate: str, *, workdir: Path, run: Outcome = outcome) -> tuple[str, str]:
    """(answer, checker). QCEC's default checker answers `no_information` or `not_equivalent` on a phase-only
    difference depending on which checker finishes first, so an undecided default answer is re-decided once by the
    alternating checker alone. A wall or a parse failure is not re-waited."""
    first = run(original, candidate, workdir=workdir, timeout_s=frozen.QCEC_TIMEOUT_S,
                hard_wall_s=frozen.QCEC_HARD_WALL_S)
    if first in VERIFIED or first in ("not_equivalent", "strict_parse", "hard_timeout"):
        return first, "default"
    return run(original, candidate, workdir=workdir, timeout_s=frozen.QCEC_TIMEOUT_S,
               hard_wall_s=frozen.QCEC_HARD_WALL_S, config=ALTERNATING), "alternating"


def recheck_latest(original: str, candidate: str, *, workdir: Path) -> str:
    """The same decision with QCEC 3.11.0, in the interpreter named by QCEC_LATEST_PYTHON (the `audit-addendum`
    re-check). 'not_run' when no such interpreter is configured."""
    python = os.environ.get("QCEC_LATEST_PYTHON")
    if not python:
        return "not_run"
    workdir = Path(workdir)
    a, b = workdir / "recheck-a.qasm", workdir / "recheck-b.qasm"
    a.write_text(original, encoding="utf-8")
    b.write_text(candidate, encoding="utf-8")
    code = ("import sys\nfrom pathlib import Path\nfrom spikes.qopt_qaoa.oracle import decide\n"
            "if __name__ == '__main__':\n"
            "    print(decide(Path(sys.argv[1]).read_text(encoding='utf-8'),"
            " Path(sys.argv[2]).read_text(encoding='utf-8'), workdir=Path(sys.argv[3]))[0])\n")
    script = workdir / "recheck_main.py"
    script.write_text(code, encoding="utf-8")
    done = subprocess.run([python, str(script), str(a), str(b), str(workdir)], capture_output=True, text=True,
                          timeout=frozen.QCEC_HARD_WALL_S * 4, env={**os.environ, "PYTHONPATH": os.getcwd()})
    return done.stdout.strip().splitlines()[-1] if done.returncode == 0 and done.stdout.strip() else "recheck_error"


@dataclass(frozen=True)
class Verdict:
    verified: bool
    answer: str
    checker: str
    recheck: str = ""
    contradicted: bool = False


def verdict(original: str, candidate: str, *, workdir: Path, run: Outcome = outcome,
            recheck: Callable[..., str] = recheck_latest) -> Verdict:
    """Verified: QCEC 3.10.2 says equivalent (up to global phase) and 3.11.0 does not say `not_equivalent`."""
    answer, checker = decide(original, candidate, workdir=workdir, run=run)
    if answer not in VERIFIED:
        return Verdict(False, answer, checker)
    second = recheck(original, candidate, workdir=workdir)
    contradicted = second == "not_equivalent"
    return Verdict(not contradicted, answer, checker, second, contradicted)


def witness(original: str, candidate: str) -> dict[str, float]:
    """1 - |<a|b>|^2 for both circuits on each witness state: the seeded random product states and two
    computational-basis states (all zeros, and one seeded bit string). Every gap is kept."""
    import numpy as np
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector
    a, b = QuantumCircuit.from_qasm_str(original), QuantumCircuit.from_qasm_str(candidate)
    if a.num_qubits != b.num_qubits:
        return {"width": 1.0}
    n = a.num_qubits

    def gap(prep: QuantumCircuit) -> float:
        sa, sb = Statevector.from_instruction(prep.compose(a)), Statevector.from_instruction(prep.compose(b))
        return float(max(0.0, 1.0 - abs(np.vdot(sa.data, sb.data)) ** 2))

    out = {}
    for seed in frozen.WITNESS_RANDOM_SEEDS:
        rng = np.random.default_rng(seed)
        prep = QuantumCircuit(n)
        for q in range(n):
            prep.u(*rng.uniform(0.0, 2 * np.pi, 3), q)
        out[f"random-{seed}"] = gap(prep)
    out["basis-zeros"] = gap(QuantumCircuit(n))
    bits = np.random.default_rng(frozen.WITNESS_BASIS_SEED).integers(0, 2, n)
    prep = QuantumCircuit(n)
    for q, bit in enumerate(bits):
        if bit:
            prep.x(q)
    out["basis-bits"] = gap(prep)
    return out


def witnessed(gaps: dict[str, float]) -> bool:
    return max(gaps.values(), default=0.0) > frozen.WITNESS_MIN


def second_opinion(original: str, candidate: str, *, workdir: Path, run: Outcome = outcome) -> str:
    """The ZX checker alone. It answers `probably_not_equivalent` where the alternating checker times out."""
    return run(original, candidate, workdir=workdir, timeout_s=frozen.QCEC_TIMEOUT_S,
               hard_wall_s=frozen.QCEC_HARD_WALL_S, config=ZX)


@dataclass
class Lead:
    kind: str  # wrong_output, oracle_disagreement
    answer: str
    confirmations: int
    second: str = ""
    gaps: dict = field(default_factory=dict)


def classify(original: str, candidate: str, *, workdir: Path, run: Outcome = outcome,
             fresh: Callable[[], None] = lambda: verify._WORKER.stop()) -> Lead | None:
    """None unless QCEC says `not_equivalent`; then confirm in fresh workers, take the ZX second opinion and the
    multi-state witness. A disagreement is a lead on the checker, never a wrong output."""
    first, _ = decide(original, candidate, workdir=workdir, run=run)
    if first != "not_equivalent":
        return None
    confirmations = 1
    for _ in range(frozen.CONFIRM_RUNS - 1):
        fresh()
        again, _ = decide(original, candidate, workdir=workdir, run=run)
        if again != "not_equivalent":
            return Lead("oracle_disagreement", first, confirmations)
        confirmations += 1
    second = second_opinion(original, candidate, workdir=workdir, run=run)
    gaps = witness(original, candidate)
    kind = "wrong_output" if second in ZX_AGREES and witnessed(gaps) else "oracle_disagreement"
    return Lead(kind, first, confirmations, second, gaps)
