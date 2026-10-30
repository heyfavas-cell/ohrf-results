"""The M2 portfolio, the depth-3 headroom probe, the statistics and the pre-registered decision rule (D-084)."""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, replace
from itertools import permutations

from spikes.qopt_p0.frozen import (ADJUSTED_LOWER, BOOTSTRAP_N, BOOTSTRAP_SEED, GO, GO_ADJUSTED, GO_LOWER,
                                   HEADROOM_LOWER, HEADROOM_MIN)
from spikes.qopt_p0.harness import TOOLS

CHAINS2 = tuple(permutations(TOOLS, 2))
CHAINS3 = tuple(permutations(TOOLS, 3))


@dataclass(frozen=True)
class Row:
    name: str
    family: str
    baseline: int   # best of qiskit (5 seeds plus extra seeds that match the portfolio's compute) and the better tket config, verified
    portfolio: int  # best verified of the 4 tools and the 12 two-tool chains
    deep: int       # best verified of the portfolio and the 24 three-tool chains
    guoq: int | None = None  # GUOQ's verified count; kept apart from the three above (D-137)
    baseline5: int | None = None  # the plain baseline, 5 Qiskit seeds and both tket configs, before compute matching
    extra_seeds: int = 0          # Qiskit seeds added to `baseline` to match the portfolio's compute (D-138)
    baseline_seconds: float = 0.0
    portfolio_seconds: float = 0.0


def reduction(*, baseline: int, best: int) -> float:
    return 0.0 if baseline == 0 else round((baseline - best) / baseline, 6)


def m2_summary(rows: list[Row]) -> dict:
    reds = [reduction(baseline=r.baseline, best=r.portfolio) for r in rows]
    return {
        "circuits": len(rows),
        "median_reduction": round(statistics.median(reds), 6),
        "geomean_ratio": round(geomean_ratio([(r.baseline, r.portfolio) for r in rows]), 6),
        "wins": sum(r.portfolio < r.baseline for r in rows),
        "ties": sum(r.portfolio == r.baseline for r in rows),
        "losses": sum(r.portfolio > r.baseline for r in rows),
    }


def geomean_ratio(pairs: list[tuple[int, int]]) -> float:
    """Geometric mean of after/before over pairs with a non-zero before."""
    logs = [math.log(max(after, 1) / before) for before, after in pairs if before > 0]
    return math.exp(sum(logs) / len(logs)) if logs else 1.0


def bootstrap_ci(pairs: list[tuple[int, int]], *, seed: int = BOOTSTRAP_SEED, n: int = BOOTSTRAP_N) -> tuple[float, float]:
    rng = random.Random(seed)
    stats = sorted(geomean_ratio([rng.choice(pairs) for _ in pairs]) for _ in range(n))
    return round(stats[int(0.025 * n)], 6), round(stats[int(0.975 * n) - 1], 6)


def bootstrap_median_ci(values: list[float], *, seed: int = BOOTSTRAP_SEED, n: int = BOOTSTRAP_N) -> tuple[float, float]:
    """95% percentile bootstrap interval of the median, resampling circuits."""
    rng = random.Random(seed)
    stats = sorted(statistics.median(rng.choice(values) for _ in values) for _ in range(n))
    return round(stats[int(0.025 * n)], 6), round(stats[int(0.975 * n) - 1], 6)


def matched_runs(budget_s: float, run_one, *, cap: int, first_seed: int) -> list[tuple[int, str, float]]:
    """Extra seeded runs of one tool until their seconds cover `budget_s`: the baseline's share of the compute the
    portfolio spent on its extra tools. `run_one(seed)` returns (qasm, seconds). Stops at `cap` runs."""
    runs, spent = [], 0.0
    while spent < budget_s and len(runs) < cap:
        seed = first_seed + len(runs)
        qasm, seconds = run_one(seed)
        runs.append((seed, qasm, seconds))
        spent += seconds
    return runs


def guoq_gap(rows: list[Row]) -> dict | None:
    """GUOQ against the portfolio on the circuits where GUOQ has a verified output; below 1 means GUOQ is better."""
    pairs = [(r.portfolio, r.guoq) for r in rows if r.guoq is not None]
    if not pairs:
        return None
    return {"circuits": len(pairs), "geomean_ratio": round(geomean_ratio(pairs), 6), "ci95": bootstrap_ci(pairs),
            "guoq_wins": sum(g < p for p, g in pairs), "ties": sum(g == p for p, g in pairs),
            "guoq_losses": sum(g > p for p, g in pairs)}


def with_guoq(rows: list[Row]) -> list[Row]:
    """Rows with GUOQ folded into the baseline and the portfolio: context only, it never sets the decision (D-137)."""
    return [r if r.guoq is None else
            replace(r, baseline=min(r.baseline, r.guoq), portfolio=min(r.portfolio, r.guoq),
                    deep=min(r.deep, r.guoq))
            for r in rows]


def decide(median_reduction: float, *, lower: float, headroom_gain: float = 0.0, headroom_lower: float = 0.0) -> str:
    """The pre-registered rule (D-084, D-137). `lower` is the 95% bootstrap lower bound of the median reduction;
    `headroom_gain` is 1 minus the depth-3 geometric-mean ratio and `headroom_lower` the lower bound of that gain.
    A tier needs the point estimate to clear its threshold and the lower bound to clear its margin."""
    if median_reduction >= GO and lower >= GO_LOWER:
        return "go"
    if median_reduction >= GO_ADJUSTED and lower > ADJUSTED_LOWER:
        return "go-adjusted"
    if headroom_gain >= HEADROOM_MIN and headroom_lower > HEADROOM_LOWER:
        return "go-verified-only"
    return "reshape"
