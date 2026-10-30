"""How much memory and CPU a QCEC check takes, by circuit size (post-tag change: the PC guard reserves it).

python -m spikes.qopt_qaoa.qcec_peak <run-folder> [--out qcec_peak.json]

Re-verifies the outputs of a development run, one circuit at a time in a fresh QCEC worker, and samples that worker's
private memory, threads and CPU while the check runs. The worker is new for every circuit, so the process's own peak
commit counter is exact for it. The table keeps the largest peak seen at each size.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

Probe = Callable[[], tuple[float, int, float]]  # private GB, threads, CPU percent (100 = one core)


@dataclass
class Peak:
    private_gb: float = 0.0
    threads: int = 0
    cores: float = 0.0


def measure(fn: Callable[[], object], *, probe: Probe, interval: float = 0.05) -> tuple[object, Peak]:
    peak, done = Peak(), threading.Event()

    def take() -> None:
        try:
            gb, threads, cpu = probe()
        except Exception:  # the process may be gone or not started; the call being measured goes on
            return
        peak.private_gb = max(peak.private_gb, gb)
        peak.threads = max(peak.threads, threads)
        peak.cores = max(peak.cores, cpu / 100.0)

    def sample() -> None:
        while not done.wait(interval):
            take()

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    try:
        value = fn()
    finally:
        done.set()
        thread.join()
    take()
    return value, peak


def worker_probe() -> Probe:
    """The shared QCEC worker of `spikes.qopt_p0.verify`, found afresh at each sample (it is replaced after a wall)."""
    import psutil
    from spikes.qopt_p0 import verify
    state: dict = {}

    def probe() -> tuple[float, int, float]:
        proc = verify._WORKER._proc
        if proc is None or proc.pid is None:
            raise RuntimeError("no worker yet")
        if state.get("pid") != proc.pid:
            state.update(pid=proc.pid, ps=psutil.Process(proc.pid))
            state["ps"].cpu_percent(None)
        ps = state["ps"]
        info = ps.memory_info()
        used = max(getattr(info, "private", 0), getattr(info, "peak_pagefile", 0), 0) or info.rss
        return used / 2**30, ps.num_threads(), ps.cpu_percent(None)

    return probe


def table(rows: list[dict]) -> dict[int, float]:
    out: dict[int, float] = {}
    for row in rows:
        out[row["size"]] = max(out.get(row["size"], 0.0), row["private_gb"])
    return dict(sorted(out.items()))


def reserve_for_size(peaks: dict[int, float], size: int) -> float:
    """The peak recorded for `size`, or for the next size down when this one was not measured, or 0."""
    known = [s for s in peaks if s <= size]
    return peaks[max(known)] if known else 0.0


def load_table(path: Path) -> dict[int, float]:
    path = Path(path)
    if not path.exists():
        return {}
    return {int(k): float(v) for k, v in json.loads(path.read_text(encoding="utf-8"))["peak_gb_by_size"].items()}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("qcec_peak.json"))
    args = parser.parse_args(argv)
    from spikes.qopt_p0 import verify
    from spikes.qopt_p0.harness import strip_measurements
    from spikes.qopt_qaoa import develop, folders, oracle
    folders.ensure_dir(args.folder / "work" / "peak")
    rows = []
    for out_file in sorted((args.folder / "work" / "out").glob("dev-*.qasm"),
                           key=lambda f: (int(f.name.split("-")[1]), f.name)):
        case = out_file.name.rsplit("-b", 1)[0]
        size = int(case.split("-")[1])
        original = strip_measurements(develop.load("dev", case))
        verify._WORKER.stop()  # a new worker, so its peak counters belong to this circuit
        began = time.monotonic()
        verdict, peak = measure(lambda: oracle.verdict(original, out_file.read_text(encoding="utf-8"),
                                                       workdir=args.folder / "work" / "peak"), probe=worker_probe())
        rows.append({"case": case, "size": size, "private_gb": round(peak.private_gb, 3), "threads": peak.threads,
                     "cores": round(peak.cores, 2), "seconds": round(time.monotonic() - began, 2),
                     "answer": verdict.answer})
        print(json.dumps(rows[-1]), flush=True)
    args.out.write_text(json.dumps({"peak_gb_by_size": table(rows), "rows": rows}, indent=1) + "\n",
                        encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
