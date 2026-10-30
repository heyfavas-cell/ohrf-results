import json
from datetime import datetime, timezone

from spikes.qopt_qaoa import slots

BOARD_IDLE = "## In\n\n### P0d model triage · `x` · sid:1\n- Branch: `spike/p0d` · Status: waiting on Favas\n"
BOARD_BUSY = "## In\n\n### P0d model triage · `x` · sid:1\n- Branch: `spike/p0d` · Status: running job\n"
BOARD_OTHER = "## In\n\n### Portal · `y` · sid:2\n- Branch: `b` · Status: running job\n"
NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def guard(tmp_path, board=BOARD_IDLE, cpu=10.0, mem=20.0, dead=()):
    (tmp_path / "board.md").write_text(board, encoding="utf-8")
    return slots.Guard(tmp_path / "reg", tmp_path / "board.md", tmp_path / "refusals.jsonl",
                       cpu_outside=lambda pids: cpu, free_memory_gb=lambda: mem,
                       alive=lambda pid: pid not in dead, now=lambda: NOW)


def start(g, n):
    for i in range(n):
        g.register(f"j{i}", 100 + i)


def refusals(tmp_path):
    path = tmp_path / "refusals.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def test_the_board_check_reads_only_a_p0d_entry_marked_running():
    assert slots.p0d_running(BOARD_BUSY) and not slots.p0d_running(BOARD_IDLE) and not slots.p0d_running(BOARD_OTHER)


def test_two_jobs_are_admitted_without_sampling_the_cpu(tmp_path):
    g = guard(tmp_path, board=BOARD_BUSY, cpu=99.0)
    start(g, 1)
    assert g.admit("next")[0]


def test_a_recorded_margin_override_lowers_the_floor_and_keeps_the_qcec_reserve(tmp_path):
    (tmp_path / "board.md").write_text(BOARD_IDLE, encoding="utf-8")
    for mem, floor, ok in ((13.5, None, False), (13.5, 5, True), (13.0, 5, False), (4.0, 5, False)):
        g = slots.Guard(tmp_path / "reg", tmp_path / "board.md", tmp_path / "refusals.jsonl",
                        cpu_outside=lambda pids: 0.0, free_memory_gb=lambda m=mem: m, now=lambda: NOW, min_free_gb=floor)
        assert g.admit("j", reserve_gb=8.1)[0] is ok  # frozen 8 + 8.1 = 16.1 needed; 5 + 8.1 = 13.1 with the override


def test_a_third_job_waits_while_p0d_runs(tmp_path):
    g = guard(tmp_path, board=BOARD_BUSY)
    start(g, 2)
    ok, why = g.admit("third")
    assert not ok and "P0d" in why and refusals(tmp_path)[0]["refused_utc"] == NOW.isoformat()


def test_a_third_job_waits_while_the_cpu_is_busy_and_runs_when_idle(tmp_path):
    busy = guard(tmp_path, cpu=75.0)
    start(busy, 2)
    assert not busy.admit("third")[0]
    assert guard(tmp_path, cpu=20.0).admit("third")[0]


def test_a_fourth_job_is_never_admitted(tmp_path):
    g = guard(tmp_path, cpu=0.0)
    start(g, 3)
    ok, why = g.admit("fourth")
    assert not ok and "never more than 3" in why


def test_low_memory_refuses_every_job(tmp_path):
    g = guard(tmp_path, mem=6.0)
    ok, why = g.admit("first")
    assert not ok and "memory" in why


def test_a_dead_process_is_a_stray_and_frees_its_slot(tmp_path):
    g = guard(tmp_path, board=BOARD_BUSY, dead=(100,))
    start(g, 2)
    assert [e["job"] for e in g.strays()] == ["j0"] and len(g.live()) == 1
    assert g.admit("next")[0]


def test_release_removes_the_registration(tmp_path):
    g = guard(tmp_path)
    start(g, 2)
    g.release("j0")
    assert [e["job"] for e in g.entries()] == ["j1"]


def test_threads_sharing_one_guard_never_trip_over_each_others_files(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    g = guard(tmp_path, cpu=0.0)

    def work(i):
        for k in range(40):
            g.register(f"t{i}-{k}", 100)
            g.live()
            g.release(f"t{i}-{k}")
        return True

    with ThreadPoolExecutor(max_workers=3) as pool:
        assert all(pool.map(work, range(3)))


def test_a_job_that_will_need_a_big_qcec_check_is_admitted_only_with_that_much_memory_above_the_minimum(tmp_path):
    g = guard(tmp_path, mem=12.0)
    assert not g.admit("big", reserve_gb=6.0)[0] and "reserve" in refusals(tmp_path)[-1]["reason"]
    assert g.admit("small", reserve_gb=3.0)[0]
    assert g.admit("plain")[0]


def test_a_live_jobs_reserve_still_counts_for_the_next_job(tmp_path):
    g = guard(tmp_path, mem=12.0)
    g.register("big", 100, reserve_gb=6.0)
    ok, why = g.admit("next")
    assert not ok and "reserve" in why
    g.release("big")
    assert g.admit("next")[0]


def test_reserves_are_not_added_because_only_one_qcec_check_runs_at_a_time(tmp_path):
    g = guard(tmp_path, mem=15.0)
    g.register("a", 100, reserve_gb=6.0)
    assert g.admit("b", reserve_gb=6.0)[0]  # 8 + max(6, 6) = 14, not 8 + 12
