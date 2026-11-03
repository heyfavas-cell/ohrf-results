import json
import sys

from spikes.qopt_audit.build_ledger import build, collect
from spikes.qopt_audit.ledger import load

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
TINY = HEAD + "qreg q[2];\nh q[0];\nh q[1];\ncu1(9.6e-05) q[0],q[1];\nh q[0];\n"


def record(findings, key, reduced, **kw):
    folder = findings / "spike" / key.replace(":", "_")
    folder.mkdir(parents=True)
    (folder / "reduced.qasm").write_text(reduced, encoding="utf-8")
    entry = {"key": key, "witness": True, "kind": "wrong_output", "reduced_gates": 1, "distance": 2.4e-05, **kw}
    (folder / "triage.json").write_text(json.dumps(entry), encoding="utf-8")


def note(**kw):
    base = {"answers": ["not_equivalent", "not_equivalent"], "alternating": "not_equivalent",
            "pass": "TwoQubitPeepholeOptimization", "triage_kind": "wrong_output", "distance": None,
            "pinned_gap": 6e-11, "latest_gap": 6e-11}
    base.update(kw)
    return base


def test_rows_follow_the_measured_notes_in_key_order(tmp_path):
    findings = tmp_path / "findings"
    record(findings, "random:random:9:qiskit", TINY, kind="verified", distance=None, reduced_gates=5)
    record(findings, "boundary:qaoa-10:1:qiskit", TINY)
    (findings / "spike" / "boundary_qaoa-6_2_qiskit").mkdir()  # no witness: no row
    (findings / "spike" / "boundary_qaoa-6_2_qiskit" / "triage.json").write_text('{"key": "x", "witness": false}')
    notes = tmp_path / "notes.json"
    notes.write_text(json.dumps({"qiskit_latest": "2.6.1", "cases": {
        "boundary:qaoa-10:1:qiskit": note(),
        "random:random:9:qiskit": {**note(answers=["equivalent_up_to_global_phase"] * 2, distance=3.8e-05,
                                          alternating="equivalent_up_to_global_phase"), "pass": "ElidePermutations"}}}))
    assert build(findings, notes, tmp_path / "ledger.jsonl") == 2
    known, other = load(tmp_path / "ledger.jsonl")
    assert known.id == "boundary:qaoa-10:1:qiskit" and known.duplicate_of == "Qiskit/qiskit#16864"
    assert known.proved_twice and known.second_opinion_ok and known.tolerance_ok and known.reproduces_latest
    assert known.reproducer_qubits == 2 and known.search_url.endswith("approximation_degree")
    assert other.distance == 3.8e-05 and other.duplicate_of is None and other.search_url is None
    assert not other.proved_twice and not other.second_opinion_ok and not other.tolerance_ok  # 3.8e-05 <= 5 * 1e-05


def test_a_witness_under_the_floor_at_either_version_does_not_reproduce(tmp_path):
    findings = tmp_path / "findings"
    record(findings, "boundary:qaoa-10:1:qiskit", TINY, distance=5e-06)
    notes = tmp_path / "notes.json"
    notes.write_text(json.dumps({"cases": {"boundary:qaoa-10:1:qiskit": note(pinned_gap=5e-12, latest_gap=5e-12)}}))
    build(findings, notes, tmp_path / "ledger.jsonl")
    (row,) = load(tmp_path / "ledger.jsonl")
    assert not row.reproduces_latest and not row.tolerance_ok


def test_collect_measures_only_what_the_notes_lack(tmp_path):
    findings = tmp_path / "findings"
    record(findings, "boundary:qaoa-10:1:qiskit", TINY)
    record(findings, "boundary:qaoa-10:2:qiskit", TINY)
    notes = tmp_path / "out" / "notes.json"
    notes.parent.mkdir()
    notes.write_text(json.dumps({"qiskit_latest": None, "cases": {"boundary:qaoa-10:1:qiskit": {
        "answers": ["kept", "kept"], "alternating": "kept"}}}))
    drop = lambda tool, text: text.replace("cu1(9.6e-05) q[0],q[1];\n", "")  # noqa: E731
    assert collect(findings, notes, latest_python=sys.executable, tool=drop)["latest"] == 2
    cases = json.loads(notes.read_text())["cases"]
    assert cases["boundary:qaoa-10:1:qiskit"]["answers"] == ["kept", "kept"]
    fresh = cases["boundary:qaoa-10:2:qiskit"]
    assert all(a in ("not_equivalent", "no_information", "probably_not_equivalent") for a in fresh["answers"])
    assert fresh["pass"] == "TwoQubitPeepholeOptimization" and fresh["pinned_gap"] > 1e-11
    assert fresh["latest_gap"] > 1e-11  # the real pipeline in the other interpreter, not the test's tool
