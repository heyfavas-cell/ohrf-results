"""GUOQ (`wisq` 0.2.7, built by `spikes/qopt_p0/guoq/Dockerfile`) at a wall-clock budget, one container per run.

The input is the circuit rebased to {cx, rz, sx, x} (`spikes.qopt_p0.guoq_inputs.rebase`). Each run gets
`CPUS_PER_WORKER` CPU and `MEMORY_PER_WORKER_GB` of memory, the same allowance as the candidate search. The run's
UTC start and end, wall-clock and its overhead beyond the budget are returned for the log.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from spikes.qopt_qaoa import folders, frozen

IMAGE = f"ohrf-wisq:{frozen.GUOQ['commit']}"
DOCKERFILE_DIR = Path(__file__).resolve().parents[1] / "qopt_p0" / "guoq"
KILL_GRACE_S = 120


@dataclass(frozen=True)
class GuoqRun:
    job: str
    budget_s: int
    start_utc: str
    end_utc: str
    wall_s: float
    overhead_s: float
    exit_code: int | None
    timed_out: bool
    output: str | None  # the output path when GUOQ wrote one

    def as_dict(self) -> dict:
        return asdict(self)


def command(job: str, source: Path, out: Path, budget_s: int) -> list[str]:
    src, out = Path(source).resolve(), Path(out).resolve()
    inner = (f"cd /tmp && wisq /in/{src.name} --mode opt --target_gateset {frozen.GUOQ['gateset']} "
             f"--optimization_objective {frozen.GUOQ['objective']} --opt_timeout {budget_s} "
             f"--output_path /out/{out.name}")
    return ["docker", "run", "--rm", "--name", f"p0e-{job}", "--cpus", str(frozen.CPUS_PER_WORKER),
            "--memory", f"{frozen.MEMORY_PER_WORKER_GB}g", "-v", f"{src.parent.as_posix()}:/in:ro",
            "-v", f"{out.parent.as_posix()}:/out", IMAGE, "sh", "-c", inner]


def ensure_image(run: Callable = subprocess.run) -> None:
    if run(["docker", "image", "inspect", IMAGE], capture_output=True).returncode != 0:
        run(["docker", "build", "-q", "-t", IMAGE, str(DOCKERFILE_DIR)], check=True, capture_output=True)


def run_guoq(job: str, source: Path, out: Path, budget_s: int, *, run: Callable = subprocess.run,
             clock: Callable[[], float] = time.monotonic,
             now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> GuoqRun:
    out = Path(out)
    folders.ensure_parent(out)
    out.unlink(missing_ok=True)
    start, began = now(), clock()
    timed_out, code = False, None
    try:
        code = run(command(job, source, out, budget_s), capture_output=True, text=True,
                   timeout=budget_s + KILL_GRACE_S).returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        run(["docker", "rm", "-f", f"p0e-{job}"], capture_output=True)
    wall = clock() - began
    return GuoqRun(job, budget_s, start.isoformat(), now().isoformat(), round(wall, 3), round(wall - budget_s, 3),
                   code, timed_out, str(out) if out.exists() else None)
