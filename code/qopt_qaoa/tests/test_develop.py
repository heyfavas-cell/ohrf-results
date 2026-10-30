import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from spikes.qopt_qaoa import develop, guoq, make_qaoa, oracle

TEXT = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncx q[0],q[1];\ncx q[0],q[1];\ncx q[0],q[1];\n'
SHORT = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncx q[0],q[1];\n'
NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc).isoformat()


def fake_guoq(text=SHORT, code=0, timed_out=False):
    def run(job, source, out, budget_s, **kw):
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        if text is not None:
            Path(out).write_text(text, encoding="utf-8")
        return guoq.GuoqRun(job, budget_s, NOW, NOW, budget_s + 3.0, 3.0, code, timed_out,
                            str(out) if text is not None else None)
    return run


def judge(verified=True, answer="equivalent", contradicted=False):
    return lambda original, candidate, **kw: oracle.Verdict(verified, answer, "alternating", "equivalent", contradicted)


def args(tmp_path, **over):
    base = dict(run_guoq=fake_guoq(), judge=judge(), rebase=lambda t: t, workdir=tmp_path / "w",
                load=lambda set_name, name: TEXT, classify=lambda *a, **k: None)
    base.update(over)
    return base


JOB = {"set": "dev", "name": "dev-6-regular3-p1-r0", "budget": 15, "rep": 0}


def test_a_verified_output_is_logged_with_both_cnot_counts_and_the_run_times(tmp_path):
    out = develop.guoq_job(JOB, **args(tmp_path))
    assert out["kind"] == "guoq" and out["case"] == JOB["name"] and out["budget"] == 15 and out["rep"] == 0
    assert (out["input_cx"], out["output_cx"], out["verified"]) == (3, 1, True)
    assert out["overhead_s"] == 3.0 and out["guoq_start_utc"] == NOW and out["lead_kind"] is None


def test_no_output_is_unverified_and_keeps_no_output_count(tmp_path):
    out = develop.guoq_job(JOB, **args(tmp_path, run_guoq=fake_guoq(text=None, code=1)))
    assert out["verified"] is False and out["output_cx"] is None and out["exit_code"] == 1


def test_a_timeout_is_logged_and_unverified(tmp_path):
    out = develop.guoq_job(JOB, **args(tmp_path, run_guoq=fake_guoq(text=None, code=None, timed_out=True)))
    assert out["timed_out"] is True and out["verified"] is False


def test_a_not_equivalent_output_is_classified_and_becomes_a_lead(tmp_path):
    lead = oracle.Lead("wrong_output", "not_equivalent", 3, "not_equivalent", {"random-11": 0.2})
    out = develop.guoq_job(JOB, **args(tmp_path, judge=judge(False, "not_equivalent"), classify=lambda *a, **k: lead))
    assert out["lead_kind"] == "wrong_output" and out["witnessed"] is True and out["verified"] is False
    (rec,) = develop.to_records([out])
    assert rec["kind"] == "wrong_output" and rec["witness"] is True and rec["duplicate_of"] is None


def test_an_output_the_newer_qcec_contradicts_is_a_recheck_contradiction_lead(tmp_path):
    out = develop.guoq_job(JOB, **args(tmp_path, judge=judge(False, "equivalent", contradicted=True)))
    (rec,) = develop.to_records([out])
    assert out["verified"] is False and rec["kind"] == "recheck_contradiction"


def test_an_ordinary_output_gives_no_lead_record(tmp_path):
    assert develop.to_records([develop.guoq_job(JOB, **args(tmp_path))]) == []


