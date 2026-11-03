"""The audit's tool calls: P0's `run_text`, with Qiskit's elided permutation made explicit.

Qiskit's ElidePermutations pass (optimization levels 2 and 3) removes swaps and records the permutation only in the
circuit's `final_layout` metadata, so the output circuit alone is not equivalent to the input. This is documented
behaviour, the same kind as tket's implicit swaps (D-081); P0's families hold no swap, the audit's random circuits do.
The permutation is appended as explicit swaps, so its cost is charged and the check sees the whole behaviour.
"""
from __future__ import annotations

import re
from decimal import Decimal

from spikes.qopt_audit import frozen
from spikes.qopt_p0.harness import BASIS, run_text

EXPONENT = re.compile(r"(?<![\w.])(\d+\.?\d*[eE][+-]?\d+)(?![\w.])")


def plain_decimals(text: str) -> str:
    """Write every number with an exponent as a plain decimal (9.6e-05 as 0.000096); nothing else changes."""
    return EXPONENT.sub(lambda m: format(Decimal(m.group(1)), "f"), text)


def run_tool(tool: str, text: str, *, seed: int = frozen.QISKIT_SEED) -> str:
    if tool == "pyzx":  # PyZX 0.10.7's reader rejects exponent notation: a known lead, bypassed here
        return run_text(tool, plain_decimals(text), seed=seed)
    if tool != "qiskit":
        return run_text(tool, text, seed=seed)
    from qiskit import QuantumCircuit, qasm2, transpile
    from qiskit.circuit.library import PermutationGate
    out = transpile(QuantumCircuit.from_qasm_str(text), basis_gates=BASIS, optimization_level=3, seed_transpiler=seed)
    layout = out.layout
    if layout is not None and layout.final_layout is not None:
        out.append(PermutationGate(list(layout.final_index_layout(filter_ancillas=True))), range(out.num_qubits))
        out = transpile(out, basis_gates=BASIS, optimization_level=0)
    return qasm2.dumps(out)
