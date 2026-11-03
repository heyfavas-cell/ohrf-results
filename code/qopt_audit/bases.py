"""The 40 base circuits: the eight P0 families at the audit's sizes, from `mqt.bench` 2.3.0 (written once).

python -m spikes.qopt_audit.bases <folder> writes them in an environment with `mqt.bench`; --manifest writes the hashes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from spikes.qopt_audit import frozen
from spikes.qopt_p0.harness import strip_measurements

# The qelib1 gates tket can read; a level-0 transpile unrolls custom gate definitions without optimising.
QELIB1 = ["u1", "u2", "u3", "cx", "id", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "cz", "cy",
          "ch", "swap", "ccx", "crz", "cu1", "cu3", "u"]


def generate(folder: Path) -> list[str]:
    import importlib.metadata as md
    if md.version("mqt.bench") != frozen.TOOL_PINS["mqt.bench"]:
        raise SystemExit(f"mqt.bench {frozen.TOOL_PINS['mqt.bench']} is required, found {md.version('mqt.bench')}")
    from mqt.bench import BenchmarkLevel, get_benchmark
    from qiskit import QuantumCircuit, qasm2, transpile
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for family in frozen.BASE_FAMILIES:
        for n in frozen.BASE_SIZES:
            qc = get_benchmark(family, BenchmarkLevel.INDEP, n, random_parameters=True)
            qc = transpile(qc, basis_gates=QELIB1, optimization_level=0)
            flat = QuantumCircuit(qc.num_qubits, name=family)  # one register: tket's export reorders registers
            flat.compose(qc.remove_final_measurements(inplace=False), inplace=True)
            path = folder / f"{family}-{n}.qasm"
            path.write_text(qasm2.dumps(flat), encoding="utf-8", newline="\n")
            written.append(path.name)
    return written


def load_bases(folder: Path) -> dict[str, str]:
    return {p.stem: strip_measurements(p.read_text(encoding="utf-8")) for p in sorted(Path(folder).glob("*.qasm"))}


def write_manifest(folder: Path, path: Path) -> int:
    import hashlib
    bases = load_bases(folder)
    digest = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in bases.items()}
    path.write_text(json.dumps(digest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return len(digest)


if __name__ == "__main__":
    if sys.argv[1] == "--manifest":
        print(write_manifest(Path(sys.argv[2]), Path(sys.argv[3])), "circuits in the manifest")
    else:
        print(len(generate(Path(sys.argv[1]))), "circuits")
