import json
import multiprocessing as mp
from datetime import datetime, timedelta
from pathlib import Path

from spikes.qopt_audit import run
from spikes.qopt_audit.bases import load_bases
from spikes.qopt_audit.generate import schedule
from spikes.qopt_audit.run import report, run_batch

BASES = load_bases(Path(__file__).resolve().parents[1] / "bases")
IDENTITY = {"qiskit": lambda t: t}
SMALL_RANDOM_SEEDS = {3, 12, 13}  # random circuits of 7 to 10 qubits: QCEC decides a dropped rotation on them


def test_a_batch_logs_one_line_per_case_and_tool_and_writes_the_circuits(tmp_path):
    cases = [c for _, c in zip(range(3), schedule())]
    summary = run_batch(cases, BASES, out=tmp_path, budget_s=600, tools=IDENTITY)
    lines = [json.loads(l) for l in (tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert summary["cases"] == 3 and summary["stopped"] == "exhausted" and len(lines) == 3
    assert {l["kind"] for l in lines} <= {"verified", "unverified"}
    assert len(list((tmp_path / "circuits").glob("*.qasm"))) == 3


def test_a_second_batch_resumes_and_does_not_repeat_work(tmp_path):
    cases = [c for _, c in zip(range(2), schedule())]
    run_batch(cases, BASES, out=tmp_path, budget_s=600, tools=IDENTITY)
    run_batch(cases, BASES, out=tmp_path, budget_s=600, tools=IDENTITY)
    assert len((tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_the_budget_stops_the_batch_and_no_worker_is_left_behind(tmp_path):
    cases = [c for _, c in zip(range(50), schedule())]
    summary = run_batch(cases, BASES, out=tmp_path, budget_s=0.001, tools=IDENTITY)
    assert summary["stopped"] == "budget" and summary["cases"] < 50
    assert mp.active_children() == []


def test_a_planted_fault_is_logged_as_a_wrong_output_and_listed_in_the_report(tmp_path):
    drop_rz = {"qiskit": lambda t: "\n".join(l for l in t.splitlines() if not l.startswith("rz")) + "\n"}
    small = [c for _, c in zip(range(400), schedule()) if c.kind == "random" and c.seed in SMALL_RANDOM_SEEDS][:3]
    assert len(small) == 3
    run_batch(small, BASES, out=tmp_path, budget_s=1200, tools=drop_rz)
    rows = [json.loads(l) for l in (tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(r["kind"] == "wrong_output" for r in rows) == 3
    text = report(tmp_path / "log.jsonl")
    assert "unverified share" in text and "wrong_output: " in text and "random random seed" in text


def _utc(stamp: str) -> datetime:
    when = datetime.fromisoformat(stamp)
    assert when.utcoffset() == timedelta(0), stamp
    return when


def test_every_observation_carries_a_utc_wall_clock_time(tmp_path):
    before = datetime.now().astimezone().replace(microsecond=0)
    run_batch([next(iter(schedule()))], BASES, out=tmp_path, budget_s=600, tools=IDENTITY)
    rows = [json.loads(l) for l in (tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows and all(_utc(r["observed_at"]) >= before for r in rows)


class _FakeWorker:
    def __init__(self, *args, **kwargs):
        pass

    def wait(self):
        return 0


def test_the_coordinator_logs_the_batch_times_before_it_triages(tmp_path, monkeypatch):
    out, findings, seen = tmp_path / "run", tmp_path / "findings", []

    def fake_triage(run_dir, folder):
        lines = (run_dir / "batches.jsonl").read_text(encoding="utf-8").splitlines()
        seen.append(len(lines))  # the batch is on the books (and its wall time closed) before triage starts
        return [{"key": "random:random:3:qiskit", "witness": True, "kind": "wrong_output", "duplicate_of": None,
                 "signature": "qiskit:rz", "observed_at": "2026-10-28T09:00:00+00:00",
                 "triaged_at": "2026-10-28T10:30:00+00:00"},
                {"key": "random:random:4:qiskit", "witness": False}]

    monkeypatch.setattr(run.subprocess, "Popen", _FakeWorker)
    monkeypatch.setattr(run, "triage_run", fake_triage)
    assert run.main([str(out), "--budget-hours", "1", "--findings", str(findings)]) == 0
    batch = json.loads((out / "batches.jsonl").read_text(encoding="utf-8"))
    assert seen == [1] and _utc(batch["ended_at"]) >= _utc(batch["started_at"])
    attention = [json.loads(l) for l in (findings / "attention.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [a["key"] for a in attention] == ["random:random:3:qiskit"]
    assert attention[0]["due_by"] == "2026-10-31T09:00:00+00:00" and attention[0]["lag_h"] == 1.5


def test_without_a_findings_folder_the_coordinator_does_not_triage(tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("triage ran without --findings")

    monkeypatch.setattr(run.subprocess, "Popen", _FakeWorker)
    monkeypatch.setattr(run, "triage_run", refuse)
    assert run.main([str(tmp_path / "run"), "--budget-hours", "1"]) == 0
