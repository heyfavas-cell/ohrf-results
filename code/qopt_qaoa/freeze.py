"""The freeze (plan, Task 11): `search_config.json` with the pool, `S*`, the search parameters and `N_heldout`.

python -m spikes.qopt_qaoa.freeze <run-folder> <search-config-id> [--write]

Everything is read from the development run files. The file records the pool, it does not change it (OD-AQ: the pool is as
the plan offers it and `passes.py` builds it). `S*` is the best single pool pass on the development set, a tie going to the
first by name. The file's sha256 is written beside it.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path

from spikes.qopt_p0.reference import Z_ALPHA, Z_BETA
from spikes.qopt_qaoa import dev_report, folders, frozen, make_qaoa, passes, sample, score

CONFIG_PATH = Path(__file__).with_name("search_config.json")
STAR_RULE = "the single pool pass with the highest geometric-mean gain on the development set; a tie goes to the first by name"
SEARCH_RULE = ("beam search over pass sequences scored by CNOT count then gate count: the first run tries the passes in pool "
               "order and keeps the best `beam` states per step; each restart (seeded by seed + restart number) tries them in "
               "a random order and keeps `beam` states sampled from the best 2 x `beam`; it ends at the budget or when two "
               "restarts in a row add no new state; the five best distinct states are verified best first")


def seconds(o: dict) -> float:
    return (datetime.fromisoformat(o["end_utc"]) - datetime.fromisoformat(o["start_utc"])).total_seconds()


def worker_seconds_per_circuit(obs: list[dict], *, config: str, star: str) -> float:
    """Mean over development circuits of the worker-seconds one circuit costs at both budgets: the GUOQ job, the search job
    (each includes its verification) and `star` (one pass call per budget, a part of a second)."""
    per: dict[str, float] = {}
    for o in obs:
        if (o["kind"] == "guoq" and o["rep"] == 0) or (o["kind"] == "search" and o["config"] == config):
            per[o["case"]] = per.get(o["case"], 0.0) + seconds(o)
        elif o["kind"] == "passes":
            spent = sum(r["seconds"] for r in o["passes"] if r["pass"] == star and r["seed"] == 1)
            per[o["case"]] = per.get(o["case"], 0.0) + 2 * spent  # at both budgets
    return sum(per.values()) / len(per)


def run_names(n: int) -> list[str]:
    return [c.name for c in make_qaoa.run_order("held_out")[:n]]


def build(obs: list[dict], *, config: dict, star: dict[str, str]) -> dict:
    stars = {int(b): name for b, name in star.items()}
    pass_obs = [o for o in obs if o["kind"] == "passes"]
    rows = dev_report.rows_for(obs, pass_obs, config["id"], stars)
    pairs = score.pairs(rows, ("guoq", frozen.B_LONG_S), ("cand", frozen.B_LONG_S))
    per = worker_seconds_per_circuit(obs, config=config["id"], star=stars[frozen.B_LONG_S])
    n = sample.n_heldout(pairs, per)
    n["smallest_gain_at_n"] = round(1 - math.exp(-(Z_ALPHA + Z_BETA) * n["s"] / math.sqrt(n["n"])), 6)  # 80% power
    return {
        "version": 1,
        "pool": list(passes.pool()),
        "s_star": star,
        "s_star_rule": STAR_RULE,
        "search": {**{k: config[k] for k in ("beam", "max_steps", "proposals", "order", "seed")}, "id": config["id"],
                   "rule": SEARCH_RULE},
        "n_heldout": {**n, "worker_seconds_per_circuit": round(per, 3), "circuits": len(rows),
                      "cap_inputs": {"held_out_cap_s": frozen.HELD_OUT_CAP_S, "workers": frozen.WORKERS_DEFAULT,
                                     "floor": frozen.HELD_OUT_MIN, "pool": sample.pool_size()}},
        "run_names": run_names(n["n"]),
    }


def write(path: Path, cfg: dict) -> Path:
    path = folders.write_text(Path(path), json.dumps(cfg, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    folders.write_text(Path(path).with_suffix(".sha256"), f"{digest}  {Path(path).name}\n")
    return Path(path)


def main(argv: list[str] | None = None) -> None:
    args = argv or sys.argv[1:]
    folder, config_id = Path(args[0]), args[1]
    config = json.loads((folder.parent / "search" / f"{config_id}.json").read_text(encoding="utf-8"))
    obs = dev_report.dev_only(dev_report.read_lines(folder / "observations.jsonl"))
    star ={str(b): t[0]["pass"] for b, t in dev_report.star_table([o for o in obs if o["kind"] == "passes"]).items()}
    cfg = build(obs, config=config, star=star)
    shown = {k: v for k, v in cfg.items() if k != "run_names"}
    print(json.dumps(shown, indent=2, sort_keys=True))
    if "--write" in args:
        print(write(CONFIG_PATH, cfg))


if __name__ == "__main__":
    main()
