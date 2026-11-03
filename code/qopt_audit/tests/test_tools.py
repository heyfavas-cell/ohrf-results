from spikes.qopt_audit.generate import random_circuit
from spikes.qopt_audit.tolerance import phase_distance
from spikes.qopt_audit.tools import run_tool
from spikes.qopt_p0.harness import run_text
from spikes.qopt_p0.verify import verified

SWAPS = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[3];\nh q[0];\nswap q[0],q[1];\nswap q[1],q[2];\ncx q[0],q[2];\n'


def test_qiskit_level_3_swaps_it_elided_are_made_explicit_in_the_output(tmp_path):
    # Qiskit's ElidePermutations (levels 2 and 3) deletes swaps and records the permutation as layout metadata only.
    out = run_tool("qiskit", SWAPS)
    assert verified(SWAPS, out, workdir=tmp_path, timeout_s=30)


def test_the_unadjusted_tool_is_the_artifact_this_wrapper_removes(tmp_path):
    assert not verified(SWAPS, run_text("qiskit", SWAPS, seed=1), workdir=tmp_path, timeout_s=30)


def test_random_circuits_with_swaps_keep_their_unitary_through_qiskit_level_3():
    from qiskit import QuantumCircuit
    for seed in (3, 12, 13):
        text = random_circuit(seed)
        out = run_tool("qiskit", text)
        assert phase_distance(QuantumCircuit.from_qasm_str(text), QuantumCircuit.from_qasm_str(out)) < 1e-6, seed


def test_the_other_tools_are_run_exactly_as_in_p0():
    for tool in ("tket-swaps", "tket-noswaps", "pyzx"):
        assert run_tool(tool, SWAPS) == run_text(tool, SWAPS, seed=1)


SCI = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\nrz(9.6e-05) q[1];\ncx q[0],q[1];\nrz(-2.5e-1) q[0];\nrz(1E-3) q[1];\n'


def test_pyzx_reads_scientific_notation_angles_through_a_plain_decimal_rewrite(tmp_path):
    # PyZX 0.10.7's QASM reader rejects `9.6e-05` (a known lead, reported separately); the audit tests PyZX's
    # optimiser on those angles by writing them as plain decimals first.
    out = run_tool("pyzx", SCI)
    assert verified(SCI, out, workdir=tmp_path, timeout_s=30)


def test_the_plain_decimal_rewrite_changes_only_exponent_numbers():
    from spikes.qopt_audit.tools import plain_decimals
    assert plain_decimals("rz(9.6e-05) q[1];") == "rz(0.000096) q[1];"
    assert plain_decimals("rz(-2.5e-1) q[0];\nrz(1E-3) q[1];") == "rz(-0.25) q[0];\nrz(0.001) q[1];"
    assert plain_decimals("rz(0.5) q[0];\nqreg q[12];\ncx q[1],q[10];") == "rz(0.5) q[0];\nqreg q[12];\ncx q[1],q[10];"
    assert plain_decimals("rz(pi/2) q[0];") == "rz(pi/2) q[0];"
