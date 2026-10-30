"""GUOQ's inputs: each circuit rebased to {CX, RZ, SX, X} without optimising, so GUOQ reads its own gate set (IBMN).

python -m spikes.qopt_p0.guoq_inputs <circuit-folder> <out-folder>. GUOQ's outputs are checked against the original
circuit, not against this rebased copy.
"""
from __future__ import annotations

import sys
from pathlib import Path

from spikes.qopt_p0.harness import BASIS, SpikeHarness


def rebase(text: str) -> str:
    from qiskit import QuantumCircuit, qasm2, transpile
    return qasm2.dumps(transpile(QuantumCircuit.from_qasm_str(text), basis_gates=BASIS, optimization_level=0))


def prepare(src: Path, out: Path) -> int:
    harness = SpikeHarness(Path(src))
    Path(out).mkdir(parents=True, exist_ok=True)
    refs = harness.circuits("spike")
    for ref in refs:
        (Path(out) / f"{ref.name}.qasm").write_text(rebase(harness.original(ref)), encoding="utf-8")
    return len(refs)


if __name__ == "__main__":
    print(prepare(Path(sys.argv[1]), Path(sys.argv[2])), "inputs written")
