"""Write the frozen P0 circuit set with the pinned mqt.bench: python -m spikes.qopt_p0.make_circuits <folder>.

Run it in an environment with `mqt.bench` 2.3.0 (it is not needed to run the spike itself). The grid is fixed in
`frozen.py`: families times sizes at the target-independent level, no choice made after seeing any result.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from spikes.qopt_p0.frozen import BENCH_VERSION, FAMILIES, SIZES

# Standard qelib1 gates. A level-0 transpile into this set unrolls custom gate definitions (tket cannot read them)
# without optimising anything.
QELIB1 = ["u1", "u2", "u3", "cx", "id", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "cz", "cy",
          "ch", "swap", "ccx", "crz", "cu1", "cu3", "u"]


def generate(folder: Path) -> list[str]:
    import importlib.metadata as md
    if md.version("mqt.bench") != BENCH_VERSION:
        raise SystemExit(f"mqt.bench {BENCH_VERSION} is required, found {md.version('mqt.bench')}")
    from mqt.bench import BenchmarkLevel, get_benchmark
    from qiskit import QuantumCircuit, qasm2, transpile
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for family in FAMILIES:
        for n in SIZES:
            qc = get_benchmark(family, BenchmarkLevel.INDEP, n, random_parameters=True)
            qc = transpile(qc, basis_gates=QELIB1, optimization_level=0)
            # One register: tket's QASM export reorders registers, and QCEC compares by qubit index.
            flat = QuantumCircuit(qc.num_qubits, name=family)
            flat.compose(qc.remove_final_measurements(inplace=False), inplace=True)
            qc = flat
            path = folder / f"{family}-{n}.qasm"
            path.write_text(qasm2.dumps(qc), encoding="utf-8")
            written.append(path.name)
    return written


def write_manifest(folder: Path, path: Path) -> int:
    """Freeze the set: circuit name to the sha256 of its stripped text, the hash the harness checks."""
    from spikes.qopt_p0.harness import SpikeHarness
    refs = SpikeHarness(folder).circuits("spike")
    text = json.dumps({r.name: r.sha for r in refs}, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    return len(refs)


if __name__ == "__main__":
    if sys.argv[1] == "--manifest":  # python -m spikes.qopt_p0.make_circuits --manifest <folder> <circuits.json>
        print(write_manifest(Path(sys.argv[2]), Path(sys.argv[3])), "circuits in the manifest")
    else:
        print(len(generate(Path(sys.argv[1]))), "circuits")
