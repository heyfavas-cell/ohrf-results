"""Run the audit in batches: python -m spikes.qopt_audit.run <out> --budget-hours 4 [--workers 3] [--start N].

Each worker is a separate process on its own shard (case index modulo the number of workers) with its own log, so
nothing is shared and a killed worker loses at most one case. `python -m spikes.qopt_audit.run <out> --report` prints
the report over every shard.

With `--findings <dir>` the coordinator triages the run as soon as the batch is logged, so no undecided output waits for
someone to start triage, and appends every lead that needs a person to `<dir>/attention.jsonl` with its filing clock.
Triage time is not batch time: the batch line (and its `wall_s`, the compute cap's measure) is written first.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Iterable

from spikes.qopt_audit import frozen
from spikes.qopt_audit.bases import load_bases
from spikes.qopt_audit.generate import Case, build, schedule
from spikes.qopt_audit.oracle import observe
from spikes.qopt_p0 import verify
from spikes.qopt_audit.tools import run_tool
from spikes.qopt_audit.triage import attention_record, needs_attention, triage_run, utc_now

BUCKETS = ((6, 10), (11, 14), (15, 18), (19, 22), (23, 10 ** 6))


def default_tools() -> dict[str, Callable[[str], str]]:
    return {tool: (lambda text, tool=tool: run_tool(tool, text)) for tool in frozen.TOOLS}


def _key(case: Case, tool: str) -> str:
    return f"{case.kind}:{case.name}:{case.seed}:{tool}"


def _qubits(qasm: str) -> int:
    return sum(int(m) for m in re.findall(r"qreg\s+\w+\[(\d+)\]", qasm))


def run_batch(cases: Iterable[Case], bases: dict[str, str], *, out: Path, budget_s: float,
              tools: dict[str, Callable[[str], str]] | None = None, now: Callable[[], str] = utc_now) -> dict:
    tools = tools or default_tools()
    out = Path(out)
    (out / "circuits").mkdir(parents=True, exist_ok=True)
    (out / "work").mkdir(parents=True, exist_ok=True)
    log = out / "log.jsonl"
    done = {l.split('"key": "')[1].split('"')[0] for l in log.read_text(encoding="utf-8").splitlines()} \
        if log.exists() else set()
    start, ran, last, stopped = time.monotonic(), 0, -1, "exhausted"
    try:
        for index, case in enumerate(cases):
            if time.monotonic() - start >= budget_s:
                stopped = "budget"
                break
            text = build(case, bases)
            name = f"{case.kind}-{case.name}-{case.seed}.qasm"
            (out / "circuits" / name).write_text(text, encoding="utf-8", newline="\n")
            for tool, fn in tools.items():
                if _key(case, tool) in done:
                    continue
                t0 = time.monotonic()
                obs = observe(text, tool, fn, workdir=out / "work")
                row = {"key": _key(case, tool), "case_kind": case.kind, "case": case.name, "seed": case.seed,
                       "tool": tool, "kind": obs.kind, "qcec": obs.qcec, "confirmations": obs.confirmations,
                       "second_opinion": obs.second_opinion, "distance": obs.distance, "signature": obs.signature,
                       "qubits": _qubits(text), "seconds": round(time.monotonic() - t0, 3), "observed_at": now()}
                with log.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
            ran, last = ran + 1, index
    finally:
        verify._WORKER.stop()  # never leave the QCEC worker behind (D-141)
    return {"cases": ran, "stopped": stopped, "last_index": last}


def _rows(log: Path) -> list[dict]:
    paths = [Path(log)] if Path(log).is_file() else sorted(Path(log).glob("**/log.jsonl"))
    return [json.loads(l) for p in paths for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def report(log: Path) -> str:
    rows = _rows(Path(log))
    lines = [f"Observations: {len(rows)}", "", "| Tool | " + " | ".join(
        ["verified", "unverified", "wrong_output", "within_tolerance", "oracle_disagreement", "crash"]) + " |",
        "|---|---|---|---|---|---|---|"]
    kinds = ["verified", "unverified", "wrong_output", "within_tolerance", "oracle_disagreement", "crash"]
    for tool in sorted({r["tool"] for r in rows}):
        count = Counter(r["kind"] for r in rows if r["tool"] == tool)
        lines.append(f"| {tool} | " + " | ".join(str(count[k]) for k in kinds) + " |")
    lines += ["", "unverified share by qubit count (QCEC could not decide, or the text was not read strictly):"]
    for low, high in BUCKETS:
        bucket = [r for r in rows if low <= r["qubits"] <= high]
        if bucket:
            share = sum(r["kind"] == "unverified" for r in bucket) / len(bucket)
            lines.append(f"- {low} to {high if high < 10 ** 6 else 'more'} qubits: {share:.1%} of {len(bucket)}")
    signatures = Counter(r["signature"] for r in rows if r["kind"] == "crash")
    lines += ["", "Distinct crash signatures:"] + [f"- {n} x {s}" for s, n in signatures.most_common()]
    for kind in ("wrong_output", "oracle_disagreement", "within_tolerance"):
        hits = [r for r in rows if r["kind"] == kind]
        lines += ["", f"{kind}: {len(hits)}"] + [
            f"- {r['case_kind']} {r['case']} seed {r['seed']} tool {r['tool']} ({r['qubits']} qubits, distance "
            f"{r['distance']})" for r in hits[:200]]
    seconds = sum(r["seconds"] for r in rows)
    lines += ["", f"Total busy time across workers: {seconds / 3600:.2f} hours"]
    return "\n".join(lines) + "\n"


def after_batch(out: Path, findings: Path) -> list[dict]:
    """Triage the run now; append the leads that need a person to the attention list and return them."""
    due = [attention_record(entry) for entry in triage_run(Path(out), Path(findings)) if needs_attention(entry)]
    if due:
        Path(findings).mkdir(parents=True, exist_ok=True)
        with (Path(findings) / "attention.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.writelines(json.dumps(record, sort_keys=True) + "\n" for record in due)
    for record in due:
        print(f"ATTENTION {record['key']} ({record['kind']}): file upstream by {record['due_by']}")
    print(f"triage: {len(due)} new lead(s) need a person")
    return due


def _used_hours(out: Path) -> float:
    path = Path(out) / "batches.jsonl"
    return sum(json.loads(l)["wall_s"] for l in path.read_text(encoding="utf-8").splitlines()) / 3600 \
        if path.exists() else 0.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--budget-hours", type=float, default=frozen.RUN_CAP_S / 3600)
    parser.add_argument("--workers", type=int, default=frozen.WORKERS)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--shard", default="")  # "k/n": internal, one worker
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--findings", default="")  # triage into this folder once the batch is logged
    args = parser.parse_args(argv)
    out = Path(args.out)
    if args.report:
        print(report(out))
        return 0
    bases = load_bases(Path(__file__).with_name("bases"))
    if args.shard:
        k, n = (int(x) for x in args.shard.split("/"))
        cases = (c for i, c in enumerate(schedule(args.start)) if i % n == k)
        print(run_batch(cases, bases, out=out / f"shard-{k}", budget_s=args.budget_hours * 3600))
        return 0
    if _used_hours(out) + args.budget_hours > frozen.COMPUTE_CAP_S / 3600:
        print("refused: this batch would pass the compute cap", file=sys.stderr)
        return 1
    if args.workers > frozen.WORKERS or args.budget_hours > frozen.RUN_CAP_S / 3600:
        print("refused: more workers or hours than registered", file=sys.stderr)
        return 1
    start, started_at = time.monotonic(), utc_now()
    procs = [subprocess.Popen([sys.executable, "-W", "ignore", "-m", "spikes.qopt_audit.run", str(out),
                               "--budget-hours", str(args.budget_hours), "--start", str(args.start),
                               "--shard", f"{k}/{args.workers}"]) for k in range(args.workers)]
    for proc in procs:
        proc.wait()
    out.mkdir(parents=True, exist_ok=True)
    with (out / "batches.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"start": args.start, "wall_s": round(time.monotonic() - start, 1),
                                 "workers": args.workers, "started_at": started_at, "ended_at": utc_now()}) + "\n")
    print(report(out))
    if args.findings:
        after_batch(out, Path(args.findings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
