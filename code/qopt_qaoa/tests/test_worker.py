import itertools
import json

from spikes.qopt_qaoa import worker

TEXT = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncx q[0],q[1];\ncx q[0],q[1];\ncx q[0],q[1];\n'
ONE = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncx q[0],q[1];\n'
SPEC = {"job": "passes", "case": "dev-6-x", "set": "dev"}


def fake_pool(calls=None):
    def drop(text, seed):
        if calls is not None:
            calls.append(("drop", seed))
        return ONE

    def broken(text, seed):
        raise ValueError("pass exploded")

    return {"drop": drop, "broken": broken, "q-level3": lambda t, s: (calls or []).append(("q-level3", s)) or ONE}


def test_every_pass_runs_alone_with_its_time_a_failure_is_recorded_and_the_seeded_pass_takes_every_seed(tmp_path):
    calls = []
    clock = itertools.count(0.0, 2.0).__next__
    result = worker.run_passes(dict(SPEC, out_dir=str(tmp_path), seeds=[1, 2, 3]), pool=fake_pool(calls), clock=clock,
                               start_text=(TEXT, TEXT))
    rows = {(r["pass"], r["seed"]): r for r in result["rows"]}
    assert result["input_cx"] == 3 and set(rows) == {("drop", 1), ("broken", 1), ("q-level3", 1), ("q-level3", 2),
                                                     ("q-level3", 3)}
    assert rows[("drop", 1)]["cx"] == 1 and rows[("drop", 1)]["seconds"] == 2.0
    assert rows[("broken", 1)]["cx"] is None and "pass exploded" in rows[("broken", 1)]["error"]
    assert (tmp_path / "drop-s1.qasm").read_text(encoding="utf-8") == ONE and ("drop", 2) not in calls


def test_a_search_job_writes_its_proposals_and_reports_its_clock_and_counts(tmp_path):
    clock = itertools.count(0.0, 1.0).__next__
    result = worker.run_search(dict(SPEC, job="search", budget=30, out_dir=str(tmp_path), proposals=2),
                               pool={"drop": fake_pool()["drop"]}, clock=clock, start_text=(TEXT, TEXT))
    assert result["kind"] == "search" and result["input_cx"] == 3 and len(result["proposals"]) == 2
    best = result["proposals"][0]
    assert best["cx"] == 1 and best["path"] == ["drop"] and (tmp_path / "proposal-0.qasm").exists()
    assert result["calls"] >= 1 and "elapsed_s" in result and result["cpu_s"] >= 0


def test_the_order_in_the_spec_limits_and_orders_the_passes_the_search_may_use(tmp_path):
    seen = []
    pool = {"a": lambda t, s: seen.append("a") or TEXT + "\n", "b": lambda t, s: seen.append("b") or ONE}
    worker.run_search(dict(SPEC, job="search", budget=1000, out_dir=str(tmp_path), order=["b"]), pool=pool,
                      clock=itertools.count(0.0, 1.0).__next__, start_text=(TEXT, TEXT))
    assert set(seen) == {"b"}


def test_the_thread_limits_pin_the_numerical_libraries_to_one_thread():
    assert set(worker.THREAD_LIMITS.values()) == {"1"} and "OMP_NUM_THREADS" in worker.THREAD_LIMITS


def test_main_reads_a_spec_file_and_writes_the_result_file(tmp_path, monkeypatch):
    spec = dict(SPEC, out_dir=str(tmp_path / "o"), names=["drop"])
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    monkeypatch.setattr(worker, "run_passes", lambda s: {"kind": "passes", "rows": [], "echo": s["case"]})
    worker.main([str(tmp_path / "spec.json"), str(tmp_path / "sub" / "result.json")])
    assert json.loads((tmp_path / "sub" / "result.json").read_text(encoding="utf-8"))["echo"] == "dev-6-x"