def test_the_shared_qcec_worker_is_never_entered_by_two_threads_at_once(tmp_path):
    inside, worst = [0], [0]

    def slow(original, candidate, **kw):
        inside[0] += 1
        worst[0] = max(worst[0], inside[0])
        time.sleep(0.05)
        inside[0] -= 1
        return oracle.Verdict(True, "equivalent", "alternating")

    threads = [threading.Thread(target=develop.guoq_job, args=(dict(JOB, rep=i),), kwargs=args(tmp_path, judge=slow))
               for i in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert worst[0] == 1


def test_the_planned_length_of_a_batch_is_its_serial_time_over_the_default_workers():
    jobs = [dict(JOB, budget=15)] * 4 + [dict(JOB, budget=300)] * 2
    assert develop.planned_seconds(jobs) == (4 * 18 + 2 * 303) / 2


def test_guoq_jobs_cover_every_dev_circuit_once_per_budget_and_repeat():
    jobs = develop.guoq_jobs([15, 300], repeats=1)
    assert len(jobs) == 72 and {j["set"] for j in jobs} == {"dev"} and len({(j["name"], j["budget"]) for j in jobs}) == 72
    reps = develop.guoq_jobs([300], repeats=3, only=[sorted(c.name for c in make_qaoa.cases("dev"))[0]])
    assert [j["rep"] for j in reps] == [0, 1, 2]


def test_the_qcec_work_folder_is_made_when_it_does_not_exist(tmp_path):
    def writes_there(original, candidate, *, workdir, **kw):
        (Path(workdir) / "x.qasm").write_text(original, encoding="utf-8")  # as verify._write does
        return oracle.Verdict(True, "equivalent", "alternating")

    assert develop.guoq_job(JOB, **args(tmp_path, judge=writes_there))["verified"] is True


def test_a_run_without_the_newer_qcec_interpreter_does_not_start(monkeypatch, tmp_path):
    import pytest
    monkeypatch.delenv("QCEC_LATEST_PYTHON", raising=False)
    with pytest.raises(SystemExit, match="QCEC_LATEST_PYTHON"):
        develop.main(["guoq", "--batch", "x", "--board", str(tmp_path / "b.md"), "--root", str(tmp_path / "r")])


def test_a_jobs_reserve_is_the_qcec_peak_measured_at_its_circuit_size():
    peaks = {6: 0.2, 22: 8.3}
    assert develop.reserve_for(dict(JOB, name="dev-22-regular3-p4-r0"), peaks) == 8.3
    assert develop.reserve_for(dict(JOB, name="dev-10-regular3-p1-r0"), peaks) == 0.2
    assert develop.reserve_for(dict(JOB, name="dev-10-regular3-p1-r0"), {}) == 0.0


# --- pass and search jobs (their work runs in a worker process; the parent verifies) ---------------------------------
def spawn_returning(result):
    def spawn(spec, *, workdir, timeout_s, **kw):
        out = Path(spec["out_dir"])
        out.mkdir(parents=True, exist_ok=True)
        for item in result.get("rows", []) + result.get("proposals", []):
            if item.get("text") is not None:
                (out / f"{item.get('pass', 'p')}-{item.get('rank', 0)}.qasm").write_text(item["text"], encoding="utf-8")
                item["file"] = str(out / f"{item.get('pass', 'p')}-{item.get('rank', 0)}.qasm")
        return result
    return spawn


PJOB = {"set": "dev", "name": "dev-6-regular3-p1-r0", "kind": "passes"}


def test_a_passes_job_verifies_every_output_and_records_a_failing_pass_and_a_lead(tmp_path):
    result = {"kind": "passes", "case": PJOB["name"], "input_cx": 3, "start_cx": 3, "rows": [
        {"pass": "good", "seed": 1, "seconds": 1.0, "cpu_s": 1.0, "error": None, "cx": 1, "gates": 1, "text": SHORT},
        {"pass": "bad", "seed": 1, "seconds": 2.0, "cpu_s": 2.0, "error": None, "cx": 2, "gates": 2, "text": TEXT + "x"},
        {"pass": "crash", "seed": 1, "seconds": 0.1, "cpu_s": 0.1, "error": "ValueError: x", "cx": None, "gates": None,
         "file": None}]}

    def judge_by_text(original, candidate, **kw):
        ok = candidate == SHORT
        return oracle.Verdict(ok, "equivalent" if ok else "not_equivalent", "alternating")

    lead = oracle.Lead("wrong_output", "not_equivalent", 3, "not_equivalent", {"random-11": 0.3})
    out = develop.passes_job(PJOB, **args(tmp_path, judge=judge_by_text, classify=lambda *a, **k: lead),
                             spawn=spawn_returning(result))
    rows = {r["pass"]: r for r in out["passes"]}
    assert rows["good"]["verified"] is True and rows["bad"]["verified"] is False and rows["crash"]["verified"] is False
    assert out["leads"] == [{"pass": "bad", "lead_kind": "wrong_output", "witnessed": True, "duplicate_of": None}]
    (rec,) = develop.to_records([out])
    assert rec["kind"] == "wrong_output" and rec["case"] == PJOB["name"] and "bad" in rec["key"]


def test_identical_outputs_are_verified_once(tmp_path):
    calls = []

    def counting(original, candidate, **kw):
        calls.append(candidate)
        return oracle.Verdict(True, "equivalent", "alternating")

    rows = [{"pass": f"p{i}", "seed": 1, "seconds": 1.0, "cpu_s": 1.0, "error": None, "cx": 1, "gates": 1,
             "text": SHORT} for i in range(4)]
    out = develop.passes_job(PJOB, **args(tmp_path, judge=counting),
                             spawn=spawn_returning({"kind": "passes", "case": "c", "input_cx": 3, "start_cx": 3,
                                                    "rows": rows}))
    assert len(calls) == 1 and all(r["verified"] for r in out["passes"])


def test_passes_jobs_can_be_limited_to_named_circuits():
    names = develop.dev_names()
    assert [j["name"] for j in develop.passes_jobs(only=names[:2])] == names[:2]
    assert len(develop.passes_jobs()) == len(names)


def test_a_search_job_takes_the_best_proposal_that_verifies_and_counts_how_many_it_tried(tmp_path):
    result = {"kind": "search", "case": "c", "budget": 15, "seed": 1, "input_cx": 3, "start_cx": 3, "elapsed_s": 15.2,
              "overrun_s": 0.2, "calls": 40, "errors": {"p": 1}, "restarts": 2, "cpu_s": 14.0, "proposals": [
                  {"rank": 0, "cx": 0, "gates": 0, "path": ["a"], "text": "BROKEN"},
                  {"rank": 1, "cx": 1, "gates": 1, "path": ["a", "b"], "text": SHORT},
                  {"rank": 2, "cx": 3, "gates": 3, "path": [], "text": TEXT}]}

    def judge_by_text(original, candidate, **kw):
        ok = candidate != "BROKEN"
        return oracle.Verdict(ok, "equivalent" if ok else "not_equivalent", "alternating")

    job = dict(PJOB, kind="search", budget=15, config={"id": "base"})
    out = develop.search_job(job, **args(tmp_path, judge=judge_by_text, classify=lambda *a, **k: None),
                             spawn=spawn_returning(result))
    assert (out["cx"], out["verified"], out["tried"], out["chosen_path"]) == (1, True, 2, ["a", "b"])
    assert out["best_unverified_cx"] == 0 and out["config"] == "base" and out["overrun_s"] == 0.2


def test_a_search_with_no_verified_proposal_is_a_loss(tmp_path):
    result = {"kind": "search", "case": "c", "budget": 15, "seed": 1, "input_cx": 3, "start_cx": 3, "elapsed_s": 15.0,
              "overrun_s": 0.0, "calls": 1, "errors": {}, "restarts": 1, "cpu_s": 1.0,
              "proposals": [{"rank": 0, "cx": 1, "gates": 1, "path": ["a"], "text": SHORT}]}
    out = develop.search_job(dict(PJOB, kind="search", budget=15, config={"id": "base"}),
                             **args(tmp_path, judge=judge(False, "hard_timeout")), spawn=spawn_returning(result))
    assert out["cx"] is None and out["verified"] is False and out["tried"] == 1


def test_spawn_runs_the_worker_with_one_thread_limits_and_returns_its_result(tmp_path):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["env"] = cmd, kw["env"]
        Path(cmd[-1]).write_text('{"kind": "passes", "rows": []}', encoding="utf-8")

        class Done:
            returncode, stderr = 0, ""
        return Done()

    out = develop.spawn({"job": "passes", "tag": "t1"}, workdir=tmp_path, timeout_s=60, run=fake_run)
    assert out == {"kind": "passes", "rows": []} and seen["env"]["OMP_NUM_THREADS"] == "1"
    assert "spikes.qopt_qaoa.worker" in seen["cmd"]


def test_a_worker_that_fails_or_times_out_raises_with_its_error(tmp_path):
    import subprocess
    import pytest

    def failing(cmd, **kw):
        class Done:
            returncode, stderr = 1, "Traceback: boom"
        return Done()

    with pytest.raises(RuntimeError, match="boom"):
        develop.spawn({"job": "search", "tag": "t2"}, workdir=tmp_path, timeout_s=60, run=failing)

    def hanging(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    with pytest.raises(RuntimeError, match="timed out"):
        develop.spawn({"job": "search", "tag": "t3"}, workdir=tmp_path, timeout_s=1, run=hanging)


def test_the_repeat_sample_is_twelve_circuits_spread_over_the_sizes_and_repeat_numbers_can_start_later():
    sample = develop.repeat_sample()
    assert len(sample) == 12 and len({n.split("-")[1] for n in sample}) >= 8
    jobs = develop.guoq_jobs([300], repeats=2, first_rep=1, only=sample)
    assert sorted({j["rep"] for j in jobs}) == [1, 2] and len(jobs) == 24
