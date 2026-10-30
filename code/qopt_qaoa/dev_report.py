"""The development report: tables from the run files. Development numbers only; an outcome is never decided here.

python -m spikes.qopt_qaoa.dev_report <run-folder> > report.md
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from spikes.qopt_p0.reference import log_sd
from spikes.qopt_qaoa import frozen, score

SHORT, LONG = frozen.B_SHORT_S, frozen.B_LONG_S


def read_lines(path: Path) -> list[dict]:
    path = Path(path)
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def size_of(case: str) -> int:
    return int(case.split("-")[1])


def geomean(values: list[float]) -> float:
    return math.exp(sum(math.log(v) for v in values) / len(values))


def guoq_cx(obs: list[dict]) -> dict[tuple[str, int], list[int | None]]:
    """(case, budget) -> the CNOT counts of its runs, in repeat order, None where not verified."""
    out: dict[tuple[str, int], list] = defaultdict(list)
    for o in sorted((o for o in obs if o["kind"] == "guoq"), key=lambda o: o["rep"]):
        out[(o["case"], o["budget"])].append(o["output_cx"] if o["verified"] else None)
    return out


def pass_effective(rows: list[dict], name: str, budget: int, input_cx: int) -> int | None:
    """A pass's verified CNOT count at a budget, or None. A pass slower than the budget has no output at it. A seeded
    pass takes seeds in order while their summed time fits the budget, and keeps the best (compute-matched)."""
    spent, best = 0.0, None
    for r in sorted((r for r in rows if r["pass"] == name), key=lambda r: r["seed"]):
        spent += r["seconds"]
        if spent > budget:
            break
        if r["verified"] and r["cx"] is not None:
            best = r["cx"] if best is None else min(best, r["cx"])
    return best


def star_table(pass_obs: list[dict]) -> dict[int, list[dict]]:
    """Per budget, every pass with its geometric-mean gain over the input (an unverified or too-slow output scores the
    input) and its verified share, best first."""
    out = {}
    names = sorted({r["pass"] for o in pass_obs for r in o["passes"]})
    for budget in (SHORT, LONG):
        table = []
        for name in names:
            ratios, ok = [], 0
            for o in pass_obs:
                cx = pass_effective(o["passes"], name, budget, o["input_cx"])
                ok += cx is not None
                ratios.append((o["input_cx"] if cx is None else cx) / o["input_cx"])
            table.append({"pass": name, "gain": round(1 - geomean(ratios), 5), "verified_share": round(ok / len(ratios), 3)})
        out[budget] = sorted(table, key=lambda t: (-t["gain"], t["pass"]))  # a tie goes to the first by name (OD-AQ)
    return out


def rows_for(obs: list[dict], pass_obs: list[dict], config: str, stars: dict[int, str]) -> list[score.Row]:
    guoq = guoq_cx(obs)
    by_case = {(o["case"], o["budget"]): o for o in obs if o["kind"] == "search" and o["config"] == config}
    passes = {o["case"]: o for o in pass_obs}
    rows = []
    for case in sorted({c for c, _ in by_case}, key=lambda c: (size_of(c), c)):
        first = [by_case[(case, b)] for b in (SHORT, LONG) if (case, b) in by_case]
        if len(first) < 2 or case not in passes or any((case, b) not in guoq for b in (SHORT, LONG)):
            continue
        inp = first[0]["input_cx"]
        rows.append(score.Row(
            case, inp,
            {b: guoq[(case, b)][0] for b in (SHORT, LONG)},
            {b: by_case[(case, b)]["cx"] for b in (SHORT, LONG)},
            {b: pass_effective(passes[case]["passes"], stars[b], b, inp) for b in (SHORT, LONG)}, size_of(case)))
    return rows


def repeat_spread(obs: list[dict]) -> dict:
    """GUOQ's own run-to-run noise at B_long: for circuits with at least two verified runs, the pooled standard
    deviation of the log CNOT count, and how many circuits differ at all."""
    logs = [[math.log(c) for c in runs if c] for (case, b), runs in guoq_cx(obs).items() if b == LONG and len(runs) > 1]
    logs = [l for l in logs if len(l) > 1]
    if not logs:
        return {"circuits": 0}
    var = statistics.mean(statistics.variance(l) for l in logs)
    return {"circuits": len(logs), "pooled_sd_log": round(math.sqrt(var), 5),
            "circuits_that_differ": sum(1 for l in logs if max(l) - min(l) > 1e-12)}


def shares_by_size(records: list[tuple[str, bool]]) -> dict[int, str]:
    tally: dict[int, list] = defaultdict(lambda: [0, 0])
    for case, ok in records:
        tally[size_of(case)][0] += ok
        tally[size_of(case)][1] += 1
    return {s: f"{a}/{b}" for s, (a, b) in sorted(tally.items())}


def compute_hours(runs: list[dict]) -> dict:
    by_phase: dict[str, float] = defaultdict(float)
    for r in runs:
        by_phase[r["phase"]] += r["seconds"]
    return {**{k: round(v / 3600, 3) for k, v in by_phase.items()}, "total": round(sum(by_phase.values()) / 3600, 3)}


def dev_only(obs: list[dict]) -> list[dict]:
    """The run folder also holds the held-out run from Task 12; the development report never reads it."""
    return [o for o in obs if o["case"].startswith("dev-")]


def render(folder: Path) -> str:
    obs, runs = dev_only(read_lines(folder / "observations.jsonl")), read_lines(folder / "runs.jsonl")
    pass_obs = [o for o in obs if o["kind"] == "passes"]
    configs = sorted({o["config"] for o in obs if o["kind"] == "search"})
    lines = ["# Development report (development numbers; no outcome is decided on this set)", ""]
    lines += ["## Compute (wall-clock hours of runs, against the 30)", f"{compute_hours(runs)}", ""]
    g = [o for o in obs if o["kind"] == "guoq"]
    lines += ["## GUOQ"]
    for b in (SHORT, LONG):
        use = [o for o in g if o["budget"] == b and o["rep"] == 0]
        if use:
            ratios = [(o["output_cx"] if o["verified"] else o["input_cx"]) / o["input_cx"] for o in use]
            lines.append(f"- B={b}: {len(use)} circuits, geometric-mean ratio to input {geomean(ratios):.4f}, verified "
                         f"{sum(o['verified'] for o in use)}/{len(use)}; by size {shares_by_size([(o['case'], o['verified']) for o in use])}")
    lines += [f"- repeat spread at B_long: {repeat_spread(obs)}", ""]
    if pass_obs:
        stars = star_table(pass_obs)
        lines += ["## Pool passes alone (gain over input; an unverified or too-slow output scores the input)"]
        for b in (SHORT, LONG):
            lines.append(f"- B={b}: " + "; ".join(f"{t['pass']} {t['gain']:+.3f} ({t['verified_share']:.0%})" for t in stars[b]))
        lines.append(f"- passes verified by size: " + str(shares_by_size(
            [(o["case"], r["verified"]) for o in pass_obs for r in o["passes"] if r["file"]])))
        star_names = {b: stars[b][0]["pass"] for b in (SHORT, LONG)}
        lines += [f"- proposed S*: {star_names}", ""]
        for config in configs:
            rows = rows_for(obs, pass_obs, config, star_names)
            if len(rows) < 2:
                continue
            d = score.decide(rows)
            pr = score.pairs(rows, ("guoq", LONG), ("cand", LONG))
            lines += [f"## Search config `{config}` ({len(rows)} circuits)",
                      f"- Q (cand@300 vs GUOQ@300): {d['Q']}", f"- T (cand@15 vs GUOQ@300): {d['T']}",
                      f"- S (cand vs S*): long {d['S_long']}; short {d['S_short']}",
                      f"- s (log sd of cand/GUOQ at B_long): {log_sd(pr):.4f}; smallest gain this size finds: {d['smallest_gain']}",
                      f"- verified shares: {d['verified_shares']}", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    print(render(Path(sys.argv[1])))
