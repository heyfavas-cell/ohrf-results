"""Gate-level reduction of a reproducer (delta debugging), and relabelling of the qubits it uses."""
from __future__ import annotations

import math
import re
from typing import Callable

from spikes.qopt_audit import frozen

HEADER = ("OPENQASM", "include", "qreg")


def _split(qasm: str) -> tuple[list[str], list[str]]:
    lines = [l for l in qasm.splitlines() if l.strip()]
    return [l for l in lines if l.startswith(HEADER)], [l for l in lines if not l.startswith(HEADER)]


def _join(head: list[str], gates: list[str]) -> str:
    return "\n".join(head + gates) + "\n"


def gate_count(qasm: str) -> int:
    return len(_split(qasm)[1])


def ddmin_gates(qasm: str, predicate: Callable[[str], bool], *, max_calls: int = frozen.REDUCE_MAX_CALLS) -> str:
    head, gates = _split(qasm)
    calls = 0

    def holds(subset: list[str]) -> bool:
        nonlocal calls
        calls += 1
        return predicate(_join(head, subset))

    if not holds(gates):
        return qasm
    n = 2
    while len(gates) >= 2 and calls < max_calls:
        size = math.ceil(len(gates) / n)
        chunks = [gates[i:i + size] for i in range(0, len(gates), size)]
        for chunk in chunks:  # a single chunk that fails on its own
            if calls >= max_calls:
                break
            if holds(chunk):
                gates, n = chunk, 2
                break
        else:
            for i in range(len(chunks)):  # a complement that still fails
                if calls >= max_calls:
                    break
                rest = [g for j, c in enumerate(chunks) if j != i for g in c]
                if rest and holds(rest):
                    gates, n = rest, max(n - 1, 2)
                    break
            else:
                if n >= len(gates):
                    break
                n = min(len(gates), n * 2)
    return _join(head, gates)


def compact(qasm: str) -> str:
    """Relabel the qubits the gates use as 0..k-1 and shrink the register to k."""
    head, gates = _split(qasm)
    used = sorted({int(i) for g in gates for i in re.findall(r"q\[(\d+)\]", g)})
    mapping = {old: new for new, old in enumerate(used)}
    gates = [re.sub(r"q\[(\d+)\]", lambda m: f"q[{mapping[int(m.group(1))]}]", g) for g in gates]
    head = [re.sub(r"qreg q\[\d+\];", f"qreg q[{max(len(used), 1)}];", h) for h in head]
    return _join(head, gates)
