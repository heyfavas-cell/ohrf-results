import json
import re

import pytest

from spikes.qopt_audit import oracle
from spikes.qopt_audit.generate import Case, random_circuit
from spikes.qopt_audit.oracle import Observation
from spikes.qopt_audit.reduce import gate_count
from spikes.qopt_audit.triage import (WITNESS_MIN, Triage, attention_record, main, needs_attention, tiny_angle_only,
                                     triage_circuit, triage_run, witness_gap)

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
TINY = HEAD + "qreg q[2];\nh q[0];\nh q[1];\ncu1(0.0001) q[0],q[1];\nh q[0];\n"
DROP_TINY = lambda t: t.replace("cu1(0.0001) q[0],q[1];\n", "")  # noqa: E731
DROP_RZ = lambda t: "\n".join(l for l in t.splitlines() if not l.startswith("rz")) + "\n"  # noqa: E731


def test_a_dropped_tiny_controlled_phase_has_a_witness_and_a_faithful_output_has_none():
    assert witness_gap(TINY, DROP_TINY(TINY)) > WITNESS_MIN
    assert witness_gap(TINY, TINY) < 1e-14


def test_a_witness_needs_no_qcec_and_works_at_the_largest_registered_size():
    big = HEAD + "qreg q[22];\n" + "".join(f"h q[{i}];\n" for i in range(22)) + "rz(0.3) q[21];\n"
    assert witness_gap(big, big.replace("rz(0.3) q[21];\n", "")) > 1e-3


def test_only_tiny_angles_are_the_known_approximation_family():
    assert tiny_angle_only(TINY, 2e-4)
    assert not tiny_angle_only(HEAD + "qreg q[1];\nrz(0.5) q[0];\n", 2e-4)
    assert tiny_angle_only(HEAD + "qreg q[1];\nrz(6.283185307179586) q[0];\n", 2e-4)  # a full turn is the identity
    assert tiny_angle_only(HEAD + "qreg q[1];\nrz(-9.6e-05) q[0];\n", 2e-4)
    assert not tiny_angle_only(HEAD + "qreg q[1];\nrz(9.6e-05) q[0];\nrx(0.1) q[0];\n", 2e-4)


def test_a_tiny_drop_is_reduced_to_one_gate_and_filed_as_the_known_qiskit_issue(tmp_path, monkeypatch):
    # QCEC's default runs its checkers in parallel and on this drop answers no_information in about one call in
    # eight; the alternating re-decision then moves the second opinion to the simulation, which cannot see a drop
    # this small. Pin the default answer to the exact checker's so the test checks triage, not the race.
    real = oracle.outcome
    monkeypatch.setattr(oracle, "outcome", lambda original, candidate, *, config=None, **kw: real(
        original, candidate, config=config or oracle.ALTERNATING, **kw))
    padded = TINY.replace("h q[1];\n", "h q[1];\n" + "".join(f"h q[{i % 2}];\ncx q[0],q[1];\n" for i in range(30)))
    result = triage_circuit(padded, "qiskit", DROP_TINY, workdir=tmp_path)
    assert gate_count(result.reduced) == 1 and "cu1(0.0001)" in result.reduced
    assert result.kind == "wrong_output" and result.duplicate_of == "Qiskit/qiskit#16864"


def test_a_dropped_ordinary_rotation_is_a_new_candidate_not_a_known_issue(tmp_path):
    source = HEAD + "qreg q[3];\n" + "h q[0];\ncx q[0],q[1];\nrz(0.7) q[2];\n" * 5
    result = triage_circuit(source, "qiskit", DROP_RZ, workdir=tmp_path)
    assert result.kind == "wrong_output" and result.duplicate_of is None and gate_count(result.reduced) == 1


def test_an_output_with_no_witness_is_not_triaged(tmp_path):
    assert triage_circuit(TINY, "qiskit", lambda t: t, workdir=tmp_path) is None


@pytest.mark.xfail(strict=True, reason="P0c: the run judges tolerance on the full circuit's gate count (oracle.py, "
                                       "gates=None), and triage never takes a within_tolerance row")
