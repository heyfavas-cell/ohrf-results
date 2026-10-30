import json
from datetime import datetime, timedelta, timezone

import pytest

from spikes.qopt_qaoa import frozen, heartbeat, run, slots, triage

T0 = datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc)
BOARD = "## In\n\n### Someone else · `w` · sid:1\n- Status: active\n"


# --- the stall alarm -------------------------------------------------------------------------------------------------
def test_a_25_hour_old_heartbeat_puts_one_line_in_the_board(tmp_path):
    beat, board = tmp_path / "hb.json", tmp_path / "board.md"
    board.write_text(BOARD, encoding="utf-8")
    heartbeat.write(beat, batch_end=T0 - timedelta(hours=25), triage_end=T0 - timedelta(hours=1))
    line = heartbeat.check(beat, board, now=T0)
    assert line and "batch_end_utc" in line and "triage_end_utc" not in line
    heartbeat.check(beat, board, now=T0)
    assert board.read_text(encoding="utf-8").count("STALL-ALARM") == 1
    assert "Someone else" in board.read_text(encoding="utf-8")


def test_either_clock_stale_or_missing_raises_the_alarm_and_a_fresh_beat_clears_it(tmp_path):
    beat, board = tmp_path / "hb.json", tmp_path / "board.md"
    board.write_text(BOARD, encoding="utf-8")
    assert heartbeat.check(beat, board, now=T0)  # no heartbeat at all while a run is open
    heartbeat.write(beat, batch_end=T0, triage_end=T0 - timedelta(hours=30))
    assert "triage_end_utc" in heartbeat.check(beat, board, now=T0)
    heartbeat.write(beat, triage_end=T0)
    assert heartbeat.check(beat, board, now=T0) is None and "STALL-ALARM" not in board.read_text(encoding="utf-8")


def test_a_closed_run_raises_no_alarm(tmp_path):
    board = tmp_path / "board.md"
    board.write_text(BOARD, encoding="utf-8")
    assert heartbeat.check(tmp_path / "none.json", board, now=T0, run_open=False) is None


# --- triage -----------------------------------------------------------------------------------------------------------
SMALL = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nrz(0.0001) q[0];\ncx q[0],q[1];\n'
BIG = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nrz(0.7) q[0];\ncx q[0],q[1];\n'


def test_a_tiny_rotation_dropped_by_the_named_pass_matches_a_known_issue_and_nothing_else_does():
    assert triage.match_known("q-peephole-2q", SMALL) == "Qiskit/qiskit#16864"
    assert triage.match_known("q-commutative-cancel", SMALL) == "Qiskit/qiskit#17315"
    assert triage.match_known("q-peephole-2q", BIG) is None
    assert triage.match_known("t-peephole", SMALL) is None and triage.match_known(None, SMALL) is None


def test_the_first_breaking_step_is_the_first_step_after_which_the_state_stops_verifying():
    passes = {"a": lambda t, s: t + "A", "b": lambda t, s: t + "B", "c": lambda t, s: t + "C"}
    assert triage.first_breaking_step("", ("a", "b", "c"), passes, lambda t: "B" not in t) == "b"
    assert triage.first_breaking_step("", ("a", "c"), passes, lambda t: True) is None


def test_a_lead_is_due_72_hours_after_it_was_seen_and_the_attention_list_takes_it_once(tmp_path):
    rec = triage.lead_record("x", "wrong_output", seen=T0, witnessed=True, duplicate_of=None)
    assert datetime.fromisoformat(rec["due_by"]) - datetime.fromisoformat(rec["seen_utc"]) == timedelta(hours=72)
    dup = triage.lead_record("y", "wrong_output", seen=T0, witnessed=True, duplicate_of="Qiskit/qiskit#16864")
    quiet = triage.lead_record("z", "wrong_output", seen=T0, witnessed=False, duplicate_of=None)
    other = triage.lead_record("w", "recheck_contradiction", seen=T0, witnessed=False, duplicate_of=None)
    att = tmp_path / "attention.jsonl"
    assert [r["key"] for r in triage.triage_batch([rec, dup, quiet, other], att)] == ["x", "w"]
    assert triage.triage_batch([rec], att) == []
    assert len(att.read_text(encoding="utf-8").splitlines()) == 2


# --- the runner -------------------------------------------------------------------------------------------------------
def guard_for(tmp_path, mem=20.0):
    (tmp_path / "board.md").write_text(BOARD, encoding="utf-8")
    return slots.Guard(tmp_path / "reg", tmp_path / "board.md", tmp_path / "refusals.jsonl",
                       cpu_outside=lambda pids: 0.0, free_memory_gb=lambda: mem)


def to_records(obs):
    return [triage.lead_record(o["job"], "wrong_output", seen=run.utc_now(), witnessed=True, duplicate_of=None)
            for o in obs if o.get("lead")]


