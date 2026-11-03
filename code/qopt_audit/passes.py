"""Which Qiskit pass first changes a reproducer's operator (the mechanism label in the ledger's duplicate check).

The probe runs the audit's Qiskit pipeline (`tools.run_tool`) with a callback and compares the operator after every
pass with the input's. `ElidePermutations` removes swaps and records them only in `virtual_permutation_layout`, so
a probe that ignores the layout names it whenever a reproducer holds a swap (the label the ledger carries for
`random:680` and `random:119`). The layout-aware probe appends the recorded permutation before comparing, as
`run_tool` does for the final output.
"""
from __future__ import annotations

from spikes.qopt_audit import frozen
from spikes.qopt_audit.tolerance import phase_distance

CHANGED = 1e-9  # the oracle's floor for a distance that is not float noise
AFTER_PIPELINE = "after the pipeline"  # the change appears only once run_tool appends the final permutation


def trace(text: str, *, layout_aware: bool) -> list[tuple[str, float]]:
    """(pass name, distance to the input) after every pass, then for run_tool's final output."""
    from qiskit import QuantumCircuit, transpile
    from qiskit.circuit.library import PermutationGate
    from qiskit.converters import dag_to_circuit
    from spikes.qopt_audit.tools import run_tool
    from spikes.qopt_p0.harness import BASIS
    source = QuantumCircuit.from_qasm_str(text)
    steps: list[tuple[str, float]] = []

    def callback(**kw):
        circuit, props = dag_to_circuit(kw["dag"]), kw["property_set"]
        recorded = props["virtual_permutation_layout"]
        if layout_aware and recorded is not None:
            index = props["original_qubit_indices"]
            circuit.append(PermutationGate([index[recorded[i]] for i in range(circuit.num_qubits)]),
                           range(circuit.num_qubits))
        steps.append((kw["pass_"].name(), phase_distance(source, circuit)))

    transpile(source, basis_gates=BASIS, optimization_level=3, seed_transpiler=frozen.QISKIT_SEED, callback=callback)
    steps.append((AFTER_PIPELINE, phase_distance(source, QuantumCircuit.from_qasm_str(run_tool("qiskit", text)))))
    return steps


def first_breaking_pass(text: str, *, layout_aware: bool) -> str | None:
    """The first pass after which the operator differs from the input's; None when the output equals the input."""
    return next((name for name, distance in trace(text, layout_aware=layout_aware) if distance > CHANGED), None)
