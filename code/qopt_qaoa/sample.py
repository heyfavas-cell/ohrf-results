"""N_heldout: how many held-out circuits are run, fixed at `qaoa-freeze` from the development set (plan, "Power")."""
from __future__ import annotations

import math

from spikes.qopt_p0.reference import circuits_needed, log_sd
from spikes.qopt_qaoa import frozen


def pool_size() -> int:
    return len(frozen.SIZES) * frozen.HELD_OUT_POOL_PER_SIZE


def n_cap(worker_seconds_per_circuit: float, *, workers: int = frozen.WORKERS_DEFAULT) -> int:
    """Circuits whose measured cost fits the held-out cap."""
    return math.floor(frozen.HELD_OUT_CAP_S * workers / worker_seconds_per_circuit)


def n_heldout(pairs: list[tuple[int, int]], worker_seconds_per_circuit: float) -> dict:
    """`pairs` are (GUOQ, candidate) CNOT counts at `B_long` on the development set. Returns N and its inputs."""
    s = log_sd(pairs)
    needed = circuits_needed(s, effect=frozen.POWER_EFFECT)
    cap = n_cap(worker_seconds_per_circuit)
    n = min(max(needed, frozen.HELD_OUT_MIN), cap, pool_size())
    return {"s": s, "needed": needed, "cap": cap, "n": n, "floor_met": n >= frozen.HELD_OUT_MIN}
