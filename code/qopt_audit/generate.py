"""Seeded circuits for the audit: random circuits, boundary-angle variants of the base circuits, and the schedule.

Every circuit is a pure function of its `Case`, so a finding replays from (kind, name, seed).
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from typing import Iterator

from spikes.qopt_audit import frozen

HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
ONE_QUBIT = {"h": 0, "x": 0, "y": 0, "z": 0, "s": 0, "sdg": 0, "t": 0, "tdg": 0, "rx": 1, "ry": 1, "rz": 1,
             "u1": 1, "u2": 2, "u3": 3}
TWO_QUBIT = {"cx": 0, "cz": 0, "cy": 0, "ch": 0, "swap": 0, "crz": 1, "cu1": 1, "cu3": 3}
PARAMETERISED = re.compile(r"^(\s*)([a-z0-9]+)\(([^)]*)\)(.*)$")


@dataclass(frozen=True)
class Case:
    kind: str  # "random" or "boundary"
    name: str  # "random" or the base circuit's name
    seed: int
    base: str | None = None


def _angle(rng: random.Random) -> str:
    return repr(rng.uniform(0.0, 2 * math.pi))


def random_circuit(seed: int) -> str:
    rng = random.Random(frozen.SCHEDULE_SEED + seed)
    n = rng.randint(*frozen.RANDOM_QUBITS)
    gates = rng.randint(*frozen.RANDOM_GATES)
    lines = [f"qreg q[{n}];"]
    for _ in range(gates):
        roll = rng.random()
        if roll < 0.60:
            name = rng.choice(list(ONE_QUBIT))
            qubits = [rng.randrange(n)]
            params = ONE_QUBIT[name]
        elif roll < 0.95:
            name = rng.choice(list(TWO_QUBIT))
            qubits = rng.sample(range(n), 2)
            params = TWO_QUBIT[name]
        else:
            name, qubits, params = "ccx", rng.sample(range(n), 3), 0
        arg = f"({','.join(_angle(rng) for _ in range(params))})" if params else ""
        lines.append(f"{name}{arg} " + ",".join(f"q[{q}]" for q in qubits) + ";")
    return HEADER + "\n".join(lines) + "\n"


def boundary_variant(base_text: str, seed: int) -> str:
    """The base circuit with each rotation argument, at random, replaced by a boundary value (tiny, quarter turn,
    binary fraction, near a boundary); the gate skeleton is unchanged."""
    rng = random.Random(frozen.SCHEDULE_SEED + seed)
    out = []
    for line in base_text.splitlines():
        match = PARAMETERISED.match(line)
        if match is None:
            out.append(line)
            continue
        indent, name, args, rest = match.groups()
        new = []
        for arg in args.split(","):
            if rng.random() < frozen.BOUNDARY_RATE:
                value = rng.choice(frozen.BOUNDARY_ANGLES) * rng.choice((1, -1))
                arg = repr(value)
            new.append(arg)
        out.append(f"{indent}{name}({','.join(new)}){rest}")
    return "\n".join(out) + "\n"


def schedule(start: int = 0) -> Iterator[Case]:
    """Case i is random when i is even and a boundary variant of a base circuit when i is odd, seed i // 2 + 1."""
    from pathlib import Path
    names = sorted(p.stem for p in (Path(__file__).with_name("bases")).glob("*.qasm"))
    i = start
    while True:
        seed = i // 2 + 1
        if i % 2 == 0:
            yield Case("random", "random", seed)
        else:
            yield Case("boundary", names[(i // 2) % len(names)], seed, base=names[(i // 2) % len(names)])
        i += 1


def build(case: Case, bases: dict[str, str]) -> str:
    if case.kind == "random":
        return random_circuit(case.seed)
    return boundary_variant(bases[case.base], case.seed)