def test_a_drop_beyond_tolerance_once_reduced_reaches_triage_from_a_long_circuit(tmp_path, monkeypatch):
    from spikes.qopt_audit.run import run_batch
    # 120 gates on 4 qubits: the full-circuit allowance (120 * 1e-5) covers the drop (D about 5e-4); one gate does not.
    padding = "".join(f"h q[{i % 4}];\ncx q[{i % 4}],q[{(i + 1) % 4}];\nt q[{(i + 2) % 4}];\n" for i in range(20))
    source = HEAD + "qreg q[4];\n" + padding + "rz(0.001) q[2];\n" + padding
    drop = lambda text: re.sub(r"^rz\(0\.001\) q\[\d+\];\n", "", text, flags=re.M)  # noqa: E731
    monkeypatch.setattr("spikes.qopt_audit.run.build", lambda case, bases: source)
    monkeypatch.setattr("spikes.qopt_audit.triage.run_tool", lambda tool, text: drop(text))
    run_batch([Case("random", "padded", 1)], {}, out=tmp_path / "run" / "shard-0", budget_s=600,
              tools={"qiskit": drop})
    main([str(tmp_path / "run"), str(tmp_path / "findings")])
    record = tmp_path / "findings" / "random_padded_1_qiskit" / "triage.json"
    assert record.exists(), "the case never reached triage"
    found = json.loads(record.read_text("utf-8"))
    assert found["witness"] and found["kind"] == "wrong_output" and found["reduced_gates"] == 1


def test_random_circuits_through_the_real_qiskit_tool_have_no_witness(tmp_path):
    from spikes.qopt_audit.tools import run_tool
    text = random_circuit(12)
    assert witness_gap(text, run_tool("qiskit", text)) < WITNESS_MIN


def _run_dir(tmp_path):
    shard = tmp_path / "run" / "shard-0"
    (shard / "circuits").mkdir(parents=True)
    (shard / "circuits" / "random-random-3.qasm").write_text(TINY, encoding="utf-8", newline="\n")
    rows = [{"key": "random:random:3:qiskit", "case_kind": "random", "case": "random", "seed": 3, "tool": "qiskit",
             "kind": "unverified", "observed_at": "2026-10-28T09:00:00+00:00"},
            {"key": "random:random:3:pyzx", "case_kind": "random", "case": "random", "seed": 3, "tool": "pyzx",
             "kind": "verified", "observed_at": "2026-10-28T09:00:05+00:00"}]
    (shard / "log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return tmp_path / "run"


def test_triage_stamps_when_a_case_was_seen_and_triaged_and_returns_only_new_entries(tmp_path):
    def fake(text, tool, fn, *, workdir):
        return Triage("wrong_output", TINY, 1e-3, None, Observation("wrong_output", tool, qcec="not_equivalent"))

    findings = tmp_path / "findings"
    entries = triage_run(_run_dir(tmp_path), findings, triage=fake, now=lambda: "2026-10-28T10:30:00+00:00")
    assert [e["key"] for e in entries] == ["random:random:3:qiskit"]  # verified rows are not triaged
    saved = json.loads((findings / "random_random_3_qiskit" / "triage.json").read_text("utf-8"))
    assert saved["observed_at"] == "2026-10-28T09:00:00+00:00" and saved["triaged_at"] == "2026-10-28T10:30:00+00:00"
    assert triage_run(_run_dir(tmp_path / "again"), findings, triage=fake) == []  # already triaged: not again


def test_only_unexplained_candidates_need_a_person():
    base = {"key": "k", "witness": True, "kind": "wrong_output", "duplicate_of": None}
    assert needs_attention(base)
    assert needs_attention({**base, "kind": "oracle_disagreement"})  # a lead on the checker itself
    assert not needs_attention({**base, "duplicate_of": "Qiskit/qiskit#16864"})
    assert not needs_attention({"key": "k", "witness": False})


def test_the_filing_clock_starts_when_the_case_was_seen_not_when_it_was_triaged():
    seen = {"key": "k", "observed_at": "2026-10-19T12:00:00+00:00", "triaged_at": "2026-10-27T09:59:00+00:00"}
    record = attention_record(seen)
    assert record["due_by"] == "2026-10-22T12:00:00+00:00" and record["lag_h"] == 189.98
    unseen = attention_record({"key": "k", "observed_at": None, "triaged_at": "2026-10-27T09:59:00+00:00"})
    assert unseen["due_by"] == "2026-10-30T09:59:00+00:00" and unseen["lag_h"] is None  # rows logged before the field
