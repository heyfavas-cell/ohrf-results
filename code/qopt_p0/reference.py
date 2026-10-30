"""GUOQ reference outputs (D-089), the power estimate and the routed two-qubit metric (D-090)."""
from __future__ import annotations

import math
import statistics
from pathlib import Path

from spikes.qopt_p0.frozen import QCEC_TIMEOUT_S
from spikes.qopt_p0.harness import cx_count
from spikes.qopt_p0.verify import verified

Z_ALPHA, Z_BETA = 1.96, 0.8416  # 95% two-sided interval, 80% power


def load_reference(folder: Path, originals: dict[str, str], *, workdir: Path, timeout_s: float = QCEC_TIMEOUT_S) -> dict[str, int]:
    """CNOT counts of the reference outputs QCEC proves equivalent; missing or unproved outputs are left out."""
    out = {}
    for name, original in originals.items():
        path = Path(folder) / f"{name}.qasm"
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if verified(original, text, workdir=workdir, timeout_s=timeout_s):
                out[name] = cx_count(text)
    return out


def log_sd(pairs: list[tuple[int, int]]) -> float:
    logs = [math.log(max(after, 1) / before) for before, after in pairs if before > 0]
    return statistics.stdev(logs) if len(logs) > 1 else 0.0


def circuits_needed(sd: float, *, effect: float = 0.01) -> int:
    """Circuits for a CI lower bound above 0 when the true geometric-mean reduction is `effect`."""
    return math.ceil(((Z_ALPHA + Z_BETA) * sd / -math.log(1 - effect)) ** 2)


def routed_2q(qasm: str, *, seed: int) -> int:
    """CZ count after routing to a distance-3 heavy-hex map (19 qubits) in the {CZ, RZ, SX, X} basis."""
    from qiskit import QuantumCircuit, transpile
    from qiskit.transpiler import CouplingMap
    qc = transpile(QuantumCircuit.from_qasm_str(qasm), coupling_map=CouplingMap.from_heavy_hex(3),
                   basis_gates=["cz", "rz", "sx", "x"], optimization_level=1, seed_transpiler=seed)
    return qc.count_ops().get("cz", 0)


def extra_lines(rows, originals: dict[str, str], best_dir: Path) -> list[str]:
    """The report lines for D-090: circuits needed for a 1% effect, and routed CZ medians."""
    base = [(r.baseline, r.portfolio) for r in rows]
    deep = [(r.portfolio, r.deep) for r in rows]
    routed_original = [routed_2q(originals[r.name], seed=1) for r in rows]
    routed_best = [routed_2q((Path(best_dir) / f"{r.name}.qasm").read_text(encoding="utf-8"), seed=1) for r in rows]
    return [
        f"Circuits needed for a 1% effect (portfolio against best baseline): {circuits_needed(log_sd(base))}",
        f"Circuits needed for a 1% effect (depth-3 headroom): {circuits_needed(log_sd(deep))}",
        f"Routed CZ count on a heavy-hex map, median: original {statistics.median(routed_original)}, "
        f"portfolio output {statistics.median(routed_best)}",
    ]
