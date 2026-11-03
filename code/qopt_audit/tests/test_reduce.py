from spikes.qopt_audit import oracle
from spikes.qopt_audit.reduce import compact, ddmin_gates, gate_count

BIG = "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[12];\n" + "".join(
    f"h q[{i % 12}];\ncx q[{i % 12}],q[{(i + 1) % 12}];\n" + ("rz(0.7) q[5];\n" if i == 20 else "") for i in range(40))


def drops_rz(text):  # a faulty tool that removes every rz
    return "\n".join(l for l in text.splitlines() if not l.startswith("rz")) + "\n"


def test_reduction_keeps_the_failure_and_ends_with_few_gates(tmp_path):
    fails = lambda t: oracle.observe(t, "qiskit", drops_rz, workdir=tmp_path).kind == "wrong_output"
    small = ddmin_gates(BIG, fails)
    assert fails(small) and gate_count(small) <= 3 and gate_count(BIG) > 70


def test_a_predicate_that_does_not_hold_returns_the_input_unchanged():
    assert ddmin_gates(BIG, lambda t: False) == BIG


def test_the_call_budget_is_respected():
    calls = []
    def never_shrinks(t):
        calls.append(1)
        return t == BIG
    ddmin_gates(BIG, never_shrinks, max_calls=25)
    assert len(calls) <= 26


def test_compact_relabels_used_qubits_and_shrinks_the_register():
    text = compact("OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[22];\nh q[3];\ncx q[3],q[17];\n")
    assert "qreg q[2];" in text and "cx q[0],q[1];" in text
