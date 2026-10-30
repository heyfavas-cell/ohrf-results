import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from spikes.qopt_qaoa import frozen, guoq


class Clock:
    def __init__(self, step):
        self.t, self.step = 0.0, step

    def __call__(self):
        self.t += self.step
        return self.t


def test_the_command_pins_the_cpu_memory_budget_and_mounts(tmp_path):
    cmd = guoq.command("j1", tmp_path / "in" / "c.qasm", tmp_path / "out" / "c.qasm", 15)
    joined = " ".join(cmd)
    assert cmd[:3] == ["docker", "run", "--rm"] and "--cpus 1" in joined and "--memory 4g" in joined
    assert "--opt_timeout 15" in joined and "--target_gateset IBMN" in joined and "TWO_Q" in joined
    assert guoq.IMAGE == "ohrf-wisq:97c12a5" and "/in:ro" in joined and "--name p0e-j1" in joined


def test_a_run_records_utc_times_wall_clock_and_overhead(tmp_path):
    out = tmp_path / "out" / "c.qasm"

    def fake(cmd, **kw):
        out.write_text("OPENQASM 2.0;\n", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    stamps = iter([datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc), datetime(2026, 10, 28, 12, 0, 18, tzinfo=timezone.utc)])
    r = guoq.run_guoq("j", tmp_path / "c.qasm", out, 15, run=fake, clock=Clock(9.0), now=lambda: next(stamps))
    assert (r.exit_code, r.timed_out, r.output) == (0, False, str(out))
    assert r.wall_s == 9.0 and r.overhead_s == -6.0 and r.start_utc.startswith("2026-10-28T12:00:00")


def test_a_stale_output_is_not_mistaken_for_a_new_one(tmp_path):
    out = tmp_path / "out" / "c.qasm"
    out.parent.mkdir()
    out.write_text("old", encoding="utf-8")
    r = guoq.run_guoq("j", tmp_path / "c.qasm", out, 15, run=lambda cmd, **kw: SimpleNamespace(returncode=1))
    assert r.output is None and r.exit_code == 1


def test_a_run_past_its_grace_is_killed_and_flagged(tmp_path):
    calls = []

    def fake(cmd, **kw):
        calls.append(cmd)
        if cmd[1] == "run":
            raise subprocess.TimeoutExpired(cmd, 1)
        return SimpleNamespace(returncode=0)

    r = guoq.run_guoq("j", tmp_path / "c.qasm", tmp_path / "o" / "c.qasm", 15, run=fake)
    assert r.timed_out and r.exit_code is None and calls[-1][:3] == ["docker", "rm", "-f"]


def test_a_real_10_second_run_writes_an_output_the_verifier_accepts(tmp_path):
    from spikes.qopt_p0.guoq_inputs import rebase
    from spikes.qopt_p0.harness import cx_count
    from spikes.qopt_qaoa import oracle
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        pytest.skip("no Docker")
    guoq.ensure_image()
    # a throwaway 4-qubit ring, in neither set: the test must not look at a development or held-out circuit
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    body = "".join(f"cx q[{a}],q[{b}];\nrz(0.7) q[{b}];\ncx q[{a}],q[{b}];\n" for a, b in edges)
    text = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[4];\n' + "h q[0];\n" + body + body
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "c.qasm").write_text(rebase(text), encoding="utf-8")
    r = guoq.run_guoq("test", tmp_path / "in" / "c.qasm", tmp_path / "out" / "c.qasm", 10)
    assert r.exit_code == 0 and r.output and 0 <= r.overhead_s < 10
    out = Path(r.output).read_text(encoding="utf-8")
    assert cx_count(out) <= cx_count(text)
    assert oracle.decide(text, out, workdir=tmp_path)[0].startswith("equivalent")
