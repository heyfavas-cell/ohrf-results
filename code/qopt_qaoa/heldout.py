"""Task 12: the held-out run, once, on the frozen `run_names` (plan, "Power" and Task 12).

python -m spikes.qopt_qaoa.heldout plan
python -m spikes.qopt_qaoa.heldout run --block 1 --board <SESSIONS.md> [--resume]

Each circuit gets five jobs: GUOQ and the candidate at both budgets, and `S*` (the one frozen pass). The circuits are the
first `N_heldout` of the stratified order, run in blocks of that order with size 22 last (it needs the most free memory).
The gate refuses to start unless the qaoa-prereg anchor is complete, `search_config.json` matches its hash and the
`qaoa-freeze` tag exists. A crash is rerun with `--resume`, which skips the jobs already logged and retunes nothing.
Nothing here reads a held-out result to choose anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Callable

from spikes.qopt_qaoa import develop, freeze, frozen

SET = "held_out"
BLOCK_SIZE = 26
STAR_PLAN_S = 10  # planning figure for the S* job (one pass call and its check); the batch's real length is logged
ANCHOR_DEFAULT = develop.ROOT_DEFAULT / "anchor.json"


class Gate(RuntimeError):
    """The held-out run may not start."""


def tag_exists(tag: str) -> bool:
    return subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd=develop.REPO,
                          capture_output=True).returncode == 0


def gate(anchor_path: Path, *, config_path: Path = freeze.CONFIG_PATH, tag_exists: Callable[[str], bool] = tag_exists) -> None:
    anchor = json.loads(Path(anchor_path).read_text(encoding="utf-8"))
    if anchor.get("status") != "complete":
        raise Gate("the qaoa-prereg anchor is not complete")
    if not anchor.get("bitcoin_attestations"):
        raise Gate("no Bitcoin attestation is recorded in the anchor")
    config_path = Path(config_path)
    recorded = config_path.with_suffix(".sha256").read_text(encoding="utf-8").split()[0]
    if hashlib.sha256(config_path.read_bytes()).hexdigest() != recorded:
        raise Gate("search_config.json does not match its recorded hash")
    if not tag_exists("qaoa-freeze"):
        raise Gate("the qaoa-freeze tag is missing")


def jobs_for(names: list[str], cfg: dict, *, set_name: str = SET, budgets: tuple[int, int] = frozen.BUDGETS_S) -> list[dict]:
    short, long = min(budgets), max(budgets)
    star = sorted(set(cfg["s_star"].values()))
    jobs: list[dict] = []
    for name in names:
        for budget in (long, short):
            jobs.append({"set": set_name, "name": name, "budget": budget, "rep": 0})
            jobs.append({"set": set_name, "name": name, "kind": "search", "budget": budget, "config": cfg["search"]})
        jobs.append({"set": set_name, "name": name, "kind": "passes", "budget": STAR_PLAN_S, "names": star})
    return jobs


def blocks(names: list[str], size: int = BLOCK_SIZE) -> list[list[str]]:
    """The run order cut into blocks of about equal length, size 22 in the last blocks."""
    def cut(items: list[str]) -> list[list[str]]:
        if not items:
            return []
        parts = math.ceil(len(items) / size)
        base, extra = divmod(len(items), parts)
        out, at = [], 0
        for i in range(parts):
            step = base + (i < extra)
            out.append(items[at:at + step])
            at += step
        return out

    return cut([n for n in names if "-22-" not in n]) + cut([n for n in names if "-22-" in n])


def key_of_job(job: dict) -> tuple:
    kind = job.get("kind", "guoq")
    if kind == "guoq":
        return ("guoq", job["name"], job["budget"], job["rep"])
    if kind == "search":
        return ("search", job["name"], job["budget"], job["config"]["id"])
    return ("passes", job["name"])


def key_of_observation(o: dict) -> tuple:
    if o["kind"] == "guoq":
        return ("guoq", o["case"], o["budget"], o["rep"])
    if o["kind"] == "search":
        return ("search", o["case"], o["budget"], o["config"])
    return ("passes", o["case"])


def pending(jobs: list[dict], observations: list[dict]) -> list[dict]:
    done = {key_of_observation(o) for o in observations}
    return [j for j in jobs if key_of_job(j) not in done]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["plan", "run"])
    parser.add_argument("--block", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--board", type=Path)
    parser.add_argument("--root", type=Path, default=develop.ROOT_DEFAULT)
    parser.add_argument("--anchor", type=Path, default=ANCHOR_DEFAULT)
    parser.add_argument("--smoke", nargs="*", help="dev circuits through this path, short budgets, own folder; no gate")
    args = parser.parse_args(argv)
    cfg = json.loads(freeze.CONFIG_PATH.read_text(encoding="utf-8"))
    cut = blocks(cfg["run_names"])
    if args.what == "plan":
        for i, block in enumerate(cut, start=1):
            print(f"block {i}: {len(block)} circuits, sizes {sorted({int(n.split('-')[1]) for n in block})}")
        return
    develop.require_recheck()
    if args.smoke is not None:
        if args.root == develop.ROOT_DEFAULT:
            args.root = develop.REPO / ".local" / "p0e" / "smoke-heldout"  # never the run folder
        jobs = jobs_for(args.smoke, cfg, set_name="dev", budgets=(10, 20))
        batch_id, phase = "heldout-smoke", "dev"
    else:
        gate(args.anchor)
        if not args.block or not 1 <= args.block <= len(cut):
            raise SystemExit(f"--block must be 1 to {len(cut)}")
        jobs = jobs_for(cut[args.block - 1], cfg)
        batch_id, phase = f"held-{args.block}", "held_out"
        if args.resume:
            from spikes.qopt_qaoa import dev_report
            jobs = pending(jobs, dev_report.read_lines(args.root / "observations.jsonl"))
            runs = dev_report.read_lines(args.root / "runs.jsonl")
            batch_id += f"-resume-{1 + sum(1 for r in runs if r['batch'].startswith(batch_id + '-resume'))}"
            if not jobs:
                print(json.dumps({"batch": batch_id, "jobs": 0, "note": "nothing left to run"}))
                return
    result = develop.run_jobs(jobs, batch_id=batch_id, phase=phase, folder=args.root, board=args.board)
    print(json.dumps({"batch": batch_id, "jobs": len(jobs), **{k: (len(v) if isinstance(v, list) else v)
                                                              for k, v in result.items()}}))


if __name__ == "__main__":
    main(sys.argv[1:])
