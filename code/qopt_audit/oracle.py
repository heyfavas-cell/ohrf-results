"""Run a tool on a circuit, check the output with QCEC, confirm a failure, and classify it (the kill rule's evidence)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from spikes.qopt_audit import frozen
from spikes.qopt_audit.reduce import gate_count
from spikes.qopt_audit.tolerance import phase_distance
from spikes.qopt_p0 import verify
from spikes.qopt_p0.verify import VERIFIED, outcome

ALTERNATING = {"run_construction_checker": False, "run_zx_checker": False, "run_simulation_checker": False,
               "run_alternating_checker": True}
# Random single-qubit stimuli see a diagonal difference that basis-state stimuli cannot.
SIMULATION = {"run_construction_checker": False, "run_zx_checker": False, "run_alternating_checker": False,
              "run_simulation_checker": True, "state_type": "random_1q_basis"}


@dataclass(frozen=True)
class Observation:
    kind: str  # verified, unverified, wrong_output, within_tolerance, oracle_disagreement, crash
    tool: str
    qcec: str = ""
    confirmations: int = 0
    second_opinion: str = ""
    distance: float | None = None
    signature: str = ""


def crash_signature(tool: str, exc: Exception) -> str:
    return f"{tool}:{type(exc).__name__}:{re.sub(r'[0-9]+', '#', str(exc))}"[:120]


def _qubits(qasm: str) -> int:
    return sum(int(m) for m in re.findall(r"qreg\s+\w+\[(\d+)\]", qasm))


def _alternating(original: str, candidate: str, *, workdir: Path) -> str:
    return outcome(original, candidate, workdir=workdir, timeout_s=frozen.QCEC_TIMEOUT_S,
                   hard_wall_s=frozen.QCEC_HARD_WALL_S, config=ALTERNATING)


def _simulation(original: str, candidate: str, *, workdir: Path) -> str:
    return outcome(original, candidate, workdir=workdir, timeout_s=frozen.QCEC_TIMEOUT_S,
                   hard_wall_s=frozen.QCEC_HARD_WALL_S, config=SIMULATION)


def _decide(original: str, candidate: str, *, workdir: Path) -> tuple[str, str]:
    """(answer, checker). QCEC's default runs its checkers in parallel and, on a phase-only difference, answers
    `not_equivalent` or `no_information` depending on which finishes first, so an undecided default answer is
    re-decided by the exact alternating checker alone."""
    first = outcome(original, candidate, workdir=workdir, timeout_s=frozen.QCEC_TIMEOUT_S,
                    hard_wall_s=frozen.QCEC_HARD_WALL_S)
    if first in VERIFIED or first in ("not_equivalent", "strict_parse", "hard_timeout"):  # a wall is not re-waited
        return first, "default"
    return _alternating(original, candidate, workdir=workdir), "alternating"


def _distance(original: str, candidate: str) -> float | None:
    if _qubits(original) > frozen.DENSE_MAX_QUBITS:
        return None
    try:
        from qiskit import QuantumCircuit
        return phase_distance(QuantumCircuit.from_qasm_str(original), QuantumCircuit.from_qasm_str(candidate))
    except Exception:  # an output Qiskit cannot read has no distance
        return None


def observe(original: str, tool: str, fn: Callable[[str], str], *, workdir: Path,
            gates: int | None = None) -> Observation:
    try:
        out = fn(original)
    except Exception as exc:  # a tool that raises on a valid input is a result, not a crash of the audit
        return Observation("crash", tool, signature=crash_signature(tool, exc))
    first, checker = _decide(original, out, workdir=workdir)
    if first in VERIFIED:
        return Observation("verified", tool, qcec=first)
    if first != "not_equivalent":
        return Observation("unverified", tool, qcec=first)
    confirmations = 1
    for _ in range(frozen.CONFIRM_RUNS - 1):
        verify._WORKER.stop()  # a fresh worker process for every confirmation
        again, _checker = _decide(original, out, workdir=workdir)
        if again != "not_equivalent":
            return Observation("oracle_disagreement", tool, qcec=first, confirmations=confirmations)
        confirmations += 1
    distance = _distance(original, out)
    count = gate_count(original) if gates is None else gates
    if distance is not None and 1e-9 < distance <= count * frozen.TOLERANCE[tool]:
        return Observation("within_tolerance", tool, qcec=first, confirmations=confirmations, distance=distance)
    # An independent second opinion: the alternating checker, or random-1q simulation when it already decided.
    second = (_simulation if checker == "alternating" else _alternating)(original, out, workdir=workdir)
    if second != "not_equivalent" or (distance is not None and distance <= 1e-9):
        return Observation("oracle_disagreement", tool, qcec=first, confirmations=confirmations,
                           second_opinion=second, distance=distance)
    return Observation("wrong_output", tool, qcec=first, confirmations=confirmations, second_opinion=second,
                       distance=distance)
