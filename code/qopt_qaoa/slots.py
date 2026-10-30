"""The PC-sharing guard (plan, "Sharing the PC"): how many P0e jobs may run beside P0d, within D-149.

P0e runs `WORKERS_DEFAULT` jobs by default and `WORKERS_IDLE_MAX` only when no P0d run is marked `running job` on the
sessions board and the CPU outside P0e is at most `IDLE_CPU_PCT`. A fourth job is never admitted. Free memory under
`FREE_MEMORY_MIN_GB` refuses every job. Every refusal is logged with its UTC time.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from spikes.qopt_qaoa import folders, frozen


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _pid_alive(pid: int) -> bool:
    import psutil
    return psutil.pid_exists(pid)


def default_cpu_outside_pct(pids: list[int], *, sample_s: float = 30.0) -> float:
    """Machine CPU over `sample_s` seconds, less what P0e's own registered processes used (containers run in the
    Docker VM and count as outside load, which is about one logical CPU each)."""
    import time
    import psutil
    own = []
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            proc.cpu_percent(None)
            own.append(proc)
        except psutil.Error:
            pass
    psutil.cpu_percent(None)
    time.sleep(sample_s)
    total = psutil.cpu_percent(None)
    mine = sum(p.cpu_percent(None) for p in own if p.is_running()) / psutil.cpu_count()
    return max(0.0, total - mine)


def default_free_memory_gb() -> float:
    import psutil
    return psutil.virtual_memory().available / 2**30


def p0d_running(board_text: str) -> bool:
    """True when a board entry that names P0d has the status `running job`."""
    for entry in board_text.split("\n### ")[1:]:
        head, _, body = entry.partition("\n")
        if "p0d" in (head + body).lower() and "status: running job" in body.lower():
            return True
    return False


class Guard:
    def __init__(self, registry: Path, board: Path, log: Path, *,
                 cpu_outside: Callable[[list[int]], float] = default_cpu_outside_pct,
                 free_memory_gb: Callable[[], float] = default_free_memory_gb,
                 alive: Callable[[int], bool] = _pid_alive, now: Callable[[], datetime] = utc_now,
                 min_free_gb: float | None = None) -> None:
        """`min_free_gb` is a recorded run-time override of the frozen margin (see `run.guard_override`); None keeps it."""
        self.min_free_gb = frozen.FREE_MEMORY_MIN_GB if min_free_gb is None else float(min_free_gb)
        self.registry, self.board, self.log = Path(registry), Path(board), Path(log)
        self._cpu, self._mem, self._alive, self._now = cpu_outside, free_memory_gb, alive, now
        folders.ensure_dir(self.registry)
        self._lock = threading.RLock()  # the runner's threads share one guard; Windows refuses a read of a file being written

    def register(self, job: str, pid: int, container: str = "", reserve_gb: float = 0.0) -> None:
        entry = {"job": job, "pid": pid, "container": container, "started_utc": self._now().isoformat(),
                 "reserve_gb": reserve_gb}
        with self._lock:
            (self.registry / f"{job}.json").write_text(json.dumps(entry), encoding="utf-8")

    def release(self, job: str) -> None:
        with self._lock:
            (self.registry / f"{job}.json").unlink(missing_ok=True)

    def entries(self) -> list[dict]:
        with self._lock:
            return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.registry.glob("*.json"))]

    def live(self) -> list[dict]:
        return [e for e in self.entries() if self._alive(e["pid"])]

    def strays(self) -> list[dict]:
        """Registered jobs whose process has gone: a job that exited without releasing its slot."""
        return [e for e in self.entries() if not self._alive(e["pid"])]

    def _refuse(self, job: str, reason: str) -> tuple[bool, str]:
        with self._lock, self.log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"job": job, "refused_utc": self._now().isoformat(), "reason": reason}) + "\n")
        return False, reason

    def admit(self, job: str, reserve_gb: float = 0.0) -> tuple[bool, str]:
        """`reserve_gb` is the QCEC peak this job's check will need (measured by size, `qcec_peak`). Checks run one at
        a time, so the reserve is the largest among this job and the live ones, on top of the frozen minimum."""
        with self._lock:
            return self._admit(job, reserve_gb)

    def _admit(self, job: str, reserve_gb: float) -> tuple[bool, str]:
        live = self.live()
        if len(live) >= frozen.WORKERS_IDLE_MAX:
            return self._refuse(job, f"{len(live)} jobs are live: never more than {frozen.WORKERS_IDLE_MAX}")
        free = self._mem()
        floor = self.min_free_gb
        if free < floor:
            return self._refuse(job, f"free memory {free:.1f} GB is under {floor:g} GB")
        reserve = max([reserve_gb] + [e.get("reserve_gb", 0.0) for e in live])
        if free < floor + reserve:
            return self._refuse(job, f"free memory {free:.1f} GB is under {floor:g} GB plus the "
                                     f"{reserve:.1f} GB reserve for a QCEC check")
        if len(live) >= frozen.WORKERS_DEFAULT:  # a third job needs an idle PC
            board = self.board.read_text(encoding="utf-8") if self.board.exists() else ""
            if p0d_running(board):
                return self._refuse(job, "a P0d run is marked running on the board")
            busy = self._cpu([e["pid"] for e in live])
            if busy > frozen.IDLE_CPU_PCT:
                return self._refuse(job, f"CPU outside P0e is {busy:.0f}%, over {frozen.IDLE_CPU_PCT}%")
        return True, "admitted"
