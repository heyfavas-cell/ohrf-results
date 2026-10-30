"""The batch runner: compute cap, PC guard, UTC-stamped observations, triage as each batch is logged, the heartbeat.

A batch is a list of jobs; `execute(job)` does one job and returns a dict of its results. The runner stamps the UTC
start and end of every job, appends one line per job to `observations.jsonl`, appends the batch's length to
`runs.jsonl` (the compute line against the 30 hours), triages the batch, and writes the heartbeat.
"""
from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from spikes.qopt_qaoa import folders, frozen, heartbeat, slots, triage


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def used_seconds(runs: Path, phase: str | None = None) -> float:
    if not Path(runs).exists():
        return 0.0
    rows = [json.loads(l) for l in Path(runs).read_text(encoding="utf-8").splitlines() if l.strip()]
    return sum(r["seconds"] for r in rows if phase is None or r["phase"] == phase)


def allowance_s(folder: Path, phase: str) -> float:
    """Seconds a recorded decision adds to one phase's cap (`<folder>/allowance.json`); never to the total or run cap."""
    path = Path(folder) / "allowance.json"
    if not path.exists():
        return 0.0
    grant = json.loads(path.read_text(encoding="utf-8"))
    return float(grant["extra_s"]) if grant.get("phase") == phase else 0.0


def guard_override(folder: Path, phase: str, batch_id: str) -> dict:
    """A recorded, operational override for matching batches (`<folder>/guard_override.json`): the free-memory margin
    (`free_memory_min_gb`) and the number of jobs run at once (`workers`). It never touches frozen.py or the other caps;
    deleting the file restores the frozen values."""
    path = Path(folder) / "guard_override.json"
    if not path.exists():
        return {}
    grant = json.loads(path.read_text(encoding="utf-8"))
    if grant.get("phase") != phase or not batch_id.startswith(grant.get("batch_prefix", "\0")):
        return {}
    out = {"decision": grant.get("decision")}
    if "free_memory_min_gb" in grant:
        out["free_memory_min_gb"] = float(grant["free_memory_min_gb"])
    if "workers" in grant:
        out["workers"] = max(1, min(int(grant["workers"]), frozen.WORKERS_IDLE_MAX))
    return out


def may_start(runs: Path, phase: str, planned_s: float, extra_s: float = 0.0) -> tuple[bool, str]:
    caps = {"dev": frozen.DEV_CAP_S, "held_out": frozen.HELD_OUT_CAP_S}
    if planned_s > frozen.RUN_CAP_S:
        return False, f"a batch of {planned_s / 3600:.1f} h is over the {frozen.RUN_CAP_S // 3600} h run cap"
    if used_seconds(runs) + planned_s > frozen.COMPUTE_CAP_S:
        return False, "the 30 hour compute cap would be passed"
    if phase in caps and used_seconds(runs, phase) + planned_s > caps[phase] + extra_s:
        return False, f"the {phase} cap of {caps[phase] // 3600} h would be passed"
    return True, "ok"


@dataclass
class Batch:
    batch_id: str
    phase: str  # step0, dev, held_out
    jobs: list


def run_batch(batch: Batch, execute: Callable[[object], dict], *, guard: slots.Guard, folder: Path,
              planned_s: float, to_records: Callable[[list[dict]], list[dict]] = lambda obs: [],
              reserve_for: Callable[[object], float] = lambda job: 0.0,
              board: Path | None = None, now: Callable[[], datetime] = utc_now,
              sleep: Callable[[float], None] = time.sleep, wait_s: float = 30.0, max_wait_rounds: int = 120) -> dict:
    folder = Path(folder)
    folders.ensure_dir(folder)
    extra = allowance_s(folder, batch.phase)
    ok, why = may_start(folder / "runs.jsonl", batch.phase, planned_s, extra_s=extra)
    if not ok:
        raise RuntimeError(f"batch {batch.batch_id} not started: {why}")
    if extra and not may_start(folder / "runs.jsonl", batch.phase, planned_s)[0]:  # it starts only because of the allowance
        grant = json.loads((folder / "allowance.json").read_text(encoding="utf-8"))
        with (folder / "allowances.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"utc": now().isoformat(), "batch": batch.batch_id, "phase": batch.phase,
                                     "decision": grant.get("decision"), "extra_s": extra, "planned_s": planned_s,
                                     "used_before_s": used_seconds(folder / "runs.jsonl", batch.phase)}) + "\n")
    override = guard_override(folder, batch.phase, batch.batch_id)
    if override:  # recorded in runs.jsonl (a note row, no compute) and in guard_overrides.jsonl
        stamp = now().isoformat()
        text = json.dumps({"batch": batch.batch_id, "phase": "note", "start_utc": stamp, "end_utc": stamp, "seconds": 0,
                           "note": f"guard override applied to {batch.batch_id}: {json.dumps(override)}"})
        with (folder / "runs.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")
        with (folder / "guard_overrides.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"utc": stamp, "batch": batch.batch_id, "phase": batch.phase, **override}) + "\n")
    workers = override.get("workers", frozen.WORKERS_IDLE_MAX)
    started = now()
    observations: list[dict] = []

    def one(item):
        index, job = item
        name = f"{batch.batch_id}-{index}"
        for _ in range(max_wait_rounds):
            reserve = reserve_for(job)
            admitted, reason = guard.admit(name, reserve)
            if admitted:
                break
            sleep(wait_s)
        else:
            raise RuntimeError(f"job {name} never admitted: {reason}")
        guard.register(name, os.getpid(), reserve_gb=reserve)
        begin = now()
        try:
            result = execute(job)
        finally:
            guard.release(name)
        obs = {"batch": batch.batch_id, "job": name, "start_utc": begin.isoformat(), "end_utc": now().isoformat(),
               **result}
        with log_lock, (folder / "observations.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(obs) + "\n")  # logged the moment the job ends, so a later crash loses nothing
        return obs

    log_lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for obs in pool.map(one, list(enumerate(batch.jobs))):
            observations.append(obs)
    ended = now()
    with (folder / "runs.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"batch": batch.batch_id, "phase": batch.phase, "start_utc": started.isoformat(),
                                 "end_utc": ended.isoformat(), "seconds": (ended - started).total_seconds()}) + "\n")
    beat = folder / "heartbeat.json"
    heartbeat.write(beat, batch_end=ended)
    new_leads = triage.triage_batch(to_records(observations), folder / "attention.jsonl")
    heartbeat.write(beat, triage_end=now())
    if board is not None:
        heartbeat.check(beat, board, now=now())
    return {"observations": len(observations), "new_leads": new_leads, "strays": guard.strays()}
