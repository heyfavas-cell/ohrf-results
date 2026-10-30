"""The ratios, the bootstrap, the rule and its outcome (plan, "The rule").

A row holds one circuit's CNOT counts: `input`, and for each of `guoq`, `cand` and `star` (the best single pass) a
mapping from budget in seconds to the CNOT count of a verified output, or None when no output was verified. An
unverified output scores the circuit's input count, on both sides. Ratios are second over first, as in
`portfolio.geomean_ratio(pairs)` with pairs (first, second).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from spikes.qopt_p0.portfolio import bootstrap_ci, geomean_ratio
from spikes.qopt_p0.reference import Z_ALPHA, Z_BETA, log_sd
from spikes.qopt_qaoa import frozen

SHORT, LONG = frozen.B_SHORT_S, frozen.B_LONG_S


@dataclass(frozen=True)
class Row:
    name: str
    input: int
    guoq: dict
    cand: dict
    star: dict
    size: int = 0


def effective(row: Row, side: str, budget: int) -> int:
    value = getattr(row, side).get(budget)
    return row.input if value is None else value


def pairs(rows: list[Row], first: tuple[str, int], second: tuple[str, int]) -> list[tuple[int, int]]:
    return [(effective(r, *first), effective(r, *second)) for r in rows]


def stats(pr: list[tuple[int, int]]) -> dict:
    """Geometric-mean ratio second/first with its 95% bootstrap interval; the gain is 1 - ratio."""
    ratio = geomean_ratio(pr)
    low, high = bootstrap_ci(pr, seed=frozen.BOOTSTRAP_SEED, n=frozen.BOOTSTRAP_N)
    return {"ratio": round(ratio, 6), "ci95": (low, high), "gain": round(1 - ratio, 6),
            "gain_lower": round(1 - high, 6), "n": len(pr)}


def meets_quality(s: dict) -> bool:
    return s["gain"] >= frozen.GAIN_MIN and s["gain_lower"] > frozen.GAIN_LOWER


def meets_time(s: dict) -> bool:
    return s["ratio"] <= frozen.TIME_RATIO_MAX and s["ci95"][1] <= frozen.TIME_RATIO_UPPER_MAX


def beats(s: dict) -> bool:
    return s["gain_lower"] > 0


def verified_shares(rows: list[Row]) -> dict:
    out = {}
    for side in ("guoq", "cand", "star"):
        for b in (SHORT, LONG):
            out[f"{side}@{b}"] = round(sum(getattr(r, side).get(b) is not None for r in rows) / len(rows), 4)
    return out


def smallest_gain(pr: list[tuple[int, int]]) -> float | None:
    """The smallest true gain this sample finds with 80% power: (z_alpha + z_beta) * s / sqrt(n)."""
    if len(pr) < 2:
        return None
    return round(1 - math.exp(-(Z_ALPHA + Z_BETA) * log_sd(pr) / math.sqrt(len(pr))), 6)


def decide(rows: list[Row]) -> dict:
    """The outcome on a set of rows. `pass`: (Q) or (T), each with (S) at the same budget. Otherwise `single-pass`
    when the best single pass alone meets (Q) or (T), else `null`. A pass takes precedence over single-pass."""
    q = stats(pairs(rows, ("guoq", LONG), ("cand", LONG)))
    t = stats(pairs(rows, ("guoq", LONG), ("cand", SHORT)))
    s_long = stats(pairs(rows, ("star", LONG), ("cand", LONG)))
    s_short = stats(pairs(rows, ("star", SHORT), ("cand", SHORT)))
    star_q = stats(pairs(rows, ("guoq", LONG), ("star", LONG)))
    star_t = stats(pairs(rows, ("guoq", LONG), ("star", SHORT)))
    pass_q = meets_quality(q) and beats(s_long)
    pass_t = meets_time(t) and beats(s_short)
    single = meets_quality(star_q) or meets_time(star_t)
    outcome = "pass" if (pass_q or pass_t) else ("single-pass" if single else "null")
    shares = verified_shares(rows)
    both = [r for r in rows if all(getattr(r, s).get(LONG) is not None for s in ("guoq", "cand"))]
    return {"outcome": outcome, "Q": q, "T": t, "S_long": s_long, "S_short": s_short, "star_vs_guoq_long": star_q,
            "star_vs_guoq_short": star_t, "pass_q": pass_q, "pass_t": pass_t, "verified_shares": shares,
            "below_verified_floor": any(v < frozen.VERIFIED_FLOOR for k, v in shares.items() if k.startswith(("guoq", "cand"))),
            "verified_only_Q": stats(pairs(both, ("guoq", LONG), ("cand", LONG))) if len(both) > 1 else None,
            "smallest_gain": smallest_gain(pairs(rows, ("guoq", LONG), ("cand", LONG))), "circuits": len(rows)}
