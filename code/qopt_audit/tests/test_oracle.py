from spikes.qopt_audit import frozen
from spikes.qopt_audit.oracle import crash_signature, observe

A = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];
rz(0.5) q[1];
cx q[0],q[1];
"""


def test_a_faithful_tool_is_verified(tmp_path):
    assert observe(A, "qiskit", lambda t: t, workdir=tmp_path).kind == "verified"


def test_a_tool_that_drops_a_rotation_is_a_wrong_output_confirmed_by_a_second_checker(tmp_path):
    obs = observe(A, "qiskit", lambda t: t.replace("rz(0.5) q[1];\n", ""), workdir=tmp_path)
    assert obs.kind == "wrong_output"
    assert obs.confirmations == frozen.CONFIRM_RUNS and obs.second_opinion == "not_equivalent"
    assert obs.distance is not None and obs.distance > 0.1


def test_a_tiny_rotation_dropped_within_the_recorded_tolerance_does_not_count(tmp_path):
    source = A.replace("rz(0.5)", "rz(1e-07)")
    obs = observe(source, "qiskit", lambda t: t.replace("rz(1e-07) q[1];\n", ""), workdir=tmp_path)
    assert obs.kind == "within_tolerance"  # QCEC says not_equivalent, but 1e-7 is under 4 gates * 1e-5


def test_the_same_drop_above_the_tolerance_does_count(tmp_path):
    source = A.replace("rz(0.5)", "rz(0.001)")
    obs = observe(source, "qiskit", lambda t: t.replace("rz(0.001) q[1];\n", ""), workdir=tmp_path)
    assert obs.kind == "wrong_output"


def test_a_tool_that_raises_is_a_crash_with_a_stable_signature(tmp_path):
    def boom(text):
        raise ValueError("bad angle 9.6e-05 at line 12")
    obs = observe(A, "pyzx", boom, workdir=tmp_path)
    assert obs.kind == "crash" and obs.signature == "pyzx:ValueError:bad angle #.#e-# at line #"
    assert crash_signature("pyzx", ValueError("x" * 500)).__len__() <= 120


def test_a_hidden_output_permutation_is_unverified_not_wrong(tmp_path):
    hidden = A.replace("h q[0];", "// o 1 0\nh q[0];")
    assert observe(A, "tket-swaps", lambda t: hidden, workdir=tmp_path).kind == "unverified"


def test_an_output_qcec_cannot_decide_is_unverified(tmp_path, monkeypatch):
    monkeypatch.setattr("spikes.qopt_audit.oracle.outcome", lambda *a, **k: "no_information")
    assert observe(A, "qiskit", lambda t: t, workdir=tmp_path).kind == "unverified"


def test_a_checker_disagreement_is_never_a_wrong_output(tmp_path, monkeypatch):
    calls = iter(["not_equivalent", "not_equivalent"])
    monkeypatch.setattr("spikes.qopt_audit.oracle.outcome", lambda *a, **k: next(calls))
    monkeypatch.setattr("spikes.qopt_audit.oracle._alternating", lambda *a, **k: "equivalent")
    assert observe(A, "qiskit", lambda t: t, workdir=tmp_path).kind == "oracle_disagreement"


BIG_REGISTER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[12];\n'


def test_a_phase_only_wrong_output_is_decided_every_time_not_left_to_a_race_between_checkers(tmp_path):
    # QCEC's default answers no_information on this about a third of the time (ZX and simulation disagree).
    source = BIG_REGISTER + "rz(0.7) q[5];\n"
    kinds = {observe(source, "qiskit", lambda t: BIG_REGISTER, workdir=tmp_path).kind for _ in range(12)}
    assert kinds == {"wrong_output"}


def test_an_undecided_default_answer_is_re_decided_by_the_alternating_checker(tmp_path, monkeypatch):
    seen = []

    def fake(original, candidate, *, workdir, timeout_s, hard_wall_s, config=None):
        seen.append(config)
        return "no_information" if config is None else "equivalent"
    monkeypatch.setattr("spikes.qopt_audit.oracle.outcome", fake)
    assert observe(A, "qiskit", lambda t: t, workdir=tmp_path).kind == "verified"
    assert seen[0] is None and seen[1]["run_alternating_checker"] is True
