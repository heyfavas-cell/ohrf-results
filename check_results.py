#!/usr/bin/env python3
"""Recompute the qaoa result from data/qaoa/results.csv, with the standard library only. Run from the repo root:

    python check_results.py

It applies the pre-registered rule, checks every number against the reported figures, checks the circuits against the
manifest, the frozen search configuration against its timestamped hash, and every file against SHA256SUMS.
"""
import csv
import hashlib
import json
import math
import random
import re
import sys
from pathlib import Path

SEED, N = 20261028, 10000  # frozen in the pre-registered parameters
GAIN_MIN, TIME_RATIO_MAX, TIME_UPPER_MAX = 0.01, 1.00, 1.01
EXPECTED = {"Q": (1.032364, 1.021317, 1.042799), "T": (1.050212, 1.04025, 1.059597),
            "S long": (0.948082, 0.932678, 0.962612), "S short": (0.964473, 0.950914, 0.977162),
            "S* vs GUOQ@300": (1.088897, 1.078958, 1.099336)}


def geomean(pairs):
    logs = [math.log(max(after, 1) / before) for before, after in pairs if before > 0]
    return math.exp(sum(logs) / len(logs))


def interval(pairs):
    rng = random.Random(SEED)
    stats = sorted(geomean([rng.choice(pairs) for _ in pairs]) for _ in range(N))
    return round(stats[int(0.025 * N)], 6), round(stats[int(0.975 * N) - 1], 6)


def stats(rows, first, second):
    pairs = [(int(r[first] or r["input_cx"]), int(r[second] or r["input_cx"])) for r in rows]  # unverified scores the input
    return (round(geomean(pairs), 6), *interval(pairs))


def text_hash(text):
    keep = [line for line in text.splitlines() if not re.match(r"\s*(measure|barrier|creg)\b", line)]
    return hashlib.sha256(("\n".join(keep) + "\n").encode()).hexdigest()


def main():
    ok = True
    rows = list(csv.DictReader(open("data/qaoa/results.csv", encoding="utf-8")))
    rows.sort(key=lambda r: (int(r["size"]), r["case"]))
    got = {"Q": stats(rows, "guoq_300", "cand_300"), "T": stats(rows, "guoq_300", "cand_15"),
           "S long": stats(rows, "star", "cand_300"), "S short": stats(rows, "star", "cand_15"),
           "S* vs GUOQ@300": stats(rows, "guoq_300", "star")}
    for name, value in got.items():
        same = value == EXPECTED[name]
        ok &= same
        print(f"{name}: ratio {value[0]}, 95% interval {value[1]} to {value[2]}  {'matches' if same else 'DIFFERS FROM THE REPORT'}")
    q, t = got["Q"], got["T"]
    pass_q = 1 - q[0] >= GAIN_MIN and 1 - q[2] > 0 and 1 - got["S long"][2] > 0
    pass_t = t[0] <= TIME_RATIO_MAX and t[2] <= TIME_UPPER_MAX and 1 - got["S short"][2] > 0
    print(f"circuits {len(rows)}; pass Q {pass_q}, pass T {pass_t}; outcome {'pass' if pass_q or pass_t else 'null'}")
    ok &= not (pass_q or pass_t) and len(rows) == 145

    manifest = json.load(open("data/qaoa/held_out_manifest.json", encoding="utf-8"))
    bad = [c for c, m in manifest.items() if text_hash(Path(f"data/qaoa/circuits/{c}.qasm").read_text(encoding="utf-8")) != m["sha"]]
    print(f"circuits against the manifest: {len(manifest) - len(bad)} of {len(manifest)} match")
    ok &= not bad

    stamped = Path("reports/qaoa-explore-anchors/qaoa-freeze.txt").read_text(encoding="utf-8").split()[-1]
    config = hashlib.sha256(Path("preregistrations/search_config.json").read_bytes()).hexdigest()
    print(f"frozen search configuration against its timestamped hash: {'matches' if config == stamped else 'DIFFERS'}")
    ok &= config == stamped

    # Result 2: the audit's rule (code/qopt_audit/ledger.py) on its ledger. A row counts as a new wrong output only if
    # every evidence condition holds and it duplicates no known issue; the verdict is fallback when none counts.
    ledger = [json.loads(line) for line in Path("data/audit/ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    counted = [r for r in ledger if r["cls"] == "wrong_output" and r["proved_twice"] and r["second_opinion_ok"]
               and r["tolerance_ok"] and r["reproduces_latest"] and not r["lead"] and r["duplicate_of"] is None]
    dups = sum(1 for r in ledger if r["duplicate_of"])
    print(f"audit ledger: {len(ledger)} rows, {dups} duplicates of known issues, {len(counted)} counted; verdict {'fallback' if not counted else 'needs the full rule'}")
    ok &= len(ledger) == 172 and dups == 170 and not counted

    sums = [line.split("  ", 1) for line in Path("SHA256SUMS").read_text(encoding="utf-8").splitlines()]
    wrong = [n for h, n in sums if hashlib.sha256(Path(n).read_bytes()).hexdigest() != h]
    print(f"SHA256SUMS: {len(sums) - len(wrong)} of {len(sums)} match")
    ok &= not wrong
    print("ALL CHECKS PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
