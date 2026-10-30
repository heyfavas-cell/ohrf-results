"""One development job in its own process, so a pass or search gets one core and its own clock.

python -m spikes.qopt_qaoa.worker <spec.json> <result.json>

`passes`: every pool pass alone on one circuit (the seeded pass at several seeds). `search`: the budgeted beam search
on one circuit. Outputs are written as files and described in the result; verifying them is the parent's job (it owns
the one QCEC worker). Single-thread limits are set by the parent through the environment.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Callable

from spikes.qopt_p0.harness import cx_count, strip_measurements
from spikes.qopt_qaoa import folders, frozen, passes, search

THREAD_LIMITS = {name: "1" for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                        "NUMEXPR_NUM_THREADS", "RAYON_NUM_THREADS")}


def _load(spec: dict) -> tuple[str, str]:
    from spikes.qopt_qaoa import develop
    original = strip_measurements(develop.load(spec["set"], spec["case"]))
    return original, passes.to_basis(original)


def _cpu() -> float:
    return time.process_time()


def run_passes(spec: dict, *, pool: dict | None = None, clock: Callable[[], float] = time.monotonic,
               start_text: tuple[str, str] | None = None) -> dict:
    walled = None
    if pool is None and spec.get("pool") == "exploratory":
        from spikes.qopt_qaoa import exploratory
        pool = exploratory.pool()
    elif pool is None:
        walled = passes.WalledPyzx()
        pool = passes.pool(walled)
    original, start = start_text or _load(spec)
    out = folders.ensure_dir(spec["out_dir"])
    names = spec.get("names") or list(pool)
    rows = []
    try:
        for name in names:
            for seed in (spec.get("seeds", [1]) if name in passes.SEEDED else [1]):
                began, cpu_began = clock(), _cpu()
                text, error = None, None
                try:
                    text = pool[name](start, seed)
                except Exception as exc:
                    error = f"{type(exc).__name__}: {str(exc)[:160]}"
                row = {"pass": name, "seed": seed, "seconds": round(clock() - began, 3),
                       "cpu_s": round(_cpu() - cpu_began, 3), "error": error, "cx": None, "gates": None, "file": None}
                if text is not None:
                    path = folders.write_text(out / f"{name}-s{seed}.qasm", text)
                    row.update(cx=cx_count(text), gates=search.gate_count(text), file=str(path))
                rows.append(row)
    finally:
        if walled is not None:
            walled.stop()
    return {"kind": "passes", "case": spec["case"], "input_cx": cx_count(original), "start_cx": cx_count(start),
            "rows": rows}


def run_search(spec: dict, *, pool: dict | None = None, clock: Callable[[], float] = time.monotonic,
               start_text: tuple[str, str] | None = None) -> dict:
    walled = None
    if pool is None:
        walled = passes.WalledPyzx()
        pool = passes.pool(walled)
    original, start = start_text or _load(spec)
    out = folders.ensure_dir(spec["out_dir"])
    names = spec.get("order") or list(pool)
    cpu_began = _cpu()
    try:
        result = search.search(start, {n: pool[n] for n in names}, spec["budget"], clock=clock, seed=spec.get("seed", 1),
                               beam=spec.get("beam", frozen.SEARCH_BEAM),
                               max_steps=spec.get("max_steps", frozen.SEARCH_STEPS_MAX),
                               proposals=spec.get("proposals", frozen.SEARCH_PROPOSALS))
    finally:
        if walled is not None:
            walled.stop()
    proposals = []
    for rank, proposal in enumerate(result.proposals):
        path = folders.write_text(out / f"proposal-{rank}.qasm", proposal.qasm)
        proposals.append({"rank": rank, "cx": proposal.cx, "gates": proposal.gates, "path": list(proposal.path),
                          "file": str(path)})
    return {"kind": "search", "case": spec["case"], "budget": spec["budget"], "seed": spec.get("seed", 1),
            "input_cx": cx_count(original), "start_cx": cx_count(start), "elapsed_s": result.elapsed_s,
            "overrun_s": result.overrun_s, "calls": result.calls, "errors": result.errors,
            "restarts": result.restarts, "cpu_s": round(_cpu() - cpu_began, 3), "proposals": proposals}


def main(argv: list[str] | None = None) -> None:
    spec_path, result_path = (Path(a) for a in (argv or sys.argv[1:3]))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    result = {"passes": run_passes, "search": run_search}[spec["job"]](spec)
    folders.write_text(result_path, json.dumps(result))


if __name__ == "__main__":
    main()
