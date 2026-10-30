"""The budgeted search over the pass pool: a beam search over pass sequences with random restarts.

The clock starts when the circuit is handed over and the search stops starting passes at the budget. A single pass
call is not interrupted (except PyZX, behind its wall), so `elapsed_s` and `overrun_s` are logged. The finished search
proposes its best distinct states; verifying them is outside the budget, as for GUOQ.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable

from spikes.qopt_p0.harness import cx_count
from spikes.qopt_qaoa import frozen


def gate_count(qasm: str) -> int:
    return sum(1 for line in qasm.splitlines() if line.strip() and not line.startswith(("OPENQASM", "include", "qreg")))


def score(qasm: str) -> tuple[int, int]:
    return cx_count(qasm), gate_count(qasm)


@dataclass(frozen=True)
class Proposal:
    qasm: str
    cx: int
    gates: int
    path: tuple[str, ...]


@dataclass
class SearchResult:
    proposals: list[Proposal]
    elapsed_s: float
    overrun_s: float
    calls: int
    errors: dict[str, int] = field(default_factory=dict)
    restarts: int = 0


def search(text: str, passes: dict[str, Callable[[str, int], str]], budget_s: float, *,
           clock: Callable[[], float] = time.monotonic, seed: int = 1, beam: int = frozen.SEARCH_BEAM,
           max_steps: int = frozen.SEARCH_STEPS_MAX, proposals: int = frozen.SEARCH_PROPOSALS) -> SearchResult:
    begin = clock()
    deadline = begin + budget_s
    seen: dict[str, Proposal] = {text: Proposal(text, *score(text), ())}
    errors: dict[str, int] = {}
    calls = restarts = idle = 0
    names = list(passes)
    while clock() < deadline and idle < 2:
        rng = random.Random(seed + restarts)
        order = names[:] if restarts == 0 else rng.sample(names, len(names))
        frontier = [seen[text]]
        grew = False
        for _ in range(max_steps):
            found: list[Proposal] = []
            for state in frontier:
                for name in order:
                    if clock() >= deadline:
                        break
                    calls += 1
                    try:
                        out = passes[name](state.qasm, seed + restarts)
                    except Exception:
                        errors[name] = errors.get(name, 0) + 1
                        continue
                    if out in seen:
                        continue
                    seen[out] = Proposal(out, *score(out), state.path + (name,))
                    found.append(seen[out])
                    grew = True
            if not found or clock() >= deadline:
                break
            found.sort(key=lambda p: (p.cx, p.gates))
            pool = found[:beam] if restarts == 0 else rng.sample(found[:2 * beam], min(beam, len(found[:2 * beam])))
            frontier = pool
        restarts += 1
        idle = 0 if grew else idle + 1
    best = sorted(seen.values(), key=lambda p: (p.cx, p.gates, len(p.path)))[:proposals]
    elapsed = clock() - begin
    return SearchResult(best, round(elapsed, 3), round(max(0.0, elapsed - budget_s), 3), calls, errors, restarts)


def choose(result: SearchResult, verify: Callable[[str], bool]) -> tuple[Proposal | None, int]:
    """The first proposal, best first, that `verify` accepts, and how many were tried. None is a loss."""
    for tried, proposal in enumerate(result.proposals, start=1):
        if verify(proposal.qasm):
            return proposal, tried
    return None, len(result.proposals)