def test_a_batch_logs_utc_times_the_compute_line_the_heartbeat_and_triages_when_it_is_logged(tmp_path):
    folder = tmp_path / "run"
    clock = iter(T0 + timedelta(seconds=s) for s in range(0, 1000, 5))
    batch = run.Batch("b1", "dev", [{"n": 1}, {"n": 2, "lead": True}, {"n": 3}])
    result = run.run_batch(batch, lambda job: {"cx": job["n"], "lead": job.get("lead", False)},
                           guard=guard_for(tmp_path), folder=folder, planned_s=100, to_records=to_records,
                           board=tmp_path / "board.md", now=lambda: next(clock))
    obs = [json.loads(l) for l in (folder / "observations.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(obs) == 3 and all(o["start_utc"] < o["end_utc"] and o["start_utc"].endswith("+00:00") for o in obs)
    assert sorted(o["cx"] for o in obs) == [1, 2, 3]
    runs = [json.loads(l) for l in (folder / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert runs[0]["phase"] == "dev" and runs[0]["seconds"] > 0 and run.used_seconds(folder / "runs.jsonl") > 0
    beat = json.loads((folder / "heartbeat.json").read_text(encoding="utf-8"))
    assert beat["batch_end_utc"] <= beat["triage_end_utc"]
    assert [l["key"] for l in result["new_leads"]] == ["b1-1"]
    assert (folder / "attention.jsonl").exists() and result["strays"] == []
    assert list((tmp_path / "reg").glob("*.json")) == []


def test_a_batch_over_a_cap_does_not_start(tmp_path):
    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "runs.jsonl").write_text(json.dumps({"batch": "x", "phase": "dev", "seconds": frozen.DEV_CAP_S - 100}) + "\n",
                                       encoding="utf-8")
    ok, why = run.may_start(folder / "runs.jsonl", "dev", 200)
    assert not ok and "dev cap" in why
    assert run.may_start(folder / "runs.jsonl", "held_out", 200)[0]
    assert not run.may_start(folder / "runs.jsonl", "held_out", frozen.RUN_CAP_S + 1)[0]
    (folder / "runs.jsonl").write_text(json.dumps({"batch": "x", "phase": "step0", "seconds": frozen.COMPUTE_CAP_S - 50}) + "\n",
                                       encoding="utf-8")
    assert not run.may_start(folder / "runs.jsonl", "held_out", 100)[0]
    with pytest.raises(RuntimeError, match="not started"):
        run.run_batch(run.Batch("b", "held_out", [1]), lambda j: {}, guard=guard_for(tmp_path), folder=folder, planned_s=100)


def write_runs(folder, **seconds_by_phase):
    folder.mkdir(exist_ok=True)
    (folder / "runs.jsonl").write_text(
        "".join(json.dumps({"batch": p, "phase": p, "seconds": s}) + "\n" for p, s in seconds_by_phase.items()),
        encoding="utf-8")


def test_an_allowance_raises_one_phase_cap_by_the_stated_seconds_and_never_the_total_or_the_run_cap(tmp_path):
    folder = tmp_path / "run"
    write_runs(folder, held_out=frozen.HELD_OUT_CAP_S - 100)
    runs = folder / "runs.jsonl"
    assert not run.may_start(runs, "held_out", 200)[0]
    assert run.may_start(runs, "held_out", 200, extra_s=8 * 3600)[0]
    assert not run.may_start(runs, "held_out", frozen.RUN_CAP_S + 1, extra_s=8 * 3600)[0]
    write_runs(folder, held_out=frozen.HELD_OUT_CAP_S, dev=frozen.COMPUTE_CAP_S - frozen.HELD_OUT_CAP_S - 50)
    ok, why = run.may_start(runs, "held_out", 100, extra_s=8 * 3600)
    assert not ok and "30 hour" in why


def test_the_allowance_comes_from_the_run_folders_file_for_its_phase_only(tmp_path):
    folder = tmp_path / "run"
    folder.mkdir()
    assert run.allowance_s(folder, "held_out") == 0
    (folder / "allowance.json").write_text(json.dumps({"phase": "held_out", "extra_s": 28800, "decision": "OD-AS"}),
                                           encoding="utf-8")
    assert run.allowance_s(folder, "held_out") == 28800 and run.allowance_s(folder, "dev") == 0


def test_a_batch_that_starts_only_because_of_the_allowance_is_logged_as_using_it(tmp_path):
    folder = tmp_path / "run"
    write_runs(folder, held_out=frozen.HELD_OUT_CAP_S - 100)
    (folder / "allowance.json").write_text(json.dumps({"phase": "held_out", "extra_s": 28800, "decision": "OD-AS"}),
                                           encoding="utf-8")
    run.run_batch(run.Batch("held-5", "held_out", [{"n": 1}]), lambda j: {}, guard=guard_for(tmp_path), folder=folder,
                  planned_s=200)
    (line,) = [json.loads(l) for l in (folder / "allowances.jsonl").read_text(encoding="utf-8").splitlines()]
    assert line["batch"] == "held-5" and line["decision"] == "OD-AS" and line["extra_s"] == 28800
    assert line["used_before_s"] == frozen.HELD_OUT_CAP_S - 100 and line["planned_s"] == 200 and line["utc"].endswith("+00:00")
    write_runs(folder, held_out=10)  # well under the plain cap: no allowance line is written
    run.run_batch(run.Batch("held-6", "held_out", [{"n": 1}]), lambda j: {}, guard=guard_for(tmp_path), folder=folder,
                  planned_s=200)
    assert len((folder / "allowances.jsonl").read_text(encoding="utf-8").splitlines()) == 1


OVERRIDE = {"phase": "held_out", "batch_prefix": "held-6", "free_memory_min_gb": 5, "workers": 1, "decision": "OD-BI 2"}


def test_a_guard_override_applies_to_its_phase_and_batch_prefix_only_and_is_bounded(tmp_path):
    folder = tmp_path / "run"
    folder.mkdir()
    assert run.guard_override(folder, "held_out", "held-6") == {}
    (folder / "guard_override.json").write_text(json.dumps(OVERRIDE), encoding="utf-8")
    assert run.guard_override(folder, "held_out", "held-6-resume-3") == {
        "decision": "OD-BI 2", "free_memory_min_gb": 5.0, "workers": 1}
    assert run.guard_override(folder, "held_out", "held-5") == {} and run.guard_override(folder, "dev", "held-6") == {}
    (folder / "guard_override.json").write_text(json.dumps({**OVERRIDE, "workers": 9}), encoding="utf-8")
    assert run.guard_override(folder, "held_out", "held-6")["workers"] == frozen.WORKERS_IDLE_MAX


def test_a_batch_under_an_override_is_logged_in_runs_and_runs_one_job_at_a_time(tmp_path):
    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "guard_override.json").write_text(json.dumps(OVERRIDE), encoding="utf-8")
    live = []
    peak = [0]
    lock = __import__("threading").Lock()

    def execute(job):
        with lock:
            live.append(1)
            peak[0] = max(peak[0], len(live))
        __import__("time").sleep(0.02)
        with lock:
            live.pop()
        return {}

    run.run_batch(run.Batch("held-6-resume-3", "held_out", [{"n": i} for i in range(5)]), execute,
                  guard=guard_for(tmp_path), folder=folder, planned_s=10)
    assert peak[0] == 1
    rows = [json.loads(l) for l in (folder / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["phase"] == "note" and rows[0]["seconds"] == 0 and "OD-BI 2" in rows[0]["note"]
    assert rows[1]["phase"] == "held_out"
    (line,) = [json.loads(l) for l in (folder / "guard_overrides.jsonl").read_text(encoding="utf-8").splitlines()]
    assert line["batch"] == "held-6-resume-3" and line["free_memory_min_gb"] == 5.0 and line["workers"] == 1


def test_a_refused_job_waits_and_retries_and_a_job_that_never_gets_in_fails_the_batch(tmp_path):
    waits = []
    g = guard_for(tmp_path, mem=1.0)  # memory too low to admit anything
    with pytest.raises(RuntimeError, match="never admitted"):
        run.run_batch(run.Batch("b", "dev", [1]), lambda j: {}, guard=g, folder=tmp_path / "r", planned_s=10,
                      sleep=waits.append, max_wait_rounds=3)
    assert len(waits) == 3 and len((tmp_path / "refusals.jsonl").read_text(encoding="utf-8").splitlines()) == 3


def test_a_job_that_raises_still_releases_its_slot(tmp_path):
    g = guard_for(tmp_path)

    def boom(job):
        raise ValueError("tool exploded")

    with pytest.raises(ValueError):
        run.run_batch(run.Batch("b", "dev", [1]), boom, guard=g, folder=tmp_path / "r", planned_s=10)
    assert g.entries() == []


def test_each_finished_job_is_logged_at_once_so_a_later_crash_loses_nothing(tmp_path):
    g = guard_for(tmp_path)
    folder = tmp_path / "r"

    def work(job):
        if job == 3:
            import time
            time.sleep(0.3)
            raise ValueError("tool exploded")
        return {"n": job}

    with pytest.raises(ValueError):
        run.run_batch(run.Batch("b", "dev", [1, 2, 3]), work, guard=g, folder=folder, planned_s=10)
    logged = [json.loads(l)["n"] for l in (folder / "observations.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sorted(logged) == [1, 2]


def test_the_runner_asks_the_guard_for_each_jobs_qcec_reserve(tmp_path):
    g = guard_for(tmp_path, mem=12.0)
    seen = {}
    result = run.run_batch(run.Batch("b", "dev", [{"n": 1, "need": 1.0}]), lambda j: {"n": j["n"]}, guard=g,
                           folder=tmp_path / "r", planned_s=10, reserve_for=lambda j: j["need"])
    assert result["observations"] == 1
    with pytest.raises(RuntimeError, match="never admitted"):
        run.run_batch(run.Batch("c", "dev", [{"n": 1, "need": 6.0}]), lambda j: {}, guard=g, folder=tmp_path / "r2",
                      planned_s=10, reserve_for=lambda j: j["need"], sleep=lambda s: None, max_wait_rounds=2)
