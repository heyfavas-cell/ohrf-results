"""Re-check every verified output with a newer QCEC (after QCEC#1100: a false `equivalent` fixed only in 3.11.0).

The run log keeps the input circuits but not the tools' outputs, so the re-check has two steps in two environments:

    python -m spikes.qopt_audit.recheck emit <run> <out>        # pinned tools: regenerate each verified output
    python -m spikes.qopt_audit.recheck check <out> [--workers 3]  # newer QCEC: re-decide each pair
    python -m spikes.qopt_audit.recheck report <out>

`check` uses the audit's own decision procedure (`oracle._decide`), so only the QCEC version differs. Outputs are
regenerated, not replayed: every tool runs with the audit's fixed seed, but a contradiction is first re-checked with
the pinned QCEC to rule out a regenerated output that differs from the one the audit verified.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Callable

from spikes.qopt_audit.oracle import _decide
from spikes.qopt_audit.run import _rows
from spikes.qopt_p0 import verify
from spikes.qopt_p0.verify import VERIFIED

UNCONFIRMED = ("no_information", "probably_equivalent", "probably_not_equivalent", "hard_timeout", "worker_died",
               "qcec_error", "strict_parse")


def _safe(key: str) -> str:
    return key.replace(":", "_")


def _done(path: Path) -> set[str]:
    return {json.loads(l)["key"] for l in path.read_text(encoding="utf-8").splitlines() if l.strip()} \
        if path.exists() else set()


def _default_tool(tool: str, text: str) -> str:
    from spikes.qopt_audit.tools import run_tool
    return run_tool(tool, text)


def emit(run: Path, out: Path, *, tool: Callable[[str, str], str] = _default_tool) -> dict:
    """Write the input and the regenerated output of every verified observation, one line per pair in pairs.jsonl."""
    run, out = Path(run), Path(out)
    (out / "pairs").mkdir(parents=True, exist_ok=True)
    manifest = out / "pairs.jsonl"
    done = _done(manifest)
    circuits = {p.name: p for p in run.glob("shard-*/circuits/*.qasm")}
    emitted = errors = 0
    for row in _rows(run):
        if row["kind"] != "verified" or row["key"] in done:
            continue
        line = {"key": row["key"], "tool": row["tool"], "qubits": row["qubits"], "old": row["qcec"],
                "original": f"pairs/{_safe(row['key'])}.in.qasm", "output": f"pairs/{_safe(row['key'])}.out.qasm"}
        try:
            source = circuits[f"{row['case_kind']}-{row['case']}-{row['seed']}.qasm"].read_text(encoding="utf-8")
            text = tool(row["tool"], source)
        except Exception as exc:  # a tool that no longer runs is recorded, not retried
            line["error"] = f"{type(exc).__name__}: {exc}"[:200]
            errors += 1
        else:
            (out / line["original"]).write_text(source, encoding="utf-8", newline="\n")
            (out / line["output"]).write_text(text, encoding="utf-8", newline="\n")
            emitted += 1
        with manifest.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(line, sort_keys=True) + "\n")
        done.add(row["key"])
    return {"emitted": emitted, "errors": errors}


def check(out: Path, *, shard: str = "0/1") -> dict:
    """Re-decide this shard's pairs (index modulo n) with whatever QCEC this interpreter has; resumable by key."""
    from mqt import qcec
    out = Path(out)
    k, n = (int(x) for x in shard.split("/"))
    log = out / f"checks-{k}.jsonl"
    done = _done(log)
    (out / "work").mkdir(exist_ok=True)
    pairs = [json.loads(l) for l in (out / "pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    checked = 0
    try:
        for index, pair in enumerate(pairs):
            if index % n != k or "error" in pair or pair["key"] in done:
                continue
            t0 = time.monotonic()
            answer, checker = _decide((out / pair["original"]).read_text(encoding="utf-8"),
                                      (out / pair["output"]).read_text(encoding="utf-8"), workdir=out / "work")
            with log.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps({"key": pair["key"], "answer": answer, "checker": checker,
                                         "seconds": round(time.monotonic() - t0, 3),
                                         "qcec_version": qcec.__version__}, sort_keys=True) + "\n")
            checked += 1
    finally:
        verify._WORKER.stop()
    return {"checked": checked}


def report(out: Path) -> str:
    out = Path(out)
    pairs = {p["key"]: p for p in (json.loads(l) for l in (out / "pairs.jsonl").read_text(encoding="utf-8")
                                   .splitlines() if l.strip())}
    checks = [json.loads(l) for p in sorted(out.glob("checks-*.jsonl"))
              for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    status = Counter("confirmed" if c["answer"] in VERIFIED else
                     "unconfirmed" if c["answer"] in UNCONFIRMED else "contradicted" for c in checks)
    errors = sum("error" in p for p in pairs.values())
    lines = [f"Pairs: {len(pairs)} ({errors} could not be regenerated); checked: {len(checks)}",
             f"QCEC versions: {sorted({c['qcec_version'] for c in checks})}",
             f"confirmed: {status['confirmed']}", f"contradicted: {status['contradicted']}",
             f"unconfirmed: {status['unconfirmed']}", "", "| Tool | confirmed | contradicted | unconfirmed |",
             "|---|---|---|---|"]
    for tool in sorted({pairs[c["key"]]["tool"] for c in checks}):
        mine = Counter("confirmed" if c["answer"] in VERIFIED else "unconfirmed" if c["answer"] in UNCONFIRMED
                       else "contradicted" for c in checks if pairs[c["key"]]["tool"] == tool)
        lines.append(f"| {tool} | {mine['confirmed']} | {mine['contradicted']} | {mine['unconfirmed']} |")
    lines += ["", "Contradicted (re-check each with the pinned QCEC before reading it as a missed wrong output):"]
    lines += [f"- {c['key']} ({pairs[c['key']]['qubits']} qubits, {c['answer']} by {c['checker']})"
              for c in checks if c["answer"] not in VERIFIED and c["answer"] not in UNCONFIRMED]
    lines += ["", f"Busy time: {sum(c['seconds'] for c in checks) / 3600:.2f} hours"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("emit", "check", "report"))
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--shard", default="")  # "k/n": internal, one worker
    args = parser.parse_args(argv)
    if args.step == "emit":
        print(emit(Path(args.paths[0]), Path(args.paths[1])))
    elif args.step == "report":
        print(report(Path(args.paths[0])))
    elif args.shard:
        print(check(Path(args.paths[0]), shard=args.shard))
    else:
        procs = [subprocess.Popen([sys.executable, "-W", "ignore", "-m", "spikes.qopt_audit.recheck", "check",
                                   args.paths[0], "--shard", f"{k}/{args.workers}"]) for k in range(args.workers)]
        for proc in procs:
            proc.wait()
        print(report(Path(args.paths[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
