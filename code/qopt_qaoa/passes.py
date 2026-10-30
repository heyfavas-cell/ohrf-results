"""The pass pool (plan, "The pass pool and the search"): named passes of the pinned tools, each `(qasm, seed) -> qasm`.

Every pass returns a circuit rebased to {cx, rz, sx, x} so that states from different tools can follow each other
and CNOT counts are comparable. PyZX passes run behind a wall in a worker process that is killed and replaced when
a call outlasts it (P0c, run change 3).
"""
from __future__ import annotations

import multiprocessing as mp
from typing import Callable

from spikes.qopt_p0.harness import BASIS
from spikes.qopt_qaoa import frozen

Pass = Callable[[str, int], str]


def to_basis(text: str) -> str:
    from qiskit import QuantumCircuit, qasm2, transpile
    return qasm2.dumps(transpile(QuantumCircuit.from_qasm_str(text), basis_gates=BASIS, optimization_level=0))


def _qiskit_passes(make: Callable[[], list]) -> Pass:
    def run(text: str, seed: int) -> str:
        from qiskit import QuantumCircuit, qasm2
        from qiskit.transpiler import PassManager
        return to_basis(qasm2.dumps(PassManager(make()).run(QuantumCircuit.from_qasm_str(text))))
    return run


def _q_l3(text: str, seed: int) -> str:
    from qiskit import QuantumCircuit, qasm2, transpile
    return qasm2.dumps(transpile(QuantumCircuit.from_qasm_str(text), basis_gates=BASIS, optimization_level=3,
                                 seed_transpiler=seed))


def _tket(make: Callable[[], object], *, accepts: tuple[str, ...] | None = None) -> Pass:
    """`accepts` names the gate set the pass can read; the circuit is rebased to it first (GreedyPauliSimp rejects sx)."""
    def run(text: str, seed: int) -> str:
        from pytket.circuit import OpType
        from pytket.passes import AutoRebase
        from pytket.qasm import circuit_from_qasm_str, circuit_to_qasm_str
        c = circuit_from_qasm_str(text)
        if accepts:
            AutoRebase({getattr(OpType, n) for n in accepts}).apply(c)
        make().apply(c)
        c.replace_implicit_wire_swaps()  # D-081: QASM export drops an implicit permutation
        AutoRebase({OpType.CX, OpType.Rz, OpType.SX, OpType.X}).apply(c)
        return to_basis(circuit_to_qasm_str(c))
    return run


def _pyzx_direct(name: str, text: str) -> str:
    import pyzx as zx
    g = zx.Circuit.from_qasm(text).to_graph()
    {"full_reduce": zx.full_reduce, "clifford_simp": zx.clifford_simp}[name](g)
    return to_basis(zx.extract_circuit(g.copy()).to_basic_gates().to_qasm())


def _qiskit_pool() -> dict[str, Pass]:
    def p(name, *args, **kw):
        import qiskit.transpiler.passes as Q
        return getattr(Q, name)(*args, **kw)

    def inverse_pairs():
        from qiskit.circuit.library import CXGate, CZGate, HGate, SwapGate, XGate, ZGate
        return [CXGate(), CZGate(), HGate(), SwapGate(), XGate(), ZGate()]

    return {
        "q-1q-decompose": _qiskit_passes(lambda: [p("Optimize1qGatesDecomposition", basis=["rz", "sx", "x"])]),
        "q-commutative-cancel": _qiskit_passes(lambda: [p("CommutativeCancellation")]),
        "q-commutative-inverse": _qiskit_passes(lambda: [p("CommutativeInverseCancellation")]),
        "q-inverse-cancel": _qiskit_passes(lambda: [p("InverseCancellation", inverse_pairs())]),
        "q-peephole-2q": _qiskit_passes(lambda: [p("Collect2qBlocks"), p("ConsolidateBlocks", basis_gates=BASIS),
                                                  p("UnitarySynthesis", basis_gates=BASIS)]),
        "q-linear-functions": _qiskit_passes(lambda: [p("CollectLinearFunctions"), p("HighLevelSynthesis")]),
        "q-level3": _q_l3,
    }


def _tket_pool() -> dict[str, Pass]:
    def p(name, *args, **kw):
        import pytket.passes as P
        return lambda: getattr(P, name)(*args, **kw)

    return {
        "t-peephole": _tket(p("FullPeepholeOptimise", allow_swaps=False)),
        "t-peephole-swaps": _tket(p("FullPeepholeOptimise", allow_swaps=True)),
        "t-clifford": _tket(p("CliffordSimp")),
        "t-kak": _tket(p("KAKDecomposition")),
        "t-commute-multis": _tket(p("CommuteThroughMultis")),
        "t-remove-redundancies": _tket(p("RemoveRedundancies")),
        "t-zz-to-rz": _tket(p("ZZPhaseToRz")),
        "t-pauli-simp": _tket(p("PauliSimp")),
        "t-greedy-pauli": _tket(p("GreedyPauliSimp"), accepts=("CX", "Rz", "H")),
    }


PYZX_PASSES = ("full_reduce", "clifford_simp")
SEEDED = {"q-level3"}


def _serve(conn) -> None:
    conn.send("ready")
    while True:
        job = conn.recv()
        if job is None:
            return
        name, text = job
        try:
            conn.send(("ok", _pyzx_direct(name, text)))
        except Exception as exc:
            conn.send(("error", f"{type(exc).__name__}: {str(exc)[:120]}"))


class WalledPyzx:
    """One long-lived PyZX worker; a call that outlasts the wall kills it and the next call starts a fresh one."""

    def __init__(self, wall_s: float = frozen.PYZX_WALL_S, serve=_serve) -> None:
        self.wall_s, self._serve, self._proc, self._conn = wall_s, serve, None, None

    def stop(self) -> None:
        if self._proc is not None and self._proc.pid is not None:
            self._proc.kill()
            self._proc.join()
        self._proc = self._conn = None

    def _start(self) -> None:
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe()
        self._proc = ctx.Process(target=self._serve, args=(child,), daemon=True)
        self._proc.start()
        child.close()
        self._conn = parent
        if not parent.poll(300) or parent.recv() != "ready":
            self.stop()
            raise RuntimeError("the PyZX worker did not start")

    def call(self, name: str, text: str) -> str:
        if self._proc is None or not self._proc.is_alive():
            self.stop()
            self._start()
        self._conn.send((name, text))
        if not self._conn.poll(self.wall_s):
            self.stop()
            raise TimeoutError(f"PyZX {name} outlasted its {self.wall_s} s wall")
        kind, value = self._conn.recv()
        if kind != "ok":
            raise RuntimeError(value)
        return value


def pool(walled: WalledPyzx | None = None) -> dict[str, Pass]:
    walled = walled or WalledPyzx()
    out = {**_qiskit_pool(), **_tket_pool()}
    for name in PYZX_PASSES:
        out[f"z-{name.replace('_', '-')}"] = (lambda n: lambda text, seed: walled.call(n, text))(name)
    return out
