import json

from spikes.qopt_audit import recheck

CIRCUIT = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


def _run_dir(tmp_path, kinds):
    shard = tmp_path / "run" / "shard-0"
    (shard / "circuits").mkdir(parents=True)
    rows = []
    for seed, kind in enumerate(kinds):
        (shard / "circuits" / f"random-random-{seed}.qasm").write_text(CIRCUIT, encoding="utf-8")
        rows.append({"key": f"random:random:{seed}:qiskit", "case_kind": "random", "case": "random", "seed": seed,
                     "tool": "qiskit", "kind": kind, "qcec": "equivalent" if kind == "verified" else "",
                     "qubits": 2})
    (shard / "log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return tmp_path / "run"


def _lines(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


def test_emit_writes_one_pair_per_verified_output_and_skips_the_rest(tmp_path):
    run = _run_dir(tmp_path, ["verified", "unverified", "verified", "wrong_output"])
    summary = recheck.emit(run, tmp_path / "re", tool=lambda tool, text: text)
    pairs = _lines(tmp_path / "re" / "pairs.jsonl")
    assert summary == {"emitted": 2, "errors": 0} and [p["key"] for p in pairs] == ["random:random:0:qiskit",
                                                                                     "random:random:2:qiskit"]
    assert all((tmp_path / "re" / p["output"]).read_text(encoding="utf-8") == CIRCUIT for p in pairs)


def test_emit_resumes_and_records_a_tool_that_now_raises(tmp_path):
    run = _run_dir(tmp_path, ["verified", "verified"])

    def flaky(tool, text):
        raise ValueError("boom")
    assert recheck.emit(run, tmp_path / "re", tool=flaky) == {"emitted": 0, "errors": 2}
    assert recheck.emit(run, tmp_path / "re", tool=flaky) == {"emitted": 0, "errors": 0}  # nothing repeated
    assert {p["error"] for p in _lines(tmp_path / "re" / "pairs.jsonl")} == {"ValueError: boom"}


def test_emit_records_a_missing_input_circuit_instead_of_stopping(tmp_path):
    run = _run_dir(tmp_path, ["verified", "verified"])
    (run / "shard-0" / "circuits" / "random-random-0.qasm").unlink()
    assert recheck.emit(run, tmp_path / "re", tool=lambda tool, text: text) == {"emitted": 1, "errors": 1}
    assert _lines(tmp_path / "re" / "pairs.jsonl")[0]["error"].startswith("KeyError")


def test_check_re_decides_every_pair_once_with_the_audits_own_procedure(tmp_path, monkeypatch):
    run = _run_dir(tmp_path, ["verified", "verified", "verified"])
    recheck.emit(run, tmp_path / "re", tool=lambda tool, text: text)
    answers = iter([("equivalent", "default"), ("not_equivalent", "default"), ("no_information", "alternating")])
    monkeypatch.setattr(recheck, "_decide", lambda original, candidate, *, workdir: next(answers))
    recheck.check(tmp_path / "re", shard="0/1")
    recheck.check(tmp_path / "re", shard="0/1")  # resumes: nothing is checked twice
    rows = _lines(tmp_path / "re" / "checks-0.jsonl")
    assert [r["answer"] for r in rows] == ["equivalent", "not_equivalent", "no_information"]
    assert all(r["qcec_version"] for r in rows)


def test_the_report_counts_confirmed_contradicted_and_unconfirmed_and_lists_every_contradiction(tmp_path):
    out = tmp_path / "re"
    out.mkdir()
    (out / "pairs.jsonl").write_text("".join(json.dumps({"key": f"k{i}", "tool": "qiskit", "qubits": 2}) + "\n"
                                             for i in range(4)), encoding="utf-8")
    checks = [("k0", "equivalent"), ("k1", "equivalent_up_to_global_phase"), ("k2", "not_equivalent"),
              ("k3", "hard_timeout")]
    (out / "checks-0.jsonl").write_text("".join(json.dumps({"key": k, "answer": a, "checker": "default",
                                                            "seconds": 1.0, "qcec_version": "3.11.0"}) + "\n"
                                                for k, a in checks), encoding="utf-8")
    text = recheck.report(out)
    assert "confirmed: 2" in text and "contradicted: 1" in text and "unconfirmed: 1" in text and "- k2 " in text
