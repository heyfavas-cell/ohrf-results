"""Task 10, development: GUOQ, pool-pass and search batches on the 36 development circuits.

python -m spikes.qopt_qaoa.develop guoq --budgets 15 300 --batch dev-guoq-1 [--repeats 1] [--first-rep 0] [--sample]
python -m spikes.qopt_qaoa.develop passes --batch dev-passes-1
python -m spikes.qopt_qaoa.develop search --budgets 15 --config <config.json> --batch dev-search-1

Run data goes to `<root>/` (default `.local/p0e/run`, outside the repository): `observations.jsonl`, `runs.jsonl`,
`attention.jsonl`, `heartbeat.json`, `reg/` and `refusals.jsonl`. Only development circuits are touched here. A pass or
search job does its work in a worker process (`worker.py`); this module verifies the outputs, one QCEC check at a time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

from spikes.qopt_p0.harness import cx_count, strip_measurements
from spikes.qopt_qaoa import folders, frozen, guoq, make_qaoa, oracle, qcec_peak, run, slots, triage

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PEAK_TABLE = HERE / "qcec_peak.json"
ROOT_DEFAULT = REPO / ".local" / "p0e" / "run"
PASS_SEEDS = [1, 2, 3, 4, 5]
PASSES_PLAN_S = 240  # planning figure for one circuit's pass job; the batch's real length is logged
_QCEC = threading.Lock()  # the QCEC worker is one child process on one pipe; one check at a time


def load(set_name: str, name: str) -> str:
    return (HERE / "circuits" / set_name / f"{name}.qasm").read_text(encoding="utf-8")


def dev_names() -> list[str]:
    return sorted((c.name for c in make_qaoa.cases("dev")), key=lambda n: (int(n.split("-")[1]), n))


def repeat_sample() -> list[str]:
    """The 12 circuits whose GUOQ runs are repeated (plan: three runs of B_long): every third in size order."""
    return dev_names()[::3]


def guoq_jobs(budgets: list[int], *, repeats: int = 1, first_rep: int = 0, only: list[str] | None = None) -> list[dict]:
    names = sorted(c.name for c in make_qaoa.cases("dev"))
    if only:
        names = [n for n in names if n in only]
    return [{"set": "dev", "name": n, "budget": b, "rep": r} for b in budgets for n in names
            for r in range(first_rep, first_rep + repeats)]


def passes_jobs(only: list[str] | None = None, pool: str | None = None) -> list[dict]:
    extra = {"pool": pool} if pool else {}
    return [{"set": "dev", "name": n, "kind": "passes", "budget": PASSES_PLAN_S, **extra} for n in dev_names()
            if not only or n in only]


def search_jobs(budgets: list[int], config: dict, *, only: list[str] | None = None) -> list[dict]:
    names = [n for n in dev_names() if not only or n in only]
    return [{"set": "dev", "name": n, "kind": "search", "budget": b, "config": config} for b in budgets for n in names]


def planned_seconds(jobs: list[dict], *, overhead_s: int = 3) -> float:
    return sum(j["budget"] + overhead_s for j in jobs) / frozen.WORKERS_DEFAULT


def check(original: str, text: str, *, workdir: Path, judge: Callable, classify: Callable) -> dict:
    """Verify `text` against `original` (QCEC, then the newer QCEC) and classify a failure; one check at a time."""
    folders.ensure_dir(Path(workdir) / "qcec")
    out = {"verified": False, "answer": "", "lead_kind": None, "witnessed": False}
    with _QCEC:
        verdict = judge(original, text, workdir=Path(workdir) / "qcec")
        out.update(verified=verdict.verified, answer=verdict.answer, checker=verdict.checker, recheck=verdict.recheck)
        if verdict.contradicted:
            out["lead_kind"] = "recheck_contradiction"
        elif verdict.answer == "not_equivalent":
            lead = classify(original, text, workdir=Path(workdir) / "qcec")
            if lead is not None:
                out.update(lead_kind=lead.kind, witnessed=oracle.witnessed(lead.gaps), lead_second=lead.second)
    return out


def guoq_job(job: dict, *, workdir: Path, run_guoq: Callable = guoq.run_guoq, judge: Callable = oracle.verdict,
             rebase: Callable[[str], str] | None = None, load: Callable[[str, str], str] = load,
             classify: Callable = oracle.classify) -> dict:
    """One GUOQ run on one circuit, its output verified (QCEC, then the newer QCEC), a failure classified."""
    if rebase is None:
        from spikes.qopt_p0.guoq_inputs import rebase
    workdir = Path(workdir)
    name, budget, rep = job["name"], job["budget"], job["rep"]
    tag = f"{name}-b{budget}-r{rep}"
    original = strip_measurements(load(job["set"], name))
    src, out = workdir / "in" / f"{tag}.qasm", workdir / "out" / f"{tag}.qasm"
    folders.write_text(src, rebase(original))
    ran = run_guoq(tag, src, out, budget)
    result = {"kind": "guoq", "case": name, "budget": budget, "rep": rep, "input_cx": cx_count(original),
              "output_cx": None, "verified": False, "answer": "no_output", "guoq_start_utc": ran.start_utc,
              "guoq_end_utc": ran.end_utc, "wall_s": ran.wall_s, "overhead_s": ran.overhead_s,
              "exit_code": ran.exit_code, "timed_out": ran.timed_out, "lead_kind": None, "witnessed": False}
    if ran.output is None:
        return result
    text = Path(ran.output).read_text(encoding="utf-8")
    result["output_cx"] = cx_count(text)
    result.update(check(original, text, workdir=workdir, judge=judge, classify=classify))
    return result


def spawn(spec: dict, *, workdir: Path, timeout_s: float, run: Callable = subprocess.run) -> dict:
    """Run one worker job in its own process with single-thread limits and return its result."""
    from spikes.qopt_qaoa import worker
    tag = spec["tag"]
    spec_path = folders.write_text(Path(workdir) / "specs" / f"{tag}.json", json.dumps(spec))
    result_path = Path(workdir) / "specs" / f"{tag}.result.json"
    result_path.unlink(missing_ok=True)
    env = {**os.environ, **worker.THREAD_LIMITS, "PYTHONPATH": str(REPO)}
    try:
        done = run([sys.executable, "-m", "spikes.qopt_qaoa.worker", str(spec_path), str(result_path)], env=env,
                   cwd=str(REPO), capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"worker {tag} timed out after {timeout_s:.0f} s") from None
    if done.returncode != 0:
        raise RuntimeError(f"worker {tag} failed: {done.stderr[-600:]}")
    return json.loads(result_path.read_text(encoding="utf-8"))


def passes_job(job: dict, *, workdir: Path, spawn: Callable = spawn, judge: Callable = oracle.verdict,
               load: Callable[[str, str], str] = load, classify: Callable = oracle.classify, **_) -> dict:
    """Every pool pass alone on one circuit (the seeded pass at five seeds); every output verified."""
    workdir = Path(workdir)
    name = job["name"]
    original = strip_measurements(load(job["set"], name))
    spec = {"job": "passes", "set": job["set"], "case": name, "tag": f"passes-{name}", "seeds": PASS_SEEDS,
            "out_dir": str(workdir / "passes" / name)}
    if job.get("pool"):
        spec["pool"] = job["pool"]
    if job.get("names"):
        spec["names"] = job["names"]  # the held-out S* arm runs the one frozen pass
    result = spawn(spec, workdir=workdir, timeout_s=1800)
    cache: dict[str, dict] = {}
    leads = []
    for row in result["rows"]:
        if not row.get("file"):
            row.update(verified=False, answer="no_output", lead_kind=None, witnessed=False)
            continue
        text = Path(row["file"]).read_text(encoding="utf-8")
        key = hashlib.sha256(text.encode()).hexdigest()
        if key not in cache:
            cache[key] = check(original, text, workdir=workdir, judge=judge, classify=classify)
        row.update(cache[key])
        if row["lead_kind"]:
            leads.append({"pass": row["pass"], "lead_kind": row["lead_kind"], "witnessed": row["witnessed"],
                          "duplicate_of": triage.match_known(row["pass"], original)})
    return {"kind": "passes", "case": name, "input_cx": result["input_cx"], "start_cx": result["start_cx"],
            "passes": result["rows"], "leads": leads}


def search_job(job: dict, *, workdir: Path, spawn: Callable = spawn, judge: Callable = oracle.verdict,
               load: Callable[[str, str], str] = load, classify: Callable = oracle.classify, **_) -> dict:
    """The budgeted search on one circuit; its proposals verified best first, the first verified is the output."""
    workdir = Path(workdir)
    name, budget, config = job["name"], job["budget"], job["config"]
    original = strip_measurements(load(job["set"], name))
    tag = f"search-{config['id']}-{name}-b{budget}"
    spec = {"job": "search", "set": job["set"], "case": name, "tag": tag, "budget": budget, "seed": config.get("seed", 1),
            "beam": config.get("beam", frozen.SEARCH_BEAM), "max_steps": config.get("max_steps", frozen.SEARCH_STEPS_MAX),
            "proposals": config.get("proposals", frozen.SEARCH_PROPOSALS), "order": config.get("order"),
            "out_dir": str(workdir / "search" / tag)}
    result = spawn(spec, workdir=workdir, timeout_s=budget + 900)
    chosen, tried, leads = None, 0, []
    for proposal in result["proposals"]:
        tried += 1
        verdict = check(original, Path(proposal["file"]).read_text(encoding="utf-8"), workdir=workdir, judge=judge,
                        classify=classify)
        if verdict["verified"]:
            chosen = proposal
            break
        if verdict["lead_kind"]:
            leads.append({"path": proposal["path"], "lead_kind": verdict["lead_kind"], "witnessed": verdict["witnessed"],
                          "duplicate_of": None})
    return {"kind": "search", "case": name, "budget": budget, "config": config["id"], "seed": result["seed"],
            "input_cx": result["input_cx"], "start_cx": result["start_cx"],
            "cx": chosen["cx"] if chosen else None, "verified": chosen is not None, "tried": tried,
            "chosen_path": chosen["path"] if chosen else None,
            "best_unverified_cx": result["proposals"][0]["cx"] if result["proposals"] else None,
            "elapsed_s": result["elapsed_s"], "overrun_s": result["overrun_s"], "calls": result["calls"],
            "errors": result["errors"], "restarts": result["restarts"], "cpu_s": result["cpu_s"], "leads": leads}


def execute(job: dict, *, workdir: Path) -> dict:
    kind = job.get("kind", "guoq")
    return {"guoq": guoq_job, "passes": passes_job, "search": search_job}[kind](job, workdir=workdir)


def reserve_for(job: dict, peaks: dict[int, float]) -> float:
    """The QCEC peak (GB) the guard keeps free for this job's check: the largest measured at its size."""
    return qcec_peak.reserve_for_size(peaks, int(job["name"].split("-")[1]))


