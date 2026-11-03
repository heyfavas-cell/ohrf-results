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
