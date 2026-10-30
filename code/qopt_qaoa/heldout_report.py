"""Reports for the held-out run: a descriptive summary per batch, and the one decision at the end.

python -m spikes.qopt_qaoa.heldout_report batch <run-folder> <batch-id>
python -m spikes.qopt_qaoa.heldout_report final <run-folder>

A batch summary never states the outcome: the rule is applied once, to all the circuits, in `final`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from spikes.qopt_p0.reference import log_sd
from spikes.qopt_qaoa import dev_report, frozen, score

SHORT, LONG = frozen.B_SHORT_S, frozen.B_LONG_S


def held(obs: list[dict]) -> list[dict]:
    return [o for o in obs if o["case"].startswith("held_out-")]


def _arm_values(obs: list[dict], star: str) -> dict[str, list[tuple[str, int, int | None]]]:
    """arm -> (case, input_cx, verified CNOT count or None) for each circuit."""
    arms: dict[str, list] = {f"{side}@{b}": [] for side in ("guoq", "cand") for b in (SHORT, LONG)}
    arms["star"] = []
    for o in obs:
        if o["kind"] == "guoq" and o["rep"] == 0:
            arms[f"guoq@{o['budget']}"].append((o["case"], o["input_cx"], o["output_cx"] if o["verified"] else None))
        elif o["kind"] == "search":
            arms[f"cand@{o['budget']}"].append((o["case"], o["input_cx"], o["cx"] if o["verified"] else None))
        elif o["kind"] == "passes":
            rows = [r for r in o["passes"] if r["pass"] == star]
            arms["star"].append((o["case"], o["input_cx"], rows[0]["cx"] if rows and rows[0]["verified"] else None))
    return arms


def _leads(obs: list[dict]) -> int:
    return sum(bool(o.get("lead_kind")) + len(o.get("leads", [])) for o in obs)


def memory_waits(all_obs: list[dict], refusals: list[dict], batch_id: str) -> dict:
    """Per batch: the jobs the guard refused at least once, and how long each waited (first refusal to start)."""
    from datetime import datetime
    started = {o["job"]: datetime.fromisoformat(o["start_utc"]) for o in all_obs if o.get("job", "").startswith(batch_id + "-")}
    mine = [r for r in refusals if r["job"].startswith(batch_id + "-")]
    first: dict[str, datetime] = {}
    for r in mine:
        at = datetime.fromisoformat(r["refused_utc"])
        first[r["job"]] = min(first.get(r["job"], at), at)
    waits = [(started[j] - at).total_seconds() for j, at in first.items() if j in started]
    return {"jobs_that_waited": len(first), "refusals": len(mine), "total_wait_s": round(sum(waits), 1),
            "max_wait_s": round(max(waits, default=0.0), 1)}


def progress(folder: Path, cfg: dict) -> dict:
    """Held-out hours used, the projection to all planned circuits, and the headroom under the caps."""
    folder = Path(folder)
    runs = dev_report.read_lines(folder / "runs.jsonl")
    obs = held(dev_report.read_lines(folder / "observations.jsonl"))
    done_batches = {r["batch"] for r in runs if r["phase"] == "held_out"}
    done = {o["case"] for o in obs if o["batch"] in done_batches}
    used = sum(r["seconds"] for r in runs if r["phase"] == "held_out") / 3600
    total = sum(r["seconds"] for r in runs) / 3600
    planned = cfg["n_heldout"]["n"]
    per = used / len(done) if done else 0.0
    projected = used + max(0, planned - len(done)) * per
    return {"held_out_hours_used": round(used, 3), "circuits_done": len(done), "circuits_planned": planned,
            "projected_held_out_hours": round(projected, 3), "projected_total_hours": round(total - used + projected, 3),
            "held_out_cap_hours": frozen.HELD_OUT_CAP_S // 3600, "reserve_hours": 8,
            "total_cap_hours": frozen.COMPUTE_CAP_S // 3600}


def batch_summary(all_obs: list[dict], batch_id: str, cfg: dict, refusals: list[dict] | None = None) -> str:
    obs = [o for o in held(all_obs) if o["batch"] == batch_id]
    star = cfg["s_star"][str(LONG)]
    cases = sorted({o["case"] for o in obs})
    lines = [f"## Batch {batch_id}: {len(cases)} circuits, {len(obs)} job results (descriptive only; the rule is applied once, at the end)"]
    for arm, values in _arm_values(obs, star).items():
        if not values:
            continue
        ratios = [(cx if cx is not None else inp) / inp for _, inp, cx in values]
        ok = sum(cx is not None for _, _, cx in values)
        lines.append(f"- {arm}: {ok}/{len(values)} verified, ratio {dev_report.geomean(ratios):.4f} (unverified scores the input)")
    guoq = [o for o in obs if o["kind"] == "guoq"]
    search = [o for o in obs if o["kind"] == "search"]
    lines.append(f"- GUOQ: timeouts {sum(bool(o['timed_out']) for o in guoq)}, bad exits {sum(o['exit_code'] not in (0, None) for o in guoq)}, "
                 f"max overhead {max((o['overhead_s'] for o in guoq), default=0)} s, max wall {max((o['wall_s'] for o in guoq), default=0)} s")
    if search:
        lines.append(f"- candidate: max overrun {max(o.get('overrun_s', 0) for o in search)} s, "
                     f"search errors {sum(sum(o.get('errors', {}).values()) for o in search)}")
    lines.append(f"- leads: {_leads(obs)}")
    if refusals is not None:
        lines.append(f"- memory waits: {memory_waits(all_obs, refusals, batch_id)}")
    return "\n".join(lines)


def final(folder: Path, cfg: dict) -> str:
    folder = Path(folder)
    obs = held(dev_report.read_lines(folder / "observations.jsonl"))
    runs = dev_report.read_lines(folder / "runs.jsonl")
    pass_obs = [o for o in obs if o["kind"] == "passes"]
    stars = {SHORT: cfg["s_star"][str(SHORT)], LONG: cfg["s_star"][str(LONG)]}
    rows = dev_report.rows_for(obs, pass_obs, cfg["search"]["id"], stars)
    planned = cfg["n_heldout"]["n"]
    lines = ["# Held-out result (decided once, on the frozen run names)", "",
             f"- circuits with every arm: {len(rows)} of {planned} planned",
             f"- compute (hours): {dev_report.compute_hours([r for r in runs if r['phase'] == 'held_out'])}"]
    if len(rows) < 2:
        return "\n".join(lines + ["- too few circuits to apply the rule"])
    d = score.decide(rows)
    pr = score.pairs(rows, ("guoq", LONG), ("cand", LONG))
    lines += [f"- outcome: {d['outcome']}", f"- Q (cand@300 vs GUOQ@300): {d['Q']}", f"- T (cand@15 vs GUOQ@300): {d['T']}",
              f"- S (cand vs S*): long {d['S_long']}; short {d['S_short']}",
              f"- S* alone vs GUOQ@300: {d['star_vs_guoq_long']}; at 15 s: {d['star_vs_guoq_short']}",
              f"- pass_q {d['pass_q']}, pass_t {d['pass_t']}",
              f"- s on this sample {log_sd(pr):.4f}; smallest gain it finds {d['smallest_gain']}",
              f"- verified shares: {d['verified_shares']}; below the {frozen.VERIFIED_FLOOR:.0%} floor: {d['below_verified_floor']}"]
    arms = _arm_values(obs, stars[LONG])
    for arm, values in arms.items():
        lines.append(f"- {arm} verified by size: " + str(dev_report.shares_by_size([(c, cx is not None) for c, _, cx in values])))
    ok = {c for c, _, cx in arms["guoq@15"] if cx is not None}
    for arm in ("guoq@300", "cand@15", "cand@300", "star"):
        ok &= {c for c, _, cx in arms[arm] if cx is not None}
    only = [r for r in rows if r.name in ok]
    if len(only) > 1:
        v = score.decide(only)
        lines.append(f"- verified-only sensitivity row ({len(only)} circuits with every arm verified): outcome {v['outcome']}; "
                     f"Q {v['Q']}; T {v['T']}")
    lines.append(f"- leads: {_leads(obs)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    args = argv or sys.argv[1:]
    from spikes.qopt_qaoa import freeze
    cfg = json.loads(freeze.CONFIG_PATH.read_text(encoding="utf-8"))
    folder = Path(args[1])
    if args[0] == "batch":
        print(batch_summary(dev_report.read_lines(folder / "observations.jsonl"), args[2], cfg,
                            refusals=dev_report.read_lines(folder / "refusals.jsonl")))
        print(f"- progress: {progress(folder, cfg)}")
    else:
        print(final(folder, cfg))


if __name__ == "__main__":
    main()