def to_records(observations: list[dict]) -> list[dict]:
    records = []
    for o in observations:
        base = f"{o['kind']}-{o['case']}-b{o.get('budget', 0)}-r{o.get('rep', 0)}-{o.get('config', '')}"
        if o.get("lead_kind"):
            records.append(triage.lead_record(base, o["lead_kind"], seen=run.utc_now(), witnessed=o.get("witnessed", False),
                                              duplicate_of=None, case=o["case"], budget=o.get("budget")))
        for lead in o.get("leads", []):
            where = lead.get("pass") or "-".join(lead.get("path", [])) or "input"
            records.append(triage.lead_record(f"{base}-{where}", lead["lead_kind"], seen=run.utc_now(),
                                              witnessed=lead.get("witnessed", False),
                                              duplicate_of=lead.get("duplicate_of"), case=o["case"],
                                              budget=o.get("budget"), where=where))
    return records


def require_recheck() -> None:
    if not os.environ.get("QCEC_LATEST_PYTHON"):  # without it the 3.11.0 re-check is skipped and the rule is not met
        raise SystemExit("QCEC_LATEST_PYTHON is not set: the QCEC 3.11.0 re-check would not run")


def run_jobs(jobs: list[dict], *, batch_id: str, phase: str, folder: Path, board: Path) -> dict:
    """One batch through the runner: the guard, the observations log, triage and the heartbeat."""
    folder = Path(folder)
    folders.ensure_dir(folder)
    if any(j.get("kind", "guoq") == "guoq" for j in jobs):
        guoq.ensure_image()
    override = run.guard_override(folder, phase, batch_id)
    guard = slots.Guard(folder / "reg", board, folder / "refusals.jsonl", min_free_gb=override.get("free_memory_min_gb"))
    workdir = folder / "work"
    peaks = qcec_peak.load_table(PEAK_TABLE)
    return run.run_batch(run.Batch(batch_id, phase, jobs), lambda job: execute(job, workdir=workdir),
                         guard=guard, folder=folder, planned_s=planned_seconds(jobs), to_records=to_records,
                         reserve_for=lambda job: reserve_for(job, peaks), board=board)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["guoq", "passes", "search"])
    parser.add_argument("--budgets", type=int, nargs="+", default=[frozen.B_SHORT_S])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--first-rep", type=int, default=0)
    parser.add_argument("--sample", action="store_true", help="only the 12 repeat circuits")
    parser.add_argument("--explore", action="store_true", help="passes: the exploratory passes, not the pool (never counted)")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    parser.add_argument("--board", type=Path, required=True)
    args = parser.parse_args(argv)
    require_recheck()
    only = repeat_sample() if args.sample else args.only
    if args.what == "guoq":
        jobs = guoq_jobs(args.budgets, repeats=args.repeats, first_rep=args.first_rep, only=only)
    elif args.what == "passes":
        jobs = passes_jobs(only=only, pool="exploratory" if args.explore else None)
    else:
        jobs = search_jobs(args.budgets, json.loads(args.config.read_text(encoding="utf-8")), only=only)
    result = run_jobs(jobs, batch_id=args.batch, phase="dev", folder=args.root, board=args.board)
    print(json.dumps({"batch": args.batch, "jobs": len(jobs), **{k: (len(v) if isinstance(v, list) else v)
                                                              for k, v in result.items()}}))


if __name__ == "__main__":
    main()
