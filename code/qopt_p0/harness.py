"""The spike's benchmark harness, shaped like P3's `Harness` protocol so P3 Task 16 can port `run_tool`."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from spikes.qopt_p0.frozen import SEEDS

DROP = re.compile(r"^\s*(measure|barrier|creg)\b")


@dataclass(frozen=True)
class CircuitRef:
    sha: str
    family: str
    name: str


@dataclass(frozen=True)
class ToolRun:
    qasm: str
    runtime_ms: int


def strip_measurements(qasm: str) -> str:
    return "".join(line + "\n" for line in qasm.splitlines() if line.strip() and not DROP.match(line))


def cx_count(qasm: str) -> int:
    return sum(1 for line in qasm.splitlines() if line.strip().startswith("cx "))


class SpikeHarness:
    name = "qopt-p0-spike"
    version = "0.1.0"

    def __init__(self, folder: Path) -> None:
        self._texts: dict[str, str] = {}
        refs = []
        for path in sorted(Path(folder).glob("*.qasm")):
            text = strip_measurements(path.read_text(encoding="utf-8"))
            sha = hashlib.sha256(text.encode()).hexdigest()
            self._texts[sha] = text
            refs.append(CircuitRef(sha=sha, family=path.stem.split("-")[0], name=path.stem))
        self._refs = sorted(refs, key=lambda r: (r.family, r.name))

    def circuits(self, set_name: str, *, fold: int | None = None) -> list[CircuitRef]:
        if set_name != "spike" or fold is not None:
            raise ValueError("the spike has one set, 'spike', without folds")
        return list(self._refs)

    def original(self, ref: CircuitRef) -> str:
        return self._texts[ref.sha]

    def seeds(self, card=None) -> list[int]:
        return list(SEEDS)

import time

BASIS = ["cx", "rz", "sx", "x"]
TOOLS = ("qiskit", "tket-swaps", "tket-noswaps", "pyzx")


def _qiskit(text: str, level: int, seed: int) -> str:
    from qiskit import QuantumCircuit, qasm2, transpile
    qc = transpile(QuantumCircuit.from_qasm_str(text), basis_gates=BASIS, optimization_level=level,
                   seed_transpiler=seed)
    return qasm2.dumps(qc)


def _tket(text: str, allow_swaps: bool) -> str:
    from pytket.circuit import OpType
    from pytket.passes import AutoRebase, FullPeepholeOptimise
    from pytket.qasm import circuit_from_qasm_str, circuit_to_qasm_str
    c = circuit_from_qasm_str(text)
    FullPeepholeOptimise(allow_swaps=allow_swaps).apply(c)
    c.replace_implicit_wire_swaps()  # D-081: QASM export drops an implicit permutation
    AutoRebase({OpType.CX, OpType.Rz, OpType.SX, OpType.X}).apply(c)
    return circuit_to_qasm_str(c)


def _pyzx(text: str) -> str:
    import pyzx as zx
    g = zx.Circuit.from_qasm(text).to_graph()
    zx.full_reduce(g)
    out = zx.extract_circuit(g.copy()).to_basic_gates().to_qasm()
    return _qiskit(out, 0, 1)  # D-082: PyZX emits H and CZ; rebase without optimising


def run_text(tool: str, text: str, *, seed: int) -> str:
    if tool == "qiskit":
        return _qiskit(text, 3, seed)
    if tool == "tket-swaps":
        return _tket(text, True)
    if tool == "tket-noswaps":
        return _tket(text, False)
    if tool == "pyzx":
        return _pyzx(text)
    raise ValueError(f"unknown tool {tool!r}; known: {', '.join(TOOLS)}")


def _run_tool(self: "SpikeHarness", tool: str, ref: CircuitRef, *, seed: int, time_budget_s: int) -> ToolRun:
    start = time.monotonic()
    out = run_text(tool, self.original(ref), seed=seed)
    return ToolRun(qasm=out, runtime_ms=int((time.monotonic() - start) * 1000))


SpikeHarness.run_tool = _run_tool
