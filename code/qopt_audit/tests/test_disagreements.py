import json

from spikes.qopt_audit.disagreements import (OTHER, RACE, SECOND_OPINION_TIMEOUT, ZX, classify, probe, probe_run,
                                             report)
from spikes.qopt_p0.verify import outcome

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
TINY = HEAD + "qreg q[2];\nh q[0];\nh q[1];\ncu1(0.0001) q[0],q[1];\nh q[0];\n"
DROPPED = TINY.replace("cu1(0.0001) q[0],q[1];\n", "")


def calls(*answers):
    return [{"answer": a, "seconds": 1.0} for a in answers]


def result(default, alternating="no_information", zx=("probably_not_equivalent",) * 3):
    return {"default": calls(*default), "alternating": calls(alternating)[0],
            "simulation": calls("probably_equivalent")[0], "zx": calls(*zx)}


FAILED_PROOF = {"confirmations": 1, "second_opinion": ""}
PROVED_TWICE = {"confirmations": 2, "second_opinion": "no_information"}
RACING = ["not_equivalent"] * 8 + ["no_information"] * 2


def test_a_failed_proof_on_a_racing_default_that_the_alternating_checker_cannot_redecide_is_the_race():
    assert classify(result(RACING), FAILED_PROOF) == RACE
    assert classify(result(["not_equivalent"] * 6 + ["probably_not_equivalent"] * 4), FAILED_PROOF) == RACE
    assert classify(result(["not_equivalent"] * 10), FAILED_PROOF) == OTHER  # no race seen: the log is unexplained


def test_proved_twice_with_an_alternating_checker_that_cannot_decide_is_a_second_opinion_timeout():
    assert classify(result(["not_equivalent"] * 10), PROVED_TWICE) == SECOND_OPINION_TIMEOUT
    assert classify(result(RACING), PROVED_TWICE) == SECOND_OPINION_TIMEOUT  # a race seen later did not cause it


def test_anything_zx_does_not_see_or_that_is_not_explained_is_other():
    assert classify(result(["not_equivalent"] * 10, zx=("equivalent",) * 3), PROVED_TWICE) == OTHER
    assert classify(result(["not_equivalent"] * 10, alternating="not_equivalent"), PROVED_TWICE) == OTHER
    assert classify(result(RACING, alternating="not_equivalent"), FAILED_PROOF) == OTHER


def test_the_zx_checker_alone_sees_a_tiny_controlled_phase_drop(tmp_path):
    assert all(outcome(TINY, DROPPED, workdir=tmp_path, timeout_s=60, config=ZX) in ("not_equivalent",
                                                                                     "probably_not_equivalent")
               for _ in range(5))


def test_a_probe_of_a_real_pair_records_every_answer(tmp_path):
    out = probe(TINY, DROPPED, workdir=tmp_path, default_calls=3, zx_calls=2)
    assert len(out["default"]) == 3 and len(out["zx"]) == 2
    assert all(c["answer"] in ("not_equivalent", "no_information") for c in out["default"])
    assert out["alternating"]["answer"] == "not_equivalent"  # small enough for the exact checker alone
    assert classify(out, PROVED_TWICE) == OTHER


def test_the_run_probe_takes_only_oracle_disagreements_and_resumes(tmp_path):
    run, out = tmp_path / "run", tmp_path / "out"
    (run / "shard-0" / "circuits").mkdir(parents=True)
    (run / "shard-0" / "circuits" / "boundary-qft-6-1.qasm").write_text(TINY, encoding="utf-8")
    rows = [{"key": "boundary:qft-6:1:qiskit", "kind": "oracle_disagreement", "case_kind": "boundary",
             "case": "qft-6", "seed": 1, "tool": "qiskit", "qubits": 2, "confirmations": 2,
             "second_opinion": "no_information", "seconds": 60.0},
            {"key": "boundary:qft-6:1:pyzx", "kind": "verified", "case_kind": "boundary", "case": "qft-6", "seed": 1,
             "tool": "pyzx", "qubits": 2}]
    (run / "shard-0" / "log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    drop = lambda tool, text: text.replace("cu1(0.0001) q[0],q[1];\n", "")  # noqa: E731
    assert probe_run(run, out, tool=drop, default_calls=2, zx_calls=1) == 1
    assert probe_run(run, out, tool=drop, default_calls=2, zx_calls=1) == 0
    assert "`boundary:qft-6:1:qiskit` | 2 | 2, no_information" in report(out)
